# PRIMER_01_SEMANTICS

How to read and interpret an IntentGraph. Assumes PRIMER_00_PHILOSOPHY.

---

## Node Fields

**intent** — WHAT this part does and WHY. Not HOW. No tool names, no library choices (those → `design_notes`). Must pass blind generation test: reader understands purpose, cannot reproduce exact code.

**constraints** — MUST conditions. Cross-cutting (orchestration) stays on parent; local (data structure, tool behavior) descends to children.

**design_notes** — WHY this choice over alternatives. Rejected options, accepted tradeoffs. Tool/library choices go here.

**epistemic_state** — What is KNOWN. Free text. Common patterns:
- `known` — stable, well-understood
- `undecided` — options exist, no decision yet
- `risky` — decision carries identified risks
- `speculative` — best guess, low confidence
- `inherited` — assumed from parent, not validated
- `observed` — extracted from code (Distill); carries a standing re-grounding obligation — re-verify cited files/symbols/lines vs current code, default-to-refuted (PRIMER_04 §Critique)
- Missing → treat as `unassessed`

**Multi-issue convention:** `<base_state> | <issue>: <desc> | <issue>: <desc>`
Issue vocabulary: `gap:`, `conflict:`, `missing:`, `unclear:`, `unvalidated:`
Example: `"observed: from auth.py | gap: perf requirements not specified"`

**impl_pointers** — WHERE realized in code. **list[str]**, one pointer per entry, grammar: `path[::Symbol[.member]][ (lines X-Y)]`. Prefer symbol anchors over line ranges.

**history** — WHO/WHEN provenance. Append-only; **never hand-written**: every `ig-tool` save auto-stamps changed nodes (write-boundary). Pass `--role <role>` (→ `who: agent:<role>`) and `-m "<why>"` (→ note; omitted → auto diff summary). Trivial changes (reorder, lens config) don't stamp.

**data_registry** — Structured data (positions, config, thresholds). Other fields reference via slash-notation: `/positions/ROOT.1/x`. Rules: values are data not prose (G2); every key referenced by another field (G1); parent=cross-cutting, children=local, no sibling duplication (G3); product IG=domain data, PIG=rendering data (G4).

**examples** — Concrete scenarios illustrating intent. Not test cases.

**collapsed_children** — (read-only in Lens) UIDs of unexpanded children.

---

## UID Format Convention

| Level | Pattern | Examples |
| --- | --- | --- |
| ROOT | Exactly `ROOT` (required, enforced); `--root-name` = display name only | `ROOT` |
| L1 (children of root) | `^[A-Z][A-Z0-9_]*$` or `^[0-9]+$` (underscores OK, no leading `_`) | `DISCOVER`, `ERRORS`, `API`, `LEXER_TOKENS`, `1` |
| L2 (numeric) | `{parent}.{number}` | `DISCOVER.1`, `PARSE.2` |
| L2 (semantic) | `{parent}.{KEYWORD}` (KEYWORD = `^[A-Z][A-Z0-9_]*$`) | `DISCOVER.DB`, `ERRORS.HANDLER`, `LEXER.PARSER_INTERFACE` |
| L3+ | `{parent}.{number}` — numeric suffix only; keyword suffix is L2-only | `ERRORS.HANDLER.1` (not `ERRORS.HANDLER.PARSE`) |
| ProjectionIG L1 | `PIG-{SEMANTIC}-{COMPONENT}` | `PIG-PY-TYPES` |

Root caveat: the root UID is always `ROOT` (enforced). `--root-name` changes the display name, never the UID.

---

## Reading the Tree

Parent = abstract summary (Level N), self-sufficient. Children = precision (Level N+1), collectively refine parent, no new scope, no overlap.

**Correct parent test:** Can you read parent alone and understand WHAT? If no → parent written wrong.
**Correct children test:** Do children collectively cover parent? Anything not addressed → missing child. Child exceeds parent scope → violates T4. Two children overlap → not orthogonal, refactor.

**Content distribution after expansion:**
- `intent`: Parent → orchestration summary. Children → specific sub-capability.
- `constraints`: Cross-cutting stays on parent. Local descends.
- `impl_pointers`: Parent → package/module. Children → files/classes/functions.
- `design_notes`: Parent → decomposition rationale. Children → sub-capability reasoning.
- `data_registry`: Parent → shared/cross-cutting. Children → local. No sibling duplication.

**Critical:** Execution order is NOT structure. "Do X then Y then Z" is projection detail, not product intent. Flag if seen.

---

## Reading IntentLinks

Semantic relationships between nodes. Four patterns:

1. **Dataflow** — "X produces output Y consumes." Y must adapt if X changes output.
2. **Requires** — "Y depends on X's capability." X must exist before Y functions.
3. **Conflicts** — "X and Y are mutually exclusive." Alternative strategies.
4. **Refines** — "Y specializes X's capability." X's data model changes must reflect in Y.

**Not intentlinks:** code-level function calls, shared utility usage, implicit tree relationships (parent↔child). **Inter intentlinks:** PIG → product (qualified `graph_id:node_uid`).

**Lifted links:** Auto-computed when nodes collapse. `EXTRACT.1→TRANSFORM.2` lifts to `EXTRACT→TRANSFORM` at coarser view. Never create manually.

---

## Dual-Graph Interpretation

Both are full IntentGraphs with same rules (T1-T4, P1-P5).

**Product IG** — WHAT/WHY. Belongs: "output is keyed mapping of function records", "must validate signatures". Does NOT belong: `Dict[str, FunctionRecord]`, "uses pglast", "errors to stderr".

**ProjectionIG** — HOW rendered, WHY those choices. Belongs: "use dataclasses not dicts", "snake_case functions", "raise exceptions not error codes".

**Language-swap test:** Replace Python→C++. Still makes sense? → Product IG. Breaks? → ProjectionIG.

---

## Common Misreadings (Avoid These)

1. **Execution sequence thinking** — Parent describes procedure ("do X then Y"). Wrong: parent describes WHAT, not HOW.
2. **Children as function calls** — Children aren't steps parent "calls". They're refinements at higher resolution.
3. **Tool names in intent** — "Use pglast to parse SQL" → wrong. Intent: "Parse SQL definitions." Tool → design_notes.
4. **Data schema in orchestration node** — Complete type signatures at parent level. Schemas are leaf detail.
5. **Missing intentlinks** — Pipeline nodes without explicit dataflow links. Make dependencies explicit.
6. **Epistemic confusion** — `undecided` ≠ bad. `known` ≠ good. Epistemic state is transparency, not quality.
