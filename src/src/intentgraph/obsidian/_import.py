"""Import Obsidian vault folder -> IntentGraph.

Parses ``nodes/*.md``, ``edges.yaml``, and (optionally) ``viz/*.canvas``
back into an IntentGraph object.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from intentgraph.errors import ObsidianFormatError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.link import IntentLink
from intentgraph.models.node import HistoryEntry, IntentNode
from intentgraph.obsidian._format import uid_from_stem, unescape_literal_content


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def import_from_obsidian(vault_dir: str | Path) -> IntentGraph:
    """Read an Obsidian vault folder and reconstruct an IntentGraph.

    The vault must contain:
    - ``nodes/`` with ``.md`` files (YAML frontmatter + UP/DOWN/CONTAINS)
    - ``edges.yaml`` with intentlinks

    Parameters
    ----------
    vault_dir : str | Path
        Root directory of the Obsidian vault.

    Returns
    -------
    IntentGraph
        The reconstructed graph.

    Raises
    ------
    ObsidianFormatError
        If the vault structure is invalid or files cannot be parsed.
    """
    root = Path(vault_dir)
    nodes_dir = root / "nodes"
    edges_file = root / "edges.yaml"

    if not nodes_dir.is_dir():
        raise ObsidianFormatError(f"nodes/ directory not found", path=str(nodes_dir))

    # 1. Parse all node .md files
    raw_nodes: dict[str, dict[str, Any]] = {}
    contains_map: dict[str, list[str]] = {}  # parent_uid -> [child_uids]

    for md_file in sorted(nodes_dir.glob("*.md")):
        parsed = _parse_node_file(md_file)
        if parsed is not None:
            uid = parsed["uid"]
            raw_nodes[uid] = parsed
            if parsed["children_uids"]:
                contains_map[uid] = parsed["children_uids"]

    if not raw_nodes:
        raise ObsidianFormatError("No valid node files found", path=str(nodes_dir))

    # 2. Build IntentGraph
    graph = IntentGraph(meta={})

    # Create all nodes (unattached)
    for uid, data in raw_nodes.items():
        history_entries = [
            HistoryEntry(**_coerce_history_dict(h)) if isinstance(h, dict) else h
            for h in (data.get("history") or [])
        ]
        node = IntentNode(
            uid=uid,
            name=data["name"],
            intent=data.get("intent", ""),
            epistemic_state=data.get("epistemic_state"),
            constraints=data.get("constraints") or [],
            examples=data.get("examples") or [],
            design_notes=data.get("design_notes"),
            effort=data.get("effort"),
            history=history_entries,
            impl_pointers=data.get("impl_pointers"),
            data_registry=data.get("data_registry") or None,
        )
        graph._nodes[uid] = node

    # Rebuild the tree. Prefer the authoritative treearc records in edges.yaml;
    # fall back to CONTAINS scraping only for legacy vaults with no treearcs
    # (this keeps the tree independent of the display nav links, so
    # --nav-links minimal|none round-trips losslessly).
    treearcs: list[tuple[str, str]] = []
    if edges_file.is_file():
        treearcs = _parse_treearcs_yaml(edges_file)

    if treearcs:
        tree_pairs = treearcs
    else:
        tree_pairs = [
            (parent_uid, child_uid)
            for parent_uid, child_uids in contains_map.items()
            for child_uid in child_uids
        ]

    for parent_uid, child_uid in tree_pairs:
        parent_node = graph._nodes.get(parent_uid)
        child_node = graph._nodes.get(child_uid)
        if parent_node is None or child_node is None:
            continue
        child_node.parent_uid = parent_uid
        if child_uid not in parent_node.children_uids:
            parent_node.children_uids.append(child_uid)

    # 3. Parse intentlinks from edges.yaml
    if edges_file.is_file():
        links = _parse_edges_yaml(edges_file)
        for link in links:
            graph._links[link.uid] = link

    return graph


# ------------------------------------------------------------------ #
#  Node markdown parsing                                             #
# ------------------------------------------------------------------ #

def _parse_node_file(file_path: Path) -> dict[str, Any] | None:
    """Parse a single Obsidian node ``.md`` file.

    Returns a dict with all extracted fields, or None on failure.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # uid and name from filename
    stem = file_path.stem
    uid = uid_from_stem(stem)
    name = stem.split(" ", 1)[1] if " " in stem else ""

    # Extract frontmatter
    frontmatter = _extract_frontmatter(content)
    if frontmatter is None:
        return None

    # Extract CONTAINS children from body
    children_uids = _extract_contains(content)

    # Unescape literal block placeholders ( - - -  -> ---,  . . .  -> ...)
    constraints = [unescape_literal_content(str(c)) for c in (frontmatter.get("constraints") or [])]
    examples = [unescape_literal_content(str(e)) for e in (frontmatter.get("examples") or [])]
    history_raw = frontmatter.get("history") or []
    history = []
    for h in history_raw:
        if isinstance(h, dict):
            d = _coerce_history_dict(h)
            d["note"] = unescape_literal_content(str(d.get("note", "")))
            history.append(d)
        else:
            history.append(h)

    return {
        "uid": uid,
        "name": name,
        "intent": _strip_str(frontmatter.get("intent")),
        "epistemic_state": _strip_str(frontmatter.get("epistemic_state")),
        "constraints": constraints,
        "design_notes": _strip_str(frontmatter.get("design_notes")),
        "examples": examples,
        "effort": frontmatter.get("effort"),
        "history": history,
        # list[str] per formalism §4.2; legacy string values coerced by the model
        "impl_pointers": frontmatter.get("impl_pointers") or [],
        "data_registry": frontmatter.get("data_registry") or None,
        "children_uids": children_uids,
    }


def _extract_frontmatter(content: str) -> dict[str, Any] | None:
    """Extract and parse YAML frontmatter from ``---`` delimited markdown."""
    if not content.startswith("---"):
        return None
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        fm = yaml.safe_load(parts[1])
        return fm if isinstance(fm, dict) else None
    except yaml.YAMLError:
        return None


def _extract_contains(content: str) -> list[str]:
    """Extract child UIDs from the ``CONTAINS:`` line in the body.

    Format: ``CONTAINS: [[uid1 name1]]  |  [[uid2 name2]]``
    """
    # Look for CONTAINS line after frontmatter
    match = re.search(r"^CONTAINS:\s*(.+)$", content, re.MULTILINE)
    if not match:
        return []

    contains_line = match.group(1)
    # Extract all wiki-link targets: [[some text here]]
    links = re.findall(r"\[\[([^\]]+)\]\]", contains_line)
    uids = [uid_from_stem(link.split("|")[0].strip()) for link in links]
    return uids


def _strip_str(val: Any) -> str | None:
    """Strip whitespace from a string value, returning None for empty/None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _coerce_history_dict(h: dict[str, Any]) -> dict[str, Any]:
    """Coerce history entry values to strings.

    PyYAML's safe_load parses bare date-like values (``2026-01-15``) as
    ``datetime.date`` objects.  HistoryEntry expects all-string fields.
    """
    return {k: str(v) for k, v in h.items()}


# ------------------------------------------------------------------ #
#  edges.yaml parsing                                                #
# ------------------------------------------------------------------ #

def _parse_treearcs_yaml(file_path: Path) -> list[tuple[str, str]]:
    """Parse ``type: treearc`` entries from ``edges.yaml`` into (parent, child).

    Treearcs are the authoritative tree structure in the vault. Returns an empty
    list for legacy vaults whose edges.yaml predates treearc entries (import then
    falls back to CONTAINS scraping).
    """
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(data, list):
        return []
    arcs: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict) or item.get("type") != "treearc":
            continue
        parent = item.get("from") or item.get("src")
        child = item.get("to") or item.get("dst")
        if parent and child:
            arcs.append((parent, child))
    return arcs


def _parse_edges_yaml(file_path: Path) -> list[IntentLink]:
    """Parse ``edges.yaml`` into a list of IntentLink objects.

    Only ``type: intentlink`` entries produce links; ``treearc`` entries (which
    carry no ``intent``) are skipped here and handled by ``_parse_treearcs_yaml``.
    If an explicit `uid` field is present in the entry, it is preferred;
    otherwise derives the uid from src/dst following the standard logic.
    """
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []

    if not isinstance(data, list):
        return []

    links: list[IntentLink] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        src = item.get("from") or item.get("src")
        dst = item.get("to") or item.get("dst")
        intent = item.get("intent", "")
        if not src or not dst or not intent:
            continue

        # Prefer explicit uid when present and non-empty
        explicit_uid = item.get("uid")
        if explicit_uid and isinstance(explicit_uid, str) and explicit_uid.strip():
            link_uid = explicit_uid.strip()
        else:
            # Derive uid (same logic as IntentLink.derive_uid)
            link_uid = IntentLink.derive_uid(src, dst)
            # Handle potential duplicates (same src/dst pair)
            if any(l.uid == link_uid for l in links):
                # Use parent or index as tag for disambiguation
                tag = item.get("parent") or str(len(links))
                link_uid = IntentLink.derive_uid(src, dst, tag)

        link = IntentLink(
            uid=link_uid,
            src=src,
            dst=dst,
            intent=intent,
            shape=item.get("shape"),
            parent=item.get("parent"),
        )
        links.append(link)

    return links
