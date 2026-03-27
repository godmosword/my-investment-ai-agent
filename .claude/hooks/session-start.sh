#!/bin/bash
set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
if [ -f "$ROOT/CLAUDE.md" ]; then
  echo "Tip: Read $ROOT/CLAUDE.md for project guide before large changes."
fi

# Only run in remote Claude Code on the web sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing Python dependencies..."
uv pip install -r requirements.txt --quiet --system

echo "Session start hook complete."
