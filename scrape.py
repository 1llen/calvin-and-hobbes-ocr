"""
Scrapes the main comic-page images for each issue's reader from batcave.biz.

Each page's image URL contains a random hash suffix that only appears in the
page's DOM once the reader's lazy-loader resolves it, so this drives a real
browser (Playwright) through every page of every issue rather than guessing
URLs. Downloads are resumable: already-saved pages are skipped on re-run.

Usage:
    python scrape.py                      # scrape every issue, all pages
    python scrape.py --issue 6            # scrape only issue 6
    python scrape.py --issue 6 --page 12  # scrape a single page (smoke test)
    python scrape.py --headless           # skip the visible browser window
                                           # (only works once Cloudflare has
                                           # already been solved for this
                                           # browser profile)
"""
import argparse
import base64
import time
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from config import ISSUES, NEWS_ID, IMAGES_DIR, BROWSER_PROFILE_DIR

READER_URL = "https://batcave.biz/reader/{news_id}/{chapter_id}"

# Masks the most common automation fingerprints (navigator.webdriver, missing
# chrome runtime, empty plugins/languages) that bot-detection/ad-gate scripts
# check for, since the raw Playwright-controlled browser was getting caught
# in an infinite ad-redirect loop instead of ever reaching the reader.
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
window.chrome = window.chrome || { runtime: {} };
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
"""


def goto_reader(page, url: str) -> None:
    page.goto(url, timeout=60000)
    try:
        page.wait_for_selector(".reader-view", timeout=15000)
    except PWTimeout:
        print("  Cloudflare challenge detected — please solve it in the browser window...")
        page.wait_for_selector(".reader-view", timeout=180000)


def goto_page(page, n: int, timeout: float = 15.0, interval: float = 0.25) -> Optional[str]:
    """Switches the reader's active page via the URL hash (matching the
    site's own #page-N links) and returns the resolved image src once the
    reader has loaded it, or None if it never appears."""
    page.evaluate("(n) => { location.hash = '#page-' + n; }", n)
    elapsed = 0.0
    while elapsed < timeout:
        active_img = page.locator(f'.reader__item-wrap[data-page="{n}"] img').first
        src = active_img.get_attribute("src")
        if src:
            return src
        time.sleep(interval)
        elapsed += interval
    return None


FETCH_JS = """
async (url) => {
    const r = await fetch(url);
    if (!r.ok) return { ok: false, status: r.status };
    const buf = await r.arrayBuffer();
    const bytes = new Uint8Array(buf);
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return { ok: true, status: r.status, base64: btoa(binary) };
}
"""


def fetch_bytes(page, url: str) -> Optional[bytes]:
    """Downloads image bytes via an in-page fetch() so the request comes from
    the real browser's network stack (same-fingerprint as the <img> tag that
    already loads it) — a plain background HTTP request from Playwright's
    request context gets a 403 from the image CDN's bot protection."""
    result = page.evaluate(FETCH_JS, url)
    if not result.get("ok"):
        return None
    return base64.b64decode(result["base64"])


def detect_ext(data: bytes) -> str:
    """The CDN serves some pages as WebP even though the URL path ends in
    .jpg, so sniff the real format from the file's magic bytes instead of
    trusting the URL extension."""
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    return "jpg"


def scrape_issue(page, issue: dict, only_page: Optional[int] = None) -> None:
    number = issue["number"]
    chapter_id = issue["chapter_id"]
    total_pages = issue["pages"]
    reader_url = READER_URL.format(news_id=NEWS_ID, chapter_id=chapter_id)

    out_dir = IMAGES_DIR / f"issue_{number:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    page_range = [only_page] if only_page else range(1, total_pages + 1)
    pending = [n for n in page_range if not any(out_dir.glob(f"page_{n:03d}.*"))]
    if not pending:
        print(f"Issue {number}: all requested pages already downloaded, skipping.")
        return

    print(f"Issue {number}: opening reader ({reader_url})")
    goto_reader(page, reader_url)

    for n in page_range:
        if any(out_dir.glob(f"page_{n:03d}.*")):
            continue

        src = goto_page(page, n, timeout=15.0)
        if not src:
            print(f"  page {n}: no image src found (missing/broken page?), skipping")
            continue

        data = fetch_bytes(page, src)
        if data is None:
            print(f"  page {n}: download failed for {src}")
            continue

        dest = out_dir / f"page_{n:03d}.{detect_ext(data)}"
        dest.write_bytes(data)
        print(f"  page {n}: saved -> {dest.name}")
        time.sleep(0.2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, help="Only scrape this issue number (1-11)")
    parser.add_argument("--page", type=int, help="Only scrape this single page number (requires --issue)")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser window")
    args = parser.parse_args()

    if args.page and not args.issue:
        parser.error("--page requires --issue")

    issues = ISSUES
    if args.issue:
        issues = [i for i in ISSUES if i["number"] == args.issue]
        if not issues:
            parser.error(f"Unknown issue number: {args.issue}")

    BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE_DIR),
            headless=args.headless,
            viewport={"width": 1280, "height": 1600},
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context.add_init_script(STEALTH_INIT_SCRIPT)
        page = context.new_page()
        try:
            for issue in issues:
                scrape_issue(page, issue, only_page=args.page)
        finally:
            context.close()


if __name__ == "__main__":
    main()
