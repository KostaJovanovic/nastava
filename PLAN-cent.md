# Plan: cent.mas.bg.ac.rs into the subjects' forums

Status: planned 2026-11-09, agreed with the user, not built. Instructions for the Claude that builds it: follow the steps
in order and copy the code as it is. `cent.py` and `load_cent` were run against the live site (241 pages) and the real
`nastava.db`; the parser tests pass on the saved pages. The templates, the `build.py` wiring and the push changes were
not run: the checks in step 9 test them. If something here turns out wrong, stop and ask the user.

After this works: survey the other department sites (meh, motori, pt, bmi, ie, hidro, fluidi, ppm, ciah; vaz is Moodle
behind a login) and plan them the same way. Not part of this plan.

## Rules for this work (from the user)

- Commit locally without asking; commit messages 3–5 words. **Never push**, never run `wrangler deploy`,
  `ci/deploy.sh forum|sync` or `gh workflow run`: those publish.
- Files: Read/Edit/Write tools only, no `sed -i`, heredocs or redirects into files. Shell for git, uv, tests, `cp`.
- Never write the word "corpus".
- Windows shell: `PYTHONIOENCODING=utf-8` for Cyrillic output; Python prints `\r\n` (strip `\r` in `$(...)`).
- Other sessions edit this repo (often `pages/build.py`, `site.js`, `style.css`, templates) at the same time. Find code
  by the quoted text below, not by line numbers. Before committing, `git status`: commit only this plan's changes;
  if a file also has someone else's unstaged edits, stage only your hunks (build the blob from `git show HEAD:<file>`
  with your edit applied, `git hash-object -w --stdin`, `git update-index --cacheinfo 100644,<blob>,<file>`).

## What was decided

| # | Question | Decision |
|---|---|---|
| 1 | What | Everything of each subject on cent: the notices **and** the material pages (predavanja, računski zadaci, laboratorijske vežbe, rezultati ispita, prezentacije, …). Files are **not** hosted: links go to cent (wp-content/uploads, Google Drive), as the forum's attachments link to the board. |
| 2 | Files | Linked from cent only, for now. |
| 3 | Look | Notices are rows in the subject's topic list and posts like the board's, with a **"cent" mark**. Material pages are a list on the subject's page, each its own page with its versions. |
| 4 | History | From today: cent keeps only current notices and the WordPress API gives page-builder code, not text. No Wayback backfill. |
| 5 | Scope | cent first; the other sites after a survey. |

Not asked, decided here (tell the user in the final report, easy to change): a cent subject the board has no forum for
gets a subject page anyway, in the smer of its program; Индустрија 4.0 has no smer on the board, so a smer
"МАС - Индустрија 4.0" (`/smer/mas-industrija-4-0/`) is made for its 7 subjects. Department-wide pages of cent
(news, "Обавештења" at /obavestenja/, staff, history) are stored but not shown.

## What cent is (found 2026-11-09, so nobody refetches to learn it)

- WordPress 7 with the Divi builder, 241 published pages, 1 post. REST `/wp-json/wp/v2/pages` lists them (id, parent,
  menu_order, slug, title, link, modified) but `content.rendered` is raw Divi shortcodes: the text must come from the
  rendered HTML pages.
- A subject is a section: a page whose header (`#brzilinkovi`, the first `.et_pb_section` of `#main-content`) reads
  "… ID: 1617 …" (the subject book's code), and its subpages: обавештења, предавања, рачунски задаци, лабораторијске
  вежбе, sometimes презентације, ресурси, резултати испита. Some subjects are a single page. The last section is a
  footer "ОАС МАС ДАС".
- Notices are `.vesti_predmeta_item` blocks: `h2.vesti_predmeta_title`, `p.vesti_predmeta_date` ("06.11.2026."),
  `p.vesti_predmeta_content`, `.vesti_predmeta_files a[href]` (icons). Only current ones are shown: 7 notices on 6
  pages on 2026-11-09. One notice can be on two subjects' pages.
- Many links exist only in a script: Divi's `et_link_options_data = [{"class": "et_pb_text_10", "url": "…pdf"}]` makes
  a module clickable (on TMO's notices page, the student lists per shift). File links are icon images (Doc.webp,
  Ikonica_video.webp) with no text.
- Some subpages copy another subject's header ("ТМО – ресурси" shows ID 1528, "Индустријски роботи – лабораторијске
  вежбе" ID 1106): a page's subject is the code of the **highest** coded page at or above it. The top-level page
  /predavanja/ copies ID 0785 with no subpages: of two sections with one code, the one with more subpages wins.
- Mapping (tested): 41 sections → 41 subjects. 33 codes are in the subject book; 0131, 0302, 9006 are not, but their
  titles are book names (1620, 1619, 9048); 9003 "Роботика и вештачка интелигенција" is in the book. 30 map to board
  subjects (14 of those have posts on the board, e.g. TMO = `/predmet/oas-mi/tehnologija-masinske-obrade/`); 11 have
  no board forum: 1314 (→ МАС - МИ), 7084 and 7055 (→ ОАС - ИТМ), and 9003, 9006/9048, 9007, 9014, 9021, 9023,
  9030, 9035 (→ the new МАС - Индустрија 4.0).
- Size: all pages' content 1.9 MB of HTML; 35 subjects have material pages, 129 pages in all. A first run fetches 241
  pages (1 request a second: ~4.5 minutes); a daily run fetches the changed pages and every notices page (~45).

## Step 1: `cent.py` (new, repo root)

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""Archive the subject pages of cent.mas.bg.ac.rs (Катедра за производно машинство, WordPress with the Divi builder):
every page as it is shown (a new version when its content changes), and each notice (обавештење) on a page apart.
The site links its files (wp-content/uploads, Google Drive); they are not downloaded.

Usage: cent.py sync
  sync   list the pages (REST API, 3 requests), fetch each new or changed one (the list's "modified") and every
         notices page, store new versions and notices; a page or notice no longer there is marked gone.
"""
import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from bs4 import BeautifulSoup

SITE = "https://cent.mas.bg.ac.rs"
DB = os.getenv("DB", str(Path(__file__).resolve().parent / "nastava.db"))
DELAY = float(os.getenv("DELAY", "1.0"))
SCHEMA = """
create table if not exists cent_pages (id integer, sha text, parent integer, menu_order integer, slug text, title text,
	link text, modified text, code text, html text, first_seen text, last_seen text, gone integer not null default 0,
	primary key (id, sha));
create table if not exists cent_notices (nid integer primary key autoincrement, key text unique, page integer,
	title text, date text, html text, files text, first_seen text, last_seen text, gone integer not null default 0);
"""
# A file link's icon (an image in the link) gives way to the file's name; these hosts are videos.
FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|dwg|txt|m|py|csv|odt|ods|step|stp|igs|nc)$", re.I)
VIDEO = re.compile(r"(drive\.google\.com|docs\.google\.com|youtube\.com|youtu\.be|vimeo\.com)", re.I)
FOOTER = "ОАС МАС ДАС"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (personal archive)"
    return s


def get(s, url, **kw):
    r = s.get(url, timeout=60, **kw)
    time.sleep(DELAY)
    r.raise_for_status()
    return r


def list_pages(s):
    """Every published page: id, parent, menu_order, slug, title, link, modified (the REST API, 100 a request)."""
    out, page = [], 1
    while True:
        r = get(s, f"{SITE}/wp-json/wp/v2/pages", params=dict(per_page=100, page=page,
                _fields="id,parent,menu_order,slug,title,link,modified"))
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            return out
        page += 1


def link_modules(soup):
    """Divi makes a whole module a link with a script (et_link_options_data: [{class, url}]), not an <a>: a
    shift's student list, say. Put those links into the page as <a>, so they survive without the script."""
    for script in soup.find_all("script"):
        m = re.search(r"et_link_options_data\s*=\s*(\[.*?\]);", script.string or "", re.S)
        if not m:
            continue
        for o in json.loads(m[1]):
            if not o.get("url") or o["url"].startswith("#"):
                continue
            for el in soup.select("." + o["class"]):
                # A row of clickable modules is clickable too (its first one's link): only the modules get theirs.
                if el.find("a") or el.select_one(".et_clickable") or not el.get_text(strip=True):
                    continue
                a = soup.new_tag("a", href=o["url"])
                for child in list(el.children):
                    a.append(child.extract())
                el.append(a)


def name_icons(soup, page_url):
    """A link whose content is only an icon gets text: the file's name, "video", or the image's alt. A link to the
    page itself (an icon in a heading) goes."""
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if href.rstrip("/") == page_url.rstrip("/") and not a.get_text(strip=True):
            a.decompose()
            continue
        if a.get_text(strip=True):
            continue
        path = unquote(urlsplit(href).path)
        name = (path.rsplit("/", 1)[-1] if FILE.search(path) else "video" if VIDEO.search(href)
                else (a.img and a.img.get("alt")) or "link")
        a.clear()
        a.append(name)


def parse(html, page_url):
    """A rendered page -> (code, content html, notices). code: the subject's code in the header ("ID: 1617"), None on
    a page that is not a subject's. The content: the sections between the header and the footer, with Divi's
    script links made <a> and icons named. A notice: dict(title, date (ISO), html, files)."""
    soup = BeautifulSoup(html, "html.parser")
    link_modules(soup)
    main = soup.select_one("#main-content")
    if main is None:
        raise ValueError(f"{page_url}: no #main-content (the theme changed?)")
    sections = main.select(".et_pb_section")
    head = main.select_one("#brzilinkovi")
    m = head and re.search(r"\bID:\s*(\d{3,4})\b", head.get_text(" ", strip=True))
    code = m[1] if m else None
    body = [x for x in sections if x is not head and x.get_text(" ", strip=True) != FOOTER
            and (x.get_text(strip=True) or x.select("a[href]"))]
    for x in body:
        name_icons(x, page_url)
        for t in x.find_all(["script", "style", "noscript"]):
            t.decompose()
    page = "".join(str(x) for x in body)
    notices = []
    for it in main.select(".vesti_predmeta_item"):
        title = it.select_one(".vesti_predmeta_title")
        date = it.select_one(".vesti_predmeta_date")
        d = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", date.get_text() if date else "")
        el = copy.copy(it)  # the page's copy keeps its title and date
        for t in el.select(".vesti_predmeta_title, .vesti_predmeta_date"):
            t.decompose()
        notices.append(dict(title=title.get_text(" ", strip=True) if title else "",
                            date=f"{d[3]}-{int(d[2]):02d}-{int(d[1]):02d}" if d else None,
                            files=[a["href"] for a in it.select(".vesti_predmeta_files a[href]")],
                            html=el.decode_contents().strip()))
    return code, page, notices


def store_page(db, p, code, html, seen):
    """A new version when the content differs from the newest stored; else that one is seen again."""
    sha = hashlib.sha1(html.encode()).hexdigest()
    title = unescape(p["title"]["rendered"])
    last = db.execute("select sha from cent_pages where id = ? order by last_seen desc limit 1", (p["id"],)).fetchone()
    if db.execute("select 1 from cent_pages where id = ? and sha = ?", (p["id"], sha)).fetchone():
        # The newest again, or back to an older version (that one becomes the newest).
        db.execute("update cent_pages set last_seen = ?, modified = ?, parent = ?, menu_order = ?, title = ?, link = ?, "
                   "code = ?, gone = 0 where id = ? and sha = ?",
                   (seen, p["modified"], p["parent"], p["menu_order"], title, p["link"], code, p["id"], sha))
        return last[0] != sha
    db.execute("insert into cent_pages values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
               (p["id"], sha, p["parent"], p["menu_order"], p["slug"], title, p["link"], p["modified"], code, html,
                seen, seen))
    return True


def store_notices(db, page_id, notices, seen):
    """A notice is its page, title and date; a changed text updates it. One no longer on its page is marked gone."""
    keys = []
    for n in notices:
        key = hashlib.sha1(f"{page_id}|{n['title']}|{n['date']}".encode()).hexdigest()
        keys.append(key)
        db.execute("insert into cent_notices (key, page, title, date, html, files, first_seen, last_seen) "
                   "values (?, ?, ?, ?, ?, ?, ?, ?) on conflict (key) do update set html = excluded.html, "
                   "files = excluded.files, last_seen = excluded.last_seen, gone = 0",
                   (key, page_id, n["title"], n["date"], n["html"], json.dumps(n["files"]), seen, seen))
    db.execute(f"update cent_notices set gone = 1 where page = ? and key not in ({','.join('?' * len(keys))})",
               (page_id, *keys))


def sync():
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    s, seen = session(), now()
    pages = list_pages(s)
    known = dict(db.execute("select id, modified from cent_pages c where last_seen = "
                            "(select max(last_seen) from cent_pages where id = c.id)"))
    fetched = new = 0
    for p in pages:
        # The notices pages every time: a notice may not change the page's "modified".
        if known.get(p["id"]) == p["modified"] and "obavestenja" not in p["slug"]:
            db.execute("update cent_pages set last_seen = ? where id = ? and last_seen = "
                       "(select max(last_seen) from cent_pages where id = ?)", (seen, p["id"], p["id"]))
            continue
        code, html, notices = parse(get(s, p["link"]).text, p["link"])
        fetched += 1
        new += store_page(db, p, code, html, seen)
        store_notices(db, p["id"], notices, seen)
        db.commit()
    live = [p["id"] for p in pages]
    db.execute(f"update cent_pages set gone = 1 where id not in ({','.join('?' * len(live))})", live)
    db.commit()
    n = db.execute("select count(*), sum(gone = 0) from cent_notices").fetchone()
    print(f"cent: {len(pages)} pages, {fetched} fetched, {new} new versions; {n[0]} notices ({n[1]} on the site)")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["sync"]:
            sync()
        case _:
            sys.exit(__doc__)
```

## Step 2: parser tests

The four fixtures are already in `test/fixtures/` (saved 2026-11-09, committed with this plan):
`cent-obavestenja.html` (TMO's notices), `cent-rezultati.html` (TMO's results), `cent-lab.html` (TMO's labs),
`cent-predmet.html` (TMO's own page, header only).

In `test/parsers_test.py`: add `import cent  # noqa: E402` after `import nastava  # noqa: E402`, and insert this block
just before the final `print('parsers ok')` (it passed against this exact `cent.py`):

```python
# cent.mas.bg.ac.rs (cent.py): a subject's notices page (a notice; Divi's script links made <a>), a results page (file
# icons named by the file), a labs page (video links), and a subject's own page (only the header: no content).
T = 'https://cent.mas.bg.ac.rs/tehnologija-masinske-obrade/'
code, html, notices = cent.parse(read('cent-obavestenja.html'), T + 'obavestenja/')
assert code == '1617' and len(notices) == 1, (code, notices)
assert (notices[0]['title'], notices[0]['date']) == ('ВАЖНО ОБАВЕШТЕЊЕ – друга лабораторијска вежба!', '2026-11-06')
assert [f.rsplit('/', 1)[1] for f in notices[0]['files']] == ['Detaljan_raspored_lab2.pdf', 'Spisak_studenata_po_grupama_lab_2.pdf']
assert 'vesti_predmeta_title' not in notices[0]['html'] and 'Detaljan_raspored_lab2.pdf</a>' in notices[0]['html']
links = [(a['href'].rsplit('/', 1)[1], a.get_text(' ', strip=True)) for a in BeautifulSoup(html, 'html.parser').find_all('a')]
assert len(links) == 12 and ('Spisak_studenata_2026-2027_smjena1_v3.pdf', 'Смена 1') in links, links
assert 'vesti_predmeta_title' in html, 'the page keeps its notices as they were shown'
code, html, notices = cent.parse(read('cent-rezultati.html'), T + 'rezultati-tmo/')
assert code == '1617' and notices == [] and html.count('<a ') == 42 and '>fin11.pdf</a>' in html
assert 'et_link_options_data' not in html and '<script' not in html
code, html, notices = cent.parse(read('cent-lab.html'), T + 'laboratorijske-vezbe-tmo/')
texts = [a.get_text(strip=True) for a in BeautifulSoup(html, 'html.parser').find_all('a')]
assert len(texts) == 15 and texts.count('video') == 3 and 'lab1.pdf' in texts and '' not in texts, texts
assert cent.parse(read('cent-predmet.html'), T) == ('1617', '', [])
# A notice no longer on its page stays, marked gone; a page's content that changes is a new version, and a page back
# to an older content makes that version the newest again.
db = sqlite3.connect(':memory:')
db.executescript(cent.SCHEMA)
notice = lambda t: dict(title=t, date='2026-11-06', html='x', files=[])
cent.store_notices(db, 1, [notice('a'), notice('b')], 's1')
cent.store_notices(db, 1, [notice('b')], 's2')
cent.store_notices(db, 2, [], 's2')
assert db.execute('select title, gone, first_seen, last_seen from cent_notices order by nid').fetchall() == [('a', 1, 's1', 's1'), ('b', 0, 's1', 's2')]
page = dict(id=5, parent=0, menu_order=0, slug='x', title=dict(rendered='X &amp; Y'), link='L', modified='m')
assert [cent.store_page(db, page, '1617', h, w) for h, w in (('a', 's1'), ('a', 's2'), ('b', 's3'), ('a', 's4'))] == [True, False, True, True]
assert db.execute('select title, html, first_seen, last_seen from cent_pages order by last_seen desc').fetchall() == [
    ('X & Y', 'a', 's1', 's4'), ('X & Y', 'b', 's3', 's3')]
```

Check: `uv run test/parsers_test.py` → `parsers ok`.

## Step 3: a real run on a copy of the database

Never on `nastava.db` itself (the deploy pulls the saved state over it; a local-only change would be confusing):

    cp nastava.db "$TEMP/cent-try.db"
    DB="$TEMP/cent-try.db" PYTHONIOENCODING=utf-8 uv run cent.py sync
      -> "cent: 241 pages, 241 fetched, 241 new versions; N notices (N on the site)"   (numbers may have moved)
    DB="$TEMP/cent-try.db" PYTHONIOENCODING=utf-8 uv run cent.py sync
      -> about 36 fetched, 0 new versions (only the notices pages and changed pages are fetched; 36 on 2026-11-09)

## Step 4: `pages/build.py`

### 4a. Two new functions

Insert right after the function `load_vesti` (before `def pagefind_tags`):

```python
def board_subject(by_code, by_name, code, name, program):
    """The board's subject of a subject-book entry: the same code, else the same name in the smer of its program."""
    return by_code.get(code) or by_name.get((fold(short_smer(program.replace(" — ", " - "))), fold(name)))


def load_cent(db, smerovi, subjects):
    """cent.py's subject pages of cent.mas.bg.ac.rs, under the board's subjects. Returns (the notices as items, the
    page versions as push.json rows); each subject with pages gets s["cent"]: its pages in the site's order, each with
    its versions, newest first (render_cent).
    A page is a subject's when the highest page at or above it with a code in its header has the subject's code (a
    subpage may copy another subject's header; of two sections with one code, the one with more pages under it). The
    code is the subject book's, or, unknown there, the section's title is a book subject's name; the book entry leads
    to the board subject as in load_book. A subject the board does not have is made here, in the smer of its program,
    and that smer too when the board has none (Индустрија 4.0). Before load_book: the book links these subjects."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'cent_pages'").fetchone():
        return [], []
    versions = defaultdict(list)
    for r in db.execute("SELECT rowid AS rid, * FROM cent_pages ORDER BY id, last_seen DESC"):
        versions[r["id"]].append(dict(r))
    pages = {i: v[0] for i, v in versions.items()}
    kids = Counter(p["parent"] for p in pages.values())

    def top(p):
        found = None
        while p:
            found = p if p["code"] else found
            p = pages.get(p["parent"])
        return found

    roots = {}
    for p in pages.values():
        if p["code"] and not p["gone"] and top(p) is p:
            if p["code"] not in roots or kids[p["id"]] > kids[roots[p["code"]]["id"]]:
                roots[p["code"]] = p
    book = {r["id"]: r for r in db.execute("SELECT id, name, program FROM subjects")} if db.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone() else {}
    book_by_name = {}
    for r in book.values():
        book_by_name.setdefault(fold(r["name"]), r["id"])
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    by_name = {(fold(s["smer"]["short"]), fold(s["name"])): s for s in subjects.values()}
    smer_of = {fold(m["short"]): m for m in smerovi.values()}
    subj_of = {}
    for code, r in roots.items():
        code = code if code in book else book_by_name.get(fold(r["title"]))
        if not code:
            print(f"cent: no subject in the book for {r['link']} ({r['title']}, ID {r['code']})", file=sys.stderr)
            continue
        name, program = book[code]["name"], book[code]["program"]
        s = board_subject(by_code, by_name, code, name, program)
        if not s:
            smer_name = program.replace(" — ", " - ")
            smer_name = smer_name[:1].lower() + smer_name[1:]
            m = smer_of.get(fold(short_smer(smer_name)))
            if not m:
                m = dict(id=f"cent:{program}", name=smer_name, short=short_smer(smer_name), label=smer_name[:1].upper() + smer_name[1:])
                m["href"] = f"/smer/{slug(m['short'])}/"
                m["key"] = m["href"].strip("/").split("/")[-1]
                smerovi[m["id"]] = smer_of[fold(m["short"])] = m
            s = dict(id=f"c{code}", name=name, smer=m, codes=[code])
            s["href"] = f"{m['href'].replace('/smer/', '/predmet/', 1)}{slug(name)}/"
            if any(o["href"] == s["href"] for o in subjects.values()):
                s["href"] = f"{s['href'][:-1]}-{code}/"
            subjects[(m["id"], name)] = by_code[code] = s
        subj_of[r["id"]] = s
    notices = defaultdict(list)
    for n in db.execute("SELECT * FROM cent_notices ORDER BY nid"):
        notices[n["page"]].append(dict(n))
    items, pushed = [], []
    for p in sorted(pages.values(), key=lambda p: (p["menu_order"], p["id"])):
        s = subj_of.get((top(p) or {}).get("id"))
        if not s:
            continue
        for n in notices[p["id"]]:
            day = n["date"] or n["first_seen"][:10]
            # Its date is the notice's; its time the one it was first seen, when that was the same day.
            posted = n["first_seen"] if n["first_seen"][:10] == day else f"{day}T10:00:00+00:00"
            html = clean_html(n["html"], p["link"])
            items.append(dict(id=f"c{n['nid']}", kind="cent", title=n["title"], smer=s["smer"], subj=s, subject=s["name"],
                              date=day, year=int(day[:4]), topic=f"c{n['nid']}", num=n["nid"],
                              when=f"{day[8:10]}.{day[5:7]}.{day[:4]}.", posted=posted, author="cent",
                              body=strip_tags(html), html=html, files=[], gone=n["gone"], source_url=p["link"]))
        shown = []
        for i, v in enumerate(versions[p["id"]]):
            html = clean_html(v["html"], p["link"]) or ""
            # The page's first heading is its name ("Резултати испита"): the title, not repeated under it.
            m = re.search(r"<h2[^>]*>(.*?)</h2>", html, re.S)
            title = strip_tags(m[1]) if m else v["title"]
            html = html[:m.start()] + html[m.end():] if m else html
            if not strip_tags(html) and "<a " not in html:
                continue
            href = f"{s['href']}cent/{p['slug']}/" if i == 0 else f"{s['href']}cent/{p['slug']}/{v['first_seen'][:10]}-{v['sha'][:6]}/"
            shown.append(dict(title=title, href=href, html=html, first_seen=v["first_seen"], last_seen=v["last_seen"]))
            new = i == len(versions[p["id"]]) - 1
            pushed.append(dict(k="s", id=v["rid"], s=s["href"], n=s["name"], t=f"{title}: {'nova stranica' if new else 'izmenjeno'}",
                               u=f"{s['href']}cent/{p['slug']}/"))
        if shown and shown[0]["href"] == f"{s['href']}cent/{p['slug']}/":
            s.setdefault("cent", []).append(dict(title=shown[0]["title"], link=p["link"], gone=p["gone"], versions=shown))
    return items, pushed


def render_cent(site, subjects):
    """Each subject's cent pages (load_cent): the newest version at <subject>/cent/<slug>/, each older one under its
    first date. Their links go to cent (the files are not hosted here)."""
    page = env.get_template("cent.html")
    for s in subjects.values():
        for p in s.get("cent", []):
            for v in p["versions"]:
                write(site / v["href"].strip("/") / "index.html", page.render(subj=s, page=p, v=v))
```

(`load_cent` was run as written against the live site's pages and the real database: 7 notices → 7 items, 35 subjects
with 129 pages, the new smer `/smer/mas-industrija-4-0/`.)

### 4b. Edits elsewhere in `build.py` (find each by its text)

1. `KIND = {"post": "obavestenje", …}`: add `"cent": "obavestenje"` (a cent notice is a notice to search).
2. In `load_book`, replace the line
   `s["forum"] = by_code.get(s["id"]) or by_name.get((fold(short_smer(s["program"].replace(" — ", " - "))), fold(s["name"])))`
   with `s["forum"] = board_subject(by_code, by_name, s["id"], s["name"], s["program"])`.
3. In `load_topics`: `if it["kind"] == "post":` → `if it["kind"] in ("post", "cent"):` (a notice is a topic of one
   post: `/item/c<nid>/`).
4. In `render_places`, after the line `s["topics"], s["count"], s["last"] = …` add
   `s["live"] = bool(rows or s.get("cent"))` and change the next `if rows:` to `if s["live"]:` (a subject with only
   cent pages gets its page too). In the smerovi loop change
   `subs = sorted((s for s in subjects.values() if s["smer"] is m and s["count"]), …)` to `… and s["live"]), …)`, and
   after `rows = in_smer[m["id"]]` add `m["live"] = bool(rows or subs)`.
5. In `write_feeds`: the signature becomes `def write_feeds(site, items, subjects, pushed=()):`;
   `posts = sorted((it for it in items if it["kind"] == "post"), …)` → `it["kind"] in ("post", "cent")`;
   `if s["count"]:` → `if s.get("live"):`; the push.json list becomes
   ```python
   (site.parent / "push.json").write_text(json.dumps(
       [dict(k=it["id"][0], id=it["num"], s=it["subj"]["href"], n=it["subj"]["name"], t=it["title"] or "", u=post_href(it))
        for it in posts if it["subj"]][:1000] + list(pushed), ensure_ascii=False), encoding="utf-8")
   ```
   (`k`: "p" a board post, "c" a cent notice, "s" a cent page version; ci/push.py keeps one "before" per kind.)
   Update its shortcut comment: "the newest 1000 posts and notices only".
6. In `render_book`: `if s["forum"] and not s["forum"]["count"]:` → `if s["forum"] and not s["forum"].get("live"):`.
7. In `picker`: `live = [s for s in subjects.values() if s.get("count")]` → `s.get("live")`; in its `index`:
   `if f and f.get("count")` → `if f and f.get("live")`.
8. In `render_home`: `[m for m in smerovi.values() if m["count"]]` → `if m.get("live")`.
9. In `main()`: after `place, smerovi, subjects = load_places(db)` add
   `cent_items, cent_pushed = load_cent(db, smerovi, subjects)` and change `items = load_items(db, place)` to
   `items = load_items(db, place) + cent_items`; change `write_feeds(site, items, subjects)` to
   `write_feeds(site, items, subjects, cent_pushed)`; after `render_places(site, topics, smerovi, subjects)` add
   `render_cent(site, subjects)`.

Notes for these edits: `main()` sets `it["teacher"]`/`it["who"]` from the author: "cent" is nobody's username, so
`who` is "cent" (the author filter then offers "cent"). `archive_stats` counts `kind == "post"` only: the statistics
stay the board's. Search, `/item/` pages and `strip_pagefind` take the notices like posts.

## Step 5: templates and style

1. `pages/templates/rows.html`, macro `who(r)`: before `{%- else %}` add
   `{%- elif r.kind == 'cent' %}<span class="src" title="Sa sajta Katedre za proizvodno mašinstvo (cent.mas.bg.ac.rs)">cent</span>`.
2. Same file, macro `gone(r)`: the text becomes
   `uklonjeno sa {{ 'sajta katedre' if (r.kind or (r.first and r.first.kind)) == 'cent' else 'foruma' }}`.
3. Same file, macro `post(r, …)`, the `<aside class="post__who" …>`: wrap its content so a cent notice shows
   `<span class="av" aria-hidden="true">C</span><div><span class="post__name">cent.mas.bg.ac.rs</span><span>Katedra za proizvodno mašinstvo</span></div>`
   (`{%- if r.kind == 'cent' %}…{%- else %}` the current content `{%- endif %}`).
4. `pages/templates/predmet.html`: before `{% call topic_rows('Objave', topics, filter=true) %}` add
   ```jinja
   {%- if subj.cent %}
   {#- The subject's pages on the department's site (build.py load_cent), in its order; each date: its last change. -#}
   <section class="fb fb--posts">
     <div class="fb__h"><h2>Sa sajta katedre <span class="src">cent</span></h2><span>Izmenjeno</span></div>
     <ol class="fb__rows">
       {%- for p in subj.cent %}
       <li class="fr">
         <span class="fr__i" aria-hidden="true"><svg class="i"><use href="/static/icons.svg#i-file"></use></svg></span>
         <div class="fr__t"><a class="fr__a" href="{{ p.versions[0].href }}">{{ p.title }}</a>{% if p.gone %}<span class="gone">uklonjeno sa sajta katedre</span>{% endif %}</div>
         <div class="fr__more"><time class="fr__d" datetime="{{ p.versions[0].first_seen }}">{{ p.versions[0].first_seen | dmy }}</time></div>
       </li>
       {%- endfor %}
     </ol>
   </section>
   {%- endif %}
   ```
   and in the same file's topic list, an empty list must not say the subject has nothing when it has cent pages:
   leave `topic_rows` as it is (an empty `<ol>` with the header is fine).
5. New `pages/templates/cent.html`:
   ```jinja
   {% extends "base.html" %}
   {% from "rows.html" import crumb %}

   {#- One version of a subject's page on cent.mas.bg.ac.rs (build.py load_cent, render_cent): the newest at
       <subject>/cent/<slug>/, each older one under its first date. Its links go to cent: the files are not hosted here. -#}
   {%- set _old = v is not sameas page.versions[0] %}
   {% block title %}{{ v.title }} · {{ subj.name }}{% if _old %} ({{ v.first_seen | dmy }}){% endif %}{% endblock %}
   {% block crumbs %}{{ crumb(subj.smer.href, subj.smer.label) }}{{ crumb(subj.href, subj.name) }}{% if _old %}{{ crumb(page.versions[0].href, page.title) }}{% endif %}{% endblock %}

   {% block main %}
   <div class="mh">
     <h1 id="title">{{ v.title }}</h1>
     <p class="mh__sub"><span class="src">cent</span> stranica sa cent.mas.bg.ac.rs, {% if _old %}verzija od {{ v.first_seen | dmy }} do {{ v.last_seen | dmy }}{% else %}provereno {{ v.last_seen | dmy }}{% endif %}
       {%- if page.gone %} · <span class="gone">uklonjeno sa sajta katedre</span>{% else %} · <a href="{{ page.link }}" rel="noopener" target="_blank">original <svg class="i" aria-hidden="true"><use href="/static/icons.svg#i-external"></use></svg></a>{% endif %}</p>
   </div>
   {%- if _old %}
   <p class="note">Ovo je ranija verzija stranice. <a href="{{ page.versions[0].href }}">Najnovija verzija</a></p>
   {%- endif %}
   <article class="panel">
     <div class="prose prose--html">{{ v.html | safe }}</div>
   </article>
   {%- if page.versions | length > 1 %}
   <section class="versions" aria-labelledby="versions-h">
     <h2 id="versions-h">Sve verzije</h2>
     <ol>
       {%- for x in page.versions %}
       <li>{% if x is sameas v %}<b>{{ x.first_seen | dmy }} – {{ x.last_seen | dmy }}</b>{% else %}<a href="{{ x.href }}">{{ x.first_seen | dmy }} – {{ x.last_seen | dmy }}</a>{% endif %}{% if loop.first %} · najnovija{% endif %}</li>
       {%- endfor %}
     </ol>
   </section>
   {%- endif %}
   {% endblock %}
   ```
6. `pages/static/style.css`, after the `.gone` rule (search for `.gone {`):
   ```css
   /* The mark of what comes from a department's site, not the board (build.py load_cent): a row's author, a page. */
   .src { display: inline-block; padding: 0 6px; border-radius: 9px; background: var(--accent); color: #fff; font: 700 11px/18px var(--sans); vertical-align: 1px; }
   ```
   If `--accent` or `--sans` is not defined in style.css's `:root`, use the variables `.tgl` uses.

## Step 6: `ci/push.py` (one "before" per kind)

1. `last()` becomes:
   ```python
   def last():
       """The newest board post, cent notice and cent page version (rowid) in nastava.db: the "before" of send."""
       db = sqlite3.connect(f"file:{ROOT / 'nastava.db'}?mode=ro", uri=True)

       def newest(sql):
           try:
               return db.execute(sql).fetchone()[0] or 0
           except sqlite3.OperationalError:  # cent.py has not run yet
               return 0
       print(newest("select max(id) from posts"), newest("select max(nid) from cent_notices"),
             newest("select max(rowid) from cent_pages"))
   ```
2. `send(before)` becomes `send(*before)`; its start:
   ```python
   after = dict(zip("pcs", before))  # board posts, cent notices, cent page versions
   if after.get("p", 0) <= 0:
       sys.exit("no post id from before the scrape")
   # A kind at 0 had nothing before this run (its first import): nothing of it is notified.
   new = [p for p in json.loads((ROOT / "pages/.build/push.json").read_text(encoding="utf-8"))
          if after.get(p.get("k", "p"), 0) > 0 and p["id"] > after[p.get("k", "p")]]
   ```
   The wait: `newest = f"{SITE}{new[0]['u'].split('#')[0]}"` (push.json has the newest post or notice first, then
   the page versions) instead of the `/item/p…/` URL. `sorted(new, key=lambda p: p["id"])` stays (it is per subject).
   The CLI: `case ["send", *ns] if ns: send(*map(int, ns))`. Docstring usage: `send <post id> [<notice id> <page rowid>]`.
3. `ci/deploy.sh`: `uv run -q ci/push.py send "$before"` → `uv run -q ci/push.py send $before` (unquoted: three
   numbers), and after the line `uv run vesti.py sync || failed+=(vesti)` add
   ```bash
   	# The subjects' pages on cent.mas.bg.ac.rs: ~45 requests a day.
   	uv run cent.py sync || failed+=(cent)
   ```
   If `PLAN-sync.md` was built first, `ci/deploy.sh` has its form: make the same two edits there. If it was not,
   edit `PLAN-sync.md`'s deploy.sh block the same way so it keeps them.
4. `ci/plan.py` fingerprint (if it exists; else in `PLAN-sync.md`'s code block): add to `queries`
   `"select count(*), sum(gone), total(length(html)) from cent_notices", "select count(*), sum(gone) from cent_pages",`.

## Step 7: README and PLAN.md

- README "Files": after the `vesti.py` bullet (or after `predmeti.py` if there is none) add:
  "- `cent.py`: archive the subject pages of cent.mas.bg.ac.rs (Катедра за производно машинство): each page as shown
  (a version per change) and each notice apart, into `cent_pages` and `cent_notices`. The files stay linked on cent.
  The site puts each subject's notices among its topics with a "cent" mark, and its pages (predavanja, rezultati, …)
  under `/predmet/…/cent/`; a subject the board has no forum for gets a page too."
- README "How it works", the run's step 3: add "the subjects' pages on cent.mas.bg.ac.rs" to what is archived daily.
- PLAN.md, the sources table row 4: cent → "scraped (cent.py, see PLAN-cent.md)". In this file: Status → built.

## Step 8: commit

`git status`; stage `cent.py`, `test/parsers_test.py`, `pages/build.py` (your hunks only), `pages/templates/rows.html`,
`pages/templates/predmet.html`, `pages/templates/cent.html`, `pages/static/style.css` (your hunk only), `ci/push.py`,
`ci/deploy.sh`, `README.md`, `PLAN.md`, `PLAN-cent.md` (and `ci/plan.py` / `PLAN-sync.md` if touched).
Message: `Cent subject pages`. Do not push.

## Step 9: check it (before the commit; fix and repeat until all pass)

1. `uv run test/parsers_test.py` → `parsers ok`; `uv run -q ci/push.py` (self-checks) prints the usage.
2. Build from the tried copy (step 3): `uv run pages/build.py "$TEMP/cent-try.db" pages/.build` → no error; the
   summary line's subjects count is about 11 more than before.
3. `python pages/serve.py 15499` in the background, then with Playwright (Edge, as in `test/browser_test.py`) or by
   fetching the HTML:
   - `/predmet/oas-mi/tehnologija-masinske-obrade/`: the "Sa sajta katedre cent" list (Предавања, Рачунски задаци,
     Лабораторијске вежбе, Обавештења, …, Резултати испита) above the topics; the notice "ВАЖНО ОБАВЕШТЕЊЕ – друга
     лабораторијска вежба!" among the topics with the "cent" mark, if cent still shows it.
   - `/predmet/oas-mi/tehnologija-masinske-obrade/cent/rezultati-tmo/`: about 35 links to
     `https://cent.mas.bg.ac.rs/wp-content/uploads/…pdf` with file names as text; clicking one opens the
     "Napuštate arhivu" dialog (site.js), as other outside links do.
   - `/smer/mas-industrija-4-0/` lists its subjects; `/predmet/mas-industrija-4-0/uvod-u-proizvodne-sisteme/` exists.
   - The home page lists the new smer; `/predmeti/` links those subjects' board pages.
   - A notice's `/item/c<nid>/` page: "od cent", the aside "cent.mas.bg.ac.rs", "original" → the cent page.
   - Search "Moodle електронска учионица" (or another current notice title) finds a notice row.
   - `/feed.xml` and the TMO subject's `feed.xml` include the cent notice; `pages/.build/push.json` has rows with
     `"k": "c"` and `"k": "s"`.
   - `uv run --with playwright python test/browser_test.py http://localhost:15499 <dir>` passes, "page errors: none".
   - Light and dark theme: the `.src` mark is readable.
4. Stop the server (PowerShell: the process whose command line has `serve.py 15499`; never other sessions' servers).

## Step 10: tell the user

- What was built; the decision made here (subjects without a forum get pages; the new smer МАС - Индустрија 4.0);
  numbers from step 3/9.
- Only they can: push; the next scheduled or PC run (`deploy.sh forum`) archives cent for real into the saved state.
- The first run with cent does not notify (its "before" is 0); later new notices and changed pages ("Rezultati
  ispita: izmenjeno") go to the followers of the subject.
- Next: the survey of the other department sites.

## Known limits (say them in the report)

- Only notices still on cent from today on; older ones are gone from cent (no backfill, by decision).
- A notice is its page + title + date: a retitled notice is a new one, and the old one is marked gone.
- A page change that keeps cent's "modified" is missed until the page changes again, except notices pages (fetched
  every run).
- Files are cent's: when cent deletes one, the link dies (same as the board's attachments).
- Department-wide pages (news, /obavestenja/, staff) are stored but not shown; material pages are not in search.
- The Divi structure (`#brzilinkovi`, `.vesti_predmeta_item`, `et_link_options_data`) is cent's theme: a redesign
  breaks `parse`, and `parsers_test.py` (with fresh fixtures) is where to fix it.
