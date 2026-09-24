---
intent: |
  Scan the generated cache directory for .sql files, parse filenames to extract schema.function_name, and parse each file's SQL to create FunctionRecord entries with generated_parsed data.
epistemic_state: known
constraints:
  - "Files named schema.function_name.sql — skip malformed names"
  - "Each file contains one CREATE FUNCTION from pg_get_functiondef()"
---