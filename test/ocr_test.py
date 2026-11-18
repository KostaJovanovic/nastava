# /// script
# requires-python = ">=3.11"
# dependencies = ["pymupdf", "pillow"]
# ///
"""The asserts of scrapers/ocr.py (what to read, the clean-ups, which readings to keep), no model and no network:
uv run test/ocr_test.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scrapers"))
import pymupdf  # noqa: E402
from ocr import cut_line_loops, cut_loops, fix_cyrillic, garbled, good, pages, words  # noqa: E402


def pdf(text, n=1):
    doc = pymupdf.open()
    for _ in range(n):
        doc.new_page().insert_text((50, 72), text)
    return doc.tobytes()


def check():
    assert cut_loops("y = 1 y = 1 y = 1 y = 1 kraj") == "y = 1 y = 1 kraj"
    assert cut_line_loops(["a", "b", "a", "b", "a", "b", "a", "c"]) == ["a", "b", "a", "b", "a", "c"]
    assert cut_line_loops(["x", "x", "y"]) == ["x", "x", "y"]
    assert fix_cyrillic("ЛЬУБАВ и нешто") == "ЉУБАВ и нешто" and fix_cyrillic("tačka") == "tačka"

    # Formulas (LaTeX, as the model writes them) are no words; Cyrillic folds to Latin, as search does.
    assert words(r"Odrediti \(\frac{dy}{dx}\) integral $x^2$") == ["odrediti", "integral"]
    assert words("Испит из механике") == ["ispit", "mehanike"]
    vocab = {"ispit", "iz", "mehanike", "prvi", "kolokvijum", "zadatak", "resenje"}
    assert good("Prvi kolokvijum iz mehanike, zadatak i resenje", vocab)
    assert not good("U nasew priweu je zadatak", vocab)  # handwriting, half read
    assert not good("Prvi kolokvijum", vocab)  # too few words to count

    # A PDF's text: a scan (almost none), the TeX Serbian encoding (q for č), a Cyrillic table with a Latin name, fine.
    assert garbled("", 3) and garbled("12", 1)
    assert garbled("Rexiti jednaqinu i nai taqku preseka " * 10, 1)
    assert not garbled("ФЕИ XUN Адамовић Павле Алексић Драган Андрејић Душан " * 10, 1)
    assert not garbled("Odrediti jednačinu ravni koja sadrži tačke " * 10, 1)

    assert pages("7/slika.JPG", b"img", None) == [b"img"]
    assert pages("7/tabela.xlsx", b"x", "nesto") == []
    fine = "Odrediti jednacinu ravni koja sadrzi tacke A i B. " * 3
    assert pages("7/rok.pdf", pdf(fine, 2), fine * 2) == []
    scan = pages("7/sken.pdf", pdf("", 2), "")
    assert len(scan) == 2 and all(p[:2] == b"\xff\xd8" for p in scan)  # each page as a JPEG


check()
print("ocr_test ok")
