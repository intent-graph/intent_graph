# PRIMER_03A_EDITING

Decision framework for modifying an IntentGraph. Assumes PRIMER_00, 01, 02.

---

## Edit Types

Create/update/delete nodes or intentlinks; decompose (expand) nodes; consolidate constraints upward. All via CLI (PRIMER_TOOLS), never manual YAML.

**Intermediate states allowed:** You may leave nodes temporarily overloaded/under-defined if `epistemic_state` records it. Example: `observed | unclear: intent overloaded, expansion pending`. Don't block progress on perfect shape — document interim state.

---

## Edit Scope and Propagation

**Scope** = atomic consistency boundary:
- Single-node: update intent, constraint, epistemic_state
- Multi-node: expansion (parent + children), link creation (src + dst; qualified `graph_id:node_uid` for inter), reparenting (node + old/new parent), consolidation (parent + children)

**Propagation** — After edit, verify consistency in waves:
- Wave 0: Apply to target
- Wave 1: Check immediate neighbors
- Wave 2+: If Wave 1 needed changes, propagate from their neighbors
- Quiescence: typically Wave 1-2. Beyond Wave 3 → deeper structural issues.

**Propagation channels:**

| Source | Propagates | Direction | Check |
|--------|-----------|-----------|-------|
| T4 | Refinement coherence | Up & Down | Parent↔children still consistent? |
| T3 | Connectivity | Horizontal | Links valid after node changes? |
| P5 | Normalization | Up & Down | Duplicates across peers → consolidate |
| P4 | Projection separation | IG↔PIG | Language-specific → route to PIG |
| P2 | Meaning stability | Down | Children add precision, not new scope |
| Epistemic | Uncertainty flow | All | Parent risky → children inherit. All children undecided → parent can't be known. |

---

## When to Expand

### Atomic Node Test (No Expansion Needed If All Pass)

1. Describes ONE capability at ONE abstraction level
2. Constraints are cohesive (all govern same sub-capability)
3. Maps to single code unit
4. Intent describable in ONE sentence without "and" joining fundamentally different things

### Expansion Signals

1. **Multiple sub-capabilities** — intent joins 2+ capabilities with "and"/"also"
2. **Constraint sprawl** — 8+ constraints across unrelated concerns
3. **Multiple implementation boundaries** — impl_pointers reference distinct modules/classes
4. **Distinct algorithmic phases** — design_notes describe separate processing stages

### When NOT to Expand

- Genuinely atomic (passes test above)
- Constraints numerous but cohesive (10 type normalization rules = one purpose)
- "Phases" are implementation detail, not conceptual boundaries

If expansion warranted but deferred → record in `epistemic_state`.

---

## Expansion Protocol

### 1. Identify Sub-Capabilities
Group parent's constraints, impl_pointers, design_notes into coherent clusters → each cluster = one child.

### 2. Create Children
UID rules: root=exactly `ROOT` (enforced), L1=keyword, L2=`{parent}.{number}` or `{parent}.{KEYWORD}`, L3+=`{parent}.{number}` (numeric suffix only — keyword suffix is L2-only, so `ERRORS.HANDLER.1` not `ERRORS.HANDLER.PARSE`). Name as capability/component, NOT action verbs ("Cache Discovery" not "Scan Cache").

Each child needs: uid, name, intent, parent, epistemic_state.

### 3. Migrate Content (Mandatory)
- **constraints**: Partition. Cross-cutting → parent. Local → children.
- **impl_pointers**: Distribute to relevant child. Parent keeps summary.
- **design_notes**: Split reasoning. Parent keeps decomposition rationale only.
- **examples**: Move to illustrating child. Parent keeps system-level.
- **data_registry**: Cross-cutting → parent. Local → children. No sibling duplication.

No orphan content (P5).

### 4. Rewrite Parent Intent
Becomes orchestration-level: "Achieve [goal] by [composition strategy]"

### 5. Discover IntentLinks
For each child pair, check: Dataflow? Requires? Conflicts? Refines? Also check cross-subtree dependencies. Create links only for semantic (intent-level) relationships — not code-level calls, shared utilities, or tree-implicit relationships.

---

## Editing Existing Nodes

**intent**: WHY not HOW (blind generation test), projection-agnostic (language-swap test), self-sufficient.
**constraints**: Cross-cutting or local? Product or projection? Duplicates? (P5)
**epistemic_state**: Be honest. Use vocabulary + issue annotations. Upgrade inherited→known with evidence in history.
**design_notes**: WHY this choice. Rejected options. Tradeoffs. Tool choices here, not in intent.

---

## Propagation Checklist (After Any Edit)

- T4: Parent↔children coherent?
- T3: IntentLinks valid?
- P5: Constraints normalized, no peer duplication?
- P4: Projection detail routed to PIG?
- P2: Refinement adds precision, not scope?
- Epistemic: Uncertainty propagated?

Violation → correct neighbor or flag with issue annotation.
