#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."
if [[ ! -f app/.env ]]; then
  echo 'Create app/.env from .env.example and configure GOOGLE_API_KEY first.' >&2
  exit 1
fi

compose=(docker compose --env-file app/.env -f compose.production.yml)
"${compose[@]}" build
"${compose[@]}" up -d vector-db

# Wait inside the Compose network, without publishing the database port.
"${compose[@]}" run --rm --no-deps -T web python - <<'PY'
import time
import httpx

for attempt in range(30):
    try:
        httpx.get('http://vector-db:6333/readyz', timeout=2).raise_for_status()
        print('Qdrant is ready.')
        break
    except (httpx.HTTPError, OSError):
        time.sleep(1)
else:
    raise SystemExit('Qdrant did not become ready. Check docker compose logs.')
PY

# Existing indexed collections are preserved. A new server needs sample.pdf.
"${compose[@]}" run --rm indexer
"${compose[@]}" run --rm --no-deps web python -m app.check_services --google
"${compose[@]}" up -d web

if [[ "${1:-}" == "--https" ]]; then
  "${compose[@]}" --profile https up -d caddy
fi

"${compose[@]}" ps
