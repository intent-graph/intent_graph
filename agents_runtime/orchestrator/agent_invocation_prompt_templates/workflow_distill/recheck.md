# AGENT TASK PAYLOAD: DISTILL.RECHECK

## 1. INPUT
<!-- Lines 5-5 -->

### 1.1 Context
<!-- Lines 8-25 -->

**Inline (critical for orientation):**

- **Step:** DISTILL.RECHECK
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read in this order before accessing Working Material):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | **First** — vocabulary, invariants, agent text format, dual-graph model |
| Lens Primer | `agents_runtime/LENS_PRIMER.md` | **Second** — understand lens views and detail levels before reading lens files |
| Tool Guide | `agents/PRIMER_TOOLS.md` (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) | When you need to invoke a hard tool (query, validate) |
| Vocabulary & Formalism | `foundation_and_formalism/VOCABULARY_AND_FORMALISM.md` | Always — reviews against invariants |
| Serialization Format | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | When lens YAML appears malformed |

### 1.2 Working Material
<!-- Lines 28-36 -->

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_lens.yaml` | Updated lens (after COMMIT applied edits, full tree with variable LOD) | Yes |
| `input_projection_ig.yaml` | Updated ProjectionIG (after COMMIT applied edits) | Yes |
| `input_steward_report.yaml` | Steward's COMMIT report (audit findings, applied changes) | Yes |

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

> Perform the final quality gate review on both graphs after the Steward has applied edits. Be stricter than CHALLENGE — this is the last gate before the target is marked done.

### 2.2 Initialization
<!-- Lines 56-63 -->

Read and follow:

- `.claude/agents/ig-critic-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

### 2.3 Algorithm / Execution Path
<!-- Lines 66-68 -->

Review the committed state of **both graphs** — the product lens and the ProjectionIG — after the Steward has applied edits.

#### Step 1: Product Lens Review
<!-- Lines 71-78 -->

Same checklist as CHALLENGE, applied to the committed state:

- **Vagueness**, **missing constraints**, **HOW-not-WHY**, **structural issues**
- **Distill-specific:** Internal consistency check, language-swap test for projection leaks
- **Under-decomposition:** Does the target have children? If not, do the constraints/impl_pointers/design_notes describe multiple distinct sub-capabilities? Signals: 8+ constraints, multiple `impl_pointers` spanning different classes/functions, design_notes describing distinct phases, or a single intent sentence joined by "and"/"with"/"also." Flag as `under_decomposition` (severity: `major`). In your suggestion, **propose concrete children** by grouping the node's constraints and impl_pointers into coherent sub-capabilities, and recommend which constraints/design_notes should transfer to each child. The parent node should retain only the orchestration-level intent that ties the children together.
- **Steward audit findings:** Check the Steward's `phase_audit` report — were any issues flagged? Are they acceptable or do they need resolution?

#### Step 2: ProjectionIG Review
<!-- Lines 81-88 -->

Review the committed PIG state:

- **Quality:** Are PIG nodes well-formed with cited examples?
- **Granularity:** Module-level patterns, not function-level details?
- **Completeness:** Any obvious patterns missing?
- **Alignment:** Do PIG nodes reference valid product nodes?

#### Step 3: Outcome
<!-- Lines 91-94 -->

- **Clean:** No issues found → target is done, workflow advances to PICK (next target) or terminates
- **Issues found:** → workflow re-enters REFINE for another pass on the same target

### 2.4 Constraints, Exits & Escalations
<!-- Lines 97-115 -->

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2
- Do not modify input files. Write issues to output file.
- Do not re-review issues that were already resolved in REFINE — focus on the committed state
- Be stricter than CHALLENGE: this is the final gate before the target is marked done

**Exit Conditions:**

- If `input_lens.yaml` and `input_projection_ig.yaml` are both missing → FAILURE

**Escalation Rules:**

- If lens format is unparseable, yield to ORCHESTRATOR
- Default Escalation Target: ORCHESTRATOR

---

## 3. OUTPUT CONTRACT
<!-- Lines 118-118 -->

### 3.1 Artifacts
<!-- Lines 121-128 -->

Write to {{step_folder}}:

- `output_issues.yaml` — Structured issue list (Critic output format):
  - Each issue: `type`, `node` (UID), `severity`, `description`, `suggestion`
  - Include both product lens issues and PIG issues
  - If no issues found, write an empty list with `summary: "clean"`

### 3.2 Epistemology
<!-- Lines 131-134 -->

- Confidence Score: 0.0–1.0 (how thoroughly the review covered the committed state)
- Unknowns / Assumptions: list any areas you couldn't assess

### 3.3 Control Flow & Telemetry
<!-- Lines 137-141 -->

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of findings
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)
<!-- Lines 144-149 -->

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
