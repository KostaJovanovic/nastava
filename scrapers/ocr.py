"""OCR on this PC's graphics card: PaddleOCR-VL 1.5 in llama-server, as ReVision runs it (the prompt "OCR:", four
images at once, at most 1920 px). For documents.py ocr (save.bat ocr); a GitHub run has no card and no model, so
available() is False there. The paths: OCR_SERVER (llama-server.exe) and OCR_MODELS (the folder of the model)."""

import base64
import io
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from translit import fold

SERVER = Path(os.getenv("OCR_SERVER", r"J:\ReVision-data\llama\llama-server.exe"))
MODELS = Path(os.getenv("OCR_MODELS", r"J:\ReVision-data\models\paddleocr-vl"))
PORT = 8091
URL = f"http://127.0.0.1:{PORT}"
PX = 1920
IMAGES = (".jpg", ".jpeg", ".png")


def available():
    return SERVER.exists() and (MODELS / "PaddleOCR-VL-1.5.gguf").exists()


class Server:
    """with Server(): llama-server runs for the block."""

    def __enter__(self):
        args = [str(SERVER), "-m", str(MODELS / "PaddleOCR-VL-1.5.gguf"), "--mmproj",
                str(MODELS / "PaddleOCR-VL-1.5-mmproj.gguf"), "--chat-template-file", str(MODELS / "chat_template.jinja"),
                "--port", str(PORT), "--host", "127.0.0.1", "-c", "32768", "-ngl", "99", "--jinja", "-np", "4"]
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(180):
            try:
                urllib.request.urlopen(URL + "/health", timeout=2)
                return self
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("llama-server exited")
                time.sleep(1)
        self.proc.kill()
        raise RuntimeError("llama-server did not start in 3 minutes")

    def __exit__(self, *_):
        self.proc.kill()


def shrink(data):
    """JPEG at most PX on the long side (the model reads small print; bigger only costs time)."""
    from PIL import Image

    im = Image.open(io.BytesIO(data))
    if max(im.size) <= PX and im.format in ("JPEG", "PNG") and im.mode in ("RGB", "L"):
        return data
    im = im.convert("RGB")
    im.thumbnail((PX, PX))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def read(image):
    """The text of one image (bytes), cleaned. Needs a Server."""
    data = shrink(image)
    kind = "png" if data[:4] == b"\x89PNG" else "jpeg"
    url = f"data:image/{kind};base64,{base64.b64encode(data).decode()}"
    body = dict(messages=[dict(role="user", content=[dict(type="image_url", image_url=dict(url=url)),
                                                     dict(type="text", text="OCR:")])],
                temperature=0, max_tokens=3000)
    req = urllib.request.Request(URL + "/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        text = json.load(r)["choices"][0]["message"].get("content") or ""
    lines = [fix_cyrillic(cut_loops(line)) for line in text.splitlines() if line.strip()]
    return "\n".join(cut_line_loops(lines))


# cut_loops and fix_cyrillic: as ReVision's studio/images.py
def cut_loops(text):
    """A small model sometimes repeats a word or a phrase until the answer limit: kept twice."""
    return re.sub(r"((?:\S+\s+){1,6}?)\1{2,}", r"\1\1", " ".join(text.split()) + " ").strip()


def cut_line_loops(lines):
    """The same loop over whole lines (a group of 1-6 lines repeated): kept twice."""
    joined = "".join(line + "\n" for line in lines)
    return re.sub(r"((?:[^\n]*\n){1,6}?)\1{2,}", r"\1\1", joined).splitlines()


RU = "йЙяЯьЬыЫэЭёЁъЪ"


def fix_cyrillic(text):
    """PaddleOCR-VL writes some Serbian letters as the nearest Russian ones (ЛЬ=Љ, НЬ=Њ, ТЬ=Ћ, Й=Ј, …)."""
    if not any(c in RU for c in text):
        return text

    def word(m):
        w = m.group(0)
        up = w.isupper()
        for a, b in (("ль", "љ"), ("нь", "њ"), ("ть", "ћ"), ("й", "ј"), ("э", "ј"), ("ё", "је"), ("ы", "и"), ("ъ", "")):
            w = re.sub(a, b.upper() if up else b, w, flags=re.I)
        w = re.sub("я(?=[аеиоуАЕИОУ])", "Ј" if up else "ј", w, flags=re.I)
        w = re.sub("я", "ЈА" if up else "ја", w, flags=re.I)
        return re.sub("ь", "", w, flags=re.I)

    return re.sub(r"[Ѐ-ӿ]+", lambda m: word(m) if any(c in RU for c in m.group(0)) else m.group(0), text)


# ---------- what to read, and which readings to keep ----------

WORD = re.compile(r"[a-z]{3,}")
MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)|\\\[.*?\\\]|\\[a-zA-Z]+", re.S)


def words(text):
    """The words of a text as search folds them, formulas (LaTeX, as the model writes them) left out."""
    return WORD.findall(fold(MATH.sub(" ", text)))


def vocabulary(db):
    """Every word the archive's own text has at least twice (once may be a typo)."""
    import html

    count = {}
    for table in ("posts", "vesti", "subjects", "cent_notices", "katedre_notices"):
        cols = [r[1] for r in db.execute(f"pragma table_info({table})") if r[2].upper() == "TEXT"]
        if not cols:
            continue
        for row in db.execute(f"select {', '.join(cols)} from {table}"):
            for value in row:
                for w in words(html.unescape(re.sub(r"<[^>]+>", " ", value or ""))):
                    count[w] = count.get(w, 0) + 1
    return {w for w, n in count.items() if n >= 2}


def good(text, vocab):
    """Good enough for search (checked on 2,352 readings, 2026-11-18): 5 words or more, 80% of them known. Below it
    is mostly handwriting, half read."""
    ws = words(text)
    return len(ws) >= 5 and sum(w in vocab for w in ws) >= 0.8 * len(ws)


def garbled(text, pages):
    """A PDF's text layer worth replacing by OCR: under 50 characters a page (a scan), or the TeX Serbian font
    encoding (q for č, ǌ for nj; ž ć đ dropped), in a mostly Latin text."""
    text = text or ""
    if len(text.strip()) < 50 * pages:
        return True
    latin = re.findall(r"[A-Za-zǈǉǋǌ]{3,}", text)
    if len(latin) <= len(re.findall(r"[Ѐ-ӿ]{3,}", text)):
        return False
    return bool(re.search("[ǇǈǉǊǋǌ]", text)) or sum(bool(re.search(r"q(?!u)", w, re.I)) for w in latin) > 0.01 * len(latin)


def pages(path, data, text):
    """The images to OCR for one attachment: an image itself; a PDF's pages when its text is garbled; else none."""
    name = path.lower()
    if name.endswith(IMAGES):
        return [data]
    if not name.endswith(".pdf"):
        return []
    import pymupdf

    with pymupdf.open(stream=data, filetype="pdf") as doc:
        if doc.page_count > 300 or not garbled(text, doc.page_count):  # shortcut: a scanned book over 300 pages is left out
            return []
        out = []
        for page in doc:
            zoom = PX / max(page.rect.width, page.rect.height, 1)
            out.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("jpeg", jpg_quality=90))
        return out
