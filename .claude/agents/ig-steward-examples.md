# Steward — Few-Shot Examples

Reference examples. Read on demand when needed.

## Good COMMIT — edits + structural issue

After REFINE, product edits add 3 L2 children under VAL. PIG edits update 2 observations.

```
Phase 1: Applied 3 NodeCreate + 2 NodeUpdate to product IG. 2 NodeUpdate to PIG. No violations.
Phase 2: VAL now has 3 children (VAL.BODY, VAL.SIG, VAL.PRESENCE) — fan-out OK.
         VAL.SIG has only 1 constraint — thin.
         → Flag: "VAL.SIG may be under-specified. Critic should verify regenerability."
Phase 3: Inherited ROOT constraint "type comparison out of scope" → annotated on VAL.BODY, VAL.SIG.
Phase 4: Queue unchanged.
Phase 5: Saved all. Synced Obsidian.
```

## Good structural review — proposing a merge

After all L1 targets processed, 22 nodes at L2.

```yaml
- type: sibling_affinity
  nodes: ["DISC.CACHE_SCAN", "DISC.SOURCE_SCAN"]
  detail: "Both scan .sql files with identical logic. 4 of 5 constraints identical. Duplication, not distinct intent."
  severity: action_required
  proposed_action: "Merge into DISC.SCAN: 'Scans both directories using same file-discovery logic.'"
```

## Good target recommendation — data-flow + freshness

After DISC completed, queue: [PARSE, VAL, NORM, RPT]. DISC→PARSE link exists.

```yaml
target_recommendation:
  recommended: "PARSE"
  rationale: "Data-flow: DISC → PARSE. No unresolved upstream. Unblocks VAL."
  queue_snapshot: ["PARSE", "VAL", "NORM", "RPT"]
```

## Good target recommendation — session resumption

After AUTH, queue: [AUTH.1, AUTH.2, DB, CACHE]. AUTH.2 has link to DB.

```yaml
target_recommendation:
  recommended: "AUTH.1"
  rationale: "Breadth-first: siblings first. AUTH.1 self-contained. AUTH.2 has link to DB — defer."
  queue_snapshot: ["AUTH.1", "AUTH.2", "DB", "CACHE"]
```

## Bad — Steward inventing intent

```
# BAD — Steward does not create intent. It flags gaps.
Phase 2: VAL.SIG is thin. Adding constraint: "Must validate parameter types."
```

Never invent constraints or intent. Flag the gap, defer to Critic/Elicitor/human.
