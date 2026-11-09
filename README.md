# nastava arhiva

A public archive of nastava.mas.bg.ac.rs, the notice board of Mašinski fakultet in Belgrade: every post (2014–today),
with the schedules and the teachers of www.mas.bg.ac.rs. The attachments link to the faculty's site.
The site is static. It is at https://nastava.masinci.org (also https://nastava.valjdakosta.com). The UI is in Serbian.

Built on Omar Žunić's [dlwms](https://github.com/omznc/dlwms) (the same archive for FIT Mostar): the same
pipeline and site, with new scrapers for phpBB.

## How it works

- `.github/workflows/sync.yml` updates the site on GitHub: `bash ci/deploy.sh forum` every 2 hours by day (06–22 in
  Belgrade), `bash ci/deploy.sh sync` on Monday night. By hand: `gh workflow run sync.yml` (`-f what=sync` for all),
  or the same `ci/deploy.sh` on a PC. A run:
  1. tests the parsers on saved pages (`test/parsers_test.py`) and gets the state (`ci/state.sh pull`);
  2. reads the forum tree and fetches the forums and topics whose counts or last post changed, and again the topics
     with a post in the last 14 days (an edit does not change the counts);
  3. checks the counts, then archives the schedules, the teachers and the subjects. A failure in these does not stop
     the run;
  4. saves the state (`nastava.db`) to the `state` release (`ci/state.sh push`);
  5. builds the static site with Pagefind search, uploads it to the `site` release and starts the `deploy` workflow,
     which only publishes it to GitHub Pages;
  6. sends the web push of the new posts once they are on the site (`ci/push.py`);
  7. exits 1 (a red run) when the count check, a side scraper or the push failed.
- A Cloudflare Worker (`pages/src/index.js`) serves the domain. It gets the pages from GitHub Pages and keeps them in the
  edge cache for a day at most (Pagefind's hashed files: a year). Most pages are stored as only their title and main
  part; the Worker puts them into `shell.html` (head, header, sidebar), which saves about 190 MB on GitHub Pages.
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
- `predmeti.py`: archive the faculty's subject book (all subjects of every program), every subject page, and where
  each subject is in the plans (program, master module, semester, elective slot such as 5.4) into the `subjects` and
  `subject_places` tables. The site has `/predmeti/`, grouped as the plans by default, and a page per subject.
  Both lists (subjects, teachers) can be grouped and sorted in the browser.
- `pages/build.py`: render `nastava.db` as the static site, in the board's layout: the index of smerovi, a page per
  smer and subject (its topics, filtered by text or author in the page), a page per topic of several posts (`/tema/`),
  and a page per post (`/item/`, what search finds). The header stays at the top; the side panel (page links,
  filters by smer and year) fits the screen beside it. A teacher's page links a search of their posts (`/?autor=`).
  Atom feeds for a feed reader: `/feed.xml` (the board's newest posts) and `feed.xml` on each subject page.
  The side panel's "Moji predmeti" gives the followed subjects' feeds as one OPML file, and notifications.
- Notifications (web push): the switch in "Moji predmeti" subscribes the browser (`pages/static/sw.js` shows them; an
  iPhone only from the home screen). The Worker keeps each subscription with its subjects in KV: that is the only
  data the site keeps about a visitor, and it goes with the switch off. After a deploy with a scrape, `ci/deploy.sh`
  runs `ci/push.py send`: once the new posts are on the site, each browser gets one notification for those in its
  subjects. The keys are in `push-secret.json` (git-ignored) and, for sync.yml, in the repository secret `PUSH_SECRET`
  (`gh secret set PUSH_SECRET < push-secret.json`). Lost keys mean new ones and every subscriber turning the switch
  on again.
- `ci/deploy.sh`: scrape (with `sync`), build and publish from this PC. `ci/state.sh`: get and save `nastava.db`.
- `test/parsers_test.py`: the parsers on the saved pages in `test/fixtures/`, no network.
- `test/browser_test.py`: real searches and screenshots in Edge against a running site.
- `save.bat`: git (commit, push, pull), and `deploy [sync]`: commit, push, then `ci/deploy.sh`. `server.bat`: build
  and serve the site on this PC, port 15497, with a QR for phones.

## First run (local, about 6 hours)

    uv run nastava.py sync
    uv run studije.py sync
    uv run nastavnici.py sync
    uv run predmeti.py sync
    uv run nastava.py stats
    gh repo create KostaJovanovic/nastava --public --source . --push
    bash ci/state.sh push

Then turn on GitHub Pages (source: GitHub Actions), publish the site with `bash ci/deploy.sh`, and deploy the Worker:

    cd pages && wrangler deploy

For notifications, once: `uv run ci/push.py keys` (writes `push-secret.json`; its public key goes in `pages/static/site.js`),
`wrangler kv namespace create PUSH` (its id into `pages/wrangler.toml`) and `wrangler secret put PUSH_KEY` (the "key"
from `push-secret.json`), before `wrangler deploy`.

When the attachments are wanted: `uv run documents.py sync`. Old .doc/.xls/.ppt files need LibreOffice (`soffice`) for their text; without it they stay pending and the next
`uv run documents.py extract` on a machine with LibreOffice reads them.
