"""Domain exceptions for the IntentGraph library.

Each exception maps to a specific invariant violation or invalid operation.
"""


class IntentGraphError(Exception):
    """Base exception for all IntentGraph errors."""


class InvariantViolation(IntentGraphError):
    """An operation would violate a structural invariant (T1–T5)."""


class TreeInvariantViolation(InvariantViolation):
    """T1 violation: treearcs must form a directed rooted tree."""


class LinkInvariantViolation(InvariantViolation):
    """T3 violation: ilink endpoints must exist and refinement rules must hold."""


class NodeNotFoundError(IntentGraphError):
    """Referenced node does not exist in the graph."""


class LinkNotFoundError(IntentGraphError):
    """Referenced ilink does not exist in the graph."""


class DuplicateNodeError(IntentGraphError):
    """A node with this uid already exists."""


class DuplicateLinkError(IntentGraphError):
    """A link with this uid already exists."""


class ParseError(IntentGraphError):
    """Failed to parse serialized input."""

    def __init__(self, message: str, line: int | None = None):
        self.line = line
        loc = f" (line {line})" if line is not None else ""
        super().__init__(f"{message}{loc}")


class ObsidianFormatError(IntentGraphError):
    """Raised when an Obsidian vault file has invalid or unsupported format.

    Attributes:
        path: Optional filesystem path of the offending file.
    """

    def __init__(self, message: str, path: str | None = None):
        self.path = path
        loc = f" ({path})" if path else ""
        super().__init__(f"{message}{loc}")


class InvalidUIDError(IntentGraphError):
    """Raised when a node UID does not follow the required format conventions."""


class ClosureViolation(IntentGraphError):
    """Raised when a LensConfig mutation would violate lens closure invariants.

    Closure invariants (Spec §6):
    - C3: Both endpoints of an intentlink must be in the lens before the link
      can be added. Adding a link whose endpoint is absent raises this error.
    """
