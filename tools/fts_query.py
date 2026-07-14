"""Helpers for safely passing user input to SQLite FTS5 queries."""

import re


def literal_fts_query(query: str) -> str:
    """Quote each whitespace-delimited term for safe implicit-AND matching.

    FTS5 otherwise parses punctuation in emails, domains, and identifiers as
    query syntax. Quoting individual terms preserves broad multi-term matching
    without requiring callers to understand FTS5 escaping rules.
    """
    query = query.strip()
    if not query:
        return '""'
    # Preserve deliberately supplied FTS phrases and boolean expressions.
    # Treat only explicit uppercase operators as FTS syntax. Ordinary legal
    # names frequently contain words such as "and"; returning those names
    # unquoted exposes punctuation later in the string (for example a comma
    # before LLC) to the FTS5 parser and can raise a syntax error.
    if '"' in query or re.search(r"\b(?:AND|OR|NOT|NEAR)\b", query):
        return query
    terms = query.split()
    return " ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)
