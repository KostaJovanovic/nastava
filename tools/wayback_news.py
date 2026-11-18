# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Every saved copy of the old faculty sites' news pages (to 2014), raw, into work/wayback/news/ for the import.

uv run tools/wayback_news.py [--list]   (--list: only the counts)

From wayback_files.py's CDX listings (run it first): HTML pages whose address says news (vest, news, novost,
obavest, aktuel, arhivavesti, show_archives: the CuteNews feeds and their archives, najvesti.html, the departments'
vesti.html), and www's front page (its news before najvesti.html). Each copy, not only the newest: a feed's copy holds
its latest items only, so the copies together are the history. A copy the same size as one kept of that address is
skipped (the same page, recrawled). Bytes as saved, their charset unchanged. Resumable, as wayback_files.py.
"""

import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

from wayback_files import DELAY, OUT, SKIP_HOSTS, get, key_of, safe

import requests

NEWS_DIR = OUT / "news"
MANIFEST = OUT / "news.jsonl"
NEWS = re.compile(r"vest|news|novost|obavest|aktuel|show_archives|arhivavesti", re.I)
JUNK = re.compile(r"_files/|\.(css|js|gif|jpe?g|png|xml|mso)$|upimages/|/rss|feed", re.I)
FRONT = re.compile(r"^www/(index\.html?|default\.html?)?$")


def captures():
    """[(key, url, ts, length)], one per address and size, oldest first."""
    rows = []
    for cache in sorted(OUT.glob("cdx-*.txt")):
        rows += [ln.split(" ") for ln in cache.read_text("utf-8").splitlines() if ln.count(" ") == 4]
    if not rows:
        sys.exit("no CDX listings: run tools/wayback_files.py --list first")
    seen, out = set(), []
    for orig, ts, mime, status, length in sorted(rows, key=lambda r: r[1]):
        k = key_of(orig) + ("?" + orig.split("?", 1)[1].lower() if "?" in orig else "")
        if status != "200" or not mime.startswith("text/html") or k.split("/")[0] in SKIP_HOSTS or JUNK.search(orig):
            continue
        if not (NEWS.search(orig) or FRONT.match(k)) or (k, length) in seen:
            continue
        seen.add((k, length))
        out.append((k, orig, ts, length))
    return out


def main():
    caps = captures()
    print(f"{len(caps)} copies of {len({c[0] for c in caps})} pages", file=sys.stderr)
    if "--list" in sys.argv:
        return
    done = set()
    if MANIFEST.exists():
        done = {(j["key"], j["ts"]) for j in map(json.loads, MANIFEST.read_text("utf-8").splitlines()) if j.get("ok")}
    todo = [c for c in caps if (c[0], c[2]) not in done]
    print(f"{len(done)} done, {len(todo)} to fetch", file=sys.stderr, flush=True)
    s = requests.Session()
    s.headers["User-Agent"] = "nastava-archive (old faculty news)"
    with MANIFEST.open("a", encoding="utf-8") as log:
        for i, (k, orig, ts, length) in enumerate(todo, 1):
            r = get(s, f"https://web.archive.org/web/{ts}id_/{orig}")
            time.sleep(DELAY)
            row = dict(key=k, url=orig, ts=ts)
            if r is None or r.status_code != 200:
                row["err"] = r.status_code if r is not None else "no answer"
            else:
                # One folder per page (its query in the name), one file per copy: <timestamp>.html.
                folder = NEWS_DIR.joinpath(*map(safe, k.split("?")[0].split("/")))
                if "?" in k:
                    folder = folder.with_name(safe(folder.name + "__" + quote(k.split("?", 1)[1], safe="=&")))
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"{ts}.html"
                path.write_bytes(r.content)
                row.update(ok=True, size=len(r.content), sha256=hashlib.sha256(r.content).hexdigest(), path=path.relative_to(OUT).as_posix())
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            log.flush()
            if i % 50 == 0:
                print(f"{i}/{len(todo)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
