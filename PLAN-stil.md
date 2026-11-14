# Plan: /stil/ style page (2026-11-14)

Decided with the user, one question at a time. Built in d7bffe3, except the verzije.md entry (see the end).

A public page at `/stil/`, title "Stil", linked from the footer and from O sajtu. build.py generates it from the
real files, so a new color, icon or poster shows up without editing the page. Every item is its own download link
(no zip).

Sections, top to bottom:

1. [x] Logo: favicon.svg, app-icon.svg, apple-touch-icon.png, icon-192.png, icon-512.png, badge.png, each with its
       size and a download link.
2. [x] Colors: every CSS variable from style.css that holds a color, as a swatch with its name and value. The
       swatches use `var(--x)`, so they follow the visitor's current theme and change when the theme switches; the
       build.py reads both values from light-dark() and CSS shows the one of the theme on (no JS).
3. [x] Typefaces: IBM Plex Sans, IBM Plex Mono, Geist (the site's fonts) and the OG poster fonts Golos Text
       ExtraBold and Roboto Mono; Masinci stays out. Each one gets a specimen (its weights, a Latin and a Cyrillic
       line) and a download link. Golos uses the site's own static/fonts/lab/GolosText.woff2 (400–800);
       Roboto Mono got copied from pages/og-fonts/ into static/fonts/.
4. [x] Icons: every symbol in icons.svg in a grid, labeled by its id. build.py writes each symbol out as its own
       SVG as a data: URL download link (no files written).
5. [x] OG posters: og*.png and og-link-*, as thumbnails linking the full file.

Touches: build.py (render + per-icon SVGs + one assert that every symbol got written), a new templates/stil.html,
style.css (grid and swatch styles), base.html footer, o_sajtu.html.

[ ] verzije.md entry: not added. verzije.md lists commits to 317 and build.py fails on a gap, so it waits
    for the next batch of entries (318 on).
[ ] The section posters (Claude Design PNGs) use other fonts than these; add them if their files are found.
