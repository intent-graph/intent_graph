# PRIMER_04_WORKFLOWS

Understanding workflows and their building blocks. Implementation-agnostic.

---

## Operation Classes

### Class 1: Structure-Preserving (Low Knowledge Delta)
Form changes, content doesn't. Reorganize existing knowledge.
- Refactor (merge overlapping siblings), Rephrase (HOW→WHY), Normalize (P5), Separate (P4 leaks)
- Epistemic delta: minimal. Human involvement: low-moderate.

### Class 2: Knowledge-Expanding (High Knowledge Delta)
Content changes. Add information not in graph.
- Expand (implicit→explicit), Decide (undecided→known), Fill gaps, Validate (inherited→known), Surface intent (vague→specific via dialogue)
- Epistemic delta: significant. Human involvement: high.

---

## Fundamental Activities

| Activity | Purpose | Class | Human | Typical Agents |
|----------|---------|-------|-------|----------------|
| **Ingest** | Bring external info into graph | 2 | High (human), Low (docs/code) | Docreader, Extractor, Elicitor |
| **Critique** | Find problems in target area; for `observed:` nodes, re-verify cited files/symbols/lines/counts vs current code (default-to-refuted) | Read-only | None | Critic, fan-out verifiers |
| **Refine** | Fix identified issues | Mixed | Varies | Elicitor, Steward |
| **Design** | Architecture from intent | 2 | High | Designer |
| **Generate** | Code synthesis from intent+arch | 1 | Low | Generator |
| **Verify** | Test code against intent | 2 (design) / 1 (run) | Moderate | Verifier |
| **Validate** | Post-edit consistency check | 1 | None | Critic, Steward |
| **Commit** | Persist changes, enforce propagation | 1 | None | Steward |

---

## Workflows

### 1. Improve
**Purpose:** Make existing IntentGraph better.
**Activities:** Critique → Refine → Validate → Commit (loop until converged).
**Convergence:** No critical issues, epistemic states resolved or deferred, invariants hold.

### 2. Distill
**Purpose:** Extract intent from existing code/docs, then improve.
**Phase 1 (Extraction):** Ingest (docs) → Ingest (code) → Critique → Refine
**Phase 2 (Improvement):** Critique → Refine → Validate → Commit
**Dual output:** Product IG + ProjectionIG (observed rendering patterns).
**Re-grounding:** `observed:` content decays as code evolves. Periodically re-run the Critique grounding check vs current code (esp. before a Project pass) to catch drifted/fabricated claims.

### 3. Project
**Purpose:** Materialize intent as code.
**Activities:** Design → Generate → Verify → Validate → Commit.
**Escape:** Intent insufficient → pause, run Improve on IG.

---

## Execution Context

Task payload includes environment flags + effort hint:

- **dry_run** — If true, propose changes but don't write.
- **verbosity** — `quiet` / `normal` / `verbose`.
- **effort hint** — Free-form guidance on depth vs speed. No fixed enum. Examples:
  - "Quick pass — flag obvious issues only"
  - "Thorough — cross-check everything"
  - "Sketch depth; exploring scope"

Interpret and adjust: fewer reads + shallow for speed hints; more reads + full propagation for thoroughness hints.

---

## Universal Patterns

**Target-Based Iteration** — Work on one node/small subgraph at a time. Queue order: data-flow priority → epistemic urgency → breadth-first.

**Critique Loop** — Identify issues → Resolve → Verify resolution. Never skip verification.

**Bounded Context** — Lens limits working memory. Query for spot checks. Adjust viewport when target shifts.

**Propagation After Commit** — Every commit triggers neighbor checks (constraints, epistemic, normalization). Quiescence typically Wave 1-2.

**Human Dialogue** — Trigger on genuine uncertainty (Class 2). Batch questions with shared context (PRIMER_DIALOGUE).

---

## Role Guidance

**Doing one activity:** Execute for current target. Watch for Class 1 vs 2, propagation triggers, convergence.

**Running full workflow:** Compose activities, manage queue, decide convergence. Batch Class 2 for human efficiency. Pause when more context needed.
