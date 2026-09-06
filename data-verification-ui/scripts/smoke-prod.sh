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

echo "== API liveness (GET /healthz only; exact JSON body required) =="
hz_url="${API_BASE%/}/healthz"
hz_file="$(mktemp)"
cleanup_hz() { rm -f "$hz_file"; }
trap cleanup_hz EXIT
hz_code="$(curl -sS -o "$hz_file" -w "%{http_code}" "$hz_url" || true)"
if [[ "$hz_code" != "200" ]]; then
  echo "FAIL $hz_url -> HTTP $hz_code (do not treat /docs or /openapi.json as liveness)"
  exit 1
fi
python3 - "$hz_file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    body = json.load(fh)
expected = {"ok": True, "service": "api"}
if body != expected:
    raise SystemExit(f"FAIL /healthz body {body!r} != {expected!r}")
print("OK /healthz exact body")
PY

echo "== API quote BTC (may be 401 without key — document your backend) =="
if [[ ${#HDR[@]} -gt 0 ]]; then
  qc=$(curl -sS -o /dev/null -w "%{http_code}" "${HDR[@]}" "${API_BASE%/}/api/symbols/BTC/quote")
else
  qc=$(curl -sS -o /dev/null -w "%{http_code}" "${API_BASE%/}/api/symbols/BTC/quote")
fi
if [[ "$qc" == "200" ]]; then
  echo "OK quote 200"
elif [[ "$qc" == "401" ]]; then
  echo "WARN quote 401 (set SMOKE_QSILICON_KEY if master key required)"
else
  echo "FAIL ${API_BASE%/}/api/symbols/BTC/quote -> $qc"; exit 1
fi

echo "== API frontend contract routes (expect 200; enabled:false is OK, 404 is not) =="
for path in /api/data-health /api/options/summary /api/options/gex/NVDA /api/options/flow/NVDA; do
  u="${API_BASE%/}${path}"
  if [[ ${#HDR[@]} -gt 0 ]]; then
    c=$(code "${HDR[@]}" "$u")
  else
    c=$(code "$u")
  fi
  [[ "$c" == "200" ]] || { echo "FAIL $u -> $c"; exit 1; }
  echo "OK $u"
done
echo "smoke-prod: all checks passed"
