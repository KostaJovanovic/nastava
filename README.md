# nastava arhiva

A public archive of nastava.mas.bg.ac.rs, the notice board of Mašinski fakultet in Belgrade: every post (2014–today),
with the schedules and the teachers of www.mas.bg.ac.rs. The attachments link to the faculty's site.
The site is static. It is at https://nastava.valjdakosta.com. The UI is in Serbian.

Built on Omar Žunić's [dlwms](https://github.com/omznc/dlwms) (the same archive for FIT Mostar): the same
pipeline and site, with new scrapers for phpBB.

## How it works

- A GitHub Action (`.github/workflows/sync.yml`) runs each day:
  1. It tests the parsers on saved pages (`test/parsers_test.py`).
  2. It gets the state (`nastava.db`) from the `state` release.
  3. It reads the forum tree and fetches the forums and topics whose counts or last post changed, and again the topics
     with a post in the last 14 days (an edit does not change the counts).
  4. It checks the counts, then archives the schedules and the teachers. A failure in these does not stop the run.
  5. It saves the state, builds the static site with Pagefind search and deploys it to GitHub Pages.
  6. The run ends red (GitHub sends an e-mail) when the count check or a side scraper failed.
- A Cloudflare Worker (`pages/src/index.js`) serves the domain. It gets the pages from GitHub Pages and keeps them in the
  edge cache for a day at most (Pagefind's hashed files: a year).
- The attachments and images link straight to nastava.mas.bg.ac.rs. The site does not host them. The local
  `files/` folder keeps a copy of each one; dlwms's `release_files.py` and Worker `/files/` route (in `ref/dlwms`)
  can host them later.
- Search finds Cyrillic and Latin alike: the index holds the text in Latin without diacritics, and the search box
  converts the query the same way ("распоред", "raspored", "rasporedjen").
- Nothing is deleted: a post that disappears from the board stays in the archive.

## Files

- `nastava.py`: scrape the forum tree and the posts into `nastava.db`. `stats` compares the board's counts with the
  stored rows and exits 1 when posts are missing.
- `documents.py`: download the attachments into `files/` and extract their text. Not run for now (not in the Action);
  `stats` writes `files/no-text.txt` (scans: need OCR).
- `studije.py`: archive the schedule pages of www.mas.bg.ac.rs (kalendar nastave, raspored predavanja, raspored ispita)
  and every file they link, into `nastava.db`. A changed page or file adds a version; the site shows the newest and
  serves the files itself (PDFs open in the browser).
- `nastavnici.py`: archive the teacher list of www.mas.bg.ac.rs, every profile (katedra, kabinet, mejl, telefon,
  termini, predmeti, bibliografija) and the emeritus page, into the `teachers` and `teacher_subjects` tables.
  The site has `/nastavnici/` (filter by name, subject, katedra, zvanje) and a page per teacher with their forum posts;
  a forum author is linked to a teacher when the username is the e-mail before @.
- `pages/build.py`: render `nastava.db` as the static site, in the board's layout: the index of smerovi, a page per
  smer and subject (its topics, filtered by text or author in the page), a page per topic of several posts (`/tema/`),
  and a page per post (`/item/`, what search finds). The header stays at the top; the side panel (page links,
  filters by smer and year) fits the screen beside it. A teacher's page links a search of their posts (`/?autor=`).
- `ci/state.sh`: get and save `nastava.db` for the Action.
- `test/parsers_test.py`: the parsers on the saved pages in `test/fixtures/`, no network.
- `test/browser_test.py`: real searches and screenshots in Edge against a running site.
- `save.bat`: git (commit, push, pull). `server.bat`: build and serve the site on this PC.

## First run (local, about 6 hours)

    uv run nastava.py sync
    uv run studije.py sync
    uv run nastavnici.py sync
    uv run nastava.py stats
    gh repo create KostaJovanovic/nastava --public --source . --push
    bash ci/state.sh push

Then turn on GitHub Pages (source: GitHub Actions), run the `sync` workflow once, and deploy the Worker:

    cd pages && wrangler deploy

When the attachments are wanted: `uv run documents.py sync`. Old .doc/.xls/.ppt files need LibreOffice (`soffice`) for their text; without it they stay pending and the next
`uv run documents.py extract` on a machine with LibreOffice reads them.
