# Dispatch Table: Distill Workflow

**Workflow:** Distill (reverse intent extraction from code)

**Full spec:** [WORKFLOW_DISTILL.md](../WORKFLOW_DISTILL.md)

**How to invoke agents:** [STEP_IO_PROTOCOL.md](STEP_IO_PROTOCOL.md) — authoritative spec for the copy-template-and-simplify workflow

**Where templates live:** [agent_invocation_prompt_templates/workflow_distill/](agent_invocation_prompt_templates/workflow_distill/)

**Template simplification note:** Current templates (~150-200 lines) duplicate agent instructions. Future work: simplify to minimal routing metadata (step_folder, target_uid, mode, effort_hint, is_resumption) — agent definitions already contain all "how to do this" instructions. This will reduce context further.

---

## Step Sequence
<!-- Lines 17-34 -->

```text
DISTILL.MAP (once)
  ↓
DISTILL.PICK → DISTILL.SCOPE → DISTILL.READ → DISTILL.EXTRACT
  ↑                                                ↓
  |                              DISTILL.CHALLENGE → DISTILL.REFINE ←─(YIELD)─→ Human
  |                                                      ↓ converges       (file dialogue)
  |                                        DISTILL.COMMIT → DISTILL.RECHECK
  +————————————— clean ——————————————————————————————————————+
```

**REFINE session reuse:** When RECHECK loops back to REFINE for the same target, or when REFINE yields for human input and resumes, the orchestrator reuses the Elicitor agent via `Task(resume=agent_id)`. See [STEP_IO_PROTOCOL.md §6a](STEP_IO_PROTOCOL.md#6a-resume-agent-when-re-entering-a-step-for-the-same-target) and [§6b](STEP_IO_PROTOCOL.md#6b-handle-yield_for_input-with-file-based-dialogue).

Escape hatch: `DISTILL.ESCAPE` between REFINE and COMMIT when scope is exceeded.

---

## Per-Step Dispatch
<!-- Lines 37-37 -->

### `DISTILL.MAP` (bootstrap — once at start)
<!-- Lines 40-50 -->

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — call `codemap_bridge.build_codemap(project_path)` |
| **Context** | Project root path |
| **Action** | Run `codemap overview {project_path}` via Bash to build CodeMap. Observe architecture-level rendering patterns (package layout, module granularity, type balance, import patterns). Propose initial ProjectionIG skeleton (`PIG-` nodes with `epistemic_state: "observed"`). |
| **Output** | CodeMap overview YAML + initial ProjectionIG nodes |
| **Next** | `DISTILL.PICK` |
| **If codemap unavailable** | Skip. Record trace: `result: "skipped — codemap not installed"`. |

### `DISTILL.PICK`
<!-- Lines 53-55 -->

Same as `DECLARE.PICK` — Steward recommends the next target (Mode 3). See [dispatch_declare.md](dispatch_declare.md#declarepick).

### `DISTILL.SCOPE`
<!-- Lines 58-68 -->

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — direct CLI invocation |
| **Context** | Target UID from `workflow_state.json` → `current_target`. |
| **Action** | Run `ig-tool lens build -g graph.json -t {target_uid} -b 30 -o {step_folder}/lens.yaml` then `ig-tool lens show -l {step_folder}/lens.yaml -o {step_folder}/input_lens.yaml`. If text is too large, rebuild with reduced budget (`-b 15`) or narrower scope. Record the lens summary (nodes, words, budget) in the trace. |
| **Output** | `{step_folder}/lens.yaml` — standalone lens file. `{step_folder}/input_lens.yaml` — agent text (full tree view with IV_ LOD filtering) for downstream agents. |
| **Next** | `DISTILL.READ` |
| **If context assembly fails** | Log error, enter `DISTILL.ESCAPE`. |

### `DISTILL.READ`
<!-- Lines 71-81 -->

| Field | Value |
| --- | --- |
| **Actor** | Docreader |
| **Agent** | `.claude/agents/ig-docreader-agent.md` |
| **Context** | Target node + target-adj lens tree. The Docreader does **not** receive pre-selected doc files — it discovers them via manifest (see below). |
| **Action** | (1) Run `md-doc-tree-rich {target_repo_path}` via Bash to get a structured index of markdown files (titles, line counts, section counts). (2) Use the manifest to select docs relevant to the current target. (3) Read selected docs. (4) Propose intent, constraints, epistemic_state from prose. Distinguish intent statements from implementation notes. |
| **Output** | Proposed edits to the lens (intent from docs). |
| **Next** | `DISTILL.EXTRACT` |
| **If manifest is empty** | Skip. Record trace: `result: "no docs found — skipped"`. Proceed to EXTRACT. |

### `DISTILL.EXTRACT`
<!-- Lines 84-93 -->

| Field | Value |
| --- | --- |
| **Actor** | Extractor |
| **Agent** | `.claude/agents/ig-extractor-agent.md` |
| **Context** | Target node (enriched by Docreader) + target-adj lens tree + CodeMap overview + CodeMap IV-context for target area + actual code files + test files. Use `assemble_agent_context(graph, lens, target_uid={UID}, iv_context_mode="lean", codemap_project_path=...)`. |
| **Action** | Ground/refine Docreader's draft from code. Extract constraints from assertions/tests. Populate `impl_pointers` field with pointers to relevant source (grammar: `path[::Symbol[ .member]][ (lines X-Y)]`). **Also observe module-level rendering patterns** → propose ProjectionIG child nodes (`PIG-` prefix, `epistemic_state: "observed"`). |
| **Output** | Two outputs: (1) modified lens YAML, (2) proposed ProjectionIG nodes (rendering observations). |
| **Next** | `DISTILL.CHALLENGE` |

### `DISTILL.CHALLENGE`
<!-- Lines 96-105 -->

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Agent** | `.claude/agents/ig-critic-agent.md` |
| **Context** | Lens YAML (with Docreader + Extractor contributions) + projection observations. No source code, no raw documentation — both are already captured in the lens's `design_notes` and `impl_pointers`. |
| **Action** | Review **both graphs**: (1) product lens — standard Declare review + internal consistency check via `design_notes`/`impl_pointers` + language-swap test for projection leaks, (2) ProjectionIG observations — quality, granularity, completeness (issue types: `pig_quality`, `pig_granularity`, `pig_missing`). |
| **Output** | Structured issue list. |
| **Next** | If issues → `DISTILL.REFINE`. If clean → `DISTILL.RECHECK`. |

### `DISTILL.REFINE`
<!-- Lines 108-118 -->

| Field | Value |
| --- | --- |
| **Actor** | Elicitor ↔ Human ↔ Critic |
| **Agent** | `.claude/agents/ig-elicitor-agent.md` — **you MUST invoke the Elicitor, not present issues to the human yourself** |
| **Context** | Lens YAML + projection observations + Critic issue list (`output_issues.yaml` from CHALLENGE). If re-entering after RECHECK, include updated issue list. Elicitor can invoke `ig-tool lens focus/promote/demote` to adjust viewport, `ig-tool lens prune/expand` to manage scope, `ig-tool node create/set/reparent/remove` to edit graph, `ig-tool link create/set/remove` to edit links. |
| **Session reuse** | If `refine_agent_id` is set and `refine_agent_target` matches `current_target`, resume the existing Elicitor via `Task(resume=refine_agent_id)` with a resumption prompt pointing to the new step folder's inputs. Otherwise, create a fresh Elicitor and store the returned `agent_id` in `workflow_state.json`. See [STEP_IO_PROTOCOL.md §6a](STEP_IO_PROTOCOL.md#6a-resume-agent-when-re-entering-a-step-for-the-same-target). |
| **Action** | Elicitor works on **both graphs**. Triages issues (auto-resolve mechanical fixes, escalate decisions). Product issues → edits to lens YAML. Projection issues (`projection_hints`, `pig_*`) → edits to ProjectionIG. For projection leaks: rewrite product constraint to be projection-agnostic *and* relocate the specific content to ProjectionIG. When human judgment is needed, the Elicitor creates dialogue files in `{step_folder}/human_dialogue/` and returns `YIELD_FOR_INPUT` — the orchestrator relays the folder path to the human (C7: do not read files). See [STEP_IO_PROTOCOL.md §6b](STEP_IO_PROTOCOL.md#6b-handle-yield_for_input-with-file-based-dialogue). |
| **Output** | Two outputs in §2/§5 agent text format: (1) `output_lens_edits.yaml` — product lens edits (applied via `ig-tool node/link create/set/remove` or `ig-tool apply --batch`), (2) `output_projection_edits.yaml` — ProjectionIG edits. May also produce new target UIDs to queue. |
| **Next** | If converges within target-adj → `DISTILL.COMMIT`. If scope exceeded → `DISTILL.ESCAPE`. If `YIELD_FOR_INPUT` → dialogue loop with human, then resume. |

### `DISTILL.ESCAPE`
<!-- Lines 121-123 -->

Same as `DECLARE.ESCAPE`. See [dispatch_declare.md](dispatch_declare.md#declareescape).

### `DISTILL.COMMIT`
<!-- Lines 126-137 -->

| Field | Value |
| --- | --- |
| **Actor** | Steward |
| **Agent** | `.claude/agents/ig-steward-agent.md` |
| **Context** | Product lens edits + PIG edits (both from REFINE/ESCAPE) + current graph.json + projection_ig.yaml + workflow_state.json + target queue. |
| **File setup** | The orchestrator creates the COMMIT step folder and populates it with inputs from REFINE output + workflow root. See concrete commands below. |
| **Action** | Steward runs five phases: (1) Review edits via `ig-tool lens diff` (product graph + ProjectionIG). (2) Apply edits via `ig-tool lens apply` (both graphs). (3) Structural audit — product graph + PIG alignment smell test. (4) Cross-level constraint inheritance. (5) Persist both graphs, workflow state. Mode module: `ig-steward-mode-commit.md`. |
| **Output** | Steward report + persisted artifacts: `output_graph.json`, `output_projection_ig.yaml`, `output_workflow_state.json`, `output_steward_report.yaml` |
| **Post-step** | Orchestrator copies outputs back to workflow root: `output_graph.json` → `graph.json`, `output_projection_ig.yaml` → `projection_ig.yaml`, `output_workflow_state.json` → `workflow_state.json`. Then runs Obsidian export (see `orchestrator_protocol.md` §Obsidian Visualization). |
| **Next** | `DISTILL.RECHECK` |

#### COMMIT file setup (orchestrator commands)
<!-- Lines 140-166 -->

```bash
# 1. Create step folder, copy REFINE outputs as COMMIT inputs (rename on copy)
ig-tool workflow step create --dir {workflow_root}/steps/ \
  --step DISTILL.COMMIT --target {target_uid} \
  --prev {workflow_root}/steps/NNN_DISTILL.REFINE \
  --copy output_lens_edits.yaml:input_lens_edits.yaml \
  --copy output_projection_edits.yaml:input_projection_edits.yaml

# 2. Copy current lens + graphs + workflow state from workflow root
cp {workflow_root}/lens.yaml {step_folder}/input_lens.yaml
cp {workflow_root}/graph.json {step_folder}/input_graph.json
cp {workflow_root}/projection_ig.yaml {step_folder}/input_projection_ig.yaml
cp {workflow_root}/workflow_state.json {step_folder}/input_workflow_state.json

# 3. Copy prompt template
cp agents_runtime/orchestrator/agent_invocation_prompt_templates/workflow_distill/commit.md \
   {step_folder}/_prompt.md

# 4. After Steward completes — copy outputs back to workflow root
cp {step_folder}/output_graph.json {workflow_root}/graph.json
cp {step_folder}/output_projection_ig.yaml {workflow_root}/projection_ig.yaml
cp {step_folder}/output_workflow_state.json {workflow_root}/workflow_state.json
```

**Edge case:** If REFINE produced no PIG edits, it should still write a minimal `output_projection_edits.yaml` (§5 diff with empty `nodes: []`). The Steward's `ig-tool lens apply` handles empty edit lists as a no-op.

### `DISTILL.RECHECK`
<!-- Lines 169-173 -->

Same as `DECLARE.RECHECK`. See [dispatch_declare.md](dispatch_declare.md#declarerecheck).

---

## Module Routing Table
<!-- Lines 176-204 -->

Which mode module to pass via `{{agent_mode_modules}}` for each step. All files live in `.claude/agents/`.

When a module applies, the orchestrator passes:

```text
{{agent_mode_modules}} = "- `.claude/agents/<module-file>` (<description>)"
```

When no module applies, pass empty string.

| Step | Agent | Mode Module | Condition |
| ---- | ----- | ----------- | --------- |
| PICK | Steward | `ig-steward-mode-pick.md` | Always |
| SCOPE | *(System — no agent)* | *(n/a)* | CLI-only step |
| READ | Docreader | *(none)* | Docreader has no mode modules |
| EXTRACT | Extractor | `ig-extractor-mode-codemap.md` | Only if DISTILL.MAP succeeded |
| EXTRACT | Extractor | *(none)* | If DISTILL.MAP was skipped |
| CHALLENGE | Critic | `ig-critic-review-pig.md` | Always in DISTILL (PIG present) |
| REFINE | Elicitor | `ig-elicitor-mode-triage.md` | Always (enters from Critic) |
| COMMIT | Steward | `ig-steward-mode-commit.md` | Always |
| RECHECK | Critic | `ig-critic-review-pig.md` | Always in DISTILL (PIG present) |

**Only one conditional case:** EXTRACT depends on whether DISTILL.MAP succeeded (CodeMap available). All other steps have fixed module assignments.

**Cross-workflow note:** CHALLENGE and RECHECK use `ig-critic-review-pig.md` because PIG is always present in DISTILL. In DECLARE (no PIG), pass empty string instead.

---

## Parameter Registry
<!-- Lines 207-209 -->

The orchestrator reads this registry to know **exactly** which parameters each step template requires — no template reading needed at invocation time. Parameters use `{{double_braces}}` in templates.

### `DISTILL.PICK`
<!-- Lines 212-218 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{agent_mode_modules}}` | text | yes | Module Routing Table → always `ig-steward-mode-pick.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

### `DISTILL.SCOPE`
<!-- Lines 221-230 -->

System step — no agent prompt template. The orchestrator runs CLI commands directly.

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `step_folder` | path | yes | `ig-tool workflow step create` output |
| `target_uid` | uid | yes | `workflow_state.json` → `current_target` |
| `graph_path` | path | yes | Workflow config → graph file path |
| `budget` | int | no | Default 4000 words |

### `DISTILL.READ`
<!-- Lines 233-241 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{target_repo_path}}` | path | yes | Workflow config → project root path |
| `{{agent_mode_modules}}` | text | no | Module Routing Table → none (Docreader has no modules) |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

### `DISTILL.EXTRACT`
<!-- Lines 244-251 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | conditional | Module Routing Table → `ig-extractor-mode-codemap.md` if MAP succeeded, else empty |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

### `DISTILL.CHALLENGE`
<!-- Lines 254-261 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | yes | Module Routing Table → always `ig-critic-review-pig.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

### `DISTILL.REFINE`
<!-- Lines 264-273 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | yes | Module Routing Table → always `ig-elicitor-mode-triage.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |
| `{{is_resumption}}` | boolean | yes | `true` if `refine_agent_id` is set and `refine_agent_target` matches current target |
| `{{refine_dialogue_round}}` | int | yes | `workflow_state.json` → `refine_dialogue_round` (0 on first invocation) |

### `DISTILL.COMMIT`
<!-- Lines 276-283 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | yes | Module Routing Table → always `ig-steward-mode-commit.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

### `DISTILL.RECHECK`
<!-- Lines 286-295 -->

| Parameter | Type | Required | Source |
| --------- | ---- | -------- | ------ |
| `{{step_folder}}` | path | yes | `ig-tool workflow step create` output |
| `{{target_uid}}` | uid | yes | `workflow_state.json` → `current_target` |
| `{{agent_mode_modules}}` | text | yes | Module Routing Table → always `ig-critic-review-pig.md` |
| `{{effort_hint}}` | effort | yes | Effort Dial (see §Effort Dial Logic) |

---

## Effort Dial Logic
<!-- Lines 298-300 -->

The `{{effort_hint}}` parameter controls how deeply agents invest in each step. The orchestrator sets this based on where the workflow is in its lifecycle.

### Values
<!-- Lines 303-308 -->

| Value | Meaning | When to use |
| ----- | ------- | ----------- |
| `sketch` | Quick, breadth-first output. Favor coverage over precision. Output will be refined in later passes. Don't agonize over edge cases or perfect wording. | First pass through L0–L2 targets. Building the initial skeleton. |
| `thorough` | Full effort. Precision matters. Investigate edge cases, validate constraints carefully, produce polished output. | L3+ targets. REFINE/RECHECK loops (second+ pass on same target). Any step re-entered after CHALLENGE found issues. |

### Decision Rule
<!-- Lines 311-323 -->

The orchestrator determines effort from two signals:

1. **Target depth:** `depth(target_uid)` — count dots in UID (ROOT = 0, D = 1, D.1 = 2, D.1.3 = 3)
2. **Pass number:** is this the first time through the PICK→RECHECK cycle for this target, or a re-entry after RECHECK found issues?

```python
if depth(target_uid) >= 3 or pass_number > 1:
    effort_hint = "thorough"
else:
    effort_hint = "sketch"
```

### How agents interpret this
<!-- Lines 326-328 -->

- **`sketch`:** Produce well-structured but concise output. Accept `epistemic_state: "unknown"` instead of investigating further. Propose children broadly rather than precisely. Flag areas for future refinement rather than resolving them now.
- **`thorough`:** Read all available context. Validate against constraints. Resolve ambiguities rather than deferring them. Produce output that should survive RECHECK without major issues.
