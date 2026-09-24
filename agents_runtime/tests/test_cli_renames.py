"""Tests for Phase 3 CLI rename/restructure (ig-tool).

Verifies:
1. Old command names produce "Did you mean?" hint to stderr + non-zero exit.
2. New command names parse successfully via build_parser().parse_args().
3. 'lens' parser exposes ONLY the 15 legacy verbs.
4. 'graph lens' parser exposes the 16 internal verbs.
5. 'apply --batch <file>' and 'apply -i edits.yaml' parse correctly.
6. 'workflow step create' and 'workflow trace record' parse correctly.
7. obsidian hint emitted for old sub-subcommand names.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ig_agents.cli import build_parser, _RENAMED


# ================================================================== #
#  Helpers                                                            #
# ================================================================== #


def _run_ig_tool(args: list[str]) -> tuple[int, str, str]:
    """Run ig-tool subprocess and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["ig-tool"] + args,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# ================================================================== #
#  1. Old command names → hint + non-zero exit                        #
# ================================================================== #


class TestRenameHints:
    """Old command tokens must be rejected with an 'ig-tool: hint:' message."""

    @pytest.mark.parametrize("old_token", list(_RENAMED.keys()))
    def test_old_command_exits_nonzero(self, old_token: str):
        """ig-tool <old> must exit non-zero."""
        code, out, err = _run_ig_tool([old_token, "--help"])
        # argparse exits 2 on invalid choice; may also be 1 for other errors
        assert code != 0, f"Expected non-zero exit for deprecated command '{old_token}'"

    @pytest.mark.parametrize("old_token", list(_RENAMED.keys()))
    def test_old_command_emits_hint(self, old_token: str):
        """ig-tool <old> must print 'ig-tool: hint:' to stderr."""
        code, out, err = _run_ig_tool([old_token])
        # The hint should appear in stderr
        assert "ig-tool: hint:" in err, (
            f"Expected hint in stderr for deprecated command '{old_token}', got: {err!r}"
        )

    def test_edit_hint_content(self):
        """Hint for 'edit' points to 'parse' and 'apply'."""
        code, out, err = _run_ig_tool(["edit"])
        assert "parse" in err or "apply" in err, (
            f"Hint for 'edit' should mention 'parse' or 'apply', got: {err!r}"
        )

    def test_batch_hint_content(self):
        """Hint for 'batch' points to 'apply --batch'."""
        code, out, err = _run_ig_tool(["batch"])
        assert "--batch" in err, (
            f"Hint for 'batch' should mention '--batch', got: {err!r}"
        )

    def test_step_hint_content(self):
        """Hint for 'step' points to 'workflow step'."""
        code, out, err = _run_ig_tool(["step"])
        assert "workflow step" in err, (
            f"Hint for 'step' should mention 'workflow step', got: {err!r}"
        )

    def test_trace_hint_content(self):
        """Hint for 'trace' points to 'workflow trace'."""
        code, out, err = _run_ig_tool(["trace"])
        assert "workflow trace" in err, (
            f"Hint for 'trace' should mention 'workflow trace', got: {err!r}"
        )


# ================================================================== #
#  2. New command names parse successfully                            #
# ================================================================== #


class TestNewCommandsParse:
    """New top-level commands must be accepted by the parser."""

    def _parser_accepts(self, argv: list[str]) -> bool:
        """Return True if build_parser().parse_args() accepts argv without error."""
        parser = build_parser()
        try:
            parser.parse_args(argv)
            return True
        except SystemExit:
            return False

    def test_parse_command_accepted(self):
        """'parse' top-level command parses with required flags."""
        assert self._parser_accepts(
            ["parse", "-g", "graph.yaml", "-i", "edits.yaml"]
        ), "parse command should be accepted"

    def test_apply_command_accepted(self):
        """'apply' top-level command parses with -i flag."""
        assert self._parser_accepts(
            ["apply", "-g", "graph.yaml", "-i", "edits.yaml"]
        ), "apply -i command should be accepted"

    def test_apply_batch_flag_accepted(self):
        """'apply --batch' parses correctly."""
        assert self._parser_accepts(
            ["apply", "-g", "graph.yaml", "--batch", "ops.yaml"]
        ), "apply --batch command should be accepted"

    def test_workflow_step_create_accepted(self):
        """'workflow step create' parses correctly."""
        assert self._parser_accepts(
            ["workflow", "step", "create", "--dir", "steps/", "--step", "S1"]
        ), "workflow step create should be accepted"

    def test_workflow_trace_record_accepted(self):
        """'workflow trace record' parses correctly."""
        assert self._parser_accepts(
            ["workflow", "trace", "record", "trace.jsonl",
             "--step", "S1", "--target", "T1", "--actor", "A", "--action", "x", "--result", "ok"]
        ), "workflow trace record should be accepted"

    def test_workflow_step_summary_accepted(self):
        """'workflow step summary' parses correctly."""
        assert self._parser_accepts(
            ["workflow", "step", "summary", "some_file.yaml"]
        ), "workflow step summary should be accepted"

    def test_workflow_trace_show_accepted(self):
        """'workflow trace show' parses correctly."""
        assert self._parser_accepts(
            ["workflow", "trace", "show", "trace.jsonl"]
        ), "workflow trace show should be accepted"

    def test_graph_lens_list_accepted(self):
        """'graph lens list' parses correctly."""
        assert self._parser_accepts(
            ["graph", "lens", "list", "-g", "graph.yaml"]
        ), "graph lens list should be accepted"

    def test_obsidian_export_canvas_accepted(self):
        """'obsidian export-canvas' new name parses correctly."""
        assert self._parser_accepts(
            ["obsidian", "export-canvas", "-g", "g.yaml", "--nodes", "A,B", "-o", "out.canvas"]
        ), "obsidian export-canvas should be accepted"

    def test_obsidian_export_tree_accepted(self):
        """'obsidian export-tree' new name parses correctly."""
        assert self._parser_accepts(
            ["obsidian", "export-tree", "-g", "g.yaml", "-o", "out.canvas"]
        ), "obsidian export-tree should be accepted"

    def test_obsidian_export_lens_canvas_accepted(self):
        """'obsidian export-lens-canvas' new name parses correctly."""
        assert self._parser_accepts(
            ["obsidian", "export-lens-canvas", "-l", "lens.yaml", "-o", "out/"]
        ), "obsidian export-lens-canvas should be accepted"


# ================================================================== #
#  3. lens parser has ONLY the 15 legacy verbs                        #
# ================================================================== #


class TestLensParserLegacyOnly:
    """The 'lens' parser must expose exactly the 15 legacy agent-I/O verbs."""

    LEGACY_VERBS = {
        "build", "show", "tree", "info", "focus", "promote", "demote",
        "set-lod", "prune", "expand", "set-budget", "list-pruned", "diff", "apply", "discard",
    }
    INTERNAL_VERBS = {
        "list", "create", "delete", "add-node", "remove-node",
        "add-link", "remove-link", "set-default", "unset-default",
        "project", "reintegrate", "validate", "set-position", "clear-position",
    }

    def _get_lens_choices(self) -> set[str]:
        parser = build_parser()
        # Find the lens subparser
        for action in parser._subparsers._group_actions:
            for name, subparser in action.choices.items():
                if name == "lens":
                    for a in subparser._actions:
                        if hasattr(a, "choices") and a.choices and "build" in a.choices:
                            return set(a.choices)
        return set()

    def test_legacy_verbs_present(self):
        """All 15 legacy verbs must be in the lens parser choices."""
        choices = self._get_lens_choices()
        missing = self.LEGACY_VERBS - choices
        assert not missing, f"Missing legacy lens verbs: {missing}"

    def test_internal_verbs_absent(self):
        """Internal verbs must NOT be in the lens parser choices."""
        choices = self._get_lens_choices()
        present = self.INTERNAL_VERBS & choices
        assert not present, f"Internal lens verbs found in lens parser (should be in graph lens): {present}"

    def test_lens_verb_count(self):
        """lens parser should have exactly 15 choices."""
        choices = self._get_lens_choices()
        assert len(choices) == 15, f"Expected 15 lens choices, got {len(choices)}: {choices}"


# ================================================================== #
#  4. graph lens parser has the 16 internal verbs                     #
# ================================================================== #


class TestGraphLensParserInternal:
    """The 'graph lens' parser must expose the 16 internal verbs."""

    INTERNAL_VERBS = {
        "list", "create", "delete", "add-node", "remove-node",
        "add-link", "remove-link", "set-default", "unset-default",
        "project", "reintegrate", "validate", "set-position", "clear-position",
        "show", "set-lod",
    }

    def _get_graph_lens_choices(self) -> set[str]:
        parser = build_parser()
        for action in parser._subparsers._group_actions:
            for name, subparser in action.choices.items():
                if name == "graph":
                    # graph has sub-subcommands; find 'lens'
                    for sub_action in subparser._subparsers._group_actions:
                        for sub_name, sub_sub in sub_action.choices.items():
                            if sub_name == "lens":
                                for a in sub_sub._actions:
                                    if hasattr(a, "choices") and a.choices and "list" in a.choices:
                                        return set(a.choices)
        return set()

    def test_internal_verbs_present(self):
        """All 16 internal verbs must be in graph lens parser choices."""
        choices = self._get_graph_lens_choices()
        missing = self.INTERNAL_VERBS - choices
        assert not missing, f"Missing internal graph lens verbs: {missing}"

    def test_internal_verb_count(self):
        """graph lens parser should have exactly 16 choices."""
        choices = self._get_graph_lens_choices()
        assert len(choices) == 16, (
            f"Expected 16 graph lens choices, got {len(choices)}: {choices}"
        )


# ================================================================== #
#  5. apply --batch and apply -i parse                                #
# ================================================================== #


class TestApplyParsing:
    """Both apply modes must parse correctly."""

    def test_apply_single_edit_parses(self):
        """apply -g G -i edits.yaml -o out.yaml parses."""
        parser = build_parser()
        args = parser.parse_args(["apply", "-g", "g.yaml", "-i", "edits.yaml", "-o", "out.yaml"])
        assert args.command == "apply"
        assert args.input == "edits.yaml"
        assert args.graph == "g.yaml"
        assert not getattr(args, "batch", None)

    def test_apply_batch_parses(self):
        """apply -g G --batch ops.yaml parses."""
        parser = build_parser()
        args = parser.parse_args(["apply", "-g", "g.yaml", "--batch", "ops.yaml"])
        assert args.command == "apply"
        assert args.batch == "ops.yaml"
        assert not getattr(args, "input", None)

    def test_apply_dry_run_flag(self):
        """apply --dry-run parses without error."""
        parser = build_parser()
        args = parser.parse_args(["apply", "-g", "g.yaml", "-i", "e.yaml", "--dry-run"])
        assert args.dry_run is True


# ================================================================== #
#  6. workflow step create and workflow trace record parse            #
# ================================================================== #


class TestWorkflowParsing:
    """workflow sub-subcommands must parse correctly."""

    def test_workflow_step_create_parses(self):
        """workflow step create --dir D --step S parses correctly."""
        parser = build_parser()
        args = parser.parse_args(
            ["workflow", "step", "create", "--dir", "steps/", "--step", "S.1"]
        )
        assert args.command == "workflow"
        assert args.workflow_action == "step"
        assert args.action == "create"
        assert args.dir == "steps/"

    def test_workflow_trace_record_parses(self):
        """workflow trace record trace.jsonl --step ... parses."""
        parser = build_parser()
        args = parser.parse_args([
            "workflow", "trace", "record", "trace.jsonl",
            "--step", "S1", "--target", "T1", "--actor", "agent",
            "--action", "did-thing", "--result", "ok",
        ])
        assert args.command == "workflow"
        assert args.workflow_action == "trace"
        assert args.action == "record"
        assert args.trace_file == "trace.jsonl"

    def test_workflow_trace_show_parses(self):
        """workflow trace show trace.jsonl parses."""
        parser = build_parser()
        args = parser.parse_args(["workflow", "trace", "show", "trace.jsonl"])
        assert args.command == "workflow"
        assert args.workflow_action == "trace"
        assert args.action == "show"


# ================================================================== #
#  7. obsidian frontier-era names are removed                         #
# ================================================================== #


class TestObsidianLegacyNamesRemoved:
    """Frontier-era obsidian sub-subcommand names must be rejected."""

    def test_canvas_removed(self, tmp_path: Path):
        code, out, err = _run_ig_tool([
            "obsidian", "canvas",
            "-g", str(tmp_path / "g.yaml"),
            "-o", str(tmp_path / "out.canvas"),
        ])
        assert code == 2, f"'obsidian canvas' should be rejected, got exit {code}"
        assert "invalid choice" in err

    def test_full_tree_removed(self, tmp_path: Path):
        code, out, err = _run_ig_tool([
            "obsidian", "full-tree",
            "-g", str(tmp_path / "g.yaml"),
            "-o", str(tmp_path / "out.canvas"),
        ])
        assert code == 2, f"'obsidian full-tree' should be rejected, got exit {code}"
        assert "invalid choice" in err

    def test_lens_canvas_removed(self, tmp_path: Path):
        code, out, err = _run_ig_tool([
            "obsidian", "lens-canvas",
            "-l", str(tmp_path / "lens.yaml"),
            "-o", str(tmp_path / "out/"),
        ])
        assert code == 2, f"'obsidian lens-canvas' should be rejected, got exit {code}"
        assert "invalid choice" in err


