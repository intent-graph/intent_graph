# Critic — ProjectionIG Review

Read this when projection observations (PIG nodes) are provided alongside the product lens. This extends the base product review with PIG-specific checks.

## PIG Review Workflow

After completing the product intent review (steps 1-9 in core), review ProjectionIG observations:

10. **Observation quality:** Does each PIG node describe a rendering pattern (not product intent)? Is epistemic_state honest (`observed` vs. assumed)?
11. **Granularity:** At the right level? Not too broad ("uses Python") nor too narrow ("line 42 uses list comprehension"). Should be at convention/pattern level.
12. **Completeness:** Obvious rendering patterns in product lens's `design_notes` that the Extractor missed?

## PIG Issue Types

- `pig_quality` — PIG node describes product intent, not a rendering pattern. Or epistemic_state is dishonest (marked `observed` but actually assumed).
- `pig_granularity` — Observation too broad or too narrow. Should be at convention/pattern level.
- `pig_missing` — Rendering pattern visible in product lens's `design_notes` or `impl_pointers` but not captured in PIG.

## Example

```yaml
- type: pig_quality
  node: PIG-PY.DATA_STRUCTURES
  severity: moderate
  description: "Observation says 'data is stored in dicts' — this describes product behavior, not a rendering pattern. The rendering pattern is 'structured data rendered as Python dicts with string keys.'"
  suggestion: "Rewrite to focus on the rendering convention, not the product data model."

- type: pig_missing
  node: null
  severity: minor
  description: "Product node DISC has design_notes mentioning 'pathlib.Path for all file operations' — this is a Python-specific library choice not captured in PIG."
  suggestion: "Add PIG observation: 'File system paths use pathlib.Path (PEP 428).'"
```
