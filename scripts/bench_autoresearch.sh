#!/usr/bin/env bash
# Autoresearch / CI 輕量 bench 入口（BL-05 / BL-07）。
# 風險註解：METRIC 行僅應由本腳本末尾的 echo 產生；請勿將 pytest/ruff 的 stdout tee 到解析器，
# 以免誤把非官方輸出當成 METRIC。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export SKIP_BIGQUERY=1 SKIP_TELEGRAM=1
T0=$(date +%s)
ruff check .
RUFF=$?
python3 -m pytest -m smoke -q
PY=$?
T1=$(date +%s)
WALL=$((T1 - T0))
# --- 官方 METRIC 區塊（供 bench / 自動化解析）---
echo "METRIC lint_pass=$([[ $RUFF -eq 0 ]] && echo 1 || echo 0)"
echo "METRIC smoke_pass=$([[ $PY -eq 0 ]] && echo 1 || echo 0)"
echo "METRIC wall_time_sec=$WALL"
echo "METRIC bench_ts_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if command -v git >/dev/null 2>&1; then
  echo "METRIC bench_git_sha=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
else
  echo "METRIC bench_git_sha=unknown"
fi
# plateau_hint：預留與歷次 METRIC 對照之錨點（0=本輪未做趨勢比對）
echo "METRIC plateau_hint=0"
exit $((RUFF || PY))
