"""Writing the site: the Jinja environment, pages as fragments of shell.html, asset versions, dev mode's pages,
the sitemap, Pagefind's tags. All the build's mutable state is here."""

import hashlib
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin
from jinja2 import Environment, FileSystemLoader, Template, select_autoescape
from jinja2.utils import htmlsafe_json_dumps
from markupsafe import Markup, escape
from translit import fold, lat
from .known import HOME_ORDER
from .text import KIND, LINK, SITE_URL, desc, katedra, plural, slug, strip_tags


HERE = Path(__file__).parent.parent  # pages/

RECENT = 20

# vesti.py's site, which keeps the news' images and files (the pages link them); the home page shows the newest few.
VESTI, VESTI_HOME = "https://vesti.mas.bg.ac.rs/", 5

# A followed subject's newest topics in its novo.json (the home page's "Moji predmeti", site.js).
MINE = 10

# The Atom feeds (write_feeds): the posts in a subject's and in the whole board's, and the domain of their links.
FEED, FEED_ALL = 20, 50

PAGEFIND = "pagefind@1.6.0"

# shortcut: a document page shows and indexes at most this much text; raise it if GitHub Pages' 1 GB allows.
PAGE_TEXT = 300_000

env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape())

env.filters["pl"] = plural

# A count as Serbian writes it: 23.692.
env.filters["n"] = lambda n: f"{n:,}".replace(",", ".")

# An ISO date (2026-11-08...) as the board writes it: 08.11.2026.
env.filters["dmy"] = lambda iso: ".".join(reversed((iso or "")[:10].split("-"))) + "." if iso else ""

env.filters["katedra"] = katedra

# The katedre with a page of their own (render_katedre): the ones with listed teachers, set by main() before any page.
katedra_pages = set()


def katedra_href(k):
    """A katedra's link: its page, or for one without (only departed teachers) the archive's list of them."""
    return f"/katedra/{slug(katedra(k))}/" if k in katedra_pages else f"/nastavnici/arhiva/?katedra={slug(k)}"


env.filters["katedra_href"] = katedra_href

# A filter's value in a URL (?katedra=katedra-za-matematiku): Latin only, the shown text stays the name.
env.filters["slug"] = slug

env.filters["desc"] = desc

env.filters["lat"] = lat

# Structured data in a page (schema.org), escaped for a <script> (<, >, &, ' as \u).
env.filters["ld"] = lambda d: Markup(f'<script type="application/ld+json">{htmlsafe_json_dumps(d, ensure_ascii=False)}</script>')

env.globals["site_url"] = SITE_URL


def pagefind_tags(it):
    kind = KIND[it["kind"]]
    tags = [("meta", "title", it["title"] or ""), ("filter", "vrsta", kind), ("meta", "vrsta", kind)]
    if it["kind"] == "vest":
        tags.append(("meta", "kategorija", ", ".join(it["cats"])))
    if it["smer"]:
        tags += [("filter", "smer", it["smer"]["key"]), ("meta", "smer", it["smer"]["name"])]
    if it["subject"]:
        tags += [("filter", "predmet", slug(it["subject"])), ("meta", "predmet", it["subject"])]
        # The subject itself (a name is in several smerovi): the followed subjects' search (search.js).
        tags.append(("filter", "pid", it["subj"]["href"]))
    if it["author"]:
        tags += [("filter", "autor", it["author"].lower()), ("meta", "autor", it["who"])]
    if it["year"]:
        tags.append(("filter", "godina", str(it["year"])))
    if it["date"]:
        tags += [("sort", "datum", it["date"]), ("meta", "datum", it["date"])]
    # The thread of a post that has replies: search.js shows one row per thread on a page of results.
    if it.get("thread") and len(it["thread"]["posts"]) > 1:
        tags.append(("meta", "tema", it["thread"]["href"]))
    # The text as written, word for word the indexed folded copy: search.js shows the excerpt in it.
    tags.append(("meta", "tekst", f"{it['title']}\n{it['body'] or ''}"))
    return "".join(f'<meta data-pagefind-{t}="{k}[content]" content="{escape(v)}">' for t, k, v in tags)


def mark_for_pagefind(page, it):
    """Index only a folded copy of the title and text (one copy, so the excerpt does not repeat the title). Dev mode
    has no Pagefind: the page as it is."""
    if dev:
        return page
    assert page.count("</article>") == 1, it["id"]
    folded = escape(fold(f"{it['title']}\n{it['body'] or ''}"))
    return page.replace("</article>", f'<div class="pf" data-pagefind-body>{pagefind_tags(it)}{folded}</div></article>', 1)


def strip_pagefind(site):
    """After Pagefind has indexed the site, drop the hidden copy it read from each item and news page (~50 MB in all).
    A stripped site cannot be indexed again: it has no data-pagefind-body left."""
    marker = '<div class="pf" data-pagefind-body>'
    assert (site / "pagefind" / "pagefind.js").exists(), "run Pagefind before stripping"
    for path in [*(site / "item").glob("*/index.html"), *(site / "vest").glob("*/index.html")]:
        html = path.read_text(encoding="utf-8")
        if (start := html.find(marker)) >= 0:
            # The copy is escaped text, so its own </div> is the first one after the marker.
            path.write_text(html[:start] + html[html.index("</div>", start) + 6 :], encoding="utf-8")


MAIN = '<main class="main" id="sadrzaj">'

HEAD_END = "<!--/head-->"

shell = None  # shell.html, set by main()

site_dir = None  # the site's folder, set by main(): write() makes a page's URL from its path in it

# Every page's canonical URL, for sitemap.xml (write).
urls = {f"{SITE_URL}/"}

# The /static/ files the pages link get ?v=<hash of the file> (version_static): each deploy that changes one changes
# its URL, so no cache (the browser's, Cloudflare's, GitHub's) pairs new pages with an old file. Not sw.js (its URL
# is the push registration), the fonts or the images: those rarely change. icons.svg first: the JS links it.
VERSIONED = ("icons.svg", "style.css", "head.js", "pismo.js", "search.js", "site.js")

ASSET = re.compile(r"/static/(%s)(?![\w?.-])" % "|".join(map(re.escape, VERSIONED)))

asset_v = {}  # file name -> its hash, set by version_static()


def versioned(text):
    return ASSET.sub(lambda m: f"{m[0]}?v={asset_v[m[1]]}" if m[1] in asset_v else m[0], text)


def version_static(static):
    """Hash each VERSIONED file after pointing its own links at the files hashed before it."""
    for name in VERSIONED:
        f = static / name
        f.write_text(versioned(f.read_text(encoding="utf-8")), encoding="utf-8")
        asset_v[name] = hashlib.sha256(f.read_bytes()).hexdigest()[:10]


# Dev mode (pages/serve.py; main(dev=True)): no page is rendered while main() runs. Each one keeps its template's
# name and data (Lazy) in pages, under its address, and serve.py renders the one asked for from the templates as they
# are then: a template's edit shows on the next reload, with no build. Nothing for Pagefind, no sitemap.
dev = False

pages = {}  # dev: "/nastavnici/" -> the page (Lazy); the 404 page under "/404.html"


class Lazy:
    """A page not rendered yet: its template's name and the data it was given. fresh: {name: function} of data read
    again at each render, from a file serve.py does not watch (verzije.md), so its edit shows on the next reload."""

    def __init__(self, name, data):
        self.name, self.data, self.fresh = name, data, {}

    def __str__(self):
        return Template.render(env.get_template(self.name), **(self.data | {k: f() for k, f in self.fresh.items()}))


class LazyTemplate(Template):
    """Dev mode's templates: render() keeps what to render (Lazy), str() of it renders."""

    def render(self, *args, **kwargs):
        return Lazy(self.name, dict(*args, **kwargs))


def write_page(path, html):
    """A page that is not a fragment of shell.html, whole (the home and 404 pages)."""
    if dev:
        pages["/" + path.relative_to(site_dir).as_posix().removesuffix("index.html")] = html
        return
    path.write_text(versioned(html), encoding="utf-8")


def split_page(html):
    """A page -> (shell, fragment). The shell is the page with an empty <title> (in place of the page's own head, from
    <title> to <!--/head-->: base.html) and <!--main--> for the main part; the fragment is the page's head, <!--/head-->
    and the main part, in <html lang="sr"> so that Pagefind reads it.
    The Worker (pages/src/index.js join) puts them together again."""
    t0, t1 = html.index("<title>"), html.index(HEAD_END)
    m0, m1 = html.index(MAIN) + len(MAIN), html.rindex("</main>")
    return (
        html[:t0] + "<title></title>" + html[t1 + len(HEAD_END) : m0] + "<!--main-->" + html[m1:],
        f'<html lang="sr">{html[t0:t1]}{HEAD_END}{html[m0:m1]}</html>',
    )


# A section's pages count as its side panel link: a teacher under Nastavnici, an archived schedule page under Raspored,
# a news post under Vesti, an archived page of the faculty's site under Linkovi (site.js has the same rule).
SECTION = {"/nastavnik/": "/nastavnici/", "/katedra/": "/nastavnici/", "/studije/": "/raspored/", "/vest/": "/vesti/", "/mf/": "/link/"}

snav = []  # the side panel's links (sidebar.html), set by main()


def snav_href(path, hrefs):
    """The link of hrefs that the page at path is under: "/" only for itself, another for the paths it starts."""
    here = next((to + path[len(fr) :] for fr, to in SECTION.items() if path.startswith(fr)), path)
    return next((h for h in hrefs if (here == "/" if h == "/" else here.startswith(h))), None)


def write(path, html, index=True, canonical=None):
    """Write only the page's fragment: every page but the home and 404 pages shares shell.html. Its canonical link:
    its URL on the main domain, for search engines (also for its copy on github.io), or that of the page canonical
    names (a site path) that shows the same. index=False: search engines leave it out (the posts, which name
    students; their subjects' pages are indexed), and so does the sitemap. Dev mode: kept for serve.py, whole."""
    # As path.parent.relative_to(site_dir), by string: pathlib's took ~4 s of dev mode's start (33k pages, Windows).
    folder, root = path.parent.as_posix(), site_dir.as_posix()
    if folder != root and not folder.startswith(root + "/"):
        raise ValueError(f"{path} is not in {site_dir}")
    own = f"/{folder[len(root) + 1 :] or '.'}/"
    if dev:
        pages[own] = html
        return
    page_shell, fragment = split_page(html)
    assert page_shell == shell, f"{path}: the page differs from shell.html outside its head and <main>"
    url = SITE_URL + (canonical or own)
    head = f'<link rel="canonical" href="{escape(url)}">'
    # join() marks that link aria-current, so the page's first frame shows it (site.js marked it after).
    if h := snav_href(own, snav):
        head += f'<meta name="snav" content="{h}">'
    if index:
        urls.add(url)
        end = fragment.rindex("</html>")
        fragment = fragment[:end] + breadcrumbs(fragment, url) + fragment[end:]
    else:
        head += '<meta name="robots" content="noindex">'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(versioned(fragment.replace(HEAD_END, head + HEAD_END, 1)), encoding="utf-8")


def breadcrumbs(page, url):
    """The page's crumbs (base.html nav.crumbs) as schema.org data: Google shows the path in place of the URL."""
    nav = re.search(r'<nav class="crumbs".*?</nav>', page, re.S)
    here = nav and re.search(r'<span class="crumbs__here"[^>]*>(.*?)</span>', nav[0], re.S)
    if not here:
        return ""
    path = [(urljoin(SITE_URL, unescape(h)), strip_tags(t)) for h, t in LINK.findall(nav[0])] + [(url, strip_tags(here[1]))]
    # str: a str + Markup would escape the whole page.
    return str(
        env.filters["ld"](
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": u} for i, (u, name) in enumerate(path, 1)],
            }
        )
    )


def write_sitemap(site):
    """sitemap.xml with every page's canonical URL, and robots.txt naming it (Cloudflare puts its own rules above)."""
    assert len(urls) <= 50_000, "a sitemap holds 50,000 URLs: split it into several under a sitemap index"
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in sorted(urls))
        + "</urlset>\n",
        encoding="utf-8",
    )
    (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")


def write_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


env.globals["smer_icons"] = HOME_ORDER
