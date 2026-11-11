# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4"]
# ///
"""Mails a teacher sent a subject's students, as posts of that subject (build.py's load_mail): each mail is a folder
mail/<date>-<key>/ with post.json (sender, date, subject line, the text without the quoted mail it answers, the reply
headers) and its attachments, which the site hosts. To and Cc are never read: they are the students' addresses.

Usage: mail.py add <folder of .eml files> <subject page, as /predmet/oas-mi/pumpe-i-ventilatori/>
  add   a mail already here (by Message-ID) is skipped.
"""
import email
import hashlib
import json
import re
import sys
from datetime import timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup

MAIL = Path(__file__).resolve().parent / "mail"


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
        post = dict(id=mid, refs=refs, page=page, author=parseaddr(str(m["From"]))[1].split("@")[0].lower(),
                    posted=sent.astimezone(timezone.utc).isoformat(), when=f"{sent:%d.%m.%Y. %H:%M}",
                    title=str(m["Subject"] or ""), html=text_of(m), files=files)
        (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        added += 1
    print(f"{added} mails added to {MAIL}")


def check():
    q = ('<div dir="ltr">Novo<br></div><div class="gmail_quote gmail_quote_container"><div class="gmail_attr">On Mon '
         'wrote:</div><blockquote class="gmail_quote">Staro</blockquote></div>')
    pasted = '<div><div class="gmail_quote"><div dir="ltr">Prepisano</div></div></div>'
    mk = lambda html: email.message_from_string(f"Content-Type: text/html; charset=utf-8\n\n{html}", policy=policy.default)
    assert text_of(mk(q)) == '<div dir="ltr">Novo<br/></div>', text_of(mk(q))
    assert "Prepisano" in text_of(mk(pasted))
    plain = email.message_from_string("Content-Type: text/plain\n\nNovo\n\nOn Mon, X wrote:\n> Staro\n", policy=policy.default)
    assert text_of(plain) == "Novo<br>", text_of(plain)


if __name__ == "__main__":
    check()
    if len(sys.argv) != 4 or sys.argv[1] != "add" or not re.fullmatch(r"/predmet/[^/]+/[^/]+/", sys.argv[3]):
        sys.exit(__doc__)
    add(sys.argv[2], sys.argv[3])
