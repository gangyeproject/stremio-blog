import getpass
import os
import secrets
from pathlib import Path


def read_env(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path, values):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        for key, value in values.items():
            if '\n' in value or '\r' in value:
                raise ValueError('Invalid environment value')
            output.write(key + '="' + value.replace('\\', '\\\\').replace('"', '\\"') + '"\n')


def main():
    root = Path('/opt/stremio-submissions')
    if (root / 'preview-worker.env').exists() or (root / 'preview-api.env').exists():
        raise RuntimeError('Preview environment already exists; refusing to overwrite secrets')
    original = read_env('/opt/stremio-publisher/.env')
    key = getpass.getpass('Review API key (hidden): ').strip()
    if not key.startswith('sk-') or len(key) < 20:
        raise ValueError('Invalid review API key')
    common = {'PUBLISH_ENABLED': 'false', 'SUBMISSIONS_DB': '/var/lib/stremio-submissions-preview/queue.sqlite3'}
    write_env(root / 'preview-worker.env', {**common,
        'PUBLISHER_MODULE_PATH': '/opt/stremio-submissions',
        'OPENAI_BASE_URL': 'https://api.sqface.sbs/v1', 'OPENAI_API_KEY': key,
        'OPENAI_MODEL': 'gpt-6-astra', 'STRAPI_URL': original.get('STRAPI_URL', 'https://admin.stremioaddonmanager.org'),
        'STRAPI_API_TOKEN': original['STRAPI_API_TOKEN']})
    write_env(root / 'preview-api.env', {**common, 'SUBMISSIONS_SECRET': secrets.token_hex(32),
        'SUBMISSIONS_ORIGINS': 'http://127.0.0.1:14323,http://127.0.0.1:14325'})
    print('Preview secrets saved with root-only permissions. Publication credentials were NOT copied.')


if __name__ == '__main__':
    main()
