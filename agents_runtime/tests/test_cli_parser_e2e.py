"""Parser-level, end-to-end tests (full-chain: parser → Namespace → DISPATCH).

The existing test suite mostly calls ``cmd_xxx(hand_built_namespace)``
directly, bypassing the real argparse parser entirely. This is exactly why
Bug 1 (``apply --batch`` silently dropping ``--role``) was invisible to tests:
no test ever exercised "parser.parse_args ([...]) actually produces a Namespace
with role set, AND that value survives all the way through to the batch
executor."

Each test class here does the full chain a real invocation exercises:

    build_parser().parse_args([...]) -> Namespace
        -> assert the Namespace has the expected fields
        -> feed that Namespace into the real DISPATCH handler
        -> assert the end-to-end effect (e.g. --role actually appears
           in history, a node is actually gone from the saved graph).

Covers, per the task brief, at minimum: ``apply`` (both ``-i`` and
``--batch`` modes, with ``--role``), ``node remove``, ``link remove``,
``tree`` (``-o`` mode).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ig_agents.cli import build_parser, DISPATCH
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import load_graph, save_graph


# ================================================================== #
#  Shared fixture graph                                              #
# ================================================================== #


def _build_graph(tmp_path: Path) -> Path:
    g = IntentGraph(meta={"name": "test"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("A", "A", "A intent", parent_uid="ROOT")
    g.add_node_under("B", "B", "B intent", parent_uid="ROOT")
    g.add_link("A", "B", "A relates to B")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    return path


def _parse(argv: list[str]):
    """Parse argv with the real parser and return the Namespace."""
    parser = build_parser()
    return parser.parse_args(argv)


def _dispatch(ns) -> None:
    """Run the real DISPATCH handler for the parsed Namespace's command."""
    handler = DISPATCH[ns.command]
    handler(ns)


# ================================================================== #
#  apply -i, with --role                                              #
# ================================================================== #


class TestApplyDashIParserE2E:
    """``ig-tool apply -g G -i EDITS -o OUT --role R`` — real parser, real
    dispatch, real effect (history stamped on the modified node).
    """

    def test_namespace_has_expected_fields(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        edits_path = tmp_path / "edits.yaml"
        edits_path.write_text("dummy")
        out_path = tmp_path / "out.json"

        ns = _parse([
            "apply", "-g", str(graph_path), "-i", str(edits_path),
            "-o", str(out_path), "--role", "steward",
        ])

        assert ns.command == "apply"
        assert ns.graph == str(graph_path)
        assert ns.input == str(edits_path)
        assert ns.batch is None
        assert ns.output == str(out_path)
        assert ns.role == "steward"
        assert ns.dry_run is False

    def test_role_survives_to_history(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        edits_path = tmp_path / "edits.yaml"
        # §2 full-frontier agent-text format: update A's intent.
        edits_path.write_text(yaml.dump({
            "frontier": {"name": "test"},
            "nodes": [
                {"uid": "A", "intent": "Updated A intent via parser E2E"},
            ],
            "intentlinks": [],
        }, sort_keys=False))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "apply", "-g", str(graph_path), "-i", str(edits_path),
            "-o", str(out_path), "--role", "steward",
        ])
        _dispatch(ns)

        updated = load_graph(str(out_path))
        node = updated.get_node("A")
        assert node.intent == "Updated A intent via parser E2E"
        assert node.history, "expected --role to stamp a history entry"
        assert any(h.who == "agent:steward" for h in node.history), (
            f"expected who='agent:steward' in history, got: {node.history}"
        )


# ================================================================== #
#  apply --batch, with --role (the exact Bug 1 shape)                #
# ================================================================== #


class TestApplyBatchParserE2E:
    """``ig-tool apply -g G --batch OPS -o OUT --role R`` — this is the exact
    surface where Bug 1 lived: ``cmd_apply`` hand-built a synthetic Namespace
    for ``cmd_batch`` that omitted ``role``, so ``--role`` parsed fine but
    was silently dropped before batch execution ever ran.
    """

    def test_namespace_has_expected_fields(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({"operations": []}))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "apply", "-g", str(graph_path), "--batch", str(batch_path),
            "-o", str(out_path), "--role", "extractor",
        ])

        assert ns.command == "apply"
        assert ns.graph == str(graph_path)
        assert ns.input is None
        assert ns.batch == str(batch_path)
        assert ns.output == str(out_path)
        assert ns.role == "extractor", (
            "the real parser must produce role='extractor' in the Namespace "
            "(this is necessary but NOT sufficient — see "
            "test_role_survives_through_batch_dispatch for the part Bug 1 "
            "actually broke: the value being consumed downstream)"
        )
        assert ns.dry_run is False

    def test_role_survives_through_batch_dispatch(self, tmp_path: Path):
        """The full chain: parse -> DISPATCH["apply"] -> batch executor ->
        history entry actually present on disk. This is the test that would
        have caught Bug 1 — a hand-built Namespace in a unit test can't
        detect a parser-vs-delegation field drop, because the test builds
        the (correct) Namespace by hand instead of asking the parser for one.
        """
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {
                    "op": "node.create",
                    "uid": "C",
                    "name": "C",
                    "intent": "C intent",
                    "parent": "ROOT",
                },
            ],
        }))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "apply", "-g", str(graph_path), "--batch", str(batch_path),
            "-o", str(out_path), "--role", "extractor",
        ])
        _dispatch(ns)

        updated = load_graph(str(out_path))
        node = updated.get_node("C")
        assert node.history, (
            "expected a history entry stamped from --role, parsed and "
            "dispatched through the REAL parser/DISPATCH path (Bug 1 regression)"
        )
        assert any(h.who == "agent:extractor" for h in node.history), (
            f"expected who='agent:extractor' in history, got: {node.history}"
        )

    def test_no_role_means_no_history(self, tmp_path: Path):
        """Without --role, the parser must produce role=None; provenance is
        still captured at the write boundary, attributed to a human actor.
        """
        graph_path = _build_graph(tmp_path)
        batch_path = tmp_path / "batch.yaml"
        batch_path.write_text(yaml.dump({
            "operations": [
                {
                    "op": "node.create",
                    "uid": "D",
                    "name": "D",
                    "intent": "D intent",
                    "parent": "ROOT",
                },
            ],
        }))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "apply", "-g", str(graph_path), "--batch", str(batch_path),
            "-o", str(out_path),
        ])
        assert ns.role is None
        _dispatch(ns)

        updated = load_graph(str(out_path))
        node = updated.get_node("D")
        assert node.history, "write-boundary provenance must stamp every save"
        assert all(not h.who.startswith("agent:") for h in node.history), (
            f"no --role means a human actor, got: {node.history}"
        )


# ================================================================== #
#  node remove                                                       #
# ================================================================== #


class TestNodeRemoveParserE2E:
    """``ig-tool node remove -g G --uid UID -o OUT`` — real parser + real
    dispatch; asserts the node is actually gone from the saved graph.
    """

    def test_namespace_has_expected_fields(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "out.json"

        ns = _parse([
            "node", "remove", "-g", str(graph_path), "--uid", "B",
            "-o", str(out_path),
        ])

        assert ns.command == "node"
        assert ns.action == "remove"
        assert ns.graph == str(graph_path)
        assert ns.uid == "B"
        assert ns.output == str(out_path)
        assert ns.recursive is False

    def test_node_actually_removed(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "out.json"

        ns = _parse([
            "node", "remove", "-g", str(graph_path), "--uid", "B",
            "-o", str(out_path),
        ])
        _dispatch(ns)

        updated = load_graph(str(out_path))
        assert "B" not in updated.nodes
        assert "A" in updated.nodes  # unrelated node untouched

    def test_recursive_flag_survives_to_dispatch(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        # Give A a child so --recursive has something to prove.
        g = load_graph(str(graph_path))
        g.add_node_under("A.1", "A.1", "A.1 intent", parent_uid="A")
        save_graph(g, graph_path)

        out_path = tmp_path / "out.json"

        ns = _parse([
            "node", "remove", "-g", str(graph_path), "--uid", "A",
            "--recursive", "-o", str(out_path),
        ])
        assert ns.recursive is True
        _dispatch(ns)

        updated = load_graph(str(out_path))
        assert "A" not in updated.nodes
        assert "A.1" not in updated.nodes, "recursive remove must cascade to descendants"


# ================================================================== #
#  link remove                                                       #
# ================================================================== #


class TestLinkRemoveParserE2E:
    """``ig-tool link remove -g G --uid UID -o OUT`` — real parser + real
    dispatch; asserts the link is actually gone from the saved graph.
    """

    def test_namespace_has_expected_fields(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        g = load_graph(str(graph_path))
        link_uid = next(iter(g.links))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "link", "remove", "-g", str(graph_path), "--uid", link_uid,
            "-o", str(out_path),
        ])

        assert ns.command == "link"
        assert ns.action == "remove"
        assert ns.graph == str(graph_path)
        assert ns.uid == link_uid
        assert ns.output == str(out_path)

    def test_link_actually_removed(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        g = load_graph(str(graph_path))
        link_uid = next(iter(g.links))
        out_path = tmp_path / "out.json"

        ns = _parse([
            "link", "remove", "-g", str(graph_path), "--uid", link_uid,
            "-o", str(out_path),
        ])
        _dispatch(ns)

        updated = load_graph(str(out_path))
        assert link_uid not in updated.links
        # Nodes on either end of the removed link must survive untouched.
        assert "A" in updated.nodes
        assert "B" in updated.nodes


# ================================================================== #
#  tree -o                                                            #
# ================================================================== #


class TestTreeParserE2E:
    """``ig-tool tree -g G -o OUT`` — real parser + real dispatch; regression
    guard for Bug 3 (KeyError('words') after the file was already written),
    this time reached via the real parser instead of a hand-built Namespace.
    """

    def test_namespace_has_expected_fields(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "tree.txt"

        ns = _parse([
            "tree", "-g", str(graph_path), "-o", str(out_path),
            "--show-intent", "--width", "100",
        ])

        assert ns.command == "tree"
        assert ns.graph == str(graph_path)
        assert ns.output == str(out_path)
        assert ns.show_intent is True
        assert ns.width == 100
        assert ns.root is None
        assert ns.style == "simple"

    def test_does_not_crash_and_writes_file(self, tmp_path: Path, capsys):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "tree.txt"

        ns = _parse(["tree", "-g", str(graph_path), "-o", str(out_path)])
        _dispatch(ns)

        assert out_path.exists()
        assert "Root" in out_path.read_text()

        captured = capsys.readouterr()
        summary = yaml.safe_load(captured.out)
        assert summary["status"] == "ok"
        assert "output_size" in summary
        assert "words" in summary["output_size"]
