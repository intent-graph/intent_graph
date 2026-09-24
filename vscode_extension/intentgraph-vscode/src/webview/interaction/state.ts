// Gesture state — the authoritative source of truth for the three orthogonal
// state machines defined in PIG INTERACTION.MODES (LOD / Compound / Mode).
//
// All gesture suppression checks read from here. Replaces the implicit timing-based
// guards (350ms dbltap window) with explicit state guards.
//
// IMPORTANT: GestureState DOES NOT own the LOD and collapse Maps — those live on
// WebviewState (see src/webview/state.ts) and survive across structural reloads
// (snapshot/restore). GestureState references the SAME Map/Set instances; mutation
// here is observed by the rest of the app immediately. Newer fields:
// `editingUid` and `grabPosition`.

import type { NodeLOD, Position, Uid } from '../../shared/graphTypes';

/**
 * Source of a Compound state transition (collapse/expand).
 *
 * `cue`           — user clicked a cue button (the only user-driven trigger; INV-9).
 * `programmatic`  — applyLens / clearLens / structural-reload restoration.
 *
 * Anything else is forbidden and must not call into the router's compound transition
 * methods. Drag, overlap, selection, and library-internal handlers are all banned.
 */
export type CompoundTransitionSource = 'cue' | 'programmatic';

/**
 * Source of a Mode (view ↔ edit) transition.
 *
 * `dbltap`         — user double-clicked a node body.
 * `outside-click`  — pointerdown outside the editing card → commit.
 * `escape`         — Escape key → cancel.
 * `programmatic`   — another node entering edit mode auto-commits the prior;
 *                    teardown on reload also triggers a programmatic exit.
 */
export type ModeTransitionSource = 'dbltap' | 'outside-click' | 'escape' | 'programmatic';

/**
 * Gesture state shared across the router and the overlay/cue layers.
 *
 * Identity-stable: the same object is held by the router for the lifetime of the
 * App. The Maps/Sets are typically the same instances held by WebviewState so
 * that snapshot/restore-on-reload works without a separate copy step.
 */
export interface GestureState {
  /** Per-node LOD. Absent uid → `lean` (default). */
  nodeLOD: Map<Uid, NodeLOD>;

  /** Compound nodes currently collapsed. */
  collapseSet: Set<Uid>;

  /** UID of the node currently in edit mode, or null. At most one. */
  editingUid: Uid | null;

  /** Position captured at `grab`, used by `wasActualDrag` on `free`. */
  grabPosition: Map<Uid, Position>;
}

/**
 * Build a GestureState that shares its `nodeLOD` and `collapseSet` instances
 * with the provided WebviewState. Use this from the App so that reload
 * snapshot/restore continues to work transparently.
 */
export function createGestureStateFrom(parts: {
  nodeLOD: Map<Uid, NodeLOD>;
  collapseSet: Set<Uid>;
}): GestureState {
  return {
    nodeLOD: parts.nodeLOD,
    collapseSet: parts.collapseSet,
    editingUid: null,
    grabPosition: new Map()
  };
}
