# Docreader — Few-Shot Examples

Reference examples. Read on demand when needed.

## Good extraction — intent from prose

**Documentation:**
> The discovery module scans both the generated function cache and the source SQL directories. It builds a mapping from function name to source file, handling cases where multiple versions of the same function exist across different schemas.

**Good intentnode:**
```yaml
- uid: DISC.1
  name: "Function discovery"
  intent: "Build a complete mapping from SQL function names to their source files, across all schemas, tolerating multiple versions of the same function."
  epistemic_state: "known"
  constraints:
    - "Must scan both generated cache and source directories"
    - "Must handle multi-schema, multi-version function name collisions"
  design_notes: "Source: README.md §Discovery Module"
```

## Bad extraction — implementation note disguised as intent

```yaml
# BAD — this describes HOW the discovery works, not WHY
- uid: DISC.1
  name: "Directory scanner"
  intent: "Walk the filesystem using os.walk, collect .sql files, parse filenames to extract function names and schema prefixes."
```

This is implementation, not intent. The Extractor will find this from code — the Docreader should stay at the intent level.

## Good handling of vague documentation

**Documentation:**
> The reporter produces output in various formats.

**Good intentnode:**
```yaml
- uid: RPT.1
  name: "Report generation"
  intent: "Produce validation results in a consumable format."
  epistemic_state: "undecided"
  design_notes: "Docs say 'various formats' but don't specify which. Extractor should clarify from code."
```
