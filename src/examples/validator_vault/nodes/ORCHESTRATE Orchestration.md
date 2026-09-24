---
intent: |
  Coordinate the full pipeline: parse CLI arguments, run discovery, iterate through functions for validation, generate reports, and print a summary with appropriate exit code.
epistemic_state: known — simple linear pipeline
constraints:
  - "CLI args: --output-dir, --verbose, --skip-fallback-search"
  - "Exit code 0 = all valid, exit code 1 = issues found"
  - "Must print progress indicators during execution"
---

UP: [[ROOT.canvas|ROOT]]