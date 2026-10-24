import os
import secrets
from pathlib import Path

from setup_preview import read_env, write_env


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Run as root')
    root = Path('/opt/stremio-submissions')
    if any((root / name).exists() for name in ['production-api.env', 'production-worker.env']):
        raise RuntimeError('Production environment already exists; refusing to overwrite secrets')
    original = read_env('/opt/stremio-publisher/.env')
    reviewed = read_env(root / 'preview-worker.env')
    required = ['STRAPI_URL', 'STRAPI_API_TOKEN', 'CLOUDFLARE_ACCOUNT_ID', 'R2_ACCESS_KEY_ID',
                'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME', 'R2_PUBLIC_BASE_URL', 'VERCEL_DEPLOY_HOOK_URL']
    if any(not original.get(key) for key in required):
        raise RuntimeError('Missing production credentials')
    if reviewed.get('OPENAI_MODEL') != 'gpt-6-astra':
        raise RuntimeError('Only gpt-6-astra is allowed')
    common = {'PUBLISH_ENABLED': 'true', 'SUBMISSIONS_DB': '/var/lib/stremio-submissions/queue.sqlite3'}
    write_env(root / 'production-worker.env', {
        **common, **{key: original[key] for key in required},
        **{key: reviewed[key] for key in ['OPENAI_BASE_URL', 'OPENAI_API_KEY', 'OPENAI_MODEL']},
        'PUBLISHER_MODULE_PATH': '/opt/stremio-submissions',
    })
    write_env(root / 'production-api.env', {
        **common, 'SUBMISSIONS_SECRET': secrets.token_hex(32),
        'SUBMISSIONS_ORIGINS': 'https://stremioaddonmanager.org,https://www.stremioaddonmanager.org',
    })
    print('Production environments created with root-only permissions; no preview data was copied.')


if __name__ == '__main__':
    main()
