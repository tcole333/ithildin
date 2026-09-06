"""Reconcile this wave against the preserved prior timeline and render it."""

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path


REPORT_DIR = Path(__file__).resolve().parent
PRIOR_DIR = REPORT_DIR.parent / 'wave2'
EVIDENCE_DIR = REPORT_DIR.parents[1] / 'evidence/wave3'
TRACKS = ('suffolk', 'plymouth', 'other-counties', 'probate-family', 'local-courts', 'capital')
SPEC = importlib.util.spec_from_file_location('prior_merge', PRIOR_DIR / 'merge_events.py')
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args()
    fields, prior = BASE.read_rows(PRIOR_DIR / 'ownership-events.csv')
    prior = [BASE.normalized(row) for row in prior]
    newer, inputs, missing = [], [], []
    for track in TRACKS:
        filename = 'property-events.csv' if track == 'capital' else 'events.csv'
        path = EVIDENCE_DIR / track / filename
        if not path.exists():
            missing.append(track)
            continue
        header, rows = BASE.read_rows(path)
        if header != fields:
            raise ValueError(f'{track}: unexpected event columns')
        newer.extend(BASE.normalized(row) for row in rows)
        inputs.append({'track': track, 'path': str(path), 'rows': len(rows),
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if args.require_all and missing:
        raise ValueError(f'Missing tracks: {missing}')
    reviewed = {BASE.record_key(row) for row in newer if BASE.original(row)} - {None}
    revised_ids = {row['event_id'] for row in newer}
    superseded = [row for row in prior if BASE.record_key(row) in reviewed
                  or row['event_id'] in revised_ids]
    retained = [row for row in prior if BASE.record_key(row) not in reviewed
                and row['event_id'] not in revised_ids]
    merged = retained + newer
    ids = [row['event_id'] for row in merged]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate event IDs in source-owner exports')
    for row in merged:
        for required in ('event_id', 'property_key', 'event_type', 'source_quote',
                         'source_url', 'evidence_status'):
            if not row[required]:
                raise ValueError(f"{row['event_id']}: empty {required}")
        value = row['event_date']
        if value:
            if len(value) == 4:
                date.fromisoformat(value + '-01-01')
            elif len(value) == 7:
                date.fromisoformat(value + '-01')
            else:
                date.fromisoformat(value)
    merged.sort(key=lambda row: (row['county'], row['property_key'],
                                row['event_date'] or '9999', row['event_id']))
    output = REPORT_DIR / 'ownership-events.csv'
    with output.open('w', newline='') as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(merged)
    (REPORT_DIR / 'ownership-events.json').write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    joins = []
    for key in sorted({BASE.record_key(row) for row in superseded} - {None}):
        joins.append({'instrument': key,
                      'prior_properties': sorted({r['property_key'] for r in superseded
                                                  if BASE.record_key(r) == key}),
                      'new_properties': sorted({r['property_key'] for r in newer
                                                if BASE.record_key(r) == key})})
    audit = {'inputs': inputs, 'missing_tracks': missing, 'prior_events': len(prior),
             'new_track_observations': len(newer), 'superseded_events': len(superseded),
             'superseded_event_ids': [r['event_id'] for r in superseded],
             'instrument_property_joins_for_review': joins, 'events': len(merged),
             'property_context_groups': len({r['property_key'] for r in merged}),
             'by_county': dict(Counter(r['county'] for r in merged)),
             'by_event_type': dict(Counter(r['event_type'] for r in merged)),
             'interpretation': 'Observation and research-context counts, not current property totals.'}
    (REPORT_DIR / 'merge-audit.json').write_text(json.dumps(audit, indent=2, ensure_ascii=False))
    subprocess.run([sys.executable, str(PRIOR_DIR / 'build_timeline.py'),
                    '--input', str(output), '--output', str(REPORT_DIR / 'ownership-timeline.html')],
                   check=True)
    for extension in ('html', 'md'):
        artifact = REPORT_DIR / f'ownership-timeline.{extension}'
        rendered = artifact.read_text().replace('September 4, 2026', 'September 5, 2026')
        if extension == 'html':
            rendered = rendered.replace('property groups · ', 'property / context groups · ')
            rendered = rendered.replace(
                'The dates show what the available records establish; gaps remain visible.',
                'The dates show what the available records establish; gaps remain visible. '
                'The selector includes properties, leased premises and unresolved address references. '
                'Search a trust name to find its records across counties.')
            rendered = rendered.replace(
                'e.property_label,e.municipality,e.from_party,e.to_party,e.notes,e.source_ref',
                'e.property_label,e.municipality,e.from_party,e.to_party,e.from_capacity,'
                'e.to_capacity,e.notes,e.source_ref,e.source_quote')
            rendered = rendered.replace('/deed|title_transfer|conveyance/',
                                        '/deed|title_transfer|certificate_of_title|conveyance/')
            rendered = rendered.replace('/court|pleading|lease_allegation/',
                                        '/court|pleading|lease_allegation|case_disposition/')
            title_rule = "if(/deed|title_transfer|certificate_of_title|conveyance/.test(s))return'title';"
            court_rule = "if(/court|pleading|lease_allegation|case_disposition/.test(s))return'legal';"
            authority_rule = ("if(/^(trust_declaration|trustee_certificate|trustee_removal|"
                              "trustee_resignation|beneficiar)/.test(s))return'trust';")
            rendered = rendered.replace(title_rule + court_rule,
                                        court_rule + authority_rule + title_rule)
            rendered = rendered.replace('.test(e.evidence_status)}',
                                        '.test(e.evidence_status.split(/supersedes/i)[0])}')
            rendered = rendered.replace(
                "amounts.push('Loan face amount: '+money(e.loan_amount_usd))",
                "amounts.push((/revolving|line.of.credit|credit.line|HELOC/i.test("
                "e.notes+' '+e.source_quote)?'Credit limit (draw not established): ':"
                "'Loan face amount: ')+money(e.loan_amount_usd))")
            legal_labels = {
                'awarded_rent_damages_usd': 'Rent damages awarded: ',
                'corrected_judgment_total_usd': 'Historical corrected judgment: ',
                'mechanics_lien_judgment_usd': 'Mechanics-lien judgment: ',
                'contract_purchase_price_usd': 'Contract price referenced by court: ',
                'amended_judgment_total_usd': 'Historical amended judgment: ',
                'attachment_cap_usd': 'Attachment cap: ',
            }
            rendered = rendered.replace(
                'const amounts=[];',
                "const amounts=[];if(kind(e)==='legal'){const labels=" + json.dumps(legal_labels)
                + ";for(const [key,label] of Object.entries(labels)){"
                "const m=e.notes.match(new RegExp(key+'=([0-9]+(?:[.][0-9]+)?)'));"
                "if(m)amounts.push(label+money(m[1]));}}")
        artifact.write_text(rendered)
    print(json.dumps({k: audit[k] for k in ('events', 'property_context_groups', 'missing_tracks')}))


if __name__ == '__main__':
    main()
