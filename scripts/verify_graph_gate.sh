#!/usr/bin/env bash
# Graph／Reviewer 變更後建議執行（見 docs/architecture/GRAPH_REVIEWER_CHANGE_CHECKLIST.md）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 -m pytest test_reviewer_loop.py -q "$@"
