"""What the public build leaves out (docs/PLAN-pravno.md 2, 5.3): a text that lists students (exam results with names
and index numbers) shows a note and the original's link instead, and is not in the search; what was removed on
request is not built at all; a removed name is taken out of every text. The local server (output.dev) shows all.
data/izostavljeno.json is the hand-kept part (its "_" says what each list holds)."""

import json
import re
from markupsafe import escape
from common import INDEX_NO
from translit import lat
from .output import HERE
from .text import strip_tags

KEPT = HERE.parent / "data" / "izostavljeno.json"

LIST_MIN = 5  # index numbers in one text, as common.lists_students


def load_kept(path=KEPT):
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {k: set(data.get(k, [])) for k in ("liste", "nisu_liste", "uklonjeno")} | {"imena": list(data.get("imena", []))}


def lists_students(text):
    """Whether a plain text lists students: LIST_MIN index numbers or more (259/2023; not a school year, 2025/2026, a
    file number after a dash, 451-03-68/2020, nor a date's month, 22/11/2008)."""
    before = lambda m: text[max(0, m.start() - 2) : m.start()]
    return sum(int(m[1]) < 1900 and not re.search(r"(-|\d/)$", before(m)) for m in INDEX_NO.finditer(text or "")) >= LIST_MIN


def is_list(key, text, kept):
    return key in kept["liste"] or (key not in kept["nisu_liste"] and lists_students(text))


def note(url):
    """In place of a list: what was there and where it is."""
    link = f' Pogledaj ga na <a href="{escape(url)}" rel="noopener noreferrer">originalu</a>.' if url else ""
    return f'<p class="note">Ovde je bio spisak studenata (imena, brojevi indeksa), pa ga sajt ne prikazuje.{link}</p>'


def unname(text, names):
    """Each removed name (and its Latin form) out of a text. shortcut: the name as written, in either script, not its
    other cases ("Петра Петровића"); list each form that occurs."""
    for n in names:
        for form in {n, lat(n)}:
            text = re.sub(re.escape(form), "…", text, flags=re.I) if text else text
    return text


# A summary's sentence of a birth (nastavnici-sazetak.jsonl: "Rođena je 1966. u Beogradu, gde …"), to the sentence's
# end: a dot before a capital (a year's dot, "2007. završila", goes on). Not a maiden name ("(rođena Mileusnić)").
BORN = re.compile(r"(?:^|(?<=\.\s))[^.]*?\b[Rr]ođen[ao]?\b[^.]*?\b(?:1[89]|20)\d\d\..*?(?:\.(?=\s+[A-ZŠĐČĆŽ])|\.$|$)\s*", re.S)
# Their own death ("Preminuo je 2022."), not someone else's in their story ("posle njegove smrti", a mentor's).
DEAD = re.compile(r"\b(?:preminu(?:o|la)|umr(?:o|la)) je\b|†", re.I)


def unborn(t):
    """A living teacher's summary without their birth (docs/PLAN-pravno.md 4.2): dead when the history says so (a death
    year, a span 1950–2020) or the summary does."""
    h = t.get("history") or {}
    paras = t.get("summary") or []
    if h.get("died") or "–" in (h.get("life") or "") or DEAD.search(" ".join(paras)):
        return paras
    return [q for p in paras if (q := BORN.sub("", p).strip())]


def withhold(items, kept):
    """The public build's items: the removed ones left out; a list's text a note (html) and nothing to search (body
    "", noindex: no Pagefind body, output.mark_for_pagefind); a removed name out of the title and text."""
    out = []
    for it in items:
        if it["id"] in kept["uklonjeno"]:
            continue
        if kept["imena"]:
            for k in ("title", "html", "body"):
                it[k] = unname(it.get(k), kept["imena"])
        if is_list(it["id"], it.get("body") or strip_tags(it.get("html")), kept):
            it["html"] = None if it["kind"] == "document" else note(it.get("source_url"))
            it["body"], it["noindex"] = "", True
        out.append(it)
    return out


def withhold_pages(pages, kept):
    """A department site's pages (load_sajtovi: dict(title, url, html, seen)) the same way, by their URL."""
    out = []
    for p in pages:
        if p["url"] in kept["uklonjeno"]:
            continue
        if kept["imena"]:
            p["html"] = unname(p["html"], kept["imena"])
        if is_list(p["url"], strip_tags(p["html"]), kept):
            p["html"] = note(p["url"])
        out.append(p)
    return out
