# /// script
# requires-python = ">=3.11"
# dependencies = ["requests", "beautifulsoup4", "pymupdf", "python-docx", "python-pptx", "openpyxl", "libarchive-c"]
# ///
"""The asserts of scrapers/documents.py's file store (files/blobs + files/index.sqlite), in a temporary folder, no
network: uv run test/documents_test.py"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = tempfile.mkdtemp()
os.environ["FILES"] = tmp  # documents.py reads it on import
sys.path.insert(0, str(ROOT / "scrapers"))
import documents  # noqa: E402
from documents import BLOBS, extract_file, file_at, store  # noqa: E402


def check():
    # A file found the old way (files/<id>/<name>) while it has no index row: a GitHub run, a run mid-move.
    Path(tmp, "5").mkdir()
    Path(tmp, "5", "a.txt").write_text("staro", encoding="utf-8")
    assert file_at("5/a.txt") == Path(tmp, "5/a.txt")

    data = b"ispitni rok"
    digest = hashlib.sha256(data).hexdigest()
    store("7/Rok 1.TXT", data)
    store("9/Rok 1 (2).txt", data)  # the same file posted again: one copy, two paths
    assert file_at("7/Rok 1.TXT") == file_at("9/Rok 1 (2).txt") == BLOBS / digest[:2] / f"{digest}.txt"
    assert file_at("7/Rok 1.TXT").read_bytes() == data
    assert len(list(BLOBS.glob("*/*"))) == 1 and not list(BLOBS.glob("*/*.part"))

    # The old place no longer matters once a path is indexed; a re-download replaces its row, not the other's.
    store("5/a.txt", b"novo")
    assert file_at("5/a.txt").read_bytes() == b"novo" and Path(tmp, "5/a.txt").read_text(encoding="utf-8") == "staro"
    store("7/Rok 1.TXT", b"izmenjeno")
    assert file_at("7/Rok 1.TXT").read_bytes() == b"izmenjeno" and file_at("9/Rok 1 (2).txt").read_bytes() == data

    assert extract_file((9, "9/Rok 1 (2).txt")) == (9, "ispitni rok", None)
    assert documents.blob_name("ab" + "0" * 62, "x.tar gz") == "ab/ab" + "0" * 62


check()
print("documents_test ok")
