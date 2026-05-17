#!/usr/bin/env bash
# Production / staging smoke: static PWA + API health + sample quote.
# Usage: BASE_URL=https://pwa.example.com API_BASE=https://api.example.com [SMOKE_QSILICON_KEY=...] bash scripts/smoke-prod.sh
set -euo pipefail
BASE_URL="${BASE_URL:?set BASE_URL to deployed PWA origin}"
API_BASE="${API_BASE:?set API_BASE to FastAPI origin (same host as VITE_API_URL)}"
HDR=()
if [[ -n "${SMOKE_QSILICON_KEY:-}" ]]; then
  HDR=(-H "X-Q-Silicon-Key: ${SMOKE_QSILICON_KEY}")
fi
code() { curl -sS -o /dev/null -w "%{http_code}" "$@"; }

echo "== PWA static (expect 200) =="
for path in /insights /news /dashboard /columns /portfolio; do
  u="${BASE_URL%/}${path}"
  c=$(code "$u")
  [[ "$c" == "200" ]] || { echo "FAIL $u -> $c"; exit 1; }
  echo "OK $u"
done

echo "== API healthz =="
hc=$(code "${API_BASE%/}/healthz")
[[ "$hc" == "200" ]] || { echo "FAIL ${API_BASE%/}/healthz -> $hc"; exit 1; }
echo "OK ${API_BASE%/}/healthz"

echo "== API quote BTC (may be 401 without key — document your backend) =="
qc=$(curl -sS -o /dev/null -w "%{http_code}" "${HDR[@]}" "${API_BASE%/}/api/symbols/BTC/quote")
if [[ "$qc" == "200" ]]; then
  echo "OK quote 200"
elif [[ "$qc" == "401" ]]; then
  echo "WARN quote 401 (set SMOKE_QSILICON_KEY if master key required)"
else
  echo "FAIL ${API_BASE%/}/api/symbols/BTC/quote -> $qc"; exit 1
fi
echo "smoke-prod: all checks passed"
