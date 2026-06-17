# AGENTS.md

Guidance for agents working **in this repository** (developing the skill), not for
agents invoking the skill against another project.

## What this repo is

This repo **is an agent skill package**, not an application. The product is the skill
itself: `SKILL.md` (entry point), `references/` (runtime instruction docs),
`scripts/collect_branch_review_context.py` (the only executable code), and `agents/`.
There is no application build, runtime, dependency manifest, or test suite here.

## Critical: the script runs against a target repo, not here

`collect_branch_review_context.py` must be run from the **target project's git root**
(the repo being reviewed). It writes `work/branch-review-context.{md,json}` into that
target project. Running it inside this skill repo produces meaningless output.
`work/` is gitignored.

## Verifying changes

There are **no automated tests, lint, or typecheck configured**. Verification is manual:

```bash
# Syntax-check (script is stdlib-only, Python 3.9+)
python3 -m py_compile scripts/collect_branch_review_context.py

# Smoke-test against a real repo (run from THAT repo's root, not from here)
python3 <this-skill-dir>/scripts/collect_branch_review_context.py \
  --include-working-tree \
  --output work/branch-review-context.md \
  --json-output work/branch-review-context.json
```

## Script invariants (do not break)

- **Dependency-free, stdlib only.** Only `argparse, json, re, subprocess, collections,
  pathlib, typing` are allowed. Do not add third-party imports — it is a hard requirement
  (README, `catalog.yaml`).
- **Branch start = oldest reflog entry for the current branch**, never the default branch.
  Never silently fall back to `main`/`master` unless `--start-mode merge-base-with=<ref>`
  is requested. This is the skill's defining behavior.
- **Python 3.9+** (PEP 585 generics rely on `from __future__ import annotations`).
- Markdown and JSON outputs must stay consistent — both are consumed by subagents.

## Skill authoring conventions

- Keep `SKILL.md` under ~500 lines; move detail into `references/` (currently 198 lines).
- **Shipped to installed skills:** `SKILL.md`, `scripts/`, `references/`, `agents/` only.
  `install.sh` excludes `README.md`, `catalog.yaml`, `LICENSE`, `install.sh`, `.git`,
  and `work/`. Do not put runtime-relevant instructions solely in README — they will not
  reach the installed skill.
- `references/` docs are read by agents at runtime. Keep them self-contained: subagents
  receive no chat history.
- The skill is **read-only by contract** (SKILL.md "Out of scope"): it must not commit,
  push, merge, or modify application source. Preserve this when editing docs or the script.
- `SKILL.md` frontmatter matters for skill loading: `version` is the skill version
  (currently `1.1.0`); `disable-model-invocation: true` is intentional.

## Workflow

- Branch from `main`. No CI, release, or pre-commit pipeline is configured.
- `references/tool-routing.md` governs CodeGraph/RTK/fallback tool use and is required at
  runtime; it is wired into `SKILL.md` and `multi-agent-orchestration.md` — keep all three
  in sync when changing tool-dispatch behavior.
