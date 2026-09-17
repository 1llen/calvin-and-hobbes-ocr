"""
Simple local web GUI for searching the OCR'd Calvin and Hobbes collection.

Usage:
    python webapp.py
    (then open http://127.0.0.1:5000 in a browser)
"""
import re
import sqlite3
from io import BytesIO

from flask import Flask, request, render_template, send_file, abort
from PIL import Image, ImageDraw

from config import DB_PATH, ISSUES
from query_utils import build_match_query

app = Flask(__name__)

ISSUE_NUMBERS = [i["number"] for i in ISSUES]
RESULTS_LIMIT = 40


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_tokens(q: str):
    """Pulls plain word tokens out of a search query (stripping FTS5 wildcard
    syntax) so they can be looked up in the per-word bounding-box table."""
    return [t.rstrip("*") for t in re.findall(r"[A-Za-z0-9']+\*?", q)]


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    issue_filter = request.args.get("issue", "").strip()
    results = []
    total = 0
    error = None

    if q:
        match_query = build_match_query(q)
        if match_query is None:
            error = "Please enter a search term."
        else:
            conn = get_db()
            where = "WHERE pages_fts MATCH ?"
            params = [match_query]
            if issue_filter:
                where += " AND issue = ?"
                params.append(int(issue_filter))

            try:
                total = conn.execute(f"SELECT COUNT(*) FROM pages_fts {where}", params).fetchone()[0]
                rows = conn.execute(
                    f"""
                    SELECT issue, page, image_path,
                           snippet(pages_fts, 0, '<mark>', '</mark>', ' … ', 16) AS snip
                    FROM pages_fts
                    {where}
                    ORDER BY issue, page LIMIT ?
                    """,
                    params + [RESULTS_LIMIT],
                ).fetchall()
                results = [dict(r) for r in rows]
            except sqlite3.OperationalError as e:
                error = f"Search syntax error: {e}"
            conn.close()

    return render_template(
        "index.html",
        q=q,
        issue_filter=issue_filter,
        issues=ISSUE_NUMBERS,
        results=results,
        total=total,
        limit=RESULTS_LIMIT,
        error=error,
        active="search",
    )


@app.route("/color")
def color_page():
    conn = get_db()
    error = None
    results = []
    try:
        rows = conn.execute(
            "SELECT issue, page FROM page_color WHERE is_color = 1 ORDER BY issue, page"
        ).fetchall()
        results = [dict(r) for r in rows]
    except sqlite3.OperationalError:
        error = "No color data yet — run detect_color.py first."
    conn.close()

    return render_template(
        "color.html",
        results=results,
        total=len(results),
        error=error,
        active="color",
    )


@app.route("/image/<int:issue>/<int:page>")
def image(issue, page):
    conn = get_db()
    row = conn.execute(
        "SELECT image_path FROM pages_fts WHERE issue=? AND page=? LIMIT 1",
        (issue, page),
    ).fetchone()
    if not row:
        conn.close()
        abort(404)
    image_path = row["image_path"]

    q = request.args.get("q", "").strip()
    if not q:
        conn.close()
        return send_file(image_path)

    boxes = []
    for tok in query_tokens(q):
        rows = conn.execute(
            "SELECT left, top, width, height FROM words WHERE issue=? AND page=? AND LOWER(word) LIKE ?",
            (issue, page, tok.lower() + "%"),
        ).fetchall()
        boxes.extend((r["left"], r["top"], r["width"], r["height"]) for r in rows)
    conn.close()

    im = Image.open(image_path).convert("RGB")
    if boxes:
        draw = ImageDraw.Draw(im)
        for left, top, width, height in boxes:
            draw.rectangle(
                [left - 4, top - 4, left + width + 4, top + height + 4],
                outline=(255, 40, 40),
                width=4,
            )

    buf = BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=False, port=5000)
