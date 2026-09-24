# OOMA Orchestrator Quick Start

**OOMA = One Man Army** — a hybrid orchestrator that self-executes coordination steps and delegates specialized extraction/analysis.

---

## What is OOMA?
<!-- Lines 9-17 -->

OOMA is an experimental orchestrator for the DISTILL workflow that:
- **Self-executes** complex coordination steps (PICK, SCOPE, REFINE, RECHECK, COMMIT)
- **Delegates** specialized steps to typed agents (READ, EXTRACT, CHALLENGE)

**Hypothesis:** Orchestrator can handle multi-phase refinement logic more reliably than delegating it to a subagent with a 200-line prompt.

---

## File Structure
<!-- Lines 20-41 -->

```text
orchestrator_ooma/
├── README.md                           # Architecture overview
├── QUICKSTART.md                       # This file
├── orchestrator_ooma_protocol.md       # OOMA orchestration rules
├── dispatch_distill_ooma.md            # Step sequence + dispatch table
├── ooma_step_procedures/               # Procedures for OOMA-owned steps
│   ├── pick.md                         # Target selection
│   ├── scope.md                        # Lens construction
│   ├── refine.md                       # Initial refinement
│   ├── recheck.md                      # Address Critic issues
│   └── commit.md                       # Validate, persist, advance
└── agent_invocation_prompt_templates/  # For delegated steps
    └── workflow_distill/
        ├── read.md                     # Docreader prompt
        ├── extract.md                  # Extractor prompt
        └── challenge.md                # Critic prompt
```

---

## How to Use OOMA
<!-- Lines 44-44 -->

### 1. Start a DISTILL Workflow
<!-- Lines 47-65 -->

From the workflow root directory (e.g., `my_project/t1_distill/`):

```bash
# Ensure you're at project root (CRITICAL — see orchestrator_ooma_protocol.md §CWD Invariant)
cd <your-checkout>/intent_code   # umbrella root; intent_graph/... paths below are relative to it

# Initialize workflow state
{
  "workflow_type": "distill",
  "current_step": "DISTILL.MAP",
  "current_target": null,
  "target_queue": [],
  "graph_path": "{workflow_root}/graph.json",
  "trace_path": "{workflow_root}/trace.jsonl"
}
# Write to {workflow_root}/workflow_state.json
```

### 2. Read OOMA Protocol Files
<!-- Lines 68-73 -->

As the OOMA orchestrator, read (once per session):
1. [orchestrator_ooma_protocol.md](orchestrator_ooma_protocol.md) — your role and rules
2. [../orchestrator/STEP_IO_PROTOCOL.md](../orchestrator/STEP_IO_PROTOCOL.md) — step folder structure (for delegated steps)
3. [dispatch_distill_ooma.md](dispatch_distill_ooma.md) — step sequence and dispatch

### 3. Execute Workflow Steps
<!-- Lines 76-76 -->

#### For SELF-EXECUTED steps (PICK, SCOPE, REFINE, RECHECK, COMMIT):
<!-- Lines 79-97 -->

1. Create step folder:
   ```bash
   ig-tool workflow step create --dir {workflow_root}/steps/ --step {STEP_UID} --target {target_uid}
   ```

2. Read procedure:
   ```text
   ooma_step_procedures/{step}.md
   ```

3. Execute procedure using `ig-tool` commands

4. Record trace:
   ```bash
   ig-tool workflow trace record trace.jsonl --step {UID} --target {target} \
     --actor "ooma" --action "{what you did}" --result "{outcome}"
   ```

#### For DELEGATED steps (READ, EXTRACT, CHALLENGE):
<!-- Lines 100-112 -->

Follow standard agent invocation (see [STEP_IO_PROTOCOL.md §Orchestrator Procedure](../orchestrator/STEP_IO_PROTOCOL.md#orchestrator-procedure)):

1. Create step folder with `ig-tool workflow step create --copy`
2. Build Lens with `ig-tool lens build`
3. Copy template: `agent_invocation_prompt_templates/workflow_distill/{step}.md`
4. Generate simplified prompt (pointer + parameters)
5. Invoke typed agent: `Task(subagent_type="ig-{agent}-agent", ...)`
6. Collect output via task result
7. Record trace

---

## Workflow Sequence (OOMA DISTILL)
<!-- Lines 115-134 -->

```text
MAP (bootstrap) → PICK (OOMA) → SCOPE (OOMA) → READ (agent) → EXTRACT (agent)
                    ↑                                                   ↓
                    |                                         REFINE (OOMA)
                    |                                                   ↓
                    |                                      CHALLENGE (agent)
                    |                                                   ↓
                    |                           If issues → RECHECK (OOMA) → loop to REFINE
                    |                           If clean → COMMIT (OOMA) → loop to PICK
                    +—————————————————— queue empty ————————————————————+
```

**Key differences from standard DISTILL:**
- No CHALLENGE → REFINE → COMMIT → RECHECK loop
- Instead: REFINE → CHALLENGE → (if issues) RECHECK → REFINE → ... → COMMIT
- OOMA retains context across REFINE/RECHECK iterations (no session resumption needed)

---

## OOMA-Specific Principles
<!-- Lines 137-137 -->

### When to delegate vs. self-execute
<!-- Lines 140-148 -->

**Delegate:**
- Specialized domain tasks (reading docs, extracting code, reviewing quality)
- Agent has unique tools (md-doc-tree, CodeMap, validation rules)

**Self-execute:**
- Coordination across multiple concerns (REFINE: triage + edit + escalate)
- Procedural logic that fits `ig-tool` primitives (PICK: query + recommend)

### How to use `ig-tool` commands
<!-- Lines 151-156 -->

- **Query first, mutate second:** Understand state before changing it
- **Validate before applying:** Use `--dry-run` for safety
- **Atomic operations:** Prefer `ig-tool apply --batch` for multi-edit operations
- **Budget-aware Lens:** Use `ig-tool lens promote/demote` to adjust detail

### Human escalation (inline dialogue)
<!-- Lines 159-171 -->

OOMA uses **inline dialogue** (not file-based like Elicitor):
1. Present context (node, brim, issue)
2. Propose options (A, B, custom)
3. Recommend (with reasoning)
4. Wait for response
5. Apply approved edits
6. Continue

No `human_dialogue/` files — OOMA retains context naturally.

---

## Key `ig-tool` Commands for OOMA
<!-- Lines 174-190 -->

| Task | Command |
| ---- | ------- |
| Create step folder | `ig-tool workflow step create --dir steps/ --step UID --target T` |
| Build Lens | `ig-tool lens build -g graph.json -t UID -b 30 -o {step}/lens.yaml` |
| Show Lens as text | `ig-tool lens show -l {step}/lens.yaml -o {step}/input_lens.yaml` |
| Query node | `ig-tool query -g graph.json --node UID -o node.yaml` |
| Edit node | `ig-tool node set -g graph.json --uid UID --intent "..." -o graph.json` |
| Create node | `ig-tool node create -g graph.json --uid UID --name "..." --intent "..." -o graph.json` |
| Batch edits | `ig-tool apply -g graph.json --batch edits.yaml -o updated.json` |
| Validate graph | `ig-tool validate -g graph.json -o report.yaml` |
| Record trace | `ig-tool workflow trace record trace.jsonl --step S --target T --actor "ooma" --action "..." --result "..."` |

Reference: [../../agents/PRIMER_TOOLS.md](../../agents/PRIMER_TOOLS.md) (WHY/when); `.claude/skills/ig-tool-*/SKILL.md` (HOW/flags)

---

## Comparison: OOMA vs. Standard Orchestrator
<!-- Lines 193-207 -->

| Step | Standard | OOMA |
| ---- | -------- | ---- |
| **PICK** | Delegates to Steward (Mode 3) | Self-executes |
| **SCOPE** | System (CLI only) | Self-executes |
| **READ** | Delegates to Docreader | Delegates (same) |
| **EXTRACT** | Delegates to Extractor | Delegates (same) |
| **CHALLENGE** | Delegates to Critic | Delegates (same) |
| **REFINE** | Delegates to Elicitor (file dialogue) | Self-executes (inline dialogue) |
| **RECHECK** | Delegates to Critic (second pass) | Self-executes |
| **COMMIT** | Delegates to Steward (Mode 1) | Self-executes |
| **Loop** | CHALLENGE → REFINE → COMMIT → RECHECK | REFINE → CHALLENGE → RECHECK → REFINE → COMMIT |

---

## Testing OOMA
<!-- Lines 210-210 -->

### Minimal Test
<!-- Lines 213-222 -->

1. Create a small test workflow root (2–3 intentnodes, simple structure)
2. Initialize `graph.json`, `projection_ig.yaml`, `workflow_state.json`
3. Run OOMA through one PICK → COMMIT cycle
4. Verify:
   - Step folders created with correct structure
   - Trace entries accurate
   - Graph/PIG updated correctly
   - Obsidian export succeeds

### Full Test
<!-- Lines 225-235 -->

1. Use a real codebase (e.g., `intent_graph/src/` or `md_structure_viz/`)
2. Run OOMA DISTILL workflow from scratch (MAP → multiple PICK/COMMIT cycles)
3. Compare outcomes vs. standard orchestrator:
   - **Quality:** Are refined nodes clearer? Fewer Critic issues?
   - **Speed:** Time per target (OOMA vs. standard)
   - **Debuggability:** Are step folders easier to inspect?
   - **Context window pressure:** Does OOMA use less context?

---

## Troubleshooting
<!-- Lines 238-249 -->

| Issue | Solution |
| ----- | -------- |
| "ig-tool command not found" | Run from project root. Verify `uv tool install -e .` succeeded. |
| "Step folder not found" | Check CWD. OOMA must run from project root (§CWD Invariant). |
| "Agent prompt template missing" | Verify `agent_invocation_prompt_templates/workflow_distill/{step}.md` exists. |
| "Procedure file not found" | Verify `ooma_step_procedures/{step}.md` exists. |
| "Graph validation fails at COMMIT" | REFINE/RECHECK applied invalid edits. Check `validation_report.yaml` for details. |
| "Lens diff non-empty at COMMIT" | Bug — REFINE/RECHECK should have applied all edits. Report to developer. |

---

## Next Steps
<!-- Lines 252-260 -->

1. **Test on small example** — verify mechanics work
2. **Test on real codebase** — compare quality/speed vs. standard orchestrator
3. **Iterate on procedure files** — refine algorithms based on observed issues
4. **Document findings** — what works? What doesn't? Why?
5. **Decide migration** — replace standard orchestrator, or keep OOMA as alternative?

---

## References
<!-- Lines 263-268 -->

- [README.md](README.md) — OOMA architecture and motivation
- [orchestrator_ooma_protocol.md](orchestrator_ooma_protocol.md) — full orchestration rules
- [dispatch_distill_ooma.md](dispatch_distill_ooma.md) — step sequence and dispatch table
- [../../agents/PRIMER_TOOLS.md](../../agents/PRIMER_TOOLS.md) — `ig-tool` command guide (WHY/when)
- [../orchestrator/orchestrator_protocol.md](../orchestrator/orchestrator_protocol.md) — standard orchestrator (for comparison)
