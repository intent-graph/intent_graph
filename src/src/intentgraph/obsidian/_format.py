"""Shared format constants and helpers for the Obsidian module.

Defines the Obsidian vault conventions (filename patterns, layout grid,
YAML/Markdown formatting) used by both export and import.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ------------------------------------------------------------------ #
#  Layout grid constants (match the reference implementation)         #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class LayoutConfig:
    """Configuration for the Obsidian Canvas grid layout."""

    node_width: int = 600
    node_height: int = 560
    gap: int = 300
    cols: int = 3
    start_x: int = 300
    start_y: int = 300
    group_offset_x: int = -50
    group_offset_y: int = -100
    group_extra_height: int = 200


DEFAULT_LAYOUT = LayoutConfig()


# ------------------------------------------------------------------ #
#  Filename conventions                                               #
# ------------------------------------------------------------------ #

def sanitize_name(name: str) -> str:
    """Make a node name safe for filenames: remove/replace invalid chars."""
    if not name:
        return ""
    s = re.sub(r'[/\\:*?"<>|]', " ", name)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def node_filename(uid: str, name: str) -> str:
    """Return the Obsidian node filename: ``'{uid} {name}.md'``."""
    title = sanitize_name(name)
    if title:
        return f"{uid} {title}.md"
    return f"{uid}.md"


def node_stem(uid: str, name: str) -> str:
    """Return the filename stem (no .md extension) for wiki-link references."""
    return node_filename(uid, name).removesuffix(".md")


def uid_from_stem(stem: str) -> str:
    """Extract UID from a filename stem like ``'IG.1.1 Define Core Terms'``."""
    if " " in stem:
        return stem.split(" ", 1)[0]
    return stem


def name_from_stem(stem: str) -> str:
    """Extract name from a filename stem like ``'IG.1.1 Define Core Terms'``."""
    if " " in stem:
        return stem.split(" ", 1)[1]
    return ""


# ------------------------------------------------------------------ #
#  ID generation (escape UID separators for Obsidian Canvas)         #
# ------------------------------------------------------------------ #

def to_canvas_id(uid: str) -> str:
    """Convert a node UID to a canvas-safe identifier.

    UIDs may contain `.` (level separator) and `_` (allowed inside keyword
    segments since the underscore-in-UID policy). Both are mapped to `_` in
    the output, so the encoding must be bijective: existing underscores in the
    UID are doubled before dots are replaced. Examples:

        ROOT             -> ROOT
        LEXER.TOKENS     -> LEXER_TOKENS         (dot becomes single underscore)
        LEXER_TOKENS     -> LEXER__TOKENS        (existing underscore doubled)
        LEXER.PARSER_INTERFACE -> LEXER_PARSER__INTERFACE

    Without the doubling, `LEXER.TOKENS` and `LEXER_TOKENS` would collide,
    silently overwriting each other in the export `id_to_uid` lookup table.
    """
    return uid.replace("_", "__").replace(".", "_")


def group_id(uid: str) -> str:
    """Canvas group node ID for a parent UID."""
    return f"group_{to_canvas_id(uid)}"


def file_node_id(uid: str) -> str:
    """Canvas file-reference node ID for a child UID."""
    return f"node_{to_canvas_id(uid)}"


def edge_id(src: str, dst: str) -> str:
    """Canvas edge ID for an intentlink between two nodes."""
    return f"edge_{to_canvas_id(src)}_{to_canvas_id(dst)}"


# ------------------------------------------------------------------ #
#  Grid layout math                                                   #
# ------------------------------------------------------------------ #

def compute_grid_positions(
    n: int,
    config: LayoutConfig | None = None,
) -> list[dict[str, int]]:
    """Compute ``(x, y)`` positions for *n* nodes on a grid.

    Returns a list of ``{"x": int, "y": int}`` dicts, one per node index.
    """
    cfg = config or DEFAULT_LAYOUT
    positions: list[dict[str, int]] = []
    for i in range(n):
        col = i % cfg.cols
        row = i // cfg.cols
        x = cfg.start_x + col * (cfg.node_width + cfg.gap)
        y = cfg.start_y + row * (cfg.node_height + cfg.gap)
        positions.append({"x": x, "y": y})
    return positions


def compute_group_size(
    n_children: int,
    config: LayoutConfig | None = None,
) -> dict[str, int]:
    """Compute the bounding group node dimensions for *n_children* child nodes."""
    cfg = config or DEFAULT_LAYOUT
    n_rows = (n_children + cfg.cols - 1) // cfg.cols
    width = cfg.cols * (cfg.node_width + cfg.gap) + cfg.gap
    height = n_rows * (cfg.node_height + cfg.gap) + cfg.gap + cfg.group_extra_height
    return {"width": width, "height": height}


# ------------------------------------------------------------------ #
#  YAML / frontmatter helpers                                        #
# ------------------------------------------------------------------ #

# Placeholders used in literal blocks so that "---" / "..." never appear as
# a substring (frontmatter is split by "---" to extract YAML).
_SAFE_DOC_START = " - - - "   # export: ---  -> this; import: this -> ---
_SAFE_DOC_END = " . . . "    # export: ...  -> this; import: this -> ...


def _safe_literal_line(line: str) -> str:
    """Replace ``---`` / ``...`` lines so frontmatter split and YAML parse don't break."""
    s = line.strip()
    if s == "---":
        return _SAFE_DOC_START
    if s == "...":
        return _SAFE_DOC_END
    return line


def unescape_literal_content(text: str | None) -> str:
    """Restore ``---`` / ``...`` that were escaped in literal blocks (round-trip)."""
    if not text:
        return text or ""
    return (
        text.replace(_SAFE_DOC_START, "---")
        .replace(_SAFE_DOC_END, "...")
    )


def yaml_literal_block(text: str | None, default: str = "") -> list[str]:
    """Format a string as YAML literal block scalar lines (indented by 2).

    Returns the lines to append *after* the ``field: |`` header.
    """
    value = (text or "").strip()
    if not value:
        value = default or " "
    return [f"  {_safe_literal_line(line)}" for line in value.split("\n")]


def yaml_str_list(items: list[str] | None) -> str | list[str]:
    """Format a list of strings for YAML (single-line items only).

    Returns ``'[]'`` for empty/None, or a list of ``'  - "item"'`` lines.
    Use ``yaml_str_list_multiline`` for items that may contain newlines.
    """
    if not items:
        return "[]"
    lines: list[str] = []
    for item in items:
        escaped = item.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  - "{escaped}"')
    return lines


def yaml_str_list_multiline(items: list[str] | None) -> list[str]:
    """Format a list of strings for YAML, using literal block for multiline items.

    Single-line items are emitted as ``  - "quoted"``. Items containing newlines
    are emitted as ``  - |`` followed by indented lines (4 spaces), so YAML
    parses correctly and Obsidian displays correctly.
    """
    if not items:
        return []
    lines: list[str] = []
    for item in items:
        if "\n" in item:
            lines.append("  - |")
            for line in item.split("\n"):
                lines.append(f"    {_safe_literal_line(line)}")
        else:
            escaped = item.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'  - "{escaped}"')
    return lines


def yaml_quote(s: str) -> str:
    """Quote a YAML string value if it contains special characters."""
    if not s:
        return '""'
    needs_quoting = any(c in s for c in ':{}[]&*?|>#%@`!,\n"')
    if needs_quoting:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s
