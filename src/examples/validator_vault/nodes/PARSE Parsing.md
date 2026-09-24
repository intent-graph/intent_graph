---
intent: |
  Parse SQL function definitions from raw .sql files into structured representations (signature + body), with type normalization to reduce false positives from PostgreSQL's type aliasing.
epistemic_state: known — uses pglast (official PG parser); robust but has edge cases
constraints:
  - "Must use pglast for reliable parsing (not regex-only)"
  - "pglast may fail on non-standard SQL (non-SQL procedural languages) — must skip gracefully"
  - "Must handle both dollar-quoted and single-quoted function bodies"
  - "Must handle multi-statement SQL files"
design_notes: |
  pglast was chosen over regex-only parsing because CREATE FUNCTION syntax is too complex for reliable regex extraction.
---

UP: [[ROOT.canvas|ROOT]]