"""The pages of www.mas.bg.ac.rs the site shows (build.py render_wiki_pages) in the site's own look, before clean_html
sanitizes them: DokuWiki's ALL-CAPS in sentence case, its rules and spacer lines gone, its coloured and large text as
headings and highlights, date-and-time paragraphs as a timeline, dash lines as lists, "label: number" lists as rows,
"на линку" links named, lists of links as cards. That much works on any page; tune() adds what only one page has and
warns when that page changed under it, leaving the generic look."""
import re
import sys
from collections import Counter, defaultdict

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

# The classes tidy() gives, the only ones clean_html keeps on these pages (style.css .wt-…).
CLASSES = {"ol": {"wt-tl"}, "li": {"wt-tl__i"}, "b": {"wt-tl__d"}, "span": {"wt-tl__h", "wt-amt"},
           "strong": {"wt-hl"}, "p": {"wt-note", "wt-lbl"}, "ul": {"wt-links", "wt-tl__l"}, "dl": {"wt-kv"},
           "div": {"wt-box", "wt-card", "wt-cards"}, "a": {"wt-go"}, "table": {"wt-mod"}}

WORD = re.compile(r"[^\W\d_]+")
MONTHS = "јануар фебруар март април мај јун јул август септемб октоб новемб децемб".split()
DATE = re.compile(r"\d{1,2}\.\s*(?:" + "|".join(MONTHS) + r")\S*\s*\d{4}", re.I)
TIME = re.compile(r"^\s*((?:до|од|у|после)?\s*\d{1,2}[:.]\d{2}(?:\s*[–-]\s*\d{1,2}[:.]\d{2})?)\s*[—–-]\s*", re.I)
MARK = re.compile(r"^\s*[-•−–·]\s*")
MONEY = re.compile(r"\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*(?:динара|евра|дин\.|RSD|EUR)")
KV = re.compile(r"^(.{3,160}?):\s*(\d[\d.,]*(?:\s*\S{1,8})?)\s*$")
# A link whose text says only where it is ("на линку", "овде"), and the words around it that say the same.
BARE = re.compile(r"^\s*(?:на\s+)?(?:следећем\s+)?(?:линку|линк|овде|link|ovde)\s*[.:]?\s*$", re.I)
FILLER = re.compile(r"\s*(?:Детаљно\s+можете\s+прочитати|можете\s+погледати|налаз[еи]\s+се)?\s*(?:на\s+)?(?:следећем\s+)?"
                    r"(?:линку|овде)?\s*[.:]?\s*$", re.I)
RED = re.compile(r"color:\s*(?:#f00\b|#ff0000|red\b|#e[0-9a-f]0000|#c00\b|#cc0000)", re.I)
COLOR = re.compile(r"color:\s*#?[0-9a-z]+", re.I)
LARGE = re.compile(r"font-size:\s*(?:large|x+-large|larger|1[.,][2-9]em|[2-9]em)", re.I)


def warn(path, what):
    print(f"[warn] mf/{path}: {what} not found, shown as the other pages", file=sys.stderr)


def lexicon(texts):
    """Each word's usual spelling in the wiki's ordinary text: {lower: form}. A word in an ALL-CAPS run is shouting,
    not counted; one alone in capitals (ОАС, ЕСПБ) is an acronym, kept as one only if never seen in small letters."""
    forms = defaultdict(Counter)
    for text in texts:
        for sentence in re.split(r"(?<=[.!?:;])\s+|\n", text):
            words = WORD.findall(sentence)
            for i, w in enumerate(words):
                caps = lambda j: 0 <= j < len(words) and words[j].isupper() and len(words[j]) > 1
                if i == 0 or (caps(i) and (caps(i - 1) or caps(i + 1))):
                    continue
                forms[w.lower()][w] += 1
    # An acronym seen in small letters too (оас in an address) stays one while it is more often in capitals.
    out = {}
    for low, c in forms.items():
        small = [(n, f) for f, n in c.items() if not f.isupper()]
        caps = sum(n for f, n in c.items() if f.isupper())
        out[low] = max(small)[1] if small and sum(n for n, _ in small) >= caps else c.most_common(1)[0][0]
    return out


def recase(text, lex, first):
    """ALL-CAPS text in the wiki's usual spelling; first: it starts a sentence."""
    # A one-letter word (У, И) is a preposition or a conjunction, never an acronym.
    out = WORD.sub(lambda m: m[0].lower() if len(m[0]) == 1 else lex.get(m[0].lower(), m[0].lower())
                   if m[0].isupper() else m[0], text)
    if first:
        out = re.sub(r"^(\W*)(\w)", lambda m: m[1] + m[2].upper(), out, count=1)
    return out


def shouting(text):
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > .8


def lines(p):
    """A block's content split at its <br>s: [[node, ...], ...], blank lines dropped."""
    out, cur = [], []
    for node in list(p.children):
        if isinstance(node, Tag) and node.name == "br":
            out.append(cur)
            cur = []
        else:
            cur.append(node)
    out.append(cur)
    return [ln for ln in out if text_of(ln).strip() or any(isinstance(n, Tag) and (n.name == "img" or n.find("img"))
                                                           for n in ln)]


def text_of(nodes):
    return "".join(n.get_text() if isinstance(n, Tag) else str(n) for n in nodes)


def html_of(nodes):
    return "".join(str(n) for n in nodes).strip()


def tidy(html, path, lex):
    soup = BeautifulSoup(html or "", "html.parser")
    root = soup.select_one("div.page") or soup
    new = lambda name, cls=None, **kw: soup.new_tag(name, attrs={"class": cls} if cls else {}, **kw)

    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for el in root.select("style, script, hr"):
        el.decompose()
    for img in root.select("img[width]"):  # the wiki's small decorations (a calendar icon above the dates)
        if img["width"].isdigit() and int(img["width"]) <= 100:
            img.decompose()
    for box in root.select("div[class*=wrap_]"):
        box.attrs = {"class": "wt-box"}
    for el in root.select("div.level1, div.level2, div.level3, div.level4, div.level5, div.li, div.table, div.page"):
        if el is not root:
            el.unwrap()

    # Headings: the topmost the page uses under its title is h2; a large or coloured line on its own is an h3.
    hs = root.find_all(re.compile(r"^h[1-6]$"))
    if hs:
        top = min(int(h.name[1]) for h in hs[1:]) if len(hs) > 1 else int(hs[0].name[1])
        for h in hs[1:]:
            h.name = f"h{min(6, int(h.name[1]) - top + 2)}"
    for p in root.find_all("p"):
        styled = p.find("span", style=LARGE) or p.find("span", style=COLOR)
        t = p.get_text(" ", strip=True)
        if styled and t and styled.get_text(" ", strip=True) == t and len(t) < 140 and not p.find("a"):
            for img in p.find_all("img"):  # an image beside the heading stays, above it
                p.insert_before(img.extract())
            p.name, p.attrs = "h3", {}
            p.string = t
    for span in root.find_all("span", style=True):
        if RED.search(span["style"]):
            span.name, span.attrs = "strong", {"class": "wt-hl"}
        else:
            span.unwrap()

    # Capitals: a heading or block all in capitals in sentence case; a run of shouted words inside ordinary text in
    # the usual spelling, kept bold.
    for el in root.find_all(["h2", "h3", "h4", "h5", "h6", "p", "li", "strong", "b", "td", "dt"]):
        if not shouting(el.get_text()) or (el.parent and el.parent.name in ("strong", "b") and shouting(el.parent.get_text())):
            continue
        first = True
        for s in el.find_all(string=True):
            if s.strip():
                s.replace_with(recase(str(s), lex, first))
                first = False
    for s in root.find_all(string=True):
        if not isinstance(s, NavigableString) or isinstance(s, Comment) or not s.strip():
            continue
        parts, last, bold = [], 0, s.find_parent(["strong", "b", "h2", "h3", "h4", "h5", "h6"]) is not None
        for m in re.finditer(r"(?:\b[^\W\d_a-zа-шђјљњћџ]{2,}\b[\s,]*){2,}|\b[^\W\d_a-zа-шђјљњћџ]{6,}\b", str(s)):
            run = m[0].rstrip(" ,")
            fixed = recase(run, lex, not str(s)[:m.start()].strip() and s.previous_sibling is None)
            if fixed == run:
                continue
            parts += [str(s)[last:m.start()], (fixed,)]
            last = m.start() + len(run)
        if not parts:
            continue
        parts.append(str(s)[last:])
        nodes = []
        for part in parts:
            if isinstance(part, tuple):
                b = new("strong")
                b.string = part[0]
                nodes.append(part[0] if bold else b)
            elif part:
                nodes.append(part)
        s.replace_with(*[NavigableString(n) if isinstance(n, str) else n for n in nodes])

    # A heading in small letters ("услови коришћења") starts with a capital, as the rest of the site's.
    for h in root.find_all(re.compile(r"^h[2-6]$")):
        s = h.find(string=lambda s: s.strip())
        if s is not None:
            s.replace_with(re.sub(r"^(\W*)(\w)", lambda m: m[1] + m[2].upper(), str(s), count=1))

    # Blocks by their lines: a date with time lines under it is a timeline step; dash lines a list.
    for p in root.find_all("p"):
        ls = lines(p)
        if not ls:
            p.decompose()
            continue
        head = ls[0]
        first = [n for n in head if not (isinstance(n, NavigableString) and not n.strip())]
        if (len(ls) > 1 and len(first) == 1 and isinstance(first[0], Tag) and first[0].name in ("strong", "b")
                and DATE.search(first[0].get_text()) and all(TIME.match(text_of(ln)) for ln in ls[1:])):
            li = new("li", "wt-tl__i")
            d = new("b", "wt-tl__d")
            d.string = first[0].get_text(" ", strip=True)
            ul = new("ul", "wt-tl__l")
            for ln in ls[1:]:
                t = TIME.match(text_of(ln))
                row = new("li")
                h = new("span", "wt-tl__h")
                h.string = t[1].strip()
                rest = new("span")  # one grid cell, bold words and all
                rest.append(BeautifulSoup(re.sub(r"^\s*" + re.escape(t[0].strip()) + r"\s*", "", html_of(ln), count=1),
                                          "html.parser"))
                row.extend([h, rest])
                ul.append(row)
            li.extend([d, ul])
            p.replace_with(li)
            continue
        # Lines that are each one link only: cards.
        only = [[n for n in ln if isinstance(n, Tag) or n.strip()] for ln in ls]
        if len(ls) > 1 and all(len(o) == 1 and o[0].name == "a" for o in only):
            ul = new("ul", "wt-links")
            for o in only:
                li = new("li")
                li.append(o[0].extract())
                ul.append(li)
            p.replace_with(ul)
            continue
        # A person or an office: a bold name over lines with an e-mail address, a card.
        if (len(ls) > 1 and first and isinstance(first[0], Tag) and first[0].name in ("strong", "b") and len(first) == 1
                and len(p.get_text()) < 400 and (p.find("a", href=re.compile(r"^mailto:"))
                                                 or all(text_of(ln).strip() in ("-", "–") for ln in ls[1:]))):
            p.name, p["class"] = "div", "wt-card"
            br = first[0].find_next_sibling()
            if br is not None and br.name == "br":  # the name is a block already
                br.decompose()
            continue
        marked = [bool(MARK.match(text_of(ln))) for ln in ls]
        if sum(marked) and sum(marked) * 2 >= len(ls):
            intro, ul = [], new("ul")
            for ln, m in zip(ls, marked):
                if m:
                    li = new("li")
                    li.append(BeautifulSoup(MARK.sub("", html_of(ln), count=1), "html.parser"))
                    ul.append(li)
                elif not ul.contents:
                    intro.append(ln)
                else:
                    ul.contents[-1].append(BeautifulSoup(" " + html_of(ln), "html.parser"))
            for ln in intro:
                q = new("p")
                q.append(BeautifulSoup(html_of(ln), "html.parser"))
                p.insert_before(q)
            p.replace_with(ul)
            continue
        # Spacer <br>s at the block's ends.
        for end in (p.contents, p.contents[::-1]):
            for n in list(end):
                if isinstance(n, Tag) and n.name == "br" or isinstance(n, NavigableString) and not n.strip():
                    n.extract()
                else:
                    break

    # Timeline steps one after another make one timeline.
    for li in root.select("li.wt-tl__i"):
        prev = li.find_previous_sibling()
        if prev is not None and prev.name == "ol" and "wt-tl" in prev.get("class", []) and _adjacent(prev, li):
            prev.append(li.extract())
        else:
            ol = new("ol", "wt-tl")
            li.replace_with(ol)
            ol.append(li)
    # Cards one after another make a grid.
    for card in root.select("div.wt-card"):
        prev = card.find_previous_sibling()
        if prev is not None and "wt-cards" in prev.get("class", []) and _adjacent(prev, card):
            prev.append(card.extract())
        else:
            grid = new("div", "wt-cards")
            card.replace_with(grid)
            grid.append(card)
    # Lists one after another (a dash line per paragraph) make one list.
    for ul in root.find_all("ul"):
        nxt = ul.find_next_sibling()
        while nxt is not None and nxt.name == "ul" and not nxt.get("class") and not ul.get("class") and _adjacent(ul, nxt):
            ul.extend(list(nxt.children))
            nxt.decompose()
            nxt = ul.find_next_sibling()
    # Numbered paragraphs one after another ("1. које је завршило…") make a numbered list.
    for p in root.find_all("p"):
        if p.parent is None or not re.match(r"^\s*1\.\s+\D", p.get_text()) or DATE.match(p.get_text().strip()):
            continue
        ol, n, cur = new("ol"), 1, p
        while cur is not None and cur.name == "p" and re.match(rf"^\s*{n}\.\s+", cur.get_text()):
            nxt = cur.find_next_sibling()
            li = new("li")
            li.append(BeautifulSoup(re.sub(rf"^\s*{n}\.\s*", "", cur.decode_contents(), count=1), "html.parser"))
            ol.append(li)
            if cur is not p:
                cur.decompose()
            cur, n = nxt, n + 1
        if len(ol.contents) > 1:
            p.replace_with(ol)
        else:
            ol.decompose()

    # A list of "label: number" lines as rows; a list of bare links as cards.
    for ul in root.find_all("ul"):
        items = ul.find_all("li", recursive=False)
        kv = [KV.match(li.get_text(" ", strip=True)) for li in items]
        if len(items) >= 2 and all(kv) and not ul.get("class"):
            dl = new("dl", "wt-kv")
            for m in kv:
                dt, dd = new("dt"), new("dd")
                dt.string, dd.string = m[1].strip(" -"), m[2]
                dl.extend([dt, dd])
            ul.replace_with(dl)
            continue
        links = [li.find("a") for li in items]
        if items and all(a is not None and a.get_text(" ", strip=True) == li.get_text(" ", strip=True) for a, li in zip(links, items)):
            ul["class"] = "wt-links"

    # A link that says only "на линку": named after the bold words before it, else "Детаљније".
    for a in root.find_all("a"):
        if not BARE.match(a.get_text()):
            continue
        before = []
        for n in a.previous_siblings:
            before.insert(0, n)
        label = [n for n in before if isinstance(n, Tag) and n.name in ("strong", "b")]
        lead = text_of(before)
        if label and not FILLER.sub("", lead.replace(label[-1].get_text(), "")).strip(" .,:–-"):
            # The whole line is "<b>Name</b> is at the link": just the link, named.
            a.string = label[-1].get_text(" ", strip=True).strip(" .:")
            for n in before:
                n.extract()
            for n in list(a.next_siblings):
                if isinstance(n, NavigableString) and not n.strip(" .\n"):
                    n.extract()
        else:
            a.string = "Детаљније"
            for n in reversed(before):
                if isinstance(n, NavigableString):
                    trimmed = FILLER.sub("", str(n))
                    n.replace_with(trimmed + " " if trimmed.strip() else "")
                    break
            nxt = a.next_sibling
            if isinstance(nxt, NavigableString) and re.match(r"^\s*\.", nxt):
                nxt.replace_with(re.sub(r"^\s*\.", "", nxt))
        a["class"] = "wt-go"

    # Notes: "Напомена: …" set apart; a sum of money stands out.
    for p in root.find_all("p"):
        t = p.get_text(" ", strip=True)
        if re.match(r"^(?:ВАЖНА\s+)?НАПОМЕНА\b|^(?:Важна\s+)?[Нн]апомена\b", t, re.I):
            p["class"] = "wt-lbl" if len(t) < 20 else "wt-note"
    for s in root.find_all(string=MONEY):
        if s.find_parent(["strong", "b", "a", "dd"]) is not None:
            continue
        parts, last = [], 0
        for m in MONEY.finditer(str(s)):
            b = new("span", "wt-amt")
            b.string = m[0]
            parts += [NavigableString(str(s)[last:m.start()]), b]
            last = m.end()
        parts.append(NavigableString(str(s)[last:]))
        s.replace_with(*parts)

    tune(root, path, new)
    for el in root.find_all(["p", "li", "ul", "ol", "div", "strong", "b"]):
        if not el.get_text(strip=True) and not el.find(["img", "table", "a"]):
            el.decompose()
    return root.decode_contents() if root is not soup else str(soup)


def _adjacent(a, b):
    """b comes right after a, with only blank text between."""
    for n in a.next_siblings:
        if n is b:
            return True
        if isinstance(n, Tag) or str(n).strip():
            return False
    return False


MODULE = re.compile(r"(\d{1,2})\.\s*([^()\d]+?)\s*\(([^)]{2,8})\)\s*(\d+)\s*кандидат\S*")


def tune(root, path, new):
    """What only one page has. A page the faculty reworded keeps the generic look, with a warning."""
    if path == "upis/mas":
        # The master's modules, "1. Аутоматско управљање (САУ) 24 кандидата" in one block: a table.
        block = next((el for el in root.find_all(["div", "p", "ol", "ul"])
                      if len(MODULE.findall(el.get_text(" "))) >= 5 and not el.find(["div", "p"])), None)
        if block is None:
            return warn(path, "the list of modules")
        table = new("table", "wt-mod")
        head = new("tr")
        for t in ("Модул", "Ознака", "Места"):
            th = new("td")
            th.string = t
            head.append(th)
        table.append(head)
        for _, name, code, n in MODULE.findall(block.get_text(" ")):
            tr = new("tr")
            for t in (name.strip(), code, n):
                td = new("td")
                td.string = t
                tr.append(td)
            table.append(tr)
        block.replace_with(table)


if __name__ == "__main__":
    lex = lexicon(["Упис на Машински факултет у Београду, ОАС и МАС. Пријава у Служби за студентске послове."])
    assert recase("УПИС НА ОАС У БЕОГРАДУ", lex, True) == "Упис на ОАС у Београду", recase("УПИС НА ОАС У БЕОГРАДУ", lex, True)
    out = tidy('<div class="page"><h1>НАСЛОВ</h1><h2>ПРИЈАВА</h2><p><strong>16. септембар 2026. године</strong><br/>'
               '12:00 – 14:00 — Пријављивање кандидата.<br/>до 17:00 — Објављивање.</p>'
               '<p><strong>17. септембар 2026. године</strong><br/>10:00 — Испит.</p>'
               '<p>Број:<br/>-број студената са инвалидитетом: 4<br/>-број студената Рома: 2</p>'
               '<p><strong>Важни датуми</strong> налазе се на <a href="/x">линку.</a></p>'
               '<p>Упис страних студената Детаљно можете прочитати на <a href="/y">линку</a>.</p>'
               '<p>Школарина износи 111.000,00 динара.</p><p><img src="/a.png" width="650"/></p>'
               '<p><a href="/b"><img src="/b.png"/></a><br/></p></div>', "x", lex)
    assert '<img src="/a.png" width="650"/>' in out and '<img src="/b.png"/>' in out, out
    assert '<h2>Пријава</h2>' in out and out.count('class="wt-tl__i"') == 2 and out.count('<ol class="wt-tl">') == 1, out
    assert '<span class="wt-tl__h">12:00 – 14:00</span>' in out and '<dl class="wt-kv">' in out, out
    assert '<a class="wt-go" href="/x">Важни датуми</a>' in out and 'Упис страних студената <a class="wt-go" href="/y">Детаљније</a>' in out, out
    assert '<span class="wt-amt">111.000,00 динара</span>' in out, out
    print("ok")
