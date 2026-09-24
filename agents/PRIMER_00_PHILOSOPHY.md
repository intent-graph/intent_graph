# PRIMER_00_PHILOSOPHY

**Purpose:** Establish the mental model and core principles. Read this before any IntentGraph task.

**Audience:** All agents, all workflows.

---

## What Is an IntentGraph?

An **IntentGraph** is a structured representation of intent — what a system does and why — as a refinable hierarchy of nodes (intentnodes) connected by refinement edges (treearcs) and semantic relationships (intentlinks). It is the canonical model; code, documentation, tests, and specs are projections derived from it.

The graph supports mixed levels of detail: different parts can remain coarse or be refined to arbitrary depth. You work on a local neighborhood (a Lens) at chosen detail levels without holding the whole system in context.

---

## The Problem

Code is the source of truth in conventional software. This creates structural failures:

1. **Intent is implicit.** Purpose, constraints, trade-offs, rejected alternatives live in meetings, tickets, comments, docs, and author memory. This means understanding, maintaining and adding feature to code base is risky and hard.

2. **Code is flat.** No native hierarchy of purpose. No zoom levels. Understanding requires reading everything or nothing. Of course good code is structured, but there are not hard conventions.

3. **Uncertainty is invisible.** Code is binary (it does X or doesn't). No representation for "this part is uncertain," "this is a workaround," "we don't know the right approach yet."

4. **It's hard to know what's relevant for one feature.** No bounded-context reasoning. Changing one function can break behavior anywhere, dependencies often invisible. For large codebase, there is no easy way to keep track of teh whole, but only get details for a part.

IntentGraph inverts this: **intent is the source of truth; code, docs, tests are projections derived from intent.**

---

## The Four Axioms

These are absolute. Violating them breaks the model.

**P1 — Intent is the source of truth.**

The IntentGraph is canonical. Code, documentation, specs, visual views are projections — derived artifacts generated from the graph. Different audiences get different projections of the same truth. The graph is the invariant; implementations are consequences.

**P2 — Zooming adds information, never changes meaning.**

Refining a node into children increases precision but preserves the intended role. A parent and its children represent the same intent surface at different resolution. This is meaning-stability — the property that makes mixed-detail coherence possible.

**P3 — Incompleteness is first-class.**

The model tolerates areas that remain coarse indefinitely, unknowns that are explicitly recorded, and uncertainty that is modeled rather than hidden. "Know what you don't know" is structural, not aspirational.

**P4 — Projection is orthogonal.**

What a system does (product intent) and how that intent is materialized into artifacts (projection intent) are independent concerns. Each gets its own IntentGraph. When mixed, implementation details contaminate the product graph, diluting the intent it exists to capture.

**P5 — Information is normalized and compressed.**

At each level of abstraction, intent is stated once without duplication. The same intent appears at multiple levels (parent and children) but with different precision — parent is lossy compression, children add detail. No overlap at the same level: children partition the parent's intent orthogonally into distinct, non-overlapping sub-capabilities. This keeps each node bounded in size: you add precision by going down (expand), not by making nodes longer. Cross-cutting concerns are captured once (at the appropriate level) and linked via intentlinks, not repeated across peers.

---

## Core Vocabulary

**intentnode** — A unit of intent at some level of detail. Describes what a part of the system is meant to do and why, not how it is implemented. Fields: uid, name, intent, epistemic_state, constraints, design_notes, examples, impl_pointers, history. UID format follows conventions enforced by validation: the **root** UID is exactly `ROOT` — required, not a convention; a parentless node with any other UID is rejected (`--root-name` sets only the display name, the UID stays `ROOT`); L1 nodes (children of root) are a single segment — an uppercase keyword matching `^[A-Z][A-Z0-9_]*$` (preferred: DISCOVER, ERRORS, API, LEXER_TOKENS — underscores allowed inside the keyword, no leading underscore) or a number (allowed: 1, 2); L2 nodes are either `{parent}.{number}` for minor nodes (DISCOVER.1) or `{parent}.{KEYWORD}` for named sub-capabilities (ERRORS.HANDLER, API.CLIENT, LEXER.PARSER_INTERFACE); L3+ nodes always use parent prefix + number (ERRORS.HANDLER.1, DISCOVER.DB.2) — a keyword suffix is an L2-only privilege (parent must be L1), so `ERRORS.HANDLER.1` is valid but `ERRORS.HANDLER.PARSE` is not.

**treearc** — A directed refinement edge `parent → child`. All treearcs form a directed rooted tree. Each node has at most one parent. Treearcs carry no payload — pure refinement structure.

**intentlink** — A directed, valued relation between two intentnodes. Carries an intent sentence describing what must be true between nodes (data exchange, dependency, coordination). Orthogonal to the tree — can connect any two nodes at any depth. When precision is needed: **intra** = same graph; **inter** = between graphs (endpoints are qualified UID `graph_id:node_uid`).

**Lens** — A working view of the full graph with variable Level of Detail (LOD) per node. Replaces the legacy frontier concept. A Lens shows the complete tree structure (preserving hierarchy for orientation) but controls detail via LOD: skeleton (uid+name only), lean (+ intent + epistemic_state), or full (all fields). You manipulate the Lens viewport (focus, promote, expand, prune) to gather or remove context as needed.

**projection** — Any derived artifact generated from a graph view. Code (in a chosen language and design flavor), documentation (spec, README, Gherkin), tests, visual rendering. Projections are bidirectional: edits to a projection can flow back into the graph.

**ProjectionIG** — A full IntentGraph (same formalism, same invariants) capturing the intent behind how a specific projection should be rendered and why. A code ProjectionIG encodes paradigm, naming, error handling. A doc ProjectionIG encodes audience, tone, emphasis. A test ProjectionIG encodes coverage strategy, assertion style. Nodes use `PIG-<TAG>.` UID prefix to avoid collision with product nodes.

---

## The Big Picture: Three Operation Types

IntentGraph supports three fundamental workflows:

**1. Graph Improvement (Declare)** — Refine the IntentGraph itself through dialogue, critique, and expansion. Build intent from scratch or improve extracted intent. Produces a higher-quality graph regardless of whether code exists.

**2. Code → Graph (Distill)** — Extract intent from existing code and documentation. Reverse-engineer the IntentGraph from an existing codebase. Produces both Product IntentGraph and ProjectionIG (observed rendering patterns).

**3. Graph → Code (Project)** — Generate code from a refined IntentGraph + ProjectionIG. Code is a projection materialized from intent. Regenerable, replaceable, producible in multiple languages or design flavors from the same intent.

The system keeps Product IntentGraph + ProjectionIG + code in sync. When code changes, reconcile back to the graph (Distill). When intent changes, regenerate or patch code (Project). The graph is the invariant.

---

## Multi-Stakeholder Collaboration

Different stakeholders — human and agent — need different views of the same system. Product managers need goals and trade-offs, developers need implementation details, QA needs behavioral specs. Agents acting as Critic need full constraint lists, agents acting as Generator need architectural context, agents acting as Extractor need code-to-intent mappings. In conventional software, these fragment into separate artifacts (tickets, docs, code, tests) that drift apart.

**IntentGraph solution:**

One canonical graph, multiple projections. Product managers see specs, developers see design docs, QA sees test scenarios — all generated from the same graph, guaranteed consistent. Projections exist in multiple formats: GUI (Obsidian) for humans, YAML/JSON for agents, code in multiple languages. When any projection is edited, changes flow back to the graph. No drift.

**Lens for context management:**

Each stakeholder works with a Lens — a personalized view showing full detail where focused, lean context for orientation, skeleton for distant parts. Product manager stays at Level 1 abstraction, developer drills to Level 4 detail — same graph, different depth. Agents manipulate their viewport (promote, expand, prune) to gather exactly the context needed without overload.

**Benefits:** No translation loss, no drift, bounded context reasoning, explicit uncertainty visible to all, changes propagate with traceability.

---

## The Mental Model: Abstraction Hierarchy, Not Execution Graph

**Critical distinction:** The tree is an abstraction hierarchy, not a call graph.

Parent and children represent the same intent surface at different resolutions (P2). The parent is not "implemented by" its children — it summarizes them at a coarser level of detail.

**Wrong thinking:** Parent = orchestrator procedure that calls children as execution steps.

**Correct thinking:** Parent = abstract summary that children refine at higher resolution.

**Test:** If a reader must expand to children to understand WHAT the parent does, the parent is written wrong.

**Map analogy:**

- Zoomed out (parent): "This region handles user authentication"
- Zoomed in (children): "Login flow", "Session management", "Password reset"

The zoomed-in view doesn't change what the region is for — it shows internal structure.

**Implication:** Details descend, abstraction ascends. Going down adds specificity (implementation detail, tool choices, data structures). Going up adds abstraction (summarize purpose, remove implementation detail).

---

## The Dual-Graph Model

P4 establishes that product intent and projection intent are independent concerns. The system uses two full IntentGraphs:

**Product IntentGraph** — Captures what the system does and why. Projection-agnostic. A constraint like "output is a keyed mapping of function records" belongs here. Language-specific typing (`Dict[str, FunctionRecord]`) does not.

**ProjectionIG** — A full IntentGraph (same formalism, same Lens mechanics, same invariants) capturing the intent behind a specific projection: how the rendering should be produced and why those choices were made. It is not a config file or style guide — it is a proper graph of intent about rendering, with its own refinement hierarchy, intentlinks, epistemic states, and review cycles.

The same product intent can yield different projections by swapping the ProjectionIG — OOP vs functional, executive summary vs technical spec, property-based vs example-based tests.

**Language-swap test:** If a constraint or intent sentence would break under a different projection (e.g., C++ instead of Python), it's projection-specific and belongs in the ProjectionIG, not the product graph.

---

## The Four Invariants

Ordered by importance. These are enforced by the core library. Violations are rejected.

**T1 — Tree well-formedness.**
Treearcs form a directed rooted tree. One parent per node, no cycles. This is structural integrity — without it, the graph is undefined.

**T4 — Refinement coherence.**
Expanding a node into children preserves the parent's meaning. Children collectively cover the parent's intent; no child contradicts or extends beyond the parent's scope. This is the semantic invariant behind P2. Without it, zooming breaks meaning.

**T3 — Graph connectivity.**
All intentlinks have valid endpoints (both src and dst exist in the graph). For **inter intentlinks**, both endpoints exist in their respective graphs when resolved via intent_resources. Nodes referenced in intentlinks, impl_pointers, or any cross-reference must exist. The graph is self-consistent.

**L1 — Lens viewport validity.**
A Lens maintains a valid tree structure at all times. Pruned branches are tracked but the visible tree remains well-formed. LOD assignments (skeleton/lean/full) are coherent with the tree structure. Pending edits do not violate T1, T4, or T3 when applied.

---

## Cardinal Rules (All Agents)

Ordered by importance.

1. **Never invent intent.** If you don't know, say so — `epistemic_state: "undecided"`. False certainty is worse than acknowledged uncertainty. The same discipline applies when *auditing* intent: when you cannot confirm a claim against a real artifact, default to refuted — treat it as failing, never as "probably fine."

2. **Keep product and projection separate (P4).** Language-specific content belongs in the ProjectionIG, not the product graph. Apply the language-swap test.

3. **Express WHY, not HOW.** If your intent reads like a code summary, rewrite it. The "blind generation test": a developer reading only the intent and constraints should understand the purpose, not reproduce the exact code.

4. **Never read the full graph.** No agent loads graph.json directly — it defeats the bounded-context design. Use the Lens you are given, and use `ig-tool query` for spot checks on specific nodes outside your view.

5. **Manipulate your Lens viewport actively.** If you need more detail on a distant node, promote it. If you need to see children, expand. If you need less clutter, prune or demote. The Lens is your working memory — adjust it to fit the task.

6. **Use hard tools when they exist.** Check `agents/PRIMER_TOOLS.md` (WHY/when) and `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) before writing scripts. If a tool doesn't exist for what you need, report the gap — do not reinvent.

7. **Task return ≤ 80 words.** All detail goes to disk. The orchestrator's context window is shared across the entire workflow — do not pollute it.

8. **Respect execution context.** Your task payload includes environment flags (dry_run, verbosity) and an **effort hint** — free-form guidance on depth vs speed. Follow it: a quick-pass hint means stay shallow and skip optional work; a thorough hint means expand, cross-check, and propagate. See PRIMER_04_WORKFLOWS §Execution context.

---

## When Rules Can Be Temporarily Relaxed

Invariants (T1–T4) and quality rules (bounded nodes, orthogonal decomposition, no overload or under-definition) describe the **target** state of the graph. During workflows you often pass through intermediate states that temporarily violate them — for example a node overloaded before expansion, or under-defined before gaps are filled. That is acceptable **provided** the epistemic state records it.

Record the temporary condition in `epistemic_state`, using the base state plus issue annotations (see PRIMER_01_SEMANTICS §epistemic_state, multi-issue convention). Examples: `observed | unclear: intent overloaded, expansion pending` or `undecided: under-specified, awaiting refinement`. The only constraint: **never leave a violation undocumented**. Once recorded, other agents and humans can see it and prioritize resolution. The graph may be temporarily "messy"; it must not be silently wrong.

---

## What You Are Documenting

You are capturing the intent of an EXISTING system, not designing a new one (exception: Declare workflow when building from scratch).

Wrong: "We should add X to handle Y" (future design intent)
Correct: "The system handles Y using X" (existing system intent)

Wrong: "This component will coordinate A, B, C" (future plan)
Correct: "This component coordinates A, B, C" (present capability)

Exception: Epistemic state `undecided` or `deferred` can note future decisions, but only when the system explicitly leaves something open. Example: "Caching strategy not yet chosen; current implementation uses in-memory dict"

---

## Next Steps

After reading this primer:

- **To interpret graphs:** Read PRIMER_01_SEMANTICS (how to read the structure correctly)
- **To navigate with Lens:** Read PRIMER_02_NAVIGATION (how to move through the graph)
- **To modify graphs:** Read PRIMER_03A_EDITING (how to make correct edits)
- **For command syntax:** See PRIMER_TOOLS (command reference catalog)
- **To understand workflows:** Read PRIMER_04_WORKFLOWS (where you are in the process)
