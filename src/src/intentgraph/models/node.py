"""IntentNode (inode) — a unit of intent at some level of detail.

Implements the node schema from VOCABULARY_AND_FORMALISM.md section 4.
Fields follow the formalism exactly; structural fields (parent_uid, children_uids)
are managed by IntentGraph and excluded from user-facing serialization.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from intentgraph._types import NonEmptyStr
from intentgraph.errors import InvalidUIDError, ParseError


def validate_uid_format(uid: str, parent_uid: str | None, grandparent_uid: str | None = None) -> None:
    """Validate that UID follows IntentGraph UID conventions.

    UID Format Rules:
    - ROOT: Must be exactly "ROOT" (case-sensitive) and have no parent
    - L1 nodes (parent=ROOT): A single segment — one uppercase keyword (preferred) or one number
      Pattern: ^[A-Z][A-Z0-9_]*$  or  ^[0-9]+$
      Examples: DISCOVER, PARSE, ERRORS, LEXER_TOKENS, 1, 2
      Invalid: ERROR.HANDLER (multi-segment), discover (lowercase), _BAD (leading underscore)
      Note: numeric L1 is allowed but a keyword is strongly preferred
    - L2 nodes (parent=L1): Parent prefix + dot + either a keyword or a number
      - Numeric: {parent}.{number}  e.g. DISCOVER.1, ERRORS.3, 1.1
      - Semantic: {parent}.{KEYWORD}  e.g. ERRORS.HANDLER, API.CLIENT, LEXER.PARSER_INTERFACE
    - L3+ nodes: Parent prefix + dot + sequential numbers only
      Pattern: ^{parent_uid}.{number}(\\.{number})*$
      Examples: DISCOVER.1.1, ERRORS.HANDLER.2, 1.1.3
    - ProjectionIG L1: PIG-{semantic}-{component}
      Pattern: ^PIG-[A-Z_]+-[A-Z_.]+$
      Examples: PIG-PY-TYPES, PIG-DOC-STYLE

    Args:
        uid: The node UID to validate
        parent_uid: The parent node UID (None for root nodes)

    Raises:
        InvalidUIDError: If UID does not follow conventions
    """
    # Special case: ROOT node
    if uid == "ROOT":
        if parent_uid is not None:
            raise InvalidUIDError(
                f"Only the root node can have UID 'ROOT'. "
                f"Got ROOT with parent '{parent_uid}'."
            )
        return

    # All non-ROOT nodes must have a parent
    if parent_uid is None:
        raise InvalidUIDError(
            f"Non-root node '{uid}' must have a parent. "
            f"Only 'ROOT' can be a parentless node."
        )

    # L1 nodes (parent is ROOT)
    if parent_uid == "ROOT":
        # Check for PIG prefix (ProjectionIG L1 nodes)
        if uid.startswith("PIG-"):
            if not re.match(r'^PIG-[A-Z_]+-[A-Z_.]+$', uid):
                raise InvalidUIDError(
                    f"ProjectionIG L1 node UID must follow pattern PIG-{{SEMANTIC}}-{{COMPONENT}}: got '{uid}'. "
                    f"Examples: PIG-PY-TYPES, PIG-DOC-STYLE"
                )
            return

        # L1 must be a single segment — no dots allowed
        if "." in uid:
            raise InvalidUIDError(
                f"L1 node UID must be a single segment (no dots): got '{uid}'. "
                f"Use a keyword like ERRORS or a number like 1. "
                f"Multi-segment compound names (e.g. ERROR.HANDLER) belong at L2."
            )

        # Numeric single-segment L1 is allowed (though keyword is preferred)
        if re.match(r'^\d+$', uid):
            return

        # Keyword L1: uppercase letters, may include digits or underscores (no leading underscore)
        if not re.match(r'^[A-Z][A-Z0-9_]*$', uid):
            raise InvalidUIDError(
                f"L1 node UID must be an uppercase keyword with optional underscores "
                f"(e.g. ERRORS, API, LEXER_TOKENS) "
                f"or a number (e.g. 1, 2): got '{uid}'."
            )
        return

    # L2+ nodes: must start with parent prefix + dot
    if not uid.startswith(f"{parent_uid}."):
        raise InvalidUIDError(
            f"Child node UID must start with parent prefix: "
            f"expected '{parent_uid}.<keyword-or-number>', got '{uid}'"
        )

    # Extract suffix after parent prefix
    suffix = uid[len(parent_uid) + 1:]

    # A single uppercase keyword suffix (e.g. ERRORS.HANDLER, LEXER.PARSER_INTERFACE) is only
    # allowed when the parent is an L1 node — its grandparent must be ROOT.
    parent_is_l1 = grandparent_uid == "ROOT"
    if parent_is_l1 and re.match(r'^[A-Z][A-Z0-9_]*$', suffix):
        return

    # Otherwise suffix must be numeric segments (e.g., "1", "1.2", "1.2.3")
    if not re.match(r'^\d+(\.\d+)*$', suffix):
        raise InvalidUIDError(
            f"L2+ node UID suffix must be numeric (e.g. '{parent_uid}.1', '{parent_uid}.1.2')"
            + (f", or a single uppercase keyword with optional underscores when parent is L1 "
               f"(e.g. '{parent_uid}.KEYWORD', '{parent_uid}.PARSER_INTERFACE')"
               if parent_is_l1 else "")
            + f": got '{uid}'."
        )


class HistoryEntry(BaseModel):
    """Provenance log entry — who touched this node, when, and what they did.

    Convention: human names as-is ('remi', 'tom'); agents prefixed with
    'agent:' ('agent:extractor', 'agent:critic').
    """

    who: str
    date: str
    note: str


class IntentNode(BaseModel):
    """A node in the IntentGraph representing a unit of intent.

    An intentnode describes *what* a part of the system is meant to do and *why*,
    not *how* it is implemented.  Intentnodes exist at any level of the refinement
    hierarchy — from system-level goals to leaf-level behavioral atoms.

    Structural fields (parent_uid, children_uids) are managed exclusively by
    IntentGraph and are excluded from serialization.
    """

    model_config = ConfigDict(validate_assignment=True)

    # --- Required fields (formalism section 4) ---
    uid: NonEmptyStr
    name: NonEmptyStr
    intent: NonEmptyStr

    # --- Optional fields ---
    epistemic_state: str | None = None
    constraints: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    design_notes: str | None = None
    effort: str | None = None
    # Pointer strings following the grammar `path[::Symbol[.member]][ (lines X-Y)]`
    # (formalism section 4.2). One pointer per entry.
    impl_pointers: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)
    # Structured data store. Other fields reference into this dict via slash notation
    # (/key/subkey). Values are JSON/YAML-compatible. Reserved key: _epistemic (per-path
    # epistemic overrides). G1: every top-level key must be referenced. G2: values are data,
    # not prose. Omitted from serialization when absent or empty.
    data_registry: dict[str, Any] | None = None

    @field_validator("impl_pointers", mode="before")
    @classmethod
    def _coerce_impl_pointers(cls, v: Any) -> Any:
        # Legacy graphs stored impl_pointers as a single string (possibly
        # newline-separated). Coerce to the canonical list[str] form.
        if isinstance(v, str):
            return [line.strip() for line in v.splitlines() if line.strip()]
        if v is None:
            return []
        return v

    @field_serializer("data_registry", when_used="always")
    def _serialize_data_registry(self, v: dict[str, Any] | None) -> dict[str, Any] | None:
        return v if v else None

    # ---- Field-clearing support ----

    #: Fields that may be cleared via an unset operation, with the value that
    #: represents "absent" for each (lists reset to [], scalars to None).
    UNSETTABLE_FIELDS: ClassVar[dict[str, Any]] = {
        "epistemic_state": None,
        "constraints": [],
        "examples": [],
        "design_notes": None,
        "effort": None,
        "impl_pointers": [],
        "data_registry": None,
    }

    @classmethod
    def empty_value(cls, field: str) -> Any:
        """The 'absent' value for an unsettable field. Raises KeyError for others."""
        value = cls.UNSETTABLE_FIELDS[field]
        return list(value) if isinstance(value, list) else value

    # --- Structural fields (managed by IntentGraph, excluded from serialization) ---
    parent_uid: str | None = Field(default=None, exclude=True)
    children_uids: list[str] = Field(default_factory=list, exclude=True)

    # ---- Derived helpers ----

    @property
    def is_leaf(self) -> bool:
        """True if this node has no children (leaf of the refinement tree)."""
        return len(self.children_uids) == 0

    @property
    def is_root(self) -> bool:
        """True if this node has no parent (root of the refinement tree)."""
        return self.parent_uid is None

    def to_serial_dict(self) -> dict:
        """Serialize to dict for persistence, excluding structural fields and defaults."""
        d = self.model_dump(exclude_defaults=True)
        # field_serializer returns None for empty data_registry; drop it explicitly
        if "data_registry" in d and not d["data_registry"]:
            del d["data_registry"]
        return d

    @classmethod
    def from_serial_dict(cls, d: dict) -> IntentNode:
        """Deserialize from persistence dict, wrapping Pydantic errors."""
        from pydantic import ValidationError
        try:
            return cls.model_validate(d)
        except ValidationError as e:
            raise ParseError(f"Invalid node data for uid={d.get('uid', '?')}: {e}") from e
