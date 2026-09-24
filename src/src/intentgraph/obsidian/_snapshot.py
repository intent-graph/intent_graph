"""Snapshot management for lossless Obsidian→IG merge detection.

A snapshot records the graph state (as hashes) at export time so merge can
detect whether the canonical graph has been modified since export.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph
from intentgraph.models.node import IntentNode


# ---- Constants ----

SNAPSHOT_FILENAME = ".ig-sync.yaml"
SNAPSHOT_SCHEMA = "ig-sync/1"


# ---- Public API ----

def node_content_hash(node: IntentNode) -> str:
    """Compute stable SHA-256 hash of a node's content fields.

    The hash includes all user-editable fields except uid (which is structural).
    Serialization is deterministic (sorted keys, canonical JSON form).

    Returns
    -------
    str
        Hash with ``"sha256:"`` prefix.
    """
    # Serialize node without uid for comparison
    d = node.to_serial_dict()
    d.pop("uid", None)
    # Canonical form: sorted keys, no extra spaces
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def graph_hash(graph: IntentGraph) -> str:
    """Compute stable SHA-256 hash of entire graph state.

    Hash includes all nodes, treearcs, and intentlinks in canonical order.

    Returns
    -------
    str
        Hash with ``"sha256:"`` prefix.
    """
    from intentgraph.serial.json_yaml import graph_to_dict

    d = graph_to_dict(graph)
    # Canonical form: sorted keys, no extra spaces
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def write_snapshot(
    vault_dir: str | Path,
    graph: IntentGraph,
    *,
    graph_id: str | None = None,
    graph_file: str | None = None,
    exported_at: str,
) -> Path:
    """Write a snapshot file to the vault directory.

    The snapshot records:
    - schema version
    - graph identifier and file path (for vault→CLI resolution)
    - export timestamp
    - content hash of entire graph
    - content hash of each node (by uid)

    Parameters
    ----------
    vault_dir : str | Path
        Vault directory (where ``.ig-sync.yaml`` is written).
    graph : IntentGraph
        The graph being exported.
    graph_id : str | None
        Optional graph identifier (stored in snapshot).
    graph_file : str | None
        Optional graph file path (stored in snapshot).
    exported_at : str
        ISO-8601 timestamp (supplied by caller for testability).

    Returns
    -------
    Path
        Path to written snapshot file.
    """
    vault_path = Path(vault_dir).resolve()
    snapshot_path = vault_path / SNAPSHOT_FILENAME

    # Build snapshot dict
    snapshot: dict[str, Any] = {
        "schema": SNAPSHOT_SCHEMA,
        "exported_at": exported_at,
        "graph_hash": graph_hash(graph),
        "nodes": {},
    }
    if graph_id is not None:
        snapshot["graph_id"] = graph_id
    if graph_file is not None:
        snapshot["graph_file"] = graph_file

    # Record per-node hashes
    for node in graph.iter_nodes():
        snapshot["nodes"][node.uid] = node_content_hash(node)

    # Write as YAML
    snapshot_path.write_text(
        yaml.dump(snapshot, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return snapshot_path


def load_snapshot(vault_dir: str | Path) -> dict[str, Any] | None:
    """Load snapshot from vault directory.

    Parameters
    ----------
    vault_dir : str | Path
        Vault directory (where ``.ig-sync.yaml`` lives).

    Returns
    -------
    dict | None
        Parsed snapshot dict, or None if file absent or invalid/malformed.
        On schema mismatch, returns None (treat as no baseline).
    """
    vault_path = Path(vault_dir).resolve()
    snapshot_path = vault_path / SNAPSHOT_FILENAME

    if not snapshot_path.is_file():
        return None

    try:
        data = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        # Validate schema
        if data.get("schema") != SNAPSHOT_SCHEMA:
            return None
        return data
    except (OSError, yaml.YAMLError):
        return None
