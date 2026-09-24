"""``ig-tool graph`` / ``ig-tool graph lens`` — graph-embedded named lenses (16 verbs).

Moved verbatim from ``cli_lens_commands.py`` (Phase 4: lens extraction).
Operates on lenses stored IN the graph file (``graph.lenses[name]``), as
opposed to ``cli/commands/lens.py``'s file-based agent-I/O lens.

``graph`` is a noun namespace whose only sub-subcommand today is ``lens``;
``cmd_graph`` dispatches to ``cmd_graph_lens`` on ``args.graph_action``.

Verbs (``graph lens <verb>``): list, show, create, delete, add-node,
remove-node, add-link, remove-link, set-lod, set-position, clear-position,
set-default, unset-default, project, reintegrate, validate.

Conservative move: ``cmd_graph_lens`` keeps its original shape (one function,
dispatching on ``args.action``) rather than the params/run/format split —
same rationale as ``cli/commands/lens.py``: high verb count entangled with
``argparse.Namespace``, zero-behavior-change move prioritized over the ideal
shape. Noted as a follow-up, not done here.
"""

from __future__ import annotations

import argparse
import math
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from intentgraph.errors import ClosureViolation, DuplicateLinkError
from intentgraph.models.graph import IntentGraph
from intentgraph.models.lens_config import LensConfig, LensNodeEntry, Position
from intentgraph.models.link import IntentLink, InterIntentLink
from intentgraph.models.node import IntentNode
from intentgraph.serial.json_yaml import load_graph, save_graph, dict_to_graph
from intentgraph.validation import validate_lenses

from ig_agents.cli.common import _die, _load_graph, _save_graph, _write_output, _summary


def cmd_graph(args: argparse.Namespace) -> None:
    """Dispatch graph sub-subcommand (currently only 'lens')."""
    if args.graph_action == "lens":
        cmd_graph_lens(args)
    else:
        _die(f"unknown graph action: {args.graph_action}")


def cmd_graph_lens(args: argparse.Namespace) -> None:
    """Handle graph lens subcommand (internal-lens operations)."""

    # ---- show (internal-lens mode) ----
    if args.action == "show":
        if not args.graph:
            _die("graph lens show requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("graph lens show requires --lens LENS_NAME")
        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        lc = graph.lenses[lens_name]
        report = {
            "name": lc.name,
            "description": lc.description,
            "target_uids": lc.target_uids,
            "node_count": len(lc.nodes),
            "nodes": lc.nodes,
            "intentlinks": lc.intentlinks,
            "is_default": graph.meta.get("default_lens") == lens_name,
        }
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)
        _summary("ok", "graph lens show", args.output, size,
                 lens=lens_name, nodes=len(lc.nodes))
        return

    # ---- set-lod (internal-lens mode) ----
    if args.action == "set-lod":
        if not args.graph:
            _die("graph lens set-lod requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("graph lens set-lod requires --lens LENS_NAME")
        if not args.uid:
            _die("graph lens set-lod requires --uid NODE_UID")
        if not args.lod:
            _die("graph lens set-lod requires --lod (skeleton|lean|full)")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        try:
            graph.lenses[lens_name].set_lod(args.uid, args.lod)
        except Exception as e:
            _die(f"graph lens set-lod failed: {e}")

        save_graph(graph, args.graph)
        _summary("ok", "graph lens set-lod", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, uid=args.uid, new_lod=args.lod)
        return

    # ---- list (internal lenses) ----
    if args.action == "list":
        if not args.graph:
            _die("lens list requires -g GRAPH")

        graph = _load_graph(args.graph)
        items: list[dict[str, Any]] = []
        default_lens_name = graph.meta.get("default_lens")
        for name, lc in graph.lenses.items():
            items.append({
                "name": name,
                "description": lc.description,
                "nodes": len(lc.nodes),
                "intentlinks": len(lc.intentlinks),
                "target_uids": lc.target_uids,
                "is_default": name == default_lens_name,
            })
        report = {
            "graph": args.graph,
            "lens_count": len(items),
            "default_lens": default_lens_name,
            "lenses": items,
        }
        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)
        _summary("ok", "lens list", args.output, size,
                 lens_count=len(items))
        return

    # ---- create (internal lens) ----
    if args.action == "create":
        if not args.graph:
            _die("lens create requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None) or getattr(args, "name", None)
        if not lens_name:
            _die("lens create requires --name LENS_NAME")

        graph = _load_graph(args.graph)
        description = getattr(args, "description", None)
        lc = LensConfig(name=lens_name, description=description)
        graph.add_lens(lc)
        save_graph(graph, args.graph)

        _summary("ok", "lens create", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name)
        return

    # ---- delete (internal lens) ----
    if args.action == "delete":
        if not args.graph:
            _die("lens delete requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens delete requires --lens LENS_NAME")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        graph.remove_lens(lens_name)
        save_graph(graph, args.graph)

        _summary("ok", "lens delete", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name)
        return

    # ---- add-node (internal lens) ----
    if args.action == "add-node":
        if not args.graph:
            _die("lens add-node requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens add-node requires --lens LENS_NAME")
        if not args.uid:
            _die("lens add-node requires --uid NODE_UID")
        if not args.lod:
            _die("lens add-node requires --lod (skeleton|lean|full)")

        # LENSSCHEMA.IGCMDS: --x and --y must be provided together or not at all
        x_val = getattr(args, "x", None)
        y_val = getattr(args, "y", None)
        if (x_val is None) != (y_val is None):
            _die("lens add-node: --x and --y must both be provided, or neither")
        position: Position | None = None
        if x_val is not None and y_val is not None:
            if not math.isfinite(x_val) or not math.isfinite(y_val):
                _die("lens add-node: --x and --y must be finite numbers (V-POS1)")
            position = Position(x=x_val, y=y_val)

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        try:
            graph.lenses[lens_name].add_node(args.uid, args.lod, graph)
            if position is not None:
                entry = graph.lenses[lens_name].nodes[args.uid]
                graph.lenses[lens_name].nodes[args.uid] = LensNodeEntry(
                    lod=entry.lod, position=position
                )
        except Exception as e:
            _die(f"lens add-node failed: {e}")

        save_graph(graph, args.graph)
        _summary("ok", "lens add-node", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, uid=args.uid, lod=args.lod,
                 position={"x": x_val, "y": y_val} if position else None,
                 total_nodes=len(graph.lenses[lens_name].nodes))
        return

    # ---- set-position (internal lens) ----
    # PIG: LENSSCHEMA.IGCMDS
    if args.action == "set-position":
        if not args.graph:
            _die("lens set-position requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens set-position requires --lens LENS_NAME")
        if not args.uid:
            _die("lens set-position requires --uid NODE_UID")
        x_val = getattr(args, "x", None)
        y_val = getattr(args, "y", None)
        if x_val is None:
            _die("lens set-position requires --x FLOAT")
        if y_val is None:
            _die("lens set-position requires --y FLOAT")
        if not math.isfinite(x_val) or not math.isfinite(y_val):
            _die("lens set-position: --x and --y must be finite numbers (V-POS1)")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        lc = graph.lenses[lens_name]
        if args.uid not in lc.nodes:
            _die(f"lens set-position: node '{args.uid}' is not in lens '{lens_name}'")

        existing = lc.nodes[args.uid]
        lc.nodes[args.uid] = LensNodeEntry(
            lod=existing.lod, position=Position(x=x_val, y=y_val)
        )
        save_graph(graph, args.graph)
        _summary("ok", "lens set-position", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, uid=args.uid, x=x_val, y=y_val)
        return

    # ---- clear-position (internal lens) ----
    # PIG: LENSSCHEMA.IGCMDS
    if args.action == "clear-position":
        if not args.graph:
            _die("lens clear-position requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens clear-position requires --lens LENS_NAME")
        if not args.uid:
            _die("lens clear-position requires --uid NODE_UID")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        lc = graph.lenses[lens_name]
        if args.uid not in lc.nodes:
            _die(f"lens clear-position: node '{args.uid}' is not in lens '{lens_name}'")

        existing = lc.nodes[args.uid]
        lc.nodes[args.uid] = LensNodeEntry(lod=existing.lod, position=None)
        save_graph(graph, args.graph)
        _summary("ok", "lens clear-position", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, uid=args.uid)
        return

    # ---- remove-node (internal lens) ----
    if args.action == "remove-node":
        if not args.graph:
            _die("lens remove-node requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens remove-node requires --lens LENS_NAME")
        if not args.uid:
            _die("lens remove-node requires --uid NODE_UID")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        try:
            graph.lenses[lens_name].remove_node(args.uid, graph)
        except Exception as e:
            _die(f"lens remove-node failed: {e}")

        save_graph(graph, args.graph)
        _summary("ok", "lens remove-node", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, uid=args.uid,
                 remaining_nodes=len(graph.lenses[lens_name].nodes))
        return

    # ---- add-link (internal lens) ----
    if args.action == "add-link":
        if not args.graph:
            _die("lens add-link requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens add-link requires --lens LENS_NAME")
        if not args.uid:
            _die("lens add-link requires --uid LINK_UID")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        try:
            graph.lenses[lens_name].add_link(args.uid, graph)
        except ClosureViolation as e:
            _die(f"lens add-link: closure violation — {e}")
        except Exception as e:
            _die(f"lens add-link failed: {e}")

        save_graph(graph, args.graph)
        _summary("ok", "lens add-link", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, link_uid=args.uid)
        return

    # ---- remove-link (internal lens) ----
    if args.action == "remove-link":
        if not args.graph:
            _die("lens remove-link requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens remove-link requires --lens LENS_NAME")
        if not args.uid:
            _die("lens remove-link requires --uid LINK_UID")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        graph.lenses[lens_name].remove_link(args.uid)
        save_graph(graph, args.graph)

        _summary("ok", "lens remove-link", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, link_uid=args.uid)
        return

    # ---- set-default ----
    if args.action == "set-default":
        if not args.graph:
            _die("lens set-default requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens set-default requires --lens LENS_NAME")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")
        graph.meta["default_lens"] = lens_name
        save_graph(graph, args.graph)

        _summary("ok", "lens set-default", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 default_lens=lens_name)
        return

    # ---- unset-default ----
    if args.action == "unset-default":
        if not args.graph:
            _die("lens unset-default requires -g GRAPH")

        graph = _load_graph(args.graph)
        previous = graph.meta.pop("default_lens", None)
        save_graph(graph, args.graph)

        _summary("ok", "lens unset-default", None,
                 {"words": 0, "lines": 0, "chars": 0},
                 previous_default=previous)
        return

    # ---- validate (lens-specific) ----
    if args.action == "validate":
        if not args.graph:
            _die("lens validate requires -g GRAPH")

        graph = _load_graph(args.graph)
        # Pass ig_path so V-CG cross-IG rules can resolve meta.intent_resources
        all_issues = validate_lenses(graph, ig_path=Path(args.graph).resolve())

        # Optionally filter to a specific lens
        target_lens_name = getattr(args, "lens_name", None)
        if target_lens_name:
            all_issues = [
                i for i in all_issues
                if i.get("lens") == target_lens_name or "lens" not in i
            ]

        errors = [i for i in all_issues if i["severity"] == "error"]
        warnings_list = [i for i in all_issues if i["severity"] == "warning"]

        report = {
            "graph": args.graph,
            "lens_count": len(graph.lenses),
            "issues": len(all_issues),
            "errors": len(errors),
            "warnings": len(warnings_list),
        }
        if all_issues:
            report["details"] = all_issues

        content = yaml.dump(report, default_flow_style=False, allow_unicode=True, sort_keys=False)
        size = _write_output(content, args.output)

        status = "error" if errors else ("warning" if warnings_list else "ok")
        _summary(status, "lens validate", args.output, size,
                 errors=len(errors), warnings=len(warnings_list))

        if errors:
            sys.exit(1)
        return

    # ---- project ----
    if args.action == "project":
        if not args.graph:
            _die("lens project requires -g GRAPH")
        lens_name = getattr(args, "lens_name", None)
        if not lens_name:
            _die("lens project requires --lens LENS_NAME")
        if not args.output:
            _die("lens project requires -o OUTPUT_GRAPH")

        graph = _load_graph(args.graph)
        if lens_name not in graph.lenses:
            _die(f"lens '{lens_name}' not found in graph")

        lc = graph.lenses[lens_name]
        reduced = _project_lens(graph, lc, args.graph, lens_name)
        save_graph(reduced, args.output)

        _summary("ok", "lens project", args.output,
                 {"words": 0, "lines": 0, "chars": 0},
                 lens=lens_name, nodes=reduced.node_count(),
                 links=reduced.link_count())
        return

    # ---- reintegrate ----
    if args.action == "reintegrate":
        if not args.input:
            _die("lens reintegrate requires -i DERIVED_IG")

        derived_path = Path(args.input)
        if not derived_path.exists():
            _die(f"derived IG not found: {args.input}")

        try:
            derived = load_graph(derived_path)
        except Exception as e:
            _die(f"failed to load derived IG: {e}")

        derived_from = derived.meta.get("derived_from")
        if not derived_from:
            _die("derived IG has no meta.derived_from — not a reduction")

        parent_path_str = derived_from.get("of")
        if not parent_path_str:
            _die("meta.derived_from.of is missing")

        # Resolve parent path relative to derived IG's directory
        parent_path = (derived_path.parent / parent_path_str).resolve()
        if args.output:
            # Override: write to explicit output path instead of in-place
            parent_path_str_resolved = args.output
            parent_path_for_load = parent_path
        else:
            parent_path_str_resolved = str(parent_path)
            parent_path_for_load = parent_path

        if not parent_path_for_load.exists():
            _die(f"parent IG not found: {parent_path_for_load}")

        try:
            parent = load_graph(parent_path_for_load)
        except Exception as e:
            _die(f"failed to load parent IG: {e}")
        # Provenance baseline so reintegration stamps only actual changes
        from intentgraph.ops.provenance import content_snapshot
        parent._provenance_baseline = content_snapshot(parent)

        # Perform reintegration (Phase-1 scope)
        try:
            _reintegrate(parent, derived)
        except Exception as e:
            _die(str(e))

        out_path = args.output or str(parent_path_for_load)
        _save_graph(parent, out_path, args)

        _summary("ok", "lens reintegrate", out_path,
                 {"words": 0, "lines": 0, "chars": 0},
                 parent=str(parent_path_for_load))
        return

    _die(f"unknown lens action: {args.action}")


# ================================================================== #
#  Internal helpers for project / reintegrate                         #
# ================================================================== #


def _project_lens(
    graph: IntentGraph,
    lc: LensConfig,
    source_path: str,
    lens_name: str,
) -> IntentGraph:
    """Build a reduced IG from a graph + LensConfig.

    Spec §9: copies nodes in lc.nodes, treearcs between them, and
    intentlinks in lc.intentlinks. Sets meta.derived_from.
    """
    reduced_meta: dict[str, Any] = {
        "name": f"{graph.meta.get('name', 'Unknown')} — {lens_name} view",
        "derived_from": {"of": source_path, "via_lens": lens_name},
    }
    # Carry over other meta fields (excluding structural ones we set ourselves)
    for k, v in graph.meta.items():
        if k not in ("name", "derived_from"):
            reduced_meta[k] = v

    # Build reduced graph manually (don't call attach() to avoid UID validation
    # issues for orphan nodes in the subset)
    reduced = IntentGraph(meta=reduced_meta)

    # Copy nodes that are in the lens
    for uid in lc.nodes:
        if uid not in graph.nodes:
            continue  # skip stale refs
        src_node = graph.nodes[uid]
        node_data = src_node.to_serial_dict()
        new_node = IntentNode.from_serial_dict(node_data)
        new_node.parent_uid = None
        new_node.children_uids = []
        reduced._nodes[uid] = new_node

    # Rebuild treearcs between nodes that are both in the lens subset
    for uid in lc.nodes:
        if uid not in reduced._nodes:
            continue
        src_node = graph.nodes.get(uid)
        if not src_node:
            continue
        # Set parent_uid if parent is also in the reduced graph
        if src_node.parent_uid and src_node.parent_uid in reduced._nodes:
            reduced._nodes[uid].parent_uid = src_node.parent_uid
            parent_node = reduced._nodes[src_node.parent_uid]
            if uid not in parent_node.children_uids:
                parent_node.children_uids.append(uid)

    # Copy intentlinks that are in the lens
    for link_uid in lc.intentlinks:
        link = graph.links.get(link_uid)
        if link:
            link_data = link.to_serial_dict()
            new_link = IntentLink.from_serial_dict(link_data)
            reduced._links[link_uid] = new_link
        else:
            inter_link = graph.inter_links.get(link_uid)
            if inter_link:
                link_data = inter_link.to_serial_dict()
                new_link = InterIntentLink.from_serial_dict(link_data)
                reduced._inter_links[link_uid] = new_link

    # Include the via_lens in the reduced IG (Spec §9)
    reduced.lenses[lens_name] = deepcopy(lc)

    return reduced


def _reintegrate(parent: IntentGraph, derived: IntentGraph) -> None:
    """Apply changes from a derived IG back to the parent IG.

    Phase-1 scope (Spec §9):
    - Supported: node content edits; add new nodes (with parent in parent IG);
      add/edit intentlinks.
    - NOT supported (error): node deletion, treearc reparenting, link endpoint changes.

    Raises ValueError with `reintegrate: operation '...' not supported in Phase 1`
    for unsupported operations.
    """
    content_fields = [
        "name", "intent", "epistemic_state", "constraints", "examples",
        "design_notes", "effort", "impl_pointers", "history", "data_registry",
    ]

    # --- Pass 1: nodes ---
    for uid, derived_node in derived.nodes.items():
        if uid in parent.nodes:
            parent_node = parent.nodes[uid]

            # Check for reparenting (Phase-1 restriction)
            derived_parent = derived_node.parent_uid
            parent_parent = parent_node.parent_uid
            if derived_parent != parent_parent:
                raise ValueError(
                    f"reintegrate: operation 'treearc_reparenting' not supported in Phase 1 "
                    f"(node '{uid}': parent changed from '{parent_parent}' to '{derived_parent}')"
                )

            # Apply content edits
            updates: dict[str, Any] = {}
            for field in content_fields:
                derived_val = getattr(derived_node, field, None)
                parent_val = getattr(parent_node, field, None)
                if derived_val != parent_val:
                    updates[field] = derived_val
            if updates:
                parent.update_node(uid, **updates)
        else:
            # New node — must specify a parent present in parent IG
            derived_parent_uid = derived_node.parent_uid
            if derived_parent_uid is None:
                raise ValueError(
                    f"reintegrate: new node '{uid}' has no parent — "
                    "cannot add a root node via reintegrate"
                )
            if derived_parent_uid not in parent.nodes:
                raise ValueError(
                    f"reintegrate: new node '{uid}' has parent '{derived_parent_uid}' "
                    "which does not exist in the parent IG"
                )
            # Create node with content fields
            kwargs: dict[str, Any] = {}
            for field in content_fields:
                val = getattr(derived_node, field, None)
                if val is not None and val != [] and val != {}:
                    kwargs[field] = val
            parent.add_node_under(
                uid=uid,
                name=derived_node.name,
                intent=derived_node.intent,
                parent_uid=derived_parent_uid,
                **{k: v for k, v in kwargs.items()
                   if k not in ("name", "intent")},
            )

    # --- Check for node deletions (Phase-1 restriction) ---
    # A node that was covered by the lens in the *parent* IG but is absent from
    # the derived IG's nodes list is a deletion attempt.  We compare against
    # parent.lenses[via_lens].nodes (the pre-edit, authoritative set) rather
    # than derived.lenses[via_lens].nodes, which a user could have mutated
    # simultaneously — that is the coordinated-deletion bypass (E5 bug fix).
    derived_from_meta = derived.meta.get("derived_from", {})
    via_lens_name = derived_from_meta.get("via_lens", "")
    source_lens_nodes: set[str] = set()
    if via_lens_name and via_lens_name in parent.lenses:
        source_lens_nodes = set(parent.lenses[via_lens_name].nodes.keys())

    for uid in source_lens_nodes:
        if uid in parent.nodes and uid not in derived.nodes:
            raise ValueError(
                f"reintegrate: operation 'node_deletion' not supported in Phase 1 "
                f"(node '{uid}' absent from derived IG but present in parent). "
                f"Removed UIDs: [{uid}]"
            )

    # --- Pass 2: intentlinks ---
    for link_uid, derived_link in derived.links.items():
        if link_uid in parent.links:
            parent_link = parent.links[link_uid]
            # Check endpoint changes (Phase-1 restriction)
            if derived_link.src != parent_link.src or derived_link.dst != parent_link.dst:
                raise ValueError(
                    f"reintegrate: operation 'link_endpoint_change' not supported in Phase 1 "
                    f"(link '{link_uid}': endpoints changed)"
                )
            # Update content (intent, shape)
            if derived_link.intent != parent_link.intent:
                parent.update_link(link_uid, intent=derived_link.intent)
        else:
            # New link — both endpoints must now be in parent
            if derived_link.src not in parent.nodes:
                raise ValueError(
                    f"reintegrate: new link '{link_uid}' has src '{derived_link.src}' "
                    "which does not exist in the parent IG"
                )
            if derived_link.dst not in parent.nodes:
                raise ValueError(
                    f"reintegrate: new link '{link_uid}' has dst '{derived_link.dst}' "
                    "which does not exist in the parent IG"
                )
            try:
                parent.add_link(
                    derived_link.src,
                    derived_link.dst,
                    derived_link.intent,
                    uid=link_uid,
                )
            except DuplicateLinkError:
                pass  # already exists — idempotent


def add_parser(sub: Any) -> None:
    """Register the ``graph`` subcommand (noun namespace; ``graph lens`` is the
    only sub-subcommand today, internal/persistent lens management, 16 verbs)."""
    p_graph = sub.add_parser(
        "graph",
        help="Graph-embedded operations. Currently: graph lens <verb>",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Sub-subcommands:\n"
            "  graph lens <verb>     Manage named lenses persisted INSIDE the graph file.\n"
            "Note: For agent I/O lenses (separate file), use 'ig-tool lens' instead.\n"
        ),
    )
    graph_sub = p_graph.add_subparsers(dest="graph_action", required=True)

    # graph lens — internal lens management (16 verbs)
    p_gl = graph_sub.add_parser(
        "lens",
        help=(
            "Internal (graph-embedded) lens operations: "
            "list, show, create, delete, add-node, remove-node, set-lod, "
            "add-link, remove-link, set-default, unset-default, "
            "project, reintegrate, validate, set-position, clear-position."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Lifecycle groups:\n"
            "  Lens lifecycle:    list, create, delete\n"
            "  Lens content:      add-node, remove-node, add-link, remove-link, set-lod\n"
            "  Canvas layout:     set-position, clear-position\n"
            "  Default selection: set-default, unset-default\n"
            "  Round-trip:        project, reintegrate\n"
            "  Inspection:        show, validate\n"
            "Examples:\n"
            "  ig-tool graph lens list   -g graph.json\n"
            "  ig-tool graph lens create -g graph.json --name auth-flow --description 'Auth subsystem'\n"
            "  ig-tool graph lens add-node -g graph.json --lens auth-flow --uid PARSER --lod full --x 100 --y 200\n"
            "  ig-tool graph lens show   -g graph.json --lens auth-flow -o view.yaml\n"
            "  ig-tool graph lens project -g graph.json --lens auth-flow -o auth_subset.json\n"
            "Notes:\n"
            "  - Operates on lenses stored IN the graph (graph.lenses[name]). For file-based lenses use 'ig-tool lens'.\n"
            "  - --lens NAME is required for most actions (exceptions: list, create, unset-default, validate without filter, reintegrate).\n"
            "  - Consumed by the VS Code extension for persistent named views.\n"
        ),
    )
    p_gl.add_argument("action", choices=[
        # Internal-lens management (14 unique verbs)
        "list", "create", "delete", "add-node", "remove-node",
        "add-link", "remove-link", "set-default", "unset-default",
        "project", "reintegrate", "validate",
        # Position management (PIG: LENSSCHEMA.IGCMDS)
        "set-position", "clear-position",
        # Shared verbs (in internal-lens context)
        "show", "set-lod",
    ])
    p_gl.add_argument("-g", "--graph", help="Path to IG file (JSON or YAML)")
    p_gl.add_argument("--lens", dest="lens_name",
                      help="Internal lens name (required for most operations)")
    p_gl.add_argument("-i", "--input", help="Input path (for reintegrate)")
    p_gl.add_argument("-m", "--message", help="One-liner history note for this change (commit-style)")
    p_gl.add_argument("--role", help="Agent role for provenance (history who = agent:<role>)")
    p_gl.add_argument("--name", help="Lens name (for create)")
    p_gl.add_argument("--description", help="Lens description (for create)")
    p_gl.add_argument("--uid", help="Node or link UID")
    p_gl.add_argument("--lod", choices=["skeleton", "lean", "full"], help="LOD level")
    p_gl.add_argument("--x", type=float, help="Position x coordinate (for set-position, add-node)")
    p_gl.add_argument("--y", type=float, help="Position y coordinate (for set-position, add-node)")
    p_gl.add_argument("-o", "--output", help="Output path")
