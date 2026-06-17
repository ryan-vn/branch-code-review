# Multi-Agent Orchestration

Use this when running `branch-code-review` in **multi-agent mode** (default unless the user asks for a quick or single-agent review).

The **orchestrator** (current agent) collects context once, dispatches specialized readonly subagents in parallel, optionally runs verification, then merges artifacts into the final report.

Subagents must receive **self-contained prompts**. Do not assume they inherit chat history.

## Roles

| Agent | subagent_type | When | Output artifact |
|-------|---------------|------|-----------------|
| Orchestrator | (current agent) | Always | `work/branch-review-context.md`, final merged report |
| Impact Agent | `explore` | Always | `work/branch-review-impact.md` |
| Bug Hunt Agent | `generalPurpose` | Always | `work/branch-review-bugs.md` |
| Security Agent | `security-review` | Security surfaces or hints present | `work/branch-review-security.md` |
| Bugbot Agent | `bugbot` | Large branch, or Bug Hunt incomplete | summarized in final report |
| Verification Agent | `shell` | Test commands detected and reasonable to run | notes in final report |

## Subagent Platform Mapping And Fallback

The `subagent_type` column lists **Cursor** types. On other hosts, map each role to the
closest read-only research/general subagent:

| Role | Cursor | Claude Code | Codex | If unavailable |
|------|--------|-------------|-------|----------------|
| Impact | `explore` | `Task` `general-purpose` | research agent | fold into Bug Hunt agent |
| Bug Hunt | `generalPurpose` | `Task` `general-purpose` | research agent | single-agent fallback |
| Security | `security-review` | `Task` `general-purpose` | research agent | skip; note in Agent Coverage |
| Bugbot | `bugbot` | only if skill installed | — | skip; note in Agent Coverage |
| Verification | `shell` | `Bash` | shell | skip; note residual risk |

Rules:

- **Never dispatch assuming a subagent has CodeGraph MCP** unless you verified it. Precompute
  structural context in Phase 0 and pass it via `work/branch-review-codegraph.md`.
- If the host has **no read-only parallel subagent at all**, use the single-agent workflow in
  SKILL.md. State this explicitly in the report's Agent Coverage section.
- A missing external skill (`review-bugbot`, `review-security`) is a **skip**, not a failure:
  record it under Agent Coverage and continue.

## Artifact Schema (all review agents)

Every review subagent writes its artifact as Markdown with a **machine-parseable finding
format** so Phase 3 dedupe and ordering can be done mechanically. Use this exact block shape
for each finding:

```markdown
### [SOURCE] short title
- id: BH1|SEC1|IMP1|BUG1      # stable id within this artifact
- location: path/to/file.ext:line
- severity: P0|P1|P2|P3
- confidence: High|Medium|Low
- type: Bug|Regression|Security|Test gap|Maintainability
- trigger: <user action/input/sequence; "n/a" for non-bugs>
- expected_vs_actual: <what should happen vs what happens>
- evidence: <diff hunk / caller / traced path / test failure>
- reproduction: <smallest repro command or step; "not reproduced" if only static read>
- suggested_fix: <smallest correction>
```

Rules:

- Non-finding sections (executive summary, impact map, residual uncertainty) stay as prose.
- Impact findings are usually P2/P3 "surface touched" notes; real bugs flow through Bug Hunt/Security.
- If a field does not apply, write `unknown` or `n/a` — **never omit a field**, gaps break dedupe.
- Phase 3 dedupes on `location` + `expected_vs_actual` (the failure mode), keeps the higher
  `severity` then higher `confidence`, and merges `evidence`/`reproduction` from both entries.
- Severity and confidence must follow `references/severity-definitions.md`.

## Phase 0 — Orchestrator Prepare

1. Confirm repository root and branch metadata (`git status --short --branch`).
2. Run context collection:

```bash
python3 <skill-dir>/scripts/collect_branch_review_context.py --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
```

3. Read `work/branch-review-context.json` (or `.md`) and extract:
   - `repo`, `start`, `head`, `branch`, `range`, `start_mode`
   - `bug_hunt_queue` top 15 paths
   - `pattern_findings` counts (bug vs security)
   - `shared_files`, `entrypoint_files`, `migration_files`, `dependency_files`
   - `test_commands`
   - diff stat / changed file count

4. Decide mode:
   - **Multi-agent** (default): 2+ changed source files, or any shared/entrypoint/migration/dependency change.
   - **Single-agent fallback**: user asked for quick review, empty diff, or context script failed.

5. Create `work/` if missing.

6. **Tool routing gate** — read `references/tool-routing.md`:
   - If CodeGraph MCP available: `codegraph_status` → precompute impact/context/trace for top triage targets → write `work/branch-review-codegraph.md`.
   - Run git via Shell (`git status --short --branch`, `git log --oneline <range>`, `git diff --stat <range>`) for RTK hook compatibility.
   - Do not start Phase 1 until context script output exists (and codegraph bundle when index is ready).

## Phase 1 — Parallel Dispatch

Launch **Impact Agent** and **Bug Hunt Agent** in the **same message** (parallel Task calls).

Launch **Security Agent** in parallel when **any** of:
- `security pattern hints` exist in context
- changed files under auth/api/config/dependency/migration paths
- entrypoint files changed

Skip Security Agent when none apply; note "Security pass skipped" in the final report.

All review subagents:
- `readonly: true`
- `run_in_background: false` unless the user asked for background

### Impact Agent prompt

```text
Full Repository Path: <absolute repo path>
Skill Directory: <absolute path to branch-code-review skill>
Branch Review Context: <absolute path>/work/branch-review-context.md
CodeGraph Bundle: <absolute path>/work/branch-review-codegraph.md
Tool Routing: <skill-dir>/references/tool-routing.md
Branch Start: <start sha or ref>
Head: <head sha>
Range: <start..HEAD>
Start Mode: <reflog | explicit | merge-base-with=...>

Role: Impact Analysis Agent (branch-code-review).

Read the Branch Review Context and CodeGraph Bundle files completely.

**Do NOT call CodeGraph MCP** — use the precomputed bundle only. Do NOT run repo-wide Grep or SemanticSearch; use bundle + context importer hints.

Do NOT hunt for logic bugs — Bug Hunt Agent owns that.

Deliver in work/branch-review-impact.md:
1. Executive summary (5 bullets max)
2. Shared/public surfaces touched + direct dependents
3. Entry points and important flows affected
4. Dependency, migration, and config risks
5. Top 10 triage files with why they matter
6. Residual impact uncertainty

Return a 3-5 sentence summary and confirm the artifact path.
```

### Bug Hunt Agent prompt

```text
Full Repository Path: <absolute repo path>
Skill Directory: <absolute path to branch-code-review skill>
Branch Review Context: <absolute path>/work/branch-review-context.md
CodeGraph Bundle: <absolute path>/work/branch-review-codegraph.md
Bug Hunting Checklist: <skill-dir>/references/bug-hunting-checklist.md
Tool Routing: <skill-dir>/references/tool-routing.md
Branch Start: <start>
Head: <head>
Range: <range>

Role: Bug Hunt Agent (branch-code-review).

Read context, codegraph bundle, and bug-hunting checklist. Start from Bug Hunt Queue and Bug Pattern Hints.
**Do NOT call CodeGraph MCP or repo-wide Grep** — use bundle + targeted Read on queued files only.
Validate every hint in source — hints are leads, not findings.

For each proven bug/regression, include:
- Severity P0-P3
- Location file:line
- Trigger
- Expected vs actual
- Evidence
- Suggested fix
- Confidence High/Medium/Low

Compare behavior at branch start vs HEAD for shared modules and removed guards/error paths.
Run focused tests when feasible.

Write work/branch-review-bugs.md with a Findings section (bugs first) and Test Gaps section.

Return: count of P0-P3 findings and artifact path.
```

### Security Agent prompt

Use `security-review` subagent with:

```text
Full Repository Path: <absolute repo path>
Diff: natural language
Change Description:
<context summary: list changed files grouped by auth/api/config/deps from branch-review-context>
Custom Instructions: Branch-local review range <start..HEAD>. Read <skill-dir>/references/security-checklist.md. Confirm or dismiss Security Pattern Hints from work/branch-review-context.md. Focus on exploitable issues and data exposure.
```

After Security Agent returns, orchestrator saves a structured summary to `work/branch-review-security.md` if the subagent did not write a file.

## Phase 2 — Conditional Follow-Up (Sequential)

After Phase 1 agents return:

| Condition | Action |
|-----------|--------|
| Changed files > 50 OR diff stat added lines > 2000 OR Bug Hunt Agent reports incomplete coverage | Launch `bugbot` (`review-bugbot` skill shape, Diff: `branch changes`) |
| `test_commands` non-empty and user did not say skip tests | Launch `shell` Verification Agent with top 1-2 focused commands |
| Security Agent found P0/P1 and exploit path unclear | Keep findings; do not auto-fix |

### Bugbot prompt (when triggered)

Follow `review-bugbot` skill. Add to Custom Instructions:

```text
This is pass 2 after branch-local bug hunt. Dedupe against work/branch-review-bugs.md themes. Focus on logic bugs and regressions vs base branch.
```

### Verification Agent prompt

```text
Repository: <absolute path>
Run focused verification only — do not modify code. Honor the skill's read-only contract.

From work/branch-review-context.json test_commands, run ONLY side-effect-free commands:
- Allowed: lint, typecheck, and unit tests scoped to touched modules.
- Do NOT run: e2e/integration suites, anything that writes to a DB, makes network calls,
  sends email, or mutates shared state — unless the user explicitly approved that command.
- If the only available command is a heavy suite (e.g. `go test ./...`, `cargo test`, full
  e2e), do not run it; report it as residual risk and ask the user.

Prefer: lint/typecheck > unit tests for touched modules > (full suite only with user approval).

Return: commands run, pass/fail, relevant failure snippets, and residual risk if tests not run.
```

## Phase 3 — Orchestrator Merge

Read all artifacts:
- `work/branch-review-impact.md`
- `work/branch-review-bugs.md`
- `work/branch-review-security.md` (if exists)
- Bugbot summary (if run)
- Verification notes (if run)

Merge rules (see `references/severity-definitions.md` for the Severity×Confidence matrix):
1. **Dedupe** by `location` + `expected_vs_actual` (the failure mode); keep higher severity then higher confidence; merge `evidence`/`reproduction`.
2. **Order findings**: P0 → P1 → P2 → P3; bugs/regressions before test gaps before maintainability.
3. **Tag source**: `[Bug Hunt]`, `[Impact]`, `[Security]`, `[Bugbot]`, `[Orchestrator]`.
4. **Verdict**: Request changes if any P0/P1 at Confidence ≥ Medium; move Low-confidence P0/P1 to Open Questions (do not auto-block); Approve with nits if only P2/P3; Approve if none.
5. **Conflict handling**: if agents disagree, prefer finding with direct evidence (test failure > trace > static read) and list disagreement under Open Questions.

Produce final report using `references/report-template.md`.

Include **Agent Coverage** section:
- Which agents ran / skipped
- Files called out as not deeply reviewed
- Residual risk

## Failure Handling

| Failure | Action |
|---------|--------|
| Context script fails | Ask user for `--start`; fall back to single-agent review |
| One parallel agent fails | Retry once; continue merge with other artifacts; note gap |
| All parallel agents fail | Fall back to single-agent workflow in SKILL.md |
| External skill missing (`review-bugbot`, `review-security`) | Skip that pass; record under Agent Coverage; continue merge |
| Specialized `subagent_type` unavailable on host | Skip role or fold into another agent per Platform Mapping; record under Agent Coverage |
| Empty diff | Stop; report no changes |

## Single-Agent Fallback

Use when user requests quick review, or multi-agent dispatch is unavailable.

Follow the monolithic workflow in SKILL.md (context → bug hunt → security → report) without Task dispatch.

## User Overrides

| User says | Behavior |
|-----------|----------|
| "quick review" / "single agent" | Single-agent fallback |
| "skip security" | Skip Security Agent |
| "skip tests" | Skip Verification Agent |
| "no bugbot" | Skip Bugbot pass |
| "parallel" / "multi-agent" (default) | Full orchestration |
