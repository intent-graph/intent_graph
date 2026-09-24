// Centralised wrapper for all four cytoscape-expand-collapse methods.
// PIG OBSERVABILITY constraint #2: every ec.expand/collapse call goes through here.
// Direct calls to ec.expand/collapse outside this file are FORBIDDEN.
//
// The wrapper logs the call via the webview trace emitter, then delegates to the
// underlying API. Zero overhead when tracing is disabled (trace() early-returns).

import type cytoscape from 'cytoscape';
import { trace } from '../trace';

/** Source tag distinguishing cue-layer calls from programmatic app calls. */
type EcCallerSrc = 'cue' | 'app';

// Minimal interfaces so callers with narrower ec types (e.g. CueLayer's ExpandCollapseLike)
// can pass their ec without a cast.
interface ExpandCollapseExpandable {
  expand(eles: cytoscape.Collection): void;
}
interface ExpandCollapseCollapsible {
  collapse(eles: cytoscape.Collection): void;
}
interface ExpandCollapseRecursive {
  expandRecursively(eles: cytoscape.Collection): void;
  collapseRecursively(eles: cytoscape.Collection): void;
}

function logEc(
  method: string,
  cause: string,
  corr: string | undefined,
  src: EcCallerSrc,
  targetCount: number
): void {
  trace({ src, kind: 'ecCall', cause, corr, data: { method, targetCount } });
}

export function ecExpand(
  ec: ExpandCollapseExpandable,
  eles: cytoscape.Collection,
  cause: string,
  src: EcCallerSrc,
  corr?: string
): void {
  logEc('expand', cause, corr, src, eles.length);
  ec.expand(eles);
}

export function ecCollapse(
  ec: ExpandCollapseCollapsible,
  eles: cytoscape.Collection,
  cause: string,
  src: EcCallerSrc,
  corr?: string
): void {
  logEc('collapse', cause, corr, src, eles.length);
  ec.collapse(eles);
}

export function ecExpandRecursively(
  ec: ExpandCollapseRecursive,
  eles: cytoscape.Collection,
  cause: string,
  src: EcCallerSrc,
  corr?: string
): void {
  logEc('expandRecursively', cause, corr, src, eles.length);
  ec.expandRecursively(eles);
}

export function ecCollapseRecursively(
  ec: ExpandCollapseRecursive,
  eles: cytoscape.Collection,
  cause: string,
  src: EcCallerSrc,
  corr?: string
): void {
  logEc('collapseRecursively', cause, corr, src, eles.length);
  ec.collapseRecursively(eles);
}
