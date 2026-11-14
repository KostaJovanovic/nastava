# /// script
# requires-python = ">=3.11"
# dependencies = ["beautifulsoup4"]
# ///
"""The asserts of scrapers/mail.py (were its __main__ block), no network: uv run test/mail_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
import email  # noqa: E402
import re  # noqa: E402
from email import policy  # noqa: E402
from mail import asset_name, text_of  # noqa: E402


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


check()
