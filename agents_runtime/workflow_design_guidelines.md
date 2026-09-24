# IntentGraph Workflow Design

**Status:** Draft — three workflows defined, engine requirements specified, step UIDs assigned.

---

## Workflows
<!-- Lines 9-25 -->

Three workflows, each with a distinct purpose:

| Workflow | UID Prefix | Purpose | Starting point | Primary agents | Document |
|----------|------------|---------|----------------|----------------|----------|
| **Declare** | `DECLARE.*` | Build intent from scratch (forward) | Empty graph or existing graph | Critic, Elicitor, Steward | [WORKFLOW_DECLARE.md](WORKFLOW_DECLARE.md) |
| **Distill** | `DISTILL.*` | Extract intent from existing code/docs (reverse) | Existing codebase + docs | Docreader, Extractor, Critic, Elicitor, Steward | [WORKFLOW_DISTILL.md](WORKFLOW_DISTILL.md) |
| **Project** | `PROJECT.*` | Generate code from intent (forward) | Refined IG + ProjectionIG + (optional) existing codebase | Designer, Generator, Verifier, Critic, Steward | [WORKFLOW_PROJECT.md](WORKFLOW_PROJECT.md) |

**Declare** and **Distill** are **graph-building workflows** — their output is a refined IntentGraph (+ ProjectionIG), not code. **Project** is a **code-producing workflow** — it consumes a settled graph and produces code. The two concerns (intent quality vs. code structure) are kept separate.

Declare and Distill share the same recursive **target-based loop**. Project uses a similar loop but with different steps (design → generate → verify instead of challenge → refine).

Both are orchestrated by the **main Claude Code session** (not a sub-agent). The workflow engine tracks state, validates ordering, and persists progress across sessions.

---

## Step UIDs
<!-- Lines 28-34 -->

Every workflow step has a codified name (UID) that serves three purposes:

1. **Traceability** — the workflow trace log records which step ran, enabling post-session review
2. **Communication** — humans and agents refer to steps by UID, not by ad-hoc descriptions
3. **State tracking** — the workflow engine stores the current step as a UID

### Naming Principles
<!-- Lines 37-41 -->

- **Prefix**: `DECLARE.*`, `DISTILL.*`, or `PROJECT.*` — identifies the workflow
- **Suffix**: semantically clear verb/noun summarizing what the step *does* (not which agent runs)
- **Shared suffixes**: steps that exist in both workflows use the same suffix (e.g., `.PICK`, `.REFINE`, `.COMMIT`)

### Declare Steps (`DECLARE.*`)
<!-- Lines 44-54 -->

| UID | Step | Actor | Description |
| --- | --- | --- | --- |
| `DECLARE.PICK` | Pick target | Steward | Recommend next target from queue with structural rationale |
| `DECLARE.SCOPE` | Build lens | System | Assemble target-adj IV-context lens via `ig-tool context` |
| `DECLARE.CHALLENGE` | Review intent | Critic | Structured issue list on the lens |
| `DECLARE.REFINE` | Dialogue | Elicitor ↔ Human ↔ Critic | Resolve issues, converge on edits |
| `DECLARE.ESCAPE` | Unstructured resolution | Human + agents | Escape hatch when scope exceeded |
| `DECLARE.COMMIT` | Apply & persist | Steward | Apply edits, audit structure, propagate constraints, reorder queue, persist |
| `DECLARE.RECHECK` | Re-review | Critic | Verify edits resolved the issues |

### Distill Steps (`DISTILL.*`)
<!-- Lines 57-70 -->

| UID | Step | Actor | Description |
| --- | --- | --- | --- |
| `DISTILL.MAP` | Build CodeMap | System | `CodeMap.build()` — structural overview (once at start) |
| `DISTILL.PICK` | Pick target | Steward | Recommend next target from queue with structural rationale |
| `DISTILL.SCOPE` | Build lens | System | Assemble target-adj IV-context lens via `ig-tool context` |
| `DISTILL.READ` | Ingest docs | Docreader | Propose intent from documentation |
| `DISTILL.EXTRACT` | Extract intent | Extractor | Ground/refine intent from code (CodeMap-assisted) |
| `DISTILL.CHALLENGE` | Review intent | Critic | Structured issue list (semantic quality + projection separation) |
| `DISTILL.REFINE` | Dialogue | Elicitor ↔ Human ↔ Critic | Resolve issues, converge on edits |
| `DISTILL.ESCAPE` | Unstructured resolution | Human + agents | Escape hatch |
| `DISTILL.COMMIT` | Apply & persist | Steward | Apply edits, audit structure, propagate constraints, reorder queue, persist |
| `DISTILL.RECHECK` | Re-review | Critic | Verify edits resolved the issues |

### Project Steps (`PROJECT.*`)
<!-- Lines 73-89 -->

| UID | Step | Actor | Description |
| --- | --- | --- | --- |
| `PROJECT.MAP` | Build CodeMap | System | `CodeMap.build()` on existing codebase (if any) |
| `PROJECT.PICK` | Pick target | Steward | Recommend next target subtree for code generation with structural rationale |
| `PROJECT.SCOPE` | Build lens | System | Broad lens via `ig-tool context` (full mode, larger budget for Designer) |
| `PROJECT.DESIGN` | Design architecture | Designer | Produce PIG-ARCH.* nodes + Target CodeMap YAML |
| `PROJECT.CLARIFY` | Refine ProjectionIG | Elicitor ↔ Human | Resolve rendering uncertainty — refine ProjectionIG nodes |
| `PROJECT.ARCHREV` | Review architecture | Critic | Architecture-specific issue review |
| `PROJECT.REFINE` | Refine architecture | Elicitor ↔ Human ↔ Critic | Resolve architecture issues |
| `PROJECT.GENERATE` | Generate code | Generator | Fill Target CodeMap skeleton with implementation |
| `PROJECT.VERIFY` | Validate code | Verifier | Run intent-derived tests against generated code |
| `PROJECT.COMMIT` | Apply & persist | Steward | Set `impl_pointers` (pointer strings: `path[::Symbol][ (lines X-Y)]`), audit structure, propagate constraints, reorder queue, persist |
| `PROJECT.RECHECK` | Re-review | Critic | Verify generated code satisfies intent + constraints |

---

## Workflow Trace
<!-- Lines 92-92 -->

### Purpose
<!-- Lines 95-99 -->

The trace is a **workflow-level log** — one entry per step transition. It shows the orchestration view: which step ran, on which target, what happened, and what the outcome was.

The trace is **separate from agent I/O logs** (`.ig_logs/{role}.jsonl`). Agent logs capture detailed input/output for training data. The trace captures the bird's-eye session flow for human review.

### Persistence
<!-- Lines 102-104 -->

File: `{graph_name}_trace.jsonl` — alongside `{graph_name}_workflow.json`.

### Entry Schema
<!-- Lines 107-122 -->

Each line is a JSON object:

```json
{"ts": "2026-02-17T14:30:45", "step": "DISTILL.EXTRACT", "target": "AUTH", "actor": "extractor", "action": "read auth.py (CodeMap: 3 functions, 2 call edges)", "result": "refined intent, +1 constraint, impl_pointers set"}
```

| Field | Type | Description |
| --- | --- | --- |
| `ts` | ISO timestamp | When the step executed |
| `step` | Step UID | Which workflow step (e.g., `DISTILL.EXTRACT`) |
| `target` | IntentNode UID | Which target node this step operates on |
| `actor` | string | Who performed it: `orchestrator`, `critic`, `elicitor`, `designer`, `generator`, `verifier`, `docreader`, `extractor`, `steward`, `system` |
| `action` | string | What happened (1-line summary) |
| `result` | string | What the outcome was (1-line summary) |

### Human-Readable Rendering
<!-- Lines 125-139 -->

```text
=== Workflow Trace: example_graph (Distill) ===

DISTILL.PICK      AUTH    steward       recommended AUTH (data-flow: ROOT→AUTH link, highest dependency density). Human confirmed.
DISTILL.SCOPE     AUTH    system        assembled lens context (5 nodes, 820 words, mode: lean)
DISTILL.READ      AUTH    docreader     ingested README.md §Authentication
DISTILL.EXTRACT   AUTH    extractor     read auth.py (3 functions, 2 call edges)
DISTILL.CHALLENGE AUTH    critic        2 issues: 1 major, 1 minor
DISTILL.REFINE    AUTH    elicitor      3 turns → edits converged
DISTILL.COMMIT    AUTH    steward       applied 2 edits, audited structure, queued AUTH.1, AUTH.2
DISTILL.RECHECK   AUTH    critic        clean — target approved
DISTILL.PICK      AUTH.1  steward       recommended AUTH.1 (breadth-first: sibling before depth, no cross-subtree links). Human confirmed.
```

### Infrastructure
<!-- Lines 142-152 -->

- **Trace:** `ig_agents/trace.py` — `WorkflowTrace` class with `record()`, `read()`, `render()`.
- **Orchestrator:** `orchestrator/` directory — shared protocol + per-workflow dispatch tables.
  - [orchestrator_protocol.md](orchestrator/orchestrator_protocol.md) — how to run steps, transition logic, format references, error handling.
  - [STEP_IO_PROTOCOL.md](orchestrator/STEP_IO_PROTOCOL.md) — **opt-in** filesystem-based I/O between orchestrator and agents. Bulk data (IG, ProjectionIG, source code, CodeMap) goes to disk in timestamped step folders; prompts carry task description + file pointers. Gives post-hoc observability and token efficiency.
  - [dispatch_declare.md](orchestrator/dispatch_declare.md) — Declare step sequence + per-step agent/context.
  - [dispatch_distill.md](orchestrator/dispatch_distill.md) — Distill step sequence + per-step agent/context.
  - [dispatch_project.md](orchestrator/dispatch_project.md) — Project step sequence + per-step agent/context.

---

## Shared Concepts
<!-- Lines 155-172 -->

Defined in the individual workflow documents, consistent across all three:

- **Target** — the intentnode being worked on
- **Target-adj** — 1-adjacency (target + parent + children + intentlinks + link neighbors)
- **Target queue** — ordered list of pending targets, persisted across sessions
- **Lens construction (v1)** — deterministic IV-shaped context from target:
  - **full mode**: all lens nodes full detail
  - **lean mode**: same lens nodes, but only target + direct neighbors are full detail; all other nodes are lean (`uid`, `name`, `intent`, `epistemic_state`)
- **Unstructured resolution** (`*.ESCAPE`) — escape hatch when problems exceed target-adj scope
- **Critic re-review** (`*.RECHECK`) — self-check after edits, before moving to next target
- **Target picking via Steward** (`*.PICK`) — not a simple queue-pop. The Steward agent recommends the next target with structural rationale (data-flow order, dependency density, constraint inheritance freshness, epistemic urgency). The human confirms or overrides. Invoked by the orchestrator like any other agent step.
- **Commit via Steward** (`*.COMMIT`) — not a mechanical system step. The Steward agent applies edits, audits structural invariants, propagates constraints to affected neighbors, reorders the target queue based on graph topology, and persists the graph. Invoked by the orchestrator like any other agent step. After COMMIT, the orchestrator exports Obsidian vaults (via `ig-tool obsidian export`) before advancing to PICK.
- **CodeMap** (Distill and Project) — structural graph of an existing codebase (from `ai_tooling/documentation_tools/codemap`). In Distill, provides context to Extractor for orientation. In Project, provides context to Designer for integration with existing code. Optional dependency — workflows degrade gracefully without it.
- **Intent insufficiency pause** (Project only) — when the Designer or Generator encounters intent that is too vague to act on, the Project workflow pauses and hands back to Declare/Distill for refinement.

---

## Workflow Engine Requirements
<!-- Lines 175-175 -->

### State Tracker
<!-- Lines 178-191 -->

Persists across Claude Code sessions. Must track:

| State | What it records |
|-------|----------------|
| **Current target** | Which node is being worked on right now (or null if paused) |
| **Target queue** | Ordered list of pending targets with priority/ordering rationale. The Steward agent reorders this queue at each `*.COMMIT` and recommends the next target at each `*.PICK`, both based on graph topology and constraint propagation; the engine persists the Steward's ordering. |
| **Processed targets** | Which targets have been completed, with summary of what happened (iterations, edits, escalations) |
| **Current step** | Step UID (e.g., `DISTILL.CHALLENGE`) — not a free-text description |
| **Graph path** | Where the IntentGraph JSON lives |
| **Workflow type** | `declare`, `distill`, or `project` |
| **Trace path** | Where the workflow trace JSONL lives |
| **Session history** | Full log of every iteration: target, edits applied, new targets queued, escalations, resolution entries |

### Navigation Helpers
<!-- Lines 194-199 -->

- `current_step()` — returns the step UID
- `previous_step()` — what was the last completed step UID?
- `next_step()` — what's the next step UID in the sequence?
- `status_summary()` — one-paragraph description of where we are

### Validation
<!-- Lines 202-210 -->

At any point, the engine can check:

- Is the current step valid given what's been completed?
- Have any steps been skipped?
- Are there targets that have been in the queue too long without processing?
- Is the graph consistent with the workflow state? (e.g., a target marked "processed" should have history entries)
- Has a target been through `*.RECHECK` before being marked done?

### Human Override
<!-- Lines 213-226 -->

The human can at any time:

- Skip a target (remove from queue with a note)
- Re-order the queue
- Force a target (jump to a specific node regardless of queue order)
- Enter unstructured resolution (`*.ESCAPE`) even if within target-adj scope
- Mark the workflow as done (even with targets remaining)
- Resume a paused workflow

All overrides are logged in the workflow trace with `actor: "human"`.

---

## Session Reuse Pattern
<!-- Lines 229-249 -->

Some steps are re-entered for the same target — notably `*.REFINE` after a RECHECK loop-back or after a human dialogue round. In these cases, the orchestrator should **resume the existing agent** rather than creating a fresh one.

**Mechanism:** The Task tool's `resume` parameter re-enters an agent with its full prior context intact. The orchestrator stores the `agent_id` returned by the first invocation and passes it on re-entry.

**State fields** (in `workflow_state.json`):

| Field | Purpose |
| ----- | ------- |
| `refine_agent_id` | Task tool's agent_id for the active Elicitor |
| `refine_agent_target` | Target UID when agent was created |
| `refine_dialogue_round` | Counter, incremented on each YIELD or RECHECK loop-back |

**Lifecycle:** Created on first `*.REFINE` for a target. Cleared when `*.PICK` selects a new target or the human overrides. Persisted in `workflow_state.json`.

**Applicability:** Currently defined for `*.REFINE` (Elicitor). The same pattern could apply to `PROJECT.CLARIFY` or any other step that re-enters with accumulated context.

**Canonical spec:** [STEP_IO_PROTOCOL.md §6a](orchestrator/STEP_IO_PROTOCOL.md#6a-resume-agent-when-re-entering-a-step-for-the-same-target).

---

## File-Based Dialogue Protocol
<!-- Lines 252-274 -->

When an agent needs human judgment (design decisions, ambiguous intent, scope questions), it creates structured dialogue files in `{step_folder}/human_dialogue/` rather than returning an inline escalation payload.

**Flow:**

1. Agent writes dialogue files (minimap, context summary, question files)
2. Agent returns `YIELD_FOR_INPUT` with `dialogue_folder` path
3. Orchestrator prints folder path to human (does NOT read files — context rule C7)
4. Human edits question files in-place (filling `<choice>` and `<comments>` tags)
5. Orchestrator resumes agent, pointing it to updated files
6. Agent regex-extracts responses and continues (may YIELD again or converge)

**Key properties:**

- **Same format as inline turns** — dialogue files mirror the Elicitor's two-section turn format (minimap + ask, then deepened context). The file IS the turn, just on disk.
- **Batch per round** — all question files for a round are created at once before YIELD. The human answers all, then confirms.
- **Grep-extractable responses** — human input is in `<choice>...</choice>` tag. Agent uses Grep tool (NOT Read) to extract answers without re-ingesting the question context.
- **Orchestrator is a relay** — it passes the folder path, never reads content.

**Canonical spec:** [STEP_IO_PROTOCOL.md §File-Dialogue Specification](orchestrator/STEP_IO_PROTOCOL.md#file-dialogue-specification).

---

## Open Questions
<!-- Lines 277-286 -->

**O1 — Lens size in practice:** How large does the target-adj lens get for real graphs? Needs testing on a large real-world graph.

**O2 — Critic re-review cost:** Full review or delta check against previous issue list? Start with full review.

**O3 — Cross-session context:** When a new session loads workflow state, how much context does it need? *Partially addressed:* Agent session reuse within a target (§Session Reuse Pattern) preserves dialogue context across REFINE loops. Cross-session context for full workflow resumption remains open.

**O4 — IV-context v2:** Should indirect neighbors receive multi-hop progressive collapsing beyond lean mode?

**O5 — Resolution mode guardrails:** Truly open, or with limits? Current design: truly open, everything logged.
