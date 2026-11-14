"""The faculty's wiki pages this site shows (studije.py wiki_pages) and the Linkovi page's groups."""

import re
import sys
from collections import defaultdict
from urllib.parse import quote, unquote, urljoin, urlsplit
from bs4 import BeautifulSoup
from studije import SHOWN, SITE as STUDY_SITE
from wiki_tidy import CLASSES as WIKI_CLASSES, lexicon, recase, tidy as wiki_tidy
from .known import LINKS, UPIS, UPIS_TABS
from .output import HERE
from .text import slug


def link_groups(archived):
    """LINKS as link.html shows them: (group, [(name, href, icon, data-domain, the card's second line)]). The second
    line: the address; a shown page of the faculty's its site (its paths are long: vaznidatumioas); with a data-domain
    (the drive), OneDrive. archived: the wiki paths the database has; one it lacks (studije.py not run yet) links the
    faculty's page."""
    wiki = {h[3:] for _, links in LINKS for _, h, _, _ in links if h.startswith("mf:")}
    assert wiki <= SHOWN, f"LINKS has pages studije.py does not keep: {wiki - SHOWN}"
    mf = lambda path: wiki_href(path) if path in archived else STUDY_SITE + path
    return [
        (
            group,
            [
                (name, mf(h[3:]), icon, domain, "www.mas.bg.ac.rs")
                if h.startswith("mf:")
                else (name, h, icon, domain, "OneDrive" if domain else h.split("://")[-1].rstrip("/"))
                for name, h, icon, domain in links
            ],
        )
        for group, links in LINKS
    ]


def link_icons():
    """{host: file} of the sites' own icons in static/link (saved by hand), for the cards (link_card.html)."""
    return {p.stem: p.name for p in (HERE / "static" / "link").iterdir()}


def archived_wiki(db):
    """The wiki paths wiki_pages has (none before studije.py made the table)."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'wiki_pages'").fetchone():
        return set()
    return {r[0] for r in db.execute("SELECT DISTINCT path FROM wiki_pages")}


def wiki_href(path):
    """A shown wiki page's address here: /mf/<path>/, in Latin as the site's other URLs (upis/konkurs-дас)."""
    return "/mf/" + "/".join(map(slug, path.split("/"))) + "/"


def wiki_link(value, hrefs):
    """A link to a page of www.mas.bg.ac.rs that this site keeps (hrefs: {wiki path: its /mf/ href}), as that copy;
    else None. Both forms the wiki writes: /ns/page and doku.php?id=ns:page; a folder's address is its start page."""
    u = urlsplit(urljoin(STUDY_SITE, value))
    if u.netloc not in ("www.mas.bg.ac.rs", "mas.bg.ac.rs"):
        return None
    path = unquote(u.path).strip("/")
    if path == "doku.php":
        path = next((v for k, v in (p.partition("=")[::2] for p in u.query.split("&")) if k == "id"), "")
    path = path.replace(":", "/")
    href = hrefs.get(path) or hrefs.get(path + "/start")
    return href and href + (f"#{u.fragment}" if u.fragment else "")


def render_wiki_pages(site, db, render):
    """The pages of www.mas.bg.ac.rs a student needs (studije.py SHOWN, of wiki_pages; Linkovi lists them, LINKS) at
    wiki_href, as the schedule pages (render, from render_study_pages), linking each other's copies. The rest of the
    wiki is kept in the database, not shown. A page gone from the wiki stays, marked."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'wiki_pages'").fetchone():
        return
    pages = defaultdict(list)
    for r in db.execute(
        f"SELECT * FROM wiki_pages WHERE path IN ({','.join('?' * len(SHOWN))}) ORDER BY path, last_seen DESC", sorted(SHOWN)
    ):
        pages[r["path"]].append(dict(r))
    hrefs = {path: wiki_href(path) for path in pages}
    lex = lexicon(BeautifulSoup(r[0], "html.parser").get_text("\n") for r in db.execute("SELECT html FROM wiki_pages"))
    shown = {}
    for path, versions in sorted(pages.items(), key=lambda kv: kv[0] == UPIS):  # upis/start last: its tabs show the rest
        for v in versions:
            v["title"] = wiki_title(v["title"], lex)
        extra = dict(tabs=upis_tabs(versions[0]["html"], pages, shown, hrefs)) if path == UPIS else {}
        shown[path] = render(
            versions,
            hrefs[path],
            STUDY_SITE + quote(path),
            ("/link/", "Linkovi"),
            link=lambda value: wiki_link(value, hrefs),
            tidy=lambda html, path=path: wiki_tidy(html, path, lex),
            classes=WIKI_CLASSES,
            **extra,
        )


def upis_tabs(raw, pages, shown, hrefs):
    """upis/start's links as tabs (studije.html; site.js shows one at a time, as /raspored/'s programs): each the
    linked page's shown html, its important-dates page linked from it shown above it in place of that link. A dates
    page that only links one page per program shows those; when their timelines are the same, the first, once."""
    soup = BeautifulSoup(raw, "html.parser")
    paths = list(dict.fromkeys(a["data-wiki-id"].replace(":", "/") for a in soup.select("a[data-wiki-id]")))
    paths = [p for p in paths if p in shown]
    if set(paths) != set(UPIS_TABS):
        print(f"[warn] mf/{UPIS}: links {paths}, the tabs expected {list(UPIS_TABS)}", file=sys.stderr)
    by_href = {h: p for p, h in hrefs.items()}
    tabs = []
    for path in paths:
        body = BeautifulSoup(shown[path], "html.parser")
        rok, seen = [], set()
        for a in body.select("a[href]"):
            dates = by_href.get(a["href"].split("#")[0])
            if not dates or "datum" not in dates:
                continue
            block = a.find_parent(["li", "p"]) or a
            if len(block.get_text(" ", strip=True)) < 80:  # "Важни датуми налазе се на линку": the dates replace it
                block.decompose()
            if dates in seen:  # linked again further down
                continue
            seen.add(dates)
            page = BeautifulSoup(shown[dates], "html.parser")
            if page.select_one("ol.wt-tl"):
                rok.append(("", from_timeline(page)))
                continue
            # A program's link: "МАШИНСКО ИНЖЕЊЕРСТВО и за студије на српском и …", named by its program alone.
            subs = [(re.split(r"\s+[иi]\s+за\s", s.get_text(" ", strip=True))[0], by_href.get(s["href"])) for s in page.select("a[href]")]
            subs = [(t, BeautifulSoup(shown[p], "html.parser")) for t, p in subs if p in shown]
            lines = {str(s.select_one("ol.wt-tl")) for _, s in subs}
            if subs and len(lines) == 1:
                rok.append((" и ".join(t for t, _ in subs), from_timeline(subs[0][1])))
            else:
                rok += [(t, from_timeline(s)) for t, s in subs] or [("", str(page))]
        short, name = UPIS_TABS.get(path, (pages[path][0]["title"], pages[path][0]["title"]))
        tabs.append(dict(key=slug(short), short=short, name=name, href=hrefs[path], rok=rok, html=str(body)))
    return tabs


def from_timeline(page):
    """A dates page from its timeline on: what is above it names the program, which the tab and the box already
    say; only a heading naming the round (рок: "Важни датуми и рокови за трећи уписни рок") stays."""
    tl = page.select_one("ol.wt-tl")
    for el in list(tl.find_previous_siblings()) if tl else []:
        if not (re.match(r"h[2-6]$", el.name or "") and "рок" in el.get_text().lower()):
            el.decompose()
    return str(page)


def wiki_title(t, lex=None):
    """A wiki page's title as the site shows it: one in capitals ("УПИС НА ОСНОВНЕ...") in sentence case, its
    acronyms kept (lex: wiki_tidy.lexicon; "VPN"), a page name ("cenovnik") capitalized."""
    if t.isupper():
        return recase(t, lex or {}, True)
    return t[0].upper() + t[1:] if t.islower() else t
