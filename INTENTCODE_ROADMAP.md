# IntentCode — Project Roadmap

**Version:** 0.1 — Living document  
**Goal:** Build the IntentCode toolchain end-to-end, validated by a blind roundtrip test on a real open-source Python library.

> **Terminology note (2026-07-15):** This roadmap predates the removal of the **display frontier** concept. A frontier was a lens with binary LOD; the current model uses the **lens** (variable-LOD view) for all agent I/O and visualization. Read historical "frontier" mentions below as "lens". Current field/CLI contracts live in `foundation_and_formalism/VOCABULARY_AND_FORMALISM.md` and the `ig-tool-*` skills.

---

## Validation criterion (definition of done)
<!-- Lines 12-18 -->

Take a popular open-source Python library. Use IntentCode to iteratively build its intent graph and a ProjectionIG for the target projection. Use IntentCode (with no knowledge of the original source) to regenerate the code from the graphs alone. An external AI judge evaluates whether the generated code is functionally equivalent.

**Critical testing principle:** Only **end-to-end / integration tests** are valid for evaluation. The intent graph captures *what* the software does, not *how* it is structured internally. Generated code may have completely different internal decomposition from the original — different functions, different classes, different module boundaries. Tests that reach into internal implementation (unit tests on private helpers, tests that import internal modules, tests that assert specific class hierarchies) are meaningless in this context. Only tests that exercise the **public API and observable behavior** — the contract the library exposes to its users — constitute a valid oracle.

---

## Phase 0 — Foundations & Formalism
<!-- Lines 21-23 -->

**Objective:** Establish the theoretical and formal basis for the IntentGraph model, grounded in existing work, with precise notation and provable invariants.

### WP-0.1 — State of the art & positioning
<!-- Lines 26-48 -->

- **0.1.1** Literature survey: intent-centric software representations
  - Program comprehension & concept assignment (Biggerstaff 1993, Rajlich & Wilde 2002)
  - Hierarchical task decomposition (HTN planning — Erol, Hendler & Nau 1994)
  - Goal-oriented requirements engineering (KAOS — van Lamsweerde 2001; i* — Yu 1997)
  - Feature models & software product lines (Kang et al. 1990, Czarnecki & Eisenecker 2000)
  - Multi-level modeling & refinement (Atkinson & Kühne 2003)
  - Knowledge graphs for software engineering (recent: CodeKG, etc.)
- **0.1.2** Literature survey: code generation from specifications
  - LLM-based code generation (Codex, AlphaCode, CodeGen, StarCoder lineage)
  - Specification-driven synthesis (TLA+, Alloy, refinement calculus)
  - Test-driven generation & search (genetic programming, program synthesis from I/O)
- **0.1.3** Literature survey: code → intent / reverse engineering
  - Program slicing & summarization (Weiser 1984, Haiduc et al. 2010)
  - LLM-based code understanding & documentation
  - Architecture recovery (reflexion models — Murphy, Notkin & Sullivan 1995)
- **0.1.4** Positioning paper — see [foundation_and_formalism/POSITIONING_SUMMARY.md](foundation_and_formalism/POSITIONING_SUMMARY.md)
  - How IntentGraph relates to and differs from each family
  - Key claims: mixed-detail coherence, explicit epistemic state, display frontier as working unit
  - Candidate venue or blog post for external version

**Milestone M0.1: COMPLETE.** Positioning paper complete. Clear differentiation from KAOS, i*, feature models, and LLM-prompting approaches.

### WP-0.2 — Formal model & notation
<!-- Lines 51-72 -->

- **0.2.1** Define notation
  - Sets, types, and symbols for `intentnode`, `treearc`, `intentlink`, `IntentGraph`, `display frontier`
  - Node field schema (intent, constraints, epistemic state, attention/effort, examples, etc.)
  - Intentlink typing vocabulary (data exchange, dependency, coordination, context transfer, etc.)
  - Epistemic state vocabulary (known, constrained, undecided, risky, deferred)
- **0.2.2** Formal invariants
  - **T1 — Tree property:** treearcs form a directed rooted tree (each node has ≤1 parent)
  - **T2 — Frontier validity:** a display frontier is an antichain in the treearc partial order (no ancestor/descendant pair)
  - **T3 — Intentlink well-formedness:** both endpoints exist in the graph; intentlinks are typed and directed
  - **T4 — Refinement coherence:** expanding a node into children preserves the meaning of the parent (semi-formal; criteria TBD)
  - **T5 — Frontier closure under operations:** expand(node) and collapse(siblings) on a valid frontier yield a valid frontier
- **0.2.3** Formal operations catalog
  - Node CRUD, treearc attach/detach, intentlink CRUD
  - Frontier: expand, collapse, add_branch, prune_branch, shift_level
  - For each operation: preconditions, postconditions, invariant preservation proof sketch
- **0.2.4** Write-up: IntentGraph white paper (internal)
  - Combines 0.2.1–0.2.3 into a self-contained document
  - Suitable as reference for all downstream implementation

**Milestone M0.2: COMPLETE.** White paper reviewed, notation stable, invariants enumerated and informally proved.

### WP-0.3 — ProjectionIG formalism
<!-- Lines 75-92 -->

- **0.3.1** Define scope of "projection-level intent" vs. "product intent"
  - Grounded in P4 (projection orthogonality): product intent and projection intent are independent concerns, each with its own IntentGraph
  - Projection-level concerns are broader than coding style: coding conventions, paradigm choice, documentation framing, test strategy, visual layout, performance tradeoffs — anything that shapes how a specific projection is rendered
  - How ProjectionIG directives relate to product intentnodes (override, default, scope rules)
- **0.3.2** Representation: ProjectionIG schema
  - Same formalism as the product IntentGraph (intentnodes, treearcs, intentlinks, frontiers, epistemic state)
  - `PIG-<TAG>.` namespace convention for node UIDs — no collision with product nodes
  - One ProjectionIG per projection instance, not per type
- **0.3.3** Integration semantics
  - Generator receives a product frontier + ProjectionIG frontier; Navigator handles ProjectionIG frontier navigation (expand, collapse, prune) on behalf of the Generator
  - Conflict resolution: product intentnode-level tradeoff annotations override ProjectionIG defaults
  - Inter-graph intentlinks (product ↔ ProjectionIG): deferred to post-Phase 4, but namespace convention prepares for them

**Milestone M0.3:** ProjectionIG formalism decided. Namespace convention documented. Integration rules documented.

---

## Phase 1 — Core Library & Minimal GUI
<!-- Lines 95-97 -->

**Objective:** Implement the IntentGraph data model and frontier operations as a standalone Python library with enforced invariants, and provide a minimal GUI so humans can actually look at and navigate the graph. The GUI is not optional: the IntentGraph is too complex to reason about from text alone, and every downstream phase (agent review, elicitation, validation) requires a human who can see the graph.

### WP-1.1 — Data model implementation
<!-- Lines 100-119 -->

- **1.1.1** `intentnode` dataclass / model
  - Fields: id, intent, constraints, epistemic_state, attention, effort, examples, notes, metadata
  - Validation on construction and mutation
- **1.1.2** `treearc` implementation
  - Parent→child edge with tree invariant enforcement
  - Adjacency structure (children lookup, parent lookup, ancestors, descendants)
- **1.1.3** `intentlink` implementation
  - Typed, directed edge between intentnodes
  - Link type vocabulary (enum or extensible registry)
- **1.1.4** `IntentGraph` container
  - Owns all nodes, treearcs, intentlinks
  - Enforces T1, T3 on every mutation (raise on violation)
  - Serialization: to/from JSON, to/from YAML
- **1.1.5** Unit tests for invariant enforcement
  - Every invariant has tests for valid and invalid operations
  - Property-based tests (hypothesis) for tree and frontier invariants

**Milestone M1.1: COMPLETE.** Core data model passes all invariant tests. Serialization round-trips cleanly.

### WP-1.2 — Frontier operations
<!-- Lines 122-142 -->

- **1.2.1** `DisplayFrontier` class
  - Construction from root + depth, or explicit node set
  - Validation: T2 enforcement (antichain check)
- **1.2.2** Operations: expand, collapse
  - expand(node): replace node with its treearc children in the frontier
  - collapse(siblings): replace sibling set with their common parent
  - Both return new valid frontier; raise if preconditions fail
- **1.2.3** Operations: add_branch, prune_branch, shift_level
  - add_branch: include a subtree root in the frontier (check no overlap)
  - prune_branch: remove a subtree from the frontier
  - shift_level: move the entire frontier one level deeper or shallower
- **1.2.4** Intentlink projection onto frontier
  - Given a frontier, compute which intentlinks are visible (both endpoints in frontier or aggregated to frontier-level ancestors)
  - Aggregation logic: when a link's endpoint is below the frontier, project it up to the frontier node
- **1.2.5** Unit tests for frontier operations
  - Each operation preserves T2, T5
  - Intentlink projection is consistent with frontier changes

**Milestone M1.2: COMPLETE.** Frontier operations complete, tested, documented. Library is usable programmatically.

### WP-1.3 — Textual serialization for agents
<!-- Lines 145-160 -->

- **1.3.1** Design the frontier text format
  - Requirements: human-readable, round-trippable, parseable by LLMs
  - Candidate: indented YAML-like with node fields + intentlink section
  - Must include: node id, intent, epistemic state, constraints, intentlinks with types
  - Must exclude (or summarize): collapsed subtree details
- **1.3.2** Implement serializer: frontier → text
- **1.3.3** Implement parser: text → frontier edits (for agent output)
  - Structured diff: agent proposes additions, modifications, deletions
  - Validate proposed edits against invariants before applying
- **1.3.4** Design the ProjectionIG text format
  - Same agent text format as the product IntentGraph; ProjectionIG frontier serializes via `frontier_to_text()`
- **1.3.5** Tests: round-trip, edge cases, malformed input handling

**Milestone M1.3: COMPLETE.** Agents can read and write IntentGraph frontiers as text. ProjectionIG serializable via the same format.

### WP-1.4 — Minimal GUI (required for human-in-the-loop)
<!-- Lines 163-200 -->

The intent graph is a deeply nested, multi-relational structure. Without visual support, a human cannot effectively review agent output, judge graph quality, or participate in elicitation. This is not a polish step — it is infrastructure.

- **1.4.1** Technology decision
  - Key constraint: must render a tree with cross-links (intentlinks) on a frontier
  - Candidates: lightweight web app (React/Svelte), Obsidian plugin, VS Code extension, or Python-native (e.g. Textual TUI as minimum viable)
  - Decision criteria: speed to build, ability to display graph + node detail, eventual agent integration
- **1.4.2** Tree display with expand/collapse
  - Render the treearc hierarchy rooted at a chosen node
  - Click to expand (show children) or collapse (show parent)
  - Visual depth indication (indentation, nesting, or spatial layout)
- **1.4.3** Frontier display
  - Highlight the current display frontier within the tree
  - Show which nodes are "active" vs. collapsed
  - Frontier validity indicator (warn if the frontier is broken)
- **1.4.4** Intentlink rendering on frontier
  - Draw edges between frontier nodes that are connected by intentlinks
  - Show link type (label or color)
  - Handle projected/aggregated links (when an endpoint is below the frontier)
- **1.4.5** Node detail panel
  - Select a node → show all fields (intent, constraints, epistemic state, etc.)
  - Read-only is acceptable for v1; inline editing is a bonus
  - Epistemic state visual encoding (color, icon, or badge on the node)
- **1.4.6** Load/save
  - Load an IntentGraph from JSON/YAML (the core library's serialization format)
  - Save edits back (if editing is supported)
- **1.4.7** Smoke test on a hand-crafted graph
  - Build a small example IntentGraph (10–20 nodes) by hand
  - Verify: tree renders, frontier operations work visually, intentlinks display, node detail is readable

**Milestone M1.4: COMPLETE.** A human can load an IntentGraph, see its structure, navigate via expand/collapse, inspect node fields, and see intentlinks on a frontier. Implemented as Obsidian vault sync (`intentgraph.obsidian` module) with:
- Bidirectional export/import/diff
- Recursive frontier canvas (ancestor groups + frontier file nodes + intentlink routing)
- Pinned layout: user-moved positions are detected, stored sparsely on `DisplayFrontier.layout`, and survive frontier operations and serialization round-trips
- 208 tests total (60 obsidian-specific). **Phase 1 complete.**

---

## Phase 2 — Agents as Configuration (v1)
<!-- Lines 203-207 -->

**Objective:** Build the core agents sufficient for the validation scenario. In this phase, agents are **configurations, not trained models**: each agent is a foundation model (Claude Opus/Sonnet) with a tailored system prompt, structured I/O format, and few-shot examples. No fine-tuning. The value is in the prompt engineering, the I/O contract with the core library, and the orchestration between agents. This approach lets us iterate fast on what each agent should do before committing to training infrastructure.

**Implication:** Agent quality depends on prompt quality and the foundation model's capabilities. This is acceptable for v1 — the goal is to validate the IntentGraph workflow end-to-end, not to achieve peak agent performance. Training custom models is Phase 5.

### WP-2.0 — Agent infrastructure (agents as configuration)
<!-- Lines 210-236 -->

- **2.0.1** Agent ↔ core library interface
  - Agent receives: serialized frontier (text) + ProjectionIG frontier (text) + conversation context
  - Agent returns: structured edits (node create/update/delete, link create/delete) or code files
  - Edits are validated by the core library before applying
  - **The interface is model-agnostic**: swap the underlying model without changing the orchestration
  - Added `history` and `impl_pointers` to the agent text format (serialization + parsing)
  - Added `agent_role` parameter to `apply_edits()` for automatic provenance injection
  - Added `graph_to_tree_overview()` and `graph_to_edge_overview()` — lightweight full-graph serialization for Navigator
  - Added `frontier_text_size()` for context budget estimation
  - Fixed NodeCreate fields deduplication bug in `text_to_edits()`
- **2.0.2** Agent configuration framework
  - Each agent = modular markdown guidance in `.claude/agents/`: core (`ig-{role}-agent.md`) + mode modules (`ig-{role}-mode-*.md` / `ig-{role}-review-*.md`) + on-demand examples (`ig-{role}-examples.md`)
  - 6 agent files: Extractor, Critic, Elicitor, Generator, Verifier, Navigator
  - Context assembly module (`ig_agents.context`) with budget checking and IV-context modes (full/lean)
  - ProjectionIG: single markdown file per project for v1 (kickstart template; structured ProjectionIG deferred)
- **2.0.3** Conversation/session management
  - `Session` dataclass with turn tracking (proposed/accepted/rejected edits)
  - `SessionStore` for JSON file persistence (save/load/list/delete)
  - Multi-turn support for Elicitor and iterative Extractor loops
- **2.0.4** Agent evaluation harness
  - JSONL I/O logging per agent role (`AgentLogger`) with automatic timing via context manager
  - Structured evaluation for Extractor (parse success, invariant compliance, epistemic coverage) and Critic (issue structure, severity, node references)
  - Stats aggregation (count, success rate, avg duration, total edits)

**Milestone M2.0: COMPLETE.** Agent harness operational. 6 agent configurations version-controlled. Context assembly with budget management. Session persistence. I/O logging for future training data. 266 tests total (232 core + 34 agent infra).

### WP-2.1 — Extractor: Code → Graph
<!-- Lines 239-260 -->

- **2.1.1** Input pipeline
  - Code ingestion: parse Python source into modules, classes, functions
  - **E2E test extraction**: identify tests that exercise the public API / top-level behavior only. Discard unit tests on internal helpers, private methods, or implementation-specific structure. These E2E tests are the oracle — they define *what the code does* independent of *how it is structured*.
  - API surface extraction: public interfaces, type hints, docstrings
- **2.1.2** Initial graph generation (via prompted model)
  - System prompt: IntentGraph vocabulary + serialization format + anti-patterns (no HOW, only WHY)
  - Top-down pass: module structure → high-level intentnodes
  - Bottom-up pass: function/class-level intent extraction
  - Intentlink inference: call graphs, data flow, imports → typed intentlinks
- **2.1.3** Epistemic state annotation
  - Mark unclear intent as `undecided` or `risky`
  - Flag implicit behavior, side effects, magic values
- **2.1.4** Iterative refinement loop (Extractor → Critic → Extractor)
  - Critic reviews the graph (see WP-2.4)
  - Extractor revises based on Critic feedback
  - Loop until Critic issues stabilize or max rounds reached
  - Human reviews final graph via GUI
- **2.1.5** Validation: feed graph to Generator (blind), run E2E tests against generated code

**Milestone M2.1:** Extractor can ingest a Python module and produce a reasonable initial intent graph with epistemic annotations.

### WP-2.2 — Elicitor: Intent Elicitation & Refinement
<!-- Lines 263-280 -->

- **2.2.1** Conversation design
  - Structured interview protocol: purpose → constraints → edge cases → epistemic state
  - Adaptive: skips fields already filled, probes weak spots
- **2.2.2** Graph edit proposals
  - Proposes: new child nodes (refinement), updated fields, new intentlinks, epistemic state changes
  - All proposals go through core library validation
- **2.2.3** Modes of operation
  - **Refinement mode:** expand a node downward
  - **Review mode:** challenge and probe existing nodes
  - **Gap detection mode:** find missing intentlinks, uncovered behavior, vague intent
- **2.2.4** Integration with Extractor output
  - Takes Extractor's initial graph as starting point
  - Focuses on areas marked `undecided` or `risky`, or flagged by Critic
- **2.2.5** Tests: scripted dialogues on sample graphs, measure graph quality improvement

**Milestone M2.2:** Elicitor can conduct a multi-turn refinement session and produce meaningful graph improvements.

### WP-2.3 — Generator: Graph → Code
<!-- Lines 283-302 -->

- **2.3.1** Input assembly
  - Product frontier text + ProjectionIG frontier text + language target (Python for v1)
  - Optional: existing partial codebase for incremental generation
- **2.3.2** Code generation strategy
  - Top-down: module/package structure from high-level product frontier
  - Per-node: function/class implementation from leaf-level intentnodes
  - Intentlink-aware: imports, interfaces, data contracts derived from intentlinks
  - **Implementation structure is Generator's choice**: the product graph prescribes intent, not how to decompose into functions/classes
- **2.3.3** ProjectionIG integration
  - Generator holds a ProjectionIG frontier slice; navigates it dynamically via Navigator delegation (expand, collapse, prune primitives → updated frontier delta)
  - ProjectionIG directives applied as generation constraints (paradigm, naming, error handling, documentation patterns, etc.)
  - Product intentnode-level tradeoff annotations override ProjectionIG defaults
- **2.3.4** Self-validation
  - If E2E tests are available, run them against generated code
  - Report pass/fail at the public API level (not per internal function)
- **2.3.5** Tests: generate code from hand-crafted intent graphs + ProjectionIG, verify against E2E test suites

**Milestone M2.3:** Generator can produce runnable Python code from a product IntentGraph frontier + ProjectionIG frontier.

### WP-2.4 — Critic: Graph Quality Review
<!-- Lines 305-318 -->

- **2.4.1** Critic configuration
  - System prompt encoding the evaluation criteria: WHY vs HOW, constraint completeness, intentlink coverage, epistemic accuracy, regenerability
  - Structured output format: issue type, node id, severity, description
- **2.4.2** Integration into Extractor loop (WP-2.1.4)
  - Critic receives: graph + original code/tests
  - Returns: structured issue list
  - Extractor revises graph based on issues
- **2.4.3** Standalone review mode
  - Can be invoked independently on any graph (not just Extractor output)
  - Useful during Elicitor sessions and before Generator runs

**Milestone M2.4:** Critic can identify meaningful quality issues in an intent graph. Full core agent suite operational.

### WP-2.5 — Verifier: Intent ↔ Test Verification Layer
<!-- Lines 321-342 -->

The Verifier owns the contract between intent and code. Its primary role is to design and maintain end-to-end tests derived from the intent graph, ensuring generated code is faithful to intent. Its secondary role handles legacy codebases: most real codebases have far more unit tests than E2E tests, and these implementation-coupled tests encode behavioral knowledge that shouldn't be discarded. The Verifier extracts that knowledge and creates intent-aligned replacements.

- **2.5.1** Verifier configuration
  - System prompt encoding the translation rules: test → functional requirement, strip implementation vocabulary, express as observable behavior
  - Structured output: requirement text + target intentnode + attachment type (constraint, example, edge case, child node)
  - Few-shot examples of good translations and correctly discarded structural tests
- **2.5.2** Test classification
  - Classify each test as: E2E (keep as runnable test), behavioral-but-coupled (translate to requirement), or purely structural (discard)
  - Heuristic indicators: imports from internal modules → coupled; asserts on mock call counts → structural; asserts on output values → behavioral
- **2.5.3** Requirement placement
  - For each translated requirement, recommend which intentnode it attaches to
  - When a test reveals behavior not yet in the graph, flag it as a gap for Extractor/Elicitor
- **2.5.4** Optional: E2E test sketch generation
  - From the translated requirement, propose an E2E test that verifies the same behavior at the public API level
  - These sketches can augment the E2E test suite for libraries with insufficient top-level tests
- **2.5.5** Integration into the graph-building workflow
  - Run after Extractor (WP-2.1) produces the initial graph
  - Feed into Critic (WP-2.4) and Elicitor (WP-2.2) sessions — they now have richer requirements to work with

**Milestone M2.5:** Verifier can (a) design end-to-end tests from an intent graph that validate generated code, and (b) process a library's legacy test suite to create intent-aligned replacements.

### WP-2.6 — Designer: Intent → Code Architecture
<!-- Lines 345-364 -->

The Designer is the grounding mechanism that ensures every code generation is explicitly anchored to intent through traceable architecture decisions. It always runs before the Generator.

- **2.6.1** Designer agent configuration
  - Agent markdown (`.claude/agents/ig-designer-agent.md`) with: primer-grounded INPUT/INSTRUCTIONS/OUTPUT, 5-phase algorithm (§2.2), Mission vs. precision (§2.0), critical rules; single core file. Same pattern for Generator and Verifier (`.claude/agents/ig-generator-agent.md`, `ig-verifier-agent.md`).
  - Two output artifacts: ProjectionIG architectural nodes (`PIG-ARCH.*` UID prefix) + Target CodeMap YAML
  - Integration with Critic (architecture-specific issue types: `structural_cohesion`, `interface_completeness`, `codemap_divergence`)
- **2.6.2** Target CodeMap format
  - Uses CodeMap's YAML tree format (`TREE_FORMAT.md` spec) with `[PLANNED]` markers instead of line numbers
  - Intentnode UID annotations for traceability
  - Planned call structure via `~calls` edges
- **2.6.3** Generator integration
  - Generator Phase 1 (Architecture) delegated to Designer — Generator follows the structural plan, does not redesign
  - Generator refuses to proceed without Designer output (grounding discipline)
- **2.6.4** Workflow integration
  - Designer step inserted between intent-approval (Critic re-review passes) and Generator invocation
  - Architecture review loop: Designer → Critic → Elicitor (if issues) → Designer (revise)

**Milestone M2.6:** Designer produces reviewable code architecture from an IntentGraph. Generator follows the structural plan.

### WP-2.7 — CodeMap Integration
<!-- Lines 367-387 -->

Integrate the CodeMap (`ai_tooling/documentation_tools/codemap`) project into the agent ecosystem, providing structural codebase context to Extractor, Designer, and Generator.

- **2.7.1** CodeMap bridge module (`ig_agents/codemap_bridge.py`)
  - Thin wrapper over CodeMap's Python API: `build_codemap()`, `overview_for_context()`, `context_for_focus()`, `neighbors_for_links()`, `validate_target_codemap()`
  - Optional dependency with graceful degradation when `codemap` package is not installed
- **2.7.2** Extractor CodeMap integration
  - CodeMap `overview()` for structural orientation before reading source
  - CodeMap edges (`~calls`, `~inherits`) as intentlink candidates
  - CodeMap `context()` for IV-context views when deepening subtrees
- **2.7.3** Designer CodeMap integration
  - Existing codebase structure as input for architecture decisions
  - Designer aligns with or explicitly diverges from existing module boundaries
- **2.7.4** Context assembly extensions
  - `assemble_designer_context()` function in `ig_agents/context.py`
  - Extended `assemble_agent_context()` with `codemap_project_path` and `target_codemap_text` parameters
- **2.7.5** Distill workflow CodeMap bootstrap (`DISTILL.MAP`)
  - `CodeMap.build()` runs at workflow start, structural overview passed as context throughout

**Milestone M2.7:** CodeMap provides structural context to agents. Phase 2 complete.

### WP-2.8 — Agent Roundtrip Test (experimental validation)
<!-- Lines 390-403 -->

End-to-end test of the three workflows (Distill → Declare → Project) on a Python codebase before tackling the full Phase 4 validation. Uses a small, bounded repo (a SQL function sync validator — see `src/examples/` for the same example as a demonstration target for IntentGraph) as the test subject.

- **2.8.1** Distill test — reverse-extract IntentGraph + ProjectionIG from existing code + docs
- **2.8.2** Distill trace analysis — evaluate orchestration quality, agent handoffs, context sufficiency
- **2.8.3** Declare test — review/refine the Distill-produced IG using the Declare workflow
- **2.8.4** Declare trace analysis — evaluate cross-workflow continuity, Critic delta, dialogue efficiency
- **2.8.5** Project test — generate code from the reviewed IG + ProjectionIG
- **2.8.6** Project trace analysis — evaluate design coherence, projection gap handling, verification quality

**Milestone M2.8:** All three workflows exercised end-to-end on a real codebase. Trace analyses identify workflow gaps before Phase 4.

---

## Phase 3 — GUI v2 (Agent Integration & Polish)
<!-- Lines 406-408 -->

**Objective:** Extend the minimal GUI from Phase 1 with agent interaction panels and richer editing, making the full human-in-the-loop workflow smooth. Helpful but not strictly blocking for Phase 4 (agents can be invoked from CLI/notebook).

### WP-3.1 — Enhanced editing
<!-- Lines 411-416 -->

- **3.1.1** Inline field editing on nodes (not just read-only)
- **3.1.2** Create/delete nodes and treearcs from the GUI
- **3.1.3** Create/delete/edit intentlinks visually (drag between nodes)
- **3.1.4** Undo/redo support

### WP-3.2 — Agent integration panels
<!-- Lines 419-425 -->

- **3.2.1** Chat panel: invoke Elicitor from the GUI, see proposals, accept/reject edits
- **3.2.2** Code panel: invoke Generator, view generated code alongside the frontier
- **3.2.3** Import panel: invoke Extractor on a codebase, review initial graph before committing
- **3.2.4** Critic panel: invoke Critic, see issues overlaid on graph nodes
- **3.2.5** Diff view: show proposed graph edits as a visual diff before applying

### WP-3.3 — Navigation & usability
<!-- Lines 428-437 -->

- **3.3.1** Search/filter nodes by field content or epistemic state
- **3.3.2** Minimap or breadcrumb for large graphs
- **3.3.3** Multiple frontier presets (save/load named frontiers)
- **3.3.4** ProjectionIG editor (view and navigate ProjectionIG frontier)

**Milestone M3:** GUI supports full interactive workflow: edit graph, invoke agents, review proposals, view generated code. Accelerates Phase 4 but not strictly required (CLI/notebook fallback exists).

---

## Phase 4 — Integration & Validation
<!-- Lines 440-442 -->

**Objective:** Execute the validation scenario end-to-end and assess results.

### WP-4.1 — Target library selection
<!-- Lines 445-467 -->

- **4.1.1** Selection criteria
  - **Strong end-to-end / integration test suite** (not just unit tests on internals). The test suite must exercise the public API and observable behavior without depending on internal implementation structure.
  - Moderate size (1k–10k LOC, 50–200 E2E tests)
  - Clear domain (not too meta / framework-heavy)
  - Python, popular, stable API
- **4.1.2** Candidates (evaluate and pick one)
  - `click` — CLI framework, ~5k LOC, well-tested, clear public API. CLI invocation tests are naturally E2E.
  - `httpx` — HTTP client, moderate complexity. Client-level tests (make a request, check response) are E2E.
  - `pydantic-core` subset — type validation, well-defined I/O behavior. Validation tests are naturally behavioral.
  - `attrs` — class definition, small. Tests on decorated classes are behavioral.
  - **Disqualifying pattern:** libraries whose test suites are mostly unit tests on internal helpers (e.g., `test_internal_parser`, `test_private_cache_eviction`). These tests would break on any reimplementation regardless of correctness.
- **4.1.3** E2E test extraction & preparation
  - Audit the target library's test suite: classify each test as E2E (public API only) vs. internal (imports private modules, tests internal structure)
  - Keep E2E tests as the runnable oracle
  - Run **Verifier** on internal/unit tests: extract behavioral requirements and fold them into the intent graph as constraints. Optionally generate E2E test sketches to augment the runnable suite.
  - Freeze the final E2E test suite (original + augmented) as the oracle
  - Set up sandboxed environment for blind generation (no source access)
- **4.1.4** Define functional equivalence criteria
  - Primary: E2E test pass rate
  - Secondary: API shape compatibility (same public functions/classes with compatible signatures)
  - Tertiary: behavioral parity on edge cases not covered by tests (AI judge)

### WP-4.2 — Graph building (forward pass)
<!-- Lines 470-477 -->

- **4.2.1** Run Extractor on the target library → initial intent graph
- **4.2.2** Run Verifier on the library's unit/internal tests → enrich graph with behavioral requirements
- **4.2.3** Run Critic → identify issues
- **4.2.4** Iterative refinement with Elicitor + human review
- **4.2.5** Build ProjectionIG (from code conventions observed + human preferences)
- **4.2.6** Quality checkpoint: is the intent graph self-consistent? Are epistemic states resolved or explicitly deferred?

### WP-4.3 — Blind code generation
<!-- Lines 480-485 -->

- **4.3.1** Clean-room setup: fresh Generator instance with no access to original source
- **4.3.2** Input: product IntentGraph + ProjectionIG only
- **4.3.3** Iterative generation: Generator produces code, runs E2E tests (if available), refines
- **4.3.4** Output: generated codebase

### WP-4.4 — Evaluation
<!-- Lines 488-504 -->

- **4.4.1** Run frozen E2E test suite against generated code
- **4.4.2** AI judge assessment
  - Functional equivalence (does it do the same thing at the public API level?)
  - API compatibility (can you swap it in as a drop-in replacement?)
  - Behavioral edge cases (error handling, defaults, side effects not covered by tests)
- **4.4.3** Gap analysis
  - What did the intent graph miss?
  - What did the ProjectionIG fail to convey?
  - Where did Generator make wrong choices?
  - **Which E2E test failures trace back to missing intent vs. wrong generation vs. ambiguous graph?**
- **4.4.4** Retrospective: update the formal model, agent configurations, and roadmap

**Milestone M4:** Validation scenario executed. Results documented. Gap analysis feeds back into all prior phases.

---

## Phase 5 — Custom Agent Training (future)
<!-- Lines 507-514 -->

**Objective:** Move from agents-as-configuration (prompted foundation models) to fine-tuned, purpose-built models. This phase begins only after the IntentCode workflow is validated end-to-end (Phase 4) and enough data has been collected through real usage.

**Prerequisites:**
- Phase 4 complete (validated workflow, known failure modes, understood agent roles)
- Sufficient logged data from Phase 2–4 usage (target: ~30k validated (code, graph) pairs from Extractor/Generator sessions, ~2k human preference pairs from Elicitor sessions)
- E2E test infrastructure for reward computation (sandboxed execution at scale)

### WP-5.1 — Training data curation
<!-- Lines 517-535 -->

- **5.1.1** Harvest logged agent I/O from Phase 2–4
  - Every Extractor session → (code + E2E tests, graph) pair
  - Every Generator session → (graph + style, code) pair
  - Every Elicitor session → (frontier, proposed edit, accept/reject) triple
  - Every Critic session → (graph, issue list) pair
- **5.1.2** Quality filtering
  - Keep only (code, graph) pairs where Generator's blind output passes E2E tests (the roundtrip gate)
  - Keep only Elicitor proposals that were accepted by human
  - Discard pairs involving graphs that violate invariants
- **5.1.3** Augmentation via iterative synthetic generation
  - For repos not yet covered: run the Extractor → Critic → Extractor → Generator → E2E test pipeline (the training data generation pipeline from the agent catalog)
  - Only pairs that pass the E2E gate enter the dataset
  - **Critical:** use only E2E / integration tests as oracle. Discard repos where no implementation-agnostic tests can be identified.
- **5.1.4** Cross-language augmentation (optional, high value)
  - One graph → generate in Python, TypeScript, Rust
  - Each language version must pass equivalent E2E tests
  - Forces language-agnostic intent in graphs

### WP-5.2 — Supervised fine-tuning (SFT)
<!-- Lines 538-544 -->

- **5.2.1** Base model selection (e.g., Llama 3.1 8B Instruct, Mistral 7B, or current best open-weights code model)
- **5.2.2** Train Extractor adapter (LoRA): code + E2E tests → graph
- **5.2.3** Train Generator adapter (LoRA): graph + style → code
- **5.2.4** Evaluate on held-out set: E2E test pass rate, invariant compliance
- **5.2.5** Critic and Elicitor stay as prompted large models for now (they require stronger reasoning; fine-tune later if data permits)

### WP-5.3 — Joint RL (cycle-consistency training)
<!-- Lines 547-556 -->

- **5.3.1** Reward function: E2E test pass rate (primary) + invariant compliance + roundtrip stability
  - **No unit-test reward.** Only E2E tests count. This prevents the agents from learning to reproduce implementation structure.
- **5.3.2** Training method: GRPO or rejection sampling
  - Generate N candidates, score by reward, fine-tune on top-K
- **5.3.3** Alternating optimization: freeze Extractor / train Generator, then swap
- **5.3.4** Curriculum: single functions → classes → modules → small packages
  - **At every level, tests must be E2E relative to that level.** For a class, tests must exercise the class's public interface, not its private methods.
- **5.3.5** Cross-language joint training (optional): one graph → code in N languages, all must pass E2E tests

### WP-5.4 — Preference learning for Elicitor
<!-- Lines 559-563 -->

- **5.4.1** DPO training on accumulated (frontier, chosen edit, rejected edit) triples
- **5.4.2** Indirect reward signal: does Generator's E2E test pass rate improve after an Elicitor refinement session?
- **5.4.3** Iterate: deploy fine-tuned Elicitor, collect more preferences, retrain

### WP-5.5 — Evaluation & iteration
<!-- Lines 566-574 -->

- **5.5.1** Re-run Phase 4 validation scenario with fine-tuned agents
- **5.5.2** Compare: prompted agents vs. fine-tuned agents on same benchmark
- **5.5.3** Identify remaining gaps → feed back into training data and reward design

**Milestone M5:** Fine-tuned agents outperform prompted agents on the validation benchmark. Training pipeline is repeatable for new data.

---

## Dependencies & sequencing
<!-- Lines 577-594 -->

```
Phase 0 ──► Phase 1 (core + minimal GUI) ──► Phase 2 (agents as config) ──► Phase 4 (validation)
                                                      │                            │
                                                      ▼                            ▼
                                                 Phase 3 (GUI v2)            Phase 5 (custom training)
                                                 (parallel)                  (after validation)
```

- **Phase 0** is prerequisite for Phase 1 (notation and invariants drive the implementation) — **COMPLETE**
- **Phase 1** includes the minimal GUI — a human must be able to see the graph before agents can be evaluated — **COMPLETE**
- **Phase 2** depends on Phase 1 (agents need the core library, serialization, and a human who can review output via GUI). **Agents are configurations of foundation models, not trained models.** — **WP-2.0 COMPLETE, WP-2.6–2.7 COMPLETE (Designer + CodeMap), WP-2.1–2.5 NEXT**
- **Phase 3** (GUI v2) can start after Phase 2 begins and run in parallel; helpful but not blocking for Phase 4
- **Phase 4** requires Phase 2; benefits from Phase 3 but can fall back to CLI/notebook + minimal GUI. **All evaluation uses E2E tests only.**
- **Phase 5** requires Phase 4 (validated workflow + collected data). Uses logged data from Phases 2–4 as training corpus. **Only E2E tests serve as reward signal — never unit tests on internals.**

---

## Risk register
<!-- Lines 597-611 -->

| Risk | Impact | Mitigation |
|---|---|---|
| Intent graph too verbose for LLM context windows | Agents can't process full frontiers | Context budget management (WP-2.0.2); aggressive frontier scoping; summarization layers |
| Code → graph loses critical implicit behavior | Generated code misses edge cases | Epistemic state annotation (WP-2.1.3); E2E tests as behavioral oracle (WP-2.1.1) |
| ProjectionIG underspecified | Generated code is correct but ugly/unidiomatic | Iterate ProjectionIG post-generation; treat as tunable, not blocking |
| Formal model too rigid for real codebases | Can't represent messy real-world intent | Allow epistemic fuzziness by design; revisit invariants if they block real use |
| Target library too complex for v1 | Validation fails due to scope, not method | Start with a small, well-scoped subset; expand progressively |
| Agent coordination overhead | Too many round-trips, slow iteration | Start with human-in-the-loop orchestration; automate loops later |
| Target library lacks E2E tests | No valid oracle for evaluation | Audit test suite before committing (WP-4.1.3); use Verifier to extract behavioral requirements and generate E2E test sketches (WP-2.5); augment from docs if needed |
| Prompted agents hit quality ceiling | Configurations can only go so far without training | Accept for Phase 2–4; this is exactly what Phase 5 addresses. Log everything for future training. |
| E2E test pass ≠ full correctness | Tests may not cover all behavior | Supplement with AI judge assessment (WP-4.4.2); treat test pass rate as necessary but not sufficient |

---

## Open questions (to resolve during Phase 0)
<!-- Lines 614-620 -->

1. **Refinement coherence (T4):** Can this be formalized enough to be machine-checkable, or does it stay semi-formal / human-judged?
2. **Intentlink aggregation semantics:** When projecting links to a coarser frontier, what are the exact rules? Union? Weighted merge? Type-dependent?
3. **ProjectionIG granularity:** How deep should a ProjectionIG go for v1? A shallow kickstart template with `undecided` decision points, refined via the Elicitor/Critic loop, is the current direction.
4. **E2E test availability:** How many real-world Python libraries have a test suite that is mostly E2E / behavioral? If few, Verifier (WP-2.5) can augment by translating unit tests into requirements and proposing E2E test sketches — but how reliable are those generated E2E tests? What heuristics distinguish E2E from internal tests (e.g., imports only from public API, no access to `_private` attributes)?
5. **E2E test augmentation quality:** Verifier can propose E2E test sketches from unit tests, but these may be incomplete or wrong. How do we validate generated E2E tests? Manual review? Run them against the original code first?
6. **Agent configuration versioning:** As agent prompts evolve rapidly in Phase 2, what's the right way to version and A/B test configurations? Track prompt versions alongside logged I/O for reproducibility.
