# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4==4.15.0", "pymupdf"]
# ///
"""The old faculty sites (mas.bg.ac.yu, to 2014) into the archive, from work/wayback/ (wayback_articles.py's items,
wayback_files.py's files).

uv run tools/stari_sajt.py vesti   data/stare-vesti.jsonl: each item, where it goes, its links made to work
uv run tools/stari_sajt.py fajlovi data/stari-fajlovi.jsonl: the other saved files, where each goes (RULES)
uv run tools/stari_sajt.py host    upload the files of both to the releases stari-<host> (gh, signed in)

An item of the faculty's news goes to /vesti/ (forum null); a department's, to its forum on the board (load_stare,
by the name in FORUM), or the subject its title names. In its text, a link to a file of the old sites is our copy when
wayback_files.py saved it (/files/stari-<host>/<asset>/<name>, the Worker serves the release), the name alone when
Wayback never had it; a link to a page of the old sites is that page's Wayback copy of the item's time.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from common import asset_name, release_assets, upload_assets  # noqa: E402
from translit import fold  # noqa: E402
from wayback_files import key_of  # noqa: E402

WB = ROOT / "work" / "wayback"
OUT = ROOT / "data" / "stare-vesti.jsonl"
FILES_OUT = ROOT / "data" / "stari-fajlovi.jsonl"
OLD = re.compile(r"(^|\.)mas\.bg\.ac\.(yu|rs)$")
PAGE = re.compile(r"(\.(html?|php\d?|aspx?|shtml|cgi)|/|^[^.]*)$", re.I)  # a path that is a page, not a file

# A department's news (the section wayback_articles.py gives it): its forum on the board.
FORUM = [
    (r"katedre/mehanika/", "катедра за механику"),
    (r"katedre/termomehanika/", "катедра за термомеханику"),
    (r"katedre/t-crtanje-mehanizmi/", "катедра за теорију механизама и машина"),
    (r"katedre/termoenergetika/", "катедра за термоенергетику"),
    (r"katedre/otpornost-konstr/", "катедра за отпорност конструкција"),
    (r"katedre/fizika-elek/", "катедра за физику и електротехнику"),
    (r"katedre/matematika/", "катедра за математику"),
    (r"katedre/opste-mas-konstr/|^omk$", "катедра за опште машинске конструкције"),
    (r"katedre/motorna vozila/", "катедра за моторна возила"),
    (r"katedre/ie/", "катедра за индустријско инжењерство"),
    (r"katedre/proizvodno/", "катедра за производно машинство"),
    (r"^(tribolab|motori)$", "катедра за моторе"),  # tribolab: the department's laboratory
    (r"^au$", "катедра за аутоматско управљање"),
]
UPIS = re.compile(r"^(www/upis|kolubara)")

# Where each saved file goes (fajlovi), the first rule that matches its key: "p:<subject>" a subject's page (load_stare
# finds it by name; "p:*" the subject the file is named after, "as05044056 cevovodi i armatura.pdf"), "a:<section>" the
# archive page, "v:<event>" a news post of its own (EVENTS), "-" left out. A file no rule matches is left out too, and
# listed. Old subjects go to their successor in today's MI program (agreed 2026-11-18, by their content).
PLANS, DOCS, NNV, REFORM, IZBORI, PAPERS = (
    "a:Nastavni planovi i programi", "a:Dokumenti fakulteta", "a:Zapisnici Nastavno-naučnog veća",
    "a:Reforma nastave", "a:Izbori u zvanja", "a:Radovi i saopštenja",
)
RULES = [
    # left out: timetables and calendars, the journal, the alumni's and CIAH's own files, programs, page leftovers
    (r"rasispit|raspnast|/raspored|raspored_|kalendar\d|kalendar/(?!kongresi)|/kursevi/", "-"),
    (r"transactions|/biblioteka/|^www/publikacije/(?!katalog)", "-"),
    (r"^(alumni/(?!kongres)|ciah/|nanoworld/|summer\.|vesti/wp-|nastava/nastava)", "-"),
    (r"\.(exe|swf|class|xml|php|mid|mov|avi|ps)$|/memo-mf|vizitka|/fphover|^www/lib/|^cent/inventor/|^meh/ostaleinfo/", "-"),
    # conferences and events: a news post each (EVENTS)
    (r"tqm iwc|iwc tqm 2005", "v:tqm2005"), (r"^cent/tqm2007/", "v:tqm2007"), (r"^cent/tqm2009/", "v:tqm2009"),
    (r"^cent/tqm/2015/", "v:tqm2015"), (r"^cent/jupiter/prvi", "v:jupiter32"), (r"^cent/jupiter/drugi", "v:jupiter33"),
    (r"^cent/jupiter/program", "v:jupiter35"), (r"^das2012/", "v:das2012"), (r"cirp-poziv", "v:cirp"),
    (r"^alumni/kongres/ii/", "v:alumni2"), (r"^alumni/kongres/saopstenja/alumni-", "v:alumni1"), (r"^meh/mhcl06/", "v:mhcl06"),
    (r"^ie/sie2009", "v:sie2009"),
    # loose announcements no saved news item links: a news post each
    (r"cocacola", "v:cocacola"), (r"formulasra2014", "v:formula2014"), (r"siemens_2012", "v:siemens2012"),
    (r"nagradjeni_studenti2009", "v:nagradjeni2009"), (r"mip_obavestenje", "v:mip"), (r"placena_praksa_vip", "v:vip2013"),
    (r"stipendije_vlade_francuske", "v:francuska2014"), (r"studentenpool|frgebogen", "v:gtz"), (r"tenderdksm", "v:dksm"),
    (r"sveti_sava", "v:svetisava2003"), (r"oglas_mf_bgd_09_2008", "v:upis2008"), (r"tekst_konkursa_poslat", "v:upis2005"),
    (r"euroavia", "v:euroavia"), (r"asme|newsletter", "v:asme"), (r"list-pi/", "v:listpi"),
    # one subject's description each (the 2005 program's 4th semester, the 1st year's electives)
    (r"^www/upis/4semestar/|^www/obrazovanje/upis/down/", "p:*"),
    # papers
    (r"^alumni/kongres/|^tribolab/|^simlab/magteze/|^cent/mpk/|kalendar/kongresi/", PAPERS),
    # the archive page
    (r"referat|/konkursi/|izbor.u.zvanje|refinz|karton", IZBORI),
    (r"nnv-(zapisnik|n?t?\d)", NNV),
    (r"reforma|bolonjsk", REFORM),
    (r"nplan|nprog|pdsstudije|pds nastava|nastavni plan|^mit/|3plus2|knjiga_predmeta|knjiga_doktorske|guidetostudies|vodic"
     r"|/upis/|^www/upis|upis2005|informator|^pt/download/(opi|tbpo|tida|tp|zzs)\.", PLANS),
    (r"^www/(dokument|_media/fakultet|down/|studenti/|fakultet/|istrazivanje/lab|publikacije/katalog|nastava/(opter|pravilnik|predlog))"
     r"|^www/obrazovanje/opste/[^/]+$|^master/"
     r"|diplomski-formular|uputstvo za diplomski|saglasnost", DOCS),
    # subjects: by the course folder (an old subject's files to today's MI subject that continues it)
    (r"^cent/nastava/(statut99/)?(0101|0114|010?1_)", "p:Технологија машинске обраде"),
    (r"^cent/nastava/(0110_|ptp|its)", "p:Интелигентни технолошки системи"),
    (r"^cent/nastava/0108_", "p:Аутоматизација производње"),
    (r"^cent/nastava/0111_", "p:Индустријски роботи"),
    (r"^cent/nastava/0112_", "p:Рачунарски интегрисани системи и технологије"),
    (r"^cent/nastava/0113_", "p:Пројектовање обрадних система"),
    (r"^cent/nastava/0117_", "p:Менаџмент квалитетом"),
    (r"^cent/nastava/(0102_|kg4)", "p:Компјутерска графика"),
    (r"^cent/nastava/(0103_|kibernetika)|vezbe_kibernetika", "p:Компјутерско управљање и надзор у аутоматизацији производње"),
    (r"^cent/nastava/(0104_|tpo)", "p:Производне технологије и метрологија"),
    (r"^cent/nastava/(0105_|(statut99/)?ma/|ma_bsc)", "p:Машине алатке"),
    (r"^cent/nastava/(0106)", "p:Алати и прибори"),
    (r"^cent/nastava/0107_", "p:Производни информациони системи"),
    (r"^cent/nastava/((statut99/)?(0109_|ukp)|kio)", "p:Менаџмент квалитетом"),
    (r"^cent/nastava/ksi?vi", "p:Компјутерска симулација и вештачка интелигенција"),
    (r"^cent/nastava/teh_mas_obrade", "p:Технологија машинске обраде"),
    (r"^cent/nastava/noveteh", "p:Нове технологије"),
    (r"^cent/nastava/praksa", "p:Стручна пракса Б"),
    (r"^cent/nastava/ps/", "p:CAD/CAM системи"),
    (r"^au/.*/(au_|ns_|heus|drugisemestar)", "p:Аутоматско управљање"),
    (r"^au/", "p:Основе аутоматског управљања"),
    (r"^fluidi/.*(mehanikafluida1501)", "p:Механика флуида 1"),
    (r"^fluidi/.*(mehanikafluidam|/mfm)", "p:Механика флуида М"),
    (r"^fluidi/", "p:Механика флуида Б"),
    (r"^geotermal/termodinamika/", "p:Термодинамика Б"),
    (r"^motori/downloads/dijag", "p:Дијагностика и одржавање мотора СУС"),
    (r"^motori/downloads/okmsus", "p:Конструкција мотора 1"),
    (r"^motori/downloads/", "p:Мотори СУС"),
    (r"^omk/bolonja/me 2|^omk/.*me ?(ii|2)\b", "p:Машински елементи 2"),
    (r"^omk/bolonja/izborni", "p:Моделирање облика"),
    (r"^omk/files/izborni", "p:Техничко законодавство – прописи и стандарди"),
    (r"^omk/downloads/.*(ok\b|ok[ _]|2202ok|opruge|aktuatori)", "p:Основе конструисања"),
    (r"^omk/", "p:Машински елементи 1"),
    (r"^simlab/zaskidanje/", "p:Пројектовање летелица"),
    (r"^ie/bp/", "p:Базе података"), (r"^ie/mis/", "p:Менаџмент информациони системи"),
    (r"^ie/sablon", "p:Индустријско инжењерство - пројектовање и пракса"), (r"^ie/ergonomija", "p:Индустријска ергономија"),
    (r"^ie/|katedre/ie/", "p:Увод у индустријско инжењерство"),
    (r"^mat/kma/nastava/mat2|lekcije_mat2|matematika ?2|mat2-", "p:Математика 2"),
    (r"^mat/kma/nastava/nume|numericke_metode", "p:Нумеричке методе"),
    (r"^mat/kma/nastava/prog", "p:Програмирање"),
    (r"^mat/kma/nastava/raal|news-ra/|racunarskialati", "p:Рачунарски алати"),
    (r"lekcije_mat3|mat3", "p:Математика 3"),
    (r"katedre/matematika/", "p:Математика 1"),
    (r"katedre/mehanika/.*(mehanika_?1|statika)", "p:Механика 1"),
    (r"katedre/mehanika/.*mehanika_? ?2", "p:Механика 2"),
    (r"katedre/otpornost-konstr/", "p:Основи отпорности конструкција"),
    (r"katedre/t-crtanje-mehanizmi/", "p:Инжењерска графика"),
    (r"katedre/termoenergetika/", "p:Увод у енергетику"),
    (r"katedre/teh-materijala/", "p:Машински материјали 1"),
    (r"katedre/motorna vozila/", "p:Безбедност возила"),
    (r"katedre/opste-mas-konstr/", "p:Машински елементи 1"),
    (r"^pt/download/bt\.", "p:Биотехнологија"), (r"^pt/download/do\.", "p:Дифузионе операције и апарати"),
    (r"^pt/download/miha\.", "p:Механичке и хидромеханичке операције и опрема"),
    (r"^pt/download/pps\.", "p:Пројектовање, изградња и експлоатација процесних система"),
    (r"^pt/download/susare\.", "p:Сушаре"),
]
# The news posts "v:<event>" makes, from their files' first pages: (title, day). No day: the earliest file's capture.
EVENTS = {
    "tqm2005": ("3. međunarodna konferencija „Total Quality Management – Advanced and Intelligent Approaches”, 30. maj – 1. jun 2005.", None),
    "tqm2007": ("4. međunarodna konferencija „Total Quality Management – Advanced and Intelligent Approaches”, 27–30. maj 2007.", None),
    "tqm2009": ("5. međunarodna konferencija „Total Quality Management – Advanced and Intelligent Approaches”, 1–4. jun 2009.", None),
    "tqm2015": ("8. međunarodna konferencija „Total Quality Management – Advanced and Intelligent Approaches”, 2–5. jun 2015.", None),
    "jupiter32": ("32. JUPITER konferencija – prvi poziv", None),
    "jupiter33": ("33. JUPITER konferencija – drugi poziv", None),
    "jupiter35": ("35. JUPITER konferencija – program", None),
    "das2012": ("29. simpozijum „Danubia Adria” (DAS 2012) – poziv za radove", None),
    "cirp": ("CIRP – poziv", None),
    "alumni1": ("Prvi kongres Alumni fonda αMEβ, 27–29. decembar 2005.", "2005-12-30"),
    "alumni2": ("Drugi kongres Alumni fonda αMEβ, 26. oktobar 2007.", "2007-10-01"),
    "mhcl06": ("XVIII međunarodna konferencija MHCL'06, 19–20. oktobar 2006. – poziv za radove", None),
    "sie2009": ("4. međunarodni simpozijum industrijskog inženjerstva SIE 2009 – prvi poziv", None),
    "cocacola": ("Coca-Cola – poziv studentima", None),
    "formula2014": ("Formula Student tim „Drumska strela” – konkurs za 2014.", None),
    "siemens2012": ("Siemens – poziv studentima 2012.", None),
    "nagradjeni2009": ("Nagrađeni studenti 2009.", None),
    "mip": ("Mašinsko inženjerstvo u praksi – materijal za pripremu ispita", None),
    "vip2013": ("Plaćena praksa u Vipu – sedma generacija Vip studenata", None),
    "francuska2014": ("Stipendije Vlade Francuske za master 2014.", None),
    "gtz": ("GTZ/WBF – pool studenata za praksu u nemačkim firmama", "2003-11-04"),
    "dksm": ("DKSM – poziv za ponude za studentski klub 2003/2004.", None),
    "svetisava2003": ("Nagrada Svetog Save za najbolju knjigu u 2002. godini", "2003-01-27"),
    "upis2008": ("Upis 2008: studiraćete na prvom akreditovanom mašinskom fakultetu u Srbiji", None),
    "upis2005": ("Konkurs za upis u prvu godinu 2005.", "2005-08-23"),
    "euroavia": ("EUROAVIA Beograd – poziv", None),
    "asme": ("ASME News: tekstovi iz 2003. i 2004.", None),
    "listpi": ("List PI, brojevi 1–6 (2005–2006)", "2006-12-01"),
}


def files():
    """{key: manifest row} of wayback_files.py's saved files."""
    rows = map(json.loads, (WB / "files.jsonl").read_text("utf-8").splitlines())
    return {r["key"]: r for r in rows if r.get("ok")}


def tag_of(key):
    return "stari-" + key.split("/")[0]


def href_of(key, row):
    name = unquote(urlsplit(row["url"]).path.rsplit("/", 1)[-1])  # as the site named it (the key is lowercase)
    return f"/files/{tag_of(key)}/{asset_name(key)}/{quote(name)}"


def is_old(url):
    u = urlsplit(url)
    return u.scheme in ("http", "https") and bool(OLD.search(u.hostname or ""))


def links(html):
    return [a for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if is_old(a["href"])]


def fix(html, ts, saved):
    """The item's links made to work (see the module's note)."""
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        if not is_old(a["href"]):
            continue
        k = key_of(a["href"])
        if k in saved:
            a["href"] = href_of(k, saved[k])
        elif PAGE.search(urlsplit(a["href"]).path):
            a["href"] = f"https://web.archive.org/web/{ts}/{a['href']}"
        else:
            a.unwrap()
    return str(soup)


def vesti():
    saved = files()
    out = []
    for a in map(json.loads, (WB / "articles.jsonl").read_text("utf-8").splitlines()):
        last = a["copies"][-1]  # https://web.archive.org/web/<ts>/<url>, the newest copy
        ts = last.split("/")[4]
        forum = next((f for pat, f in FORUM if re.search(pat, a["section"])), None)
        out.append(
            dict(
                key=a["key"],
                date=a["date"],
                title=a["title"],
                author=a["author"] or None,
                html=fix(a["html"], ts, saved),
                full=fix(a["full"], ts, saved) if a["full"] else "",
                forum=forum,
                upis=bool(UPIS.match(a["section"])),
                wp=int(a["id"]) if a["kind"] == "wordpress" and a["id"] else None,
                host=urlsplit(last.split("/", 5)[5]).hostname.removeprefix("www."),
                wayback=last,
            )
        )
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"{OUT.name}: {len(out)} items, {sum(1 for r in out if r['forum'])} departments'")


def linked():
    """The keys of the saved files the news items link."""
    saved = files()
    return {k for a in map(json.loads, (WB / "articles.jsonl").read_text("utf-8").splitlines())
            for k in map(key_of, (x["href"] for x in links(a["html"] + a["full"]))) if k in saved}


def place(key):
    """Where a file goes (RULES): ("p"|"a"|"v", what), or None."""
    to = next((t for pat, t in RULES if re.search(pat, key)), "-")
    if to == "-":
        return None
    kind, what = to.split(":", 1)
    if what == "*":
        stem = key.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        what = re.sub(r"^as\d+\s*", "", stem) if kind == "p" else stem
    return kind, what


YUSCII = str.maketrans("{}~`|[]^@\\qw", "šćčžđŠĆČŽĐљњ")  # the old 7-bit Serbian fonts' letters ("Ma{inski", "prijavqenim")


def candidates(path, name, teachers):
    """The id of the teacher an election report is about, or none: the one its file name names ("SBosnjak_Karton.pdf",
    "TaskoManeskiIzbor.pdf": first name or initial, and surname), else the one its text names right after "kandidat"
    or "prijavio se" whose surname comes back through the report (their biography; a committee member's or a mentor's
    seldom does). A file that names someone else ("Referat-Dragan Urosevic.pdf"), or two of one name neither its
    name nor its text tells apart: none. Folded (fold) to compare. [] or [id]."""
    import fitz

    tokens = re.findall(r"[a-z]+", fold(name.rsplit(".", 1)[0]))
    stem = "".join(tokens)
    try:
        text = " ".join(p.get_text() for p in list(fitz.open(path))[:2])
    except Exception:
        text = ""
    if re.search(r"[a-z][{}~`|]", text):
        text = text.translate(YUSCII)
    text = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", fold(text)))
    named = lambda t, s=text: re.search(rf"\b{t[1]} ({t[2] or '[a-z]'} )?{t[3]}\b|\b{t[3]} ({t[2] or '[a-z]'} )?{t[1]}\b", s)

    def one(ts):  # two teachers of one name: the one whose middle initial the file name or the text has
        if len(ts) > 1:
            ts = [t for t in ts if t[2] and (t[2] in tokens or re.search(rf"\b{t[1]} {t[2]} {t[3]}\b", text))]
        return [ts[0][0]] if len(ts) == 1 else []

    if full := [t for t in teachers if t[1] + t[3] in stem or t[3] + t[1] in stem]:
        return one(full)
    if initial := [t for t in teachers if any(tok.startswith(t[1][0] + t[3]) for tok in tokens)]:
        return one([t for t in initial if named(t)] if len(initial) > 1 else initial)
    if any(tok in {t[1] for t in teachers} for tok in tokens):
        return []
    near = " | ".join(text[m.end():m.end() + 160] for m in re.finditer(r"kandidat|prijavi", text))
    return one([t for t in teachers if named(t, near) and len(re.findall(rf"\b{t[3]}\b", text)) >= 3])


def teacher_names():
    """[(id, first, middle initial or "", last)] folded, of every teacher nastava.db has ("Драган С. Алексендрић")."""
    import sqlite3

    db = sqlite3.connect(f"file:{ROOT / 'nastava.db'}?mode=ro", uri=True)
    out = []
    for i, name in db.execute("SELECT id, name FROM teachers"):
        parts = re.sub(r"[^a-z ]", " ", fold(name)).split()
        if len(parts) >= 2:
            out.append((i, parts[0], parts[1] if len(parts) > 2 else "", parts[-1]))
    return out


def fajlovi():
    """data/stari-fajlovi.jsonl: each saved file RULES places, once (the same bytes under two addresses: the first).
    A course file a department's news item links stays with the item (its post), not on the subject too."""
    saved, news, teachers = files(), linked(), teacher_names()
    out, seen, left = [], set(), []
    for k, r in sorted(saved.items()):
        if r["sha256"] in seen:
            continue
        seen.add(r["sha256"])
        to = place(k)
        if not to or (to[0] == "p" and k in news):
            left.append(k) if not to else None
            continue
        name = unquote(urlsplit(r["url"]).path.rsplit("/", 1)[-1])
        row = dict(key=k, name=name, href=href_of(k, r), to=to[0], where=to[1], date=f"{r['ts'][:4]}-{r['ts'][4:6]}-{r['ts'][6:8]}",
                   folder=unquote(urlsplit(r["url"]).path).rsplit("/", 2)[-2], wayback=f"https://web.archive.org/web/{r['ts']}/{r['url']}")
        if to[0] == "v":
            row["title"], row["day"] = EVENTS[to[1]]
        if to == tuple(IZBORI.split(":", 1)):
            row["people"] = candidates(WB / r["path"], name, teachers)
        out.append(row)
    FILES_OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    from collections import Counter
    print(f"{FILES_OUT.name}: {len(out)} files, {dict(Counter(r['to'] for r in out))}; {len(left)} left out")


def host():
    """Upload the saved files the items link and fajlovi places to stari-<host>: those missing, or changed since."""
    saved = files()
    wanted = linked() | {r["key"] for r in map(json.loads, FILES_OUT.read_text("utf-8").splitlines())}
    by_tag = {}
    for k in sorted(wanted):
        by_tag.setdefault(tag_of(k), []).append(k)
    for tag, keys in by_tag.items():
        have = release_assets(tag, tag, "Files of the old faculty sites (mas.bg.ac.yu), from the Wayback Machine (tools/stari_sajt.py).")
        todo = {}
        for k in keys:
            data = (WB / saved[k]["path"]).read_bytes()
            if have.get(asset_name(k)) not in (hashlib.sha256(data).hexdigest(), ""):
                todo[asset_name(k)] = data
        upload_assets(tag, todo)
        print(f"{tag}: {len(todo)} uploaded, {len(keys)} files")


if __name__ == "__main__":
    {"vesti": vesti, "fajlovi": fajlovi, "host": host}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
