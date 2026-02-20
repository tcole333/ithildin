#!/usr/bin/env python3
"""Ingest extracted DS09 files into datasets/lmsband_epstein_files.db."""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path


DEFAULT_DB = Path("datasets/lmsband_epstein_files.db")
DEFAULT_INPUT_DIR = Path("datasets/epstein_files_ds09_extracted")
DEFAULT_EXTENSIONS = "pdf,doc,docx,xls,xlsx,csv,ppt,pptx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest extracted DS09 files into LMSBAND file inventory."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite DB path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Extracted DS09 directory (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--extensions",
        default=DEFAULT_EXTENSIONS,
        help=f"Comma-separated extensions to ingest (default: {DEFAULT_EXTENSIONS})",
    )
    parser.add_argument(
        "--dataset",
        type=int,
        default=9,
        help="Dataset number to assign in files table (default: 9).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Rows per transaction batch (default: 5000).",
    )
    parser.add_argument(
        "--skip-zero-byte",
        action="store_true",
        help="Skip zero-byte files.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after ingesting N new rows (0 = no limit).",
    )
    parser.add_argument(
        "--register-production",
        action="store_true",
        help="Also register rows in production_files.",
    )
    parser.add_argument(
        "--no-skip-existing-filename",
        action="store_true",
        help="Allow duplicate dataset+filename entries (default skips existing DS9 filenames).",
    )
    return parser.parse_args()


def iter_files(input_dir: Path):
    for root, _dirs, files in os.walk(input_dir):
        root_path = Path(root)
        for filename in files:
            yield root_path / filename


def main() -> int:
    args = parse_args()

    if not args.db_path.exists():
        raise SystemExit(f"DB not found: {args.db_path}")
    if not args.input_dir.exists():
        raise SystemExit(f"Input dir not found: {args.input_dir}")

    ext_filter = {e.strip().lower() for e in args.extensions.split(",") if e.strip()}
    if not ext_filter:
        raise SystemExit("No extensions configured.")

    repo_root = Path.cwd().resolve()
    input_dir = args.input_dir.resolve()

    con = sqlite3.connect(args.db_path)
    cur = con.cursor()

    existing_filenames: set[str] = set()
    if not args.no_skip_existing_filename:
        rows = cur.execute(
            "SELECT filename FROM files WHERE dataset = ?",
            (args.dataset,),
        ).fetchall()
        existing_filenames = {row[0] for row in rows}
        print(f"Existing dataset {args.dataset} filenames: {len(existing_filenames)}")

    seen_new_filenames: set[str] = set()
    rows_batch: list[tuple] = []
    prod_batch: list[tuple] = []

    scanned = 0
    inserted = 0
    skipped_ext = 0
    skipped_zero = 0
    skipped_existing_name = 0

    def flush() -> None:
        nonlocal inserted
        if not rows_batch:
            return

        before = con.total_changes
        cur.executemany(
            """
            INSERT OR IGNORE INTO files
              (filename, dataset, rel_path, file_size, has_text, needs_ocr)
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            rows_batch,
        )
        inserted += max(0, con.total_changes - before)

        if args.register_production and prod_batch:
            cur.executemany(
                """
                INSERT OR IGNORE INTO production_files
                  (filename, dataset, rel_path, file_size, file_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                prod_batch,
            )

        con.commit()
        rows_batch.clear()
        prod_batch.clear()

    for path in iter_files(input_dir):
        scanned += 1
        ext = path.suffix.lower().lstrip(".")
        if ext not in ext_filter:
            skipped_ext += 1
            continue

        stat = path.stat()
        if args.skip_zero_byte and stat.st_size == 0:
            skipped_zero += 1
            continue

        filename = path.name
        if (
            not args.no_skip_existing_filename
            and (filename in existing_filenames or filename in seen_new_filenames)
        ):
            skipped_existing_name += 1
            continue

        try:
            rel_path = path.relative_to(repo_root).as_posix()
        except ValueError:
            rel_path = str(path)

        row = (filename, args.dataset, rel_path, stat.st_size)
        rows_batch.append(row)
        if args.register_production:
            prod_batch.append((filename, args.dataset, rel_path, stat.st_size, ext))

        seen_new_filenames.add(filename)

        if len(rows_batch) >= args.batch_size:
            flush()
            if inserted and inserted % 50000 == 0:
                print(f"Inserted {inserted:,} rows...")

        if args.limit and inserted >= args.limit:
            break

    flush()

    total_ds = cur.execute(
        "SELECT COUNT(*) FROM files WHERE dataset = ?",
        (args.dataset,),
    ).fetchone()[0]
    text_ds = cur.execute(
        """
        SELECT COUNT(*)
        FROM text_cache tc
        JOIN files f ON f.id = tc.file_id
        WHERE f.dataset = ?
        """,
        (args.dataset,),
    ).fetchone()[0]

    print("\nDS09 ingestion complete")
    print(f"  scanned: {scanned:,}")
    print(f"  inserted: {inserted:,}")
    print(f"  skipped_ext: {skipped_ext:,}")
    print(f"  skipped_zero_byte: {skipped_zero:,}")
    print(f"  skipped_existing_filename: {skipped_existing_name:,}")
    print(f"  files(dataset={args.dataset}): {total_ds:,}")
    print(f"  text_cache(dataset={args.dataset}): {text_ds:,}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
