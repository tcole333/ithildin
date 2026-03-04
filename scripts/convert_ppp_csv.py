#!/usr/bin/env python3
"""
Convert SBA PPP/EIDL CSV bulk download to Parquet for DuckDB queries.

Download from: https://data.sba.gov/dataset/ppp-foia
Place CSV file(s) in data/ directory, then run:

    python scripts/convert_ppp_csv.py data/public_150k_plus_*.csv
    python scripts/convert_ppp_csv.py data/public_up_to_150k_*.csv --append

Output: data/ppp_loans.parquet (~11M records from all CSV files combined)
"""

import argparse
import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    print("ERROR: duckdb required. Install: uv add duckdb", file=sys.stderr)
    sys.exit(1)


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "ppp_loans.parquet"


def convert(csv_paths, append=False):
    """Convert one or more PPP CSV files to a single Parquet file."""
    con = duckdb.connect()

    for i, csv_path in enumerate(csv_paths):
        csv_path = Path(csv_path)
        if not csv_path.exists():
            print(f"ERROR: {csv_path} not found", file=sys.stderr)
            sys.exit(1)

        print(f"Reading {csv_path.name}...")
        # DuckDB auto-detects CSV schema; normalize column names
        # ignore_errors=true handles non-UTF-8 bytes in SBA data
        con.execute(f"""
            CREATE OR REPLACE TABLE batch_{i} AS
            SELECT * FROM read_csv_auto('{csv_path}', normalize_names=true, ignore_errors=true)
        """)
        count = con.execute(f"SELECT COUNT(*) FROM batch_{i}").fetchone()[0]
        print(f"  {count:,} rows")

    # Union all batches
    tables = [f"batch_{i}" for i in range(len(csv_paths))]
    union_sql = " UNION ALL ".join(f"SELECT * FROM {t}" for t in tables)

    if append and OUTPUT_PATH.exists():
        print(f"Appending to existing {OUTPUT_PATH.name}...")
        con.execute(f"""
            CREATE TABLE combined AS
            SELECT * FROM read_parquet('{OUTPUT_PATH}')
            UNION ALL
            {union_sql}
        """)
    else:
        con.execute(f"CREATE TABLE combined AS {union_sql}")

    total = con.execute("SELECT COUNT(*) FROM combined").fetchone()[0]
    print(f"Total: {total:,} rows")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY combined TO '{OUTPUT_PATH}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"Written to {OUTPUT_PATH} ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Convert SBA PPP CSV to Parquet")
    parser.add_argument("csv_files", nargs="+", help="CSV file path(s)")
    parser.add_argument("--append", action="store_true",
                        help="Append to existing parquet instead of overwriting")
    args = parser.parse_args()
    convert(args.csv_files, append=args.append)


if __name__ == "__main__":
    main()
