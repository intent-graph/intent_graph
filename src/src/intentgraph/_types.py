"""Reusable constrained types for the IntentGraph library.

Makes constraints visible in the type, not hidden in validator methods.
The type itself expresses the invariant (KB 0.4: Making Invalid States Unrepresentable).
"""

from typing import Annotated

from pydantic import AfterValidator


def _non_empty_str(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("must be a non-empty string")
    return v


NonEmptyStr = Annotated[str, AfterValidator(_non_empty_str)]
"""A string that must contain at least one non-whitespace character."""
