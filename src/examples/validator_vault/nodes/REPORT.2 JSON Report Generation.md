---
intent: |
  Generate structured JSON data with timestamp, summary statistics, and per-function results including severity, issues, and details.
epistemic_state: known
constraints:
  - "Output: validation_data.json"
  - "Must include: timestamp, summary (totals, pass_rate, by_severity), results array"
---