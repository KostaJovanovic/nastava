# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4"]
# ///
"""The asserts of scrapers/site_files.py (were its __main__ block), no network: uv run test/site_files_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
from site_files import OUT, target  # noqa: E402

assert (
    target("https://ie.mas.bg.ac.rs/data_store/upload/1815_R%C5%A0 2.docx")
    == OUT / "ie.mas.bg.ac.rs" / "data_store" / "upload" / "1815_RŠ 2.docx"
)
assert target("https://cent.mas.bg.ac.rs/a/../x.pdf?id=3").name == "x.pdf_id=3"
