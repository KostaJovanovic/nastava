# Plan: aesthetics round (2026-11-13)

Decided with the user, one question at a time. Done items are marked.

1. [x] Raspored tabs: `OAS - MI`, `OAS - ITM`, `MAS - MI`, `MAS - IND4.0`, `DAS` (950651c).
2. [x] Header search: subject rows show their katedra's icon, katedre found by initials (7b4a1c3).
   [ ] Subjects with no katedra icon show the book icon.
3. Teacher page:
   [ ] Biography section above the forum posts: ~2 paragraphs per teacher, written by Claude once from the
       teacher's sources (monograph, faculty profile, old-site card, history), saved to a JSONL, done in batches the
       user reviews. Example accepted for Tatjana Lazović-Kapor (education/career; research/teaching/books/awards).
   [ ] Bibliography as its own section: the repository's Radovi and the faculty profile's Bibliografija merged into
       one list, deduped by DOI/title; entry = title (bold), authors (teacher highlighted), journal · year · M-badge,
       DOI link; by year, newest 10, rest behind "Prikaži još".
4. [x] Linkovi: Studentski webmail before Predmeti in Izdvojeno's small cards (950651c).
5. [ ] OG images, sections only (og, -predmeti, -nastavnici, -raspored, -vesti, -arhiva): poster style, huge
       left-aligned title cropped at the edge, one strong color per section, small "nastava" logo, one-line
       subtitle. Fonts vary per poster: playful, bold, heavy, fitting the site. Show previews before replacing.
6. [ ] A local page per katedra from www.mas.bg.ac.rs/organizacija/katedre/<id> (store the page; nastavnici.py
       fetches it already), with a link to the katedra's own site, its teachers as cards, its subjects, its latest
       notices. Katedra links (search, cards, icon) go there instead of /nastavnici/?katedra=.
7. [ ] Biomed icon: a good-looking helix with a gear peeking from behind. Preview before applying.
8. [ ] Subject page header: its katedra icon (book if none), linking to the katedra page.
   [ ] Friendlier empty states: icon + a useful link instead of grey one-liners.
