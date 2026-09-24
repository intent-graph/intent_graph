---
intent: |
  Extract function metadata from pglast AST: schema, name, parameter types, return type, and language.
epistemic_state: known
constraints:
  - "Uses pglast AST nodes: CreateFunctionStmt, DefElem, TypeName"
  - "Schema defaults to 'public' if not specified"
  - "Language defaults to 'plpgsql' if not specified"
---