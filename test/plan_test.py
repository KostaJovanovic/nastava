# /// script
# requires-python = ">=3.11"
# dependencies = ["pypdf"]
# ///
"""The asserts of ci/plan.py (were its __main__ block), no network: uv run test/plan_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ci"))
import datetime as dt  # noqa: E402
from plan import for_year, hot, parts, windows  # noqa: E402

_t = """ПРИЈАВЕ испита мањег блока (2.11.-4.11.)
ИСПИТИ мањег блока (VI недеља)
ПРИЈАВЕ испита за јануарски рок (11.1.-13.1.)
ЈАНУАРСКИ ИСПИТНИ РОК 18.1.-31.1.
ПРИЈАВЕ испита за фебруарски рок (3.2. и 4.2.)
ФЕБРУАРСКИ ИСПИТНИ РОК 8.2.-21.2.
(испитни дани 14.2. и 21.2.- надокнада за 15.2. и 16.2.)
ПРИЈАВЕ испита мањег блока (22.3.-24.3.)
ПРИЈАВЕ испита за јунски рок (31.5.-2.6.)
ЈУНСКИ ИСПИТНИ РОК 7.6.-20.6.
ПРИЈАВЕ испита за јулски рок (23.6.-24.6.)
ЈУЛСКИ ИСПИТНИ РОК 28.6.-11.7.
ПРИЈАВЕ испита за септембарски рок (16.8.-18.8.)
СЕПТЕМБАРСКИ ИСПИТНИ РОК 23.8.-5.9.
ПРИЈАВЕ испита за октобарски рок (8.9.-9.9.)
ОКТОБАРСКИ ИСПИТНИ РОК 13.9.-26.9."""
D = dt.date
_w = windows(_t, 2026)
assert _w == [
    ("prijave", D(2027, 1, 11), D(2027, 1, 13)),
    ("rok", D(2027, 1, 18), D(2027, 1, 31)),
    ("prijave", D(2027, 2, 3), D(2027, 2, 4)),
    ("rok", D(2027, 2, 8), D(2027, 2, 21)),
    ("prijave", D(2027, 5, 31), D(2027, 6, 2)),
    ("rok", D(2027, 6, 7), D(2027, 6, 20)),
    ("prijave", D(2027, 6, 23), D(2027, 6, 24)),
    ("rok", D(2027, 6, 28), D(2027, 7, 11)),
    ("prijave", D(2027, 8, 16), D(2027, 8, 18)),
    ("rok", D(2027, 8, 23), D(2027, 9, 5)),
    ("prijave", D(2027, 9, 8), D(2027, 9, 9)),
    ("rok", D(2027, 9, 13), D(2027, 9, 26)),
], _w
_p = lambda slot, *ymd: parts(slot, D(*ymd), _w)
assert _p("morning", 2027, 1, 18) == "forum studije" and _p("afternoon", 2027, 1, 18) == "forum"  # an exam period starts
assert _p("morning", 2027, 3, 1) == "forum studije" and _p("noon", 2027, 3, 1) == "forum"  # the 1st: morning only
assert _p("morning", 2026, 11, 10) == "forum" and _p("late", 2027, 3, 30) == "forum"  # every run scrapes
assert _p("evening", 2026, 12, 5) == "forum" and _p("late", 2027, 3, 1) == "forum"
assert _p("morning", 2027, 1, 11) == "forum studije" and _p("noon", 2027, 1, 11) == "forum"  # registration opens
assert _p("noon", 2027, 2, 2) == "forum" and _p("morning", 2027, 2, 1) == "forum studije"  # after January's; the 1st
assert _p("morning", 2027, 10, 1) == "forum studije nastavnici predmeti"  # the 1st, 1 October
assert _p("noon", 2026, 10, 1) == "forum"
assert hot(D(2026, 10, 3), [("rok", D(2026, 9, 13), D(2026, 9, 26))]) and not hot(D(2026, 10, 4), [("rok", D(2026, 9, 13), D(2026, 9, 26))])
_c = {2026: _w}
assert for_year(_c, 2027)[0] == ("prijave", D(2028, 1, 11), D(2028, 1, 13)) and for_year(_c, 2026) == _w and for_year({}, 2026) == []
assert for_year({2027: [("rok", D(2028, 2, 15), D(2028, 2, 29))]}, 2028) == [("rok", D(2029, 2, 15), D(2029, 2, 28))]
