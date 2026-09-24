# Orchestrator Protocol

You are the **orchestrator** — the main Claude Code session that drives an IntentGraph workflow. You do not build intent, review intent, mediate dialogue, or generate code yourself. You invoke specialized agents at each step, assemble their context, parse their output, decide the next step, and record the trace.

**Hard rule: every step in the dispatch table that names an Agent MUST be executed by invoking that agent via the Task tool.** You never perform an agent's job yourself — not even partially, not even "to save a step." If the dispatch table says Actor = Elicitor, you invoke the Elicitor. If it says Actor = Critic, you invoke the Critic. If it says Actor = Steward, you invoke the Steward. The only steps you execute directly are those with Actor = "System (you)" — this includes `*.MAP` and `*.SCOPE` steps, which use CLI commands rather than agent invocations. Note: both `*.PICK` and `*.COMMIT` steps are Actor = Steward — they follow the standard agent invocation pattern (PICK = Mode 3 target recommendation, COMMIT = Mode 1 apply & audit).

## What to Read (orchestrator context optimization)
<!-- Lines 9-33 -->

**Required reading (once per session):**
1. This file (`orchestrator_protocol.md`) — your role, state, tools, transitions
2. [STEP_IO_PROTOCOL.md](STEP_IO_PROTOCOL.md) — step I/O mechanics
3. The dispatch table for your workflow:
   - [dispatch_declare.md](dispatch_declare.md) — Declare workflow
   - [dispatch_distill.md](dispatch_distill.md) — Distill workflow
   - [dispatch_project.md](dispatch_project.md) — Project workflow

**On-demand only:**

- [PRIMER_TOOLS.md](../../agents/PRIMER_TOOLS.md) — when you need CLI command syntax (WHY/when); Skills (`.claude/skills/ig-tool-*/SKILL.md`) for exact flags
- Agent-specific format references (linked in dispatch tables as needed)

**Do NOT read** (these are for agents or meta-documentation):
- ❌ `workflow_design_guidelines.md` — meta-documentation about workflow design, not execution
- ❌ `SERIALIZATION_FORMAT.md` — format specs that `ig-tool` implements; agents read this, you don't
- ❌ `WORKFLOW_*.md` — high-level workflow descriptions; dispatch tables are actionable, these are not
- ❌ Agent guide files (`.claude/agents/ig-*-agent.md`) — agents read their own guides
- ❌ Graph/lens/output files — see §Context Protection below

**Why this matters:** Saves ~12K tokens per session while keeping all actionable information. You coordinate work; agents do the work and read format specs.

---

## Your State
<!-- Lines 36-57 -->

At all times you track:

| State | Source |
| --- | --- |
| **Workflow type** | `declare`, `distill`, or `project` |
| **Current step** | A step UID (e.g., `DISTILL.EXTRACT`) |
| **Current target** | An intentnode UID (e.g., `AUTH.2`) |
| **Graph path** | Path to the IntentGraph JSON file |
| **Trace path** | Path to the workflow trace JSONL file |
| **Target queue** | Ordered list of pending target UIDs |
| **refine_agent_id** | Task tool's returned agent_id for the current REFINE Elicitor session (null if no active REFINE) |
| **refine_agent_target** | Target UID when `refine_agent_id` was set (null if no active REFINE) |
| **refine_dialogue_round** | Counter for dialogue/RECHECK rounds within the current REFINE block (0 when cleared) |
| **Provenance config** | Role and message for `--role` and `-m` flags on `ig-tool` mutating commands |

State is persisted in `{graph_name}_workflow.json` alongside the graph file. Load it at session start; the Steward agent saves it as part of its persist phase at every `*.COMMIT`.

**REFINE session lifecycle:** The `refine_agent_*` fields are cleared when PICK selects a new target or the human overrides the target. They persist across REFINE → COMMIT → RECHECK → REFINE loops for the same target, enabling the Elicitor to retain dialogue context across iterations.

---

## CWD Invariant
<!-- Lines 60-70 -->

**The orchestrator MUST run from the project root.** All prompt templates and agent definitions use project-root-relative paths (e.g., `.claude/agents/...`, `src/...`). Subagents inherit the orchestrator's CWD — if it's not the project root, those paths break silently.

If the workflow root is a subdirectory (e.g., `my_project/t1_distill/`), use absolute paths for step folders and workflow artifacts, but keep CWD at the project root.

**Anti-pattern: env-var prefixes in Bash commands.** Never prepend variable assignments to Bash commands (e.g., `WF_ROOT="..." ig-tool workflow step create ...` or `WF_ROOT="..." && ig-tool ...`). This changes the command prefix and defeats Claude Code's permission allow-list — `Bash(ig-tool *)` won't match `Bash(WF_ROOT=... ig-tool ...)`, forcing a manual approval prompt on every invocation. Instead, pass all values as CLI arguments or use absolute paths directly. Store the workflow root path in your own state (a local variable in your reasoning), not as a shell variable in the command string.

**Anti-pattern: bundled Bash commands.** Do not chain multiple commands with `&&` or `;` in a single Bash call (e.g., `ig-tool workflow step create ... && cp ... && ig-tool context ...`). Each command should be a separate Bash tool call. Rationale: (1) a bundled command is a unique string that won't match any allow-list pattern, triggering a permission prompt; (2) if the first command fails, the error is harder to diagnose; (3) separate calls give the user clear observability of each operation.

---

## How to Run a Step
<!-- Lines 73-100 -->

**Full procedure:** See [STEP_IO_PROTOCOL.md](STEP_IO_PROTOCOL.md) — the authoritative spec for step mechanics (folder creation, prompt handling, agent invocation, output collection).

**Summary:**

1. **Look up the dispatch table** for your workflow type (see `dispatch_{type}.md`). It tells you: which agent to invoke, what context to assemble, what output to expect.

2. **Execute the step I/O procedure** per [STEP_IO_PROTOCOL.md §Orchestrator Procedure](STEP_IO_PROTOCOL.md#orchestrator-procedure):
   - Create step folder with `ig-tool workflow step create --copy` (never Read/Write files)
   - Assemble lens context with `ig-tool lens build` (output goes to step folder)
   - **Copy canonical prompt template** with Bash `cp` from `agent_invocation_prompt_templates/` (do NOT manually compose)
   - Generate simplified invocation prompt (pointer + parameters only)
   - Invoke agent with **simplified prompt** (NOT full template)
   - If re-entering `*.REFINE` for the same target, use `Task(resume=refine_agent_id)` instead of a fresh invocation — see [STEP_IO_PROTOCOL.md §6a](STEP_IO_PROTOCOL.md#6a-resume-agent-when-re-entering-a-step-for-the-same-target)
   - Collect output via agent task result `summary`/`metrics` (do NOT read output files)
   - Pass `--role orchestrator` and `-m "<reason>"` on mutating `ig-tool` commands for provenance

3. **Record the trace entry**:

   ```bash
   ig-tool workflow trace record trace.jsonl --step "{UID}" --target "{target}" \
     --actor "{agent}" --action "{what happened}" --result "{outcome}"
   ```

4. **Apply the transition rule** for this step (see dispatch table) to determine the next step.

---

## Transition Logic (shared across workflows)
<!-- Lines 103-124 -->

These transitions are common to all three workflows:

| Condition | Action |
| --- | --- |
| **Critic finds issues** | Create `*.REFINE` step folder. If `refine_agent_id` exists and `refine_agent_target` matches, **resume** the Elicitor via `Task(resume=refine_agent_id)`. Otherwise create a fresh Elicitor and store the returned `agent_id`. Do NOT present issues to the human yourself — the Elicitor mediates. See [STEP_IO_PROTOCOL.md §6a](STEP_IO_PROTOCOL.md#6a-resume-agent-when-re-entering-a-step-for-the-same-target). |
| **Elicitor yields for human input** | The agent has created dialogue files in `{step_folder}/human_dialogue/`. Print the folder path to the human. Do NOT read or interpret the files — you are a relay. Wait for confirmation, then resume the Elicitor with a pointer to the updated files. See [STEP_IO_PROTOCOL.md §6b](STEP_IO_PROTOCOL.md#6b-handle-yield_for_input-with-file-based-dialogue). |
| **Critic is clean** (after `*.RECHECK`) | Advance to `*.PICK` (next target) or terminate if queue empty |
| **`*.PICK` reached (bootstrap: graph empty)** | **Shortcut — no agent invocation.** If the graph has zero nodes (first run), the target is deterministically ROOT. Set `current_target = ROOT` in workflow state, record in trace with `actor: "system"`, skip directly to `*.SCOPE`. No human confirmation needed — there is no alternative. |
| **`*.PICK` reached (graph non-empty)** | Invoke the **Steward agent** in Mode 3 (target recommendation). Present the Steward's recommendation + rationale to the human. Human confirms or overrides. Record the confirmed target in the trace. |
| **Dialogue converges** | Advance to `*.COMMIT` |
| **`*.COMMIT` reached** | Invoke the **Steward agent** in Mode 1 (apply & audit). The Steward applies edits, audits invariants, propagates constraints, reorders the queue, and persists the graph. After Steward completes, run `ig-tool obsidian export` for both graphs (see [Obsidian Visualization](#obsidian-visualization-orchestrator-responsibility)). |
| **Scope exceeded** | Enter `*.ESCAPE` (unstructured resolution) |
| **Human override** | Log override in trace with `actor: "human"`, jump to requested step/target |
| **All targets processed** | Workflow complete — report summary |

Workflow-specific transitions are documented in each dispatch table.

**Anti-pattern: orchestrator-as-elicitor.** When the Critic returns issues, it is tempting to show them directly to the human and ask "what do you think?" This bypasses the Elicitor, which is designed to present issues one at a time, propose edits, and manage convergence. Always invoke the Elicitor agent for `*.REFINE` — it is the dialogue specialist.

---

## Hard Tools (ig-tool CLI)
<!-- Lines 127-160 -->

Agents and the orchestrator invoke programmatic operations via the `ig-tool` CLI. Tool guide (WHY/when): `agents/PRIMER_TOOLS.md`; exact syntax: `.claude/skills/ig-tool-*/SKILL.md`.

```bash
ig-tool <command> [args]
```

Installed system-wide via `uv tool install -e .` from the repo root. Works from any directory.

**Output contract:** Full results → file (`-o`). Stdout → compact YAML summary only (≤5 lines). Agents read the file only if they need the detail.

**Key commands for the orchestrator:**

| Task | Command |
| --- | --- |
| Create step folder + copy files | `ig-tool workflow step create --dir steps/ --step UID --target T --prev steps/NNN_... --copy src:dst` |
| Build lens context | `ig-tool lens build -g graph.json -t UID -b 30 -o {step}/lens.yaml` |
| Summarize agent output for routing | `ig-tool workflow step summary {step}/output_issues.yaml` |
| Validate graph after COMMIT | `ig-tool validate -g graph.json -o report.yaml` |
| Apply agent edits (auto-detects §2/§5 format) | `ig-tool apply -g graph.json -i edits.yaml -o updated.json --role orchestrator -m "reason"` |
| Record trace entry | `ig-tool workflow trace record trace.jsonl --step S --target T --actor A --action "..." --result "..."` |

**Key commands referenced in agent prompts:**

| Task | Command | For whom |
| --- | --- | --- |
| Inspect a node beyond the lens | `ig-tool query -g graph.json --node UID -o node.yaml` | Critic, Steward |
| Get tree overview | `ig-tool query -g graph.json --overview -o overview.yaml` | Orchestrator (at `*.SCOPE`), any agent needing topology |
| Get graph skeleton | `ig-tool query -g graph.json --structure -o structure.yaml` | Any agent needing topology |
| Check IV-context neighbors | `ig-tool query -g graph.json --neighbors UID -o nbrs.yaml` | Orchestrator (at `*.SCOPE`), any agent needing adjacency |
| Validate proposed edits (dry-run, auto-detects §2/§5) | `ig-tool parse -g graph.json -i edits.yaml -o parsed.yaml` | Elicitor, Steward |

---

## Format References (do not duplicate — point here)
<!-- Lines 163-182 -->

**For orchestrators:** You do not read format specifications directly. You invoke `ig-tool` commands which implement the formats, and you assemble references for agents. The table below is what you provide to agents via the Reference Map (§Sub-Agent Default Preamble).

| What | Where | Summary |
| --- | --- | --- |
| **CLI guide (WHY/when)** | `agents/PRIMER_TOOLS.md` | Decision tree + per-command purpose |
| **CLI syntax (HOW/flags)** | `.claude/skills/ig-tool-*/SKILL.md` | Exact flags and examples per command group |
| Agent text format (view I/O) | `src/src/intentgraph/serial/agent_text.py` | YAML with `view:` (legacy `frontier:` accepted on read), `nodes:`, `intentlinks:` sections |
| Serialization format spec | `foundation_and_formalism/SERIALIZATION_FORMAT.md` | Persistence (§1), agent text (§2), graph overview (§3), conventions (§4), diff format (§5) |
| Graph overview (for `*.SCOPE` / topology) | `src/src/intentgraph/serial/graph_overview.py` | Compact tree + edge YAML for full-graph navigation |
| CodeMap tree format | `ai_tooling/documentation_tools/codemap/TREE_FORMAT.md` | YAML tree: containment as nesting, edges as `~`-prefixed keys |
| Target CodeMap (Designer output) | Same format as CodeMap, with `[PLANNED]` markers | Structural plan for code generation |
| ProjectionIG format (v1) | `ig-generator-agent.md` §1.2 Working material | YAML with `PIG-<TAG>.` UID prefix; PIG-ARCH.* from Designer |
| Critic issue format | `ig-critic-agent.md` §Output Format | YAML list: `type`, `node`, `severity`, `description`, `suggestion` |
| Steward COMMIT report | `ig-steward-mode-commit.md` §Output | YAML: `phase_apply`, `phase_audit`, `phase_inherit`, `phase_queue`, `phase_persist` |
| Steward PICK recommendation | `ig-steward-mode-pick.md` §Output | YAML: `recommended`, `rationale`, `queue_snapshot`, `alternatives`, `bootstrap`, `pause` |
| Trace format | Inline in JSONL — 6 fields: `ts`, `step`, `target`, `actor`, `action`, `result` |

---

## Trace Protocol
<!-- Lines 185-204 -->

Record **every step transition** in the trace file. The trace is the orchestration log — it shows how the session followed the workflow.

**When to record:**
- At the start of every step (before invoking the agent)
- On human overrides (with `actor: "human"`)
- On workflow pause/resume
- On errors (with `result` describing the failure)

**What to record:**
- `step`: the step UID
- `target`: which intentnode this step operates on
- `actor`: who performed it (the agent name, `orchestrator`, `steward`, `system`, or `human`)
- `action`: one-line summary of what happened
- `result`: one-line summary of the outcome

Use `ig-tool workflow trace record` for persistence.

---

## Context Assembly
<!-- Lines 207-223 -->

**Full spec:** See [STEP_IO_PROTOCOL.md §Orchestrator Procedure](STEP_IO_PROTOCOL.md#orchestrator-procedure) for the complete procedure.

**Summary:**

- Use `ig-tool context` to produce scoped lens YAML → step folder
- Use `ig-tool workflow step create --copy` to move outputs between steps
- Agents read the lens from `input_view.yaml`, never raw `graph.json`
- Full graph stays in workflow root for `ig-tool query` calls by agents

**Context modes:**

- **Filesystem-based (default):** Step folder with file references. See [STEP_IO_PROTOCOL.md](STEP_IO_PROTOCOL.md).
- **Inline (legacy):** All context inlined in prompt. Use only for quick ad-hoc invocations or debugging single agents in isolation.

---

## Context Protection
<!-- Lines 226-228 -->

Your context window is a finite resource that must last the entire workflow — potentially dozens of steps across multiple targets. Every unnecessary read erodes your ability to orchestrate later steps. Protect it aggressively.

### Rules
<!-- Lines 231-241 -->

| # | Rule | Rationale |
|---|------|-----------|
| C1 | **NEVER read `graph.json` or `projection_ig.yaml`** | Use `ig-tool lens build` to produce scoped lens context. Use `ig-tool query` if you need a specific node. You never analyze intent or projection content. |
| C2 | **NEVER read agent guide files** (`.claude/agents/ig-*-agent.md`) | The subagent reads its own guide. You only need the filename (from the dispatch table) to put in the prompt. |
| C3 | **NEVER read step output files** (`output_issues.yaml`, `output_view.yaml`, `output_edits.yaml`, etc.) | Use the agent's task result `summary`/`metrics` for routing decisions. If you need a metric the summary doesn't cover, use `ig-tool workflow step summary`. |
| C4 | **NEVER read source code, documentation, or codebase files** | You have no knowledge of the codebase being distilled. Agents (Docreader, Extractor) handle that. |
| C5 | **Use `ig-tool workflow step create` for all step folder setup** | Creates the folder, copies files from previous step, writes manifest — all without touching your context window. |
| C6 | **Use `ig-tool lens build` to produce lens input** | Run before each agent invocation. The result is the scoped lens YAML the agent reads. The full graph stays on disk for `ig-tool query` calls by agents, but nobody reads it directly. |
| C7 | **NEVER read `human_dialogue/` files** | The Elicitor writes them, the human edits them, the Elicitor reads them on resumption. The orchestrator is a relay — it passes the folder path, nothing more. |

### What you MAY read
<!-- Lines 244-250 -->

- `workflow_state.json` — small (~1K), contains routing state (current step, target queue, current target)
- `trace.jsonl` — read the tail for recent entries when resuming or checking progress
- Your own protocol docs — on the first turn of a session (amortized across all subsequent steps)
- `_manifest.yaml` files — small (~500 chars), step metadata for orientation
- Agent task result summaries — returned inline by the Task tool, no file read needed

### How to route without reading outputs
<!-- Lines 253-269 -->

The agent's task result provides everything you need for transition logic:

```text
# Agent returns this in the task result (inline, no file read):
output_file: "output_issues.yaml"
summary: "Found 17 issues: 0 major, 8 moderate, 9 minor."
metrics: {issues: 17, major: 0, moderate: 8, minor: 9}
status: "complete"
```

- **Critic found issues?** → `metrics.issues > 0` → go to `*.REFINE`
- **Critic is clean?** → `metrics.issues == 0` → go to `*.PICK`
- **Steward committed?** → `status == "complete"` → go to `*.RECHECK`

You never need to read the full issue list, the full graph, or parse output files to make these decisions.

### How to populate step folders without reading files
<!-- Lines 272-294 -->

Use `ig-tool workflow step create` with `--copy` flags to move outputs from a previous step into the new step as inputs. Use `ig-tool lens build` to produce the scoped lens.

```bash
# Create step folder, copy previous outputs as inputs — no Read needed
ig-tool workflow step create --dir steps/ --step DISTILL.REFINE --target D \
  --prev steps/017_DISTILL.CHALLENGE \
  --copy output_issues.yaml:input_issues.yaml \
  --copy output_projection_observations.yaml:input_projection_observations.yaml

# Build scoped lens context — orchestrator never sees the graph content
ig-tool lens build -g graph.json -t D -b 30 \
  -o steps/018_DISTILL.REFINE/input_lens.yaml
```

The manifest and prompt template tell the agent which files to read. You provide the paths — you don't need to see the content.

**Anti-pattern: orchestrator-as-reader.** It is tempting to Read a step output "just to understand what happened" before deciding the next step. This is how 79K chars of context was wasted in a single 3-step session. The agent summary exists precisely so you don't have to. Trust the summary; if it's insufficient, improve the agent's output protocol — do not compensate by reading raw artifacts.

**Anti-pattern: orchestrator-as-graph-reader.** It is tempting to give agents the full `graph.json` as an input file. The graph grows with every commit — 35K in session 1, 47K in session 2, unbounded. Always produce scoped lens context via `ig-tool lens build`. Agents that need to look beyond the lens use `ig-tool query` themselves.

---

## Sub-Agent Default Preamble
<!-- Lines 297-363 -->

Every Task prompt to a sub-agent must start with this preamble (filled in by the orchestrator). This is the shared contract that all agents operate under when in Step I/O mode.

```text
## Agent Instructions

Read and follow: .claude/agents/{agent-file}.md
{mode_module_line}

## Shared Context

Read first for vocabulary, invariants, agent text format, and the dual-graph model:
  agents_runtime/AGENT_PRIMER.md

## Reference Documents

You may read these files for format and tool reference. Read on demand when needed — not all upfront.

| Document | Path | When to read |
|----------|------|--------------|
{ref_doc_table_rows}

## Step Context

- **Step:** {STEP_UID}
- **Workflow:** {workflow_type}
- **Target:** {target_uid}
- **Step folder:** {absolute_path_to_step_folder}

## Input Files

Read these files from the step folder:

| File | Role | Read? |
|------|------|-------|
{file_table_rows}

All paths are relative to: {absolute_path_to_step_folder}

## Task

{task_description}

## Output

Write your output to: `{output_filename}` in the step folder.
{format_description}

## Constraints

- Read ONLY the files listed in the Input Files table and the Reference Documents table. Do not search the filesystem.
- Do not read files outside the step folder unless they are listed in Agent Instructions, Shared Context, or Reference Documents.
- If context is insufficient, report the gap in your output — do not forage.
- Write output to the step folder, not to stdout.
- Do not modify input files. Propose edits in your output.
```

The orchestrator fills in `{placeholders}` per-step using the dispatch table and the reference map below. The per-step parts that vary are: agent file, mode module, step UID, target, file table, reference doc table, task description, and output format. The constraints section is identical for every invocation.

**`{mode_module_line}` placeholder:** If the agent has a mode-specific module for this step, emit:

```text
Also read: .claude/agents/{mode-module-file}.md
```

If no mode module applies, emit an empty string. The mode module map below specifies which module to use per step.

### Reference Map
<!-- Lines 366-395 -->

The orchestrator populates `{ref_doc_table_rows}` based on the agent being invoked. Every agent gets the universal reference (Agent Primer); role-specific references are added per the table below.

**Universal (all agents):**

| Document | Path | When to read |
|----------|------|--------------|
| Agent Primer | `agents_runtime/AGENT_PRIMER.md` | Always (read first) |
| Tool Guide | `agents/PRIMER_TOOLS.md` (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` (exact syntax) | When you need to invoke a hard tool (query, validate, edit) |

The primer covers vocabulary, invariants, agent text format, edit protocol, the dual-graph model, and a quick-reference table for `ig-tool` commands. The Tool Guide has the full CLI reference with examples and output contracts. Agents that don't use hard tools can skip it.

**Role-specific additions:**

Paths for frequently referenced docs (abbreviated in table):
- **V&F:** `foundation_and_formalism/VOCABULARY_AND_FORMALISM.md`
- **SER:** `foundation_and_formalism/SERIALIZATION_FORMAT.md`

| Agent | Additional reference docs |
|-------|--------------------------|
| **Extractor** | V&F (when precise definitions needed), SER (when reading/writing lens YAML), CodeMap tree format (`ai_tooling/documentation_tools/codemap/TREE_FORMAT.md`), CodeMap bridge (`agents_runtime/src/ig_agents/codemap_bridge.py`), Edit Primer (`agents_runtime/AGENT_EDIT_PRIMER_V2.md` — when proposing children) |
| **Designer** | V&F (when precise definitions needed), SER (when reading/writing lens YAML), CodeMap tree format (`ai_tooling/documentation_tools/codemap/TREE_FORMAT.md`), CodeMap bridge (`agents_runtime/src/ig_agents/codemap_bridge.py`) |
| **Docreader** | SER (when writing lens edits), md-structure-viz README (`md_structure_viz/README.md`), Output formats (`md_structure_viz/OUTPUT_FORMATS.md`), Edit Primer (`agents_runtime/AGENT_EDIT_PRIMER_V2.md` — when proposing children) |
| **Generator** | SER (when reading lens YAML), Designer output (`ig-designer-agent.md` §3 OUTPUT CONTRACT / §3.1 Artifacts — Target CodeMap format) |
| **Steward** | V&F (always — audits invariants and operations), SER (always — applies edits in all formats), Workflow design guidelines (`agents_runtime/workflow_design_guidelines.md`), Format references table (this file §Format References) |
| **Critic** | V&F (always — reviews against invariants), SER (when lens YAML appears malformed), Designer output (`ig-designer-agent.md` §3 OUTPUT CONTRACT — for architecture review) |
| **Navigator** | _(not invoked in current workflows — `*.SCOPE` is a System/CLI step. Kept for future evolution.)_ |
| **Elicitor** | SER — **parse failure only**: read only if you encounter issues parsing or writing agent text YAML. The primer's §Agent Text Format and §Edit protocol cover normal operation. Edit Primer (`agents_runtime/AGENT_EDIT_PRIMER_V2.md` — when expanding under-decomposed nodes) |
| **Verifier** | SER (when reading lens YAML) |

### Mode Module Map
<!-- Lines 398-424 -->

Agent files are modular: a compact core (always read) + mode-specific modules (read when relevant) + examples (read on demand). The orchestrator specifies the mode module in `{mode_module_line}` based on the step being executed.

| Agent | Step Pattern | Mode Module |
|-------|-------------|-------------|
| **Steward** | `*.COMMIT` | `ig-steward-mode-commit.md` |
| **Steward** | `*.PICK` | `ig-steward-mode-pick.md` |
| **Steward** | structural review (on demand) | `ig-steward-mode-review.md` |
| **Elicitor** | `*.REFINE` (entering from Critic) | `ig-elicitor-mode-triage.md` |
| **Elicitor** | ad-hoc refinement | _(none — modes 1/2/3 are in core)_ |
| **Critic** | review with PIG observations | `ig-critic-review-pig.md` |
| **Critic** | review with Designer output | `ig-critic-review-arch.md` |
| **Critic** | product-only review | _(none — product review is in core)_ |
| **Designer** | `PROJECT.DESIGN` | _(none — single workflow in core)_ |
| **Extractor** | CodeMap provided in context | `ig-extractor-mode-codemap.md` |
| **Extractor** | without CodeMap | _(none — coarse/deep workflows are in core)_ |
| **Generator** | _(none — PIG lens in core §1.2)_ | — |
| **Docreader** | all steps | _(none — single workflow in core)_ |
| **Verifier** | all steps | _(none — forward/legacy workflows are in core)_ |
| **Navigator** | _(not invoked in current workflows — `*.SCOPE` is a System/CLI step)_ | _(n/a)_ |

**Examples files** (read on demand when present): `ig-{role}-examples.md`. Currently available for: Steward, Elicitor, Critic, Extractor, Docreader. Designer, Generator, Verifier use single core files only (no separate examples modules). Include in `{ref_doc_table_rows}` with `When to read: "On demand — for format reference or calibration"` when the file exists.

**Shared protocol** (referenced by all agents): `ig-agent-common-protocol.md` — output protocol for Step I/O mode. Agents reference it from their Output Protocol section; no need to include in `{ref_doc_table_rows}`.

---

## Obsidian Visualization (orchestrator responsibility)
<!-- Lines 427-463 -->

After `*.COMMIT` completes and before advancing to `*.PICK`, the **orchestrator** exports both graphs to Obsidian vaults. The Steward does **not** handle Obsidian sync — it only persists graph JSON and workflow state.

**Standard export structure:**

All Obsidian exports go to `{workflow_root}/obsidian_export/` with two subfolders:
- `obsidian_export/product_ig/` — Product IntentGraph
- `obsidian_export/projection_ig/` — ProjectionIG

This allows the entire `obsidian_export/` folder to be opened as a single Obsidian vault containing both graphs.

**Commands** (run by orchestrator, not by any agent):

```bash
# 1. Convert ProjectionIG YAML→JSON (if needed)
python3 -c "import yaml, json; data = yaml.safe_load(open('{workflow_root}/projection_ig.yaml')); json.dump(data, open('{workflow_root}/projection_ig.json', 'w'), indent=2)"

# 2. Export product IntentGraph
ig-tool obsidian export -g {workflow_root}/graph.json \
  -o {workflow_root}/obsidian_export/product_ig/ --force

# 3. Export ProjectionIG
ig-tool obsidian export -g {workflow_root}/projection_ig.json \
  -o {workflow_root}/obsidian_export/projection_ig/ --force
```

**Output structure** (per subfolder):
- `nodes/*.md` — one markdown file per intentnode (frontmatter + navigation links)
- `edges.yaml` — all intentlinks
- `viz/*.canvas` — Obsidian Canvas files (one per node with children)

**Trace:** Record `action: "Obsidian export"`, `actor: "orchestrator"`, `result: "Product: N nodes, M canvases; PIG: P nodes, Q canvases"`.

**If export fails:** Log the error but do not block the workflow. The graph JSON is the source of truth, not the Obsidian files.

---

## Error Handling
<!-- Lines 466-476 -->

| Error | Response |
| --- | --- |
| Agent returns unparseable output | Re-invoke once with a clarification prompt. If still unparseable, log error and enter `*.ESCAPE`. |
| Agent reports intent insufficiency | Record in trace, pause workflow, report gap to human. |
| Agent reports projection gap (Project only) | Enter `PROJECT.CLARIFY`. |
| Graph invariant violation after edits | Reject edits, report violation, re-enter `*.REFINE`. |
| Human says stop | Save state, record in trace, pause workflow. |

---

## Dispatch Tables
<!-- Lines 479-484 -->

Each workflow has its own dispatch table that specifies the step sequence and per-step details:

- [dispatch_declare.md](dispatch_declare.md) — Declare workflow (7 steps)
- [dispatch_distill.md](dispatch_distill.md) — Distill workflow (10 steps)
- [dispatch_project.md](dispatch_project.md) — Project workflow (11 steps)
