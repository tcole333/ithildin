#!/usr/bin/env python3
"""
Ingest and query the svetfm/epstein-fbi-files dataset.

8,150 OCR'd documents from the FBI's release of Jeffrey Epstein-related files
(Textract OCR, date range 1990-2020). Documents are Bates-numbered with EFTA IDs
(EFTA00000001-EFTA00009664) plus 12 named exhibits (Flight Log, Contact Book,
Evidence List from US v. Maxwell, etc.).

Source parquet (already local): datasets/svetfm_fbi_files.parquet
Canonical remote: https://huggingface.co/datasets/svetfm/epstein-fbi-files (ocr/all_ocr.jsonl)

NOTE ON PROVENANCE: EFTA Bates numbers are production-specific. ~50% of the EFTA
IDs here also appear in lmsband_epstein_files.db (the DOJ EFTA datasets), but a
matching Bates number is not proof of an identical document. Use the `overlap`
command to cross-reference; treat same-number/different-production as distinct
until verified.

Database: datasets/epstein_fbi_files.db (SQLite with FTS5)

Usage:
    python tools/ingest_fbi_files.py ingest
    python tools/ingest_fbi_files.py search "flight log" --limit 20
    python tools/ingest_fbi_files.py doc EFTA00000001
    python tools/ingest_fbi_files.py stats
    python tools/ingest_fbi_files.py overlap
    python tools/ingest_fbi_files.py download   # refresh ocr/all_ocr.jsonl from HF
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

try:
    from tools.fts_query import literal_fts_query
except ImportError:
    from fts_query import literal_fts_query

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "datasets" / "epstein_fbi_files.db"
PARQUET_PATH = BASE_DIR / "datasets" / "svetfm_fbi_files.parquet"
JSONL_PATH = BASE_DIR / "datasets" / "epstein_fbi_files" / "all_ocr.jsonl"

HF_REPO = "svetfm/epstein-fbi-files"
HF_OCR_FILE = "ocr/all_ocr.jsonl"

EFTA_RE = re.compile(r"(EFTA\d+)")


def extract_efta(bates_number):
    """Pull the EFTA id out of a bates_number, or None for named exhibits."""
    if not bates_number:
        return None
    m = EFTA_RE.search(bates_number)
    return m.group(1) if m else None


def get_db(create=False):
    """Connect to the FBI files database."""
    if not create and not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python tools/ingest_fbi_files.py ingest' first.", file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def init_db(db):
    """Create tables and FTS5 index."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bates_number TEXT NOT NULL UNIQUE,
            efta_id TEXT,
            volume TEXT,
            page_count INTEGER,
            confidence REAL,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            word_count INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_fbi_efta ON documents(efta_id);
        CREATE INDEX IF NOT EXISTS idx_fbi_volume ON documents(volume);
    """)

    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'"
    ).fetchone()
    if not row:
        db.execute("""
            CREATE VIRTUAL TABLE documents_fts USING fts5(
                bates_number,
                text,
                content=documents,
                content_rowid=id,
                tokenize='porter unicode61'
            );
        """)
        db.executescript("""
            CREATE TRIGGER IF NOT EXISTS fbi_docs_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, bates_number, text)
                VALUES (new.id, new.bates_number, new.text);
            END;

            CREATE TRIGGER IF NOT EXISTS fbi_docs_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, bates_number, text)
                VALUES ('delete', old.id, old.bates_number, old.text);
            END;

            CREATE TRIGGER IF NOT EXISTS fbi_docs_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts(documents_fts, rowid, bates_number, text)
                VALUES ('delete', old.id, old.bates_number, old.text);
                INSERT INTO documents_fts(rowid, bates_number, text)
                VALUES (new.id, new.bates_number, new.text);
            END;
        """)

    db.commit()


# --- Source readers ---


def iter_parquet(path):
    """Yield dicts from the consolidated parquet."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(str(path))
    for batch in pf.iter_batches(batch_size=1000):
        cols = batch.to_pydict()
        n = len(cols["bates_number"])
        for i in range(n):
            yield {
                "bates_number": cols["bates_number"][i],
                "text": cols["text"][i],
                "volume": cols.get("volume", [None] * n)[i],
                "page_count": cols.get("page_count", [None] * n)[i],
                "confidence": cols.get("confidence", [None] * n)[i],
            }


def iter_jsonl(path):
    """Yield dicts from the canonical ocr/all_ocr.jsonl."""
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            yield {
                "bates_number": obj.get("bates_number"),
                "text": obj.get("text") or obj.get("ocr_text") or "",
                "volume": obj.get("volume") or obj.get("source_volume"),
                "page_count": obj.get("page_count") or obj.get("total_pages"),
                "confidence": obj.get("confidence") or obj.get("ocr_confidence"),
            }


def resolve_source():
    """Pick the best available local source file and its reader."""
    if PARQUET_PATH.exists():
        return PARQUET_PATH, iter_parquet
    if JSONL_PATH.exists():
        return JSONL_PATH, iter_jsonl
    return None, None


# --- Commands ---


def cmd_download(args):
    """Download the canonical OCR jsonl from HuggingFace."""
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("ERROR: huggingface_hub not installed.", file=sys.stderr)
        print("Install with: uv pip install huggingface_hub", file=sys.stderr)
        sys.exit(1)

    JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if JSONL_PATH.exists() and not args.force:
        size_mb = JSONL_PATH.stat().st_size / 1024 / 1024
        print(f"File already exists: {JSONL_PATH} ({size_mb:.1f} MB)")
        print("Use --force to re-download.")
        return

    print(f"Downloading {HF_REPO}/{HF_OCR_FILE}...")
    downloaded = hf_hub_download(
        HF_REPO,
        HF_OCR_FILE,
        repo_type="dataset",
        local_dir=str(JSONL_PATH.parent),
    )
    # hf_hub_download nests under the file's repo path (ocr/all_ocr.jsonl)
    nested = JSONL_PATH.parent / HF_OCR_FILE
    if nested.exists() and nested != JSONL_PATH:
        nested.replace(JSONL_PATH)
    size_mb = JSONL_PATH.stat().st_size / 1024 / 1024 if JSONL_PATH.exists() else 0
    print(f"Downloaded: {JSONL_PATH} ({size_mb:.1f} MB) [from {downloaded}]")


def cmd_ingest(args):
    """Parse the source file into SQLite with FTS5."""
    src_path, reader = resolve_source()
    if not src_path:
        print(f"ERROR: No source found at {PARQUET_PATH} or {JSONL_PATH}", file=sys.stderr)
        print("Run 'python tools/ingest_fbi_files.py download' first.", file=sys.stderr)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_db(create=True)
    init_db(db)

    existing = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if existing > 0 and not args.force:
        print(f"Database already has {existing:,} documents.")
        print("Use --force to re-ingest (will drop and recreate).")
        db.close()
        return

    if existing > 0 and args.force:
        print("Dropping existing data...")
        db.execute("DELETE FROM documents")
        db.execute("DELETE FROM documents_fts")
        db.commit()

    print(f"Ingesting from: {src_path}")
    size_mb = src_path.stat().st_size / 1024 / 1024
    print(f"File size: {size_mb:.1f} MB")

    count = 0
    skipped = 0
    batch = []
    batch_size = 500

    for rec in reader(src_path):
        bates = rec["bates_number"]
        if not bates:
            skipped += 1
            continue
        text = rec["text"] or ""
        efta = extract_efta(bates)
        char_count = len(text)
        word_count = len(text.split())
        page_count = int(rec["page_count"]) if rec["page_count"] is not None else None
        confidence = float(rec["confidence"]) if rec["confidence"] is not None else None

        batch.append((bates, efta, rec["volume"], page_count, confidence,
                      text, char_count, word_count))
        count += 1

        if len(batch) >= batch_size:
            db.executemany(
                """INSERT OR IGNORE INTO documents
                   (bates_number, efta_id, volume, page_count, confidence,
                    text, char_count, word_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )
            db.commit()
            batch = []
            if count % 2000 == 0:
                print(f"  ... {count:,} documents ingested")

    if batch:
        db.executemany(
            """INSERT OR IGNORE INTO documents
               (bates_number, efta_id, volume, page_count, confidence,
                text, char_count, word_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )
        db.commit()

    final_count = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    db.close()

    print(f"\nIngestion complete:")
    print(f"  Documents: {final_count:,}")
    print(f"  Skipped (no bates): {skipped}")
    print(f"  Database: {DB_PATH}")
    print(f"  Size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")


def cmd_search(args):
    """FTS5 full-text search across all documents."""
    db = get_db()
    query = literal_fts_query(args.query)

    sql = """
        SELECT
            d.id,
            d.bates_number,
            d.efta_id,
            d.char_count,
            d.word_count,
            d.confidence,
            snippet(documents_fts, 1, '>>>', '<<<', '...', 64) as snippet
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
    """
    params = [query]
    if args.min_chars:
        sql += " AND d.char_count >= ?"
        params.append(args.min_chars)
    sql += " ORDER BY rank LIMIT ?"
    params.append(args.limit)

    rows = db.execute(sql, params).fetchall()

    count_sql = """
        SELECT COUNT(*)
        FROM documents_fts
        JOIN documents d ON d.id = documents_fts.rowid
        WHERE documents_fts MATCH ?
    """
    count_params = [query]
    if args.min_chars:
        count_sql += " AND d.char_count >= ?"
        count_params.append(args.min_chars)
    total = db.execute(count_sql, count_params).fetchone()[0]

    results = [dict(r) for r in rows]
    if write_output(
        results,
        args,
        summary=f"FBI Epstein Files search '{args.query}': {total} matches",
    ):
        db.close()
        return

    filt = f" (min_chars={args.min_chars})" if args.min_chars else ""
    print(f"Search: '{args.query}'{filt} -- {total} matches (showing {len(rows)})")
    print()

    for r in rows:
        bates = r["bates_number"]
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "?"
        print(f"  {bates} ({r['char_count']:,} chars / {r['word_count']:,} words / conf {conf})")
        snippet = (r["snippet"] or "").replace("\n", " ").strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        print(f"    {snippet}")
        print()

    if args.json_out:
        print(json.dumps([dict(r) for r in rows], indent=2, default=str))

    db.close()


def cmd_doc(args):
    """Retrieve a specific document by bates number / EFTA id."""
    db = get_db()
    raw = args.doc_id

    # Normalize a bare number or efta id
    candidates = [raw]
    if raw.isdigit():
        candidates.append(f"EFTA{int(raw):08d}")
    norm = raw.upper()
    if norm.startswith("EFTA"):
        candidates.append(norm)

    rows = []
    for cand in candidates:
        rows = db.execute(
            "SELECT * FROM documents WHERE bates_number = ? OR efta_id = ?",
            [cand, cand],
        ).fetchall()
        if rows:
            break

    if not rows:
        rows = db.execute(
            "SELECT * FROM documents WHERE bates_number LIKE ?",
            [f"%{raw}%"],
        ).fetchall()

    if not rows:
        print(f"Document not found: {raw}")
        db.close()
        sys.exit(1)

    for r in rows:
        conf = f"{r['confidence']:.3f}" if r["confidence"] is not None else "?"
        print(f"=== {r['bates_number']} ===")
        print(f"EFTA: {r['efta_id'] or '-'} | volume: {r['volume'] or '-'} | "
              f"pages: {r['page_count'] or '?'} | {r['char_count']:,} chars | "
              f"{r['word_count']:,} words | OCR conf {conf}")
        print("-" * 60)
        text = r["text"]
        if args.full or len(text) <= args.chars:
            print(text)
        else:
            print(text[:args.chars])
            print(f"\n... [{len(text) - args.chars:,} more chars, use --full for complete text]")
        print()

    if args.json_out:
        print(json.dumps([dict(r) for r in rows], indent=2, default=str))

    db.close()


def cmd_stats(args):
    """Database statistics."""
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    total_chars = db.execute("SELECT SUM(char_count) FROM documents").fetchone()[0] or 0
    total_words = db.execute("SELECT SUM(word_count) FROM documents").fetchone()[0] or 0
    avg_chars = db.execute("SELECT AVG(char_count) FROM documents").fetchone()[0] or 0
    max_chars = db.execute("SELECT MAX(char_count) FROM documents").fetchone()[0] or 0
    empty = db.execute("SELECT COUNT(*) FROM documents WHERE char_count = 0").fetchone()[0]
    named = db.execute("SELECT COUNT(*) FROM documents WHERE efta_id IS NULL").fetchone()[0]
    avg_conf = db.execute("SELECT AVG(confidence) FROM documents WHERE confidence IS NOT NULL").fetchone()[0]

    efta_range = db.execute("""
        SELECT
            MIN(CAST(REPLACE(efta_id, 'EFTA', '') AS INTEGER)),
            MAX(CAST(REPLACE(efta_id, 'EFTA', '') AS INTEGER))
        FROM documents WHERE efta_id IS NOT NULL
    """).fetchone()

    print(f"=== FBI Epstein Files Database ===")
    print(f"  Source: {HF_REPO}")
    print(f"  Database: {DB_PATH}")
    print(f"  DB size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print()
    print(f"Documents: {total:,}")
    if efta_range[0] is not None:
        print(f"  EFTA-numbered: {total - named:,} "
              f"(EFTA{efta_range[0]:08d} - EFTA{efta_range[1]:08d})")
    print(f"  Named exhibits (no EFTA): {named}")
    print(f"  Empty (no OCR text): {empty}")
    if avg_conf is not None:
        print(f"  Avg OCR confidence: {avg_conf:.3f}")
    print()
    print(f"Text statistics:")
    print(f"  Total chars: {total_chars:,} ({total_chars / 1024 / 1024:.1f} MB)")
    print(f"  Total words: {total_words:,}")
    print(f"  Avg chars/doc: {avg_chars:,.0f}")
    print(f"  Max chars: {max_chars:,}")
    print()

    print("Document size distribution:")
    brackets = [
        (0, 0, "empty"),
        (1, 100, "tiny (<100 chars)"),
        (100, 500, "small (100-500)"),
        (500, 2000, "medium (500-2K)"),
        (2000, 10000, "large (2K-10K)"),
        (10000, 50000, "very large (10K-50K)"),
        (50000, None, "huge (50K+)"),
    ]
    for lo, hi, label in brackets:
        if hi is None:
            cnt = db.execute("SELECT COUNT(*) FROM documents WHERE char_count >= ?", [lo]).fetchone()[0]
        else:
            cnt = db.execute(
                "SELECT COUNT(*) FROM documents WHERE char_count >= ? AND char_count < ?",
                [lo, hi],
            ).fetchone()[0]
        if cnt > 0:
            print(f"  {label}: {cnt:,}")

    # Named exhibits are the headline FBI items — list them
    print()
    print("Named exhibits:")
    for r in db.execute(
        "SELECT bates_number, char_count FROM documents WHERE efta_id IS NULL ORDER BY bates_number"
    ).fetchall():
        print(f"  {r['bates_number']} ({r['char_count']:,} chars)")

    db.close()


def cmd_overlap(args):
    """Cross-reference EFTA ids with existing investigation databases."""
    db = get_db()

    print("=== Cross-Reference with Existing Databases ===\n")

    fbi_efta = set()
    for r in db.execute("SELECT DISTINCT efta_id FROM documents WHERE efta_id IS NOT NULL"):
        fbi_efta.add(r["efta_id"])
    print(f"This dataset: {len(fbi_efta):,} unique EFTA IDs (FBI release)")

    # LMSBAND — DOJ EFTA datasets
    lms_path = BASE_DIR / "datasets" / "lmsband_epstein_files.db"
    if lms_path.exists():
        lms = sqlite3.connect(str(lms_path))
        lms_efta = set()
        for (fn,) in lms.execute("SELECT filename FROM files WHERE filename LIKE 'EFTA%'"):
            m = EFTA_RE.search(fn or "")
            if m:
                lms_efta.add(m.group(1))
        lms.close()
        overlap = fbi_efta & lms_efta
        only_fbi = fbi_efta - lms_efta
        print(f"\nLMSBAND (DOJ EFTA datasets): {len(lms_efta):,} EFTA IDs")
        print(f"  Shared Bates numbers: {len(overlap):,} "
              f"({100 * len(overlap) / max(1, len(fbi_efta)):.0f}% of FBI set)")
        print(f"  FBI-only Bates numbers: {len(only_fbi):,}")
        print(f"  CAVEAT: shared EFTA Bates number != proven identical document "
              f"(production-specific numbering).")
    else:
        print("\nLMSBAND: not found")

    # 20K House Oversight — different scheme
    ho_path = BASE_DIR / "datasets" / "epstein_files_20k.db"
    if ho_path.exists():
        ho = sqlite3.connect(str(ho_path))
        ho_count = ho.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        ho.close()
        print(f"\nHouse Oversight 20K: {ho_count:,} docs (HOUSE_OVERSIGHT IDs)")
        print(f"  NOTE: different release/scheme (HOUSE_OVERSIGHT vs EFTA) — no Bates overlap.")
    else:
        print("\nHouse Oversight 20K: not found")

    # OCR quality sample
    print("\n--- OCR Quality Sample ---")
    sample = db.execute(
        "SELECT bates_number, text FROM documents WHERE char_count > 500 ORDER BY RANDOM() LIMIT 1"
    ).fetchone()
    if sample:
        text = sample["text"][:500]
        alpha = sum(1 for c in text if c.isalpha())
        ratio = alpha / max(len(text), 1) * 100
        print(f"  Sample doc: {sample['bates_number']}")
        print(f"  Alpha ratio: {ratio:.1f}% (higher = cleaner OCR)")
        print(f"  First 300 chars: {text[:300]}")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest and query the FBI Epstein Files dataset (svetfm/epstein-fbi-files)"
    )
    subs = parser.add_subparsers(dest="command", help="Command to run")

    p_dl = subs.add_parser("download", help="Download ocr/all_ocr.jsonl from HuggingFace")
    p_dl.add_argument("--force", action="store_true", help="Re-download if exists")

    p_in = subs.add_parser("ingest", help="Parse source into SQLite with FTS5")
    p_in.add_argument("--force", action="store_true", help="Drop and re-ingest")

    p_s = subs.add_parser("search", help="FTS5 full-text search")
    p_s.add_argument("query", help="Search query (FTS5 syntax)")
    p_s.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_s.add_argument("--min-chars", type=int, help="Minimum document size in chars")
    add_output_args(p_s)

    p_d = subs.add_parser("doc", help="Retrieve a specific document")
    p_d.add_argument("doc_id", help="EFTA id (EFTA00000001 or 1) or named exhibit substring")
    p_d.add_argument("--full", action="store_true", help="Show full text")
    p_d.add_argument("--chars", type=int, default=2000, help="Max chars to show (default: 2000)")
    p_d.add_argument("--json", dest="json_out", action="store_true", help="Output JSON")

    subs.add_parser("stats", help="Database statistics")
    subs.add_parser("overlap", help="Cross-reference with existing databases")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "download": cmd_download,
        "ingest": cmd_ingest,
        "search": cmd_search,
        "doc": cmd_doc,
        "stats": cmd_stats,
        "overlap": cmd_overlap,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
