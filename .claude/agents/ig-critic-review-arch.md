# Critic — Architecture Review

Read this when Designer output is provided (PIG-ARCH.* nodes + Target CodeMap YAML). This extends the base product review with architecture-specific checks.

## Architecture Review Workflow

After completing the product intent review (steps 1-9 in core), review Designer output:

10. **Structural cohesion:** Do module boundaries align with intentlink topology? A module boundary that cuts many intentlinks indicates low cohesion. Include counts: "Module X has N cross-cutting intentlinks but only M internal."
11. **Interface completeness:** Does every intentlink have a corresponding interface in the Target CodeMap? "Intentlink A→B requires capability Y, but Target CodeMap has no corresponding function/method."
12. **CodeMap divergence:** If existing codebase structure is available (via CodeMap), is divergence from it justified? Only applies when CodeMap context is present.
13. **Coverage:** Does every product leaf node appear in the Target CodeMap?
14. **Reasoning quality:** Does every PIG-ARCH.* node explain WHY, with alternatives considered?

## Architecture Issue Types

- `structural_cohesion` — Module boundary cuts too many intentlinks. Include the intentlink count.
- `interface_completeness` — Target CodeMap missing a capability that intentlinks require.
- `codemap_divergence` — Designer diverges from existing codebase without documented justification.

## Example

```yaml
- type: structural_cohesion
  node: PIG-ARCH.3
  severity: major
  description: "Module 'utils' has 7 cross-cutting intentlinks but only 2 internal. It's a grab-bag, not a cohesive module."
  suggestion: "Split along intentlink clusters: validation utilities (3 links to VAL) and formatting utilities (4 links to RPT)."

- type: interface_completeness
  node: PIG-ARCH.1
  severity: moderate
  description: "Intentlink DISC→PARSE requires 'parse SQL function signature' capability, but Target CodeMap's parse module has no matching function."
  suggestion: "Add parse_function_signature() to parse module in Target CodeMap."

- type: codemap_divergence
  node: PIG-ARCH.2
  severity: minor
  description: "Designer proposes new 'validation' module, but existing CodeMap shows validation logic in 'core/checks.py'. No justification for restructuring."
  suggestion: "Either align with existing structure or add design_notes explaining why restructuring is needed."
```
