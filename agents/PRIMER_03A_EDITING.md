# PRIMER_03A_EDITING

Purpose: Decision framework for modifying an IntentGraph. Assumes you have read PRIMER_00_PHILOSOPHY, PRIMER_01_SEMANTICS, and PRIMER_02_NAVIGATION.

Audience: Agents that modify graphs (Extractor, Elicitor, Steward, Docreader).

---

## What Is Editing?

Editing means modifying the graph to better capture intent while preserving invariants and maintaining global consistency.

End goal:
- Better capture intent so it can be leveraged (projection to code, docs, tests)
- Keep graph aligned with philosophy and rules, reducing corruption so it remains an effective tool

Edit types:
- Create/update/delete nodes
- Create/update/delete intentlinks (intra or inter: use qualified UID `graph_id:node_uid` in `link create` for inter; `link set`/`link remove` by UID apply to both)
- Decompose (expand) nodes into children
- Consolidate constraints upward (reverse of expansion)

All edits are made via CLI commands (see PRIMER_TOOLS for syntax), never by manually editing YAML.

**Execution context:** Your **effort hint** (PRIMER_04_WORKFLOWS §Execution context) affects how far you propagate and how many optional fixes you attempt: quick pass → fix only the target and obvious neighbors; thorough → run full propagation and address all detected issues.

### Intermediate States: You Have Flexibility

Quality rules (bounded nodes, orthogonal decomposition, no overload or under-definition) describe the target state, not every moment during editing. You are **allowed** to leave a node temporarily overloaded (e.g. before you expand it) or under-defined (e.g. before you fill gaps or get human input). The only requirement: record the condition in `epistemic_state` so it is visible (see PRIMER_00_PHILOSOPHY §When Rules Can Be Temporarily Relaxed, PRIMER_01_SEMANTICS §epistemic_state). Example: after creating a stub child, set `epistemic_state: "undecided: under-specified, refinement pending"`; when you later expand a bloated node, you can set `observed | unclear: intent overloaded, expansion pending` until the expansion is done. Do not block progress on achieving perfect shape in one step — document the interim state and let the next pass (or another agent) resolve it.

---

## Editing Theory: Scope and Propagation

### Edit Scope (The Target Subgraph)

An edit operates on a local subgraph, not always a single node. The target defines the atomic consistency boundary.

Single-node targets:
- Update intent, constraint, epistemic_state → target = one node

Multi-node targets:
- Expansion → target = parent + new children (content transfer + refinement)
- IntentLink creation → target = src + dst (relationship coherent with both endpoints)
- Reparenting → target = node + old parent + new parent (tree structure mutation)
- Constraint consolidation → target = parent + children (identical child constraints merge to parent)

The edit is atomic over the target. You cannot partially execute.

### Edit Propagation (Information Flow)

When the target subgraph changes, consistency must be verified and restored through neighbor checking. This is constraint propagation - information flow that continues until quiescence.

Wave 0: Apply change to target subgraph

Wave 1: Check immediate neighbors (parent, children, siblings, intentlink endpoints)

Wave 2+: If Wave 1 requires changes, those become new targets. Propagate again from their neighbors.

Quiescence: Typically Wave 2-3. Pruning: stop when change is local enough (doesn't affect distant semantics).

**Propagation channels:**

| Source | What propagates | Direction | Check |
|--------|----------------|-----------|-------|
| T4 | Refinement coherence | Up & Down | Parent change → children still covered? Child change → still within parent scope? |
| T3 | Connectivity validity | Horizontal | Node delete → update intentlinks. Link create → endpoints exist and constraints align? |
| P5 | Normalization | Up & Down | Duplicate constraints across peers → consolidate. Bloated parent → descend to children. |
| P4 | Projection separation | IG↔PIG | Product constraint → language-specific? Route to ProjectionIG. |
| P2 | Meaning stability | Down | Parent refined → children add precision, not new scope. |
| Epistemic | Uncertainty flow | All | Parent `risky` → children inherit. All children `undecided` → parent can't be `known`. X→Y with X `speculative` → Y inherits risk. |

Rule: After edit to target S, scan neighbors N. For each N, apply relevant checks. If violation detected, either correct N (becomes new target) or flag with issue annotation.

Rule of thumb: Because of the IntentGraph design (rough-to-fine hierarchy, normalized and compressed via P5, orthogonal decomposition), propagation is naturally bounded. Most edits quiesce at Wave 1-2. If you find propagation cascading beyond Wave 3, the graph likely has deeper structural issues (excessive coupling, violations of P5, missing intentlinks creating implicit dependencies). Signal this rather than chasing infinite propagation.

---

## When to Expand a Node

Expansion (decomposing a node into children) is the most significant edit. Apply this decision framework.

### Atomic Node Test

A node is genuinely atomic (no expansion needed) when:

1. Describes ONE capability at ONE level of abstraction
2. Constraints are cohesive (all govern same sub-capability)
3. Maps to single code unit (one module, one class, one major function)
4. Intent describable in ONE sentence without "and" joining fundamentally different things

If any fail, consider expansion.

### Signals That Warrant Expansion

1. Multiple distinct sub-capabilities
   - Intent joins 2+ separate capabilities with "and"/"with"/"also"
   - Example needing expansion: "Validate signatures and compare bodies and classify discrepancies"
   - Example atomic: "Validate signatures using type normalization"

2. Constraint sprawl across concerns
   - 8+ constraints spanning unrelated aspects (performance, security, data format)
   - Judge by cohesion, not count

3. Multiple implementation boundaries
   - impl_pointers reference distinct modules/classes/functions
   - Example: discovery.py::FunctionDiscovery, parser.py::SQLParser, validator.py::BodyValidator

4. Distinct algorithmic phases
   - design_notes describe separate processing stages
   - Example: "First scans cache, then parses source, finally fallback search"

### When NOT to Expand

- Node is genuinely atomic (passes atomic node test)
- Constraints numerous but cohesive (10 type normalization rules = one purpose)
- impl_pointers tightly coupled (class + its helper methods)
- "Distinct phases" are implementation detail, not conceptual boundaries

If a node warrants expansion but you defer it (e.g. focus elsewhere first), set `epistemic_state` to record the temporary overload (see §Intermediate States above).

---

## Expansion Protocol

### 1. Identify Sub-Capabilities

Group parent's constraints, impl_pointers, design_notes into coherent clusters. Each cluster becomes a child.

Grouping criteria:
- Code boundaries: group by module/class in impl_pointers
- Functional boundaries: group by conceptual sub-capability
- Temporal phases (if genuinely distinct): group by processing stage

### 2. Create Children

**UID Format Rules (CRITICAL — enforced by validation):**

- **L1 nodes** (parent=root): A single segment — one uppercase keyword (preferred) or one number
  - Pattern: `^[A-Z][A-Z0-9_]*$` or `^[0-9]+$`
  - Keyword examples: `DISCOVER`, `PARSE`, `VALIDATE`, `ERRORS`, `API`, `LEXER_TOKENS` (underscores allowed inside the keyword)
  - Numeric examples: `1`, `2` (allowed, but a keyword is strongly preferred)
  - **Invalid**: `D` (too cryptic — use a full word), `DISCOVER.DB` (multi-segment — belongs at L2), `_BAD` (leading underscore rejected), `discover` (lowercase rejected)

- **Root naming**: The root UID is **exactly `ROOT`** (required, enforced) and has no parent; a parentless node with any other UID is rejected. `--root-name` sets only the display name — the UID stays `ROOT`.

- **L2 nodes** (children of L1): Two patterns based on expected size:
  - **Numeric**: `{parent}.{number}` — for minor nodes unlikely to have many children (e.g., `DISCOVER.1`, `PARSE.2`)
  - **Semantic**: `{parent}.{keyword}` where keyword matches `^[A-Z][A-Z0-9_]*$` — for named sub-capabilities worth labeling (e.g., `DISCOVER.DB`, `ERRORS.HANDLER`, `API.CLIENT`, `LEXER.PARSER_INTERFACE`)

- **L3+ nodes**: Parent prefix + dot + sequential number
  - Pattern: `{parent_uid}.{number}` (e.g., `DISCOVER.DB.1`, `ERRORS.HANDLER.2`, `PARSE.2.1`)
  - Numbers indicate refinement depth: `.1`, `.2`, `.3` for siblings; `.1.1`, `.1.2` for grandchildren
  - **Trap**: the keyword suffix is an L2-only privilege (parent must be L1). At L3+ the suffix is **numeric only** — `ERRORS.HANDLER.1` valid, `ERRORS.HANDLER.PARSE` rejected. Do not carry the L2 keyword pattern down to L3.

- **ProjectionIG L1**: `PIG-{SEMANTIC}-{COMPONENT}` (e.g., `PIG-PY-TYPES`, `PIG-DOC-STYLE`)

**Rationale**: L1 UIDs are single-segment labels for top-level capabilities — a keyword like `ERRORS` or rarely a number like `1`. L2 either adds a semantic qualifier (for named sub-domains, e.g. `ERRORS.HANDLER`) or a number (for minor refinements, e.g. `ERRORS.1`). L3+ always use numbers. Single-letter UIDs (D, P, V) are discouraged — use full words.

**Naming**: Capability/component names, NOT action verbs.
- Correct: "Cache Discovery", "Source Parsing", "Validation Engine"
- Wrong: "Scan Cache", "Parse Sources", "Validate Functions"

Each child needs: uid, name, intent, parent, epistemic_state.

### 3. Migrate Content

Mandatory. Expansion without migration leaves children empty, parent bloated.

constraints: Partition among children. Cross-cutting constraints (span multiple children) stay on parent. Local constraints descend.

impl_pointers: Distribute to child whose code they reference. Parent keeps summary pointer (package/module).

design_notes: Split reasoning to children. Parent keeps decomposition rationale only.

examples: Move to child they illustrate. Parent keeps system-level examples.

data_registry: Cross-cutting data (shared config, global parameters) stays on parent. Local data (per-component positions, specific configs) descends. No duplication across siblings — shared values ascend (P5).

Invariant: No orphan content (P5).

### 4. Rewrite Parent Intent

Parent intent becomes orchestration-level - describes how children compose.

Pattern: "Achieve [high-level goal] by [composition strategy]"

Before (too specific):
```
intent: "Enable identification of which SQL functions in database have matching source definitions"
```

After (orchestration):
```
intent: "Discover all SQL functions by searching multiple information sources with fallback strategies"
```

### 5. Discover and Create IntentLinks

After creating children, search for relationships.

Between new children, ask for each pair:
1. Dataflow? Does A's output feed B's input?
2. Requires? Does B depend on A's capability?
3. Conflicts? Do A and B have mutually exclusive constraints?
4. Refines? Does B specialize A's capability?

Cross-subtree: Query neighbors of each child to find dependencies outside parent.

When to create:
- Explicit data flow (A's output → B's input)
- Dependency (B needs A)
- Constraint relationship (A limits B, or they conflict)
- Relationship is semantic (intent-level), not just implementation

Do NOT create when:
- Only in code (shared utility), not in intent
- Implicit in tree (parent depends on children)
- Projection detail (execution order)

---

## Editing Existing Nodes

### Updating intent

- Express WHY, not HOW (blind generation test)
- Keep projection-agnostic (language-swap test)
- Make self-sufficient (readable without expanding)

### Updating constraints

- Cross-cutting (stays on parent) or local (descends to child)?
- Product intent (universal) or projection detail (language-specific)?
- Duplicates existing constraint? Refactor (P5).

### Updating epistemic_state

- Be honest: `undecided` better than false certainty
- Use vocabulary: known, undecided, risky, speculative, inherited, observed
- Upgrade from `inherited` to `known` → document WHY in history

When discovering issues:
- Add issue annotations: `<base_state> | <issue_type>: <description> | <issue_type>: <description>`
- Issue vocabulary: `gap:`, `conflict:`, `missing:`, `unclear:`, `unvalidated:`
- Example: `"observed: from auth.py | gap: perf requirements not specified | missing: no link to PERF node"`
- Issues are observations about problems, not commands
- When resolved, remove issue clause and update base state

### Updating design_notes

- Capture WHY this choice over alternatives
- Record rejected options
- Note accepted tradeoffs
- Projection detail (tool choice) goes here, not in `intent`

---

## Propagation Checklist

After any edit, verify propagation:

T4: Parent↔children refinement coherent?
T3: IntentLinks valid? Endpoints exist and align?
P5: Constraints normalized? No duplication across peers? Parent bounded in size?
P4: Projection detail routed to ProjectionIG?
P2: Refinement adds precision, not new scope?
Epistemic: Uncertainty propagated correctly?

If violation detected: correct neighbor or flag with issue annotation.

---

## Next Steps

After reading this primer:

- For command syntax: See PRIMER_TOOLS (command reference catalog)
- To understand workflows: Read PRIMER_04_WORKFLOWS (Declare, Distill, Project step sequences)
