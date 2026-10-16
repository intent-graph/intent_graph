# IntentGraph Logo

![IntentGraph Logo](logo.png)

## What It Represents
<!-- Lines 7-16 -->

The logo encodes the **IV-shaped context principle**:

> Keep the same lens nodes, but vary detail by distance from the target.

`I` = vertical lineage (root-to-target orientation).  
`V` = lateral neighborhood around the target (parent/children/link-neighbors).

This keeps local reasoning rich while controlling context weight.

## Anatomy
<!-- Lines 19-37 -->

```
  ___              ___
      \     |     /
       \    |    /
        \   |   /
         \  |  /
          \ | /
           \|/
          _____
```

- **The V** — detail gradient on lateral context.
- **Horizontal stubs** — target neighborhood (parent/children/intentlink neighbors).
- **Center vertical** — root-to-target orientation path.
- **Ground bar** — the convergence point. Where intent becomes concrete output.

The left half is an exact mirror of the right half. The shape is constructed by mirroring one path group with `matrix(-1,0,0,1,...)`.

## IV-context Modes
<!-- Lines 40-46 -->

Two serialization modes use the same lens nodes:

- **Full IV-context**: all nodes are serialized with full node detail.
- **Lean IV-context**: same node set, but only target + direct neighbors are full detail.  
  All other nodes are lean: `uid` + `name` (title) + `intent` + `epistemic_state`.

## Files
<!-- Lines 49-66 -->

The mark is `logo.svg` and nothing else: every derived asset embeds its path data unchanged and
only scales it.

| File | Format | Use |
|------|--------|-----|
| `logo.svg` | Vector (Inkscape) | Source of truth. Editable. |
| `logo.png` | Raster | For docs, GitHub, embeds. |
| `logo-white.svg`, `logo-white.png` | Vector, raster | The mark in white, for dark backgrounds. |
| `wordmark.svg` | Vector | Horizontal lockup: mark + "IntentGraph", black, for light backgrounds. Text is outlined. |
| `wordmark.png` | Raster, 1200 px wide, transparent | Same lockup, for places that do not take SVG. |
| `wordmark-white.svg`, `wordmark-white.png` | Vector, raster | The lockup in white, for dark backgrounds (GitHub dark theme). |
| `social-preview.png` | Raster, 1280x640 | GitHub social preview card (mark, name, tagline) on `#0d1117`. Set by hand in the repository settings. |
| `favicon.svg` | Vector, 128x128 | Mark on a rounded `#0d1117` badge: legible on light and dark browser chrome. |
| `favicon-32.png` | Raster, 32x32 | Same badge, for tabs and bookmarks. |
| `favicon-180.png` | Raster, 180x180 | Same badge, full-bleed square (the OS rounds it): `apple-touch-icon`. |
| `build_assets.py` | Python | Regenerates the wordmark, social preview and favicon files from `logo.svg`'s path data (needs `fonttools`, `rsvg-convert` and Inter Medium). |

## Using the Assets
<!-- Lines 69-92 -->

Light/dark switching in a README (GitHub serves the matching variant):

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="logo/wordmark-white.svg"/>
  <img src="logo/wordmark.svg" alt="IntentGraph" width="420"/>
</picture>
```

Favicon links for a web page:

```html
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="icon" href="favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="favicon-180.png">
```

Limits: the mark is a thin line drawing (stroke about 6% of its height). It reads well from about
32 px up, on white and on `#0d1117`; at 16 px it blurs into a gray smudge, so do not rely on it
at that size (the favicon files are tested at 32 px).

The name is set in Inter Medium (SIL Open Font License 1.1, <https://github.com/rsms/inter>) and
converted to outlines, so no font is needed to display the files.
