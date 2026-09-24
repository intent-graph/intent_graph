# PRIMER_05_INTENT_RESOURCES

**intent_resources.yaml** is the project manifest for IntentGraph: product graphs, projection graphs by target, and pointers to where code/doc/GUI live. The format is **self-documenting** — the file itself explains how to read it. Below is a full example; after it, short notes on building, using, and maintaining.

Full spec: [docs/PROJECT_RESOURCES_SPEC.md](../docs/PROJECT_RESOURCES_SPEC.md).

---

## Self-documenting example

This is what **intent_resources.yaml** looks like. The comment block at the top is the main documentation; anyone (agent or human) opening the file sees it first.

```yaml
# ------------------------------------------------------------------------------
# intent_resources.yaml — Project resources (IntentGraph framework).
# Read this first:
#   product: list of product IntentGraphs (WHAT/WHY). Each entry: id, name, file.
#   projection_by_target: map from target (e.g. python, db-schema) to list of
#     projection graphs (HOW). Same entry shape: id, name, file. Optional: role_hint.
#   resources: where projection outputs live. code / doc / gui — each a list of
#     {id, path, description?}. gui = Obsidian; one vault root, all graphs export there.
# Paths are relative to this file. Graph ids (product[*].id, projection id) are used
# for cross-graph links and "include other IG". No per-graph Obsidian path.
# ------------------------------------------------------------------------------

name: "Library Loans"
description: "Product + projection graphs for library loans."

product:
  - id: product
    name: "Product IG"
    description: "Library book-loans system — WHAT and WHY."
    file: "intent_graph/product/graph.json"

projection_by_target:
  python:
    - id: pig-py-guidelines
      name: "Python guidelines"
      file: "intent_graph/projection/python_style.yaml"
      role_hint: guidelines
    - id: pig-py-project
      name: "Project Python decisions"
      file: "intent_graph/projection/PIG-project.yaml"
      role_hint: project
  db-schema:
    - id: pig-db-schema
      name: "DB schema projection"
      file: "intent_graph/projection/PIG-db-schema.yaml"

resources:
  code:
    - id: main
      path: "src/"
      description: "Main application code."
    - id: migrations
      path: "migrations/"
  doc:
    - id: spec
      path: "doc/spec/"
  gui:
    - id: obsidian
      path: "obsidian_export"
      description: "Obsidian vault root; all graphs export here."
```

---

## Build

- **Create:** Add the comment block at the top (copy from the example; adjust if you add keys). Then fill `product`, `projection_by_target`, `resources`. Required per graph entry: `id`, `name`, `file`. Required per resource entry: `id`, `path`.
- **Add a graph:** Append to `product` or to the right `projection_by_target.<target>` list. Give it a stable `id`; set `file` relative to the manifest.
- **Add a resource:** Append to `resources.code`, `.doc`, or `.gui`. For Obsidian, keep a single entry in `resources.gui` (one vault root); do not add per-graph Obsidian paths.
- **Paths:** Relative to the directory containing intent_resources.yaml. Keep the header in sync if you introduce new top-level keys.

---

## Use

- **Graph files:** Resolve `product[*].file` and `projection_by_target.<target>[*].file` relative to the manifest path. Load those files to get the IntentGraphs.
- **Output locations:** Resolve `resources.code[*].path`, `resources.doc[*].path`, `resources.gui[*].path` for where code, docs, and the Obsidian vault live. One gui path = vault root; all graphs are exported under it.
- **Graph ids:** Use `product[*].id` and each projection entry’s `id` for cross-graph link resolution and when using "include other IG". These ids appear in qualified endpoints (`graph_id:node_uid`) in inter intentlinks; tooling loads intent_resources.yaml to resolve graph_id to graph file. They are graph identifiers, not node UIDs inside a graph.

---

## Maintain

- Keep the top comment block accurate: if someone can read only that, they should know how to interpret the rest of the file.
- When adding or moving graph files, update the corresponding `file` path. When adding or moving code/doc/vault roots, update `resources`.
- Do not add `obsidian_export` (or any Obsidian path) to product or projection entries. Obsidian is one projection; its location is `resources.gui`.
