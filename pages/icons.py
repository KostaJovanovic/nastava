"""The phone's PNG icons from static/app-icon.svg, and the notification badge: uv run --with playwright python pages/icons.py

An iPhone's home screen takes no SVG (apple-touch-icon), Android's install wants 192 and 512 px; the badge is the
logo alone, white on clear (Android tints it): static/sw.js.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

STATIC = Path(__file__).resolve().parent / "static"
SIZES = {"apple-touch-icon.png": 180, "icon-192.png": 192, "icon-512.png": 512}
# The Android app's (docs/PLAN-app.md): @capacitor/assets makes its icons from these (cd app && npx capacitor-assets
# generate --android), and the notification's small icon is the badge.
APP = STATIC.parent.parent / "app"
NOTIFY = APP / "android/app/src/main/res/drawable/ic_notify.png"


def badge(svg):
    """The icon's logo without its square, a little larger: 96 px, white on clear."""
    svg = re.sub(r'<rect width="40" height="40" fill="#0076b1" stroke="none"/>\n', "", svg)
    return svg.replace('transform="translate(6 6) scale(.7)"', 'transform="translate(2 2) scale(.9)"')


def foreground(svg):
    """Android's adaptive icon's front: the logo on clear, as placed on the web icon (the generated ic_launcher.xml
    insets it to the visible middle, whose mask keeps that 70%)."""
    return re.sub(r'<rect width="40" height="40" fill="#0076b1" stroke="none"/>\n', "", svg)


if __name__ == "__main__":
    svg = (STATIC / "app-icon.svg").read_text(encoding="utf-8")
    assert "#0076b1" not in badge(svg) and "scale(.9)" in badge(svg)
    assert "#0076b1" not in foreground(svg) and "scale(.7)" in foreground(svg)
    background = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"><rect width="1" height="1" fill="#0076b1"/></svg>'
    (APP / "assets").mkdir(exist_ok=True)
    app = [
        (APP / "assets/icon-only.png", 1024, svg),
        (APP / "assets/icon-foreground.png", 1024, foreground(svg)),
        (APP / "assets/icon-background.png", 1024, background),
        (NOTIFY, 96, badge(svg)),
    ]
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        for name, px, src in [*((STATIC / n, s, svg) for n, s in SIZES.items()), (STATIC / "badge.png", 96, badge(svg)), *app]:
            g = b.new_page(viewport={"width": px, "height": px})
            g.set_content(f'<body style="margin:0">{src.replace("<svg ", f"<svg width={px} height={px} ", 1)}</body>')
            g.screenshot(path=name, omit_background=True)
            print(name.name, px)
        b.close()
