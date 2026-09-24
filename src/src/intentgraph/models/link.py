"""IntentLink (ilink) — a directed, valued relation between two intentnodes.

Implements the intentlink schema from VOCABULARY_AND_FORMALISM.md section 5.
Intentlinks state what must be true *between* nodes — data exchange, dependency,
coordination, constraint propagation, compatibility, etc.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from intentgraph._types import NonEmptyStr
from intentgraph.errors import ParseError


class IntentLink(BaseModel):
    """A directed, valued relation between two intentnodes.

    Unlike treearcs (structural refinement edges), intentlinks carry semantic
    payload: an intent sentence and optionally a shape (structured grounding).
    Intentlinks are orthogonal to the tree and refinable (parent link field).
    """

    model_config = ConfigDict(validate_assignment=True)

    # --- Required fields ---
    uid: NonEmptyStr
    src: NonEmptyStr
    dst: NonEmptyStr
    intent: NonEmptyStr

    # --- Optional fields ---
    shape: dict[str, Any] | None = None
    parent: str | None = None  # UID of parent link (link refinement)

    # ---- UID generation helpers ----

    @staticmethod
    def derive_uid(src: str, dst: str, tag: str | None = None) -> str:
        """Derive a canonical link UID from endpoints per the formalism PK scheme.

        Format: ``{src}_{dst}`` or ``{src}_{dst}#{tag}`` when multiple links
        exist between the same pair.
        """
        base = f"{src}_{dst}"
        return f"{base}#{tag}" if tag else base

    def to_serial_dict(self) -> dict:
        """Serialize to dict for persistence, excluding defaults."""
        return self.model_dump(exclude_defaults=True)

    @classmethod
    def from_serial_dict(cls, d: dict) -> IntentLink:
        """Deserialize from persistence dict, wrapping Pydantic errors."""
        from pydantic import ValidationError
        try:
            return cls.model_validate(d)
        except ValidationError as e:
            raise ParseError(f"Invalid link data for uid={d.get('uid', '?')}: {e}") from e


# --------------------------------------------------------------------------- #
#  InterIntentLink — link between graphs (Option A: qualified UID)            #
# --------------------------------------------------------------------------- #


class InterIntentLink(BaseModel):
    """A directed, valued relation between an intentnode in one graph and another.

    Endpoints are qualified as ``graph_id:node_uid`` (Option A). Stored in the
    graph that owns the link (convention: source graph). No refinement (parent);
    refinement remains intra-only per intentlink_spec.
    """

    model_config = ConfigDict(validate_assignment=True)

    # --- Required fields ---
    src: NonEmptyStr   # graph_id:node_uid
    dst: NonEmptyStr   # graph_id:node_uid
    intent: NonEmptyStr

    # --- Optional fields ---
    uid: str | None = None
    shape: dict[str, Any] | None = None

    @staticmethod
    def derive_uid(src: str, dst: str) -> str:
        """Derive a canonical UID for an inter intentlink from endpoints."""
        return f"{src}_{dst}"

    def to_serial_dict(self) -> dict:
        """Serialize to dict for persistence, excluding defaults."""
        return self.model_dump(exclude_defaults=True)

    @classmethod
    def from_serial_dict(cls, d: dict) -> InterIntentLink:
        """Deserialize from persistence dict, wrapping Pydantic errors."""
        from pydantic import ValidationError
        try:
            return cls.model_validate(d)
        except ValidationError as e:
            raise ParseError(
                f"Invalid inter link data for src={d.get('src', '?')}: {e}"
            ) from e
