---
intent: |
  Locate all SQL function definitions in both the generated cache (database source of truth) and the source code directories, then map each generated function to its source counterpart.
epistemic_state: known — well-tested discovery with fallback grep
constraints:
  - "Generated cache dir: build/db_dump/functions/"
  - "Source dirs: sql/functions/ (recursive)"
  - "Exclude dirs: sql/functions/deprecated/"
  - "Filenames in generated cache follow schema.function_name.sql convention"
design_notes: |
  Three-pass strategy: (1) scan generated cache, (2) scan source dirs, (3) fallback grep for unmatched functions. The fallback grep is optional but catches functions stored in unexpected locations.
---

UP: [[ROOT.canvas|ROOT]]