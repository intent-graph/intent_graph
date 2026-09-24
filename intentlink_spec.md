## intentlink spec (v0)

### Purpose

An **intentlink** is a directed, valued relation between two **intentnodes**. It states what must be true *between* those nodes (data, dependency, constraint propagation, compatibility, inheritance/conformance, coordination, etc.). intentlinks are refinable across levels of detail while avoiding cross-product explosion under mixed lenses.

---

## 1) Payload

### Fields

* **`intent`** *(required)*: one sentence describing the relationship asserted between `src` and `dst`.
* **`shape`** *(optional)*: structured grounding/constraints for that relationship (e.g., interface/schema/protocol/signature/examples/invariants). Tools may treat this as opaque at v0.

### Non-duplication rule (boundary with node intent)

* **intentnode.intent** describes the node’s responsibility/role (“within the node”).
* **intentlink.intent** describes the contract/relation between nodes (“between nodes”).
* Refinement adds precision; it must not change the asserted relationship category.

---

## 2) Refinement of intentlinks (LOD behavior)

### 2.1 Canonical vs displayed links

* **Canonical intentlinks** are authored/stored in the IntentGraph.
* **Displayed intentlinks** may be generated on the fly for a given **lens** (projection).

### 2.2 Link refinement relation

An intentlink may be refined into child intentlinks:

* Each link may have **0..N refined children**.
* Each refined child has **exactly 1 parent link** (a tree/forest of links).
* Link refinement is explicit (cannot be inferred from IDs).

**Endpoint constraint (descendant rule)**
If a parent link is `A → B`, any refined child link must connect descendants of those endpoints:

* `A.{1}+ → B.{1}+`
  (i.e., `src_child` is a descendant of `A`, and `dst_child` is a descendant of `B` under `treearc`.)

This expresses: refinement increases precision *inside the regions* represented by the endpoints.

---

## 3) Lens behavior (mixed detail without explosion)

### 3.1 Projection (generated display artifacts)

Given a **lens** `L`, define `rep(L, x)` as the nearest ancestor-or-self of `x` in `dom(L)` (the node set included in `L`). Lens membership is ancestor-closed (T2), so `rep(L, x)` is total for any non-empty lens.

For any canonical intentlink `u → v`, its **projected display link** is:

* `rep(L, u) → rep(L, v)`

This projection is generated on the fly; it is not a canonical intentlink. If `rep(L, u) = rep(L, v)`, the intentlink is internal to a single lens node and is hidden.

### 3.2 Dominance / de-cluttering rule

To avoid showing coarse links when finer ones are relevant:

* Prefer the **most refined available** canonical links whose projections are meaningful at the current lens.
* Coarser parent links are **suppressed** when their refined descendants are already represented in the displayed set for the same projected endpoints.

(Informally: don’t show both `A→B` and a set of refined links that “cover” it at the current lens.)

### 3.3 No cross-product maintenance rule

Authors must *not* maintain mixed-level variants such as:

* `A.1.1 → B`, `A → B.1.1`, `A.1.1 → B.1`, etc.

Those are produced by projection as needed for a specific lens.

---

## 3.4 Inter intentlinks

An **inter intentlink** connects an intentnode in one IntentGraph to an intentnode in another (e.g. ProjectionIG → product). Endpoints are **graph-qualified** (Option A): `src` and `dst` are strings of the form `graph_id:node_uid`. The link is stored in the graph file in a top-level list `inter_intentlinks`; the graph that owns the link is conventionally the source of the relationship. `graph_id` must match an id in the project's **intent_resources.yaml**. The existence invariant (T3) extends to inter intentlinks: for each endpoint `(graph_id, node_uid)`, that graph must be loadable via the manifest and contain a node with that uid. Refinement (parent/child link) remains **same-graph only**; inter intentlinks do not participate in link refinement.

---

## 4) Aggregation and merging (display-level only)

When multiple canonical links project to the same displayed endpoints at a lens, the UI/tool may:

* show them as separate parallel displayed links, or
* merge them into one displayed link with grouped children (tooling choice).

This aggregation is a visualization/convenience layer; it does not require additional canonical links.

---

## 5) Minimal canonical representation (shape-agnostic)

A canonical intentlink contains at minimum:

* `uid`
* `src` (intentnode uid)
* `dst` (intentnode uid)
* `intent`
* optional `shape`
* optional `parent` (for refined links)

Displayed links do not require stable IDs; they are ephemeral and derived from `(canonical_link_uid, lens)` via projection.
