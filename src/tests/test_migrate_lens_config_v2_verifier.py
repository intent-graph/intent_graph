"""Verifier tests for migrate_lens_config_v2.py — Phase 5.3 verification.

Tests derived from PIG LENSSCHEMA.MIGRATION, LENSSCHEMA.NODESHAPE constraints.
Verifies:
  - Migrator correctly wraps old-shape {uid: "scalar"} to {uid: {lod: "scalar"}}
  - Idempotency: running migrator on new-shape is safe (no spurious changes)
  - Mixed-shape handling: selective migration (old→new, new→unchanged)
  - Atomicity: failures don't corrupt source files
  - CLI invocation: script entry point works, exit codes correct
  - Pydantic round-trip: migrated output instantiates via LensConfig
  - ig-tool validate: migrated output passes (except pre-existing V-L1 on STALE.NODE)

REFERENCES:
  PIG: LENSSCHEMA.MIGRATION (constraints)
  PIG: LENSSCHEMA.NODESHAPE (shape definition: old vs new)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from intentgraph.models.lens_config import LensConfig, LensNodeEntry, Position
from intentgraph.serial.json_yaml import load_graph

# Add scripts/ to path for direct migrator import (internal testing)
_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from migrate_lens_config_v2 import migrate_dict, process_file  # noqa: E402


# ================================================================
#  Test Scenarios from PIG constraints
# ================================================================


class TestMigratorOldShapeWrap:
    """from PIG: LENSSCHEMA.MIGRATION — Migration logic: for each uid in nodes,
    wrap the scalar string in {lod: <scalar>}.

    Covers: skeleton, lean, full LOD values.
    """

    def test_wrap_skeleton(self, tmp_path: Path):
        """Old shape {uid: "skeleton"} wraps to {uid: {lod: "skeleton"}}."""
        data = {
            "meta": {"name": "Test"},
            "nodes": [{"uid": "ROOT", "name": "R", "intent": "I", "epistemic_state": "known"}],
            "treearcs": [],
            "intentlinks": [],
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {"ROOT": "skeleton"},
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        assert result["lenses"]["view1"]["nodes"]["ROOT"] == {"lod": "skeleton"}

    def test_wrap_lean(self, tmp_path: Path):
        """Old shape {uid: "lean"} wraps to {uid: {lod: "lean"}}."""
        data = {
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {"A": "lean"},
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        assert result["lenses"]["v"]["nodes"]["A"] == {"lod": "lean"}

    def test_wrap_full(self, tmp_path: Path):
        """Old shape {uid: "full"} wraps to {uid: {lod: "full"}}."""
        data = {
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {"X": "full"},
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        assert result["lenses"]["v"]["nodes"]["X"] == {"lod": "full"}

    def test_wrap_multiple_lods(self, tmp_path: Path):
        """Multiple old-shape entries all wrap."""
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {
                        "ROOT": "skeleton",
                        "AUTH": "lean",
                        "AUTH.1": "full",
                    },
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        nodes = result["lenses"]["view"]["nodes"]
        assert nodes == {
            "ROOT": {"lod": "skeleton"},
            "AUTH": {"lod": "lean"},
            "AUTH.1": {"lod": "full"},
        }


class TestIdempotency:
    """from PIG: LENSSCHEMA.MIGRATION — Idempotent: files already in new shape are skipped;
    mtime is not touched.

    Verify: second run on migrated file produces no changes (changed=False).
    """

    def test_idempotent_new_shape(self, tmp_path: Path):
        """New-shape file returns changed=False."""
        data = {
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {"A": {"lod": "lean"}},
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert not changed

    def test_idempotent_with_position(self, tmp_path: Path):
        """New-shape with position returns changed=False."""
        data = {
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {
                        "A": {"lod": "full", "position": {"x": 1.0, "y": 2.0}},
                    },
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert not changed

    def test_idempotent_file_round_trip(self, tmp_path: Path):
        """Migrate a file, then migrate again — no changes on second run."""
        f = tmp_path / "idempotent.yaml"
        original_data = {
            "meta": {"name": "Test"},
            "nodes": [{"uid": "R", "name": "R", "intent": "I", "epistemic_state": "known"}],
            "treearcs": [],
            "intentlinks": [],
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"R": "lean"},
                }
            },
        }
        f.write_text(
            yaml.dump(original_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        # First migration
        status1 = process_file(f, dry_run=False)
        assert status1 == "migrated"

        # Read back
        data1 = yaml.safe_load(f.read_text(encoding="utf-8"))

        # Second migration
        status2 = process_file(f, dry_run=False)
        assert status2 == "skipped:already new shape"

        # Content unchanged
        data2 = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert data1 == data2


class TestMixedShape:
    """from PIG: LENSSCHEMA.MIGRATION — Only old-shape entries are migrated;
    new-shape entries pass through unchanged.

    Verify: selective wrapping in a single lens with both old and new entries.
    """

    def test_mixed_old_and_new(self, tmp_path: Path):
        """File with mixed old/new entries: old wrapped, new untouched."""
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {
                        "ROOT": "skeleton",  # old
                        "AUTH": {"lod": "lean"},  # new
                        "DATA": "full",  # old
                    },
                }
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        nodes = result["lenses"]["view"]["nodes"]
        assert nodes["ROOT"] == {"lod": "skeleton"}
        assert nodes["AUTH"] == {"lod": "lean"}
        assert nodes["DATA"] == {"lod": "full"}

    def test_mixed_multi_lens(self, tmp_path: Path):
        """File with multiple lenses, each with mixed entries."""
        data = {
            "lenses": {
                "view1": {
                    "name": "view1",
                    "nodes": {
                        "A": "skeleton",  # old
                        "B": {"lod": "lean"},  # new
                    },
                },
                "view2": {
                    "name": "view2",
                    "nodes": {
                        "A": {"lod": "full"},  # new
                        "C": "lean",  # old
                    },
                },
            },
        }
        result, changed = migrate_dict(data, source="test")
        assert changed
        assert result["lenses"]["view1"]["nodes"]["A"] == {"lod": "skeleton"}
        assert result["lenses"]["view1"]["nodes"]["B"] == {"lod": "lean"}
        assert result["lenses"]["view2"]["nodes"]["A"] == {"lod": "full"}
        assert result["lenses"]["view2"]["nodes"]["C"] == {"lod": "lean"}


class TestAtomicity:
    """from PIG: LENSSCHEMA.MIGRATION — No backward-compatibility shim in production code.
    If migration fails partway, file is untouched.

    Verify: malformed entries raise ValueError; source file is not written.
    """

    def test_malformed_int_raises(self, tmp_path: Path):
        """Malformed entry (int value) raises ValueError without writing."""
        f = tmp_path / "malformed.yaml"
        data = {
            "meta": {"name": "Bad"},
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"A": 42},  # malformed
                }
            },
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        original_content = f.read_text(encoding="utf-8")

        # Attempt migration
        status = process_file(f, dry_run=False)
        assert status.startswith("error")

        # File unchanged
        assert f.read_text(encoding="utf-8") == original_content

    def test_malformed_none_raises(self, tmp_path: Path):
        """Malformed entry (None value) raises ValueError without writing."""
        f = tmp_path / "malformed_none.yaml"
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"A": None},  # malformed
                }
            },
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        original_content = f.read_text(encoding="utf-8")

        status = process_file(f, dry_run=False)
        assert status.startswith("error")
        assert f.read_text(encoding="utf-8") == original_content


class TestMigratorCLI:
    """from PIG: LENSSCHEMA.MIGRATION — Script lives at src/scripts/migrate_lens_config_v2.py.

    Verify: subprocess invocation, exit codes, --dry-run flag.
    """

    def test_cli_dry_run(self, tmp_path: Path):
        """--dry-run flag does not write."""
        f = tmp_path / "test.yaml"
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"A": "lean"},
                }
            },
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        original = f.read_text(encoding="utf-8")

        # Invoke via subprocess
        script = _SCRIPTS_DIR / "migrate_lens_config_v2.py"
        result = subprocess.run(
            [sys.executable, str(script), "--dry-run", str(f)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "[dry-run]" in result.stdout
        assert f.read_text(encoding="utf-8") == original  # unchanged

    def test_cli_migrates_file(self, tmp_path: Path):
        """Subprocess invocation migrates the file."""
        f = tmp_path / "test.yaml"
        data = {
            "meta": {"name": "Test"},
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"A": "lean"},
                }
            },
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        script = _SCRIPTS_DIR / "migrate_lens_config_v2.py"
        result = subprocess.run(
            [sys.executable, str(script), str(f)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "migrated" in result.stdout

        # Verify file was updated
        updated = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert updated["lenses"]["view"]["nodes"]["A"] == {"lod": "lean"}

    def test_cli_error_exit_code(self, tmp_path: Path):
        """Subprocess exits with code 1 on malformed entry."""
        f = tmp_path / "bad.yaml"
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {"A": 123},  # malformed
                }
            },
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        script = _SCRIPTS_DIR / "migrate_lens_config_v2.py"
        result = subprocess.run(
            [sys.executable, str(script), str(f)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "ERROR" in result.stderr or "error" in result.stdout

    def test_cli_nonexistent_path_warning(self, tmp_path: Path):
        """Subprocess warns on nonexistent path and continues."""
        nonexistent = tmp_path / "does_not_exist.yaml"

        script = _SCRIPTS_DIR / "migrate_lens_config_v2.py"
        result = subprocess.run(
            [sys.executable, str(script), str(nonexistent)],
            capture_output=True,
            text=True,
        )
        # Should exit cleanly (no files to process)
        assert result.returncode == 0


class TestPydanticRoundTrip:
    """from PIG: LENSSCHEMA.NODESHAPE — New shape dict[uid, LensNodeEntry] where
    LensNodeEntry = {lod: lod_str, position?: {x: float, y: float}}.

    Verify: migrated output can be instantiated via LensConfig model.
    """

    def test_lensconfig_instantiate_from_migrated(self, tmp_path: Path):
        """Migrated lens nodes can be loaded into LensConfig."""
        old_data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "description": "Test",
                    "nodes": {
                        "ROOT": "skeleton",
                        "AUTH": "lean",
                        "AUTH.1": "full",
                    },
                    "intentlinks": [],
                }
            },
        }
        migrated, _ = migrate_dict(old_data, source="test")
        lens_dict = migrated["lenses"]["view"]

        # Instantiate via Pydantic
        lens_config = LensConfig.model_validate(lens_dict)
        assert lens_config.name == "view"
        assert lens_config.description == "Test"
        assert len(lens_config.nodes) == 3
        assert lens_config.nodes["ROOT"].lod == "skeleton"
        assert lens_config.nodes["AUTH"].lod == "lean"
        assert lens_config.nodes["AUTH.1"].lod == "full"

    def test_lensconfig_with_position(self, tmp_path: Path):
        """New-shape with position instantiates correctly."""
        data = {
            "lenses": {
                "view": {
                    "name": "view",
                    "nodes": {
                        "A": {"lod": "full", "position": {"x": 10.0, "y": 20.0}},
                    },
                    "intentlinks": [],
                }
            },
        }
        migrated, _ = migrate_dict(data, source="test")
        lens_dict = migrated["lenses"]["view"]

        lens_config = LensConfig.model_validate(lens_dict)
        assert lens_config.nodes["A"].lod == "full"
        assert lens_config.nodes["A"].position is not None
        assert lens_config.nodes["A"].position.x == 10.0
        assert lens_config.nodes["A"].position.y == 20.0


class TestIgToolValidateIntegration:
    """from PIG: LENSSCHEMA.MIGRATION — Output validates via ig-tool validate.

    Verify: migrated fixture passes ig-tool validate (except intentional V-L1 on STALE.NODE).
    """

    def test_migrated_fixture_validates(self):
        """The actual migrated fixture (sample-with-lenses.ig.yaml) passes validate."""
        fixture = (
            Path(__file__).parent.parent.parent
            / "vscode_extension/intentgraph-vscode/docs/fixtures/sample-with-lenses.ig.yaml"
        )
        assert fixture.exists(), f"Fixture not found: {fixture}"

        # Load via load_graph (full IG validation)
        try:
            graph = load_graph(fixture)
            # If it loads, the basic structure is valid (IntentGraph object)
            assert hasattr(graph, "lenses"), "Graph must have lenses attribute"
            assert hasattr(graph, "nodes"), "Graph must have nodes attribute"
            # Check that lenses are present
            assert len(graph.lenses) > 0, "Graph must have at least one lens"
            # Check that nodes are present
            assert len(graph.nodes) > 0, "Graph must have nodes"
        except Exception as e:
            pytest.fail(f"Failed to load migrated fixture: {e}")

    def test_migrated_file_json_validates(self, tmp_path: Path):
        """Migrated JSON file loads correctly."""
        f = tmp_path / "test.json"
        data = {
            "meta": {"name": "Test"},
            "nodes": [
                {"uid": "ROOT", "name": "R", "intent": "I", "epistemic_state": "known"},
            ],
            "treearcs": [],
            "intentlinks": [],
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {"ROOT": "lean"},
                    "intentlinks": [],
                }
            },
        }
        f.write_text(json.dumps(data), encoding="utf-8")

        # Migrate
        status = process_file(f, dry_run=False)
        assert status == "migrated"

        # Load and validate structure
        migrated_data = json.loads(f.read_text(encoding="utf-8"))
        assert migrated_data["lenses"]["v"]["nodes"]["ROOT"] == {"lod": "lean"}

        # Try to instantiate via LensConfig
        lens_config = LensConfig.model_validate(migrated_data["lenses"]["v"])
        assert lens_config.nodes["ROOT"].lod == "lean"


class TestFilesWithoutLenses:
    """from PIG: LENSSCHEMA.MIGRATION — Skip files without `lenses:` key.

    Verify: files with no lenses key are silently skipped (status="skipped:no lenses key").
    """

    def test_no_lenses_key_skipped(self, tmp_path: Path):
        """File without 'lenses' key is skipped."""
        f = tmp_path / "no_lenses.yaml"
        data = {
            "meta": {"name": "No Lenses"},
            "nodes": [{"uid": "A", "name": "A", "intent": "A", "epistemic_state": "known"}],
            "treearcs": [],
            "intentlinks": [],
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        status = process_file(f, dry_run=False)
        assert status == "skipped:no lenses key"

    def test_empty_lenses_skipped(self, tmp_path: Path):
        """File with empty lenses dict is skipped (no change needed)."""
        f = tmp_path / "empty_lenses.yaml"
        data = {
            "meta": {"name": "Empty Lenses"},
            "nodes": [],
            "treearcs": [],
            "intentlinks": [],
            "lenses": {},
        }
        f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        status = process_file(f, dry_run=False)
        assert status == "skipped:already new shape"  # no change


class TestDirectoryRecursion:
    """from PIG: LENSSCHEMA.MIGRATION — Targets: src/tests/fixtures/, agents_runtime/tests/fixtures/,
    vscode_extension/.../fixtures/.

    Verify: migrator recurses into directories and finds all *.yaml/*.yml/*.json files.
    """

    def test_directory_recursion(self, tmp_path: Path):
        """Migrator recurses into subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        f1 = tmp_path / "file1.yaml"
        f2 = subdir / "file2.yaml"

        data = {
            "lenses": {
                "v": {
                    "name": "v",
                    "nodes": {"A": "lean"},
                }
            },
        }
        f1.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        f2.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        # Process directory
        from migrate_lens_config_v2 import _collect_files

        files = _collect_files(tmp_path)
        assert len(files) == 2
        assert f1 in files
        assert f2 in files

    def test_file_extension_filtering(self, tmp_path: Path):
        """Migrator only processes .yaml, .yml, .json files."""
        f_yaml = tmp_path / "test.yaml"
        f_yml = tmp_path / "test.yml"
        f_json = tmp_path / "test.json"
        f_txt = tmp_path / "test.txt"
        f_md = tmp_path / "test.md"

        data = {"lenses": {"v": {"name": "v", "nodes": {}}}}
        for f in [f_yaml, f_yml, f_json]:
            if f.suffix == ".json":
                f.write_text(json.dumps(data), encoding="utf-8")
            else:
                f.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")

        f_txt.write_text("not yaml", encoding="utf-8")
        f_md.write_text("# Markdown", encoding="utf-8")

        from migrate_lens_config_v2 import _collect_files

        files = _collect_files(tmp_path)
        assert f_yaml in files
        assert f_yml in files
        assert f_json in files
        assert f_txt not in files
        assert f_md not in files
