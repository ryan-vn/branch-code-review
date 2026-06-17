# Severity And Confidence Definitions

**Required reading for every review.** All agents must classify findings with the same
scale so Phase 3 merge and the final verdict are reproducible. Do not invent local
P-levels.

## Severity (P0–P3)

Severity = **impact if the bug ships**, independent of how confident you are.

| Level | Name | Definition | Merge implication |
|-------|------|------------|-------------------|
| **P0** | Critical / Blocker | Data loss or corruption, security hole enabling RCE / auth bypass / secret exposure, production crash or data exposure, financial loss, irreversible migration. Blocks release. | Must fix before merge |
| **P1** | High | Functional bug on a primary user/API flow that users can trigger, no safe workaround; or a serious security misconfiguration (overly broad CORS, missing auth on a new route). | Must fix before merge |
| **P2** | Medium | Bug on an edge case, secondary flow, or with a reasonable workaround; correctness issue that degrades but does not break the feature; missing test coverage for changed risky behavior. | Recommend fix before merge |
| **P3** | Low / Nit | Code quality, maintainability, minor inconsistency, documentation gap. No behavior risk by itself. | Optional; do not block merge |

### Severity heuristics

- A bug with **no trigger path a user/caller can reach** is at most P2 regardless of how bad it looks.
- A **deleted guard / removed error path** that previously protected a shared surface starts at P1 until proven safe.
- Style-only observations are P3 and must be folded into a single nits entry, not listed individually.
- "Could be a problem" without a concrete failure mode is an **Open Question**, not a finding.

## Confidence (High / Medium / Low)

Confidence = **how well you proved the failure mode**.

| Level | Requires |
|-------|----------|
| **High** | Reproduced (failing test, run command, traced path to user-visible outcome) OR direct evidence in the diff that the old/new behavior diverges. |
| **Medium** | Strong static read: caller verified, contract checked against at least one consumer, logic traced by hand but not executed. |
| **Low** | Suspicion from a pattern hint or unverified assumption; not traced end to end. |

## Severity × Confidence Decision Matrix

Use this to decide whether a finding blocks merge and how to present it.

| Severity＼Confidence | High | Medium | Low |
|----------------------|------|--------|-----|
| **P0** | Must fix | Must fix + verify repro | Convert to Open Question; flag for human verification; do not auto-block |
| **P1** | Must fix | Recommend fix before merge | Open Question (list under Open Questions, not Findings) |
| **P2** | Recommend fix | Record as finding | Record as finding, mark unverified |
| **P3** | Nit (batch) | Nit | Drop unless it changes risk assessment |

## Verdict Rules

- **Request changes**: any P0/P1 finding with Confidence ≥ Medium.
- **Approve with nits**: only P2/P3 remain.
- **Approve**: no findings, or only P3 nits.
- A P0/P1 at Low confidence does **not** auto-block — surface it under Open Questions and state what verification is needed. The reviewer (user) makes the final call.

## Applying During Merge (Phase 3)

When two agents report the same `file:line + failure mode`:
1. Keep the higher severity; if tied, keep higher confidence.
2. Merge evidence from both into one finding (single ID).
3. If agents disagree on severity, prefer the entry with direct execution evidence (test failure > trace > static read) and record the disagreement under Open Questions.
