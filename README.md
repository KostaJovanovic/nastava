# nastava arhiva

A public archive of nastava.mas.bg.ac.rs, the notice board of Mašinski fakultet in Belgrade: every post (2014–today),
with the schedules and the teachers of www.mas.bg.ac.rs. The attachments link to the faculty's site.
The site is static. It is at https://masinci.org (https://nastava.masinci.org and https://nastava.valjdakosta.com
redirect there). The UI is
in Serbian. Search engines may index its pages (subjects, smerovi, teachers, news, schedules, lists), but not the
posts (`/item/`, `/tema/`) or the cent pages: those name students (exam results). Each page has a description,
link-preview tags, a canonical URL on the main domain (also for its copy on github.io), and schema.org data (news,
teachers); `build.py` writes `sitemap.xml` (the indexed pages) and `robots.txt`.

Built on Omar Žunić's [dlwms](https://github.com/omznc/dlwms) (the same archive for FIT Mostar): the same
pipeline and site, with new scrapers for phpBB.

## How it works

- `.github/workflows/sync.yml` updates the site on GitHub (`bash ci/deploy.sh auto SLOT`, morning to late). The board and
  the news are scraped five times a day, at 7:17, 11:17, 15:17, 19:17 and 22:17 Belgrade time (an hour later in summer): the
  Worker's cron (`pages/wrangler.toml`) starts each run, as GitHub's own schedule started them hours late.
  `ci/plan.py` reads the exam dates from the faculty's teaching calendar (the PDF `studije.py` archives): the morning
  run also takes the schedule pages on the 1st of the month and on the first day of each registration and exam
  period, and the teachers and the subjects on 1 October.
  A run that finds nothing new stops before saving and publishing. By hand, on GitHub:
  `gh workflow run sync.yml -f what=forum` (or `"forum studije"`, `sync`); on a PC: `bash ci/deploy.sh forum`
  (or `forum studije`, `sync`), which first gets the saved state. A run:
  1. gets the state (`ci/state.sh pull`) and tests the parsers on saved pages (`test/parsers_test.py`);
  2. reads the forum tree and fetches the forums and topics whose counts or last post changed, and again the topics
     with a post in the last 14 days (an edit does not change the counts);
  3. checks the counts, archives the news and the subjects' pages on cent.mas.bg.ac.rs, and the schedules, the
     teachers and the subjects when they are due (the departments' sites only with `sync`). A failure in these does
     not stop the run;
  4. saves the state (`nastava.db`) to the `state` release (`ci/state.sh push`);
  5. builds the static site with Pagefind search, uploads it to the `site` release and starts the `deploy` workflow,
     which only publishes it to GitHub Pages;
  6. sends the web push of the new posts once they are on the site (`ci/push.py`);
  7. exits 1 (a red run, GitHub's e-mail) when the count check, a scraper, the push or the calendar check failed.
- A Cloudflare Worker (`pages/src/index.js`) serves the domain. It gets the pages from GitHub Pages and keeps them in the
  edge cache for a day at most (Pagefind's hashed files: a year). Most pages are stored as only their title and main
  part; the Worker puts them into `shell.html` (head, header, sidebar), which saves about 190 MB on GitHub Pages.
- The attachments and images link straight to nastava.mas.bg.ac.rs. The site does not host them. The mails' and
  Teams files (`mail/`) are assets of the GitHub release `mail`, which the Worker serves under `/files/`. The local
  `files/` folder keeps a copy of each one; dlwms's `release_files.py` and Worker `/files/` route (in `ref/dlwms`)
  can host them later.
- Search finds Cyrillic and Latin alike: the index holds the text in Latin without diacritics, and the search box
  converts the query the same way ("распоред", "raspored", "rasporedjen").
- Nothing is deleted: a post that disappears from the board stays in the archive.

## Files

- `scrapers/nastava.py`: scrape the forum tree and the posts into `nastava.db`. `stats` compares the board's counts with the
  stored rows and exits 1 when posts are missing.
- `scrapers/documents.py`: download the attachments into `files/` and extract their text. Not run for now (not in the Action);
  `stats` writes `files/no-text.txt` (scans: need OCR).
- `scrapers/studije.py`: archive the schedule pages of www.mas.bg.ac.rs (kalendar nastave, raspored predavanja, raspored ispita),
  the rest of its wiki that no other scraper keeps (the site shows only the pages a student needs, `SHOWN`: enrollment,
  re-enrollment, payments, accounts, in Linkovi)
  and every file they link, into `nastava.db`. A changed page or file adds a version; the site shows the newest and
  serves the files itself (PDFs open in the browser).
- `scrapers/vesti.py`: archive the news of vesti.mas.bg.ac.rs (WordPress REST API: each run lists every post, and reads the new or changed ones) into the
  `vesti` and `vesti_categories` tables; a changed post adds a version, a deleted one stays, marked gone. Images and
  files stay on the news site (linked). The site has `/vesti/` (a year per page, filter by category), a page per news
  post (which search finds; the header's scope "Vesti"), the newest five on the home page, and `/vesti/feed.xml`.
- `scrapers/cent.py`: archive the subject pages of cent.mas.bg.ac.rs (Катедра за производно машинство): each page as shown
  (a version per change) and each notice apart, into `cent_pages` and `cent_notices`. The files stay linked on cent.
  The site puts each subject's notices among its topics with a "cent" mark, and its pages (predavanja, rezultati, …)
  under `/predmet/…/cent/`; a subject the board has no forum for gets a page too.
- `scrapers/katedre.py`: the announcements of the departments' own sites (ie, meh, bmi, pt, fluidi, hidro, ciah): only the
  pages that have them (pt's news: its JSON API), each as shown (a version per change) into `katedre_pages`, and each
  notice apart (a reader per site) into `katedre_notices`. The site puts the notices among the topics with the site's
  mark (as cent's, with a web push): a subject page's (ie, fluidi) on that subject, a department's on its forum under
  Katedre (made for bmi and ciah), or on the subject its title names; ie's "Literatura" is on the subject's page as a
  list of files. The files stay linked. Not the rest of a site, the Moodles (a login), etc, motori, ppm (no
  announcements) nor omk, geotermal, au, tmm (no answer).
- `scrapers/mail.py`: mails a teacher sent a subject's students (exported from webmail as .eml), in `mail/`: a folder per
  mail with `post.json` (sender, date, subject line, the text without the quoted mail) and its attachments. To and Cc
  are never read. The site shows them as that subject's board posts (a "Re:" in its mail's topic). Git keeps only the
  `.json` files; `mail.py upload` puts the attachments (and teams.py's files) in the release `mail` (an asset per
  file, named by a hash of its path). Keep a copy of `mail/` elsewhere (OneDrive). Done by hand, not in the Action.
- `scrapers/teams.py`: the posts of the faculty's Teams classes into `mail/`, in the same form: each thread a teacher started,
  with its replies (a student's is "Student #N", numbered per thread, with no name, index, e-mail or file of theirs),
  and the rest of each class's SharePoint library as the subject's "Materijal sa Teams-a". `tools/teams/teams-export.js` reads
  the posts in the browser.
- `scrapers/nastavnici.py`: archive the teacher list of www.mas.bg.ac.rs, every profile (katedra, kabinet, mejl, telefon,
  termini, predmeti, bibliografija) and the emeritus page, into the `teachers` and `teacher_subjects` tables.
  The site has `/nastavnici/` (filter by name, subject, katedra, zvanje) and a page per teacher with their forum posts;
  a forum author is linked to a teacher when the username is the e-mail before @. `scrapers/nastavnici_istorija.py`
  (once, by hand): the teachers who left before the archive began, from the Wayback Machine and masinac.org.
- `scrapers/predmeti.py`: archive the faculty's subject book (all subjects of every program), every subject page, and where
  each subject is in the plans (program, master module, semester, elective slot such as 5.4) into the `subjects` and
  `subject_places` tables. The site has `/predmeti/`, grouped as the plans by default, and a page per subject.
  Both lists (subjects, teachers) can be grouped and sorted in the browser.
- `scrapers/common.py`: what the scrapers share (the database, the HTTP session and its run log, file links);
  `scrapers/translit.py`: Serbian Cyrillic ↔ Latin, for the scrapers and `build.py` (`pismo.js` has the browser's
  copy). A scraper imports no other scraper but the one of its own source.
- `data/`: the teachers' history, photos, biographies and summaries (`nastavnici-*.jsonl`), gathered by hand and
  read by `build.py`. `docs/`: the plans. `tools/teams/`: the browser-console scripts for Teams.
- `pages/build.py`: render `nastava.db` as the static site, in the board's layout: the index of smerovi, a page per
  smer and subject (its topics, filtered by text or author in the page), a page per topic of several posts (`/tema/`),
  and a page per post (`/item/`, what search finds). The header stays at the top; the side panel (page links,
  filters by smer and year) fits the screen beside it. A teacher's page links a search of their posts (`/?autor=`).
  Atom feeds for a feed reader: `/feed.xml` (the board's newest posts) and `feed.xml` on each subject page.
  The side panel's "Obaveštenja" links `/mojipredmeti/`: step 1 picks the subjects; step 2 has the notifications'
  switch, per subject the teachers whose posts notify (none: all), and the subjects' feeds as one OPML file.
- Notifications (web push): the switch on `/mojipredmeti/` subscribes the browser (`pages/static/sw.js` shows them; an
  iPhone only from the home screen). The Worker keeps each subscription with its subjects and picked teachers in KV,
  and it goes with the switch off; for `/statistika/`'s count of them, D1 keeps each one's push address too
  (`push_subs`, gone with it). Besides it the site keeps only a visitor's IP, three days, for the visitor counter on
  `/statistika/` (D1, `pages/schema.sql`; counted like valjdakosta.com's, each IP once per three days). After a deploy with a scrape, `ci/deploy.sh`
  runs `ci/push.py send`: once the new posts are on the site, each browser gets one notification for those in its
  subjects. The keys are in `push-secret.json` (git-ignored) and, for sync.yml, in the repository secret `PUSH_SECRET`
  (`gh secret set PUSH_SECRET < push-secret.json`). Lost keys mean new ones and every subscriber turning the switch
  on again.
- `ci/deploy.sh`: scrape, build and publish (`auto SLOT`, `sync`, `forum [studije] [nastavnici] [predmeti]`, or
  nothing: only build and publish). `ci/plan.py`: what a scheduled run does, from the calendar; the database
  fingerprint. `ci/state.sh`: get and save `nastava.db`.
- The run log: every `ci/deploy.sh` run, here and on GitHub, adds a JSON line to `runs.jsonl` on the `runs` release
  (`ci/runs.py`): each step's time, each scraper's requests per site (errors, retries, ETag / Last-Modified support,
  the slowest pages), what was new, how long new posts took to be found and to be on the site, the sizes, the
  notifications, and on GitHub how late the run started. `uv run ci/runs.py report` sums it up; `uv run ci/runs.py
  schedule` replays the board's posts since 2022 against the schedule in use and the best 2–6 runs a day per season.
- `test/parsers_test.py`: the parsers on the saved pages in `test/fixtures/`, no network.
- `test/worker_test.mjs`: the Worker's page join, push subscriptions and `/files/` paths, no network
  (`node --test test/worker_test.mjs`, before `wrangler deploy`).
- `test/browser_test.py`: real searches and screenshots in Edge against a running site.
- `save.bat`: git (commit, push, pull), and `deploy [sync]`: commit, push, then `ci/deploy.sh`. `server.bat`: build
  and serve the site on this PC, port 15497, with a QR for phones.

## First run (local, about 6 hours)

    uv run scrapers/nastava.py sync
    uv run scrapers/studije.py sync
    uv run scrapers/vesti.py sync
    uv run scrapers/cent.py sync
    uv run scrapers/nastavnici.py sync
    uv run scrapers/predmeti.py sync
    uv run scrapers/nastava.py stats
    gh repo create KostaJovanovic/nastava --public --source . --push
    bash ci/state.sh push

Then turn on GitHub Pages (source: GitHub Actions), publish the site with `bash ci/deploy.sh`, and deploy the Worker:

    cd pages && wrangler deploy

For notifications, once: `uv run ci/push.py keys` (writes `push-secret.json`; its public key goes in `pages/static/site.js`),
`wrangler kv namespace create PUSH` (its id into `pages/wrangler.toml`) and `wrangler secret put PUSH_KEY` (the "key"
from `push-secret.json`), before `wrangler deploy`. For the visitor counter, once: `wrangler d1 create nastava` (its id
into `pages/wrangler.toml`) and `wrangler d1 execute nastava --remote --file schema.sql`.

When the attachments are wanted: `uv run scrapers/documents.py sync`. Old .doc/.xls/.ppt files need LibreOffice (`soffice`) for their text; without it they stay pending and the next
`uv run scrapers/documents.py extract` on a machine with LibreOffice reads them.

To add mails: in webmail (RainLoop) open each mail, ▾ next to Reply → "Download as .eml", into one folder; then
`uv run scrapers/mail.py add <folder> /predmet/<smer>/<subject>/` (the subject page's URL; in Git Bash prefix
`MSYS_NO_PATHCONV=1`), `uv run scrapers/mail.py upload`, and commit `mail/`. A mail already there is skipped.

To add Teams posts: open teams.microsoft.com in a browser, paste `tools/teams/teams-export.js` into the DevTools console (Firefox:
Ctrl+B for the multi-line editor) and run it: it saves `teams-export.json` (every channel's messages, read with the
page's own sign-in; Graph needs an admin's consent for them). Then `tools/teams/teams-files.js` the same way: each class's
SharePoint library as a zip in Downloads (its `CLASSES` list is teams.py's group ids); the sign-in never leaves the
page. A new class goes in `CLASSES` (its group id → subject page; in both files), a new teacher in
`TEACHERS` (their Teams account → board username), a student's name written in a reply with no index next to it in
`NAMED`; then `uv run scrapers/teams.py add <teams-export.json> <zip folder>`, read the students' replies in `mail/` for names
it missed, `uv run scrapers/mail.py upload`, and commit `mail/`.

## License

The code is under the [GNU GPL v3](LICENSE). It covers the code only: the archived posts, news, schedules, files and
photos belong to their authors and the faculty. The parts taken from dlwms are under it with Omar Žunić's consent.
