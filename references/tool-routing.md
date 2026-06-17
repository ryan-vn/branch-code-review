# Tool Routing (Required)

Follow this routing **before** reading files ad hoc or running broad searches. Skills are instructions — compliance is measured by **which tools you actually call**. The final report must include a **Tool Usage** line listing CodeGraph, RTK-eligible shell, and fallback tools used.

**Claude Code:** use **Bash** instead of Shell; default to **No-CodeGraph mode** unless MCP is
present. See `references/claude-code.md` for platform dispatch.

## Phase 0 Gate (Orchestrator, before subagents)

Run in order:

1. **Context script** (required):
   ```bash
   python3 <skill-dir>/scripts/collect_branch_review_context.py --include-working-tree --output work/branch-review-context.md --json-output work/branch-review-context.json
   ```

2. **CodeGraph status** (required when `user-codegraph` MCP is in the tool list):
   - Call `codegraph_status` once.
   - If not initialized → ask user about `codegraph init -i`; continue in no-CodeGraph mode only after stating that.

3. **CodeGraph preflight bundle** (required when index is ready):
   - For top 10 paths from `bug_hunt_queue` in context JSON, run **one** `codegraph_impact` or `codegraph_context` per shared/entrypoint file (batch via `codegraph_explore` when many symbols in same file).
   - For one entrypoint flow, run **one** `codegraph_trace`.
   - Write results to `work/branch-review-codegraph.md` (orchestrator creates this). Subagents **must read this file** — do not assume subagents have CodeGraph MCP.

4. **Git via Shell** (narrow, path-scoped — do not inline huge output into prompts):
   ```bash
   git status --short --branch
   git log --oneline <start>..HEAD
   git diff --stat <start>..HEAD
   ```
   Read large diffs from `work/branch-review-context.md` instead of pasting them into chat.

## Tool Selection Matrix

| Intent | First choice | Second choice | Avoid |
|--------|--------------|---------------|--------|
| Symbol / function / class location | `codegraph_search` | — | Grep, Glob+Read loop |
| Area / feature context | `codegraph_context` | — | SemanticSearch, many Reads |
| Who calls X? | `codegraph_callers` | context JSON importer hints | Grep for symbol name |
| What does X call? | `codegraph_callees` | — | manual import parsing |
| Flow A → B | `codegraph_trace` | — | chained Grep |
| Blast radius of change | `codegraph_impact` | context script triage | full-repo Grep |
| Several related symbols | `codegraph_explore` | — | many `codegraph_node` calls |
| Directory survey | `codegraph_files` | `Glob` | `find` via shell unless RTK |
| Literal string / comment / config value | `Grep` | Shell `rg` | CodeGraph |
| Read known file from triage queue | `Read` | — | Read entire repo |
| Branch file inventory | context script output | — | repeated `git diff` reads |
| Run tests / lint | Shell | — | — |

## CodeGraph Rules (from MCP server policy)

- **Do not grep first** when looking up a symbol by name — `codegraph_search` is faster and returns kind + location + signature.
- **Do not chain** `codegraph_search` + `codegraph_node` when you want context — use **one** `codegraph_context`.
- **Do not loop** `codegraph_node` over many symbols — use **one** `codegraph_explore`.
- **Do not query immediately after editing** — index lags ~1s.
- Answer structural questions in **2–3 CodeGraph calls**, then **one** `codegraph_explore` or `Read` for bodies if needed.

## Shell And Optional RTK

Prefer **Shell** for git metadata and literal ripgrep searches when CodeGraph does not apply.
Keep commands narrow and path-scoped regardless of tooling:

1. Prefer context script output (`work/branch-review-context.md`) over re-running a full
   `git diff` in shell.
2. For literal strings at a known path: `rg '<pattern>' <path>` via Shell, or the Grep tool.
3. Never paste megabyte-scale diffs into prompts — read from the artifact file instead.

**RTK (Realtime Token Kompress)** is an *optional*, user-installed hook that rewrites Shell
commands at hook time. It is **not required** and may not be installed. Do not write routing
that depends on it; the narrow-command guidance above is valuable with or without RTK. RTK
does not apply to Grep / Read / SemanticSearch / CodeGraph MCP calls.

## No-CodeGraph Mode

When CodeGraph is unavailable:

1. Use `work/branch-review-context.md` impact map and bug hunt queue — **not** repo-wide Grep.
2. Read highest-risk files directly from the queue.
3. Use Grep only for **concrete unresolved** path/symbol names after reading importer hints.

## Multi-Agent Mode

| Role | CodeGraph access | Routing |
|------|------------------|---------|
| Orchestrator | Yes (if MCP available) | Runs Phase 0 gate; writes `work/branch-review-codegraph.md` |
| Impact Agent | Often **no** | Read context + codegraph bundle; do not spawn Grep loops |
| Bug Hunt Agent | Often **no** | Read context + codegraph bundle + checklist; Read flagged files |
| Security Agent | Varies | Read context + security hints; Grep only for literal secrets paths |

**Never dispatch subagents expecting them to call CodeGraph** unless you verified that subagent type exposes MCP. Precompute structural context in Phase 0.

## Anti-Patterns (do not do these)

- ❌ `Glob` → `Read` 20 files to find callers when CodeGraph is available
- ❌ `SemanticSearch` for "how does auth work" when `codegraph_context` applies
- ❌ Full `git diff` without range/limit when context script already ran
- ❌ Subagent prompt says "use CodeGraph" but subagent has no MCP
- ❌ Report omits Tool Usage section

## Report: Tool Usage (required)

In the final report Verification or Agent Coverage section, include:

```markdown
### Tool Usage
- CodeGraph: status ready / not initialized / not available — calls: impact N, context N, trace N, explore N
- Shell: git/rg used for: ... (RTK hooks: active / not installed / not checked)
- Fallback: Grep N calls (literal-only: yes/no), Read N files from triage queue
```
