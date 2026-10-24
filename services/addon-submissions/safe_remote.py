import io
import ipaddress
import json
import re
import socket
import ssl
import time
import warnings
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import urllib3
from PIL import Image, UnidentifiedImageError


class InvalidSubmission(ValueError):
    pass


def public_url(value, manifest=False):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048:
        raise InvalidSubmission('Enter a valid public HTTPS URL.')
    if re.search(r'[\s\x00-\x1f\x7f\\]', value):
        raise InvalidSubmission('URLs cannot contain spaces or control characters.')
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
        if parsed.scheme != 'https' or parsed.port not in (None, 443) or not host:
            raise ValueError()
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise ValueError()
        if not re.fullmatch(r'[a-z0-9.-]+', host) or '.' not in host:
            raise ValueError()
        if host.endswith(('.local', '.internal', '.localhost', '.test', '.invalid')):
            raise ValueError()
        if host in {'admin.stremioaddonmanager.org', 'stremioaddonmanager.org', 'www.stremioaddonmanager.org'}:
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and (not address.is_global or address.is_multicast or address.is_reserved or host == '104.168.83.194'):
            raise InvalidSubmission('Private, reserved and local server addresses are not allowed.')
        if manifest and not parsed.path.endswith('/manifest.json'):
            raise InvalidSubmission('The URL must end in /manifest.json.')
        return urlunsplit(('https', host, quote(unquote(parsed.path or '/'), safe='/~:@!$&\'()*+,;=-._'), '', ''))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, InvalidSubmission):
            raise
        raise InvalidSubmission('Use a public HTTPS URL without credentials, query parameters or fragments.') from None


def public_addresses(host):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses:
        raise InvalidSubmission('This hostname could not be resolved.')
    for address in addresses:
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global or parsed.is_multicast or parsed.is_reserved or address == '104.168.83.194':
            raise InvalidSubmission('Private, reserved and local server addresses are not allowed.')
    return addresses


def safe_get(url, limit=262144):
    started = time.monotonic()
    current = public_url(url)
    for redirect in range(4):
        if time.monotonic() - started > 35:
            raise InvalidSubmission('The remote server took too long to respond.')
        parsed = urlsplit(current)
        address = public_addresses(parsed.hostname)[0]
        pool = urllib3.HTTPSConnectionPool(address, port=443, server_hostname=parsed.hostname,
                                         assert_hostname=parsed.hostname, cert_reqs=ssl.CERT_REQUIRED,
                                         timeout=urllib3.Timeout(connect=6, read=6), maxsize=1)
        response = None
        try:
            response = pool.urlopen('GET', parsed.path, headers={'Host': parsed.hostname,
                                   'User-Agent': 'StremioAddonManager-SubmissionReview/1.0',
                                   'Accept-Encoding': 'identity'}, redirect=False, retries=False,
                                   preload_content=False, decode_content=False)
            if response.status in (301, 302, 303, 307, 308):
                current = public_url(urljoin(current, response.headers.get('Location', '')))
                continue
            if response.status != 200:
                raise InvalidSubmission('The public URL must return HTTP 200.')
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                raise InvalidSubmission('Compressed responses are not supported for submissions.')
            data = bytearray()
            while True:
                if time.monotonic() - started > 35:
                    raise InvalidSubmission('The remote server took too long to respond.')
                chunk = response.read(min(16384, limit + 1 - len(data)), decode_content=False)
                if not chunk:
                    return bytes(data), response.headers.get('Content-Type', ''), current
                data.extend(chunk)
                if len(data) > limit:
                    raise InvalidSubmission('The remote file is too large.')
        finally:
            if response:
                response.close()
            pool.close()
    raise InvalidSubmission('Too many redirects.')


def validate_manifest(data):
    try:
        manifest = json.loads(data)
    except (ValueError, UnicodeError):
        raise InvalidSubmission('The manifest is not valid JSON.') from None
    if not isinstance(manifest, dict):
        raise InvalidSubmission('The manifest must be a JSON object.')
    for key, maximum in [('id', 160), ('name', 80), ('description', 5000), ('version', 64)]:
        if not isinstance(manifest.get(key), str) or not 1 <= len(manifest[key].strip()) <= maximum:
            raise InvalidSubmission(f'The manifest needs a valid {key}.')
    if not re.fullmatch(r'[A-Za-z0-9._-]+', manifest['id']):
        raise InvalidSubmission('The manifest ID is invalid.')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', manifest['version']):
        raise InvalidSubmission('The manifest version must use major.minor.patch format.')
    types = manifest.get('types')
    if not isinstance(types, list) or not 1 <= len(types) <= 20 or not all(
        isinstance(kind, str) and re.fullmatch(r'[\w -]{1,40}', kind) for kind in types
    ):
        raise InvalidSubmission('The manifest must declare its supported content types.')
    resources = manifest.get('resources')
    if not isinstance(resources, list) or not 1 <= len(resources) <= 20:
        raise InvalidSubmission('The manifest must declare supported addon resources.')
    for resource in resources:
        name = resource.get('name') if isinstance(resource, dict) else resource
        if name not in ('catalog', 'meta', 'stream', 'subtitles', 'addon_catalog'):
            raise InvalidSubmission('The manifest declares an unsupported resource.')
    catalogs = manifest.get('catalogs')
    if not isinstance(catalogs, list) or len(catalogs) > 200:
        raise InvalidSubmission('The manifest needs a valid catalogs array.')
    for catalog in catalogs:
        if not isinstance(catalog, dict) or not isinstance(catalog.get('id'), str) or not catalog['id'] or catalog.get('type') not in types:
            raise InvalidSubmission('A catalog is missing its ID or supported type.')
    if 'catalog' in [item.get('name') if isinstance(item, dict) else item for item in resources] and not catalogs:
        raise InvalidSubmission('A catalog addon must provide at least one catalog.')
    hints = manifest.get('behaviorHints', {})
    if not isinstance(hints, dict):
        raise InvalidSubmission('Manifest behavior hints must be an object.')
    if hints.get('configurationRequired'):
        raise InvalidSubmission('Submit a public manifest that works without private configuration or credentials.')
    return manifest


def sanitized_icon(url):
    if not url:
        return None
    data, content_type, final_url = safe_get(url, limit=2 * 1024 * 1024)
    if content_type.split(';')[0].lower() not in {'image/png', 'image/jpeg', 'image/webp'}:
        raise InvalidSubmission('The icon must be a PNG, JPEG or WebP image, not SVG or HTML.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as icon:
                if icon.format not in {'PNG', 'JPEG', 'WEBP'} or icon.width * icon.height > 16000000:
                    raise InvalidSubmission('The icon is too large or uses an unsupported format.')
                icon.thumbnail((384, 384))
                clean = icon.convert('RGB')
                output = io.BytesIO()
                clean.save(output, format='PNG')
                return output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise InvalidSubmission('The icon could not be read safely.') from None
