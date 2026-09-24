"""ig-tool ``query`` command: graph navigation queries.

Moved verbatim from ``cli_impl.py`` (Phase 2: command extraction). Pure move:
no behavior change.
"""

from __future__ import annotations

import argparse
from typing import Any

import yaml

from intentgraph.ops.iv_context import target_neighbor_uids
from intentgraph.serial.graph_overview import (
    graph_to_edge_overview,
    graph_to_structure,
    graph_to_tree_overview,
)

from ig_agents.cli.common import _die, _write_output, _summary, _load_graph


# ================================================================== #
#  query                                                               #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``query`` subcommand on *sub*."""
    p_q = sub.add_parser(
        "query",
        help="Graph navigation queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool query -g graph.json --overview\n"
            "  ig-tool query -g graph.json --node ROOT.PARSE\n"
            "  ig-tool query -g graph.json --children ROOT --neighbors UID -o out.yaml\n"
            "  ig-tool query -g graph.json --structure        # uid+name skeleton (compact)\n"
            "Notes:\n"
            "  - Exactly one of --node/--children/--ancestors/--links/--neighbors/--overview/--structure is required.\n"
            "  - --projection-links UID inspects inter-graph links (qualified UIDs).\n"
        ),
    )
    p_q.add_argument("-g", "--graph", required=True, help="Path to graph file (JSON or YAML)")
    p_q.add_argument("-o", "--output", help="Write full result to this path")
    grp = p_q.add_mutually_exclusive_group(required=True)
    grp.add_argument("--node", metavar="UID", help="Full content of a single node")
    grp.add_argument("--children", metavar="UID", help="List children of a node")
    grp.add_argument("--ancestors", metavar="UID", help="Ancestor chain of a node")
    grp.add_argument("--links", metavar="UID", help="Intentlinks (intra) touching a node")
    grp.add_argument("--projection-links", metavar="UID", dest="projection_links", help="Inter intentlinks where UID appears as node in src or dst (graph_id:node_uid)")
    grp.add_argument("--neighbors", metavar="UID", help="Direct neighbors (IV-context adjacency)")
    grp.add_argument("--overview", action="store_true", help="Compact tree + edge overview")
    grp.add_argument("--structure", action="store_true", help="Skeleton: node uid+name, link uid+src+dst")


def _node_to_dict(node: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"uid": node.uid, "name": node.name, "intent": node.intent}
    if node.parent_uid:
        d["parent"] = node.parent_uid
    if node.children_uids:
        d["children"] = list(node.children_uids)
    if node.epistemic_state:
        d["epistemic_state"] = node.epistemic_state
    if node.constraints:
        d["constraints"] = list(node.constraints)
    if node.examples:
        d["examples"] = list(node.examples)
    if node.design_notes:
        d["design_notes"] = node.design_notes
    if node.effort:
        d["effort"] = node.effort
    if node.impl_pointers:
        d["impl_pointers"] = node.impl_pointers
    if node.history:
        d["history"] = [{"who": h.who, "date": h.date, "note": h.note} for h in node.history]
    if node.data_registry:
        d["data_registry"] = node.data_registry
    return d


def cmd_query(args: argparse.Namespace) -> None:
    graph = _load_graph(args.graph)

    label = "query"
    result: Any = None

    if args.overview:
        label = "query --overview"
        tree = graph_to_tree_overview(graph)
        edges = graph_to_edge_overview(graph)
        content = tree + "---\n" + edges
        size = _write_output(content, args.output)
        _summary("ok", label, args.output, size,
                 nodes=graph.node_count(), links=graph.link_count())
        return

    if args.structure:
        label = "query --structure"
        content = graph_to_structure(graph)
        size = _write_output(content, args.output)
        _summary("ok", label, args.output, size,
                 nodes=graph.node_count(), links=graph.link_count())
        return

    if args.node:
        label = f"query --node {args.node}"
        node = graph.get_node_or_none(args.node)
        if node is None:
            _die(f"node '{args.node}' not found")
        result = _node_to_dict(node)

    elif args.children:
        label = f"query --children {args.children}"
        children = graph.children(args.children)
        result = {"parent": args.children,
                  "count": len(children),
                  "children": [_node_to_dict(c) for c in children]}

    elif args.ancestors:
        label = f"query --ancestors {args.ancestors}"
        anc_uids = graph.anc(args.ancestors)
        chain: list[dict[str, str]] = []
        current = args.ancestors
        while True:
            p = graph.parent(current)
            if p is None:
                break
            chain.append({"uid": p.uid, "name": p.name})
            current = p.uid
        result = {"node": args.ancestors,
                  "depth": len(chain),
                  "ancestor_chain": chain,
                  "all_ancestor_uids": sorted(anc_uids)}

    elif args.links:
        label = f"query --links {args.links}"
        uid = args.links
        incoming: list[dict[str, str]] = []
        outgoing: list[dict[str, str]] = []
        for link in graph.iter_links():
            ld = {"uid": link.uid, "src": link.src, "dst": link.dst, "intent": link.intent}
            if link.src == uid:
                outgoing.append(ld)
            elif link.dst == uid:
                incoming.append(ld)
        result = {"node": uid,
                  "outgoing_count": len(outgoing), "outgoing": outgoing,
                  "incoming_count": len(incoming), "incoming": incoming}

    elif getattr(args, "projection_links", None):
        label = f"query --projection-links {args.projection_links}"
        uid = args.projection_links
        def _node_uid(q: str) -> str | None:
            if ":" in q:
                return q.split(":", 1)[1]
            return None
        outgoing: list[dict[str, Any]] = []
        incoming: list[dict[str, Any]] = []
        for link in graph.iter_inter_links():
            ld = {"uid": link.uid, "src": link.src, "dst": link.dst, "intent": link.intent}
            src_node = _node_uid(link.src)
            dst_node = _node_uid(link.dst)
            if src_node == uid:
                outgoing.append(ld)
            elif dst_node == uid:
                incoming.append(ld)
        result = {"node": uid,
                  "outgoing_count": len(outgoing), "outgoing": outgoing,
                  "incoming_count": len(incoming), "incoming": incoming}

    elif args.neighbors:
        label = f"query --neighbors {args.neighbors}"
        uid = args.neighbors
        nbrs = target_neighbor_uids(graph, uid)
        parent = graph.parent(uid)
        children = [c.uid for c in graph.children(uid)]
        link_nbrs = nbrs - ({parent.uid} if parent else set()) - set(children)
        result = {"target": uid,
                  "neighbor_count": len(nbrs),
                  "parent": parent.uid if parent else None,
                  "children": sorted(children),
                  "link_neighbors": sorted(link_nbrs),
                  "all_neighbors": sorted(nbrs)}

    else:
        _die("query requires one of: --node, --children, --ancestors, --links, --projection-links, --neighbors, --overview, --structure")

    content = yaml.dump(result, default_flow_style=False, allow_unicode=True, sort_keys=False)
    size = _write_output(content, args.output)

    # Extract a count metric from the result for the summary
    count_key = next((k for k in ("neighbor_count", "count", "depth",
                                  "outgoing_count") if k in (result or {})), None)
    extra: dict[str, Any] = {}
    if count_key and result:
        extra[count_key] = result[count_key]

    _summary("ok", label, args.output, size, **extra)
