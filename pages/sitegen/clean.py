"""Making stored HTML safe and the site's own: the board's posts, cent's Divi pages, attachments, links."""

import re
from html import unescape
from urllib.parse import unquote, urljoin, urlsplit
import nh3
from bs4 import BeautifulSoup
from markupsafe import escape
from .text import BASE, strip_tags


def preuzeto(text):
    """The board's English download count, in Serbian: in a post's HTML and in its plain text (the search excerpt)."""
    return re.sub(r"Downloaded (\d+) times?", r"preuzeto \1 puta", text or "")


def clean_html(html, base=BASE, local=lambda value: None, classes=None):
    """Sanitize; a link that local() maps goes to this site, every other relative link to the faculty's page.
    classes: the classes to keep ({tag: {class}}, cent's CENT_CLASSES); none by default."""

    def attribute(tag, attr, value):
        if attr not in ("href", "src"):
            return value
        if value.startswith("data:"):
            return value if tag == "img" and value.startswith("data:image/") else None
        # Posts link relative to the board page, so attachments and images resolve to the faculty's site.
        # shortcut: board files are not hosted here; when the board deletes one, the link dies.
        # Drop the scraper's phpBB session id from the link, and the board's search highlight (hilit=, often Cyrillic).
        value = re.sub(r"([?&])hilit=[^&#]*&?", r"\1", re.sub(r"([?&])sid=[0-9a-f]+&?", r"\1", value))
        return local(value) or urljoin(base, re.sub(r"[?&]+(?=#|$)", "", value))

    # The board's attachment box is in English; in Serbian it reads right in both scripts.
    html = preuzeto(re.sub(r">\s*Attachments\s*<", ">Prilozi<", html or ""))
    html = nh3.clean(
        html,
        tags=nh3.ALLOWED_TAGS | {"tfoot"},
        attribute_filter=attribute,
        allowed_classes=classes,
        url_schemes=nh3.ALLOWED_URL_SCHEMES | {"data"},
        link_rel="noopener noreferrer",
    )
    # Kept classes leave the others' attribute empty.
    return (html.replace(' class=""', "") if classes else html) or None


# The classes cent_tidy gives cent's pages (style.css .cent-…): the only ones clean_html keeps.
CENT_CLASSES = {
    "details": {"cent-acc"},
    "summary": {"cent-head"},
    "div": {"cent-head", "cent-btns", "cent-c"},
    "b": {"cent-code"},
    "a": {"cent-btn", "cent-file"},
    # A file's type as on a post's attachments (FILE_KINDS).
    "span": {"cent-t", "cent-wk", "cent-btn", "att__t"} | {f"att__t--{k}" for k in ("pdf doc xls ppt zip img file video".split())},
}


def cent_tidy(html):
    """cent's Divi layout (cent.py keeps a page as shown) in this site's own classes, before clean_html drops Divi's:
    an accordion item is a <details>, closed as on cent; a lab row (code, title, file, week) a line like an accordion's
    head; a clickable block a button (one cent links nowhere, "#", stays a greyed one); a file link a chip with its
    type; a centred text stays centred."""
    soup = BeautifulSoup(html, "html.parser")

    def txt(el):
        return el.get_text(" ", strip=True) if el else ""

    def head(name, code, title, links, week):
        h = soup.new_tag(name, attrs={"class": "cent-head"})
        for tag, cls, text in (("b", "cent-code", code), ("span", "cent-t", title)):
            if text:
                h.append(soup.new_tag(tag, attrs={"class": cls}, string=text))
        for a in links:
            h.append(a.extract())
        if week:
            h.append(soup.new_tag("span", attrs={"class": "cent-wk"}, string=week))
        return h

    for t in soup.select(".et_pb_toggle"):
        h = t.select_one(".et_pb_toggle_title")
        links = [a.extract() for a in h.select("a[href]")] if h else []
        mark, title = (h.select_one(".accordion_mark"), h.select_one(".accordion_title")) if h else (None, None)
        d = soup.new_tag("details", attrs={"class": "cent-acc"})
        d.append(head("summary", txt(mark), txt(title) if title or mark else txt(h), links, txt(h and h.select_one(".accordion-nedelja"))))
        if body := t.select_one(".et_pb_toggle_content"):
            d.append(body.extract())
        t.replace_with(d)
    for row in soup.select(".et_pb_row:has(> #at-col-head)"):
        title = next((txt(c) for c in row.select(":scope > #at-col") if txt(c)), "")
        row.replace_with(
            head(
                "div",
                txt(row.select_one("#at-col-head")),
                title,
                row.select("#at-col-attach a[href]"),
                txt(row.select_one("#at-col-nedelja")),
            )
        )
    for el in soup.select(".et_clickable"):
        # The innermost: a clickable row holds clickable columns, each its own button.
        if el.select_one(".et_clickable") or el.find_parent(class_="cent-btn"):
            continue
        if not txt(el):
            el.decompose()
            continue
        a = el.find("a", href=True)
        b = (
            soup.new_tag("a", attrs={"class": "cent-btn", "href": a["href"]}, string=txt(el))
            if a
            else soup.new_tag("span", attrs={"class": "cent-btn", "title": "bez linka na sajtu katedre"}, string=txt(el))
        )
        row = el.find_parent(class_="et_pb_row")
        if row:
            row["class"] = "cent-btns"
        el.replace_with(b)
    for a in soup.select("a[href]"):
        path = unquote(urlsplit(a["href"]).path)
        ext = re.search(r"\.(\w{1,4})$", path.lower())
        # A file icon cent.py named by its file, or a video's.
        if "cent-btn" in a.get("class", []):
            continue
        if txt(a) == "video":
            kind, badge = "video", "▶"
        elif ext and txt(a) == path.rsplit("/", 1)[-1]:
            kind, badge = FILE_KINDS.get(ext[1], "file"), ext[1].upper()
        else:
            continue
        a["class"] = "cent-file"
        a.insert(0, soup.new_tag("span", attrs={"class": f"att__t att__t--{kind}"}, string=badge))
    for el in soup.select(".et_pb_text_align_center"):
        el["class"] = "cent-c"
    return str(soup)


# A board attachment after clean_html: <dl><dt><span></span> <a href>name</a></dt>[<dd>comment</dd>]<dd>(size)
# preuzeto N puta</dd></dl>.
ATTACHMENT = re.compile(
    r'<dl>\s*<dt>(?:<span></span>)?\s*<a href="([^"]+)"[^>]*>([^<]*)</a>\s*</dt>\s*'
    r"(?:<dd>((?:(?!</?d[dlt]>).)*)</dd>\s*)?<dd>\(([^)<]*)\)\s*([^<]*)</dd>\s*</dl>",
    re.S,
)

# A file type's colour on its badge (style.css .att__t--*).
FILE_KINDS = {
    **dict.fromkeys(["pdf"], "pdf"),
    **dict.fromkeys(["doc", "docx", "odt", "rtf"], "doc"),
    **dict.fromkeys(["xls", "xlsx", "ods", "csv"], "xls"),
    **dict.fromkeys(["ppt", "pptx", "pps", "ppsx", "odp"], "ppt"),
    **dict.fromkeys(["zip", "rar", "7z"], "zip"),
    **dict.fromkeys(["jpg", "jpeg", "png", "gif"], "img"),
}


def downloads(html):
    """A post's attachments as (attachment id, file name, downloads), from clean_html's output.
    shortcut: the count is as the board showed it when the topic was last fetched (only changed or recent topics are
    fetched again); re-fetch every topic now and then if fresh counts matter."""
    return [
        (int(i[1]), unescape(m[2]), int(n[0]) if (n := re.search(r"\d+", m[5])) else 0)
        for m in ATTACHMENT.finditer(html or "")
        if (i := re.search(r"file\.php\?id=(\d+)", m[1]))
    ]


def attachments(html):
    """A post's attachments as rows (style.css .att): the file's type as a badge, its name, its comment, its size and
    downloads. It runs on clean_html's output and only moves its parts, which are sanitized already; the type is
    letters only."""

    def row(m):
        ext = re.search(r"\.([a-z0-9]{1,5})\s*$", unescape(m[2]).lower())
        ext = ext[1] if ext else ""
        note = f'<span class="att__c">{m[3].strip()}</span>' if m[3] and m[3].strip() else ""
        return (
            f'<a class="att" href="{m[1]}" rel="noopener noreferrer"><span class="att__t att__t--{FILE_KINDS.get(ext, "file")}">'
            f'{ext.upper() or "FAJL"}</span><span class="att__n">{m[2]}{note}<small>{m[4]} · {m[5].strip()}</small></span></a>'
        )

    return ATTACHMENT.sub(row, html) if html else html


# A link written as text (ie's): made a link. Not its last dot, comma or bracket (the sentence's).
BARE_URL = re.compile(r"https?://[^\s<>\"']+[^\s<>\"'.,;:!?)\]]")


def linkify(html):
    """The addresses written as text in a notice, as links (shortened to 60 letters); not those inside a link."""
    out, inside = [], False
    for part in re.split(r"(<[^>]+>)", html or ""):
        if part.startswith("<"):
            inside = bool(re.match(r"<a\b", part)) or (inside and not part.startswith("</a"))
        elif not inside:
            part = BARE_URL.sub(
                lambda m: f'<a href="{m[0]}" rel="noopener noreferrer">{m[0] if len(m[0]) <= 60 else m[0][:57] + "…"}</a>', part
            )
        out.append(part)
    return "".join(out)


def file_rows(files, title="Prilozi"):
    """Files [(href, name, note)] as a post's attachments (style.css .att): the type's badge, the name, a note under
    it. A file's name loses ie's upload number ("1815_РЕЗУЛТАТИ_2.docx"); one without (katedre.py's "link") is the
    address's."""

    def row(href, name, note):
        path = unquote(urlsplit(href).path)
        ext = (re.search(r"\.([a-z0-9]{1,5})$", path.lower()) or [None, ""])[1]
        file = re.sub(r"^\d+_", "", path.rsplit("/", 1)[-1])
        name, note = (file if x in (None, "", "link") or re.fullmatch(r"\d+_.+", x) else x for x in (name, note))
        note = None if note == name else note
        return (
            f'<dd><a class="att" href="{escape(href)}" rel="noopener noreferrer"><span class="att__t att__t--{FILE_KINDS.get(ext, "file")}">'
            f'{ext.upper() or "FAJL"}</span><span class="att__n">{escape(name)}'
            + (f"<small>{escape(note)}</small>" if note else "")
            + "</span></a></dd>"
        )

    # The links come from other sites, not through clean_html: a web address or the release's file, no javascript:.
    files = [f for f in files if re.match(r"(https?://|/files/)", f[0], re.I)]
    return f"<dl><dt>{title}</dt>{''.join(row(*f) for f in files)}</dl>" if files else ""


FILE_PATH = re.compile(r"(?:/file\.php|\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|7z|txt|csv|dwg|stp|step|m|py|jpe?g|png))$", re.I)


def has_kinds(it):
    """What a post has besides its text, for its topic's row (rows.html topic_row): (a file, a link). A file: an
    attachment, or a link to one (a cent or department file, a PDF anywhere); a link: any other web page, not the
    board's own (another thread, a quote's source)."""
    file, link = bool(it.get("files")), False
    for href in re.findall(r'<a\b[^>]*\bhref="([^"]+)"', it.get("html") or ""):
        u = urlsplit(unescape(href))
        if FILE_PATH.search(u.path):
            file = True
        elif u.scheme in ("http", "https") and (u.hostname or "").lower() != "nastava.mas.bg.ac.rs":
            link = True
    return file, link


def drop_empty_tables(html):
    """Leave out a table whose cells are all empty, with the heading right above it: the exam page keeps its forms
    with no rows between terms. The <div>s between the heading and the table stay (their </div> is after it)."""

    def table(m):
        cells = re.findall(r"<td\b[^>]*>(.*?)</td>", m[0], re.S)
        return (m[2] or "") if cells and not strip_tags("".join(cells)) else m[0]

    return re.sub(r"(?:<h([1-6])[^>]*>(?:(?!</?h[1-6]).)*</h\1>(\s*(?:<div[^>]*>\s*)*))?<table\b.*?</table>", table, html, flags=re.S)


NUMBERED = re.compile(r"(?:\w+\s+)?(\d+)[.:)]\s+")


def book_page(html):
    """The faculty's page of a subject -> its parts as predmet_opis.html shows them: {heading: (lines, numbered)} of the
    text sections; the hours (total, groups of (label, hours)) and the points ((label, points), the minimum for the exam),
    both without the zero rows; the literature, one book a row. Every page has the same sections (predmeti.py); the
    head (ID, ECTS, teachers) and 'Извођења' (the plans) are the page's head, from the same fields."""
    sec = {}
    for head, body in re.findall(r"<h[24][^>]*>(.*?)</h[24]>\s*<div[^>]*>(.*?)</div>", html or "", re.S):
        sec[strip_tags(head)] = [" ".join(l.split()) for l in unescape(re.sub(r"<[^>]+>", "\n", body)).splitlines() if l.strip()]
    pairs = lambda lines: [(m[1], int(m[2])) for l in lines if (m := re.fullmatch(r"(.+?):\s*(\d+)", l))]
    total = pairs(sec.get("Фонд часова", []))
    points = pairs(sec.get("Провера знања (укупно 100 поена)", []))

    def text(h):
        """(lines, numbered): numbered when the lines go 1, 2, 3 ('1. Увод', 'Лекција 2: …'), the numbers taken off
        (the list shows them); else a bullet ('- ') off each line."""
        lines = sec.get(h, [])
        nums = [int(m[1]) if (m := NUMBERED.match(l)) else 0 for l in lines]
        if len(lines) > 1 and nums == list(range(1, len(lines) + 1)):
            return [NUMBERED.sub("", l, count=1) for l in lines], True
        return [re.sub(r"^[-–•]\s*", "", l) for l in lines], False

    return dict(
        text={h: text(h) for h in ("Циљ", "Исход", "Садржај теоријске наставе", "Садржај практичне наставе", "Услов похађања", "Ресурси")},
        hours=dict(
            total=total[0][1] if total else None,
            groups=[
                (g, rows)
                for g in ("Активна настава (теоријска)", "Активна настава (практична)", "Провера знања")
                if (rows := [(l, n) for l, n in pairs(sec.get(g, [])) if n])
            ],
        ),
        points=[(l, n) for l, n in points if n and not l.startswith("Услов")],
        pass_min=next((n for l, n in points if l.startswith("Услов")), None),
        books=[b.strip() for b in " ".join(sec.get("Литература", [])).split(";") if b.strip()],
    )
