"""Load intent_resources.yaml and resolve graph_id to graph file path.

Used by validation and CLI when \"include other IG\" is enabled: inter
intentlink endpoints reference graph_id (e.g. product, pig-py-project);
this module resolves them to actual graph files via the manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_manifest(manifest_path: str | Path) -> dict[str, Any]:
    """Load intent_resources.yaml as a dict. Paths in the file are relative to manifest dir."""
    path = Path(manifest_path)
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    import yaml
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a YAML object, got {type(data)}")
    return data


def resolve_graph_path(manifest_path: str | Path, graph_id: str) -> Path | None:
    """Resolve a graph_id (from inter intentlink endpoints) to an absolute graph file path.

    Searches product[*].id and projection_by_target.<target>[*].id. Returns the
    absolute path for the matching entry's ``file`` (resolved relative to the
    manifest directory), or None if not found.
    """
    data = load_manifest(manifest_path)
    manifest_dir = Path(manifest_path).resolve().parent

    # product: list of {id, name, file, ...}
    for entry in data.get("product") or []:
        if isinstance(entry, dict) and entry.get("id") == graph_id:
            f = entry.get("file")
            if f:
                return (manifest_dir / f).resolve()
            return None

    # projection_by_target: dict of target -> list of {id, name, file, ...}
    for target, entries in (data.get("projection_by_target") or {}).items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") == graph_id:
                f = entry.get("file")
                if f:
                    return (manifest_dir / f).resolve()
                return None

    return None


def list_graph_ids(manifest_path: str | Path) -> list[str]:
    """Return all graph ids defined in the manifest (product + all projections)."""
    data = load_manifest(manifest_path)
    ids: list[str] = []
    for entry in data.get("product") or []:
        if isinstance(entry, dict) and entry.get("id"):
            ids.append(entry["id"])
    for entries in (data.get("projection_by_target") or {}).values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id"):
                ids.append(entry["id"])
    return ids
