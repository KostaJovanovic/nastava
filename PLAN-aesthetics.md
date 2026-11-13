# Plan: aesthetics round (2026-11-13)

Decided with the user, one question at a time. Done items are marked.

1. [x] Raspored tabs: `OAS - MI`, `OAS - ITM`, `MAS - MI`, `MAS - IND4.0`, `DAS` (950651c).
2. [x] Header search: subject rows show their katedra's icon, katedre found by initials (7b4a1c3).
   [ ] Subjects with no katedra icon show the book icon.
3. Teacher page:
   [~] Biography section (nastavnici-sazetak.jsonl; batch 1 = OMK, 12 teachers, ecfc5c5; sources dumped with
       %TEMP%\bios\dossier.py <repo> <katedra part>; next batches by katedra after the user reviews) above the forum posts: ~2 paragraphs per teacher, written by Claude once from the
       teacher's sources (monograph, faculty profile, old-site card, history), saved to a JSONL, done in batches the
       user reviews. Example accepted for Tatjana Lazović-Kapor (education/career; research/teaching/books/awards).
   [x] (5fffaf7) Bibliography as its own section: the repository's Radovi and the faculty profile's Bibliografija merged into
       one list, deduped by DOI/title; entry = title (bold), authors (teacher highlighted), journal · year · M-badge,
       DOI link; by year, newest 10, rest behind "Prikaži još".
4. [x] Linkovi: Studentski webmail before Predmeti in Izdvojeno's small cards (950651c).
5. [x] (the user's Claude Design PNGs, as they are) OG images, sections only (og, -predmeti, -nastavnici, -raspored, -vesti, -arhiva): poster style, huge
       left-aligned title cropped at the edge, one strong color per section, small "nastava" logo, one-line
       subtitle. Fonts vary per poster: playful, bold, heavy, fitting the site. Show previews before replacing.
       Status: a first version is in og.html (uncommitted, fonts in og-fonts/), previews in %TEMP%\ogprev. The user
       is designing them in Claude Design from %TEMP%\ogprev\BRIEF.md; port what comes back into og.html.
6. [x] (d632c0e; departments table via `nastavnici.py departments`) A local page per katedra from www.mas.bg.ac.rs/organizacija/katedre/<id> (store the page; nastavnici.py
       fetches it already), with a link to the katedra's own site, its teachers as cards, its subjects, its latest
       notices. Katedra links (search, cards, icon) go there instead of /nastavnici/?katedra=.
7. [x] Biomed icon: helix open at both ends, gaps at the crossings, half a gear behind on the right (variant L of
       %TEMP%\helix\helix.py).
8. [x] Subject page header: its katedra icon (book if none); link goes to /nastavnici/?katedra= until #6.
   [x] Friendlier empty states: icon + a useful link instead of grey one-liners (rows.html empty).
2. [x] (book fallback done)
