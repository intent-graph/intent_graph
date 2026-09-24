# Test Fixtures

## Files

| File | Purpose |
|---|---|
| `sample-with-lenses.ig.yaml` | Hand-crafted IG with two named lenses and one stale UID |

---

## sample-with-lenses.ig.yaml

### What it contains

- 5 nodes: `ROOT`, `AUTH`, `AUTH_1`, `AUTHZ`, `SESSION`
- 4 treearcs (standard hierarchy)
- 2 intentlinks: `AUTH_SESSION`, `SESSION_AUTHZ`
- `meta.default_lens: focused` — triggers auto-apply on open (AC4)
- `lenses.focused`: mix of `full`, `lean`, `skeleton` LOD assignments
  plus `STALE.NODE: lean` (not in graph) — triggers diagnostics banner (AC7)
- `lenses.overview`: all nodes at `lean` (clean, no stale UIDs)

### How to use it in F5 session

1. Start the extension in Debug (`F5` in VS Code).
2. In the Extension Development Host window, open this file.
3. The IntentGraph viewer opens automatically.

**AC4 — default lens auto-applied:**
The `focused` lens should apply automatically after first mount:
- `AUTH` and `SESSION` show HTML overlays (full LOD).
- `AUTH_1` shows canvas name only (lean LOD).
- `AUTHZ` (skeleton compound with no children in scope) should collapse.
- No user interaction required.

**AC7 — diagnostics banner:**
Because `STALE.NODE` is in `lenses.focused` but absent from the graph,
a diagnostics banner appears at the bottom listing one warning:
`warn · 'STALE.NODE' not found in graph (stale UID — node may have been deleted)`.

**AC8 — viewer still renders:**
All 5 valid nodes render normally despite the stale UID.

**AC9 — dismiss banner:**
Click `Dismiss` — the banner hides.

**AC5 — openLens QuickPick:**
Run `IntentGraph: Open Lens…` from the command palette.
Both `focused` and `overview` should appear in the picker.
Pick `overview` — all nodes switch to lean display (no overlays).

**AC6 / AC10 — clearLens:**
Run `IntentGraph: Clear Lens` — all compounds expand, overlays disappear,
status shows `Lens cleared`.

**AC11 — Lens + edit composition:**
After applying `focused`, double-click on `AUTH` (full LOD) — the edit
overlay should open on the `intent` or `name` field.

**AC12 — lean LOD no overlay:**
`AUTH_1` is at `lean` in the `focused` lens — it must NOT show an HTML overlay.
