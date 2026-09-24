// Webview-side trace emitter.
// PIG OBSERVABILITY constraints #6–#7.
//
// Zero cost when disabled: the early-return guard in trace() is the only check.
// Sequence numbers are monotonic per-panel (per page lifetime).

import type { TraceEntry, TraceState } from '../messaging/messageTypes';
import type { WebviewMessaging } from './messaging';

let _seq = 0;
let _enabled = false;
let _messaging: WebviewMessaging | null = null;

/**
 * Initialise the trace emitter. Call once after messaging is constructed.
 * Also subscribes to TraceStateNotification so the host can toggle tracing at runtime.
 */
export function initTrace(messaging: WebviewMessaging, initialEnabled: boolean): void {
  _messaging = messaging;
  _enabled = initialEnabled;
  // Subscribe to host-pushed TraceStateNotification updates.
  messaging.onTraceState((state: TraceState) => {
    _enabled = state.enabled;
  });
}

/**
 * Emit a trace entry. ZERO cost when disabled: early return before any allocation.
 * Callers pass everything except ts and seq; those are stamped here.
 */
export function trace(entry: Omit<TraceEntry, 'ts' | 'seq'>): void {
  if (!_enabled || !_messaging) return;
  const full: TraceEntry = {
    ts: new Date().toISOString(),
    seq: _seq++,
    ...entry
  };
  _messaging.sendTraceEntry(full);
}

/**
 * Generate a correlation id for linking causally-related events across boundaries.
 * Example: dbltap generates a corr that is passed to enterNodeEditMode and
 * then referenced in the resulting editEnter trace entry.
 *
 * Format: "c-<seq>-<random6>" — low collision probability for a session.
 */
export function corr(): string {
  return `c-${_seq}-${Math.random().toString(36).slice(2, 8)}`;
}
