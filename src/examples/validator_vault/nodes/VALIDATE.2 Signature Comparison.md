---
intent: |
  Compare function signatures between generated and source, currently limited to language-only checking due to type aliasing limitations.
epistemic_state: constrained — parameter and return type comparison disabled
constraints:
  - "Only language is compared (sanity check)"
  - "Type validation disabled: PostgreSQL OID resolution makes comparison unreliable"
---