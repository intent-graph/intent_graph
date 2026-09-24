# AGENT TASK PAYLOAD: DISTILL.PICK

## 1. INPUT
<!-- Lines 5-5 -->

### 1.1 Context
<!-- Lines 8-25 -->

**Inline (critical for orientation):**

- **Step:** DISTILL.PICK
- **Workflow:** distill
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
<!-- Lines 28-36 -->

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_graph.json` | Current product IntentGraph | Yes |
| `input_projection_ig.yaml` | Current ProjectionIG | Yes |
| `input_workflow_state.json` | Workflow state (target queue, processed targets, workflow type) | Yes |

### 1.3 Environment
<!-- Lines 39-45 -->

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS
<!-- Lines 48-48 -->

### 2.1 Primary Objective
<!-- Lines 51-53 -->

> Recommend the next target node for the distill workflow based on graph topology, data-flow order, and epistemic urgency.

### 2.2 Initialization
<!-- Lines 56-63 -->

Read and follow:

- `.claude/agents/ig-steward-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

### 2.3 Algorithm / Execution Path
<!-- Lines 66-66 -->

#### Analysis
<!-- Lines 69-77 -->

Evaluate candidates using these criteria (in priority order):

1. **Tree-level breadth (primary):** Complete all nodes at the shallowest unfinished depth before descending to children. This maximizes graph coverage if the workflow is cut short. Example: if queue has L1 nodes (P, V, R, B) and L2 nodes (D.1, D.2), process all L1 nodes first.
2. **Data-flow order (within same level):** Among same-depth candidates, prefer nodes whose upstream dependencies are already processed
3. **Dependency density (tiebreaker):** Prefer nodes with many dependents (high impact)
4. **Intentlink readiness (tiebreaker):** Prefer nodes whose linked neighbors have stable intent
5. **Epistemic urgency (tiebreaker):** Prefer nodes with `epistemic_state: "unknown"` or `"risky"`

#### Bootstrap Cases
<!-- Lines 80-83 -->

- **Queue empty + graph empty:** Recommend ROOT as first target
- **Queue empty + graph exists:** Recommend pause — all targets processed

#### Human Confirmation
<!-- Lines 86-88 -->

Your recommendation will be presented to the human for confirmation or override. Provide clear rationale so the human can make an informed decision.

### 2.4 Constraints, Exits & Escalations
<!-- Lines 91-108 -->

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2
- Do not modify input files. Write recommendation to output file.

**Exit Conditions:**

- If `input_graph.json` is missing → FAILURE
- If `input_workflow_state.json` is missing → FAILURE

**Escalation Rules:**

- If two candidates are equally viable (true 50/50 split), yield to HUMAN with both options
- Default Escalation Target: HUMAN

---

## 3. OUTPUT CONTRACT
<!-- Lines 111-111 -->

### 3.1 Artifacts
<!-- Lines 114-124 -->

Write to {{step_folder}}:

- `output_pick_recommendation.yaml` — Target recommendation:
  - `recommended`: UID of recommended target
  - `rationale`: Why this target, using the criteria above
  - `queue_snapshot`: Current state of the target queue
  - `alternatives`: Other viable targets with brief rationale
  - `bootstrap`: Whether this is a bootstrap scenario (empty graph)
  - `pause`: Whether the workflow should pause (no more targets)

### 3.2 Epistemology
<!-- Lines 127-130 -->

- Confidence Score: 0.0–1.0 (how clear the best candidate is)
- Unknowns / Assumptions: list any topology ambiguities or missing dependency info

### 3.3 Control Flow & Telemetry
<!-- Lines 133-137 -->

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of recommendation
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)
<!-- Lines 140-145 -->

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
