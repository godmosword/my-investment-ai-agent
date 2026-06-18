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

ready=0
for _ in $(seq 1 50); do
  if curl -sf "${API_URL}/api/symbols/BTC/quote" >/dev/null; then
    ready=1
    break
  fi
  sleep 0.15
done
if [ "$ready" != "1" ]; then
  echo "::error::E2E mock API not ready at ${API_URL}"
  exit 1
fi
echo "E2E mock API ready at ${API_URL}"

export VITE_API_URL="${API_URL}"
export VITE_GLASSBOX_MOCK=0
export VITE_E2E=1
export VITE_STRUCTURED_REPORT=1
export VITE_TECH_PULSE_URL="https://tech-pulse.e2e.example"

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

preview_ready=0
for _ in $(seq 1 80); do
  if curl -sf "http://127.0.0.1:${PREVIEW_PORT}/" >/dev/null; then
    preview_ready=1
    break
  fi
  sleep 0.25
done
if [ "$preview_ready" != "1" ]; then
  echo "::error::E2E preview not ready at http://127.0.0.1:${PREVIEW_PORT}/"
  exit 1
fi
echo "E2E preview ready at http://127.0.0.1:${PREVIEW_PORT}/"

export PLAYWRIGHT_BASE_URL="http://127.0.0.1:${PREVIEW_PORT}"
if [ -z "${PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD:-}" ]; then
  npx playwright install chromium
fi
npx playwright test "$@"
