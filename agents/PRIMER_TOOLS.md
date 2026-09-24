# PRIMER_TOOLS — ig-tool Command Guide

**WHY layer.** For exact syntax and flags, see the Skills: `.claude/skills/ig-tool-*/SKILL.md`.

**Formats:** `-g` / `-o` accept `.json`, `.yaml`, `.yml`; format inferred from extension.

---

## Decision Tree: What Do I Need?
<!-- Lines 11-31 -->

| Goal | Command(s) |
| --- | --- |
| Inspect graph topology (cheap start) | `query --structure` or `tree` |
| Inspect graph topology (richer) | `query --overview` |
| Read one node's full content | `query --node` |
| Make a single node/link change | `node create/set/remove` or `link create/set/remove` |
| Apply many changes atomically (batch ops format) | `apply --batch` *(format ≠ §2/§5 — see `ig-tool-graph-edit` skill)* |
| Apply agent-produced diff (§2/§5 format) | `apply -i` *(see `ig-tool-graph-edit` skill)* |
| Validate an agent diff without applying | `parse` |
| Agent I/O: build a working view | `lens build` → `lens show` → `lens diff` → `lens apply` |
| Persistent named view in graph | `graph lens create` / `graph lens show` |
| Orchestrator step management | `workflow step create` / `workflow step summary` |
| Record or inspect workflow trace | `workflow trace record` / `workflow trace show` |
| Export to Obsidian vault | `obsidian export` |
| Convert JSON ↔ YAML | `convert` |
| Check graph integrity | `validate` |
| Inspect CLI usage log | `telemetry show` / `telemetry tail` |

---

## Commands (all 15)
<!-- Lines 34-34 -->

### validate — Check graph integrity
<!-- Lines 37-48 -->

Checks: orphan nodes, broken refs, broken link endpoints, empty intents.
Returns exit code 1 if errors found.

```bash
ig-tool validate -g graph.yaml [-o report.yaml]
```

Skill: `ig-tool-query`.

---

### query — Graph navigation
<!-- Lines 51-68 -->

Read-only. Choose the cheapest variant that meets your need.

- `--structure`: uid+name skeleton (cheapest, start here)
- `--overview`: hierarchy + annotations
- `--node UID`: full content of one node
- `--children UID`, `--ancestors UID`, `--links UID`, `--neighbors UID`: targeted navigation
- `--projection-links UID`: inter (cross-graph) links for a node

```bash
ig-tool query -g graph.yaml --structure
ig-tool query -g graph.yaml --node D -o node_d.yaml
```

Skill: `ig-tool-query`.

---

### tree — ASCII tree visualization
<!-- Lines 71-81 -->

Human-readable hierarchy. Not the same as `query --structure` (which returns parseable YAML).

```bash
ig-tool tree -g graph.yaml [--show-intent] [--root D]
```

Skill: `ig-tool-query`.

---

### parse — Validate an agent diff without mutating
<!-- Lines 84-94 -->

Accepts §2 (view; `view:` header, legacy `frontier:` accepted on read) or §5 (diff) format. Reports edit count. Safe dry-run.

```bash
ig-tool parse -g graph.yaml -i edits.yaml [-o parsed.yaml]
```

Skill: `ig-tool-graph-edit`.

---

### apply — Apply agent diffs or batch operations
<!-- Lines 97-115 -->

Two modes — **the input formats are different**, do not mix them:

1. **Agent diff** (`-i`): apply a §2 (view) or §5 (diff) agent-produced YAML. `--dry-run` simulates.
2. **Batch ops** (`--batch`): a YAML file with `operations:` list, each entry an `op:` like `node.create`, `link.remove` (dot notation, **not** `node_create`). Atomic. `--dry-run` validates without writing.

§2/§5 are documented in `SERIALIZATION_FORMAT.md`. The batch ops format is **only** documented in the `ig-tool-graph-edit` skill — read it before authoring a batch file.

Provenance stamps automatically at save (write-boundary diff): `--role <r>` sets `who: agent:<r>`, `-m "<one-liner>"` sets the note (omitted → auto diff summary). Applies to both modes — never hand-edit `history`.

```bash
ig-tool apply -g graph.yaml -i edits.yaml -o updated.yaml --role extractor
ig-tool apply -g graph.yaml --batch batch.yaml -o updated.yaml
```

Skill: `ig-tool-graph-edit` (canonical for both modes; mandatory for batch).

---

### node — Single-node mutations
<!-- Lines 118-131 -->

`create`, `set`, `reparent`, `reorder`, `remove`, `show`. `--parent` is **omitted only for the root node** (whose UID is always `ROOT`, and which has no parent); required for everything else. **`--parent` takes an existing UID** — for L1 nodes this is `ROOT`. Passing a non-existent parent fails with `Node 'ROOT' does not exist`.

```bash
ig-tool node create -g graph.yaml --uid ROOT --name "Root" --intent "..." -o graph.yaml         # root: no --parent
ig-tool node create -g graph.yaml --uid ROOT.5 --parent ROOT --name "..." --intent "..." -o graph.yaml
ig-tool node set -g graph.yaml --uid ROOT.5 --intent "Updated" -o graph.yaml
ig-tool node remove -g graph.yaml --uid ROOT.5 --recursive -o graph.yaml
```

Skill: `ig-tool-graph-edit`.

---

### link — IntentLink mutations
<!-- Lines 134-145 -->

`create`, `set`, `remove`.

```bash
ig-tool link create -g graph.yaml --src ROOT.1 --dst ROOT.2 --intent "..." -o graph.yaml
ig-tool link remove -g graph.yaml --uid ROOT.1_ROOT.2 -o graph.yaml
```

Skill: `ig-tool-graph-edit`.

---

### lens — File-based agent I/O (primary workflow)
<!-- Lines 148-164 -->

The main agent interface. Builds a full-tree view with per-node LOD. 15 verbs:

`build`, `show`, `tree`, `info`, `focus`, `promote`, `demote`, `set-lod`, `prune`, `expand`,
`set-budget`, `list-pruned`, `diff`, `apply`, `discard`.

```bash
ig-tool lens build -g graph.yaml -t ROOT.1 -b 30 -o lens.yaml
ig-tool lens show -l lens.yaml -o view.yaml
ig-tool lens diff -l lens.yaml -g graph.yaml -o diff.yaml
ig-tool lens apply -l lens.yaml -g graph.yaml -o updated.yaml
```

Skill: `ig-tool-lens`.

---

### graph — Internal (graph-embedded) lens management
<!-- Lines 167-182 -->

`graph lens` manages named persistent lenses stored inside the graph. 16 verbs:
`list`, `create`, `delete`, `add-node`, `remove-node`, `add-link`, `remove-link`,
`set-lod`, `set-position`, `clear-position`, `set-default`, `unset-default`,
`project`, `reintegrate`, `validate`, `show`.

```bash
ig-tool graph lens list -g graph.yaml
ig-tool graph lens create -g graph.yaml --lens my-view -o graph.yaml
ig-tool graph lens show -g graph.yaml --lens my-view
```

Skill: `ig-tool-graph`.

---

### context — Assemble context payload
<!-- Lines 185-195 -->

Combines working-view serialization + IV-context + budget check. For orchestrators and advanced agents.

```bash
ig-tool context -g graph.yaml [-t D] [-b 4000] [--overview] -o context.yaml   # check --help for current view flags
```

Skill: `ig-tool-query`.

---

### workflow — Step folder and trace management
<!-- Lines 198-212 -->

**step create**: create a step folder with copies of prior step outputs.
**step summary**: compact metrics from an agent output file (used for orchestrator routing).
**trace record**: append a JSONL trace entry.
**trace show**: display workflow timeline.

```bash
ig-tool workflow step create --dir steps/ --step DISTILL.REFINE --target D
ig-tool workflow trace record trace.jsonl --step DISTILL.REFINE --target D --actor extractor --action "..." --result "..."
```

Skill: `ig-tool-workflow`.

---

### obsidian — Vault sync
<!-- Lines 215-229 -->

Export, import, diff, and canvas operations for Obsidian vaults. `export` accepts JSON or YAML.
`--intentlinks {all,siblings,none}` controls link rendering in FT canvases.

```bash
ig-tool obsidian export -g graph.yaml -o vault/ --force
ig-tool obsidian export -g graph.yaml -o vault/product_ig/ --vault-root vault/ --force
```

Subcommands: `export`, `import`, `diff`, `export-canvas`, `export-tree`, `export-lens-canvas`, `detect-pins`.

Skill: `ig-tool-obsidian`.

---

### convert — JSON ↔ YAML
<!-- Lines 232-241 -->

```bash
ig-tool convert -i graph.json -o graph.yaml
ig-tool convert -i graph.yaml -o graph.json
```

Skill: `ig-tool-query`.

---

### init — Create a new graph
<!-- Lines 244-261 -->

```bash
ig-tool init -o graph.json --root --name "My Project"                          # empty graph + a ROOT node
ig-tool init -o graph.json --root --root-name "ETL Pipeline" --root-intent "..."  # named root
ig-tool init -o graph.json --template three-level --name "ETL Pipeline"        # ROOT + 3 modules
ig-tool init -o graph.json --name "My Project"                                 # truly empty (no nodes)
```

**Important:** Without `--root` or `--template`, init creates a graph with **zero nodes**. Subsequent `node create --parent ROOT` will then fail with "Node 'ROOT' does not exist." Pass `--root` (optionally with `--root-name` / `--root-intent`) to add a `ROOT` node, or use `--template`.

The `--root` flag always creates the root with UID `ROOT`; `--root-name` only changes its display name. To use a non-`ROOT` UID for the root, omit `--root` and create the first node yourself with `node create` (no `--parent`).

Templates: `minimal` (ROOT only), `three-level` (ROOT + 3 modules + 2 components + 1 link). Use `--force` to overwrite.

Skill: `ig-tool-query`.

---

### telemetry — Inspect CLI usage log
<!-- Lines 264-274 -->

Usage log lives at `~/.cache/ig-tool/usage.jsonl`. Default-on; opt-out with `--no-telemetry` or `IG_TOOL_NO_TELEMETRY=1`.

```bash
ig-tool telemetry show
ig-tool telemetry tail -n 10
ig-tool telemetry path
```

---

## Next Steps
<!-- Lines 277-280 -->

- Navigation logic: [PRIMER_02_NAVIGATION](PRIMER_02_NAVIGATION.md)
- Editing decisions: [PRIMER_03A_EDITING](PRIMER_03A_EDITING.md)
- Exact syntax and flags: `.claude/skills/ig-tool-*/SKILL.md`
