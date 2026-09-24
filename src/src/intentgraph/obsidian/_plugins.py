"""Provision the Obsidian community plugins a vault's canvases require.

Obsidian has **no system-level plugin install**: plugins live per-vault under
``<vault>/.obsidian/plugins/<id>/`` and are enabled by listing their id in
``<vault>/.obsidian/community-plugins.json``. Vault isolation is deliberate on
Obsidian's part (a plugin has full filesystem and network access), so "install
once, applies everywhere" is not available to us.

Since ``ig-tool obsidian export`` *creates* these vaults, the export owns their
``.obsidian/`` config: a vault whose canvases cannot render is an incomplete
export, not a user setup step. This module installs the required plugin files
into each vault as it is written.

**Why this matters for ``--layout portal``.** Portal canvases carry
``"portal": true`` file-nodes, an Advanced Canvas extension to the canvas
format. Vanilla Obsidian silently ignores the key and renders a static file
card — the branch never expands no matter how far you zoom. There is no error;
the map just looks permanently collapsed. So portal exports REQUIRE the plugin.

**Source of the plugin bytes.** We never download at export time (an export must
work offline and must not silently pull code from the network). Instead the
plugin is read from a local cache directory, populated once:

    ~/.local/share/intentgraph/obsidian-plugins/<plugin-id>/

Override with ``$INTENTGRAPH_OBSIDIAN_PLUGIN_DIR``. When the cache is missing,
export still succeeds — it returns a report the CLI surfaces as a warning
telling the user how to populate it, rather than failing a vault that is
otherwise correct.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Plugin ids required per layout engine. Engines absent from this map need none
# (``grid`` and ``radial`` emit only vanilla canvas features).
_REQUIRED_PLUGINS: dict[str, tuple[str, ...]] = {
    "portal": ("advanced-canvas",),
}

# Files that make up an Obsidian plugin. ``styles.css`` is optional (not every
# plugin ships one); the other two are mandatory for Obsidian to load it.
_PLUGIN_REQUIRED_FILES = ("manifest.json", "main.js")
_PLUGIN_OPTIONAL_FILES = ("styles.css", "data.json")

_CACHE_ENV = "INTENTGRAPH_OBSIDIAN_PLUGIN_DIR"
_DEFAULT_CACHE = Path.home() / ".local" / "share" / "intentgraph" / "obsidian-plugins"


@dataclass
class PluginReport:
    """What ``ensure_vault_plugins`` did, for the CLI to surface."""

    installed: list[str] = field(default_factory=list)
    already_current: list[str] = field(default_factory=list)
    missing_from_cache: list[str] = field(default_factory=list)

    @property
    def cache_dir(self) -> Path:
        return plugin_cache_dir()

    def hint(self) -> str | None:
        """Actionable message when a required plugin could not be provisioned."""
        if not self.missing_from_cache:
            return None
        ids = ", ".join(self.missing_from_cache)
        return (
            f"required Obsidian plugin(s) not in cache: {ids}. "
            f"Portal canvases will render as static file cards until installed. "
            f"Populate {self.cache_dir}/<id>/ with the plugin's manifest.json, "
            f"main.js and styles.css (copy from a vault that has it, or from the "
            f"plugin's GitHub release), then re-run the export."
        )


def plugin_cache_dir() -> Path:
    """The directory plugin payloads are read from."""
    override = os.environ.get(_CACHE_ENV)
    return Path(override).expanduser() if override else _DEFAULT_CACHE


def required_plugins(layout_engine: str) -> tuple[str, ...]:
    """Plugin ids a given layout engine's output needs in order to render."""
    return _REQUIRED_PLUGINS.get(layout_engine, ())


def ensure_vault_plugins(
    vault_root: str | Path,
    *,
    layout_engine: str,
) -> PluginReport:
    """Install and enable the plugins *layout_engine*'s canvases require.

    Idempotent: a plugin whose installed version already matches the cache is
    left alone, and enabling is a set-union on ``community-plugins.json`` so a
    user's other plugins are never dropped.

    Never raises for a missing cache — the vault's markdown, edges and canvases
    are all still correct without the plugin; only the portal *rendering* is
    degraded. The caller decides how loudly to report it.
    """
    report = PluginReport()
    plugin_ids = required_plugins(layout_engine)
    if not plugin_ids:
        return report

    vroot = Path(vault_root).resolve()
    cache = plugin_cache_dir()
    dot_obsidian = vroot / ".obsidian"
    plugins_dir = dot_obsidian / "plugins"

    for pid in plugin_ids:
        src = cache / pid
        if not _is_valid_plugin_dir(src):
            report.missing_from_cache.append(pid)
            continue

        dest = plugins_dir / pid
        if _installed_version(dest) == _installed_version(src):
            report.already_current.append(pid)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            for fname in _PLUGIN_REQUIRED_FILES + _PLUGIN_OPTIONAL_FILES:
                fsrc = src / fname
                if fsrc.is_file():
                    shutil.copy2(fsrc, dest / fname)
            report.installed.append(pid)

        _enable_plugin(dot_obsidian, pid)

    return report


# ------------------------------------------------------------------ #
#  Internals                                                          #
# ------------------------------------------------------------------ #


def _is_valid_plugin_dir(path: Path) -> bool:
    """A directory holding at least a readable manifest.json and main.js."""
    return path.is_dir() and all(
        (path / f).is_file() for f in _PLUGIN_REQUIRED_FILES
    )


def _installed_version(plugin_dir: Path) -> str | None:
    """Version string from a plugin dir's manifest, or None if unreadable."""
    manifest = plugin_dir / "manifest.json"
    if not manifest.is_file():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except (json.JSONDecodeError, OSError):
        return None


def _enable_plugin(dot_obsidian: Path, plugin_id: str) -> None:
    """Add *plugin_id* to ``community-plugins.json``, preserving other entries.

    Obsidian treats this file as the enabled-plugin list; a plugin present on
    disk but absent here stays dormant. A corrupt file is replaced rather than
    inherited — it would disable every plugin anyway.
    """
    dot_obsidian.mkdir(parents=True, exist_ok=True)
    path = dot_obsidian / "community-plugins.json"

    enabled: list[str] = []
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                enabled = [p for p in loaded if isinstance(p, str)]
        except (json.JSONDecodeError, OSError):
            enabled = []

    if plugin_id not in enabled:
        enabled.append(plugin_id)
        path.write_text(json.dumps(enabled, indent=2) + "\n", encoding="utf-8")
