# AGENT TASK PAYLOAD: DISTILL.EXTRACT

## 1. INPUT

### 1.1 Context

**Inline (critical for orientation):**

- **Step:** DISTILL.EXTRACT
- **Workflow:** distill
- **Target:** {{target_uid}}
- **Step folder:** {{step_folder}}

**External (read on demand):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `intent_graph/agents_runtime/AGENT_PRIMER.md` | Always (read first) |
| Lens Primer | `intent_graph/agents_runtime/LENS_PRIMER.md` | Always — understand lens views and detail levels |
| Serialization Format | `intent_graph/foundation_and_formalism/SERIALIZATION_FORMAT.md` | When reading/writing lens YAML |
| Vocabulary & Formalism | `intent_graph/foundation_and_formalism/VOCABULARY_AND_FORMALISM.md` | When you need precise definitions or invariants |
| CodeMap Tree Format | `ai_tooling/documentation_tools/codemap/TREE_FORMAT.md` | When reading CodeMap context and interpreting structural overview |
| Edit Primer | `intent_graph/agents_runtime/AGENT_EDIT_PRIMER_V2.md` | When proposing children (Step 3) |

### 1.2 Working Material

You will receive a **lens view** of the IntentGraph:

- **Input Format:** `input_lens.json` — A lens view with variable Level of Detail (LOD) per node
- **Lens Structure:** Full tree hierarchy visible; LOD levels control detail depth
  - `skeleton` — uid + name only
  - `lean` — uid + name + intent + epistemic_state
  - `full` — all fields (constraints, impl_pointers, design_notes, history, etc.)
- **CodeMap Context:** If available:
  - `input_codemap_overview.yaml` — Structural overview of entire project
  - `input_codemap_context.yaml` — IV-context for target area (modules, functions, calls, edges)
- **Source Code:** `input_source_files/` directory with actual code for target area
- **Tests (optional):** `input_test_files/` directory with test files for target area
- **ProjectionIG:** `input_projection_ig.yaml` for extending with new observations

### 1.3 Environment

- `dry_run: false`
- `verbosity: normal`
- Effort Hint: {{effort_hint}}

---

## 2. INSTRUCTIONS

### 2.1 Primary Objective

> Ground and refine intent from code. Validate Docreader's draft against actual implementation. Extract constraints from tests/assertions. Observe module-level rendering patterns for the ProjectionIG.

### 2.2 Initialization

Read and follow:

- `.claude/agents/ig-extractor-agent.md` (core agent definition)
{{agent_mode_modules}}

Read first for vocabulary, invariants, agent text format, and the dual-graph model:
  `intent_graph/agents_runtime/AGENT_PRIMER.md`

### 2.3 Algorithm / Execution Path

#### Step 1: Navigate & Ground from Code

**Viewport Navigation:**
- Use `ig-tool lens focus --uid UID` to refocus on different target areas as needed
- Use `ig-tool lens promote --uid UID` to increase detail level when inspecting specific nodes (skeleton→lean→full)
- Use `ig-tool lens demote --uid UID` to decrease detail and simplify view
- Use CodeMap context for orientation (structural overview, call structure, module layout)

**Code Reading & Validation:**
- Sparsely read code files in `input_source_files/` using the lens tree for orientation
- **Validate Docreader's proposed intent against actual implementation:**
  - Does the code do what the docs say?
  - Are there deviations? (e.g., docs say feature X is critical, code has it disabled)
  - Are there undocumented behaviors in the code?
- **Refine intent** to match code reality:
  - Update `intent` field to reflect actual behavior
  - Set `design_notes` to explain any Docreader vs code deviations
  - Update `epistemic_state`:
    - `unknown` → `risky` if code is unclear/complex/has TODOs
    - `unknown` → `known` if code is clear and straightforward
- **Set `impl_pointers`** to actual source file paths (relative to project root)

#### Step 2: Extract Constraints from Assertions and Tests

- Read test files (if present) in `input_test_files/`
- Extract **hard constraints** from:
  - Assertions (e.g., `assert result > 0`)
  - Type checks (e.g., `isinstance(x, MyClass)`)
  - Validation logic (e.g., `if len(data) == 0: raise ValueError`)
  - Test expectations (e.g., `assertEqual(output, expected)`)
- Add these as `constraints` entries on the target node
- **Distinguish:** constraints (must be true) vs examples (illustrative cases)
- **Format requirement:** Write constraints as plain strings in a YAML list, never as dicts
  - If describing a pattern like "Two-tier: wrapper + base", write it as one string
  - Example: `"Soft delete functions follow two-tier pattern (public wrapper + __base internal function)"`

#### Step 3: Validate and Refine Decomposition (Children)

**This step is mandatory.** Read the **Edit Primer** (`intent_graph/agents_runtime/AGENT_EDIT_PRIMER_V2.md` §Expansion Protocol) for signals, mechanics, content migration, and intentlink handling.

**Extractor-specific guidance:**

- **If Docreader proposed children:** Validate each against actual code boundaries (classes, major functions, distinct modules). Remove children that don't map to code. Add children the Docreader missed.
- **If no children proposed:** Examine the code. Does it contain 2+ distinct sub-capabilities? If yes, propose children per the protocol.
- **If genuinely atomic:** State: "No decomposition — single class/function with one responsibility."
- **Content migration is mandatory.** Distribute the parent's constraints and impl_pointers to children based on which code files they reference.

**Tools for decomposition:**
- Use `ig-tool node create --uid UID --name "Name" --intent "Intent" --parent PARENT` to propose new child nodes
- Use `ig-tool node set --uid UID --intent "New intent" --epistemic-state known` to modify existing nodes
- Use `ig-tool link create --src SRC --dst DST --intent "Intent"` to create intentlinks between nodes

**Do not skip this step.** Enriching a node's constraints without decomposing it is an incomplete extraction.

#### Step 4: Observe Module-Level Rendering Patterns

Examine the codebase structure and propose **ProjectionIG observations** (rendering patterns):

**What to observe:**

- **Module structure:** flat vs nested, domain-grouped vs functional-grouped?
- **Naming conventions:** snake_case, prefixes (e.g., `_private`), suffixes (e.g., `_utils`)?
- **Type usage:** structural typing, nominal typing, gradual typing (type hints present/absent)?
- **Import patterns:** relative imports, absolute imports, star imports (`from x import *`)?
- **File organization:** one class per file, multiple classes per file, functional modules?

**Output:** Propose ProjectionIG child nodes:

- **UID format:** `PIG-{TAG}.{SUBTAG}` (e.g., `PIG-MOD.LAYOUT`, `PIG-NAME.FUNC`, `PIG-TYPE.USAGE`)
- **epistemic_state:** `"observed"` (you've seen this pattern in the code)
- **Cite examples:** Use `design_notes` to reference specific code locations

### 2.4 Constraints, Exits & Escalations

**Constraints:**

- Read ONLY the files listed in §1.1 and §1.2
- Do not read files outside the step folder unless listed in §1.1 External references
- If context is insufficient (e.g., missing source files, CodeMap unavailable), report the gap in your output — do not forage for files
- Do not modify input files. Propose edits in output files.
- Use CodeMap for orientation and call structure, but read the actual code for implementation details (CodeMap is a skeleton, not the full picture)
- When observing rendering patterns, focus on module-level and project-level conventions (not function-level implementation details)

**Exit Conditions:**

- If `input_lens.yaml` is missing or empty → FAILURE
- If `input_source_files/` is missing or empty → FAILURE

**Escalation Rules:**

- If code contradicts docs on a critical design decision (not just a minor deviation), yield to HUMAN with options
- Default Escalation Target: ORCHESTRATOR

---

## 3. OUTPUT CONTRACT

### 3.1 Artifacts

Use `ig-tool` commands to apply all changes. The orchestrator will apply changes via lens diff/apply.

**Node Creation & Editing:**
```bash
# Create new nodes
ig-tool node create --uid UID --name "Name" --intent "Intent" --parent PARENT

# Update existing node fields
ig-tool node set --uid UID --intent "Updated intent" --epistemic-state known

# Create intentlinks between nodes
ig-tool link create --src SRC --dst DST --intent "Relationship description"

# Reparent a node
ig-tool node reparent --uid CHILD --under NEW_PARENT
```

**Batch Operations (for multiple changes):**
```bash
ig-tool apply -g graph.json --batch batch.yaml -o updated.json
```

Where `batch.yaml`:
```yaml
operations:
  - op: node.create
    uid: ROOT.1.5
    name: "Sub-capability"
    intent: "..."
    parent: ROOT.1
  - op: node.set
    uid: ROOT.1.2
    intent: "Updated"
    epistemic_state: "known"
  - op: link.create
    src: ROOT.1.2
    dst: ROOT.1.5
    intent: "Calls"
```

**Important:**
- Viewport changes (focus/promote/demote/prune/expand) don't affect the graph — they're only for your navigation
- All structural changes go through `ig-tool node`/`ig-tool link`/`ig-tool apply --batch` commands
- The orchestrator applies your changes and returns updated lens views

### 3.2 Epistemology

- Confidence Score: 0.0–1.0 (how thoroughly the extraction covered the target's code)
- Unknowns / Assumptions: list any areas you couldn't assess (e.g., missing tests, unclear code paths, external dependencies)

### 3.3 Control Flow & Telemetry

- Task Status: [SUCCESS | PARTIAL | FAILURE | YIELD_FOR_INPUT]
- Summary: 1-3 sentence summary of extraction results
- Resource Usage: `tokens: {{token_count}}, tool_calls: {{tool_call_count}}`

### 3.4 Escalation Payload (only if Status is YIELD_FOR_INPUT)

- Target: [HUMAN | ORCHESTRATOR]
- Blockage Summary: what is ambiguous or missing
- Impact Assessment: risk of guessing wrong
- Proposed Options: concrete alternatives with tradeoffs
- Agent Recommendation: leaning, if any
