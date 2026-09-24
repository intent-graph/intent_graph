"""
Backward-compatibility re-export shim for ``ig_agents.cli_lens_commands``.

Historically this module owned ``node``/``link``/``batch`` command handlers
plus a re-export of ``lens``/``graph``/``graph_lens``. The refactor moved
``node``/``link`` to ``cli/commands/graph_mutate.py`` and folded batch execution
into ``cli/commands/parse_apply.py`` (as a typed ``run_batch(BatchParams)``
call, replacing the old Namespace-delegation ``cmd_batch``). Later, the
``lens``/``graph``/``graph_lens`` handlers were moved to their own modules.

This module now only re-exports ``cmd_graph``/``cmd_graph_lens`` (and lens
internals) for backward compatibility with existing importers — notably
``tests/test_lens_cli.py``, which does
``from ig_agents.cli_lens_commands import cmd_graph_lens``.
"""

from __future__ import annotations

# lens (15 verbs) and graph/graph-lens (16 verbs) live in
# cli/commands/lens.py and cli/commands/graph_lens.py (Phase 4). Re-exported
# here, unchanged, for backward compatibility with existing importers.
from ig_agents.cli.commands.lens import cmd_lens, _load_lens_file  # noqa: F401
from ig_agents.cli.commands.graph_lens import (  # noqa: F401
    cmd_graph,
    cmd_graph_lens,
    _project_lens,
    _reintegrate,
)
