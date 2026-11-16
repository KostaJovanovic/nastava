# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4", "pymupdf", "requests"]
# ///
"""The asserts of scrapers/mail.py (were its __main__ block), and of the release files they share with documents.py
(common.thumbnail, documents.release_base), no network: uv run test/mail_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
import email  # noqa: E402
import re  # noqa: E402
from email import policy  # noqa: E402
from common import THUMB_WIDTH, thumbnail  # noqa: E402
from documents import release_base  # noqa: E402
from mail import asset_name, text_of, unique  # noqa: E402


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
    # Two attachments with one name (Gmail's inline image.png): both kept.
    assert unique("image.png", ["image.png", "image (2).png"]) == "image (3).png" and unique("prilog", ["prilog"]) == "prilog (2)"
    assert unique("a.pdf", []) == "a.pdf"
    # A thumbnail: a PDF's first page, THUMB_WIDTH wide; none for a page under a .pdf name or another kind.
    import pymupdf

    doc = pymupdf.open()
    doc.new_page(width=200, height=300).insert_text((20, 50), "Rok")
    jpg = pymupdf.Pixmap(thumbnail("a.PDF", doc.tobytes()))
    assert (jpg.width, jpg.height) == (THUMB_WIDTH, 360), (jpg.width, jpg.height)
    assert thumbnail("a.pdf", b"<html>x</html>") is None and thumbnail("a.docx", b"PK") is None and thumbnail("a.png", b"x") is None
    assert [release_base(p) for p in ("2026-10-01T00:00:00+00:00", "2027-09-30T22:00:00+00:00", "2027-10-02T00:00:00")] == [
        "files-2026-2027",
        "files-2026-2027",
        "files-2027-2028",
    ]


check()
