# Steward Mode 3: Target Recommendation

Runs at every `*.PICK` step. Recommends next target from the queue.

## Tool use protocol (binding)

Before any ig-tool invocation:
  1. Consult the relevant Skill: `ig-tool-{lens,graph,graph-edit,query,obsidian,workflow}`.
  2. If unsure of syntax, run `ig-tool <cmd> --help`.
Inline examples below are illustrative shorthand; the Skill is authoritative on flags.

## Workflow

```
Receive: graph.json + projection_ig.json + workflow_state.json + workflow type
```

1. **Decide from the structure, not from full content.**
   Run `ig-tool query -g graph.json --structure -o structure.yaml` and make your recommendation from that. The structure gives you topology (who connects to whom), fill levels (which nodes are fleshed out vs hollow), and epistemic states — that is sufficient for PICK in the vast majority of cases.
   - **Do not** load the full graph, a lens, or `--overview` as a first step. PICK is about *where* to go, not *what's there*.
   - **Escalation:** if the structure alone leaves the decision ambiguous (e.g., two candidates with identical fill and epistemic state at the same level), you may query individual nodes for full detail using `ig-tool query -g graph.json --node UID -o node.yaml` on the specific candidates. This is a targeted probe, not a bulk load — query only the 2-3 nodes you need to break the tie.
2. Review queue in context:
   - What was just completed? (last processed_targets entry)
   - Structural issues from last COMMIT affecting ordering?
   - New children queued by last COMMIT?
3. Ordering principle — **balanced breadth-first**:
   - **Primary goal: keep the tree balanced.** Don't let one subtree race ahead while siblings remain skeletal. Complete all nodes at the shallowest unfinished depth before descending. This maximizes coverage if the workflow is cut short and avoids lopsided graphs.
   - **Within same level:** data-flow ordering via intentlinks (src before dst), then dependency density.
   - **Incompleteness penalty:** a node with no fill (only uid+name, no intent written yet) among filled siblings is a gap — prioritize it. Use the `--structure` fill comments to spot these. An isolated undefined node next to defined peers is more urgent than deepening a well-developed subtree.
   - **Workflow overrides:**
     - **Declare/Distill:** strict breadth-first (primary), data-flow within level (secondary).
     - **Project:** depth-first within subtrees, breadth-first across subtrees.
4. Tiebreakers (when multiple candidates are at the same level with similar fill):
   - **Epistemic state** — but only meaningful for nodes that have already been filled. Comparing `undecided` vs `known` on two filled nodes is a real signal. Comparing epistemic states on empty vs filled nodes is noise — the empty one wins by the incompleteness rule above, not by epistemic urgency.
   - Intentlink readiness (neighbors already processed → richer context when this node's turn comes)
   - Constraint inheritance freshness (relevant when comparing nodes under different parents)
5. Present recommendation + rationale

**Bootstrap:** Queue empty + graph empty → recommend ROOT. Queue empty + graph exists → recommend pause.

**Human override:** Recommendation is a suggestion. Human confirms or overrides.

## Output

Write `output_target_recommendation.yaml` to the step folder:

```yaml
target_recommendation:
  recommended: "PARSE"
  rationale: |
    DISC just completed. PARSE is next in data-flow order (DISC_PARSE link).
    Processing PARSE unblocks VAL. RPT is terminal, last.
  queue_snapshot: ["PARSE", "VAL", "NORM", "RPT"]
  alternatives:
    - target: "VAL"
      reason: "High priority — 10 constraints, most complex L1 node"
  bootstrap: false
  pause: false
```

## Summary to Orchestrator

```yaml
output_file: "output_target_recommendation.yaml"
summary: "Recommended PARSE (data-flow order after DISC). Queue: [PARSE, VAL, NORM, RPT]."
metrics:
  recommended_target: "PARSE"
  queue_size: 4
  alternatives_considered: 2
status: "complete"
```
