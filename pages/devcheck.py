# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0"]
# ///
"""Dev mode (build.py main(dev=True), pages/serve.py) shows what a build writes: uv run pages/devcheck.py [nastava.db]

Builds twice into a temporary folder, as a deploy does (Pagefind skipped) and in dev mode, and compares every page
both ways. A page differs when build.py changes its data after writing it: dev mode renders the data as it is at the
end. The search's hidden copy (mark_for_pagefind) is in the build's item and news pages only.
"""

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

PF = re.compile(r'<div class="pf" data-pagefind-body>.*?</div>(?=</article>)', re.S)


def main(db):
    built = {}
    output = build.output
    # Every module that holds a writer (build.py and the sitegen modules import them by name): patched in each.
    holders = [m for name, m in sys.modules.items() if name == "build" or name.startswith("sitegen.")]

    def patch(**fs):
        for m in holders:
            for name, f in fs.items():
                if hasattr(m, name):
                    setattr(m, name, f)

    def keep(path, html, index=True, canonical=None):
        built[f"/{path.parent.relative_to(output.site_dir).as_posix()}/"] = html
        path.parent.mkdir(parents=True, exist_ok=True)

    def keep_page(path, html):
        built["/" + path.relative_to(output.site_dir).as_posix().removesuffix("index.html")] = html

    write, write_page = output.write, output.write_page
    patch(write=keep, write_page=keep_page, write_sitemap=lambda site: None, strip_pagefind=lambda *a, **k: None)
    build.shutil.which = lambda name: "npx"
    build.subprocess.run = lambda *a, **k: None
    with tempfile.TemporaryDirectory() as out:
        build.main(db, out)
        patch(write=write, write_page=write_page)
        build.main(db, out, dev_mode=True)
    pages = output.pages
    assert built.keys() == pages.keys(), sorted(built.keys() ^ pages.keys())[:10]
    bad = [u for u, html in built.items() if PF.sub("", html) != str(pages[u])]
    print(f"{len(built)} pages, {len(bad)} differ" + (": " + " ".join(bad[:20]) if bad else ""))
    kinds = {}
    for u in bad:  # the first difference of each kind of page (its first path segment)
        kinds.setdefault(u.split("/")[1], u)
    for u in kinds.values():
        a, b = PF.sub("", built[u]), str(pages[u])
        i = next(i for i in range(min(len(a), len(b)) + 1) if i == min(len(a), len(b)) or a[i] != b[i])
        print(f"\n{u} at {i}:\n  build: {a[max(0, i - 150) : i + 150]!r}\n  dev:   {b[max(0, i - 150) : i + 150]!r}")
    return not bad


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1] if len(sys.argv) > 1 else "nastava.db") else 1)
