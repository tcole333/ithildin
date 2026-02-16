#!/usr/bin/env python3
"""
FinCEN Files integration for Epstein OSINT investigation.

Dataset: 200K+ suspicious activity reports (SARs) from FinCEN leaked to BuzzFeed/ICIJ.
Covers 2000-2017 transactions ($35B+) flagged by financial institutions.

Two datasets:
- Transactions: 4,508 rows - originator/beneficiary banks, amounts, date ranges
- Bank Connections: 5,498 rows - correspondent banking relationships

Usage:
    python tools/query_fincen.py download        # Download and cache dataset
    python tools/query_fincen.py search-tx "bank name"
    python tools/query_fincen.py search-connections "entity"
    python tools/query_fincen.py stats
    python tools/query_fincen.py filer "Deutsche Bank"
    python tools/query_fincen.py country "SGP"
    python tools/query_fincen.py sar 3297
"""
import argparse
import csv
import json
import os
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

FINCEN_URL = "https://media.icij.org/uploads/2020/09/download_data_fincen_files.zip"
CACHE_DIR = Path("datasets/fincen_files")
TX_FILE = CACHE_DIR / "download_transactions_map.csv"
CONN_FILE = CACHE_DIR / "download_bank_connections.csv"

def download_dataset(force=False):
    """Download and extract FinCEN Files dataset."""
    if CACHE_DIR.exists() and TX_FILE.exists() and CONN_FILE.exists() and not force:
        print(f"Dataset already cached at {CACHE_DIR}")
        return

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_DIR / "fincen_files.zip"

    print(f"Downloading FinCEN Files from {FINCEN_URL}...")
    urllib.request.urlretrieve(FINCEN_URL, zip_path)
    print(f"Downloaded {zip_path.stat().st_size / 1024:.1f} KB")

    print(f"Extracting to {CACHE_DIR}...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(CACHE_DIR)

    # Clean up __MACOSX directory if present
    macosx_dir = CACHE_DIR / "__MACOSX"
    if macosx_dir.exists():
        import shutil
        shutil.rmtree(macosx_dir)

    zip_path.unlink()
    print(f"Dataset ready at {CACHE_DIR}")
    print(f"  - {TX_FILE.name}: {sum(1 for _ in open(TX_FILE)) - 1:,} transactions")
    print(f"  - {CONN_FILE.name}: {sum(1 for _ in open(CONN_FILE)) - 1:,} connections")

def ensure_downloaded():
    """Ensure dataset is downloaded before queries."""
    if not TX_FILE.exists() or not CONN_FILE.exists():
        print("Dataset not found. Downloading...", file=sys.stderr)
        download_dataset()

def search_transactions(query, output=None, limit=None):
    """Search transaction data for query term."""
    ensure_downloaded()

    results = []
    with open(TX_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Search across key fields
            searchable = ' '.join([
                row['filer_org_name'],
                row['originator_bank'],
                row['originator_bank_country'],
                row['beneficiary_bank'],
                row['beneficiary_bank_country']
            ]).lower()

            if query.lower() in searchable:
                results.append(row)
                if limit and len(results) >= limit:
                    break

    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"{len(results)} results saved to {output}")
    else:
        print(f"Found {len(results)} transactions matching '{query}':")
        for i, tx in enumerate(results[:20], 1):
            amount = tx['amount_transactions']
            if amount:
                try:
                    amount_str = f"${float(amount):,.0f}"
                except ValueError:
                    amount_str = amount
            else:
                amount_str = "N/A"

            print(f"\n{i}. SAR {tx['icij_sar_id']} - {tx['filer_org_name']}")
            print(f"   {tx['originator_bank']} ({tx['originator_iso']}) → {tx['beneficiary_bank']} ({tx['beneficiary_iso']})")
            print(f"   {tx['begin_date']} to {tx['end_date']} | {tx['number_transactions']} txns | {amount_str}")

        if len(results) > 20:
            print(f"\n... and {len(results) - 20} more. Use --output to save all results.")

    return results

def search_connections(query, output=None, limit=None):
    """Search bank connection data for query term."""
    ensure_downloaded()

    results = []
    with open(CONN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            searchable = ' '.join([
                row['filer_org_name'],
                row['entity_b'],
                row['entity_b_country']
            ]).lower()

            if query.lower() in searchable:
                results.append(row)
                if limit and len(results) >= limit:
                    break

    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"{len(results)} results saved to {output}")
    else:
        print(f"Found {len(results)} connections matching '{query}':")
        for i, conn in enumerate(results[:20], 1):
            print(f"{i}. SAR {conn['icij_sar_id']}: {conn['filer_org_name']} ↔ {conn['entity_b']} ({conn['entity_b_iso_code']})")

        if len(results) > 20:
            print(f"\n... and {len(results) - 20} more. Use --output to save all results.")

    return results

def get_filer_transactions(filer_name, output=None):
    """Get all transactions filed by a specific organization."""
    ensure_downloaded()

    results = []
    with open(TX_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if filer_name.lower() in row['filer_org_name'].lower():
                results.append(row)

    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"{len(results)} transactions saved to {output}")
    else:
        print(f"Found {len(results)} transactions filed by organizations matching '{filer_name}':")

        # Group by filer
        by_filer = defaultdict(list)
        for tx in results:
            by_filer[tx['filer_org_name']].append(tx)

        for filer, txs in sorted(by_filer.items()):
            total_amount = sum(float(tx['amount_transactions']) for tx in txs if tx['amount_transactions'])
            print(f"\n{filer}: {len(txs)} transactions, ${total_amount:,.0f} total")
            for tx in txs[:5]:
                print(f"  SAR {tx['icij_sar_id']}: {tx['originator_bank']} → {tx['beneficiary_bank']}")
            if len(txs) > 5:
                print(f"  ... and {len(txs) - 5} more")

    return results

def get_country_transactions(country_code, output=None):
    """Get transactions involving a specific country (ISO code)."""
    ensure_downloaded()

    results = []
    with open(TX_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if country_code.upper() in [row['originator_iso'], row['beneficiary_iso']]:
                results.append(row)

    if output:
        with open(output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"{len(results)} transactions saved to {output}")
    else:
        print(f"Found {len(results)} transactions involving {country_code}:")
        for i, tx in enumerate(results[:20], 1):
            print(f"{i}. SAR {tx['icij_sar_id']}: {tx['originator_bank']} ({tx['originator_iso']}) → {tx['beneficiary_bank']} ({tx['beneficiary_iso']})")

        if len(results) > 20:
            print(f"... and {len(results) - 20} more. Use --output to save all results.")

    return results

def get_sar_details(sar_id, output=None):
    """Get all transactions and connections for a specific SAR ID."""
    ensure_downloaded()

    result = {'sar_id': sar_id, 'transactions': [], 'connections': []}

    with open(TX_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['icij_sar_id'] == str(sar_id):
                result['transactions'].append(row)

    with open(CONN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['icij_sar_id'] == str(sar_id):
                result['connections'].append(row)

    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"SAR {sar_id} data saved to {output}")
    else:
        print(f"SAR {sar_id}:")
        print(f"\nTransactions: {len(result['transactions'])}")
        for tx in result['transactions']:
            print(f"  {tx['originator_bank']} ({tx['originator_iso']}) → {tx['beneficiary_bank']} ({tx['beneficiary_iso']})")
            print(f"    {tx['begin_date']} to {tx['end_date']} | {tx['number_transactions']} txns | ${tx['amount_transactions']}")

        print(f"\nConnections: {len(result['connections'])}")
        for conn in result['connections']:
            print(f"  {conn['filer_org_name']} ↔ {conn['entity_b']} ({conn['entity_b_iso_code']})")

    return result

def get_stats(output=None):
    """Get dataset statistics."""
    ensure_downloaded()

    stats = {
        'transactions': {'count': 0, 'filers': set(), 'countries': set(), 'sars': set()},
        'connections': {'count': 0, 'filers': set(), 'entities': set(), 'sars': set()}
    }

    with open(TX_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats['transactions']['count'] += 1
            stats['transactions']['filers'].add(row['filer_org_name'])
            stats['transactions']['countries'].add(row['originator_iso'])
            stats['transactions']['countries'].add(row['beneficiary_iso'])
            stats['transactions']['sars'].add(row['icij_sar_id'])

    with open(CONN_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats['connections']['count'] += 1
            stats['connections']['filers'].add(row['filer_org_name'])
            stats['connections']['entities'].add(row['entity_b'])
            stats['connections']['sars'].add(row['icij_sar_id'])

    # Convert sets to counts
    result = {
        'transactions': {
            'total_records': stats['transactions']['count'],
            'unique_filers': len(stats['transactions']['filers']),
            'unique_countries': len(stats['transactions']['countries']),
            'unique_sars': len(stats['transactions']['sars'])
        },
        'connections': {
            'total_records': stats['connections']['count'],
            'unique_filers': len(stats['connections']['filers']),
            'unique_entities': len(stats['connections']['entities']),
            'unique_sars': len(stats['connections']['sars'])
        },
        'combined': {
            'unique_sars': len(stats['transactions']['sars'] | stats['connections']['sars'])
        }
    }

    if output:
        with open(output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Statistics saved to {output}")
    else:
        print("FinCEN Files Dataset Statistics:")
        print(f"\nTransactions:")
        print(f"  Total records: {result['transactions']['total_records']:,}")
        print(f"  Unique filers: {result['transactions']['unique_filers']:,}")
        print(f"  Unique countries: {result['transactions']['unique_countries']:,}")
        print(f"  Unique SARs: {result['transactions']['unique_sars']:,}")
        print(f"\nConnections:")
        print(f"  Total records: {result['connections']['total_records']:,}")
        print(f"  Unique filers: {result['connections']['unique_filers']:,}")
        print(f"  Unique entities: {result['connections']['unique_entities']:,}")
        print(f"  Unique SARs: {result['connections']['unique_sars']:,}")
        print(f"\nCombined unique SARs: {result['combined']['unique_sars']:,}")

    return result

def main():
    parser = argparse.ArgumentParser(description="FinCEN Files query tool")
    sub = parser.add_subparsers(dest="command")

    # Download
    dl = sub.add_parser("download", help="Download and cache dataset")
    dl.add_argument("--force", action="store_true", help="Re-download even if cached")

    # Search transactions
    stx = sub.add_parser("search-tx", help="Search transaction data")
    stx.add_argument("query", help="Search term")
    stx.add_argument("--limit", type=int, help="Limit results")
    add_output_args(stx)

    # Search connections
    sconn = sub.add_parser("search-connections", help="Search bank connection data")
    sconn.add_argument("query", help="Search term")
    sconn.add_argument("--limit", type=int, help="Limit results")
    add_output_args(sconn)

    # Filer transactions
    filer = sub.add_parser("filer", help="Get transactions by filer organization")
    filer.add_argument("name", help="Filer organization name (partial match)")
    add_output_args(filer)

    # Country transactions
    country = sub.add_parser("country", help="Get transactions involving a country")
    country.add_argument("code", help="ISO country code (e.g., USA, SGP, GBR)")
    add_output_args(country)

    # SAR details
    sar = sub.add_parser("sar", help="Get all data for a specific SAR ID")
    sar.add_argument("id", help="ICIJ SAR ID")
    add_output_args(sar)

    # Stats
    stats = sub.add_parser("stats", help="Get dataset statistics")
    add_output_args(stats)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure output attribute exists
    if not hasattr(args, 'output'):
        args.output = None

    if args.command == "download":
        download_dataset(force=args.force)
    elif args.command == "search-tx":
        search_transactions(args.query, output=args.output, limit=args.limit)
    elif args.command == "search-connections":
        search_connections(args.query, output=args.output, limit=args.limit)
    elif args.command == "filer":
        get_filer_transactions(args.name, output=args.output)
    elif args.command == "country":
        get_country_transactions(args.code, output=args.output)
    elif args.command == "sar":
        get_sar_details(args.id, output=args.output)
    elif args.command == "stats":
        get_stats(output=args.output)

if __name__ == "__main__":
    main()
