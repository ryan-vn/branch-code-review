# branch-code-review

Agent Skill for **branch-local code review** with multi-agent orchestration, impact analysis, and bug-focused findings.

Review scope is from **branch creation → `HEAD`**, not `main..HEAD`. Includes a dependency-free Python context collector, bug/security pattern hints, and optional CodeGraph integration.

## Skills in this repository

| Skill | Path | Description |
|-------|------|-------------|
| `branch-code-review` | `.` (repo root) | Multi-agent branch review: impact, bug hunt, security, merge report |

## Requirements

- **Python 3.9+** — for `scripts/collect_branch_review_context.py`
- **Git** — target project must be a git repository
- **Optional**: [CodeGraph MCP](https://github.com/) for structural impact/trace analysis
- **Optional**: Cursor subagents for multi-agent mode (`explore`, `generalPurpose`, `security-review`, `bugbot`)

## Install

### Cursor (recommended)

Clone into user skills directory:

```bash
git clone git@github.com:ryan-vn/branch-code-review.git ~/.cursor/skills/branch-code-review
```

Restart Cursor or start a new Agent chat. Invoke with `/branch-code-review` or ask:

> Use branch-code-review to review all code on the current branch since it was created.

**Remote import (Cursor Settings):**

1. Settings → Rules → Add Rule → Remote Rule (GitHub)
2. Repository: `https://github.com/ryan-vn/branch-code-review`

### Codex / Claude Code

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo ryan-vn/branch-code-review \
  --path . \
  --name branch-code-review
```

Or clone manually:

```bash
git clone git@github.com:ryan-vn/branch-code-review.git ~/.codex/skills/branch-code-review
# or: ~/.claude/skills/branch-code-review
```

Restart Codex after install.

### Project-level (team)

Copy or submodule into your project:

```bash
mkdir -p .cursor/skills
git submodule add git@github.com:ryan-vn/branch-code-review.git .cursor/skills/branch-code-review
```

## Usage

Run the skill **from the target project's git root** (the repo you want to review), not from this skills repo.

**Full review (multi-agent, default):**

```
Use branch-code-review to review the current branch including working tree changes.
```

**Quick single-agent review:**

```
Use branch-code-review for a quick single-agent review of the current branch.
```

**PR-oriented range vs main:**

```
Use branch-code-review with merge-base against origin/main.
```

The orchestrator runs:

```bash
python3 ~/.cursor/skills/branch-code-review/scripts/collect_branch_review_context.py \
  --include-working-tree \
  --output work/branch-review-context.md \
  --json-output work/branch-review-context.json
```

Outputs land in the **target project's** `work/` directory.

## Repository layout

```
branch-code-review/
├── SKILL.md                 # Main skill instructions
├── README.md                # This file
├── LICENSE
├── catalog.yaml             # Skill catalog for installers
├── install.sh               # Local install helper
├── agents/
│   └── openai.yaml          # Codex agent interface metadata
├── scripts/
│   └── collect_branch_review_context.py
└── references/
    ├── multi-agent-orchestration.md
    ├── bug-hunting-checklist.md
    ├── security-checklist.md
    ├── testing-review.md
    ├── review-checklist.md
    └── report-template.md
```

## Multi-agent workflow

| Phase | Agent | Role |
|-------|-------|------|
| 0 | Orchestrator | Context script + branch metadata |
| 1 | Impact / Bug Hunt / Security | Parallel readonly subagents |
| 2 | Bugbot / Verification | Large branches or test runs |
| 3 | Orchestrator | Merge findings → final report |

See [references/multi-agent-orchestration.md](references/multi-agent-orchestration.md).

## Related skills

- `review-bugbot` — merge-base logic review (second pass)
- `review-security` — dedicated security subagent
- `split-to-prs` — split oversized branches

## License

MIT — see [LICENSE](LICENSE).

## Contributing

1. Fork and branch from `main`
2. Keep `SKILL.md` under ~500 lines; put detail in `references/`
3. Test the context script on a sample git repo before opening a PR
