---
intent: |
  Generate a human-readable markdown report with summary statistics, severity-grouped tables (missing/misplaced, body mismatch, not deployed), and valid function counts.
epistemic_state: known
constraints:
  - "Output: VALIDATION_REPORT.md"
  - "Sections: Missing/misplaced, No Match, Outside sql/functions/, Body Mismatch, Not Deployed, Valid"
---