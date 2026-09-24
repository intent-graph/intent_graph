# Lens Redesign Specification — IG Core

Formal specification for the internal-lens redesign. Replaces the rejected v1 design
(external `*.lens.yaml` files with bundled node bodies).

## Table of Contents

1. [1. Why This Redesign Exists](#1-why-this-redesign-exists) _(Lines 79-102)_
1. [2. Core Decisions](#2-core-decisions) _(Lines 105-105)_
   1. [D1 — One Lens concept, one in-memory model](#d1--one-lens-concept-one-in-memory-model) _(Lines 108-112)_
   1. [D2 — External lens file format dropped](#d2--external-lens-file-format-dropped) _(Lines 115-118)_
   1. [D3 — Internal lens = LensConfig inside the IG file](#d3--internal-lens--lensconfig-inside-the-ig-file) _(Lines 121-125)_
   1. [D4 — LensConfig shape (final)](#d4--lensconfig-shape-final) _(Lines 128-137)_
   1. [D5 — LOD vocabulary: three levels](#d5--lod-vocabulary-three-levels) _(Lines 140-144)_
   1. [D6 — Closure enforced by every API method](#d6--closure-enforced-by-every-api-method) _(Lines 147-150)_
   1. [D7 — IntentGraph.lenses at top level](#d7--intentgraphlenses-at-top-level) _(Lines 153-156)_
   1. [D8 — meta.default_lens pointer](#d8--metadefault_lens-pointer) _(Lines 159-162)_
   1. [D9 — meta.intent_resources pointer](#d9--metaintent_resources-pointer) _(Lines 165-169)_
   1. [D10 — meta.derived_from marker](#d10--metaderived_from-marker) _(Lines 172-177)_
   1. [D11 — ig-tool lens subcommand surface (see §8 for full spec)](#d11--ig-tool-lens-subcommand-surface-see-8-for-full-spec) _(Lines 180-184)_
   1. [D12 — Validation extensions](#d12--validation-extensions) _(Lines 187-189)_
   1. [D13 — Viewer robustness](#d13--viewer-robustness) _(Lines 192-195)_
   1. [D14 — Default lens application](#d14--default-lens-application) _(Lines 198-201)_
   1. [D15 — Lens switching in viewer](#d15--lens-switching-in-viewer) _(Lines 204-206)_
   1. [D16 — No viewport in lens](#d16--no-viewport-in-lens) _(Lines 209-213)_
1. [3. Vocabulary](#3-vocabulary) _(Lines 216-265)_
1. [4. LensConfig Pydantic Model](#4-lensconfig-pydantic-model) _(Lines 268-271)_
   1. [Field specification](#field-specification) _(Lines 274-340)_
   1. [Serialization (YAML example)](#serialization-yaml-example) _(Lines 343-365)_
   1. [Serialization (JSON example)](#serialization-json-example) _(Lines 368-387)_
   1. [Wire format notes](#wire-format-notes) _(Lines 390-400)_
1. [4.1 Position Semantics](#41-position-semantics) _(Lines 403-423)_
1. [5. IntentGraph Schema Additions](#5-intentgraph-schema-additions) _(Lines 426-429)_
   1. [5.1 IntentGraph.lenses](#51-intentgraphlenses) _(Lines 432-455)_
   1. [5.2 meta.default_lens](#52-metadefault_lens) _(Lines 458-463)_
   1. [5.3 meta.intent_resources](#53-metaintent_resources) _(Lines 466-472)_
   1. [5.4 meta.derived_from](#54-metaderived_from) _(Lines 475-493)_
1. [6. Closure Invariants and API Contract](#6-closure-invariants-and-api-contract) _(Lines 496-499)_
   1. [C1 — Ancestor completeness (node add)](#c1--ancestor-completeness-node-add) _(Lines 502-509)_
   1. [C2 — Descendant purge (node remove)](#c2--descendant-purge-node-remove) _(Lines 512-519)_
   1. [C3 — Link endpoint check (link add)](#c3--link-endpoint-check-link-add) _(Lines 522-529)_
   1. [C4 — Link purge on node remove (automatic)](#c4--link-purge-on-node-remove-automatic) _(Lines 532-537)_
   1. [C5 — Link remove is unconstrained](#c5--link-remove-is-unconstrained) _(Lines 540-543)_
   1. [C6 — set_lod is structural-invariant-preserving](#c6--set_lod-is-structural-invariant-preserving) _(Lines 546-550)_
   1. [Summary table](#summary-table) _(Lines 553-563)_
1. [7. Validation Rules](#7-validation-rules) _(Lines 566-597)_
1. [8. ig-tool lens Subcommand Surface](#8-ig-tool-lens-subcommand-surface) _(Lines 600-604)_
   1. [New subcommands (internal lens management)](#new-subcommands-internal-lens-management) _(Lines 607-650)_
   1. [Migration of legacy ig-tool lens commands](#migration-of-legacy-ig-tool-lens-commands) _(Lines 653-680)_
1. [9. Reduced IG (Derived) Format](#9-reduced-ig-derived-format) _(Lines 683-687)_
   1. [Shape](#shape) _(Lines 690-730)_
   1. [Validation treatment](#validation-treatment) _(Lines 733-739)_
   1. [Round-trip: project → reintegrate](#round-trip-project--reintegrate) _(Lines 742-762)_
1. [10. Cross-IG References in Lenses](#10-cross-ig-references-in-lenses) _(Lines 765-768)_
   1. [Resolution rules](#resolution-rules) _(Lines 771-778)_
   1. [Validation rules (cross-IG)](#validation-rules-cross-ig) _(Lines 781-787)_
   1. [Scope note](#scope-note) _(Lines 790-796)_
1. [11. Migration Plan for Existing Lens Model](#11-migration-plan-for-existing-lens-model) _(Lines 799-799)_
   1. [What survives unchanged](#what-survives-unchanged) _(Lines 802-810)_
   1. [New additions](#new-additions) _(Lines 813-828)_
   1. [What gets removed](#what-gets-removed) _(Lines 831-836)_
   1. [Import sites that change](#import-sites-that-change) _(Lines 839-845)_
   1. [Extension-side removal](#extension-side-removal) _(Lines 848-854)_
1. [12. Acceptance Criteria](#12-acceptance-criteria) _(Lines 857-859)_
   1. [Schema and models](#schema-and-models) _(Lines 862-869)_
   1. [Closure](#closure) _(Lines 872-879)_
   1. [Validation](#validation) _(Lines 882-890)_
   1. [CLI](#cli) _(Lines 893-902)_
   1. [Serialization round-trip](#serialization-round-trip) _(Lines 905-910)_
1. [13. Out of Scope](#13-out-of-scope) _(Lines 913-930)_
1. [14. Risks and Mitigations](#14-risks-and-mitigations) _(Lines 933-941)_



---

## 1. Why This Redesign Exists
<!-- Lines 79-102 -->

The v1 implementation introduced `*.lens.yaml` sibling files for named views. The user
rejected it on four grounds:

**B1 — Schema conflation.** The v1 reused the IG core `Lens` schema (designed for agent I/O)
as a display-state format. Because `IntentNode.intent` is required, the extension had to inject
`'[no intent]'` placeholders to satisfy Pydantic — a structural workaround, not a solution.

**B2/B3 — ig-tool blind spot.** `ig-tool validate` could not validate lens files; `ig-tool lens`
commands could not consume them. Named views were orphaned from the tooling ecosystem.

**B4 — Data duplication.** Each `*.lens.yaml` file carried full or stub node bodies. Three lenses
for a 200-node IG = three copies of 200 node stubs, going stale silently on every edit.

**B5/B9 — No discovery, no agent visibility.** No `ig-tool lens list`, no way for an agent to
enumerate views without filesystem scanning, workspaceState invisible to agents.

The redesign eliminates the external file format and moves lens configuration into the IG file
itself as a `lenses` dictionary (`LensConfig` objects) — UIDs and LOD pointers only, no node
body copies. The agent-I/O `Lens` object (full node bodies, diff tracking, budget) is preserved
unchanged for workflow use.

---

## 2. Core Decisions
<!-- Lines 105-105 -->

### D1 — One Lens concept, one in-memory model
<!-- Lines 108-112 -->

The `Lens` class in `models/lens.py` is the single in-memory model for agent I/O. It is not
reused for view configuration. `LensConfig` is a new, separate, lightweight model that records
*which nodes are displayed at what LOD* — without any node body copies.

### D2 — External lens file format dropped
<!-- Lines 115-118 -->

The `*.lens.yaml` sibling file format is removed. The `serial/lens_file.py` module (load/save
for the full `Lens` object) is unchanged and continues to serve agent workflows.

### D3 — Internal lens = LensConfig inside the IG file
<!-- Lines 121-125 -->

An **internal lens** is a `LensConfig` stored in the `lenses` dict at the top level of an IG
file. It is authoritative. The IG file is always the source of truth; `LensConfig` carries
pointers (UIDs), not deep copies.

### D4 — LensConfig shape (final)
<!-- Lines 128-137 -->

`LensConfig` has exactly these fields (see §4 for full Pydantic spec):
- `name` — required str (redundant with the dict key; kept for self-documentation)
- `description` — optional str
- `target_uids` — optional `list[str]`, default `[]`; replaces the old singleton `target_uid`
- `nodes` — required `dict[str, LensNodeEntry]` where `LensNodeEntry = {lod: lod_str, position?: {x: float, y: float}}`
- `intentlinks` — required `list[str]` of intentlink UIDs

Dropped from `LensMeta`: `budget`, `scope_root`, `source_graph`.

### D5 — LOD vocabulary: three levels
<!-- Lines 140-144 -->

`skeleton | lean | full`. The viewer renders `skeleton` and `lean` identically (canvas name only)
for now; `full` triggers the HTML overlay. The distinction is preserved for future finer rendering.
Defined in the existing `LOD` enum (`models/lens.py:24`).

### D6 — Closure enforced by every API method
<!-- Lines 147-150 -->

The `LensConfig` class (or a companion `LensConfigManager`) enforces structural invariants on
every mutation. Validation at load time is a sanity belt only. See §6.

### D7 — IntentGraph.lenses at top level
<!-- Lines 153-156 -->

`IntentGraph` gains a `lenses: dict[str, LensConfig]` attribute, optional, default empty dict.
Serialized as a top-level `lenses:` key in the IG file. Deserialized by `dict_to_graph`.

### D8 — meta.default_lens pointer
<!-- Lines 159-162 -->

`meta.default_lens: str | None` — a pointer into `lenses`. If set, must reference an existing
key. Validated at load time. Viewer applies it immediately on open.

### D9 — meta.intent_resources pointer
<!-- Lines 165-169 -->

`meta.intent_resources: str | None` — optional path to a project's `intent_resources.yaml`.
When present, qualified UIDs (`graph_id:uid`) in lens node/link lists resolve through it.
When absent, only local UIDs are valid.

### D10 — meta.derived_from marker
<!-- Lines 172-177 -->

`meta.derived_from: {of: str, via_lens: str} | None` — marks an IG file as a *reduction*.
- `of` — path or graph_id of the parent IG.
- `via_lens` — name of the parent's lens that produced this reduction.
Absence means primary IG. Presence means derived IG. See §9.

### D11 — ig-tool lens subcommand surface (see §8 for full spec)
<!-- Lines 180-184 -->

Complete rewrite of `ig-tool lens`. New subcommands: `list`, `show`, `create`, `delete`,
`add-node`, `remove-node`, `set-lod`, `add-link`, `remove-link`, `set-default`,
`unset-default`, `project`, `reintegrate`, `validate`. Legacy subcommands migrated or dropped.

### D12 — Validation extensions
<!-- Lines 187-189 -->

Seven new checks added to `ig-tool validate` for lens consistency. See §7.

### D13 — Viewer robustness
<!-- Lines 192-195 -->

Extension never refuses to render due to stale UIDs. Unknown UIDs in a lens produce webview
diagnostics (level/uid/message), dismissable, cleared on next lens load.

### D14 — Default lens application
<!-- Lines 198-201 -->

On viewer open, if `meta.default_lens` is set, apply that lens immediately. Otherwise show
default LOD state (everything at lean-equivalent).

### D15 — Lens switching in viewer
<!-- Lines 204-206 -->

`intentgraph.openLens` quickpick enumerates `lenses` from the loaded IG (no file picker).

### D16 — No viewport in lens
<!-- Lines 209-213 -->

Pan/zoom stays in `workspaceState` as ephemeral, not in any `LensConfig`.

---

## 3. Vocabulary
<!-- Lines 216-265 -->

**IntentGraph (IG)** — The canonical artifact `(nodes, treearcs, intentlinks)`. Code is a
projection; the IG is the source of truth. Defined in
[VOCABULARY_AND_FORMALISM.md](VOCABULARY_AND_FORMALISM.md) and [SERIALIZATION_FORMAT.md §1](SERIALIZATION_FORMAT.md).

**internal lens** — A `LensConfig` stored inside an IG file under `lenses[name]`. It is
authoritative: it records which nodes are displayed at what LOD, and which intentlinks are
explicitly included. It does not carry node bodies.

**LensConfig** — The Pydantic model representing an internal lens. Fields: `name`,
`description`, `target_uids`, `nodes`, `intentlinks`. See §4.

**agent Lens** — The existing `Lens` class in `models/lens.py`. Full node bodies + diff
tracking + budget. Used for agent I/O workflows. NOT used for view configuration. Unchanged
by this redesign.

**displayed node** — A node whose UID appears in `LensConfig.nodes`. The value is a
`LensNodeEntry` carrying `lod` and an optional `position`.

**displayed link** — An intentlink whose UID appears in `LensConfig.intentlinks`. Closure
requires both endpoints to be displayed nodes.

**closure** — The structural invariant that a `LensConfig` is self-consistent: every displayed
node's ancestors are also displayed nodes; every displayed link's endpoints are displayed nodes.
Closure is enforced by API methods (§6) and verified by validation (§7).

**LOD** — Level of Detail. Three values: `skeleton` (uid+name only), `lean` (+intent
+epistemic_state), `full` (all fields + overlay). Defined in `LOD` enum at
`models/lens.py:24`. In `LensConfig`, LOD is stored as `nodes[uid].lod` (a `LensNodeEntry`
field). See §4 for the full `LensNodeEntry` shape.

**pinned node** — A displayed node whose `LensNodeEntry.position` is not `None`. Its position
is stored explicitly in the lens; the layout engine respects it. Contrast with an unpinned
node, where `position` is absent and ELK places the node freely.

**target_uids** — Optional list of focus-node UIDs in a `LensConfig`. Hints for the viewer
about which nodes are the "primary focus". Does not gate rendering.

**primary IG** — An IG file without `meta.derived_from`. The authoritative source.

**reduction** (also: **derived IG**) — An IG file with `meta.derived_from` set. Contains only
the subset of nodes/links referenced by a specific lens of the parent IG. Validates as a real
IG (same schema, relaxed orphan check). Produced by `ig-tool lens project`.

**reintegration** — Writing changes from a reduction back to the parent IG. Performed by
`ig-tool lens reintegrate`. Phase-1 scope: content edits, new nodes (with parent), new/edited
links. No structural changes. See §9.

---

## 4. LensConfig Pydantic Model
<!-- Lines 268-271 -->

`LensConfig` is a new model, separate from `Lens` and `LensMeta`. It lives in
`models/lens_config.py` (new file) and is imported by `models/__init__.py`.

### Field specification
<!-- Lines 274-340 -->

```python
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

LOD_LITERAL = Literal["skeleton", "lean", "full"]


class Position(BaseModel):
    """Cytoscape node center position, parent-relative.

    Coordinate frame: parent-relative (x, y) offset from parent top-left.
    Stores Cytoscape node CENTER (MVP choice; see §4.1 for rationale).
    ROOT position is implicit (0, 0) and never stored.
    None on LensNodeEntry means unpinned (ELK places the node freely).

    PIG: LENSSCHEMA.NODESHAPE
    """

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class LensNodeEntry(BaseModel):
    """Per-node entry in LensConfig.nodes.

    Carries lod and optional position together so the lens is the sole store
    for all user-decidable visual state.

    PIG: LENSSCHEMA.NODESHAPE
    """

    lod: LOD_LITERAL
    position: Optional[Position] = None


class LensConfig(BaseModel):
    """Internal lens configuration stored inside an IG file.

    Carries pointers (UIDs + LOD assignments) only — no node body copies.
    Closure invariants: every node's ancestors are in nodes; every link's
    endpoints are in nodes. Enforced by API methods; verified by validation.
    """
    # Self-documenting identity (same as the dict key)
    name: str                        # required; non-empty
    description: str | None = None   # optional

    # Focus hints — list of UIDs the viewer should treat as primary focus.
    # Empty list = no specific focus.
    target_uids: list[str] = Field(default_factory=list)

    # Core display config: uid → LensNodeEntry (lod + optional position)
    nodes: dict[str, LensNodeEntry] = Field(default_factory=dict)

    # Explicit intentlink inclusion list (UIDs)
    intentlinks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def name_must_be_nonempty(self) -> "LensConfig":
        if not self.name or not self.name.strip():
            raise ValueError("LensConfig.name must be a non-empty string")
        return self
```

### Serialization (YAML example)
<!-- Lines 343-365 -->

```yaml
lenses:
  auth-flow:
    name: auth-flow
    description: "Authentication data path"
    target_uids:
      - AUTH.1
    nodes:
      ROOT:
        lod: skeleton
      AUTH:
        lod: lean
      AUTH.1:
        lod: full
        position: {x: 120.0, y: 80.0}
      AUTH.1.1:
        lod: full
    intentlinks:
      - AUTH.1_AUTH.1.1
      - AUTH_VALIDATE
```

### Serialization (JSON example)
<!-- Lines 368-387 -->

```json
{
  "lenses": {
    "auth-flow": {
      "name": "auth-flow",
      "description": "Authentication data path",
      "target_uids": ["AUTH.1"],
      "nodes": {
        "ROOT":    {"lod": "skeleton"},
        "AUTH":    {"lod": "lean"},
        "AUTH.1":  {"lod": "full", "position": {"x": 120.0, "y": 80.0}},
        "AUTH.1.1":{"lod": "full"}
      },
      "intentlinks": ["AUTH.1_AUTH.1.1", "AUTH_VALIDATE"]
    }
  }
}
```

### Wire format notes
<!-- Lines 390-400 -->

- `nodes` is a `dict[uid, LensNodeEntry]` — each entry is a sub-object with a required
  `lod` key and an optional `position` key.
- When `position` is `None`, the key is **omitted** from the serialized output (not written
  as `null`). See §4.1 for the omission rule.
- `intentlinks` is a flat list of link UIDs.
- All omission rules from [SERIALIZATION_FORMAT.md §4](SERIALIZATION_FORMAT.md) apply:
  empty `target_uids`, empty `intentlinks`, and null `description` are omitted when serializing.

---

## 4.1 Position Semantics
<!-- Lines 403-423 -->

Position is stored as a `{x: float, y: float}` object on a `LensNodeEntry`. When absent
(`None`), the node is **unpinned** — the layout engine (ELK) places it freely.

**Coordinate frame:** parent-relative. `(x, y)` is the offset from the parent node's
top-left corner. ROOT's position is always implicit `(0, 0)` and is never stored.

**Center vs. top-left (MVP decision):** Position stores the Cytoscape node CENTER,
not its top-left corner. This matches Cytoscape's `node.position()` API and simplifies
the vscode_viewer drag handler. Conversion to top-left (for pixel-perfect layout
integration) is deferred to Phase 2.

**Omission rule:** When `LensNodeEntry.position` is `None`, the `position` key is
absent from the serialized YAML/JSON output. Reading code must treat a missing `position`
key as `None` (unpinned), not as an error.

**PIG references:** `LENSSCHEMA.NODESHAPE` (shape definition), `LENSSCHEMA.VALIDATION`
(validation rules V-POS1, V-POS2 — see §7).

---

## 5. IntentGraph Schema Additions
<!-- Lines 426-429 -->

All additions land in `models/graph.py` (runtime attributes) and `serial/json_yaml.py`
(serialization/deserialization).

### 5.1 IntentGraph.lenses
<!-- Lines 432-455 -->

**Type:** `dict[str, LensConfig]`
**Default:** `{}` (empty dict)
**Location (runtime):** `IntentGraph.lenses` attribute, set in `IntentGraph.__init__`
**Location (serial):** top-level `lenses:` key in `.ig.yaml` / `.ig.json`

Serialized by `graph_to_dict` as a plain dict: `{name: config.model_dump(exclude_defaults=True)}`.
Deserialized by `dict_to_graph` via `LensConfig.model_validate`.

```yaml
# Example IG file (partial)
meta:
  name: "Auth System"
  default_lens: auth-flow
nodes: [...]
treearcs: [...]
intentlinks: [...]
lenses:
  auth-flow:
    name: auth-flow
    nodes: {ROOT: skeleton, AUTH: lean, AUTH.1: full}
    intentlinks: [AUTH.1_AUTH.1.1]
```

### 5.2 meta.default_lens
<!-- Lines 458-463 -->

**Type:** `str | None`
**Location:** `graph.meta["default_lens"]` (stored in the free-form meta dict)
**Validation:** if set, must be a key in `graph.lenses`
**Effect:** viewer applies this lens on open

### 5.3 meta.intent_resources
<!-- Lines 466-472 -->

**Type:** `str | None`
**Location:** `graph.meta["intent_resources"]`
**Validation:** if set and the file does not exist on load, emit a warning (not error); cross-IG
lens UIDs are flagged as unresolvable if the manifest cannot be loaded.
**Effect:** enables qualified UIDs (`graph_id:uid`) in `LensConfig.nodes` and `intentlinks`

### 5.4 meta.derived_from
<!-- Lines 475-493 -->

**Type:** `{of: str, via_lens: str} | None`
**Location:** `graph.meta["derived_from"]` as a dict with keys `of` and `via_lens`
**Validation rules (see §7):**
- `of` must be a non-empty string (path or graph_id)
- `via_lens` must be a non-empty string and must match a lens name in the IG's own `lenses`
- Every node in the IG must be referenced by the `via_lens` lens's `nodes` dict
- Orphan check is relaxed: nodes in a derived IG whose dot-path parent is absent are allowed

```yaml
meta:
  name: "Auth System — reduced"
  derived_from:
    of: "../auth_system.ig.yaml"
    via_lens: auth-flow
```

---

## 6. Closure Invariants and API Contract
<!-- Lines 496-499 -->

Closure is the invariant that a `LensConfig` remains structurally valid. Every mutation method
enforces closure proactively. Validation (§7) is the post-hoc safety belt.

### C1 — Ancestor completeness (node add)
<!-- Lines 502-509 -->

**Invariant:** For every displayed node `U`, all ancestors of `U` must also be displayed nodes.
**Enforcement:** When adding node `U` via `add_node(uid, lod, graph)`:
- Precondition: `uid` exists in `graph`; `lod` is a valid LOD string.
- Action: compute `graph.anc(uid)`. For each ancestor not yet in `lens.nodes`, insert it at
  default LOD `"skeleton"`.
- Postcondition: `lens.nodes[uid] = lod`; all ancestors of `uid` are in `lens.nodes`.

### C2 — Descendant purge (node remove)
<!-- Lines 512-519 -->

**Invariant:** When node `U` is removed, no descendant of `U` may remain displayed.
**Enforcement:** When removing node `U` via `remove_node(uid, graph)`:
- Precondition: `uid` in `lens.nodes`.
- Action: compute `graph.desc(uid)`. Remove `uid` and every descendant in `lens.nodes`.
  For each removed node, remove all intentlinks in `lens.intentlinks` that touch it.
- Postcondition: `uid` and all its descendants absent from `lens.nodes`; no stale links.

### C3 — Link endpoint check (link add)
<!-- Lines 522-529 -->

**Invariant:** Both endpoints of an intentlink must be displayed nodes.
**Enforcement:** When adding link `link_uid` via `add_link(link_uid, graph)`:
- Precondition: `link_uid` exists in `graph.links` (intra) or `graph.inter_links` (inter).
  Retrieve `src` and `dst` from the graph. Both must be in `lens.nodes`. If not: raise
  `ClosureViolation("Cannot add link: endpoint {uid} not in lens. Add the node first.")`.
- Postcondition: `link_uid` in `lens.intentlinks`.

### C4 — Link purge on node remove (automatic)
<!-- Lines 532-537 -->

**Invariant:** A link is removed when any of its endpoints is removed.
**Enforcement:** Covered by C2. When `remove_node` computes nodes to remove, it also removes
every `intentlinks` entry whose `src` or `dst` (local uid for intra, or the local part of the
qualified uid for inter) is in the removed set.

### C5 — Link remove is unconstrained
<!-- Lines 540-543 -->

**Invariant:** Removing an intentlink from the lens has no structural side-effects.
**Enforcement:** `remove_link(link_uid)` removes from `lens.intentlinks`. No closure check needed.

### C6 — set_lod is structural-invariant-preserving
<!-- Lines 546-550 -->

**Invariant:** LOD changes do not affect closure (which nodes are present is unchanged).
**Enforcement:** `set_lod(uid, lod)` requires `uid` in `lens.nodes`. Sets the value. No ancestor
or descendant changes. No link changes.

### Summary table
<!-- Lines 553-563 -->

| API method | Closure rules applied | Graph ref required? |
|---|---|---|
| `add_node(uid, lod, graph)` | C1 (ancestor fill) | Yes |
| `remove_node(uid, graph)` | C2 (descendant purge), C4 (link purge) | Yes |
| `set_lod(uid, lod)` | C6 (node-only; no structural change) | No |
| `add_link(link_uid, graph)` | C3 (endpoint check) | Yes |
| `remove_link(link_uid)` | C5 (unconstrained) | No |

---

## 7. Validation Rules
<!-- Lines 566-597 -->

These rules are added to `ig-tool validate` (implemented in `validation.py`).

All checks apply when the IG has a non-empty `lenses` dict.

| ID | Scope | Severity | Rule | Error message template |
|---|---|---|---|---|
| V-L1 | each lens | error | Every UID in `lens.nodes` exists in the IG. | `lens '{name}': node UID '{uid}' not found in graph` |
| V-L2 | each lens | error | Every UID in `lens.intentlinks` exists in `graph.links` or `graph.inter_links`. | `lens '{name}': intentlink UID '{uid}' not found in graph` |
| V-L3 | each lens | error | Ancestor closure: for every `uid` in `lens.nodes`, all ancestors of `uid` (computed via `graph.anc`) are also in `lens.nodes`. | `lens '{name}': node '{uid}' present but ancestor '{anc_uid}' missing` |
| V-L4 | each lens | error | Link endpoint closure: for every `link_uid` in `lens.intentlinks`, both endpoints of the link are in `lens.nodes`. | `lens '{name}': link '{link_uid}' present but endpoint '{ep_uid}' not in lens nodes` |
| V-L5 | IG meta | warning | If `meta.default_lens` is set, it must be a key in `lenses`. | `meta.default_lens '{name}' does not match any lens` |
| V-L6 | derived IG | error | If `meta.derived_from` is set: `via_lens` must be a key in `lenses`. | `meta.derived_from.via_lens '{name}' not found in lenses` |
| V-L7 | derived IG | error | If `meta.derived_from` is set: every node UID in the IG must appear in `lenses[via_lens].nodes`. | `derived IG: node '{uid}' not covered by via_lens '{lens_name}'` |
| V-POS1 | each lens node entry | error | If `position` is present, `x` and `y` must both be numeric (int or float) and finite. NaN and Infinity are rejected. | `lens '{name}': node '{uid}' position.{coord} is not a finite number (got {value})` |
| V-POS2 | each lens node entry | error | If `position` is present, it must contain exactly the keys `x` and `y` (no extra keys, no missing keys). Enforced by `Position.extra="forbid"` at construction; belt-and-suspenders check at validation time. | `lens '{name}': node '{uid}' position must have exactly keys 'x' and 'y'` |

Notes:
- V-L1 through V-L4 and V-POS1/V-POS2 apply to all IGs with lenses (primary and derived).
- V-POS1 and V-POS2 apply only to nodes whose `LensNodeEntry.position` is not `None`. Unpinned
  nodes (position absent) are unaffected.
- V-L5 is a warning because a stale `default_lens` pointer after lens deletion is recoverable.
- V-L6 and V-L7 apply only when `meta.derived_from` is present.
- The existing orphan check (dotted UID with no parent treearc) is **relaxed** for derived IGs:
  it is replaced by V-L7 (every node covered by the lens). Derived IGs are intentional subsets.
- Cross-IG link validation (existing `validate_inter_intentlinks` in `validation.py`) runs
  independently and is unaffected by lens rules.
- V-POS1 and V-POS2 are implemented in `validate_lenses()` in `validation.py`.
  PIG reference: `LENSSCHEMA.VALIDATION`.

---

## 8. ig-tool lens Subcommand Surface
<!-- Lines 600-604 -->

The `ig-tool lens` group is rewritten. All new subcommands operate on **internal lenses**
(inside IG files via `-g`). The legacy agent-I/O lens commands (build, show, focus, etc.)
operate on **Lens files** (via `-l`) and are preserved with no changes.

### New subcommands (internal lens management)
<!-- Lines 607-650 -->

All new subcommands use `-g graph.ig.yaml` (both input and output — in-place write). `--lens NAME` identifies the target lens.

| Subcommand | Synopsis | Reads | Writes | Closure |
|---|---|---|---|---|
| `list` | `ig-tool lens list -g G` | IG | nothing | — |
| `show` | `ig-tool lens show -g G --lens N` | IG | nothing | — |
| `create` | `ig-tool lens create -g G --name N [--description D]` | IG | IG | trivial (empty) |
| `delete` | `ig-tool lens delete -g G --lens N` | IG | IG; clears default_lens if N was default | — |
| `add-node` | `ig-tool lens add-node -g G --lens N --uid U --lod L [--x F --y F]` | IG | IG | C1 (ancestor fill at skeleton) |
| `remove-node` | `ig-tool lens remove-node -g G --lens N --uid U` | IG | IG | C2 (descendant purge), C4 (link purge) |
| `set-lod` | `ig-tool lens set-lod -g G --lens N --uid U --lod L` | IG | IG | C6 (node-only) |
| `set-position` | `ig-tool lens set-position -g G --lens N --uid U --x F --y F` | IG | IG | — |
| `clear-position` | `ig-tool lens clear-position -g G --lens N --uid U` | IG | IG | — |
| `add-link` | `ig-tool lens add-link -g G --lens N --uid LINK_UID` | IG | IG | C3 (endpoint check) |
| `remove-link` | `ig-tool lens remove-link -g G --lens N --uid LINK_UID` | IG | IG | C5 (unconstrained) |
| `set-default` | `ig-tool lens set-default -g G --lens N` | IG | IG | — |
| `unset-default` | `ig-tool lens unset-default -g G` | IG | IG | — |
| `project` | `ig-tool lens project -g G --lens N -o reduced.ig.yaml` | source IG | reduced IG | — (§9) |
| `reintegrate` | `ig-tool lens reintegrate -i reduced.ig.yaml [-o parent.ig.yaml]` | derived IG + parent IG | parent IG | — (§9) |
| `validate` | `ig-tool lens validate -g G [--lens N]` | IG | nothing | V-L1–V-L4, V-POS1, V-POS2 |

**`add-node` with position:** When `--x` and `--y` are both provided, sets
`position = {"x": x, "y": y}` on the new `LensNodeEntry`. When omitted, position
defaults to `None` (unpinned). Auto-fills ancestors at `skeleton` per C1 regardless
of whether a position is given.

**`set-position` detail:** Sets or overwrites the `position` field on the
`LensNodeEntry` for `--uid` in `--lens`. Creates the node entry if absent (auto-fills
ancestors at skeleton per C1). Values must pass V-POS1 and V-POS2. Writes back
to the IG file in-place.

**`clear-position` detail:** Sets `position = None` on the `LensNodeEntry` for
`--uid`, reverting the node to unpinned. Does NOT remove the node from the lens —
only clears its position. Idempotent: no-op if the UID has no position set.
`position` is omitted from the serialized output when `None` (see §4.1).

**`project` detail:** copies node bodies for every `uid` in `LensConfig.nodes`, treearcs between them, and intentlinks in `LensConfig.intentlinks`. Writes `meta.derived_from: {of: source_path, via_lens: NAME}`. Includes a single lens equal to the source lens. No other lenses copied.

**`reintegrate` Phase-1 scope:**
- Supported: node content edits (name, intent, constraints, design_notes, examples, impl_pointers, epistemic_state, history-append); add new nodes (must specify parent present in parent IG); add/edit intentlinks (both endpoints in parent IG after add-node pass).
- NOT supported (error): node deletion, treearc reparenting, link endpoint changes.
- Error template: `reintegrate: operation '{op}' not supported in Phase 1`.

### Migration of legacy ig-tool lens commands
<!-- Lines 653-680 -->

The legacy commands operate on agent-I/O `Lens` files (via `-l`). They are **unchanged** and
continue to work for agent workflow use.

| Legacy command | Status | Notes |
|---|---|---|
| `lens build` | **Kept unchanged** | Agent I/O; `-l` output; no relation to internal lenses |
| `lens show` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens tree` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens info` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens focus` | **Kept unchanged** | Agent I/O; reads `-l` Lens file + `-g` graph |
| `lens promote` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens demote` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens set-lod` | **Renamed** `lens set-lod-agent` OR disambiguated by flag presence: `-l` = legacy agent mode, `-g --lens` = internal lens mode. Prefer flag-based dispatch. |
| `lens prune` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens expand` | **Kept unchanged** | Agent I/O; reads `-l` Lens file + `-g` graph |
| `lens set-budget` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens list-pruned` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |
| `lens diff` | **Kept unchanged** | Agent I/O; reads `-l` Lens file + `-g` graph |
| `lens apply` | **Kept unchanged** | Agent I/O; reads `-l` Lens file + `-g` graph |
| `lens discard` | **Kept unchanged** | Agent I/O; reads `-l` Lens file |

**Disambiguation rule:** If a `lens` subcommand receives `-l` (lens file path), it operates in
legacy agent-I/O mode. If it receives `-g` + `--lens` (IG path + lens name), it operates in
new internal-lens mode. Commands that exist in only one mode need no disambiguation.

---

## 9. Reduced IG (Derived) Format
<!-- Lines 683-687 -->

A **derived IG** is produced by `ig-tool lens project` and is a valid IG conforming to the
standard schema (`SERIALIZATION_FORMAT.md §1`). It differs from a primary IG only in its
`meta.derived_from` marker.

### Shape
<!-- Lines 690-730 -->

```yaml
meta:
  name: "Auth System — auth-flow view"
  derived_from:
    of: "../auth_system.ig.yaml"   # path or graph_id
    via_lens: "auth-flow"
  # may carry default_lens, intent_resources, etc.

nodes:
  # Only nodes referenced by auth-flow LensConfig.nodes
  - uid: ROOT
    name: "Auth System"
    intent: "..."
  - uid: AUTH
    name: "Authentication"
    intent: "..."
  - uid: AUTH.1
    name: "Credential Validation"
    intent: "..."
    # all fields copied from parent IG

treearcs:
  # Only arcs between nodes in the lens
  - {parent: ROOT, child: AUTH}
  - {parent: AUTH, child: AUTH.1}

intentlinks:
  # Only links listed in LensConfig.intentlinks
  - uid: AUTH_AUTH.1
    src: AUTH
    dst: AUTH.1
    intent: "..."

lenses:
  auth-flow:                        # matches via_lens
    name: auth-flow
    nodes: {ROOT: skeleton, AUTH: lean, AUTH.1: full}
    intentlinks: [AUTH_AUTH.1]
```

### Validation treatment
<!-- Lines 733-739 -->

- V-L3 (ancestor closure) runs normally — the derived IG's treearcs cover the subset.
- V-L7 applies: every node in the derived IG must be covered by the `via_lens` lens.
- Orphan check relaxed: a node with a dot-uid whose UID-parent does not appear in the derived
  IG is allowed (the orphan check is replaced by V-L7 for derived IGs).
- All other standard validation rules (T1 well-formedness, T3 link endpoints) apply.

### Round-trip: project → reintegrate
<!-- Lines 742-762 -->

```
parent.ig.yaml
  └─ ig-tool lens project --lens auth-flow -o auth_reduced.ig.yaml
       → auth_reduced.ig.yaml (derived IG)
         [edit node content, add nodes, add/edit links]
  └─ ig-tool lens reintegrate -i auth_reduced.ig.yaml
       → parent.ig.yaml (updated)
```

The `reintegrate` command identifies changes by comparing the derived IG against the parent IG:
1. For each node in the derived IG: if `uid` exists in parent, diff content fields and apply
   updates. If `uid` is new (not in parent), add it with its `parent_uid` treearc.
2. For each intentlink in the derived IG: if `uid` exists in parent, update content fields.
   If `uid` is new and both endpoints are now in the parent, add the link.
3. Phase-1 abort conditions: node deletion attempted (uid in parent but absent in derived);
   reparenting attempted (node uid in both but different parent treearc); link endpoint change
   (same uid, different src/dst). All raise errors listing the violation.

---

## 10. Cross-IG References in Lenses
<!-- Lines 765-768 -->

When `meta.intent_resources` is set on an IG, lens node and link UIDs may use qualified form:
`graph_id:node_uid` (same format as inter intentlinks per [intentlink_spec.md §3.4](../intentlink_spec.md)).

### Resolution rules
<!-- Lines 771-778 -->

1. Parse `meta.intent_resources` as a path relative to the IG file's directory.
2. Load the manifest. Extract all graph IDs from `product` and `projection_by_target`.
3. A qualified UID `graph_id:node_uid` in `LensConfig.nodes` or `LensConfig.intentlinks` is
   valid if `graph_id` resolves to a known graph in the manifest, and `node_uid` exists in that
   graph.
4. Local UIDs (no `:`) resolve against the current IG only.

### Validation rules (cross-IG)
<!-- Lines 781-787 -->

- V-CG1 (warning): `meta.intent_resources` path set but file not found — warn, skip cross-IG checks.
- V-CG2 (error): qualified UID present but `meta.intent_resources` absent — error.
- V-CG3 (error): qualified UID `graph_id:node_uid` present but `graph_id` not in manifest — error.
- V-CG4 (error): qualified UID `graph_id:node_uid` present but `node_uid` not in the resolved
  graph — error.

### Scope note
<!-- Lines 790-796 -->

Cross-IG lenses are primarily intended for `reintegrate` flows where a derived IG may reference
nodes across graph boundaries. For typical single-IG work, `meta.intent_resources` is absent
and only local UIDs are valid.

---

## 11. Migration Plan for Existing Lens Model
<!-- Lines 799-799 -->

### What survives unchanged
<!-- Lines 802-810 -->

- `models/lens.py` — entire file. `LOD`, `LensNode`, `LensMeta`, `Lens` classes are untouched.
  The `Lens` object continues to serve agent-I/O workflows via `serial/lens_file.py`.
- `serial/lens_file.py` — `load_lens`, `save_lens`, `lens_to_agent_text` unchanged.
- `ops/lens_ops.py` — `build_lens`, `promote`, `demote`, `focus_on`, `prune_subtree`,
  `expand_subtree`, `set_budget`, `compute_diff`, `apply_diff`, `discard_changes` unchanged.
- All `ig-tool lens {build|show|tree|info|focus|promote|demote|prune|expand|set-budget|
  list-pruned|diff|apply|discard}` commands in `cli_lens_commands.py` unchanged.

### New additions
<!-- Lines 813-828 -->

- `models/lens_config.py` — new file containing `LensConfig` class (§4). No inheritance from
  `LensMeta` or `Lens`.
- `models/__init__.py` — add `LensConfig` to imports and `__all__`.
- `models/graph.py` — add `self.lenses: dict[str, LensConfig] = {}` to `IntentGraph.__init__`.
  Add `add_lens`, `remove_lens`, `get_lens` convenience methods.
- `serial/json_yaml.py:graph_to_dict` — serialize `lenses` if non-empty; serialize
  `meta.derived_from`, `meta.default_lens`, `meta.intent_resources` as part of `meta` dict.
- `serial/json_yaml.py:dict_to_graph` — deserialize `lenses` dict via `LensConfig.model_validate`;
  no change to meta handling (meta is freeform dict already).
- `validation.py` — add `validate_lenses(graph)` function returning issues list; called by
  `ig-tool validate`.
- `cli_lens_commands.py` — add handlers for all new subcommands (§8). Extend the lens action
  dispatch block after the existing `discard` handler.
- `errors.py` — add `ClosureViolation(IntentGraphError)` exception class.

### What gets removed
<!-- Lines 831-836 -->

- `serial/lens_file.py` is NOT removed (agent workflows depend on it).
- The `[no intent]` placeholder logic in `lensFileIO.ts` (extension) is removed — it was
  only needed because the old lens files carried node bodies. No Python equivalent exists.
- No Python code is removed. The migration is purely additive.

### Import sites that change
<!-- Lines 839-845 -->

| File | Change |
|---|---|
| `models/__init__.py` | Add `from intentgraph.models.lens_config import LensConfig` |
| `cli_lens_commands.py` | Add `from intentgraph.models.lens_config import LensConfig` |
| `validation.py` | Add `from intentgraph.models.lens_config import LensConfig` |

### Extension-side removal
<!-- Lines 848-854 -->

The H2 `'[no intent]'` placeholder in `src/host/lensFileIO.ts:139` is removed alongside the
entire `lensFileIO.ts` module (see extension spec §2). The `LensState` type (`lensState.ts`)
is also removed. Both existed solely for the `*.lens.yaml` round-trip.

---

## 12. Acceptance Criteria
<!-- Lines 857-859 -->

The following conditions must all be true before the implementation is considered complete.

### Schema and models
<!-- Lines 862-869 -->

- AC1. `LensConfig` can be instantiated with `name`, `nodes`, `intentlinks` only; `description`
  and `target_uids` default correctly.
- AC2. `LensConfig.name_must_be_nonempty` raises `ValidationError` for empty/whitespace name.
- AC3. `graph_to_dict(graph)` includes `lenses` key only when `graph.lenses` is non-empty.
- AC4. `dict_to_graph(d)` round-trips a graph with lenses: identical `lenses` after
  `dict_to_graph(graph_to_dict(g))`.

### Closure
<!-- Lines 872-879 -->

- AC5. `add_node(uid, "full", graph)` auto-inserts all ancestors at `"skeleton"` when they
  were absent.
- AC6. `remove_node(uid, graph)` removes `uid`, all descendants, and all links touching them.
- AC7. `add_link(link_uid, graph)` raises `ClosureViolation` when either endpoint is not in
  `lens.nodes`.
- AC8. `set_lod(uid, "lean")` does not change `lens.nodes` keyset.

### Validation
<!-- Lines 882-890 -->

- AC9. `ig-tool validate -g graph.ig.yaml` reports V-L1 error when a lens references a
  non-existent node UID.
- AC10. `ig-tool validate -g graph.ig.yaml` reports V-L3 error when ancestor closure is violated.
- AC11. `ig-tool validate -g graph.ig.yaml` reports V-L5 warning when `meta.default_lens`
  references a non-existent lens name.
- AC12. Derived IG with correct `meta.derived_from` + V-L7 coverage passes `ig-tool validate`.
- AC13. Derived IG with a node not covered by `via_lens` fails V-L7 with error.

### CLI
<!-- Lines 893-902 -->

- AC14. `ig-tool lens create -g g.yaml --name foo` adds an empty lens; `ig-tool lens list` shows it.
- AC15. `ig-tool lens add-node -g g.yaml --lens foo --uid EXTRACT --lod full` populates ancestors
  at skeleton; verified by `ig-tool lens show`.
- AC16. `ig-tool lens project --lens foo -g g.yaml -o reduced.yaml` produces a valid IG that
  passes `ig-tool validate -g reduced.yaml`.
- AC17. `ig-tool lens reintegrate -i reduced.yaml` applies content edits to the parent IG.
- AC18. `ig-tool lens reintegrate` errors on Phase-1 unsupported operations (node delete,
  reparent, endpoint change).

### Serialization round-trip
<!-- Lines 905-910 -->

- AC19. A hand-authored `.ig.yaml` with a `lenses:` block round-trips through `load_graph` +
  `save_graph` without data loss.

---

## 13. Out of Scope
<!-- Lines 913-930 -->

The following items are explicitly deferred to Phase 2 or later:

- **Structural-edit reintegration**: node deletion, treearc reparenting, link endpoint changes
  via `lens reintegrate`. Phase-1 only supports content edits and additions.
- **Lens diff/merge UI**: visualizing differences between two lenses; merging lens configs.
- **Multi-IG transactional reintegration**: atomically applying a derived IG across multiple
  parent IGs in a single transaction.
- **Lens-aware agent I/O**: using `LensConfig` directly as an agent communication format
  (rather than the full `Lens` object). Agents continue to use the `Lens` object.
- **Finer LOD rendering**: distinguishing `skeleton` from `lean` visually in the viewer.
  Currently both render as canvas-name-only.
- **`saveCurrentAsLens` command** in the extension: capturing the current viewer state
  as a named lens in the IG file. Planned; not in this redesign.
- **Lens template/pattern library**: predefined lens configs (e.g. "show all full LOD").

---

## 14. Risks and Mitigations
<!-- Lines 933-941 -->

| Risk | Severity | Mitigation |
|---|---|---|
| `dict_to_graph` migration: existing IG files have no `lenses` key — deserializer must handle absence gracefully | Low | `d.get("lenses", {})` with empty default; no breaking change |
| `meta` dict is freeform — `derived_from`, `default_lens`, `intent_resources` stored as plain dict keys. A typo in a key goes silently undetected. | Medium | V-L5 catches a wrong `default_lens`. V-L6/V-L7 catch a malformed `derived_from`. Documented key names are the contract. Consider a `GraphMeta` Pydantic model in Phase 2. |
| Closure enforcement requires a graph reference for add/remove-node. The graph must be loaded when calling these methods. | Low | All CLI commands that mutate lenses load the graph (`-g` flag required). API contract documented. |
| `reintegrate` identity matching relies on UID stability. If UIDs were renamed in the derived IG, reintegrate will incorrectly treat old uid as deleted and new uid as added. | High | Phase-1 spec explicitly prohibits UID changes in derived IGs. Document prominently. UID stability is a core IG axiom (PRIMER_00). |
| `meta.intent_resources` path is relative to the IG file. If the IG file is moved without moving the manifest, cross-IG lens resolution breaks silently. | Medium | V-CG1 emits a warning when the manifest is not found. Users should use `intent_resources.yaml` at a stable path. |
| Legacy `lens set-lod` (agent-I/O, `-l` flag) vs new `lens set-lod` (internal, `-g --lens` flags): flag ambiguity in the CLI parser. | Medium | Dispatch on presence of `-l`: if `-l` present → legacy mode. Document the disambiguation rule. Both modes are supported. |
