# Claude Code Adaptation

**Read this file completely when running `branch-code-review` on Claude Code** (including
Codex CLI with Claude-style Agent tool). It overrides Cursor-specific names in `SKILL.md` and
supplements `references/multi-agent-orchestration.md`.

Claude Code has no Cursor `Task` or `subagent_type`. Use **named parallel subagents** installed
from this skill (`agents/claude/`) and the **Agent tool** — multiple calls in **one turn**.

## Parallel-First (Core Design)

Review agents **run at the same time**, not in sequence.

```text
Phase 0  [Orchestrator]  context script + git metadata  (alone — sequential)
         │
Phase 1  ├─► branch-review-impact   ──┐
         ├─► branch-review-bugs     ──┼── SAME TURN, parallel Agent calls
         └─► branch-review-security ──┘   (security when triggers apply)
         │
         ▼  wait for ALL Phase 1 agents
Phase 2  ├─► /code-review (logic pass) ──┐  same turn when BOTH triggers apply
         └─► branch-review-verify      ──┘
         │
         ▼  wait for ALL Phase 2 agents (or note partial failure)
Phase 3  [Orchestrator]  merge artifacts → final report
```

**Forbidden:** Impact finishes → then Bug Hunt starts → then Security. That is single-agent
behavior disguised as multi-agent.

**Required:** Orchestrator sends **2–3 Agent tool invocations in one assistant message**.
Each agent writes its own artifact under `work/` independently.

## Install And Invoke

```bash
# Skill + parallel review subagents (recommended for Claude Code)
./install.sh --target claude

# Skill only, no subagents
./install.sh --target claude --no-agents
```

`--target claude` installs:

| Destination | Contents |
|-------------|----------|
| `~/.claude/skills/branch-code-review/` | Skill, scripts, references |
| `~/.claude/agents/branch-review-*.md` | Impact, Bug Hunt, Security subagents |

Subagents enable reliable **parallel** dispatch: orchestrator calls
`Agent(branch-review-impact)`, `Agent(branch-review-bugs)`, and optionally
`Agent(branch-review-security)` in one turn.

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

| Role | Claude Code subagent | Parallel in Phase 1? | Output artifact |
|------|----------------------|----------------------|-----------------|
| Orchestrator | Main session | No (runs alone in Phase 0/3) | `work/branch-review-context.md`, final report |
| Impact | **branch-review-impact** | **Yes** | `work/branch-review-impact.md` |
| Bug Hunt | **branch-review-bugs** | **Yes** | `work/branch-review-bugs.md` |
| Security | **branch-review-security** | **Yes** (when triggered) | `work/branch-review-security.md` |
| Bugbot | skip; optional `/code-review` | Phase 2, **parallel** with verify when both apply | merged into final report |
| Verification | **branch-review-verify** | Phase 2, **parallel** with code-review when both apply | notes in final report |

Fallback when subagents are not installed: built-in **Explore** (impact) and **general-purpose**
(bug hunt) — still **must** dispatch in parallel in one turn.

### Why named subagents

Dedicated agents (`agents/claude/*.md`) give the orchestrator stable `Agent(name)` targets so
Claude Code spawns **separate context windows simultaneously**. Built-in Explore works for
impact but is harder to parallelize with a distinct bug-hunt identity.

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

## Phase 1 — Simultaneous Parallel Dispatch

After Phase 0 completes, the orchestrator **must not analyze code itself** beyond reading
context JSON for dispatch decisions. Immediately spawn review agents **in parallel**.

### Step 1 — Fill prompt templates

Copy Impact / Bug Hunt / Security prompts from `multi-agent-orchestration.md`. Replace
`<absolute repo path>`, `<skill-dir>`, `<start>`, `<head>`, `<range>`, `<start_mode>`.

### Step 2 — One message, multiple Agent calls

Send **one orchestrator message** containing **2 or 3 parallel Agent tool invocations**:

```text
Phase 1 parallel dispatch — run ALL of the following subagents simultaneously in this turn.
Do not start the next agent after another finishes.

Agent(branch-review-impact):
<paste Impact Agent prompt>

Agent(branch-review-bugs):
<paste Bug Hunt Agent prompt>

Agent(branch-review-security):   # omit entire block when Security triggers do not apply
<paste Security Agent prompt>
```

Claude Code executes these subagents **concurrently** — each in its own context window — then
returns summaries to the orchestrator.

### Step 3 — Wait, then merge

Do **not** start Phase 2 until **every** spawned Phase 1 agent has returned (or failed after
one retry). Read artifacts from `work/` — not from chat paraphrase.

### Anti-patterns

| Wrong | Right |
|-------|-------|
| Run impact, read result, then spawn bug hunt | Spawn impact + bug hunt together |
| One general-purpose agent does impact then bugs | Separate agents, parallel |
| Orchestrator reads all files before spawning agents | Orchestrator only runs context script + dispatch |
| Security runs after bug hunt completes | Security in same turn as impact + bug hunt when triggered |

### Subagent constraints (include in every delegation prompt)

- Read-only: do not Edit, Write, or commit.
- Do **not** call CodeGraph MCP — read `work/branch-review-codegraph.md` if present.
- Do **not** repo-wide Grep loops — use context queue + targeted Read.
- Write the artifact file under `work/` before returning.
- Return a 3–5 sentence summary + artifact path + P0–P3 counts (Bug Hunt / Security).

Include repo-specific ignore rules (e.g. skip `vendor/`, `node_modules/`) in prompts when needed.

## Phase 2 — Simultaneous Parallel Follow-Up

After **all** Phase 1 agents return, Phase 2 has **two optional agents** that are **independent**
— they can and should run **at the same time** when both triggers apply:

| Agent | Trigger | Claude Code dispatch |
|-------|---------|----------------------|
| Logic second pass | Large branch or incomplete Bug Hunt | `Skill(code-review)` |
| Verification | `test_commands` present, user did not skip tests | `Agent(branch-review-verify)` |

Neither agent needs the other's output to start. Bug hunt artifacts are already on disk from
Phase 1; verification reads `test_commands` from context JSON.

### Parallel dispatch (mandatory when both apply)

```text
Phase 2 parallel dispatch — run BOTH simultaneously in this turn.

Agent(branch-review-verify):
<paste Verification prompt from multi-agent-orchestration.md>

Skill(code-review):
Custom Instructions: Pass 2 after branch-local bug hunt. Dedupe against work/branch-review-bugs.md.
Diff scope note: bundled /code-review is default-branch-oriented; branch-local scope is in work/branch-review-context.md.
```

If only verification applies (small branch + tests): spawn `branch-review-verify` alone.
If only code-review applies (large branch, user skipped tests): spawn `/code-review` alone.

### Why parallel is safe here

- **Verification** runs lint/tests — does not read Bugbot output.
- **Code-review pass** re-reads diffs and `work/branch-review-bugs.md` — does not need test results.
- Orchestrator merges both in Phase 3; dedupe findings by location + failure mode.

### Anti-patterns

| Wrong | Right |
|-------|-------|
| Run `/code-review`, then run tests | Both in one turn |
| Wait for verify failures before code-review | Parallel spawn |
| Orchestrator runs tests inline instead of delegating | `Agent(branch-review-verify)` |

| Condition | Notes |
|-----------|-------|
| Large branch or incomplete Bug Hunt | Optional `/code-review`; note merge-base vs branch-local in report |
| `test_commands` non-empty, user did not say skip tests | `branch-review-verify` |
| Security P0/P1 unclear exploit path | Keep finding; do not auto-fix |

**Do not** block Phase 3 waiting for one Phase 2 agent if the other already failed — merge what
returned and note gaps in Agent Coverage.

## Phase 3 — Merge And Report

Unchanged from `multi-agent-orchestration.md` Phase 3. Use `references/report-template.md`.

In **Agent Coverage**, always state:

- Host: Claude Code
- Phase 1 parallel: branch-review-impact / branch-review-bugs / branch-review-security (which ran, which skipped)
- Phase 1 was simultaneous: yes / no (if no, explain why)
- CodeGraph: available or no-CodeGraph mode
- Phase 2 parallel: branch-review-verify + `/code-review` (which ran, simultaneous: yes/no)

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
  - Agent(branch-review-impact)
  - Agent(branch-review-bugs)
  - Agent(branch-review-security)
  - Agent(branch-review-verify)
  - Agent(general-purpose)
  - Skill(code-review)
```

Review project skills before trusting a repo — `allowed-tools` grants access without per-use
approval.

## Subagent Source Files

Installed from `agents/claude/` in this skill repo:

- `branch-review-impact.md` — shared surfaces, dependents, entry points
- `branch-review-bugs.md` — bug hunt queue, pattern validation, focused tests
- `branch-review-security.md` — security hints, exploitable issues
- `branch-review-verify.md` — Phase 2 lint/tests (parallel with `/code-review`)

To reinstall subagents only:

```bash
cp agents/claude/*.md ~/.claude/agents/
```

## Example User Prompts

```text
/branch-code-review
Multi-agent parallel review. Phase 1: spawn impact + bug hunt + security simultaneously.
Include working tree. Artifacts under work/.
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
