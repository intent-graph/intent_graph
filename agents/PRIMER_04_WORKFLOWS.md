# PRIMER_04_WORKFLOWS

Purpose: Understanding workflows and their building blocks. Implementation-agnostic (applies whether you're doing one step, orchestrating multiple agents, or running full workflow in one session).

Audience: All agents working within workflows.

---

## Operation Classes

All operations fall into two classes by knowledge delta:

### Class 1: Structure-Preserving (Low Knowledge Delta)

Form changes, content doesn't. You reorganize existing knowledge.

Examples:
- Refactor: merge overlapping siblings, consolidate duplicate constraints
- Rephrase: intent says HOW → rewrite as WHY
- Normalize: duplication across peers → consolidate (P5)
- Separate: projection leak in Product IG → route to ProjectionIG (P4)

Epistemic delta: Minimal. `observed` stays `observed`, `known` stays `known`.

Human involvement: Low (mechanical) to moderate (phrasing choices).

When to use: Fix violations, enforce invariants, improve clarity without adding information.

### Class 2: Knowledge-Expanding (High Knowledge Delta)

Content changes. You add information not previously in graph.

Examples:
- Expand: atomic node → children (implicit knowledge becomes explicit)
- Decide: `undecided` → `known` with human choice
- Fill gaps: missing constraints/intentlinks → create them
- Validate: `inherited`/`speculative` → `known` with evidence
- Surface intent: vague → specific via human dialogue

Epistemic delta: Significant. New nodes, constraints, epistemic_state upgrades.

Human involvement: High (source of new knowledge).

When to use: Resolve uncertainty, add missing information, make design decisions.

---

## Fundamental Activities

Building blocks that workflows compose. Each activity has a purpose, typical operation class, and human involvement level.

### Ingest

Bring external information into graph.

Sources: Documentation, code, human dialogue.

What it does: Create nodes/links from observations. Mark epistemic_state based on source (`observed` from code, `known` from validated human input).

Operation class: Primarily Class 2 (new knowledge entering graph).

Human involvement: High if source is human, low if source is docs/code.

Typical agents: Docreader (docs), Extractor (code), Elicitor (human dialogue).

### Critique

Find problems in specific area of graph.

Input: Target node/subgraph + context (what changed recently, hints about what to check).

Output: Issues (vagueness, violations, gaps, conflicts) focused on target area.

What it does: Scan target + neighbors for: vague intent, missing constraints, P1-P5 violations, epistemic_state needing resolution. Uses recent change context to focus (e.g., "just expanded DISCOVER → check children overlap, parent self-sufficiency").

Grounding check (for `observed:` nodes): a Distilled graph can drift from — or fabricate against — the code it was extracted from. When critiquing `observed:` content, treat every cited file path, symbol, line number, and count as a falsifiable claim and re-verify it against the *current* ground truth (the code/docs), not memory or plausibility. A claim whose cited artifact no longer exists is `hallucinated`; one whose artifact moved/renamed/changed is `drifted`. Default to refuted: if you cannot confirm a claim against a real artifact, treat it as failing, never as "probably fine." This generalizes well as a fan-out — claims are independent and read-only, so cheap parallel verifiers (one per node/subtree) can re-ground a whole graph, each returning a verdict + the evidence path it actually opened. Fixes then follow the standard path: lowest node that fully owns the fact, then propagate up (PRIMER_03A; Validate / Propagation After Commit below).

Operation class: Neither (read-only analysis).

Human involvement: None (mechanical analysis).

Typical agents: Critic (single-target), fan-out verifiers (whole-graph grounding audit).

### Refine

Fix identified issues.

Methods: Edits (via CLI), dialogue (for Class 2), refactoring (for Class 1).

What it does: Resolve issues from Critique. Mix of mechanical fixes (Class 1) and human-decision fixes (Class 2).

Operation class: Mixed.

Human involvement: Varies (low for Class 1, high for Class 2).

Typical agents: Elicitor (dialogue-based), Steward (structural fixes), any agent resolving issues.

### Design

Architecture from intent.

Input: Product IntentGraph + ProjectionIG.

Output: Target architecture (how code should be structured to satisfy intent).

What it does: Translate intent into code structure decisions. Choose paradigm, module boundaries, data flow.

Operation class: Class 2 (architectural decisions).

Human involvement: High (if intent insufficient or trade-offs exist).

Typical agents: Designer.

### Generate

Code synthesis from intent + architecture.

Input: Intent + ProjectionIG + target architecture.

Output: Code satisfying intent.

What it does: Mechanical generation following architecture and ProjectionIG constraints.

Operation class: Class 1 (generation from specification).

Human involvement: Low (unless generation blocked by vague intent).

Typical agents: Generator.

### Verify

Test code against intent.

Input: Generated code + intent.

Method: Tests derived from intent (not from code structure).

What it does: Validate code faithfulness to intent via behavioral tests.

Operation class: Class 2 if designing tests, Class 1 if running existing tests.

Human involvement: Moderate (test design decisions).

Typical agents: Verifier.

### Validate

Check post-edit consistency.

Methods: Propagation checks, re-critique.

What it does: Verify edits didn't break invariants (T1-T4, P1-P5). Check neighbors, run propagation.

Operation class: Class 1 (mechanical verification).

Human involvement: None.

Typical agents: Critic (re-review), Steward (propagation checks), any agent doing post-edit verification.

### Commit

Persist changes, enforce propagation.

What it does: Apply edits atomically, propagate constraints/epistemic state to neighbors, update work queue.

Operation class: Class 1 (structural enforcement).

Human involvement: None.

Typical agents: Steward.

---

## Workflows

Workflows compose activities. Purpose, typical sequence, and convergence criteria.

### 1. Improve

Purpose: Make IntentGraph better, regardless of starting state.

What you have: IntentGraph (any quality level), optional code/docs.

Activities: Critique → Refine → Validate → Commit (loop until converged).

Operation mix: Both classes. Class 1 for mechanical fixes, Class 2 for resolving uncertainty/expanding.

Convergence: Quality criteria met (no critical issues, epistemic states resolved or explicitly `deferred`, invariants hold).

When to use: Graph exists but needs improvement (fix violations, resolve `undecided`, expand coarse nodes, refactor structure).

### 2. Distill

Purpose: Extract intent from existing artifacts, then improve.

What you have: Code, docs (existing system).

Phase 1 — Extraction:
Activities: Ingest (docs) → Ingest (code) → Critique → Refine

Operation mix: Heavy Class 2 (extracting knowledge from code/docs into graph).

Phase 2 — Improvement:
Activities: Critique → Refine → Validate → Commit

Operation mix: Both classes (validate extracted intent with human, refactor structure).

Dual output: Product IntentGraph + ProjectionIG (observed rendering patterns).

Convergence: Extracted intent validated, docs ≠ code conflicts resolved, graph quality criteria met.

When to use: Existing codebase needs IntentGraph.

Re-grounding: `observed:` content is a snapshot of the code at extraction time and decays as the code evolves. Periodically re-run the Critique grounding check (above) against the current code — especially before trusting a Distilled graph for a Project pass — to catch claims that have drifted or were fabricated.

### 3. Project

Purpose: Materialize intent as code.

What you have: Refined IntentGraph + ProjectionIG.

Activities: Design → Generate → Verify → Validate → Commit.

Operation mix:
- Design: Class 2 (architectural decisions)
- Generate: Class 1 (mechanical synthesis)
- Verify: Class 2 (test design)

Convergence: Code satisfies intent (tests pass), code follows ProjectionIG conventions.

When to use: Intent is refined, ready to project to code.

Escape: If intent insufficient during Design/Generate → pause, run Improve on IntentGraph.

---

## Execution Context

When you are invoked (by an orchestrator or a human), your task payload includes **execution context**: environment flags and hints that control how you run, not what you do.

**Environment flags:**
- **dry_run** — If true, propose changes but do not write. Output edits to the designated file; do not call `ig-tool` mutating commands.
- **verbosity** — `quiet` / `normal` / `verbose`. Controls how much you write to disk (summaries vs full reasoning).

**Effort hint** — Free-form natural language guidance on how much time, thoroughness, and token budget to spend. The orchestrator (or human) sets this to balance depth vs speed. Examples:
- *"Quick pass — flag obvious issues only, skip optional reads"*
- *"Thorough — this is a retry after PARTIAL, cross-check everything"*
- *"Sketch depth; we're exploring scope"*

There is no fixed enum. You are expected to interpret the hint and adjust: read fewer optional inputs and stay shallow when the hint asks for speed; read more and propagate further when it asks for thoroughness. Respecting the effort hint keeps workflow cost predictable and lets the orchestrator tune per step.

**Where it's defined:** The full structure of the agent task payload (INPUT, INSTRUCTIONS, OUTPUT CONTRACT, including execution context) is specified in [ai_tooling/howto/programming_subagents.md](../../ai_tooling/howto/programming_subagents.md). Serialization of graph and Lens data is in [SERIALIZATION_FORMAT.md](../foundation_and_formalism/SERIALIZATION_FORMAT.md).

---

## Universal Patterns

Patterns that apply across all workflows and activities.

### Target-Based Iteration

Work on one node (or small subgraph) at a time. Complete before moving to next.

Queue determines order:
- Data-flow priority (upstream before downstream)
- Epistemic urgency (`undecided` with issues before `known`)
- Breadth-first (siblings before depth)

### Critique Loop

Pattern: Identify issues → Resolve → Verify resolution.

Applies to all workflows. Never skip verification (validate after refine, verify after generate).

### Bounded Context

Lens limits working memory to target + neighbors. No agent holds full graph.

Use query for spot checks outside Lens. Adjust viewport (promote/expand) when target area shifts.

### Propagation After Commit

Every commit triggers neighbor checks:
- Constraint propagation (up, down, horizontal)
- Epistemic propagation (risk/uncertainty flows)
- Normalization enforcement (P5)

Quiescence typically Wave 1-2. Beyond Wave 3 signals deeper issues.

### Human Dialogue

Trigger: Genuine uncertainty (Class 2 operations needing decisions).

Pattern: Batch questions with shared context (PRIMER_DIALOGUE), extract answers efficiently.

When: `undecided` needs resolution, trade-offs exist, validation needed.

---

## Role Guidance

### If you're doing one activity

Your task prompt tells you which activity (Critique, Refine, Ingest, etc.).

Your job: Execute that activity for the current target.

Watch for:
- Class 1 vs Class 2: Mechanical or needs dialogue?
- Propagation triggers: Did your edits affect neighbors?
- Convergence: Is this target done, or does it need another pass?

### If you're running full workflow

You cycle through activities for each target until convergence.

Your job: Compose activities (Critique → Refine → Validate → Commit), manage queue, decide when to converge.

Watch for:
- Quality criteria: When is graph good enough?
- Batching: Group Class 2 operations for human efficiency
- Escapes: When to pause and ask for more context

---

## Next Steps

After reading this primer:

- For specific workflow step details: See agents_runtime/WORKFLOW_*.md (implementation-specific)
- For orchestrator mechanics: See agents_runtime/orchestrator/orchestrator_protocol.md
