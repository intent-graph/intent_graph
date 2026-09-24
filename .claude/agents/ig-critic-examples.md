# Critic — Few-Shot Examples

Reference examples. Read on demand when needed.

## Good critique — under-decomposition + regenerability

Node under review:
```yaml
- uid: A.2
  name: "User authentication"
  intent: "Verify user identity"
  epistemic_state: "known"
```

```yaml
- type: under_decomposition
  node: A.2
  severity: major
  description: "'Verify user identity' too vague — what methods? What on failure? What tokens/sessions?"
  suggestion: "Add constraints (auth methods, session behavior, failure response) or decompose."

- type: regenerability
  node: A.2
  severity: major
  description: "Cannot implement from 'verify user identity' alone. Missing: protocol, storage, session, errors."
  suggestion: "Needs constraints or children before Generator can act."
```

## Good critique — projection leak via language-swap test

Node:
```yaml
- uid: DISC
  constraints:
    - "Output is Dict[str, FunctionRecord] keyed by 'schema.function_name'."
    - "Each FunctionRecord holds both raw locations and pre-parsed representations (ParsedFunction)."
```

```yaml
- type: projection_hints
  node: DISC
  severity: moderate
  description: "Uses Python types: 'Dict[str, FunctionRecord]', 'ParsedFunction'. Language-swap: meaningless in C++/Go. Product intent is 'keyed mapping of function records.'"
  suggestion: "Rewrite: 'Output is mapping keyed by qualified function name, each entry holds location + parsed representation from both sides.' Move Python types to PIG."
```

## Bad critique — not actionable

```yaml
# BAD — doesn't help fix anything
- type: intent_quality
  node: A.2
  severity: minor
  description: "Could be better."
```

Every critique must be specific enough to know exactly what to change.
