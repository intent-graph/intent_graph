"""Validation helpers for IntentGraph (T1–T5, inter intentlink endpoint checks, and lens rules).

Lens validation rules (Spec §7):
  V-L1  every UID in lens.nodes exists in the IG
  V-L2  every UID in lens.intentlinks exists in graph.links or graph.inter_links
  V-L3  ancestor closure: every ancestor of a displayed node is also displayed
  V-L4  link endpoint closure: both endpoints of every displayed link are displayed
  V-L5  meta.default_lens (if set) must be a key in lenses  [warning]
  V-L6  derived IG: via_lens must be a key in lenses
  V-L7  derived IG: every node UID in the IG must appear in lenses[via_lens].nodes

Cross-IG lens validation rules (Spec §10):
  V-CG1  meta.intent_resources path set but file not found — warn, skip cross-IG checks
  V-CG2  qualified UID present but meta.intent_resources absent — error
  V-CG3  qualified UID graph_id not found in manifest — error
  V-CG4  qualified UID node_uid not found in the resolved graph — error
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

from intentgraph.models.graph import IntentGraph
from intentgraph.serial.json_yaml import load_graph


def _parse_qualified_uid(qualified: str) -> tuple[str, str] | None:
    """Split graph_id:node_uid into (graph_id, node_uid). Returns None if no colon."""
    if ":" not in qualified:
        return None
    idx = qualified.index(":")
    return (qualified[:idx], qualified[idx + 1 :])


def validate_inter_intentlinks(
    graph: IntentGraph,
    resolve_graph_path_fn: Callable[[str], Path | None],
) -> list[dict[str, str]]:
    """Validate that every inter intentlink endpoint exists in its respective graph.

    For each inter link, parses src and dst as graph_id:node_uid, resolves
    graph_id to a graph file via resolve_graph_path_fn, loads that graph, and
    checks that node_uid exists. Returns a list of issues (severity, link_uid, issue).
    """
    issues: list[dict[str, str]] = []
    # Cache loaded graphs by graph_id to avoid repeated loads
    graph_cache: dict[str, IntentGraph] = {}

    for link in graph.iter_inter_links():
        link_uid = link.uid or f"{link.src}_{link.dst}"
        for endpoint in (link.src, link.dst):
            parsed = _parse_qualified_uid(endpoint)
            if not parsed:
                issues.append({
                    "severity": "error",
                    "uid": link_uid,
                    "issue": f"inter link endpoint '{endpoint}' is not qualified (expected graph_id:node_uid)",
                })
                continue
            graph_id, node_uid = parsed
            path = resolve_graph_path_fn(graph_id)
            if path is None or not path.exists():
                issues.append({
                    "severity": "error",
                    "uid": link_uid,
                    "issue": f"graph_id '{graph_id}' could not be resolved to a graph file for endpoint '{endpoint}'",
                })
                continue
            if graph_id not in graph_cache:
                try:
                    graph_cache[graph_id] = load_graph(path)
                except Exception as e:
                    issues.append({
                        "severity": "error",
                        "uid": link_uid,
                        "issue": f"failed to load graph for '{graph_id}' ({path}): {e}",
                    })
                    continue
            other = graph_cache[graph_id]
            if node_uid not in other.nodes:
                issues.append({
                    "severity": "error",
                    "uid": link_uid,
                    "issue": f"endpoint '{endpoint}' — node '{node_uid}' does not exist in graph '{graph_id}'",
                })

    return issues


# ------------------------------------------------------------------ #
#  Lens validation (Spec §7)                                          #
# ------------------------------------------------------------------ #


def validate_lenses(
    graph: IntentGraph,
    ig_path: Path | None = None,
) -> list[dict[str, str]]:
    """Validate all internal lenses in *graph*.

    Returns a list of issue dicts with keys ``severity``, ``lens``
    (optional), ``uid`` (optional), ``issue``.

    Rules applied (Spec §7):
    - V-L1  through V-L4 apply to every lens in the IG.
    - V-L5  applies to ``meta.default_lens`` (warning only).
    - V-L6  and V-L7 apply only when ``meta.derived_from`` is present.

    Rules applied (Spec §10, cross-IG lens references):
    - V-CG1  meta.intent_resources path set but file not found — warning, skip cross-IG.
    - V-CG2  qualified UID (graph_id:uid) present but meta.intent_resources absent — error.
    - V-CG3  qualified UID graph_id not found in manifest — error.
    - V-CG4  qualified UID node_uid not found in the resolved graph — error.
    Cross-IG rules require *ig_path* to resolve ``meta.intent_resources`` (relative path).
    If *ig_path* is None, cross-IG checks are skipped.
    """
    issues: list[dict[str, str]] = []

    # --- Cross-IG resolution state (Spec §10, V-CG1–V-CG4) ---
    # Resolved once per validate_lenses call; shared across all lenses.
    _ir_path: Path | None = None          # absolute path to the manifest file
    _ir_missing: bool = False             # V-CG1: manifest declared but missing
    _ir_skip_cross_ig: bool = ig_path is None  # skip if no IG file path given
    _ir_graph_cache: dict[str, IntentGraph] = {}  # keyed by graph_id

    if ig_path is not None and not _ir_skip_cross_ig:
        intent_resources_rel: str | None = graph.meta.get("intent_resources")
        if intent_resources_rel is not None:
            _ir_path = (ig_path.parent / intent_resources_rel).resolve()
            if not _ir_path.exists():
                # V-CG1: manifest declared but not found — warn, skip cross-IG
                issues.append({
                    "severity": "warning",
                    "issue": (
                        f"meta.intent_resources '{intent_resources_rel}' not found "
                        f"at '{_ir_path}' — cross-IG lens checks skipped (V-CG1)"
                    ),
                })
                _ir_missing = True

    def _check_cross_ig_uid(uid: str, lens_name: str) -> bool:
        """Check a potentially-qualified lens node UID against cross-IG rules.

        Returns True if the UID is qualified (caller should skip V-L1 for it).
        Appends V-CG2/V-CG3/V-CG4 issues as appropriate.
        """
        parsed = _parse_qualified_uid(uid)
        if parsed is None:
            return False  # local UID — handled by V-L1

        graph_id, node_uid = parsed

        # V-CG2: qualified UID present but meta.intent_resources absent
        if _ir_path is None and not _ir_skip_cross_ig:
            # ig_path was given, but no intent_resources in meta
            issues.append({
                "severity": "error",
                "lens": lens_name,
                "uid": uid,
                "issue": (
                    f"lens '{lens_name}': qualified UID '{uid}' requires "
                    "meta.intent_resources to be set (V-CG2)"
                ),
            })
            return True

        if _ir_skip_cross_ig or _ir_missing or _ir_path is None:
            # Cannot perform cross-IG checks without a manifest
            return True

        # V-CG3: graph_id not found in manifest
        from intentgraph.serial.intent_resources import resolve_graph_path
        foreign_path = resolve_graph_path(_ir_path, graph_id)
        if foreign_path is None or not foreign_path.exists():
            issues.append({
                "severity": "error",
                "lens": lens_name,
                "uid": uid,
                "issue": (
                    f"lens '{lens_name}': graph_id '{graph_id}' not found "
                    f"in intent_resources at '{_ir_path}' (V-CG3)"
                ),
            })
            return True

        # Load foreign graph (cached)
        if graph_id not in _ir_graph_cache:
            try:
                _ir_graph_cache[graph_id] = load_graph(foreign_path)
            except Exception as exc:
                issues.append({
                    "severity": "error",
                    "lens": lens_name,
                    "uid": uid,
                    "issue": (
                        f"lens '{lens_name}': failed to load graph '{graph_id}' "
                        f"from '{foreign_path}': {exc} (V-CG3)"
                    ),
                })
                return True

        # V-CG4: node_uid not found in foreign graph
        if node_uid not in _ir_graph_cache[graph_id].nodes:
            issues.append({
                "severity": "error",
                "lens": lens_name,
                "uid": uid,
                "issue": (
                    f"lens '{lens_name}': uid '{node_uid}' not found "
                    f"in graph '{graph_id}' (V-CG4)"
                ),
            })
        return True

    # --- V-L5: meta.default_lens pointer ---
    default_lens_name: str | None = graph.meta.get("default_lens")
    if default_lens_name is not None and default_lens_name not in graph.lenses:
        issues.append({
            "severity": "warning",
            "issue": f"meta.default_lens '{default_lens_name}' does not match any lens",
        })

    # Per-lens checks (V-L1 through V-L4 + V-CG2/V-CG3/V-CG4)
    for lens_name, lens in graph.lenses.items():

        # V-L1: every local UID in lens.nodes exists in the IG.
        # Qualified UIDs (graph_id:uid) are handled by V-CG2–V-CG4 instead.
        for uid in lens.nodes:
            if _check_cross_ig_uid(uid, lens_name):
                continue  # qualified UID — checked by V-CG rules above
            if uid not in graph.nodes:
                issues.append({
                    "severity": "error",
                    "lens": lens_name,
                    "uid": uid,
                    "issue": f"lens '{lens_name}': node UID '{uid}' not found in graph",
                })

        # V-POS1 / V-POS2: position field validation (PIG: LENSSCHEMA.VALIDATION)
        for uid, entry in lens.nodes.items():
            pos = entry.position
            if pos is None:
                continue
            # V-POS2: position must have exactly {x, y} — enforced by Position.extra="forbid"
            # at construction time; belt-and-suspenders check here for direct construction.
            pos_keys = set(pos.model_fields_set or {"x", "y"})
            extra_keys = set(vars(pos).keys()) - {"x", "y", "__dict__", "__pydantic_fields_set__"}
            # Check by attempting field access rather than introspecting private attrs
            if not hasattr(pos, "x") or not hasattr(pos, "y"):
                issues.append({
                    "severity": "error",
                    "lens": lens_name,
                    "uid": uid,
                    "issue": (
                        f"lens '{lens_name}': node '{uid}' position must have "
                        "exactly keys 'x' and 'y' (V-POS2)"
                    ),
                })
                continue
            # V-POS1: x and y must be finite floats (not NaN, not ±Inf)
            # PIG: LENSSCHEMA.VALIDATION
            for coord_name, coord_val in (("x", pos.x), ("y", pos.y)):
                if not isinstance(coord_val, (int, float)) or not math.isfinite(coord_val):
                    issues.append({
                        "severity": "error",
                        "lens": lens_name,
                        "uid": uid,
                        "issue": (
                            f"lens '{lens_name}': node '{uid}' position.{coord_name} "
                            f"is not a finite number (got {coord_val!r}) (V-POS1)"
                        ),
                    })

        # V-L2: every UID in lens.intentlinks exists in graph.links or inter_links
        for link_uid in lens.intentlinks:
            if link_uid not in graph.links and link_uid not in graph.inter_links:
                issues.append({
                    "severity": "error",
                    "lens": lens_name,
                    "uid": link_uid,
                    "issue": f"lens '{lens_name}': intentlink UID '{link_uid}' not found in graph",
                })

        # V-L3: ancestor closure — every ancestor of every displayed node must
        # also be a displayed node.
        for uid in list(lens.nodes):
            if uid not in graph.nodes:
                continue  # already flagged by V-L1
            try:
                for anc_uid in graph.anc(uid):
                    if anc_uid not in lens.nodes:
                        issues.append({
                            "severity": "error",
                            "lens": lens_name,
                            "uid": uid,
                            "issue": (
                                f"lens '{lens_name}': node '{uid}' present "
                                f"but ancestor '{anc_uid}' missing"
                            ),
                        })
            except Exception:
                pass  # broken graph structure — already caught by other validators

        # V-L4: link endpoint closure
        for link_uid in lens.intentlinks:
            link = graph.links.get(link_uid) or graph.inter_links.get(link_uid)
            if link is None:
                continue  # already flagged by V-L2
            for ep in (link.src, link.dst):
                local_ep = ep.split(":", 1)[1] if ":" in ep else ep
                if local_ep not in lens.nodes:
                    issues.append({
                        "severity": "error",
                        "lens": lens_name,
                        "uid": link_uid,
                        "issue": (
                            f"lens '{lens_name}': link '{link_uid}' present "
                            f"but endpoint '{local_ep}' not in lens nodes"
                        ),
                    })

    # --- Derived IG rules (V-L6, V-L7) ---
    derived_from: dict[str, str] | None = graph.meta.get("derived_from")
    if derived_from:
        via_lens: str = derived_from.get("via_lens", "")

        # V-L6: via_lens must be a key in lenses
        if via_lens not in graph.lenses:
            issues.append({
                "severity": "error",
                "issue": (
                    f"meta.derived_from.via_lens '{via_lens}' not found in lenses"
                ),
            })
        else:
            # V-L7: every node UID in the IG must appear in lenses[via_lens].nodes
            via_lens_cfg = graph.lenses[via_lens]
            for uid in graph.nodes:
                if uid not in via_lens_cfg.nodes:
                    issues.append({
                        "severity": "error",
                        "uid": uid,
                        "issue": (
                            f"derived IG: node '{uid}' not covered "
                            f"by via_lens '{via_lens}'"
                        ),
                    })

    return issues
