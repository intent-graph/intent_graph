# PRIMER_02_NAVIGATION

Purpose: How to navigate an IntentGraph using Lens. Assumes you have read PRIMER_00_PHILOSOPHY and PRIMER_01_SEMANTICS.

Audience: All agents working with Lens-based I/O.

---

## Why Lens?

The full graph cannot fit in context. You need bounded working memory that shows full detail where focused, orientation context for "where am I?", and minimal noise from irrelevant parts.

A Lens is a dynamic, personalized view of the graph. It maintains workable context size through Level of Detail (LOD) control. You manipulate the viewport to suit your task: promote nodes to see more detail, expand to see children, prune to remove irrelevant branches, refocus to shift target.

The Lens is not static. It adapts to your needs as you work.

---

## LOD Levels

Three levels of detail per node:

`skeleton` — uid + name only. Tells you a node exists and what it's called. ~5 tokens.

`lean` — + intent + epistemic_state. Tells you what it does and how certain it is. ~50-100 tokens.

`full` — all fields (constraints, design_notes, examples, impl_pointers, history). Complete context. ~200-500 tokens.

Lens assigns LOD per node following the IV_ pattern (see below). You adjust it via promote/demote.

---

## IV_ Pattern (Default LOD Assignment)

When a Lens is built around a target node:

- `_` (ground bar) — target + direct neighbors (parent, children, intentlink endpoints) → full LOD
- `I` (vertical stroke) — all ancestors from target to root → lean LOD
- `V` (brim) — all L1 children of root (top-level modules) → lean LOD
- Everything else → skeleton LOD

This ensures you have full detail where you're working, visibility of "where am I?" (ancestors), and awareness of project structure (L1), without overwhelming detail from distant parts.

**Execution context:** Your **effort hint** (see PRIMER_04_WORKFLOWS §Execution context) may steer how much you expand: quick pass → keep LOD lean, avoid promoting distant nodes; thorough → promote and expand where it helps the task.

---

## Orientation: Understanding Where You Are

### Use ASCII tree for full-graph overview

```bash
ig-tool lens tree -l lens.yaml
```

This renders the entire tree structure with LOD markers. Use this when you need to see the big picture: how many nodes, what the top-level structure is, where your target sits.

Example output:
```
ROOT [lean]
├── DISCOVER [lean]
│   ├── DISCOVER.1 [full] ← target
│   └── DISCOVER.2 [lean]
├── EXTRACT [skeleton]
└── FORMAT [skeleton]
    ├── FORMAT.1 [skeleton]
    └── FORMAT.2 [skeleton]
```

You can see: DISCOVER.1 is the target (full), DISCOVER is its parent (lean), EXTRACT and FORMAT are siblings of DISCOVER (skeleton). The tree shows structure; LOD shows focus.

### Use treearcs for specific parent-child queries

The `treearcs` section in lens.yaml shows all parent-child relationships:

```yaml
treearcs:
  - parent: ROOT
    child: DISCOVER
  - parent: DISCOVER
    child: DISCOVER.1
  - parent: DISCOVER
    child: DISCOVER.2
```

Use this to verify: "What is DISCOVER.1's parent?" (DISCOVER). "What are DISCOVER's children?" (DISCOVER.1, DISCOVER.2).

### Use LOD to identify working zone

Check each node's `lod` field:
- `full` → your working zone (you have complete context)
- `lean` → orientation context (you know what it does)
- `skeleton` → awareness only (you know it exists)

If you're tempted to modify a skeleton node, stop. Promote or query it first.

---

## Navigation Decisions

### When to adjust viewport

Need more detail on distant node? → `lens promote` (PRIMER_TOOLS §Viewport Operations)
Need to see children of collapsed node? → `lens expand` (PRIMER_TOOLS §Viewport Operations)
Need big-picture overview? → `lens tree` (PRIMER_TOOLS §Viewport Operations)
Subtree irrelevant, cluttering view? → `lens prune` (PRIMER_TOOLS §Viewport Operations)
Realize task is about different node? → `lens focus` (PRIMER_TOOLS §Viewport Operations)
Node less relevant than expected? → `lens demote` (PRIMER_TOOLS §Viewport Operations)

### When to query vs viewport adjust

Use query for spot checks (inspect one node without changing viewport):
- Need full detail on one node? → `query --node` (PRIMER_TOOLS §Query Operations)
- Need to see intentlinks? → `query --links` (PRIMER_TOOLS §Query Operations)
- Need inter intentlinks for a node? → `query --projection-links UID` (optional `-m manifest` for resolve)
- Need ancestors path? → `query --ancestors` (PRIMER_TOOLS §Query Operations)
- Need immediate context? → `query --neighbors` (PRIMER_TOOLS §Query Operations)

Use viewport operations when you'll work in that area (persistent change to Lens).

### Budget Management

Check status: `lens info` (PRIMER_TOOLS §Viewport Operations)

When budget exceeded:
1. Prune irrelevant subtrees (preferred)
2. Demote full nodes to lean
3. Increase budget via `lens set-budget` (last resort)

Budget forces focused reasoning. Don't inflate budget — remove noise.

---

## Navigation Workflow

1. **Orient** — Read lens.yaml once OR use `lens tree` for ASCII overview (PRIMER_TOOLS §Viewport Operations)
2. **Adjust viewport** — Promote/expand relevant nodes, prune irrelevant branches (see Navigation Decisions above)
3. **Work** — Make edits (see PRIMER_03A_EDITING)
4. **Spot-check** — Use query commands for individual checks, not full re-reads (PRIMER_TOOLS §Query Operations)
5. **Review** — Use `lens diff` before committing (PRIMER_TOOLS §Review Operations)

Do NOT re-read lens.yaml after every change. Orient once, adjust as needed, use spot checks.

---

## Next Steps

After reading this primer:

- To modify graphs: Read PRIMER_03A_EDITING (decomposition, content migration, link creation)
- For command syntax: See PRIMER_TOOLS (command reference catalog)
- To understand workflows: Read PRIMER_04_WORKFLOWS (Declare, Distill, Project step sequences)
