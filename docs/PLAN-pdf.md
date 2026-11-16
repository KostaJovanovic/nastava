# PDF viewer

Status: planned 2026-11-16, no code yet.

A viewer of our own for the PDFs the site hosts, on every device: the browser (phone and desktop) and the app (which
loads the site, so no new APK). Built on PDF.js (`pdfjs-dist`, 6.5.x), Mozilla's library, the one in Firefox.

## Which files

- Only PDFs on our own domain: `/files/…` (GitHub releases through the Worker) and any other `.pdf` path on masinci.org.
- External PDFs (mas.bg.ac.rs and others) work as now: in the app the phone's reader (`openFile`), on the web the
  leave dialog and a new tab. No proxy through the Worker for them.
- This replaces, for our PDFs only, the app's "attachments open in the phone's apps" (PLAN-app.md): "open with" keeps it.

## What it does

- Renders at the screen's full resolution (devicePixelRatio), sharp again after zoom.
- Zoom and pan: pinch, double-tap, Ctrl+wheel on desktop; opens fit to width.
- Text selection (PDF.js text layer) and the PDF's own links (annotation layer): ours in the viewer or the page,
  outside ones as other outside links (app: the phone's browser).
- Find: all matches highlighted, next and previous; Ctrl+F on desktop opens it.
- Page number and count; a tap on the number jumps to a page; arrows on desktop.
- Contents: the PDF's own outline, when it has one.
- Reopens at the last page read (localStorage, per address).
- A loading bar for big files.
- Exit: a close button, Esc, and Back (the viewer pushes a history entry, so Android's Back and the browser's close it).
- "Open with": the app hands the file to the phone (`openFile`, as now); the web downloads it.
- Fallback: a PDF that won't load (password, damaged, the library fails) goes the old way, without an error page.

Find and selection need text in the PDF: a scan has none.

## How

- `pdfjs-dist` vendored into `pages/static/pdf/` (the library and its worker, no viewer UI), pinned; loaded only
  when a PDF is opened. Our own UI, in the site's style.
- site.js: the click handler sends our `.pdf` links to the viewer before `openFile` and before `window.open`.
- The viewer is a full-screen layer over the page, not a page of its own: the Worker and the build are unchanged.

## Open

- The Serbian labels (close, find, contents, open with, page n of m, the loading and failure lines): shown before
  committing.
- Checks: a long text PDF, a scan, a PDF with links and an outline; phone browser, the app, desktop.
