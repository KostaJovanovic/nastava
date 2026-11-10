# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the departments' own sites (ie, etc, motori, meh, bmi, pt, ppm, fluidi, hidro, ciah .mas.bg.ac.rs): every
page reached by links from the site's start pages, on the same host, as it is shown (a new version when its text or
links change). Files are linked, not downloaded. Not here: the Moodles (mat, cs, it0, vaz: a login) and the sites that
do not answer (omk, geotermal, au, tmm).

Usage: katedre.py sync [site ...]
  sync   crawl each site (or only the named ones), store new versions; a page no longer reached is marked gone.
"""
import hashlib
import os
import re
import sqlite3
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Comment

from cent import FILE, name_icons, now

DB = os.getenv("DB", str(Path(__file__).resolve().parent / "nastava.db"))
DELAY = float(os.getenv("DELAY", "1.0"))
MAX = int(os.getenv("MAX", "400"))  # pages a site, so a calendar or a gallery cannot crawl forever
SITES = {
    "ie": ["https://ie.mas.bg.ac.rs/", "https://ie.mas.bg.ac.rs/predmeti.php"],
    "etc": ["https://etc.mas.bg.ac.rs/"],
    "motori": ["https://motori.mas.bg.ac.rs/"],
    "meh": ["https://meh.mas.bg.ac.rs/"],
    "bmi": ["https://bmi.mas.bg.ac.rs/"],
    "pt": ["https://pt.mas.bg.ac.rs/"],
    "ppm": ["https://ppm.mas.bg.ac.rs/"],
    "fluidi": ["https://fluidi.mas.bg.ac.rs/"],
    "hidro": ["https://hidro.mas.bg.ac.rs/"],
    "ciah": ["https://ciah.mas.bg.ac.rs/"],
}
# Not pages: WordPress's own, logins, feeds, a Moodle (a login), English copies, a directory listing's sort links, a
# wiki's actions (log in, edit, history) and a page again in another language.
SKIP = re.compile(r"/(wp-[a-z]+|feed|login|wp-login\.php|xmlrpc\.php|cdn-cgi|en|moodle)(/|$)|-en\.html$"
                  r"|[?&](C=|replytocom=|share=|do=|rev=|lang=)", re.I)
# The part of a page that is its content; else the whole body.
MAIN = ("main", "#main-content", "#content", ".entry-content", "article")
KEEP = {"href", "src", "alt", "title", "colspan", "rowspan"}
SCHEMA = """
create table if not exists katedre_pages (url text, sha text, site text, title text, html text, first_seen text,
	last_seen text, gone integer not null default 0, primary key (url, sha));
"""


def norm(url):
    """One URL a page: https, no fragment, a folder's index file as the folder."""
    p = urlsplit(url)
    path = re.sub(r"(^|/)index\.(html?|php)$", r"\1", p.path) or "/"
    return f"https://{p.hostname}{path}" + (f"?{p.query}" if p.query else "")


def parse(html, url):
    """A page -> (title, content html, the links to follow). The content: MAIN without scripts, forms, menus and
    hidden parts (an injected spam list is hidden), its links absolute and icons named (cent.name_icons). The links
    to follow: <a>, frames and a meta refresh, from the whole page (a menu is how a site is crawled)."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    follow = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]
    follow += [urljoin(url, f["src"]) for f in soup.find_all(["frame", "iframe"], src=True)]
    for m in soup.find_all("meta", attrs={"http-equiv": re.compile("refresh", re.I)}):
        if (r := re.search(r"url\s*=\s*['\"]?([^'\"\s;]+)", m.get("content", ""), re.I)):
            follow.append(urljoin(url, r[1]))
    main = next((x for sel in MAIN if (x := soup.select_one(sel))), soup.body or soup)
    for t in main.find_all(["script", "style", "noscript", "form", "svg", "nav", "header", "footer"]):
        t.decompose()
    for f in main.find_all("iframe"):  # an embedded form, video or document: a link to it
        if f.get("src"):
            a = soup.new_tag("a", href=urljoin(url, f["src"]))
            a.string = urljoin(url, f["src"])
            f.replace_with(a)
        else:
            f.decompose()
    for t in main.select('[style*="display:none"], [style*="display: none"], [hidden]'):
        t.decompose()
    for c in main.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in main.find_all(lambda t: ":" in t.name):  # Word's <o:p>
        t.unwrap()
    # Only what carries content: a page saved from Word is mostly its styles (2 MB for a table of results).
    for t in [main, *main.find_all(True)]:
        t.attrs = {k: v for k, v in t.attrs.items() if k in KEEP}
        if t.name in ("a", "img", "area"):
            for k in ("href", "src"):
                if k in t.attrs:
                    t[k] = urljoin(url, t[k])
    name_icons(main, url)
    content = main.decode_contents().strip() if main.name in ("body", "[document]") else str(main)
    return title, content, follow


def sha_of(content):
    """The text and the links: a page whose markup only shifts (a theme's ids, a nonce) is not a new version."""
    soup = BeautifulSoup(content, "html.parser")
    links = "|".join(x.get("href") or x.get("src") for x in soup.find_all(["a", "img"]) if x.get("href") or x.get("src"))
    return hashlib.sha1(f"{soup.get_text(' ', strip=True)}\n{links}".encode()).hexdigest()


def store(db, site, url, title, content, seen):
    """A new version when the content differs from every stored one; else that version is seen again (and is the
    newest). Returns whether it differs from the newest before."""
    sha = sha_of(content)
    last = db.execute("select sha from katedre_pages where url = ? order by last_seen desc limit 1", (url,)).fetchone()
    if db.execute("update katedre_pages set last_seen = ?, title = ?, gone = 0 where url = ? and sha = ?",
                  (seen, title, url, sha)).rowcount:
        return last[0] != sha
    db.execute("insert into katedre_pages values (?, ?, ?, ?, ?, ?, ?, 0)", (url, sha, site, title, content, seen, seen))
    return True


def fetch(s, url):
    """A page's html, or None for a file, an error page or a timeout."""
    try:
        r = s.get(url, timeout=60, stream=True)
    except requests.RequestException:
        return None, url
    finally:
        time.sleep(DELAY)
    if r.status_code != 200 or "html" not in r.headers.get("Content-Type", ""):
        r.close()
        return None, r.url
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    return r.text, r.url


def crawl(db, s, site, starts, seen):
    host = urlsplit(starts[0]).hostname
    queue, queued, got, new = deque(map(norm, starts)), set(map(norm, starts)), set(), 0
    while queue and len(got) < MAX:
        url = queue.popleft()
        html, final = fetch(s, url)
        if html is None or urlsplit(final).hostname != host:
            continue
        url = norm(final)
        if url in got:  # a redirect to a page already stored
            continue
        title, content, follow = parse(html, final)
        got.add(url)
        new += store(db, site, url, title, content, seen)
        db.commit()
        for u in map(norm, follow):
            if urlsplit(u).hostname == host and u not in queued and not SKIP.search(u) and not FILE.search(urlsplit(u).path):
                queued.add(u)
                queue.append(u)
    # A page not reached is gone, unless the crawl stopped early (MAX) or the site did not answer.
    if got and not queue:
        db.execute(f"update katedre_pages set gone = 1 where site = ? and url not in ({','.join('?' * len(got))})",
                   (site, *got))
        db.commit()
    print(f"{site}: {len(got)} pages, {new} new versions" + (f", stopped at {MAX} ({len(queue)} left)" if queue else "")
          + ("" if got else ", the site did not answer"), flush=True)
    return bool(got)


def sync(names):
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    # No retries (not nastava.session): a crawl meets dead links, and backing off on each would take minutes apiece.
    s, seen = requests.Session(), now()
    s.headers["User-Agent"] = "Mozilla/5.0 (personal archive)"
    down = [n for n in names if not crawl(db, s, n, SITES[n], seen)]
    if down:
        sys.exit(f"katedre: no answer from {', '.join(down)}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["sync", *names] if all(n in SITES for n in names):
            sync(names or list(SITES))
        case _:
            sys.exit(__doc__)
