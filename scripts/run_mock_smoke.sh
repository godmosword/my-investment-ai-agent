#!/usr/bin/env bash
# Contributor 一鍵 mock smoke（MOCK_APIS + 跳過外部推送／BQ）
set -euo pipefail
cd "$(dirname "$0")/.."
export MOCK_APIS=1
export SKIP_TELEGRAM=1
export SKIP_BIGQUERY=1
exec python3 -m pytest -m smoke -q "$@"
