# PRIMER_01_SEMANTICS

Purpose: How to read and interpret an IntentGraph correctly. Assumes you have read PRIMER_00_PHILOSOPHY.

Audience: All agents that need to understand graph structure before acting on it.

---

## Reading Intentnodes
<!-- Lines 11-13 -->

An intentnode has fields. Each field has a specific semantic role. Your **execution context** (effort hint; see PRIMER_04_WORKFLOWS §Execution context) may guide how deeply you interpret ambiguous or vague content — quick pass vs thorough.

### intent
<!-- Lines 16-17 -->
WHAT this part does and WHY. Not HOW it's implemented. If you see tool names, library choices, or data schemas in `intent`, they belong in `design_notes` instead. The intent should pass the blind generation test: a developer reading only this should understand the purpose, not be able to reproduce the exact code.

### constraints
<!-- Lines 20-24 -->
MUST conditions. These are boundaries that cannot be violated. Distinguish types:
- Cross-cutting constraints (orchestration level): "Must complete in <100ms total", "Must combine results from all strategies without duplication"
- Local constraints (leaf level): "FunctionRecord has fields: schema (str), name (str), ...", "Cache lookup must hit >90%"
- If a constraint is about orchestration/composition, it stays at the parent. If it's about data structure or tool behavior, it descends to children.

### design_notes
<!-- Lines 27-28 -->
WHY this choice over alternatives. Captures reasoning, rejected options, accepted tradeoffs. Also holds projection-level detail: "Uses pglast library for PostgreSQL-compliant parsing. Chosen for standards-compliance vs regex approaches." Tool names and library choices go here, not in `intent`.

### epistemic_state
<!-- Lines 31-40 -->
What is KNOWN about this node. Free text, not an enum. Common patterns:
- `known` — well-understood, stable
- `undecided` — multiple options, no decision yet → act: present options to human or research further
- `risky` — decision made but carries identified risks → act: flag in reviews, add validation
- `speculative` — best guess, low confidence → act: validate before building on it
- `inherited` — assumed from parent, not independently validated → act: validate if this node becomes critical
- `observed` — extracted from existing code (Distill workflow) → act: confirm this still matches the actual code. `observed:` carries a standing re-grounding obligation — its evidence (cited files, symbols, lines, counts) is a snapshot that can drift or be fabricated; re-verify against current ground truth, defaulting to refuted when you cannot confirm (PRIMER_04 §Critique grounding check)

If epistemic_state is missing, treat as `unassessed` (not `known`). Do not assume stability.

#### Multi-Issue Convention (Pipe-Separated)
<!-- Lines 43-72 -->

When discovering problems during workflows, append issue annotations using pipe (`|`) separation:

**Pattern:**
```
epistemic_state: "<base_state>: <description> | <issue_type>: <issue> | <issue_type>: <issue> ..."
```

**Issue vocabulary:**
- `gap:` — missing information
- `conflict:` — contradiction or tension
- `missing:` — expected relationship/link absent
- `unclear:` — vague or ambiguous
- `unvalidated:` — needs confirmation

**Examples:**
```yaml
epistemic_state: "observed: extracted from auth.py | gap: performance requirements not specified"
epistemic_state: "known | missing: no intentlink to CONCURRENCY node"
epistemic_state: "undecided: three strategies proposed | unvalidated: no test coverage data"
epistemic_state: "risky: uses experimental API | conflict: constraint C1 contradicts parent INFRA"
```

**Usage:**
- Base state comes first (the fundamental epistemic status)
- Issues follow, each as `type: description` after a pipe
- No schema change — this is a lightweight textual convention
- Steward and Elicitor agents should prioritize nodes with `|` in epistemic_state (indicates discovered issues)
- Issues accumulate during workflow steps; resolve them by updating the base state and removing the issue annotation

### impl_pointers
<!-- Lines 75-76 -->
WHERE this intent is realized in code. **A list of pointer strings**, one location per entry, each following the grammar `path[::Symbol[.member]][ (lines X-Y)]` (formalism §4.2) — e.g. `src/auth.py::AuthParser.parse (lines 40-80)`. Prefer symbol anchors over line ranges (lines rot; symbols survive edits). Machine-checkable: validate/Verifier can parse and resolve pointers against the codebase. Used for traceability and by Extractor/Generator agents.

### history
<!-- Lines 79-82 -->
WHO did what, WHEN. Provenance log, append-only. Format: `{who: "agent:extractor", date: "2026-02-15T14:30", note: "extracted from auth.py"}`.

**You do not write history entries by hand.** Provenance is captured automatically at the write boundary: every `ig-tool` save diffs the graph and stamps one commit-style entry per changed node. Pass `--role <role>` so `who` resolves to `agent:<role>`, and `-m "<one-liner>"` to supply the note (say *why*; omitted → auto-generated diff summary like `"updated: intent, constraints"`). Humans resolve from `IG_ACTOR`/git identity, with a `via:<channel>` qualifier for GUI channels (e.g. `remi via:obsidian`). Trivial changes (sibling reorder, lens config) never stamp.

### data_registry
<!-- Lines 85-101 -->
Structured data store attached to a node. Holds **data** (positions, measurements, config values, lookup tables) that other fields reference via slash-notation paths. Not prose.

**Slash-notation references.** Any field (intent, constraints, design_notes, examples) may reference into the registry using a slash-prefixed path:
```
/positions/ROOT.1/x      → data_registry["positions"]["ROOT.1"]["x"]
/spacing/horizontal      → data_registry["spacing"]["horizontal"]
```

**Key rules for agents:**
- Values are data, not sentences. Prose belongs in `intent` or `design_notes` (G2).
- Every top-level key must be referenced by at least one other field on the same node (G1 — no orphan keys).
- Parent holds cross-cutting data; children hold local data; no duplication across siblings (G3).
- Product IG holds domain data; ProjectionIG holds rendering data — don't mix concerns (G4).
- Reserved key `_epistemic`: per-path epistemic state overrides — opaque at model level, do not use for application data.

**When writing nodes:** if you have structured data (positions, spacing, thresholds, config values) that you'd otherwise embed inline in a constraint string, put it in `data_registry` and reference it with a slash path.

### examples
<!-- Lines 104-105 -->
Concrete scenarios illustrating the intent. Not test cases (those belong in a test ProjectionIG or verification layer), but usage examples that clarify what the intent means.

### collapsed_children
<!-- Lines 108-109 -->
(read-only when you receive a Lens) UIDs of children that exist but are not expanded in your current view. Tells you "this node has refinement available but you're seeing it collapsed."

### UID Format Convention
<!-- Lines 112-133 -->

UIDs follow a hierarchical naming convention enforced by validation:

- **ROOT** *(required — enforced by validation)*: The single root node. Its UID is **exactly `ROOT`** — a parentless node with any other UID is rejected. `--root-name` sets only the display name; the UID stays `ROOT`.
- **L1 nodes** (children of root): A single segment — one uppercase keyword (preferred) or one number
  - Pattern: `^[A-Z][A-Z0-9_]*$` or `^[0-9]+$`
  - Examples: `DISCOVER`, `PARSE`, `ERRORS`, `API`, `LEXER_TOKENS`, `1`, `2`
  - Must be one segment — no dots
  - Underscores are **allowed inside** the keyword; a leading underscore is **rejected** (`_BAD` invalid)
  - Lowercase rejected (`discover`, `lexer_tokens` invalid)
  - Keyword is strongly preferred; numeric is allowed but rare
  - **Cannot** be multi-segment: ~~`DISCOVER.DB`~~, ~~`ERROR.HANDLER`~~ (these belong at L2)
- **L2 nodes** (children of L1): Two patterns depending on expected size:
  - **Numeric** — when the L2 node is minor or unlikely to have many children: `{parent}.{number}` (e.g., `DISCOVER.1`, `PARSE.2`)
  - **Semantic** — when the L2 node is a named sub-capability worth labeling: `{parent}.{keyword}` where keyword matches `^[A-Z][A-Z0-9_]*$` (e.g., `DISCOVER.DB`, `ERRORS.HANDLER`, `API.CLIENT`, `LEXER.PARSER_INTERFACE`)
- **L3+ nodes**: Parent prefix + dot + sequential number
  - Examples: `DISCOVER.DB.1`, `ERRORS.HANDLER.1`, `PARSE.2.1`
  - The keyword suffix is an **L2-only privilege** — allowed only when the parent is L1. At L3+ the suffix is **numeric only**: `ERRORS.HANDLER.1` valid, `ERRORS.HANDLER.PARSE` rejected.
- **ProjectionIG L1**: `PIG-{SEMANTIC}-{COMPONENT}` (e.g., `PIG-PY-TYPES`, `PIG-DOC-STYLE`)

This makes the tree self-documenting: `ERRORS.HANDLER.1` tells you this is the first refinement of the handler sub-domain of top-level errors.

### Node Name Content Safety
<!-- Lines 136-160 -->

The node's **display name** (`name` field) must not contain filesystem-unsafe or wiki-link-unsafe characters, as these cause silent data corruption during Obsidian export/import round-trips:

**Forbidden characters in node `name`:**

```text
/ \ : * ? " < > | [ ] # ^
```

**Why these matter:**

- `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|` — Illegal in filenames (POSIX `/`, Windows `\:*?"<>|`). When a node is exported to Obsidian vault, the filename is built as `{uid} {sanitized_name}.md`. These characters are stripped during export, leaving only whitespace. On merge-back, the stripped name looks like a genuine edit — a silent, lossy corruption that breaks round-trip integrity.
- `[`, `]`, `|`, `#`, `^` — Break Obsidian wiki-link syntax (`[[name]]`, `[[name|alias]]`, `^blockid`, `#heading`), causing parse failures in the vault.

**Example of the corruption hazard:**

- Original node name: `"Modern / Minimalist"` (uid: `IDIOM.MODERN_MINIMALIST`)
- Exported filename: `IDIOM.MODERN_MINIMALIST Modern  Minimalist.md` (the `/` is stripped)
- Filename read back: `name = "Modern  Minimalist"` (trailing spaces collapsed to single space)
- Merge result: Silent edit to node name; user did not change it, but `name` field is now different in the canonical graph.

**Rule:** Always use the `name` field for human-facing intent and explanation; use the `UID` for system-level hierarchy. If you need alternative descriptions, use `examples` or `design_notes`. Never encode structure or special syntax into the `name`.

---

## Reading the Tree Structure
<!-- Lines 163-196 -->

The tree is an abstraction hierarchy. P2 (zooming adds information) governs how to interpret parent-child relationships.

Parent-child semantics:

Parent = abstract summary at Level N. Self-sufficient: you can read the parent alone and understand WHAT it does without expanding to children.

Children = precision at Level N+1. They collectively refine the parent's intent. They do NOT add new scope — they break down existing scope into sub-capabilities.

Children do NOT overlap: Each child addresses a distinct sub-capability. If two children describe overlapping concerns, they should be merged or one should be removed. The decomposition must be orthogonal — like database normalization, each piece of intent appears exactly once at each level.

Test for correct parent: Can you read the parent's intent without expanding to children and understand WHAT it does? If no, the parent is written wrong (too vague, too procedural, or missing key information).

Test for correct children: Do the children collectively cover the parent's intent? Is there anything in the parent's intent that isn't addressed by at least one child? If yes, you're missing a child. Is there anything in a child's intent that wasn't implied by the parent? If yes, the child is adding scope (violates T4). Do any two children describe overlapping capabilities? If yes, the decomposition is not orthogonal — refactor.

Content distribution after expansion:

When a node is expanded into children, content migrates:
- intent: Parent becomes orchestration-level summary ("Achieve X by coordinating A, B, C"). Children get specific sub-capability intents.
- constraints: Cross-cutting constraints stay on parent. Local constraints descend to children.
- impl_pointers: Parent keeps high-level pointers (package/module). Children get specific pointers (files, classes, functions).
- design_notes: Parent keeps decomposition rationale ("Why this breakdown"). Children get reasoning specific to their sub-capability.
- data_registry: Parent holds cross-cutting data (shared config, global parameters). Children hold local data (specific positions, per-component config). No duplication across siblings.

Execution order is NOT structure:

Wrong interpretation: "Parent does step 1, then step 2, then step 3" (procedural thinking).

Correct interpretation: "Parent represents a capability that is refined into sub-capabilities A, B, C. The fact that they execute sequentially is a projection-level detail (belongs in ProjectionIG or design_notes), not a structural property of the intent."

If you see constraints like "Invoke D.1 first, then D.2 second, then D.3 third" at orchestration level, flag this as a pathology. Execution order is HOW, not WHAT.

---

## Reading IntentLinks
<!-- Lines 199-234 -->

An intentlink captures a semantic relationship between two intentnodes. The `intent` field on the link describes what must be true between them. **Inter intentlinks** link projection choices to product nodes (e.g. PIG → product); endpoints are qualified as `graph_id:node_uid`.

Four common patterns:

1. Dataflow — "X produces output that Y consumes"
   - Example: `PARSE.1 (SQL Parsing) → PARSE.2 (Metadata Extraction)` with intent "Parsed AST feeds metadata extractor"
   - Interpretation: Y depends on X's output. If X changes output format, Y must adapt.

2. Requires — "Y depends on X's capability being available"
   - Example: `VALIDATE.1 (Signature Validation) requires PARSE.3 (Type Normalization)` with intent "Cannot validate signatures without normalized types"
   - Interpretation: Y cannot function without X. X must be implemented/available before Y.

3. Conflicts — "X and Y have mutually exclusive constraints or modes"
   - Example: `DISCOVER.1 (Cache Discovery) conflicts with DISCOVER.2 (Fallback Search)` with intent "Fallback only invoked when cache fails"
   - Interpretation: These are alternative strategies. Both shouldn't execute in the same scenario.

4. Refines — "Y is a more specific version of X's capability"
   - Example: `REPORT.2 (Human-Readable Report) refines REPORT.1 (Summary Statistics)` with intent "Same data, different presentation"
   - Interpretation: Y specializes X. Changes to X's data model must be reflected in Y.

What intentlinks are NOT:

- Not code-level function calls (those are implementation detail)
- Not "X uses utility function from Y" (shared utility is not an intent relationship)
- Not implicit in the tree (parent depends on children is automatic, don't create a link for it)

Lifted vs canonical intentlinks:

- Canonical link: Explicitly created at a specific tree level. Stored in the graph.
- Lifted link: Automatically computed when nodes are collapsed. If `EXTRACT.1 → TRANSFORM.2` exists and you collapse to show only `EXTRACT` and `TRANSFORM`, the system lifts this to `EXTRACT → TRANSFORM` for display. You don't create lifted links manually — the system computes them.

When you see a link in your Lens, it's either canonical at the displayed level or lifted from below. Check the link's `parent` field: if it references a node at a deeper level, it's lifted.

---

## Dual-Graph Interpretation
<!-- Lines 237-239 -->

Product IntentGraph and ProjectionIG are both full IntentGraphs. They follow the same rules (T1-T4, P1-P5, same node/link schema). The only difference is semantic: what they capture.

### Product IntentGraph
<!-- Lines 242-253 -->
WHAT the system does and WHY.

Belongs here:
- "Output is a keyed mapping of function records"
- "Must validate signatures against source definitions"
- "Discovery combines results from multiple strategies"

Does NOT belong here:
- "Output is Dict[str, FunctionRecord]" (language-specific typing)
- "Uses pglast for SQL parsing" (tool choice)
- "Errors logged to stderr" (projection rendering choice)

### ProjectionIG
<!-- Lines 256-263 -->
HOW a specific projection should be rendered and WHY those rendering choices.

Belongs here (for a Python code ProjectionIG):
- "Use dataclasses for structured data (not dicts or NamedTuples)" (paradigm choice)
- "Naming convention: snake_case for functions, PascalCase for classes" (style choice)
- "Error handling: raise custom exceptions, don't return error codes" (architectural choice)
- "Type hints required for all public APIs" (annotation policy)

### Language-swap test
<!-- Lines 266-281 -->

Read a constraint or intent sentence. Mentally replace the target language (Python → C++, or Markdown → LaTeX, or pytest → JUnit). Does the sentence still make sense?

- If YES: it's projection-agnostic, belongs in Product IG.
- If NO: it's projection-specific, belongs in ProjectionIG.

Examples:
- "Must handle concurrent requests safely" → YES (universal constraint) → Product IG
- "Must use thread-safe collections from `collections`" → NO (Python-specific) → ProjectionIG
- "Output must be human-readable" → YES (universal) → Product IG (doc projection)
- "Output must use Oxford comma and Title Case headings" → NO (style-specific) → ProjectionIG (doc projection)

When you encounter projection leakage (language-specific content in Product IG), flag it. Critic agents use the `projection_hints` issue type for this.

---

## Common Misreadings
<!-- Lines 284-336 -->

These are patterns observed in actual agent outputs. Recognize them and avoid.

Misreading 1: Execution sequence thinking

Symptom: Parent constraints describe procedure ("do X first, then Y, then Z").

Why wrong: Parent should describe WHAT the capability achieves at an abstract level, not HOW it orchestrates steps. Execution order is a projection-level choice (performance optimization), not product intent.

Correct interpretation: Parent describes the goal and composition strategy. Design_notes or ProjectionIG captures execution order if it matters.

Misreading 2: Children as function calls

Symptom: Interpreting children as steps in a procedure that the parent "calls."

Why wrong: Children are refinements of the parent's intent surface, not execution steps. The parent doesn't "implement" by calling children — the parent and children describe the same capability at different resolutions.

Correct interpretation: Parent is abstract summary. Children add precision. Both describe the same thing.

Misreading 3: Tool names in intent

Symptom: Intent field says "Use pglast to parse SQL" or "Store in Redis cache."

Why wrong: Tool/library choice is HOW (projection detail), not WHAT (product intent).

Correct interpretation: Intent should be tool-agnostic: "Parse SQL function definitions to extract metadata." Design_notes records the tool choice: "Uses pglast library for PostgreSQL-compliant parsing."

Misreading 4: Data schema in orchestration node

Symptom: Parent node has complete type signatures or data structure schemas as constraints.

Why wrong: Complete schemas are leaf-level detail. Orchestration nodes should have semantic constraints about data properties, not schemas.

Correct interpretation: Parent constraint: "Output provides unified view of each function's presence in generated cache vs source code." Leaf node constraint: "FunctionRecord structure: schema, name, full_name, generated_location, source_locations."

Misreading 5: Missing intentlinks

Symptom: Nodes form a pipeline (A produces data, B transforms it, C validates it) but no intentlinks capture these relationships.

Why wrong: The graph structure doesn't capture dataflow or dependencies. You're relying on implicit understanding.

Correct interpretation: Create intentlinks between A→B (dataflow), B→C (dataflow), and potentially A→C (if C validates A's output). Explicit relationships make dependencies traceable.

Misreading 6: Confusing epistemic_state with quality

Symptom: Treating `undecided` as "bad" and `known` as "good."

Why wrong: Epistemic state is descriptive, not evaluative. `undecided` means "we know there are options and no decision has been made" — which is honest and useful. `known` means "well-understood and stable" — but if it's wrong, marking it `known` doesn't make it right.

Correct interpretation: Epistemic state is transparency. If something is uncertain, mark it `undecided` or `speculative`. This signals to other agents and humans that care is needed. False certainty (marking `known` when it's not) is worse than acknowledged uncertainty.

---

## Interpreting Collapsed Context
<!-- Lines 339-357 -->

When you receive a Lens, some nodes will have `collapsed_children` — a list of child UIDs that exist but aren't expanded in your view.

What this tells you:

"This node has refinement available. You're seeing it at a coarse level. Children exist but you don't have their detail."

How to act:

- If you need to understand this node's children to complete your task: use `ig-tool lens expand -l lens.yaml -g graph.json --uid UID -o lens.yaml` to expand it.
- If the coarse level is sufficient: leave it collapsed. Don't expand unnecessarily — budget is limited.
- If you need detail on just ONE specific child: use `ig-tool query -g graph.json --node CHILD_UID -o node.yaml` for a spot check without expanding the whole subtree.

What NOT to do:

Don't assume collapsed children are unimportant. They might be critical to your task — you just don't have visibility yet. If you're unsure, expand or query rather than guessing.

---

## Next Steps
<!-- Lines 360-366 -->

After reading this primer:

- To navigate with Lens: Read PRIMER_02_NAVIGATION (viewport manipulation, LOD control, budget management)
- To modify graphs: Read PRIMER_03A_EDITING (decomposition, content migration, link creation)
- For command syntax: See PRIMER_TOOLS (command reference catalog)
- To understand workflows: Read PRIMER_04_WORKFLOWS (Declare, Distill, Project step sequences)
