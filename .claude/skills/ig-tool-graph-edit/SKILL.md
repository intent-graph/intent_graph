---
name: ig-tool-graph-edit
description: >
  Reference for ig-tool graph mutation commands: node, link, apply (single + batch), parse.
  Use when directly creating, updating, or deleting nodes and links in an IntentGraph.
user-invocable: false
---

# ig-tool — Graph Edit (Direct Mutations)

Direct graph mutations — create, update, delete nodes and links atomically.
Use these when you need precise control. For lens-mediated edits, see the ig-tool-lens skill.

**Formats:** `-g` (graph input) and `-o` (graph output) accept `.json`, `.yaml`, or `.yml`; format is inferred from extension.

## When to Use Direct Edits vs Lens

| Approach | When |
|----------|------|
| **Lens** (build → edit → diff → apply) | Agent workflows: explore, reshape, stage changes, review, commit |
| **Direct** (node/link) | Precise single mutations, orchestrator-driven bulk ops, programmatic scripts |
| **apply** | Applying agent-produced YAML diffs (§2 view or §5 diff format) |
| **apply --batch** | Atomic multi-operation YAML file |

---

## node — Single Node Operations

### create

```bash
ig-tool node create -g graph.json --uid UID --name "Name" --intent "Intent" -o graph.json
ig-tool node create -g graph.json --uid UID --name "Name" --intent "Intent" --parent PARENT_UID -o graph.json
```

| Flag | Required | Notes |
|------|----------|-------|
| `--uid` | Yes | Must be unique |
| `--name` | Yes | Display name |
| `--intent` | Yes | Intent body |
| `--parent` | **No** | Parent node UID — omit ONLY for the root node. Otherwise it must be an **existing** UID (often `ROOT`, but check with `ig-tool query --structure -g graph.json` if unsure — `ig-tool init` without `--root`/`--template` produces a graph with zero nodes, in which case you must create the root first without `--parent`). Non-existent parent → `Node 'XXX' does not exist`. |
| `--constraints` | No | Repeatable: `--constraints "C1" --constraints "C2"` |
| `--examples` | No | Repeatable |
| `--effort` | No | Free text (e.g. `"high correctness critical"`) — never a number |
| `--impl-pointer` | No | Repeatable, one pointer per flag. Grammar: `path[::Symbol[.member]][ (lines X-Y)]` |
| `--data-registry` | No | JSON dict |
| `-m` / `--role` | No | Provenance: one-liner note / agent role (see Provenance section) |
| `-o` | Yes | Output graph |

### set — Update fields

```bash
ig-tool node set -g graph.json --uid UID --intent "New intent" --epistemic-state known -o graph.json
```

Settable fields: `--name`, `--intent`, `--epistemic-state` (free text per the primer convention — workflows define their own vocabulary, e.g. `known`, `undecided`, `excluded | reason: ...`), `--constraints` (**replaces all**), `--examples` (**replaces all**), `--design-notes`, `--effort` (free text), `--impl-pointer` (repeatable, **replaces all**), `--data-registry` (JSON).

**Clearing fields:** `--unset FIELD` (repeatable) resets an optional field to absent — lists to `[]`, scalars to `null`. Unsettable fields: `epistemic_state`, `constraints`, `examples`, `design_notes`, `effort`, `impl_pointers`, `data_registry`. A field cannot be both set and unset in one call.

```bash
ig-tool node set -g graph.json --uid UID --unset design_notes --unset effort -o graph.json -m "cleanup"
```

**CAUTION:** `--constraints` replaces the entire list. To add one constraint, you must pass all existing ones plus the new one.

**Strict updates:** unknown field names raise an error (no silent drops) — a typo'd batch key fails the batch.

### reparent — Move to different parent

```bash
ig-tool node reparent -g graph.json --uid CHILD_UID --under NEW_PARENT_UID -o graph.json
```

Flag is `--under`, not `--parent`.

### reorder — Change child ordering

```bash
ig-tool node reorder -g graph.json --parent PARENT_UID --children UID1 UID2 UID3 -o graph.json
```

**All children must be listed** in desired order (not just the ones you want to move).

### remove — Delete a node

```bash
ig-tool node remove -g graph.json --uid UID [--recursive] -o graph.json
```

Without `--recursive`: fails if node has children. With `--recursive`: deletes entire subtree.

### show — Read-only display

```bash
ig-tool node show -g graph.json --uid UID
```

Prints full YAML to stdout. No `-o` needed.

---

## link — IntentLink Operations

### create

```bash
ig-tool link create -g graph.json --src SRC_UID --dst DST_UID --intent "Intent" -o graph.json
```

Optional: `--uid LINK_UID` (auto-generated if omitted), `--tag TAG` (uid disambiguator), `--shape '{"type":"flow"}'` (JSON string), `--parent PARENT_LINK_UID` (link refinement — intra-graph links only).

Inter intentlinks: qualify either endpoint as `graph_id:node_uid` and the command auto-dispatches to the inter-link store (`--parent` rejected — refinement is intra-graph only).

### set

```bash
ig-tool link set -g graph.json --uid LINK_UID --intent "New intent" -o graph.json
```

Optional: `--shape '{"type":"dependency"}'`, `--parent PARENT_LINK_UID` (intra-graph only). `src`/`dst`/`uid` are immutable — delete and recreate instead.

### remove

```bash
ig-tool link remove -g graph.json --uid LINK_UID -o graph.json
```

---

## apply --batch — Atomic Multi-Operation

Apply multiple mutations in one atomic command from a YAML file.

```bash
ig-tool apply -g graph.json --batch batch.yaml -o updated_graph.json [--dry-run]
```

### Batch YAML Format

```yaml
operations:
  - op: node.create
    uid: ROOT.5
    name: "New Node"
    intent: "Intent description"
    parent: ROOT
    constraints:
      - "Must handle X"

  - op: node.set
    uid: ROOT.1
    intent: "Updated intent"
    epistemic_state: known
    unset: [design_notes]      # optional — clear fields (lists → [], scalars → null)

  - op: node.reparent
    uid: ROOT.2
    under: ROOT.1

  - op: node.remove
    uid: ROOT.3
    recursive: false

  - op: link.create
    src: ROOT.1
    dst: ROOT.2
    intent: "ROOT.1 calls ROOT.2"
    shape:
      type: flow
    parent: PARENT_LINK_UID    # optional — link refinement

  - op: link.set
    uid: ROOT.1->ROOT.2
    intent: "Updated link intent"

  - op: link.remove
    uid: ROOT.1->ROOT.2
```

**Operation names** use dot notation: `node.create`, `node.set`, `node.reparent`, `node.remove`, `link.create`, `link.set`, `link.remove`.

`--dry-run` validates and reports without applying.

---

## parse — Validate Agent-Produced Diffs

```bash
ig-tool parse -g graph.json -i output_edits.yaml [-o parsed.yaml]
```

Auto-detects §2 (view) vs §5 (diff) format. Reports edit count without mutating.

---

## apply — Apply Agent-Produced Diffs

```bash
ig-tool apply -g graph.json -i output_edits.yaml -o updated_graph.json [--role extractor] [--dry-run]
```

| Flag | Meaning |
|------|---------|
| `-i` | Agent output YAML (§2 or §5 format) |
| `--role` | Agent role for provenance (`who: agent:<role>`) |
| `-m` | One-liner history note (commit-style; omitted → auto diff summary) |
| `--dry-run` | Simulate without writing |

**CRITICAL:** The `-i` file must be in **§2 (view) or §5 (diff) format**. These are the agent text serialization formats defined in SERIALIZATION_FORMAT.md. §2 uses a `view:` header (legacy `frontier:` accepted on read).

**KNOWN ISSUE:** The Elicitor agent's custom edit YAML (with `operation`/`target_field`/`old_text`/`new_text` structure) is **NOT parseable** by `apply`. If you have Elicitor output, apply it programmatically via Python:

```python
from intentgraph.serial.agent_text import parse_agent_output, apply_edits
from intentgraph.serial.json_yaml import load_json, save_json

graph = load_json("graph.json")
edits = parse_agent_output(agent_yaml_text, graph)
log = apply_edits(graph, edits)  # no role param — provenance stamps at the ig-tool save boundary
save_json(graph, "updated_graph.json")
```

The original graph at `-g` is **never overwritten** — `-o` is required and writes to a new path.

## Provenance (write-boundary, all mutating commands)

History is stamped **automatically at every save** — `node`, `link`, `apply` (both modes), `init`, `lens apply`, `graph lens reintegrate`, `obsidian merge`. The save diffs loaded-vs-final state and appends one commit-style `HistoryEntry` per changed node (same message on all touched nodes, like one git commit spanning files). Never hand-edit `history`.

- `--role <role>` → `who: agent:<role>`. Without it, `who` resolves from `IG_ACTOR` env, then git `user.name`, then the OS user (GUI channels add `via:<channel>`).
- `-m "<one-liner>"` → the note; say *why*, not what. Omitted → auto diff summary (`"updated: intent, constraints"`, `"created"`, `"reparented"`).
- Trivial changes never stamp: sibling reorder, lens configs. Content and structural changes always do.

---

## Common Mistakes

1. **Wrong `op:` names in batch**: It's `node.create` not `create_node` or `node-create`.
2. **Missing `--under` in reparent**: The flag is `--under`, not `--parent` (which is for `node create`).
3. **Partial `--children` in reorder**: You must list ALL children, not just the ones changing position.
4. **`--constraints` replaces all**: There's no append mode. Always pass the full list.
5. **Sending Elicitor YAML to `apply`**: Use Python API instead (see above).
6. **Forgetting `-o`**: All mutation commands require `-o` for output. The source `-g` is never overwritten.
7. **Old names**: `ig-tool edit parse` → `ig-tool parse`; `ig-tool edit apply` → `ig-tool apply`; `ig-tool batch` → `ig-tool apply --batch`.
8. **Assuming root is named `ROOT`**: Examples use `ROOT` as a stand-in. The actual root UID depends on how the graph was built — `ig-tool init --root` produces UID `ROOT`, but a graph created from scratch (`ig-tool init` without flags) has **zero nodes** and any `--parent ROOT` will fail "Node 'ROOT' does not exist." Always check with `ig-tool query --structure -g graph.json` before assuming.
9. **Underscore in UID keywords (allowed since 2026-04-29)**: `LEXER_TOKENS`, `LEXER.PARSER_INTERFACE` are now valid. Pattern is `^[A-Z][A-Z0-9_]*$` for keyword segments (no leading underscore, no lowercase). Older docs claiming "no underscores" are stale.
