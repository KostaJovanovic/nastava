# Plan: /knjige/, the books of all subjects (2026-11-16)

Decided with the user, one question at a time. Not started.

## Source

Each subject's faculty page (`subjects.html` in nastava.db, scraped by `scrapers/predmeti.py`) has a "Литература"
section. `book_page()` (`pages/sitegen/clean.py:292`) already splits it on `;` into one book a row. Checked
2026-11-16: 783 of 784 subjects have books, 3,030 entries; only "Стручна пракса М - МОТ" has none. No new scraping.

Not included: ie's department "Literatura" files (`load_sources.py:224`); they are files, not titles, and stay on
the subject pages.

## Steps

1. [ ] Data: `load_knjige(book)` in `pages/sitegen/` builds the list from every subject's `book_page(s["html"])["books"]`.
   - One row per book: merged by ISBN when the entry has one, else by identical text (whitespace-normalised).
     Entries written slightly differently stay separate rows.
   - Each row: the book text, the subjects that list it (name, program, href), and a folded `find` text (book +
     subjects' names and acronyms) for the filter.
   - Order: alphabetical by the entry's text (`azbuka`), which mostly starts with the first author's surname.
   - Subjects with `gone` set: decide while building (probably left out, as in `plan_groups`).
2. [ ] Page: `pages/templates/knjige.html`, written by `build.py` to `/knjige/index.html` like `/link/`.
   - Header (`mh`) with title "Knjige" and a one-line subtitle; `kp_tabs('/knjige/')`.
   - Search: the existing filter bar (`<form data-filter>`, `data-f="find"`, `?q=`; `site.js:454`), rows with
     `data-find`. Latin and Cyrillic both match through the folded text. No new JS.
   - Row: the book text, then links to the subject pages using it.
3. [ ] Link: a third tab in `kp_tabs` (`pages/templates/rows.html:12`): Predmeti | Katedre | Knjige. No sidebar entry.
   - `site.js:276`: map `/knjige/` to `/predmeti/` so the sidebar's "Katedre i predmeti" stays marked.
   - The nav's aria-label "Katedre i predmeti" and the sidebar label stay as they are unless the user says otherwise.
4. [ ] Test: in `test/build_test.py`, two subjects listing the same book (same ISBN, different text) give one row
   with both subjects; a book without ISBN merges only on identical text.
5. [ ] Preview: build outside `pages/.build`; the user reviews and does the real rebuild.

## Open

- Page title and subtitle wording (casual Serbian, see verzije style).
- Whether to show a count of subjects per book in the row.
