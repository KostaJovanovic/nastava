# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4"]
# ///
"""Mails a teacher sent a subject's students, as posts of that subject (build.py's load_mail): each mail is a folder
mail/<date>-<key>/ with post.json (sender, date, subject line, the text without the quoted mail it answers, the reply
headers) and its attachments. To and Cc are never read: they are the students' addresses. Git keeps only the .json
files of mail/; the attachments (and teams.py's files) are assets of the GitHub release "mail", which the Worker serves
under /files/mail/.

Usage: mail.py add <folder of .eml files> <subject page, as /predmet/oas-mi/pumpe-i-ventilatori/>
       mail.py upload
  add     a mail already here (by Message-ID) is skipped.
  upload  upload the files of mail/ that the release has not yet (gh, signed in).
"""

import email
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup

MAIL = Path(__file__).resolve().parent / "mail"
REPO, TAG = "KostaJovanovic/nastava", "mail"


def asset_name(path):
    """A file's asset name, from its path in mail/: GitHub changes spaces and non-ASCII letters in a name (dlwms's)."""
    base = path.rsplit("/", 1)[-1]
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    ext = ext if re.fullmatch(r"[a-z0-9]{1,8}", ext) else "bin"
    return f"{hashlib.sha256(path.encode()).hexdigest()[:20]}.{ext}"


def upload():
    gh = lambda *a: subprocess.run(["gh", *a], check=True, capture_output=True, text=True).stdout
    try:
        rid = json.loads(gh("api", f"repos/{REPO}/releases/tags/{TAG}"))["id"]
        have = set(
            gh(
                "api", "--paginate", f"repos/{REPO}/releases/{rid}/assets?per_page=100", "-q", '.[] | select(.state == "uploaded") | .name'
            ).split()
        )
    except subprocess.CalledProcessError:
        gh(
            "release",
            "create",
            TAG,
            "-R",
            REPO,
            "--latest=false",
            "--title",
            "Mails and Teams files",
            "--notes",
            "The files of mail/ (mail.py, teams.py). An asset's name is a hash of its path in mail/.",
        )
        have = set()
    todo = {asset_name(p.relative_to(MAIL).as_posix()): p for p in MAIL.rglob("*") if p.is_file() and p.suffix != ".json"}
    todo = {name: p for name, p in todo.items() if name not in have}
    with tempfile.TemporaryDirectory() as tmp:
        # gh names an asset after its file: each file is copied under its asset name, 20 to an upload.
        names = list(todo)
        for i in range(0, len(names), 20):
            batch = []
            for name in names[i : i + 20]:
                (Path(tmp) / name).write_bytes(todo[name].read_bytes())
                batch.append(str(Path(tmp) / name))
            gh("release", "upload", TAG, "-R", REPO, "--clobber", *batch)
            print(f"{min(i + 20, len(names))}/{len(names)}", flush=True)
    print(f"{len(todo)} uploaded, {len(have)} were there")


def text_of(m):
    """The mail's own text as HTML, without the mail it quotes (Gmail's "On … wrote:" block, Thunderbird's cite).
    shortcut: only Gmail's and Thunderbird's quote markup is known; another client's quote stays in the post."""
    body = m.get_body(("html", "plain"))
    if body is None:
        return ""
    if body.get_content_type() == "text/plain":
        lines = body.get_content().splitlines()
        cut = next((i for i, l in enumerate(lines) if re.match(r"On .+ wrote:$", l.strip()) or l.startswith(">")), len(lines))
        return "<br>".join(escape(l) for l in lines[:cut]).strip()
    soup = BeautifulSoup(body.get_content(), "html.parser")
    # A Gmail quote has its "On … wrote:" line (gmail_attr); a gmail_quote without one is text pasted from another mail.
    for q in soup.select(".gmail_quote"):
        if q.find(class_="gmail_attr", recursive=False):
            q.decompose()
    for q in soup.select(".moz-cite-prefix, blockquote[type=cite]"):
        q.decompose()
    return str(soup).strip()


def add(folder, page):
    MAIL.mkdir(exist_ok=True)
    added = 0
    for path in sorted(Path(folder).glob("*.eml")):
        m = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        mid = str(m["Message-ID"] or "").strip() or sys.exit(f"{path.name}: no Message-ID")
        key = hashlib.sha1(mid.encode()).hexdigest()[:8]
        if any(MAIL.glob(f"*-{key}")):
            continue
        sent = parsedate_to_datetime(m["Date"])
        out = MAIL / f"{sent.astimezone(timezone.utc):%Y-%m-%d}-{key}"
        out.mkdir()
        files = []
        for a in m.iter_attachments():
            # The file's own name only: a name with a path or a drive cannot write outside the folder.
            name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", a.get_filename() or f"prilog-{len(files) + 1}").strip(" .") or "prilog"
            (out / name).write_bytes(a.get_payload(decode=True) or b"")
            files.append(name)
        refs = list(dict.fromkeys(re.findall(r"<[^>]+>", f"{m['References'] or ''} {m['In-Reply-To'] or ''}")))
        post = dict(
            id=mid,
            refs=refs,
            page=page,
            author=parseaddr(str(m["From"]))[1].split("@")[0].lower(),
            posted=sent.astimezone(timezone.utc).isoformat(),
            when=f"{sent:%d.%m.%Y. %H:%M}",
            title=str(m["Subject"] or ""),
            html=text_of(m),
            files=files,
            sizes={f: (out / f).stat().st_size for f in files},
        )
        (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        added += 1
    print(f"{added} mails added to {MAIL}")


def check():
    q = (
        '<div dir="ltr">Novo<br></div><div class="gmail_quote gmail_quote_container"><div class="gmail_attr">On Mon '
        'wrote:</div><blockquote class="gmail_quote">Staro</blockquote></div>'
    )
    pasted = '<div><div class="gmail_quote"><div dir="ltr">Prepisano</div></div></div>'
    mk = lambda html: email.message_from_string(f"Content-Type: text/html; charset=utf-8\n\n{html}", policy=policy.default)
    assert text_of(mk(q)) == '<div dir="ltr">Novo<br/></div>', text_of(mk(q))
    assert "Prepisano" in text_of(mk(pasted))
    plain = email.message_from_string("Content-Type: text/plain\n\nNovo\n\nOn Mon, X wrote:\n> Staro\n", policy=policy.default)
    assert text_of(plain) == "Novo<br>", text_of(plain)
    assert re.fullmatch(r"[0-9a-f]{20}\.pdf", asset_name("2026-01-01-ab/Резултати 1.PDF")) and asset_name("a/b.tar gz").endswith(".bin")


if __name__ == "__main__":
    check()
    if sys.argv[1:] == ["upload"]:
        upload()
    elif len(sys.argv) == 4 and sys.argv[1] == "add" and re.fullmatch(r"/predmet/[^/]+/[^/]+/", sys.argv[3]):
        add(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
