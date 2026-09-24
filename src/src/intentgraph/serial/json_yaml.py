"""JSON / YAML round-trip serialization for IntentGraph.

The serialized dict matches the formalism schema:
``{meta, nodes: [...], treearcs: [{parent, child}, ...], intentlinks: [...]}``

Treearcs are **not** stored on nodes in the serialized form; they are emitted
as an explicit list and rebuilt into adjacency on deserialization.

A legacy top-level ``frontiers:`` key (removed display-frontier concept) is
tolerated on read: it is ignored, never stored, and never re-emitted.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

from intentgraph.errors import TreeInvariantViolation
from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens_config import LensConfig
from intentgraph.models.link import IntentLink, InterIntentLink
from intentgraph.models.node import IntentNode


# ------------------------------------------------------------------ #
#  IntentGraph → dict                                                 #
# ------------------------------------------------------------------ #

def graph_to_dict(graph: IntentGraph) -> dict[str, Any]:
    """Serialize an IntentGraph to a plain dict (formalism schema).

    Treearcs are extracted from the adjacency structure and emitted as
    ``[{parent: str, child: str}, ...]``.
    """
    # Nodes — serialized in breadth-first order (root, then L1, then L2, …)
    nodes = [node.to_serial_dict() for node in graph.iter_nodes_bfs()]

    # Treearcs — extracted from adjacency in same BFS order for consistency
    treearcs: list[dict[str, str]] = []
    for node in graph.iter_nodes_bfs():
        for child_uid in node.children_uids:
            treearcs.append({"parent": node.uid, "child": child_uid})

    # Intentlinks (intra)
    intentlinks = [link.to_serial_dict() for link in graph.iter_links()]

    # Inter intentlinks (Option A: qualified UID)
    inter_intentlinks = [link.to_serial_dict() for link in graph.iter_inter_links()]

    # Strip private/runtime-only keys (`_`-prefixed) from meta before serializing.
    # These hold live runtime objects; without this they leak as
    # !!python/object tags into YAML and crash json.dumps with TypeError.
    clean_meta = {k: v for k, v in graph.meta.items() if not k.startswith("_")}

    out: dict[str, Any] = {
        "meta": clean_meta,
        "nodes": nodes,
        "treearcs": treearcs,
        "intentlinks": intentlinks,
    }
    if inter_intentlinks:
        out["inter_intentlinks"] = inter_intentlinks

    # Serialize internal lenses (Spec §5.1, §11).
    # Omit the key entirely when empty to keep backward-compatible wire format.
    if graph.lenses:
        lenses_dict: dict[str, Any] = {}
        for lens_name, lens_cfg in graph.lenses.items():
            # Exclude defaults so the serialized form is compact.
            # Spec §4: empty target_uids, empty intentlinks, null description
            # are omitted.
            raw = lens_cfg.model_dump(exclude_none=True)
            # Drop empty lists to stay tidy (serialization format note §4)
            if not raw.get("target_uids"):
                raw.pop("target_uids", None)
            if not raw.get("intentlinks"):
                raw.pop("intentlinks", None)
            lenses_dict[lens_name] = raw
        out["lenses"] = lenses_dict

    return out


# ------------------------------------------------------------------ #
#  dict → IntentGraph                                                 #
# ------------------------------------------------------------------ #

def dict_to_graph(d: dict[str, Any]) -> IntentGraph:
    """Deserialize a plain dict (formalism schema) into an IntentGraph.

    Rebuilds adjacency from the treearc list.
    """
    graph = IntentGraph(meta=d.get("meta") or {})

    # 1. Create all nodes (unattached)
    for node_dict in d.get("nodes", []):
        node = IntentNode.from_serial_dict(node_dict)
        graph._nodes[node.uid] = node

    # 2. Rebuild treearc adjacency
    for tarc in d.get("treearcs", []):
        parent_uid = tarc["parent"]
        child_uid = tarc["child"]
        if parent_uid in graph._nodes and child_uid in graph._nodes:
            parent_node = graph._nodes[parent_uid]
            child_node = graph._nodes[child_uid]
            child_node.parent_uid = parent_uid
            if child_uid not in parent_node.children_uids:
                parent_node.children_uids.append(child_uid)

    # 3. Recreate intentlinks (intra)
    for link_dict in d.get("intentlinks", []):
        link = IntentLink.from_serial_dict(link_dict)
        graph._links[link.uid] = link

    # 3b. Recreate inter intentlinks
    for link_dict in d.get("inter_intentlinks", []):
        link = InterIntentLink.from_serial_dict(link_dict)
        key = link.uid or InterIntentLink.derive_uid(link.src, link.dst)
        link.uid = key  # ensure round-trip preserves key
        graph._inter_links[key] = link

    # 3c. Deserialize internal lenses (Spec §5.1, §11).
    # Missing key → empty dict (backward-compatible; existing IGs have no lenses).
    for lens_name, lens_raw in d.get("lenses", {}).items():
        # Ensure the name field is set (may be absent if the serialized form
        # omitted it, but the spec says it's required; fill from the dict key).
        if isinstance(lens_raw, dict) and "name" not in lens_raw:
            lens_raw = dict(lens_raw, name=lens_name)
        lens_cfg = LensConfig.model_validate(lens_raw)
        graph.lenses[lens_name] = lens_cfg

    # A legacy top-level `frontiers:` key (removed display-frontier concept)
    # is deliberately ignored here: tolerant read, never stored, never
    # re-emitted.

    return graph


# ------------------------------------------------------------------ #
#  JSON helpers                                                       #
# ------------------------------------------------------------------ #

def graph_to_json(graph: IntentGraph, *, indent: int = 2) -> str:
    """Serialize IntentGraph to a JSON string."""
    return json.dumps(graph_to_dict(graph), indent=indent, ensure_ascii=False)


def json_to_graph(text: str) -> IntentGraph:
    """Deserialize IntentGraph from a JSON string."""
    return dict_to_graph(json.loads(text))


def save_json(graph: IntentGraph, path: str | Path, *, indent: int = 2) -> None:
    """Write IntentGraph to a JSON file.

    Raises ``TreeInvariantViolation`` if any non-root node lacks a parent
    (orphaned nodes indicate a broken tree structure).
    """
    _check_tree_integrity(graph)
    Path(path).write_text(graph_to_json(graph, indent=indent), encoding="utf-8")


def load_json(path: str | Path) -> IntentGraph:
    """Read IntentGraph from a JSON file."""
    return json_to_graph(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ #
#  YAML helpers                                                       #
# ------------------------------------------------------------------ #

def graph_to_yaml(graph: IntentGraph) -> str:
    """Serialize IntentGraph to a YAML string."""
    return yaml.dump(
        graph_to_dict(graph),
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def yaml_to_graph(text: str) -> IntentGraph:
    """Deserialize IntentGraph from a YAML string."""
    return dict_to_graph(yaml.safe_load(text))


def save_yaml(graph: IntentGraph, path: str | Path) -> None:
    """Write IntentGraph to a YAML file.

    Raises ``TreeInvariantViolation`` if any non-root node lacks a parent
    (orphaned nodes indicate a broken tree structure).
    """
    _check_tree_integrity(graph)
    Path(path).write_text(graph_to_yaml(graph), encoding="utf-8")


def load_yaml(path: str | Path) -> IntentGraph:
    """Read IntentGraph from a YAML file."""
    return yaml_to_graph(Path(path).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ #
#  Format-agnostic load/save (extension-based)                       #
# ------------------------------------------------------------------ #

def load_graph(path: str | Path) -> IntentGraph:
    """Read IntentGraph from a file. Format inferred from extension (.json, .yaml, .yml)."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        return load_json(p)
    if suffix in (".yaml", ".yml"):
        return load_yaml(p)
    raise ValueError(
        f"Graph path must have extension .json, .yaml, or .yml; got {suffix!r}"
    )


def save_graph(graph: IntentGraph, path: str | Path, *, indent: int = 2) -> None:
    """Write IntentGraph to a file. Format inferred from extension (.json, .yaml, .yml)."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".json":
        save_json(graph, p, indent=indent)
    elif suffix in (".yaml", ".yml"):
        save_yaml(graph, p)
    else:
        raise ValueError(
            f"Graph path must have extension .json, .yaml, or .yml; got {suffix!r}"
        )


# ------------------------------------------------------------------ #
#  Save-time validation                                               #
# ------------------------------------------------------------------ #

def _check_tree_integrity(graph: IntentGraph) -> None:
    """Validate that the treearc structure is not obviously broken.

    Checks one condition:

    **No orphaned children:** Any node whose UID contains ``.``
    (implying it is a child in the hierarchy) must have a parent — when
    the UID-parent it names (``A.B.C`` → ``A.B``) exists in the graph.
    Catches the case where nodes are created but never attached. A prefix
    that names no node is a namespace, not a parent: ``PIG-OBS.ROOT`` is
    the legitimate root of a ProjectionIG.

    **Relaxation for derived IGs (Spec §9):**
    When ``graph.meta["derived_from"]`` is set the graph is a *reduction* —
    an intentional subset of a parent IG. In this case, nodes with dotted
    UIDs whose UID-parent is not present in the reduction are permitted.
    The orphan check is replaced by V-L7 validation (every node covered by
    the ``via_lens`` lens) which runs in ``validate_lenses``.

    Raises ``TreeInvariantViolation`` on failure.
    """
    # Derived IGs are allowed to have "orphan" nodes (Spec §9, §5.4).
    if graph.meta.get("derived_from"):
        return

    uids = {node.uid for node in graph.iter_nodes()}
    orphans = [
        node.uid
        for node in graph.iter_nodes()
        if "." in node.uid
        and node.parent_uid is None
        and node.uid.rsplit(".", 1)[0] in uids
    ]
    if orphans:
        raise TreeInvariantViolation(
            f"Cannot save: {len(orphans)} node(s) with hierarchical UIDs "
            f"but no parent treearc: {orphans}. "
            f"Did you forget to call graph.attach()?"
        )
