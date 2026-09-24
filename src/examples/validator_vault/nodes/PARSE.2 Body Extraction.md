---
intent: |
  Extract the function body text from a CREATE FUNCTION statement, handling dollar-quoted ($$ ... $$) and single-quoted bodies.
epistemic_state: "constrained — uses heuristic regex, not pure AST"
constraints:
  - "Must handle $tag$...$tag$ dollar quoting"
  - "Must handle '...' single quoting with escaped quotes"
  - "Fallback strips LANGUAGE/IMMUTABLE/etc. clauses via regex"
design_notes: |
  Body extraction is regex-based (not from pglast AST) because pglast normalizes the body text, losing the original formatting. We need the raw body for comparison.
---