"""
Crops the "Read more FREE comics on ReadComicOnline" banner off the bottom
of scraped pages, and scrubs the banner's OCR'd words out of the search
index so they stop matching searches like "free" or "read".

The banner is always a separate 83px strip appended below the page, so
pages that have it are exactly 1600x1083 while every other page (covers
and full-page Sundays included — they're letterboxed) is 1600x1000.
Checked across the full ~1870-page collection: all 262 of the 1083px pages
have a bottom strip that matches the banner almost pixel-for-pixel (avg
difference < 1 grey level), while no 1000px page comes anywhere close
(min avg difference ~79), and the strip starts at exactly row 1000 on
every page. As a belt-and-braces check, a page is only cropped if it's
the expected size AND its bottom strip is near-black like the banner.

Originals (and a copy of ocr.sqlite3) are saved to data/images_original/
before anything is overwritten, and cropped pages are re-saved as lossless WebP so the comic
itself isn't recompressed. Safe to re-run: cropped pages are 1000px tall
and get skipped.

Usage:
    python remove_footer.py --dry-run
    python remove_footer.py
    python remove_footer.py --issue 6
"""
import argparse
import shutil
import sqlite3

from PIL import Image, ImageStat

from config import DATA_DIR, IMAGES_DIR, DB_PATH, ISSUES

BACKUP_DIR = DATA_DIR / "images_original"

PAGE_SIZE = (1600, 1000)
FOOTER_HEIGHT = 83
# The banner is black with a line of white text, averaging ~25 brightness;
# comic pages are mostly white paper.
MAX_FOOTER_BRIGHTNESS = 60


def has_footer(im: Image.Image) -> bool:
    if im.size != (PAGE_SIZE[0], PAGE_SIZE[1] + FOOTER_HEIGHT):
        return False
    strip = im.convert("L").crop((0, PAGE_SIZE[1], im.width, im.height))
    return ImageStat.Stat(strip).mean[0] <= MAX_FOOTER_BRIGHTNESS


def scrub_footer_words(conn: sqlite3.Connection, issue: int, page: int) -> int:
    """Drop OCR'd words that sit in the banner and rebuild the page's FTS text.

    pages_fts.text is just the page's rows in `words` joined by spaces (both
    come from the same loop in ocr_index.py), so it can be rebuilt without
    re-running OCR.
    """
    removed = conn.execute(
        "DELETE FROM words WHERE issue = ? AND page = ? AND top + height / 2.0 >= ?",
        (issue, page, PAGE_SIZE[1]),
    ).rowcount
    if removed:
        remaining = conn.execute(
            "SELECT word FROM words WHERE issue = ? AND page = ? ORDER BY rowid", (issue, page)
        ).fetchall()
        conn.execute(
            "UPDATE pages_fts SET text = ? WHERE issue = ? AND page = ?",
            (" ".join(r[0] for r in remaining), issue, page),
        )
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, help="Only process this issue number")
    parser.add_argument(
        "--dry-run", action="store_true", help="List pages that would be cropped without changing anything"
    )
    args = parser.parse_args()

    conn = None
    if DB_PATH.exists():
        if not args.dry_run and not (BACKUP_DIR / DB_PATH.name).exists():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(DB_PATH, BACKUP_DIR / DB_PATH.name)
        conn = sqlite3.connect(DB_PATH)

    issues = ISSUES
    if args.issue:
        issues = [i for i in ISSUES if i["number"] == args.issue]

    total = 0
    words_removed = 0
    for issue in issues:
        number = issue["number"]
        issue_dir = IMAGES_DIR / f"issue_{number:02d}"
        if not issue_dir.exists():
            continue
        for image_path in sorted(issue_dir.glob("page_*.*")):
            page_num = int(image_path.stem.split("_")[1])
            with Image.open(image_path) as im:
                if not has_footer(im):
                    continue
                if args.dry_run:
                    print(f"Would crop {image_path.relative_to(IMAGES_DIR)}")
                    total += 1
                    continue
                cropped = im.crop((0, 0, *PAGE_SIZE))
                cropped.load()

            backup_path = BACKUP_DIR / image_path.relative_to(IMAGES_DIR)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            if not backup_path.exists():
                shutil.copy2(image_path, backup_path)
            cropped.save(image_path, "WEBP", lossless=True, method=6)

            if conn:
                words_removed += scrub_footer_words(conn, number, page_num)
                conn.commit()
            total += 1
            if total % 50 == 0:
                print(f"Cropped {total} pages so far...")

    if conn:
        conn.close()
    if args.dry_run:
        print(f"Dry run: {total} page(s) would be cropped.")
    else:
        print(f"Done. Cropped {total} page(s), removed {words_removed} footer word(s) from the OCR index.")


if __name__ == "__main__":
    main()
