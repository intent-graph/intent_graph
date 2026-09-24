"""Canvas layout primitives shared by the Obsidian export pipeline."""

from __future__ import annotations

from pydantic import BaseModel


class NodeLayout(BaseModel):
    """Canvas position for a single node, as set by a human or a layout engine.

    Stored only for **pinned** (user-touched) positions or engine-computed
    layouts (e.g. ``data_registry.positions``). Nodes absent from a layout
    dict are auto-positioned by the layout algorithm.
    """

    x: int
    y: int
    width: int = 600
    height: int = 560
