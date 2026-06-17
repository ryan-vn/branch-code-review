# Bug Hunting Checklist

Use this after the impact triage queue. The goal is to find **concrete bugs and regressions**, not only structural risk.

Start from `Bug Pattern Hints` and `Bug Hunt Queue` in `work/branch-review-context.md` when the context script ran. Treat hints as leads, not findings — read the surrounding code and prove a failure mode before reporting.

## Bug Hunt Workflow

1. **Pick targets**: high-risk files from triage, entry points, changed control flow, deleted fallback branches, and files with bug-pattern hints.
2. **Read behavior, not syntax**: for each target, state the intended behavior, inputs, outputs, and side effects before judging the diff.
3. **Trace one failure path**: follow a bug hypothesis from trigger → code path → wrong state → user-visible outcome.
4. **Cross-check callers**: for shared utilities, find at least one caller and verify the new behavior still matches its assumptions.
5. **Run focused verification**: execute the smallest test, script, or manual flow that would expose the bug.
6. **Report only proven or strongly evidenced bugs**: include trigger, expected vs actual, and affected callers/users.

## Control Flow And Logic

- Off-by-one, wrong comparator (`>` vs `>=`), inverted boolean, missing `else`, unreachable branch after early return.
- Switch/match missing cases; enum extended without handling new value.
- Null/undefined/nil/None handling removed or narrowed; optional chaining replaced with direct access.
- Default argument or fallback removed; empty string vs null treated differently than before.
- Wrong variable reused in nested scope; shadowed loop variable; stale captured value in callback/closure.
- Error swallowed: empty `catch`, `except: pass`, ignored return value, missing `return` after error branch.
- Guard clause removed; validation moved after side effect; validation only on happy path.
- Integer overflow, division by zero, modulo by zero, empty collection assumed non-empty.

## State, Concurrency, And Timing

- Read-modify-write without lock/transaction/version check.
- Check-then-act race (double submit, duplicate create, lost update).
- Async without await; fire-and-forget task whose failure is invisible.
- Stale state after navigation, tab switch, websocket reconnect, or cache hit.
- Missing cleanup: subscriptions, timers, listeners, file handles, DB connections.
- Unmount/update after async completion in UI code.
- Debounce/throttle removed or interval changed without updating callers.

## Data Shape And Contracts

- API request/response field renamed, removed, or type changed without client/server sync.
- Breaking change to shared type/interface used by multiple packages.
- Serializer/deserializer mismatch (date format, timezone, bigint, enum string vs number).
- Database migration: nullable → NOT NULL without backfill; dropped column still read; wrong default.
- Sort order, pagination cursor, or filter semantics changed silently.
- Cache key missing dimension (tenant, locale, user); invalidation too narrow or too broad.

## Boundaries And Edge Cases

- Empty list, single item, max-size input, whitespace-only string, zero, negative numbers.
- Time boundaries: DST, leap day, end-of-month, timezone conversion, `Date.now()` in tests.
- Unicode normalization, emoji, RTL text, very long strings.
- Permission denied vs not found confused; admin-only path reachable without check.
- Feature flag default changed; old clients hit new code path unexpectedly.

## Integration And Wiring

- Added file never imported, routed, registered, or exported.
- Renamed/deleted symbol still referenced (confirm script hints manually).
- Config/env var read but not documented; wrong env var name; missing default in prod.
- Event handler registered twice; listener never removed.
- Background job/cron missing idempotency or retry safety.

## Tests That Hide Bugs

- Assertion weakened to match bug (expect changed from `toBe(3)` to `toBeTruthy()`).
- Over-mocked test: implementation detail changed but mock still passes.
- Snapshot updated without understanding diff.
- Test covers happy path only while branch changed error handling.
- Deleted test file or removed case without replacement.

## When To Escalate To Bugbot

Use the `review-bugbot` skill as a second pass when:

- The branch is large and manual tracing is incomplete.
- Logic spans many files or dynamic dispatch obscures the path.
- You found suspicious patterns but cannot prove impact locally.
- The change touches auth, payments, billing, permissions, or data migration.

Bugbot compares against the repository default/base branch. Use branch-code-review for branch-local impact and bug hunting first; use Bugbot when you need a merge-base-focused second opinion on logic defects.

## Finding Format

Each bug finding must follow the artifact schema in `references/multi-agent-orchestration.md`.
At minimum:

- **ID**: stable within the artifact (e.g. BH1, BH2).
- **Trigger**: user action, input, or sequence that exposes the bug.
- **Expected vs actual**: what should happen vs what will happen.
- **Evidence**: file/line, caller, test failure, or traced path.
- **Reproduction**: smallest repro command/step, or "not reproduced (static read only)".
- **Severity**: P0–P3 per `references/severity-definitions.md`.
- **Confidence**: High / Medium / Low per the Severity×Confidence matrix.
- **Suggested fix**: smallest correction that preserves intended behavior.
