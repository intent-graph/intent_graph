"""ig-tool CLI package.

Transitional shape (CLI refactor Phase 1): the package boundary exists and
``common.py`` holds the one canonical copy of the shared helpers, but the
command implementations still live in ``ig_agents.cli_impl`` (the module
formerly named ``ig_agents.cli``, renamed to make room for this package).
This module re-exports everything from there so ``ig_agents.cli`` keeps
behaving exactly as it did before the split — same importable names
(``build_parser``, ``main``, ``DISPATCH``, every ``cmd_*``, ``_RENAMED``,
etc.), same CLI behavior. Later phases move each ``cmd_*`` into
``cli/commands/<name>.py`` one domain at a time; this file's re-export list
will shrink accordingly.

The re-export is done lazily (module ``__getattr__``, PEP 562) rather than
with a plain ``from ig_agents.cli_impl import *`` at module scope: eagerly
importing ``cli_impl`` here would deadlock the import graph, because
``cli_impl`` itself (via ``cli_lens_commands``) imports ``ig_agents.cli.common``
— and importing any submodule of ``ig_agents.cli`` always runs this
``__init__.py`` first. A lazy re-export breaks that cycle while keeping the
same public surface.
"""

from __future__ import annotations

from typing import Any

from ig_agents.cli import common  # noqa: F401  (submodule import is safe/side-effect-free)

__all__ = ["common"]


def __getattr__(name: str) -> Any:
    # Deferred: only touches ig_agents.cli_impl on first access of a name,
    # by which point cli_impl has finished initializing.
    import ig_agents.cli_impl as _cli_impl

    try:
        return getattr(_cli_impl, name)
    except AttributeError as e:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from e
