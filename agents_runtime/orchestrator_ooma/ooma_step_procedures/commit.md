# OOMA Procedure: DISTILL.COMMIT

**Role:** OOMA self-executes this step (no agent delegation).

**Goal:** Validate, audit, and persist the refined IntentGraph + ProjectionIG. Update workflow state. Prepare for next target.

---

## Input

- `lens.yaml` — Lens view (with all REFINE/RECHECK edits applied)
- `graph.json` — full IntentGraph (already reflects all edits)
- `projection_ig.yaml` — full ProjectionIG
- `workflow_state.json` — current workflow state

---

## Output

- `output_graph.json` — validated product IntentGraph
- `output_projection_ig.yaml` — validated ProjectionIG
- `output_workflow_state.json` — updated workflow state (queue reordered, target removed)
- `output_commit_report.yaml` — audit summary

---

## Algorithm

### Phase 1: Verify Lens is Clean

#### 1a. Check for uncommitted edits

```bash
ig-tool lens diff --lens {step_folder}/lens.yaml --graph graph.json -o {step_folder}/lens_diff.yaml
```

**Expected result:** Empty diff (all edits already applied by REFINE/RECHECK via `ig-tool` commands).

**If diff is non-empty:** Something wrong — REFINE/RECHECK should have applied edits already. Log as error, report to human, pause workflow.

### Phase 2: Structural Audit

#### 2a. Validate graph invariants

```bash
ig-tool validate --graph graph.json -o {step_folder}/validation_report.yaml
```

Check for:
- **UID uniqueness:** No duplicate UIDs
- **Tree structure:** No cycles, all nodes reachable from ROOT
- **Parent-child consistency:** Every `treearc` references valid UIDs
- **Intentlink validity:** All `src`/`dst` UIDs exist in graph
- **Field completeness:** All required fields present (uid, name, intent, epistemic_state)

**If validation fails:** Error. Log in trace, report violations to human, pause workflow. Do not persist invalid graph.

#### 2b. Check ProjectionIG alignment (smell test)

For each `full` LOD node in product graph, check if corresponding PIG node exists:

```bash
ig-tool query --graph projection_ig.yaml --node PIG-{product_uid} -o {step_folder}/pig_node.yaml
```

**Not a hard requirement** (PIG can be sparse), but log gaps for awareness:
```yaml
pig_gaps:
  - product_node: ROOT.CACHE
    pig_node: PIG-CACHE.IMPL
    status: "present"
  - product_node: ROOT.EXPORT
    pig_node: PIG-EXPORT
    status: "missing — no rendering observations yet"
```

### Phase 3: Cross-Level Constraint Inheritance

#### 3a. Propagate ancestor constraints

For the target node and its children, check if ancestors have `constraints` that should apply:

Example:
```yaml
# Ancestor (ROOT.PARSE)
constraints:
  - "UTF-8 encoding"
  - "Max 1GB file size"

# Child (ROOT.PARSE.LEX)
constraints:
  - "Token length < 1KB"
# Missing: UTF-8 encoding (inherited from parent)
```

**Auto-propagate** if:
- Ancestor constraint is universal (e.g., "UTF-8 encoding", "thread-safe")
- Child doesn't explicitly override it

**Apply:**
```bash
ig-tool node set ROOT.PARSE.LEX \
  --constraints "Token length < 1KB" \
  --constraints "UTF-8 encoding (inherited)" \
  --constraints "Max 1GB file size (inherited)"
```

**Do NOT propagate** if:
- Child explicitly contradicts (e.g., parent says "read-only", child says "mutable cache")
- Constraint is node-specific (e.g., "lexer must emit tokens in order" for LEXER only)

### Phase 4: Update Target Queue

#### 4a. Remove completed target

Load `workflow_state.json` → `target_queue`.

Remove `current_target` from queue (it's now complete).

#### 4b. Add new targets discovered during REFINE/RECHECK

If REFINE or RECHECK created new child nodes under the current target, add them to the queue:

```bash
ig-tool query --graph graph.json --children {current_target} -o {step_folder}/new_children.yaml
```

For each new child:
- If `epistemic_state` is `undecided` or `constrained` → add to queue (high priority)
- If `epistemic_state` is `known` → add to queue (low priority)

#### 4c. Reorder queue

**Priority heuristic:**
1. `undecided` nodes (highest)
2. `constrained` nodes
3. `known` nodes (lowest)
4. Within same epistemic state: breadth-first (L1 before L2, L2 before L3)

Write updated queue back to `workflow_state.json`.

### Phase 5: Persist

#### 5a. Write outputs to step folder

```bash
cp graph.json {step_folder}/output_graph.json
cp projection_ig.yaml {step_folder}/output_projection_ig.yaml
```

Update workflow state:
```yaml
current_target: null  # cleared after COMMIT
current_step: "DISTILL.PICK"  # next step
target_queue:
  - AUTH.2
  - AUTH.3
  - PARSE.1
  ...
```

Write:
```bash
# Manually write updated workflow_state.json via Write tool
# (ig-tool doesn't manipulate workflow_state.json — orchestrator does)
```

#### 5b. Copy outputs back to workflow root

```bash
cp {step_folder}/output_graph.json {workflow_root}/graph.json
cp {step_folder}/output_projection_ig.yaml {workflow_root}/projection_ig.yaml
cp {step_folder}/output_workflow_state.json {workflow_root}/workflow_state.json
```

#### 5c. Write commit report

Create `{step_folder}/output_commit_report.yaml`:
```yaml
target_completed: {target_uid}
validation_status: "passed"
constraints_inherited: 3
queue_updates:
  removed: 1  # completed target
  added: 2    # new children discovered
  reordered: true
persistence:
  graph: "written to {workflow_root}/graph.json"
  projection_ig: "written to {workflow_root}/projection_ig.yaml"
  workflow_state: "written to {workflow_root}/workflow_state.json"
```

### Phase 6: Obsidian Visualization (OOMA responsibility)

Export both graphs to Obsidian vaults:

#### 6a. Export product IntentGraph

```bash
ig-tool obsidian export \
  --graph {workflow_root}/graph.json \
  --output {vault_dir}/ \
  --force
```

Output:
- `{vault_dir}/nodes/*.md` — one markdown file per intentnode
- `{vault_dir}/edges.yaml` — all intentlinks
- `{vault_dir}/viz/*.canvas` — Obsidian Canvas files (one per node with children)

#### 6b. Export ProjectionIG

```bash
# obsidian export accepts both YAML and JSON (no conversion needed).
ig-tool obsidian export \
  --graph {workflow_root}/projection_ig.yaml \
  --output {pig_vault_dir}/ \
  --force
```

#### 6c. Log export

Record in trace: `actor: "ooma"`, `action: "Obsidian export"`, `result: "{N} nodes, {M} canvases exported"`.

**If export fails:** Log error but do not block workflow. Graph JSON is source of truth, Obsidian is convenience.

---

## Edge Cases

| Case | Response |
| ---- | -------- |
| Validation fails | Error. Do not persist. Report to human, pause workflow. |
| Lens diff is non-empty | Error. REFINE/RECHECK should have applied all edits. Log, report to human, pause workflow. |
| Queue becomes empty after removing current target | Workflow complete. Log in trace, report to human, exit. |
| New children all have `epistemic_state: known` | Acceptable. Add to queue (low priority). User may want to refine even known nodes. |
| Obsidian export fails | Log warning, continue. Graph JSON is source of truth. |

---

## Trace Entry

```bash
ig-tool workflow trace record trace.jsonl \
  --step DISTILL.COMMIT \
  --target {target_uid} \
  --actor "ooma" \
  --action "Validated, persisted graph + PIG, exported to Obsidian" \
  --result "queue_size={N}, next_target={next_uid or 'none'}"
```

---

## Next Step

**If queue is non-empty:** Advance to `DISTILL.PICK` (next target).

**If queue is empty:** Workflow complete. Report summary to human:
```text
DISTILL workflow complete.
Total targets processed: {N}
Final graph: {M} nodes, {P} intentlinks
ProjectionIG: {Q} observations
Trace: {workflow_root}/trace.jsonl
```

Exit.
