---
intent: |
  Generate human-readable and machine-readable reports summarizing validation results, grouped by severity and issue type, with actionable information for each discrepancy.
epistemic_state: known — stable output format
constraints:
  - "Markdown report: VALIDATION_REPORT.md with severity-grouped tables"
  - "JSON report: validation_data.json with structured data for tooling"
  - "Reports must include pass rate, severity counts, and per-function details"
  - "Reports must be generated within seconds for large repositories"
---

UP: [[ROOT.canvas|ROOT]]