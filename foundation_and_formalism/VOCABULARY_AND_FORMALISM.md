# IntentGraph — Vocabulary & Formalism (Phase 0)

**Status:** Working draft — consolidation of existing material into a single reference  
**Sources:** `docs/rules.md`, `docs/intentlink_spec.md`, `docs/project_definition.md`, `schema/*.v0.yaml`  
**Goal:** One document where every term has exactly one definition, every invariant has a precise statement, and every operation has pre/postconditions. This is the foundation everything else compiles against.

---

## Table of Contents

1. [1. Guiding Principles](#1-guiding-principles) _(Lines 82-98)_
1. [2. Vocabulary](#2-vocabulary) _(Lines 101-103)_
   1. [2.1 — intentnode](#21--intentnode) _(Lines 106-112)_
   1. [2.2 — treearc](#22--treearc) _(Lines 115-122)_
   1. [2.3 — intentlink](#23--intentlink) _(Lines 125-132)_
   1. [2.4 — IntentGraph](#24--intentgraph) _(Lines 135-141)_
   1. [2.5 — lens](#25--lens) _(Lines 144-153)_
   1. [2.6 — projection](#26--projection) _(Lines 156-163)_
   1. [2.7 — ProjectionIG](#27--projectionig) _(Lines 166-176)_
1. [3. Notation](#3-notation) _(Lines 179-181)_
   1. [3.1 — Symbols (the nouns)](#31--symbols-the-nouns) _(Lines 184-195)_
   1. [3.2 — Operators (the verbs)](#32--operators-the-verbs) _(Lines 198-223)_
1. [4. Node Schema](#4-node-schema) _(Lines 226-244)_
   1. [History field — provenance, not audit](#history-field--provenance-not-audit) _(Lines 247-286)_
   1. [Provenance capture — write-boundary, commit-style](#provenance-capture--write-boundary-commit-style) _(Lines 289-299)_
   1. [data_registry field — structured data, not prose](#data_registry-field--structured-data-not-prose) _(Lines 302-331)_
   1. [4.1 — ID / Primary Key Scheme](#41--id--primary-key-scheme) _(Lines 334-336)_
      1. [Node IDs](#node-ids) _(Lines 339-356)_
      1. [Treearc IDs](#treearc-ids) _(Lines 359-363)_
      1. [Intentlink IDs](#intentlink-ids) _(Lines 366-386)_
      1. [ProjectionIG Node IDs](#projectionig-node-ids) _(Lines 389-401)_
   1. [4.2 — impl_pointers Grammar](#42--impl_pointers-grammar) _(Lines 404-429)_
1. [5. Intentlink Schema](#5-intentlink-schema) _(Lines 432-443)_
   1. [Intentlink typing vocabulary (v0)](#intentlink-typing-vocabulary-v0) _(Lines 446-459)_
   1. [Non-duplication rule](#non-duplication-rule) _(Lines 462-466)_
   1. [Intentlink refinement](#intentlink-refinement) _(Lines 469-476)_
   1. [Inter intentlinks](#inter-intentlinks) _(Lines 479-495)_
1. [6. IntentGraph Schema](#6-intentgraph-schema) _(Lines 498-511)_
1. [7. Lens Schema](#7-lens-schema) _(Lines 514-530)_
1. [8. Invariants](#8-invariants) _(Lines 533-535)_
   1. [T1 — Tree property (tarcs)](#t1--tree-property-tarcs) _(Lines 538-546)_
   1. [T2 — Lens closure](#t2--lens-closure) _(Lines 549-561)_
   1. [T3 — Intentlink well-formedness](#t3--intentlink-well-formedness) _(Lines 564-572)_
   1. [T4 — Refinement coherence (meaning-stability)](#t4--refinement-coherence-meaning-stability) _(Lines 575-587)_
   1. [T5 — Lens closure under operations](#t5--lens-closure-under-operations) _(Lines 590-603)_
1. [9. Operations Catalog](#9-operations-catalog) _(Lines 606-608)_
   1. [9.1 — inode operations](#91--inode-operations) _(Lines 611-611)_
      1. [`inode_create(uid, name, intent, ...)`](#inode_createuid-name-intent-) _(Lines 614-618)_
      1. [`inode_update(uid, fields...)`](#inode_updateuid-fields) _(Lines 621-625)_
      1. [`inode_delete(uid)`](#inode_deleteuid) _(Lines 628-632)_
   1. [9.2 — tarc operations](#92--tarc-operations) _(Lines 635-635)_
      1. [`tarc_attach(p, c)`](#tarc_attachp-c) _(Lines 638-642)_
      1. [`tarc_detach(p, c)`](#tarc_detachp-c) _(Lines 645-649)_
   1. [9.3 — ilink operations](#93--ilink-operations) _(Lines 652-652)_
      1. [`ilink_create(uid, u, v, m)`](#ilink_createuid-u-v-m) _(Lines 655-659)_
      1. [`ilink_update(uid, fields...)`](#ilink_updateuid-fields) _(Lines 662-666)_
      1. [`ilink_delete(uid)`](#ilink_deleteuid) _(Lines 669-673)_
   1. [9.4 — Lens operations](#94--lens-operations) _(Lines 676-676)_
      1. [`lens_add_node(L, n, ℓ)` → `L'`](#lens_add_nodel-n-ℓ--l) _(Lines 679-683)_
      1. [`lens_remove_node(L, n)` → `L'`](#lens_remove_nodel-n--l) _(Lines 686-690)_
      1. [`set_lod(L, n, ℓ)` → `L'`](#set_lodl-n-ℓ--l) _(Lines 693-697)_
      1. [`lens_add_link(L, e)` / `lens_remove_link(L, e)` → `L'`](#lens_add_linkl-e--lens_remove_linkl-e--l) _(Lines 700-708)_
1. [10. Ilink Lifting & Projection](#10-ilink-lifting--projection) _(Lines 711-713)_
   1. [10.1 — Visibility rule](#101--visibility-rule) _(Lines 716-720)_
   1. [10.2 — Projection (lifting)](#102--projection-lifting) _(Lines 723-731)_
   1. [10.3 — Dominance / de-cluttering](#103--dominance--de-cluttering) _(Lines 734-741)_
   1. [10.4 — Aggregation (display-level only)](#104--aggregation-display-level-only) _(Lines 744-751)_
   1. [10.5 — No cross-product maintenance](#105--no-cross-product-maintenance) _(Lines 754-756)_
   1. [10.6 — The core guarantee](#106--the-core-guarantee) _(Lines 759-765)_
1. [11. Epistemic State](#11-epistemic-state) _(Lines 768-772)_
   1. [Recommended vocabulary](#recommended-vocabulary) _(Lines 775-789)_
   1. [Implications for tooling](#implications-for-tooling) _(Lines 792-798)_
1. [12. Open Questions](#12-open-questions) _(Lines 801-815)_
1. [Appendix A — Source Traceability](#appendix-a--source-traceability) _(Lines 818-834)_



---

## 1. Guiding Principles
<!-- Lines 82-98 -->

Four axioms that precede and constrain all definitions below.

**P1 — Intent is the source of truth.**  
Code, documentation, specs, visual views are *projections* — derived artifacts generated from the IntentGraph. Different audiences get different projections of the same truth. The graph is the invariant; implementations are consequences.

**P2 — Zooming adds information, never changes meaning.**  
Refining a node into children increases precision but preserves the intended role. A parent and its children represent the *same intent surface* at different resolution. This is the "meaning-stability" constraint — the single property that makes mixed-detail coherence possible.

**P3 — Incompleteness is first-class.**
The model must tolerate areas that remain coarse indefinitely, unknowns that are explicitly recorded, and uncertainty that is modeled rather than hidden. "Know what you don't know" is a structural requirement, not an aspiration.

**P4 — Projection is orthogonal.**
What a system does (product intent) and how that intent is materialized into artifacts (projection intent) are independent concerns. Each gets its own IntentGraph. When they are mixed, implementation details contaminate the product graph, diluting the intent it exists to capture. Every reader — human or agent — would then have to separate purpose from rendering choices before they can reason about either, or risk mistaking projection assumptions for intent and building the wrong thing.

---

## 2. Vocabulary
<!-- Lines 101-103 -->

Every term used in IntentGraph, defined exactly once. Terms are ordered by dependency (each term uses only previously defined terms).

### 2.1 — intentnode
<!-- Lines 106-112 -->

A **node in the IntentGraph** representing a unit of intent at some level of detail.

- An intentnode describes *what* a part of the system is meant to do and *why*, not *how* it is implemented.
- Intentnodes exist at any level of the refinement hierarchy — from system-level goals to leaf-level behavioral atoms.
- An intentnode is self-sufficient at its level: it carries enough information to understand its purpose without requiring expansion into children (though expansion adds precision).

### 2.2 — treearc
<!-- Lines 115-122 -->

A **directed edge** `parent → child` forming the **refinement tree** of the IntentGraph.

- Treearcs define how a coarse intentnode decomposes into finer intentnodes.
- The collection of all treearcs forms a **directed rooted tree** (forest if multiple roots, but canonical usage assumes one root per graph).
- Each intentnode has at most one parent via treearc. The root has none.
- Treearcs carry no payload — the relationship they encode is pure refinement ("this node elaborates into these children").

### 2.3 — intentlink
<!-- Lines 125-132 -->

A **directed, valued relation** between two intentnodes.

- Intentlinks state what must be true *between* nodes — data exchange, dependency, coordination, constraint propagation, compatibility, etc.
- Unlike treearcs (which are structural/refinement edges), intentlinks carry semantic payload: an `intent` sentence and optionally a `shape` (structured grounding).
- Intentlinks are orthogonal to the tree: they can connect any two nodes at any depth, including nodes in different subtrees.
- Intentlinks are refinable: a coarse link can be decomposed into finer child links (see §5, §10).

### 2.4 — IntentGraph
<!-- Lines 135-141 -->

The **complete artifact**: a graph whose nodes are intentnodes, whose structural edges are treearcs (forming a refinement tree), and whose semantic edges are intentlinks (carrying valued relationships).

- The IntentGraph owns all nodes, treearcs, intentlinks, inter intentlinks (links to nodes in other graphs — see §5), and named lens configurations (see §7).
- It enforces structural invariants on every mutation (see §8).
- It is serializable (JSON, YAML) and round-trippable. See [SERIALIZATION_FORMAT.md](SERIALIZATION_FORMAT.md) for the wire format specification. On save, nodes and treearcs are emitted in **breadth-first** order (root(s) first, then each level).

### 2.5 — lens
<!-- Lines 144-153 -->

A **shaped view of the IntentGraph** — an assignment of a **level of detail (LOD)** to a set of included intentnodes: `skeleton < lean < full`.

- The lens is the unit of work: a human or agent reasons about a target area at `full` detail, with ancestors at `lean` for orientation and distant branches at `skeleton` or pruned entirely.
- The included node set is **ancestor-closed**: if a node is in the lens, so are all its ancestors (closure invariant C1, [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md) §6). Hierarchy is therefore always navigable within a lens.
- Two artifacts realize the concept:
  - **Lens** (agent I/O) — a materialized full-tree view carrying node bodies, used as the primary agent read/write format.
  - **LensConfig** (stored view) — a named, lightweight configuration inside the graph file (`lenses:` block) recording *which* nodes at *what* LOD, plus optional display positions. Multiple named lenses per graph.
- The lens subsumes the former **display frontier** (a partial antichain of visible nodes): a frontier is exactly a lens whose deepest included nodes are at `full` with everything below pruned. The frontier concept is retired.

### 2.6 — projection
<!-- Lines 156-163 -->

Any **derived artifact** generated from the IntentGraph, typically through a lens.

- Code (in a chosen language and design flavor), documentation (spec, README, Gherkin, executive summary), visual rendering (GUI), or textual serialization (for agent I/O — see [SERIALIZATION_FORMAT.md](SERIALIZATION_FORMAT.md) §2).
- Projections are **bidirectional**: edits to a projection can flow back into the graph (reconciliation).
- Different projections of the same lens serve different audiences (PM sees spec, dev sees code, tester sees scenarios).
- Each projection instance may be backed by a **ProjectionIG** (§2.7) that captures the intent behind *how that particular rendering should be produced and why*.

### 2.7 — ProjectionIG
<!-- Lines 166-176 -->

A **full IntentGraph** — same formalism (intentnodes, treearcs, intentlinks, lenses, epistemic state) — that captures the **projection-specific intent** behind a particular projection instance: *how* the rendering should be produced and *why* those choices were made.

- **Broader than coding style.** A code ProjectionIG encodes paradigm preference, naming conventions, error handling patterns, performance tradeoffs. A documentation ProjectionIG encodes audience, tone, emphasis, level of detail. A test ProjectionIG encodes coverage strategy, assertion style, scenario structure. Any rendering-specific concern that shapes the projection belongs here.
- **Separates product intent from projection intent.** The product IntentGraph captures *what the system does and why*. The ProjectionIG captures *how a specific rendering should be written and why those rendering choices were made*. These are orthogonal concerns: the same product intent can yield different code projections (OOP vs. functional), different doc projections (executive summary vs. technical spec), or different test projections (property-based vs. example-based).
- **One per projection instance, not per type.** Multiple Python code projections can each have their own ProjectionIG with different design flavors. A project might have a "fast CLI" ProjectionIG alongside a "well-documented library" ProjectionIG for the same product intent.
- **Same graph machinery.** ProjectionIG nodes use the `PIG-<TAG>.` UID prefix (e.g., `PIG-PY-LIB.0.3`) to prevent collision with product IntentGraph nodes. See §4.1. The full formalism applies: refinement via treearcs, cross-node relations via intentlinks, mixed-detail lenses, epistemic state on every node.
- **Navigated dynamically.** The materializing agent (e.g., Generator for code) works with a **ProjectionIG lens** — a lens over the ProjectionIG — alongside the product lens. It does not hold the full ProjectionIG in context. Instead, it delegates lens shaping (focus, promote/demote LOD, prune, expand) to the Navigator and receives updated lens views as needed during generation.

---

## 3. Notation
<!-- Lines 179-181 -->

Separated into **symbols** (the nouns — what things are) and **operators** (the verbs — what you can query or compute). All names are domain-specific and memorable.

### 3.1 — Symbols (the nouns)
<!-- Lines 184-195 -->

| Symbol | What it is | Structure |
|--------|-----------|-----------|
| `IG` | The IntentGraph — the complete artifact | `IG = (inodes, tarcs, ilinks)` |
| `inode` | An intentnode — a unit of intent | Identified by its uid (e.g. `EXTRACT.1.3`) |
| `tarc(p, c)` | A treearc — refinement edge from parent `p` to child `c` | `p` and `c` are inodes |
| `ilink(u, v, m)` | An intentlink — valued relation from `u` to `v` with metadata `m` | `u`, `v` are inodes; `m` = {intent, shape?, parent?} |
| `L` | A lens — an ancestor-closed LOD assignment over inodes | `L: dom(L) → {skeleton, lean, full}`, `dom(L)` ⊆ `inodes`, `dom(L)` closed under `anc` |
| `PIG` | A ProjectionIG — an IntentGraph capturing projection-specific intent | Same structure as `IG`; nodes prefixed with `PIG-<TAG>.` |

Variables: `n`, `p`, `c`, `u`, `v` are always inodes. `p` is typically a parent, `c` a child, `u` a source, `v` a destination.

### 3.2 — Operators (the verbs)
<!-- Lines 198-223 -->

**Tree navigation** — querying the treearc structure:

| Operator | Returns | Meaning |
|----------|---------|---------|
| `parent(n)` | inode or ⊥ | The unique parent of `n`, or ⊥ if `n` is ROOT |
| `children(n)` | set of inodes | All direct children of `n` |
| `anc(n)` | set of inodes | All ancestors of `n` (transitive closure of `parent`) |
| `desc(n)` | set of inodes | All descendants of `n` (transitive closure of `children`) |
| `is_above(n, m)` | boolean | True iff `n` is an ancestor of `m`, or `n = m`. Written `n ⪰ m` |
| `is_leaf(n)` | boolean | True iff `children(n)` is empty |
| `siblings(n)` | set of inodes | `children(parent(n))` — all children of `n`'s parent, including `n` |

**Lens operations** — working with a lens:

| Operator | Returns | Meaning |
|----------|---------|---------|
| `dom(L)` | set of inodes | The nodes included in the lens (ancestor-closed). |
| `lod(L, n)` | LOD or ⊥ | The LOD assigned to `n` by `L`; ⊥ if `n` ∉ `dom(L)`. |
| `rep(L, n)` | inode | The nearest ancestor-or-self of `n` in `dom(L)`. Total whenever `ROOT` ∈ `dom(L)` (guaranteed by ancestor closure for any non-empty lens). |
| `expand(L, n)` | lens | Add `children(n)` to `dom(L)` (at a chosen LOD, default `lean`). |
| `prune(L, n)` | lens | Remove `desc(n)` ∩ `dom(L)` from the lens; `n` stays. |
| `set_lod(L, n, ℓ)` | lens | Reassign `n`'s LOD; membership unchanged. |

---

## 4. Node Schema
<!-- Lines 226-244 -->

The field-level structure of an intentnode. Consolidates and revises `schema/intentnode.v0.yaml`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uid` | string | **yes** | **Primary key.** Encodes the node's position in the hierarchy. Root is `ROOT`; L1 nodes are a single segment — keyword (preferred, e.g. `EXTRACT`) or number (allowed, e.g. `1`); L2 nodes are either `{parent}.{KEYWORD}` for named sub-capabilities (e.g. `EXTRACT.DB`) or `{parent}.{number}` for minor nodes (e.g. `EXTRACT.1`); L3+ nodes are always `{parent}.{number}` (e.g. `EXTRACT.DB.1`, `TRANSFORM.2.1`). See §4.1. |
| `name` | string | **yes** | Short human-readable label. |
| `intent` | string | **yes** | WHAT: the intended behavior/role. Must be level-consistent across refinement (P2). |
| `epistemic_state` | string | no | Free-text assessment of what is known, uncertain, risky, or deferred about this node. Not an enum — nuance matters. See §11 for recommended vocabulary, but authors should write what is true rather than pick from a menu. |
| `constraints` | list[string] | no | Hard constraints / guardrails — must-not-violate statements. |
| `examples` | list[string] | no | Concrete ground-truth examples. Highly valuable for generation and validation. |
| `design_notes` | string | no | WHY: the reasoning behind choices — why this approach, what alternatives were considered and rejected, what tradeoffs were accepted. Captures the rationale that `intent` alone doesn't convey. |
| `effort` | string | no | Guidance on attention/effort allocation (e.g. "high correctness critical", "best effort"). Free text — never a number. |
| `impl_pointers` | list[string] | no | WHERE: pointers into the codebase where this intent is realized. Each entry follows the pointer grammar `path[::Symbol[.member]][ (lines X-Y)]` — e.g. `src/auth.py::AuthParser.parse (lines 40-80)`. One pointer per entry. See §4.2. |
| `history` | list[{who, date, note}] | no | Provenance log: who touched this node (human or agent), when, and what they did. The primary signal for whether a human has been involved. Captured automatically at every save — see "Provenance capture" below. |
| `data_registry` | dict | no | Structured data store referenced by other fields via slash notation (`/key/subkey`). Values are JSON/YAML-compatible (strings, numbers, bools, null, nested dicts/lists). Every top-level key must be referenced in at least one other field. Optional; omitted when absent or empty. |

**Key distinction:** `intent` captures WHAT (the intended behavior/role). `design_notes` captures WHY (the reasoning behind choices — rejected alternatives, accepted tradeoffs, rationale for constraints). `impl_pointers` captures WHERE (the code locations that realize the intent). `history` captures WHO — which humans and agents touched this node and what they did. Together they give a reader the destination, the reasoning, the realization, and the provenance.

### History field — provenance, not audit
<!-- Lines 247-286 -->

The `history` field exists to make one thing crystal clear: **where a human has been involved and where they haven't.**

In a system where AI agents (Extractor, Elicitor, Critic) do substantial work on the graph, every node needs visible provenance. A node that a human wrote, reviewed, and refined is fundamentally different from one an agent proposed and nobody looked at. The history field is how you tell them apart.

Each entry has:

| Subfield | Type | Required | Description |
|----------|------|----------|-------------|
| `who` | string | **yes** | Who did this. Must distinguish human from agent. Convention: human names/handles as-is (`remi`, `tom`); agents prefixed with `agent:` (`agent:extractor`, `agent:elicitor`, `agent:critic`). |
| `date` | string (ISO 8601) | **yes** | When. `2026-02-12`, `2026-02-12T14:30`, or just `2026-02` — precision is the author's choice. |
| `note` | string | **yes** | What was done and why. Free-text. |

Example:

```yaml
history:
  - who: "agent:extractor"
    date: "2026-01-15"
    note: "Created node. Initial intent extracted from codebase module auth.py."
  - who: "remi"
    date: "2026-01-22"
    note: "Reviewed and refined intent after domain expert interview. Narrowed scope — dropped real-time requirement."
  - who: "agent:critic"
    date: "2026-01-23"
    note: "Flagged: intent is vague on error handling. Suggested adding constraints."
  - who: "remi"
    date: "2026-02-03"
    note: "Added constraints for error handling. Marked epistemic_state as risky — load testing showed 2x latency."
  - who: "remi"
    date: "2026-02-10"
    note: "Resolved: accepted latency tradeoff. Updated design_notes with rationale."
```

**Reading this log tells you instantly:** a machine created this node, a human reviewed it, a machine flagged an issue, a human addressed it twice. The node has been human-validated.

**A node with only `agent:*` entries has never been human-touched.** That is the most important signal in the entire graph — it means the intent is unvalidated.

The log pairs with `epistemic_state`: the state says where the node is now, the history says who brought it there.

### Provenance capture — write-boundary, commit-style
<!-- Lines 289-299 -->

History is **captured automatically at the write boundary**, not opted into per command. The contract, modeled on a git commit:

- **Every save of the graph carries an actor context.** Tools diff the loaded state against the state being saved and append one history entry to each node whose content changed — same message on every touched node, exactly like one commit spanning several files.
- **`who` is resolved from the channel**, never typed per entry: agents pass their role (`agent:extractor`); humans are resolved from identity (`IG_ACTOR` environment variable, else git `user.name`, else OS user). A channel qualifier may be appended: `remi via:obsidian`, `remi via:vscode`.
- **`date` is stamped automatically** as a full ISO 8601 timestamp (`2026-07-15T14:30`). Hand-written entries may use coarser precision.
- **`note` is a one-liner commit message.** Callers supply it (`-m` on the CLI); when omitted, tools generate a diff summary (e.g. `"intent updated; +2 constraints"`). A supplied message should say *why*, not restate the diff.
- **Trivial changes never stamp:** sibling reordering, lens configuration, serialization noise. Content-field changes (`name`, `intent`, `epistemic_state`, `constraints`, `examples`, `design_notes`, `effort`, `impl_pointers`, `data_registry`) and structural changes (create, delete, reparent) always stamp. `history` itself is excluded from the diff.

Consequences: history is append-only by construction, no pathway can forget to stamp, and a node with only `agent:*` entries is *reliably* a node no human has touched.

### data_registry field — structured data, not prose
<!-- Lines 302-331 -->

`data_registry` is a free-form nested dict attached to a node. Its purpose is to hold **data that other fields reference** — positions, measurements, config values, lookup tables — rather than prose that belongs in `intent`, `design_notes`, or `constraints`.

**Slash-notation references.** Any field (intent, constraints, design_notes, examples) may reference into the registry using a slash-prefixed path:

```
/positions               → data_registry["positions"]
/positions/ROOT.1/x      → data_registry["positions"]["ROOT.1"]["x"]
/spacing/horizontal      → data_registry["spacing"]["horizontal"]
```

**Governance rules:**

- **G1 — no orphan keys.** Every top-level key must be referenced by at least one other field in the same node. Unreferenced data is dead data.
- **G2 — values are data, not prose.** Strings in the registry are identifiers, labels, or codes — not sentences. Prose belongs in `intent` or `design_notes`.
- **G3 — hierarchy.** Parent nodes hold cross-cutting data (shared config, global parameters). Children hold local data (specific positions, per-component config). No duplication across siblings.
- **G4 — projection-aware.** Product IG holds domain data (e.g. field names, business rules). ProjectionIG holds rendering data (e.g. canvas positions, pixel spacing). Don't mix these concerns in the same node.
- **G5 — bounded.** Soft limit ~100 KB per node, hard limit ~1 MB. If a registry grows past the soft limit, consider splitting the node.

**Reserved key `_epistemic`.** The key `_epistemic` is reserved for per-path epistemic state overrides. Its internal structure is opaque at the graph model level — the epistemic layer owns interpretation. Do not use `_epistemic` for application data.

**Decision framework — registry vs prose:**

| Question | Yes → | No → |
|----------|-------|------|
| Is it a collection of values? | registry | prose field |
| Will it be machine-parsed or computed? | registry | prose field |
| Does it change independently of the intent? | registry | inline in prose |
| Is it structured (dict/list), not a sentence? | registry | prose field |

### 4.1 — ID / Primary Key Scheme
<!-- Lines 334-336 -->

All primary keys are **hierarchy-encoded** — plain ASCII, human-readable, self-describing. No special characters.

#### Node IDs
<!-- Lines 339-356 -->

Format: `{root}.{segment}.{segment}...`

- **Root node**: a conventional name, typically `ROOT`. Explicit, not implicit.
- **L1 nodes**: A single segment chosen by the author. A keyword is strongly preferred; a number is allowed.
  - Keyword (preferred): `EXTRACT`, `TRANSFORM`, `LOAD`, `API`, `UI`, `DB`
  - Numeric (allowed): `1`, `2`, `3`
  - Single-letter UIDs (`E`, `T`, `L`) are discouraged — use full words.
  - Multi-segment compound names (`ERROR.HANDLER`, `DISCOVER.DB`) are **not** valid at L1 — they belong at L2.
- **L2 nodes**: Two patterns based on how the node is expected to grow:
  - **Numeric** (minor node): `{parent}.{number}` — e.g. `EXTRACT.1`, `LOAD.2`
  - **Semantic** (named sub-capability): `{parent}.{keyword}` — e.g. `EXTRACT.DB`, `API.CLIENT`
- **L3+ nodes**: Always parent prefix + dot + sequential number.

Examples: `ROOT`, `EXTRACT`, `EXTRACT.DB`, `EXTRACT.1`, `EXTRACT.DB.1`, `TRANSFORM.2.1`

Reading `TRANSFORM.2.1`: the 1st child of the 2nd child of top-level TRANSFORM.

#### Treearc IDs
<!-- Lines 359-363 -->

No separate ID. A treearc is identified by the `(parent_uid, child_uid)` pair, which is unique by T1.

Example: `(EXTRACT, EXTRACT.1)`, `(EXTRACT.1, EXTRACT.1.3)`

#### Intentlink IDs
<!-- Lines 366-386 -->

Format: `{src_uid}_{dst_uid}` or `{src_uid}_{dst_uid}#{tag}`

The underscore `_` separates source from destination. Node IDs use dots and alphanumerics only, so `_` is unambiguous. The `#tag` disambiguator is author-chosen when multiple links exist between the same pair.

Examples: `EXTRACT.1.1_TRANSFORM.2.1`, `EXTRACT.1.1_TRANSFORM.2.1#auth`, `EXTRACT.3_LOAD.1#data`, `EXTRACT.3_LOAD.1#schema`

| Entity | PK format | Example |
|--------|-----------|---------|
| **intentnode** | `{root}.{keyword}.{pos}...` | `ROOT`, `EXTRACT`, `EXTRACT.1.3`, `TRANSFORM.2.1.4` |
| **treearc** | `(parent, child)` | `(EXTRACT, EXTRACT.1)`, `(EXTRACT.1, EXTRACT.1.3)` |
| **intentlink** | `{src}_{dst}` or `{src}_{dst}#{tag}` | `EXTRACT.1.1_TRANSFORM.2.1`, `EXTRACT.3_LOAD.1#auth` |

**Design rationale:**

- **Self-describing.** You can read the tree position, the source/target of a link, and the domain meaning directly from the ID. No lookups needed.
- **Author-chosen keywords.** L1 keywords are a naming decision, not auto-assigned. This gives the graph a readable top-level structure (`EXTRACT.*`, `TRANSFORM.*`, `LOAD.*`) that maps to the domain rather than arbitrary numbers.
- **Plain ASCII only.** No `→`, no Unicode. IDs are safe in filenames, YAML keys, URLs, grep, and every tool in the chain.
- **Reparenting = cascading rename.** Moving a subtree changes all descendant UIDs and every reference to them. This is manageable by software at reasonable scale (hundreds to low thousands of nodes). If the graph grows beyond that, a stable internal UUID can be added as a secondary key.
- **Sibling ordering.** Positions are ordinal (1, 2, 3...). Inserting between `.1` and `.2` requires renumbering — again, manageable by software.

#### ProjectionIG Node IDs
<!-- Lines 389-401 -->

Format: `PIG-<TAG>.{segment}.{segment}...`

- **`PIG-` prefix** identifies the node as belonging to a ProjectionIG, not the product IntentGraph.
- **TAG** is an author-chosen short identifier for the projection instance (e.g., `PY-LIB`, `PY-CLI`, `DOCS-EXEC`, `TEST-PROP`). Should be mnemonic and unambiguous within the project.
- **Segments** follow the same dot-separated ordinal convention as product IntentGraph nodes.

Examples: `PIG-PY-LIB`, `PIG-PY-LIB.1`, `PIG-PY-LIB.1.3`, `PIG-DOCS-EXEC.2.1`

Reading `PIG-PY-LIB.1.3`: the 3rd child of the 1st child of the root of the `PY-LIB` ProjectionIG.

**No-collision guarantee:** Product IntentGraph nodes use plain letters/ordinals (`E.`, `T.`, `ROOT`). The `PIG-` prefix is never a valid product node ID, so UIDs from different graphs are always distinguishable. This prepares for future inter-graph intentlinks without requiring a separate namespace layer.

### 4.2 — impl_pointers Grammar
<!-- Lines 404-429 -->

Each `impl_pointers` entry is a **canonical pointer string** — writable by hand, parseable by tools:

```text
pointer   := path [ "::" symbol ] [ " (lines " start "-" end ")" ]
path      := repo-relative file path
symbol    := Identifier ( "." Identifier )*      # class, function, or dotted member chain
```

Examples:

```yaml
impl_pointers:
  - "src/auth.py::AuthParser.parse (lines 40-80)"
  - "src/auth.py::AuthParser"
  - "migrations/0042_add_roles.sql"
```

Rules:

- **One pointer per list entry.** Never pack several locations into one string.
- **Symbol over lines.** The `::symbol` anchor survives edits; line ranges rot. Prefer symbol-only pointers; add line ranges only when the symbol is too coarse.
- **Machine-checkable.** Because the grammar is fixed, `validate` and the Verifier can parse pointers and resolve them against the codebase (path exists, symbol resolvable — e.g. via codemap). A pointer that no longer resolves is a re-grounding obligation, not an error.

---

## 5. Intentlink Schema
<!-- Lines 432-443 -->

The field-level structure of an intentlink. Consolidates `schema/intentlink.v0.yaml` and `docs/intentlink_spec.md`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uid` | string | **yes** | **Primary key.** Derived from endpoints: `{src}_{dst}` or `{src}_{dst}#{tag}` when multiple links exist between the same pair. See §4.1. |
| `src` | string | **yes** | Source intentnode uid. |
| `dst` | string | **yes** | Target intentnode uid. |
| `intent` | string | **yes** | One sentence: the relationship asserted between `src` and `dst`. |
| `shape` | object | no | Structured grounding (interface, schema, protocol, signature, invariants). Opaque at v0. |
| `parent` | string | no | UID of the parent link, if this is a refined child link. |

### Intentlink typing vocabulary (v0)
<!-- Lines 446-459 -->

The `intent` field is free-text, but the following **categories** are recommended for consistency:

| Category | Meaning | Example |
|----------|---------|---------|
| `data_exchange` | `src` provides data consumed by `dst` | "Sends user profile to rendering" |
| `dependency` | `dst` cannot function without `src` | "Requires authentication service" |
| `coordination` | `src` and `dst` must synchronize behavior | "Must agree on session state" |
| `context_transfer` | `src` establishes context consumed by `dst` | "Provides locale for formatting" |
| `constraint_propagation` | A constraint on `src` implies a constraint on `dst` | "Rate limit on API propagates to queue" |
| `compatibility` | `src` and `dst` must maintain interface compatibility | "Must accept same JSON schema" |

This is a recommended vocabulary, not a closed enum. Links may combine categories or use domain-specific descriptions.

### Non-duplication rule
<!-- Lines 462-466 -->

- **intentnode.intent** describes the node's responsibility ("within the node").
- **intentlink.intent** describes the contract/relation ("between nodes").
- They must not redundantly restate each other.

### Intentlink refinement
<!-- Lines 469-476 -->

An intentlink may be refined into child intentlinks (link tree):

- Each link has **0..N refined children**.
- Each child has **exactly 1 parent link** (forest of links).
- **Endpoint constraint (descendant rule):** If a parent link is `ilink(A, B, m)`, any child link must connect descendants: `ilink(a, b, m')` where `a` ∈ `desc(A)` ∪ {`A`} and `b` ∈ `desc(B)` ∪ {`B`}.
- Refinement adds precision *within the regions* represented by the endpoints.

### Inter intentlinks
<!-- Lines 479-495 -->

An **inter intentlink** connects an intentnode in one IntentGraph to an intentnode in another (e.g. ProjectionIG → product). Full specification: `docs/intentlink_spec.md` §Inter.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `uid` | string | no | Derived from endpoints when omitted: `{src}_{dst}`. |
| `src` | string | **yes** | Graph-qualified endpoint: `graph_id:node_uid`. |
| `dst` | string | **yes** | Graph-qualified endpoint: `graph_id:node_uid`. |
| `intent` | string | **yes** | The cross-graph relationship asserted. |
| `shape` | object | no | Structured grounding, opaque at v0. |

- Stored in the graph that owns the relationship (conventionally the source graph), in the top-level `inter_intentlinks` list.
- `graph_id` must resolve through the project's `intent_resources.yaml` manifest; T3 extends across graphs via the manifest (endpoint graphs must be loadable and contain the node).
- **No refinement:** inter intentlinks have no `parent` field. Link refinement remains same-graph only.

---

## 6. IntentGraph Schema
<!-- Lines 498-511 -->

The container.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `meta` | object | no | Graph metadata. Recognized keys: `name`, `description`, `version`, `default_lens` (pointer into `lenses`), `intent_resources` (path to the project manifest for inter-graph UID resolution), `derived_from` (`{of, via_lens}` — marks a reduction). Keys starting with `_` are transient and stripped on save. |
| `nodes` | list[intentnode] | **yes** | All intentnodes. |
| `treearcs` | list[{parent, child}] | **yes** | Refinement tree edges. |
| `intentlinks` | list[intentlink] | **yes** | Semantic relation edges. |
| `inter_intentlinks` | list[inter_intentlink] | no | Links whose endpoints live in different graphs (see §5, "Inter intentlinks"). Stored in the source graph. |
| `lenses` | dict[name → LensConfig] | no | Named lens configurations (see §7). |

---

## 7. Lens Schema
<!-- Lines 514-530 -->

Two artifacts realize the lens concept (§2.5). Full specification: [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md).

**LensConfig** — a named view stored in the graph's `lenses` block. Pointers only, no node copies:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | **yes** | Lens name (also the `lenses` dict key). |
| `description` | string | no | What this view is for. |
| `target_uids` | list[string] | no | The focus nodes this lens was built around. |
| `nodes` | dict[uid → {lod, position?}] | **yes** | Included nodes with LOD (`skeleton`/`lean`/`full`) and optional display position. Ancestor-closed (C1). |
| `intentlinks` | list[string] | **yes** | Included intentlink UIDs. Both endpoints must be in `nodes` (C3). |

**Lens** (agent I/O) — a materialized full-tree view carrying node bodies plus a `lod` per node, produced by `lens build` and consumed/edited by agents. Its closure and visibility rules are the same; it exists so an agent can read and write intent without holding the whole graph.

---

## 8. Invariants
<!-- Lines 533-535 -->

Structural rules `IG` must satisfy at all times. Named T1–T5 per the roadmap.

### T1 — Tree property (tarcs)
<!-- Lines 538-546 -->

> All tarcs form a directed rooted tree.

1. Every inode has at most one parent: for all `n` in `inodes`, there is at most one `p` such that `tarc(p, n)` exists
2. Exactly one root: there is exactly one `r` in `inodes` where `parent(r)` = ⊥
3. No cycles: the tarc structure is acyclic

**When to check:** Every tarc add/remove/move operation.

### T2 — Lens closure
<!-- Lines 549-561 -->

> A lens is ancestor-closed over nodes and endpoint-closed over links.

1. **Ancestor completeness:** for all `n` ∈ `dom(L)`, `anc(n)` ⊆ `dom(L)` (C1).
2. **Link endpoints included:** every intentlink carried by `L` has both endpoints in `dom(L)` (C3).
3. **Referential validity:** every uid in `L` exists in the graph.

Consequence: `rep(L, n)` (the nearest included ancestor-or-self) is total for any non-empty lens, and hierarchy within a lens is always navigable.

Full closure contract (C1–C6): [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md) §6.

**When to check:** Every lens mutation (add/remove node, add/remove link, set LOD); load-time validation as a sanity belt.

### T3 — Intentlink well-formedness
<!-- Lines 564-572 -->

> Both endpoints of an ilink must exist in the graph. Ilinks carry metadata and are directed.

For all `ilink(u, v, m)` in `ilinks`: `u` ∈ `inodes` and `v` ∈ `inodes`.

**Refinement well-formedness:** If `ilink(a, b, m')` has parent `ilink(A, B, m)`, then `is_above(A, a)` and `is_above(B, b)`.

**When to check:** Every ilink create/modify, and every inode delete (must cascade or reject).

### T4 — Refinement coherence (meaning-stability)
<!-- Lines 575-587 -->

> Expanding an inode into children preserves the meaning of the parent.

This is the formalization of **P2**. Semi-formal statement:

- The union of children's intents must *cover* the parent's intent (no loss of meaning).
- No child may introduce intent that contradicts or extends beyond the parent's scope.
- The parent's intent, read alone, must remain a valid (if coarser) description of what its subtree does.

**Status:** Semi-formal. Human-judged for now. Machine-checkable criteria are an open research question (see §12, Q1).

**When to check:** After every refinement operation (add children to an inode). In practice: Critic agent responsibility.

### T5 — Lens closure under operations
<!-- Lines 590-603 -->

> Every lens operation on a valid lens yields a valid lens.

Consequence of T1 + T2, stated explicitly as a design requirement: the core library enforces closure **inside each mutation method** — invalid intermediate states are unrepresentable, and load-time validation exists only as a sanity belt (D6, [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md)).

Proof sketch:

- **add node:** adding `n` also adds `anc(n)` (C1 restores ancestor completeness).
- **remove node:** removing `n` also removes `desc(n)` ∩ `dom(L)` and purges links with a lost endpoint (C2 + C4).
- **add link:** rejected unless both endpoints ∈ `dom(L)` (C3).
- **set_lod:** membership unchanged, so closure is untouched (C6).

---

## 9. Operations Catalog
<!-- Lines 606-608 -->

For each operation: preconditions, effect, postconditions (invariant preservation).

### 9.1 — inode operations
<!-- Lines 611-611 -->

#### `inode_create(uid, name, intent, ...)`
<!-- Lines 614-618 -->

- **Pre:** `uid` not already in `inodes`.
- **Effect:** Add inode to `inodes`. Inode is initially unattached (no tarc). A tarc must be added to place it in the tree (unless it's ROOT).
- **Post:** T1 satisfied (once tarc added), T3 unaffected.

#### `inode_update(uid, fields...)`
<!-- Lines 621-625 -->

- **Pre:** `uid` ∈ `inodes`.
- **Effect:** Update fields on the inode.
- **Post:** T4 may be affected (check coherence with parent/children). All other invariants preserved.

#### `inode_delete(uid)`
<!-- Lines 628-632 -->

- **Pre:** `uid` ∈ `inodes`. Must be `is_leaf(uid)` OR deletion cascades to entire subtree.
- **Effect:** Remove inode (and subtree if cascading). Remove all tarcs and ilinks referencing deleted inodes. Purge deleted inodes from all lenses (C2/C4 cascade).
- **Post:** T1, T2, T3 preserved by cascade.

### 9.2 — tarc operations
<!-- Lines 635-635 -->

#### `tarc_attach(p, c)`
<!-- Lines 638-642 -->

- **Pre:** `p` ∈ `inodes`, `c` ∈ `inodes`. `parent(c)` = ⊥ (or `c` is being reparented). Attaching must not create a cycle: `c` ∉ `anc(p)`.
- **Effect:** Add `tarc(p, c)` to `tarcs`.
- **Post:** T1 preserved (no cycle, at most one parent).

#### `tarc_detach(p, c)`
<!-- Lines 645-649 -->

- **Pre:** `tarc(p, c)` exists in `tarcs`.
- **Effect:** Remove the tarc. `c` becomes unattached (must be reattached or deleted).
- **Post:** T1 preserved. T2: lenses containing `desc(c)` may need re-validation. T3: ilinks with refinement constraints may be affected.

### 9.3 — ilink operations
<!-- Lines 652-652 -->

#### `ilink_create(uid, u, v, m)`
<!-- Lines 655-659 -->

- **Pre:** `u` ∈ `inodes`, `v` ∈ `inodes`. If `m.parent` specified, the descendant-rule must hold. `uid` not already in `ilinks`.
- **Effect:** Add `ilink(u, v, m)` to `ilinks`.
- **Post:** T3 satisfied.

#### `ilink_update(uid, fields...)`
<!-- Lines 662-666 -->

- **Pre:** `uid` refers to existing ilink. If `u`/`v` change, new endpoints must exist and descendant-rule must hold for any child ilinks.
- **Effect:** Update fields.
- **Post:** T3 preserved.

#### `ilink_delete(uid)`
<!-- Lines 669-673 -->

- **Pre:** `uid` ∈ `ilinks`.
- **Effect:** Remove ilink. Child ilinks (where `m.parent` = `uid`) become orphans (parent field cleared, or also deleted — policy TBD).
- **Post:** T3 preserved.

### 9.4 — Lens operations
<!-- Lines 676-676 -->

#### `lens_add_node(L, n, ℓ)` → `L'`
<!-- Lines 679-683 -->

- **Pre:** `n` ∈ `inodes`. `ℓ` ∈ {skeleton, lean, full}.
- **Effect:** `dom(L')` = `dom(L)` ∪ {`n`} ∪ `anc(n)`; added ancestors default to `lean` (C1).
- **Post:** T2 satisfied.

#### `lens_remove_node(L, n)` → `L'`
<!-- Lines 686-690 -->

- **Pre:** `n` ∈ `dom(L)`.
- **Effect:** `dom(L')` = `dom(L)` \ ({`n`} ∪ `desc(n)`); links with a removed endpoint are purged (C2 + C4).
- **Post:** T2 satisfied.

#### `set_lod(L, n, ℓ)` → `L'`
<!-- Lines 693-697 -->

- **Pre:** `n` ∈ `dom(L)`.
- **Effect:** LOD of `n` becomes `ℓ`; membership unchanged.
- **Post:** T2 trivially satisfied (C6).

#### `lens_add_link(L, e)` / `lens_remove_link(L, e)` → `L'`
<!-- Lines 700-708 -->

- **Pre (add):** both endpoints of `e` ∈ `dom(L)` (C3). **Pre (remove):** `e` ∈ `L` (unconstrained otherwise, C5).
- **Effect:** link set updated.
- **Post:** T2 satisfied.

`expand` and `prune` (§3.2) are derived operations — sequences of `lens_add_node` / `lens_remove_node` over a node's children or descendants.

---

## 10. Ilink Lifting & Projection
<!-- Lines 711-713 -->

How ilinks behave when viewed through a lens. Consolidates `docs/intentlink_spec.md` §3–4 and `rules.md` §ilink visibility.

### 10.1 — Visibility rule
<!-- Lines 716-720 -->

An `ilink(u, v, m)` is **directly visible** at lens `L` iff `u` ∈ `dom(L)` and `v` ∈ `dom(L)`.

LOD refines visibility: the link is **rendered** when both endpoints are at `lean` or above; its `intent` description is shown when at least one endpoint is at `full`.

### 10.2 — Projection (lifting)
<!-- Lines 723-731 -->

For any canonical `ilink(u, v, m)`, its **projected display link** at lens `L` is:

`rep(L, u)` → `rep(L, v)`

where `rep(L, n)` is the nearest ancestor-or-self of `n` in `dom(L)` — total for any non-empty lens (T2).

**Note:** If `rep(L, u)` = `rep(L, v)`, the ilink is **internal** to a single lens node and is hidden (it connects descendants within the same pruned subtree).

### 10.3 — Dominance / de-cluttering
<!-- Lines 734-741 -->

When both a coarse parent ilink and its refined child ilinks have projections at the current lens:

- Prefer the **most refined available** canonical ilinks whose projections are meaningful.
- Suppress coarse parent ilinks when their refined descendants already cover the same projected endpoints.

(Informally: don't show both `E_T` and a set of refined ilinks that "cover" it.)

### 10.4 — Aggregation (display-level only)
<!-- Lines 744-751 -->

When multiple canonical ilinks project to the same displayed endpoints, the UI may:

- Show them as separate parallel displayed links, or
- Merge them into one displayed link with grouped child descriptions.

This is a **visualization** choice — it does not create canonical ilinks.

### 10.5 — No cross-product maintenance
<!-- Lines 754-756 -->

Authors must NOT maintain mixed-level variants (`E.1.1_T`, `E_T.1.1`, etc.). These are produced by projection as needed. Only canonical ilinks at their natural level are authored.

### 10.6 — The core guarantee
<!-- Lines 759-765 -->

> Any ilink between two inodes has a representation at any lens that covers both inodes' subtrees.

This is the "no disappearing relationships" property — the fundamental reason lifting exists.

---

## 11. Epistemic State
<!-- Lines 768-772 -->

Every intentnode may carry an `epistemic_state` — a free-text field describing what is known, uncertain, risky, or deferred about this node. This makes uncertainty a first-class structural property rather than something hidden or forbidden.

**This is not an enum.** Real epistemic states are nuanced — "we're fairly confident about the happy path but the error handling is speculative and the performance implications are unknown" is a valid and useful epistemic state. Authors should write what is true, not squeeze reality into a label.

### Recommended vocabulary
<!-- Lines 775-789 -->

The following terms are useful building blocks for epistemic state descriptions, not a closed set:

| Term | Meaning |
|------|---------|
| known | This aspect is well-understood and stable. |
| constrained | Some boundaries are set, but the full picture is not resolved. |
| undecided | Multiple viable options exist; no decision made yet. |
| risky | A decision has been made but carries identified risks. |
| deferred | Deliberately postponed — will be addressed later. |
| speculative | A best guess; low confidence. |
| inherited | Assumed from parent node or context; not independently validated. |

These can be combined, qualified, and nuanced: "Undecided between X and Y — leaning toward X because of Z, but need to validate performance." That sentence is more useful than the label `undecided`.

### Implications for tooling
<!-- Lines 792-798 -->

- **Agents** should parse epistemic state text to assess confidence before generating from a node. A node with clear uncertainty signals should be surfaced for elicitation, not silently generated from.
- **Propagation heuristic:** A parent node's epistemic state should reflect the least-resolved state among its children. This is guidance, not an invariant — the parent's author decides how to summarize.
- **If omitted:** The node's epistemic state is unassessed (not "known" — absence of annotation is not the same as confidence).

---

## 12. Open Questions
<!-- Lines 801-815 -->

Carried forward from the roadmap, scoped to formalism.

**Q1 — Refinement coherence (T4):** Can meaning-stability be formalized enough to be machine-checkable, or does it stay semi-formal / human-judged? Candidate approaches: (a) require parent.intent to be derivable as a summary of children.intent via an LLM judge, (b) define coverage heuristics (keywords, constraint subsumption), (c) leave it to the Critic agent with structured rubric.

**Q2 — Intentlink aggregation semantics:** When multiple links project to the same lens endpoints, what are the exact merging rules? Union of intents? Weighted by type? Type-dependent aggregation? Current answer: display-level choice (§10.4), but may need tighter semantics for agent consumption.

**Q3 — (Resolved by lens ancestor closure.)** The former "partial frontier `rep_F` undefined" question is moot: lens membership is ancestor-closed (T2), so `rep(L, n)` is total for any non-empty lens.

**Q4 — ProjectionIG depth for v1:** How deep should a ProjectionIG go initially? A shallow 2-level kickstart template (root + decision-point children with `undecided` epistemic state) may suffice for bootstrapping, with deeper refinement driven by the Elicitor/Critic loop during use. Scoped directives (subtree-level within the ProjectionIG) with product-intentnode-level override remain the current direction for conflict resolution.

**Q5 — Self-loop under projection:** When `rep(L, u) = rep(L, v)`, the projected link is a self-loop on a single lens node. Currently hidden. Should it be surfaceable on demand (e.g. "show internal dependencies of this pruned node")?

---

## Appendix A — Source Traceability
<!-- Lines 818-834 -->

Where each section's content originates:

| Section | Primary source(s) |
|---------|--------------------|
| §1 Principles | `docs/project_definition.md` |
| §2 Vocabulary | `docs/rules.md` (§Terms), `docs/project_definition.md`, `README.md` (§Core Concepts). §2.7 revised: "style graph" → ProjectionIG (full IntentGraph for projection-specific intent). |
| §3 Notation | New — formalizing implicit usage from `rules.md` and `docs/intentlink_spec.md` |
| §4 Node schema | `schema/intentnode.v0.yaml` + `ROADMAP.md` (WP-0.2.1) |
| §5 Intentlink schema | `schema/intentlink.v0.yaml` + `docs/intentlink_spec.md` |
| §6 IntentGraph schema | `schema/intentgraph.v0.yaml` |
| §7 Lens schema | `LENS_REDESIGN_SPEC.md` |
| §8 Invariants | `docs/rules.md` (§Invariants) + `ROADMAP.md` (WP-0.2.2) |
| §9 Operations | `docs/rules.md` (§Operations) + `ROADMAP.md` (WP-0.2.3) |
| §10 Lifting | `docs/rules.md` (§intentlink visibility) + `docs/intentlink_spec.md` (§3–4) |
| §11 Epistemic state | `ROADMAP.md` (WP-0.2.1) |
| §12 Open questions | `ROADMAP.md` (§Open questions) + new questions from formalization |
