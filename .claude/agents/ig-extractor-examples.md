# Extractor — Few-Shot Examples

Reference examples. Read on demand when needed.

## Good extraction — intent, not code

**Code:**
```python
def retry_with_backoff(fn, max_retries=3, base_delay=1.0):
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(base_delay * (2 ** attempt))
```

**Good intentnode:**
```yaml
- uid: R.1
  name: "Retry with backoff"
  intent: "Ensure transient failures are tolerated by retrying the operation with exponentially increasing wait times."
  epistemic_state: "known"
  constraints:
    - "Maximum retry count is configurable (default 3)"
    - "Wait time doubles after each failure"
    - "Final failure is re-raised, not swallowed"
  impl_pointers: "src/utils/retry.py:retry_with_backoff"
```

## Bad extraction — code-shaped, not intent-shaped

```yaml
# BAD — this is HOW, not WHY
- uid: R.1
  name: "Retry loop"
  intent: "Loop from 0 to max_retries, call fn(), catch exceptions, sleep with exponential delay."
```

This is a paraphrase of the code, not an abstraction above it. The "blind generation test" fails: a developer reading only this node would reproduce the exact same code, not understand the intent behind retrying.
