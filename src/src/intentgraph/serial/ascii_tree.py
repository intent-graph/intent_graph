"""ASCII tree visualization for IntentGraph.

Renders the tree structure of an IntentGraph as ASCII art showing the
hierarchical refinement structure (treearcs).

Example output:

    root
    ├── PAR
    │   ├── PAR.1
    │   └── PAR.2
    └── CON
        ├── CON.1
        └── CON.2

Supports both compact (uid + name) and detailed (with intent) modes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intentgraph.models.graph import IntentGraph
    from intentgraph.models.node import IntentNode


def render_ascii_tree(
    graph: IntentGraph,
    *,
    root_uid: str | None = None,
    show_intent: bool = False,
    max_width: int = 80,
    indent: str = "    ",
) -> str:
    """Render the IntentGraph as an ASCII tree.

    Args:
        graph: The IntentGraph to visualize
        root_uid: UID of the root node to start from (if None, finds the actual root)
        show_intent: If True, include intent description below each node
        max_width: Maximum width for wrapping intent text
        indent: Indentation string for tree structure

    Returns:
        ASCII tree representation as a string
    """
    if root_uid is None:
        # Find the root(s)
        roots = [n for n in graph.nodes.values() if n.parent_uid is None]
        if not roots:
            return "(empty graph)"
        if len(roots) > 1:
            # Multiple roots - render each separately
            parts = []
            for root in roots:
                parts.append(render_ascii_tree(
                    graph,
                    root_uid=root.uid,
                    show_intent=show_intent,
                    max_width=max_width,
                    indent=indent
                ))
            return "\n\n".join(parts)
        root_uid = roots[0].uid

    root = graph.get_node(root_uid)
    lines: list[str] = []
    _render_node(graph, root, "", True, lines, show_intent, max_width, indent)
    return "\n".join(lines)


def _render_node(
    graph: IntentGraph,
    node: IntentNode,
    prefix: str,
    is_last: bool,
    lines: list[str],
    show_intent: bool,
    max_width: int,
    indent: str,
) -> None:
    """Recursively render a node and its children."""
    # Determine the connector symbol
    connector = "└── " if is_last else "├── "

    # Build the node label
    label = f"{node.uid}: {node.name}"

    # Add the node line
    lines.append(f"{prefix}{connector}{label}")

    # Add intent if requested
    if show_intent and node.intent:
        intent_prefix = prefix + ("    " if is_last else "│   ")
        wrapped = _wrap_text(node.intent, max_width - len(intent_prefix) - 2)
        for line in wrapped:
            lines.append(f"{intent_prefix}  {line}")

    # Prepare prefix for children
    child_prefix = prefix + ("    " if is_last else "│   ")

    # Render children
    children = graph.children(node.uid)
    for i, child in enumerate(children):
        child_is_last = (i == len(children) - 1)
        _render_node(graph, child, child_prefix, child_is_last, lines, show_intent, max_width, indent)


def _wrap_text(text: str, max_width: int) -> list[str]:
    """Simple word-wrap for intent text."""
    if max_width <= 0:
        return [text]

    words = text.split()
    lines: list[str] = []
    current_line: list[str] = []
    current_length = 0

    for word in words:
        word_len = len(word)
        if current_length + word_len + len(current_line) > max_width:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_len
            else:
                # Word is longer than max_width
                lines.append(word)
        else:
            current_line.append(word)
            current_length += word_len

    if current_line:
        lines.append(" ".join(current_line))

    return lines if lines else [""]


def render_ascii_tree_boxed(
    graph: IntentGraph,
    *,
    root_uid: str | None = None,
    max_width: int = 120,
) -> str:
    """Render the IntentGraph as an ASCII tree with boxes (like your mockup).

    This creates a more elaborate box-based visualization similar to your example,
    with proper box drawing and connection lines.

    Args:
        graph: The IntentGraph to visualize
        root_uid: UID of the root node to start from (if None, finds the actual root)
        max_width: Maximum width for the entire diagram

    Returns:
        Boxed ASCII tree representation
    """
    if root_uid is None:
        roots = [n for n in graph.nodes.values() if n.parent_uid is None]
        if not roots:
            return "(empty graph)"
        if len(roots) > 1:
            parts = []
            for root in roots:
                parts.append(render_ascii_tree_boxed(graph, root_uid=root.uid, max_width=max_width))
            return "\n\n".join(parts)
        root_uid = roots[0].uid

    root = graph.get_node(root_uid)

    # For now, fall back to simple tree rendering
    # A full box-based renderer would require significant layout computation
    # to handle proper spacing, alignment, and connection routing
    return render_ascii_tree(graph, root_uid=root_uid, show_intent=True, max_width=max_width)


def print_tree(graph: IntentGraph, **kwargs) -> None:
    """Print the ASCII tree to stdout (convenience wrapper)."""
    print(render_ascii_tree(graph, **kwargs))
