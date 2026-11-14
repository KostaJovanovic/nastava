"""The /stil/ page: the site's colours, fonts and logos, read from the real files."""

import re
from .known import STIL_FONTS, STIL_LOGOS
from .output import HERE


def css_colors(css):
    """style.css -> [(--name, light, dark)] of each variable holding a colour, first definition only (the old Safari
    block repeats them). A plain colour is the same in both themes."""
    seen = {}
    for name, value in re.findall(r"^\s*(--[\w-]+):\s*([^;]+);", css, re.M):
        if name in seen or not (value.startswith("light-dark(") or re.fullmatch(r"#[0-9a-fA-F]{3,8}", value)):
            continue
        if value.startswith("light-dark("):
            inner, depth = value[len("light-dark(") : -1], 0
            for i, c in enumerate(inner):  # the comma between the two, not one inside color-mix()
                depth += (c == "(") - (c == ")")
                if c == "," and not depth:
                    break
            seen[name] = (inner[:i].strip(), inner[i + 1 :].strip())
        else:
            seen[name] = (value, value)
    return [(n, *v) for n, v in seen.items()]


def png_size(path):
    head = path.read_bytes()[:24]  # the IHDR chunk: width and height, big-endian, at bytes 16 and 20
    return f"{int.from_bytes(head[16:20])}×{int.from_bytes(head[20:24])}"


def stil_data():
    static = HERE / "static"
    sprite = (static / "icons.svg").read_text(encoding="utf-8")
    # Each symbol as an SVG of its own, for its download link (a data: URL: no files to write).
    icons = [
        dict(id=i, svg=f'<svg xmlns="http://www.w3.org/2000/svg"{attrs}>{body}</svg>')
        for i, attrs, body in re.findall(r'<symbol id="([^"]+)"([^>]*)>(.*?)</symbol>', sprite, re.S)
    ]
    assert len(icons) == sprite.count("<symbol"), "icons.svg: a symbol /stil/ did not read"
    logos = [dict(name=n, size=png_size(static / n) if n.endswith(".png") else "SVG") for n in STIL_LOGOS]
    posters = sorted(p.name for p in static.iterdir() if p.name.startswith("og") and p.suffix in (".png", ".jpg"))
    fonts = [dict(name=n, family=f, files=files, weights=w, use=u) for n, f, files, w, u in STIL_FONTS]
    assert all((static / "fonts" / f).exists() for t in fonts for f in t["files"]), "STIL_FONTS: a file not in static/fonts"
    return dict(
        colors=css_colors((static / "style.css").read_text(encoding="utf-8")), icons=icons, logos=logos, posters=posters, fonts=fonts
    )
