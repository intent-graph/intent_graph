"""Lens file serialization — build, round-trip, and file I/O.

Functions:
- lens_to_dict / dict_to_lens: round-trip serialization
- save_lens / load_lens: file I/O (YAML default, JSON for .json)
- lens_to_agent_text: serialize Lens to agent-readable YAML with LOD filtering
- is_lens_file: type discriminator for dicts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from intentgraph.models.lens import Lens, LOD


# ================================================================== #
#  Dict round-trip                                                   #
# ================================================================== #


def lens_to_dict(lens: Lens) -> dict[str, Any]:
    """Serialize a Lens to a plain dict.

    Structure follows the IG serialization format with a `lens` key
    as discriminator.

    Nodes include LOD and pruned_children fields inline.
    """
    return lens.to_serial_dict()


def dict_to_lens(d: dict[str, Any]) -> Lens:
    """Deserialize a plain dict into a Lens.

    Expects the structure produced by `lens_to_dict()`.
    """
    return Lens.from_serial_dict(d)


# ================================================================== #
#  File I/O                                                          #
# ================================================================== #


def save_lens(lens: Lens, path: str | Path) -> None:
    """Write a Lens to disk (YAML by default, JSON for .json extension)."""
    path = Path(path)
    d = lens_to_dict(lens)

    if path.suffix == ".json":
        text = json.dumps(d, indent=2, ensure_ascii=False)
    else:
        text = yaml.dump(d, default_flow_style=False, allow_unicode=True, sort_keys=False)

    path.write_text(text, encoding="utf-8")


def load_lens(path: str | Path) -> Lens:
    """Read a Lens from disk (auto-detects YAML vs JSON)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")

    if path.suffix == ".json":
        d = json.loads(text)
    else:
        d = yaml.safe_load(text)

    return dict_to_lens(d)


# ================================================================== #
#  Agent text format with LOD filtering                              #
# ================================================================== #


def lens_to_agent_text(lens: Lens) -> str:
    """Serialize a Lens to agent-readable YAML with LOD-based field filtering.

    LOD determines which fields are included per node:
    - skeleton: uid, name only
    - lean: + intent, epistemic_state
    - full: all fields + collapsed_children

    IntentLinks:
    - Only visible if both endpoints are at lean or above
    - Description shown only if at least one endpoint is at full

    Format matches §2 (agent text) from SERIALIZATION_FORMAT.md.
    """
    # ---- Header ----
    header: dict[str, Any] = {
        "name": lens.meta.name,
        "target": lens.meta.target_uid,
        "budget": lens.meta.budget,
    }
    if lens.meta.scope_root:
        header["scope_root"] = lens.meta.scope_root

    # ---- Nodes with LOD filtering ----
    node_dicts: list[dict[str, Any]] = []
    for uid in sorted(lens.nodes.keys()):
        node = lens.nodes[uid]
        lod = lens.get_lod(uid)

        # Start with minimal fields
        d: dict[str, Any] = {
            "uid": node.uid,
            "name": node.name,
        }

        # Add fields based on LOD
        if lod >= LOD.lean:
            d["intent"] = node.intent
            if node.epistemic_state is not None:
                d["epistemic_state"] = node.epistemic_state

        if lod >= LOD.full:
            # Full detail: all optional fields
            if node.constraints:
                d["constraints"] = list(node.constraints)
            if node.examples:
                d["examples"] = list(node.examples)
            if node.design_notes is not None:
                d["design_notes"] = node.design_notes
            if node.effort is not None:
                d["effort"] = node.effort
            if node.impl_pointers is not None:
                d["impl_pointers"] = node.impl_pointers
            if node.history:
                d["history"] = [
                    {"who": h.who, "date": h.date, "note": h.note}
                    for h in node.history
                ]
            if node.data_registry:
                d["data_registry"] = node.data_registry

            # Collapsed children (pruned or not in lens)
            node_metadata = lens.node_metadata[uid]
            if node_metadata.pruned_children > 0:
                d["pruned_children"] = node_metadata.pruned_children

            # Show visible children UIDs (for tree context)
            visible_children = [c for c in node.children_uids if c in lens.nodes]
            if visible_children:
                d["collapsed_children"] = visible_children

        node_dicts.append(d)

    # ---- Treearcs (explicit tree structure) ----
    treearc_dicts: list[dict[str, str]] = [
        {"parent": p, "child": c} for p, c in sorted(lens.treearcs)
    ]

    # ---- IntentLinks with visibility filtering ----
    link_dicts: list[dict[str, Any]] = []
    for uid in sorted(lens.intentlinks.keys()):
        link = lens.intentlinks[uid]
        src_lod = lens.get_lod(link.src)
        dst_lod = lens.get_lod(link.dst)

        # Visibility rule: both endpoints must be at lean or above
        if src_lod >= LOD.lean and dst_lod >= LOD.lean:
            ld: dict[str, Any] = {
                "uid": link.uid,
                "src": link.src,
                "dst": link.dst,
            }

            # Description rule: show only if at least one endpoint is full
            if src_lod >= LOD.full or dst_lod >= LOD.full:
                ld["intent"] = link.intent
                if link.shape:
                    ld["shape"] = link.shape
            else:
                # Lean-lean: structural only (no description)
                pass

            link_dicts.append(ld)

    # ---- Assemble ----
    doc: dict[str, Any] = {
        "lens": header,
        "nodes": node_dicts,
        "treearcs": treearc_dicts,
        "intentlinks": link_dicts,
    }

    return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ================================================================== #
#  Type discriminator                                                #
# ================================================================== #


def is_lens_file(d: dict[str, Any]) -> bool:
    """Check if a dict represents a lens file (vs graph or agent-text view).

    Lens files have a top-level `lens` key with at least `name`, `target_uid`,
    and `source_graph`.  Agent-text views have a `view` (or legacy
    `frontier`) key; graph files have a `meta` key.
    """
    if not isinstance(d, dict):
        return False
    lens_meta = d.get("lens")
    if not isinstance(lens_meta, dict):
        return False
    return all(k in lens_meta for k in ("name", "target_uid", "source_graph"))
