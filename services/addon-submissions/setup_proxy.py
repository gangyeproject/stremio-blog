import ipaddress
import os
from pathlib import Path

import requests


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root')
    root = Path('/www/server/panel/vhost/nginx')
    limits = root / 'stremio-submissions-limits.conf'
    route = root / 'extension/admin.stremioaddonmanager.org/stremio-submissions.conf'
    if limits.exists() or route.exists():
        raise RuntimeError('Submission proxy configuration already exists')
    networks = []
    for family in ['v4', 'v6']:
        response = requests.get('https://www.cloudflare.com/ips-' + family, timeout=(10, 30))
        response.raise_for_status()
        group = [ipaddress.ip_network(value.strip()) for value in response.text.splitlines() if value.strip()]
        if len(group) < 5 or any(network.prefixlen < 10 or not network.is_global for network in group):
            raise RuntimeError('Unexpected Cloudflare trusted-proxy list')
        networks.extend(group)
    limits.write_text('limit_req_zone $binary_remote_addr zone=stremio_submissions:10m rate=2r/s;\n')
    trusted = ''.join(f'    set_real_ip_from {network};\n' for network in networks)
    route.write_text('location ^~ /addon-submissions/ {\n' + trusted + '''    real_ip_header CF-Connecting-IP;
    real_ip_recursive on;
    client_max_body_size 16k;
    client_body_timeout 10s;
    limit_req zone=stremio_submissions burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:14326;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 35s;
    proxy_redirect off;
    proxy_cache off;
}
''')
    print('Created submission-only route and rate limits using official Cloudflare IP ranges. Validate nginx before reload.')


if __name__ == '__main__':
    main()
