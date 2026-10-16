#!/usr/bin/env python3
"""Regenerate the derived logo assets (wordmark, social preview, favicon) from the IV mark.

The mark's path data is copied verbatim from logo.svg; this script never redraws it. Text is
converted to outlines (no font needed to display the files). Needs: fonttools, rsvg-convert,
and the Inter Medium (500) .woff/.ttf (SIL Open Font License 1.1, https://github.com/rsms/inter):

    python3 build_assets.py --font inter-500.woff
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent

# --- the IV mark, exactly as in logo.svg -------------------------------------------------------
# Two mirrored path groups, stroke 6.5, round caps. Only the stroke colour is parameterised.
MARK_BBOX = (12.34, 15.28, 146.70, 127.74)  # x0, y0, x1, y1 (stroke included), in logo.svg units
MARK_W = MARK_BBOX[2] - MARK_BBOX[0]
MARK_H = MARK_BBOX[3] - MARK_BBOX[1]


def mark_group(color: str) -> str:
    return f"""<g transform="translate(-20.2425,-8.8712502)">
      <g style="stroke-width:6.5;stroke-dasharray:none">
        <path style="fill:none;stroke:{color};stroke-width:6.5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:none;stroke-opacity:1" d="M 35.834411,36.756286 56.548133,36.538794 99.611711,133.3231 99.569147,27.404095"/>
        <path style="fill:none;stroke:{color};stroke-width:6.5;stroke-linecap:round;stroke-linejoin:miter;stroke-dasharray:none;stroke-opacity:1" d="M 99.694776,133.3567 H 78.768218"/>
      </g>
      <g transform="matrix(-1,0,0,1,199.52919,0)" style="stroke-width:6.5;stroke-dasharray:none">
        <path style="fill:none;stroke:{color};stroke-width:6.5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:none;stroke-opacity:1" d="M 35.834411,36.549536 56.548133,36.538794 99.611711,133.3231 99.569147,27.404095"/>
        <path style="fill:none;stroke:{color};stroke-width:6.5;stroke-linecap:round;stroke-linejoin:miter;stroke-dasharray:none;stroke-opacity:1" d="M 99.694776,133.3567 H 78.768218"/>
      </g>
    </g>"""


def place_mark(color: str, x: float, y: float, height: float) -> str:
    """Mark whose stroke-inclusive bounding box has its top-left at (x, y) and the given height."""
    s = height / MARK_H
    return (
        f'<g transform="translate({x - MARK_BBOX[0] * s:.3f},{y - MARK_BBOX[1] * s:.3f}) scale({s:.5f})">'
        f"{mark_group(color)}</g>"
    )


# --- text as outlines ---------------------------------------------------------------------------
def text_outline(font: TTFont, text: str, size: float, x: float, baseline: float) -> tuple[str, float]:
    """SVG path data for `text` set at `size` px with its origin at (x, baseline); and its width."""
    gs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    cursor = 0.0
    for ch in text:
        name = cmap[ord(ch)]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + cursor * scale, baseline))
        gs[name].draw(tp)
        cursor += gs[name].width
    return pen.getCommands(), cursor * scale


def cap_height(font: TTFont) -> float:
    return font["OS/2"].sCapHeight / font["head"].unitsPerEm


def svg_doc(w: float, h: float, body: str, title: str, bg: str | None = None) -> str:
    rect = f'<rect width="{w:g}" height="{h:g}" fill="{bg}"/>' if bg else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" width="{w:g}" height="{h:g}" '
        f'role="img" aria-label="{title}">\n  <title>{title}</title>\n  {rect}\n  {body}\n</svg>\n'
    )


# --- assets ------------------------------------------------------------------------------------
def lockup(font: TTFont, color: str, mark_h: float, x: float, y: float) -> tuple[str, float, float]:
    """Mark + 'IntentGraph' on one line. Returns (svg body, width, height) of the lockup."""
    mark_w = MARK_W * mark_h / MARK_H
    cap = 0.50 * mark_h  # cap height of the name relative to the mark
    size = cap / cap_height(font)
    gap = 0.30 * mark_h
    baseline = y + mark_h / 2 + cap / 2  # name vertically centred on the mark
    d, tw = text_outline(font, "IntentGraph", size, x + mark_w + gap, baseline)
    body = place_mark(color, x, y, mark_h) + f'<path fill="{color}" d="{d}"/>'
    return body, mark_w + gap + tw, mark_h


def wordmark(font: TTFont, color: str) -> str:
    pad = 8.0
    body, w, h = lockup(font, color, 112.46, pad, pad)
    return svg_doc(round(w + 2 * pad, 2), round(h + 2 * pad, 2), body, "IntentGraph")


def social_preview(font: TTFont) -> str:
    W, H = 1280, 640
    fg, muted, bg, line = "#ffffff", "#c9d1d9", "#0d1117", "#30363d"
    mark_h = 190.0
    _, lw, lh = lockup(font, fg, mark_h, 0, 0)
    ox, oy = (W - lw) / 2, 170.0  # lockup centred horizontally, in the upper part of the card
    body, _, _ = lockup(font, fg, mark_h, ox, oy)
    tag = "Code, docs and specs are projections of one intent graph."
    tsize = 38.0
    td, tw = text_outline(font, tag, tsize, 0, 0)
    td, tw = text_outline(font, tag, tsize, (W - tw) / 2, oy + lh + 92)
    url = "github.com/intent-graph/intent_graph"
    usize = 24.0
    ud, uw = text_outline(font, url, usize, 0, 0)
    ud, uw = text_outline(font, url, usize, (W - uw) / 2, H - 62)
    frame = f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" fill="none" stroke="{line}" stroke-width="2"/>'
    inner = (
        frame
        + body
        + f'<path fill="{muted}" d="{td}"/>'
        + f'<path fill="#8b949e" d="{ud}"/>'
    )
    return svg_doc(W, H, inner, "IntentGraph: code, docs and specs are projections of one intent graph", bg=bg)


def favicon(color: str, bg: str, r: float = 26) -> str:
    """Square badge, mark centred; the mark is scaled, never redrawn. r = corner radius."""
    S = 128.0
    mark_w = 100.0
    mark_h = mark_w * MARK_H / MARK_W
    x, y = (S - mark_w) / 2, (S - mark_h) / 2
    body = (
        f'<rect width="{S:g}" height="{S:g}" rx="{r}" fill="{bg}"/>'
        + place_mark(color, x, y, mark_h)
    )
    return svg_doc(S, S, body, "IntentGraph")


def render(svg: Path, png: Path, width: int, height: int | None = None) -> None:
    cmd = ["rsvg-convert", "-w", str(width)]
    if height:
        cmd += ["-h", str(height)]
    subprocess.run([*cmd, "-o", str(png), str(svg)], check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", required=True, type=Path, help="Inter Medium (500), .woff or .ttf")
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args()
    font = TTFont(a.font)
    out: Path = a.out

    files = {
        "wordmark.svg": wordmark(font, "#000000"),
        "wordmark-white.svg": wordmark(font, "#ffffff"),
        "social-preview.svg": social_preview(font),  # intermediate, deleted after rendering
        "favicon.svg": favicon("#ffffff", "#0d1117"),
    }
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")

    render(out / "wordmark.svg", out / "wordmark.png", 1200)
    render(out / "wordmark-white.svg", out / "wordmark-white.png", 1200)
    render(out / "social-preview.svg", out / "social-preview.png", 1280, 640)
    (out / "social-preview.svg").unlink()
    render(out / "favicon.svg", out / "favicon-32.png", 32)
    # touch icon: full-bleed square, the OS applies its own rounded mask
    (out / "favicon-touch.svg").write_text(favicon("#ffffff", "#0d1117", r=0), encoding="utf-8")
    render(out / "favicon-touch.svg", out / "favicon-180.png", 180)
    (out / "favicon-touch.svg").unlink()


if __name__ == "__main__":
    main()
