"""Operations: IV-context helpers and ilink projection."""

from intentgraph.ops.iv_context import (
    IV_CONTEXT_MODE_FULL,
    IV_CONTEXT_MODE_LEAN,
    build_iv_context_profile,
    target_neighbor_uids,
)
from intentgraph.ops.projection import (
    ProjectedLink,
    project_links,
    project_links_with_dominance,
    rep,
)

__all__ = [
    "target_neighbor_uids",
    "build_iv_context_profile",
    "IV_CONTEXT_MODE_FULL",
    "IV_CONTEXT_MODE_LEAN",
    "rep",
    "project_links",
    "project_links_with_dominance",
    "ProjectedLink",
]
