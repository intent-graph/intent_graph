"""Local CLI usage telemetry for ig-tool.

Append-only JSONL log at ``~/.cache/ig-tool/usage.jsonl``. Default-on, opt out
with ``--no-telemetry`` or environment variable ``IG_TOOL_NO_TELEMETRY=1``.
No network — local file only.

One record per CLI invocation:
  {ts, command, action, exit_code, duration_ms, argv}

argv is sanitized: absolute paths become basenames, ``$HOME`` is stripped.
This keeps the log small and avoids leaking user paths into logs that might
later be shared.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path.home() / ".cache" / "ig-tool"
LOG_PATH = LOG_DIR / "usage.jsonl"

# Env var override (set by wrapper scripts that want telemetry off
# without rewriting argv)
_DISABLE_ENV = "IG_TOOL_NO_TELEMETRY"


def disabled_via_env() -> bool:
    """True if telemetry is disabled via the environment variable."""
    val = os.environ.get(_DISABLE_ENV, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def _sanitize_argv(argv: list[str]) -> list[str]:
    """Replace $HOME-prefixed paths with ~/<rest>; replace other absolute
    paths with basenames. Relative paths are passed through unchanged."""
    home = str(Path.home())
    out: list[str] = []
    for tok in argv:
        # $HOME-prefixed path takes precedence (more specific match)
        if tok.startswith(home):
            out.append("~" + tok[len(home):])
            continue
        # Other absolute path → basename (keeps the file extension)
        if tok.startswith("/") and len(tok) > 1:
            out.append(Path(tok).name)
            continue
        out.append(tok)
    return out


def write_record(
    *,
    command: str | None,
    action: str | None,
    exit_code: int,
    duration_ms: int,
    argv: list[str],
) -> None:
    """Append one record. Silently swallows ALL errors — telemetry must
    never break the CLI."""
    try:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "command": command,
            "action": action,
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "argv": _sanitize_argv(argv),
        }
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # Disk full, permission denied, race on mkdir — swallow.
        pass


def read_records(limit: int | None = None) -> list[dict[str, Any]]:
    """Read records from the log. Returns an empty list if no log exists."""
    if not LOG_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    with LOG_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed lines (e.g., from a partial write)
                continue
    if limit is not None:
        return out[-limit:]
    return out


# ------------------------------------------------------------------ #
#  Subcommand handlers (`ig-tool telemetry {show, tail, path}`)        #
# ------------------------------------------------------------------ #


def cmd_telemetry_path() -> None:
    """Print the log file path."""
    print(str(LOG_PATH))


def cmd_telemetry_tail(n: int) -> None:
    """Print the last N records as JSONL."""
    records = read_records(limit=n)
    for record in records:
        print(json.dumps(record, ensure_ascii=False))


def cmd_telemetry_show() -> None:
    """Print a summary table: top commands, top failures, totals."""
    records = read_records()
    if not records:
        print("ig-tool: no telemetry records yet")
        print(f"log path: {LOG_PATH}")
        return

    total = len(records)
    failures = [r for r in records if r.get("exit_code", 0) != 0]
    by_command: dict[str, int] = {}
    by_failure: dict[str, int] = {}
    for r in records:
        cmd = r.get("command") or "<unknown>"
        action = r.get("action")
        key = f"{cmd} {action}".strip() if action else cmd
        by_command[key] = by_command.get(key, 0) + 1
        if r.get("exit_code", 0) != 0:
            by_failure[key] = by_failure.get(key, 0) + 1

    print(f"ig-tool telemetry — {LOG_PATH}")
    print(f"total invocations: {total}")
    print(f"failures:          {len(failures)} ({100 * len(failures) / total:.1f}%)")
    print()
    print("Top commands:")
    for key, count in sorted(by_command.items(), key=lambda kv: -kv[1])[:10]:
        fail = by_failure.get(key, 0)
        print(f"  {count:>5}  {key}" + (f"  (failures: {fail})" if fail else ""))

    if failures:
        print()
        print("Top failure surfaces:")
        for key, count in sorted(by_failure.items(), key=lambda kv: -kv[1])[:10]:
            print(f"  {count:>5}  {key}")
