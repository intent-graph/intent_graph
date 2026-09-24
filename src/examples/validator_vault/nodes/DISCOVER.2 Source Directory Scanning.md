---
intent: |
  Scan all source function directories for .sql files, parse them for CREATE FUNCTION statements (possibly multiple per file), and map each to the corresponding FunctionRecord.
epistemic_state: known
constraints:
  - "Multiple functions per file are supported"
  - "Excluded directories (sql/functions/deprecated/) are skipped"
---