#!/usr/bin/env bash
# Copy agent-orchestration Meta layer into a target repo.
# Does NOT overwrite docs/AGENT-DOMAIN.md if it already exists.
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") /path/to/target-repo" >&2
  exit 1
}

[[ $# -eq 1 ]] || usage
TARGET="$(cd "$1" && pwd)"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$TARGET/.git" ]] && [[ ! -f "$TARGET/README.md" ]]; then
  echo "warn: $TARGET does not look like a project root (no .git or README.md)" >&2
fi

mkdir -p "$TARGET/.cursor/commands" "$TARGET/.cursor/rules" "$TARGET/docs"

copy_file() {
  local rel="$1"
  cp "$SRC/$rel" "$TARGET/$rel"
  echo "  + $rel"
}

echo "Installing agent-orchestration into: $TARGET"
copy_file ".cursor/commands/agent-plan.md"
copy_file ".cursor/commands/agent-action.md"
copy_file ".cursor/rules/agent-orchestration.mdc"
copy_file "docs/AGENT-WORKFLOW.md"

if [[ -f "$TARGET/docs/AGENT-DOMAIN.md" ]]; then
  echo "  = docs/AGENT-DOMAIN.md (kept existing)"
else
  cp "$SRC/docs/AGENT-DOMAIN.template.md" "$TARGET/docs/AGENT-DOMAIN.md"
  echo "  + docs/AGENT-DOMAIN.md (from template — please fill in)"
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit $TARGET/docs/AGENT-DOMAIN.md"
echo "  2. Reopen workspace in Cursor"
echo "  3. Try /agent-plan"
echo ""
echo "See: $SRC/README.md"
