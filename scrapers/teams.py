# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "tzdata"]
# ///
"""The posts of the faculty's Teams classes, as posts of their subjects (build.py's load_mail, as mail.py's mails):
each thread a teacher started, with its replies; a student's reply is "Student #N" (numbered per thread), with no name,
index number, e-mail or file of theirs. Their files come from each class's SharePoint library (a zip each,
teams-files.js); the rest of a library is the subject's material (mail/teams-<class>/material.json).

The export and the zips come from Teams in the browser (README: "To add Teams posts").

Usage: teams.py add <teams-export.json> <folder of the classes' library zips>
  add   a post already here is skipped; a class's material is written again.
"""

import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from common import ROOT
from translit import FOLD

MAIL = ROOT / "mail"
# A class (its group id) -> its subject's page.
CLASSES = {
    "082939b7-8d05-4150-9f90-ba736597d7ef": "/predmet/oas-mi/masinsko-inzenjerstvo-i-odrzivi-razvoj/",  # 113, 2025/26
    "0cb46977-404b-4aa6-9c2b-449ee54640be": "/predmet/oas-mi/masinsko-inzenjerstvo-i-odrzivi-razvoj/",  # 108, 2024/25
    "a646ee0b-1bb6-4ef8-8ce4-b05e82bf50ef": "/predmet/oas-mi/termodinamika-b/",
    "43364f3f-2bd5-4b18-b88f-fec1d421aaed": "/predmet/oas-mi/osnovi-otpornosti-konstrukcija/",  # 6. smena 2025/26
    "3df598f2-4de9-47ec-b16b-7b609ae8b19a": "/predmet/oas-mi/osnovi-otpornosti-konstrukcija/",  # druga smena 2024/25
    "274e521b-a673-4a1d-b293-84b70456a381": "/predmet/oas-mi/otpornost-materijala/",
    "96abf82f-eadd-4c9d-a7ab-c153ac610316": "/predmet/oas-mi/estetski-dizajn/",
    "4148033c-786d-483f-9fb6-f2bc99ad2952": "/predmet/oas-mi/inzenjerska-grafika/",
}
# A teacher's Teams account -> their board username (their teacher page), or their name when they have none. By
# account, not by name: a student can share a teacher's name.
TEACHERS = {
    "8:orgid:79737da1-b1e1-4c10-a8a0-34814a5750fe": "Nikola Stošić",
    "8:orgid:efa6d2fb-364b-42d1-9780-7005617b1035": "vjovanovic",
    "8:orgid:583e14a4-584d-454b-82d2-8009010af15f": "nmanic",
    "8:orgid:15435294-054d-434a-9fca-855c23db3293": "mkomatina",
    "8:orgid:41d2dc34-33b9-4a29-9cb6-50fdc8955a35": "sotovic",
    "8:orgid:f72e3cc8-d26f-4ea0-ae9e-bf8654b5d66f": "mmjankovic",
    "8:orgid:853733f3-8b4d-4d59-9b15-2cb5ab1550fe": "aspetrovic",
    "8:orgid:b5b4047f-39be-426f-9869-3fc1aef7da54": "zjeli",
    "8:orgid:075bdb40-e4d7-4245-b821-2788c4da3b43": "bkosic",
    "8:orgid:c4968b8f-858d-404a-a1ad-84a109148a8c": "mregodic",
}
POSTS = ("RichText/Html", "Text")  # not the joins and other notices, nor the bots' cards
# Folders of a library that are not material: meeting recordings show the students.
NOT_MATERIAL = re.compile(r"(^|/)(Recordings|Snimci)/", re.I)
# Files about the students that a teacher put in a library: the class list, the students' own work. Not published.
PRIVATE = re.compile(r"spisak|списак|radovi studenata|радови студената", re.I)
TZ = ZoneInfo("Europe/Belgrade")
# An index number (385-2023, 385/2023), not a school year (2023/2024).
INDEX = re.compile(r"\b(\d{1,4})\s*[-/]\s*(20\d\d)\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def who(m):
    return m["from"].rsplit("/", 1)[-1]


def lib_path(f):
    """A posted file's path in its class's library ("Predavanja/Popravni T1.pdf")."""
    url = unquote(f["fileInfo"].get("fileUrl") or "")
    return url.split("/Shared Documents/", 1)[1] if "/Shared Documents/" in url else None


# A student's signature: up to three capitalized words before or after their index number ("Petrović Danilo 385/2023").
WORD = r"[A-ZČĆŽŠĐА-ЯЂЈЉЊЋЏ][a-zčćžšđа-яђјљњћџ'’-]+"


def signed(number):
    """A student's index number (its part after the first digits: number) with up to three names around it."""
    return re.compile(rf"((?:{WORD}[\s,]{{1,4}}){{1,3}})?\b(\d{{1,4}})\s*{number}\b((?:[\s,]{{1,4}}{WORD}){{1,3}})?")


SIGNED = signed(r"[-/]\s*(?:20)?\d\d")
# A teacher's list of results ("Petar Petrović 385/2023 15.6"): there "10-12" is a time, so an index has a slash or a
# four-digit year.
SIGNED_T = signed(r"(?:/\s*(?:20)?\d\d|-\s*20\d\d)")
# The addresses a teacher's post keeps: all but a student's faculty one (their class's gmail is where work goes).
STUDENT_MAIL = re.compile(r"@studenti?\.mas\.bg\.ac\.rs$", re.I)
# Students named in a reply with no index next to it, and not under their Teams name: found by reading the replies.
NAMED = ["Jovan Geratovic"]
# A letter of a name without diacritics, as it can be written: with them, or in Cyrillic.
LATIN = {"dj": "(?:dj|đ)", "dz": "(?:dz|dž)", "c": "[cčć]", "s": "[sš]", "z": "[zž]", "d": "[dđ]"}
CYRIL = {
    **{v: k for k, v in FOLD.items() if v not in ("c", "s", "z", "d", "dj", "lj", "nj", "dz")},
    "dj": "(?:ђ|дј)",
    "lj": "(?:љ|лј)",
    "nj": "(?:њ|нј)",
    "dz": "(?:џ|дж|дз)",
    "c": "[цчћ]",
    "s": "[сш]",
    "z": "[зж]",
    "d": "[дђ]",
}


def plain(name):
    """A name in Latin, lower case, without diacritics: "Ђорђе Илић", "Đorđe Ilić" -> "djordje ilic"."""
    s = "".join(FOLD.get(ch, ch) for ch in name.lower()).replace("đ", "dj")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def spelled(word):
    """A plain word as a pattern of its spellings, in Latin with or without diacritics, or in Cyrillic."""
    tokens = re.findall(r"dj|dz|lj|nj|.", word)
    return "(?:" + "".join(LATIN.get(t, re.escape(t)) for t in tokens) + "|" + "".join(CYRIL.get(t, re.escape(t)) for t in tokens) + ")"


def redact(text, teacher=False):
    """A student's index numbers, the name written next to one, and e-mails: each letter a block, spaces kept.
    teacher: a teacher's post, which keeps its times ("10-12") and every address but a student's."""
    text = EMAIL.sub(lambda m: m[0] if teacher and not STUDENT_MAIL.search(m[0]) else "█" * len(m[0]), text)
    return (SIGNED_T if teacher else SIGNED).sub(lambda m: re.sub(r"\S", "█", m[0]) if int(m[2]) < 1900 else m[0], text)


def names_pattern(names):
    """Every student's full name, in either order and any spelling, as one pattern (longest first)."""
    alts = set()
    for n in names:
        words = plain(n).split()
        if len(words) >= 2:
            alts |= {r"\s+".join(map(spelled, words)), r"\s+".join(map(spelled, reversed(words)))}
    return re.compile(r"\b(?:" + "|".join(sorted(alts, key=len, reverse=True)) + r")\b", re.I) if alts else None


def name_key(name):
    """The same key for a name in any order or spelling."""
    return " ".join(sorted(plain(name).split()))


def body(m, label, students, name_re):
    """A message's HTML: a student's mention, name, index number and e-mail replaced; no images (Teams-only links)."""
    if m["messagetype"] == "Text":
        html = "<br>".join(escape(line) for line in (m.get("content") or "").splitlines())
    else:
        html = m.get("content") or ""
    soup = BeautifulSoup(html, "html.parser")
    mentions = {str(x["itemid"]): x for x in json.loads(m.get("properties", {}).get("mentions") or "[]")}
    for span in soup.select('span[itemtype="http://schema.skype.com/Mention"]'):
        x = mentions.get(span.get("itemid"), {})
        mri = x.get("mri", "")
        span.replace_with(span.get_text() if not mri.startswith("8:") or mri in TEACHERS else label(mri))
    for img in soup.find_all("img"):
        img.decompose()
    student = who(m) not in TEACHERS

    def named(n):
        acct = students.get(name_key(n[0]))
        return label(acct) if acct else "Student"

    for node in soup.find_all(string=True):
        text = name_re.sub(named, str(node)) if name_re else str(node)
        # A teacher's post too: a list of results names students who never posted (name_re does not know them).
        text = redact(text, teacher=not student)
        if text != str(node):
            node.replace_with(text)
    return str(soup).strip()


def title_of(m):
    subject = (m.get("properties") or {}).get("subject")
    if subject:
        return " ".join(subject.split())
    text = " ".join(BeautifulSoup(m.get("content") or "", "html.parser").get_text(" ").split())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    return first if len(first) <= 80 else first[:80].rsplit(" ", 1)[0] + "…"


def add(export, zips):
    data = json.loads(Path(export).read_text(encoding="utf-8"))
    archives = [zipfile.ZipFile(p) for p in sorted(Path(zips).glob("*.zip"))]
    # Every student's name (their posts and the mentions of them): replaced wherever it is written.
    student_ids = {}
    for t in data["teams"]:
        for c in t["channels"]:
            for m in c["messages"]:
                if m["messagetype"] in POSTS and who(m) not in TEACHERS and m.get("imdisplayname"):
                    student_ids[m["imdisplayname"]] = who(m)
                for x in json.loads((m.get("properties") or {}).get("mentions") or "[]"):
                    if x.get("mri", "").startswith("8:") and x["mri"] not in TEACHERS and x.get("displayName"):
                        student_ids[x["displayName"]] = x["mri"]
    name_re = names_pattern(list(student_ids) + NAMED)
    student_ids = {name_key(n): acct for n, acct in student_ids.items()}
    MAIL.mkdir(exist_ok=True)
    added, missing = 0, []
    for t in data["teams"]:
        page = CLASSES.get(t.get("groupId"))
        if not page:
            print(f"skipped (no subject in CLASSES): {t['name']} {t.get('groupId')}", file=sys.stderr)
            continue
        posted_files, student_files = set(), set()
        for c in t["channels"]:
            msgs = [m for m in c["messages"] if m["messagetype"] in POSTS and not (m.get("properties") or {}).get("deletetime")]
            for m in msgs:
                files = {p for f in json.loads((m.get("properties") or {}).get("files") or "[]") if (p := lib_path(f))}
                (posted_files if who(m) in TEACHERS else student_files).update(files)
            threads = {}
            for m in sorted(msgs, key=lambda m: m["composetime"]):
                threads.setdefault(m.get("rootMessageId") or m["id"], []).append(m)
            for root_id, thread in threads.items():
                root = thread[0]
                if root["id"] != root_id or who(root) not in TEACHERS:
                    continue  # a student's thread, or one whose first post is gone
                numbers = {}

                def label(account):
                    if account not in numbers:
                        numbers[account] = len(numbers) + 1
                    return f"Student #{numbers[account]}"

                for m in thread[1:]:
                    if who(m) not in TEACHERS:
                        label(who(m))
                title = title_of(root)
                root_key = f"teams:{c['id']}:{root_id}"
                for m in thread:
                    mid = f"teams:{c['id']}:{m['id']}"
                    key = hashlib.sha1(mid.encode()).hexdigest()[:8]
                    if any(MAIL.glob(f"*-{key}")):
                        continue
                    teacher = who(m) in TEACHERS
                    sent = datetime.fromisoformat(m["composetime"][:19] + "+00:00")
                    out = MAIL / f"{sent:%Y-%m-%d}-{key}"
                    names = []
                    for f in json.loads((m.get("properties") or {}).get("files") or "[]") if teacher else []:
                        path = lib_path(f)
                        if path and PRIVATE.search(path):
                            print(f"  not published (about the students): {path}")
                            continue
                        z = next((z for z in archives if path and path in z.namelist()), None)
                        if not z:
                            missing.append(f"{t['name']}: {path or f.get('fileName')}")
                            continue
                        out.mkdir(parents=True, exist_ok=True)
                        name = Path(path).name
                        (out / name).write_bytes(z.read(path))
                        names.append(name)
                    out.mkdir(parents=True, exist_ok=True)
                    post = dict(
                        id=mid,
                        refs=[] if m is root else [root_key],
                        page=page,
                        author=TEACHERS[who(m)] if teacher else label(who(m)),
                        posted=sent.isoformat(),
                        when=f"{sent.astimezone(TZ):%d.%m.%Y. %H:%M}",
                        title=title if m is root else f"Re: {title}",
                        html=body(m, label, student_ids, name_re),
                        files=names,
                        sizes={f: (out / f).stat().st_size for f in names},
                    )
                    (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
                    added += 1
        material(t, page, archives, posted_files, student_files)
    print(f"{added} posts added to {MAIL}")
    if missing:
        print(f"{len(missing)} files of posts not in the zips:\n  " + "\n  ".join(missing), file=sys.stderr)


def material(t, page, archives, posted_files, student_files):
    """The rest of a class's library: its zip is the one with most of the class's posted files. Not the files of a
    student's post, the recordings, the files about the students, nor a copy of a file listed already (a folder the
    teacher copied)."""
    known = posted_files | student_files
    z = next((z for z in archives if Path(z.filename).stem == t["groupId"][:8]), None) or max(
        archives, key=lambda z: len(known & set(z.namelist())), default=None
    )
    if not z or not (known & set(z.namelist()) or Path(z.filename).stem == t["groupId"][:8]):
        print(f"no library zip for {t['name']}", file=sys.stderr)
        return
    out, rest, seen = MAIL / f"teams-{t['groupId'][:8]}", [], set()
    for p in sorted(z.namelist()):
        if p.endswith("/") or p in known or NOT_MATERIAL.search(p) or PRIVATE.search(p):
            continue
        data = z.read(p)
        if (h := hashlib.sha1(data).digest()) in seen:
            continue
        seen.add(h)
        (out / p).parent.mkdir(parents=True, exist_ok=True)
        (out / p).write_bytes(data)
        rest.append(p)
    if not rest:
        return print(f"{t['name']}: every file is on a post")
    (out / "material.json").write_text(
        json.dumps(dict(page=page, name=t["name"], files=rest), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{t['name']}: {len(rest)} files of material")


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


if __name__ == "__main__":
    check()
    if len(sys.argv) != 4 or sys.argv[1] != "add":
        sys.exit(__doc__)
    add(sys.argv[2], sys.argv[3])
