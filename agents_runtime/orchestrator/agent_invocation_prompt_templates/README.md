# Agent Invocation Prompt Templates

Pre-written, version-controlled prompt templates for workflow step agent invocations.

**How to use these templates:** See [STEP_IO_PROTOCOL.md](../STEP_IO_PROTOCOL.md) for the authoritative procedure (copy template with Bash, generate simplified invocation, invoke agent).

**Prompt design philosophy:** See [ai_tooling/howto/programming_subagents.md](../../../../ai_tooling/howto/programming_subagents.md) for the canonical template rationale (agents as functions, typed I/O, output contracts).

## Structure

One subdirectory per workflow, one template per step:

```text
agent_invocation_prompt_templates/
  workflow_distill/
    pick.md
    scope.md          ← CLI execution spec (System step, not agent payload)
    read.md
    extract.md
    challenge.md
    refine.md
    commit.md
    recheck.md
```

## Two Template Types

Most templates are **agent payloads** — prompts sent to a sub-agent via the Task tool, following the 3-section layout below. Some steps are **System steps** (Actor = "System (you)") where the orchestrator runs CLI commands directly instead of invoking an agent. These use a **CLI execution spec** format (procedure + commands + error handling). Currently: `scope.md` is a CLI execution spec; all others are agent payloads.

## Canonical 3-Section Layout (Agent Payloads)

Every template follows the same three top-level sections:

```text
# AGENT TASK PAYLOAD: {{STEP_UID}}

## 1. INPUT
### 1.1 Context        — immutable orientation (step metadata + external ref docs)
### 1.2 Working Material — files the agent reads and transforms
### 1.3 Environment     — execution flags (dry_run, verbosity, effort_hint)

## 2. INSTRUCTIONS
### 2.1 Primary Objective    — one-sentence goal
### 2.2 Initialization       — agent files to read, shared context
### 2.3 Algorithm / Execution Path — step-by-step procedure
### 2.4 Constraints, Exits & Escalations

## 3. OUTPUT CONTRACT
### 3.1 Artifacts        — filenames + formats
### 3.2 Epistemology      — confidence score + unknowns
### 3.3 Control Flow & Telemetry — status enum + summary
### 3.4 Escalation Payload — only if YIELD_FOR_INPUT
```

## Template Parameters

Parameters use `{{double_braces}}` to distinguish from literal text. **The orchestrator does not read templates to discover parameters.** Parameters are declared in the dispatch table's **§Parameter Registry** (e.g., [dispatch_distill.md §Parameter Registry](../dispatch_distill.md#parameter-registry)).

Common parameters across all steps:

| Parameter | Type | Description |
|-----------|------|-------------|
| `{{step_folder}}` | path | Absolute path to step folder |
| `{{target_uid}}` | uid | Target node UID |
| `{{agent_mode_modules}}` | text | Mode-specific agent module line (from Module Routing Table) |
| `{{effort_hint}}` | effort | `"sketch"` or `"thorough"` — controls agent depth (see [dispatch_distill.md §Effort Dial Logic](../dispatch_distill.md#effort-dial-logic)) |

Step-specific parameters (e.g., `{{target_repo_path}}` for DISTILL.READ) are documented in the dispatch table.

## Module Routing

**Which mode module to pass per step:** See Module Routing Table in each dispatch file (e.g., [dispatch_distill.md §Module Routing Table](../dispatch_distill.md#module-routing-table)).

## Maintenance

When step I/O changes:

1. Update template (source of truth for instructions and output contract)
2. Update dispatch table §Parameter Registry if parameters changed
3. Test with one invocation

**Naming:** `workflow_{type}/` directories, `{step_name}.md` files (lowercase, e.g., `extract.md` for DISTILL.EXTRACT)
