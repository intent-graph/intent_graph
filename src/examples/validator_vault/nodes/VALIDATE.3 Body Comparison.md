---
intent: |
  Compare function bodies after whitespace normalization, using SequenceMatcher for similarity scoring when bodies differ.
epistemic_state: known
constraints:
  - "Whitespace normalized: trailing spaces removed, lines stripped"
  - "Uses difflib.SequenceMatcher for similarity ratio"
  - "Any difference = WARNING severity"
---