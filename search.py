"""
Searches the OCR'd Calvin and Hobbes text index built by ocr_index.py.

A search for multiple words requires all of them to be present on the page
(AND, not OR). A trailing * on a word does a prefix search.

Usage:
    python search.py "transmogrifier"
    python search.py "stupendous man" --issue 6
    python search.py "snowman*" --limit 10
    python search.py "don't"
"""
import argparse
import sqlite3
import sys

from config import DB_PATH
from query_utils import build_match_query


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Search words (all must be present); trailing * does a prefix search")
    parser.add_argument("--issue", type=int, help="Restrict search to a single issue number")
    parser.add_argument("--limit", type=int, default=25, help="Max results to show")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print("No OCR index found yet. Run ocr_index.py first.", file=sys.stderr)
        sys.exit(1)

    match_query = build_match_query(args.query)
    if match_query is None:
        print("Please enter a search term.")
        return

    conn = sqlite3.connect(DB_PATH)
    sql = """
        SELECT issue, page, image_path,
               snippet(pages_fts, 0, '[', ']', ' ... ', 12) AS snip
        FROM pages_fts
        WHERE pages_fts MATCH ?
    """
    params = [match_query]
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
