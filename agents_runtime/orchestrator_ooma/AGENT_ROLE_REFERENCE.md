# OOMA Agent Role Reference

**Purpose:** When OOMA self-executes steps (PICK, SCOPE, REFINE, RECHECK, COMMIT), it acts in place of specialized agents. This document summarizes what those agents do, so OOMA understands the intent behind each procedure.

**Sources:** Standard orchestrator prompt templates, agent definition files (`.claude/agents/ig-*-agent.md`), and agent primers.

---

## Overview: What OOMA Replaces

| Step | Original Agent | Agent's Core Role | OOMA Execution |
|------|----------------|-------------------|----------------|
| **PICK** | Steward (Mode 3) | Target recommendation based on graph topology | Self-executed via [pick.md](ooma_step_procedures/pick.md) |
| **SCOPE** | System (CLI only) | Lens construction with IV_-shaped detail | Self-executed via [scope.md](ooma_step_procedures/scope.md) |
| **REFINE** | Elicitor (Mode: Triage) | Structured dialogue to resolve Critic issues | Self-executed via [refine.md](ooma_step_procedures/refine.md) |
| **RECHECK** | Critic (second pass) | Re-review after REFINE edits | Self-executed via [recheck.md](ooma_step_procedures/recheck.md) |
| **COMMIT** | Steward (Mode 1) | Apply edits, audit, persist, export | Self-executed via [commit.md](ooma_step_procedures/commit.md) |

**Agents still delegated:** READ (Docreader), EXTRACT (Extractor), CHALLENGE (Critic).

---

## Agent Roles OOMA Impersonates

### 1. Steward (PICK step — Mode 3: Target Recommendation)

**Source:** `.claude/agents/ig-steward-agent.md` + `ig-steward-mode-pick.md`

**Core capability:**
> Recommend the next target node for the workflow based on graph topology, data-flow order, and epistemic urgency.

**What Steward does:**
1. **Analyzes graph structure:**
   - Tree-level breadth (primary criterion): Complete all nodes at shallowest depth before descending
   - Data-flow order (within same level): Prefer nodes whose upstream dependencies are processed
   - Dependency density (tiebreaker): Prefer nodes with many dependents (high impact)
   - Intentlink readiness (tiebreaker): Prefer nodes whose linked neighbors have stable intent
   - Epistemic urgency (tiebreaker): Prefer `epistemic_state: "undecided"` or `"risky"`

2. **Handles bootstrap cases:**
   - Queue empty + graph empty → Recommend ROOT
   - Queue empty + graph exists → Recommend pause (all targets processed)

3. **Provides rationale:** Explain why this target makes sense (structural position, epistemic state, dependencies)

4. **Respects human override:** Present recommendation, wait for confirmation or alternative

**What OOMA must preserve:**
- **Breadth-first default** — don't dive deep before covering L1
- **Structural awareness** — use `ig-tool query --overview` and `--neighbors` to understand topology
- **Clear rationale** — human needs to understand why this target was chosen
- **Queue intelligence** — maintain target_queue in workflow_state.json

**Steward critical rules:**
- Single mutation point (other agents propose; Steward applies)
- Use `ig-tool` CLI for all graph operations (never hand-edit JSON)
- Structural judgment yes, intent creation no
- Never persist with invariant violations
- Product IG and PIG are separate files

---

### 2. Steward (COMMIT step — Mode 1: Apply & Audit)

**Source:** `.claude/agents/ig-steward-agent.md` + `ig-steward-mode-commit.md`

**Core capability:**
> Apply edits from REFINE/RECHECK, audit structural health, propagate inherited constraints, reconcile ProjectionIG, persist both graphs, update workflow state.

**What Steward does:**

**Phase 1: Review Edits**
- Verify all proposed edits are structurally valid
- Check that UIDs don't collide
- Ensure parent-child relationships are well-formed

**Phase 2: Apply Edits**

- Use `ig-tool apply` for product graph edits
- Use `ig-tool apply` for ProjectionIG edits
- Both graphs follow same format

**Phase 3: Structural Audit**
- **Fan-out:** Check if any node has too many children (>7 = smell)
- **Constraint density:** Check if constraints are well-distributed (not all on leaves)
- **Depth balance:** Check if decomposition is lopsided
- **Orphaned links:** Check for intentlinks with deleted endpoints
- **Epistemic drift:** Check if children have weaker epistemic state than parent

**Phase 4: Cross-Level Constraint Inheritance**
- Propagate ancestor constraints to descendants
- **Annotate via `design_notes`** — do NOT duplicate into `constraints` field
- Format: `"Inherited from {parent_uid}: {constraint}"`
- Only propagate if universal (e.g., "UTF-8 encoding", "thread-safe")

**Phase 5: Update Target Queue**
- Remove completed target from queue
- Add new children discovered during REFINE/RECHECK
- Reorder by priority: undecided > constrained > known
- Within same epistemic state: breadth-first (L1 before L2)

**Phase 6: Persist**
- Write `graph.json`, `projection_ig.yaml`, `workflow_state.json` to workflow root
- Validate graph invariants before persisting
- Export to Obsidian vaults (both graphs)

**What OOMA must preserve:**
- **Validation before persistence** — use `ig-tool validate` to check invariants
- **Inheritance is annotation, not duplication** — add to `design_notes`, not `constraints`
- **Audit severity is honest:** `info` = noted, `warning` = discuss, `action_required` = blocks progress
- **Queue reordering is a suggestion** — present with rationale, human confirms
- **Append to history** — add `{who: "agent:ooma", date: "...", note: "..."}` to modified nodes

**Steward critical rules (same as PICK):**
- Never persist invalid graphs
- Product IG and PIG are separate files
- Use `ig-tool` CLI exclusively

---

### 3. Elicitor (REFINE step — Mode: Triage)

**Source:** `.claude/agents/ig-elicitor-agent.md` + `ig-elicitor-mode-triage.md`

**Core capability:**
> Refine both the product IntentGraph and the ProjectionIG through structured dialogue with the human. Propose one edit at a time, explain reasoning, wait for approval.

**What Elicitor does:**

**Step 1: Triage Issues** (from Critic)
- **Auto-resolve:** Mechanical fixes without human input
  - Typos, obvious missing constraints, formatting issues
  - Batch and apply immediately
- **Escalate:** Design decisions requiring human judgment
  - Ambiguous intent, conflicting constraints, scope questions
  - Present one at a time with full context

**Step 2: Resolve Product Issues**
- Present escalated issues using **two-section turn format:**
  - **Section 1 (short):** Minimap (ASCII tree) + Critic issue + the ask (options/proposal)
  - **Section 2 (deep):** Target node in full + brim summary (siblings, parent, intentlink neighbors)
- Propose concrete edits
- Use `ig-tool node set/create`, `ig-tool link create` to apply approved edits

**Step 2a: File-Based Dialogue** (when escalation needed)
- Create `human_dialogue/` folder
- Write `round_summary.md` — cumulative context (what's resolved, what's next)
- Write `question_NNN.md` per decision point (same two-section format)
- Batch all questions for a round, then return `YIELD_FOR_INPUT`
- On resumption: regex-extract responses from `<choice>` and `<comments>` tags

**Step 2b: Expand Under-Decomposed Nodes**
- For `under_decomposition` issues: read Edit Primer
- Present proposed decomposition to human as decision (not auto-resolve)
- Show: current node, proposed children with migrated content, intentlink handling
- After approval: use `ig-tool node create` and `ig-tool link create`
- Add new child UIDs to queue

**Step 3: Resolve Projection Issues**
- For `pig_quality`, `pig_granularity`, `pig_missing`: propose PIG edits
- For `projection_leak`: rewrite product constraint (abstract) AND create PIG node (specific)

**What OOMA must preserve:**
- **One question at a time** — explain why you're asking
- **Pattern first, then individual** — detect patterns, ask for rulings, batch similar fixes
- **Auto-resolve mechanical, escalate decisions** — clear separation
- **Bundle by node** — 2+ issues on same node → present together
- **Preserve human edits** — never overwrite explicitly set content
- **Two-section format** — minimap + ask (Section 1), full node + brim (Section 2)

**Elicitor critical rules:**
- Three modes: refinement (expand down), review (challenge existing), gap detection (find missing)
- Dual-graph scope: product issues → product edits, projection issues → PIG edits
- Make graph precise enough that Generator could produce correct code
- Focus on `undecided`/`risky` areas and Critic-flagged issues

**OOMA adaptation:**
- **Inline dialogue instead of file-based** — OOMA retains context naturally, no `human_dialogue/` folder
- Present decisions inline: show context, propose options, recommend, wait for response, apply

---

### 4. Critic (RECHECK step — second pass after REFINE)

**Source:** `.claude/agents/ig-critic-agent.md` + agent primer

**Core capability:**
> Review graph quality and report issues. Read-only analysis — proposes fixes but doesn't apply them.

**What Critic does:**

**Review Types:**
1. **Product graph review:**
   - Intent clarity (WHAT/WHY, not HOW)
   - Constraint precision (testable, projection-agnostic)
   - Epistemic state accuracy (matches constraints)
   - Design notes hygiene (relevant, concise)
   - Under/over decomposition
   - Missing intentlinks

2. **ProjectionIG review** (when present):
   - Quality (clear rendering intent)
   - Granularity (module-level, not function-level)
   - Completeness (all major rendering decisions captured)
   - Alignment with product graph

3. **Cross-graph review:**
   - Projection leaks (product constraints mention Python, Redis, etc.)
   - Language-swap test (can product intent be rendered in another language?)

**Issue Types:**
- `intent_vague`, `intent_conflict`, `missing_constraint`, `projection_leak`
- `under_decomposition`, `over_decomposition`, `epistemic_mismatch`
- `pig_quality`, `pig_granularity`, `pig_missing`

**Issue Severity:**
- `major` — blocks progress, must fix
- `moderate` — should fix before COMMIT
- `minor` — cosmetic, defer if needed

**What OOMA must preserve in RECHECK:**
- **Triage logic** — same as Elicitor: auto-resolve mechanical, escalate substantive
- **Issue-by-issue resolution** — don't batch-apply without understanding
- **Critic found issues → must address** — either fix or explicitly defer with human approval
- **Loop to REFINE if changes made** — Critic re-reviews to verify fixes

**Critic critical rules:**
- Read-only — no edits, only analysis
- Semantic quality (Critic) vs. structural quality (Steward) — complementary
- Report issues with severity and suggestion

**OOMA adaptation:**
- OOMA doesn't re-invoke Critic at RECHECK
- Instead: OOMA reads Critic's issue list, applies same triage logic, presents substantive issues to human

---

## Common Themes Across All Roles

### 1. Epistemic Discipline

**From Agent Primer (P3 — Incompleteness is first-class):**
- Never invent missing intent
- If information is missing, record it explicitly as unknown
- Prefer marking uncertainty over guessing

**Epistemic state vocabulary:**
- `known` — well-understood and stable
- `constrained` — some boundaries set, full picture not resolved
- `undecided` — multiple viable options, no decision yet
- `risky` — decision made but carries identified risks
- `deferred` — deliberately postponed
- `speculative` — best guess, low confidence
- `inherited` — assumed from parent/context, not independently validated

### 2. Use `ig-tool` CLI for All Mutations

**From Steward rules:**
- Never hand-edit JSON
- Use CLI commands: `ig-tool node set/create/remove`, `ig-tool link create/set/remove`
- Use `ig-tool apply --batch` for multi-edit operations
- Use `--dry-run` for validation

**Key commands:**
```bash
# Query
ig-tool query -g graph.json --node UID -o node.yaml
ig-tool query -g graph.json --overview -o overview.yaml
ig-tool query -g graph.json --neighbors UID -o nbrs.yaml

# Edit
ig-tool node set -g graph.json --uid UID --intent "..." --epistemic-state known -o graph.json
ig-tool node create -g graph.json --uid UID --name "..." --intent "..." -o graph.json
ig-tool link create -g graph.json --src SRC --dst DST --intent "..." -o graph.json
ig-tool apply -g graph.json --batch edits.yaml -o updated.json

# Validate
ig-tool validate -g graph.json -o report.yaml
ig-tool parse -g graph.json -i edits.yaml -o parsed.yaml

# Lens
ig-tool lens build -g graph.json -t UID -b 30 -o lens.yaml
ig-tool lens show -l lens.yaml -o input_lens.yaml
```

### 3. Structural Judgment vs. Intent Creation

**From Steward rules:**
- OOMA can propose restructuring (merge, split, reparent)
- OOMA **cannot** write new intent, add constraints, or change epistemic states arbitrarily
- Intent/constraints/epistemic_state come from:
  - Agents (Docreader, Extractor)
  - Human (via dialogue)
  - Inference from code/docs (Extractor)

**When OOMA creates nodes:**
- During REFINE: only if fixing `under_decomposition` with human approval
- During COMMIT: never (edits come from REFINE/RECHECK)

### 4. Dual-Graph Model (P4)

**From Agent Primer:**
- Product IntentGraph = WHAT/WHY (projection-agnostic)
- ProjectionIG = HOW (rendering-specific, e.g., Python, Django, Postgres)
- Independent concerns — edit both, keep separate

**Projection leak:**
- Product constraint mentions "Redis" or "Django" → leak
- Fix: abstract product constraint + create PIG node with specific choice

**ProjectionIG UIDs:**
- Prefix: `PIG-<TAG>.` (e.g., `PIG-CACHE.IMPL`)
- Should align with product UID (PIG-CACHE.IMPL ↔ ROOT.CACHE)

### 5. History and Provenance

**From Steward rules:**
- Append to `history` field on every modified node
- Format: `{who: "agent:ooma", date: "2026-02-20", note: "Fixed projection leak in constraint"}`
- Conventions: `agent:steward`, `agent:elicitor`, `agent:critic`, `agent:ooma`
- Humans use plain names

### 6. Constraint Inheritance

**From Steward COMMIT mode:**
- Propagate ancestor constraints to descendants
- **Annotate via `design_notes`** — do NOT copy into `constraints`
- Format: `"Inherited from {parent_uid}: {constraint}"`
- Only propagate if universal (not node-specific)

---

## Key Primers OOMA Should Internalize

### Agent Primer Core Concepts

**P1 — Intent is the source of truth:**
- Code/docs/tests are projections, not sources
- Graph drives artifacts, not the other way

**P2 — Zooming adds information, never changes meaning:**
- Refining a node into children increases precision
- Children cover parent's intent; no child contradicts or extends beyond parent's scope

**P3 — Incompleteness is first-class:**
- Unknown is modeled, not hidden
- `epistemic_state` captures confidence level

**P4 — Projection is orthogonal:**
- Product intent (WHAT/WHY) separate from rendering intent (HOW)
- Each gets its own IntentGraph

**Invariants OOMA Must Respect:**
- **T1 — Tree well-formedness:** One parent per node, no cycles
- **T2 — Frontier validity:** No ancestor/descendant pairs in frontier
- **T3 — Intentlink endpoints exist:** Both src and dst must exist
- **T4 — Refinement coherence:** Children preserve parent's meaning
- **T5 — Frontier closure:** expand()/collapse() yield valid frontiers

### IV-Shaped Context

**From Agent Primer:**
- **Full IV-context:** All frontier nodes at full detail
- **Lean IV-context:** Target + direct neighbors full, others lean (uid, name, intent, epistemic_state)

**OOMA uses Lens for IV_-shaped detail:**
- `skeleton` LOD: uid + name
- `lean` LOD: uid + name + intent + epistemic_state
- `full` LOD: all fields

---

## OOMA-Specific Adaptations

### 1. No File-Based Dialogue

**Elicitor uses:** `human_dialogue/` folder with `question_NNN.md` files

**OOMA uses:** Inline dialogue
- Present context (node, issue, brim)
- Propose options (A, B, custom)
- Recommend with reasoning
- Wait for response
- Apply immediately

**Rationale:** OOMA retains context naturally (same session), no need for file-based handoff

### 2. No Session Resumption

**Standard orchestrator tracks:**
- `refine_agent_id` — Elicitor agent ID
- `refine_agent_target` — target UID when agent was created
- `refine_dialogue_round` — counter for dialogue rounds

**OOMA doesn't need this:**
- OOMA executes REFINE/RECHECK itself
- Context is preserved across steps naturally
- No separate agent to resume

### 3. Procedure-Driven Execution

**Standard orchestrator:**
- Composes 150-200 line prompts for each agent invocation
- Passes full context inline or via step folder

**OOMA:**
- Reads compact procedures (~50-150 lines)
- Executes step-by-step using `ig-tool` commands
- Writes outputs to step folder

**Benefit:** Lower context window pressure, clearer execution trace

---

## Quick Reference: Role-to-Procedure Mapping

| OOMA Role | When | Procedure File | Key Actions |
|-----------|------|----------------|-------------|
| **Steward (PICK)** | Select next target | [pick.md](ooma_step_procedures/pick.md) | Query graph topology, recommend target, present to human |
| **System (SCOPE)** | Build Lens | [scope.md](ooma_step_procedures/scope.md) | `ig-tool lens build`, set IV_ LOD, verify budget |
| **Elicitor (REFINE)** | Initial refinement | [refine.md](ooma_step_procedures/refine.md) | Review agent outputs, fix quality issues, handle projection leaks, escalate design decisions |
| **Critic (RECHECK)** | Address issues | [recheck.md](ooma_step_procedures/recheck.md) | Triage Critic's issue list, auto-resolve mechanical, escalate substantive, loop to REFINE if needed |
| **Steward (COMMIT)** | Validate & persist | [commit.md](ooma_step_procedures/commit.md) | Validate invariants, audit structure, inherit constraints, update queue, persist graphs, export Obsidian |

---

## Summary

When OOMA executes self-owned steps, it combines the concerns of multiple specialized agents:

- **Steward's structural awareness** (topology, queue management, validation)
- **Elicitor's dialogue discipline** (triage, escalate, one-at-a-time)
- **Critic's quality lens** (what to check, what constitutes an issue)

**Key success criteria:**
1. **Follow procedures exactly** — they encode agent expertise
2. **Use `ig-tool` CLI exclusively** — validation, atomicity, observability
3. **Respect epistemic discipline** — never invent intent, mark unknowns explicitly
4. **Triage correctly** — auto-resolve mechanical, escalate substantive
5. **Validate before persisting** — invariants are hard constraints
6. **Preserve dual-graph separation** — product vs. projection orthogonal

**When in doubt:** Escalate to human. OOMA's strength is coordination and mechanical fixes, not intent invention.
