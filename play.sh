#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${HS_PORT:-8000}"
HOST="${HS_HOST:-127.0.0.1}"

if [ ! -d "$ROOT/frontend/dist" ]; then
  echo "Building frontend..."
  (cd "$ROOT/frontend" && npm run build)
fi

echo "Starting Hearthstone Classic Local Server at http://$HOST:$PORT"
echo "Antigravity CLI ready at: $ROOT/hs (e.g. ./hs status, ./hs wait)"
exec python3 -m uvicorn server.app:app --host "$HOST" --port "$PORT"
