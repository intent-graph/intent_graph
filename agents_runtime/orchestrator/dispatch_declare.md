# Dispatch Table: Declare Workflow

**Workflow:** Declare (forward intent creation)
**Full spec:** [WORKFLOW_DECLARE.md](../WORKFLOW_DECLARE.md)

---

## Step Sequence

```
DECLARE.PICK → DECLARE.SCOPE → DECLARE.CHALLENGE → DECLARE.REFINE
                                                        ↓ converges
                                              DECLARE.COMMIT → DECLARE.RECHECK
                                                        ↑ issues     ↓ clean
                                                   DECLARE.REFINE   DECLARE.PICK
```

Escape hatch: `DECLARE.ESCAPE` between REFINE and COMMIT when scope is exceeded.

---

## Per-Step Dispatch

### `DECLARE.PICK`

**Bootstrap shortcut:** If the graph is empty (zero nodes), the orchestrator skips the Steward invocation entirely. The target is deterministically ROOT — set `current_target = ROOT` in workflow state, record trace with `actor: "system"`, and proceed directly to `DECLARE.SCOPE`.

| Field | Value |
| --- | --- |
| **Actor** | Steward *(skipped on bootstrap — see above)* |
| **Agent** | `.claude/agents/ig-steward-agent.md` |
| **Context** | Current graph.json + projection_ig.json + workflow_state.json (target queue, processed targets) + workflow type. |
| **Action** | Steward recommends the next target with structural rationale (Mode 3: Target recommendation). Considers data-flow order, dependency density, constraint inheritance freshness, intentlink readiness, and epistemic urgency. If queue empty + graph exists → recommends pause. **Human confirms or overrides.** |
| **Output** | Target recommendation YAML (recommended UID + rationale + alternatives). Mode module: `ig-steward-mode-pick.md`. |
| **Next** | `DECLARE.SCOPE` |

### `DECLARE.SCOPE`

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — direct CLI invocation |
| **Context** | Target UID from `workflow_state.json` → `current_target`. |
| **Action** | Run `ig-tool lens build -g graph.json -t {target_uid} -b 30 -o {step_folder}/lens.yaml` then `ig-tool lens show -l {step_folder}/lens.yaml -o {step_folder}/input_lens.yaml`. If text is too large, rebuild with reduced budget (`-b 15`) or narrower scope. Record the lens summary (nodes, words, budget) in the trace. |
| **Output** | `{step_folder}/lens.yaml` — standalone lens file. `{step_folder}/input_lens.yaml` — agent text (full tree view with IV_ LOD filtering) for downstream agents. |
| **Next** | `DECLARE.CHALLENGE` |
| **If context assembly fails** | Log error, enter `DECLARE.ESCAPE`. |

### `DECLARE.CHALLENGE`

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Agent** | `.claude/agents/ig-critic-agent.md` |
| **Context** | Serialized lens YAML (from `ig-tool lens show`), using IV-context with full tree view. No source code (this is Declare — no code exists). |
| **Output** | Structured issue list (YAML). See Critic §Output Format. |
| **Next** | If issues → `DECLARE.REFINE`. If clean → `DECLARE.RECHECK` (skip dialogue). |

### `DECLARE.REFINE`

| Field | Value |
| --- | --- |
| **Actor** | Elicitor ↔ Human ↔ Critic |
| **Agent** | `.claude/agents/ig-elicitor-agent.md` |
| **Context** | Lens YAML + Critic issue list. If re-entering after RECHECK, include updated issue list. Elicitor can invoke `ig-tool lens focus/promote/demote` to adjust viewport, `ig-tool lens prune/expand` to manage scope, `ig-tool node create/set/reparent/remove` to edit graph, `ig-tool link create/set/remove` to edit links. |
| **Action** | Elicitor presents issues one at a time. Human responds. Elicitor proposes edits. Human approves/rejects. Loop until convergence. |
| **Output** | Proposed edits (via `ig-tool node/link create/set/remove` or `ig-tool apply --batch`). May also produce new target UIDs to queue. |
| **Next** | If converges within target-adj → `DECLARE.COMMIT`. If scope exceeded → `DECLARE.ESCAPE`. |

### `DECLARE.ESCAPE`

| Field | Value |
| --- | --- |
| **Actor** | Human + agents |
| **Agent** | None — open mode, human drives |
| **Context** | Full workflow state. Human can change target, reshape view, edit outside target-adj, etc. |
| **Action** | Log all actions in trace with `actor: "human"`. |
| **Output** | Whatever edits the human produces. |
| **Next** | `DECLARE.COMMIT` |

### `DECLARE.COMMIT`

| Field | Value |
| --- | --- |
| **Actor** | Steward |
| **Agent** | `.claude/agents/ig-steward-agent.md` |
| **Context** | Product lens edits (from REFINE/ESCAPE) + current graph.json + projection_ig.json + workflow_state.json + target queue. |
| **Action** | Steward runs five phases: (1) Review edits via `ig-tool lens diff`. (2) Apply edits via `ig-tool lens apply -l ... -g ... -o ...`. (3) Structural audit — fan-out, constraint density, depth balance, orphaned links, epistemic drift. (4) Cross-level constraint inheritance — annotate child nodes with inherited parent constraints in `design_notes`. (5) Queue intelligence — reorder target queue based on data-flow and dependency analysis. (6) Persist — save graph, workflow state. Mode module: `ig-steward-mode-commit.md`. |
| **Output** | Steward report (edits applied, structural issues, inherited constraints, reordered queue) + persisted artifacts |
| **Next** | `DECLARE.RECHECK` |

### `DECLARE.RECHECK`

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Agent** | `.claude/agents/ig-critic-agent.md` |
| **Context** | Updated lens YAML (after edits applied). Same as CHALLENGE context. |
| **Output** | Structured issue list. |
| **Next** | If issues remain → `DECLARE.REFINE` (same target, another pass). If clean + more targets → `DECLARE.PICK`. If clean + queue empty → workflow complete. |
