"""Minimize retrieved FEC data and log completed UI observations, not new research."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from tools.lead_tracker import check_searched, log_search

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True)
args = parser.parse_args()
lane = Path(args.output).parent
obs = json.loads((lane / 'ui-observations.json').read_text())
logged = []
for source in obs['sources']:
    for name in source['names']:
        query = {'url': source['url'], 'name': name, 'filters': source['filters'],
                 'observed': obs['observation_window_utc'],
                 'provenance': 'CUA rendered result; analyst transcription'}
        query_text = json.dumps(query, sort_keys=True, ensure_ascii=False)
        prior = check_searched(query_text, source['source'])
        if not prior:
            log_search(query_text, source['source'], source['result_count_each'])
        logged.append({'source': source['source'], 'name': name,
                       'result_count': source['result_count_each'],
                       'query_text': query_text, 'previously_logged': bool(prior)})
for control in obs['positive_controls']:
    query_text = json.dumps({'url': next(s['url'] for s in obs['sources']
                                         if s['source'] == control['source']),
                             'name': control['name'], 'filters': control['filters'],
                             'control': True, 'rows_seen': control['rows_seen'],
                             'scope': control['limitation'],
                             'observed': obs['observation_window_utc']}, sort_keys=True)
    prior = check_searched(query_text, control['source'])
    if not prior:
        log_search(query_text, control['source'], control['result_count'])
    logged.append({'source': control['source'], 'name': control['name'],
                   'result_count': control['result_count'], 'query_text': query_text,
                   'previously_logged': bool(prior)})
for barrier in obs['access_barriers']:
    attempts = barrier.get('attempts', [{}])
    for attempt in attempts:
        query_text = json.dumps({'url': barrier['url'],
                                 'name': barrier.get('attempted_name'),
                                 'attempt': attempt, 'status': barrier['status'],
                                 'error': barrier.get('result_quote'),
                                 'observed': obs['observation_window_utc']}, sort_keys=True)
        prior = check_searched(query_text, barrier['source'])
        if not prior:
            log_search(query_text, barrier['source'], None)
        logged.append({'source': barrier['source'], 'query_text': query_text,
                       'result_count': None, 'previously_logged': bool(prior)})

fec = []
fields = ['recipient_name', 'recipient_city', 'recipient_state', 'committee_id',
          'disbursement_date', 'disbursement_amount', 'disbursement_description',
          'disbursement_purpose_category', 'disbursement_type',
          'disbursement_type_description', 'transaction_id', 'sub_id',
          'file_number', 'image_number', 'pdf_url', 'amendment_indicator',
          'amendment_indicator_desc', 'memo_code', 'memo_text', 'memoed_subtotal']
for file_name in ['fec-sweep-live.json', 'fec-wynn-2024.json', 'fec-wynn-2026.json']:
    for item in json.loads((lane / file_name).read_text()):
        row = {key: value for key, value in item.items() if key != 'results'}
        row['retrieval_file'] = file_name
        row['results'] = []
        for hit in item.get('results', []):
            result = {key: hit.get(key) for key in fields}
            result['committee_name'] = hit.get('committee', {}).get('name')
            result['resolution'] = 'Excluded: distinct named venue/resort, geography and commercial travel/facility purpose; not a Wynn entity/DBA.'
            row['results'].append(result)
        fec.append(row)
(lane / 'fec-minimized.json').write_text(json.dumps(fec, indent=2) + '\n')
Path(args.output).write_text(json.dumps({'logged_at': datetime.now(timezone.utc).isoformat(),
                                      'rows': logged}, indent=2, ensure_ascii=False) + '\n')
artifacts = []
for file_name in ['ui-observations.json', 'fec-minimized.json', 'search-log-receipt.json',
                  'fec-sweep.py', 'finalize-evidence.py']:
    file_path = lane / file_name
    data = file_path.read_bytes()
    artifacts.append({'path': str(file_path), 'bytes': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
manifest = {'created_at': datetime.now(timezone.utc).isoformat(),
            'lead_id': 95000, 'profile': 'elephant-clipping',
            'artifacts': artifacts,
            'provenance': 'FEC-minimized retains fetched API fields and query/pagination metadata; UI file is explicitly analyst transcription, not raw source response. No source payment finding added.',
            'temporary_raw_files_not_for_durable_export': ['fec-sweep.json (sandbox DNS failures)',
                'fec-sweep-live.json (original provider output)', 'fec-wynn-2024.json', 'fec-wynn-2026.json']}
(lane / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'search_scopes_logged_or_verified': len(logged),
                  'fec_response_scopes': len(fec), 'manifest': str(lane / 'manifest.json')}))
