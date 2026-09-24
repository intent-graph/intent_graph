# PRIMER_02_NAVIGATION

How to navigate an IntentGraph using Lens. Assumes PRIMER_00 and PRIMER_01.

---

## Why Lens

Full graph cannot fit in context. Lens = dynamic view with variable LOD. Full detail where focused, orientation context nearby, minimal noise elsewhere.

## LOD Levels

| Level | Content | ~Tokens |
|-------|---------|---------|
| `skeleton` | uid + name only | ~5 |
| `lean` | + intent + epistemic_state | ~50-100 |
| `full` | all fields | ~200-500 |

## IV_ Pattern (Default LOD Assignment)

When Lens built around a target:
- **`_` (ground bar)** — target + direct neighbors (parent, children, link endpoints) → `full`
- **`I` (vertical stroke)** — ancestors from target to root → `lean`
- **`V` (brim)** — all L1 children of root → `lean`
- **Everything else** → `skeleton`

Effort hint steers expansion: quick → keep lean, avoid promoting; thorough → promote/expand where helpful.

---

## Navigation Decisions

| Need | Action |
|------|--------|
| More detail on distant node | `lens promote` |
| See children of collapsed node | `lens expand` |
| Big-picture overview | `lens tree` |
| Subtree irrelevant | `lens prune` |
| Task about different node | `lens focus` |
| Node less relevant | `lens demote` |

### Query vs Viewport

**Query** = spot check (one node, no viewport change): `query --node`, `--links`, `--projection-links UID` (inter), `--ancestors`, `--neighbors`.
**Viewport** = persistent change for ongoing work: promote, expand, prune, focus.

### Budget Management

Check: `lens info`. When exceeded: (1) prune irrelevant subtrees, (2) demote full→lean, (3) increase budget (last resort). Budget forces focus — remove noise, don't inflate.

---

## Navigation Workflow

1. **Orient** — `lens tree` for ASCII overview
2. **Adjust** — Promote/expand relevant, prune irrelevant
3. **Work** — Make edits (PRIMER_03A)
4. **Spot-check** — Query commands, not full re-reads
5. **Review** — `lens diff` before committing

Do NOT re-read lens.yaml after every change.
