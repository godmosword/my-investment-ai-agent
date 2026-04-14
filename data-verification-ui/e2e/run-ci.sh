#!/usr/bin/env bash
# Playwright E2E：mock API → Vite build（內嵌 VITE_API_URL）→ preview → playwright test
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${E2E_MOCK_API_PORT:-9999}"
export E2E_MOCK_API_PORT="$PORT"
API_URL="http://127.0.0.1:${PORT}"

node e2e/mock-api-server.mjs &
MOCK_PID=$!
cleanup() {
  kill "${MOCK_PID}" 2>/dev/null || true
  kill "${PREVIEW_PID}" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 50); do
  if curl -sf "${API_URL}/api/symbols/BTC/quote" >/dev/null; then
    break
  fi
  sleep 0.15
done

export VITE_API_URL="${API_URL}"
export VITE_GLASSBOX_MOCK=0
export VITE_E2E=1

npm run build

pick_preview_port() {
  if [[ -n "${E2E_PREVIEW_PORT:-}" ]]; then
    echo "${E2E_PREVIEW_PORT}"
    return
  fi
  python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
}

PREVIEW_PORT="$(pick_preview_port)"
npm run preview -- --host 127.0.0.1 --port "${PREVIEW_PORT}" --strictPort &
PREVIEW_PID=$!

for _ in $(seq 1 80); do
  if curl -sf "http://127.0.0.1:${PREVIEW_PORT}/" >/dev/null; then
    break
  fi
  sleep 0.25
done

export PLAYWRIGHT_BASE_URL="http://127.0.0.1:${PREVIEW_PORT}"
npx playwright install chromium
npx playwright test "$@"
