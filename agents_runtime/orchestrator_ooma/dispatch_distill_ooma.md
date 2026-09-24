# Dispatch Table: OOMA DISTILL Workflow

**Workflow:** OOMA DISTILL (hybrid: OOMA self-executes coordination, delegates extraction/analysis)

**OOMA protocol:** [orchestrator_ooma_protocol.md](orchestrator_ooma_protocol.md)

**Standard step I/O protocol:** [../orchestrator/STEP_IO_PROTOCOL.md](../orchestrator/STEP_IO_PROTOCOL.md) (for delegated steps)

---

## Step Sequence

```text
DISTILL.MAP (once)
  ↓
DISTILL.PICK (OOMA) → DISTILL.SCOPE (OOMA) → DISTILL.READ (agent) → DISTILL.EXTRACT (agent)
  ↑                                                                            ↓
  |                                                              DISTILL.REFINE (OOMA)
  |                                                                            ↓
  |                                                         DISTILL.CHALLENGE (agent)
  |                                                                            ↓
  |                                             If issues → DISTILL.RECHECK (OOMA) → loops to REFINE
  +————————————— clean ——— DISTILL.COMMIT (OOMA) —————————————————————————————+
```

**Key differences from standard DISTILL:**
1. No CHALLENGE → REFINE → COMMIT → RECHECK loop. Instead: REFINE → CHALLENGE → (if issues) RECHECK → REFINE → ...
2. PICK, SCOPE, REFINE, RECHECK, COMMIT are OOMA-executed (not delegated)
3. READ, EXTRACT, CHALLENGE remain agent-delegated

---

## Per-Step Dispatch

### `DISTILL.MAP` (bootstrap — once at start)

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — call `codemap_bridge.build_codemap(project_path)` |
| **Context** | Project root path |
| **Action** | Run `codemap overview {project_path}` via Bash to build CodeMap. Observe architecture-level rendering patterns. Propose initial ProjectionIG skeleton (`PIG-` nodes with `epistemic_state: "observed"`). |
| **Output** | CodeMap overview YAML + initial ProjectionIG nodes |
| **Next** | `DISTILL.PICK` |
| **If codemap unavailable** | Skip. Record trace: `result: "skipped — codemap not installed"`. |

---

### `DISTILL.PICK` (OOMA self-executed)

| Field | Value |
| --- | --- |
| **Actor** | OOMA (self) |
| **Execution** | Follow procedure in [ooma_step_procedures/pick.md](ooma_step_procedures/pick.md) |
| **Context** | Target queue from `workflow_state.json`, full graph for topology |
| **Action** | Query queue, analyze graph topology (depth, sibling count, epistemic state), recommend next target. Present recommendation + rationale to human for confirmation. |
| **ig-tool commands** | `ig-tool query --graph graph.json --overview`, `ig-tool query --neighbors {UID}` |
| **Output** | `output_target_recommendation.yaml` — recommended UID + rationale |
| **Next** | `DISTILL.SCOPE` |
| **Bootstrap case** | If graph is empty (first run), target = ROOT (deterministic), skip confirmation. |

---

### `DISTILL.SCOPE` (OOMA self-executed)

| Field | Value |
| --- | --- |
| **Actor** | OOMA (self) |
| **Execution** | Follow procedure in [ooma_step_procedures/scope.md](ooma_step_procedures/scope.md) |
| **Context** | Target UID from confirmed PICK decision |
| **Action** | Build Lens with IV_-shaped detail (target + neighbors full, ancestors lean, L1 brim lean, rest skeleton). Set budget (default 30 words). If too large, reduce budget or prune scope. |
| **ig-tool commands** | `ig-tool lens build -g graph.json -t {target_uid} -b 30 -o {step}/lens.yaml`, `ig-tool lens show -l {step}/lens.yaml -o {step}/input_lens.yaml` |
| **Output** | `lens.yaml` (standalone Lens) + `input_lens.yaml` (agent text view) |
| **Next** | `DISTILL.READ` |

---

### `DISTILL.READ` (agent-delegated)

| Field | Value |
| --- | --- |
| **Actor** | Docreader |
| **Execution** | Standard agent invocation (copy template → simplify → invoke `ig-docreader-agent`) |
| **Template** | [agent_invocation_prompt_templates/workflow_distill/read.md](agent_invocation_prompt_templates/workflow_distill/read.md) |
| **Context** | Lens from SCOPE + manifest from `md-doc-tree-rich` |
| **Action** | Discover docs via manifest, read selected docs, propose intent/constraints from prose. Distinguish intent from implementation notes. |
| **Output** | Agent applies edits via `ig-tool` during execution. Returns `output_summary.yaml` with nodes modified/created. |
| **Next** | `DISTILL.EXTRACT` |

---

### `DISTILL.EXTRACT` (agent-delegated)

| Field | Value |
| --- | --- |
| **Actor** | Extractor |
| **Execution** | Standard agent invocation (copy template → simplify → invoke `ig-extractor-agent`) |
| **Template** | [agent_invocation_prompt_templates/workflow_distill/extract.md](agent_invocation_prompt_templates/workflow_distill/extract.md) |
| **Context** | Lens (updated by READ) + CodeMap context + source code + test files |
| **Action** | Ground/refine Docreader's draft from code. Set `impl_pointers`. Extract constraints from tests. Observe module rendering patterns → propose ProjectionIG child nodes. |
| **Output** | Agent applies edits to product graph via `ig-tool` during execution. Writes `output_projection_observations.yaml` (proposed PIG nodes). Returns `output_summary.yaml`. |
| **Next** | `DISTILL.REFINE` |

---

### `DISTILL.REFINE` (OOMA self-executed)

| Field | Value |
| --- | --- |
| **Actor** | OOMA (self) |
| **Execution** | Follow procedure in [ooma_step_procedures/refine.md](ooma_step_procedures/refine.md) |
| **Context** | Lens (updated by READ/EXTRACT) + ProjectionIG observations from EXTRACT |
| **Action** | Review agent contributions (READ + EXTRACT). Verify: (1) product graph quality (intent clear, constraints precise, epistemic state accurate), (2) ProjectionIG observations (granularity, completeness). Apply fixes directly via `ig-tool`. If major design decisions needed, escalate to human via inline dialogue (not file-based — OOMA retains context naturally). |
| **ig-tool commands** | `ig-tool node set`, `ig-tool node create`, `ig-tool link create`, `ig-tool lens promote/demote`, `ig-tool apply --batch` |
| **Output** | Edits applied directly to graph. Writes `output_refine_summary.yaml` (what was fixed, what was created). |
| **Next** | `DISTILL.CHALLENGE` |
| **Escalation** | If human judgment needed, OOMA presents options inline, waits for response, continues. No separate YIELD step. |

---

### `DISTILL.CHALLENGE` (agent-delegated)

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Execution** | Standard agent invocation (copy template → simplify → invoke `ig-critic-agent`) |
| **Template** | [agent_invocation_prompt_templates/workflow_distill/challenge.md](agent_invocation_prompt_templates/workflow_distill/challenge.md) |
| **Context** | Lens (updated by REFINE) + ProjectionIG observations |
| **Action** | Review both graphs: (1) product lens — standard quality review + internal consistency via `design_notes`/`history` + language-swap test for projection leaks, (2) ProjectionIG observations — quality, granularity, completeness. |
| **Output** | `output_issues.yaml` — structured issue list |
| **Next** | If issues (metrics.issues > 0) → `DISTILL.RECHECK`. If clean → `DISTILL.COMMIT`. |

---

### `DISTILL.RECHECK` (OOMA self-executed)

| Field | Value |
| --- | --- |
| **Actor** | OOMA (self) |
| **Execution** | Follow procedure in [ooma_step_procedures/recheck.md](ooma_step_procedures/recheck.md) |
| **Context** | Lens + ProjectionIG observations + Critic issue list from CHALLENGE |
| **Action** | Triage issues: (1) mechanical fixes → apply via `ig-tool` immediately, (2) substantive issues → present to human for judgment, apply approved edits. Iterative: fix issues, loop back to REFINE for Critic re-review. |
| **ig-tool commands** | `ig-tool node set`, `ig-tool node create`, `ig-tool link create`, `ig-tool apply --batch` |
| **Output** | Edits applied directly to graph. Writes `output_recheck_summary.yaml` (issues resolved, issues deferred). |
| **Next** | Loop back to `DISTILL.REFINE` (same target) for another CHALLENGE pass. |

---

### `DISTILL.COMMIT` (OOMA self-executed)

| Field | Value |
| --- | --- |
| **Actor** | OOMA (self) |
| **Execution** | Follow procedure in [ooma_step_procedures/commit.md](ooma_step_procedures/commit.md) |
| **Context** | Lens (with all refinements applied) + full graph + ProjectionIG + workflow state + target queue |
| **Action** | Five phases: (1) Verify Lens is clean (all edits already applied by prior steps). (2) Structural audit — validate graph invariants, check PIG alignment. (3) Cross-level constraint inheritance (propagate constraints from ancestors). (4) Update target queue (reorder by priority, add new targets discovered during REFINE/RECHECK). (5) Persist: write `graph.json`, `projection_ig.yaml`, `workflow_state.json` back to workflow root. |
| **ig-tool commands** | `ig-tool validate -g graph.json`, `ig-tool query --graph graph.json --structure` |
| **Output** | `output_graph.json`, `output_projection_ig.yaml`, `output_workflow_state.json`, `output_commit_report.yaml` |
| **Post-step** | OOMA copies outputs back to workflow root, then runs Obsidian export for both graphs. |
| **Next** | `DISTILL.PICK` (next target) |

---

## Module Routing Table

For **delegated steps only** (READ, EXTRACT, CHALLENGE). OOMA self-executed steps don't use agent mode modules.

| Step | Agent | Mode Module | Condition |
| ---- | ----- | ----------- | --------- |
| READ | Docreader | *(none)* | Docreader has no mode modules |
| EXTRACT | Extractor | `ig-extractor-mode-codemap.md` | Only if DISTILL.MAP succeeded |
| EXTRACT | Extractor | *(none)* | If DISTILL.MAP was skipped |
| CHALLENGE | Critic | `ig-critic-review-pig.md` | Always in DISTILL (PIG present) |

---

## Parameter Registry

For **delegated steps only**. OOMA self-executed steps read procedure files instead of templates.

### `DISTILL.READ`

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{target_repo_path}}` | path | yes | Workflow config → project root path |
| `{{agent_mode_modules}}` | text | no | Empty string (Docreader has no modules) |
| `{{effort_hint}}` | effort | yes | Effort Dial (sketch/thorough) |

### `DISTILL.EXTRACT`

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | conditional | `ig-extractor-mode-codemap.md` if MAP succeeded, else empty |
| `{{effort_hint}}` | effort | yes | Effort Dial (sketch/thorough) |

### `DISTILL.CHALLENGE`

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | yes | Always `ig-critic-review-pig.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (sketch/thorough) |

---

## Effort Dial Logic

Same as standard orchestrator. OOMA uses this for delegated steps (READ, EXTRACT, CHALLENGE) and as a heuristic for its own work depth.

| Value | Meaning | When to use |
| ----- | ------- | ----------- |
| `sketch` | Quick, breadth-first. Favor coverage over precision. | First pass through L0–L2 targets. |
| `thorough` | Full effort. Precision matters. Investigate edge cases. | L3+ targets. Second+ pass on same target. |

**Decision rule:**
```python
if depth(target_uid) >= 3 or pass_number > 1:
    effort_hint = "thorough"
else:
    effort_hint = "sketch"
```

OOMA applies this when delegating (pass as `{{effort_hint}}`). For self-executed steps, OOMA uses it as guidance but has discretion to adjust based on observed complexity.

---

## Comparison: OOMA vs. Standard

| Aspect | Standard Orchestrator | OOMA Orchestrator |
| ------ | --------------------- | ----------------- |
| **PICK** | Delegates to Steward agent (Mode 3) | OOMA self-executes |
| **SCOPE** | System (CLI only) | OOMA self-executes |
| **READ** | Delegates to Docreader | Delegates to Docreader (same) |
| **EXTRACT** | Delegates to Extractor | Delegates to Extractor (same) |
| **CHALLENGE** | Delegates to Critic | Delegates to Critic (same) |
| **REFINE** | Delegates to Elicitor (file dialogue, resumable session) | OOMA self-executes (inline dialogue) |
| **RECHECK** | Delegates to Critic (second pass) | OOMA self-executes |
| **COMMIT** | Delegates to Steward (Mode 1) | OOMA self-executes |
| **Loop structure** | CHALLENGE → REFINE → COMMIT → RECHECK → (loop or exit) | REFINE → CHALLENGE → RECHECK → REFINE → ... → COMMIT |
| **Session resumption** | Elicitor agent resumed across REFINE/RECHECK loops | Not needed (OOMA retains context naturally) |
| **File dialogue** | Elicitor creates `human_dialogue/` files | OOMA uses inline dialogue (no files) |
| **Context window pressure** | High (agent prompts 150-200 lines each) | Lower (OOMA reads compact procedures, no agent prompt composition) |

---

## Next Steps After Creating This Dispatch Table

1. Create procedure files in `ooma_step_procedures/`:
   - [x] `pick.md` — target selection logic
   - [x] `scope.md` — Lens construction
   - [x] `refine.md` — initial refinement of agent outputs
   - [x] `recheck.md` — address Critic issues
   - [x] `commit.md` — validate, audit, persist

2. Copy agent prompt templates for delegated steps:
   - [x] `agent_invocation_prompt_templates/workflow_distill/read.md`
   - [x] `agent_invocation_prompt_templates/workflow_distill/extract.md`
   - [x] `agent_invocation_prompt_templates/workflow_distill/challenge.md`

3. Test on a real DISTILL workflow run

4. Compare outcomes vs. standard orchestrator (quality, speed, debuggability)
