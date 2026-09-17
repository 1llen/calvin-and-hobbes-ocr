"""
Turns a raw user search string into a safe SQLite FTS5 MATCH expression.

Plain FTS5 query syntax chokes on characters like apostrophes (a bareword
containing "'" is a syntax error), and its default operator precedence isn't
obvious to a casual user. This instead treats the input as plain words: each
word is individually quoted (so punctuation like apostrophes can never break
the query syntax) and every word is required (AND) for a page to match. A
trailing "*" on a word still does a prefix search, e.g. "transmog*".
"""
import re

_WORD_RE = re.compile(r"[^\s]+")


def build_match_query(raw_query: str) -> str | None:
    clauses = []
    for word in _WORD_RE.findall(raw_query):
        prefix = word.endswith("*")
        core = word[:-1] if prefix else word
        # Keep letters/digits/apostrophes, drop stray punctuation like
        # commas or question marks that a user might type around a word.
        core = re.sub(r"[^\w']", "", core, flags=re.UNICODE).strip("'")
        if not core:
            continue
        escaped = core.replace('"', '""')
        clause = f'"{escaped}"'
        if prefix:
            clause += "*"
        clauses.append(clause)

    if not clauses:
        return None
    return " AND ".join(clauses)
