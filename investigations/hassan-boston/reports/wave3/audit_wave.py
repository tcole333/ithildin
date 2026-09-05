"""Audit the completed wave's local evidence and export its review snapshot."""

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROFILE = HERE.parents[1]
ROOT = HERE.parents[3]
TRACKS = ('suffolk', 'plymouth', 'other-counties', 'probate-family', 'local-courts', 'capital')


def read_csv(path):
    csv.field_size_limit(8 * 1024 * 1024)
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        return list(reader)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    audit = json.loads((HERE / 'merge-audit.json').read_text())
    if audit['missing_tracks']:
        raise ValueError('Run the completed six-track assembly first')
    records = read_csv(HERE / 'ownership-events.csv')
    start = json.loads((HERE / 'run-start.json').read_text())
    sources = json.loads((PROFILE / 'source-urls.json').read_text())
    for path in (
        PROFILE / 'evidence/wave3/suffolk/citation-map.json',
        PROFILE / 'evidence/wave3/capital/source-urls.json',
        PROFILE / 'evidence/wave3/other-counties/source-url-manifest.json',
        PROFILE / 'evidence/wave3/local-courts/source-urls.json',
    ):
        mapping = json.loads(path.read_text())
        mapping = mapping.get('source_urls', mapping)
        for ref, url in mapping.items():
            if isinstance(url, str) and url.startswith('https://'):
                sources.setdefault(ref, url)
    for row in records:
        if row['source_ref'] and row['source_url'].startswith(('https://', 'http://')):
            sources.setdefault(row['source_ref'], row['source_url'])
    for row in read_csv(PROFILE / 'evidence/wave3/plymouth/sources-manifest.csv'):
        sources.setdefault(row['source_ref'], row['source_url'])
    dump(PROFILE / 'source-urls.json', sources)
    shared_path = ROOT / 'web/src/data/source-urls.json'
    shared = json.loads(shared_path.read_text())
    for ref, url in sources.items():
        shared.setdefault(ref, url)
    dump(shared_path, shared)
    dump(HERE / 'source-urls.json', sources)

    db = sqlite3.connect(f'file:{ROOT / "investigation.db"}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    findings = [dict(r) for r in db.execute(
        'SELECT * FROM findings WHERE profile_id=? ORDER BY id', ('hassan-boston',))]
    new = [r for r in findings if r['id'] > start['last_finding_id']]
    issues = {'new_findings_missing_evidence': [], 'new_findings_missing_entity_links': [],
              'confidence_cap_errors': [], 'unmapped_new_finding_refs': [],
              'missing_track_reports': [], 'stale_source_exports': [],
              'court_amounts_in_deed_or_loan_columns': []}
    for row in records:
        if row['event_type'].startswith('court_') and (row['consideration_usd']
                                                     or row['loan_amount_usd']):
            issues['court_amounts_in_deed_or_loan_columns'].append(row['event_id'])
    for row in new:
        evidence = [dict(r) for r in db.execute(
            'SELECT * FROM finding_evidence WHERE finding_id=?', (row['id'],))]
        if not evidence or any(not e['source_quote'] or not e['evidence_ref'] for e in evidence):
            issues['new_findings_missing_evidence'].append(row['id'])
        if not db.execute('SELECT 1 FROM finding_entities WHERE finding_id=?',
                          (row['id'],)).fetchone():
            issues['new_findings_missing_entity_links'].append(row['id'])
        for e in evidence:
            ref = e['evidence_ref']
            if ref and not ref.startswith(('http://', 'https://')) and ref not in sources:
                issues['unmapped_new_finding_refs'].append({'finding_id': row['id'], 'ref': ref})
        if ((row['claim_type'] in ('inference', 'synthesis')
             and row['confidence'] in ('high', 'confirmed'))
            or (row['claim_type'] == 'paraphrase' and row['confidence'] == 'confirmed')):
            issues['confidence_cap_errors'].append(row['id'])
    for track in TRACKS:
        if not (HERE / f'report-{track}.md').exists():
            issues['missing_track_reports'].append(track)
    for item in audit['inputs']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            issues['stale_source_exports'].append(item['track'])
    leads = [dict(r) for r in db.execute(
        'SELECT * FROM leads WHERE profile_id=? ORDER BY id', ('hassan-boston',))]
    dump(HERE / 'leads-2026-09-05.json', leads)
    validation = {
        'profile': 'hassan-boston', 'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'analysis_run_id': 154,
        'scope': 'Bounded third-wave deliverables; remaining original records and search cells are documented.',
        'team_new_findings': len(new), 'team_new_finding_ids': [r['id'] for r in new],
        'total_profile_findings': len(findings), 'event_observations': len(records),
        'property_context_groups': len({r['property_key'] for r in records}),
        'count_interpretation': 'Observations and property/context groups, not current-property totals or independent transactions.',
        'by_county': dict(Counter(r['county'] for r in records)),
        'superseded_prior_rows': audit['superseded_events'],
        'new_track_observations': audit['new_track_observations'],
        'lead_status_counts': dict(Counter(r['status'] for r in leads)),
        'checks': issues,
        'review_limits': {
            'primary_review': 'Original-image scope is recorded per source; some browser-only readings are saved as manual excerpts rather than local originals.',
            'independent_review': 'Selected Concepts and Middlesex images independently inspected; Suffolk/Plymouth reviews include transcription consistency checks, not duplicate original-image review.',
            'courts': 'Public MassCourts display may omit recent activity. Name candidates require independent identity resolution; unexecuted cells remain visible.',
            'money': 'Assignments, mortgage releases, revised judgments and multi-parcel rows must not be summed as separate advances or current debts.',
        },
    }
    dump(HERE / 'validation.json', validation)
    if any(issues.values()):
        raise ValueError(json.dumps(issues))
    print(json.dumps({k: validation[k] for k in ('team_new_findings', 'total_profile_findings',
                                               'event_observations', 'property_context_groups')}))


if __name__ == '__main__':
    main()
