# Claude Code Adaptation

**Read this file completely when running `branch-code-review` on Claude Code** (including
Codex CLI with Claude-style Agent tool). It overrides Cursor-specific names in `SKILL.md` and
supplements `references/multi-agent-orchestration.md`.

Claude Code has no `Task`, `explore`, `bugbot`, or `security-review` subagent types. Use the
mappings and dispatch patterns below instead.

## Install And Invoke

```bash
# From this skill repo
./install.sh --target claude

# Or manually
git clone git@github.com:ryan-vn/branch-code-review.git ~/.claude/skills/branch-code-review
```

Run the skill **from the target project's git root**, not from the skill directory.

This skill sets `disable-model-invocation: true`, so Claude will **not** auto-load it. Invoke
explicitly:

```text
/branch-code-review
```

Or with scope:

```text
/branch-code-review Review the current branch including working tree changes.
/branch-code-review Quick single-agent review of uncommitted changes only.
/branch-code-review Use merge-base against origin/main for a PR-oriented range.
```

Restart Claude Code after installing or updating the skill. Live edits to `SKILL.md` reload
within the session; plugin hooks need `/reload-plugins`.

## Mode Selection On Claude Code

| Condition | Mode |
|-----------|------|
| Default — user did not say "quick" | Multi-agent (Phase 0→3) |
| User says "quick" / "single agent" | Single-agent fallback in `SKILL.md` |
| Empty diff after context script | Stop; report no changes |
| Context script fails | Ask for `--start`; single-agent fallback |
| User denies Agent tool / subagent spawn | Single-agent fallback; note in Agent Coverage |
| Branch has 1 trivial file and no shared surfaces | Single-agent is acceptable |

**Default assumption:** CodeGraph MCP is **not** installed. Use **No-CodeGraph mode** (below)
unless `user-codegraph` tools appear in the tool list.

## Tool Name Mapping

| Cursor / generic | Claude Code |
|------------------|-------------|
| Shell | Bash |
| Task / subagent dispatch | Agent tool (built-in subagents) or natural-language delegation |
| SemanticSearch | Grep + Read on triage queue (no direct equivalent) |
| CodeGraph MCP | Same server name when configured; optional |

## Agent Mapping

| Role | Claude Code dispatch | Read-only? | Output artifact |
|------|----------------------|------------|-----------------|
| Orchestrator | Main session (you) | n/a | `work/branch-review-context.md`, final report |
| Impact | **Explore** subagent | Yes | `work/branch-review-impact.md` |
| Bug Hunt | **general-purpose** subagent | Prefer Read/Grep only in prompt | `work/branch-review-bugs.md` |
| Security | **`/security-review`** bundled skill **or** general-purpose + `security-checklist.md` | Yes | `work/branch-review-security.md` |
| Bugbot | **Skip** (no equivalent). Optional weak substitute: bundled `/code-review` | Yes | merged into final report |
| Verification | **general-purpose** with Bash | Run tests only | notes in final report |

### Why Explore for Impact

Claude Code's **Explore** agent is read-only and optimized for codebase search. It skips
`CLAUDE.md` and parent git status — that is fine because Impact prompts must be
**self-contained** (paths to context + codegraph bundle + absolute repo root).

### Security pass options

1. **Preferred when available:** invoke bundled `/security-review` via the Skill tool. Pass a
   natural-language change description built from `work/branch-review-context.md` (auth/api/config
   files grouped by provider security pattern hints). Save structured output to
   `work/branch-review-security.md`.
2. **Fallback:** spawn **general-purpose** with the Security Agent prompt from
   `multi-agent-orchestration.md` and `references/security-checklist.md`.

There is no Cursor `review-bugbot` / `review-security` skill on Claude Code unless you install
them separately. Skipping is normal — record under Agent Coverage.

## Phase 0 — Orchestrator (Main Session)

Same as `multi-agent-orchestration.md`, with Claude Code specifics:

1. Confirm target repo root (`pwd` must be git root).
2. Run context collection via **Bash**:

```bash
python3 ~/.claude/skills/branch-code-review/scripts/collect_branch_review_context.py \
  --include-working-tree \
  --output work/branch-review-context.md \
  --json-output work/branch-review-context.json
```

Adjust `<skill-dir>` if the skill lives under `.claude/skills/` in the project.

3. Read `work/branch-review-context.json` — extract bug hunt queue, pattern hints, test commands.
4. Create `work/` if missing.
5. **No-CodeGraph path (default):** skip CodeGraph; ensure
   `work/branch-review-codegraph.md` contains a one-line note:

   ```markdown
   # CodeGraph Bundle
   CodeGraph not available. Use import hints and bug hunt queue in branch-review-context.md.
   ```

6. **Optional CodeGraph path:** if `user-codegraph` MCP is in the tool list, follow
   `references/tool-routing.md` Phase 0 gate and write a real bundle.
7. Git metadata via **Bash** (narrow commands only):

```bash
git status --short --branch
git log --oneline <start>..HEAD
git diff --stat <start>..HEAD
```

Do **not** paste full diffs into chat — subagents read `work/branch-review-context.md`.

## Phase 1 — Parallel Dispatch (Agent Tool)

Launch **Impact (Explore)** and **Bug Hunt (general-purpose)** in the **same turn** using
parallel Agent tool calls. Add Security in parallel when triggers in orchestration doc apply.

Claude Code pattern (natural language that reliably spawns parallel subagents):

```text
Use the Agent tool to run these two subagents in parallel in the same message:

1. Explore subagent (thoroughness: medium) — Impact Analysis Agent. Write work/branch-review-impact.md.
   <paste Impact Agent prompt from multi-agent-orchestration.md with absolute paths filled in>

2. general-purpose subagent — Bug Hunt Agent. Write work/branch-review-bugs.md.
   <paste Bug Hunt Agent prompt from multi-agent-orchestration.md with absolute paths filled in>
```

When Security applies, add a third parallel dispatch (`/security-review` or general-purpose).

### Subagent constraints (repeat in every prompt)

- Read-only: do not Edit, Write, or commit.
- Do **not** call CodeGraph MCP — read `work/branch-review-codegraph.md` if present.
- Do **not** repo-wide Grep loops — use context queue + targeted Read.
- Write the artifact file under `work/` before returning.
- Return a 3–5 sentence summary + artifact path + P0–P3 counts (Bug Hunt / Security).

### Explore-specific note

Because Explore skips `CLAUDE.md`, include any repo-specific ignore rules (e.g. "skip `vendor/`,
`node_modules/`") directly in the Impact prompt when the target repo requires it.

## Phase 2 — Conditional Follow-Up

After Phase 1 returns, run sequentially (not parallel with Phase 1):

| Condition | Claude Code action |
|-----------|---------------------|
| Large branch (>50 files or >2000 added lines) or incomplete Bug Hunt | Optional: bundled `/code-review` as second pass. **Note in report:** it is default-branch-oriented, not branch-local reflog range. Dedupe against bug hunt findings. |
| `test_commands` non-empty, user did not say skip tests | general-purpose subagent with Verification prompt from orchestration doc |
| Security P0/P1 with unclear exploit path | Keep finding; do not auto-fix |

**Do not** block the review waiting for Bugbot — Claude Code has no branch-local Bugbot agent.

## Phase 3 — Merge And Report

Unchanged from `multi-agent-orchestration.md` Phase 3. Use `references/report-template.md`.

In **Agent Coverage**, always state:

- Host: Claude Code
- Subagents used: Explore / general-purpose / `/security-review` / skipped
- CodeGraph: available or no-CodeGraph mode
- Bugbot equivalent: skipped or `/code-review` second pass

In **Tool Usage**, use Claude Code tool names (Bash, not Shell).

## No-CodeGraph Mode (Claude Code Default)

When CodeGraph is unavailable — the normal case:

1. **Impact map** = `work/branch-review-context.md` sections: shared files, entrypoints,
   import impact, bug hunt queue, pattern hints.
2. **Read** top 10–15 queue files directly; use **Grep** only for literal strings after hints
   are exhausted.
3. **Never** substitute repo-wide Grep for structural analysis.
4. Orchestrator may run a **single** targeted trace by hand (Read call chain) for one entrypoint
   flow when Impact Agent reports uncertainty.

Subagents must not assume CodeGraph exists. Pass the stub or real bundle path either way.

## Optional: Pre-Authorize Tools

To reduce permission prompts during review, add frontmatter to a **project copy** of the skill
(`.claude/skills/branch-code-review/SKILL.md`) — do not require this for personal install:

```yaml
allowed-tools:
  - Bash(git *)
  - Bash(python3 *)
  - Read
  - Grep
  - Glob
  - Agent(Explore)
  - Agent(general-purpose)
  - Skill(security-review)
```

Review project skills before trusting a repo — `allowed-tools` grants access without per-use
approval.

## Optional: Project Subagents

For teams that review often, define focused subagents in `.claude/agents/`:

```markdown
---
name: branch-impact
description: Branch impact analysis for branch-code-review. Read-only. Use when orchestrating branch-code-review impact pass.
tools: Read, Grep, Glob
---

You are the Impact Agent for branch-code-review. Read the paths in the delegation message.
Write work/branch-review-impact.md. Do not hunt logic bugs. Do not modify files.
```

Then dispatch with `Agent(branch-impact)` instead of generic Explore when the description
matches.

## Example User Prompts

```text
/branch-code-review
Multi-agent review since branch creation. Include working tree. Write report under work/.
```

```text
/branch-code-review quick
Single-agent sanity check on my WIP — focus on bug hunt queue top 5 files.
```

```text
/branch-code-review
merge-base with origin/main — PR review range. Skip tests.
```

## Limitations On Claude Code

| Gap | Mitigation |
|-----|------------|
| No Cursor `bugbot` | Skip or weak `/code-review` second pass; note in Agent Coverage |
| No dedicated `security-review` subagent | Use bundled `/security-review` skill |
| Explore skips CLAUDE.md | Put repo rules in subagent prompt |
| Parallel subagents return verbose output | Orchestrator summarizes; artifacts live in `work/` |
| `disable-model-invocation: true` | User must invoke `/branch-code-review` manually |
| Bundled `/code-review` ≠ branch-local range | Prefer this skill's context script for scope; use `/code-review` only as additive pass |

## Related Bundled Skills

Claude Code ships `/code-review` and `/security-review`. **This skill replaces neither** for
branch-local reflog-scoped review. Use bundled skills only as optional Phase 2 add-ons and
always dedupe against `work/branch-review-bugs.md`.
