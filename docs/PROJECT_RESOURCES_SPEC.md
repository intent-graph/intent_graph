# Project Resources — Spec (draft)

**Status:** Design draft. Not yet adopted.

**Purpose:** Single manifest that lists all IntentGraph resources for a project: product graph(s) (possibly hierarchical), projection graphs organized by target, **and pointers to projection outputs** (code, doc, GUI). In the IntentGraph framework, projections like code, doc, and GUI are first-class; the manifest keeps pointers to where they live. Provides a clear entry point for tooling, agents, and humans. Inter-graph links live **inside their respective intent graphs** (each link stored once, no duplication); the manifest only indexes graphs and resources.

**Requirement — Self-documenting:** The manifest file must be understandable by agents without separate instructions. Either (1) the format stays simple enough that structure is obvious from the keys, or (2) the file **starts with a short comment block** that explains how to read and use it (see §3.0). Prefer (2) if the format has more than a few top-level keys.

---

## 1. Why a project resources manifest?
<!-- Lines 13-22 -->

- **One place to look:** "What graphs does this project have, and where do they live?"
- **Product:** Today often one product graph; in the future, **hierarchies** of product IGs (e.g. main product + included/reused libs or codebases that have their own IG). The manifest lists all product graphs and can express inclusion relationships.
- **Projection:** Multiple ProjectionIGs, **organized by target** (keyword): e.g. `python`, `db-schema`, `udf`, `query`, `doc`. Within one target, several projections (e.g. Python: guidelines + project-specific; DB+SQL: one guideline per concern — schema, UDF, query).
- **Obsidian is a projection:** Like code and doc, the GUI (Obsidian) is a projection. **All graphs are always projected into the same Obsidian export root vault** — one path; product and all projection graphs export under that root (e.g. as subfolders). The manifest points to that single vault in `resources.gui`.
- **Resources (projection outputs):** Code, doc, and GUI are part of the framework. The manifest keeps **pointers to where they are** — code root(s), doc root(s), and the **single** Obsidian vault root — so tooling and humans have one place to find "the code", "the docs", "the Obsidian vault".
- **Inter-graph links:** Stored **in the intent graphs** that own them (see §5); not in the manifest. Links must not be duplicated — each link exists in exactly one graph.

---

## 2. Graph roles (for code generation and beyond)
<!-- Lines 25-34 -->

| Role | What it is | Example |
|------|------------|--------|
| **Product** | WHAT/WHY — domain intent. **One or more** graphs; in the future possibly a **hierarchy** (main product + included/reused lib/codebase IGs). | Main product IG; optional "shared-lib-X" IG. |
| **Projection (by target)** | HOW — rendering intent, grouped by **target** (keyword). Per target: one or more projection graphs (e.g. guidelines + project-specific, or one per sub-concern). | Target `python`: guidelines + project PIG. Target `db-schema`, `udf`, `query`: one guideline each. |

So: **product** = one or more graphs (flat list today; hierarchy when reusing existing lib/codebase). **Projection** = organized by **target**; within each target, several graphs (guidelines, project-specific, or per sub-concern).

---

## 3. Proposed structure
<!-- Lines 37-41 -->

The manifest is a single file (YAML or JSON).

**Recommended filename:** `intent_resources.yaml` — short, signals "intent" (graphs + projection outputs), matches the `resources` section inside the file. Place at project root or in a dedicated intent-graph folder (e.g. `intent_graph/`). Alternatives: `project_resources.yaml` (emphasizes project scope), `ig_resources.yaml` (brief, IG-branded).

### 3.0 File header (how to read this) — recommended for self-documentation
<!-- Lines 44-62 -->

If the format is not minimal, the file **should start with a comment block** so that any agent or human opening the file sees how to use it first. In YAML, use a block of lines starting with `#`. Example:

```yaml
# ------------------------------------------------------------------------------
# intent_resources.yaml — Project resources manifest (IntentGraph framework).
# Read this first:
#   - product: list of product IntentGraphs (WHAT/WHY). Each has id, name, file.
#   - projection_by_target: map from target (e.g. python, db-schema) to list of projection graphs (HOW). Same entry shape.
#   - resources: where projections live. code / doc / gui (Obsidian = one vault root; all graphs export there). List of {id, path, description}. Paths relative to this file.
# Use: resolve graph files from product[*].file and projection_by_target.<target>[*].file; resolve code/doc/gui from resources.<kind>[*].path.
# ------------------------------------------------------------------------------

name: "Library Loans"
# ... rest of file
```

Keep the header short (under ~15 lines). JSON does not support comments; if using JSON, either keep the structure very simple (few keys, obvious names) or provide a separate one-line pointer (e.g. a `_readme` or `$schema` field with a short description). For YAML, the comment block is the preferred way to make the file self-documenting.

### 3.1 Top-level
<!-- Lines 65-91 -->

```yaml
# Optional: human-readable project name
name: "Library Loans"

# Optional: one-line description
description: "Product + projection graphs for the library loans feature."

# Product graphs (one or more; future: hierarchy / includes for reused libs)
product:
  - {product graph entry}

# Projection graphs, organized by target (keyword)
projection_by_target:
  python:
    - {projection graph entry}
  db-schema:
    - {projection graph entry}
  # ...

# Pointers to projection outputs (code, doc, GUI) — part of the framework
resources:
  code: [ {resource entry}, ... ]
  doc:  [ {resource entry}, ... ]
  gui:  [ {resource entry}, ... ]
```

### 3.2 Product graph entry
<!-- Lines 94-104 -->

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Stable identifier (e.g. `product`, `product-lib-x`). Used in cross-graph links and by tooling. |
| `name` | Yes | Short human-readable name. |
| `description` | No | One or two sentences. |
| `file` | Yes | Path to the graph file (relative to manifest or absolute). |
| `includes` | No | (Future) List of graph `id`s this product IG includes (e.g. reused lib/codebase IGs). |

Obsidian is a projection; all graphs export into the **same** vault root (see `resources.gui`). No per-graph `obsidian_export`.

### 3.3 Projection graph entry (per target)
<!-- Lines 107-182 -->

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Stable identifier (e.g. `pig-py-guidelines`, `pig-py-project`, `pig-db-schema`). |
| `name` | Yes | Short human-readable name. |
| `description` | No | One or two sentences. |
| `file` | Yes | Path to the graph file. |
| `role_hint` | No | `guidelines` \| `project` (or similar). Per target: e.g. guidelines + project-specific. |

Obsidian is a projection; all graphs export into the same vault root (see `resources.gui`). No per-graph `obsidian_export`.

**Example (with self-documenting header):**

```yaml
# Project resources: product + projection graphs + where code/doc/GUI live.
# product: list of {id, name, file}. projection_by_target: <target> -> list of same. resources: code|doc|gui -> list of {id, path, description?}. Obsidian = one vault root in resources.gui; all graphs export there. Paths relative to this file.

name: "Library Loans"
description: "Product + projection graphs for library loans."

product:
  - id: product
    name: "Product IG"
    description: "Library book-loans system — WHAT and WHY."
    file: "intent_graph/product/graph.json"
  # Future: - id: product-lib-x
  #           name: "Reused lib X"
  #           file: "vendor/lib_x/graph.json"
  #           includes: []

projection_by_target:
  python:
    - id: pig-py-guidelines
      name: "Python guidelines"
      description: "Conventions from python_defaults; shared style."
      file: "intent_graph/projection/python_style.yaml"
      role_hint: guidelines
    - id: pig-py-project
      name: "Project Python decisions"
      description: "FastAPI, module naming, error handling for this project."
      file: "intent_graph/projection/PIG-project.yaml"
      role_hint: project
  db-schema:
    - id: pig-db-schema
      name: "DB schema projection"
      file: "intent_graph/projection/PIG-db-schema.yaml"
  udf:
    - id: pig-udf
      name: "User-defined functions"
      file: "intent_graph/projection/PIG-udf.yaml"
  query:
    - id: pig-query
      name: "Query projection"
      file: "intent_graph/projection/PIG-query.yaml"

# Pointers to projection outputs. Obsidian = one vault root; all graphs (product + projections) export under it.
resources:
  code:
    - id: main
      path: "src/"
      description: "Main application code."
    - id: migrations
      path: "migrations/"
      description: "DB migrations."
  doc:
    - id: spec
      path: "doc/spec/"
      description: "Generated spec and API docs."
  gui:
    - id: obsidian
      path: "obsidian_export"
      description: "Obsidian vault root; all graphs (product + projection_by_target) export here."
```

---

## 4. Resources: pointers to projection outputs (code, doc, GUI)
<!-- Lines 185-187 -->

In the IntentGraph framework, **projections** — code, documentation, GUI — are first-class. The manifest keeps **pointers to where they are** so that tooling, agents, and humans can resolve "the code", "the docs", "the GUI export" from a single place.

### 4.1 Top-level `resources`
<!-- Lines 190-200 -->

Optional section keyed by **kind**: `code`, `doc`, `gui`. Each kind is a list of resource entries (one or more). Paths are relative to the manifest location or absolute.

| Kind  | Meaning |
|-------|--------|
| `code` | Where generated or maintained code lives (repo root, package, backend/frontend dirs, migrations, etc.). |
| `doc`  | Where documentation projections live (spec, API docs, Confluence, etc.). |
| `gui`  | **Obsidian is a projection.** All graphs (product + all projection graphs) are always projected into the **same** Obsidian export root vault. `resources.gui` points to that single root (typically one entry). No per-graph Obsidian path; the export tool writes each graph under that root (e.g. as subfolders). |

There is no per-graph `obsidian_export` field; the GUI projection target is the vault root in `resources.gui`.

### 4.2 Resource entry
<!-- Lines 203-211 -->

| Field | Required | Description |
|-------|----------|-------------|
| `id`  | Yes      | Stable identifier (e.g. `main`, `migrations`, `spec`, `obsidian-product`). |
| `path`| Yes      | Path to the resource (directory or file). Relative to manifest or absolute. |
| `description` | No  | Short description (e.g. "Main application code", "Product IG in Obsidian"). |

Multiple entries per kind are allowed for `code` and `doc`. For `gui`, typically **one** entry (the Obsidian vault root); all graphs export under it.

### 4.3 Use
<!-- Lines 214-218 -->

- **Tooling:** "Open code", "open docs", "open in Obsidian" resolve from `resources` + manifest path.
- **Agents:** Generator knows where to write code; Doc agents know where to write docs; export scripts know where to write GUI exports.
- **Bidirectional sync:** Extractor / Doc agents read from these paths when reconciling edits back into the graph.

### 4.4 Obsidian sync snapshot (`.ig-sync.yaml`)
<!-- Lines 221-248 -->

Obsidian is a **bidirectional** projection: `ig-tool obsidian export` writes the vault from the graph, and `ig-tool obsidian merge` flows vault edits back into the canonical graph (the graph file is always the source of truth). To detect conflicts safely, export writes a **standardized baseline snapshot** at the vault root. It is a machine-managed file — **do not hand-edit**.

**Location:** `<vault_root>/.ig-sync.yaml` (one per exported graph vault; for multi-graph vaults, one per graph subfolder).

**Schema (`schema: ig-sync/1`):**

```yaml
# ig-obsidian sync snapshot — written by `ig-tool obsidian export`. Do not edit by hand.
schema: ig-sync/1
graph_id: product              # optional — resolved via intent_resources.yaml when known; null otherwise
graph_file: intent_graph/product/graph.json   # path to the canonical graph at export time
exported_at: "2026-07-08T12:56:45+00:00"      # ISO-8601 UTC timestamp of the export
graph_hash: "sha256:<hex>"     # hash of the whole canonical graph at export time
nodes:                         # per-node content hash at export time (identity = uid)
  ROOT: "sha256:<hex>"
  ERRORS.1: "sha256:<hex>"
```

**How `merge` uses it:**

- **`graph_hash`** — a fast "did the canonical graph move at all since export?" gate. If it differs from the current graph and `--force` is not given, `merge` refuses (re-export or resolve first). The graph file always wins.
- **`nodes[uid]`** — the per-node baseline that drives **whole-node conflict resolution**. For a node the vault changed: if the canonical node's current content hash still equals the baseline, the vault edit is applied; if the canonical also changed since export (hash differs), the **whole node is a conflict** — the vault edit is skipped, the canonical value stands, and the node is reported.

The snapshot anchors on the same identifiers this manifest defines: `graph_id` matches a `product[*].id` / projection `id`, and the vault lives under `resources.gui`. When `merge` is invoked without an explicit `-g`, it resolves the target graph from the snapshot's `graph_file` (and, in future, via `graph_id` against `intent_resources.yaml`).

---

## 5. Inter-graph links: in their respective intent graphs
<!-- Lines 251-265 -->

Inter-graph links (e.g. "PIG node X applies to product node Y") **live inside the intent graphs**, not in the manifest. Each link is stored in **exactly one** graph (no duplication).

**Rationale (theoretical):** The graph that states the relationship owns the link; graphs remain self-contained; no central registry to keep in sync. Tooling that needs cross-graph visibility loads the relevant graphs and follows links from each.

**Convention:** A link is stored in the graph that is the **source** of the relationship (e.g. PIG → product: the PIG graph holds the link). Endpoints use **qualified UID** (Option A): `src` and `dst` are strings `graph_id:node_uid` (e.g. `src: "pig-py:PIG-PY-TYPES.1"`, `dst: "product:DISCOVER.1"`). The **graph_id** in each endpoint must match an **id** in this manifest (a `product[*].id` or a projection entry `id`). Tooling resolves that id to a graph file by loading intent_resources.yaml. The product graph does not duplicate the link; it may be discovered when tooling "includes other IG" (see §6).

**Rules:**

- Each cross-graph link appears in **one** graph only (e.g. the source graph). Validation can check consistency when "include other IG" is enabled.
- Endpoints: one endpoint is local (this graph); the other is graph-qualified (`graph_id` + `uid`). Existence invariant: the other graph must be loadable and contain the referenced node.
- Same payload as same-graph intentlinks: `intent`, optional `shape`. Refinement (parent/child link) remains same-graph only for v0.

---

## 6. Tooling: "include other IG"
<!-- Lines 268-277 -->

Existing tools (Lens, query, validate, generation) need to be extended with an option to **include other IGs** or not.

- **Without "include other IG":** Work with a single graph only (current behaviour). Cross-graph links in that graph are either ignored or treated as opaque references.
- **With "include other IG":** Tool loads the current graph plus referenced/included graphs (from the project resources manifest). Cross-graph link endpoints are resolved; validation checks that referenced nodes exist in the other graphs; query/Lens can optionally show "linked from / links to other graph" for displayed nodes.

So: one graph in isolation vs. one graph plus its referenced graphs. No duplication of links; each link lives in one graph; tools activate cross-graph resolution when requested.

---

## 7. Relation to existing docs
<!-- Lines 280-286 -->

- **project_definition.md** — Defines IntentGraph, ProjectionIG, projection. This spec adds a **project-level index** (the manifest), **product** (one or more, future hierarchy), **projection by target** (keyword, several graphs per target), and **inter-graph links in graphs**.
- **intentlink_spec** — Same-graph intentlinks unchanged. Cross-graph links are an extension stored **in** a graph; see [intentlink_spec.md §3.4](intentlink_spec.md).
- **projection/README.md** — Reference artifacts (dimension ontology, python_defaults) remain. Projection graphs in the manifest may reference or derive from them.

---

## 8. Summary
<!-- Lines 289-299 -->

| Concept | Purpose |
|--------|--------|
| **Project resources manifest** | Single file: **product**, **projection_by_target**, **resources**. Each graph entry: id, name, description, file (no per-graph obsidian_export). Obsidian = one vault root in resources.gui; all graphs export there. **Self-documenting:** simple format or comment block at top (see §3.0). |
| **Product** | One or more product IGs; future: hierarchy when reusing existing lib/codebase with its own IG. |
| **Projection by target** | Organized by target keyword (e.g. `python`, `db-schema`, `udf`, `query`). Several projections per target (e.g. guidelines + project for Python; one per concern for DB+SQL). |
| **Resources** | Pointers to **where projection outputs are**: `code`, `doc`, `gui` (each a list of {id, path, description}). Code, doc, and GUI are part of the framework; the manifest keeps their locations. |
| **Inter-graph links** | Stored **in the intent graphs** that own them; each link in exactly one graph (no duplication). Convention: source graph holds the link. |
| **Include other IG** | Tool option: work with this graph only, or this graph + referenced graphs; cross-graph links resolved when enabled. |

**Next steps (if adopted):** Define wire format (YAML schema), add cross-graph link format to serialization (in-graph), implement manifest load and "include other IG" in tooling, extend validator and ig-tool (e.g. `query --include-other-ig`, `validate --include-other-ig`).
