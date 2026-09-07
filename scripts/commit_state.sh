#!/usr/bin/env bash
# 把 .qsilicon/ 的管線狀態 commit 回 repo。
#
# GitHub Actions runner 是 ephemeral：JSONL 狀態不 commit 回來就等於失憶
# （既有的 paper-execution-tick 正是如此，execution_intents.jsonl 每輪即失）。
# 形狀沿用 .github/workflows/weekly-scout.yml 的 commit-back，另加 pull --rebase，
# 以免多個排程 job 併發推送時互撞。
#
# 用法：scripts/commit_state.sh "<commit subject>"
set -euo pipefail

SUBJECT="${1:-chore(state): pipeline state $(date -u +%F)}"

# 只納入實際的狀態檔；scratchpad 與 last_gate_failure 已由 .gitignore 排除。
STATE_PATHS=(".qsilicon")

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add -- "${STATE_PATHS[@]}"

if git diff --staged --quiet; then
  echo "No state changes to commit."
  exit 0
fi

git commit -m "${SUBJECT}"

# 併發的 tick job 可能已推過；rebase 後重試三次再放棄，避免無限迴圈。
for attempt in 1 2 3; do
  if git pull --rebase --quiet && git push --quiet; then
    echo "State pushed (attempt ${attempt})."
    exit 0
  fi
  echo "Push attempt ${attempt} failed; retrying after rebase."
  sleep $((attempt * 5))
done

echo "Failed to push pipeline state after 3 attempts." >&2
exit 1
