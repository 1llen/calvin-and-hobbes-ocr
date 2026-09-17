"""
Scans every scraped page image for whether it's printed in color (Sunday
strips, covers) vs black-and-white (daily strips) and stores the result in
data/ocr.sqlite3, so the web GUI's /color page can list them.

These collections split cleanly into two clusters: pages that are pure
black-and-white line art (aside from tiny compression noise) and pages with
real color content, with a wide, empty gap between them — checked across
the full ~1870-page collection, the most-saturated "B&W" page measured
~0.12 average saturation and the least-saturated "color" page ~5.9, with
nothing in between. MIN_SATURATION sits safely in that gap.

Usage:
    python detect_color.py
    python detect_color.py --issue 6
"""
import argparse
import sqlite3

from PIL import Image

from config import IMAGES_DIR, DB_PATH, ISSUES

SCHEMA = """
CREATE TABLE IF NOT EXISTS page_color (
    issue INTEGER NOT NULL,
    page INTEGER NOT NULL,
    avg_saturation REAL NOT NULL,
    is_color INTEGER NOT NULL,
    PRIMARY KEY (issue, page)
);
"""

MIN_SATURATION = 3.0
THUMB_SIZE = (80, 80)


def measure_saturation(image_path) -> float:
    im = Image.open(image_path).convert("RGB").resize(THUMB_SIZE)
    sat_bytes = im.convert("HSV").getchannel("S").tobytes()
    return sum(sat_bytes) / len(sat_bytes)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def already_scored(conn: sqlite3.Connection, issue: int, page: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM page_color WHERE issue = ? AND page = ? LIMIT 1", (issue, page)
    ).fetchone()
    return row is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, help="Only scan this issue number")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    issues = ISSUES
    if args.issue:
        issues = [i for i in ISSUES if i["number"] == args.issue]

    total = 0
    colored = 0
    for issue in issues:
        number = issue["number"]
        issue_dir = IMAGES_DIR / f"issue_{number:02d}"
        if not issue_dir.exists():
            continue
        for image_path in sorted(issue_dir.glob("page_*.*")):
            page_num = int(image_path.stem.split("_")[1])
            if already_scored(conn, number, page_num):
                continue
            avg_sat = measure_saturation(image_path)
            is_color = 1 if avg_sat >= MIN_SATURATION else 0
            conn.execute(
                "INSERT INTO page_color (issue, page, avg_saturation, is_color) VALUES (?, ?, ?, ?)",
                (number, page_num, avg_sat, is_color),
            )
            total += 1
            colored += is_color
            if total % 100 == 0:
                conn.commit()
                print(f"Scanned {total} pages so far ({colored} colored)...")

    conn.commit()
    conn.close()
    print(f"Done. Scanned {total} new page(s), {colored} marked as colored.")


if __name__ == "__main__":
    main()
