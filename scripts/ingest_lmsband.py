#!/usr/bin/env python3
"""Ingest LMSBAND/epstein-files-db into the unified database."""

import sqlite3
import re
import hashlib

DB_PATH = "datasets/unified_epstein.db"
LMSBAND_PATH = "datasets/lmsband_epstein_files.db"


def content_hash(text):
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    return hashlib.md5(normalized.encode()).hexdigest()


def ingest_documents(dst, src):
    """Add LMSBAND documents to unified DB's documents table."""
    existing = set(r[0] for r in dst.execute("SELECT content_hash FROM documents").fetchall())

    rows = src.execute("""
        SELECT f.id, f.filename, f.dataset, f.rel_path,
               tc.extracted_text, tc.char_count, tc.method
        FROM text_cache tc
        JOIN files f ON f.id = tc.file_id
        WHERE tc.char_count > 200
    """).fetchall()

    count = 0
    for r in rows:
        text = r[4] or ''
        if len(text.strip()) < 100:
            continue

        ch = content_hash(text[:2000])
        if ch in existing:
            continue
        existing.add(ch)

        doc_id = r[1]  # filename like EFTA01360644.pdf
        dataset_num = r[2]

        dst.execute("""
            INSERT INTO documents (source_dataset, doc_id, category, summary, full_text,
                date_earliest, date_latest, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f'lmsband_ds{dataset_num}',
            doc_id,
            f'doj_dataset_{dataset_num}',
            '',
            text,
            '',
            '',
            ch
        ))
        count += 1

        if count % 5000 == 0:
            print(f"  ... {count} documents ingested")
            dst.commit()

    dst.commit()
    return count


def ingest_entities(dst, src):
    """Add LMSBAND entities to unified DB."""
    # Get top entities (normalized, with count > 5 across files)
    rows = src.execute("""
        SELECT normalized, entity_label, COUNT(DISTINCT file_id) as file_count
        FROM entities
        WHERE normalized IS NOT NULL AND length(normalized) > 2
        GROUP BY normalized, entity_label
        HAVING file_count >= 3
        ORDER BY file_count DESC
    """).fetchall()

    existing = set(r[0].lower() for r in dst.execute("SELECT canonical_name FROM entities").fetchall())
    count = 0

    for r in rows:
        name = r[0]
        if name.lower() in existing:
            continue
        existing.add(name.lower())

        dst.execute("""
            INSERT INTO entities (canonical_name, hop_distance, source)
            VALUES (?, ?, ?)
        """, (name, -1, f'lmsband_{r[1]}'))
        count += 1

    dst.commit()
    return count


def ingest_cooccurrences(dst, src):
    """Create entity_cooccurrence table in unified DB."""
    dst.execute("""
        CREATE TABLE IF NOT EXISTS entity_cooccurrence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_a TEXT,
            entity_b TEXT,
            file_count INTEGER,
            label_a TEXT,
            label_b TEXT,
            source TEXT
        )
    """)
    dst.execute("CREATE INDEX IF NOT EXISTS idx_cooc_a ON entity_cooccurrence(entity_a)")
    dst.execute("CREATE INDEX IF NOT EXISTS idx_cooc_b ON entity_cooccurrence(entity_b)")

    rows = src.execute("""
        SELECT entity_a, entity_b, file_count, label_a, label_b
        FROM entity_cooccurrence
        WHERE file_count >= 3
    """).fetchall()

    for r in rows:
        dst.execute("""
            INSERT INTO entity_cooccurrence (entity_a, entity_b, file_count, label_a, label_b, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (r[0], r[1], r[2], r[3], r[4], 'lmsband'))

    dst.commit()
    return len(rows)


def main():
    dst = sqlite3.connect(DB_PATH)
    src = sqlite3.connect(LMSBAND_PATH)

    print("Ingesting LMSBAND documents...")
    n_docs = ingest_documents(dst, src)
    print(f"  Added {n_docs} unique documents")

    print("Ingesting LMSBAND entities...")
    n_ents = ingest_entities(dst, src)
    print(f"  Added {n_ents} unique entities")

    print("Ingesting entity co-occurrences...")
    n_cooc = ingest_cooccurrences(dst, src)
    print(f"  Added {n_cooc} co-occurrence pairs")

    # Rebuild FTS for documents
    print("Rebuilding documents FTS...")
    dst.execute("INSERT INTO documents_fts(documents_fts) VALUES('rebuild')")
    dst.commit()

    # Stats
    print(f"\n=== UPDATED UNIFIED DATABASE ===")
    for table in ['emails', 'documents', 'triples', 'entities', 'entity_cooccurrence']:
        try:
            count = dst.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: {count}")
        except:
            pass

    src.close()
    dst.close()


if __name__ == "__main__":
    main()
