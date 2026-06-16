#!/usr/bin/env bash
# Install branch-code-review into Cursor / Codex / Claude skill directories.
set -euo pipefail

SKILL_NAME="branch-code-review"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--target cursor|codex|claude|agents] [--dest PATH]

Install the branch-code-review skill from this repository.

Options:
  --target   Install target (default: cursor)
             cursor  -> ~/.cursor/skills/$SKILL_NAME
             codex   -> ~/.codex/skills/$SKILL_NAME
             claude  -> ~/.claude/skills/$SKILL_NAME
             agents  -> ~/.agents/skills/$SKILL_NAME
  --dest     Override destination directory
  -h, --help Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --target codex
  $(basename "$0") --dest ~/.cursor/skills/$SKILL_NAME
EOF
}

TARGET="cursor"
DEST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --dest)
      DEST="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$DEST" ]]; then
  case "$TARGET" in
    cursor) DEST="$HOME/.cursor/skills/$SKILL_NAME" ;;
    codex) DEST="$HOME/.codex/skills/$SKILL_NAME" ;;
    claude) DEST="$HOME/.claude/skills/$SKILL_NAME" ;;
    agents) DEST="$HOME/.agents/skills/$SKILL_NAME" ;;
    *)
      echo "Unknown target: $TARGET" >&2
      exit 1
      ;;
  esac
fi

if [[ -e "$DEST" ]]; then
  echo "Destination already exists: $DEST" >&2
  echo "Remove it first or pass --dest to a new path." >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude '.git' \
    --exclude 'work' \
    --exclude 'install.sh' \
    --exclude 'README.md' \
    --exclude 'catalog.yaml' \
    --exclude 'LICENSE' \
    "$REPO_ROOT/" "$DEST/"
else
  mkdir -p "$DEST"
  cp -R "$REPO_ROOT"/SKILL.md "$REPO_ROOT"/scripts "$REPO_ROOT"/references "$REPO_ROOT"/agents "$DEST/"
fi

echo "Installed $SKILL_NAME -> $DEST"
echo "Restart Cursor / Codex / Claude Code to load the skill."
