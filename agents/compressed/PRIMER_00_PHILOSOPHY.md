# PRIMER_00_PHILOSOPHY

An **IntentGraph** is a refinable hierarchy of intentnodes connected by treearcs (refinement) and intentlinks (semantic relations). It is the canonical model — code, docs, tests are derived projections. Mixed detail levels: different parts stay coarse or refine arbitrarily. You work on a local Lens at chosen detail, never the whole graph.

**The problem it solves:** In conventional software, intent is implicit (scattered in meetings/tickets/memory), code is flat (no zoom levels), uncertainty is invisible, and relevance is hard to scope. IntentGraph inverts this: intent is source of truth; code is a derived projection.

---

## Axioms (Absolute — Violating Breaks the Model)

**P1 — Intent is source of truth.** Code, docs, specs are projections derived from the graph. The graph is the invariant.

**P2 — Zooming adds information, never changes meaning.** Refining a node into children increases precision but preserves the parent's role. Parent + children = same intent surface at different resolution.

**P3 — Incompleteness is first-class.** Coarse areas, unknowns, and uncertainty are modeled structurally, not hidden.

**P4 — Projection is orthogonal.** WHAT a system does (product intent) and HOW it's materialized (projection intent) are independent. Each gets its own IntentGraph.

**P5 — Information is normalized and compressed.** Intent stated once per level. Children partition parent orthogonally. Add precision by going down, not making nodes longer. Cross-cutting concerns captured once and linked.

---

## Core Vocabulary

**intentnode** — Unit of intent. Fields: uid, name, intent, epistemic_state, constraints, design_notes, examples, impl_pointers, history, data_registry. UID convention (enforced): root UID **exactly `ROOT`** (required; `--root-name` = display only); L1=single keyword `^[A-Z][A-Z0-9_]*$` (`DISCOVER`, `ERRORS`, `LEXER_TOKENS` — underscores OK inside, no leading `_`) or number; L2=`{parent}.{number}` or `{parent}.{KEYWORD}` (e.g. `LEXER.PARSER_INTERFACE`); L3+=`{parent}.{number}` — numeric suffix only, keyword suffix is L2-only (`ERRORS.HANDLER.1` OK, `ERRORS.HANDLER.PARSE` rejected).

**treearc** — Directed refinement edge `parent → child`. All form a rooted tree. No payload.

**intentlink** — Directed, valued relation between nodes. Carries intent sentence (data exchange, dependency). Orthogonal to tree. Intra = same graph; inter = between graphs (qualified UID).

**Lens** — Working view with variable LOD per node (skeleton/lean/full). Manipulate viewport: focus, promote, expand, prune.

**projection** — Derived artifact from a graph view (code, docs, tests). Bidirectional: projection edits can flow back.

**ProjectionIG** — Full IntentGraph capturing rendering intent (paradigm, naming, error handling). Same formalism as product graph. `PIG-<TAG>.` UID prefix.

---

## Three Operation Types

1. **Improve** — Refine the graph through dialogue, critique, expansion.
2. **Distill** — Extract intent from existing code/docs into graph.
3. **Project** — Generate code/doc from refined IntentGraph + ProjectionIG.

---

## Dual-Graph Model

**Product IntentGraph** — WHAT the system does and WHY. Projection-agnostic.
**ProjectionIG** — HOW a specific projection is rendered and WHY those choices.

**Language-swap test:** Replace target language mentally. Sentence still makes sense? → Product IG. Breaks? → ProjectionIG.

---

## Invariants (Enforced by Core Library)

**T1 — Tree well-formedness.** Rooted tree, one parent per node, no cycles.
**T4 — Refinement coherence.** Children collectively cover parent's intent; no child contradicts or extends beyond parent scope.
**T3 — Graph connectivity.** All intentlink endpoints exist. Inter intentlink endpoints exist in their respective graphs (via intent_resources). Cross-references valid.
**L1 — Lens viewport validity.** Lens maintains valid tree. LOD assignments coherent.

---

## Cardinal Rules

1. **Never invent intent.** Unknown → `epistemic_state: "undecided"`. False certainty worse than acknowledged uncertainty. When *auditing*: cannot confirm a claim against a real artifact → default to refuted, never "probably fine."
2. **Keep product and projection separate (P4).** Language-specific → ProjectionIG. Apply language-swap test.
3. **Express WHY, not HOW.** Intent reads like code summary → rewrite. Blind generation test: reader understands purpose, not exact code.
4. **Never read the full graph.** Use Lens + `ig-tool query` for spot checks.
5. **Manipulate viewport actively.** Promote, expand, prune, demote as needed.
6. **Use hard tools when they exist.** Check `PRIMER_TOOLS.md` (WHY/when) and `.claude/skills/ig-tool-*/SKILL.md` (exact flags) first.
7. **Task return ≤ 80 words.** Detail goes to disk.
8. **Respect execution context.** Follow effort hint, dry_run, verbosity from task payload.

---

## Temporary Relaxation

Quality rules (bounded nodes, orthogonal decomposition) describe target state. Intermediate violations are acceptable **if** recorded in `epistemic_state` with issue annotations. Example: `observed | unclear: intent overloaded, expansion pending`. Never leave violations undocumented.

---

## What You Are Documenting

Capture intent of EXISTING systems, not future designs (exception: Declare from scratch).
- Wrong: "We should add X" → Correct: "The system handles Y using X"
- Exception: `undecided`/`deferred` can note open decisions.

---

## Mental Model

The tree is an **abstraction hierarchy**, not a call graph. Parent summarizes; children refine at higher resolution. Parent doesn't "call" children.

**Test:** If you must expand children to understand WHAT the parent does, the parent is written wrong.
