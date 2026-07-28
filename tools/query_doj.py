#!/usr/bin/env python3
"""
Query DOJ Volume 11 database (331,655 OCR'd pages, FTS5).

Database: /Users/travcole/projects/epstein-docs/output/documents.db

Usage:
    python tools/query_doj.py search "churkin ambassador" --limit 20 --context 200
    python tools/query_doj.py efta EFTA02663759
    python tools/query_doj.py count "rod-larsen"
    python tools/query_doj.py names EFTA02663759
"""

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
    from tools.fts_query import literal_fts_query
except ImportError:
    from output_util import add_output_args, write_output
    from fts_query import literal_fts_query


def _log(query, source, count):
    """Log search to prevent redundant queries."""
    try:
        from tools.lead_tracker import log_search
        log_search(query, source, count)
    except Exception:
        pass


DB_PATH = "/Users/travcole/projects/epstein-docs/output/documents.db"
DOJ_EPSTEIN_HOSTS = {"justice.gov", "www.justice.gov"}
MAX_PDF_BYTES = 500 * 1024 * 1024


def get_db():
    try:
        db = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
        return db
    except Exception as e:
        print(f"ERROR: Cannot open DOJ Vol 11 database at {DB_PATH}: {e}")
        sys.exit(1)


def search(query, limit=20, context_chars=200):
    """FTS5 search across OCR text. Returns matches with context snippets."""
    db = get_db()
    rows = db.execute("""
        SELECT
            d.bates_id,
            d.page_count,
            d.word_count,
            snippet(documents_fts, 1, '>>>', '<<<', '...', 64) as snippet
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (literal_fts_query(query), limit)).fetchall()
    db.close()
    return [dict(r) for r in rows]


def get_efta(bates_id):
    """Get a specific document by bates ID."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM documents WHERE bates_id = ?", (bates_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def count_matches(query):
    """Count total documents matching a query."""
    db = get_db()
    row = db.execute("""
        SELECT COUNT(*) as cnt
        FROM documents_fts
        WHERE documents_fts MATCH ?
    """, (literal_fts_query(query),)).fetchone()
    db.close()
    return row[0]


def get_names(bates_id):
    """Get extracted names from a document."""
    db = get_db()
    row = db.execute(
        "SELECT extracted_names FROM documents WHERE bates_id = ?", (bates_id,)
    ).fetchone()
    db.close()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return row[0]
    return None


def download_epstein_pdf(url, output_path, *, opener=None):
    """Download one public DOJ Epstein PDF through the age-verification gate."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in DOJ_EPSTEIN_HOSTS
        or not parsed.path.casefold().startswith("/epstein/files/")
        or not parsed.path.casefold().endswith(".pdf")
    ):
        raise ValueError(
            "download URL must be an official HTTPS justice.gov/epstein/files/*.pdf"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "Accept": "application/pdf",
            "Cookie": "justiceGovAgeVerified=true",
            "User-Agent": "Ithildin Research research@example.com",
        },
    )
    opener = opener or urlopen
    temp_path = None
    total = 0
    try:
        with opener(request, timeout=60) as response:
            content_type = response.headers.get("Content-Type", "")
            prefix = response.read(5)
            if "text/html" in content_type.casefold() or prefix != b"%PDF-":
                raise ValueError(
                    "DOJ returned a non-PDF response; age verification or the "
                    "document URL may have changed"
                )
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{output_path.name}.",
                suffix=".tmp",
                dir=output_path.parent,
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(prefix)
                total = len(prefix)
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        raise ValueError(
                            f"DOJ PDF exceeds the {MAX_PDF_BYTES:,}-byte safety limit"
                        )
                    handle.write(chunk)
        os.replace(temp_path, output_path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    return {
        "url": url,
        "output": str(output_path),
        "content_type": content_type,
        "bytes": total,
    }


def main():
    parser = argparse.ArgumentParser(description="Query DOJ Vol 11 (331K OCR'd pages)")
    subparsers = parser.add_subparsers(dest="command")

    # search
    s = subparsers.add_parser("search", help="Full-text search")
    s.add_argument("query", help="FTS5 search query")
    s.add_argument("--limit", "-n", type=int, default=20)
    s.add_argument("--context", type=int, default=200, help="Context chars around match")
    s.add_argument("-j", "--json", action="store_true")
    add_output_args(s)

    # efta
    e = subparsers.add_parser("efta", help="Get document by bates ID")
    e.add_argument("bates_id", help="e.g. EFTA02663759")
    e.add_argument("-j", "--json", action="store_true")
    add_output_args(e)
    e.add_argument("--text", action="store_true", help="Show full OCR text")

    # count
    c = subparsers.add_parser("count", help="Count matching documents")
    c.add_argument("query", help="FTS5 search query")

    # names
    n = subparsers.add_parser("names", help="Get extracted names from document")
    n.add_argument("bates_id")

    # download
    d = subparsers.add_parser(
        "download",
        help="Download a public DOJ Epstein PDF through the age gate",
    )
    d.add_argument("url", help="Official justice.gov/epstein/files/*.pdf URL")
    d.add_argument("--output", required=True, help="Destination PDF path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        results = search(args.query, limit=args.limit, context_chars=args.context)
        _log(args.query, "doj_vol11", len(results))
        if write_output(results, args, summary=f"DOJ search '{args.query}'"):
            pass
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"\nDOJ Vol 11 search: '{args.query}' — {len(results)} results")
            print("=" * 70)
            for i, r in enumerate(results, 1):
                print(f"\n[{i}] {r['bates_id']} ({r['page_count']} pages, {r['word_count']} words)")
                snippet = r.get("snippet", "")
                if snippet:
                    print(f"    {snippet[:400]}")

    elif args.command == "efta":
        doc = get_efta(args.bates_id)
        if not doc:
            print(f"Document {args.bates_id} not found.")
            sys.exit(1)
        if write_output(doc, args, summary=f"EFTA {args.bates_id}"):
            pass
        elif args.json:
            if not args.text:
                doc.pop("ocr_text", None)
            print(json.dumps(doc, indent=2, default=str))
        else:
            print(f"\n{doc['bates_id']} — {doc['page_count']} pages, {doc['word_count']} words")
            print(f"PDF: {doc['pdf_path']}")
            if doc.get("extracted_dates"):
                print(f"Dates: {doc['extracted_dates']}")
            if doc.get("extracted_names"):
                print(f"Names: {doc['extracted_names'][:200]}")
            if args.text and doc.get("ocr_text"):
                print(f"\n--- OCR Text ---\n{doc['ocr_text'][:5000]}")
                if len(doc.get("ocr_text", "")) > 5000:
                    print(f"\n... [{len(doc['ocr_text']) - 5000} more chars]")

    elif args.command == "count":
        cnt = count_matches(args.query)
        print(f"'{args.query}': {cnt} documents in DOJ Vol 11")

    elif args.command == "names":
        names = get_names(args.bates_id)
        if names:
            if isinstance(names, list):
                for n in names:
                    print(n)
            else:
                print(names)
        else:
            print(f"No extracted names for {args.bates_id}")

    elif args.command == "download":
        try:
            result = download_epstein_pdf(args.url, args.output)
        except (HTTPError, URLError, OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(2) from error
        print(
            f"Downloaded DOJ PDF ({result['bytes']:,} bytes) to "
            f"{result['output']}"
        )


if __name__ == "__main__":
    main()
