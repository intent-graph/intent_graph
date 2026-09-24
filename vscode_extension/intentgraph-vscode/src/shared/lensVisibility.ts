// Canonical realisation of PIG node `LENSSCHEMA.VISIBILITY`.
// Source of truth for the rule: query the PIG node directly:
//   ig-tool query --node LENSSCHEMA.VISIBILITY -g projection_ig/vscode_viewer.ig.yaml
//
// Rule (verbatim from PIG constraints):
//   - Node UID present in lens.nodes => the node is displayed.
//   - Node UID absent from lens.nodes => the node is not displayed.
//   - Compound C in lens AND >=1 of C.children in lens => C is displayed expanded.
//   - Compound C in lens AND no C.child in lens => C is displayed collapsed.
//   - The 'lod' field on a compound has no effect on its expand/collapse state.
//
// All call sites (applyLens, cue handlers, tests) MUST consult deriveLensVisibility
// rather than re-derive the rule inline. This is the single point of change if the
// rule ever evolves.

import type { Uid } from './graphTypes';

/**
 * Per-node display state implied by lens membership.
 *
 * - `absent`              — uid not in the lens; not rendered at all.
 * - `visible-leaf`        — uid in the lens; node is a leaf (no children in topology).
 * - `visible-expanded`    — uid in the lens, node is a compound, AND ≥1 child also in lens.
 * - `visible-collapsed`   — uid in the lens, node is a compound, AND no child in lens.
 *
 * "Compound" here means: has at least one child in the tree topology
 * (`childrenOf.get(uid)?.length > 0`). The rule is purely topology + lens-membership;
 * no LOD inspection.
 */
export type DisplayState =
  | 'absent'
  | 'visible-leaf'
  | 'visible-expanded'
  | 'visible-collapsed';

/**
 * Result of applying the visibility rule to a lens.
 *
 * `displayState` covers every uid known to the topology (passed via `childrenOf` keys).
 * Callers can index it directly without conditional checks.
 */
export interface LensVisibility {
  /** Display state per uid. Includes ALL uids from the topology, not only lens members. */
  displayState: Map<Uid, DisplayState>;
  /** Convenience: uids the user should see (every uid whose state ≠ 'absent'). */
  visibleUids: Set<Uid>;
  /** Convenience: compound uids that should render collapsed. Used by applyLens. */
  collapsedCompoundUids: Set<Uid>;
}

/**
 * Pure function. Apply the lens visibility rule.
 *
 * @param lensNodeUids  The set of uids present in `lens.nodes` keys.
 * @param childrenOf    Tree topology: parent uid → ordered list of child uids.
 *                      Pass the same Map that lives on `IntentGraphModel.childrenOf`.
 *                      Every uid the caller cares about must appear as a key (use
 *                      empty arrays for leaves).
 *
 * Implementation notes:
 *   - We iterate every uid in `childrenOf.keys()` so the result covers the full
 *     topology, not just lens members. This lets callers ask about any uid without
 *     a fallback branch.
 *   - "Is this a compound?" is decided by `childrenOf.get(uid)?.length > 0`. We do
 *     not consult cytoscape or the model — topology alone.
 */
export function deriveLensVisibility(
  lensNodeUids: ReadonlySet<Uid>,
  childrenOf: ReadonlyMap<Uid, ReadonlyArray<Uid>>
): LensVisibility {
  const displayState = new Map<Uid, DisplayState>();
  const visibleUids = new Set<Uid>();
  const collapsedCompoundUids = new Set<Uid>();

  for (const uid of childrenOf.keys()) {
    if (!lensNodeUids.has(uid)) {
      displayState.set(uid, 'absent');
      continue;
    }

    const children = childrenOf.get(uid) ?? [];
    if (children.length === 0) {
      displayState.set(uid, 'visible-leaf');
      visibleUids.add(uid);
      continue;
    }

    const anyChildInLens = children.some((c) => lensNodeUids.has(c));
    if (anyChildInLens) {
      displayState.set(uid, 'visible-expanded');
    } else {
      displayState.set(uid, 'visible-collapsed');
      collapsedCompoundUids.add(uid);
    }
    visibleUids.add(uid);
  }

  return { displayState, visibleUids, collapsedCompoundUids };
}
