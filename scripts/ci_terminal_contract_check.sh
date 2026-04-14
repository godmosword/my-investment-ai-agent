#!/usr/bin/env bash
# Terminal / PWA contract checks for CI (Bloomberg alignment §4 items 6 & 14 anchor).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
python3 -m pytest test_terminal_numeric_consistency.py -q --tb=short
cd "$ROOT/data-verification-ui"
npm install --no-audit --no-fund
npm run build
