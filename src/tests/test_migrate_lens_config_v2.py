"""Tests for migrate_lens_config_v2.py migrator.

Covers:
  - Old-shape file migrates correctly
  - New-shape file is left unchanged
  - Idempotency: second run produces zero changes
  - Mixed file: only old entries are wrapped
  - Malformed entry (int value) errors without corrupting file
  - File without 'lenses' key is silently skipped
  - Migrated output passes `ig-tool validate`
  - Script entry-point invocation (subprocess)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# Add scripts/ to path so we can import the migrator directly
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from migrate_lens_config_v2 import (  # noqa: E402
    main,
    migrate_dict,
    process_file,
)


# ------------------------------------------------------------------ #
#  Helpers                                                            #
# ------------------------------------------------------------------ #

_VALID_GRAPH_YAML = """\
meta:
  name: "Migration Test"
nodes:
  - uid: ROOT
    name: "Root"
    intent: "System root."
    epistemic_state: "known"
  - uid: AUTH
    name: "Auth"
    intent: "Handles auth."
    epistemic_state: "known"
treearcs:
  - {{parent: ROOT, child: AUTH}}
intentlinks: []
lenses:
  test:
    name: test
    nodes:
      ROOT: lean
      AUTH: full
"""


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _make_old_shape_file(tmp_path: Path, *, suffix: str = ".yaml") -> Path:
    """Create a YAML file with old-shape scalar lod strings."""
    f = tmp_path / f"old{suffix}"
    data = {
        "meta": {"name": "Old Shape"},
        "nodes": [
            {"uid": "ROOT", "name": "Root", "intent": "Root.", "epistemic_state": "known"},
            {"uid": "AUTH", "name": "Auth", "intent": "Auth.", "epistemic_state": "known"},
        ],
        "treearcs": [{"parent": "ROOT", "child": "AUTH"}],
        "intentlinks": [],
        "lenses": {
            "view1": {
                "name": "view1",
                "nodes": {"ROOT": "skeleton", "AUTH": "lean"},
            }
        },
    }
    _write_yaml(f, data)
    return f


def _make_new_shape_file(tmp_path: Path) -> Path:
    """Create a YAML file with new-shape LensNodeEntry dicts."""
    f = tmp_path / "new.yaml"
    data = {
        "meta": {"name": "New Shape"},
        "nodes": [
            {"uid": "ROOT", "name": "Root", "intent": "Root.", "epistemic_state": "known"},
        ],
        "treearcs": [],
        "intentlinks": [],
        "lenses": {
            "view1": {
                "name": "view1",
                "nodes": {"ROOT": {"lod": "lean"}},
            }
        },
    }
    _write_yaml(f, data)
    return f


def _make_new_shape_with_position_file(tmp_path: Path) -> Path:
    """Create a YAML file with new-shape entries that include position."""
    f = tmp_path / "pos.yaml"
    data = {
        "meta": {"name": "With Position"},
        "nodes": [
            {"uid": "ROOT", "name": "Root", "intent": "Root.", "epistemic_state": "known"},
        ],
        "treearcs": [],
        "intentlinks": [],
        "lenses": {
            "view1": {
                "name": "view1",
                "nodes": {"ROOT": {"lod": "full", "position": {"x": 10.0, "y": 20.0}}},
            }
        },
    }
    _write_yaml(f, data)
    return f


# ------------------------------------------------------------------ #
#  Unit tests: migrate_dict                                           #
# ------------------------------------------------------------------ #


class TestMigrateDict:
    def test_old_shape_wrapped(self):
        """All scalar string entries are wrapped in {lod: ...}."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {
                        "ROOT": "skeleton",
                        "AUTH": "lean",
                        "AUTH.1": "full",
                    },
                }
            }
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        nodes = result["lenses"]["view1"]["nodes"]
        assert nodes["ROOT"] == {"lod": "skeleton"}
        assert nodes["AUTH"] == {"lod": "lean"}
        assert nodes["AUTH.1"] == {"lod": "full"}

    def test_new_shape_unchanged(self):
        """Entries already in {lod: ...} shape are left untouched."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {"ROOT": {"lod": "lean"}},
                }
            }
        }
        result, changed = migrate_dict(data, source="test")
        assert not changed
        assert result is data  # same object (no copy needed when unchanged)

    def test_new_shape_with_position_unchanged(self):
        """Entries with position are left untouched."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {"ROOT": {"lod": "full", "position": {"x": 1.0, "y": 2.0}}},
                }
            }
        }
        result, changed = migrate_dict(data, source="test")
        assert not changed

    def test_mixed_file_only_old_migrated(self):
        """Mixed old/new entries: only old entries are wrapped."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {
                        "ROOT": "skeleton",            # old
                        "AUTH": {"lod": "lean"},       # new
                        "AUTH.1": "full",              # old
                    },
                }
            }
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        nodes = result["lenses"]["view1"]["nodes"]
        assert nodes["ROOT"] == {"lod": "skeleton"}
        assert nodes["AUTH"] == {"lod": "lean"}   # unchanged
        assert nodes["AUTH.1"] == {"lod": "full"}

    def test_no_lenses_key_unchanged(self):
        """Data without 'lenses' key is returned unchanged."""
        data = {"meta": {"name": "no lenses"}, "nodes": []}
        result, changed = migrate_dict(data, source="test")
        assert not changed
        assert result is data

    def test_malformed_int_raises(self):
        """Integer value raises ValueError; does not silently corrupt."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {"ROOT": 42},
                }
            }
        }
        with pytest.raises(ValueError, match="unexpected type"):
            migrate_dict(data, source="test")

    def test_malformed_none_raises(self):
        """None value raises ValueError."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {"ROOT": None},
                }
            }
        }
        with pytest.raises(ValueError, match="None"):
            migrate_dict(data, source="test")

    def test_empty_nodes_dict_unchanged(self):
        """Empty nodes dict reports no change."""
        data = {"lenses": {"view1": {"name": "view1", "nodes": {}}}}
        result, changed = migrate_dict(data, source="test")
        assert not changed

    def test_multi_lens(self):
        """Multiple lenses: each is migrated independently."""
        data = {
            "lenses": {
                "a": {"name": "a", "nodes": {"ROOT": "lean"}},
                "b": {"name": "b", "nodes": {"ROOT": {"lod": "full"}}},
            }
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        assert result["lenses"]["a"]["nodes"]["ROOT"] == {"lod": "lean"}
        assert result["lenses"]["b"]["nodes"]["ROOT"] == {"lod": "full"}  # untouched


# ------------------------------------------------------------------ #
#  File-level tests: process_file                                     #
# ------------------------------------------------------------------ #


class TestProcessFile:
    def test_old_shape_migrated(self, tmp_path):
        f = _make_old_shape_file(tmp_path)
        original_text = f.read_text()

        status = process_file(f, dry_run=False)
        assert status == "migrated"

        data = _read_yaml(f)
        nodes = data["lenses"]["view1"]["nodes"]
        assert nodes["ROOT"] == {"lod": "skeleton"}
        assert nodes["AUTH"] == {"lod": "lean"}

    def test_new_shape_skipped(self, tmp_path):
        f = _make_new_shape_file(tmp_path)
        original_text = f.read_text()

        status = process_file(f, dry_run=False)
        assert status.startswith("skipped")
        assert f.read_text() == original_text  # file untouched

    def test_no_lenses_key_skipped(self, tmp_path):
        f = tmp_path / "nolens.yaml"
        _write_yaml(f, {"meta": {"name": "test"}, "nodes": []})
        status = process_file(f, dry_run=False)
        assert status.startswith("skipped")

    def test_malformed_entry_errors_no_corruption(self, tmp_path):
        f = tmp_path / "bad.yaml"
        data = {
            "lenses": {"v": {"name": "v", "nodes": {"ROOT": 42}}}
        }
        _write_yaml(f, data)
        original_text = f.read_text()

        status = process_file(f, dry_run=False)
        assert status.startswith("error")
        # File must not be corrupted — content unchanged
        assert f.read_text() == original_text

    def test_dry_run_does_not_write(self, tmp_path):
        f = _make_old_shape_file(tmp_path)
        original_text = f.read_text()

        status = process_file(f, dry_run=True)
        assert status == "would-migrate"
        assert f.read_text() == original_text  # unchanged

    def test_json_file_migrated(self, tmp_path):
        f = tmp_path / "old.json"
        data = {
            "meta": {"name": "JSON"},
            "nodes": [
                {"uid": "ROOT", "name": "Root", "intent": "Root.", "epistemic_state": "known"},
            ],
            "treearcs": [],
            "intentlinks": [],
            "lenses": {
                "v": {"name": "v", "nodes": {"ROOT": "full"}}
            },
        }
        f.write_text(json.dumps(data, indent=2), encoding="utf-8")

        status = process_file(f, dry_run=False)
        assert status == "migrated"

        saved = json.loads(f.read_text(encoding="utf-8"))
        assert saved["lenses"]["v"]["nodes"]["ROOT"] == {"lod": "full"}


# ------------------------------------------------------------------ #
#  Idempotency                                                        #
# ------------------------------------------------------------------ #


class TestIdempotency:
    def test_second_run_no_change(self, tmp_path):
        f = _make_old_shape_file(tmp_path)

        status1 = process_file(f, dry_run=False)
        assert status1 == "migrated"

        text_after_first = f.read_text()

        status2 = process_file(f, dry_run=False)
        assert status2.startswith("skipped")
        assert f.read_text() == text_after_first  # exactly identical


# ------------------------------------------------------------------ #
#  ig-tool validate integration                                       #
# ------------------------------------------------------------------ #


class TestIgToolValidate:
    """After migration the fixture must pass ig-tool validate."""

    def test_migrated_file_passes_validate(self, tmp_path):
        """The canonical sample-with-lenses.ig.yaml migrates and validates."""
        import shutil

        # Resolve relative to the src root (2 parents up from tests/)
        _p1_core = Path(__file__).parent.parent
        src = (
            _p1_core.parent
            / "vscode_extension"
            / "intentgraph-vscode"
            / "docs"
            / "fixtures"
            / "sample-with-lenses.ig.yaml"
        )
        if not src.exists():
            pytest.skip(f"Fixture not found at {src}")

        dest = tmp_path / "sample.ig.yaml"
        shutil.copy(src, dest)

        # First, migrate
        process_file(dest, dry_run=False)

        # Then validate with full report
        report_path = tmp_path / "report.yaml"
        result = subprocess.run(
            ["ig-tool", "validate", "-g", str(dest), "-o", str(report_path)],
            capture_output=True,
            text=True,
        )

        # The fixture deliberately includes STALE.NODE (a UID that does not exist
        # in the graph) to exercise the diagnostics banner in the vscode viewer.
        # This produces a known V-L1 error that is intentional, not a migration
        # artifact. We assert that:
        #   1. No migration-caused errors: the only error is the known stale-UID.
        #   2. The schema shape is correct (all nodes dict entries are dicts, not strings).
        import yaml as _yaml  # avoid name clash with outer import

        report = _yaml.safe_load(report_path.read_text()) or {}
        details = report.get("details", [])
        unexpected = [
            d for d in details
            if not (
                d.get("severity") == "error"
                and "STALE.NODE" in str(d.get("uid", ""))
                and "not found in graph" in str(d.get("issue", ""))
            )
        ]
        assert not unexpected, (
            f"Unexpected validation issues after migration:\n"
            + "\n".join(str(d) for d in unexpected)
        )

        # Also assert: all nodes entries are dicts (new shape)
        migrated_data = _yaml.safe_load(dest.read_text()) or {}
        for ln, lb in migrated_data.get("lenses", {}).items():
            for uid, val in lb.get("nodes", {}).items():
                assert isinstance(val, dict), (
                    f"Lens '{ln}' node '{uid}' still has old scalar shape after migration"
                )


# ------------------------------------------------------------------ #
#  CLI entry-point                                                    #
# ------------------------------------------------------------------ #


class TestCLI:
    def test_main_migrates_old_file(self, tmp_path):
        f = _make_old_shape_file(tmp_path)
        rc = main([str(f)])
        assert rc == 0
        data = _read_yaml(f)
        assert data["lenses"]["view1"]["nodes"]["ROOT"] == {"lod": "skeleton"}

    def test_main_nonexistent_path_warns(self, tmp_path, capsys):
        rc = main([str(tmp_path / "missing.yaml")])
        assert rc == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err or "No files found" in captured.out

    def test_main_dry_run_no_write(self, tmp_path):
        f = _make_old_shape_file(tmp_path)
        original = f.read_text()
        rc = main(["--dry-run", str(f)])
        assert rc == 0
        assert f.read_text() == original

    def test_main_error_exit_nonzero(self, tmp_path):
        f = tmp_path / "bad.yaml"
        _write_yaml(f, {"lenses": {"v": {"name": "v", "nodes": {"ROOT": 99}}}})
        rc = main([str(f)])
        assert rc == 1

    def test_script_subprocess_invocation(self, tmp_path):
        """Entry-point works when invoked as subprocess."""
        f = _make_old_shape_file(tmp_path)
        script = _SCRIPTS_DIR / "migrate_lens_config_v2.py"
        result = subprocess.run(
            [sys.executable, str(script), str(f)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = _read_yaml(f)
        assert data["lenses"]["view1"]["nodes"]["ROOT"] == {"lod": "skeleton"}
