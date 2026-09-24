// Typed RPC client wrapping vscode-messenger-webview's Messenger.
// Single acquireVsCodeApi() call here; other modules ask the singleton.
// Covers the RPC messages plus the Fit notification.
// ApplyLensNotification replaces the removed
//   WireLensState / LensStateChangedNotification / GetLensStateRequest machinery.
//   sendBootComplete kept — repurposed for default-lens delivery trigger.
// EditFieldRequest, EditConflictNotification.

import { Messenger } from 'vscode-messenger-webview';
import { HOST_EXTENSION } from 'vscode-messenger-common';

import {
  ApplyLensNotification,
  BootCompleteNotification,
  CreateLensRequestType,
  DeleteLensRequestType,
  EditConflictNotification,
  EditFieldRequestType,
  EditNodeRequestType,
  FitNotification,
  GraphChangedNotification,
  LoadGraphRequestType,
  PersistLensLodRequestType,
  PersistLensVisibilityRequestType,
  PersistPositionRequestType,
  RenameLensRequestType,
  SelectLensRequestType,
  TraceEntryNotification,
  TraceStateNotification,
  type CreateLensPayload,
  type DeleteLensPayload,
  type EditFieldPayload,
  type EditFieldResponse,
  type EditNodePayload,
  type EditNodeResponse,
  type LensApplyPayload,
  type LensMutationResponse,
  type LoadGraphResponse,
  type PersistLensLodRequest,
  type PersistLensLodResponse,
  type PersistLensVisibilityRequest,
  type PersistLensVisibilityResponse,
  type PersistPositionRequest,
  type PersistPositionResponse,
  type PersistPositionFailure,
  type RenameLensPayload,
  type SelectLensPayload,
  type TraceEntry,
  type TraceState
} from '../messaging/messageTypes';

declare function acquireVsCodeApi(): {
  postMessage(msg: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
};

export interface VsCodeApi {
  postMessage(msg: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

let _vscode: VsCodeApi | null = null;
export function getVsCodeApi(): VsCodeApi {
  if (!_vscode) _vscode = acquireVsCodeApi();
  return _vscode;
}

export class WebviewMessaging {
  private readonly messenger: Messenger;

  constructor(vscode: VsCodeApi) {
    this.messenger = new Messenger(vscode);
    this.messenger.start();
  }

  loadGraph(): Promise<LoadGraphResponse> {
    return this.messenger.sendRequest(LoadGraphRequestType, HOST_EXTENSION, undefined);
  }

  onGraphChanged(cb: () => void): void {
    this.messenger.onNotification(GraphChangedNotification, () => cb());
  }

  onFit(cb: () => void): void {
    this.messenger.onNotification(FitNotification, () => cb());
  }

  // ---------- Internal lens model ----------

  /** Register handler for host→webview ApplyLensNotification.
   *  payload is null when the host sends a clear-lens command. */
  onApplyLens(cb: (payload: LensApplyPayload | null) => void): void {
    this.messenger.onNotification(ApplyLensNotification, (payload) => cb(payload ?? null));
  }

  /** Notify host that the initial structural mount is complete.
   *  Called exactly once per editor lifetime.
   *  Host repurposes this to deliver the default lens (meta.default_lens). */
  sendBootComplete(): void {
    this.messenger.sendNotification(BootCompleteNotification, HOST_EXTENSION, undefined);
  }

  // ---------- Bidirectional field edits ----------

  /** Send an EditFieldRequest to the host and await the response. */
  sendEditField(payload: EditFieldPayload): Promise<EditFieldResponse> {
    return this.messenger.sendRequest(EditFieldRequestType, HOST_EXTENSION, payload);
  }

  /** Send an EditNodeRequest (whole-node edit) to the host and await the response. */
  sendEditNode(payload: EditNodePayload): Promise<EditNodeResponse> {
    return this.messenger.sendRequest(EditNodeRequestType, HOST_EXTENSION, payload);
  }

  /** Register handler for host→webview EditConflictNotification. */
  onEditConflict(cb: (message: string) => void): void {
    this.messenger.onNotification(EditConflictNotification, (payload) => cb(payload.message));
  }

  // ---------- Position Persistence ----------

  /** Send a PersistPositionRequest to the host and await the response. */
  sendPersistPosition(
    payload: PersistPositionRequest
  ): Promise<PersistPositionResponse | PersistPositionFailure> {
    return this.messenger.sendRequest(PersistPositionRequestType, HOST_EXTENSION, payload);
  }

  /** Bug 1 fix: persist a cue-driven visibility change. PIG LENSSCHEMA.VISIBILITY. */
  sendPersistLensVisibility(
    payload: PersistLensVisibilityRequest
  ): Promise<PersistLensVisibilityResponse> {
    return this.messenger.sendRequest(PersistLensVisibilityRequestType, HOST_EXTENSION, payload);
  }

  /** Persist a leaf's LOD change (lean ↔ full). */
  sendPersistLensLod(
    payload: PersistLensLodRequest
  ): Promise<PersistLensLodResponse> {
    return this.messenger.sendRequest(PersistLensLodRequestType, HOST_EXTENSION, payload);
  }

  // ---------- Lens CRUD + select ----------

  /** Apply a named lens (or null to clear). Host updates entry.activeLensName
   *  and replies with the same so reload can re-apply. */
  sendSelectLens(payload: SelectLensPayload): Promise<LensMutationResponse> {
    return this.messenger.sendRequest(SelectLensRequestType, HOST_EXTENSION, payload);
  }

  /** Create a new lens. */
  sendCreateLens(payload: CreateLensPayload): Promise<LensMutationResponse> {
    return this.messenger.sendRequest(CreateLensRequestType, HOST_EXTENSION, payload);
  }

  /** Rename a lens. */
  sendRenameLens(payload: RenameLensPayload): Promise<LensMutationResponse> {
    return this.messenger.sendRequest(RenameLensRequestType, HOST_EXTENSION, payload);
  }

  /** Delete a lens. */
  sendDeleteLens(payload: DeleteLensPayload): Promise<LensMutationResponse> {
    return this.messenger.sendRequest(DeleteLensRequestType, HOST_EXTENSION, payload);
  }

  // ---------- OBSERVABILITY trace ----------

  /** Webview → Host: forward a trace entry for disk write. */
  sendTraceEntry(entry: TraceEntry): void {
    this.messenger.sendNotification(TraceEntryNotification, HOST_EXTENSION, entry);
  }

  /** Host → Webview: subscribe to trace-enabled state updates. */
  onTraceState(cb: (state: TraceState) => void): void {
    this.messenger.onNotification(TraceStateNotification, cb);
  }
}
