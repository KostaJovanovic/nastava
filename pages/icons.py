"""The phone's PNG icons from static/app-icon.svg, and the notification badge: uv run --with playwright python pages/icons.py

An iPhone's home screen takes no SVG (apple-touch-icon), Android's install wants 192 and 512 px; the badge is the
logo alone, white on clear (Android tints it): static/sw.js.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

STATIC = Path(__file__).resolve().parent / "static"
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}


def badge(svg):
    """The icon's logo without its square, a little larger: 96 px, white on clear."""
    svg = re.sub(r'<rect width="40" height="40" fill="#0076b1" stroke="none"/>\n', "", svg)
    return svg.replace('transform="translate(6 6) scale(.7)"', 'transform="translate(2 2) scale(.9)"')


if __name__ == "__main__":
    svg = (STATIC / "app-icon.svg").read_text(encoding="utf-8")
    assert "#0076b1" not in badge(svg) and "scale(.9)" in badge(svg)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        for name, px, src in [*((n, s, svg) for n, s in SIZES.items()), ("badge.png", 96, badge(svg))]:
            g = b.new_page(viewport={"width": px, "height": px})
            g.set_content(f'<body style="margin:0">{src.replace("<svg ", f"<svg width={px} height={px} ", 1)}</body>')
            g.screenshot(path=STATIC / name, omit_background=True)
            print(name, px)
        b.close()
