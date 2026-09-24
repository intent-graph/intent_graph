# Steward Mode 1: COMMIT Checkpoint

Primary invocation — runs at every `*.COMMIT` step.

## Tool use protocol (binding)

Before any ig-tool invocation:
  1. Consult the relevant Skill: `ig-tool-{lens,graph,graph-edit,query,obsidian,workflow}`.
  2. If unsure of syntax, run `ig-tool <cmd> --help`.
Inline examples below are illustrative shorthand; the Skill is authoritative on flags.

## Workflow

```
Receive: product lens edits + PIG edits + graph.json + projection_ig.json
         + workflow_state.json + target queue
```

### Phase 1 — APPLY (mechanical)

1. Parse product edits → `ig-tool parse -g graph.json -i edits.yaml -o parsed.yaml` → `ig-tool apply -g graph.json -i parsed.yaml -o updated.json --role steward`
2. Parse PIG edits → `ig-tool parse -g projection_ig.json -i pig_edits.yaml -o parsed.yaml` → `ig-tool apply -g projection_ig.json -i parsed.yaml -o updated_pig.json --role steward`
3. Queue new targets from REFINE output
4. If invariant violation → STOP, report, do not persist

### Phase 2 — AUDIT (structural judgment)

5. Fan-out: any node with >7 children? Flag.
6. Constraint density: any node with >10 constraints? Consider splitting.
7. Depth balance: sibling subtrees at wildly different depths? Flag.
8. Orphaned links: intentlink referencing nonexistent node?
9. Epistemic drift: parent "known" but child "undecided"? Flag (not necessarily wrong).
10. PIG alignment smell test (P4): product constraint mentioning language, library, class name, or file path?

### Phase 3 — INHERIT (cross-level constraint propagation)

11. For each newly queued child target: scan parent constraints for scope-level decisions.
12. Annotate child `design_notes += "Inherited from {parent_uid}: {constraint text}"`. Do NOT duplicate into child's `constraints` list.

### Phase 4 — QUEUE (intelligent ordering)

13. Reorder queue: data-flow order (intentlinks: src before dst) → dependency density (more unresolved links first) → breadth-first default.
14. Present reordered queue with rationale.

### Phase 5 — PERSIST

15. Save graph.json
16. Save projection_ig.json
17. Update workflow_state.json (current_step, target_queue, processed_targets)
18. Sync Obsidian vault (both graphs)
19. Append trace entry

## Output

Write `output_commit_report.yaml` to the step folder:

```yaml
steward_report:
  phase_apply:
    product_edits_applied: 5
    pig_edits_applied: 3
    targets_queued: ["DISC", "PARSE", "VAL"]
    invariant_violations: []

  phase_audit:
    structural_issues:
      - type: fan_out    # or: constraint_density, depth_balance, orphaned_link, epistemic_drift, pig_smell
        node: ROOT
        detail: "ROOT has 5 children at L1. Acceptable."
        severity: info   # info | warning | action_required

  phase_inherit:
    inherited_constraints:
      - parent: ROOT
        children: ["DISC", "PARSE"]
        constraint: "Pipeline is sequential: discover -> validate -> report."

  phase_queue:
    reordered_queue: ["DISC", "PARSE", "VAL", "NORM", "RPT"]
    rationale: "Data-flow order: DISC → PARSE → VAL → RPT. NORM after VAL."

  phase_persist:
    graph_saved: true
    pig_saved: true
    workflow_state_saved: true
    obsidian_synced: true
    node_count: 6
    link_count: 5
    pig_node_count: 26
```

## Summary to Orchestrator

```yaml
output_file: "output_commit_report.yaml"
summary: "Applied 6 product nodes + 7 links + 16 PIG updates. Audited (clean). Queued 5 targets. Persisted."
metrics:
  product_nodes: 6
  product_links: 7
  pig_nodes: 16
  structural_issues: 0
  queue_size: 5
status: "complete"
```
