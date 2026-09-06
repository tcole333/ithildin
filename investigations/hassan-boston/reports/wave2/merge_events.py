"""Merge source-owner event exports without duplicating superseded index observations."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


TRACKS = ('timeline-baseline', 'suffolk', 'plymouth', 'other-counties',
          'probate-family', 'local-courts', 'capital')


def read_rows(path):
    csv.field_size_limit(8 * 1024 * 1024)
    with path.open(newline='') as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, [dict(row) for row in reader]


def normalized(row):
    result = {key: (value or '').strip() for key, value in row.items()}
    bp = result['book_page']
    if re.fullmatch(r'\d+-\d+', bp):
        result['book_page'] = bp.replace('-', '/')
    result['county'] = re.sub(r'\s*\([^)]*\)\s*$', '', result['county']).strip().removesuffix(' County').title()
    if record_key(result) is not None:
        district, land_type, book_page = record_key(result)
        stable_id = f'US-MA-{district.upper()}:{land_type.upper()}:{book_page}'
        if result['instrument_id'] and result['instrument_id'] != stable_id:
            result['notes'] += f" Native recorder identifier: {result['instrument_id']}."
        result['instrument_id'] = stable_id
    return result


def record_key(row):
    # A pleading can cite a deed's book/page without being that land instrument.
    if any(term in row['event_type'].lower() for term in (
        'assessment', 'assessor', 'permit', 'court', 'pleading', 'lease_allegation',
        'case_disposition', 'alleged_family_agreement',
    )):
        return None
    if re.fullmatch(r'\d+/\d+', row['book_page']):
        district = row['county'].lower()
        registry = row['registry'].lower()
        if district == 'middlesex':
            if 'south' in registry:
                district += '-south'
            elif 'north' in registry:
                district += '-north'
            else:
                district += '-division-unresolved'
        land_type = 'registered' if 'registered' in registry else 'recorded'
        return (district, land_type, row['book_page'])
    return None


def original(row):
    return 'original' in row['evidence_status'].lower() and not any(
        term in row['evidence_status'].lower()
        for term in ('unread', 'not_reviewed', 'unavailable', 'index_only')
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-all', action='store_true')
    args = parser.parse_args()
    report_dir = Path(__file__).resolve().parent
    evidence_dir = report_dir.parents[1] / 'evidence/wave2'
    fields, baseline = read_rows(evidence_dir / 'timeline-baseline/events.csv')
    rows_by_track = {'timeline-baseline': [normalized(row) for row in baseline]}
    inputs, missing = [], []
    for track in TRACKS:
        file_path = evidence_dir / track / 'events.csv'
        if not file_path.exists():
            missing.append(track)
            continue
        header, rows = read_rows(file_path)
        if header != fields:
            raise ValueError(f'{track}: unexpected CSV header {header}')
        rows_by_track[track] = [normalized(row) for row in rows]
        inputs.append({'track': track, 'path': str(file_path), 'rows': len(rows),
                       'sha256': hashlib.sha256(file_path.read_bytes()).hexdigest()})
    if args.require_all and missing:
        raise ValueError(f'Missing source-owner event exports: {missing}')
    newer = [row for track, rows in rows_by_track.items()
             if track != 'timeline-baseline' for row in rows]
    reviewed = {record_key(row) for row in newer if original(row)} - {None}
    superseded = [row for row in rows_by_track['timeline-baseline']
                  if record_key(row) in reviewed]
    merged = [row for row in rows_by_track['timeline-baseline']
              if record_key(row) not in reviewed] + newer
    seen, unique, duplicates = {}, [], []
    for row in merged:
        identity = (record_key(row), row['property_key'], row['event_type'], row['event_date'])
        if record_key(row) is None:
            identity = ('event', row['event_id'])
        if identity in seen:
            previous = seen[identity]
            if row != previous:
                raise ValueError(f'Conflicting duplicate event: {identity}')
            duplicates.append(row['event_id'])
            continue
        seen[identity] = row
        unique.append(row)
    ids = [row['event_id'] for row in unique]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate event IDs across exports')
    for row in unique:
        for required in ('event_id', 'property_key', 'event_type', 'source_quote', 'source_url', 'evidence_status'):
            if not row[required]:
                raise ValueError(f"{row['event_id']}: empty {required}")
        date = row['event_date']
        if date and not re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', date):
            raise ValueError(f"{row['event_id']}: unsupported date {date}")
    unique.sort(key=lambda row: (row['county'], row['property_key'], row['event_date'] or '9999', row['event_id']))
    with (report_dir / 'ownership-events.csv').open('w', newline='') as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(unique)
    (report_dir / 'ownership-events.json').write_text(json.dumps(unique, indent=2, ensure_ascii=False))
    prior_property_keys = {}
    new_property_keys = {}
    for row in superseded:
        prior_property_keys.setdefault(str(record_key(row)), set()).add(row['property_key'])
    for row in newer:
        if record_key(row) in reviewed:
            new_property_keys.setdefault(str(record_key(row)), set()).add(row['property_key'])
    joins = [{'instrument': key, 'baseline_properties': sorted(values),
              'new_properties': sorted(new_property_keys.get(key, set()))}
             for key, values in sorted(prior_property_keys.items())]
    metrics = {
        'inputs': inputs, 'missing_tracks': missing, 'events': len(unique),
        'property_context_groups': len({row['property_key'] for row in unique}),
        'by_county': dict(Counter(row['county'] for row in unique)),
        'by_event_type': dict(Counter(row['event_type'] for row in unique)),
        'by_evidence_status': dict(Counter(row['evidence_status'] for row in unique)),
        'superseded_baseline_rows': len(superseded),
        'superseded_instrument_joins_for_review': joins,
        'exact_duplicates_dropped': duplicates,
        'unique_land_instruments': len({record_key(row) for row in unique if record_key(row)}),
        'interpretation': 'Counts measure observations and research contexts, not properties currently owned or independent transactions.',
    }
    (report_dir / 'merge-audit.json').write_text(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(json.dumps({key: metrics[key] for key in ('events','property_context_groups','by_county','missing_tracks','superseded_baseline_rows')}))


if __name__ == '__main__':
    main()
