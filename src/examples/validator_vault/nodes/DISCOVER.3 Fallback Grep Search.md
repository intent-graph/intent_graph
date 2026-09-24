---
intent: |
  For generated functions with no source match after directory scanning, search the entire repository using grep/ripgrep to find function definitions in unexpected locations.
epistemic_state: "known — optional, can be skipped for speed"
constraints:
  - "Blacklist approach: exclude only docs/ and deprecated/"
  - "10-second timeout per grep search"
  - "Falls back to ripgrep if grep is not found"
  - "Functions found outside sql/functions/ are flagged"
---