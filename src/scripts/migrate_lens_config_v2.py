"""migrate_lens_config_v2.py — one-off: wrap scalar lod strings in {lod: <value>}.

Converts old-shape  nodes: {uid: "lean"}
         to new-shape nodes: {uid: {lod: "lean"}}

Targets:
  src/tests/fixtures/            (may not exist)
  agents_runtime/tests/fixtures/  (may not exist)
  vscode_extension/intentgraph-vscode/docs/fixtures/

Usage:
  python scripts/migrate_lens_config_v2.py <path> [<path> ...]
  python scripts/migrate_lens_config_v2.py --help

Options:
  --dry-run   Show what would change without writing.

Each <path> may be a file (.yaml/.yml/.json) or a directory (recursively scanned).
Idempotent: files already in new shape are skipped; mtime is not touched.
Exit code 1 if any file errored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


# ------------------------------------------------------------------ #
#  Core migration logic                                               #
# ------------------------------------------------------------------ #


def _migrate_nodes_dict(nodes: Any, source: str) -> tuple[dict[str, Any], bool]:
    """Migrate a single lens's ``nodes`` value in-place.

    Returns (migrated_nodes, changed).
    Raises ValueError for malformed entries (not str, not dict).
    """
    if not isinstance(nodes, dict):
        raise ValueError(f"{source}: lens 'nodes' must be a dict, got {type(nodes).__name__}")

    result: dict[str, Any] = {}
    changed = False
    for uid, val in nodes.items():
        if isinstance(val, str):
            # Old scalar shape → wrap
            result[uid] = {"lod": val}
            changed = True
        elif isinstance(val, dict):
            # New shape (with or without position) — leave untouched
            result[uid] = val
        elif val is None:
            # None is not a valid entry
            raise ValueError(
                f"{source}: lens node '{uid}' is None — this is a malformed entry. "
                "Fix or remove it before migrating."
            )
        else:
            raise ValueError(
                f"{source}: lens node '{uid}' has unexpected type "
                f"{type(val).__name__!r} (value: {val!r}). "
                "Expected str (old shape) or dict (new shape)."
            )
    return result, changed


def migrate_dict(data: dict[str, Any], source: str) -> tuple[dict[str, Any], bool]:
    """Walk *data* and migrate any old-shape lens nodes.

    Returns (migrated_data, changed).  *data* is NOT mutated.
    Raises ValueError for malformed entries.

    ``source`` is used only in error messages (e.g. the file path).
    """
    lenses = data.get("lenses")
    if not lenses:
        return data, False  # no lenses key — nothing to do

    if not isinstance(lenses, dict):
        raise ValueError(f"{source}: top-level 'lenses' is not a dict")

    new_lenses: dict[str, Any] = {}
    any_changed = False
    for lens_name, lens_body in lenses.items():
        if not isinstance(lens_body, dict):
            raise ValueError(
                f"{source}: lens '{lens_name}' body is not a dict "
                f"(got {type(lens_body).__name__!r})"
            )
        nodes = lens_body.get("nodes")
        if nodes is None:
            new_lenses[lens_name] = lens_body
            continue
        migrated_nodes, changed = _migrate_nodes_dict(
            nodes, source=f"{source} / lens '{lens_name}'"
        )
        if changed:
            new_lens = dict(lens_body, nodes=migrated_nodes)
            new_lenses[lens_name] = new_lens
            any_changed = True
        else:
            new_lenses[lens_name] = lens_body

    if not any_changed:
        return data, False

    return dict(data, lenses=new_lenses), True


# ------------------------------------------------------------------ #
#  File-level load / save                                             #
# ------------------------------------------------------------------ #


def _load(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text) or {}


def _save(path: Path, data: dict[str, Any]) -> None:
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


# ------------------------------------------------------------------ #
#  File scan                                                          #
# ------------------------------------------------------------------ #


def _collect_files(root: Path) -> list[Path]:
    """Collect .yaml/.yml/.json files under *root* (recursive if directory)."""
    if root.is_file():
        return [root] if root.suffix.lower() in {".yaml", ".yml", ".json"} else []
    return sorted(
        p for p in root.rglob("*") if p.suffix.lower() in {".yaml", ".yml", ".json"}
    )


# ------------------------------------------------------------------ #
#  Per-file migrate                                                   #
# ------------------------------------------------------------------ #


def process_file(path: Path, *, dry_run: bool) -> str:
    """Migrate a single file.  Returns a status string: 'migrated', 'skipped', 'error:<msg>'."""
    try:
        data = _load(path)
    except Exception as exc:
        return f"error:failed to load: {exc}"

    if not isinstance(data, dict):
        return "skipped:not a mapping"

    if "lenses" not in data:
        return "skipped:no lenses key"

    try:
        migrated, changed = migrate_dict(data, source=str(path))
    except ValueError as exc:
        return f"error:{exc}"

    if not changed:
        return "skipped:already new shape"

    if dry_run:
        return "would-migrate"

    try:
        _save(path, migrated)
    except Exception as exc:
        return f"error:failed to save: {exc}"

    return "migrated"


# ------------------------------------------------------------------ #
#  Entry point                                                        #
# ------------------------------------------------------------------ #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="PATH",
        help="File or directory to migrate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    args = parser.parse_args(argv)

    files: list[Path] = []
    for raw in args.inputs:
        p = Path(raw)
        if not p.exists():
            print(f"WARNING: path does not exist, skipping: {p}", file=sys.stderr)
            continue
        files.extend(_collect_files(p))

    if not files:
        print("No files found to process.")
        return 0

    migrated = skipped = errors = 0
    for path in files:
        status = process_file(path, dry_run=args.dry_run)
        if status == "migrated":
            migrated += 1
            print(f"  migrated : {path}")
        elif status == "would-migrate":
            migrated += 1  # count as "would migrate" for summary
            print(f"  [dry-run] would migrate: {path}")
        elif status.startswith("skipped"):
            skipped += 1
        elif status.startswith("error"):
            errors += 1
            print(f"  ERROR    : {path}: {status[6:]}", file=sys.stderr)

    suffix = " (dry run)" if args.dry_run else ""
    print(
        f"\nScanned {len(files)} files{suffix}: "
        f"migrated {migrated}, skipped {skipped}, errored {errors}."
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
