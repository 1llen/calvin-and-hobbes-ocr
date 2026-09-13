# Calvin and Hobbes OCR search

Personal-use tool: scrapes the ~1,870 pages across all 11 issues from your
batcave.biz reader links, OCRs each page, and builds a searchable text index
so you can find a specific strip by the words in it.

## Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Install the Tesseract OCR engine (not a Python package — a separate binary):
   - Windows installer: https://github.com/UB-Mannheim/tesseract/wiki
   - Default install path is usually `C:\Program Files\Tesseract-OCR\tesseract.exe`.
     If it's not on your PATH, pass `--tesseract-cmd` to `ocr_index.py` (see below).

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

```
python search.py "transmogrifier"
python search.py "stupendous man" --issue 6
```

Each result prints the issue/page number, the local image file path, and a
snippet of the matched OCR text so you can jump straight to the page.

## Notes

- OCR on scanned comic lettering is imperfect (stylized fonts, sound effects,
  slanted panels) — if a search misses something you know is there, try a
  shorter/partial word, wildcards (`snowm*`), or check the misspelling isn't
  an OCR artifact by browsing nearby pages.
- Everything is stored locally under `data/` (images + `ocr.sqlite3`) — nothing
  is uploaded anywhere. This is intended strictly for personal, offline search
  of a collection you already own.
