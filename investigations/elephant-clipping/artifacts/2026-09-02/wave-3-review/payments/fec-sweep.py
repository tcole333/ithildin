"""Bounded one-off use of the existing FEC fetch helper; no new integration."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from tools.query_fec import _fetch, FECRequestError
from tools.lead_tracker import check_searched, log_search

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
parser.add_argument('--name', action='append')
parser.add_argument('--cycle', type=int)
args = parser.parse_args()
out = Path(args.output)
names = ['B WYNN SPORTS', 'BG CONTROL', 'NEVER FOLD', 'BW COUNTERPUNCH', '1776 CASTLE', 'BWRP', 'ENCLAVE & KEY', 'ENCLAVE AND KEY', 'CELEBRITY POKER TOUR', 'ENCLAVE']
if args.name:
    names = args.name
records = []
for name in names:
    params = {'recipient_name': name, 'min_date': '2024-01-01', 'max_date': '2026-09-02', 'sort': '-disbursement_date', 'per_page': 100}
    if args.cycle:
        params['two_year_transaction_period'] = args.cycle
    query = json.dumps({'endpoint': '/schedules/schedule_b/', 'all_committees': True, 'filters': params, 'max_pages': 20}, sort_keys=True)
    prior = check_searched(query, 'fec_wave3_all_committee')
    if prior:
        print(f'{name}: prior query logged; skipped', flush=True)
        continue
    entry = {'query': json.loads(query), 'started_at': datetime.now(timezone.utc).isoformat()}
    try:
        results, pagination = _fetch('/schedules/schedule_b/', dict(params), max_pages=20)
        entry.update({'status': 'retrieved', 'results': results, 'pagination': pagination, 'returned': len(results)})
        log_search(query, 'fec_wave3_all_committee', len(results))
        print(f'{name}: {len(results)} rows; pagination {pagination}', flush=True)
    except FECRequestError as exc:
        entry.update(exc.as_payload())
        log_search(query + ' ACCESS_ERROR: ' + str(exc), 'fec_wave3_all_committee', None)
        print(f'{name}: {exc}', flush=True)
    entry['finished_at'] = datetime.now(timezone.utc).isoformat()
    records.append(entry)
    out.write_text(json.dumps(records, indent=2))
