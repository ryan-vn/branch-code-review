# Testing Review Checklist

Use when judging whether changed behavior is actually protected against regressions.

## Coverage Mapping

- Map each changed source file to nearby/importing tests from the context script.
- Flag source changes with no test neighbor and no test file in the branch diff.
- Flag deleted or renamed tests when corresponding source still exists.

## Test Quality

- Assertions match behavior, not implementation details that can change safely.
- Error paths, permission denied, empty input, and timeout/failure cases covered where logic changed.
- Mocks reflect real contracts; mock return shape matches production.
- Snapshots: understand why snapshot changed; reject snapshot-only updates that mask bugs.
- Flaky signals: fixed `sleep`, wall-clock time, random without seed, shared mutable global state.

## Test Level Fit

- Pure logic → unit tests.
- API + DB + auth → integration tests.
- User workflow / navigation → e2e or UI tests.
- Shared module change → at least one caller-level regression test.

## Verification Section Requirements

In the final report, state:

- Commands run and pass/fail.
- Tests intentionally not run and why.
- Behavior changed but untested — list by file/flow.
- Whether failing tests were observed and interpreted as pre-existing vs introduced.
