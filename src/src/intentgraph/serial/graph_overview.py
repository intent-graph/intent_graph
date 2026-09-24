"""Lightweight graph overview — compact serialization for agent navigation.

Produces two complementary YAML representations of the full IntentGraph:

1. **Tree overview** — the node hierarchy with minimal fields per node
   (uid, name, depth, epistemic_state, children count).  Enough for an
   agent (Navigator, Critic) to understand the graph structure and choose
   where to focus without blowing the token budget.

2. **Edge overview** — intentlinks as a flat list of src→dst pairs with
   their intent sentence.

Inspired by the ``md_structure_viz`` full-mode pattern of separating node
and edge concerns into two compact YAML files.
"""

from __future__ import annotations

from typing import Any

import yaml

from intentgraph.models.graph import IntentGraph


# ================================================================== #
#  Tree overview (nodes + hierarchy)                                   #
# ================================================================== #


def graph_to_tree_overview(graph: IntentGraph) -> str:
    """Serialize the graph's tree structure as a compact YAML hierarchy.

    Output format::

        meta:
          name: "ETL Pipeline"
          node_count: 15
          link_count: 8
          max_depth: 3

        tree:
          ROOT:  # ETL System [3 children]
            E:  # Extract [3 children] epistemic:known
              E.1:  # Parse CSV [leaf]
              E.2:  # Parse JSON [leaf]
              E.3:  # Validate [leaf]
            T:  # Transform [3 children]
              ...

    Each node line includes: name, children count (or "leaf"), and
    epistemic_state if set.  This is intentionally terse — full node
    details come from the agent text format.
    """
    roots = graph.roots()
    if not roots:
        return yaml.dump({"meta": graph.meta, "tree": {}},
                         default_flow_style=False, sort_keys=False)

    max_depth = 0

    def _build_subtree(uid: str, depth: int) -> dict[str, Any]:
        nonlocal max_depth
        if depth > max_depth:
            max_depth = depth

        node = graph.get_node(uid)
        children = graph.children(uid)

        # Build the comment-like label
        parts = [node.name]
        if children:
            parts.append(f"[{len(children)} children]")
        else:
            parts.append("[leaf]")
        if node.epistemic_state:
            parts.append(f"epistemic:{node.epistemic_state}")

        label = " — ".join([parts[0]] + parts[1:])

        if not children:
            return {uid: f"# {label}"}

        subtree: dict[str, Any] = {}
        for child in sorted(children, key=lambda c: c.uid):
            child_tree = _build_subtree(child.uid, depth + 1)
            subtree.update(child_tree)

        return {uid: {"_label": f"# {label}", **subtree}}

    tree: dict[str, Any] = {}
    for root in sorted(roots, key=lambda r: r.uid):
        tree.update(_build_subtree(root.uid, 0))

    meta = {
        **(graph.meta or {}),
        "node_count": graph.node_count(),
        "link_count": graph.link_count(),
        "max_depth": max_depth,
    }
    if graph.inter_link_count():
        meta["inter_link_count"] = graph.inter_link_count()

    doc = {"meta": meta, "tree": tree}
    return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ================================================================== #
#  Edge overview (intentlinks)                                         #
# ================================================================== #


def graph_to_edge_overview(graph: IntentGraph) -> str:
    """Serialize all intentlinks as a compact YAML list.

    Output format::

        link_count: 8
        intentlinks:
          - E -> T: "Extracted data flows to transformation"
          - T -> L: "Transformed data flows to loading"
          - E.3 -> T.1: "Validated records sent for normalization"
    """
    links_list: list[str] = []
    for link in sorted(graph.iter_links(), key=lambda l: l.uid):
        links_list.append(f"{link.src} -> {link.dst}: {link.intent!r}")

    doc: dict[str, Any] = {
        "link_count": graph.link_count(),
        "intentlinks": links_list,
    }
    if graph.inter_link_count():
        inter_list: list[str] = []
        for link in sorted(graph.iter_inter_links(), key=lambda l: (l.uid or f"{l.src}_{l.dst}")):
            inter_list.append(f"{link.src} -> {link.dst}: {link.intent!r}")
        doc["inter_link_count"] = graph.inter_link_count()
        doc["inter_intentlinks"] = inter_list
    return yaml.dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ================================================================== #
#  Structure overview (uid + title skeleton, same keys as agent text)  #
# ================================================================== #


def _node_fill_comment(node: Any) -> str:
    """Build a YAML comment showing field fill for an intentnode.

    String fields → char count, list fields → entry count.
    Only populated fields appear; absence means empty.
    ``epistemic_state`` is excluded (it's a label, not sized content).
    """
    parts: list[str] = []
    # intent is always present (required field)
    parts.append(f"intent:{len(node.intent)}")
    if node.constraints:
        parts.append(f"constraints:{len(node.constraints)}")
    if node.examples:
        parts.append(f"examples:{len(node.examples)}")
    if node.design_notes:
        parts.append(f"design_notes:{len(node.design_notes)}")
    if node.effort:
        parts.append(f"effort:{len(node.effort)}")
    if node.impl_pointers:
        parts.append(f"impl_pointers:{len(node.impl_pointers)}")
    if node.history:
        parts.append(f"history:{len(node.history)}")
    return " ".join(parts)


def graph_to_structure(graph: IntentGraph) -> str:
    """Serialize the full graph as a skeleton using the agent text key layout.

    Same top-level keys as ``view_to_text`` (``nodes:``, ``intentlinks:``)
    but stripped to identification fields only:

    - **nodes**: ``uid``, ``name``, ``epistemic_state`` (if set),
      plus a YAML comment with field fill
    - **intentlinks**: ``uid``, ``src``, ``dst``

    No intent bodies, no constraints, no optional fields in the data.
    Field fill rides as comments (schema-neutral, read-only signal).

    Built as manual YAML to support inline comments (pyyaml cannot emit them).
    """
    lines: list[str] = ["nodes:"]
    for node in sorted(graph.iter_nodes(), key=lambda n: n.uid):
        fill = _node_fill_comment(node)
        lines.append(f"  - uid: {node.uid}")
        lines.append(f"    name: {_yaml_scalar(node.name)}  # {fill}")
        if node.epistemic_state:
            lines.append(f"    epistemic_state: {_yaml_scalar(node.epistemic_state)}")

    lines.append("intentlinks:")
    for link in sorted(graph.iter_links(), key=lambda l: l.uid):
        lines.append(f"  - uid: {link.uid}")
        lines.append(f"    src: {link.src}")
        lines.append(f"    dst: {link.dst}")

    if graph.inter_link_count():
        lines.append("inter_intentlinks:")
        for link in sorted(graph.iter_inter_links(), key=lambda l: (l.uid or f"{l.src}_{l.dst}")):
            uid = link.uid or f"{link.src}_{link.dst}"
            lines.append(f"  - uid: {uid}")
            lines.append(f"    src: {link.src}")
            lines.append(f"    dst: {link.dst}")

    lines.append("")  # trailing newline
    return "\n".join(lines)


def _yaml_scalar(s: str) -> str:
    """Quote a string for safe YAML scalar emission."""
    if not s or any(c in s for c in ':#{}[]&*!|>\\\'"') or s.strip() != s:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


# ================================================================== #
#  View size estimation                                                #
# ================================================================== #


def view_text_size(view_text: str) -> dict[str, int]:
    """Estimate the size of a serialized agent-text view.

    Returns a dict with ``chars``, ``words``, and ``lines`` counts.
    Use this to check whether a view is too large for agent context.
    If it is, use lean IV-context: full detail on the target and its
    direct neighbors, lean fields everywhere else.
    """
    chars = len(view_text)
    words = len(view_text.split())
    lines = view_text.count("\n") + (1 if view_text else 0)
    return {"chars": chars, "words": words, "lines": lines}
