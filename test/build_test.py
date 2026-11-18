# /// script
# requires-python = ">=3.11"
# dependencies = ["jinja2==3.1.6", "nh3==0.3.2", "beautifulsoup4==4.15.0", "pillow==12.1.1"]
# ///
"""The asserts of pages/build.py (were its __main__ block), no network: uv run test/build_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pages"))
sys.path.insert(0, str(ROOT / "scrapers"))
import json  # noqa: E402
import re  # noqa: E402
import sqlite3  # noqa: E402
from collections import Counter  # noqa: E402
from mail import asset_name, thumb_asset  # noqa: E402
from markupsafe import Markup  # noqa: E402
from pathlib import Path  # noqa: E402
from sitegen.clean import CENT_CLASSES  # noqa: E402
from sitegen.clean import attachments  # noqa: E402
from sitegen.clean import book_page  # noqa: E402
from sitegen.clean import cent_changes  # noqa: E402
from sitegen.clean import cent_tidy  # noqa: E402
from sitegen.clean import clean_html  # noqa: E402
from sitegen.clean import downloads  # noqa: E402
from sitegen.clean import vesti_tidy  # noqa: E402
from sitegen.clean import drop_empty_tables  # noqa: E402
from sitegen.clean import file_rows  # noqa: E402
from sitegen.clean import linkify  # noqa: E402
from sitegen.clean import preuzeto  # noqa: E402
from sitegen.feeds import atom  # noqa: E402
from sitegen.links import mark_elsewhere  # noqa: E402
from sitegen.links import service  # noqa: E402
from sitegen.load_board import hosted_files  # noqa: E402
from sitegen.load_board import row_katedra  # noqa: E402
from sitegen.load_board import subject_name  # noqa: E402
from sitegen.load_sources import load_katedre  # noqa: E402
from sitegen.load_sources import load_mail  # noqa: E402
from sitegen.load_teachers import bibliography  # noqa: E402
from sitegen.load_teachers import department_intro  # noqa: E402
from sitegen.output import HEAD_END  # noqa: E402
from sitegen.output import MAIN  # noqa: E402
from sitegen.output import asset_v  # noqa: E402
from sitegen.output import breadcrumbs  # noqa: E402
from sitegen.output import env  # noqa: E402
from sitegen.output import katedra_href  # noqa: E402
from sitegen.output import katedra_pages  # noqa: E402
from sitegen.output import snav_href  # noqa: E402
from sitegen.output import split_page  # noqa: E402
from sitegen.output import versioned  # noqa: E402
from sitegen.output import write_assets_config  # noqa: E402
from sitegen.render import load_verzije  # noqa: E402
from sitegen.render import picker  # noqa: E402
from sitegen.schedule import first_link  # noqa: E402
from sitegen.schedule import parse_lectures  # noqa: E402
from sitegen.stats import bars  # noqa: E402
from sitegen.stats import post_words  # noqa: E402
from sitegen.stats import ranking  # noqa: E402
from sitegen.stats import same_words  # noqa: E402
from sitegen.stats import saved_cloud  # noqa: E402
from sitegen.stil import css_colors  # noqa: E402
from sitegen.text import BASE  # noqa: E402
from sitegen.text import PROGRAMS  # noqa: E402
from sitegen.text import SITE_URL  # noqa: E402
from sitegen.text import acronyms  # noqa: E402
from sitegen.text import desc  # noqa: E402
from sitegen.text import katedra  # noqa: E402
from sitegen.text import plural  # noqa: E402
from sitegen.text import set_hrefs  # noqa: E402
from sitegen.text import short_smer  # noqa: E402
from sitegen.text import slot_label  # noqa: E402
from sitegen.text import slug  # noqa: E402
from sitegen.text import smer_label  # noqa: E402
from sitegen.wiki import wiki_link  # noqa: E402
from sitegen.wiki import wiki_title  # noqa: E402
from translit import fold  # noqa: E402
from translit import lat  # noqa: E402

assert fold("Ђачки распоред, Čas") == "djacki raspored, cas"
assert wiki_title("УПИС 2026/2027.") == "Упис 2026/2027." and wiki_title("cenovnik") == "Cenovnik" and wiki_title("ОАС Упис") == "ОАС Упис"
hrefs = {"upis/oas": "/mf/upis/oas/", "biblioteka/start": "/mf/biblioteka/start/"}
assert (
    wiki_link("/upis/oas#rok", hrefs) == "/mf/upis/oas/#rok"
    and wiki_link("https://www.mas.bg.ac.rs/biblioteka", hrefs) == "/mf/biblioteka/start/"
)
assert wiki_link("/doku.php?id=upis:oas", hrefs) == "/mf/upis/oas/" and wiki_link("https://ie.mas.bg.ac.rs/upis/oas", hrefs) is None
assert wiki_link("/_media/upis/oas.pdf", hrefs) is None
assert acronyms("Основи отпорности конструкција") == {"ook"} and acronyms("Машински елементи 1") == {"me1", "me"}
assert acronyms("Математика 1", ["МАТ1 рок", "МИ - вежбе"]) == {"m1", "mat1"} and acronyms("Електротехника") == set()
assert acronyms("Понашање заварених спојева у експлоатацији") == {"pzsue", "pzse"}
assert acronyms("Биомедицинска инструментација и опрема", ["BMIO - испит", "ДОМАЋИ 2", "ОМ ПРВИ ДЕО", "ММ1 рок"]) == {
    "biio",
    "bio",
    "bmio",
}
assert css_colors(
    ":root {\n  --a: #fff;\n  --m: light-dark(color-mix(in srgb, #b 16%, transparent), #c);\n  --r: 6px;\n  --a: #000; }"
) == [("--a", "#fff", "#fff"), ("--m", "color-mix(in srgb, #b 16%, transparent)", "#c")]
asset_v["site.js"] = "ab"
assert versioned('<script src="/static/site.js"> `/static/site.js#${k}` /static/site.js?v=ab /static/sw.js /static/site.json') == (
    '<script src="/static/site.js?v=ab"> `/static/site.js?v=ab#${k}` /static/site.js?v=ab /static/sw.js /static/site.json'
)
asset_v.clear()
assert snav_href("/nastavnik/x/", ["/", "/nastavnici/", "/vesti/"]) == "/nastavnici/"
assert snav_href("/", ["/", "/vesti/"]) == "/" and snav_href("/tema/1/", ["/", "/vesti/"]) is None
assert slug(" Душан Љ. Ђукић ") == "dusan-lj-djukic" and slug(short_smer("основне академске студије - МИ")) == "oas-mi"
_r = [dict(id=1, n="Мата 1"), dict(id=7, n="Mata 1"), dict(id=9, n="Друго")]
set_hrefs(_r, lambda r: f"/p/{slug(r['n'])}/")
assert [r["href"] for r in _r] == ["/p/mata-1/", "/p/mata-1-7/", "/p/drugo/"]
assert subject_name("﻿Цевни  водови (1044) ") == "Цевни водови"
assert [
    plural(n, "thread") for n in (1, 2, 5, 11, 12, 21, 22, 25, 111)
] == "thread threada threadova threadova threadova thread threada threadova threadova".split()
assert [plural(n, "post") for n in (1, 2, 5, 21, 22)] == "post posta postova post posta".split()
_v = load_verzije("note\n## 2. x\nLead **b**.\n- 2–3 [novo] **A** `B`\n  dalje\n### H\n- 1, 4 C <i>\n")[0]
assert (_v["span"], _v["n"], _v["lead"]) == ("0.1–0.4", 4, Markup("Lead <b>b</b>.")), _v
assert _v["parts"][0]["items"] == [dict(v="0.2–0.3", tag=("Novo", "new"), html=Markup("<b>A</b> <span data-notx>B</span> dalje"))]
assert _v["parts"][1]["head"] == "H" and _v["parts"][1]["items"][0]["html"] == Markup("C &lt;i&gt;"), _v
assert [
    katedra("Катедра за " + k)
    for k in (
        "термодинамику",
        "процесну технику",
        "теорију механизама и машина",
        "аутоматско управљање",
        "моторна возила",
        "моторе",
        "информационе технологије у машинству",
    )
] == [
    "термодинамика",
    "процесна техника",
    "теорија механизама и машина",
    "аутоматско управљање",
    "моторна возила",
    "мотори",
    "информационе технологије у машинству",
]
assert env.filters["dmy"]("2026-11-08 10:00") == "08.11.2026."
assert env.filters["katedra"]("Катедра за механику флуида") == "механика флуида" and env.filters["katedra"](None) == ""
assert short_smer("основне академске студије - ИТМ") == "ОАС - ИТМ" and short_smer("катедре") == "катедре"
assert (
    slot_label("Изборни предмет 5.4.5", "5.4") == "Изборни предмет 5.4"
    and slot_label("Изборни предмет 5.2", "5.2") == "Изборни предмет 5.2"
)
assert fold(short_smer(PROGRAMS[0].replace(" — ", " - "))) == fold("ОАС - МИ")
assert [
    service(u)
    for u in (
        "https://teams.microsoft.com/l/x",
        "https://docs.google.com/document/d/1",
        "https://docs.google.com/forms/d/1",
        "https://us02web.zoom.us/j/1",
        "http://ie.mas.bg.ac.rs/x",
        "https://nastava.mas.bg.ac.rs/x",
        "https://masbgacrs-my.sharepoint.com/x",
        "https://youtu.be/x",
        "https://mat.mas.bg.ac.rs/moodle/login/",
        "http://it0.mas.bg.ac.rs/",
    )
] == ["Teams", "Google Drive", None, None, "ie.mas.bg.ac.rs", None, "OneDrive", "YouTube", "Moodle", "Moodle"]
# A mark names who links it, most posts first; only teachers' usernames (for their own pages).
_s, _t = dict(name="ME"), dict(username="pl")
_p = lambda who, t, d: dict(kind="post", subj=_s, who=who, teacher=t, posted=d, html='<a href="https://classroom.google.com/c/1">c</a>')
mark_elsewhere([_p("Ana", None, "2021"), _p("Petar L", _t, "2023"), _p("Petar L", _t, "2026"), dict(kind="post", subj=None)])
_e = _s["elsewhere"]["Classroom"]
assert (_e["who"], _e["users"], _e["first"]["posted"], _e["last"]["posted"]) == (["Petar L", "Ana"], {"pl"}, "2021", "2026")


# One video is not a place, two are, as is a playlist; a meeting and a results sheet are not material.
def _marks(*urls):
    s = dict(name="S")
    mark_elsewhere([dict(kind="post", subj=s, who="A", teacher=None, posted="2025", html=f'<a href="{u}">v</a>') for u in urls])
    return list(s.get("elsewhere", {}))


assert _marks(
    "https://youtu.be/a",
    "https://drive.google.com/drive/folders/x",
    "https://teams.microsoft.com/l/meetup-join/19x",
    "https://docs.google.com/spreadsheets/d/e/x/pubhtml",
) == ["Google Drive"]
assert _marks("https://youtu.be/a", "https://youtu.be/b") == ["YouTube"] and _marks("https://youtu.be/a") == []
assert service("https://solfins.sharepoint.com/x") is None
_a = lambda v: re.search(r'href="([^"]*)"', clean_html(f'<a href="{v}">x</a>'))[1].replace("&amp;", "&")
assert _a("viewtopic.php?p=1&hilit=%D1%81#p1") == f"{BASE}viewtopic.php?p=1#p1"
assert _a("viewtopic.php?f=2&sid=0af3&t=9") == f"{BASE}viewtopic.php?f=2&t=9" and _a("viewtopic.php?sid=0af3") == f"{BASE}viewtopic.php"
assert env.filters["slug"]("Катедра за математику") == "katedra-za-matematiku" and env.filters["slug"](None) == ""
_t = lambda k: dict(katedra=k)
_post = lambda k: dict(posts=[dict(teacher=_t(k)), dict(teacher=None)])
assert row_katedra(dict(name="катедра за моторе", smer=dict(key="katedre")), []) == "катедра за моторе"
assert row_katedra(dict(smer=dict(key="x"), info=dict(katedra=None, holder_t=_t("Б"), teachers=[])), []) == "Б"
assert row_katedra(dict(smer=dict(key="moduli")), [_post("А"), _post("В"), _post("В")]) == "В"
assert row_katedra(dict(smer=dict(key="x")), []) is None
_m, _k = dict(name="основне академске студије - МИ"), dict(name="катедре")
assert smer_label(_m["name"]) == "Основне академске студије - Машинско инжењерство" and smer_label("катедре") == "Катедре"
_a, _b, _c, _e = (
    dict(id=i, name=n, href=f"/{i}/", count=1, smer=m) for i, n, m in ((1, "Б", _m), (2, "А", _m), (3, "В", _k), (4, "Г", _k))
)
_pl = dict(program=PROGRAMS[0], module=None, semester=3, i=0, slot=None)
_bk = lambda f, places, **kw: dict(dict(forum=f, places=places, gone=0, id="b", href="/b/", name="Б"), **kw)
_p = picker(
    {1: _a, 2: _b, 3: _c, 4: _e},
    [
        _bk(_a, [_pl, dict(_pl, i=1, slot="4.4", slot_name="Изборни предмет 4.4.5")]),
        _bk(_c, [dict(_pl, i=2, semester=4)]),
        _bk(None, [dict(_pl, i=3, semester=5)], id="b9", href="/b9/", name="Д"),
        _bk(None, [_pl], id="b8", gone=1),
    ],
    [
        dict(
            shown="Г",
            page_name="Г Г. Г",
            href="/g/",
            gone=1,
            courses=[dict(subj=_a)],
            thumb=None,
            title="доцент",
            katedra=None,
            span={"from": 1950, "to": 1980, "from_est": True},
            last_seen="1980",
            age=40,
        ),
        dict(
            shown="Н",
            page_name="Н Н. Н",
            href="/n/",
            gone=0,
            courses=[dict(subj=_b), dict(subj=None)],
            thumb="/foto/n.jpg",
            title="доцент",
            katedra="Катедра за математику",
        ),
        dict(shown="Ж", page_name="Ж Ж. Ж", href="/z/", gone=1, courses=[], thumb=None, title=None, katedra=None, span={"to": 1990}, last_seen="0000", age=0),
    ],
    [dict(subj=_b, teacher=dict(href="/n/"))] * 2
    + [dict(subj=_a, teacher=dict(href="/g/")), dict(subj=_b, teacher=None), dict(subj=None, teacher=dict(href="/n/"))],
)
assert _p["posters"] == [[[1, 1]], [[0, 2]], [], [], []], _p["posters"]
_g = lambda n, s: dict(n=n, c=[], s=s)
assert _p["tree"] == [
    dict(
        n=PROGRAMS[0],
        s=[],
        c=[
            dict(n="2. godina", s=[], c=[_g("", [0, 2]), _g("Изборни предмет 4.4", [0])]),
            dict(n="3. godina", s=[], c=[_g("", [4])]),
            dict(n="Stari predmeti", s=[], c=[_g("", [1])]),
        ],
    ),
    dict(n="Катедре", s=[], c=[_g("", [3])]),
], _p["tree"]
# The teachers and the cards (people) by the full name (load_teachers page_name): site.js finds a teacher's card by it
# ("Predaju"); the picker's search by name still finds the shown one in it.
assert _p["teachers"] == [["Н Н. Н", [1]]] and _p["people"] == [
    ["Н Н. Н", "/n/", "/foto/n.jpg", "доцент · математика"],
    ["Г Г. Г", "/g/", None, "доцент · ~1950–1980", 40],
    ["Ж Ж. Ж", "/z/", None, "do 1990", None],
], _p["people"]
assert _p["katedre"] == [["Катедра за математику", "Математика", "katedra-za-matematiku", 1, katedra_href("Катедра за математику")]], _p[
    "katedre"
]
katedra_pages.add("Катедра за математику")
assert katedra_href("Катедра за математику") == "/katedra/matematika/", katedra_href("Катедра за математику")
katedra_pages.clear()
assert katedra_href("Катедра за моторе") == "/nastavnici/arhiva/?katedra=katedra-za-motore"
_d = (
    '<h1 id="k">Катедра за x</h1><div class="level1"><div class="wrap_related wrap_right plugin_wrap"><p>'
    '<a href="http://x.mas.bg.ac.rs/" class="urlextern"> веб сајт</a></p></div><p>Текст.</p></div>'
    '<div class="plugin_include_content x"><h2>Наставници</h2></div>'
)
assert department_intro(_d) == ("<div><p>Текст.</p></div>", "http://x.mas.bg.ac.rs/"), department_intro(_d)
_b = bibliography(
    '<div id="nastavnici-bibliografija"><h3>Радови у часописима ван SCI и SCIe листа</h3><div><p>\n'
    'Marić Ana, Lazović Tatjana M. (2014). <a href="https://m/h/1"> Wear</a>, Tribology, 3(2).<br/>\n'
    'ISSN: 1, <a href="https://dx.doi.org/10.1/x">10.1/x</a>, M24.\n</p></div></div>',
    [dict(title="Wear", year=2014, url="https://m/h/1"), dict(title="Old", year=1999, url="https://m/h/2")],
    "Татјана М. Лазовић-Капор",
)
assert _b == [
    dict(
        kind="časopis",
        authors=[("Marić Ana", False), ("Lazović Tatjana M.", True)],
        year=2014,
        title="Wear",
        url="https://m/h/1",
        venue="Tribology, 3(2)",
        doi="10.1/x",
        m="M24",
    ),
    dict(kind=None, authors=[], year=1999, title="Old", url="https://m/h/2", venue="", doi=None, m=None),
], _b
# An ie notice is a post of the subject its page's h1 names, punctuation aside; its written links are links, its
# files a post's; the page's "Literatura" is the subject's material; a page no subject has is left out.
assert file_rows([("javascript:alert(1)", "x.pdf", None)]) == "" and "https://a/b.pdf" in file_rows([("https://a/b.pdf", "b", None)])
assert linkify('Link: https://1drv.ms/x?e=V&amp;a=1. <a href="https://a/b">https://a/b</a>') == (
    'Link: <a href="https://1drv.ms/x?e=V&amp;a=1" rel="noopener noreferrer">https://1drv.ms/x?e=V&amp;a=1</a>. '
    '<a href="https://a/b">https://a/b</a>'
)
_db = sqlite3.connect(":memory:")
_db.row_factory = sqlite3.Row
_db.execute("CREATE TABLE katedre_pages (url, sha, site, title, html, first_seen, last_seen, gone)")
_db.execute("CREATE TABLE katedre_notices (nid, key, site, url, title, label, date, html, files, first_seen, last_seen, gone)")
_u = "https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=19"
_db.executemany(
    "INSERT INTO katedre_pages VALUES (?, 'ab', 'ie', 'IE', ?, '2026-11-11T05:00:00+00:00', '2026-11-11T05:00:00+00:00', 0)",
    [
        (
            _u,
            "<h1>Projektovanje sistema čovek-mašina</h1><section><h1>LITERATURA</h1><div><div>"
            '<a href="https://ie.mas.bg.ac.rs/data_store/upload/90_pz_1.pdf">90_pz_1.pdf</a><div>Predavanje 1</div></div></div></section>',
        ),
        ("https://ie.mas.bg.ac.rs/predmeti_p.php?SchoolSubjectID=38", "<h1>Engineering Management and Economics</h1>"),
    ],
)
_db.execute(
    "INSERT INTO katedre_notices VALUES (7, 'k', 'ie', ?, 'Kolokvijum', '05.11.2026', '2026-11-05', "
    "'Rezultati: https://1drv.ms/x', '[[\"https://ie.mas.bg.ac.rs/data_store/upload/1815_R_2.docx\", \"1815_R_2.docx\"]]', "
    "'2026-11-11T05:42:23+00:00', '2026-11-11T05:42:23+00:00', 0)",
    (_u,),
)
_sm = dict(key="mas-mi", short="МАС - МИ", href="/smer/mas-mi/")
_subj = {1: dict(id=1, name="Пројектовање система човек - машина", smer=_sm, codes=["0520"])}
import contextlib, io

with contextlib.redirect_stderr(io.StringIO()):
    _k = load_katedre(_db, {1: _sm}, _subj)
assert [(i["id"], i["subj"]["id"], i["date"], i["posted"], i["site"]["mark"]) for i in _k] == [
    ("k7", 1, "2026-11-05", "2026-11-05T10:00:00+00:00", "ie")
], _k
assert '<a href="https://1drv.ms/x"' in _k[0]["html"] and 'att__t--doc">DOCX</span><span class="att__n">R_2.docx</span>' in _k[0]["html"]
assert _subj[1]["site"] == _u and _subj[1]["lit"]["n"] == 1 and "Predavanje 1<small>pz_1.pdf</small>" in _subj[1]["lit"]["html"]
# A department's notice is its forum's (made when the board has none), or the subject its title names.
_db.execute(
    "INSERT INTO katedre_pages VALUES ('https://meh.mas.bg.ac.rs/vesti/', 'ab', 'meh', 'Вести', '', "
    "'2026-11-11T05:00:00+00:00', '2026-11-11T05:00:00+00:00', 0)"
)
_db.executemany(
    "INSERT INTO katedre_notices VALUES (?, ?, 'meh', 'https://meh.mas.bg.ac.rs/vesti/', ?, ?, '2026-06-11', "
    "'<p>a</p>', '[]', '2026-11-11T05:42:23+00:00', '2026-11-11T05:42:23+00:00', 0)",
    [(8, "k8", "Транспортни уређаји – резултати", "x"), (9, "k9", "Обавештење", "y")],
)
_kat = dict(id=2, key="katedre", href="/smer/katedre/", short="катедре")
_subj = {1: dict(id=1, name="Транспортни уређаји", smer=_sm, codes=[])}
with contextlib.redirect_stderr(io.StringIO()):
    _k = load_katedre(_db, {1: _sm, 2: _kat}, _subj)
assert [(i["id"], i["subj"]["id"]) for i in _k] == [("k8", 1), ("k9", "k:meh")], _k
assert _subj[(2, "катедра за механизацију")]["href"] == "/predmet/katedre/katedra-za-mehanizaciju/"
# A mail's "Re:" is in the topic of the oldest mail it answers that is here; one answering a mail not here, or with
# a new subject line, starts its own.
import tempfile

with tempfile.TemporaryDirectory() as _t:
    for _d, _id, _refs, _at, _ti in [
        ("2026-01-01-aaaaaaaa", "<a>", [], "09:00", "T"),
        ("2026-01-02-bbbbbbbb", "<b>", ["<x>", "<a>"], "09:00", "Re: T"),
        ("2026-01-03-cccccccc", "<c>", ["<a>", "<b>"], "08:00", "RE: T"),
        ("2026-01-04-dddddddd", "<d>", ["<x>"], "09:00", "Re: X"),
        ("2026-01-05-eeeeeeee", "<e>", ["<a>"], "09:00", "Novo"),
    ]:
        (Path(_t) / _d).mkdir()
        # No file on disk: the build has only post.json (the files are in the release).
        (Path(_t) / _d / "post.json").write_text(
            json.dumps(
                dict(
                    id=_id,
                    refs=_refs,
                    page="/1/",
                    author="llecic",
                    posted=f"{_d[:10]}T{_at}:00+00:00",
                    when="",
                    title=_ti,
                    html='<div style="x">Hi <script>x</script></div>',
                    files=["r.pdf"] if _id == "<a>" else [],
                    sizes={"r.pdf": 2048} if _id == "<a>" else {},
                )
            ),
            encoding="utf-8",
        )
    (Path(_t) / "teams-x").mkdir()
    (Path(_t) / "teams-x" / "material.json").write_text(
        json.dumps(dict(page="/1/", name="T 2025/2026. godina", files=["Predavanja/P 1.pdf", "a.docx"])), encoding="utf-8"
    )
    (Path(_t) / "moodle-x").mkdir()
    (Path(_t) / "moodle-x" / "material.json").write_text(
        json.dumps(dict(page="/2/", name="M 2024/2025", source="moodle", files=["2. nedelja/c.pdf"])), encoding="utf-8"
    )
    _ms, _ms2 = dict(id=1, name="S", smer=_sm, href="/1/"), dict(id=2, name="S2", smer=_sm, href="/2/")
    _m = load_mail({1: _ms, 2: _ms2}, Path(_t))
assert _ms2["lit"]["mark"] == "moodle" and _ms2["lit"]["title"] == "Materijal sa Moodle-a" and "2024/2025 · 2. nedelja" in _ms2["lit"]["html"], _ms2["lit"]
assert _ms["lit"]["mark"] == "teams" and _ms["lit"]["title"] == "Materijal sa Teams-a"
assert _ms["lit"]["n"] == 2 and f'href="/files/mail/{asset_name("teams-x/Predavanja/P 1.pdf")}/P%201.pdf"' in _ms["lit"]["html"], _ms["lit"]
assert "P 1.pdf<small>2025/2026 · Predavanja</small>" in _ms["lit"]["html"] and "a.docx<small>2025/2026</small>" in _ms["lit"]["html"]
assert [(i["id"], i["topic"]) for i in _m] == [
    ("maaaaaaaa", "maaaaaaaa"),
    ("mbbbbbbbb", "maaaaaaaa"),
    ("mcccccccc", "maaaaaaaa"),
    ("mdddddddd", "mdddddddd"),
    ("meeeeeeee", "meeeeeeee"),
], _m
assert _m[0]["num"] < _m[1]["num"] < _m[2]["num"] and "script" not in _m[0]["html"] and "style=" not in _m[0]["html"]
assert (
    f'href="/files/mail/{asset_name("2026-01-01-aaaaaaaa/r.pdf")}/r.pdf"' in _m[0]["html"] and "<small>2.0 KiB</small>" in _m[0]["html"]
), _m[0]["html"]
assert _p["subjects"][0] == ["/1/", "Б"] and _p["subjects"][4:] == [["/b9/", "Д", 0]], _p["subjects"]
assert first_link('<h1>K</h1><a href="/f/k.pdf?a=1&amp;b=2">Календар  2026</a>') == ("Календар 2026", "/f/k.pdf?a=1&b=2")
_pr = (
    "<h2>Raspored 2026</h2><h3>Jesenji semestar</h3><h4>OSNOVNE AKADEMSKE STUDIJE - <b>MAŠINSKO</b> INŽENjERSTVO</h4>"
    '<p>I god. <a href="/f/1.pdf">raspored</a> za obavezne<br/>II god. <a href="/f/2.pdf"> raspored</a></p>'
    '<p>Izborni predmeti: <a href="/f/54.pdf">5.4</a>, <a href="/f/55.pdf">5.5</a><br/>Računarska sala: <a href="/f/3.pdf">324</a></p>'
    '<h4>MASTER AKADEMSKE STUDIJE - INDUSTRIJA 4.0</h4><p>Obavezni (po modulima):<br/><a href="/f/b.pdf">BMI - Biomedicina</a><br/>'
    '<a href="/f/i.pdf">OAS - Informacione - 3. godina</a></p><h4>DOKTORSKE</h4><p>Biće objavljen!</p>'
)
_l = parse_lectures(_pr)
assert (_l["title"], _l["semester"], [p["key"] for p in _l["programs"]]) == (
    "Raspored 2026",
    "Jesenji semestar",
    ["osnovne-akademske-studije-masinsko-inzenjerstvo", "master-akademske-studije-industrija-4-0", "doktorske"],
)
assert _l["programs"][0] == dict(
    key=_l["programs"][0]["key"],
    level="Osnovne akademske studije",
    name="Mašinsko inženjerstvo",
    cards=[("1", "1. godina", "/f/1.pdf"), ("2", "2. godina", "/f/2.pdf")],
    electives=[("5.4", "/f/54.pdf"), ("5.5", "/f/55.pdf")],
    rooms=[("324", "/f/3.pdf")],
    notes=[],
    short="OAS",
), _l["programs"][0]
assert [p["short"] for p in parse_lectures(_pr.replace("DOKTORSKE", "MASTER AKADEMSKE STUDIJE - MAŠINSKO INŽENjERSTVO"))["programs"]] == [
    "OAS",
    "MAS - IND4.0",
    "MAS - MI",
]
assert _l["programs"][1]["cards"] == [("BMI", "Biomedicina", "/f/b.pdf"), ("3", "3. godina", "/f/i.pdf")]
assert _l["programs"][2]["notes"] == ["Biće objavljen!"] and parse_lectures("<p>x</p>") is None
_at_html = clean_html(
    '<dl class="attachbox"><dt>Attachments</dt><dd><dl class="file"><dt><span class="imageset"></span> '
    '<a class="postlink" href="./download/file.php?id=7">Rok &amp; B.PDF</a></dt><dd>(58.7 KiB) Downloaded 4 times'
    "</dd></dl></dd></dl>"
)
_at = attachments(_at_html)
assert (
    '<a class="att" href="https://nastava.mas.bg.ac.rs/nastava/download/file.php?id=7" rel="noopener noreferrer">'
    '<span class="att__t att__t--pdf">PDF</span><span class="att__n">Rok &amp; B.PDF<small>58.7 KiB · preuzeto 4 puta</small>'
    "</span></a>"
) in _at and "<dt>Prilozi</dt>" in _at, _at
assert attachments(None) is None and attachments("<p>x</p>") == "<p>x</p>"
# A file the site keeps (documents.py host): the release's link and its thumbnail; another attachment is unchanged.
_ah = attachments(_at_html, {7: ("/files/files-2026-2027/ab.pdf/Rok%20%26%20B.PDF", "/files/files-2026-2027/cd.jpg/thumb.jpg")})
assert (
    '<a class="att" href="/files/files-2026-2027/ab.pdf/Rok%20%26%20B.PDF" rel="noopener noreferrer"><img class="att__img" '
    'src="/files/files-2026-2027/cd.jpg/thumb.jpg" alt="" loading="lazy" decoding="async"><span class="att__t'
) in _ah, _ah
assert attachments(_at_html, {8: ("/x", None)}) == _at
_hf = hosted_files({7: dict(id=7, release="files-2026-2027", thumb=1, path="7/a b.pdf", filename="a/b.pdf"), 8: dict(id=8, path="8/c")})
assert list(_hf) == [7] and _hf[7] == (f"/files/files-2026-2027/{asset_name('7/a b.pdf')}/a%2Fb.pdf", f"/files/files-2026-2027/{thumb_asset('7/a b.pdf')}/thumb.jpg"), _hf
assert thumb_asset("7/a.jpg") != asset_name("7/a.jpg") and thumb_asset("7/a.jpg").endswith(".jpg")
assert 'src="/t.jpg"' in file_rows([("/files/mail/a.pdf/a.pdf", "a.pdf", None, "/t.jpg")]) and "<img" not in file_rows([("/files/mail/a.pdf/a.pdf", "a.pdf", None)])
_dl = clean_html(
    '<dl class="file"><dt><a class="postlink" href="./download/file.php?id=11&amp;sid=b0c">R&amp;T.zip</a></dt>'
    "<dd><em>овде</em></dd> <dd>(45.16 KiB) Downloaded 642 times</dd></dl>"
    '<dl class="file"><dt><a href="./download/file.php?id=12">b.pdf</a></dt><dd>(1 KiB) Downloaded 1 time</dd></dl>'
)
assert downloads(_dl) == [(11, "R&T.zip", 642), (12, "b.pdf", 1)] and downloads(None) == [], downloads(_dl)
assert bars([(2014, 5), (2015, 10)], str) == [
    dict(label=2014, n=5, pct=50.0, href="2014"),
    dict(label=2015, n=10, pct=100.0, href="2015"),
]
assert ranking(Counter(a=4, b=1, c=2), lambda k: (k.upper(), None, None), k=2) == [
    dict(label="A", href=None, note=None, n=4, pct=100.0),
    dict(label="C", href=None, note=None, n=2, pct=50.0),
]
assert env.filters["n"](23692) == "23.692" and plural(642, "preuzimanje") == "preuzimanja"
_at = attachments(
    '<dl>\n<dt><span></span> <a href="/f?id=1" rel="x">a.docx</a></dt>\n<dd><em>Ocene</em></dd> <dd>(1 KiB) preuzeto 2 puta</dd>\n</dl>'
)
assert _at == (
    '<a class="att" href="/f?id=1" rel="noopener noreferrer"><span class="att__t att__t--doc">DOCX</span><span class="att__n">'
    'a.docx<span class="att__c"><em>Ocene</em></span><small>1 KiB · preuzeto 2 puta</small></span></a>'
), _at
_ct = clean_html(
    cent_tidy(
        '<div class="et_pb_row responsive-buttons"><div class="et_pb_column et_clickable"><a href="https://c/s1.pdf"><div class="x">'
        '<p>Смена 1</p></div></a></div><div class="et_pb_column et_clickable"><p>Смена 2</p></div></div>'
        '<div class="et_pb_row"><div id="at-col-arrow"><img src="https://c/a.webp"></div><div id="at-col-head"><p>ПЛ-1</p></div>'
        '<div id="at-col"><p>Лаб 1</p></div><div id="at-col-attach"><a href="https://c/u/lab1.pdf">lab1.pdf</a></div>'
        '<div id="at-col"></div><div id="at-col-nedelja">I недеља</div></div>'
        '<div class="et_pb_toggle et_pb_toggle_open"><h4 class="et_pb_toggle_title"><span class="accordion_mark">ПЛ-3</span>'
        '<p class="accordion_title">Лаб 3</p><a href="https://c/u/lab3.PDF">lab3.PDF</a><span class="accordion-nedelja"></span></h4>'
        '<div class="et_pb_toggle_content"><ul><li>Упутство <a href="https://drive.google.com/x">video</a></li></ul></div></div>'
        '<div class="et_pb_text et_pb_text_align_center"><p>c</p></div>'
    ),
    "https://c/",
    classes=CENT_CLASSES,
)
assert _ct == (
    '<div class="cent-btns"><a class="cent-btn" href="https://c/s1.pdf" rel="noopener noreferrer">Смена 1</a>'
    '<span class="cent-btn" title="bez linka na sajtu katedre">Смена 2</span></div>'
    '<div class="cent-head"><b class="cent-code">ПЛ-1</b><span class="cent-t">Лаб 1</span><a class="cent-file" '
    'href="https://c/u/lab1.pdf" rel="noopener noreferrer"><span class="att__t att__t--pdf">PDF</span>lab1.pdf</a>'
    '<span class="cent-wk">I недеља</span></div>'
    '<details class="cent-acc"><summary class="cent-head"><b class="cent-code">ПЛ-3</b><span class="cent-t">Лаб 3</span>'
    '<a class="cent-file" href="https://c/u/lab3.PDF" rel="noopener noreferrer"><span class="att__t att__t--pdf">PDF</span>'
    'lab3.PDF</a></summary><div><ul><li>Упутство <a class="cent-file" href="https://drive.google.com/x" '
    'rel="noopener noreferrer"><span class="att__t att__t--video">▶</span>video</a></li></ul></div></details>'
    '<div class="cent-c"><p>c</p></div>'
), _ct
# A toggle without a title: its content in place, no empty fold.
_ct = cent_tidy('<div class="et_pb_toggle"><h4 class="et_pb_toggle_title"></h4><div class="et_pb_toggle_content"><p>x</p></div></div>')
assert "<details" not in _ct and "<p>x</p>" in _ct, _ct
# A news post's WordPress pieces (vesti_tidy, then clean_html as load_vesti): a YouTube or Facebook embed a link to the
# video, a captioned photo a figure keeping its alignment, a gallery's thumbnails opening the image, an upload's player.
_U = "https://vesti.mas.bg.ac.rs/wp-content/uploads/2022/05/"
_vt = clean_html(
    vesti_tidy(
        '<p><iframe src="https://www.youtube.com/embed/w8gGMK9VY_M?si=x"></iframe></p>'
        '<p><iframe src="https://www.facebook.com/plugins/video.php?height=314&amp;href=https%3A%2F%2Fwww.facebook.com%2Freel%2F19%2F&amp;t=0"></iframe></p>'
        f'<div id="attachment_1" style="width: 955px" class="wp-caption alignleft"><a href="{_U}a.jpg"><img class="wp-image-1" src="{_U}a.jpg"></a>'
        '<p class="wp-caption-text">Foto</p></div>'
        "<style>#gallery-1 {margin: auto}</style><div id='gallery-1' class='gallery gallery-columns-5'><dl class='gallery-item'><dt class='gallery-icon'>"
        f"<a href='https://vesti.mas.bg.ac.rs/?attachment_id=9'><img src=\"{_U}3-150x150.jpg\"></a></dt></dl></div>"
        f'<video class="wp-video-shortcode" controls="controls" preload="metadata"><source type="video/mp4" src="{_U}v.mp4?_=1"></video>'
    ),
    classes={"figure": {"alignleft"}, "div": {"gallery"}},
)
for _want in (
    '<a href="https://www.youtube.com/watch?v=w8gGMK9VY_M" rel="noopener noreferrer">Video na YouTube-u</a>',
    '<a href="https://www.facebook.com/reel/19/" rel="noopener noreferrer">Video na Facebooku</a>',
    f'<figure class="alignleft"><a href="{_U}a.jpg"',
    "<figcaption>Foto</figcaption>",
    f'<div class="gallery"><figure><a href="{_U}3.jpg"',
    f'<source src="{_U}v.mp4?_=1" type="video/mp4">',
):
    assert _want in _vt, (_want, _vt)
assert "<iframe" not in _vt and "margin" not in _vt and "attachment_id" not in _vt and "controls" in _vt, _vt
# A cent page's change against its older version: TMO's "Smena 5" button to a new PDF, a new text in a fold, a removed
# link; nothing changed, the page as it was.
_old = '<a class="cent-btn" href="/s5_v3.pdf">Smena 5</a><a href="/x.pdf">Raspored</a><details><p>a</p></details>'
_new = '<a class="cent-btn" href="/s5_v4.pdf">Smena 5</a><details><p>a</p><p>b</p></details>'
_html, _ch = cent_changes(_old, _new)
assert _ch == ["novi fajl – Smena 5", "uklonjeno – Raspored", "novi tekst"], _ch
_chip = '<a class="cent-file" href="/r.pdf"><span class="att__t att__t--pdf">PDF</span>r.pdf</a>'
assert cent_changes("", _chip)[1] == ["novo – r.pdf"]
assert '<a class="cent-btn cent-new" href="/s5_v4.pdf">' in _html and "<details open" in _html and '<p class="cent-new">b</p>' in _html, _html
assert "<p>a</p>" in _html and cent_changes(_new, _new) == (_new, [])
_s, _f = split_page(f"<html><title>T</title><meta>{HEAD_END}<x>{MAIN}a</main><p></main></html>")
assert (_s, _f) == (
    f"<html><title></title><x>{MAIN}<!--main--></main></html>",
    f'<html lang="sr"><title>T</title><meta>{HEAD_END}a</main><p></html>',
), (_s, _f)
assert desc(" a\n b ") == "a b" and desc("aaa bbb ccc", 9) == "aaa bbb…"
assert lat("Љиљана ЉУБА Ђорђе, Џ. Mašina 2") == "Ljiljana LJUBA Đorđe, Dž. Mašina 2" and lat(None) == ""
assert lat(Markup("Ш &amp; A")) == Markup("Š &amp; A")
_bc = breadcrumbs(
    '<nav class="crumbs"><a href="/"><svg></svg>Početna</a><svg></svg><a href="/smer/x/" title="A &amp; B">A &amp; B</a>'
    '<svg></svg><span class="crumbs__here" aria-current="page">Мата</span></nav>',
    f"{SITE_URL}/p/",
)
assert [(i["position"], i["name"], i["item"]) for i in json.loads(re.search(r">(.*)</script>", _bc)[1])["itemListElement"]] == [
    (1, "Početna", f"{SITE_URL}/"),
    (2, "A & B", f"{SITE_URL}/smer/x/"),
    (3, "Mata", f"{SITE_URL}/p/"),  # in Latin, as the <title>
], _bc
assert breadcrumbs("<p>no crumbs</p>", SITE_URL) == "" and type(_bc) is str
assert drop_empty_tables("<table><tr><th>Predmet</th></tr><tr><td> &nbsp;</td></tr></table><p>x</p>") == "<p>x</p>"
assert drop_empty_tables("<table><tr><td></td><td><b>2.11.</b></td></tr></table>").startswith("<table>")
assert (
    drop_empty_tables('<h2>A</h2><div><table><td>1</td></table></div><h2>B</h2>\n<div class="l"><table><th>x</th><td> </td></table></div>')
    == '<h2>A</h2><div><table><td>1</td></table></div>\n<div class="l"></div>'
)
assert preuzeto("(1 KiB) Downloaded 1 time, Downloaded 22 times") == "(1 KiB) preuzeto 1 puta, preuzeto 22 puta"
assert post_words(
    dict(
        title="Rezultati ispita",
        files=[(1, "OPK 3. predavanje.pdf", 9)],
        body="Видети http://x.rs/a, www.mas.bg.ac.rs, a@b.rs i Moodle_2015.pdf\nOPK 3. predavanje.pdf\n(4.29 MiB) preuzeto 1021 puta",
    )
) == ["rezultati", "ispita", "videti"]
_bp = book_page(
    '<h1>X</h1><h2 id="циљ">Циљ</h2>\n<div class="level2"><p>\n\nA &amp; b.\n\n</p></div>'
    "<h2>Фонд часова</h2><div><p>Укупан фонд часова: 30<br></p></div>"
    "<h4>Провера знања</h4><div><p>Тест: 0<br>\nЗавршни испит: 4<br></p></div>"
    "<h2>Провера знања (укупно 100 поена)</h2><div><p>Пројекат: 40<br>Рачунски задаци: 0<br>"
    "Услов за излазак на испит (потребан број поена): 30<br></p></div>"
    "<h2>Литература</h2><div><p>\n\nA, 1992.; B, 2010.\n</p></div>"
)
assert book_page("<h2>Ресурси</h2><div><p>Лекција 1: А\n2. Б</p></div>")["text"]["Ресурси"] == (["А", "Б"], True)
assert book_page("<h2>Ресурси</h2><div><p>- А\n2. Б</p></div>")["text"]["Ресурси"] == (["А", "2. Б"], False)
assert (_bp["text"]["Циљ"][0], _bp["hours"], _bp["points"], _bp["pass_min"], _bp["books"]) == (
    ["A & b."],
    dict(total=30, groups=[("Провера знања", [("Завршни испит", 4)])]),
    [("Пројекат", 40)],
    30,
    ["A, 1992.", "B, 2010."],
), _bp
assert same_words(
    Counter(ispit=2, ispita=5, ispitu=1, ispitni=1, studenti=3, studenata=2, smene=5, smena=1, smen=1, kandidata=1)
) == Counter(ispit=8, ispitni=1, studenti=5, smene=7, kandidata=1)
import xml.etree.ElementTree as ET

_it = dict(
    id="p5",
    num=5,
    title="A & <b>",
    posted="2026-11-08T14:39:57+00:00",
    who="Ђ",
    html="<p>x &amp; y</p>",
    body="",
    subj=dict(name="Мата 1"),
    smer=None,
    thread=dict(href="/tema/3/", posts=[1, 2]),
)
_x = ET.fromstring(atom("T", "/predmet/m/", [_it]))
_ns = {"a": "http://www.w3.org/2005/Atom"}
assert _x.find("a:entry/a:link", _ns).get("href") == f"{SITE_URL}/tema/3/#p5" and _x.find("a:entry/a:title", _ns).text == "A & <b>"
assert _x.find("a:entry/a:content", _ns).text == "<p>x &amp; y</p>" and ET.fromstring(atom("T", "/", [])).find("a:updated", _ns) is not None

# The word cloud meta keeps (build.py words): used while under 7 days old; none, too old or no meta table: None.
from datetime import date as _date  # noqa: E402

_wdb = sqlite3.connect(":memory:")
assert saved_cloud(_wdb, _date(2026, 11, 14)) is None
_wdb.execute("CREATE TABLE meta (key text primary key, value text)")
assert saved_cloud(_wdb, _date(2026, 11, 14)) is None
_wdb.executemany("INSERT INTO meta VALUES (?, ?)", [("words", '[["ispit", 3], ["usmeni", 1]]'), ("words_at", "2026-11-08")])
assert saved_cloud(_wdb, _date(2026, 11, 14)) == [("ispit", 3), ("usmeni", 1)]
assert saved_cloud(_wdb, _date(2026, 11, 15)) is None

# The departments' whole sites (load_sajtovi): a page's title, its group, the teacher it is about.
from sitegen.load_sajtovi import group_of, own_title, slug_title, teacher_of  # noqa: E402

assert own_title("Industrijsko Inženjerstvo - Predmeti") == "Predmeti"
assert own_title("Prof. Dr. Đuro Koruga — Katedra za biomedicinsko inženjerstvo") == "Prof. Dr. Đuro Koruga"
assert own_title("Катедра за ХМЕС") == ""
assert slug_title("https://hidro.mas.bg.ac.rs/centri_lab1.html") == "Centri lab1"
assert group_of("ciah", "https://ciah.mas.bg.ac.rs/stakla", "Испитивање") == "Laboratorija CIAH"
assert group_of("hidro", "https://hidro.mas.bg.ac.rs/istorijat.html", "Историјат") == "O katedri"
assert group_of("meh", "https://meh.mas.bg.ac.rs/projekti/", "Пројекти") == "Istraživanje i projekti"
_gajic = dict(id="1", name="Александар Гајић", katedra="Катедра за хидрауличне машине и енергетске системе", _tok={"aleksandar", "gajic"})
_rad = dict(id="2", name="др Зоран Ј. Радаковић", username="zradakovic")
_byk = {_gajic["katedra"]: [_gajic]}
assert teacher_of("hidro", "https://hidro.mas.bg.ac.rs/profesori_gajic.html", {}, _byk) is _gajic
assert teacher_of("hidro", "https://hidro.mas.bg.ac.rs/istorijat.html", {}, _byk) is None
assert teacher_of("etc", "https://etc.mas.bg.ac.rs/zradakovic/EM1.htm", {"zradakovic": _rad}, {}) is _rad
assert teacher_of("etc", "https://etc.mas.bg.ac.rs/", {"zradakovic": _rad}, {}) is None

# An upis tab's summary (wiki.summary): shown while the pages it was written from are unchanged, left out after.
from sitegen import wiki  # noqa: E402

_pages = {"upis/x": [{"sha": "aaaaaaaaaa11"}], "upis/x/datumi": [{"sha": "bbbbbbbbbb22"}]}
wiki.UPIS_SUMMARY["upis/x"] = dict(seen={"upis/x": "aaaaaaaaaa", "upis/x/datumi": "bbbbbbbbbb"}, rows=[("Rok", "1. 9.")])
assert wiki.summary("upis/x", ["upis/x", "upis/x/datumi"], _pages) == [("Rok", "1. 9.")]
_pages["upis/x/datumi"] = [{"sha": "cccccccccc33"}]
# The warning it gives is the test's, not the build's: kept off the run's output, but checked.
with contextlib.redirect_stderr(_err := io.StringIO()):
    assert wiki.summary("upis/x", ["upis/x", "upis/x/datumi"], _pages) is None
assert "mf/upis/x: changed since its summary was written" in _err.getvalue(), _err.getvalue()
assert wiki.summary("upis/y", ["upis/y"], {"upis/y": [{"sha": "d"}]}) is None
del wiki.UPIS_SUMMARY["upis/x"]

# An emeritus's years (render.faculty_span): an estimated retirement is not before their last post; an exact one stays.
from sitegen.render import faculty_span  # noqa: E402

_h = {"start": 1979, "retired": 2020, "retired_est": True, "years": "2008–2013"}
_em = dict(history=_h, first_seen="2026-11-08", emeritus=1, gone=1, last_seen="2026-11-11", posts=[{"date": "2025-07-08"}, {"date": None}])
assert faculty_span(_em, "2014") == {"from": 1979, "to": 2025, "from_est": False, "to_est": True}
assert faculty_span(dict(_em, posts=[]), "2014")["to"] == 2020
assert faculty_span(dict(_em, history=dict(_h, retired=2016, retired_est=False)), "2014")["to"] == 2016

# Teacher photos (load_teachers.fit_photo): a JPEG wider than 300 px scaled to 300, a narrower one or another kind
# served as stored; the small copy (the app's offline one) always a JPEG, at most 150 px wide.
from PIL import Image as _Image  # noqa: E402
from sitegen.load_teachers import fit_photo, small_path  # noqa: E402


def _photo(w, h, kind="JPEG", mode="RGB"):
    out = io.BytesIO()
    _Image.new(mode, (w, h), "gray").save(out, kind)
    return out.getvalue()


_big, _narrow, _png = _photo(900, 1050), _photo(130, 155), _photo(400, 500, "PNG", "RGBA")
assert _Image.open(io.BytesIO(fit_photo(_big))).size == (300, 350)
assert fit_photo(_narrow) is _narrow and fit_photo(_png) is _png
_small = _Image.open(io.BytesIO(fit_photo(_png, 150, always=True)))
assert (_small.format, _small.size, _small.mode) == ("JPEG", (150, 188), "RGB")
assert _Image.open(io.BytesIO(fit_photo(_narrow, 150, always=True))).size == (130, 155)
assert small_path("/foto/ab12.png") == "/foto/mala/ab12.jpg"

# The first frame's target (base.html rel=expect, block paint): the 20th row of a filtered list; none in a folded
# list, which shares its page with an unfolded one (smer.html).
_rows = env.get_template("rows.html").module
_places = [{"href": f"/p{i}/", "label": f"P{i}", "topics": 1, "count": 1, "last": None} for i in range(25)]
for _fold in (False, True):
    _html = str(_rows.forum_rows("T", _places, "book", filter=True, fold=_fold))
    assert _html.count('id="paint"') == (not _fold)
    assert _fold or _html.index('href="/p18/"') < _html.index('id="paint"') < _html.index('href="/p19/"')
_topics = [{"href": f"/t{i}/", "title": f"T{i}", "posts": [1], "first": {}, "last": {}} for i in range(25)]
assert str(_rows.topic_rows("T", _topics, filter=True)).count('id="paint"') == 1
assert 'id="paint"' not in str(_rows.topic_rows("T", _topics))

# The icons are inline in each page (base.html): a link to the sprite file would show nothing, and a name with no
# symbol shows a blank.
_sprite = (ROOT / "pages/static/icons.svg").read_text(encoding="utf-8")
assert '{% include "icons.svg" %}' in (ROOT / "pages/templates/base.html").read_text(encoding="utf-8")
for _f in [*(ROOT / "pages/templates").glob("*.html"), *(ROOT / "pages/static").glob("*.js")]:
    _text = _f.read_text(encoding="utf-8")
    assert "/static/icons.svg" not in _text, _f.name
    for _id in re.findall(r"#(i-[\w-]+)[\"']", _text):
        assert f'id="{_id}"' in _sprite, f"{_f.name}: no symbol {_id}"

# The Worker's static assets (wrangler.toml): the photos only. _headers is not let back in: wrangler reads it anyway,
# and an asset of it would be served.
with tempfile.TemporaryDirectory() as _d:
    write_assets_config(Path(_d))
    assert (Path(_d) / ".assetsignore").read_text(encoding="utf-8").split() == ["*", "!foto/", "!foto/**"]
    assert (Path(_d) / "_headers").read_text(encoding="utf-8").startswith("/foto/*\n")
