# OOMA Procedure: DISTILL.RECHECK

**Role:** OOMA self-executes this step (no agent delegation).

**Goal:** Address issues found by the Critic (from CHALLENGE step). Triage: auto-fix mechanical issues, escalate substantive issues to human. Loop back to REFINE for Critic re-review.

---

## Input

- `lens.yaml` — Lens view (updated by REFINE)
- `input_issues.yaml` — Critic issue list from CHALLENGE
- `graph.json` — full IntentGraph

---

## Output

- Edits applied directly to graph via `ig-tool` commands
- `output_recheck_summary.yaml` — issues resolved, issues deferred

---

## Algorithm

### Phase 1: Load and Triage Issues

#### 1a. Load issue list

Read `input_issues.yaml` (from CHALLENGE step).

Format:
```yaml
issues:
  - uid: issue_001
    type: intent_vague
    node: ROOT.PARSE
    severity: moderate
    description: "Intent says 'parse input' but doesn't specify what aspect."
    suggestion: "Add detail: 'parse CSV input into row dictionaries'."

  - uid: issue_002
    type: projection_leak
    node: ROOT.CACHE
    severity: major
    description: "Constraint mentions 'Redis TTL' which is projection-specific."
    suggestion: "Abstract to 'cache expiry policy', move Redis detail to PIG-CACHE."

  - uid: issue_003
    type: under_decomposition
    node: ROOT.VALIDATE
    severity: moderate
    description: "Node spans input validation + business logic validation."
    suggestion: "Decompose into ROOT.VALIDATE.INPUT and ROOT.VALIDATE.BUSINESS."
```

#### 1b. Triage

Classify each issue:

**Auto-resolve (mechanical fixes):**
- `intent_vague` with clear suggestion → rewrite intent
- `missing_constraint` with clear suggestion → add constraint
- `typo` or `formatting` → fix directly
- `projection_leak` with clear abstraction path → apply abstraction + relocate to PIG

**Escalate (human judgment needed):**
- `under_decomposition` → requires design decision
- `over_decomposition` → requires design decision
- `intent_conflict` → requires disambiguation
- `scope_exceeded` → requires scope adjustment
- Any issue with `severity: major` and ambiguous suggestion

### Phase 2: Auto-Resolve Mechanical Issues

For each auto-resolvable issue:

#### 2a. Apply fix

Use `ig-tool` commands:

```bash
# Fix vague intent
ig-tool node set ROOT.PARSE --intent "Parse CSV input into row dictionaries"

# Add missing constraint
ig-tool node set ROOT.LEXER --constraints "UTF-8 encoding" --constraints "Max 1GB file"

# Fix projection leak
ig-tool node set ROOT.CACHE --constraints "Cache expiry < 1 hour"  # abstract
ig-tool node create --parent PIG-CACHE \
  --name "Cache TTL Implementation" \
  --intent "Rendering: Redis TTL=3600s" \
  --epistemic-state "observed"
```

#### 2b. Log resolution

Track in `auto_resolved` list:
```yaml
auto_resolved:
  - issue_uid: issue_001
    node: ROOT.PARSE
    action: "Rewrote intent per Critic suggestion"
  - issue_uid: issue_002
    node: ROOT.CACHE
    action: "Abstracted constraint, created PIG-CACHE.TTL for Redis detail"
```

### Phase 3: Escalate Substantive Issues

For each escalated issue:

#### 3a. Present to human (inline dialogue)

**Format:**
```text
Critic Issue: {type} ({severity})
Node: {uid} — {name}
Description: {description}
Suggestion: {suggestion}

Options:
A — {Critic's suggestion}
B — {Alternative approach if any}
C — Defer (mark as known issue, address later)

Recommendation: {OOMA's recommendation with reasoning}
```

Wait for human response.

#### 3b. Apply approved edits

Based on human choice:

**Option A (Critic's suggestion):**
```bash
# Example: decompose under-decomposed node
ig-tool node create --parent ROOT.VALIDATE \
  --name "Input Validation" \
  --intent "Validate input format and schema"

ig-tool node create --parent ROOT.VALIDATE \
  --name "Business Rule Validation" \
  --intent "Validate domain constraints"
```

**Option B (alternative):**
Apply alternative logic per human input.

**Option C (defer):**
Add to `deferred` list, do not apply edits now.

#### 3c. Log escalation outcome

Track in `escalations` list:
```yaml
escalations:
  - issue_uid: issue_003
    node: ROOT.VALIDATE
    human_choice: "A"
    action: "Decomposed into ROOT.VALIDATE.INPUT and ROOT.VALIDATE.BUSINESS"
  - issue_uid: issue_004
    node: ROOT.EXPORT
    human_choice: "C"
    action: "Deferred — marked as known issue"
```

### Phase 4: Summarize and Loop Decision

#### 4a. Write summary

Create `{step_folder}/output_recheck_summary.yaml`:
```yaml
issues_processed: 12
auto_resolved: 8
escalated: 4
deferred: 1

auto_resolved_details:
  - { issue_uid: issue_001, node: ROOT.PARSE, action: "Rewrote intent" }
  - { issue_uid: issue_002, node: ROOT.CACHE, action: "Fixed projection leak" }
  ...

escalations_details:
  - { issue_uid: issue_003, node: ROOT.VALIDATE, human_choice: "A", action: "Decomposed" }
  - { issue_uid: issue_004, node: ROOT.EXPORT, human_choice: "C", action: "Deferred" }

deferred_issues:
  - { issue_uid: issue_004, node: ROOT.EXPORT, reason: "Requires deeper investigation" }

edits_applied:
  nodes_modified: 8
  nodes_created: 2
  links_created: 1
```

#### 4b. Loop decision

**If any edits were applied** (auto-resolved or escalated):
- Loop back to `DISTILL.REFINE` for another CHALLENGE pass
- Trace entry: `result: "resolved {N} issues, looping to REFINE"`

**If no edits applied** (all issues deferred or already clean):
- This should not happen — Critic wouldn't have found issues if graph was clean
- If it does: log as anomaly, advance to COMMIT
- Trace entry: `result: "no edits applied — anomaly, advancing to COMMIT"`

**If all issues deferred by human:**
- Human accepts current state despite Critic issues
- Advance to COMMIT
- Trace entry: `result: "all issues deferred by human, advancing to COMMIT"`

---

## Edge Cases

| Case | Response |
| ---- | -------- |
| Critic found 0 issues | Should not reach RECHECK. Dispatch logic: CHALLENGE clean → COMMIT directly. |
| All issues are auto-resolvable | Fast path: apply all, loop to REFINE. |
| All issues escalated, human defers all | Acceptable — human accepts current state. Advance to COMMIT. |
| Issue list is empty but RECHECK invoked | Log as anomaly, write empty summary, advance to COMMIT. |
| Issue refers to non-existent node | Critic error. Log in trace, skip issue, continue. |

---

## Trace Entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.RECHECK \
  --target {target_uid} \
  --actor "ooma" \
  --action "Resolved {N} issues ({auto} auto, {esc} escalated)" \
  --result "loop_to_refine={true/false}, deferred={M}"
```

---

## Next Step

**If edits applied:** Loop back to `DISTILL.REFINE` (same target).

**If no edits or all deferred:** Should not happen via normal flow, but if it does, advance to `DISTILL.COMMIT`.

**Normal flow:** RECHECK → REFINE → CHALLENGE → (if clean) COMMIT.
