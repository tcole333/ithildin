"""Persist the 18 observed Ohio query scopes and one functionality control."""
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
observations = json.loads((lane / 'ohio-statewide-observations.json').read_text())
rows = []
for entity_type in observations['entity_types']:
    for name in observations['names']:
        query = {'url': observations['published_form_url'], 'name': name,
                 'entity_type': entity_type['selected_label'],
                 'filters': observations['common_filters'],
                 'observed': observations['observed_window_utc'],
                 'status': observations['result_each']['status'],
                 'result_heading': entity_type['result_heading_quote'],
                 'source_count': None, 'rows_displayed': 0}
        query_text = json.dumps(query, ensure_ascii=False, sort_keys=True)
        prior = check_searched(query_text, observations['source'])
        if not prior:
            log_search(query_text, observations['source'], None)
        rows.append({**query, 'previously_logged': bool(prior)})
control = observations['positive_control']
control_query = {'url': observations['published_form_url'], 'control': True,
                 **control, 'observed': observations['observed_window_utc']}
query_text = json.dumps(control_query, ensure_ascii=False, sort_keys=True)
prior = check_searched(query_text, observations['source'])
if not prior:
    log_search(query_text, observations['source'], control['source_count'])
rows.append({**control_query, 'previously_logged': bool(prior)})
Path(args.output).write_text(json.dumps({'logged_at': datetime.now(timezone.utc).isoformat(),
                                      'rows': rows}, ensure_ascii=False, indent=2) + '\n')
manifest_path = lane / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
for file_path in [lane / 'ohio-statewide-observations.json', Path(args.output),
                  lane / 'finalize-ohio.py', lane.parent / 'report-agent-c.md']:
    artifact = {'path': str(file_path), 'bytes': file_path.stat().st_size,
                'sha256': hashlib.sha256(file_path.read_bytes()).hexdigest()}
    manifest['artifacts'] = [x for x in manifest['artifacts'] if x['path'] != str(file_path)]
    manifest['artifacts'].append(artifact)
manifest['updated_at'] = datetime.now(timezone.utc).isoformat()
manifest['ohio_addendum_scope'] = '18 completed empty-display target scopes with no source-provided count, plus one first-page positive control; helper routing is not duplicate queries.'
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'ohio_target_scopes': 18, 'controls': 1, 'manifest': str(manifest_path)}))
