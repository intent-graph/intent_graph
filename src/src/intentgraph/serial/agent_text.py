"""Agent text format — working-view serialization for LLM agent I/O.

Provides a YAML-based text format that is:
- **Human-readable**: an engineer can scan and understand it.
- **Round-trippable**: serialize -> parse -> serialize = identical content.
- **LLM-parseable**: clear structure, standard YAML, no ambiguity.

The format serializes a working view (§2 of SERIALIZATION_FORMAT.md): the
nodes in the view with their fields, the projected intentlinks visible at
that view, and metadata about collapsed children (for context without
clutter). The top-level header key is ``view:``; the legacy ``frontier:``
key is still accepted on read.

Edit operations
---------------
The parser does NOT produce a new view directly.  Instead it produces a list
of structured edit operations (``NodeCreate``, ``NodeUpdate``, ``NodeDelete``,
``LinkCreate``, ``LinkDelete``) that can be validated by the IntentGraph before
applying.  This separation enforces the invariant gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

from intentgraph.errors import ParseError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.view import View
from intentgraph.ops.projection import project_links


# ================================================================== #
#  Helper functions                                                    #
# ================================================================== #


def _infer_parent_from_uid(uid: str) -> str | None:
    """Infer parent UID from hierarchical UID structure.

    Examples:
        ROOT.1 -> ROOT
        ROOT.1.2 -> ROOT.1
        PIG-MOD.LAYOUT -> PIG-MOD
        ROOT -> None (no parent)
    """
    if "." not in uid:
        return None
    return uid.rsplit(".", 1)[0]


def _validate_constraints_format(node_dict: dict, uid: str) -> None:
    """Validate that constraints field is list[str], not dict or other types."""
    if "constraints" not in node_dict:
        return

    constraints = node_dict["constraints"]
    if not isinstance(constraints, list):
        raise ParseError(
            f"Node '{uid}': constraints must be list[str], got {type(constraints).__name__}. "
            f"If you have key-value patterns, write them as single strings."
        )

    for i, c in enumerate(constraints):
        if not isinstance(c, str):
            raise ParseError(
                f"Node '{uid}': constraints[{i}] must be a string, got {type(c).__name__}"
            )


# ================================================================== #
#  Edit operations — structured diffs produced by the parser          #
# ================================================================== #


@dataclass
class NodeCreate:
    """Propose creating a new node."""
    uid: str
    name: str
    intent: str
    parent: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeUpdate:
    """Propose updating fields on an existing node."""
    uid: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeDelete:
    """Propose deleting a node."""
    uid: str


@dataclass
class LinkCreate:
    """Propose creating a new intentlink."""
    src: str
    dst: str
    intent: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkUpdate:
    """Propose updating fields on an existing intentlink."""
    uid: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkDelete:
    """Propose deleting an intentlink."""
    uid: str


EditOp = NodeCreate | NodeUpdate | NodeDelete | LinkCreate | LinkUpdate | LinkDelete


# ================================================================== #
#  Serializer: view -> agent text                                     #
# ================================================================== #


def view_to_text(
    view: View,
    *,
    lean_node_uids: set[str] | frozenset[str] | None = None,
) -> str:
    """Serialize a working view to the agent text format (§2).

    The output is valid YAML with the following structure::

        view:
          name: "..."
          scope: "..."        # optional

        nodes:
          - uid: E.1.1
            name: "Extract credentials"
            intent: "Parse and validate auth credentials"
            epistemic_state: "known"
            constraints:
              - "Must support OAuth2"
            collapsed_children: [E.1.1.1, E.1.1.2]

        intentlinks:
          - uid: E.1.1_E.1.2
            src: E.1.1
            dst: E.1.2
            intent: "Passes credentials for token gen"
            lifted: false
    Parameters
    ----------
    lean_node_uids:
        Optional subset of view node UIDs to serialize in lean form.
        Lean form includes only: ``uid``, ``name``, ``intent``,
        ``epistemic_state`` (if present). Full form includes all currently
        supported optional fields plus ``collapsed_children``.
        Defaults to ``view.lean_uids``.
    """
    graph = view.graph
    lean_uids = set(lean_node_uids if lean_node_uids is not None else view.lean_uids)

    # ---- Header ----
    header: dict[str, Any] = {"name": view.name}
    if view.scope:
        header["scope"] = view.scope

    # ---- Nodes ----
    node_dicts: list[dict[str, Any]] = []
    for uid in sorted(view.node_uids):
        node = graph.get_node(uid)
        d: dict[str, Any] = {
            "uid": node.uid,
            "name": node.name,
            "intent": node.intent,
        }
        if node.epistemic_state is not None:
            d["epistemic_state"] = node.epistemic_state

        is_lean = uid in lean_uids
        if not is_lean:
            if node.constraints:
                d["constraints"] = list(node.constraints)
            if node.examples:
                d["examples"] = list(node.examples)
            if node.design_notes is not None:
                d["design_notes"] = node.design_notes
            if node.effort is not None:
                d["effort"] = node.effort
            if node.impl_pointers:
                d["impl_pointers"] = list(node.impl_pointers)
            if node.history:
                d["history"] = [
                    {"who": h.who, "date": h.date, "note": h.note}
                    for h in node.history
                ]
            if node.data_registry:
                d["data_registry"] = node.data_registry

            # Collapsed children — context for the agent
            children = graph.children(uid)
            if children:
                d["collapsed_children"] = [c.uid for c in children]

        node_dicts.append(d)

    # ---- Intentlinks (projected) ----
    projected = project_links(view)
    link_dicts: list[dict[str, Any]] = []
    for pl in projected:
        ld: dict[str, Any] = {
            "uid": pl.original.uid,
            "src": pl.display_src,
            "dst": pl.display_dst,
            "intent": pl.original.intent,
        }
        if pl.is_lifted:
            ld["lifted"] = True
            ld["original_src"] = pl.original.src
            ld["original_dst"] = pl.original.dst
        link_dicts.append(ld)

    # ---- Assemble ----
    doc: dict[str, Any] = {
        "view": header,
        "nodes": node_dicts,
        "intentlinks": link_dicts,
    }

    return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ================================================================== #
#  Parser: agent text -> edit operations                              #
# ================================================================== #


def text_to_edits(
    text: str,
    graph: IntentGraph,
    auto_parent: bool = False,
) -> list[EditOp]:
    """Parse agent text and produce structured edit operations.

    The parser compares the text content against the current graph state:
    - Nodes in the text that don't exist in the graph -> ``NodeCreate``
    - Nodes in the text with changed fields -> ``NodeUpdate``
    - Nodes marked with ``_delete: true`` -> ``NodeDelete``
    - Links in the text that don't exist -> ``LinkCreate``
    - Links marked with ``_delete: true`` -> ``LinkDelete``

    Args:
        text: Agent text YAML (§2 view or §5 diff format). The §2 header key
            is ``view:``; the legacy ``frontier:`` key is also accepted
            (both are ignored by the parser — only ``nodes``/``intentlinks``
            drive edits).
        graph: Current graph state
        auto_parent: If True, infer parent from UID hierarchy when missing

    Raises ``ParseError`` on malformed input.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e

    if not isinstance(doc, dict):
        raise ParseError("Expected a YAML mapping at the top level")

    edits: list[EditOp] = []

    # ---- Parse nodes ----
    nodes_list = doc.get("nodes", [])
    if not isinstance(nodes_list, list):
        raise ParseError("'nodes' must be a list")

    for i, node_dict in enumerate(nodes_list):
        if not isinstance(node_dict, dict):
            raise ParseError(f"Node entry {i} must be a mapping")

        uid = node_dict.get("uid")
        if not uid or not isinstance(uid, str):
            raise ParseError(f"Node entry {i}: 'uid' is required and must be a string")

        # Check for delete marker
        if node_dict.get("_delete"):
            edits.append(NodeDelete(uid=uid))
            continue

        # Validate constraints format before parsing
        _validate_constraints_format(node_dict, uid)

        # Gather content fields (exclude structural/metadata)
        content_fields = _extract_node_fields(node_dict)

        existing = graph.get_node_or_none(uid)
        if existing is None:
            # New node
            name = node_dict.get("name")
            intent = node_dict.get("intent")
            if not name or not intent:
                raise ParseError(
                    f"Node '{uid}': new nodes require 'name' and 'intent'"
                )
            parent_uid = node_dict.get("parent")

            # Auto-infer parent from UID hierarchy if enabled and missing
            if not parent_uid and auto_parent:
                parent_uid = _infer_parent_from_uid(uid)

            # Exclude name/intent from fields — they are explicit NodeCreate params
            extra = {k: v for k, v in content_fields.items() if k not in ("name", "intent")}
            edits.append(NodeCreate(
                uid=uid,
                name=name,
                intent=intent,
                parent=parent_uid,
                fields=extra,
            ))
        else:
            # Existing node — check for changed fields
            changed = _diff_node_fields(existing, content_fields)
            if changed:
                edits.append(NodeUpdate(uid=uid, fields=changed))

    # ---- Parse links ----
    links_list = doc.get("intentlinks", [])
    if not isinstance(links_list, list):
        raise ParseError("'intentlinks' must be a list")

    for i, link_dict in enumerate(links_list):
        if not isinstance(link_dict, dict):
            raise ParseError(f"Link entry {i} must be a mapping")

        # Check for delete marker
        link_uid = link_dict.get("uid")
        if link_dict.get("_delete"):
            if not link_uid:
                raise ParseError(f"Link entry {i}: '_delete' requires 'uid'")
            edits.append(LinkDelete(uid=link_uid))
            continue

        src = link_dict.get("src")
        dst = link_dict.get("dst")
        intent = link_dict.get("intent")

        if not src or not dst or not intent:
            raise ParseError(f"Link entry {i}: 'src', 'dst', and 'intent' are required")

        # Skip lifted links (they are projections, not canonical)
        if link_dict.get("lifted"):
            continue

        # Check if link exists
        if link_uid and link_uid in graph.links:
            # Existing link — check for changed content fields (mirrors the
            # node path's _diff_node_fields -> NodeUpdate handling above).
            existing_link = graph.get_link(link_uid)
            changed = _diff_link_fields(existing_link, link_dict)
            if changed:
                edits.append(LinkUpdate(uid=link_uid, fields=changed))
            continue

        extra_fields: dict[str, Any] = {}
        if link_dict.get("shape"):
            extra_fields["shape"] = link_dict["shape"]

        edits.append(LinkCreate(
            src=src,
            dst=dst,
            intent=intent,
            fields=extra_fields,
        ))

    return edits


# ================================================================== #
#  Diff parser: diff text -> edit operations                          #
# ================================================================== #


_DIFF_SKIP_FIELDS = {"uid", "_delete", "_new", "_prev", "collapsed_children",
                     "parent_uid", "children_uids", "parent", "lifted",
                     "original_src", "original_dst"}

_LINK_CONTENT_FIELDS = {"intent", "shape", "parent"}


def diff_to_edits(
    text: str,
    graph: IntentGraph,
) -> list[EditOp]:
    """Parse a diff-format YAML and produce structured edit operations.

    A diff is an agent text document (§2 of SERIALIZATION_FORMAT) that
    contains only changed entities, with ``diff_meta`` replacing the
    ``view`` header.  Change markers:

    - ``_new: true`` — create this entity (node or link).
    - ``_delete: true`` — delete this entity.
    - (neither) — update only the fields present.
    - ``_prev`` — optional previous-value dict, ignored by the parser.
    - ``parent`` on new nodes — treearc target (required for node creation).

    Raises ``ParseError`` on malformed input.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ParseError(f"Invalid YAML: {e}") from e

    if not isinstance(doc, dict):
        raise ParseError("Expected a YAML mapping at the top level")

    if "diff_meta" not in doc:
        raise ParseError("Diff format requires a 'diff_meta' key at top level")

    edits: list[EditOp] = []

    # ---- Parse nodes ----
    nodes_list = doc.get("nodes", [])
    if not isinstance(nodes_list, list):
        raise ParseError("'nodes' must be a list")

    for i, node_dict in enumerate(nodes_list):
        if not isinstance(node_dict, dict):
            raise ParseError(f"Node entry {i} must be a mapping")

        uid = node_dict.get("uid")
        if not uid or not isinstance(uid, str):
            raise ParseError(f"Node entry {i}: 'uid' is required and must be a string")

        if node_dict.get("_delete"):
            edits.append(NodeDelete(uid=uid))
            continue

        if node_dict.get("_new"):
            name = node_dict.get("name")
            intent = node_dict.get("intent")
            if not name or not intent:
                raise ParseError(
                    f"Node '{uid}': new nodes require 'name' and 'intent'"
                )
            parent_uid = node_dict.get("parent")
            extra = {
                k: v for k, v in node_dict.items()
                if k in _NODE_CONTENT_FIELDS and k not in ("name", "intent") and v is not None
            }
            edits.append(NodeCreate(uid=uid, name=name, intent=intent,
                                    parent=parent_uid, fields=extra))
            continue

        # Update — only changed fields
        content_fields = {
            k: v for k, v in node_dict.items()
            if k in _NODE_CONTENT_FIELDS and v is not None
        }
        if content_fields:
            edits.append(NodeUpdate(uid=uid, fields=content_fields))

    # ---- Parse links ----
    links_list = doc.get("intentlinks", [])
    if not isinstance(links_list, list):
        raise ParseError("'intentlinks' must be a list")

    for i, link_dict in enumerate(links_list):
        if not isinstance(link_dict, dict):
            raise ParseError(f"Link entry {i} must be a mapping")

        link_uid = link_dict.get("uid")

        if link_dict.get("_delete"):
            if not link_uid:
                raise ParseError(f"Link entry {i}: '_delete' requires 'uid'")
            edits.append(LinkDelete(uid=link_uid))
            continue

        if link_dict.get("lifted"):
            continue

        if link_dict.get("_new"):
            src = link_dict.get("src")
            dst = link_dict.get("dst")
            intent = link_dict.get("intent")
            if not src or not dst or not intent:
                raise ParseError(f"Link entry {i}: new links require 'src', 'dst', and 'intent'")
            extra_fields: dict[str, Any] = {}
            if link_dict.get("shape"):
                extra_fields["shape"] = link_dict["shape"]
            edits.append(LinkCreate(src=src, dst=dst, intent=intent, fields=extra_fields))
            continue

        # Update — only changed fields
        if not link_uid:
            raise ParseError(f"Link entry {i}: link updates require 'uid'")
        changed = {
            k: v for k, v in link_dict.items()
            if k in _LINK_CONTENT_FIELDS and v is not None
        }
        if changed:
            edits.append(LinkUpdate(uid=link_uid, fields=changed))

    return edits


# ================================================================== #
#  Auto-detection dispatcher                                          #
# ================================================================== #


def parse_agent_output(
    text: str,
    graph: IntentGraph,
) -> list[EditOp]:
    """Parse agent output, auto-detecting full view vs diff format.

    Routes to ``text_to_edits`` (full view, §2 — ``view:`` or legacy
    ``frontier:`` header) or ``diff_to_edits`` (diff format, §5) based on
    the presence of a ``diff_meta`` key.
    """
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError:
        raise ParseError("Invalid YAML — cannot auto-detect format")

    if isinstance(doc, dict) and "diff_meta" in doc:
        return diff_to_edits(text, graph)
    return text_to_edits(text, graph)


# ================================================================== #
#  Apply edits to graph (convenience)                                 #
# ================================================================== #


def apply_edits(
    graph: IntentGraph,
    edits: list[EditOp],
    *,
    agent_role: str | None = None,
) -> list[str]:
    """Apply a list of edit operations to the graph.

    Returns a list of human-readable descriptions of what was applied.
    Raises on the first invariant violation (fail-fast).

    If *agent_role* is provided (e.g. ``"extractor"``, ``"elicitor"``),
    a ``HistoryEntry`` is automatically appended to every created or
    updated node with ``who="agent:{role}"`` and today's date.
    """
    from intentgraph.models.node import HistoryEntry

    log: list[str] = []
    today = date.today().isoformat() if agent_role else None

    for edit in edits:
        if isinstance(edit, NodeCreate):
            # Inject history entry for agent provenance
            if agent_role:
                h = {"who": f"agent:{agent_role}", "date": today,
                     "note": f"Created node via {agent_role} agent."}
                hist = edit.fields.get("history", [])
                hist.append(h)
                edit.fields["history"] = hist
            graph.add_node(
                uid=edit.uid,
                name=edit.name,
                intent=edit.intent,
                **edit.fields,
            )
            # Attach to parent (treearc) if specified
            if edit.parent:
                graph.attach(edit.parent, edit.uid)
            log.append(f"Created node '{edit.uid}'")

        elif isinstance(edit, NodeUpdate):
            graph.update_node(edit.uid, **edit.fields)
            # Append history entry after update
            if agent_role:
                node = graph.get_node(edit.uid)
                node.history.append(HistoryEntry(
                    who=f"agent:{agent_role}",
                    date=today,
                    note=f"Updated {list(edit.fields.keys())} via {agent_role} agent.",
                ))
            log.append(f"Updated node '{edit.uid}': {list(edit.fields.keys())}")

        elif isinstance(edit, NodeDelete):
            graph.remove_node(edit.uid, cascade=True)
            log.append(f"Deleted node '{edit.uid}'")

        elif isinstance(edit, LinkCreate):
            graph.add_link(
                src=edit.src,
                dst=edit.dst,
                intent=edit.intent,
                **edit.fields,
            )
            log.append(f"Created link '{edit.src}' -> '{edit.dst}'")

        elif isinstance(edit, LinkUpdate):
            graph.update_link(edit.uid, **edit.fields)
            log.append(f"Updated link '{edit.uid}': {list(edit.fields.keys())}")

        elif isinstance(edit, LinkDelete):
            graph.remove_link(edit.uid)
            log.append(f"Deleted link '{edit.uid}'")

    return log


# ================================================================== #
#  Internal helpers                                                   #
# ================================================================== #


_NODE_CONTENT_FIELDS = {
    "name", "intent", "epistemic_state", "constraints",
    "examples", "design_notes", "effort", "impl_pointers",
    "history", "data_registry",
}

_NODE_SKIP_FIELDS = {
    "uid", "collapsed_children", "_delete",
    "parent_uid", "children_uids",
}


def _extract_node_fields(d: dict) -> dict[str, Any]:
    """Extract content fields from a node dict (exclude uid, structural, metadata)."""
    return {
        k: v for k, v in d.items()
        if k in _NODE_CONTENT_FIELDS and v is not None
    }


def _diff_link_fields(existing_link: Any, link_dict: dict[str, Any]) -> dict[str, Any]:
    """Return only content fields that differ from the existing link.

    Compares the same content fields the §5 diff parser recognizes
    (``_LINK_CONTENT_FIELDS``: intent, shape, parent) so an existing
    canonical link's changed fields produce a ``LinkUpdate`` instead of
    being silently dropped.
    """
    changed: dict[str, Any] = {}
    for field_name in _LINK_CONTENT_FIELDS:
        if field_name not in link_dict:
            continue
        new_value = link_dict[field_name]
        if new_value is None:
            continue
        old_value = getattr(existing_link, field_name, None)
        if old_value != new_value:
            changed[field_name] = new_value
    return changed


def _diff_node_fields(existing_node: Any, new_fields: dict[str, Any]) -> dict[str, Any]:
    """Return only fields that differ from the existing node."""
    changed: dict[str, Any] = {}
    for field_name, new_value in new_fields.items():
        old_value = getattr(existing_node, field_name, None)
        # History: compare as list of dicts for round-trip stability
        if field_name == "history":
            old_as_dicts = [
                {"who": h.who, "date": h.date, "note": h.note}
                for h in (old_value or [])
            ]
            if old_as_dicts != new_value:
                changed[field_name] = new_value
        elif old_value != new_value:
            changed[field_name] = new_value
    return changed
