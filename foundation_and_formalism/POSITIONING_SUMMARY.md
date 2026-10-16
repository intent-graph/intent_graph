# IntentGraph — Positioning Summary (Phase 0)

**Status:** Working draft — synthesis of existing positioning material  
**Sources:** [STATE_OF_THE_ART__INTENT_FIRST_AND_SPEC_DRIVEN.md](../STATE_OF_THE_ART__INTENT_FIRST_AND_SPEC_DRIVEN.md)  
**Goal:** One-page answer to "how does IntentGraph relate to and differ from every other approach?" — the positioning paper called for in WP-0.1.4.

---

## The Root Claim

**Code is the wrong source of truth.** It records *how* but not *why*, *what was rejected*, or *what remains uncertain*. Every downstream problem — documentation drift, stakeholder lock-out, flat hierarchy, invisible uncertainty, language lock-in — traces to this.

**IntentGraph replaces code with a structured, multi-level, navigable intent graph as the canonical model.** Everything else — code, docs, specs, visual views — is a projection.

---

## Landscape: Four Families and Their Gaps

### 1. Spec-Driven Development (Tessl, Traycer, Kiro, GitHub Spec Kit)

**What they do:** Capture expected behavior in structured natural-language documents (Markdown specs, EARS syntax, Given/When/Then). Use specs to guide LLM code generation.

**Where they stop:**
- A spec describes *behavior*, not *intent*. It says what the system should do, not why those behaviors were chosen, what alternatives were rejected, or what remains undecided.
- Specs are **flat text** — no hierarchy of purpose, no explicit relationships, no zoom. Dependencies between spec items are implicit. When the system grows, the implicit relationship surface grows combinatorially.
- Specs have **no representation for uncertainty** — an item is either written or not.
- Specs are better prompts. They do not capture the reasoning that precedes and outlives any implementation.

**IntentGraph difference:** The IntentGraph is hierarchical (mixed-detail tree), relational (intentlinks with typed semantics), and epistemic (explicit known/undecided/risky/deferred states). Specs can be *generated as projections* of the graph for the right audience. Product intent and rendering-specific concerns (language, paradigm, naming conventions) live in separate graphs — the product IntentGraph and the ProjectionIG — so behavioral specs never carry implementation assumptions (P4).

### 2. Formal Methods & Goal Modeling (KAOS, i*, TLA+, Alloy)

**What they do:** Mathematical rigor — goal decomposition, state-machine specification, relational constraint modeling.

**Where they stop:**
- Still about **goals and behavior**, not intent. A KAOS goal tree captures the *result* of a design decision, not the *reasoning* behind it.
- They are **alternative programming languages** — with their own syntax, semantics, type systems. The stakeholder problem is not solved, just relocated. The specification itself can drift from reality.
- They **demand completeness** — you cannot have a half-specified model. This is fundamentally at odds with iterative, uncertainty-laden real-world development.

**IntentGraph difference:** Incompleteness is first-class (P3). Epistemic state is modeled, not forbidden. The graph does not require formal-logic fluency to read or contribute to — it is navigable by mixed-skill teams at chosen levels of detail.

### 3. Projectional Editing & Language Workbenches (JetBrains MPS, Intentional Programming)

**What they do:** Separate the model from its views. Code stored as AST; users edit projections; generation plans transform models.

**Where they stop:**
- The architecture is right (separate model from views) but applied to the **wrong object**: they separate syntax from code structure, when the problem is separating intent from implementation.
- The underlying model is still an AST — a representation of code, not of intent.
- No definition of what intent *is*, how it decomposes hierarchically, how to represent uncertainty.

**IntentGraph difference:** The model is an intent graph, not an AST. The projections are intent-derived (code, docs, specs, visual views), not syntax-derived. The architecture is the same principle (canonical model + projections) applied at the right level of abstraction.

### 4. Intent-Native Runtimes (Unison, Embabel/GOAP, Darklang)

**What they do:** Embed intent into execution or storage — content-addressed code, goal-oriented action planning at runtime, trace-driven infrastructure.

**Where they stop:**
- Address **execution**, not design. They do not capture the human decisions, trade-offs, and unknowns that precede implementation.
- Language-locked. Cannot represent a system that doesn't exist yet or parts that are deliberately underspecified.
- Non-technical stakeholders still cannot interact with the source of truth.

**IntentGraph difference:** Operates at design time, not runtime. Language-agnostic (one graph → code in any language). Accessible to non-technical stakeholders via lens-level projections.

---

## The Structural Gap IntentGraph Fills

None of the four families make **intent** — the why, the reasoning, the trade-offs, the uncertainty — into a **first-class, structured, multi-level, navigable artifact** that *replaces* code as the source of truth rather than sitting alongside it.

| Property | Spec-Driven | Formal Methods | Projectional | Runtimes | **IntentGraph** |
|----------|-------------|----------------|--------------|----------|----------------|
| Hierarchical (mixed-detail) | No (flat text) | Partial (goal trees) | No (AST) | No | **Yes** (treearc refinement) |
| Explicit relationships | No (implicit) | Yes (formal) | No | No | **Yes** (intentlinks, typed) |
| Epistemic state | No | No (demands completeness) | No | No | **Yes** (known/undecided/risky/deferred) |
| Stakeholder-accessible | Partial (text) | No (formal notation) | No | No | **Yes** (lens projections) |
| Language-agnostic | No | Yes | No | No | **Yes** (code is a projection) |
| Bidirectional sync | No | No | Partial | No | **Yes** (projection reconciliation) |
| Tolerates incompleteness | No | No | N/A | N/A | **Yes** (P3) |
| Product/projection separation | No | No | No | No | **Yes** (P4 — dual-graph architecture) |

---

## Strategic Position

IntentGraph is not competing with Cursor/Copilot on the speed of writing the first line of code. Text will always win there.

But that first line is the easy part. Vibe-coded systems **cannot grow** — adding a feature means re-prompting the whole thing and hoping it doesn't break. They **cannot be reused** — there is no structured knowledge to extract and carry to another project. And they **can barely be used** — the moment you need to debug, extend, or hand off, you're reverse-engineering an artifact that not even its "author" understands.

This is not about convenience or maintainability as a nice-to-have. Without captured intent, AI-generated code is **disposable by construction**. It works once, for one context, and then it's trash. IntentGraph is the condition for producing software that is reliable, evolvable, and reusable at all — the difference between a throwaway demo and something you can actually build on.

---

## Source Traceability

| Claim | Source |
|-------|--------|
| "Code is a terrible source of truth" argument | — |
| Four-family taxonomy and gap analysis | [STATE_OF_THE_ART__INTENT_FIRST_AND_SPEC_DRIVEN.md](../STATE_OF_THE_ART__INTENT_FIRST_AND_SPEC_DRIVEN.md) §2–4 |
| Comparison table properties | — |
| Strategic position (not competing on first line) | — |
| "Governance layer" framing | — |
