# Plan: search inside the attachments (2026-11-18)

Decided with the user, one question at a time. Not started; the open points below come first.

## What it does

A word that is only inside an attachment (a PDF, xlsx, csv, docx, …) finds the post that has it. The text goes into
the post's indexed copy (`mark_for_pagefind`, `pages/sitegen/output.py`), so a match opens the post page, which
links the file as now (the faculty's link for older files, the site's own since 1 October 2026).

## Decided

- Every format `scrapers/documents.py` can read (pdf, docx, pptx, xlsx, zip, rar; doc, xls, ppt through
  LibreOffice; csv and txt as text). Easy to add: 7z and tar.gz (libarchive or 7-Zip), ods and odt, ppsx and pps.
  No text: CAD files, video, exe.
- New OCR only for the files since 1 October 2026 (the ones the site hosts).
- The OCR already done (one-off, 2026-11-18, `work/ocr/ocr_images.py`) is used too: `files/ocr.jsonl`, 2,352
  readings by PaddleOCR-VL 1.5 (1,759 images, loose and inside archives; 593 pages of 62 scanned or TeX-encoded
  PDFs). Only the good readings go into search: 5 words or more (formulas dropped), at least 80% of them words the
  archive's own text has (`work/ocr/good_ocr.py`, a list in `work/ocr/good_ocr.jsonl`): 553 of the 2,352, the
  printed pages. Below that is mostly handwriting, half read; nobody re-reads it by hand.
- 20784 (`Predavanja - Elektromagnetika 2.pdf`) was broken in the faculty's own copy; `files/20784/` now holds the
  intact copy of 16751 (the broken one: `work/redl-20784/fresh.pdf`).

## Found (2026-11-18)

- `files/` has 14,309 attachments (7.32 GiB), but `documents` knows only the 300 hosted ones (path, text); the
  others have no row with a path yet.
- PDFs, from `work/ocr/pdf_scores.py`: 542 have little or no text (scans); 789 are in the TeX Serbian font encoding
  (q for č, x for š, ǌ for nj, and ž ć đ dropped: only OCR gets them back); 420 have split accents (`Maˇsinski`),
  which a text fix mends (ˇs → š, ´c → ć). Symbol fonts in formulas read fine.
- This PC has neither LibreOffice nor libarchive, so doc, xls, ppt and rar give no text here yet.

- The first 1,500 characters of each file only (the user: no bloat). The estimate: the index from 97 MB to
  ~180 MB, the site from 414 MB to ~500 MB; 3,000 would nearly double that. A file posted again is indexed once,
  in the first post that has it.
- A result is the post, as any other: no mark that the match is in a file.
- The storage plan (`PLAN-storage.md`) comes first.

## Open

- The real size, from a test build outside `pages/.build`.
- The OCR of new files: PaddleOCR runs on this PC's graphics card, the GitHub runs have none.
