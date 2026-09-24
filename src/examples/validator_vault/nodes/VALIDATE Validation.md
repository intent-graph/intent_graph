---
intent: |
  Compare parsed function representations from the database (generated) against source code, detecting signature mismatches, body differences, and existence gaps, and classify each discrepancy by severity.
epistemic_state: risky — signature comparison disabled; considering re-enabling with fuzzy matching for v2
constraints:
  - "Severity levels: CRITICAL (missing source, signature mismatch), WARNING (body diff), INFO (minor)"
  - "Type comparison uses normalized forms (int8 = bigint, etc.)"
  - "Body comparison normalizes whitespace before diffing"
  - "Parameter type validation currently disabled — not reliable due to OID resolution"
design_notes: |
  Signature validation is intentionally limited: only language is checked as a sanity check. Parameter type and return type comparison was disabled because PostgreSQL's internal type canonicalization and OID resolution in pg_get_functiondef makes exact comparison unreliable.
---

UP: [[ROOT.canvas|ROOT]]