# Calvin and Hobbes OCR search

Personal-use tool: scrapes the ~1,870 pages across all 11 issues from your
batcave.biz reader links, OCRs each page, and builds a searchable text index
so you can find a specific strip by the words in it.

## Setup

1. Create and activate a virtual environment, then install Python dependencies:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Install the Tesseract OCR engine (not a Python package — a separate binary):
   - Windows installer: https://github.com/UB-Mannheim/tesseract/wiki (or `winget install UB-Mannheim.TesseractOCR`)
   - Default install path is usually `C:\Program Files\Tesseract-OCR\tesseract.exe`.
     If it's not on your PATH, pass `--tesseract-cmd` to `ocr_index.py` (see below).
3. Make sure real Google Chrome is installed (not just Chromium) — `scrape.py`
   drives it specifically (see the note on bot detection below).

## 1. Scrape the pages

```
python scrape.py --issue 6 --page 12
```
Run this smoke test first. A visible Chromium window will open. If Cloudflare
shows a "verifying you are human" challenge, solve it in that window — the
script waits up to 3 minutes for the reader to load. The browser profile is
saved under `data/browser_profile`, so once solved it usually won't ask again
for a while.

Once that single page downloads correctly to
`data/images/issue_06/page_012.jpg`, scrape everything:

```
python scrape.py
```

This is resumable — it's safe to stop (Ctrl+C) and re-run; already-downloaded
pages are skipped. You can also scrape one issue at a time:

```
python scrape.py --issue 1
```

Add `--headless` on later runs once Cloudflare has already been solved for
your browser profile, to skip showing the window.

## 2. OCR the pages and build the index

```
python ocr_index.py
```

Also resumable/incremental — re-run after scraping more issues and it'll only
process new pages. If tesseract isn't on your PATH:

```
python ocr_index.py --tesseract-cmd "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

## 3. Search

### Command line

```
python search.py "transmogrifier"
python search.py "stupendous man" --issue 6
```

Each result prints the issue/page number, the local image file path, and a
snippet of the matched OCR text so you can jump straight to the page.

### Web GUI (recommended)

```
python webapp.py
```

Then open http://127.0.0.1:5000 in a browser. It's a search box that shows
each matching page's actual comic image inline, with the matched word boxed
in red directly on the page — click a result to open the full-size,
highlighted image in a new tab. Optional issue filter dropdown included.

## How OCR works here

Comic pages are many small speech bubbles scattered across panels, not one
flowing block of text — feeding a whole page to Tesseract's default mode
mashes unrelated bubbles together into garbled compound words. `ocr_index.py`
instead:
1. Upscales each page 2x and binarizes it (comic lettering is bold and
   high-contrast, and benefits from more pixels).
2. Runs Tesseract in sparse-text mode (`--psm 11`), which looks for scattered
   text regions instead of assuming a single reading order.
3. Keeps only individual words above a confidence threshold, joined by
   spaces — sentence order doesn't matter for search, and this avoids
   stitching two unrelated bubbles into one nonsense word.
4. Stores each kept word's bounding box, which is what lets the web GUI draw
   a highlight box on the exact spot in the page image.

## Notes

- OCR on scanned comic lettering is still imperfect (stylized fonts, sound
  effects, slanted panels) — if a search misses something you know is there,
  try a shorter/partial word, wildcards (`snowm*`), or check the misspelling
  isn't an OCR artifact by browsing nearby pages.
- The highlight feature does a best-effort prefix match between your search
  words and the stored OCR words for that page — it can occasionally miss a
  box (e.g. due to FTS5's stemming matching a word form the highlighter
  doesn't) even when the page itself is a correct match.
- batcave.biz runs bot detection that specifically catches Playwright's
  automated Chromium (infinite ad-redirect loop) and blocks its background
  HTTP requests even after the page loads — `scrape.py` works around this by
  driving real installed Chrome with stealth patches, and downloading image
  bytes via an in-page `fetch()` rather than a background request.
- Everything is stored locally under `data/` (images + `ocr.sqlite3`) — nothing
  is uploaded anywhere. This is intended strictly for personal, offline search
  of a collection you already own.
