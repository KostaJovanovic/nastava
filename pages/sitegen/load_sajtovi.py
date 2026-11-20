"""The departments' whole sites (katedre.py site, nastava.db katedre_pages): a katedra's pages on its page, in groups
(SITE_GROUPS); a teacher's own (etc's folders, hidro's, meh's and bmi's page about one person, brodogradnja's card
of one: CARDS) on theirs. Not the
announcement pages (their notices are posts) nor ie's and fluidi's subject pages (on the subjects' pages)."""

import hashlib
import re
from collections import Counter, defaultdict
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, Tag
from translit import fold

# A tag not decomposed has no _decomposed, so bs4's .decomposed fell to Tag.__getattr__, which searches the whole
# subtree for a tag of that name, on each of thousands of calls here. decompose() still sets it on the instance.
Tag._decomposed = False

from .clean import clean_html
from .known import ANNOUNCEMENTS, CARDS, POST_LINK, SITE_GROUPS, SITE_KATEDRA, SUBJECT_PAGE

# The blocks a site repeats on its pages (a menu, a header, a footer); hidro keeps its menu in every page's content,
# its sections' bold names and rules too (strong, hr), and a footer that only its spacing tells apart.
BLOCKS = ["table", "tbody", "tr", "th", "td", "div", "center", "ul", "ol", "p", "section", "aside", "span", "strong", "hr"]
MIN_TEXT = 150  # characters of text: less is a menu, a redirect or an empty form
# A page title's parts that only name the site ("Industrijsko Inženjerstvo - Predmeti", "… — Katedra za …").
TITLE_SPLIT = re.compile(r"\s+[–—|-]\s+")
TITLE_SITE = re.compile(r"katedr|катедр|laboratorij|industrijsko inzenjerstvo|masinsk|^start \[|^index of")
# A menu link's text that names nothing.
NO_NAME = {"link", "vise", "detaljnije", "more", "read more", "opsirnije", "ovde", "here", "saznajte vise", "[dir]", "parent directory"}
# A URL's words that are no one's name ("profesori_gajic.html", "/teams/srdjan-bosnjak/").
NOT_NAME = {"html", "htm", "php", "profesori", "prof", "dr", "teams", "o", "nama"}


def norm(url):
    """As katedre.py stores a URL: no fragment, a folder's index file as the folder."""
    p = urlsplit(url)
    path = re.sub(r"(^|/)index\.(html?|php)$", r"\1", p.path) or "/"
    return f"https://{p.hostname}{path}" + (f"?{p.query}" if p.query else "")


def block_key(el):
    # formatter=None: no entity escaping, which a key only compared for equality doesn't need (a third of the time).
    return " ".join(el.decode(formatter=None).split())


def repeated(keyed):
    """The blocks (block_key) on most of a site's pages: its menu and footer, not any one page's content. keyed: per
    page, its blocks' [(el, key)]."""
    counts = Counter()
    for blocks in keyed:
        counts.update({key for _, key in blocks})
    n = len(keyed)
    return {h for h, c in counts.items() if n >= 4 and c >= max(3, n * 0.4)} if n else set()


def menu_names(soups, base_of):
    """{url: the text the site's links to it show most}: a page's name where its title is the site's."""
    names = defaultdict(Counter)
    for s, base in zip(soups, base_of):
        for a in s.find_all("a", href=True):
            text = a.get_text(" ", strip=True)
            if 2 <= len(text) <= 60 and fold(text) not in NO_NAME and not text.startswith("http") and urlsplit(a["href"]).hostname:
                names[norm(a["href"])][text] += 1
    return {u: c.most_common(1)[0][0] for u, c in names.items()}


def own_title(title):
    """'Industrijsko Inženjerstvo - Predmeti' -> 'Predmeti'; '' when it only names the site. WordPress's 'Blog
    Archives' -> 'Blog'."""
    parts = [re.sub(r"\s+Archives$", "", p.strip()) for p in TITLE_SPLIT.split(title or "")]
    return " – ".join(p for p in parts if p and not TITLE_SITE.search(fold(p)))


def slug_title(url):
    """'…/centri_lab1.html' -> 'Centri lab1': the last resort."""
    seg = unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
    words = re.sub(r"[-_]+", " ", re.sub(r"\.(html?|php)$", "", seg)).strip()
    return words[:1].upper() + words[1:] if words else urlsplit(url).hostname


def name_tokens(s):
    return set(re.findall(r"[a-z]+", fold(s)))


def teacher_of(site, url, users, by_katedra):
    """The teacher a page is about: etc's folder by its username; elsewhere the page's last path segment naming
    exactly one teacher of the site's katedra ('profesori_gajic', 'srdjan-bosnjak')."""
    path = urlsplit(url).path
    if site == "etc":
        return users.get(path.split("/")[1].lower()) if path.count("/") >= 2 else None
    return named(site, unquote(path.rstrip("/").rsplit("/", 1)[-1]), by_katedra)


def named(site, text, by_katedra):
    """The one teacher of the site's katedra whose name has all of text's words."""
    words = name_tokens(text) - NOT_NAME
    found = [t for t in by_katedra.get(SITE_KATEDRA.get(site), []) if words and words <= t["_tok"]]
    return found[0] if len(found) == 1 else None


def group_of(site, url, title):
    key = f"{site} {fold(unquote(urlsplit(url).path))} {fold(title)}"
    return next(label for label, rx in SITE_GROUPS if re.search(rx, key))


def day(ts):
    return f"{ts[8:10]}.{ts[5:7]}.{ts[:4]}."


def load_sajtovi(db, teachers):
    """({katedra: dict(host, seen, groups=[(label, pages)])}, {teacher id: dict(host, seen, pages)}); a page:
    dict(title, url, html, seen)."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'katedre_pages'").fetchone():
        return {}, {}
    users = {t["username"]: t for t in sorted(teachers, key=lambda t: not t["gone"]) if t.get("username")}
    by_katedra = defaultdict(list)
    for t in teachers:
        t["_tok"] = name_tokens(t["name"])
        by_katedra[t["katedra"]].append(t)
    rows = db.execute(
        "SELECT url, site, title, html, last_seen FROM katedre_pages k WHERE gone = 0"
        " AND last_seen = (SELECT max(last_seen) FROM katedre_pages WHERE url = k.url)"
        " ORDER BY (SELECT min(rowid) FROM katedre_pages WHERE url = k.url)"  # the crawl's order: the site's menu
    ).fetchall()
    has_notices = db.execute("SELECT 1 FROM sqlite_master WHERE name = 'katedre_notices'").fetchone()
    notices = db.execute("SELECT html FROM katedre_notices").fetchall() if has_notices else []
    posts = {m[1] for (h,) in notices if (m := POST_LINK.fullmatch(h))}
    sites = defaultdict(list)
    for r in rows:
        if r["url"] not in posts and not ANNOUNCEMENTS.search(r["url"]) and not SUBJECT_PAGE.search(r["url"]) and r["html"].lstrip()[:1] not in "[{":
            sites[r["site"]].append(r)
    kat, mine = defaultdict(lambda: defaultdict(list)), {}
    for site, pages in sites.items():
        soups = [BeautifulSoup(r["html"], "html.parser") for r in pages]
        names = menu_names(soups, [r["url"] for r in pages])
        # Each block's key once, before any is removed: in document order a block comes before what it holds, so one
        # still there has lost nothing, and its key then is the key now.
        keyed = [[(el, block_key(el)) for el in s.find_all(BLOCKS)] for s in soups]
        common = repeated(keyed)
        titles = Counter(r["title"] for r in pages)
        seen_text = set()
        for r, soup, blocks in zip(pages, soups, keyed):
            for el, key in blocks:
                if not el.decomposed and key in common:
                    el.decompose()
            # What that leaves: empty cells and boxes, and a layout table down to the one cell of the content.
            for el in reversed(soup.find_all(BLOCKS)):
                if not el.get_text(strip=True) and not el.find("img") and el.name != "hr":
                    el.decompose()
            for table in soup.find_all("table"):
                if not table.decomposed and len(cells := table.find_all(["td", "th"])) == 1 and not cells[0].find("table"):
                    table.replace_with(cells[0])
                    cells[0].unwrap()
            if CARDS.search(r["url"]):  # a card naming a teacher on their page; the others stay on the katedra's
                for card in soup.find_all("a", href=re.compile("#")):
                    h = card.find("h3")
                    if h and (t := named(site, h.find(string=True) or "", by_katedra)):
                        url = card["href"]
                        card.name, card.attrs = "div", {}  # not the whole card one link
                        html = clean_html(str(card.extract()), r["url"]) or ""
                        page = dict(title="Nastavnici", url=url, html=html.replace("<img ", '<img loading="lazy" '), seen=day(r["last_seen"]))
                        m = mine.setdefault(t["id"], dict(host=urlsplit(url).hostname, seen=page["seen"], pages=[]))
                        m["pages"].append(page)
            text = soup.get_text(" ", strip=True)
            digest = hashlib.sha1(text.encode()).hexdigest()
            if len(text) < MIN_TEXT or digest in seen_text:  # a stub, or the same page under another URL
                continue
            seen_text.add(digest)
            own = own_title(r["title"]) if titles[r["title"]] < 3 else ""
            head = soup.find(["h1", "h2", "h3"])
            head = head and head.get_text(" ", strip=True)
            path = urlsplit(r["url"]).path
            listing = re.match(r"Index of (/.*)", r["title"] or "")  # a folder's file list (Apache)
            title = (
                "Početna strana" if path == "/" else f"Fajlovi u {listing[1]}" if listing else own or names.get(r["url"])
                or (head if head and len(head) <= 80 else "") or slug_title(r["url"])
            )
            html = clean_html(str(soup), r["url"]) or ""
            page = dict(title=title, url=r["url"], html=html.replace("<img ", '<img loading="lazy" '), seen=day(r["last_seen"]))
            host = urlsplit(r["url"]).hostname
            if t := teacher_of(site, r["url"], users, by_katedra):
                m = mine.setdefault(t["id"], dict(host=host, seen=page["seen"], pages=[]))
                m["pages"].append(page)
            elif k := SITE_KATEDRA.get(site):
                kat[k][group_of(site, r["url"], title)].append(page)
                kat[k]["_meta"] = dict(host=host, seen=page["seen"])
    for t in teachers:
        t.pop("_tok", None)
    order = [label for label, _ in SITE_GROUPS]
    out = {}
    for k, groups in kat.items():
        meta = groups.pop("_meta")
        out[k] = dict(meta, groups=[(label, groups[label]) for label in order if groups.get(label)])
    return out, mine
