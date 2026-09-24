# PRIMER_TOOLS (compressed)

**WHY layer.** Exact syntax: `.claude/skills/ig-tool-*/SKILL.md`.
Formats: `-g`/`-o` accept `.json`, `.yaml`, `.yml` (inferred from extension).

---

## Decision Tree

| Goal | Command |
| --- | --- |
| Inspect topology (cheap) | `query --structure` or `tree` |
| Inspect topology (richer) | `query --overview` |
| Read one node | `query --node` |
| Single node/link change | `node` / `link` |
| Many changes atomically (batch ops format) | `apply --batch` *(format ≠ §2/§5 — see ig-tool-graph-edit skill)* |
| Apply agent diff (§2/§5 format) | `apply -i` *(see ig-tool-graph-edit skill)* |
| Validate diff without applying | `parse` |
| Agent I/O (full workflow) | `lens build → show → diff → apply` |
| Persistent named view | `graph lens create/show` |
| Step folder / trace | `workflow step` / `workflow trace` |
| Obsidian export | `obsidian export` |
| Convert JSON ↔ YAML | `convert` |
| Check integrity | `validate` |
| CLI usage log | `telemetry` |

---

## Commands

**validate** — integrity check. Exit 1 if errors. `ig-tool validate -g graph.yaml`. Skill: ig-tool-query.

**query** — read-only navigation. Pick cheapest variant: `--structure` (skeleton) → `--overview` (richer) → `--node UID` (full detail). Also: `--children`, `--ancestors`, `--links`, `--neighbors`, `--projection-links` (no `-m` flag). Skill: ig-tool-query.

**tree** — ASCII tree. `ig-tool tree -g graph.yaml [--show-intent] [--root UID]`. Human-readable; use `query --structure` for parseable YAML. Skill: ig-tool-query.

**parse** — validate agent diff without mutating. `ig-tool parse -g graph.yaml -i edits.yaml`. Skill: ig-tool-graph-edit.

**apply** — two modes, **distinct input formats**: (1) **agent diff** (`-i`): §2 (view; `view:` header, legacy `frontier:` accepted on read) or §5 (diff) YAML, defined in `SERIALIZATION_FORMAT.md`; (2) **batch ops** (`--batch`): YAML with `operations:` list, each `op:` in dot notation (`node.create`, `link.remove` — NOT `node_create`). Batch ops format is documented **only** in the `ig-tool-graph-edit` skill — read it before authoring. `apply -g graph.yaml -i edits.yaml -o out.yaml [--role extractor] [-m "why"] [--dry-run]` or `apply -g graph.yaml --batch batch.yaml -o out.yaml [--role r] [-m "why"] [--dry-run]`. Skill: ig-tool-graph-edit (mandatory for batch).

**node** — single node mutations. Verbs: `create`, `set`, `reparent`, `reorder`, `remove`, `show`. `--parent` is optional on `create`. `set` supports `--unset FIELD` (clear optional fields); `--impl-pointer` is repeatable (list field); `--effort` is free text. Skill: ig-tool-graph-edit.

**link** — intentlink mutations. Verbs: `create`, `set`, `remove`. `--parent` (link refinement) settable at create and set (intra-graph only). Skill: ig-tool-graph-edit.

**Provenance (all mutating commands)** — history stamps automatically at every save (write-boundary diff): `--role <r>` → `who: agent:<r>`; `-m "<one-liner>"` → the note (omitted → auto diff summary). Never hand-edit `history`.

**lens** — file-based agent I/O (primary). 15 verbs: build, show, tree, info, focus, promote, demote, set-lod, prune, expand, set-budget, list-pruned, diff, apply, discard. `-l` = lens file, `-g` = source graph, `-o` = output. Skill: ig-tool-lens.

**graph** — internal (graph-embedded) lens management. `graph lens` + 16 verbs: list, create, delete, add-node, remove-node, add-link, remove-link, set-lod, set-position, clear-position, set-default, unset-default, project, reintegrate, validate, show. All use `-g graph --lens NAME`. Skill: ig-tool-graph.

**context** — assemble context payload (working view). Select the view with `--nodes UID,UID,…` or `--depth N`: `ig-tool context -g graph.yaml --nodes E,T,L [-t UID] [-b 4000] -o ctx.yaml`. Skill: ig-tool-query. For new work prefer `lens build`.

**workflow** — step and trace management. `workflow step create/summary`, `workflow trace record/show`. Skill: ig-tool-workflow.

**obsidian** — vault sync. `obsidian export -g graph.yaml -o vault/ [--vault-root vault/] [--force] [--intentlinks {all,siblings,none}]`. Subcommands: export, import, diff, export-canvas, export-tree, export-lens-canvas, detect-pins. Skill: ig-tool-obsidian.

**convert** — `ig-tool convert -i graph.json -o graph.yaml`. Skill: ig-tool-query.

**init** — create new graph. `ig-tool init -o graph.json --root --name "..."` (with ROOT node) or `--template three-level` (ROOT + 3 modules). **Without `--root` or `--template`, the graph has ZERO nodes** — subsequent `node create --parent ROOT` will fail "Node 'ROOT' does not exist." `--root` always creates UID `ROOT`; `--root-name` only sets display name. For a non-`ROOT` root UID, omit `--root` and create the first node manually (no `--parent`). Skill: ig-tool-query.

**telemetry** — CLI usage log. `telemetry show/tail/path`. Default-on; opt out with `--no-telemetry`.

---

## Next Steps

- Navigation: [PRIMER_02_NAVIGATION](PRIMER_02_NAVIGATION.md)
- Editing: [PRIMER_03A_EDITING](PRIMER_03A_EDITING.md)
- Exact syntax: `.claude/skills/ig-tool-*/SKILL.md`
