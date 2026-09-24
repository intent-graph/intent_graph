# Elicitor — Few-Shot Examples

Reference examples. Read on demand when needed.

## Good — both sections, full context

**Section 1 — Minimap + ask:**

```
             ROOT "SQL function sync validator"
                         │
 ┌────────────┬──────────┼───────────┬──────────────────┐
DISC         PARSE      [VAL]       RPT                NORM
"Function    "SQL       "Discrepancy "Report           "Body normalization
 discovery"   parsing"   detection"   generation"       & classification"
```

**Critic (epistemic_gap, major):** Docs say type comparison is CRITICAL. Code has it disabled. `design_notes` flags this but intent doesn't resolve.

**A — Out of scope:** Type comparison excluded this version. VAL → `known`.
**B — Intended but broken:** Type comparison desired but non-functional. VAL stays `risky`.

Which reflects the true product intent?

**Section 2 — Deepened context:**

```yaml
- uid: VAL
  name: "Discrepancy detection and classification"
  intent: "Compare parsed function representations..."
  epistemic_state: "risky"
  constraints:
    - "Language mismatch: CRITICAL (only signature-level check active)"
    - "Parameter type comparison DISABLED due to unreliable detection"
  design_notes: "SIGNIFICANT DEVIATION from Docreader: docs say type checks CRITICAL, code disabled."
```

Siblings: DISC "Discovery" (known), PARSE "Parsing" (known), RPT "Report" (known), NORM "Normalization" (known)
Parent: ROOT "SQL sync validator" (known)
Links: DISC → VAL "produces FunctionRecord" | VAL → RPT "produces ValidationReport"

## Good — pattern ruling

**Section 1:**

13 projection leaks with Python-specific terms:
- "Python function" (3 nodes), "dict key" (4), "JSON output" (2), "list comprehension" (1), "kwargs" (3)

**Ruling:** Rewrite all language-specific constraints to abstract terms + move specifics to PIG?

**A** — Yes, apply pattern. Show batch.
**B** — No, review case-by-case.

**Section 2:**

**Pattern rationale:** Language-swap test flags all 13. Rendering choices, not product intent.

**Example rewrite:**
```yaml
# Before (product): "Returns dict with 'status' and 'message' keys"
# After (product):  "Returns structure with status and message fields"
# After (PIG):      PIG-PY.DATA_STRUCTURES: "Structures rendered as Python dicts"
```

Affected: VAL (3), RPT (2), NORM (4), DISC (2), PARSE (2)

## Good — node bundle

**Section 1:**

Three issues on VAL:

```
       ROOT "SQL sync validator"
          │
    ┌─────┼──────┬───────┐
   DISC  [VAL]  RPT    NORM
```

1. **epistemic_gap (major):** Type comparison disabled, docs say CRITICAL.
2. **missing_constraint (moderate):** No max discrepancy limit.
3. **projection_hints (minor):** "CRITICAL" is severity language, not intent.

Start with #1 — is type comparison permanently out of scope or intended but non-functional?

**Section 2:**

```yaml
- uid: VAL
  name: "Discrepancy detection and classification"
  intent: "Compare parsed representations, identify discrepancies, classify by severity"
  epistemic_state: "risky"
  constraints:
    - "Language mismatch: CRITICAL (only signature-level check active)"
    - "Parameter type comparison DISABLED due to unreliable detection"
  design_notes: "SIGNIFICANT DEVIATION: docs say type checks CRITICAL, code disabled."
```

Siblings: DISC (known), PARSE (known), RPT (known), NORM (known)
Parent: ROOT (known)
Links: DISC → VAL "produces FunctionRecord" | VAL → RPT "produces ValidationReport"

## Bad — no sections, no context

> 19 issues found. 18 auto-resolvable. One decision on VAL: type comparison — out of scope or broken?

No node content, no hierarchy, no brim. Human can't reason about it.
