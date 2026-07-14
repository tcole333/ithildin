#!/usr/bin/env python3
"""
Ingest and query the kabasshouse/epstein-data dataset.

The most complete single downloadable Epstein corpus as of mid-2026:
~1.42M logical documents (2.84M page-level rows) fully OCR'd, spanning DOJ
DataSets 1-12 + FBI Vault + House Oversight, plus structured layers not present
in our other corpora (financial transactions, named entities, curated "gold"
docs, communication/investigative records).

Canonical remote: https://huggingface.co/datasets/kabasshouse/epstein-data
  (Parquet, CC-BY-4.0, last modified 2026-03-01)

We DELIBERATELY skip two of the dataset's configs:
  - embeddings_chunk (11.6 GB of 768-dim vectors -- no vector-search use here)
  - chunks (1.2 GB of text chunks -- redundant with documents.full_text)
Everything else (~1.4 GB) is pulled.

OCR provenance: 856K files via Gemini 2.5 Flash-Lite (structured JSON),
531K via Tesseract. See the `ocr_source` column and PROVENANCE.md upstream.

NOTE ON OVERLAP: this corpus re-OCRs the SAME primary DOJ/FBI/House releases we
already hold in documents.db / lmsband / unified / epstein_fbi_files. A matching
`file_key` (EFTA Bates) is the same underlying page, re-OCR'd -- treat as a
higher-quality re-extraction, NOT independent corroboration. The genuinely new
capability is the structured financial / entity / curated layers.

Download mechanism: DuckDB httpfs reads the remote `hf://` Parquet directly
(no huggingface_hub dependency required).

Database: datasets/kabasshouse_epstein.db (SQLite with FTS5)

Usage:
    python tools/ingest_kabasshouse.py download          # pull wanted configs -> local parquet
    python tools/ingest_kabasshouse.py ingest            # build SQLite + FTS5
    python tools/ingest_kabasshouse.py search "query"    # full-text search documents
    python tools/ingest_kabasshouse.py doc <file_key>    # retrieve a document's pages
    python tools/ingest_kabasshouse.py financials --cardholder "Epstein" --limit 20
    python tools/ingest_kabasshouse.py entity "Wexner"   # entity lookup
    python tools/ingest_kabasshouse.py curated --subject <subject>
    python tools/ingest_kabasshouse.py stats
    python tools/ingest_kabasshouse.py overlap           # cross-ref with existing DBs
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
    from tools.fts_query import literal_fts_query
except ImportError:
    from output_util import add_output_args, write_output
    from fts_query import literal_fts_query

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "datasets" / "kabasshouse_epstein.db"
PARQUET_DIR = BASE_DIR / "datasets" / "kabasshouse"

HF_BASE = "hf://datasets/kabasshouse/epstein-data/data"

# Configs we pull (name -> remote glob). Ordered small-to-large is not required;
# `documents` is the big one. embeddings_chunk / chunks are intentionally absent.
#
# IMPORTANT: each config dir contains TWO export generations -- a canonical
# `<cfg>-NNNNN-of-MMMMM.parquet` sharded set and an older bare `<cfg>-NNNNN.parquet`
# set with a DIFFERENT (id-less) schema. Globbing `*.parquet` double-counts and
# fails on schema mismatch. We match only the canonical `*-of-*.parquet` shards.
CONFIGS = {
    "documents": "documents/documents-*-of-*.parquet",
    "entities": "entities/entities-*-of-*.parquet",
    "financial_transactions": "financial_transactions/*-of-*.parquet",
    "curated_docs": "curated_docs/*-of-*.parquet",
    "communication_records": "communication_records/*-of-*.parquet",
    "investigative_records": "investigative_records/*-of-*.parquet",
    "persons": "persons/persons-*-of-*.parquet",
}

# Columns kept per table (rest dropped). None => keep all columns found.
DOC_COLS = [
    "id", "file_key", "dataset", "document_type", "date", "ocr_source",
    "page_number", "document_number", "is_photo", "has_handwriting",
    "has_stamps", "char_count", "email_fields", "full_text",
]


def get_db(create=False):
    if not create and not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        print("Run 'python tools/ingest_kabasshouse.py ingest' first.", file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def init_db(db):
    """Create tables and the documents FTS5 index."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            file_key TEXT,
            dataset TEXT,
            document_type TEXT,
            date TEXT,
            ocr_source TEXT,
            page_number INTEGER,
            document_number TEXT,
            is_photo INTEGER,
            has_handwriting INTEGER,
            has_stamps INTEGER,
            char_count INTEGER,
            email_fields TEXT,
            full_text TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kbh_filekey ON documents(file_key);
        CREATE INDEX IF NOT EXISTS idx_kbh_dataset ON documents(dataset);
        CREATE INDEX IF NOT EXISTS idx_kbh_doctype ON documents(document_type);

        CREATE TABLE IF NOT EXISTS entities (
            id TEXT,
            document_id TEXT,
            entity_type TEXT,
            value TEXT,
            normalized_value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kbh_ent_doc ON entities(document_id);
        CREATE INDEX IF NOT EXISTS idx_kbh_ent_norm ON entities(normalized_value);
        CREATE INDEX IF NOT EXISTS idx_kbh_ent_type ON entities(entity_type);

        CREATE TABLE IF NOT EXISTS financial_transactions (
            id TEXT, file_key TEXT, dataset TEXT, transaction_date TEXT,
            amount TEXT, currency TEXT, merchant_name TEXT, merchant_raw TEXT,
            merchant_category TEXT, location TEXT, cardholder TEXT,
            description TEXT, card_type TEXT, account_digits TEXT,
            statement_date TEXT, flight_from TEXT, flight_to TEXT,
            flight_carrier TEXT, flight_departure TEXT, flight_ticket TEXT,
            flight_passenger TEXT, source_page TEXT, extraction_model TEXT,
            extraction_confidence TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kbh_fin_card ON financial_transactions(cardholder);
        CREATE INDEX IF NOT EXISTS idx_kbh_fin_merch ON financial_transactions(merchant_name);

        CREATE TABLE IF NOT EXISTS curated_docs (
            id TEXT, file_key TEXT, subject TEXT, status TEXT, tier TEXT,
            category TEXT, doc_date TEXT, doc_from TEXT, doc_to TEXT,
            headline TEXT, key_quote TEXT, detail TEXT, thread_value TEXT,
            also_appears_as TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_kbh_cur_subj ON curated_docs(subject);

        CREATE TABLE IF NOT EXISTS communication_records (data TEXT);
        CREATE TABLE IF NOT EXISTS investigative_records (data TEXT);
        CREATE TABLE IF NOT EXISTS persons (data TEXT);
    """)

    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'"
    ).fetchone()
    if not row:
        db.execute("""
            CREATE VIRTUAL TABLE documents_fts USING fts5(
                file_key,
                full_text,
                content=documents,
                content_rowid=rowid,
                tokenize='porter unicode61'
            );
        """)
    db.commit()


def _duckdb():
    try:
        import duckdb
    except ImportError:
        print("ERROR: duckdb not installed (uv add duckdb).", file=sys.stderr)
        sys.exit(1)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    return con


def cmd_download(args):
    """Copy the wanted remote configs to local single-file parquet."""
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    con = _duckdb()
    for name, glob in CONFIGS.items():
        out = PARQUET_DIR / f"{name}.parquet"
        if out.exists() and not args.force:
            mb = out.stat().st_size / 1024 / 1024
            print(f"  {name}: already present ({mb:.1f} MB) -- skip (use --force)")
            continue
        src = f"{HF_BASE}/{glob}"
        print(f"  {name}: downloading from {src} ...")
        con.execute(
            f"COPY (SELECT * FROM read_parquet('{src}', union_by_name=true)) "
            f"TO '{out}' (FORMAT parquet)"
        )
        mb = out.stat().st_size / 1024 / 1024
        n = con.execute(f"SELECT COUNT(*) FROM read_parquet('{out}')").fetchone()[0]
        print(f"    -> {out.name}: {n:,} rows ({mb:.1f} MB)")
    print("Download complete.")


def _iter_parquet(path, batch_size=2000):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(str(path))
    for batch in pf.iter_batches(batch_size=batch_size):
        cols = batch.to_pydict()
        n = batch.num_rows
        for i in range(n):
            yield {k: cols[k][i] for k in cols}


def _jsonify(v):
    """Serialize struct/list cells to JSON text; pass scalars through."""
    if v is None:
        return None
    if isinstance(v, (dict, list)):
        return json.dumps(v, default=str)
    return v


def _ingest_documents(db, path, force):
    existing = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if existing and not force:
        print(f"  documents: {existing:,} already present -- skip (use --force)")
        return
    if existing and force:
        db.execute("DELETE FROM documents")
        db.execute("DELETE FROM documents_fts")
        db.commit()

    count, batch = 0, []
    for rec in _iter_parquet(path):
        row = (
            str(rec.get("id")),
            rec.get("file_key"),
            str(rec.get("dataset")) if rec.get("dataset") is not None else None,
            rec.get("document_type"),
            str(rec.get("date")) if rec.get("date") is not None else None,
            rec.get("ocr_source"),
            rec.get("page_number"),
            str(rec.get("document_number")) if rec.get("document_number") is not None else None,
            1 if rec.get("is_photo") else 0,
            1 if rec.get("has_handwriting") else 0,
            1 if rec.get("has_stamps") else 0,
            rec.get("char_count"),
            _jsonify(rec.get("email_fields")),
            rec.get("full_text") or "",
        )
        batch.append(row)
        count += 1
        if len(batch) >= 1000:
            db.executemany(
                "INSERT OR IGNORE INTO documents "
                "(id, file_key, dataset, document_type, date, ocr_source, "
                "page_number, document_number, is_photo, has_handwriting, "
                "has_stamps, char_count, email_fields, full_text) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            db.commit()
            batch = []
            if count % 50000 == 0:
                print(f"    ... {count:,} document pages")
    if batch:
        db.executemany(
            "INSERT OR IGNORE INTO documents "
            "(id, file_key, dataset, document_type, date, ocr_source, "
            "page_number, document_number, is_photo, has_handwriting, "
            "has_stamps, char_count, email_fields, full_text) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        db.commit()

    print("  documents: rebuilding FTS5 index ...")
    db.execute(
        "INSERT INTO documents_fts(rowid, file_key, full_text) "
        "SELECT rowid, file_key, full_text FROM documents"
    )
    db.commit()
    final = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    print(f"  documents: {final:,} pages ingested + indexed")


def _ingest_flat(db, path, table, columns, force):
    """Ingest a small table selecting a fixed column list."""
    existing = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if existing and not force:
        print(f"  {table}: {existing:,} already present -- skip")
        return
    if existing and force:
        db.execute(f"DELETE FROM {table}")
        db.commit()
    placeholders = ",".join("?" * len(columns))
    collist = ",".join(columns)
    count, batch = 0, []
    for rec in _iter_parquet(path):
        batch.append(tuple(_jsonify(rec.get(c)) for c in columns))
        count += 1
        if len(batch) >= 1000:
            db.executemany(
                f"INSERT INTO {table} ({collist}) VALUES ({placeholders})", batch)
            db.commit()
            batch = []
    if batch:
        db.executemany(
            f"INSERT INTO {table} ({collist}) VALUES ({placeholders})", batch)
        db.commit()
    print(f"  {table}: {count:,} rows ingested")


def _ingest_blob(db, path, table, force):
    """Ingest an arbitrary-schema small table as one JSON column per row."""
    existing = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if existing and not force:
        print(f"  {table}: {existing:,} already present -- skip")
        return
    if existing and force:
        db.execute(f"DELETE FROM {table}")
        db.commit()
    count, batch = 0, []
    for rec in _iter_parquet(path):
        batch.append((json.dumps(rec, default=str),))
        count += 1
        if len(batch) >= 1000:
            db.executemany(f"INSERT INTO {table} (data) VALUES (?)", batch)
            db.commit()
            batch = []
    if batch:
        db.executemany(f"INSERT INTO {table} (data) VALUES (?)", batch)
        db.commit()
    print(f"  {table}: {count:,} rows ingested")


FIN_COLS = [
    "id", "file_key", "dataset", "transaction_date", "amount", "currency",
    "merchant_name", "merchant_raw", "merchant_category", "location",
    "cardholder", "description", "card_type", "account_digits",
    "statement_date", "flight_from", "flight_to", "flight_carrier",
    "flight_departure", "flight_ticket", "flight_passenger", "source_page",
    "extraction_model", "extraction_confidence",
]
CUR_COLS = [
    "id", "file_key", "subject", "status", "tier", "category", "doc_date",
    "doc_from", "doc_to", "headline", "key_quote", "detail", "thread_value",
    "also_appears_as",
]
ENT_COLS = ["id", "document_id", "entity_type", "value", "normalized_value"]


def cmd_ingest(args):
    if not PARQUET_DIR.exists() or not (PARQUET_DIR / "documents.parquet").exists():
        print(f"ERROR: no local parquet in {PARQUET_DIR}", file=sys.stderr)
        print("Run 'python tools/ingest_kabasshouse.py download' first.", file=sys.stderr)
        sys.exit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = get_db(create=True)
    init_db(db)

    p = PARQUET_DIR
    if (p / "documents.parquet").exists():
        _ingest_documents(db, p / "documents.parquet", args.force)
    if (p / "entities.parquet").exists():
        _ingest_flat(db, p / "entities.parquet", "entities", ENT_COLS, args.force)
    if (p / "financial_transactions.parquet").exists():
        _ingest_flat(db, p / "financial_transactions.parquet",
                     "financial_transactions", FIN_COLS, args.force)
    if (p / "curated_docs.parquet").exists():
        _ingest_flat(db, p / "curated_docs.parquet", "curated_docs", CUR_COLS, args.force)
    for name in ("communication_records", "investigative_records", "persons"):
        fp = p / f"{name}.parquet"
        if fp.exists():
            _ingest_blob(db, fp, name, args.force)

    db.execute("PRAGMA optimize")
    db.close()
    print(f"\nIngestion complete. Database: {DB_PATH}")
    print(f"  Size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")


def cmd_search(args):
    db = get_db()
    sql = """
        SELECT d.id, d.file_key, d.dataset, d.document_type, d.date,
               d.ocr_source, d.char_count,
               snippet(documents_fts, 1, '>>>', '<<<', '...', 64) AS snippet
        FROM documents_fts
        JOIN documents d ON d.rowid = documents_fts.rowid
        WHERE documents_fts MATCH ?
    """
    params = [literal_fts_query(args.query)]
    if args.dataset:
        sql += " AND d.dataset = ?"
        params.append(args.dataset)
    if args.min_chars:
        sql += " AND d.char_count >= ?"
        params.append(args.min_chars)
    sql += " ORDER BY rank LIMIT ?"
    params.append(args.limit)
    rows = db.execute(sql, params).fetchall()

    results = [dict(r) for r in rows]
    if write_output(results, args, summary=f"Kabasshouse search '{args.query}'"):
        db.close()
        return

    print(f"Search: '{args.query}' -- showing {len(rows)}")
    print()
    for r in rows:
        print(f"  {r['file_key']}  [ds {r['dataset']} | {r['document_type'] or '-'} | "
              f"{r['date'] or '-'} | {r['ocr_source']} | {r['char_count']} chars]")
        snip = (r["snippet"] or "").replace("\n", " ").strip()
        print(f"    {snip[:400]}")
        print()
    if args.json_out:
        print(json.dumps(results, indent=2, default=str))
    db.close()


def cmd_doc(args):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM documents WHERE file_key = ? OR id = ? "
        "ORDER BY page_number", [args.doc_id, args.doc_id]
    ).fetchall()
    if not rows:
        rows = db.execute(
            "SELECT * FROM documents WHERE file_key LIKE ? ORDER BY page_number LIMIT 50",
            [f"%{args.doc_id}%"]
        ).fetchall()
    if not rows:
        print(f"Document not found: {args.doc_id}")
        db.close()
        sys.exit(1)
    for r in rows:
        print(f"=== {r['file_key']} (page {r['page_number']}) ===")
        print(f"ds {r['dataset']} | {r['document_type'] or '-'} | {r['date'] or '-'} | "
              f"OCR {r['ocr_source']} | {r['char_count']} chars")
        if r["email_fields"]:
            print(f"email_fields: {r['email_fields']}")
        print("-" * 60)
        text = r["full_text"] or ""
        print(text if (args.full or len(text) <= args.chars) else text[:args.chars] + "\n...")
        print()
    db.close()


def cmd_financials(args):
    db = get_db()
    sql = "SELECT * FROM financial_transactions WHERE 1=1"
    params = []
    if args.cardholder:
        sql += " AND cardholder LIKE ?"
        params.append(f"%{args.cardholder}%")
    if args.merchant:
        sql += " AND merchant_name LIKE ?"
        params.append(f"%{args.merchant}%")
    sql += " LIMIT ?"
    params.append(args.limit)
    rows = db.execute(sql, params).fetchall()
    print(f"Transactions: {len(rows)}")
    for r in rows:
        print(f"  {r['transaction_date'] or '-'}  {r['amount'] or '-'} {r['currency'] or ''}  "
              f"{r['merchant_name'] or r['merchant_raw'] or '-'}  "
              f"[{r['cardholder'] or '-'} | {r['file_key']}]")
    if args.json_out:
        print(json.dumps([dict(r) for r in rows], indent=2, default=str))
    db.close()


def cmd_entity(args):
    db = get_db()
    rows = db.execute(
        "SELECT entity_type, value, normalized_value, COUNT(*) AS n "
        "FROM entities WHERE value LIKE ? OR normalized_value LIKE ? "
        "GROUP BY entity_type, normalized_value ORDER BY n DESC LIMIT ?",
        [f"%{args.name}%", f"%{args.name}%", args.limit]
    ).fetchall()
    print(f"Entity matches for '{args.name}': {len(rows)}")
    for r in rows:
        print(f"  [{r['entity_type']}] {r['normalized_value'] or r['value']}  x{r['n']}")
    db.close()


def cmd_curated(args):
    db = get_db()
    sql = "SELECT subject, tier, headline, doc_date, key_quote FROM curated_docs WHERE 1=1"
    params = []
    if args.subject:
        sql += " AND subject = ?"
        params.append(args.subject)
    sql += " LIMIT ?"
    params.append(args.limit)
    rows = db.execute(sql, params).fetchall()
    if not args.subject:
        subs = db.execute(
            "SELECT subject, COUNT(*) n FROM curated_docs GROUP BY subject ORDER BY n DESC"
        ).fetchall()
        print("Subjects:", ", ".join(f"{s['subject']}({s['n']})" for s in subs))
        print()
    for r in rows:
        print(f"  [{r['subject']} | tier {r['tier']} | {r['doc_date'] or '-'}] {r['headline']}")
        if r["key_quote"]:
            print(f"    \"{r['key_quote'][:200]}\"")
    db.close()


def cmd_stats(args):
    db = get_db()
    print(f"=== kabasshouse/epstein-data ===")
    print(f"  Database: {DB_PATH}")
    print(f"  DB size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print()
    docs = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    keys = db.execute("SELECT COUNT(DISTINCT file_key) FROM documents").fetchone()[0]
    chars = db.execute("SELECT SUM(char_count) FROM documents").fetchone()[0] or 0
    print(f"Documents: {docs:,} page-rows across {keys:,} unique file_keys")
    print(f"  Total OCR text: {chars/1e6:.0f}M chars")
    print("  By dataset:")
    for r in db.execute(
        "SELECT dataset, COUNT(*) n FROM documents GROUP BY dataset ORDER BY n DESC LIMIT 20"):
        print(f"    {r['dataset']}: {r['n']:,}")
    print("  By OCR source:")
    for r in db.execute("SELECT ocr_source, COUNT(*) n FROM documents GROUP BY ocr_source"):
        print(f"    {r['ocr_source']}: {r['n']:,}")
    for tbl in ("entities", "financial_transactions", "curated_docs",
                "communication_records", "investigative_records", "persons"):
        n = db.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"{tbl}: {n:,}")
    db.close()


def cmd_overlap(args):
    """Compare file_key (EFTA) coverage vs existing local DBs."""
    import re
    db = get_db()
    efta_re = re.compile(r"(EFTA\d+)")
    kbh = set()
    for (fk,) in db.execute("SELECT DISTINCT file_key FROM documents WHERE file_key LIKE '%EFTA%'"):
        m = efta_re.search(fk or "")
        if m:
            kbh.add(m.group(1))
    print(f"This corpus: {len(kbh):,} unique EFTA file_keys")

    lms_path = BASE_DIR / "datasets" / "lmsband_epstein_files.db"
    if lms_path.exists():
        lms = sqlite3.connect(str(lms_path))
        lms_efta = set()
        for (fn,) in lms.execute("SELECT filename FROM files WHERE filename LIKE 'EFTA%'"):
            m = efta_re.search(fn or "")
            if m:
                lms_efta.add(m.group(1))
        lms.close()
        ov = kbh & lms_efta
        print(f"\nLMSBAND: {len(lms_efta):,} EFTA IDs")
        print(f"  Shared: {len(ov):,} ({100*len(ov)/max(1,len(kbh)):.0f}% of this corpus)")
        print(f"  In kabasshouse only: {len(kbh - lms_efta):,}")
        print(f"  In LMSBAND only: {len(lms_efta - kbh):,}")
        print("  CAVEAT: shared EFTA = same page re-OCR'd, not independent corroboration.")
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest/query kabasshouse/epstein-data (most complete Epstein corpus)")
    subs = parser.add_subparsers(dest="command")

    p = subs.add_parser("download", help="Pull wanted configs -> local parquet")
    p.add_argument("--force", action="store_true")

    p = subs.add_parser("ingest", help="Build SQLite + FTS5 from local parquet")
    p.add_argument("--force", action="store_true")

    p = subs.add_parser("search", help="FTS5 full-text search of documents")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dataset")
    p.add_argument("--min-chars", type=int)
    p.add_argument("--json", dest="json_out", action="store_true")
    add_output_args(p)

    p = subs.add_parser("doc", help="Retrieve a document's pages by file_key/id")
    p.add_argument("doc_id")
    p.add_argument("--full", action="store_true")
    p.add_argument("--chars", type=int, default=2000)

    p = subs.add_parser("financials", help="Query financial_transactions")
    p.add_argument("--cardholder")
    p.add_argument("--merchant")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--json", dest="json_out", action="store_true")

    p = subs.add_parser("entity", help="Entity lookup")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=30)

    p = subs.add_parser("curated", help="Query curated gold docs")
    p.add_argument("--subject")
    p.add_argument("--limit", type=int, default=30)

    subs.add_parser("stats", help="Database statistics")
    subs.add_parser("overlap", help="Cross-reference EFTA coverage vs local DBs")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    {
        "download": cmd_download, "ingest": cmd_ingest, "search": cmd_search,
        "doc": cmd_doc, "financials": cmd_financials, "entity": cmd_entity,
        "curated": cmd_curated, "stats": cmd_stats, "overlap": cmd_overlap,
    }[args.command](args)


if __name__ == "__main__":
    main()
