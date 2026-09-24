# Dispatch Table: Project Workflow

**Workflow:** Project (intent → code)
**Full spec:** [WORKFLOW_PROJECT.md](../WORKFLOW_PROJECT.md)

---

## Step Sequence

```
PROJECT.MAP (once, if existing code)
  ↓
PROJECT.PICK → PROJECT.SCOPE → PROJECT.DESIGN ←→ PROJECT.CLARIFY
  ↑                                  ↓
  |                        PROJECT.ARCHREV → PROJECT.REFINE → PROJECT.DESIGN
  |                              ↓ approved
  |                        PROJECT.GENERATE ←→ PROJECT.CLARIFY
  |                              ↓
  |                        PROJECT.VERIFY → PROJECT.COMMIT → PROJECT.RECHECK
  +————————————— clean ————————————————————————————————————————+
```

Pause exits: `PROJECT.DESIGN` or `PROJECT.GENERATE` → PAUSE (intent insufficient → return to Declare/Distill).

---

## Per-Step Dispatch

### `PROJECT.MAP` (bootstrap — once at start, if existing code)

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — run `codemap overview /path/to/project` via Bash |
| **Context** | Existing codebase root path |
| **Action** | Run `codemap overview {project_path}` via Bash to build CodeMap. Pass overview to Designer and Generator throughout. |
| **Output** | CodeMap overview YAML |
| **Next** | `PROJECT.PICK` |
| **If greenfield** | Skip. Record trace: `result: "greenfield — no existing code"`. |

### `PROJECT.PICK`

| Field | Value |
| --- | --- |
| **Actor** | Steward |
| **Agent** | `.claude/agents/ig-steward-agent.md` |
| **Context** | Current graph.json + projection_ig.json + workflow_state.json (target queue, processed targets) + workflow type (`project`). |
| **Action** | Steward recommends the next target **subtree** for code generation (Mode 3: Target recommendation). Ordering heuristic: depth-first within subtrees (generate children before integrating parent), breadth-first across subtrees, data-flow order via intentlinks. Also considers code coverage — subtrees with no generated code yet take priority. **Human confirms or overrides.** |
| **Output** | Target recommendation YAML (recommended UID + rationale + alternatives). Mode module: `ig-steward-mode-pick.md`. |
| **Next** | `PROJECT.SCOPE` |

### `PROJECT.SCOPE`

| Field | Value |
| --- | --- |
| **Actor** | System (you) |
| **Agent** | None — direct CLI invocation |
| **Context** | Target UID from `workflow_state.json` → `current_target`. |
| **Action** | Run `ig-tool lens build -g graph.json -t {target_uid} -b 50 -o {step_folder}/lens.yaml` then `ig-tool lens show -l {step_folder}/lens.yaml -o {step_folder}/input_lens.yaml`. Project uses broader budget (50 vs. 30) because the Designer needs cross-module context (target subtree + intentlink neighbors + ProjectionIG nodes + CodeMap overview). If text is too large, rebuild with reduced budget (`-b 30`) before escalating. Record the lens summary in the trace. |
| **Output** | `{step_folder}/lens.yaml` — standalone lens file. `{step_folder}/input_lens.yaml` — agent text (full tree view with IV_ LOD filtering) for Designer. |
| **Next** | `PROJECT.DESIGN` |
| **If context assembly fails** | Log error, enter `PROJECT.ESCAPE`. |

### `PROJECT.DESIGN`

| Field | Value |
| --- | --- |
| **Actor** | Designer |
| **Agent** | `.claude/agents/ig-designer-agent.md` |
| **Context** | `assemble_designer_context(graph, lens, projection_ig_path=..., codemap_project_path=...)`. Pass product lens + ProjectionIG + CodeMap overview. |
| **Action** | Produce architecture: PIG-ARCH.* nodes + Target CodeMap YAML. |
| **Output** | Two artifacts: (1) ProjectionIG architectural YAML, (2) Target CodeMap YAML. |
| **Next** | If **intent insufficient** → PAUSE. If **projection gap** → `PROJECT.CLARIFY`. Otherwise → `PROJECT.ARCHREV`. |

### `PROJECT.CLARIFY`

| Field | Value |
| --- | --- |
| **Actor** | Elicitor ↔ Human |
| **Agent** | `.claude/agents/ig-elicitor-agent.md` |
| **Context** | The rendering uncertainty (from Designer or Generator) + current ProjectionIG + the specific decision needed. |
| **Action** | Elicitor presents the rendering question. Human decides. Elicitor proposes new/refined ProjectionIG node(s). Human approves. |
| **Output** | New or refined ProjectionIG nodes (`PIG-` prefix). These are **durable** — they persist in the ProjectionIG and apply to future targets. |
| **Next** | Return to the step that triggered clarification (`PROJECT.DESIGN` or `PROJECT.GENERATE`). |

### `PROJECT.ARCHREV`

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Agent** | `.claude/agents/ig-critic-agent.md` |
| **Context** | Designer output (PIG-ARCH.* nodes + Target CodeMap YAML) + product lens + CodeMap overview (if available). |
| **Action** | Review architecture using issue types: `structural_cohesion`, `interface_completeness`, `codemap_divergence`. |
| **Output** | Structured issue list. |
| **Next** | If issues → `PROJECT.REFINE`. If clean → `PROJECT.GENERATE`. |

### `PROJECT.REFINE`

| Field | Value |
| --- | --- |
| **Actor** | Elicitor ↔ Human ↔ Critic |
| **Agent** | `.claude/agents/ig-elicitor-agent.md` |
| **Context** | Critic architecture issues + Designer output + product lens. |
| **Action** | Elicitor presents architecture issues. Human decides. Architecture decisions are revised. |
| **Output** | Revised architecture direction (fed back to Designer). |
| **Next** | `PROJECT.DESIGN` (Designer revises based on feedback). |

### `PROJECT.GENERATE`

| Field | Value |
| --- | --- |
| **Actor** | Generator |
| **Agent** | `.claude/agents/ig-generator-agent.md` |
| **Context** | Product lens YAML + ProjectionIG lens (including PIG-ARCH.* nodes) + Target CodeMap YAML + CodeMap overview (if available). Use `assemble_agent_context(graph, lens, target_uid={UID}, iv_context_mode="lean", target_codemap_text=..., codemap_project_path=...)`. |
| **Action** | Fill the Target CodeMap skeleton with implementation. Follow the structural plan. |
| **Output** | Code files on disk + updated lens YAML with `impl_pointers` populated (grammar: `path[::Symbol[ .member]][ (lines X-Y)]`). |
| **Next** | If **intent insufficient** → PAUSE. If **projection gap** → `PROJECT.CLARIFY`. Otherwise → `PROJECT.VERIFY`. |

### `PROJECT.VERIFY`

| Field | Value |
| --- | --- |
| **Actor** | Verifier |
| **Agent** | `.claude/agents/ig-verifier-agent.md` |
| **Context** | Product lens + generated code files + Target CodeMap YAML. |
| **Action** | Design and run intent-derived tests. Verify constraint satisfaction. Verify ProjectionIG adherence. |
| **Output** | Test results: pass/fail per test + summary. |
| **Next** | If tests pass → `PROJECT.COMMIT`. If tests fail → `PROJECT.GENERATE` (revision pass). If deep failure → `PROJECT.DESIGN` (architecture revision). |

### `PROJECT.COMMIT`

| Field | Value |
| --- | --- |
| **Actor** | Steward |
| **Agent** | `.claude/agents/ig-steward-agent.md` |
| **Context** | Product lens edits (with `impl_pointers` set by Generator) + PIG edits (from CLARIFY, if any) + current graph.json + projection_ig.json + workflow_state.json + target queue. |
| **Action** | Steward runs six phases: (1) Review edits via `ig-tool lens diff`. (2) Apply edits via `ig-tool lens apply` — apply node updates including `impl_pointers`, apply PIG updates. (3) Structural audit — verify code-to-intent mapping completeness, cross-reference `impl_pointers` with generated code. (4) Cross-level constraint inheritance. (5) Queue intelligence. (6) Persist both graphs, workflow state. Mode module: `ig-steward-mode-commit.md`. |
| **Output** | Steward report + persisted artifacts |
| **Next** | `PROJECT.RECHECK` |

### `PROJECT.RECHECK`

| Field | Value |
| --- | --- |
| **Actor** | Critic |
| **Agent** | `.claude/agents/ig-critic-agent.md` |
| **Context** | Updated lens + generated code + Target CodeMap. |
| **Action** | Final check: code matches Target CodeMap structure? All constraints satisfied? `impl_pointers` populated and traceable? |
| **Output** | Structured issue list. |
| **Next** | If issues → `PROJECT.DESIGN` (re-architecture). If clean + more targets → `PROJECT.PICK`. If clean + queue empty → workflow complete. |
