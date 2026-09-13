"""
Searches the OCR'd Calvin and Hobbes text index built by ocr_index.py.

Usage:
    python search.py "transmogrifier"
    python search.py "stupendous man" --issue 6
    python search.py "snowman*" --limit 10
"""
import argparse
import sqlite3
import sys

from config import DB_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help='Search text (FTS5 syntax, e.g. "tiger duplicate" or transmogrifier*)')
    parser.add_argument("--issue", type=int, help="Restrict search to a single issue number")
    parser.add_argument("--limit", type=int, default=25, help="Max results to show")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("No OCR index found yet. Run ocr_index.py first.", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    sql = """
        SELECT issue, page, image_path,
               snippet(pages_fts, 0, '[', ']', ' ... ', 12) AS snip
        FROM pages_fts
        WHERE pages_fts MATCH ?
    """
    params = [args.query]
    if args.issue:
        sql += " AND issue = ?"
        params.append(args.issue)
    sql += " ORDER BY issue, page LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No matches.")
        return

    for issue, page, image_path, snip in rows:
        print(f"Issue {issue}, page {page}: {image_path}")
        print(f"    {snip}\n")


if __name__ == "__main__":
    main()
