# IntentGraph Serialization Format

Authoritative specification for how IntentGraph data is represented on disk and in agent I/O. All serializers and parsers must conform to this document. Schema definitions (field names, types, semantics) live in [VOCABULARY_AND_FORMALISM.md](VOCABULARY_AND_FORMALISM.md) sections 4-7 — this document specifies the **wire format** only.

## Table of Contents

1. [1. Persistence Format (Full Graph)](#1-persistence-format-full-graph) _(Lines 57-61)_
   1. [Top-level structure](#top-level-structure) _(Lines 64-87)_
   1. [Node object](#node-object) _(Lines 90-115)_
      1. [UID Format Rules (Enforced by Validation)](#uid-format-rules-enforced-by-validation) _(Lines 118-138)_
      1. [epistemic_state Format Convention](#epistemic_state-format-convention) _(Lines 141-163)_
   1. [Treearc object](#treearc-object) _(Lines 166-173)_
   1. [Intentlink object](#intentlink-object) _(Lines 176-187)_
   1. [Inter intentlinks (in-graph)](#inter-intentlinks-in-graph) _(Lines 190-202)_
   1. [LensConfig object](#lensconfig-object) _(Lines 205-220)_
1. [2. Agent Text Format (Lens I/O)](#2-agent-text-format-lens-io) _(Lines 223-225)_
   1. [Structure](#structure) _(Lines 228-266)_
   1. [Key differences from persistence format](#key-differences-from-persistence-format) _(Lines 269-279)_
   1. [Edit protocol](#edit-protocol) _(Lines 282-302)_
   1. [Provenance injection](#provenance-injection) _(Lines 305-316)_
1. [3. Graph Overview Format (Navigation)](#3-graph-overview-format-navigation) _(Lines 319-321)_
   1. [Tree overview (`graph_to_tree_overview`)](#tree-overview-graph_to_tree_overview) _(Lines 324-346)_
   1. [Edge overview (`graph_to_edge_overview`)](#edge-overview-graph_to_edge_overview) _(Lines 349-359)_
   1. [Size estimation (`view_text_size`)](#size-estimation-view_text_size) _(Lines 362-366)_
1. [4. Conventions Across All Formats](#4-conventions-across-all-formats) _(Lines 369-369)_
   1. [Omission rules](#omission-rules) _(Lines 372-376)_
   1. [YAML style](#yaml-style) _(Lines 379-383)_
   1. [ID conventions (summary — see formalism §4.1)](#id-conventions-summary--see-formalism-41) _(Lines 386-394)_
   1. [Encoding](#encoding) _(Lines 397-403)_
1. [5. Diff Format (Sparse Deltas)](#5-diff-format-sparse-deltas) _(Lines 406-412)_
   1. [Structure](#structure-1) _(Lines 415-429)_
   1. [Change markers](#change-markers) _(Lines 432-442)_
   1. [Node operations](#node-operations) _(Lines 445-467)_
   1. [Intentlink operations](#intentlink-operations) _(Lines 470-492)_
   1. [Topology constraints](#topology-constraints) _(Lines 495-497)_
   1. [Relationship to §2](#relationship-to-2) _(Lines 500-512)_
   1. [Auto-detection](#auto-detection) _(Lines 515-522)_
   1. [PIG diffs](#pig-diffs) _(Lines 525-529)_
1. [6. Lens Format](#6-lens-format) _(Lines 532-540)_
   1. [Structure](#structure-2) _(Lines 543-586)_
   1. [LOD Levels](#lod-levels) _(Lines 589-597)_
   1. [Intentlink Visibility](#intentlink-visibility) _(Lines 600-625)_
   1. [IV_ LOD Assignment Pattern](#iv_-lod-assignment-pattern) _(Lines 628-659)_
   1. [Pruning](#pruning) _(Lines 662-690)_
   1. [Diff Tracking](#diff-tracking) _(Lines 693-712)_
   1. [Type Discriminator](#type-discriminator) _(Lines 715-721)_
   1. [Relationship to Persistence and Agent Text](#relationship-to-persistence-and-agent-text) _(Lines 724-737)_
1. [Reference Implementation](#reference-implementation) _(Lines 740-760)_
1. [7. Agent task payload format (orchestrator → agent)](#7-agent-task-payload-format-orchestrator--agent) _(Lines 763-770)_



---

## 1. Persistence Format (Full Graph)
<!-- Lines 57-61 -->

Used by `load_graph` / `save_graph` (and `save_json` / `load_json` / `save_yaml` / `load_yaml`). This is the canonical storage format for a complete IntentGraph.

**Encoding:** JSON or YAML. Both use the identical dict structure. UTF-8. CLI and Python API accept both; format is inferred from file extension (`.json`, `.yaml`, `.yml`).

### Top-level structure
<!-- Lines 64-87 -->

```yaml
meta:                    # object, optional — graph metadata
  name: "..."            # string — human-readable graph name
  # ... any additional keys (version, description, etc.)

nodes:                   # list, required — all intentnodes in breadth-first order
  - {node}               # (root(s) first, then each level; roots sorted by uid)

treearcs:                # list, required — refinement edges in BFS order
  - {parent: str, child: str}

intentlinks:             # list, required — all semantic edges (intra-graph)
  - {link}

inter_intentlinks:       # list, optional — links between graphs (Option A: qualified UID)
  - {inter_link}

lenses:                  # dict, optional — named LensConfig views (see LENS_REDESIGN_SPEC.md §4)
  overview: {lens_config}
```

**Node and treearc order:** The `nodes` list and the `treearcs` list are emitted in **breadth-first** order: root(s) first (sorted by uid if multiple roots), then all nodes at depth 1, then depth 2, and so on. Within a level, siblings follow each parent's `children_uids` order. This yields stable, human-readable files and deterministic diffs.

### Node object
<!-- Lines 90-115 -->

Only non-default fields are emitted. Structural fields (`parent_uid`, `children_uids`) are **never** serialized — treearcs carry the tree structure.

```yaml
uid: "EXTRACT.1.3"      # string, required — hierarchy-encoded PK (see UID format rules below)
name: "Parse CSV"       # string, required
intent: "Extract..."    # string, required
epistemic_state: "..."  # string, optional — omitted when null
constraints:             # list[string], optional — omitted when empty
  - "Must handle UTF-8"
examples:                # list[string], optional — omitted when empty
  - "Given a CSV with..."
design_notes: "..."      # string, optional — omitted when null
effort: "..."            # string, optional — omitted when null
impl_pointers:           # list[string], optional — omitted when empty; pointer grammar: formalism §4.2
  - "src/auth.py::AuthParser.parse (lines 40-80)"
history:                 # list[{who, date, note}], optional — omitted when empty; auto-stamped at save (formalism §4, Provenance capture)
  - who: "remi"          # string, required — human name or "agent:<role>"; optional " via:<channel>" qualifier
    date: "2026-02-12"   # string (ISO 8601), required — auto-stamped entries use full timestamp
    note: "Created..."   # string, required — one-liner commit-style message
data_registry:          # dict, optional — omitted when absent or empty
  positions:
    ROOT.1: {x: 100, y: 300, width: 250, height: 150}
  spacing: {horizontal: 150, vertical: 100}
```

#### UID Format Rules (Enforced by Validation)
<!-- Lines 118-138 -->

UIDs follow a hierarchical naming convention:

- **Root node**: The single parentless node. By **convention** named `"ROOT"`, but any UID matching the L1 keyword regex is permitted (e.g. `ig-tool init` may produce a different root UID). Docs and examples say `ROOT` as shorthand — substitute the actual root UID when issuing commands.
- **L1 nodes** (parent=root): A single segment — one uppercase keyword (preferred) or one number (allowed)
  - Keyword pattern: `^[A-Z][A-Z0-9_]*$` — Examples: `"DISCOVER"`, `"PARSE"`, `"ERRORS"`, `"API"`, `"LEXER_TOKENS"`, `"API_V2"` (underscores permitted inside the keyword)
  - Numeric pattern: `^[0-9]+$` — Examples: `"1"`, `"2"` (allowed but keyword is strongly preferred)
  - Invalid: `"ERROR.HANDLER"` (multi-segment — belongs at L2), `"_BAD"` (leading underscore rejected), `"discover"` (lowercase rejected)
- **L2 nodes** (children of L1): Two patterns based on expected size:
  - **Numeric** — minor node: `{parent}.{number}` — Pattern: `^[A-Z][A-Z0-9_]*\.[0-9]+$`
    - Examples: `"DISCOVER.1"`, `"PARSE.2"`
  - **Semantic** — named sub-capability: `{parent}.{keyword}` — Pattern: `^[A-Z][A-Z0-9_]*\.[A-Z][A-Z0-9_]*$`
    - Examples: `"ERRORS.HANDLER"`, `"API.CLIENT"`, `"DISCOVER.DB"`, `"LEXER.PARSER_INTERFACE"`
- **L3+ nodes**: Parent prefix + dot + sequential number — Pattern: `^.+\.[0-9]+(\.[0-9]+)*$`
  - Examples: `"DISCOVER.DB.1"`, `"ERRORS.HANDLER.2"`, `"PARSE.2.1.3"`
- **ProjectionIG L1**: `PIG-{SEMANTIC}-{COMPONENT}`
  - Pattern: `^PIG-[A-Z_]+-[A-Z_.]+$`
  - Examples: `"PIG-PY-TYPES"`, `"PIG-DOC-STYLE"`

Rationale: L1 UIDs are single-segment labels — a keyword for readability, or a number when needed. L2 either adds a named qualifier (semantic, e.g. `ERRORS.HANDLER`) or a numeric index (minor, e.g. `ERRORS.1`). L3+ always use numbers. This keeps the top level scannable and the refinement hierarchy unambiguous.

#### epistemic_state Format Convention
<!-- Lines 141-163 -->

The `epistemic_state` field is free-text. When multiple issues are discovered during workflows, use pipe-separated issue annotations:

```
epistemic_state: "<base_state>: <description> | <issue_type>: <issue> | <issue_type>: <issue> ..."
```

**Issue types:**
- `gap:` — missing information
- `conflict:` — contradiction or tension
- `missing:` — expected relationship/link absent
- `unclear:` — vague or ambiguous
- `unvalidated:` — needs confirmation

**Examples:**
```yaml
epistemic_state: "observed: extracted from auth.py | gap: performance requirements not specified"
epistemic_state: "known | missing: no intentlink to ROOT.5 concurrency constraint"
epistemic_state: "undecided: three strategies proposed | unvalidated: no test coverage data"
```

This is a **textual convention**, not a schema constraint. No validation enforces the format. Parsers treat the entire field as an opaque string. Agents should recognize the `|` separator as a signal that issues have been discovered and need resolution.

### Treearc object
<!-- Lines 166-173 -->

```yaml
parent: "ROOT"           # string, required — parent node uid
child: "EXTRACT"         # string, required — child node uid
```

Treearcs are an **explicit list**, not embedded on nodes. One entry per parent-child edge.

### Intentlink object
<!-- Lines 176-187 -->

Only non-default fields are emitted.

```yaml
uid: "EXTRACT.1_TRANSFORM.2"   # string, required — derived PK (see formalism §4.1)
src: "EXTRACT.1"               # string, required — source node uid
dst: "TRANSFORM.2"             # string, required — destination node uid
intent: "Passes..."            # string, required
shape: {...}                    # object, optional — structured grounding, omitted when null
parent: "EXTRACT_TRANSFORM"    # string, optional — parent link uid (link refinement)
```

### Inter intentlinks (in-graph)
<!-- Lines 190-202 -->

Inter intentlinks connect intentnodes across different IntentGraphs (e.g. ProjectionIG → product). They are stored **in the graph that owns the link** (convention: the source graph). Each endpoint is a **qualified UID** of the form `graph_id:node_uid`; `graph_id` must match an id in the project's **intent_resources.yaml** (see [PROJECT_RESOURCES_SPEC](../docs/PROJECT_RESOURCES_SPEC.md)). Refinement (parent/child link) does not apply to inter intentlinks.

Only non-default fields are emitted.

```yaml
src: "pig-py:PIG-PY-TYPES.1"   # string, required — source endpoint (graph_id:node_uid)
dst: "product:DISCOVER.1"      # string, required — destination endpoint (graph_id:node_uid)
intent: "Renders..."           # string, required
uid: "pig-py:PIG-PY-TYPES.1_product:DISCOVER.1"  # string, optional — derived from src_dst if omitted
shape: {...}                    # object, optional — omitted when null
```

### LensConfig object
<!-- Lines 205-220 -->

Stored under the top-level `lenses:` dict, keyed by name. Pointers only — no node bodies. Full spec: [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md) §4.

```yaml
name: "overview"         # string, required — same as the dict key
description: "..."       # string, optional
target_uids: ["PARSE"]   # list[string], optional — focus nodes the lens was built around
nodes:                   # dict[uid -> entry], required — ancestor-closed (C1)
  ROOT: {lod: lean}
  PARSE: {lod: full, position: {x: 100.0, y: 200.0}}
intentlinks:             # list[string], required — both endpoints must be in nodes (C3)
  - "PARSE.1_VALIDATE.2"
```

---

## 2. Agent Text Format (Lens I/O)
<!-- Lines 223-225 -->

Used by `text_to_edits` / `apply_edits` (`ig-tool apply -i`). This is how agents write back a **working view** — a lens at uniform full LOD over the selected nodes, with pruned children listed as read-only context. Always YAML.

### Structure
<!-- Lines 228-266 -->

```yaml
view:                    # header; legacy key `frontier:` accepted on read
  name: "auth subsystem"
  scope: "..."           # optional

nodes:
  - uid: EXTRACT.1.1
    name: "Extract credentials"
    intent: "Parse and validate auth credentials"
    epistemic_state: "known"                    # optional
    constraints:                                # optional
      - "Must support OAuth2"
    examples:                                   # optional
      - "JWT token from header"
    design_notes: "..."                         # optional
    effort: "..."                               # optional
    impl_pointers:                              # optional, list[string] — grammar: formalism §4.2
      - "src/auth.py::AuthParser"
    history:                                    # optional
      - who: "agent:extractor"
        date: "2026-01-15"
        note: "Created from codebase analysis."
    collapsed_children: [EXTRACT.1.1.1, EXTRACT.1.1.2]   # read-only context (pruned subtree)

intentlinks:
  - uid: EXTRACT.1.1_EXTRACT.1.2
    src: EXTRACT.1.1
    dst: EXTRACT.1.2
    intent: "Passes credentials for token gen"
  - uid: EXTRACT.1_TRANSFORM.1                 # lifted link example
    src: EXTRACT.1                             # display endpoint (view node)
    dst: TRANSFORM.1
    intent: "Auth data flows to transform"
    lifted: true                               # marks this as a projection
    original_src: EXTRACT.1.1                 # canonical endpoint
    original_dst: TRANSFORM.1.2              # canonical endpoint
```

### Key differences from persistence format
<!-- Lines 269-279 -->

| Aspect | Persistence | Agent text |
|--------|-------------|------------|
| Scope | Full graph | Working view (lens at full LOD) |
| Tree structure | Explicit `treearcs` list | Implicit via `collapsed_children` |
| Intentlinks | All canonical links | Projected links (lifted + direct) |
| `lifted` / `original_src` / `original_dst` | Never present | Present on projected links |
| `collapsed_children` | Never present | Read-only context for agents |

For variable-LOD agent I/O (target full, ancestors lean, distant branches skeleton), use the Lens Format (§6) with `lens build` / `lens apply`.

### Edit protocol
<!-- Lines 282-302 -->

Agents modify the view text and return it. The parser (`text_to_edits`) diffs the returned text against the current graph state to produce structured edit operations:

| Agent action | Detected as | Edit operation |
|---|---|---|
| Add a new node entry | uid not in graph | `NodeCreate` |
| Change fields on existing node | field values differ | `NodeUpdate` |
| Add `_delete: true` to a node | delete marker | `NodeDelete` |
| Add a new non-lifted link entry | uid not in graph | `LinkCreate` |
| Add `_delete: true` to a link | delete marker | `LinkDelete` |
| Modify a lifted link | Ignored | Lifted links are projections, not canonical |

The `_delete: true` marker:
```yaml
nodes:
  - uid: EXTRACT.1.1
    _delete: true        # signals deletion — only uid + _delete needed
```

Edit operations are validated through the IntentGraph invariant gateway before applying. Agents never mutate the graph directly.

### Provenance injection
<!-- Lines 305-316 -->

Provenance is captured at the **write boundary** for every save pathway, not just `apply_edits` — see formalism §4, "Provenance capture". The actor comes from the channel (`--role` for agents, `IG_ACTOR`/git identity for humans); the note is a supplied one-liner (`-m`) or an auto-generated diff summary:

```yaml
history:
  - who: "agent:extractor"
    date: "2026-02-17T14:30"
    note: "Created node via extractor agent."
```

---

## 3. Graph Overview Format (Navigation)
<!-- Lines 319-321 -->

Lightweight formats for agents that need graph structure without full node content. Used by Navigator and Critic agents for orientation.

### Tree overview (`graph_to_tree_overview`)
<!-- Lines 324-346 -->

```yaml
meta:
  name: "ETL Pipeline"
  node_count: 15
  link_count: 8
  max_depth: 3

tree:
  ROOT:
    _label: "# ETL System — [3 children]"
    EXTRACT:
      _label: "# Extract — [3 children] — epistemic:known"
      EXTRACT.1: "# Parse CSV — [leaf]"
      EXTRACT.2: "# Parse JSON — [leaf]"
      EXTRACT.3: "# Validate — [leaf]"
    TRANSFORM:
      _label: "# Transform — [2 children]"
      ...
```

Leaf nodes are `uid: "# label"` (string value). Branch nodes are `uid: {_label: ..., children...}` (dict value).

### Edge overview (`graph_to_edge_overview`)
<!-- Lines 349-359 -->

```yaml
link_count: 8
intentlinks:
  - "EXTRACT -> TRANSFORM: 'Extracted data flows to transformation'"
  - "TRANSFORM -> LOAD: 'Transformed data flows to loading'"
  - "EXTRACT.3 -> TRANSFORM.1: 'Validated records sent for normalization'"
```

Each entry is a single string: `"{src} -> {dst}: '{intent}'"`. Sorted by link uid.

### Size estimation (`view_text_size`)
<!-- Lines 362-366 -->

Returns `{chars: int, words: int, lines: int}` for a serialized agent-text view. Use to check whether a view fits in an agent's context window before sending it.

---

## 4. Conventions Across All Formats
<!-- Lines 369-369 -->

### Omission rules
<!-- Lines 372-376 -->

- **Null/None fields:** Omitted entirely (not emitted as `null`).
- **Empty lists:** Omitted entirely (not emitted as `[]`).
- **Default values:** Omitted (Pydantic `exclude_defaults=True` for persistence).

### YAML style
<!-- Lines 379-383 -->

- Block style (`default_flow_style=False`).
- Unicode allowed (`allow_unicode=True`).
- Key order preserved (`sort_keys=False`) — keys appear in schema order, not alphabetical.

### ID conventions (summary — see formalism §4.1)
<!-- Lines 386-394 -->

| Entity | Format | Example |
|--------|--------|---------|
| Node | `{root}.{segment}...` | `ROOT`, `EXTRACT`, `EXTRACT.1.3` |
| Intentlink | `{src}_{dst}` or `{src}_{dst}#{tag}` | `EXTRACT.1_TRANSFORM.2`, `EXTRACT.3_LOAD.1#auth` |
| ProjectionIG node | `PIG-<TAG>.{segment}...` | `PIG-PY.IMPL.NAME`, `PIG-DIM.TEST.STRAT` |
| Dimension ontology node | `PIG-DIM.{segment}...` | `PIG-DIM.ROOT`, `PIG-DIM.IMPL.ERR` |
| Language defaults node | `PIG-<LANG>.{segment}...` | `PIG-PY.ROOT`, `PIG-PY.DOC.STR` |

### Encoding
<!-- Lines 397-403 -->

- UTF-8 throughout.
- Plain ASCII for all identifiers (UIDs, keys).
- No BOM.

---

## 5. Diff Format (Sparse Deltas)
<!-- Lines 406-412 -->

A concise way to express changes to an IntentGraph or ProjectionIG. The diff format is **not a new format** — it is an agent text document (§2) that contains only changed entities, with a `diff_meta` header replacing the `view` header.

**When to use:** Agents returning small edits to a large view. Instead of echoing the entire view, the agent emits only what changed.

**When not to use:** Full rewrites where most nodes changed — use the standard agent text (§2) instead.

### Structure
<!-- Lines 415-429 -->

```yaml
diff_meta:                          # required — replaces the §2 'view' header
  base: "graph.json"                # string — what this diff applies against
  base_step: "019_DISTILL.COMMIT"   # string, optional — step that produced the base
  author: "agent:extractor"         # string — who produced this diff
  date: "2026-02-18"                # string (ISO 8601), optional

nodes:                              # list, optional — only changed nodes
  - {node with change markers}

intentlinks:                        # list, optional — only changed links
  - {link with change markers}
```

### Change markers
<!-- Lines 432-442 -->

Three markers control the operation. They extend the §2 node/link schema — all other fields are identical.

| Marker | On | Meaning |
|--------|-----|---------|
| `_new: true` | node or link | Create this entity. Requires all mandatory fields (`uid`, `name`, `intent` for nodes; `src`, `dst`, `intent` for links). Nodes require `parent` for treearc placement. |
| `_delete: true` | node or link | Delete this entity. Only `uid` + `_delete` needed. (Already in §2.) |
| `_prev: {fields}` | node or link | Previous values, for review only. **Parser ignores this field.** |

An entity that appears **without** `_new` or `_delete` is an **update** — only the fields present are changed; absent fields are preserved.

### Node operations
<!-- Lines 445-467 -->

```yaml
nodes:
  # UPDATE — only changed fields
  - uid: DISCOVER.1
    name: "Discover SQL files"
    intent: "Walk directory tree looking for *.sql files"
    _prev:                          # optional — review context
      name: "Find SQL files"
      intent: "Locate SQL source files"

  # CREATE — new node with treearc
  - uid: DISCOVER.3
    name: "Index discovered functions"
    intent: "Build a lookup table mapping function names to file paths"
    parent: DISCOVER                # treearc target (required for new nodes)
    _new: true

  # DELETE
  - uid: DISCOVER.2
    _delete: true
```

### Intentlink operations
<!-- Lines 470-492 -->

```yaml
intentlinks:
  # CREATE
  - uid: DISCOVER.1_DISCOVER.3
    src: DISCOVER.1
    dst: DISCOVER.3
    intent: "Passes file list for indexing"
    _new: true

  # UPDATE — change mutable fields (intent, shape)
  - uid: EXTRACT_TRANSFORM
    intent: "Validated data flows to strict transformation"
    _prev:
      intent: "Extracted data flows to transformation"

  # DELETE
  - uid: DISCOVER.1_DISCOVER.2
    _delete: true
```

Lifted links must never appear in a diff (they are projections, not canonical).

### Topology constraints
<!-- Lines 495-497 -->

The diff format supports **adding** and **deleting** nodes only. Reparenting (moving a node to a different parent) is not supported — delete and recreate instead. This keeps the format simple and the parser stateless.

### Relationship to §2
<!-- Lines 500-512 -->

| Aspect | Agent text (§2) | Diff (§5) |
|--------|-----------------|-----------|
| Header | `view:` | `diff_meta:` |
| Scope | Full view — all nodes | Sparse — only changed entities |
| Absent entities | Outside the view | Unchanged |
| `_new` marker | Not used (Create inferred from uid not in graph) | Required for creates |
| `_delete` marker | Identical | Identical |
| `_prev` marker | Not used | Optional, parser ignores |
| `LinkUpdate` | Not supported | Supported — uid + changed fields |
| Node/link schema | Identical | Identical |
| Omission rules (§4) | Apply | Apply |

### Auto-detection
<!-- Lines 515-522 -->

`parse_agent_output()` examines the top-level YAML for a `diff_meta` key:

- Present → routes to `diff_to_edits()` (§5 parser)
- Absent → routes to `text_to_edits()` (§2 parser)

Agents and tools can use either format — the system accepts both transparently.

### PIG diffs
<!-- Lines 525-529 -->

ProjectionIG is a full IntentGraph (same formalism). The diff format works identically for PIG — only the UID namespace differs (`PIG-*` prefix). No special handling needed.

---

## 6. Lens Format
<!-- Lines 532-540 -->

The Lens format extends the agent text format (§2) with Level of Detail (LOD) metadata and pruning state. It represents a full-tree view of the graph with variable detail levels based on the `IV_` pattern (see [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md)).

**When to use:** Interactive exploration of large graphs where context must vary by distance from focus node. Trade-off between completeness and readability.

**When not to use:** Uniform full-detail working views for agent I/O — use §2 or §5 instead.

Lens files can be stored as `.json` or `.yaml`/`.yml`; `load_lens` / `save_lens` infer format from file extension.

### Structure
<!-- Lines 543-586 -->

```yaml
lens:                           # required — top-level key
  name: "working-lens"          # string — human-readable name
  target_uid: CORE.DATA         # string, required — focus node UID
  budget: 30                    # int, optional — max node count before pruning
  source_graph: "graph.json"    # string — source file for provenance
  scope_root: null              # string, optional — UID for subtree scope (null for full)

nodes:                          # list, required — nodes with LOD metadata
  - uid: ROOT
    name: "Project"
    lod: skeleton               # LOD level (added field)

  - uid: CORE
    name: "Core Module"
    intent: "..."
    epistemic_state: "known"
    lod: lean

  - uid: CORE.DATA
    name: "Data Model"
    intent: "..."
    epistemic_state: "constrained"
    constraints: ["...", "..."]
    design_notes: "..."
    lod: full
    collapsed_children: [CORE.DATA.1, CORE.DATA.2]  # children included in lens
    pruned_children: 2                               # count of pruned children

treearcs:                       # list, required — same format and BFS order as persistence (§1)
  - { parent: ROOT, child: CORE }
  - { parent: CORE, child: CORE.DATA }

intentlinks:                    # list, optional — filtered by LOD visibility rules
  - uid: link_01
    src: CORE.DATA
    dst: CORE.API
    intent: "..."               # shown only if ≥1 endpoint is full LOD

pruned_subtrees:                # list, optional — subtree root UIDs removed during pruning
  - UTIL
```

### LOD Levels
<!-- Lines 589-597 -->

Three levels define which fields appear in a node:

- **skeleton:** `uid`, `name` only — minimum for tree navigation
- **lean:** + `intent`, `epistemic_state` — topic and certainty
- **full:** all fields + `collapsed_children`, `pruned_children` — complete context and local structure

Fields from higher levels include fields from lower levels. Schema is otherwise identical to §1 and §2 nodes.

### Intentlink Visibility
<!-- Lines 600-625 -->

Links are subject to LOD filtering:

- Link appears in the `intentlinks` list if **both endpoints are at lean LOD or above**
- Link `intent` field is shown only if **at least one endpoint is at full LOD**
- Between two lean nodes: only `uid`, `src`, `dst` present
- Between skeleton and any other: link omitted entirely

Example: link between two lean nodes
```yaml
intentlinks:
  - uid: EXTRACT.1_TRANSFORM.2
    src: EXTRACT.1
    dst: TRANSFORM.2
    # intent omitted — neither endpoint is full
```

Example: link where one endpoint is full
```yaml
intentlinks:
  - uid: EXTRACT.1.2_TRANSFORM.2
    src: EXTRACT.1.2
    dst: TRANSFORM.2
    intent: "Validated data sent to transformation"
```

### IV_ LOD Assignment Pattern
<!-- Lines 628-659 -->

The default LOD assignment algorithm (see [LENS_REDESIGN_SPEC.md](LENS_REDESIGN_SPEC.md)):

- **`_`** (underscore suffix): target node + direct neighbors → **full LOD**
  - Includes all ancestors, descendants, and intentlink endpoints one hop away
- **`I`** (ancestors): all ancestors of target up to root → **lean LOD**
  - Tree structure without detailed intent on non-target nodes
- **`V`** (vertices): all L1 nodes (direct children of root) → **lean LOD**
  - Graph-level navigation landmarks
- **Everything else:** → **skeleton LOD**
  - Provides tree structure without cognitive load

Example with target `CORE.DATA`:
```yaml
lens:
  target_uid: CORE.DATA

nodes:
  - uid: ROOT                          # ancestor (I)
    lod: lean
  - uid: CORE                          # ancestor (I)
    lod: lean
  - uid: CORE.DATA                     # target (_)
    lod: full
  - uid: CORE.DATA.1                   # child of target (_)
    lod: full
  - uid: ENGINE                        # sibling of ancestor (V)
    lod: lean
  - uid: UTIL                          # other subtree
    lod: skeleton
```

### Pruning
<!-- Lines 662-690 -->

When `budget` is set and node count would exceed it:

1. Compute shortest graph distance from target node to all other nodes
2. Remove most distant leaf subtrees (fewest connections to lens)
3. Record pruned subtree root UIDs in `pruned_subtrees`
4. Parent nodes show `pruned_children` count for transparency

Example:
```yaml
lens:
  budget: 30
  target_uid: EXTRACT.1

nodes:
  - uid: EXTRACT.1
    lod: full
    pruned_children: 5                 # 5 children removed for budget

pruned_subtrees:
  - EXTRACT.1.5
  - EXTRACT.1.6
  - EXTRACT.1.7
  - EXTRACT.1.8
  - EXTRACT.1.9
```

Pruned subtrees are **not** included in `nodes` or `treearcs`. The lens represents what is visible, not what was discarded.

### Diff Tracking
<!-- Lines 693-712 -->

Lenses track `base_state` (when created) vs `working_state` (after edits). Changes are **not serialized** — instead, compute diffs via the `ig-tool lens diff` command (§6 operations):

```bash
ig-tool lens diff lens.yaml graph.json
```

Returns:
```yaml
nodes_created: [...]            # new node UIDs
nodes_modified: [...]           # changed node UIDs
nodes_deleted: [...]
links_created: [...]
links_modified: [...]
links_deleted: [...]
treearcs_modified: [...]        # reparenting operations
```

**Note:** LOD changes are viewport operations and do **not** appear in diffs.

### Type Discriminator
<!-- Lines 715-721 -->

Lens files are identified by the top-level `lens` key containing at minimum:
- `target_uid` — distinguishes from persistence (§1, which has no `target_uid`)
- `source_graph` — provenance

Check presence of these fields to identify a Lens file in I/O parsing.

### Relationship to Persistence and Agent Text
<!-- Lines 724-737 -->

| Aspect | Persistence (§1) | Agent text (§2) | Lens (§6) |
|--------|------------------|---------------|-----------|
| Scope | Full graph | Working view (full LOD) | Full tree, variable LOD |
| Tree structure | Explicit `treearcs` | Implicit via `collapsed_children` | Explicit `treearcs` + LOD |
| Node/treearc order | **BFS** (root, then by level) | N/A | Same as persistence when emitted |
| Target focus | None | None | Required (`target_uid`) |
| Node detail | Full or omitted | Full or omitted | Full, lean, or skeleton |
| Pruning | N/A | N/A | Explicit `pruned_subtrees` + `pruned_children` counts |
| Intentlinks | All canonical | Projected + canonical | Filtered by LOD visibility |
| Use case | Storage | Agent editing | Interactive exploration |

---

## Reference Implementation
<!-- Lines 740-760 -->

All formats are implemented in `src/intentgraph/serial/`:

| Module | Format |
|--------|--------|
| `json_yaml.py` | Persistence (§1) |
| `agent_text.py` | Agent text (§2), Diff (§5) |
| `graph_overview.py` | Graph overview (§3) |

Key functions for diff support:

| Function | Purpose |
|----------|---------|
| `diff_to_edits(text, graph)` | Parse diff YAML → `list[EditOp]` |
| `parse_agent_output(text, graph)` | Auto-detect §2 vs §5, dispatch to correct parser |
| `LinkUpdate(uid, fields)` | Edit operation for updating intentlink fields |

Tests: `src/tests/test_serialization.py`, `test_agent_text.py`.

---

## 7. Agent task payload format (orchestrator → agent)
<!-- Lines 763-770 -->

The structure of the prompt sent from orchestrator to agent — INPUT (context, working material, environment, execution state), INSTRUCTIONS, and OUTPUT CONTRACT — is **not** specified in this document. This document covers graph, Lens, agent-text view, and diff wire formats only.

The canonical specification for the **agent task payload** (including execution context: dry_run, verbosity, **effort_hint**, handles, and the full three-section template) is:

**[ai_tooling/howto/programming_subagents.md](../../ai_tooling/howto/programming_subagents.md)** (in the ai_tooling repo).

Agents and orchestrators should treat that document as the source of truth for payload structure and parameter semantics. Primer docs (agents/PRIMER_04_WORKFLOWS §Execution context) reference it for execution context and effort hint.
