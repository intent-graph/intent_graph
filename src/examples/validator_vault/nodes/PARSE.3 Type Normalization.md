---
intent: |
  Normalize PostgreSQL type aliases to canonical forms so that type comparisons are not confused by synonyms (e.g., bigint = int8).
epistemic_state: known — covers 9+ type aliases
constraints:
  - "Canonical forms: int8, int4, int2, float8, float4, bool, bpchar, varchar, text"
  - "Also handles: timestamptz, timestamp"
  - "Normalization is case-insensitive and whitespace-normalized"
---