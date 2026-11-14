"""Serbian Cyrillic and Latin, one table for the whole repo (no dependencies: build.py, teams.py import it).
pages/static/pismo.js has its own copy for the browser: a change here goes there too."""

import re
import unicodedata
from functools import lru_cache

CYRILLIC = "абвгдђежзијклљмнњопрстћуфхцчџш"
# As written in Latin, and as plain ASCII (folded: what search and the name matching compare).
LATIN = "a b v g d đ e ž z i j k l lj m n nj o p r s t ć u f h c č dž š".split()
ASCII = "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()
FOLD = dict(zip(CYRILLIC, ASCII))
LAT = dict(zip(CYRILLIC, LATIN))
assert len(FOLD) == len(LAT) == 30

# lat(): the letters as one table; Љ, Њ, Џ (two Latin letters) by the next letter, before it.
_LAT_TABLE = str.maketrans({**LAT, **{c.upper(): l.upper() for c, l in LAT.items() if len(l) == 1}})
_TWO = re.compile("[ЉЊЏ]")


def _two(m):
    l, after = LAT[m[0].lower()], m.string[m.end() : m.end() + 1]
    return l.upper() if after and after != after.lower() else l[0].upper() + l[1:]


def lat(s):
    """Serbian Cyrillic to Latin, as pismo.js toLat shows a page by default: for what no script converts (the link
    previews, base.html). Љ is 'LJ' in a word of capitals, 'Lj' otherwise. Escaped text stays escaped (Markup)."""
    out = _TWO.sub(_two, str(s or "")).translate(_LAT_TABLE)
    # Markup by name: markupsafe is build.py's, and teams.py does not install it.
    return type(s)(out) if type(s).__name__ == "Markup" else out


@lru_cache(maxsize=1 << 16)  # the same names are folded again and again (subjects, teachers, authors)
def fold(s):
    """Serbian Cyrillic to Latin, no diacritics, lower case. search.js folds the query the same way."""
    s = "".join(FOLD.get(ch, ch) for ch in (s or "").lower()).replace("đ", "dj")
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if not unicodedata.combining(ch))


def to_cyr(s):
    """'Miloš Glavonjić' -> 'Милош Главоњић' (masinac.org writes in Latin, the faculty in Cyrillic)."""

    def one(m):
        c = CYRILLIC[LATIN.index(m[0].lower())]
        return c.upper() if m[0][0].isupper() else c

    return re.sub("dž|lj|nj|[a-zčćšžđ]", one, s, flags=re.I)
