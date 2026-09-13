"""
Runs OCR over every scraped page image and builds a searchable SQLite
full-text index (FTS5). Safe to re-run: pages already indexed are skipped.

Usage:
    python ocr_index.py
    python ocr_index.py --issue 6
    python ocr_index.py --tesseract-cmd "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
"""
import argparse
import sqlite3

import pytesseract
from PIL import Image

from config import IMAGES_DIR, DB_PATH, ISSUES

SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
    text,
    issue UNINDEXED,
    page UNINDEXED,
    image_path UNINDEXED,
    tokenize = 'porter unicode61'
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def already_indexed(conn: sqlite3.Connection, issue: int, page: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pages_fts WHERE issue = ? AND page = ? LIMIT 1", (issue, page)
    ).fetchone()
    return row is not None


def index_image(conn: sqlite3.Connection, issue: int, page: int, image_path) -> None:
    # --psm 6 (treat the page as one uniform block of text) captures
    # noticeably more of a multi-panel comic strip's dialogue than the
    # default auto page-segmentation mode, which tends to drop whole panels.
    text = pytesseract.image_to_string(Image.open(image_path), config="--psm 6")
    conn.execute(
        "INSERT INTO pages_fts (text, issue, page, image_path) VALUES (?, ?, ?, ?)",
        (text, issue, page, str(image_path)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, help="Only index this issue number")
    parser.add_argument(
        "--tesseract-cmd",
        type=str,
        help=r"Path to tesseract.exe if it isn't on PATH, e.g. C:\Program Files\Tesseract-OCR\tesseract.exe",
    )
    args = parser.parse_args()

    if args.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = args.tesseract_cmd

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    issues = ISSUES
    if args.issue:
        issues = [i for i in ISSUES if i["number"] == args.issue]

    total_indexed = 0
    for issue in issues:
        number = issue["number"]
        issue_dir = IMAGES_DIR / f"issue_{number:02d}"
        if not issue_dir.exists():
            continue
        for image_path in sorted(issue_dir.glob("page_*.*")):
            page_num = int(image_path.stem.split("_")[1])
            if already_indexed(conn, number, page_num):
                continue
            index_image(conn, number, page_num, image_path)
            total_indexed += 1
            if total_indexed % 20 == 0:
                conn.commit()
                print(f"Indexed {total_indexed} pages so far...")

    conn.commit()
    conn.close()
    print(f"Done. Indexed {total_indexed} new page(s).")


if __name__ == "__main__":
    main()
