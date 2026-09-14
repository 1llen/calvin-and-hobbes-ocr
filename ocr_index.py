"""
Runs OCR over every scraped page image and builds a searchable SQLite
full-text index (FTS5). Safe to re-run: pages already indexed are skipped.

Comic pages are multi-panel, with dialogue scattered across many small
speech bubbles rather than one flowing block of text. Whole-page OCR modes
tend to mash unrelated bubbles together into garbled compound words, so
this instead:
  1. Preprocesses each page (2x upscale + binarize) since the stylized,
     bold comic lettering benefits from more pixels and hard black/white
     contrast.
  2. Runs Tesseract in sparse-text mode (--psm 11), which looks for
     scattered text regions instead of assuming one reading order.
  3. Keeps only individual words above a confidence threshold, joined by
     spaces — this sacrifices sentence order (irrelevant for search) in
     exchange for much less cross-bubble garbage.
  4. Stores each kept word's bounding box (scaled back to original image
     coordinates) so a viewer can highlight exactly where a match sits on
     the page.

Usage:
    python ocr_index.py
    python ocr_index.py --issue 6
    python ocr_index.py --tesseract-cmd "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
"""
import argparse
import sqlite3

import pytesseract
from pytesseract import Output
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

CREATE TABLE IF NOT EXISTS words (
    issue INTEGER NOT NULL,
    page INTEGER NOT NULL,
    word TEXT NOT NULL,
    left INTEGER NOT NULL,
    top INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_words_issue_page ON words(issue, page);
CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
"""

MIN_CONFIDENCE = 60
PREPROCESS_SCALE = 2
PREPROCESS_THRESHOLD = 180


def preprocess(im: Image.Image) -> Image.Image:
    im = im.convert("L")
    w, h = im.size
    im = im.resize((w * PREPROCESS_SCALE, h * PREPROCESS_SCALE), Image.LANCZOS)
    im = im.point(lambda p: 255 if p > PREPROCESS_THRESHOLD else 0)
    return im


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def already_indexed(conn: sqlite3.Connection, issue: int, page: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pages_fts WHERE issue = ? AND page = ? LIMIT 1", (issue, page)
    ).fetchone()
    return row is not None


def index_image(conn: sqlite3.Connection, issue: int, page: int, image_path) -> None:
    prepped = preprocess(Image.open(image_path))
    data = pytesseract.image_to_data(prepped, config="--psm 11", output_type=Output.DICT)

    words = []
    word_rows = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = int(data["conf"][i])
        if not text or conf < MIN_CONFIDENCE:
            continue
        words.append(text)
        word_rows.append(
            (
                issue,
                page,
                text,
                data["left"][i] // PREPROCESS_SCALE,
                data["top"][i] // PREPROCESS_SCALE,
                data["width"][i] // PREPROCESS_SCALE,
                data["height"][i] // PREPROCESS_SCALE,
            )
        )

    conn.execute(
        "INSERT INTO pages_fts (text, issue, page, image_path) VALUES (?, ?, ?, ?)",
        (" ".join(words), issue, page, str(image_path)),
    )
    conn.executemany(
        "INSERT INTO words (issue, page, word, left, top, width, height) VALUES (?, ?, ?, ?, ?, ?, ?)",
        word_rows,
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
