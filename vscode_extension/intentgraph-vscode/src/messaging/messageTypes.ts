// Shared message envelope definitions for extension host <-> webview RPC.
// Covers: ping smoke-test; load graph, file-changed notification; dropping
//         FetchNode (LOD content travels in initial LoadGraphResponse) in
//         favour of FitNotification for status-bar "click to recentre";
//         the internal lens model — ApplyLensNotification replaces
//         the removed Tier A/B machinery (WireLensState, LensStateChangedNotification,
//         GetLensStateRequestType, RestoreLensNotification removed).
//         BootCompleteNotification kept: repurposed for default-lens delivery.
//         Bidirectional field edits — EditFieldRequestType,
//         EditConflictNotification. LoadGraphResponse extended with fileHash.

import { NotificationType, RequestType } from 'vscode-messenger-common';

import type { Position, SerialisedIntentGraphModel, SerialisedLensConfig, Uid } from '../shared/graphTypes';

export interface PingResponse {
  ok: boolean;
  igToolFound: boolean;
  igToolVersion?: string;
  error?: string;
}

export const PingRequestType: RequestType<void, PingResponse> = { method: 'intentgraph/ping' };

/** Webview asks host to (re)load the bound document. */
export interface LoadGraphResponse {
  ok: boolean;
  model?: SerialisedIntentGraphModel;
  error?: string;
  /** SHA-256 hex of the raw file content (CRLF-normalised) at load time.
   *  Webview caches this to send with EditFieldRequest. */
  fileHash?: string;
  /** All internal lenses parsed from the IG file. Empty object if none. */
  lenses?: Record<string, SerialisedLensConfig>;
  /** Resolved default lens name from meta.default_lens. Null if absent or unresolved. */
  default_lens?: string | null;
}
export const LoadGraphRequestType: RequestType<void, LoadGraphResponse> = {
  method: 'intentgraph/load'
};

/** Host pushes when underlying file changed. Webview replies by re-requesting load. */
export const GraphChangedNotification: NotificationType<void> = {
  method: 'intentgraph/changed'
};

/** Host asks the webview to recentre the cytoscape view (cy.fit). §3.3. */
export const FitNotification: NotificationType<void> = {
  method: 'intentgraph/fit'
};

// ---------- Internal lens model ----------

/** Diagnostic item reported when a lens references a UID not in the current model. */
export interface LensDiagnostic {
  level: 'warn' | 'error';
  uid?: string;
  message: string;
}

/** Payload for applying an internal lens to the webview.
 *  null means "clear the active lens and return to default LOD." */
export interface LensApplyPayload {
  /** Lens name (for display in status bar). */
  name: string;
  /** uid → lod assignments. Only UIDs present in the current model are included. */
  nodes: Record<Uid, 'skeleton' | 'lean' | 'full'>;
  /**
   * Coord-frame fix: uid → parent-relative position, only for nodes that have
   * a stored position in the lens. Empty record = no positions persisted.
   * PIG LENSSCHEMA.NODESHAPE: parent-relative storage → child follows parent.
   */
  positions: Record<Uid, Position>;
  /** Intentlink UIDs included in the lens (informational; for diagnostic check). */
  intentlinks: string[];
  /** Diagnostics computed at translation time (stale UIDs). */
  diagnostics: LensDiagnostic[];
}

/** Host → Webview: apply a named lens or clear the active one (null = clear). */
export const ApplyLensNotification: NotificationType<LensApplyPayload | null> = {
  method: 'intentgraph/applyLens'
};

/** Webview → Host: signals that the initial structural mount is complete.
 *  Fired exactly once per editor lifetime, after cy.add + positions + plugins +
 *  tap handlers + overlay layer are wired and the UI phase is ready.
 *  NOT fired on metadata-only reloads.
 *  H1 boot-race fix: originally used to deliver pending
 *  workspaceState lens restore. Repurposed — on receipt,
 *  host sends ApplyLensNotification with the default lens if meta.default_lens is set.
 *  NOTE: Phase 2 may introduce a dedicated EditorReadyNotification to decouple this.
 */
export const BootCompleteNotification: NotificationType<void> = {
  method: 'intentgraph/boot-complete'
};

// ---------- Bidirectional field edits ----------

/** Which field the user is editing. */
export type EditableField = 'name' | 'intent' | 'constraint' | 'epistemic_state';

/** Payload sent by webview when user commits a field edit. */
export interface EditFieldPayload {
  nodeUid: Uid;
  field: EditableField;
  /** Required when field === 'constraint'. */
  constraintIndex?: number;
  oldValue: string;
  /** Trimmed by webview before send. */
  newValue: string;
  /** SHA-256 hex of file at last load or last successful write. */
  fileHash: string;
}

/** Response from host after attempting to apply a field edit. */
export interface EditFieldResponse {
  ok: boolean;
  error?: string;
  /** SHA-256 hex of newly written content; present when ok=true. */
  newFileHash?: string;
}

/** Webview → Host: request to edit a single field on an existing node. */
export const EditFieldRequestType: RequestType<EditFieldPayload, EditFieldResponse> = {
  method: 'intentgraph/editField'
};

/** Host → Webview: file changed externally while an edit was in flight; reload required. */
export const EditConflictNotification: NotificationType<{ message: string }> = {
  method: 'intentgraph/editConflict'
};

// ---------- Whole-node edit ----------

/** Fields that can be submitted together in a whole-node edit.
 *  Replaces per-field one-at-a-time editing. */
export interface EditNodeFields {
  name?: string;
  intent?: string;
  /** Free-form epistemic-state string (non-empty). Drives node risk-border styling downstream. */
  epistemic_state?: string;
  /** Full replacement constraints array (only present elements updated; array length unchanged). */
  constraints?: string[];
}

/** Payload sent by webview when user commits a whole-node edit. */
export interface EditNodePayload {
  nodeUid: Uid;
  fields: EditNodeFields;
  /** SHA-256 hex of file at last load or last successful write. */
  fileHash: string;
}

/** Response from host after attempting a whole-node edit. */
export interface EditNodeResponse {
  ok: boolean;
  error?: string;
  /** SHA-256 hex of newly written content; present when ok=true. */
  newFileHash?: string;
}

/** Webview → Host: request to edit multiple fields on an existing node atomically.
 *  A single parseDocument → multiple setIn → toString → writeFile cycle. */
export const EditNodeRequestType: RequestType<EditNodePayload, EditNodeResponse> = {
  method: 'intentgraph/editNode'
};

// ---------- Position Persistence ----------

/** Webview → Host: request to persist a dragged node's position to the active lens.
 *  PIG INTERACTION.DRAG → PERSISTENCE.AUTOSAVE precedence.
 *  If activeLensName is null, PERSISTENCE.AUTOCREATE runs first. */
export interface PersistPositionRequest {
  uid: Uid;
  /** Position in Cytoscape node-center coords (parent-relative). */
  position: Position;
  /** Active lens name at drag-release; null if no lens is currently active. */
  activeLensName: string | null;
}

/** Host → Webview: acknowledgment of position persist. */
export interface PersistPositionResponse {
  ok: true;
  /** The lens that was written to (may differ from request if autocreate kicked in). */
  lensName: string;
  /** Whether a new lens was just created. */
  autoCreated: boolean;
}

/** Host → Webview (on persist failure). */
export interface PersistPositionFailure {
  ok: false;
  error: string;
}

/** Webview → Host: request to persist node position. */
export const PersistPositionRequestType: RequestType<PersistPositionRequest, PersistPositionResponse | PersistPositionFailure> = {
  method: 'intentgraph/persistPosition'
};

// ---------- Bug 1 fix: lens-visibility persistence (PIG LENSSCHEMA.VISIBILITY) ----------

/**
 * Webview → Host: persist a cue-driven visibility change to the active lens.
 * Source of truth for the rule: PIG node `LENSSCHEMA.VISIBILITY`.
 *
 * - `op: 'collapse'` — remove every descendant of `uid` from `lens.nodes`.
 *   The compound itself stays in the lens; that's what makes it "visible-collapsed"
 *   per the visibility rule.
 * - `op: 'expand'`   — add `uid`'s direct children to `lens.nodes`. `childPositions`
 *   carries the current cytoscape positions of those children (host cannot compute
 *   them on its own).
 *
 * Active lens is implicit: server-side reads `entry.activeLensName`. If null,
 * the request is rejected (no place to persist visibility into).
 */
export interface PersistLensVisibilityRequest {
  uid: Uid;
  op: 'collapse' | 'expand';
  /** For 'expand': uid → current cy position for each direct child. Empty for 'collapse'. */
  childPositions?: Record<Uid, Position>;
  /** SHA-256 of the file as the webview last saw it; lets the host detect external changes. */
  fileHash: string;
}

export interface PersistLensVisibilityResponse {
  ok: boolean;
  error?: string;
  newFileHash?: string;
}

export const PersistLensVisibilityRequestType: RequestType<PersistLensVisibilityRequest, PersistLensVisibilityResponse> = {
  method: 'intentgraph/persistLensVisibility'
};

/**
 * Persist a leaf's LOD change (lean ↔ full) to the active lens.
 * Mirror of PersistLensVisibilityRequest pattern but for a single field on
 * a single uid. Compound LOD is not persisted (constraint #5 of PIG
 * LENSSCHEMA.VISIBILITY: compound LOD has no effect on visibility).
 */
export interface PersistLensLodRequest {
  uid: Uid;
  lod: 'lean' | 'full';
  fileHash: string;
}

export interface PersistLensLodResponse {
  ok: boolean;
  error?: string;
  newFileHash?: string;
}

export const PersistLensLodRequestType: RequestType<PersistLensLodRequest, PersistLensLodResponse> = {
  method: 'intentgraph/persistLensLod'
};

// ---------- Lens CRUD + host sync ----------

/**
 * Common shape for a lens-mutation request: every operation carries fileHash
 * for optimistic concurrency. The host rejects with `ok=false, error=...`
 * on hash mismatch (file changed externally).
 */
export interface LensMutationResponse {
  ok: boolean;
  error?: string;
  /** SHA-256 hex of the newly-written file content. Present when ok=true. */
  newFileHash?: string;
  /** New active lens name after mutation (may differ from request — e.g. delete clears active). */
  activeLensName?: string | null;
}

/** Webview → Host: select (apply) a named lens, or null to clear.
 *  Replaces the prior client-only applyLensByName path so the host's
 *  entry.activeLensName stays in sync and survives reload. */
export interface SelectLensPayload {
  /** Name to apply, or null to clear. */
  name: string | null;
}
export const SelectLensRequestType: RequestType<SelectLensPayload, LensMutationResponse> = {
  method: 'intentgraph/selectLens'
};

/** Webview → Host: create a new lens with the given name. Auto-activates on success. */
export interface CreateLensPayload {
  name: string;
  /** SHA-256 hex of file at last load or last successful write. */
  fileHash: string;
}
export const CreateLensRequestType: RequestType<CreateLensPayload, LensMutationResponse> = {
  method: 'intentgraph/createLens'
};

/** Webview → Host: rename the lens from `oldName` to `newName`. */
export interface RenameLensPayload {
  oldName: string;
  newName: string;
  fileHash: string;
}
export const RenameLensRequestType: RequestType<RenameLensPayload, LensMutationResponse> = {
  method: 'intentgraph/renameLens'
};

/** Webview → Host: delete the lens with the given name. */
export interface DeleteLensPayload {
  name: string;
  fileHash: string;
}
export const DeleteLensRequestType: RequestType<DeleteLensPayload, LensMutationResponse> = {
  method: 'intentgraph/deleteLens'
};

// ---------- OBSERVABILITY trace stream from webview to host ----------
// PIG: OBSERVABILITY constraints #5–#7.

/** A single structured trace entry (JSONL line). PIG OBSERVABILITY constraint #7. */
export interface TraceEntry {
  ts: string;
  seq: number;
  src: 'router' | 'cue' | 'overlay' | 'host' | 'lens' | 'app';
  kind: string;
  cause?: string;
  corr?: string;
  data?: Record<string, unknown>;
}

/** Webview → Host: one trace entry forwarded for disk write. */
export const TraceEntryNotification: NotificationType<TraceEntry> = {
  method: 'intentgraph/trace'
};

/** Host → Webview: push current trace-enabled state so the webview emitter knows. */
export interface TraceState {
  enabled: boolean;
}

export const TraceStateNotification: NotificationType<TraceState> = {
  method: 'intentgraph/traceState'
};
