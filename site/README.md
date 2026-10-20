# IntentGraph website

The static site for IntentGraph: what it is, why it exists, and how to try it. Plain HTML and CSS, no build step, no framework, no third-party requests (no CDN, no web fonts, no analytics). It is served by GitHub Pages from this folder.

## Table of Contents

1. [What it is](#what-it-is) _(Lines 13-24)_
1. [Preview locally](#preview-locally) _(Lines 27-35)_
1. [How it deploys](#how-it-deploys) _(Lines 38-42)_
1. [Keeping it true](#keeping-it-true) _(Lines 45-52)_
## What it is
<!-- Lines 13-24 -->

Three pages and a stylesheet:

- `index.html` — overview: the problem, the IntentGraph answer, how it works, comparison with prior approaches, where the project stands, where to start.
- `concepts.html` — graph, levels of detail, lens, epistemic state, projections, agents; three inline-SVG diagrams.
- `start.html` — a five-minute hands-on path, the reading order for the primers, the companion repository `ai_tooling`, feedback and contribution rules.
- `assets/style.css` — the single stylesheet; light and dark themes follow `prefers-color-scheme`.
- `assets/logo.svg`, `assets/logo-white.svg` — copies of `../logo/logo.svg` and `../logo/logo-white.svg`; the dark theme uses the white one. The favicon is the same SVG.
- `assets/obsidian_canvas_js_defaults.png` — screenshot on `index.html` of an Obsidian canvas of the JavaScript defaults graph (`ai_tooling/dev_guidelines/javascript_guidelines/intent_graphs/js_defaults.ig.yaml`), cropped to the content and reduced to a 256-colour palette. Its caption quotes the node counts (287 in the graph, 30 in the view): retake the screenshot or fix the caption if the graph changes much.

All links between pages are relative, so the site works opened from disk and under the project path (`/intent_graph/`) on GitHub Pages. Links into the repository are absolute `https://github.com/intent-graph/intent_graph/blob/main/<path>` URLs, because the site and the repository are served from different places.

## Preview locally
<!-- Lines 27-35 -->

Open `site/index.html` in a browser; nothing else is needed. To see it as Pages will serve it:

```bash
python3 -m http.server 8000 --directory site
```

then visit `http://localhost:8000/`. Test both colour schemes (browser dev tools, or your operating system setting) and a narrow window (360 px wide).

## How it deploys
<!-- Lines 38-42 -->

`.github/workflows/pages.yml` deploys `site/` with the official GitHub actions (`configure-pages`, `upload-pages-artifact`, `deploy-pages`). It runs on every push to `main` that touches `site/**`, and on demand (`workflow_dispatch`).

It does nothing useful until the repository owner enables Pages once: **Settings, Pages, Source: GitHub Actions**. Before that, a run stops at the `configure-pages` step with a message that Pages is not enabled. After that, the site appears at `https://intent-graph.github.io/intent_graph/`.

## Keeping it true
<!-- Lines 45-52 -->

The site makes claims about the project. When these change, update the pages in the same commit:

- install and command lines in `start.html` (the repository `README.md` is the reference; the commands were run against the bundled example graph),
- the status section of `index.html` (it follows `ARCHITECTURE.md` and `ROADMAP.md`),
- every `github.com/.../blob/main/<path>` link, if a file is renamed or moved.

Licence wording: `intent_graph` is source-available under the PolyForm Shield License 1.0.0 (see `../LICENSE.md`), and the site must keep saying exactly that. Only the companion repository `ai_tooling` (MIT code, CC BY 4.0 knowledge bases) is open source.
