# OOMA Procedure: DISTILL.SCOPE

**Role:** OOMA self-executes this step (no agent delegation).

**Goal:** Build a Lens view of the IntentGraph with IV_-shaped detail (target + neighbors full, ancestors lean, L1 brim lean, rest skeleton).

---

## Input

- `workflow_state.json` → `current_target` (confirmed by PICK)
- `graph.json` — full IntentGraph

---

## Output

- `lens.yaml` — standalone Lens file (IV_ detail, budget-constrained)
- `input_lens.yaml` — agent text view (for downstream agents: READ, EXTRACT)

---

## Algorithm

### 1. Determine budget

Default: 30 words (measured in Lens text output).

**Adjust based on target depth:**
- L0–L2: 30 words (broad context)
- L3–L4: 40 words (deeper focus)
- L5+: 50 words (very deep focus)

### 2. Build Lens

```bash
ig-tool lens build \
  --source graph.json \
  --target {target_uid} \
  --budget {budget} \
  --output {step_folder}/lens.yaml
```

**IV_ detail assignment (automatic in `ig-tool lens build`):**
- **Full LOD:** Target node + direct children + intentlink neighbors (brim)
- **Lean LOD:** Ancestors (path to ROOT) + L1 sibling nodes (horizontal context)
- **Skeleton LOD:** Everything else (uid + name only)

**Pruning:** If full tree exceeds budget, `ig-tool` prunes distant branches (furthest from target first) and marks them with `[+N children pruned]`.

### 3. Verify Lens quality

Check stdout summary from `ig-tool lens build`:
- Node count (should be manageable: 10–50 nodes typical)
- Words (should be ≤ budget)
- Pruned branches (if any)

If Lens is too large (>60% pruned):
- Reduce budget by 25%
- Rebuild

If Lens is too small (target has no context):
- Increase budget by 50%
- Rebuild

### 4. Render Lens to agent text

```bash
ig-tool lens show \
  --lens {step_folder}/lens.yaml \
  --output {step_folder}/input_lens.yaml
```

This produces YAML with LOD-aware rendering:
- `skeleton` nodes: only `uid` + `name`
- `lean` nodes: `uid` + `name` + `intent` + `epistemic_state`
- `full` nodes: all fields (`uid`, `name`, `intent`, `epistemic_state`, `constraints`, `design_notes`, `history`, `impl_pointers`)

Intentlinks:
- Visible if both endpoints ≥ `lean` LOD
- Full description if ≥1 endpoint is `full` LOD

### 5. Summarize for trace

Read Lens metadata (from `ig-tool lens build` stdout or `ig-tool lens info`):
- Target: {UID}
- Budget: {N} words
- Nodes: {M} total ({full_count} full, {lean_count} lean, {skeleton_count} skeleton)
- Pruned: {P} branches

---

## Edge Cases

| Case | Response |
| ---- | -------- |
| Target is ROOT and graph has 0–2 nodes | Lens will be tiny. Acceptable — READ/EXTRACT will expand it. |
| Target is L5+ deep with 100+ descendants | Lens will prune aggressively. Acceptable — agents can use `ig-tool query` to inspect pruned branches if needed. |
| Lens exceeds budget despite pruning | Reduce budget further. Minimum: 15 words. |
| Lens fails (invalid target UID) | Error. Log in trace, pause workflow, report to human. |

---

## Trace Entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.SCOPE \
  --target {target_uid} \
  --actor "ooma" \
  --action "Built Lens with IV_ detail, budget={budget}" \
  --result "nodes={M}, full={F}, lean={L}, skeleton={S}, pruned={P}"
```

---

## Next Step

Advance to `DISTILL.READ`.

The `input_lens.yaml` file is now available for READ and EXTRACT agents to read and mutate.
