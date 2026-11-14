"""Words and names: Serbian plurals, katedra names, acronyms, slugs, dates; constants every part uses."""

import re
from html import unescape
from translit import fold


BASE = "https://nastava.mas.bg.ac.rs/nastava/"

KIND = {"post": "obavestenje", "document": "dokument", "vest": "vest", "cent": "obavestenje", "katedra": "obavestenje"}

SITE_URL = "https://masinci.org"

# The noun after a number: 1, 21 thread; 2, 3, 4, 22 threada; 5–20, 11–14 threadova.
# The site's words: a topic is a "thread" (Cyrillic "низ", pismo.js), one post in it a "post".
FORMS = {
    "thread": ("thread", "threada", "threadova"),
    "post": ("post", "posta", "postova"),
    "odgovor": ("odgovor", "odgovora", "odgovora"),
    "predmet": ("predmet", "predmeta", "predmeta"),
    "nastavnik": ("nastavnik", "nastavnika", "nastavnika"),
    "autor": ("autor", "autora", "autora"),
    "prilog": ("prilog", "priloga", "priloga"),
    "preuzimanje": ("preuzimanje", "preuzimanja", "preuzimanja"),
    "verzija": ("verzija", "verzije", "verzija"),
    "čas": ("čas", "časa", "časova"),
    "poen": ("poen", "poena", "poena"),
    "rad": ("rad", "rada", "radova"),
}


def plural(n, word):
    one, few, many = FORMS[word]
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


# The masculine plurals among the katedre; every other name changes only a feminine '-у' (or is neuter).
KATEDRA_NOM = {
    "моторе": "мотори",
    "системе наоружања": "системи наоружања",
    "хидрауличне машине и енергетске системе": "хидрауличне машине и енергетски системи",
}


def katedra(k):
    """'Катедра за математику' -> 'математика': in a list headed Katedra the prefix only repeats, and the name
    stands alone, so in the nominative."""
    rest = re.sub(r"^(Катедра|Katedra) (за|za) ", "", k or "")
    # What follows 'у' ('технологије у машинству') is in its own case: kept.
    head, at, tail = rest.partition(" у ")
    return KATEDRA_NOM.get(rest) or re.sub(r"у\b", "а", head) + at + tail


# The short words a subject's acronym may leave out: teachers write both ОИККЗС and ОККЗС, ПЗСУЕ and ПЗСЕ.
ACR_SKIP = {"i", "u", "iz", "za", "na", "o", "od", "sa", "s", "a", "po", "pri", "kod", "ili"}


def acronyms(name, titles=()):
    """A subject's acronyms for the search, folded: its words' initials with the short words and without, with its
    number and without (ООК; МЕ1 and МЕ). And one in its topics' titles (ММ1, БМИО) whose letters follow the name's
    and hold its initials (БМИО: Биомедицинска инструментација и опрема; ДОМАЋИ and ГРУПА are no one's)."""
    words = re.findall(r"[a-z0-9]+", fold(name))
    out = set()
    for ws in (words, [w for w in words if w not in ACR_SKIP]):
        a = "".join(w if w[0].isdigit() else w[0] for w in ws)
        out |= {a, re.sub(r"\d+$", "", a)}
    key = "".join(w[0] for w in words if w not in ACR_SKIP and not w[0].isdigit())

    def follows(a, b):
        """a's letters in b, in order: 'bmio' in 'biomedicinska...'."""
        rest = iter(b)
        return all(c in rest for c in a)

    for title in titles:
        for m in re.finditer(r"(?<!\w)([A-ZА-ЯЂЈЉЊЋЏŠĐČĆŽ]{2,6})(\d?)(?!\w)", title):
            letters, num = fold(m[1]), m[2]
            # Three letters at least: МИ (the smer) is not Механика 3's.
            if (
                len(letters) > 2
                and key
                and letters[0] == key[0]
                and follows(key, letters)
                and follows(letters, "".join(words))
                and (not num or num in words)
            ):
                out.add(letters + num)
    return {a for a in out if len(a) > 1}


def slug(s):
    """A name as a URL part: 'Душан Љ. Ђукић' -> 'dusan-lj-djukic'."""
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")


def desc(text, n=160):
    """A page's description (base.html): its text on one line, cut at a word."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def set_hrefs(rows, path):
    """Give each row href path(row); a name that folds the same as an earlier row's gets the row's suffix (a past
    teacher's years) or id appended. rows: in the order they first appeared, so an existing page keeps its URL when a
    namesake is added later."""
    seen = set()
    for r in rows:
        href = path(r)
        if href in seen:
            href = f"{href[:-1]}-{r.get('suffix') or r['id']}/"
        seen.add(href)
        r["href"] = href


def parse_date(*values):
    """Return (iso date or None, year or None) from the first parsable value."""
    for v in values:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", v or "")
        if m:
            return f"{m[3]}-{m[2]}-{m[1]}", int(m[3])
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v or "")
        if m:
            return m[0], int(m[1])
    return None, None


def strip_tags(html):
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html or "")).split())


LINK = re.compile(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)

AZBUKA = {c: i for i, c in enumerate("абвгдђежзијклљмнњопрстћуфхцчџш")}


def azbuka(word):
    return [AZBUKA.get(c, 100 + ord(c)) for c in word.lower()]


# The programs in the order of the faculty's studies; a subject book program not here goes last.
PROGRAMS = [
    "Основне академске студије — МИ",
    "Основне академске студије — ИТМ",
    "Мастер академске студије — МИ",
    "Мастер академске студије — Индустрија 4.0",
    "Докторске студије — МИ",
]

# The board's smer names end in these abbreviations; the pages spell them out.
PROGRAM_NAMES = {"МИ": "Машинско инжењерство", "ИТМ": "Информационе технологије у машинству"}


def slot_label(slot_name, slot):
    """'Изборни предмет 5.4.5', '5.4' -> 'Изборни предмет 5.4': the cell's last number is the ECTS."""
    return re.sub(r"\s*[\d.]+$", "", slot_name) + " " + slot


def short_smer(name):
    """'основне академске студије - МИ' -> 'ОАС - МИ': the faculty's own abbreviations, for the smer's URL."""
    return re.sub(r"^мастер академске студије", "МАС", re.sub(r"^основне академске студије", "ОАС", name, flags=re.I), flags=re.I)


def smer_label(name):
    """'основне академске студије - МИ' -> 'Основне академске студије - Машинско инжењерство': the smer as shown."""
    name = re.sub(r" - (МИ|ИТМ)$", lambda m: " - " + PROGRAM_NAMES[m[1]], name)
    return name[:1].upper() + name[1:]


def smer_abbr(name):
    """'мастер академске студије - индустрија 4.0' -> 'Мастер академске студије - Инд. 4.0': the smer on a phone."""
    name = re.sub(r" - индустрија 4\.0$", " - Инд. 4.0", name, flags=re.I)
    return name[:1].upper() + name[1:]
