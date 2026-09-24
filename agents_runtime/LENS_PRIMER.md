# Lens Primer

**Practical guide for agents working with Lens-based IntentGraph I/O**

---

## Core Concepts

**Lens = working memory for a task**
- Snapshot of graph focused on target area
- Budget-limited (default 30 nodes)
- Tracks changes vs source graph
- Two operation types: viewport (adjust view) vs graph (actual edits)

**LOD levels** (Level of Detail):
- `skeleton`: uid + name only
- `lean`: + intent + epistemic_state
- `full`: all fields

**IV_ pattern** (LOD assignment):
- `_` (full): target + direct neighbors
- `I` (lean): ancestors of target
- `V` (lean): all L1 nodes
- Rest: skeleton

**IntentLink visibility**:
- Present if both endpoints ≥ lean
- Description shown if ≥1 endpoint full

---

## Operational Rules

### Reading

**Initial read**: Full lens.yaml once at session start (build mental model of tree)
**After edits start**: Never re-read entire lens.yaml
**Spot checks**: `ig-tool node show -g graph.json --uid UID` for individual nodes
**Structure check**: `ig-tool lens tree -l lens.yaml` if lost orientation
**Stats**: `ig-tool lens info -l lens.yaml` for metadata only

**Pattern**: Read whole lens once → work with node-by-node spot checks → review via diff

### Editing

**Never edit YAML directly**. Use CLI commands:

```bash
# Node operations
ig-tool node create -g graph.json --uid UID --name "N" --intent "I" --parent P -o graph.json
ig-tool node set -g graph.json --uid UID --intent "New" -o graph.json
ig-tool node reparent -g graph.json --uid CHILD --under PARENT -o graph.json
ig-tool node remove -g graph.json --uid UID --recursive -o graph.json

# Link operations
ig-tool link create -g graph.json --src S --dst D --intent "I" -o graph.json
ig-tool link set -g graph.json --uid UID --intent "New" -o graph.json
ig-tool link remove -g graph.json --uid UID -o graph.json

# Batch (atomic multi-op)
ig-tool apply -g graph.json --batch batch.yaml -o graph.json
```

**Batch format**:
```yaml
operations:
  - op: node.create
    uid: ROOT.5
    name: "Name"
    intent: "Intent"
    parent: ROOT
  - op: node.set
    uid: ROOT.1
    intent: "Updated"
  - op: link.create
    src: ROOT.1
    dst: ROOT.2
    intent: "Link intent"
```

### Viewport Adjustment

```bash
# LOD changes
ig-tool lens promote -l lens.yaml --uid UID -o lens.yaml
ig-tool lens demote -l lens.yaml --uid UID -o lens.yaml
ig-tool lens set-lod -l lens.yaml --uid UID --lod (skeleton|lean|full) -o lens.yaml

# Focus change
ig-tool lens focus -l lens.yaml -g graph.json --uid NEW_TARGET -o lens.yaml

# Scope changes
ig-tool lens prune -l lens.yaml --uid UID -o lens.yaml
ig-tool lens expand -l lens.yaml -g graph.json --uid UID --depth N -o lens.yaml
ig-tool lens set-budget -l lens.yaml -g graph.json -b N -o lens.yaml
```

**After viewport changes**: Use `node show` for spot checks on specific nodes (not full re-read).

### Review & Commit

```bash
# Review changes
ig-tool lens diff -l lens.yaml -o diff.yaml

# Discard if wrong
ig-tool lens discard -l lens.yaml -o lens.yaml

# Apply (orchestrator runs this)
ig-tool lens apply -l lens.yaml -g graph.json -o graph.json
```

---

## Workflow Pattern

1. **Receive** lens.yaml from orchestrator
2. **Orient** - read full lens.yaml once (build mental model)
3. **Adjust viewport** if needed (promote/expand nodes)
4. **Work** - make graph edits via CLI commands, use `node show` for spot checks
5. **Review** with `lens diff` (shows all changes)
6. **Return** to orchestrator (will run `lens apply`)

---

## Common Patterns

**Explore unknown area**:
```bash
ig-tool lens promote -l lens.yaml --uid ROOT.2 -o lens.yaml
ig-tool lens expand -l lens.yaml -g graph.json --uid ROOT.2 --depth 2 -o lens.yaml
ig-tool node show -g graph.json --uid ROOT.2  # spot check specific node
```

**Create related nodes**:
```yaml
# batch.yaml
operations:
  - op: node.create
    uid: ROOT.1.2.1
    name: "Schema"
    intent: "..."
    parent: ROOT.1.2
  - op: node.create
    uid: ROOT.1.2.2
    name: "Migration"
    intent: "..."
    parent: ROOT.1.2
  - op: link.create
    src: ROOT.1.2.1
    dst: ROOT.1.2.2
    intent: "Schema changes trigger migrations"
```
```bash
ig-tool apply -g graph.json --batch batch.yaml -o graph.json
```

**Iterative refinement**:
```bash
ig-tool node set -g graph.json --uid ROOT.1.2 --intent "First draft" -o graph.json
ig-tool lens diff -l lens.yaml -o diff.yaml  # check
ig-tool node set -g graph.json --uid ROOT.1.2 --intent "Refined" -o graph.json
ig-tool node set -g graph.json --uid ROOT.1.2 --constraints "C1" --constraints "C2" -o graph.json
```

---

## Anti-Patterns

**Don't**: Re-read lens.yaml after each edit
**Do**: Use `node show` for spot checks on specific nodes

**Don't**: Edit YAML files manually
**Do**: Use CLI commands (validated, atomic)

**Don't**: Ignore budget constraints
**Do**: Check `lens info`, prune or increase budget consciously

**Don't**: Skip `lens diff` before commit
**Do**: Always review changes before handing back

**Don't**: Create nodes without --parent
**Do**: Specify parent (all nodes except root need parent)

---

## Performance

- Batch viewport changes, single refresh at end
- Use `batch` for multiple graph edits (1 graph load vs N)
- Prefer `node show` over full lens re-read for spot checks
- Don't render tree unnecessarily (use `lens info` for stats)

---

## Error Recovery

**Validation failure**: Check current state with `node show`, use different UID or update existing

**Budget exceeded**: `lens prune --uid UID` or `lens set-budget -b N`

**Wrong target**: `lens focus --uid CORRECT_TARGET`

**Wrong edits**: `lens discard` (reverts all changes since last apply)

**Batch failure**: All operations rolled back automatically, fix batch.yaml and retry

---

## Quick Reference

| Task | Command |
|------|---------|
| Initial view | Read lens.yaml directly (once) |
| Spot check node | `node show -g graph.json --uid UID` |
| Tree structure | `lens tree -l lens.yaml` |
| Stats | `lens info -l lens.yaml` |
| Increase detail | `lens promote -l lens.yaml --uid UID -o lens.yaml` |
| Refocus | `lens focus -l lens.yaml -g graph.json --uid UID -o lens.yaml` |
| Create node | `node create -g graph.json --uid UID --name N --intent I --parent P -o graph.json` |
| Update node | `node set -g graph.json --uid UID --intent "New" -o graph.json` |
| Create link | `link create -g graph.json --src S --dst D --intent I -o graph.json` |
| Multi-op | `batch -g graph.json -i batch.yaml -o graph.json` |
| Review | `lens diff -l lens.yaml -o diff.yaml` |
| Revert | `lens discard -l lens.yaml -o lens.yaml` |

---

**Key principle**: Read once, edit through tools, refresh minimally.

Reference: agents/PRIMER_TOOLS.md (command guide), .claude/skills/ig-tool-*/SKILL.md (exact syntax), foundation_and_formalism/LENS_REDESIGN_SPEC.md (design rationale)
