// Cytoscape stylesheet — pure data, no DOM.
// Covers node/edge styling plus LOD-driven node sizing/labels.
// Amendment 3 (Bug 3): FULL_LOD_HEIGHT imported from elkBridge to keep one source of truth.
// UX Rework: FULL_LOD_WIDTH (240) and FULL_LOD_HEIGHT (180) — 1.5× wide, 1.5× tall vs pre-Amend-4 base (160×120).
//
// PIG LAYOUT.CUES: an earlier background-image cue approach is REMOVED. The DOM-button cue
// tracked by HtmlOverlayLayer is the sole expand/collapse affordance. CSS background-image on
// cy nodes cannot receive click events reliably; a hit-test approach proved brittle. DOM buttons
// with real click handlers are correct.

import type cytoscape from 'cytoscape';
import { LEAF_WIDTH, LEAF_HEIGHT, FULL_LOD_WIDTH, FULL_LOD_HEIGHT } from '../elkBridge';

// Cytoscape's style engine does NOT expand CSS variables (it's not part of
// the browser CSS cascade — it composites onto a canvas). Use literal hex /
// rgba colours that read on both light and dark VS Code themes.
export const cyStyles: cytoscape.StylesheetStyle[] = [
  // Base node properties shared across both LOD variants.
  {
    selector: 'node',
    style: {
      'shape': 'round-rectangle',
      'background-color': '#3c3c3c',
      'background-opacity': 0.85,
      'border-width': 1,
      'border-color': '#888888',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-size': '11px',
      'color': '#e0e0e0',
      'text-wrap': 'wrap'
    }
  },
  // Lean LOD (default): name only, compact box.
  {
    selector: 'node[lod = "lean"]',
    style: {
      'width': LEAF_WIDTH,
      'height': LEAF_HEIGHT,
      'label': 'data(name)',
      'text-max-width': '140px',
      'font-size': '11px',
      'text-valign': 'center'
    }
  },
  // Full LOD: canvas label suppressed — HTML overlay (htmlOverlayLayer.ts) is
  // the sole renderer for full-LOD nodes.
  // Width/height updated to FULL_LOD_WIDTH × FULL_LOD_HEIGHT (240 × 180) in UX Rework:
  //   - width: FULL_LOD_WIDTH (240 = 1.5 × 160 pre-Amend-4) — user-requested 1.5× (was 320)
  //   - height: FULL_LOD_HEIGHT (180 = 1.5 × 120 pre-Amend-4) — user-requested 1.5× (was 360)
  //   - applied post-layout (style-only, no ELK re-run) — neighbouring nodes may overlap;
  //     this is the accepted trade-off under the "no relayout" rule.
  // CAVEAT: Cytoscape style changes on laid-out graphs do NOT trigger a relayout
  //   (Cytoscape JS applies style-driven sizing without re-running the external layout).
  //   Verified: cy.style().update() only redraws; no ELK run is triggered.
  {
    selector: 'node[lod = "full"]',
    style: {
      'width': FULL_LOD_WIDTH,
      'height': FULL_LOD_HEIGHT,
      'label': '',
      'background-opacity': 0.95
    }
  },
  // Amendment 3 (Bug 3): when node is full-LOD and NOT in small fallback,
  // ensure height is FULL_LOD_HEIGHT. This is the normal visible-overlay state.
  // Union selector: !lodDisplay matches nodes where the data key is absent (initial state);
  // lodDisplay = "normal" matches after htmlOverlayLayer.ts restores it from 'small'.
  // Spaces around '=' required by the Cytoscape selector parser.
  {
    selector: 'node[lod = "full"][!lodDisplay], node[lod = "full"][lodDisplay = "normal"]',
    style: {
      'width': FULL_LOD_WIDTH,
      'height': FULL_LOD_HEIGHT
    }
  },
  // Amendment (Amend 1): when zoom shrinks the node below MIN_READABLE_HEIGHT (now 50 px),
  // the overlay hides itself and sets lodDisplay = 'small'. This selector
  // re-enables the canvas name label so node identity is preserved at any zoom.
  // Height reverts to LEAF_HEIGHT (60) so the node does not appear oversized in fallback.
  // Spaces around '=' are required by the Cytoscape selector parser.
  {
    selector: 'node[lod = "full"][lodDisplay = "small"]',
    style: {
      'width': LEAF_WIDTH,
      'height': LEAF_HEIGHT,
      'label': 'data(name)',
      'font-size': '9px',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-max-width': '80px'
    }
  },
  {
    // PIG LAYOUT.PARENT_AFFORDANCE — distinguish compound parent nodes with border emphasis.
    // (Fix 4A — kept.)
    // PIG LAYOUT.CUES — background-image cue removed; DOM button handles cue.
    selector: 'node:parent',
    style: {
      'text-valign': 'top',
      'text-halign': 'left',
      'padding': '20px',
      'background-opacity': 0.10,
      'border-style': 'dashed',
      'border-color': '#0078d4',
      'border-width': 2,
      'font-weight': 'bold'
    }
  },
  {
    selector: 'node[?epistemicRisk]',
    style: {
      'border-color': '#e6a700',
      'border-width': 2
    }
  },
  {
    // Collapsed compound — distinct opacity and solid border so it reads as a collapsed container.
    // PIG LAYOUT.CUES — background-image cue removed; DOM button handles cue.
    selector: 'node.cy-expand-collapse-collapsed-node',
    style: {
      'background-opacity': 0.45,
      'border-style': 'solid',
      'border-width': 2
    }
  },
  {
    selector: 'edge',
    style: {
      'width': 1.5,
      'line-color': '#888888',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#888888',
      'curve-style': 'taxi'
    }
  },
  {
    selector: 'edge[edgeType="dataflow"]',
    style: {
      'line-color': '#4A90E2',
      'target-arrow-color': '#4A90E2',
      'width': 2
    }
  },
  // edgeType="requires" inherits the default edge style (no override).
  {
    selector: 'edge[edgeType="conflicts"]',
    style: {
      'line-color': '#D9534F',
      'target-arrow-color': '#D9534F',
      'source-arrow-shape': 'triangle',
      'source-arrow-color': '#D9534F'
    }
  },
  {
    selector: 'edge[edgeType="refines"]',
    style: {
      'line-style': 'dashed',
      'line-color': '#9B59B6',
      'target-arrow-color': '#9B59B6'
    }
  },
  {
    selector: 'edge[edgeType="unspecified"]',
    style: {
      'line-color': '#666666',
      'target-arrow-color': '#666666'
    }
  },
  {
    selector: 'edge.cy-expand-collapse-meta-edge',
    style: {
      'width': 3,
      'line-style': 'solid'
    }
  },
  {
    selector: 'edge.cy-expand-collapse-meta-edge[directionType="bidirection"]',
    style: {
      'line-style': 'dashed',
      'source-arrow-shape': 'triangle'
    }
  }
];
