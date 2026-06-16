---
name: branch-code-review
description: "Review all code developed on the current branch since the branch was created or checked out from its starting point, with whole-branch impact analysis. Use when Codex needs to code review branch-local work without comparing to the default branch, including added files, file tree changes, modified files, dependent files, public components, shared/common files, dependency/package changes, routes/APIs, tests, risk-focused findings, and a strong no-CodeGraph fallback using local import/symbol/reference/test impact analysis."
---

# Branch Code Review

## Purpose

Use this skill to review an entire branch, not only isolated diff hunks. The review range is from the current branch's creation/check-out starting commit to `HEAD`, not from the repository's default branch to `HEAD`. Treat the branch as a product change: understand what was added, what was modified, what shared surfaces were touched, what depends on those surfaces, and what can break.

Lead with actionable findings. Summaries, inventories, and architectural notes support the review but do not replace it.

## Inputs

Require or infer:

- Target repository root.
- Current branch start commit. Prefer the oldest reflog entry for the current branch, because it represents where the branch was created or checked out locally.
- If the branch start cannot be inferred from git reflog, ask the user for the branch start commit/ref. Do not silently fall back to `origin/main`, `origin/master`, `main`, `master`, or another default branch.
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

Use the generated Markdown/JSON as a starting map, not as the final review. It includes committed inventory, staged/unstaged/untracked inventory, test command candidates, dependency deltas, resolved local importers, public symbol candidate deltas, symbol reference hints, deleted-file reference hints, nearby/importing test hints, and a risk-ranked no-CodeGraph triage queue. Verify high-risk areas by reading source.

## Structural Analysis

When a CodeGraph MCP server is available, prefer it for structural questions:

- Use `codegraph_context` for focused context around changed areas.
- Use `codegraph_impact` for changed exported functions, components, hooks, services, utilities, routes, and shared modules.
- Use `codegraph_callers` for specific changed functions/classes whose callers matter.
- Use `codegraph_trace` for user-facing flows, API-to-state paths, callback chains, and React/JSX dynamic hops.
- Use native search only for literal strings, comments, logs, config values, and after a specific file is already identified.

If CodeGraph reports that the project is not initialized, ask whether to run `codegraph init -i`.

## No-CodeGraph Impact Mode

When CodeGraph is unavailable, not installed, not initialized, or not exposed in the current tool list, do not downgrade to a shallow diff review. Treat `work/branch-review-context.md` and `work/branch-review-context.json` as the local impact map:

- Start with `No-CodeGraph Impact Triage`; inspect the highest-score files first.
- For changed shared/public/source files, read the file, its direct importer hints, symbol reference hints, deleted-file reference hints, and nearby/importing test hints.
- For deleted and renamed files, verify every deleted-path reference hint and search only for concrete unresolved names/paths that remain ambiguous.
- For changed dependency files, inspect the dependency deltas and consistency warnings before reviewing runtime code.
- For changed config, migration, route, API, command, or entrypoint files, trace one user-facing or runtime flow manually from entrypoint to side effects.
- If the script reports no direct importers, use language-native tools before generic grep: package manager test discovery, `go list`, `cargo metadata`, `python -m pytest --collect-only`, framework route manifests, or project-specific build commands when available.
- Keep residual risk explicit where local heuristics cannot resolve dynamic imports, framework conventions, reflection, dependency injection, generated code, or runtime wiring.

## Review Workflow

1. Establish branch metadata:
   - Current branch, inferred or provided branch start, commit range, commits since branch start.
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
   - Without CodeGraph, use the script's risk queue, direct importer hints, symbol reference hints, deleted-file reference hints, and test hints to choose what to read next.

5. Review behavior and risk:
   - Correctness, edge cases, data shape changes, race conditions, caching, auth/permission boundaries, persistence, navigation, error handling.
   - UI regressions across responsive states when frontend is involved.
   - Test gaps for changed behavior, especially shared modules and branch-level workflows.

6. Verify selectively:
   - Run focused tests/build/lint when available and reasonable.
   - For frontend changes, start the app and use browser verification when the UI behavior is central to the review.
   - If verification cannot run, say why and keep the residual risk explicit.

## Required Report Shape

Produce the review in this order:

1. Findings first, ordered by severity:
   - `P0` blocks release or causes data/security loss.
   - `P1` likely user-visible breakage or serious regression.
   - `P2` meaningful bug, missing coverage, or fragile shared behavior.
   - `P3` maintainability or small correctness risk.
   - Include file and line references when possible.
   - Explain the concrete failure mode, affected users/callers, and a suggested fix.

2. Open questions and assumptions.

3. Branch inventory:
   - Branch start/head/range.
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

If no actionable findings are found, say so clearly, then still provide inventory, impact map, and test gaps.

## Review Standards

- Do not spend the review praising the code. Mention good context only when it changes the risk assessment.
- Do not report style-only issues unless they create concrete maintenance or behavior risk.
- Do not assume a changed shared file is safe because the diff is small. Inspect its callers or impact.
- Do not rely on generated summaries alone. Read the highest-risk files directly.
- Do not treat no-CodeGraph mode as permission for grep-only review. Use the local impact map first, then targeted searches only for unresolved questions.
- Do not ignore deleted files; confirm all references were removed or migrated.
- Do not ignore added files; confirm they are wired into the app, tested, and named consistently.
- Do not ignore lockfiles; dependency changes are part of the code review.

## References

- Read `references/review-checklist.md` when the branch touches frontend UI, APIs, auth, data persistence, shared components, or dependency manifests.
- Read `references/report-template.md` when producing a formal review artifact.
