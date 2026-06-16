---
name: branch-code-review
description: "Review all code developed on the current branch since the branch was created or checked out from its starting point, with whole-branch impact analysis and bug-focused findings. Use when Codex needs to code review branch-local work without comparing to the default branch, including added files, file tree changes, modified files, dependent files, public components, shared/common files, dependency/package changes, routes/APIs, tests, security hints, bug pattern hints, risk-focused findings, and a strong no-CodeGraph fallback using local import/symbol/reference/test impact analysis."
---

# Branch Code Review

## Purpose

Use this skill to review an entire branch, not only isolated diff hunks. The review range is from the current branch's creation/check-out starting commit to `HEAD`, not from the repository's default branch to `HEAD`. Treat the branch as a product change: understand what was added, what was modified, what shared surfaces were touched, what depends on those surfaces, and **what bugs or regressions can ship**.

**Primary deliverable: actionable bug and regression findings.** Impact maps, inventories, and architecture notes support bug hunting but do not replace it.

## When To Use

| Scenario | Use this skill |
|----------|----------------|
| Local feature branch — full review since branch creation | Yes |
| WIP with uncommitted changes included | Yes |
| Need caller/impact analysis without default-branch diff | Yes |
| PR merge diff vs `main` only | Optional: add `--start-mode merge-base-with=origin/main` or run `review-bugbot` as second pass |
| Dedicated security pass | Run this first, then `review-security` if hints or auth/crypto surfaces appear |

## Inputs

Require or infer:

- Target repository root.
- Current branch start commit. Prefer the oldest reflog entry for the current branch, because it represents where the branch was created or checked out locally.
- Optional `--start-mode merge-base-with=<ref>` when the user wants PR-oriented range instead of branch-local range. State which mode was used.
- If the branch start cannot be inferred from git reflog, ask the user for the branch start commit/ref. Do not silently fall back to `origin/main`, `origin/master`, `main`, `master`, or another default branch unless the user explicitly requests merge-base mode.
- Review scope: default to `git diff <branch-start>..HEAD`.

Before analysis, check `git status --short --branch`. If there are uncommitted changes, state whether they are included. Do not discard or revert user changes.

## Fast Context Collection

Run the bundled script from the repository root when local git history is available. Include working tree changes unless the user explicitly asks for committed-only review:

```bash
python3 <skill-dir>/scripts/collect_branch_review_context.py --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
```

The script tries to infer the current branch start from the branch reflog. If that fails, pass the exact branch start commit or ref:

```bash
python3 <skill-dir>/scripts/collect_branch_review_context.py --start <branch-start-commit-or-ref> --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
```

For PR-oriented range against a target branch:

```bash
python3 <skill-dir>/scripts/collect_branch_review_context.py --start-mode merge-base-with=origin/main --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
```

Use the generated Markdown/JSON as a starting map, not as the final review. It includes committed inventory, staged/unstaged/untracked inventory, test command candidates, dependency deltas, resolved local importers, public symbol candidate deltas, symbol reference hints, deleted-file reference hints, nearby/importing test hints, **bug pattern hints**, **security pattern hints**, a **bug hunt queue**, and a risk-ranked no-CodeGraph triage queue. Verify high-risk areas by reading source and **prove bugs before reporting them**.

## Bug Hunting (Required)

After context collection, actively search for bugs — do not stop at impact analysis.

1. Read `references/bug-hunting-checklist.md` and work through it for changed control flow, data contracts, and integration wiring.
2. Start from `Bug Hunt Queue` and `Bug Pattern Hints` in the context report; treat each hint as a lead to validate or dismiss with evidence.
3. For every high-risk file, answer: **What can go wrong? Who breaks? How do I trigger it?**
4. Compare behavior at branch start vs `HEAD` for shared modules and entry points — look for removed guards, changed defaults, and deleted error paths.
5. Run focused tests or minimal reproduction when feasible; a failing test is stronger evidence than static reading.
6. If manual bug hunting is incomplete on a large branch, run `review-bugbot` as a second pass and deduplicate findings.

Report bugs with: trigger, expected vs actual, evidence (file:line or trace), severity, suggested fix.

## Security Pass (When Applicable)

When auth, user input, secrets, crypto, uploads, admin tools, dependencies, or infra config changed:

1. Read `references/security-checklist.md`.
2. Inspect `Security Pattern Hints` from the context script; confirm or dismiss each in source.
3. Escalate to `review-security` when exploitation path is unclear or impact is high.

## Structural Analysis

When a CodeGraph MCP server is available, prefer it for structural questions:

- Use `codegraph_context` for focused context around changed areas.
- Use `codegraph_impact` for changed exported functions, components, hooks, services, utilities, routes, and shared modules.
- Use `codegraph_callers` for specific changed functions/classes whose callers matter.
- Use `codegraph_trace` for user-facing flows, API-to-state paths, callback chains, and React/JSX dynamic hops — **especially when hunting logic bugs across hops**.
- Use native search only for literal strings, comments, logs, config values, and after a specific file is already identified.

If CodeGraph reports that the project is not initialized, ask whether to run `codegraph init -i`.

## No-CodeGraph Impact Mode

When CodeGraph is unavailable, not installed, not initialized, or not exposed in the current tool list, do not downgrade to a shallow diff review. Treat `work/branch-review-context.md` and `work/branch-review-context.json` as the local impact map:

- Start with `Bug Hunt Queue` and `No-CodeGraph Impact Triage`; inspect the highest-score files first.
- For changed shared/public/source files, read the file, its direct importer hints, symbol reference hints, deleted-file reference hints, bug/security hints, and nearby/importing test hints.
- For deleted and renamed files, verify every deleted-path reference hint and search only for concrete unresolved names/paths that remain ambiguous.
- For changed dependency files, inspect the dependency deltas and consistency warnings before reviewing runtime code.
- For changed config, migration, route, API, command, or entrypoint files, trace one user-facing or runtime flow manually from entrypoint to side effects and look for logic bugs along the path.
- If the script reports no direct importers, use language-native tools before generic grep: package manager test discovery, `go list`, `cargo metadata`, `python -m pytest --collect-only`, framework route manifests, or project-specific build commands when available.
- Keep residual risk explicit where local heuristics cannot resolve dynamic imports, framework conventions, reflection, dependency injection, generated code, or runtime wiring.

## Review Workflow

1. Establish branch metadata:
   - Current branch, inferred or provided branch start, start mode, commit range, commits since branch start.
   - Whether working tree changes are included.
   - Framework/runtime and test commands from package or build config.
   - Whether CodeGraph was available; if not, confirm the no-CodeGraph impact script was run.

2. Inventory the branch:
   - Added, modified, deleted, and renamed files.
   - New directories and file tree changes.
   - Dependency manifest and lockfile changes.
   - Generated assets, build outputs, migrations, schema files, fixtures, and tests.

3. Classify changed files:
   - Feature entry points: pages, routes, controllers, API handlers, screens, commands.
   - Shared surfaces: common components, UI primitives, hooks, utilities, stores, service clients, config, middleware, package exports.
   - Domain logic: validators, transforms, business rules, data access, permission checks.
   - Tests and docs.

4. Analyze impact:
   - For each shared surface, identify direct callers/importers and likely indirect flows.
   - For each new public component or exported API, inspect props, defaults, accessibility, loading/error/empty states, and call sites.
   - For modified public files, compare old and new behavior, not only syntax.
   - For package changes, inspect version risk, bundle/runtime impact, lockfile consistency, and whether the dependency is actually used.
   - Without CodeGraph, use the script's bug hunt queue, risk queue, direct importer hints, symbol reference hints, deleted-file reference hints, and test hints to choose what to read next.

5. **Hunt bugs and review behavior** (required):
   - Follow `references/bug-hunting-checklist.md`.
   - Correctness, edge cases, data shape changes, race conditions, caching, auth/permission boundaries, persistence, navigation, error handling.
   - UI regressions across responsive states when frontend is involved.
   - Test gaps for changed behavior — use `references/testing-review.md`.
   - Security when applicable — use `references/security-checklist.md`.

6. Verify selectively:
   - Run focused tests/build/lint when available and reasonable.
   - For frontend changes, start the app and use browser verification when the UI behavior is central to the review.
   - If verification cannot run, say why and keep the residual risk explicit.

## Large Branch Strategy

When the branch exceeds ~50 changed files or ~2000 added lines in diff stat:

- Review `Bug Hunt Queue` top entries and all entrypoint/migration/shared files first.
- Batch by domain; list files not deeply reviewed and their residual risk.
- Consider `review-bugbot` for merge-base logic coverage after branch-local pass.

## Required Report Shape

Produce the review in this order:

0. **Verdict** (one block):
   - **Verdict**: Request changes / Approve with nits / Approve
   - **Release risk**: High / Medium / Low
   - **Must-fix before merge**: count and short list
   - **Start mode**: branch-local reflog / explicit `--start` / merge-base-with=…

1. Findings first, ordered by severity:
   - **Bugs and regressions first** within each severity band when possible.
   - `P0` blocks release or causes data/security loss.
   - `P1` likely user-visible breakage, serious regression, or exploitable issue.
   - `P2` meaningful bug, missing coverage, or fragile shared behavior.
   - `P3` maintainability or small correctness risk.
   - Include file and line references when possible.
   - For bugs: trigger, expected vs actual, evidence, suggested fix.
   - **Confidence**: High / Medium / Low per finding when not proven by test.

2. Open questions and assumptions.

3. Branch inventory:
   - Branch start/head/range/start mode.
   - Added/modified/deleted/renamed files.
   - New file tree/directories.
   - Dependency changes.

4. Impact map:
   - Shared/public files touched.
   - Public components/hooks/utilities/APIs changed or added.
   - Direct dependent files and important flows.

5. Verification:
   - Commands run and results.
   - Browser/manual checks if performed.
   - Tests not run and remaining risk.
   - Impact-analysis mode used: CodeGraph, no-CodeGraph local impact map, or both.
   - Optional second passes: Bugbot, Security Review.

If no actionable findings are found, say so clearly, then still provide inventory, impact map, test gaps, and **residual bug risks you could not disprove**.

## Review Standards

- **Find real bugs.** Impact analysis alone is insufficient; trace failure modes and compare old vs new behavior.
- Do not report pattern hints as findings without validating them in context.
- Do not spend the review praising the code. Mention good context only when it changes the risk assessment.
- Do not report style-only issues unless they create concrete maintenance or behavior risk.
- Do not assume a changed shared file is safe because the diff is small. Inspect its callers or impact.
- Do not rely on generated summaries alone. Read the highest-risk files directly.
- Do not treat no-CodeGraph mode as permission for grep-only review. Use the local impact map and bug hunt queue first.
- Do not ignore deleted files; confirm all references were removed or migrated.
- Do not ignore added files; confirm they are wired into the app, tested, and named consistently.
- Do not ignore lockfiles; dependency changes are part of the code review.

## References

- Read `references/bug-hunting-checklist.md` for every review — required for bug-focused findings.
- Read `references/security-checklist.md` when the branch touches auth, input handling, secrets, crypto, or dependencies.
- Read `references/testing-review.md` when judging coverage and verification gaps.
- Read `references/review-checklist.md` when the branch touches frontend UI, APIs, auth, data persistence, shared components, or dependency manifests.
- Read `references/report-template.md` when producing a formal review artifact.

## Optional Follow-Up Skills

- `review-bugbot` — second opinion on logic bugs vs default/base branch; use when branch is large or bugs span many files.
- `review-security` — dedicated security subagent when hints or surfaces warrant deeper exploit analysis.
- `split-to-prs` — when the branch is too large to review safely as one unit.
