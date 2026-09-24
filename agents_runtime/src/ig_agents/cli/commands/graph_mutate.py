"""ig-tool ``node`` and ``link`` commands: direct single-entity graph mutation.

Moved from ``cli_lens_commands.py`` (Phase 3: Edit pipeline — parse, apply,
node, link share the same domain because they all touch the ``EditOp``/
mutation surface). This module owns only ``node`` and ``link`` (direct
single-entity mutation via ``graph.add_node``/``update_node``/etc.);
``parse``/``apply``/batch (the ``EditOp``-based pipeline) live in
``cli/commands/parse_apply.py``.

Pure move for ``cmd_node``/``cmd_link`` themselves: no behavior change.
``node remove``/``link remove`` still lack ``--dry-run``/``--force`` — that
enhancement was deferred and kept as a follow-up opportunity.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import yaml

from ig_agents.cli.common import _die, _load_graph, _save_graph, _write_output, _summary


# ================================================================== #
#  node                                                               #
# ================================================================== #


def cmd_node(args: argparse.Namespace) -> None:
    """Handle node subcommand with all actions."""

    # ---- create ----
    if args.action == "create":
        if not args.graph:
            _die("node create requires -g GRAPH")
        if not args.uid:
            _die("node create requires --uid NODE_UID")
        if not args.name:
            _die("node create requires --name NODE_NAME")
        if not args.intent:
            _die("node create requires --intent NODE_INTENT")
        if not args.output:
            _die("node create requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        # Build node kwargs
        kwargs = {}
        if hasattr(args, 'epistemic_state') and args.epistemic_state:
            kwargs['epistemic_state'] = args.epistemic_state
        if hasattr(args, 'constraints') and args.constraints:
            kwargs['constraints'] = list(args.constraints)
        if hasattr(args, 'examples') and args.examples:
            kwargs['examples'] = list(args.examples)
        if hasattr(args, 'design_notes') and args.design_notes:
            kwargs['design_notes'] = args.design_notes
        if hasattr(args, 'effort') and args.effort:
            kwargs['effort'] = args.effort
        if hasattr(args, 'impl_pointers') and args.impl_pointers:
            kwargs['impl_pointers'] = list(args.impl_pointers)
        if hasattr(args, 'data_registry') and args.data_registry:
            try:
                kwargs['data_registry'] = json.loads(args.data_registry)
            except json.JSONDecodeError as e:
                _die(f"invalid --data-registry JSON: {e}")

        try:
            graph.add_node(args.uid, args.name, args.intent, **kwargs)

            # Attach to parent if specified
            if hasattr(args, 'parent') and args.parent:
                graph.attach(args.parent, args.uid)

        except Exception as e:
            _die(f"node create failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "node create", args.output, size,
                 uid=args.uid,
                 parent=getattr(args, 'parent', None))
        return

    # ---- set ----
    if args.action == "set":
        if not args.graph:
            _die("node set requires -g GRAPH")
        if not args.uid:
            _die("node set requires --uid NODE_UID")
        if not args.output:
            _die("node set requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        # Build update kwargs from optional fields
        kwargs = {}
        if hasattr(args, 'name') and args.name:
            kwargs['name'] = args.name
        if hasattr(args, 'intent') and args.intent:
            kwargs['intent'] = args.intent
        if hasattr(args, 'epistemic_state') and args.epistemic_state:
            kwargs['epistemic_state'] = args.epistemic_state
        if hasattr(args, 'constraints') and args.constraints:
            kwargs['constraints'] = list(args.constraints)
        if hasattr(args, 'examples') and args.examples:
            kwargs['examples'] = list(args.examples)
        if hasattr(args, 'design_notes') and args.design_notes:
            kwargs['design_notes'] = args.design_notes
        if hasattr(args, 'effort') and args.effort:
            kwargs['effort'] = args.effort
        if hasattr(args, 'impl_pointers') and args.impl_pointers:
            kwargs['impl_pointers'] = list(args.impl_pointers)
        if hasattr(args, 'data_registry') and args.data_registry:
            try:
                kwargs['data_registry'] = json.loads(args.data_registry)
            except json.JSONDecodeError as e:
                _die(f"invalid --data-registry JSON: {e}")

        unset_fields = list(getattr(args, 'unset', None) or [])
        overlap = set(unset_fields) & set(kwargs)
        if overlap:
            _die(f"field(s) both set and unset: {sorted(overlap)}")
        if not kwargs and not unset_fields:
            _die("node set requires at least one field to update (or --unset FIELD)")

        try:
            if kwargs:
                graph.update_node(args.uid, **kwargs)
            if unset_fields:
                graph.unset_node_fields(args.uid, unset_fields)
        except Exception as e:
            _die(f"node set failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "node set", args.output, size,
                 uid=args.uid,
                 fields_updated=list(kwargs.keys()) + [f"unset:{f}" for f in unset_fields])
        return

    # ---- reparent ----
    if args.action == "reparent":
        if not args.graph:
            _die("node reparent requires -g GRAPH")
        if not args.uid:
            _die("node reparent requires --uid CHILD_UID")
        if not args.under:
            _die("node reparent requires --under NEW_PARENT_UID")
        if not args.output:
            _die("node reparent requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        try:
            # Detach from current parent
            child = graph.get_node(args.uid)
            if child.parent_uid:
                graph.detach(child.parent_uid, args.uid)

            # Attach to new parent
            graph.attach(args.under, args.uid)

        except Exception as e:
            _die(f"node reparent failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "node reparent", args.output, size,
                 child=args.uid,
                 new_parent=args.under)
        return

    # ---- reorder ----
    if args.action == "reorder":
        if not args.graph:
            _die("node reorder requires -g GRAPH")
        if not args.parent:
            _die("node reorder requires --parent PARENT_UID")
        if not args.children:
            _die("node reorder requires --children UID1 UID2 ...")
        if not args.output:
            _die("node reorder requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        try:
            parent = graph.get_node(args.parent)

            # Validate all children exist and belong to this parent
            current_children = set(parent.children_uids)
            new_children = args.children

            if set(new_children) != current_children:
                missing = current_children - set(new_children)
                extra = set(new_children) - current_children
                if missing:
                    _die(f"missing children in reorder list: {missing}")
                if extra:
                    _die(f"extra children not belonging to parent: {extra}")

            # Set new order
            parent.children_uids = list(new_children)

        except Exception as e:
            _die(f"node reorder failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "node reorder", args.output, size,
                 parent=args.parent,
                 children_count=len(args.children))
        return

    # ---- remove ----
    if args.action == "remove":
        if not args.graph:
            _die("node remove requires -g GRAPH")
        if not args.uid:
            _die("node remove requires --uid NODE_UID")
        if not args.output:
            _die("node remove requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        recursive = getattr(args, 'recursive', False)

        try:
            removed_count = 1
            if recursive:
                # Count descendants before removal
                desc_uids = graph.desc(args.uid)
                removed_count = 1 + len(desc_uids)

            graph.remove_node(args.uid, cascade=recursive)

        except Exception as e:
            _die(f"node remove failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "node remove", args.output, size,
                 uid=args.uid,
                 recursive=recursive,
                 nodes_removed=removed_count)
        return

    # ---- show ----
    if args.action == "show":
        if not args.graph:
            _die("node show requires -g GRAPH")
        if not args.uid:
            _die("node show requires --uid NODE_UID")

        graph = _load_graph(args.graph)

        try:
            node = graph.get_node(args.uid)
            result = node.to_serial_dict()
            result['parent'] = node.parent_uid
            result['children'] = list(node.children_uids)
        except Exception as e:
            _die(f"node show failed: {e}")

        content = yaml.dump(result, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)

        _summary("ok", "node show", args.output, size,
                 uid=args.uid)
        return

    _die(f"unknown node action: {args.action}")


# ================================================================== #
#  link                                                               #
# ================================================================== #


def cmd_link(args: argparse.Namespace) -> None:
    """Handle link subcommand with all actions."""

    # ---- create ----
    if args.action == "create":
        if not args.graph:
            _die("link create requires -g GRAPH")
        if not args.src:
            _die("link create requires --src SRC_UID")
        if not args.dst:
            _die("link create requires --dst DST_UID")
        if not args.intent:
            _die("link create requires --intent LINK_INTENT")
        if not args.output:
            _die("link create requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        # Build kwargs
        kwargs = {}
        if hasattr(args, 'uid') and args.uid:
            kwargs['uid'] = args.uid
        if hasattr(args, 'tag') and args.tag:
            kwargs['tag'] = args.tag
        if hasattr(args, 'shape') and args.shape:
            try:
                kwargs['shape'] = json.loads(args.shape)
            except json.JSONDecodeError as e:
                _die(f"invalid --shape JSON: {e}")
        if hasattr(args, 'parent') and args.parent:
            kwargs['parent'] = args.parent

        # Inter intentlink: either endpoint is qualified (graph_id:node_uid)
        is_inter = ":" in args.src or ":" in args.dst
        if is_inter:
            if kwargs.get('parent'):
                _die("inter intentlinks do not support --parent (refinement is intra-graph only)")
            inter_kwargs = {k: v for k, v in kwargs.items() if k in ("uid", "shape")}
            try:
                link = graph.add_inter_link(args.src, args.dst, args.intent, **inter_kwargs)
                link_uid = link.uid or f"{link.src}_{link.dst}"
            except Exception as e:
                _die(f"link create (inter) failed: {e}")
        else:
            try:
                link = graph.add_link(args.src, args.dst, args.intent, **kwargs)
                link_uid = link.uid
            except Exception as e:
                _die(f"link create failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "link create", args.output, size,
                 link_uid=link_uid,
                 src=args.src,
                 dst=args.dst)
        return

    # ---- set ----
    if args.action == "set":
        if not args.graph:
            _die("link set requires -g GRAPH")
        if not args.uid:
            _die("link set requires --uid LINK_UID")
        if not args.output:
            _die("link set requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        # Build update kwargs
        kwargs = {}
        if hasattr(args, 'intent') and args.intent:
            kwargs['intent'] = args.intent
        if hasattr(args, 'shape') and args.shape:
            try:
                kwargs['shape'] = json.loads(args.shape)
            except json.JSONDecodeError as e:
                _die(f"invalid --shape JSON: {e}")
        if hasattr(args, 'parent') and args.parent:
            kwargs['parent'] = args.parent

        if not kwargs:
            _die("link set requires at least one field to update")

        try:
            if args.uid in graph.inter_links:
                if kwargs.get('parent'):
                    _die("inter intentlinks do not support --parent (refinement is intra-graph only)")
                graph.update_inter_link(args.uid, **kwargs)
            else:
                graph.update_link(args.uid, **kwargs)
        except Exception as e:
            _die(f"link set failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "link set", args.output, size,
                 uid=args.uid,
                 fields_updated=list(kwargs.keys()))
        return

    # ---- remove ----
    if args.action == "remove":
        if not args.graph:
            _die("link remove requires -g GRAPH")
        if not args.uid:
            _die("link remove requires --uid LINK_UID")
        if not args.output:
            _die("link remove requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)

        try:
            if args.uid in graph.inter_links:
                graph.remove_inter_link(args.uid)
            else:
                graph.remove_link(args.uid)
        except Exception as e:
            _die(f"link remove failed: {e}")

        _save_graph(graph, args.output, args)

        size = {"words": 0, "lines": 0, "chars": 0}
        _summary("ok", "link remove", args.output, size,
                 uid=args.uid)
        return

    _die(f"unknown link action: {args.action}")


# ================================================================== #
#  Argument parser additions                                          #
# ================================================================== #


def add_parser(sub: Any) -> None:
    """Register the ``node`` and ``link`` subcommands on *sub*.

    Called from ``cli_impl.py``'s ``build_parser()``.
    """

    # ---- node ----
    p_node = sub.add_parser(
        "node",
        help="Node manipulation (create, set, reparent, reorder, remove, show)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool node create -g graph.json --uid PARSER --name 'Parser' --intent '...' --parent ROOT -o graph.json\n"
            "  ig-tool node create -g graph.json --uid ROOT --name 'Root' --intent 'System root' -o graph.json   # no --parent for root\n"
            "  ig-tool node set    -g graph.json --uid PARSER --intent 'Updated intent' -o graph.json\n"
            "  ig-tool node reparent -g graph.json --uid PARSER --under FRONTEND -o graph.json\n"
            "  ig-tool node remove -g graph.json --uid OBSOLETE --recursive -o graph.json\n"
            "  ig-tool node show   -g graph.json --uid PARSER\n"
            "Notes:\n"
            "  - --parent is OPTIONAL on create (omit for root nodes).\n"
            "  - --constraints / --examples are repeatable.\n"
            "  - For multiple edits in one call, use: ig-tool apply --batch ops.yaml.\n"
        ),
    )
    p_node.add_argument("action", choices=["create", "set", "reparent", "reorder", "remove", "show"])
    p_node.add_argument("-g", "--graph", help="Path to graph file (JSON or YAML)")
    p_node.add_argument("--uid", help="Node UID")
    p_node.add_argument("--name", help="Node name")
    p_node.add_argument("--intent", help="Node intent")
    p_node.add_argument("--parent", help="Parent UID (for create)")
    p_node.add_argument("--under", help="New parent UID (for reparent)")
    p_node.add_argument("--children", nargs="+", help="Ordered child UIDs (for reorder)")
    p_node.add_argument("--epistemic-state", help="Epistemic state")
    p_node.add_argument("--constraints", action="append", help="Constraint (repeatable)")
    p_node.add_argument("--examples", action="append", help="Example (repeatable)")
    p_node.add_argument("--design-notes", help="Design notes")
    p_node.add_argument("--effort", help="Effort/attention guidance (free text, e.g. 'high correctness critical')")
    p_node.add_argument("--impl-pointer", action="append", dest="impl_pointers",
                        help="Implementation pointer, repeatable. Grammar: path[::Symbol[.member]][ (lines X-Y)]")
    p_node.add_argument("--data-registry", help="Structured data store (JSON)")
    p_node.add_argument("--unset", action="append", metavar="FIELD",
                        help="Clear an optional field (repeatable, for set). Lists reset to [], scalars to null.")
    p_node.add_argument("--recursive", action="store_true", help="Recursive delete (for remove)")
    p_node.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_node.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")
    p_node.add_argument("-o", "--output", help="Output path")

    # ---- link ----
    p_link = sub.add_parser(
        "link",
        help="IntentLink manipulation (create, set, remove)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ig-tool link create -g graph.json --src PARSER --dst LEXER --intent 'parser depends on lexer' -o graph.json\n"
            "  ig-tool link set    -g graph.json --uid LINK_UID --intent 'Updated relation' -o graph.json\n"
            "  ig-tool link remove -g graph.json --uid LINK_UID -o graph.json\n"
            "Notes:\n"
            "  - 'create' uses --src and --dst; 'set' and 'remove' use --uid.\n"
            "  - For batch link creation, use: ig-tool apply --batch ops.yaml.\n"
        ),
    )
    p_link.add_argument("action", choices=["create", "set", "remove"])
    p_link.add_argument("-g", "--graph", help="Path to graph file (JSON or YAML)")
    p_link.add_argument("--uid", help="Link UID")
    p_link.add_argument("--src", help="Source node UID")
    p_link.add_argument("--dst", help="Destination node UID")
    p_link.add_argument("--intent", help="Link intent")
    p_link.add_argument("--tag", help="Link tag")
    p_link.add_argument("--shape", help="Link shape (JSON)")
    p_link.add_argument("--parent", help="Parent link UID (link refinement; intra-graph links only)")
    p_link.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_link.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")
    p_link.add_argument("-o", "--output", help="Output path")
