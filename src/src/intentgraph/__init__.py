"""IntentGraph core library — data model, lens/view operations, agent serialization.

Implements the IntentGraph formalism (Phase 0) as a standalone Python package
with enforced invariants (T1-T5), working views, ilink projection, and
round-trip serialization for both persistence and agent I/O.

Usage::

    from intentgraph import IntentGraph, View

    g = IntentGraph(meta={"name": "my system"})
    g.add_node("ROOT", "Root", "Top-level system goal")
    g.add_node_under("A", "Module A", "Handles A", parent_uid="ROOT")
"""

__version__ = "0.1.0"

# Core models — the primary public API
from intentgraph.models.node import HistoryEntry, IntentNode
from intentgraph.models.link import IntentLink, InterIntentLink
from intentgraph.models.graph import IntentGraph
from intentgraph.models.view import View

# Validation (inter intentlinks when manifest available)
from intentgraph.validation import validate_inter_intentlinks

# Errors — domain exceptions
from intentgraph.errors import (
    IntentGraphError,
    InvariantViolation,
    TreeInvariantViolation,
    LinkInvariantViolation,
    NodeNotFoundError,
    LinkNotFoundError,
    DuplicateNodeError,
    DuplicateLinkError,
    ParseError,
)

__all__ = [
    # Models
    "IntentGraph",
    "IntentNode",
    "IntentLink",
    "InterIntentLink",
    "View",
    "HistoryEntry",
    # Errors
    "IntentGraphError",
    "InvariantViolation",
    "TreeInvariantViolation",
    "LinkInvariantViolation",
    "NodeNotFoundError",
    "LinkNotFoundError",
    "DuplicateNodeError",
    "DuplicateLinkError",
    "ParseError",
    # Validation
    "validate_inter_intentlinks",
]
