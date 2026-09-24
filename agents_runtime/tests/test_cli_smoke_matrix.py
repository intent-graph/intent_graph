"""Command smoke matrix (test strategy: representative subcommands in both output modes).

Parametrized end-to-end test: for a representative set of subcommands, run
each in both output modes -- ``-o FILE`` and stdout-only -- through the REAL
argparse parser and the REAL ``DISPATCH`` handler (not a hand-built
Namespace). Assert:

  - exit code 0 (no uncaught exception / no ``SystemExit(nonzero)``)
  - the output file exists when ``-o`` was requested
  - the stdout summary parses as valid YAML
  - the summary contains the baseline contract keys (``status``, ``command``)
    and, when ``-o`` was used, ``output``/``output_size`` with a ``words`` key

This is exactly the layer that would have caught Bug 3: ``tree -o`` wrote its
file successfully, then raised a bare ``KeyError('words')`` while building the
summary -- a crash that ONLY happens in ``-o`` mode (stdout mode never touches
that code path), so a test matrix that skips the ``-o`` cell for any command is
blind to this whole defect class.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
import yaml

from ig_agents.cli import build_parser, DISPATCH
from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import save_graph


# ================================================================== #
#  Shared fixture graph                                              #
# ================================================================== #


def _build_graph(tmp_path: Path) -> Path:
    g = IntentGraph(meta={"name": "smoke"})
    g.add_node("ROOT", "Root", "root intent")
    g.add_node_under("A", "A", "A intent", parent_uid="ROOT")
    g.add_node_under("B", "B", "B intent", parent_uid="ROOT")
    g.add_link("A", "B", "A relates to B")

    path = tmp_path / "graph.json"
    save_graph(g, path)
    return path


def _run(argv: list[str]) -> tuple[int, str]:
    """Parse argv with the real parser, dispatch through the real DISPATCH
    table, and return (exit_code, captured_stdout). Mirrors what ``main()``
    does, minus telemetry, so failures surface the same way a real
    invocation would.
    """
    import contextlib
    import io

    parser = build_parser()
    ns = parser.parse_args(argv)
    handler = DISPATCH[ns.command]

    buf = io.StringIO()
    exit_code = 0
    try:
        with contextlib.redirect_stdout(buf):
            handler(ns)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    return exit_code, buf.getvalue()


def _extract_summary_block(stdout: str) -> str:
    """Isolate the ``_summary()`` YAML block from full captured stdout.

    Content-emitting commands (``tree``, ``query --overview``, ...) print
    their rendered content to stdout FIRST when no ``-o`` is given, then
    ``_summary()`` appends its own compact YAML block after it -- both go to
    the same stream. ``_summary``'s dict always starts with the ``status:``
    key (see ``ig_agents.cli.common._summary``), so the block we want is
    everything from the last ``status:`` line onward.
    """
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("status:"):
            return "\n".join(lines[i:])
    return stdout


def _assert_valid_summary(stdout: str, output_path: Path | None) -> dict:
    summary_block = _extract_summary_block(stdout)
    summary = yaml.safe_load(summary_block)
    assert isinstance(summary, dict), f"summary did not parse as a YAML mapping: {stdout!r}"
    assert "status" in summary, f"summary missing 'status' key: {summary}"
    assert "command" in summary, f"summary missing 'command' key: {summary}"
    if output_path is not None:
        assert "output" in summary, f"summary missing 'output' key when -o was used: {summary}"
        assert "output_size" in summary, (
            f"summary missing 'output_size' key when -o was used: {summary}"
        )
        assert "words" in summary["output_size"], (
            f"output_size missing 'words' key (this is exactly Bug 3's shape): "
            f"{summary['output_size']}"
        )
    return summary


# ================================================================== #
#  Matrix definition                                                  #
# ================================================================== #
#
# Each entry: (label, argv_builder). argv_builder(graph_path, output_path)
# returns (argv, actual_output_path) -- actual_output_path is what the
# command will really write to (usually == output_path, but e.g. `convert`
# needs an extension it recognizes, so it derives its own path from the
# harness-provided one rather than reusing it verbatim). None in, None out
# for the stdout-only cell.


def _argv_validate(graph_path: Path, output_path: Path | None):
    argv = ["validate", "-g", str(graph_path)]
    if output_path is not None:
        argv += ["-o", str(output_path)]
    return argv, output_path


def _argv_query_overview(graph_path: Path, output_path: Path | None):
    argv = ["query", "-g", str(graph_path), "--overview"]
    if output_path is not None:
        argv += ["-o", str(output_path)]
    return argv, output_path


def _argv_query_structure(graph_path: Path, output_path: Path | None):
    argv = ["query", "-g", str(graph_path), "--structure"]
    if output_path is not None:
        argv += ["-o", str(output_path)]
    return argv, output_path


def _argv_tree(graph_path: Path, output_path: Path | None):
    argv = ["tree", "-g", str(graph_path)]
    if output_path is not None:
        argv += ["-o", str(output_path)]
    return argv, output_path


def _argv_convert(graph_path: Path, output_path: Path | None):
    # convert infers output format from -o's extension; the smoke-matrix
    # harness always names the -o cell's file "out.result" (a generic
    # extension chosen so the SAME argv-builder signature works for every
    # command in the matrix), so convert needs its own -o path with a
    # convert-recognized extension instead of reusing the generic one.
    # The stdout cell has no file to write at all -- exercised via -f yaml
    # to keep the "no file written" contract intact for that cell.
    if output_path is not None:
        real_path = output_path.with_suffix(".yaml")
        return ["convert", "-i", str(graph_path), "-o", str(real_path)], real_path
    return ["convert", "-i", str(graph_path), "-f", "yaml"], None


def _argv_node_show(graph_path: Path, output_path: Path | None):
    argv = ["node", "show", "-g", str(graph_path), "--uid", "A"]
    if output_path is not None:
        argv += ["-o", str(output_path)]
    return argv, output_path


MATRIX: dict[str, Callable[[Path, Path | None], tuple[list[str], Path | None]]] = {
    "validate": _argv_validate,
    "query --overview": _argv_query_overview,
    "query --structure": _argv_query_structure,
    "tree": _argv_tree,
    "convert": _argv_convert,
    "node show": _argv_node_show,
}


@pytest.mark.parametrize("label", list(MATRIX.keys()))
class TestCommandSmokeMatrix:

    def test_stdout_mode(self, label: str, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        argv, actual_output_path = MATRIX[label](graph_path, None)

        exit_code, stdout = _run(argv)

        assert exit_code == 0, f"{label} (stdout mode) exited {exit_code}: {stdout!r}"
        _assert_valid_summary(stdout, output_path=actual_output_path)

    def test_output_file_mode(self, label: str, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        requested_path = tmp_path / "out.result"
        argv, actual_output_path = MATRIX[label](graph_path, requested_path)

        exit_code, stdout = _run(argv)

        assert exit_code == 0, f"{label} (-o mode) exited {exit_code}: {stdout!r}"
        assert actual_output_path is not None and actual_output_path.exists(), (
            f"{label} (-o mode) did not write the requested output file"
        )
        _assert_valid_summary(stdout, output_path=actual_output_path)


# ================================================================== #
#  Mutating commands: node remove / link remove                       #
# ================================================================== #
#
# These always require -o (they save a new graph) -- the "smoke matrix"
# concept for them is {-o only} rather than {-o, stdout}, but the summary
# contract still applies: the mutation must have actually happened AND the
# summary must be well-formed.


class TestMutatingCommandsSmoke:

    def test_node_remove(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        out_path = tmp_path / "removed.json"
        argv = ["node", "remove", "-g", str(graph_path), "--uid", "B", "-o", str(out_path)]

        exit_code, stdout = _run(argv)

        assert exit_code == 0, f"node remove exited {exit_code}: {stdout!r}"
        assert out_path.exists()
        summary = yaml.safe_load(stdout)
        assert summary["status"] == "ok"
        assert summary["command"] == "node remove"

    def test_link_remove(self, tmp_path: Path):
        graph_path = _build_graph(tmp_path)
        from intentgraph.serial.json_yaml import load_graph
        g = load_graph(str(graph_path))
        link_uid = next(iter(g.links))
        out_path = tmp_path / "removed.json"
        argv = ["link", "remove", "-g", str(graph_path), "--uid", link_uid, "-o", str(out_path)]

        exit_code, stdout = _run(argv)

        assert exit_code == 0, f"link remove exited {exit_code}: {stdout!r}"
        assert out_path.exists()
        summary = yaml.safe_load(stdout)
        assert summary["status"] == "ok"
        assert summary["command"] == "link remove"
