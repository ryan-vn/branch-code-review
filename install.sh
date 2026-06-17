#!/usr/bin/env bash
# Install branch-code-review into Cursor / Codex / Claude skill directories.
set -euo pipefail

SKILL_NAME="branch-code-review"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--target cursor|codex|claude|agents] [--dest PATH] [--no-agents] [--agents-only]

Install the branch-code-review skill from this repository.

Options:
  --target       Install target (default: cursor)
               cursor  -> ~/.cursor/skills/$SKILL_NAME
               codex   -> ~/.codex/skills/$SKILL_NAME
               claude  -> ~/.claude/skills/$SKILL_NAME (+ parallel subagents by default)
               agents  -> ~/.agents/skills/$SKILL_NAME
  --dest       Override destination directory
  --no-agents  Skip installing Claude parallel subagents (claude target only)
  --agents-only  Copy agents/claude/*.md -> ~/.claude/agents/ only (skill already installed)
  -h, --help   Show this help

Examples:
  $(basename "$0")
  $(basename "$0") --target claude
  $(basename "$0") --target claude --no-agents
  $(basename "$0") --agents-only
  $(basename "$0") --dest ~/.cursor/skills/$SKILL_NAME
EOF
}

TARGET="cursor"
DEST=""
INSTALL_CLAUDE_AGENTS=1
AGENTS_ONLY=0

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
    --no-agents)
      INSTALL_CLAUDE_AGENTS=0
      shift
      ;;
    --agents-only)
      AGENTS_ONLY=1
      shift
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

install_claude_agents() {
  local src="$1"
  local agents_dest="$HOME/.claude/agents"
  mkdir -p "$agents_dest"
  for agent in "$src"/agents/claude/*.md; do
    [[ -f "$agent" ]] || continue
    base="$(basename "$agent")"
    cp "$agent" "$agents_dest/$base"
    echo "Installed subagent -> $agents_dest/$base"
  done
  echo "Parallel subagents: branch-review-impact, branch-review-bugs, branch-review-security, branch-review-verify"
}

if [[ "$AGENTS_ONLY" -eq 1 ]]; then
  SRC="$REPO_ROOT"
  if [[ -d "$HOME/.claude/skills/$SKILL_NAME/agents/claude" ]]; then
    SRC="$HOME/.claude/skills/$SKILL_NAME"
  fi
  install_claude_agents "$SRC"
  echo "Restart Claude Code if Agent(branch-review-*) is not recognized in this session."
  exit 0
fi

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

if [[ "$TARGET" == "claude" && "$INSTALL_CLAUDE_AGENTS" -eq 1 ]]; then
  install_claude_agents "$REPO_ROOT"
fi

echo "Restart Cursor / Codex / Claude Code to load the skill."
