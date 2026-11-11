# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The announcements of the departments' own sites (ie, meh, bmi, pt, fluidi, hidro, ciah .mas.bg.ac.rs): only the
pages that have them (SITES), each stored as shown (a new version when its text or links change), and ie's notices
one by one (katedre_notices; build.py makes them posts of their subjects). Files are linked, not downloaded. Not
here: the rest of a site (about, staff, galleries), the Moodles (mat, cs, it0, vaz: a login) and the sites without
announcements (etc, motori, ppm) or that do not answer (omk, geotermal, au, tmm).

Usage: katedre.py sync [site ...]
  sync   fetch each site's announcement pages (or only the named sites'), store new versions and notices; a page or
         notice no longer there is marked gone.
"""
import json
import hashlib
import os
import re
import sqlite3
import sys
import time
from collections import deque
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Comment

from cent import FILE, name_icons, now
from nastava import instrument

DB = os.getenv("DB", str(Path(__file__).resolve().parent / "nastava.db"))
# One request at a time, never two in flight: 8 of the 10 sites are one server (147.91.26.9), so they are not crawled
# in parallel; 0.3 s keeps it to ~2-3 requests a second, a run ~3-4 minutes.
DELAY = float(os.getenv("DELAY", "0.3"))
MAX = int(os.getenv("MAX", "400"))  # pages a site, so a calendar or a gallery cannot crawl forever
# Each site: the pages a crawl starts from (read for their links), and the pages it keeps (its announcements; ie's
# subject pages also have the subject's material): only those are followed and stored.
SITES = {
    "ie": (["https://ie.mas.bg.ac.rs/predmeti.php"], r"/predmeti_p\.php\?SchoolSubjectID=\d+$"),
    "meh": (["https://meh.mas.bg.ac.rs/vesti/"], r"/vesti/(page/\d+/)?$"),
    "bmi": (["https://bmi.mas.bg.ac.rs/vesti/"], r"/vesti/([^/]+/)?$"),
    "pt": (["https://pt.mas.bg.ac.rs/"], r"^https://pt\.mas\.bg\.ac\.rs/$"),
    "fluidi": (["https://fluidi.mas.bg.ac.rs/"], r"^https://fluidi\.mas\.bg\.ac\.rs/[a-z]+/$"),
    "hidro": (["https://hidro.mas.bg.ac.rs/obavestenja.html"], r"/obavestenja\.html$"),
    "ciah": (["https://ciah.mas.bg.ac.rs/obavestenja"], r"/obavestenja$"),
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
create table if not exists katedre_notices (nid integer primary key autoincrement, key text unique, site text, url text,
	title text, label text, date text, html text, files text, first_seen text, last_seen text,
	gone integer not null default 0);
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


# A greeting ("Poštovani studenti,", "Поштоване колеге,") or a shout ("- Važno -"): a line that is not a title.
GREETING = r"(po[sš]tovan|поштован|drag|драг|na[sš]i|наши)[^,]{0,30},"
SHOUT = r"[-\s!]*((va[zž]no|obave[sš]tenje|novo)[-\s!]*)+"


def title_of(html):
    """A notice without a title (ie's): (title, the text without it). Its first line when that is short and more
    follows; else its first line that is not a greeting, without one in front, cut at a word, and the text whole."""
    lines = [strip(x) for x in re.split(r"<br\s*/?>", html)]
    skip = lambda x: not x or re.fullmatch(GREETING, x, re.I) or re.fullmatch(SHOUT, x, re.I)
    first = next((x for x in lines if x), "")
    i = lines.index(first)
    if first and len(first) <= 90 and not skip(first) and any(lines[i + 1:]):
        rest = re.split(r"<br\s*/?>", html, maxsplit=i + 1)[-1]
        title, html = first, re.sub(r"^(\s*<br\s*/?>)+", "", rest).strip()
    else:
        title = re.sub(r"^" + GREETING + r"\s*", "", next((x for x in lines if not skip(x)), first), flags=re.I)
        # A long line: its first sentence when that is short enough, else cut at a word.
        cut = re.match(r"(.{20,90}?[.!?])(\s+[A-ZŠĐČĆŽЂЉЊЋЏА-Я]|$)", title)
        title = title if len(title) <= 90 else cut[1] if cut else title[:80].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    title = re.sub(r"^" + GREETING + r"\s*", "", title, flags=re.I)
    return title[:1].upper() + title[1:].rstrip(":,"), html


def strip(html):
    return " ".join(BeautifulSoup(html, "html.parser").get_text(" ").split())


def day(label):
    """'05.11.2026' -> '2026-11-05'; None for no date ("- Bez datuma -") or a wrong one (01.01.1970, 16.12.1025)."""
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\.?\s*", label)
    try:
        d = m and date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None
    return d.isoformat() if d and 2000 <= d.year <= datetime.now().year + 1 else None


def ie_notices(content):
    """ie's subject page (parse's content) -> its notices, newest first as on the page: dict(label, date, title, html,
    files). Each is a block under "Vesti": an h2 with its date, an h2 with its text, its attachments' links. ie stacks
    backslashes before quotes (each edit adds some): they go. A notice posted twice the same day with the same text is
    one. A notice with no date or a wrong one has the one below it (an older one), else above."""
    soup = BeautifulSoup(content, "html.parser")
    h1 = next((h for h in soup.find_all("h1") if h.get_text(strip=True) == "Vesti"), None)
    out, seen = [], set()
    for d in h1.parent.find_all("div", recursive=False) if h1 else []:
        hs = d.find_all("h2", recursive=False)
        if len(hs) < 2:
            continue
        html = re.sub(r"\\+(?=[\"'])", "", hs[1].decode_contents()).strip()
        files = [[a["href"], a.get_text(strip=True)] for a in d.find_all("a", href=True) if not a.find_parent("h2")]
        label = hs[0].get_text(" ", strip=True)
        if (key := json.dumps([label, html, files])) in seen:
            continue
        seen.add(key)
        title, body = title_of(html)
        out.append(dict(label=label, date=day(label), title=title, html=body, files=files))
    for i, n in enumerate(out):
        n["date"] = n["date"] or next((o["date"] for o in out[i + 1:] + out[i::-1] if o["date"]), None)
    return out


# The sites whose notices are read one by one (the others' pages are only stored, until each has its reader).
NOTICES = {"ie": ie_notices}


def store_notices(db, site, url, notices, seen):
    """A notice is its page, its date as shown and its place among the page's notices of that date, counted from the
    oldest (a new one goes on top); a changed text updates it (the page's versions keep the old). One no longer on its
    page is marked gone. Nothing is deleted."""
    keys, count = [], {}
    for n in reversed(notices):
        count[n["label"]] = count.get(n["label"], 0) + 1
        key = hashlib.sha1(f"{url}|{n['label']}|{count[n['label']]}".encode()).hexdigest()
        keys.append(key)
        db.execute("insert into katedre_notices (key, site, url, title, label, date, html, files, first_seen, last_seen) "
                   "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict (key) do update set title = excluded.title, "
                   "date = excluded.date, html = excluded.html, files = excluded.files, last_seen = excluded.last_seen, "
                   "gone = 0", (key, site, url, n["title"], n["label"], n["date"], n["html"], json.dumps(n["files"]),
                                seen, seen))
    db.execute(f"update katedre_notices set gone = 1 where url = ? and key not in ({','.join('?' * len(keys))})",
               (url, *keys))


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


def crawl(db, s, site, starts, keep, seen):
    host, keep = urlsplit(starts[0]).hostname, re.compile(keep)
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
        # A login wall (most of pt's student wiki) is not a page: one that was public and is now behind it is gone.
        if re.search(r"<h1[^>]*>\s*Permission Denied\s*</h1>", content):
            continue
        if keep.search(url):
            got.add(url)
            new += store(db, site, url, title, content, seen)
            if site in NOTICES:
                store_notices(db, site, url, NOTICES[site](content), seen)
            db.commit()
        for u in map(norm, follow):
            if (urlsplit(u).hostname == host and u not in queued and keep.search(u) and not SKIP.search(u)
                    and not FILE.search(urlsplit(u).path)):
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
    s, seen = instrument(requests.Session()), now()
    s.headers["User-Agent"] = "Mozilla/5.0 (personal archive)"
    down = [n for n in names if not crawl(db, s, n, *SITES[n], seen)]
    if down:
        sys.exit(f"katedre: no answer from {', '.join(down)}")


if __name__ == "__main__":
    assert day("05.11.2026") == "2026-11-05" and day("01.01.1970") is day("16.12.1025") is day("- Bez datuma -") is None
    assert title_of("Konacne ocene<br/>\n<br/>\nVAŽNO") == ("Konacne ocene", "VAŽNO")
    assert title_of("Poštovani studenti,<br/>Prvi kolokvijum je 12.11.") == ("Prvi kolokvijum je 12.11.", "Poštovani studenti,<br/>Prvi kolokvijum je 12.11.")
    assert title_of("Poštovani studenti, u prilogu su rezultati.") == ("U prilogu su rezultati.", "Poštovani studenti, u prilogu su rezultati.")
    assert title_of("- Važno -<br/>Upis je u 12h.")[0] == "Upis je u 12h."
    assert title_of("U prilogu je spisak po grupama za izradu projektnog zadatka. Projekat se realizuje u grupama, a odbrane su 8. i 15. juna.")[0] == "U prilogu je spisak po grupama za izradu projektnog zadatka."
    assert title_of("Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali 320, a rezultati biće objavljeni na sajtu.")[0] == "Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali…"
    _n = ie_notices('<section><div><h1>Vesti</h1>'
                    '<div><h2>09.06.2026</h2><h2>Isto</h2></div><div><h2>09.06.2026</h2><h2>Isto</h2></div>'
                    '<div><h2>16.12.1025</h2><h2>Tema \\\\\\"x\\\\\\"</h2><div><a href="https://ie/f.pdf">f.pdf</a></div></div>'
                    '<div><h2>09.12.2025</h2><h2>Staro</h2></div></div></section>')
    assert [(n["date"], n["title"], n["files"]) for n in _n] == [("2026-06-09", "Isto", []), ("2025-12-09", 'Tema "x"', [["https://ie/f.pdf", "f.pdf"]]),
                                                               ("2025-12-09", "Staro", [])], _n
    match sys.argv[1:]:
        case ["sync", *names] if all(n in SITES for n in names):
            sync(names or list(SITES))
        case _:
            sys.exit(__doc__)
