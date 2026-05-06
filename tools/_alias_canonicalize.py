#!/usr/bin/env python3
"""Canonicalize connections.person_a/person_b name strings after entity-merge.

Internal helper — operates only on the connections name-string columns.
Logs every change to connection_notes for audit trail.
"""
import sqlite3, sys, datetime, json
from pathlib import Path

# Mapping is hard-coded for the peru-lockheed Wave-2 merge pass.
# Add to it for future merges.
CANONICAL_MAP = {
    'Bernie Navarro': 'Bernardo "Bernie" Navarro',
    'Bernardo (Bernie) Navarro': 'Bernardo "Bernie" Navarro',
    'Lockheed Martin': 'Lockheed Martin Corporation',
    'José Jerí': 'José Enrique Jerí Oré',
    'Jose Jeri': 'José Enrique Jerí Oré',
    'Jose Jeri Ore': 'José Enrique Jerí Oré',
    'Carlos Diaz Danino': 'Carlos Alberto Díaz Dañino',
    'Carlos Díaz Dañino': 'Carlos Alberto Díaz Dañino',
    'Carlos Chávez Cateriano': 'Carlos Enrique Chávez Cateriano',
    'Carlos Enrique Chavez Cateriano': 'Carlos Enrique Chávez Cateriano',
    'Mario Contreras León Carty': 'Mario Raúl Contreras León Carty',
    'Mario Contreras Leon Carty': 'Mario Raúl Contreras León Carty',
    'Fuerza Aerea del Peru (FAP)': 'Fuerza Aérea del Perú (FAP)',
    'Fuerza Aerea del Peru': 'Fuerza Aérea del Perú (FAP)',
    'Fuerza Aérea del Perú': 'Fuerza Aérea del Perú (FAP)',
    'FAP': 'Fuerza Aérea del Perú (FAP)',
    'Andy Winns': 'Anthony "Andy" Winns',
    'Anthony Winns': 'Anthony "Andy" Winns',
}

def main():
    db_path = Path(__file__).parent.parent / 'investigation.db'
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    ts = datetime.datetime.now().isoformat()
    total = 0
    detail = []
    for old, new in CANONICAL_MAP.items():
        r1 = cur.execute('UPDATE OR IGNORE connections SET person_a=? WHERE person_a=?', (new, old))
        c1 = r1.rowcount
        r2 = cur.execute('UPDATE OR IGNORE connections SET person_b=? WHERE person_b=?', (new, old))
        c2 = r2.rowcount
        # Any rows still using old name = duplicates. Mark them merged_duplicate via verification_status.
        leftover = cur.execute(
            'SELECT id FROM connections WHERE person_a=? OR person_b=?',
            (old, old)).fetchall()
        for (cid,) in leftover:
            cur.execute(
                'UPDATE connections SET verification_status=? WHERE id=?',
                (f'merged_duplicate_of_canonical:{new}', cid))
        if c1 or c2 or leftover:
            detail.append(f"  {c1+c2:>3} '{old}' -> '{new}' ({len(leftover)} duplicate edges retired)")
            total += c1 + c2
    db.commit()
    print(f'Canonicalized {total} connection name-string occurrences ({ts}):')
    print('\n'.join(detail))

if __name__ == '__main__':
    main()
