---
name: branch-code-review
description: >-
  Reviews all code developed on the current branch since branch creation or checkout,
  using multi-agent orchestration (impact, bug hunt, security), whole-branch impact
  analysis, and bug-focused findings. Use when reviewing a feature branch, WIP changes,
  branch-local diffs, shared-surface impact, dependency changes, or when the user asks
  for branch code review, bug hunting on a branch, or review since branch was created.
disable-model-invocation: true
metadata:
  author: ryan-vn
  repository: https://github.com/ryan-vn/branch-code-review
  license: MIT
  version: "1.1.0"
---

# Branch Code Review

## Purpose

Use this skill to review an entire branch, not only isolated diff hunks. The review range is from the current branch's creation/check-out starting commit to `HEAD`, not from the repository's default branch to `HEAD`. Treat the branch as a product change: understand what was added, what was modified, what shared surfaces were touched, what depends on those surfaces, and **what bugs or regressions can ship**.

**Primary deliverable: actionable bug and regression findings.** Impact maps, inventories, and architecture notes support bug hunting but do not replace it.

**Out of scope:** This skill does not commit, push, open pull requests, merge branches, or modify application source code. It produces review artifacts under `work/` and a report only.

## Multi-Agent Mode (Default)

Unless the user asks for a **quick** or **single-agent** review, run **multi-agent orchestration**.

Read and follow `references/multi-agent-orchestration.md` completely.

```text
Phase 0  Orchestrator → collect context (script) + branch metadata
Phase 1  Parallel     → Impact Agent + Bug Hunt Agent [+ Security Agent]
Phase 2  Sequential   → Bugbot (large branch) + Verification (tests)
Phase 3  Orchestrator → merge artifacts → final report
```

| Role | Cursor subagent_type | Output |
|------|----------------------|--------|
| Orchestrator | (current agent) | `work/branch-review-context.md`, final report |
| Impact | `explore`, readonly | `work/branch-review-impact.md` |
| Bug Hunt | `generalPurpose`, readonly | `work/branch-review-bugs.md` |
| Security | `security-review`, readonly | `work/branch-review-security.md` |
| Bugbot | `bugbot`, readonly | merged into final report |
| Verification | `shell` | verification notes in final report |

**Platform mapping:** the `subagent_type` values above are Cursor-specific. On Claude Code
use `Task` with `general-purpose` (or the platform's read-only research agent); on Codex use
its equivalent. If a platform has no equivalent for a specialized role (`bugbot`,
`security-review`), **skip that pass and record it under Agent Coverage** — never let
dispatch silently fail. If no read-only parallel subagent exists, use single-agent fallback.

Dispatch Impact + Bug Hunt (+ Security when applicable) **in one message with parallel Task calls**. Subagents get **self-contained prompts** from the orchestration doc — never rely on chat history.

After subagents return, merge with dedupe rules in the orchestration doc and produce the report from `references/report-template.md`.

**Single-agent fallback:** quick review, empty diff, context script failure, or Task dispatch unavailable → run the monolithic workflow below without subagents.

## When To Use

| Scenario | Use this skill |
|----------|----------------|
| Local feature branch — full review since branch creation | Yes (multi-agent default) |
| WIP with uncommitted changes included | Yes |
| Need caller/impact analysis without default-branch diff | Yes |
| Quick sanity check | Yes — user says "quick" → single-agent |
| PR merge diff vs `main` only | `--start-mode merge-base-with=origin/main` or Bugbot pass |

## Inputs

Require or infer:

- Target repository root.
- Current branch start commit. Prefer the oldest reflog entry for the current branch.
- Optional `--start-mode merge-base-with=<ref>` for PR-oriented range.
- If branch start cannot be inferred, ask the user for `--start`. Do not silently fall back to default branch unless merge-base mode is requested.
- Review scope: default `git diff <branch-start>..HEAD`.

Before analysis, check `git status --short --branch`. State whether uncommitted changes are included.

## Fast Context Collection

Run from repository root (Orchestrator Phase 0):

```bash
python3 <skill-dir>/scripts/collect_branch_review_context.py --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
```

With explicit start or merge-base mode — see `references/multi-agent-orchestration.md`.

Context includes: inventory, bug hunt queue, bug/security pattern hints, impact triage, dependency deltas, test commands. Subagents and orchestrator must read this file — do not substitute ad-hoc git diffs alone.

## Tool Routing (Required)

Read and follow `references/tool-routing.md` for **every** review.

**Phase 0 gate (orchestrator, before subagents):**

1. Run context script (above).
2. If `user-codegraph` MCP is available: `codegraph_status` → precompute impact/context/trace for top triage files → write `work/branch-review-codegraph.md`.
3. Use **Shell** for git metadata (`git status`, `git log --oneline <range>`, `git diff --stat`) so RTK hooks can rewrite commands when installed.
4. Do **not** use Grep/SemanticSearch/Glob loops for symbol or caller lookup when CodeGraph is ready.

Subagents often **lack CodeGraph MCP** — pass precomputed `work/branch-review-codegraph.md` in their prompts.

Final report must include **Tool Usage** (CodeGraph calls, RTK-eligible shell, fallback Grep/Read counts).

## Bug Hunting (Required)

Owned by **Bug Hunt Agent** in multi-agent mode; orchestrator validates merge quality.

1. Read `references/bug-hunting-checklist.md`.
2. Start from Bug Hunt Queue and Bug Pattern Hints; validate hints in source.
3. For each high-risk file: **What can go wrong? Who breaks? How do I trigger it?**
4. Compare branch start vs `HEAD` for removed guards and error paths.
5. Run focused tests when feasible.

Report bugs with: trigger, expected vs actual, evidence, severity, suggested fix, confidence.

## Security Pass (When Applicable)

Owned by **Security Agent** in multi-agent mode when security surfaces or hints exist.

1. Read `references/security-checklist.md`.
2. Confirm or dismiss Security Pattern Hints.
3. Use `security-review` subagent per orchestration doc.

## Structural Analysis

When CodeGraph MCP is available, **mandatory** — follow `references/tool-routing.md`:

- Phase 0: `codegraph_status` → precompute bundle → `work/branch-review-codegraph.md`
- `codegraph_context` — focused context (prefer over SemanticSearch + Read loops)
- `codegraph_impact` — changed exports/shared modules
- `codegraph_callers` / `codegraph_callees` — dependency direction
- `codegraph_trace` — one user-facing flow per review minimum
- `codegraph_explore` — multiple symbols in one call
- **Do not grep first** for symbol/caller questions when index is ready

If CodeGraph reports not initialized, ask whether to run `codegraph init -i`; then use no-CodeGraph mode.

## No-CodeGraph Impact Mode

When CodeGraph is unavailable, use `work/branch-review-context.md` as the local impact map. Do not downgrade to repo-wide Grep. Grep only for literal strings after triage queue and importer hints are exhausted.

## Monolithic Workflow (Single-Agent Fallback)

1. Establish branch metadata and run context script.
2. Inventory added/modified/deleted/renamed files and dependencies.
3. Classify entry points, shared surfaces, domain logic, tests.
4. Analyze impact (callers, flows, package risk).
5. Hunt bugs (`bug-hunting-checklist.md`), security (`security-checklist.md`), tests (`testing-review.md`).
6. Verify selectively; note residual risk.

## Large Branch Strategy

When changed files > ~50 or diff stat > ~2000 lines:

- Parallel agents still run; Bug Hunt focuses on Bug Hunt Queue top entries + all entrypoint/migration/shared files.
- Trigger Bugbot pass (Phase 2).
- List files not deeply reviewed under Agent Coverage.

## Required Report Shape

0. **Verdict**: Request changes / Approve with nits / Approve per the Severity×Confidence matrix (`references/severity-definitions.md`); release risk; must-fix finding IDs; start mode; **agents run**.

1. **Findings** (P0→P3, bugs first), each with a stable **ID** (F1…), source tag `[Bug Hunt]` / `[Security]` / `[Bugbot]` / etc., severity, confidence, and reproduction step.

2. Open questions and assumptions (Low-confidence P0/P1 go here, not in Findings).

3. Branch inventory.

4. Impact map (from Impact Agent artifact).

5. Verification + **Agent Coverage** (who ran, what was skipped, residual risk).

Use `references/report-template.md`. Prefer **depth over breadth**: a few proven bugs beat
a long list of low-value items; trim inventory/impact sections when they add no risk signal.

## Review Standards

- **Find real bugs.** Impact analysis alone is insufficient.
- Do not report unvalidated pattern hints as findings.
- Merge subagent outputs with dedupe; prefer evidence-backed findings.
- Do not praise code unless it changes risk assessment.
- Do not report style-only issues unless they create behavior risk.
- Do not ignore deleted files, added wiring, or lockfiles.

## References

- `references/severity-definitions.md` — **required** P0–P3 + Confidence + verdict matrix
- `references/multi-agent-orchestration.md` — **required in multi-agent mode**
- `references/tool-routing.md` — **required** CodeGraph + fallback routing
- `references/bug-hunting-checklist.md` — required for bug findings
- `references/security-checklist.md` — auth, secrets, deps
- `references/testing-review.md` — coverage gaps
- `references/review-checklist.md` — UI, API, persistence
- `references/report-template.md` — final artifact shape

## Related Skills

- `review-bugbot` — Phase 2 logic pass vs base branch (orchestrated automatically on large branches)
- `review-security` — same subagent as Security Agent; prefer orchestration dispatch
- `split-to-prs` — branch too large to review safely as one unit
