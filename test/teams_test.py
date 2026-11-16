# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "tzdata", "openpyxl", "xlrd", "pypdf", "python-docx", "pymupdf"]
# ///
"""The asserts of scrapers/teams.py (were its __main__ block), no network: uv run test/teams_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
import json  # noqa: E402
import io  # noqa: E402
import tempfile  # noqa: E402
import zipfile  # noqa: E402
import openpyxl  # noqa: E402
import teams  # noqa: E402
import pymupdf  # noqa: E402
from common import lists_students, redact_students  # noqa: E402
from teams import body, clean_title, name_key, names_pattern, own_zip, redact, title_of  # noqa: E402


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


def xlsx(rows):
    wb = openpyxl.Workbook()
    for r in rows:
        wb.active.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def check_private():
    """What a closed class's file must not publish: lists_students, a thread's title, a student's upload."""
    # A results sheet by its column; a handout with only school years and a subscript "индекс" passes.
    assert lists_students("Rezultati.xlsx", xlsx([["р.бр.", "ШПАН", "име"], [1, "Petrović", "Petar"]]))
    assert lists_students("OPP.xlsx", xlsx([["Презиме", "Име", "Бр. Инд."], ["Ilić", "Ana", 12]]))
    assert not lists_students("plan.xlsx", xlsx([["Nedelja", "Tema"], [1, "Uvod 2025/2026"]]))
    assert lists_students("r.txt", "\n".join(f"{i}/2023 Ime Prezime 7" for i in range(5)).encode()) == "5 index numbers"
    assert not lists_students("HO1.txt", "школска 2025/2026. индекс i, 4/2023".encode())
    assert not lists_students("x.SLDPRT", b"\x00\x01") and not lists_students("bad.xlsx", b"not a zip")
    # A thread's title: the index and the known student's name go, as in its text.
    assert clean_title("Petar Petrović 385/2023 položio", names_pattern(["Petar Petrovic"])) == "███████ ████████ položio"
    assert clean_title("Čestitke Petru, Petar Petrović je prvi", names_pattern(["Petar Petrovic"])) == "Čestitke Petru, Student je prvi"
    assert clean_title("Rezultati 2025/2026", None) == "Rezultati 2025/2026"
    # A results sheet blacked out: the students' columns and an index elsewhere; the points stay.
    data, why = redact_students("OPP.xlsx", xlsx([["Презиме", "Име", "Бр. Инд.", "Год.", "Тест 1"], ["Ilić", "Ana", 12, 2023, 24],
                                                  [None, None, None, None, "napomena: 7/2024 kasni"]]))
    rows = list(openpyxl.load_workbook(io.BytesIO(data)).active.iter_rows(values_only=True))
    assert rows[1] == ("████", "███", "██", "████", 24) and rows[2][4] == "napomena: ██████ kasni", rows
    # A results PDF: each row with an index loses its letters' words and the index, text and all; the grade, the heading
    # and a school year stay.
    doc = pymupdf.open()
    page = doc.new_page()
    for y, line in ((60, "Rezultati 2025/2026"), (90, "indeks prezime ime ocena"), (110, "259/2023 Petrovic Petar 8"), (130, "12/2024 Ilic Ana 9")):
        page.insert_text((50, y), line)
    for n in range(3):
        page.insert_text((50, 150 + 20 * n), f"{100 + n}/2023 Jovanovic Jovan 7")
    data, why = redact_students("r.pdf", doc.tobytes())
    left = " ".join(w[4] for w in pymupdf.open(stream=data, filetype="pdf")[0].get_text("words"))
    assert why == "5 index numbers: 15 redacted" and left == "Rezultati 2025/2026 indeks prezime ime ocena 8 9 7 7 7", (why, left)
    # A kind that cannot be redacted here is not published; a file listing no one goes out as it is.
    assert redact_students("r.txt", "\n".join(f"{i}/2023 Ime Prezime 7" for i in range(5)).encode())[0] is None
    assert redact_students("plan.pdf", b"%PDF") == (b"%PDF", None)
    # The library: only a teacher's upload, a results list of theirs blacked out; a zip without the uploaders list, none.
    teacher = next(k for k in teams.TEACHERS if k.startswith("8:orgid:")).removeprefix("8:orgid:")
    with tempfile.TemporaryDirectory() as tmp:
        teams.MAIL = Path(tmp)
        for name, with_list in (("Klasa (abcd1234).zip", True), ("abcd1234.zip", False)):
            z = Path(tmp) / name
            with zipfile.ZipFile(z, "w") as w:
                w.writestr("General/predavanje.pdf", b"%PDF")
                w.writestr("General/moj rad.pdf", b"%PDF")
                w.writestr("General/rezultati.xlsx", xlsx([["ШПАН", "име"], ["1/2023", "Ana"]]))
                if with_list:
                    up = {"General/predavanje.pdf": teacher, "General/moj rad.pdf": "student-id", "General/rezultati.xlsx": teacher}
                    w.writestr(teams.UPLOADERS, json.dumps(up))
            assert own_zip(zipfile.ZipFile(z), "abcd1234")
            teams.material(dict(groupId="abcd1234-0000", name="Klasa"), "/predmet/x/y/", [zipfile.ZipFile(z)], set(), set())
            m = Path(tmp) / "teams-abcd1234" / "material.json"
            if with_list:
                assert json.loads(m.read_text(encoding="utf-8"))["files"] == ["General/predavanje.pdf", "General/rezultati.xlsx"], m.read_text()
                sheet = openpyxl.load_workbook(Path(tmp) / "teams-abcd1234" / "General" / "rezultati.xlsx").active
                assert [c.value for c in sheet[2]] == ["██████", "███"], [c.value for c in sheet[2]]
                m.unlink()
            else:
                assert not m.exists()
    teams.MAIL = ROOT / "mail"


check()
check_private()
