# Branch Code Review Report Template

**Depth over breadth.** The report's value is the Findings section — a few proven bugs beat
a long list of low-value items. Keep Impact Map / Branch Inventory as supporting context and
trim them when they add no risk signal. Every finding needs a stable **ID** (F1, F2…) and a
**reproduction** step so the user can act on it and reference it later. Severity and
confidence follow `references/severity-definitions.md`.

## Verdict

- **Verdict**: Request changes / Approve with nits / Approve (per Severity×Confidence matrix)
- **Release risk**: High / Medium / Low
- **Must-fix before merge**: list finding IDs (e.g. F1, F3)
- **Start mode**: branch-local reflog / explicit `--start` / merge-base-with=…
- **Review mode**: Multi-agent / Single-agent fallback
- **Agents run**: Impact / Bug Hunt / Security / Bugbot / Verification
- **Review confidence**: High / Medium / Low

## Findings

List bugs and regressions before other finding types when severities tie. Batch P3 nits into
a single entry instead of listing them individually.

### F1. [P0] Short title

- Source: [Bug Hunt] / [Impact] / [Security] / [Bugbot] / [Orchestrator]
- Severity: P0 / P1 / P2 / P3
- Confidence: High / Medium / Low
- Type: Bug / Regression / Security / Test gap / …
- Location: `path/to/file.ext:line`
- Trigger: User action, input, or sequence that exposes the issue (n/a for non-bugs).
- Expected vs actual:
- Problem: Concrete failure mode.
- Impact: Affected users, callers, flows, or shared surfaces.
- Evidence: Diff hunk, caller, test failure, or traced path.
- Reproduction: Smallest repro command/step, or "not reproduced (static read only)".
- Suggested fix: Smallest practical correction.

### F2. [P1/P2/P3] Short title

- Source:
- Severity:
- Confidence:
- Type:
- Location:
- Trigger:
- Expected vs actual:
- Problem:
- Impact:
- Evidence:
- Reproduction:
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

### Tool Usage
- CodeGraph: ...
- RTK / Shell: ...
- Fallback Grep/Read: ...

## Agent Coverage

- Review mode: Multi-agent / Single-agent
- Impact Agent: ran / skipped — artifact `work/branch-review-impact.md`
- Bug Hunt Agent: ran / skipped — artifact `work/branch-review-bugs.md`
- Security Agent: ran / skipped / not applicable — artifact `work/branch-review-security.md`
- Bugbot pass: ran / skipped
- Verification Agent: ran / skipped
- Files not deeply reviewed:
- Merge notes (deduped findings, agent disagreements):
