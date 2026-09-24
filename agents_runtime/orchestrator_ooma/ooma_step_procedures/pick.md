# OOMA Procedure: DISTILL.PICK

**Role:** OOMA self-executes this step (no agent delegation).

**Goal:** Select the next target intentnode to refine.

---

## Input

- `workflow_state.json` — contains `target_queue` (ordered list of pending UIDs)
- `graph.json` — full IntentGraph for topology queries

---

## Output

- `output_target_recommendation.yaml` — recommended UID + rationale
- Human confirmation of target (inline dialogue)

---

## Algorithm

### 1. Check bootstrap case

```bash
ig-tool query --graph graph.json --overview -o {step_folder}/graph_overview.yaml
```

If graph has zero nodes:
- Target = ROOT (deterministic)
- Record in trace: `actor: "ooma"`, `action: "bootstrap pick"`, `result: "target=ROOT (graph empty)"`
- Skip to step 5 (no human confirmation needed)

### 2. Load target queue

Read `workflow_state.json` → `target_queue` field.

If queue is empty:
- Workflow complete
- Record in trace: `result: "workflow complete — queue empty"`
- Report to human, exit

### 3. Analyze queue head

Take first UID from queue. Query its context:

```bash
ig-tool query --graph graph.json --node {UID} -o {step_folder}/target_candidate.yaml
ig-tool query --graph graph.json --neighbors {UID} -o {step_folder}/target_neighbors.yaml
```

**Analyze:**
- Depth (count dots in UID): ROOT=0, D=1, D.1=2, D.1.3=3
- Sibling count (how many children does parent have?)
- Epistemic state (`undecided` → prioritize, `known` → lower priority)
- **Issue annotations** (presence of `|` in epistemic_state → **highest priority**)
- Brim complexity (how many intentlink neighbors?)

### 4. Recommend target

**Heuristic (breadth-first, prioritize uncertainty and issues):**
1. **Prefer nodes with `|` in epistemic_state** (discovered issues need resolution) — **highest priority**
2. Prefer `undecided` or `constrained` over `known`
3. Prefer L1–L3 over L4+ (avoid deep dives early)
4. Prefer nodes with few siblings (complete a decomposition before jumping)
5. Prefer nodes with high brim complexity (architectural crossroads)

Write recommendation:

```yaml
recommended: {UID}
rationale: |
  {1-3 sentence explanation of why this target makes sense}
queue_snapshot:
  - {UID1}: depth=2, epistemic_state=undecided, siblings=3
  - {UID2}: depth=3, epistemic_state=known, siblings=1
  ...
alternatives:
  - uid: {UID2}
    reason: "Also viable, but {UID} is prioritized because..."
```

Save to `{step_folder}/output_target_recommendation.yaml`.

### 5. Present to human (unless bootstrap)

If not bootstrap case:
- Display recommendation + rationale + queue snapshot
- Ask: "Proceed with {UID}, or override?"
- Human confirms or specifies alternative UID

Record human decision in trace:
- If confirmed: `actor: "human"`, `action: "confirmed target"`, `result: "target={UID}"`
- If overridden: `actor: "human"`, `action: "override target"`, `result: "target={overridden_UID}"`

### 6. Update workflow state

Set `workflow_state.json` → `current_target` = confirmed UID.

(Do NOT remove UID from queue yet — that happens in COMMIT after successful completion.)

---

## Edge Cases

| Case | Response |
| ---- | -------- |
| Queue empty | Workflow complete, report to human, exit |
| Graph empty (bootstrap) | Target = ROOT, skip confirmation |
| Human overrides with invalid UID | Reject, ask again |
| All queue nodes are `known` | Acceptable — still refine them (may discover new unknowns) |

---

## Trace Entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.PICK \
  --target {confirmed_UID} \
  --actor "ooma" \
  --action "Selected target via breadth-first heuristic" \
  --result "target={confirmed_UID}, depth={N}, epistemic_state={state}"
```

---

## Next Step

Advance to `DISTILL.SCOPE`.
