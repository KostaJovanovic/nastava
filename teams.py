# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "tzdata"]
# ///
"""The posts of the faculty's Teams classes, as posts of their subjects (build.py's load_mail, as mail.py's mails):
each thread a teacher started, with its replies; a student's reply is "Student #N" (numbered per thread), with no name,
index number, e-mail or file of theirs. Their files come from each class's SharePoint library (downloaded as zips); the
rest of a library is the subject's material (mail/teams-<class>/material.json).

The export comes from Teams in the browser (README: "To add Teams posts"): every channel's messages, as JSON.

Usage: teams.py files <token file> <zip folder>
       teams.py add <teams-export.json> <zip folder>
  files  download each class's library (CLASSES) through Graph into <zip folder>/<group>.zip; the token is Graph
         Explorer's (its "Access token" tab, after consenting to Files.Read.All), saved in a file.
  add    a post already here is skipped; a class's material is written again.
"""
import hashlib
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

MAIL = Path(__file__).resolve().parent / "mail"
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
SIGNED = re.compile(rf"((?:{WORD}[ ,]{{1,2}}){{1,3}})?\b(\d{{1,4}})\s*[-/]\s*(?:20)?\d\d\b((?:[ ,]{{1,2}}{WORD}){{1,3}})?")
# Students named in a reply with no index next to it, and not under their Teams name: found by reading the replies.
NAMED = ["Jovan Geratovic"]
LAT = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш", "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()))
# A letter of a name without diacritics, as it can be written: with them, or in Cyrillic.
LATIN = {"dj": "(?:dj|đ)", "dz": "(?:dz|dž)", "c": "[cčć]", "s": "[sš]", "z": "[zž]", "d": "[dđ]"}
CYRIL = {**{v: k for k, v in LAT.items() if v not in ("c", "s", "z", "d", "dj", "lj", "nj", "dz")},
         "dj": "(?:ђ|дј)", "lj": "(?:љ|лј)", "nj": "(?:њ|нј)", "dz": "(?:џ|дж|дз)", "c": "[цчћ]", "s": "[сш]", "z": "[зж]", "d": "[дђ]"}


def plain(name):
    """A name in Latin, lower case, without diacritics: "Ђорђе Илић", "Đorđe Ilić" -> "djordje ilic"."""
    s = "".join(LAT.get(ch, ch) for ch in name.lower()).replace("đ", "dj")
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def spelled(word):
    """A plain word as a pattern of its spellings, in Latin with or without diacritics, or in Cyrillic."""
    tokens = re.findall(r"dj|dz|lj|nj|.", word)
    return "(?:" + "".join(LATIN.get(t, re.escape(t)) for t in tokens) + "|" + "".join(CYRIL.get(t, re.escape(t)) for t in tokens) + ")"


def redact(text):
    """A student's index numbers, the name signed next to one, and e-mails: each letter a block, spaces kept."""
    text = EMAIL.sub(lambda m: "█" * len(m[0]), text)
    return SIGNED.sub(lambda m: re.sub(r"\S", "█", m[0]) if int(m[2]) < 1900 else m[0], text)


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
        if student:
            text = redact(text)
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
                        z = next((z for z in archives if path and path in z.namelist()), None)
                        if not z:
                            missing.append(f"{t['name']}: {path or f.get('fileName')}")
                            continue
                        out.mkdir(parents=True, exist_ok=True)
                        name = Path(path).name
                        (out / name).write_bytes(z.read(path))
                        names.append(name)
                    out.mkdir(parents=True, exist_ok=True)
                    post = dict(id=mid, refs=[] if m is root else [root_key], page=page,
                                author=TEACHERS[who(m)] if teacher else label(who(m)),
                                posted=sent.isoformat(), when=f"{sent.astimezone(TZ):%d.%m.%Y. %H:%M}",
                                title=title if m is root else f"Re: {title}",
                                html=body(m, label, student_ids, name_re), files=names)
                    (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
                    added += 1
        material(t, page, archives, posted_files, student_files)
    print(f"{added} posts added to {MAIL}")
    if missing:
        print(f"{len(missing)} files of posts not in the zips:\n  " + "\n  ".join(missing), file=sys.stderr)


def material(t, page, archives, posted_files, student_files):
    """The rest of a class's library: its zip is the one with most of the class's posted files. Not the files of a
    student's post, nor the recordings."""
    known = posted_files | student_files
    z = max(archives, key=lambda z: len(known & set(z.namelist())), default=None)
    if not z or not known & set(z.namelist()):
        print(f"no library zip for {t['name']}", file=sys.stderr)
        return
    rest = [p for p in z.namelist() if not p.endswith("/") and p not in known and not NOT_MATERIAL.search(p)]
    out = MAIL / f"teams-{t['groupId'][:8]}"
    for p in rest:
        (out / p).parent.mkdir(parents=True, exist_ok=True)
        (out / p).write_bytes(z.read(p))
    (out / "material.json").write_text(json.dumps(dict(page=page, name=t["name"], files=rest), ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"{t['name']}: {len(rest)} files of material")


GRAPH = "https://graph.microsoft.com/v1.0"
MAX = 95 << 20  # GitHub Pages takes no file over 100 MB


def files(token_file, out):
    """Each class's library as <out>/<group>.zip, its paths as in the library ("Predavanja/P1.pdf"); not the
    recordings, nor a file too big for the site."""
    token = Path(token_file).read_text(encoding="utf-8").strip().removeprefix("Bearer ")

    def get(url):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}), timeout=300)
        except urllib.error.HTTPError as e:
            sys.exit(f"{e.code} {url}\n{e.read()[:300].decode(errors='replace')}\n401: a new token; 403: consent to Files.Read.All")

    def children(url):
        while url:
            page = json.load(get(url))
            yield from page["value"]
            url = page.get("@odata.nextLink")
    Path(out).mkdir(parents=True, exist_ok=True)
    for group in dict.fromkeys(CLASSES):
        drive = json.load(get(f"{GRAPH}/groups/{group}/drive"))["id"]
        n = size = 0
        with zipfile.ZipFile(Path(out) / f"{group[:8]}.zip", "w", zipfile.ZIP_DEFLATED) as z:
            folders = [("", f"{GRAPH}/drives/{drive}/root/children")]
            while folders:
                prefix, url = folders.pop()
                for item in children(url):
                    path = prefix + item["name"]
                    if "folder" in item:
                        folders.append((path + "/", f"{GRAPH}/drives/{drive}/items/{item['id']}/children"))
                    elif NOT_MATERIAL.search(path) or item["size"] > MAX:
                        print(f"  skipped {path} ({item['size'] / 2**20:.0f} MB)")
                    else:
                        z.writestr(path, get(f"{GRAPH}/drives/{drive}/items/{item['id']}/content").read())
                        n, size = n + 1, size + item["size"]
        print(f"{group[:8]}: {n} files, {size / 2**20:.1f} MB")


def check():
    assert redact("Ana, 385-2023, ana@x.rs, 2023/2024") == "████ ████████, ████████, 2023/2024", redact("Ana, 385-2023, ana@x.rs, 2023/2024")
    assert redact("nema me na spisku. Milošević Nemanja 12/2024") == "nema me na spisku. █████████ ███████ ███████"
    assert redact("prijavljujem 1. kolokvijum, 7/2024 Đorđe Ilić.") == "prijavljujem 1. kolokvijum, ██████ █████ ████."
    r = names_pattern(["Petar Petrovic", "Jovan", "Đorđe Ilić"])
    assert r.sub("X", "pozdrav petrović  petar i Петар Петровић, Jovan, Djordje Ilic") == "pozdrav X i X, Jovan, X"
    assert name_key("Петровић Петар") == name_key("Petar Petrovic") == "petar petrovic"
    assert redact("Бојана Лучић 902/24, 2023/24") == "██████ █████ ██████, 2023/24"
    m = dict(messagetype="RichText/Html", **{"from": "x/8:orgid:s1"}, content='<p>Hvala <span itemtype="http://schema.skype.com/Mention" '
             'itemid="0">Mirko</span> <img src="a">— Petar Petrović 12/2024</p>', properties=dict(mentions=json.dumps(
                 [dict(itemid=0, mri="8:orgid:t9")])))
    n = {}
    label = lambda a: n.setdefault(a, f"Student #{len(n) + 1}")
    ids, pat = {"petar petrovic": "8:orgid:s1"}, names_pattern(["Petar Petrović"])
    assert body(m, label, ids, pat) == "<p>Hvala Student #1 — Student #2 ███████</p>", body(m, label, ids, pat)
    m["content"] = "<p>Petrovic Petar</p>"
    assert body(m, label, ids, pat) == "<p>Student #2</p>"
    assert title_of(dict(content="<p>Prvi red. Drugi</p>", properties={})) == "Prvi red."


if __name__ == "__main__":
    check()
    if len(sys.argv) != 4 or sys.argv[1] not in ("add", "files"):
        sys.exit(__doc__)
    (add if sys.argv[1] == "add" else files)(sys.argv[2], sys.argv[3])
