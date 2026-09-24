# AGENT TASK PAYLOAD: DISTILL.CHALLENGE

## 1. INPUT
<!-- Lines 5-5 -->

### 1.1 Context
<!-- Lines 8-24 -->

**Inline (critical for orientation):**

- **Step:** DISTILL.CHALLENGE
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read in this order before accessing Working Material):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | **First** — vocabulary, invariants, agent text format, dual-graph model |
| Lens Primer | `agents_runtime/LENS_PRIMER.md` | **Second** — understand lens views and detail levels before reading lens files |
| Tool Guide | `agents/PRIMER_TOOLS.md` (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) | When you need to invoke a hard tool (query, validate) |
| Serialization Format | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | Only when lens YAML appears malformed |

### 1.2 Working Material
<!-- Lines 27-34 -->

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_lens.yaml` | Lens with Docreader + Extractor contributions (full tree with variable LOD) | Yes |
| `input_projection_observations.yaml` | ProjectionIG observations from Extractor | Yes |

### 1.3 Environment
<!-- Lines 37-43 -->

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS
<!-- Lines 46-46 -->

### 2.1 Primary Objective
<!-- Lines 49-51 -->

> Review both graphs — the product intent lens and the ProjectionIG observations — for quality issues, structural gaps, and projection leaks.

### 2.2 Initialization
<!-- Lines 54-61 -->

Read and follow:

- `.claude/agents/ig-critic-agent.md` (core agent definition)
{{agent_mode_modules}}

Refer to §1.1 External for primer reading order.

### 2.3 Algorithm / Execution Path
<!-- Lines 64-66 -->

**Important:** You receive no source code and no raw documentation. Both are already captured in the lens's `design_notes`, `impl_pointers`, and `history`. Review the lens on its own terms.

#### Step 1: Product Lens Review
<!-- Lines 69-82 -->

Apply the standard Declare review checklist:

- **Vagueness:** Is the intent precise enough to act on? Could two developers interpret it differently?
- **Missing constraints:** Are there obvious invariants or requirements not captured?
- **HOW-not-WHY:** Does the intent describe implementation details instead of purpose?
- **Structural issues:** Fan-out balance, orphaned links, epistemic drift

**Distill-specific checks:**

- **Internal consistency:** Do `design_notes` and `history` corroborate the `intent` field? (e.g., if Docreader proposed X but Extractor found Y, is the resolution clear?)
- **Language-swap test for projection leaks:** Would the intent change if the codebase were rewritten in a different language? If yes, it contains projection content that belongs in the ProjectionIG.
- **Under-decomposition:** See Edit Primer §Expansion Protocol (`AGENT_EDIT_PRIMER_V2.md`) for the full signals checklist. Does this target have children? If not, does the intent/constraints/design_notes describe multiple distinct sub-capabilities that should be separate child nodes? Signals: 8+ constraints, multiple `impl_pointers` spanning different classes/functions, design_notes describing distinct phases, or a single intent sentence joined by "and"/"with"/"also." Flag as `under_decomposition` (severity: `major`). In your suggestion, **propose concrete children** by grouping the node's constraints and impl_pointers into coherent sub-capabilities, and recommend which constraints/design_notes should transfer to each child. The parent node should retain only the orchestration-level intent that ties the children together.

#### Step 2: ProjectionIG Observation Review
<!-- Lines 85-91 -->

Review the Extractor's proposed PIG nodes for:

- **`pig_quality`:** Are observations well-formed? Do they cite code examples?
- **`pig_granularity`:** Are they at the right level (module-level, not function-level)?
- **`pig_missing`:** Are there obvious rendering patterns in the lens that the Extractor missed?

#### Step 3: Issue Classification
<!-- Lines 94-99 -->

For each issue found, classify:

- **Severity:** `major` (blocks commit), `moderate` (should fix), `minor` (nice to fix)
- **Type:** Standard Critic types + distill-specific: `pig_quality`, `pig_granularity`, `pig_missing`, `projection_leak`

### 2.4 Constraints, Exits & Escalations
<!-- Lines 102-119 -->

**Constraints:**

- Read ONLY files listed in §1.1 and §1.2
- Do not read source code or documentation — review the lens as-is
- Do not modify input files. Write issues to output file.

**Exit Conditions:**

- If both input files are missing or empty → FAILURE

**Escalation Rules:**

- If lens format is unparseable, yield to ORCHESTRATOR
- Default Escalation Target: ORCHESTRATOR

---

## 3. OUTPUT CONTRACT
<!-- Lines 122-122 -->

### 3.1 Artifacts
<!-- Lines 125-132 -->

Write to {{step_folder}}:

- `output_issues.yaml` — Structured issue list (Critic output format):
  - Each issue: `type`, `node` (UID), `severity`, `description`, `suggestion`
  - Include both product lens issues and PIG observation issues
  - If no issues found, write an empty list with `summary: "clean"`

### 3.2 Epistemology
<!-- Lines 135-138 -->

- Confidence Score: 0.0–1.0 (how thoroughly the review covered the lens)
- Unknowns / Assumptions: list any areas you couldn't assess

### 3.3 Control Flow & Telemetry
<!-- Lines 141-145 -->

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of findings
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)
<!-- Lines 148-153 -->

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
