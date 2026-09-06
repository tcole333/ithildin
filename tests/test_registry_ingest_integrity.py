"""Registry refreshes preserve identity, historical evidence and referential integrity."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from tools import ingest_florida, ingest_ohio, query_registry
from tools.registry_ingest_util import upsert_current_agent, upsert_current_officer


@pytest.fixture
def db():
    connection = sqlite3.connect(':memory:')
    connection.execute('PRAGMA foreign_keys=ON')
    query_registry._ensure_schema(connection)
    yield connection
    connection.close()


def _fl_entity(name='EXAMPLE LLC'):
    return ('fl', 'FL0001', name, 'llc', 'active') + (None,) * 16 + (
        'https://example.test/FL0001',
    )


def test_florida_refresh_preserves_entity_id_and_prior_evidence(db):
    officers = [('FL0001', 'EXAMPLE OFFICER', None, 'person', 'OLD ADDRESS', None, None, None)]
    agents = [('FL0001', 'EXAMPLE AGENT', 'person', None, None, None, None)]
    ingest_florida._flush_batch(db, [_fl_entity()], officers, agents)
    entity_id = db.execute('SELECT id FROM registry_entities').fetchone()[0]
    db.execute(
        'INSERT INTO registry_filings (entity_id, filing_type, filing_date) VALUES (?, ?, ?)',
        (entity_id, 'annual_report', '2025-01-01'),
    )
    db.execute(
        "UPDATE registry_entities SET dissolution_date='2025-02-01', purpose='Historic purpose'"
    )
    db.commit()

    officers[0] = (*officers[0][:4], 'NEW ADDRESS', *officers[0][5:])
    ingest_florida._flush_batch(db, [_fl_entity('UPDATED LLC')], officers, agents)

    assert db.execute('SELECT id, entity_name FROM registry_entities').fetchall() == [
        (entity_id, 'UPDATED LLC'),
    ]
    assert db.execute('SELECT dissolution_date, purpose FROM registry_entities').fetchone() == (
        '2025-02-01', 'Historic purpose',
    )
    assert db.execute('SELECT COUNT(*) FROM registry_officers').fetchone()[0] == 1
    assert db.execute('SELECT address FROM registry_officers').fetchone()[0] == 'NEW ADDRESS'
    assert db.execute('SELECT COUNT(*) FROM registry_agents').fetchone()[0] == 1
    assert db.execute(
        'SELECT COUNT(*) FROM registry_filings f JOIN registry_entities e ON e.id=f.entity_id'
    ).fetchone()[0] == 1
    assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_failed_florida_batch_rolls_back_without_committing_callers_work(db):
    db.execute("INSERT INTO registry_entities (source_jurisdiction, source_id, entity_name) VALUES ('oh', 'PENDING', 'PENDING')")
    with pytest.raises(sqlite3.IntegrityError):
        ingest_florida._flush_batch(
            db, [_fl_entity()], [('FL0001', None, None, None, None, None, None, None)], [],
        )
    assert db.in_transaction
    assert db.execute('SELECT source_id FROM registry_entities').fetchall() == [('PENDING',)]
    db.rollback()
    assert db.execute('SELECT COUNT(*) FROM registry_entities').fetchone()[0] == 0
    assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_ohio_repeat_refresh_updates_one_current_agent(db):
    search = {'charter_num': 'OH0001', 'business_name': 'EXAMPLE INC', 'status': 'A'}
    detail = {'registrant': {'contact_name': 'EXAMPLE AGENT', 'contact_addr1': 'OLD ADDRESS'}}
    entity_id = ingest_ohio._upsert_entity(db, search, detail)
    agent_id = db.execute('SELECT id FROM registry_agents').fetchone()[0]
    detail['registrant']['contact_addr1'] = 'NEW ADDRESS'
    assert ingest_ohio._upsert_entity(db, search, detail) == entity_id
    assert db.execute('SELECT id, address FROM registry_agents').fetchall() == [(agent_id, 'NEW ADDRESS')]
    detail['registrant']['contact_name'] = 'DIFFERENT AGENT'
    ingest_ohio._upsert_entity(db, search, detail)
    assert db.execute('SELECT COUNT(*) FROM registry_agents').fetchone()[0] == 2


def test_current_party_update_preserves_dated_ended_and_filing_linked_history(db):
    ingest_florida._flush_batch(db, [_fl_entity()], [], [])
    entity_id = db.execute('SELECT id FROM registry_entities').fetchone()[0]
    filing_id = db.execute(
        "INSERT INTO registry_filings (entity_id, filing_type) VALUES (?, 'annual_report') RETURNING id",
        (entity_id,),
    ).fetchone()[0]
    for effective, ended in [('2024-01-01', None), (None, '2025-01-01')]:
        db.execute(
            'INSERT INTO registry_agents (entity_id, agent_name, effective_date, end_date, address) VALUES (?, ?, ?, ?, ?)',
            (entity_id, 'AGENT', effective, ended, 'HISTORIC ADDRESS'),
        )
    db.execute(
        'INSERT INTO registry_officers (entity_id, officer_name, source_filing_id, address) VALUES (?, ?, ?, ?)',
        (entity_id, 'OFFICER', filing_id, 'FILING ADDRESS'),
    )
    for _ in range(2):
        upsert_current_agent(db, entity_id=entity_id, agent_name='AGENT', address='CURRENT ADDRESS')
        upsert_current_officer(db, entity_id=entity_id, officer_name='OFFICER', address='CURRENT ADDRESS')
    assert db.execute('SELECT address FROM registry_agents ORDER BY id').fetchall() == [
        ('HISTORIC ADDRESS',), ('HISTORIC ADDRESS',), ('CURRENT ADDRESS',),
    ]
    assert db.execute('SELECT address FROM registry_officers ORDER BY id').fetchall() == [
        ('FILING ADDRESS',), ('CURRENT ADDRESS',),
    ]


def test_existing_legacy_duplicates_are_not_deleted_or_extended(db):
    ingest_florida._flush_batch(db, [_fl_entity()], [], [])
    entity_id = db.execute('SELECT id FROM registry_entities').fetchone()[0]
    db.executemany(
        'INSERT INTO registry_agents (entity_id, agent_name, address) VALUES (?, ?, ?)',
        [(entity_id, 'AGENT', 'ONE'), (entity_id, 'AGENT', 'TWO')],
    )
    upsert_current_agent(db, entity_id=entity_id, agent_name='AGENT', address='CURRENT')
    assert db.execute('SELECT address FROM registry_agents ORDER BY id').fetchall() == [
        ('CURRENT',), ('TWO',),
    ]


def test_concurrent_current_agent_upserts_are_idempotent_even_in_autocommit(tmp_path):
    database = tmp_path / 'registry.sqlite'
    with sqlite3.connect(database) as connection:
        query_registry._ensure_schema(connection)
        connection.execute("INSERT INTO registry_entities (source_jurisdiction, source_id, entity_name) VALUES ('fl', 'ONE', 'ONE')")

    def write_agent(_):
        with sqlite3.connect(database, isolation_level=None) as connection:
            return upsert_current_agent(connection, entity_id=1, agent_name='AGENT')

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(write_agent, range(8)))
    assert len(set(ids)) == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT COUNT(*) FROM registry_agents').fetchone()[0] == 1
