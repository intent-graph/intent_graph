# Steward Mode 2: Structural Review

On-demand, read-only assessment. No edits applied.

## Tool use protocol (binding)

Before any ig-tool invocation:
  1. Consult the relevant Skill: `ig-tool-{lens,graph,graph-edit,query,obsidian,workflow}`.
  2. If unsure of syntax, run `ig-tool <cmd> --help`.
Inline examples below are illustrative shorthand; the Skill is authoritative on flags.

## Workflow

```
Receive: graph.json + projection_ig.json
```

1. Generate tree overview + structure: `ig-tool query -g graph.json --overview -o tree.yaml` and `ig-tool query -g graph.json --structure -o structure.yaml`
2. For each level:
   - Fan-out: children per node
   - Constraint load: constraints per node
   - Intentlink density: connections at this level
   - Sibling similarity: siblings sharing identical constraints?
3. Cross-level coherence:
   - Parent intents subsume children? (T4 smell test)
   - Subtrees that should merge? (shared intentlinks, similar intent)
   - Nodes to reparent? (more links to non-siblings than siblings)
4. PIG health:
   - Coverage: product nodes with rendering-relevant design_notes but no PIG observation?
   - Staleness: PIG observations from earlier iterations still accurate?
   - Compaction: multiple PIG observations that can merge?

## Output

Write `output_structural_review.yaml` to the step folder:

```yaml
structural_review:
  summary: "Graph has 6 nodes, 5 intentlinks, depth 2. Well-balanced."

  level_analysis:
    - level: 0
      nodes: ["ROOT"]
      fan_out: 5
      assessment: "5 children reasonable for a pipeline."
    - level: 1
      nodes: ["DISC", "PARSE", "VAL", "RPT", "NORM"]
      assessment: "All leaves. Constraint counts: DISC(10), PARSE(7), VAL(10), RPT(4), NORM(7)."

  structural_issues:
    - type: sibling_affinity    # or: constraint_density, depth_imbalance, etc.
      nodes: ["DISC", "PARSE"]
      detail: "DISC delegates to PARSE. PARSE has no other consumers."
      severity: warning
      proposed_action: "Reparent PARSE under DISC."

  pig_health:
    coverage: "16/24 PIG-PY nodes have observations."
    staleness: "All from ROOT iteration."
    compaction_candidates: []

  proposed_restructuring:
    - action: reparent    # or: split, merge
      node: PARSE
      current_parent: ROOT
      proposed_parent: DISC
      rationale: "PARSE is only consumed by DISC — sub-concern, not peer."
```
