"""Ilink projection onto a working view — rep, lifting, dominance.

Implements the projection semantics from VOCABULARY_AND_FORMALISM.md section 10:
- ``rep(V, n)``: the unique view representative of node *n*.
- ``project_links``: compute projected display links for a view.
- ``project_links_with_dominance``: suppress coarse parent links when refined
  children already cover the same projected endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass

from intentgraph.models.view import View
from intentgraph.models.link import IntentLink


@dataclass(frozen=True)
class ProjectedLink:
    """A canonical intentlink projected onto a view.

    Attributes
    ----------
    original : IntentLink
        The canonical link in the graph.
    display_src : str
        The view node representing the link's source.
    display_dst : str
        The view node representing the link's destination.
    is_lifted : bool
        True if either endpoint was projected up to a view ancestor
        (i.e. the original endpoint is not directly in the view).
    """

    original: IntentLink
    display_src: str
    display_dst: str
    is_lifted: bool = False


# ------------------------------------------------------------------ #
#  rep(V, n) — view representative                                    #
# ------------------------------------------------------------------ #


def rep(view: View, node_uid: str) -> str | None:
    """``rep(V, n)`` — the unique view node that represents *n*.

    Returns *n* itself if ``n ∈ V``, or the nearest ancestor of *n* that is
    in *V*.  Returns ``None`` if *n*'s ancestry does not intersect the view
    (possible with partial views).
    """
    graph = view.graph

    # Fast path: n is directly in the view
    if node_uid in view:
        return node_uid

    # Walk up ancestors
    current = graph.get_node_or_none(node_uid)
    if current is None:
        return None

    while current is not None:
        if current.parent_uid is not None:
            if current.parent_uid in view:
                return current.parent_uid
            current = graph.get_node_or_none(current.parent_uid)
        else:
            break

    return None


# ------------------------------------------------------------------ #
#  project_links — basic projection                                   #
# ------------------------------------------------------------------ #


def project_links(view: View) -> list[ProjectedLink]:
    """Compute projected display links for a view.

    For each canonical ilink in the graph:
    1. Compute ``rep(V, src)`` and ``rep(V, dst)``.
    2. Filter out **unrepresentable** links (either rep is None).
    3. Filter out **self-loops** (rep_src == rep_dst — the link is internal
       to a single collapsed view node).
    4. Return ``ProjectedLink`` with display endpoints and lifted flag.

    Implements VOCABULARY_AND_FORMALISM.md section 10.1–10.2.
    """
    graph = view.graph
    projected: list[ProjectedLink] = []

    for link in graph.iter_links():
        src_rep = rep(view, link.src)
        dst_rep = rep(view, link.dst)

        # Unrepresentable: one or both endpoints outside the view's coverage
        if src_rep is None or dst_rep is None:
            continue

        # Self-loop: both endpoints collapse to the same view node
        if src_rep == dst_rep:
            continue

        is_lifted = (src_rep != link.src) or (dst_rep != link.dst)

        projected.append(
            ProjectedLink(
                original=link,
                display_src=src_rep,
                display_dst=dst_rep,
                is_lifted=is_lifted,
            )
        )

    return projected


# ------------------------------------------------------------------ #
#  project_links_with_dominance — suppress coarse parents             #
# ------------------------------------------------------------------ #


def project_links_with_dominance(view: View) -> list[ProjectedLink]:
    """Project links with dominance/de-cluttering.

    Builds on ``project_links`` and additionally suppresses coarse parent ilinks
    when their refined child ilinks already cover the same projected endpoints.

    Implements VOCABULARY_AND_FORMALISM.md section 10.3:
    *"Prefer the most refined available canonical ilinks whose projections are
    meaningful.  Suppress coarse parent ilinks when their refined descendants
    already cover the same projected endpoints."*
    """
    all_projected = project_links(view)

    if not all_projected:
        return all_projected

    graph = view.graph

    # Build a set of (display_src, display_dst) pairs covered by child links
    # A link "covers" a parent if the parent link's uid matches link.parent
    child_coverage: dict[str, set[tuple[str, str]]] = {}
    for pl in all_projected:
        if pl.original.parent is not None:
            parent_uid = pl.original.parent
            if parent_uid not in child_coverage:
                child_coverage[parent_uid] = set()
            child_coverage[parent_uid].add((pl.display_src, pl.display_dst))

    # Filter: suppress parent links that are fully covered by children
    result: list[ProjectedLink] = []
    for pl in all_projected:
        link_uid = pl.original.uid
        if link_uid in child_coverage:
            # This link has refined children that project onto this view.
            # The parent is dominated — suppress it.
            continue
        result.append(pl)

    return result
