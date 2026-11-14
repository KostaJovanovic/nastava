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
import sys
import time
from collections import deque
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Comment

from common import FILE, connect, name_icons, now, plain_session

# One request at a time, never two in flight: 8 of the 10 sites are one server (147.91.26.9), so they are not crawled
# in parallel; 0.3 s keeps it to ~2-3 requests a second, a run ~3-4 minutes.
DELAY = float(os.getenv("DELAY", "0.3"))
MAX = int(os.getenv("MAX", "400"))  # pages a site, so a calendar or a gallery cannot crawl forever
# Each site: the pages a crawl starts from (read for their links), and the pages it keeps (its announcements; ie's
# subject pages also have the subject's material): only those are followed and stored.
SITES = {
    "ie": (
        ["https://ie.mas.bg.ac.rs/predmeti.php", "https://ie.mas.bg.ac.rs/novosti.php"],
        r"/(predmeti_p\.php\?SchoolSubjectID=\d+|novosti\.php)$",
    ),
    "meh": (["https://meh.mas.bg.ac.rs/vesti/"], r"/vesti/(page/\d+/)?$"),
    "bmi": (["https://bmi.mas.bg.ac.rs/vesti/"], r"/vesti/$"),
    # Its home page shows the news from these with a script.
    "pt": (
        ["https://pt.mas.bg.ac.rs/api.php?tip=vesti", "https://pt.mas.bg.ac.rs/api.php?tip=poslovi"],
        r"/api\.php\?tip=(vesti|poslovi)$",
    ),
    "fluidi": (["https://fluidi.mas.bg.ac.rs/"], r"^https://fluidi\.mas\.bg\.ac\.rs/[a-z]+/$"),
    "hidro": (["https://hidro.mas.bg.ac.rs/obavestenja.html"], r"/obavestenja\.html$"),
    "ciah": (["https://ciah.mas.bg.ac.rs/obavestenja"], r"/obavestenja$"),
}
# Not pages: WordPress's own, logins, feeds, a Moodle (a login), English copies, a directory listing's sort links, a
# wiki's actions (log in, edit, history) and a page again in another language.
SKIP = re.compile(
    r"/(wp-[a-z]+|feed|login|wp-login\.php|xmlrpc\.php|cdn-cgi|en|moodle)(/|$)|-en\.html$"
    r"|[?&](C=|replytocom=|share=|do=|rev=|lang=)",
    re.I,
)
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
        if r := re.search(r"url\s*=\s*['\"]?([^'\"\s;]+)", m.get("content", ""), re.I):
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
    if db.execute(
        "update katedre_pages set last_seen = ?, title = ?, gone = 0 where url = ? and sha = ?", (seen, title, url, sha)
    ).rowcount:
        return last[0] != sha
    db.execute("insert into katedre_pages values (?, ?, ?, ?, ?, ?, ?, 0)", (url, sha, site, title, content, seen, seen))
    return True


# A greeting ("Poštovani studenti,", "Поштоване колеге,") or a shout ("- Važno -"): a line that is not a title.
GREETING = r"(po[sš]tovan|поштован|drag|драг|na[sš]i|наши)[^,]{0,30},"
SHOUT = r"[-\s!]*((va[zž]no|obave[sš]tenje|novo)[-\s!]*)+"
LINE = r"<br\s*/?>|</?p\b[^>]*>|</?[uo]l\b[^>]*>|</?li\b[^>]*>"  # where a notice's text breaks a line


def title_of(html):
    """A notice without a title (ie's): (title, the text without it). Its first line when that is short and more
    follows; else its first line that is not a greeting, without one in front, cut at a word, and the text whole."""
    lines = [strip(x) for x in re.split(LINE, html)]
    skip = lambda x: not x or re.fullmatch(GREETING, x, re.I) or re.fullmatch(SHOUT, x, re.I)
    first = next((x for x in lines if x), "")
    i = lines.index(first)
    if first and len(first) <= 90 and not skip(first) and any(lines[i + 1 :]):
        rest = re.split(LINE, html, maxsplit=i + 1)[-1]
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


DATE = r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})"


def day(label, latest=None):
    """'05.11.2026' or '25. 9. 2024.' -> '2026-11-05'; None for no date ("- Bez datuma -") or a wrong one (01.01.1970,
    16.12.1025, after latest: next year by default)."""
    m = re.fullmatch(r"\s*" + DATE + r"\.?\s*", label or "")
    try:
        d = m and date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None
    return d.isoformat() if d and date(2000, 1, 1) <= d <= (latest or date(datetime.now().year + 1, 12, 31)) else None


def finish(raw):
    """A page's notices as found, newest first (dict(label: its date as shown, or its title where none is; title:
    None when the site gives none; html; files; date: when not the label's)) -> the notices to store: dict(label, date,
    title, html, files). The backslashes ie stacks before quotes (each edit adds some) go; an empty one (a heading over
    nothing) goes; one posted twice the same day with the same text is one. One with no date or a wrong one has the
    one below it (older), else above."""
    out, seen = [], set()
    for n in raw:
        html = re.sub(r"\\+(?=[\"'])", "", n["html"]).strip()
        if not strip(html) and not n["files"] or (key := json.dumps([n["label"], html, n["files"]])) in seen:
            continue
        seen.add(key)
        title, body = (n["title"], html) if n.get("title") else title_of(html)
        out.append(dict(label=n["label"], date=n.get("date") or day(n["label"]), title=title, html=body, files=n["files"]))
    for i, n in enumerate(out):
        n["date"] = n["date"] or next((o["date"] for o in out[i + 1 :] + out[i::-1] if o["date"]), None)
    return out


def files_in(el, only_files=False):
    """[href, text] of the links in el; only_files: those to a file (a pdf, not a page)."""
    return [
        [a["href"], a.get_text(strip=True)] for a in el.find_all("a", href=True) if not only_files or FILE.search(urlsplit(a["href"]).path)
    ]


def inner(els):
    """The html of a run of nodes (tags and text)."""
    return "".join(str(x) for x in els).strip()


def ie_notices(soup):
    """ie's subject page: a block under "Vesti" a notice: an h2 with its date, an h2 with its text, its attachments."""
    h1 = next((h for h in soup.find_all("h1") if h.get_text(strip=True) == "Vesti"), None)
    raw = []
    for d in h1.parent.find_all("div", recursive=False) if h1 else []:
        hs = d.find_all("h2", recursive=False)
        if len(hs) >= 2:
            raw.append(
                dict(
                    label=hs[0].get_text(" ", strip=True),
                    html=hs[1].decode_contents(),
                    files=[f for f in files_in(d) if f not in files_in(hs[1])],
                )
            )
    return raw


def ie_novosti(soup):
    """ie's department news (novosti.php): an h5 with the date, then the text; a bold first line is its title."""
    raw = []
    for h in soup.find_all("h5"):
        body = list(h.next_siblings)
        b = next((x for x in body if getattr(x, "name", None) == "p"), None)
        b = b and b.find("b")
        title = b and b.get_text(" ", strip=True)
        if b:
            b.decompose()
        html = re.sub(r"^(\s*<br\s*/?>)+|(?<=<p>)(\s*<br\s*/?>)+", "", inner(body))
        raw.append(dict(label=h.get_text(strip=True), title=title, html=html, files=[]))
    return raw


def fluidi_notices(soup):
    """A fluidi subject page: an h2 (its title), its date in the div after it, its text in the p after that (some
    are only a heading: "Обавештење" over nothing)."""
    raw = []
    for h in soup.find_all("h2"):
        d, p = h.find_next_sibling("div"), h.find_next_sibling("p")
        if d and p and day(d.get_text()):
            raw.append(dict(label=d.get_text(strip=True), title=h.get_text(" ", strip=True), html=p.decode_contents(), files=[]))
    return raw


def ciah_notices(soup):
    """ciah's notices: a p that starts with its date in bold, and what follows up to the next one."""
    raw = []
    for el in (soup.main or soup).children:
        b = next((c for c in el.children if str(c).strip()), None) if getattr(el, "name", None) == "p" else None
        if getattr(b, "name", None) == "b" and day(b.get_text()):
            label = b.get_text(strip=True)
            b.decompose()
            raw.append(dict(label=label, title=None, html="", files=[], els=[el]))
        elif raw:
            raw[-1]["els"].append(el)
    for n in raw:
        els = n.pop("els")
        n["html"] = re.sub(r"^(\s*<p>)?(\s*<br\s*/?>)+", r"\1", inner(els))
        n["files"] = [f for e in els if hasattr(e, "find_all") for f in files_in(e, only_files=True)]
    return raw


def hidro_notices(soup):
    """hidro's notices: a p that ends with its date in italics, in brackets."""
    raw = []
    for i in soup.find_all("i"):
        if day(i.get_text()) and i.parent.name == "p":
            label, p = i.get_text(strip=True), i.parent
            i.decompose()
            raw.append(
                dict(
                    label=label,
                    title=None,
                    html=re.sub(r"\(\s*\)\s*$", "", p.decode_contents().strip()),
                    files=files_in(p, only_files=True),
                )
            )
    return raw


def bmi_notices(soup):
    """bmi's news list: an article with its date, its title (a link to the news) and a summary."""
    raw = []
    for a in soup.find_all("article"):
        t, h = a.find("time"), a.find("h2")
        link = h and h.find("a", href=True)
        if t and h:
            more = f'<p><a href="{link["href"]}">Pročitaj vest</a></p>' if link else ""
            raw.append(
                dict(
                    label=t.get_text(strip=True),
                    title=h.get_text(" ", strip=True),
                    html=inner(p for p in a.find_all("p") if not p.find("time")) + more,
                    files=[],
                )
            )
    return raw


def meh_notices(soup):
    """meh's news: an h5 (its title), its text up to the next hr. Its date: the one its title gives ("… - датум
    објаве 31.03.2019."), else the first in its text (not after today), else the month of its first upload
    (wp-content/uploads/2026/06/), else its neighbours'. Its title without the department's name and that date; the
    h5 as shown is its label (its key)."""
    raw = []
    for h in soup.find_all("h5"):
        els = []
        for x in h.next_siblings:
            if getattr(x, "name", None) in ("hr", "h5"):
                break
            els.append(x)
        html, label = inner(els), h.get_text(" ", strip=True)
        posted = re.search(r"\s*-\s*датум објаве\s*(" + DATE + r"\.?)\s*$", label)
        when = next((d for m in re.finditer(DATE, strip(html)) if (d := day(m[0], date.today()))), None)
        up = re.search(r"/uploads/(20\d\d)/(\d\d)/", html)
        title = re.sub(r"^Катедра за механизацију\s*-\s*", "", label[: posted.start()] if posted else label)
        raw.append(
            dict(label=label, title=title, html=html, files=[], date=(posted and day(posted[1])) or when or (up and f"{up[1]}-{up[2]}-01"))
        )
    return raw


def pt_notices(text):
    """pt's news and job offers (api.php, JSON: naslov, datum, tekst, embed, link_url, link_tekst, att_url, att_name)."""
    raw = []
    for x in json.loads(text or "[]") or []:
        embed = re.search(r'src="([^"]+)"', x.get("embed") or "")
        html = (
            (x.get("tekst") or "")
            + (f'<p><a href="{embed[1]}">{embed[1]}</a></p>' if embed else "")
            + (f'<p><a href="{x["link_url"]}">{x.get("link_tekst") or x["link_url"]}</a></p>' if x.get("link_url") else "")
        )
        raw.append(
            dict(
                label=x.get("datum") or x.get("naslov") or "",
                title=x.get("naslov"),
                html=html,
                files=[[x["att_url"], x.get("att_name") or ""]] if x.get("att_url") else [],
            )
        )
    return raw


# Each kept page's reader: its address -> the notices as found (finish makes them notices). pt's is JSON, not a page.
NOTICES = [
    (r"ie\.mas\.bg\.ac\.rs/novosti\.php$", ie_novosti),
    (r"ie\.mas\.bg\.ac\.rs/predmeti_p", ie_notices),
    (r"fluidi\.", fluidi_notices),
    (r"ciah\.", ciah_notices),
    (r"hidro\.", hidro_notices),
    (r"bmi\.mas\.bg\.ac\.rs/vesti/$", bmi_notices),
    (r"meh\.", meh_notices),
    (r"pt\.mas\.bg\.ac\.rs/api\.php", pt_notices),
]


def notices_of(url, content):
    """The notices of a kept page (NOTICES), or None for a page without a reader."""
    read = next((f for rx, f in NOTICES if re.search(rx, url)), None)
    if read is None:
        return None
    return finish(read(content if read is pt_notices else BeautifulSoup(content, "html.parser")))


def store_notices(db, site, url, notices, seen):
    """A notice is its page, its date as shown and its place among the page's notices of that date, counted from the
    oldest (a new one goes on top); a changed text updates it (the page's versions keep the old). One no longer on its
    page is marked gone. Nothing is deleted."""
    keys, count = [], {}
    for n in reversed(notices):
        count[n["label"]] = count.get(n["label"], 0) + 1
        key = hashlib.sha1(f"{url}|{n['label']}|{count[n['label']]}".encode()).hexdigest()
        keys.append(key)
        db.execute(
            "insert into katedre_notices (key, site, url, title, label, date, html, files, first_seen, last_seen) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) on conflict (key) do update set title = excluded.title, "
            "date = excluded.date, html = excluded.html, files = excluded.files, last_seen = excluded.last_seen, "
            "gone = 0",
            (key, site, url, n["title"], n["label"], n["date"], n["html"], json.dumps(n["files"]), seen, seen),
        )
    db.execute(f"update katedre_notices set gone = 1 where url = ? and key not in ({','.join('?' * len(keys))})", (url, *keys))


def fetch(s, url):
    """A page's html (or JSON: pt's news), or None for a file, an error page or a timeout."""
    try:
        r = s.get(url, timeout=60, stream=True)
    except requests.RequestException:
        return None, url
    finally:
        time.sleep(DELAY)
    if r.status_code != 200 or not re.search(r"html|json", r.headers.get("Content-Type", "")):
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
        # JSON (pt's news) is kept as it came: nothing to follow.
        title, content, follow = ("", html, []) if html.lstrip()[:1] in ("[", "{") else parse(html, final)
        # A login wall (most of pt's student wiki) is not a page: one that was public and is now behind it is gone.
        if re.search(r"<h1[^>]*>\s*Permission Denied\s*</h1>", content):
            continue
        if keep.search(url):
            got.add(url)
            new += store(db, site, url, title, content, seen)
            if (notices := notices_of(url, content)) is not None:
                store_notices(db, site, url, notices, seen)
            db.commit()
        for u in map(norm, follow):
            if (
                urlsplit(u).hostname == host
                and u not in queued
                and keep.search(u)
                and not SKIP.search(u)
                and not FILE.search(urlsplit(u).path)
            ):
                queued.add(u)
                queue.append(u)
    # A page not reached is gone, unless the crawl stopped early (MAX) or the site did not answer.
    if got and not queue:
        db.execute(f"update katedre_pages set gone = 1 where site = ? and url not in ({','.join('?' * len(got))})", (site, *got))
        db.commit()
    print(
        f"{site}: {len(got)} pages, {new} new versions"
        + (f", stopped at {MAX} ({len(queue)} left)" if queue else "")
        + ("" if got else ", the site did not answer"),
        flush=True,
    )
    return bool(got)


def sync(names):
    db = connect(SCHEMA)
    # No retries (not nastava.session): a crawl meets dead links, and backing off on each would take minutes apiece.
    s, seen = plain_session(), now()
    down = [n for n in names if not crawl(db, s, n, *SITES[n], seen)]
    if down:
        sys.exit(f"katedre: no answer from {', '.join(down)}")


if __name__ == "__main__":
    assert day("05.11.2026") == "2026-11-05" and day("01.01.1970") is day("16.12.1025") is day("- Bez datuma -") is None
    assert title_of("Konacne ocene<br/>\n<br/>\nVAŽNO") == ("Konacne ocene", "VAŽNO")
    assert title_of("Poštovani studenti,<br/>Prvi kolokvijum je 12.11.") == (
        "Prvi kolokvijum je 12.11.",
        "Poštovani studenti,<br/>Prvi kolokvijum je 12.11.",
    )
    assert title_of("Poštovani studenti, u prilogu su rezultati.") == (
        "U prilogu su rezultati.",
        "Poštovani studenti, u prilogu su rezultati.",
    )
    assert title_of("- Važno -<br/>Upis je u 12h.")[0] == "Upis je u 12h."
    assert (
        title_of(
            "U prilogu je spisak po grupama za izradu projektnog zadatka. Projekat se realizuje u grupama, a odbrane su 8. i 15. juna."
        )[0]
        == "U prilogu je spisak po grupama za izradu projektnog zadatka."
    )
    assert (
        title_of(
            "Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali 320, a rezultati biće objavljeni na sajtu."
        )[0]
        == "Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali…"
    )
    assert day("25. 9. 2024.") == "2024-09-25" and day("17.06.2026", date(2026, 6, 16)) is None
    _sum = lambda url, html: [(n["label"], n["date"], n["title"], strip(n["html"]), n["files"]) for n in notices_of(url, html)]
    _n = _sum(
        "https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=5",
        "<section><div><h1>Vesti</h1>"
        "<div><h2>09.06.2026</h2><h2>Isto</h2></div><div><h2>09.06.2026</h2><h2>Isto</h2></div>"
        '<div><h2>16.12.1025</h2><h2>Tema \\\\\\"x\\\\\\"</h2><div><a href="https://ie/f.pdf">f.pdf</a></div></div>'
        "<div><h2>09.12.2025</h2><h2>Staro</h2></div></div></section>",
    )
    assert [x[1:3] + x[4:] for x in _n] == [
        ("2026-06-09", "Isto", []),
        ("2025-12-09", 'Tema "x"', [["https://ie/f.pdf", "f.pdf"]]),
        ("2025-12-09", "Staro", []),
    ], _n
    # The other sites' layouts, from their pages (11.11.2026.).
    assert _sum(
        "https://ie.mas.bg.ac.rs/novosti.php",
        "<div><h5>14.10.2019.</h5><p><b> Skup ICES 2019</b><br/><br/>Naši "
        "studenti,<br/><br/>učestvovali su.</p></div><div><h5>16.03.2020.</h5><p><b> </b><br/><br/>Dragi naši studenti,<br/>"
        "nastava je obustavljena.</p></div>",
    ) == [
        ("14.10.2019.", "2019-10-14", "Skup ICES 2019", "Naši studenti, učestvovali su.", []),
        ("16.03.2020.", "2020-03-16", "Nastava je obustavljena.", "Dragi naši studenti, nastava je obustavljena.", []),
    ]
    assert _sum(
        "https://fluidi.mas.bg.ac.rs/omf/",
        "<h2> Обавештење о промени учионице </h2><div><span>08.10.2026.</span>"
        "</div><p>Настава је у учионици <strong>320</strong>.<br/></p><h2> Обавештење </h2><div><span>06.10.2026.</span>"
        "</div><p><br/></p>",
    ) == [("08.10.2026.", "2026-10-08", "Обавештење о промени учионице", "Настава је у учионици 320 .", [])]
    assert _sum(
        "https://ciah.mas.bg.ac.rs/obavestenja",
        "<main><h2>Обавештења</h2><p>\n<b>25.7.2022.</b><br/><br/>Обука.</p>"
        '<p>Пријава <a href="https://ciah/p.doc">ОВДЕ</a> (<a href="https://ciah/multi.html">листа</a>)</p>\n*минимум 5.\n'
        "<p><b>01.4.2022.</b><br/><br/>Друга.</p></main>",
    ) == [
        ("25.7.2022.", "2022-07-25", "Обука.", "Пријава ОВДЕ ( листа ) *минимум 5.", [["https://ciah/p.doc", "ОВДЕ"]]),
        ("01.4.2022.", "2022-04-01", "Друга.", "Друга.", []),
    ]
    assert _sum(
        "https://hidro.mas.bg.ac.rs/obavestenja.html",
        "<p><b>ОБАВЕШТЕЊА</b></p><p>Екскурзија одлаже се за 2027. год. (<i>01.09.2026.</i>)</p>",
    ) == [("01.09.2026.", "2026-09-01", "Екскурзија одлаже се за 2027. год.", "Екскурзија одлаже се за 2027. год.", [])]
    assert _sum(
        "https://bmi.mas.bg.ac.rs/vesti/",
        '<article><div><p><time>25. 9. 2024.</time></p><h2><a href="https://bmi/v/qi/">'
        "Promocija knjige</a></h2><p>Pozivamo vas.</p></div></article>",
    ) == [("25. 9. 2024.", "2024-09-25", "Promocija knjige", "Pozivamo vas. Pročitaj vest", [])]
    assert _sum(
        "https://meh.mas.bg.ac.rs/vesti/",
        "<div><h5>ТУ – <span>резултати</span></h5><p>Колоквијум одржан 11.06.2026. "
        '<a href="https://meh/wp-content/uploads/2026/06/K3.pdf">овде</a>.</p><hr/><h5>Download</h5><p>Нов материјал '
        '<a href="https://meh/wp-content/uploads/2025/03/a.pdf">a</a>.</p><hr/><h5>Обавештење</h5><p>Сајт ради.</p><hr/>'
        "<h5>Катедра за механизацију - Обавештење - датум објаве 31.03.2019.</h5><p>Од 2.4.2019.</p></div>",
    ) == [
        ("ТУ – резултати", "2026-06-11", "ТУ – резултати", "Колоквијум одржан 11.06.2026. овде .", []),
        ("Download", "2025-03-01", "Download", "Нов материјал a .", []),
        ("Обавештење", "2019-03-31", "Обавештење", "Сајт ради.", []),
        ("Катедра за механизацију - Обавештење - датум објаве 31.03.2019.", "2019-03-31", "Обавештење", "Од 2.4.2019.", []),
    ]
    assert _sum(
        "https://pt.mas.bg.ac.rs/api.php?tip=vesti",
        '[{"naslov": "Procesing", "datum": "02.03.2027.", "tekst": "<p>Kongres.</p>", '
        '"link_url": "https://procesing.rs", "att_url": "https://pt/a.pdf", "att_name": "Program"}]',
    ) == [("02.03.2027.", "2027-03-02", "Procesing", "Kongres. https://procesing.rs", [["https://pt/a.pdf", "Program"]])]
    assert notices_of("https://pt.mas.bg.ac.rs/api.php?tip=poslovi", "[]") == [] and notices_of("https://meh.x/", "") == []
    match sys.argv[1:]:
        case ["sync", *names] if all(n in SITES for n in names):
            sync(names or list(SITES))
        case _:
            sys.exit(__doc__)
