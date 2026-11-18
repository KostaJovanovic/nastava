# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4==4.15.0", "nh3==0.3.2"]
# ///
"""Each news item on the saved old news pages (wayback_news.py) as one row of work/wayback/articles.jsonl.

uv run --no-project --with beautifulsoup4==4.15.0 --with nh3==0.3.2 python -I tools/wayback_articles.py
(-I: the pages are downloaded files, so nothing from the working directory is imported.)

Three shapes: CuteNews (the faculty's and the departments' news/ feeds, and the front page that included the feed:
a table per item, title row, text row, "05 Jun 2007 author" row), WordPress (vesti.mas.bg.ac.rs, 2014: .hentry), and
hand-made pages (front page before 2006, upis, the departments' own sites), where an item starts with its date,
"24.1.2003.", and runs to the next date in the same table cell. The same item from many copies and pages is one row:
by section (whose news it is), date and title (hand-made: the first words), the newest copy's text, a full story when
one was saved, and every copy it was seen in.
"""

import hashlib
import html
import json
import re
import sys
from difflib import SequenceMatcher
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import nh3
from bs4 import BeautifulSoup

OUT = Path(__file__).resolve().parent.parent / "work" / "wayback"
TAGS = {"a", "b", "strong", "i", "em", "u", "br", "p", "ul", "ol", "li", "table", "tr", "td", "th", "tbody"}
MONTHS = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
SR_MONTHS = {m: i for i, m in enumerate("јан феб мар апр мај јун јул авг сеп окт нов дец".split(), 1)}
SR_MONTHS.update({m: i for i, m in enumerate("jan feb mar apr maj jun jul avg sep okt nov dec".split(), 1)})
CN_DATE = re.compile(r"^\s*(\d{1,2}) ([A-Za-z]{3}) ((?:19|20)\d\d)\b\s*(.*)$", re.S)
DATE = re.compile(r"^[\s.,;:\-–—•·*(]*(\d{1,2})\s*[./]\s*(\d{1,2})\s*[./]\s*((?:19|20)\d\d)\b\.?")
DATE2 = re.compile(r"^\s*\[\s*(\d{1,2})\s+(\d{1,2})\s+((?:19|20)\d\d)\s*\]")
WP_DATE = re.compile(r"(\d{1,2})\.?\s+([^\W\d_]{3})[^\W\d_]*\.?,?\s+((?:19|20)\d\d)")
SPLIT = "@@ARTICLE@@"


def decode(b):
    """The page's text: its declared charset, else UTF-8, else Windows Latin 2."""
    m = re.search(rb'charset=["\']?([\w-]+)', b[:4000])
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8", "cp1250"]:
        try:
            return b.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return b.decode("cp1250", "replace")


def clean(fragment):
    """Only the text's own markup (nh3 also closes what a cut left open)."""
    out = nh3.clean(fragment, tags=TAGS, attributes={"a": {"href"}}, link_rel=None, strip_comments=True)
    out = re.sub(r"[-_=]{6,}", "", out)  # the hand-made pages' text rules between items
    out = re.sub(r"Н\s*О\s*В\s*О\s*!+", "", out)  # the old front page's "Н О В О !!!" heading over the next item
    return re.sub(r"(\s*<br>\s*)+$|^(\s*<br>\s*)+", "", re.sub(r"(<br>\s*){3,}", "<br><br>", out)).strip()


def text_of(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def ymd(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def section(key):
    """Whose news: the feed's folder (…/news-ra), the faculty's main news for its front pages, else the page."""
    host, _, path = key.split("?")[0].partition("/")
    path = path.removeprefix("_export/xhtml/")  # DokuWiki's bare copy of the page
    m = re.match(r"(.*?/?news[^/]*)/", path)
    if host == "www" and m:
        return f"www/{m.group(1)}"
    if host == "www" and re.match(r"(index\.html?|default\.html?|(mfb-en/)?najvesti.*|arhivavesti\.html|template/.*|vesti/.*|news/.*)?$", path):
        return "www/vesti"
    if host == "www":
        return f"www/{path}"
    return host


def cutenews(soup):
    """[(title, html, date, author, id)] from CuteNews's item tables."""
    out = []
    for i in soup.find_all("i"):
        m = CN_DATE.match(i.get_text(" ", strip=True))
        meta = i.find_parent("table")
        item = meta and meta.find_parent("table")
        if not (m and item and m.group(2).lower() in MONTHS):
            continue
        rows = [r for r in item.find_all("tr") if r.find_parent("table") is item]
        if len(rows) < 3:
            continue
        cell = rows[1].find("td")
        body = cell.find("font") or cell
        ids = re.findall(r"[?&](?:amp;)?id=(\d{9,})", str(meta))
        out.append((rows[0].get_text(" ", strip=True), clean(body.decode_contents()),
                    ymd(m.group(3), MONTHS[m.group(2).lower()], m.group(1)), m.group(4).strip(), ids[0] if ids else None))
    return out


def wordpress(soup):
    out = []
    for post in soup.select(".hentry"):
        t = post.select_one(".entry-title")
        body = post.select_one(".entry-content") or post.select_one(".entry-summary")
        meta = post.select_one(".entry-meta") or post.select_one(".post-date") or post
        tm = meta.find("time")
        when = None
        if tm and tm.get("datetime"):
            when = tm["datetime"][:10]
        elif m := re.search(r"(\d{1,2})\.(\d{1,2})\.((?:19|20)\d\d)", meta.get_text(" ", strip=True)):
            when = ymd(m.group(3), m.group(2), m.group(1))
        elif m := WP_DATE.search(meta.get_text(" ", strip=True)):
            mon = SR_MONTHS.get(m.group(2).lower()) or MONTHS.get(m.group(2).lower())
            when = mon and ymd(m.group(3), mon, m.group(1))
        pid = next((c[5:] for c in post.get("class", []) if re.fullmatch(r"post-\d+", c)), None)
        who = post.select_one(".author")
        out.append((t.get_text(" ", strip=True) if t else "", clean(body.decode_contents()) if body else "",
                    when, who.get_text(" ", strip=True) if who else "", pid))
    return out


def date_at(s):
    """(ISO date, the text after it) when s starts with a date: 24.1.2003., 31/10/2012, [ 25 03 2008 ]."""
    m = DATE.match(s) or DATE2.match(s)
    when = m and ymd(m.group(3), m.group(2), m.group(1))
    return (when, s[m.end():].lstrip(" \xa0-–:]")) if when else (None, s)


def dated(soup):
    """Hand-made pages: an item from each date that starts a text to the next one in the same cell."""
    # A date Word split into pieces, <b>2<span>8/03/2012</span></b>: one string.
    for tag in soup.find_all(["b", "strong", "font", "span", "i", "u", "p"]):
        t = tag.get_text()
        if len(t) < 40 and tag.find(True) and date_at(t)[0] and not date_at(next(tag.strings, ""))[0]:
            tag.string = t
    marks = defaultdict(list)
    for s in soup.find_all(string=lambda s: date_at(s)[0]):
        if not s.find_parent(["script", "style", "title", "select", "option"]):
            marks[id(s.find_parent("td") or s.find_parent("body") or soup)].append(s)
    out = []
    for strings in marks.values():
        cell = strings[0].find_parent("td") or strings[0].find_parent("body") or soup
        whens = []
        for s in strings:
            when, rest = date_at(str(s))
            whens.append(when)
            s.replace_with(SPLIT + rest)
        for when, part in zip(whens, cell.decode_contents().split(SPLIT)[1:]):
            body = clean(part)
            if len(text_of(body)) >= 12:
                out.append((None, body, when, "", None))
    return out


def main():
    rows = [j for j in map(json.loads, (OUT / "news.jsonl").read_text("utf-8").splitlines()) if j.get("ok")]
    found = {}
    for r in sorted(rows, key=lambda r: r["ts"]):
        raw = (OUT / r["path"]).read_bytes()
        # www/novosti/ (2000–2001): EUnet's news, its pages under the faculty's address then. studije/vesti (2014,
        # DokuWiki): the nastava board's posts, which the archive has.
        if re.match(r"www/(novosti/|(_export/xhtml/)?studije/vesti)", r["key"]) or b"<" not in raw[:2000]:
            continue
        soup = BeautifulSoup(decode(raw), "html.parser")
        for a in soup.find_all("a", href=True):
            a["href"] = urljoin(r["url"], a["href"].strip())
        kind, items = "cutenews", cutenews(soup)
        if not items and soup.select(".hentry"):
            kind, items = "wordpress", wordpress(soup)
        if not items:
            kind, items = "dated", dated(soup)
        full = "subaction=showfull" in r["key"] or bool(re.search(r"\?p=\d", r["key"]))
        sec = section(r["key"])
        for title, body, when, who, nid in items:
            text = text_of(body)
            if not when or not (title or text):
                continue
            made = not title
            title = title or (text[:90].rsplit(" ", 1)[0] + "…" if len(text) > 90 else text)
            k = (sec, nid) if kind == "wordpress" else (sec, when, norm(title)[:80] if not made else norm(text)[:60])
            a = found.setdefault(k, dict(section=sec, kind=kind, date=when, title=title, title_made=made, author=who,
                                         id=nid, html="", full="", pages=[], copies=[]))
            # The newest copy's text (sorted by capture time); a full-story page's text as full.
            if full and len(body) >= len(a["full"]):
                a["full"] = body
            elif not full:
                a["html"], a["title"] = body, title
            a["author"] = a["author"] or who
            a["id"] = a["id"] or nid
            if r["key"] not in a["pages"]:
                a["pages"].append(r["key"])
            a["copies"].append(f"https://web.archive.org/web/{r['ts']}/{r['url']}")
    # A hand-made item edited between copies (its first words changed): one, the newer text.
    arts, kept = [], defaultdict(list)
    for a in sorted(found.values(), key=lambda a: a["copies"][-1].split("/")[4]):
        same = a["kind"] == "dated" and next((b for b in kept[(a["section"], a["date"])] if b["kind"] == "dated"
                                              and SequenceMatcher(None, text_of(b["html"])[:300], text_of(a["html"])[:300]).ratio() > 0.85), None)
        if same:
            same.update(html=a["html"], title=a["title"], pages=list(dict.fromkeys(same["pages"] + a["pages"])),
                        copies=sorted(set(same["copies"] + a["copies"]), key=lambda c: c.split("/")[4]))
        else:
            kept[(a["section"], a["date"])].append(a)
            arts.append(a)
    arts.sort(key=lambda a: (a["date"], a["section"]))
    for a in arts:
        if not a["html"]:
            a["html"], a["full"] = a["full"], ""
        if a["full"] and text_of(a["full"]) == text_of(a["html"]):
            a["full"] = ""
        a["key"] = hashlib.sha1(f"{a['section']}|{a['date']}|{a['title']}".encode()).hexdigest()[:12]
        a["text"] = text_of(a["html"] + " " + a["full"])
    with (OUT / "articles.jsonl").open("w", encoding="utf-8") as f:
        for a in arts:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(arts)} articles, {Counter(a['kind'] for a in arts)}")
    by = defaultdict(Counter)
    for a in arts:
        by[a["section"]][a["date"][:4]] += 1
    for sec, years in sorted(by.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{sum(years.values()):5} {sec}: " + " ".join(f"{y}:{n}" for y, n in sorted(years.items())))


if __name__ == "__main__":
    main()
