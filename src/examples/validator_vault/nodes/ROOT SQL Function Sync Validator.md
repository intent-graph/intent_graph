---
intent: |
  Detect and report discrepancies between SQL functions in the database (represented by generated cache) and their source code definitions in the repository, so that DB drift is caught before it causes production issues.
epistemic_state: known
constraints:
  - "Source of truth is the database (generated cache via pg_get_functiondef)"
  - "Must scale to repositories with many schemas"
  - "Must gracefully skip unparseable SQL (pglast limitations)"
  - "Output must be both human-readable (markdown) and machine-readable (JSON)"
design_notes: |
  Pipeline architecture: Discovery -> Parsing -> Validation -> Reporting. Chosen over a monolithic approach for testability and clear separation of concerns. Parser uses pglast (the official PostgreSQL parser).
history:
  - who: "agent:extractor"
    date: 2026-02-12
    note: Created IntentGraph by hand as a demonstration.
---