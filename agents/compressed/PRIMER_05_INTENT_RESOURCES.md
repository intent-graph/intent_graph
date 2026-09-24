# PRIMER_05_INTENT_RESOURCES (Compressed)

**intent_resources.yaml** = project manifest; self-documenting. Example first, then build/use/maintain. Full: [../PRIMER_05_INTENT_RESOURCES.md](../PRIMER_05_INTENT_RESOURCES.md).

---

## Self-documenting example

```yaml
# intent_resources.yaml — Project resources (IntentGraph framework).
# product: list of {id, name, file}. projection_by_target: <target> -> list of same (id, name, file, role_hint?).
# resources: code|doc|gui -> list of {id, path, description?}. gui = one Obsidian vault root; all graphs export there. Paths relative to this file.

name: "My Project"
product:
  - id: product
    name: "Product IG"
    file: "intent_graph/product/graph.json"
projection_by_target:
  python:
    - id: pig-py-project
      name: "Project PIG"
      file: "intent_graph/projection/PIG-project.yaml"
resources:
  code: [{ id: main, path: "src/" }]
  doc: [{ id: spec, path: "doc/spec/" }]
  gui: [{ id: obsidian, path: "obsidian_export" }]
```

---

## Build

Create: header comment first, then product, projection_by_target, resources. Add graphs to product or projection_by_target.<target>; add outputs to resources. One entry in resources.gui (vault root). No per-graph Obsidian path. Paths relative to manifest.

## Use

Resolve graph files from product[*].file and projection_by_target.<target>[*].file. Resolve code/doc/gui from resources.<kind>[*].path. Graph ids = product[*].id and projection id (qualified endpoint `graph_id:node_uid` in inter intentlinks; "include other IG").

## Maintain

Keep header accurate. Update file paths when graphs move; update resources when output locations move. No obsidian_export on graph entries.
