# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The asserts of scrapers/katedre.py (were its __main__ block), no network: uv run test/katedre_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from datetime import date  # noqa: E402
from katedre import day, notices_of, strip, title_of  # noqa: E402

assert day("05.11.2026") == "2026-11-05" and day("01.01.1970") is day("16.12.1025") is day("- Bez datuma -") is None
assert title_of("Konacne ocene<br/>\n<br/>\nVAŽNO") == ("Konacne ocene", "VAŽNO")
assert title_of("Poštovani studenti,<br/>Prvi kolokvijum je 12.11.") == (
    "Prvi kolokvijum je 12.11.",
    "Poštovani studenti,<br/>Prvi kolokvijum je 12.11.",
)
assert title_of("Poštovani studenti, u prilogu su rezultati.") == (
    "U prilogu su rezultati.",
    "Poštovani studenti, u prilogu su rezultati.",
)
assert title_of("- Važno -<br/>Upis je u 12h.")[0] == "Upis je u 12h."
assert (
    title_of("U prilogu je spisak po grupama za izradu projektnog zadatka. Projekat se realizuje u grupama, a odbrane su 8. i 15. juna.")[0]
    == "U prilogu je spisak po grupama za izradu projektnog zadatka."
)
assert (
    title_of("Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali 320, a rezultati biće objavljeni na sajtu.")[0]
    == "Kolokvijum će se održati u sredu, 25. novembra 2026. godine u 14 časova u sali…"
)
assert day("25. 9. 2024.") == "2024-09-25" and day("17.06.2026", date(2026, 6, 16)) is None
_sum = lambda url, html: [(n["label"], n["date"], n["title"], strip(n["html"]), n["files"]) for n in notices_of(url, html)]
_n = _sum(
    "https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=5",
    "<section><div><h1>Vesti</h1>"
    "<div><h2>09.06.2026</h2><h2>Isto</h2></div><div><h2>09.06.2026</h2><h2>Isto</h2></div>"
    '<div><h2>16.12.1025</h2><h2>Tema \\\\\\"x\\\\\\"</h2><div><a href="https://ie/f.pdf">f.pdf</a></div></div>'
    "<div><h2>09.12.2025</h2><h2>Staro</h2></div></div></section>",
)
assert [x[1:3] + x[4:] for x in _n] == [
    ("2026-06-09", "Isto", []),
    ("2025-12-09", 'Tema "x"', [["https://ie/f.pdf", "f.pdf"]]),
    ("2025-12-09", "Staro", []),
], _n
# The other sites' layouts, from their pages (11.11.2026.).
assert _sum(
    "https://ie.mas.bg.ac.rs/novosti.php",
    "<div><h5>14.10.2019.</h5><p><b> Skup ICES 2019</b><br/><br/>Naši "
    "studenti,<br/><br/>učestvovali su.</p></div><div><h5>16.03.2020.</h5><p><b> </b><br/><br/>Dragi naši studenti,<br/>"
    "nastava je obustavljena.</p></div>",
) == [
    ("14.10.2019.", "2019-10-14", "Skup ICES 2019", "Naši studenti, učestvovali su.", []),
    ("16.03.2020.", "2020-03-16", "Nastava je obustavljena.", "Dragi naši studenti, nastava je obustavljena.", []),
]
assert _sum(
    "https://fluidi.mas.bg.ac.rs/omf/",
    "<h2> Обавештење о промени учионице </h2><div><span>08.10.2026.</span>"
    "</div><p>Настава је у учионици <strong>320</strong>.<br/></p><h2> Обавештење </h2><div><span>06.10.2026.</span>"
    "</div><p><br/></p>",
) == [("08.10.2026.", "2026-10-08", "Обавештење о промени учионице", "Настава је у учионици 320 .", [])]
assert _sum(
    "https://ciah.mas.bg.ac.rs/obavestenja",
    "<main><h2>Обавештења</h2><p>\n<b>25.7.2022.</b><br/><br/>Обука.</p>"
    '<p>Пријава <a href="https://ciah/p.doc">ОВДЕ</a> (<a href="https://ciah/multi.html">листа</a>)</p>\n*минимум 5.\n'
    "<p><b>01.4.2022.</b><br/><br/>Друга.</p></main>",
) == [
    ("25.7.2022.", "2022-07-25", "Обука.", "Пријава ОВДЕ ( листа ) *минимум 5.", [["https://ciah/p.doc", "ОВДЕ"]]),
    ("01.4.2022.", "2022-04-01", "Друга.", "Друга.", []),
]
assert _sum(
    "https://hidro.mas.bg.ac.rs/obavestenja.html",
    "<p><b>ОБАВЕШТЕЊА</b></p><p>Екскурзија одлаже се за 2027. год. (<i>01.09.2026.</i>)</p>",
) == [("01.09.2026.", "2026-09-01", "Екскурзија одлаже се за 2027. год.", "Екскурзија одлаже се за 2027. год.", [])]
assert _sum(
    "https://bmi.mas.bg.ac.rs/vesti/",
    '<article><div><p><time>25. 9. 2024.</time></p><h2><a href="https://bmi/v/qi/">'
    "Promocija knjige</a></h2><p>Pozivamo vas.</p></div></article>",
) == [("25. 9. 2024.", "2024-09-25", "Promocija knjige", "Pozivamo vas. Pročitaj vest", [])]
assert _sum(
    "https://meh.mas.bg.ac.rs/vesti/",
    "<div><h5>ТУ – <span>резултати</span></h5><p>Колоквијум одржан 11.06.2026. "
    '<a href="https://meh/wp-content/uploads/2026/06/K3.pdf">овде</a>.</p><hr/><h5>Download</h5><p>Нов материјал '
    '<a href="https://meh/wp-content/uploads/2025/03/a.pdf">a</a>.</p><hr/><h5>Обавештење</h5><p>Сајт ради.</p><hr/>'
    "<h5>Катедра за механизацију - Обавештење - датум објаве 31.03.2019.</h5><p>Од 2.4.2019.</p></div>",
) == [
    ("ТУ – резултати", "2026-06-11", "ТУ – резултати", "Колоквијум одржан 11.06.2026. овде .", []),
    ("Download", "2025-03-01", "Download", "Нов материјал a .", []),
    ("Обавештење", "2019-03-31", "Обавештење", "Сајт ради.", []),
    ("Катедра за механизацију - Обавештење - датум објаве 31.03.2019.", "2019-03-31", "Обавештење", "Од 2.4.2019.", []),
]
assert _sum(
    "https://pt.mas.bg.ac.rs/api.php?tip=vesti",
    '[{"naslov": "Procesing", "datum": "02.03.2027.", "tekst": "<p>Kongres.</p>", '
    '"link_url": "https://procesing.rs", "att_url": "https://pt/a.pdf", "att_name": "Program"}]',
) == [("02.03.2027.", "2027-03-02", "Procesing", "Kongres. https://procesing.rs", [["https://pt/a.pdf", "Program"]])]
assert notices_of("https://pt.mas.bg.ac.rs/api.php?tip=poslovi", "[]") == [] and notices_of("https://meh.x/", "") == []
