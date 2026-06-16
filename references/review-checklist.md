# Branch Review Checklist

Use this checklist selectively. Prioritize sections that match the changed files and affected flows.

**Required companion docs:**

- `bug-hunting-checklist.md` — find concrete bugs and regressions (required every review).
- `security-checklist.md` — when auth, input, secrets, crypto, or deps changed.
- `testing-review.md` — when judging whether behavior is actually covered.

## Bug Hunting

- Start from `Bug Hunt Queue` and `Bug Pattern Hints` in the context script output.
- For each high-risk file: what can go wrong, who breaks, how to trigger it.
- Compare behavior at branch start vs `HEAD` for guards, defaults, and error paths.
- Trace at least one failure path from trigger to user-visible outcome before reporting.
- Run focused tests or minimal repro when possible.
- Escalate to `review-bugbot` when the branch is too large for complete manual tracing.

## Branch And Diff

- Confirm branch start, head, commit range, and any optional merge-base context.
- Identify uncommitted changes and whether they are included.
- Compare `git diff --name-status`, `git diff --stat`, and changed dependency manifests.
- Check added, deleted, and renamed files separately.
- Check whether generated files, snapshots, or build outputs were committed intentionally.

## No-CodeGraph Impact Map

- Run `collect_branch_review_context.py --include-working-tree` and use the risk-ranked triage queue.
- Inspect direct importer hints for changed source/shared files before broader search.
- Inspect public symbol candidate deltas and symbol reference hints for changed APIs, components, utilities, hooks, services, and data models.
- Inspect deleted-file reference hints for every deleted or renamed file.
- Inspect nearby/importing test hints before claiming coverage is absent.
- Treat unresolved dynamic imports, framework wiring, generated code, dependency injection, reflection, or runtime registration as residual risk.

## Added Files

- Confirm each added file is reachable from a route, command, export, test, or documented entry point.
- Check naming and folder placement against adjacent files.
- Look for missing tests, missing exports, or dead code.
- Inspect added components for loading, empty, error, disabled, and responsive states.
- Inspect added APIs for validation, auth, error shape, and backward compatibility.

## Modified Files

- Compare behavior before and after the branch.
- For modified shared modules, inspect callers/importers and downstream assumptions.
- Look for changed defaults, changed return shapes, changed timing, and changed side effects.
- Check whether old tests still assert the intended behavior.
- Check deleted branches and fallback logic carefully.

## File Tree And Architecture

- Identify new directories and whether they match existing architecture.
- Check whether feature files are colocated consistently.
- Check whether public exports were added from package barrels or index files.
- Watch for accidental coupling across domains.
- Watch for duplicated utilities or components that should reuse existing shared code.

## Dependencies

- Inspect `package.json`, lockfiles, build config, and runtime config.
- Review dependency delta output from the context script when available.
- Confirm new packages are used and justified.
- Check version compatibility, peer dependencies, bundle impact, and runtime environment assumptions.
- Confirm lockfile changes match manifest changes.
- Watch for packages that duplicate existing dependencies.

## Public Components And Shared Files

- Treat changes under `components`, `ui`, `shared`, `common`, `lib`, `utils`, `hooks`, `stores`, `services`, `api`, `config`, and package export files as shared-surface changes until proven otherwise.
- Identify direct callers/importers.
- Check props, defaults, optional fields, event contracts, refs, accessibility, and styling hooks.
- Check whether changed utilities preserve behavior for all existing callers.
- Check whether shared CSS/tokens/theme changes affect unrelated screens.

## Frontend UI

- Check responsive layout, text overflow, keyboard navigation, focus management, and ARIA semantics.
- Check loading, empty, error, and retry states.
- Check permission-gated UI and disabled states.
- Check network race conditions and stale state after navigation.
- Use browser verification for central UI behavior when feasible.

## Backend/API/Data

- Check request validation, auth/authorization, idempotency, pagination, sorting, filtering, and error handling.
- Check database migrations, rollback assumptions, nullability, defaults, and data backfills.
- Check cache invalidation and consistency between read/write paths.
- Check whether response shape changes break existing clients.

## Tests

- Confirm new behavior has tests at the right level: unit for pure logic, integration for API/data flows, UI tests for user workflows.
- Confirm shared modules have regression coverage for existing callers.
- Use detected test command candidates as a starting point, then narrow to focused tests when possible.
- Run focused tests when available.
- If tests cannot run, report the exact limitation and residual risk.
