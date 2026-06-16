# Branch Code Review Report Template

## Verdict

- **Verdict**: Request changes / Approve with nits / Approve
- **Release risk**: High / Medium / Low
- **Must-fix before merge**:
- **Start mode**: branch-local reflog / explicit `--start` / merge-base-with=…
- **Review confidence**: High / Medium / Low

## Findings

List bugs and regressions before other finding types when severities tie.

### P0 Title

- Location: `path/to/file.ext:line`
- Type: Bug / Regression / Security / Test gap / …
- Confidence: High / Medium / Low
- Trigger: User action, input, or sequence that exposes the issue.
- Expected vs actual:
- Problem: Concrete failure mode.
- Impact: Affected users, callers, flows, or shared surfaces.
- Evidence: Diff hunk, caller, test failure, or traced path.
- Suggested fix: Smallest practical correction.

### P1/P2/P3 Title

- Location: `path/to/file.ext:line`
- Type:
- Confidence:
- Trigger:
- Expected vs actual:
- Problem:
- Impact:
- Evidence:
- Suggested fix:

## Open Questions

- List assumptions that affect review confidence.

## Branch Inventory

- Base:
- Branch start:
- Head:
- Range:
- Start mode:
- Commits reviewed:
- Working tree state:
- Impact-analysis mode:

### Added Files

### Modified Files

### Deleted/Renamed Files

### New Directories

### Dependency Changes

## Impact Map

### Bug Hunt Queue

### No-CodeGraph Triage Queue

### Shared/Public Files Touched

### Public Components/Hooks/Utilities/APIs

### Direct Dependents

### Symbol/Deleted-Reference Hints

### Bug Pattern Hints

### Security Pattern Hints

### Test Coverage Hints

### Important Flows

### Files Not Deeply Reviewed (large branches)

## Verification

- Commands run:
- Browser/manual checks:
- Second passes (Bugbot / Security Review):
- Not run:
- Residual risk:
