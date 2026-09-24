# OOMA Orchestrator (One Man Army)

**Status:** Experimental — testing hypothesis that orchestrator can do refinement work directly instead of delegating to subagents for complex steps.

## Motivation

The standard orchestrator delegates every step to typed agents. This works well for specialized steps (READ → Docreader, EXTRACT → Extractor), but struggles with complex coordination steps like REFINE:

- **REFINE agent** receives ~200-line prompts, triages issues, manages dialogue with humans, edits both product IG and ProjectionIG
- When subagents get complex prompts, they sometimes struggle with:
  - Understanding multi-phase procedures
  - Balancing multiple constraints (epistemic discipline, edit atomicity, human escalation protocol)
  - Retaining context across dialogue rounds

**OOMA hypothesis:** For steps that require coordination across multiple concerns, the orchestrator can do the work itself using the same `ig-tool` CLI primitives that agents use.

## Architecture

OOMA is a **hybrid orchestrator**:
- **Agent-invoked steps** (READ, EXTRACT, CHALLENGE) — delegates to typed agents like the standard orchestrator
- **Self-executed steps** (PICK, SCOPE, REFINE, RECHECK, COMMIT) — OOMA does the work itself using `ig-tool` commands

### New Workflow Sequence

```text
DISTILL.MAP (once — builds CodeMap)
  ↓
DISTILL.PICK (OOMA) → DISTILL.SCOPE (OOMA) → DISTILL.READ (agent) → DISTILL.EXTRACT (agent)
                                                                              ↓
                                                            DISTILL.REFINE (OOMA)
                                                                              ↓
                                                         DISTILL.CHALLENGE (agent)
                                                                              ↓
                                            If issues → DISTILL.RECHECK (OOMA) → back to REFINE
                                            If clean → DISTILL.COMMIT (OOMA) → next target
```

**Key change from standard workflow:** No CHALLENGE → REFINE → COMMIT → RECHECK loop. Instead:
1. READ → EXTRACT → REFINE (OOMA does initial refinement of agent outputs)
2. CHALLENGE (agent reviews)
3. If issues: RECHECK (OOMA addresses them) → back to REFINE
4. If clean: COMMIT → next target

## File Structure

```text
orchestrator_ooma/
├── README.md                           # This file
├── orchestrator_ooma_protocol.md       # OOMA-specific orchestration rules
├── dispatch_distill_ooma.md            # Step sequence + per-step dispatch (OOMA variant)
├── ooma_step_procedures/               # Procedures for OOMA-owned steps
│   ├── pick.md                         # How OOMA does PICK (target selection)
│   ├── scope.md                        # How OOMA does SCOPE (lens construction)
│   ├── refine.md                       # How OOMA does REFINE (resolve issues, apply edits)
│   ├── recheck.md                      # How OOMA does RECHECK (address Critic findings)
│   └── commit.md                       # How OOMA does COMMIT (apply, audit, persist)
└── agent_invocation_prompt_templates/  # For agent-invoked steps (READ, EXTRACT, CHALLENGE)
    └── workflow_distill/
        ├── read.md                     # Same as standard orchestrator
        ├── extract.md                  # Same as standard orchestrator
        └── challenge.md                # Same as standard orchestrator
```

## Shared vs. OOMA-Specific Files

### Shared (read by OOMA, same as standard orchestrator)
- [STEP_IO_PROTOCOL.md](../orchestrator/STEP_IO_PROTOCOL.md) — step folder structure, prompt structure, agent contract
- [../../agents/PRIMER_TOOLS.md](../../agents/PRIMER_TOOLS.md) — `ig-tool` command guide
- [AGENT_PRIMER.md](../AGENT_PRIMER.md) — vocabulary, invariants, agent text format

### OOMA-Specific
- `orchestrator_ooma_protocol.md` — OOMA orchestration rules (when to delegate, when to self-execute)
- `dispatch_distill_ooma.md` — step sequence with OOMA-owned steps marked
- `ooma_step_procedures/` — how OOMA executes each self-owned step

## Key Design Decisions

1. **Use `ig-tool` CLI for all mutations** — OOMA doesn't manipulate graph structures in-memory. It uses the same CLI primitives that agents use. This ensures:
   - Validation and atomicity (ig-tool enforces invariants)
   - Observability (every edit is a CLI invocation)
   - Consistency (OOMA and agents use the same edit protocol)

2. **Step folders for self-executed steps** — Even when OOMA does the work itself, it creates step folders with `_manifest.yaml`, `_procedure.md`, `input_*.yaml`, and `output_*.yaml`. This preserves observability and makes debugging easier.

3. **Agent invocations unchanged** — READ, EXTRACT, CHALLENGE use the standard agent invocation flow (copy template → simplify → invoke typed agent → collect output).

4. **Shared protocol files** — OOMA reads the same `STEP_IO_PROTOCOL.md` that the standard orchestrator uses. It just has different dispatch logic.

## Migration Path

This is experimental. If OOMA proves effective:
- Move `orchestrator_ooma/` → `orchestrator/` (replace standard orchestrator)
- Deprecate `ig-elicitor-agent` for DISTILL workflow
- Keep Elicitor for ad-hoc refinement tasks (not part of orchestrated workflow)

If OOMA proves ineffective:
- Keep standard orchestrator as primary
- Treat OOMA as a failed experiment
- Consider alternative approaches (better agent prompts, smaller agent scopes, more rigid procedures)

## Next Steps

1. Create `orchestrator_ooma_protocol.md` — orchestration rules
2. Create `dispatch_distill_ooma.md` — step sequence + dispatch
3. Create `ooma_step_procedures/*.md` — procedures for each OOMA-owned step
4. Test on a real DISTILL workflow run
5. Compare outcomes (quality, speed, debuggability) vs. standard orchestrator
