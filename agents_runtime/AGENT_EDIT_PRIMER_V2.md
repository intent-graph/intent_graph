# IntentGraph Edit Primer v2

## 1. Core Semantic Model: Abstraction Hierarchy, Not Call Graph

### The Fundamental Misunderstanding

The tree is an abstraction hierarchy, not an execution call graph. Parent and children represent the same intent surface at different resolutions (P2). The parent is not "implemented by" its children — it summarizes them at a coarser level of detail.

Wrong: Parent = orchestrator procedure that calls children as execution steps
Correct: Parent = abstract summary that children refine at higher resolution

### Principle P2: Zooming Adds Information, Never Changes Meaning

Parent = self-sufficient abstract summary. You can read and understand the parent WITHOUT expanding to children. It tells you WHAT this part does and WHY, at its level of abstraction.

Children = precision, not extension. Expanding reveals HOW the parent's intent breaks down into sub-capabilities, but the WHAT was already in the parent. Children refine existing intent scope, they don't add new scope.

Map analogy:
- Zoomed out (parent): "This region handles user authentication"
- Zoomed in (children): "Login flow", "Session management", "Password reset"

The zoomed-in view doesn't change what the region is for — it shows internal structure.

Critical test: If a reader must expand to children to understand WHAT the parent does, you wrote the parent wrong.

### Details Descend, Abstraction Ascends

The tree is a hierarchy of increasing specificity as you descend:

Level 0 (ROOT): "System validates SQL function sync"
Level 1 (D,P,V,R): "Discovery", "Parsing", "Validation", "Reporting"
Level 2 (D.1,D.2): "Cache-based discovery", "Source-based discovery"
Level 3 (D.1.1): "Filename parsing for schema extraction"

Going down: More specific (add implementation detail, tool choices, data structures)
Going up: More abstract (summarize purpose, remove implementation detail)

Rule: A node's content must be appropriate for its level in the hierarchy. Implementation details (file counts, directory names, tool names, data schemas) descend to leaves. Orchestration-level summaries ascend to parents.

### What You Are Documenting

You are capturing the intent of an EXISTING system, not designing a new one.

Wrong: "We should add X to handle Y" (future design intent)
Correct: "The system handles Y using X" (existing system intent)

Wrong: "This component will coordinate A, B, C" (future plan)
Correct: "This component coordinates A, B, C" (present capability)

Exception: Epistemic state `undecided` or `deferred` can note future decisions, but only when the system explicitly leaves something open. Example: "Caching strategy not yet chosen; current implementation uses in-memory dict"

---

## 2. Content Distribution Rules

### After Expansion: Where Content Goes

After expansion, content migrates from parent to children following abstraction level:

intent:
- Parent: Summary ("Achieve X by coordinating A, B, C")
- Children: Specific ("Achieve A using this approach")

constraints:
- Parent: Cross-cutting, composition rules
- Children: Local to child's sub-capability

impl_pointers (list of pointer strings; grammar: `path[::Symbol[.member]][ (lines X-Y)]`):

- Parent: High-level (package/module path)
- Children: Specific (file::Symbol anchor, with optional line range)

design_notes:
- Parent: Why this decomposition, tradeoffs
- Children: Reasoning specific to this child

examples:
- Parent: System-level scenarios
- Children: Examples illustrating this child

### Constraint Typing

Orchestration-level constraints (stay on parent):
- Cross-cutting requirements: "Must complete in <100ms total"
- Composition rules: "Must combine results from all strategies without duplication"
- Scope boundaries: "Must handle functions across all schemas"
- Coordination invariants: "Children execute independently and merge results"

Leaf-level constraints (migrate to children):
- Data structure schemas: "FunctionRecord has fields: schema (str), name (str), ..."
- Tool-specific requirements: "Must use pglast for SQL parsing"
- Implementation details: "Cache contains N files with naming convention X"
- Local performance: "Cache lookup must hit >90%"

Example pathology - Parent D has leaf-level constraint:
```yaml
Wrong:
  Parent D:
    constraints:
      - "Output FunctionRecord: schema (str), name (str), full_name (str),
         generated_location (Optional[FunctionLocation]), ..."

Correct:
  Parent D:
    constraints:
      - "Must provide unified view of each function's presence in cache vs source"

  Child D.4 "Discovery Output Format":
    constraints:
      - "FunctionRecord structure: schema, name, full_name, generated_location,
         source_locations, parsed metadata"
```

### Execution Order is Implementation Detail

Sequential execution order ("do X first, then Y, then Z") is HOW the code works, not WHAT the intent is.

Pathology from actual graph:
```yaml
Wrong - Parent D constraints:
  - "Invoke D.1 (generated cache scan) first"
  - "Invoke D.2 (source directory scan) second, combining results with D.1"
  - "Invoke D.3 (fallback search) third, adding locations not found in primary scans"

Correct:
  Parent D:
    intent: "Discover all SQL functions by searching multiple sources with fallback strategies"
    constraints:
      - "Must combine results from cache-based, source-based, and pattern-based discovery"
      - "Must de-duplicate when same function found in multiple locations"
    design_notes: "Discovery executes three strategies in sequence: cache (fast),
                   source (comprehensive), fallback (robustness). Order affects performance
                   but not correctness. See ProjectionIG for execution orchestration."
```

The order is a projection-level choice (execution optimization) - belongs in design_notes or ProjectionIG.

### Tool Names and Library Choices

Tool names, library choices, file formats are projection-level details describing HOW the intent is implemented in this specific projection.

```yaml
Wrong (in intent field):
  intent: "Use pglast to parse CREATE FUNCTION statements and extract metadata"

Correct (in design_notes):
  intent: "Parse SQL function definitions to extract signature and body metadata"
  design_notes: "Uses pglast library for PostgreSQL-compliant parsing. Chosen for
                 standards-compliance and robustness vs regex approaches."
```

Exception: If the tool choice is a constraint that shapes the intent (e.g., "Must work without network access" rules out cloud APIs), state it as a constraint, not as a tool name.

### Data Schemas and Type Signatures

Complete data structure schemas belong at leaves or in design_notes, not in orchestration nodes.

At orchestration level: semantic description ("provides location mapping")
At leaf level: concrete schema ("Dict[str, FunctionRecord] where FunctionRecord = ...")

---

## 3. Decomposition Decision Framework

### Atomic Node Test

A node is genuinely atomic (no expansion needed) when:
1. It describes ONE capability at ONE level of abstraction
2. Its constraints are cohesive (all govern the same sub-capability)
3. It maps to a single code unit (one module, one class, one major function)
4. You can describe its intent in ONE sentence without "and" joining fundamentally different things

If any of these fail, consider expansion.

### Signals That Warrant Expansion

1. Multiple distinct sub-capabilities
Intent describes 2+ things joined by "and"/"with"/"also" that represent separate capabilities, not aspects of one capability.
Example needing expansion: "Validate function signatures and compare function bodies and classify discrepancies by severity"
Example that is atomic: "Validate function signatures against source definitions using type normalization"

2. Constraint sprawl across concerns
8+ constraints spanning unrelated aspects (performance, security, data format, error handling, etc.). Judge by cohesion.
Example: Node has constraints about caching strategy, SQL parsing rules, error severity classification, and output formatting - these are distinct concerns.

3. Multiple implementation boundaries
impl_pointers reference distinct modules, classes, or major functions (list of pointer strings with different anchors).
Example: Node points to `src/discovery.py::FunctionDiscovery`, `src/parser.py::SQLParser`, `src/validator.py::BodyValidator` — separate components.

4. Distinct algorithmic phases
design_notes describe separate processing stages or sequential phases.
Example: "First scans cache, then parses source, finally performs fallback search" - these are phases.

5. Critic flag
The Critic agent raised an `under_decomposition` issue.

### When NOT to Expand

Do not force expansion when:
- Node is genuinely atomic (passes atomic node test)
- Constraints are numerous but cohesive (e.g., 10 type normalization rules all serve same purpose)
- impl_pointers reference tightly coupled code (e.g., a class and its helper methods all in same file/module)
- "Distinct phases" are implementation detail, not conceptual boundaries (e.g., "read file, parse, return" is one capability: "parse file")

When uncertain, state reasoning explicitly in design_notes.

### Expansion Decision Tree

Ask in order:

1. Does this node describe ONE thing at ONE level of abstraction?
   No → EXPAND
   Yes → Continue to 2

2. If I read just the parent (without expanding), is it a valid, complete description at its level?
   No (parent is vague/incomplete) → ENRICH PARENT FIRST, then reconsider expansion
   Yes → Continue to 3

3. Do the constraints/impl_pointers/design_notes naturally group into distinct clusters?
   Yes → EXPAND (each cluster becomes a child)
   No → Continue to 4

4. Would a reader need to expand to children to understand WHAT this does?
   Yes → You wrote the parent wrong (rewrite to be self-sufficient), then reconsider
   No → KEEP ATOMIC (no expansion needed)

---

## 4. Expansion Protocol

### Scope Boundary (Hard Rule)

You can ONLY decompose the target node.

If working on node X, you can create children X.1, X.2, X.3
You cannot decompose Y (another node in the lens) - queue it for its own distill cycle
You cannot decompose X.1 after creating it - it gets queued for its own cycle

Why: Mixed-detail coherence requires that each distill cycle works at ONE level. Recursive decomposition breaks the limited-context reasoning model.

If you discover other nodes need expansion: Add them to output_queue_additions.yaml, do NOT expand them in-place.

### Expansion Steps

Step 1: Identify Sub-Capabilities

Group the parent's constraints, impl_pointers, and design_notes into coherent clusters. Each cluster becomes a child.

Grouping criteria:
- Code boundaries (Extractor): group by module/class referenced in impl_pointers
- Functional boundaries (Docreader/Elicitor): group by conceptual sub-capability
- Temporal phases (if genuinely distinct): group by processing stage

Step 2: Create Child Nodes

Use diff format. Each child needs at minimum: uid, name, intent, parent

```yaml
- uid: PARENT.1
  name: "Sub-capability name"  # Capability noun phrase, not action verb
  intent: "What this child achieves and why (at this level)"
  parent: PARENT
  epistemic_state: "inherited"
  _new: true
```

UID convention: {parent_uid}.N (sequential: .1, .2, .3)
Check: Inspect collapsed_children on the parent to avoid collisions with pre-existing children.

Naming convention:
Correct: Capability/component names: "Cache Discovery", "Source Parsing", "Validation Engine"
Wrong: Action verbs: "Scan Cache", "Parse Sources", "Validate Functions"

The name should describe what this part IS, not what action to invoke.

Step 3: Migrate Content from Parent to Children

This is mandatory. Expansion without migration leaves children empty and the parent bloated.

For each parent field:

constraints: Partition among children. Each constraint goes to the child whose sub-capability it governs. Constraints that span multiple children (cross-cutting, composition rules) remain on parent.

impl_pointers: Distribute each pointer string to the child whose code it references (each list item to one child). Parent retains only summary pointers (e.g., package/module path, not specific file::Symbol anchors).

design_notes: Split reasoning that pertains to specific sub-capabilities into child design_notes. Parent keeps only cross-cutting rationale (why this decomposition, overarching tradeoffs).

examples: Move to the child they illustrate. Parent keeps only system-level examples.

Invariant: No orphan content. After migration, every parent constraint, impl_pointer, example, and design_notes passage must either live on a child OR remain on the parent with clear orchestration-level justification.

Step 4: Rewrite the Parent Intent

The parent's intent must become orchestration-level - it describes how the children compose, not their individual details.

Pattern: "Achieve [high-level goal] by [composition strategy]"

Example correcting actual pathology:

Before (execution-step thinking):
```yaml
Parent D:
  intent: "Enable identification of which SQL functions in the database have matching
           source definitions, and where those definitions are located..."
  constraints:
    - "Invoke D.1 first"
    - "Invoke D.2 second, combining results"
    - "Invoke D.3 third, adding locations not found"
```

After (abstraction-level summary):
```yaml
Parent D:
  intent: "Discover all SQL functions in the system by searching multiple information
           sources with fallback strategies to ensure comprehensive coverage"
  constraints:
    - "Must identify functions from both database-generated cache and source code repositories"
    - "Must combine results from all strategies without duplication"
    - "Must provide complete location mapping for each discovered function"
  design_notes: "Discovery uses three strategies (cache, source, fallback) executed in
                 sequence for performance with fallback for robustness.
                 Children are independent search strategies; parent merges results."

Children:
  D.1: "Discover functions from database-extracted definitions via filename parsing"
  D.2: "Discover functions from source code via AST parsing of CREATE FUNCTION statements"
  D.3: "Discover functions via text-based pattern matching when structured approaches incomplete"
```

Step 5: Discover and Handle Intentlinks

### Step 5a: Discover Missing Intentlinks

After creating children, actively search for cross-child and cross-subtree relationships. Under-linked graphs are a common pathology — agents focus on hierarchical decomposition but miss horizontal relationships.

**Between new children:**

Ask for each pair of children:
1. **Dataflow**: Does Child A's output feed into Child B's input?
   - Example: ROOT.2.1 (SQL Parsing) → ROOT.2.2 (Metadata Extraction) — parsed AST flows to metadata extractor
   - Pattern: Sequential pipeline stages, transformation chains

2. **Requires**: Does Child B depend on Child A's capability being available?
   - Example: ROOT.3.1 (Signature Validation) requires ROOT.2.3 (Type Normalization) — can't validate without normalized types
   - Pattern: One capability enables or constrains another

3. **Conflicts**: Do Child A and B have mutually exclusive constraints or modes?
   - Example: ROOT.1.1 (Cache Discovery) conflicts with ROOT.1.2 (Fallback Search) — only invoked when cache fails
   - Pattern: Alternative strategies, error handling branches

4. **Refines**: Does Child B provide a more specific version of Child A's capability?
   - Example: ROOT.4.2 (Human-Readable Report) refines ROOT.4.1 (Summary Statistics) — same data, different presentation
   - Pattern: Specialization, format transformation

**Cross-subtree (children to existing nodes outside this parent):**

Query siblings and cousins:
```bash
# Find all nodes at the same level (siblings of parent)
ig-tool query -g G --children {parent.parent}

# Find neighbors of each child (may reveal cross-subtree dependencies)
ig-tool query -g G --neighbors {CHILD_UID}
```

Common cross-subtree patterns:
- Shared data structures (multiple nodes read/write same format)
- Cross-cutting concerns (logging, caching, error handling)
- Constraint propagation (one subtree's output constrains another's input)

**When to create an intentlink:**

Create a link when:
- There's explicit data flow (output of A is input to B)
- There's a dependency (B cannot function without A)
- There's a constraint relationship (A limits B's behavior, or they conflict)
- The relationship is semantic (intent-level), not just implementation detail

Do NOT create a link when:
- Relationship is only in code (shared utility function) but not in intent
- It's implicit in the parent-child tree (parent depends on child is automatic, don't link)
- It's a projection-level detail (execution order, performance optimization)

### Step 5b: Handle Existing Intentlinks

Intentlinks touching the expanded node must be addressed:

Incoming links (ilink(X, PARENT)):
- If the link's purpose maps to a specific child: create refined child link (ilink(X, PARENT.N) with parent: X_PARENT) and note the refinement
- If the link applies broadly to all children: leave it on parent (lifted automatically at display time)

Outgoing links (ilink(PARENT, Y)):
- Same logic - refine to child if relationship is specific, leave on parent if general

Between new children:
- Create intentlinks where children exchange data, have ordering dependencies, or must coordinate
- These are new canonical links (not lifted)

Never create lifted links in a diff. Only canonical links. The system computes lifted projections automatically.

Tool: ig-tool query -g G --links UID -o links.yaml to inspect existing links before deciding.

Step 6: Queue New Children

Add child UIDs to output_queue_additions.yaml so the orchestrator schedules them for their own distill cycle.

Epistemic state: Children created during expansion get epistemic_state: "inherited" - they need their own pass to validate and refine.

---

## 5. Common Pathologies

Patterns observed in actual agent outputs. Recognize and avoid them.

### Execution Sequence Thinking

Symptom: Parent constraints describe procedure: "do X first, then Y, then Z"

Actual pathology from graph.json:
```yaml
Wrong - Parent D:
  constraints:
    - "Invoke D.1 (generated cache scan) first"
    - "Invoke D.2 (source directory scan) second, combining results with D.1"
    - "Invoke D.3 (fallback search) third, adding locations not found in primary scans"

Why wrong: Parent treats children as execution steps in a call graph, not as refinements of the discovery intent.

Correct:
  Parent D:
    intent: "Discover all SQL functions by searching multiple sources with fallback strategies"
    constraints:
      - "Must combine results from cache-based, source-based, and pattern-based discovery"
      - "Must de-duplicate when same function found in multiple locations"
    design_notes: "Three strategies executed in sequence (cache → source → fallback) for
                   performance. Order is projection-level choice; intent is comprehensive
                   coverage through multiple methods."
```

### Data Schema in Orchestration Node

Symptom: Parent constraints include complete type signatures

Actual pathology:
```yaml
Wrong - Parent D:
  constraints:
    - "Output FunctionRecord: schema (str), name (str), full_name (str),
       generated_location (Optional[FunctionLocation]), source_locations (List[FunctionLocation]),
       generated_parsed (Optional[ParsedFunction]), source_parsed (List[ParsedFunction])"

Why wrong: Leaf-level implementation detail (complete data structure schema) in orchestration node.

Correct - Option 1 (separate child):
  Parent D:
    constraints:
      - "Must provide unified view of each function's presence in generated cache vs source code"

  Child D.4 "Discovery Output Format":
    constraints:
      - "FunctionRecord structure: schema, name, full_name, generated_location,
         source_locations, generated_parsed, source_parsed"

Correct - Option 2 (projection-level detail):
  Parent D:
    constraints:
      - "Must provide unified view of each function's presence in generated cache vs source code"
    design_notes: "Output structure defined as FunctionRecord dataclass. Complete schema in impl_pointers."
    impl_pointers:
      - "src/discovery.py::FunctionRecord (lines 15-45)"
```

### Implementation Details at Root Level

Symptom: ROOT node has file counts, directory names, tool names

Actual pathology:
```yaml
Wrong - ROOT:
  constraints:
    - "Must discover functions from both generated cache (N files extracted via
       pg_get_functiondef) and source code (by_feature/, by_schema/ organization)"

Why wrong: "N files" is test-specific, "pg_get_functiondef" is tool name, "by_feature/, by_schema/" are directory names.

Correct:
  ROOT:
    constraints:
      - "Must discover functions from both database-generated definitions and source code repositories"

  Child D or D.2:
    constraints:
      - "Source code organized in: by_feature/, by_schema/"
    design_notes: "Generated cache extracted via pg_get_functiondef (N files in test dataset)."
```

### Children Named as Actions

Symptom: Child names are verb phrases describing actions

Actual pathology:
```yaml
Wrong: D.1: "Scan Generated Cache", D.2: "Scan Source Directories", D.3: "Fallback Search"

Why wrong: Action verbs (execution steps), not capability names. Reinforces "procedure call" thinking.

Correct: D.1: "Generated Cache Discovery", D.2: "Source Code Discovery", D.3: "Pattern-Based Fallback Discovery"
```

### Tool Names in Intent Field

Symptom: Intent describes implementation tool instead of capability

```yaml
Wrong:
  intent: "Use pglast library to parse CREATE FUNCTION statements and extract metadata"

Correct:
  intent: "Parse SQL function definitions to extract signature and body metadata for validation"
  design_notes: "Uses pglast library for PostgreSQL-compliant parsing."
```

### Parent Not Self-Sufficient

Symptom: Must read children to understand what parent does

```yaml
Wrong:
  Parent: "Discovery Orchestration"
  intent: "Coordinate discovery phases"

Why wrong: Violates P2. "Coordinate discovery phases" doesn't tell you WHAT discovery achieves.

Correct:
  Parent: "Discovery Orchestration"
  intent: "Discover all SQL functions in the system by searching multiple information
           sources with fallback strategies to ensure comprehensive coverage"
```

### Children Extend Parent Scope

Symptom: Child adds intent not present in parent

```yaml
Wrong:
  Parent: "Validate function signatures against source definitions"
  Child: "Also log analytics events for validation failures"

Why wrong: Violates T4 (refinement coherence). Logging analytics is NEW intent, not refinement of validation.

Fix: Either (1) recognize parent was under-specified, add logging to parent intent, or (2) remove scope creep, logging belongs to separate node.
```

### Missing Intentlinks Between Children

Symptom: Children form a pipeline or have dependencies, but no intentlinks capture the relationships

Actual pathology from graph with 16 nodes but only 7 intentlinks:
```yaml
Wrong:
  ROOT.2: Function Parsing & Extraction
    Children: ROOT.2.1 (SQL Parsing), ROOT.2.2 (Metadata Extraction), ROOT.2.3 (Type Normalization)
    No intentlinks between children

Why wrong: These form a clear pipeline (parse → extract metadata → normalize types), but relationships are implicit. Graph structure doesn't capture dataflow.

Correct:
  ROOT.2: Function Parsing & Extraction
    Children:
      ROOT.2.1: SQL Parsing
      ROOT.2.2: Metadata Extraction
      ROOT.2.3: Type Normalization
    Intentlinks:
      LINK.2.A: ROOT.2.1 → ROOT.2.2 (dataflow: "Parsed AST feeds metadata extractor")
      LINK.2.B: ROOT.2.2 → ROOT.2.3 (dataflow: "Raw metadata requires type normalization")
```

Common under-linked patterns:
- Sequential pipeline stages (parse → transform → validate → output)
- Alternative strategies with no conflict links (cache vs source vs fallback)
- Cross-subtree dependencies (ROOT.3.1 requires ROOT.2.3's normalized types)

Diagnostic: Run `ig-tool query -g G --overview` — if nodes >> links, graph is likely under-linked. Rule of thumb: expect 0.4-0.8 intentlinks per node for well-connected graphs.

---

## 6. Invariants & Tools

### Invariants to Maintain

T4 - Refinement coherence:
Children collectively cover the parent's intent. No child contradicts or extends beyond the parent's scope.

P2 - Zooming adds information:
Children add precision but don't change the parent's meaning. The parent, read alone, remains a valid coarser description.

T3 - Intentlink well-formedness:
All link endpoints must exist. Refined child links must satisfy the descendant rule (V&F §5).

No orphan content:
Every parent field value must be accounted for after migration (either on children or remaining on parent with justification).

### Tools

Query node details:
ig-tool query -g G --node UID -o node.yaml

Inspect intentlinks touching a node:
ig-tool query -g G --links UID -o links.yaml

Dry-run validate expansion:
ig-tool parse -g G -i edits.yaml -o parsed.yaml

Apply edits:
ig-tool apply -g G -i edits.yaml -o G_updated.json

Lens-specific operations:
See agents/PRIMER_TOOLS.md for command guide; .claude/skills/ig-tool-*/SKILL.md for exact syntax.

## Agent Mental Checklist

Before making an edit, verify:

1. Am I treating children as refinements (not execution steps)?
2. Can I read the parent alone and understand WHAT it does at this level?
3. Do children collectively cover the parent's intent (not extend it)?
4. Am I putting HOW (tools, data schemas) in design_notes (not intent)?
5. Are constraints appropriate for this abstraction level (orchestration vs leaf)?
6. Am I documenting the existing system (not designing a future one)?
7. Have I migrated content from parent to children (no orphan content)?
8. Have I identified intentlinks between new children (dataflow, requires, conflicts, refines)?
9. Have I checked for cross-subtree dependencies with siblings/cousins using ig-tool query?
10. Does each node with impl_pointers that calls/uses other nodes have appropriate intentlinks?

Core principle: Intent is hierarchical. Details descend, abstraction ascends. The tree lets readers zoom in/out without losing coherence. Preserve that property with every edit. A well-formed graph has both vertical structure (parent-child refinement) and horizontal structure (peer-to-peer intentlinks).
