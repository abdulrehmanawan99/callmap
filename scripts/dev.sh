#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d web/node_modules ]]; then
  echo 'Install dependencies first; see README.md.' >&2
  exit 1
fi
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
# Port overrides (set in .env or the shell). Defaults match .env.example.
export CALLMAP_API_PORT="${CALLMAP_API_PORT:-8012}"
export CALLMAP_WEB_PORT="${CALLMAP_WEB_PORT:-5175}"
export CALLMAP_PG_PORT="${CALLMAP_PG_PORT:-55434}"
export CALLMAP_REDIS_PORT="${CALLMAP_REDIS_PORT:-6382}"
export DATABASE_URL="${DATABASE_URL:-postgresql://callmap:${POSTGRES_PASSWORD:-callmap_local_only}@127.0.0.1:${CALLMAP_PG_PORT}/callmap}"
export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:${CALLMAP_REDIS_PORT}/0}"
for port in "$CALLMAP_API_PORT" "$CALLMAP_WEB_PORT"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is occupied. Stop your own prior CallMap process or set CALLMAP_API_PORT/CALLMAP_WEB_PORT in .env. No process was stopped." >&2
    exit 1
  fi
done
docker compose up -d --wait
.venv/bin/python -c 'from api.core import migrate; migrate()'
echo 'Local access token (paste into the workspace):'
.venv/bin/python -c 'from api.core import local_token; print(local_token())'
echo "CallMap: http://127.0.0.1:${CALLMAP_WEB_PORT} · API http://127.0.0.1:${CALLMAP_API_PORT}"
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port "$CALLMAP_API_PORT" --no-access-log --limit-concurrency 8 --timeout-keep-alive 5 &
api_pid=$!
.venv/bin/python -m api.worker &
worker_pid=$!
(cd web && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$CALLMAP_WEB_PORT" --strictPort) &
web_pid=$!
cleanup() {
  kill "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait
