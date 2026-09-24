# AGENT TASK PAYLOAD: DISTILL.COMMIT

## 1. INPUT
<!-- Lines 5-5 -->

### 1.1 Context
<!-- Lines 8-26 -->

**Inline (critical for orientation):**

- **Step:** DISTILL.COMMIT
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read in this order before accessing Working Material):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | **First** — vocabulary, invariants, agent text format, dual-graph model |
| Lens Primer | `agents_runtime/LENS_PRIMER.md` | **Second** — understand lens views and detail levels before reading lens files |
| Tool Guide | `agents/PRIMER_TOOLS.md` (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) | When you need to invoke a hard tool (query, validate, edit) |
| Vocabulary & Formalism | `foundation_and_formalism/VOCABULARY_AND_FORMALISM.md` | Always — audits invariants and operations |
| Serialization Format | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | Always — applies edits in all formats |
| Workflow Design Guidelines | `agents_runtime/workflow_design_guidelines.md` | For queue intelligence and constraint propagation |

### 1.2 Working Material
<!-- Lines 29-39 -->

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_lens.json` | Lens view of product IntentGraph (current state with variable LOD) | Yes |
| `input_projection_lens.json` | Lens view of ProjectionIG observations | Yes |
| `input_graph.json` | Current product IntentGraph (full graph for validation) | Yes |
| `input_projection_ig.yaml` | Current ProjectionIG (full for validation) | Yes |
| `input_workflow_state.json` | Workflow state (current target, queue) | Yes |

### 1.3 Environment
<!-- Lines 42-48 -->

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS
<!-- Lines 51-51 -->

### 2.1 Primary Objective
<!-- Lines 54-56 -->

> Apply lens-based edits to both graphs (product IntentGraph and ProjectionIG) via `ig-tool lens` commands, run structural audit, propagate constraints, reorder queue, and persist all artifacts.

### 2.2 Initialization
<!-- Lines 59-68 -->

Read and follow:

- `.claude/agents/ig-steward-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

See `ig-steward-mode-commit.md` for detailed phase specifications.

### 2.3 Algorithm / Execution Path
<!-- Lines 71-71 -->

#### Phase 1: Apply Edits via Lens
<!-- Lines 74-91 -->

Extract all changes requested by REFINE/EXTRACT and apply them atomically via `ig-tool lens apply`:

```bash
# Apply all accumulated edits from REFINE/EXTRACT
ig-tool lens apply -g input_graph.json -p input_projection_ig.json -o output_lens_diff.json

# This returns a lens diff showing:
# - Changes made to the product graph
# - Changes made to the ProjectionIG
# - Any validation errors or invariant violations
```

**Change Tracking:**
- Collect all `ig-tool node create`, `ig-tool node set`, `ig-tool link create`, and `ig-tool apply --batch` commands issued by REFINE/EXTRACT
- The orchestrator accumulates these into a batch for atomic application
- Lens apply validates and applies all changes in one transaction, enforcing invariants

#### Phase 2: Structural Audit
<!-- Lines 94-109 -->

After applying edits, validate the committed state:

```bash
# Validate product graph structure
ig-tool validate -g output_graph.json --mode steward

# Validate ProjectionIG alignment
ig-tool validate -g output_projection_ig.yaml --mode pig_alignment
```

**Audit Checks:**
- **Product graph:** Fan-out balance, constraint density, depth balance, orphaned links, epistemic drift
- **PIG alignment smell test:** Do PIG nodes reference valid product nodes? Are rendering patterns consistent with the product structure?
- Report issues but do not block the commit

#### Phase 3: Cross-Level Constraint Inheritance
<!-- Lines 112-116 -->

- Propagate constraints from parent nodes to affected child nodes
- Annotate inherited constraints in `design_notes` (not in `constraints` — those are self-owned)
- Check for constraint conflicts between inherited and self-owned constraints

#### Phase 4: Queue Intelligence
<!-- Lines 119-123 -->

- Reorder the target queue based on updated graph topology
- Consider: data-flow order, dependency density, constraint inheritance freshness
- Add any new targets from REFINE's `output_queue_additions.yaml` (if present in step folder)

#### Phase 5: Persist
<!-- Lines 126-130 -->

- Save updated product IntentGraph
- Save updated ProjectionIG
- Save updated workflow state (new queue order, advance current step)

### 2.4 Constraints, Exits & Escalations
<!-- Lines 133-152 -->

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2
- Do not modify input files. Write all outputs to separate output files.
- If structural audit fails, report issues in steward report but do not block persist

**Exit Conditions:**

- If `input_lens.yaml` or `input_graph.json` is missing → FAILURE
- If `ig-tool lens apply` fails with validation errors → FAILURE (report errors in output)

**Escalation Rules:**

- If constraint inheritance creates a conflict between parent and child, yield to HUMAN with options
- If queue reordering would skip a dependency, yield to ORCHESTRATOR
- Default Escalation Target: ORCHESTRATOR

---

## 3. OUTPUT CONTRACT
<!-- Lines 155-155 -->

### 3.1 Artifacts
<!-- Lines 158-170 -->

Write to {{step_folder}}:

- `output_steward_report.yaml` — Phase reports: `phase_apply`, `phase_audit`, `phase_inherit`, `phase_queue`, `phase_persist`
  - `phase_apply`: lens apply result (number of nodes/links created/updated, validation status)
  - `phase_audit`: structural audit findings (any balance/link/epistemic issues flagged)
  - `phase_inherit`: constraint propagation summary (parent→child inheritance records)
  - `phase_queue`: reordered queue with rationale
  - `phase_persist`: persistence confirmation (graphs saved, workflow state updated)
- `output_graph.json` — Updated product IntentGraph (after edits applied)
- `output_projection_ig.yaml` — Updated ProjectionIG (after edits applied)
- `output_workflow_state.json` — Updated workflow state (new queue, current target advanced)

### 3.2 Epistemology
<!-- Lines 173-176 -->

- Confidence Score: 0.0–1.0 (how cleanly all phases completed)
- Unknowns / Assumptions: list any audit issues deferred, constraint conflicts noted but not resolved

### 3.3 Control Flow & Telemetry
<!-- Lines 179-183 -->

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of commit results
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)
<!-- Lines 186-191 -->

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
