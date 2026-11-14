# Plan: /stil/ style page (2026-11-14)

Decided with the user, one question at a time. Nothing built yet.

A public page at `/stil/`, title "Stil", linked from the footer and from O sajtu. build.py generates it from the
real files, so a new color, icon or poster shows up without editing the page. Every item is its own download link
(no zip).

Sections, top to bottom:

1. [ ] Logo: favicon.svg, app-icon.svg, apple-touch-icon.png, icon-192.png, icon-512.png, badge.png, each with its
       size and a download link.
2. [ ] Colors: every CSS variable from style.css that holds a color, as a swatch with its name and value. The
       swatches use `var(--x)`, so they follow the visitor's current theme and change when the theme switches; the
       value shown is read in the browser with getComputedStyle.
3. [ ] Typefaces: IBM Plex Sans, IBM Plex Mono, Geist (the site's fonts) and the OG poster fonts Golos Text
       ExtraBold and Roboto Mono; Masinci stays out. Each one gets a specimen (its weights, a Latin and a Cyrillic
       line) and a download link. Golos ExtraBold and Roboto Mono get copied from pages/og-fonts/ into
       static/fonts/.
4. [ ] Icons: every symbol in icons.svg in a grid, labeled by its id. build.py writes each symbol out as its own
       SVG under /stil/ikone/<id>.svg so it can be downloaded.
5. [ ] OG posters: og*.png and og-link-*, as thumbnails linking the full file.

Touches: build.py (render + per-icon SVGs + one assert that every symbol got written), a new templates/stil.html,
style.css (grid and swatch styles), base.html footer, o_sajtu.html, verzije.md entry.
