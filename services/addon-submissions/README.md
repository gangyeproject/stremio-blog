# Community submissions

Status: 2026-10-24. The user reviewed the preview and then approved release.
The preview and production environments use separate queues and credentials.

## Architecture

- Astro form: `/blog/submit-addon`; entry on the addon directory. Existing detail templates remain unchanged.
- Flask API validates form data, consent, HMAC challenges and submission limits. Receipt hashes protect status lookup.
- SQLite WAL stores an independent persistent review queue on the existing VPS; the Strapi database is not modified directly.
- The worker validates public manifests and optional images, then requests text-and-image review and editorial content in a single call to `gpt-6-astra` at the configured provider. Other returned model names fail closed.
- Blank authors become `Anonymous`; blank icons use the addon name's first character. Icons accept public PNG/JPEG/WebP URLs, not file uploads.
- Adult, unsafe, deceptive and uncertain submissions cannot automatically publish. AI approval is not a safety or ownership certification.
- Production publication code reconciles a deterministic CMS slug, triggers deployment, and verifies matching detail and directory pages before reporting `published`.

## Current private preview

- Frontend: `http://127.0.0.1:14323/blog/submit-addon`.
- API: `127.0.0.1:14324`, accessed through a local SSH tunnel; no public nginx route.
- Server code: `/opt/stremio-submissions`; venv: `/opt/stremio-submissions/.venv`.
- Queue: `/var/lib/stremio-submissions-preview/queue.sqlite3`.
- Units: `stremio-submissions-preview.service` and `stremio-submissions-preview-worker.service`; started but not enabled on boot.
- Root-only credentials: `preview-api.env` and `preview-worker.env`. Never copy these into source control, logs, frontend assets, or documentation.
- Both environments use `PUBLISH_ENABLED=false`. Preview worker has no R2 or Vercel deployment credentials. Accepted previews terminate at `approved_preview`.
- Frontend was built with `PUBLIC_SUBMISSIONS_API=http://127.0.0.1:14324/addon-submissions`; do not deploy this local `dist` directory.
- Closing the local preview process or SSH tunnel stops local access, not the production website.

## Reproducibility and validation

The worker imports the reviewed publisher helper snapshot included alongside this README, deployed to `/opt/stremio-submissions/publisher.py` and selected with `PUBLISHER_MODULE_PATH`. Expected SHA256:
`6fde92679f15484cb70ea7b094ab397c02c0267934ea8baa89915cfb6ac0cd9c`.
Do not silently substitute a newer daily publisher without rerunning integration tests.

Run backend tests on Linux with that helper snapshot and the pinned requirements:

```sh
PUBLISHER_MODULE_PATH=/opt/stremio-submissions /opt/stremio-submissions/.venv/bin/python -m unittest test_submissions -v
```

Frontend checks: Astro build, `scripts/check-addon-content.mjs`, `scripts/check-addon-filters.mjs`, and `scripts/check-ads.mjs`.
A real provider smoke test passed with public Cinemeta manifest evidence and a generated test PNG; the provider reported `gpt-6-astra`. The test performed no CMS writes or deployment.
Tests verify approval/publication/deployment separation with mocked CMS writes. No fabricated addon is inserted into the live directory just for testing.

The included `strapi-addon-lifecycles.js` preserves the existing lifecycle but skips its unsafe second network fetch for community records already validated by the worker. Deploy it to the existing addon lifecycle path and restart only the CMS after taking a backup. `test-lifecycles.cjs` verifies old addon behavior is unchanged.

## Production configuration

`setup_production.py` creates root-only server environments using the reviewed API key and existing storage/deployment credentials; it refuses to overwrite existing files. API and worker units use `/var/lib/stremio-submissions/queue.sqlite3` and port `127.0.0.1:14326`. The API environment does not contain CMS, AI, storage or deployment credentials.

`setup_proxy.py` creates only the submission API location and a request-rate zone. It fetches current trusted Cloudflare networks from Cloudflare's HTTPS IP lists; client-supplied IP headers are not trusted outside those networks. Run `nginx -t` before reloading. The resulting public endpoint is `https://admin.stremioaddonmanager.org/addon-submissions`.

## Activation checklist — only after user approval

1. Snapshot current frontend source, server configuration, and existing CMS/database backups. Recheck the remote main revision before preparing a release.
2. Create a separate production queue and environment; never automatically promote preview submissions. Configure production origins, independent challenge secret, R2 credentials and Vercel hook server-side.
3. Keep API and worker credentials separate and the API on loopback. Add a narrow nginx location for the submission API, body/rate limits, and authoritative client-IP forwarding. Trust only explicitly configured proxies; never accept arbitrary client-supplied IP headers.
4. Install separate production units under the dedicated unprivileged user. Confirm public health/CORS and fail-closed behavior before switching publication on.
5. Build the frontend without the localhost API override; deploy through the existing project after approval. Keep old titles, cards, details, and daily publisher unchanged.
6. With an authorized addon fixture, verify queue, model rejection/approval, image/anonymous fallback, CMS publication, deployment visibility and receipt lookup. Check deployment timeout reconciliation without duplicate posts.
7. Monitor rate limits (3 submissions/network/day, 20 total/day, 30 model calls/day), cost and abuse. These controls are not a substitute for a CAPTCHA if abuse appears.

## Rollback

Disable the new production worker and submission route, then restore the prior frontend deployment. Do not delete the queue or approved CMS records automatically; reconcile records and deployment state first. The existing daily publisher and original CMS schema are independent of this feature.
