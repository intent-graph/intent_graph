# AGENT TASK PAYLOAD: DISTILL.CHALLENGE

## 1. INPUT

### 1.1 Context

**Inline (critical for orientation):**

- **Step:** DISTILL.CHALLENGE
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read on demand):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `intent_graph/agents_runtime/AGENT_PRIMER.md` | Always (read first) |
| Lens Primer | `intent_graph/agents_runtime/LENS_PRIMER.md` | Always — understand lens views and detail levels |
| Tool reference | `intent_graph/agents/PRIMER_TOOLS.md` | When you need to invoke a hard tool (query, validate) — see also `.claude/skills/ig-tool-*/SKILL.md` |
| Serialization Format | `intent_graph/foundation_and_formalism/SERIALIZATION_FORMAT.md` | Only when lens YAML appears malformed |

### 1.2 Working Material

Read these files from {{step_folder}}:

| File | Role | Required |
|------|------|----------|
| `input_lens.yaml` | Lens with Docreader + Extractor contributions (full tree with variable LOD) | Yes |
| `input_projection_observations.yaml` | ProjectionIG observations from Extractor | Yes |

### 1.3 Environment

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS

### 2.1 Primary Objective

> Review both graphs — the product intent lens and the ProjectionIG observations — for quality issues, structural gaps, and projection leaks.

### 2.2 Initialization

Read and follow:

- `.claude/agents/ig-critic-agent.md` (core agent definition)
{{agent_mode_modules}}

Read first for vocabulary, invariants, agent text format, and the dual-graph model:
  `intent_graph/agents_runtime/AGENT_PRIMER.md`

### 2.3 Algorithm / Execution Path

**Important:** You receive no source code and no raw documentation. Both are already captured in the lens's `design_notes`, `impl_pointers`, and `history`. Review the lens on its own terms.

#### Step 1: Product Lens Review

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

Review the Extractor's proposed PIG nodes for:

- **`pig_quality`:** Are observations well-formed? Do they cite code examples?
- **`pig_granularity`:** Are they at the right level (module-level, not function-level)?
- **`pig_missing`:** Are there obvious rendering patterns in the lens that the Extractor missed?

#### Step 3: Issue Classification

For each issue found, classify:

- **Severity:** `major` (blocks commit), `moderate` (should fix), `minor` (nice to fix)
- **Type:** Standard Critic types + distill-specific: `pig_quality`, `pig_granularity`, `pig_missing`, `projection_leak`

### 2.4 Constraints, Exits & Escalations

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

### 3.1 Artifacts

Write to {{step_folder}}:

- `output_issues.yaml` — Structured issue list (Critic output format):
  - Each issue: `type`, `node` (UID), `severity`, `description`, `suggestion`
  - Include both product lens issues and PIG observation issues
  - If no issues found, write an empty list with `summary: "clean"`

### 3.2 Epistemology

- Confidence Score: 0.0–1.0 (how thoroughly the review covered the lens)
- Unknowns / Assumptions: list any areas you couldn't assess

### 3.3 Control Flow & Telemetry

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of findings
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
