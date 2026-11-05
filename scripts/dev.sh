#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python || ! -d web/node_modules ]]; then
  echo 'Install dependencies first; see README.md.' >&2
  exit 1
fi
for port in 8012 5175; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is occupied. Stop your own prior CallMap process or choose a different configuration. No process was stopped." >&2
    exit 1
  fi
done
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
docker compose up -d --wait
.venv/bin/python -c 'from api.core import migrate; migrate()'
echo 'Local access token (paste into the workspace):'
.venv/bin/python -c 'from api.core import local_token; print(local_token())'
echo 'CallMap: http://127.0.0.1:5175 · API http://127.0.0.1:8012'
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8012 --no-access-log --limit-concurrency 8 --timeout-keep-alive 5 &
api_pid=$!
.venv/bin/python -m api.worker &
worker_pid=$!
(cd web && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5175 --strictPort) &
web_pid=$!
cleanup() {
  kill "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
  wait "$api_pid" "$worker_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
wait
