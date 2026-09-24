"""Tests for per-vault Obsidian plugin provisioning.

Obsidian has no global plugin install — plugins live per-vault under
``.obsidian/plugins/<id>/`` and are enabled via ``community-plugins.json``.
Since export creates the vault, export must provision what its canvases need:
a ``--layout portal`` vault without Advanced Canvas renders portals as static
file cards that never expand, with no error shown to the user.

Test strategy:
1. Portal export installs + enables the plugin; grid/radial do not.
2. The cache is the source (no network); a missing cache warns, never fails.
3. Idempotence: re-export doesn't rewrite a current plugin, and enabling is a
   set-union that preserves a user's other plugins.
4. Multi-graph vaults install at the vault ROOT, not the graph subfolder.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intentgraph.models.graph import IntentGraph
from intentgraph.obsidian import export_to_obsidian
from intentgraph.obsidian._plugins import (
    ensure_vault_plugins,
    plugin_cache_dir,
    required_plugins,
)

PLUGIN_ID = "advanced-canvas"


@pytest.fixture
def graph() -> IntentGraph:
    g = IntentGraph(meta={"name": "plugins"})
    g.add_node("ROOT", "System", "top-level goal")
    g.add_node_under("ALPHA", "Alpha", "branch intent", parent_uid="ROOT")
    g.add_node_under("ALPHA.1", "A1", "leaf", parent_uid="ALPHA")
    return g


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A populated plugin cache, wired in via the env override."""
    root = tmp_path / "plugin-cache"
    pdir = root / PLUGIN_ID
    pdir.mkdir(parents=True)
    (pdir / "manifest.json").write_text(
        json.dumps({"id": PLUGIN_ID, "name": "Advanced Canvas", "version": "6.4.0"})
    )
    (pdir / "main.js").write_text("/* plugin code */")
    (pdir / "styles.css").write_text(".portal {}")
    monkeypatch.setenv("INTENTGRAPH_OBSIDIAN_PLUGIN_DIR", str(root))
    return root


@pytest.fixture
def empty_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "empty-cache"
    root.mkdir()
    monkeypatch.setenv("INTENTGRAPH_OBSIDIAN_PLUGIN_DIR", str(root))
    return root


def _installed(vault: Path) -> Path:
    return vault / ".obsidian" / "plugins" / PLUGIN_ID


def _enabled(vault: Path) -> list[str]:
    path = vault / ".obsidian" / "community-plugins.json"
    return json.loads(path.read_text()) if path.is_file() else []


# ------------------------------------------------------------------ #
#  Engine -> requirement mapping                                      #
# ------------------------------------------------------------------ #


def test_portal_requires_advanced_canvas():
    assert required_plugins("portal") == (PLUGIN_ID,)


@pytest.mark.parametrize("engine", ["grid", "radial"])
def test_vanilla_engines_require_nothing(engine: str):
    """grid/radial emit only stock canvas features — no plugin needed."""
    assert required_plugins(engine) == ()


# ------------------------------------------------------------------ #
#  Export wiring                                                      #
# ------------------------------------------------------------------ #


def test_portal_export_installs_and_enables(graph, tmp_path, cache):
    vault = tmp_path / "vault"
    report = export_to_obsidian(graph, vault, layout_engine="portal")

    assert (_installed(vault) / "main.js").is_file()
    assert (_installed(vault) / "manifest.json").is_file()
    assert (_installed(vault) / "styles.css").is_file()
    assert _enabled(vault) == [PLUGIN_ID]
    assert report.installed == [PLUGIN_ID]
    assert report.hint() is None


@pytest.mark.parametrize("engine", ["grid", "radial"])
def test_vanilla_export_installs_nothing(graph, tmp_path, cache, engine: str):
    vault = tmp_path / "vault"
    report = export_to_obsidian(graph, vault, layout_engine=engine)

    assert not (vault / ".obsidian" / "plugins").exists()
    assert report.installed == []


def test_no_install_plugins_opts_out(graph, tmp_path, cache):
    vault = tmp_path / "vault"
    report = export_to_obsidian(
        graph, vault, layout_engine="portal", install_plugins=False,
    )

    assert not (vault / ".obsidian" / "plugins").exists()
    assert report.installed == []


# ------------------------------------------------------------------ #
#  Missing cache degrades, never fails                                #
# ------------------------------------------------------------------ #


def test_missing_cache_warns_but_export_succeeds(graph, tmp_path, empty_cache):
    """The vault is still correct — only portal rendering is degraded."""
    vault = tmp_path / "vault"
    report = export_to_obsidian(graph, vault, layout_engine="portal")

    assert report.missing_from_cache == [PLUGIN_ID]
    assert report.installed == []
    # The export itself completed: canvases and nodes are on disk.
    assert (vault / "viz" / "OVERVIEW.canvas").is_file()
    assert list((vault / "nodes").glob("*.md"))

    hint = report.hint()
    assert hint is not None
    assert PLUGIN_ID in hint
    assert str(plugin_cache_dir()) in hint


def test_incomplete_cache_entry_is_treated_as_missing(graph, tmp_path, cache):
    """A manifest without main.js can't be loaded by Obsidian — don't install it."""
    (cache / PLUGIN_ID / "main.js").unlink()

    vault = tmp_path / "vault"
    report = export_to_obsidian(graph, vault, layout_engine="portal")

    assert report.missing_from_cache == [PLUGIN_ID]
    assert not _installed(vault).exists()


# ------------------------------------------------------------------ #
#  Idempotence & preservation                                         #
# ------------------------------------------------------------------ #


def test_reexport_is_idempotent(graph, tmp_path, cache):
    vault = tmp_path / "vault"
    export_to_obsidian(graph, vault, layout_engine="portal")
    report = export_to_obsidian(graph, vault, layout_engine="portal")

    assert report.already_current == [PLUGIN_ID]
    assert report.installed == []
    assert _enabled(vault) == [PLUGIN_ID]  # not duplicated


def test_version_bump_reinstalls(graph, tmp_path, cache):
    vault = tmp_path / "vault"
    export_to_obsidian(graph, vault, layout_engine="portal")

    (cache / PLUGIN_ID / "manifest.json").write_text(
        json.dumps({"id": PLUGIN_ID, "name": "Advanced Canvas", "version": "6.5.0"})
    )
    (cache / PLUGIN_ID / "main.js").write_text("/* v6.5.0 */")
    report = export_to_obsidian(graph, vault, layout_engine="portal")

    assert report.installed == [PLUGIN_ID]
    assert (_installed(vault) / "main.js").read_text() == "/* v6.5.0 */"


def test_other_enabled_plugins_are_preserved(graph, tmp_path, cache):
    """Never clobber a user's own plugin list — enabling is a set-union."""
    vault = tmp_path / "vault"
    dot = vault / ".obsidian"
    dot.mkdir(parents=True)
    (dot / "community-plugins.json").write_text(json.dumps(["dataview", "templater"]))

    export_to_obsidian(graph, vault, layout_engine="portal")

    assert _enabled(vault) == ["dataview", "templater", PLUGIN_ID]


def test_corrupt_plugin_list_is_replaced(graph, tmp_path, cache):
    vault = tmp_path / "vault"
    dot = vault / ".obsidian"
    dot.mkdir(parents=True)
    (dot / "community-plugins.json").write_text("{not json")

    export_to_obsidian(graph, vault, layout_engine="portal")

    assert _enabled(vault) == [PLUGIN_ID]


# ------------------------------------------------------------------ #
#  Multi-graph vaults                                                 #
# ------------------------------------------------------------------ #


def test_installs_at_vault_root_not_subfolder(graph, tmp_path, cache):
    """product_ig/ and projection_ig/ share the vault root's one .obsidian/."""
    vroot = tmp_path / "obsidian_export"
    out = vroot / "product_ig"
    export_to_obsidian(graph, out, vault_root=vroot, layout_engine="portal")

    assert (_installed(vroot) / "main.js").is_file()
    assert not (out / ".obsidian").exists()


# ------------------------------------------------------------------ #
#  Direct API                                                         #
# ------------------------------------------------------------------ #


def test_ensure_vault_plugins_is_standalone(tmp_path, cache):
    """Usable to retrofit an already-exported vault without re-exporting."""
    vault = tmp_path / "existing"
    vault.mkdir()

    report = ensure_vault_plugins(vault, layout_engine="portal")

    assert report.installed == [PLUGIN_ID]
    assert _enabled(vault) == [PLUGIN_ID]
