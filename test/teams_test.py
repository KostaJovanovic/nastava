# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "tzdata"]
# ///
"""The asserts of scrapers/teams.py (were its __main__ block), no network: uv run test/teams_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
import json  # noqa: E402
from teams import body, name_key, names_pattern, redact, title_of  # noqa: E402


def check():
    assert redact("Ana, 385-2023, ana@x.rs, 2023/2024") == "████ ████████, ████████, 2023/2024", redact(
        "Ana, 385-2023, ana@x.rs, 2023/2024"
    )
    assert redact("nema me na spisku. Milošević Nemanja 12/2024") == "nema me na spisku. █████████ ███████ ███████"
    assert redact("prijavljujem 1. kolokvijum, 7/2024 Đorđe Ilić.") == "prijavljujem 1. kolokvijum, ██████ █████ ████."
    r = names_pattern(["Petar Petrovic", "Jovan", "Đorđe Ilić"])
    assert r.sub("X", "pozdrav petrović  petar i Петар Петровић, Jovan, Djordje Ilic") == "pozdrav X i X, Jovan, X"
    assert name_key("Петровић Петар") == name_key("Petar Petrovic") == "petar petrovic"
    assert redact("Бојана Лучић 902/24, 2023/24") == "██████ █████ ██████, 2023/24"
    # A teacher's results list: the names and numbers go; times, school years and the teacher's address stay.
    assert redact("Matija Stepanović   175/2023  15.6", teacher=True) == "██████ ██████████   ████████  15.6"
    assert redact("Ana Ilić, 20-2024; ana.ilic@studenti.mas.bg.ac.rs", teacher=True) == "███ █████ ███████; " + "█" * 30
    assert (
        redact("Konsultacije Utorkom 10-12h, 2024/25, pera@mas.bg.ac.rs, dizajn@gmail.com", teacher=True)
        == "Konsultacije Utorkom 10-12h, 2024/25, pera@mas.bg.ac.rs, dizajn@gmail.com"
    )
    m = dict(
        messagetype="RichText/Html",
        **{"from": "x/8:orgid:s1"},
        content='<p>Hvala <span itemtype="http://schema.skype.com/Mention" '
        'itemid="0">Mirko</span> <img src="a">— Petar Petrović 12/2024</p>',
        properties=dict(mentions=json.dumps([dict(itemid=0, mri="8:orgid:t9")])),
    )
    n = {}
    label = lambda a: n.setdefault(a, f"Student #{len(n) + 1}")
    ids, pat = {"petar petrovic": "8:orgid:s1"}, names_pattern(["Petar Petrović"])
    assert body(m, label, ids, pat) == "<p>Hvala Student #1 — Student #2 ███████</p>", body(m, label, ids, pat)
    m["content"] = "<p>Petrovic Petar</p>"
    assert body(m, label, ids, pat) == "<p>Student #2</p>"
    assert title_of(dict(content="<p>Prvi red. Drugi</p>", properties={})) == "Prvi red."


check()
