# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""A local backup of the files the department sites link (cent.py's and katedre.py's pages and notices, every
version) and those of www.mas.bg.ac.rs's wiki pages (studije.py): files/sites/<host>/<path>. The site links them on their own servers; this copy is only for when they go.
One request at a time (8 of the sites are one server, as katedre.py); a file already here is skipped.

Usage: site_files.py list | download
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from common import DB, FILE, ROOT
from studije import SITE as STUDY_SITE, media_path

OUT = ROOT / "files" / "sites"
DELAY = float(os.getenv("DELAY", "0.3"))


def links(db):
    """Every file URL the stored pages and notices link, on a faculty host."""
    found = set()

    def add(base, html, files=None):
        soup = BeautifulSoup(html or "", "html.parser")
        hrefs = [a.get("href") for a in soup.find_all("a")] + [i.get("src") for i in soup.find_all("img")]
        hrefs += [f[0] for f in json.loads(files or "[]") if f]
        for h in filter(None, hrefs):
            url = urljoin(base, h.strip()).split("#")[0]
            parts = urlsplit(url)
            if (
                parts.scheme in ("http", "https")
                and parts.hostname
                and parts.hostname.endswith("mas.bg.ac.rs")
                and FILE.search(unquote(parts.path))
            ):
                found.add(url)

    for url, html in db.execute("SELECT url, html FROM katedre_pages"):
        add(url, html)
    for url, html, files in db.execute("SELECT url, html, files FROM katedre_notices"):
        add(url, html, files)
    for link, html in db.execute("SELECT link, html FROM cent_pages"):
        add(link, html)
    for link, html, files in db.execute("SELECT p.link, n.html, n.files FROM cent_notices n JOIN cent_pages p ON p.id = n.page"):
        add(link, html, files)
    # www.mas.bg.ac.rs (studije.py wiki_pages): every media link, as its plain /_media/ URL (FILE knows no .rtf, .gz).
    if db.execute("SELECT 1 FROM sqlite_master WHERE name = 'wiki_pages'").fetchone():
        for (html,) in db.execute("SELECT html FROM wiki_pages"):
            for tag in BeautifulSoup(html, "html.parser").find_all(["a", "img"]):
                if p := media_path(tag.get("href") or tag.get("src")):
                    found.add(STUDY_SITE + "_media/" + quote(p))
    return sorted(found)


def target(url):
    parts = urlsplit(url)
    path = [p for p in unquote(parts.path).split("/") if p not in ("", ".", "..")]
    # Windows: no reserved characters in a name; a query (a few download scripts) as part of the name.
    clean = lambda s: "".join("_" if c in '<>:"\\|?*' or ord(c) < 32 else c for c in s).strip(" .") or "_"
    name = clean(path[-1] + (f"_{parts.query}" if parts.query else ""))
    return OUT / parts.hostname / Path(*map(clean, path[:-1])) / name


def download(urls):
    s = requests.Session()
    s.headers["User-Agent"] = "nastava-arhiva (backup of linked files)"
    done = failed = 0
    for i, url in enumerate(urls, 1):
        path = target(url)
        if path.exists():
            continue
        try:
            r = s.get(url, timeout=60)
            r.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(r.content)
            done += 1
        except requests.RequestException as e:
            failed += 1
            print(f"failed {url}: {e}", file=sys.stderr, flush=True)
        if i % 100 == 0:
            print(f"{i}/{len(urls)}", flush=True)
        time.sleep(DELAY)
    print(f"{done} downloaded, {failed} failed, {len(urls) - done - failed} were here")


if __name__ == "__main__":
    if sys.argv[1:] not in (["list"], ["download"]):
        sys.exit(__doc__)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    urls = links(db)
    if sys.argv[1] == "list":
        from collections import Counter

        print(len(urls), "files:", dict(Counter(urlsplit(u).hostname for u in urls).most_common()))
    else:
        download(urls)
