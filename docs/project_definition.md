# Project main intent
## Goal (intent only)
<!-- Lines 4-6 -->

This workflow is meant to let humans (and later AI) reason within limited context: you should be able to work on a small portion without holding the whole system in memory, while still staying aligned with the whole. Code is for machines (hard science: sharp, fully determined); intent is human, and this project takes inspiration from social science. The process can be rigorous while allowing uncertainty, fuzziness, and ambiguity in intent—and making epistemic state explicit (what is known, constrained, undecided, risky)—so the Intent graph doesn’t pretend to be complete and supports “know what you don’t know.” Code is downstream: it can be generated or written from the Intent, but it is not where intent lives.

## IntentGraph: title
<!-- Lines 9-10 -->
Mixed-detail Intent Graph as the source of truth

## IntentGraph: one sentence
<!-- Lines 13-14 -->
Center software development on a single Intent Graph that remains coherent under mixed levels of detail, so *direct* intent (what the system is for), constraints, and unknowns can be refined locally to generate code without rewriting the whole system.

## IntentGraph: one paragraph
<!-- Lines 17-18 -->
The objective is to make a mixed-detail Intent Graph the primary way software is defined, navigated, and evolved. The graph captures **direct intent**—what the system is meant to do—and aligns with the no-code / intent-first movement: express goals and structure first, then derive implementations. Different parts of a system can remain at different depths of description simultaneously, while preserving coherence and meaning across zoom levels: refinement adds precision but does not change what a component or connection is meant to represent. **Projection-level concerns** (coding conventions, documentation framing, test strategy, visual layout) are captured separately in a **ProjectionIG** — a full IntentGraph dedicated to a specific projection instance — or called out explicitly on intentnodes where tradeoffs matter. The workflow is designed for limited working context and explicit uncertainty, so it supports incremental elaboration, keeps constraints and design choices visible, and avoids pretending the model is complete. Code becomes a derived output of this evolving Intent Graph rather than the place where intent must be inferred.

## IntentGraph (project)
<!-- Lines 21-30 -->
The project is named after its model, the **IntentGraph**, and comprises: the model itself, a human-facing GUI, and agents that build, challenge, and derive projections from the graph.

**Central principle:** The intent graph is the canonical model; everything else is a **projection**. Code is a projection (derived from a product lens + a ProjectionIG lens, in a chosen language and design flavor). Documentation is a projection (a lens rendered as a spec, README, executive summary, or Gherkin scenario — shaped by its own ProjectionIG capturing audience, tone, and emphasis). The GUI is a projection (interactive visual rendering of a lens). Each projection instance can be backed by a **ProjectionIG** — a full IntentGraph capturing *how* that specific rendering should be produced and *why* those choices were made. Projections are bidirectional: when a projection is edited (a PM rewrites a requirement in the spec, a developer modifies code), the change flows back into the graph. IntentGraph does not replace spec-driven development or documentation workflows — it subsumes them. Specs, docs, and code become maintained views rather than parallel artifacts that drift.

**Core agents:** Elicitor (structured intent elicitation), Critic (graph quality review), Generator (graph→code), Extractor (code→graph, iterative), Verifier (intent→tests verification layer). **Supporting agents:** Navigator (lens recommendation), Propagator (change management across projections), Doc agents (bidirectional doc↔graph sync).

- **Roadmap:** [ROADMAP.md](../ROADMAP.md) (phases 0–5, validation, training)
- **Agent catalog:** [agents/README.md](../agents/README.md)

# Project vocabulary and definition
## direct intent
<!-- Lines 33-38 -->

**Definition:** What the system is meant to do—the goal, purpose, and "why"—as opposed to how it is implemented or how a specific projection is rendered.
**Role:** The primary content of the (product) IntentGraph. Distinct from **projection-level intent** (coding conventions, documentation framing, test strategy, visual layout, tradeoffs), which is captured in a **ProjectionIG** or stated explicitly on product intentnodes where tradeoffs matter.

---

## ProjectionIG
<!-- Lines 41-45 -->

**Definition:** A full IntentGraph — same formalism (intentnodes, treearcs, intentlinks, lenses, epistemic state) — capturing the intent behind *how a specific projection instance should be rendered and why*. This is broader than coding conventions: a code ProjectionIG encodes paradigm choice, naming, error handling; a documentation ProjectionIG encodes audience, tone, emphasis; a test ProjectionIG encodes coverage strategy and assertion style. One ProjectionIG per projection instance, not per type. ProjectionIG nodes use the `PIG-<TAG>.` UID prefix (e.g., `PIG-PY-LIB.0.3`) to avoid collision with product IntentGraph nodes. The main (product) intent graph can call out tradeoffs explicitly on intentnodes (e.g. "this part is intended to be fast, at the cost of X"); these override ProjectionIG defaults. See [VOCABULARY_AND_FORMALISM.md](../foundation_and_formalism/VOCABULARY_AND_FORMALISM.md) §2.7, §4.1.

---

## IntentGraph
<!-- Lines 48-54 -->

**Definition:** The complete multi-level Intent artifact: a graph whose nodes represent units of intent and whose edges capture both refinement structure and cross-node intent relations.
**Role:** Source of truth for describing a system at mixed levels of detail (direct intent).
**Contains:** `intentnode`, `intentlink`, `treearc`.

---

## intentnode
<!-- Lines 57-71 -->

**Definition:** A node in the IntentGraph representing a unit of intent at some level of detail.
**Role:** Carries the editable fields that express what is intended (and supporting context such as constraints, assumptions, examples, attention/effort, etc.).
**Key fields include:**
- **intent**: what this node is for and why.
- **constraints**: what must hold.
- **epistemic state**: what is *known, constrained, undecided, risky,* or *deferred*.
- **assumptions**: what is taken for granted at this node — conditions believed to be true but not verified, or choices that appear neutral but shape the design (e.g., "users have reliable internet," "input is always English," "sequential processing is fast enough"). Making assumptions explicit enables review, challenge, and informed revision as context changes.
- **data_registry**: structured data store (positions, configs, schemas, lookup tables) referenced by other fields via slash notation (`/key/subkey`). Data that would otherwise be buried in prose or live in sidecar files.
- **examples, attention/effort, notes, metadata**: supporting context.

**Refinement:** May be expanded into finer intentnodes via `treearc`, or treated as a leaf depending on the current lens.

---

## treearc
<!-- Lines 74-80 -->

**Definition:** A directed edge type forming the refinement tree of the IntentGraph.
**Role:** Defines the parent→children structure used for decomposition/refinement and for expand/collapse operations.
**Constraint:** All `treearc` edges together form a directed tree (each node has at most one parent, except the root).

---

## intentlink
<!-- Lines 83-91 -->

**Definition:** A directed edge between two intentnodes carrying an explicit, valued relationship (e.g., data exchange, dependency, coordination, context transfer).
**Role:** Captures “what connects what” at the current working level; intended to remain representable across levels when nodes are expanded/collapsed.
**Note:** Multiple intentlinks may aggregate/generalize when viewed at higher levels of the refinement tree.

**Inter intentlink:** A directed, valued relation between an intentnode in one IntentGraph and an intentnode in another; same intent/shape semantics as same-graph intentlinks. Endpoints are graph-qualified (`graph_id:node_uid`). Primary use: link ProjectionIG nodes to product IG nodes. When precision is needed, the same-graph intentlink is called **intra intentlink**.

---

## lens
<!-- Lines 94-101 -->

**Definition:** A shaped view of the IntentGraph — an ancestor-closed set of intentnodes, each carrying a level of detail (`skeleton < lean < full`), plus the intentlinks whose endpoints are both included.
**Role:** The unit of visualization and editing: you typically operate through a lens rather than the full IntentGraph. Two artifacts realize it — the **Lens** (materialized full-tree view for agent I/O) and the **LensConfig** (named, stored view inside the graph's `lenses` block).
**Behavior:** Expanding a node adds its children; pruning removes a subtree; `set_lod` changes a node's detail. Ancestor closure keeps hierarchy navigable at all times.
**Note:** The lens supersedes the former **display frontier** (a partial antichain of visible nodes) — a frontier was exactly a lens with binary LOD. The frontier concept is retired.

---

## projection
<!-- Lines 104-109 -->

**Definition:** Any derived artifact generated from the graph through a lens — code, documentation, tests, or a visual rendering. The intent graph is the canonical model; projections are materializations for specific audiences and purposes. Each projection instance may be backed by a **ProjectionIG** that captures the rendering-specific intent behind it.
**Examples:** Code in a chosen language and design flavor (via Generator, guided by a ProjectionIG lens). A spec document, README, or executive summary (via Doc agents, shaped by a documentation ProjectionIG). A Gherkin scenario file. The GUI's visual rendering of a lens.
**Bidirectional:** Projections are not read-only outputs. When a projection is edited (a developer modifies code, a PM rewrites a spec), the change can be reconciled back into the graph (via Extractor, Doc agents, or Propagator), keeping the canonical model and its projections in sync.
**Implication:** IntentGraph subsumes spec-driven development and documentation workflows. Specs, docs, and code are maintained views of the graph rather than parallel artifacts that drift.

