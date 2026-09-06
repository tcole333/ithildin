#!/usr/bin/env python3
"""Normalized sidecars for property and state/local court records.

This module is the single schema authority for the two regenerable public-record
sidecars described in ``docs/PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md``.
Large source material stays out of ``investigation.db``; curated findings keep
canonical references back to these rows.

The schemas preserve source-native identifiers, raw observations, distinct
event dates, document hashes, access states, and later restriction events. They
do not claim that an assessor owner is legal title or that portal metadata is a
certified court record.

Usage:
    uv run python tools/public_records_store.py init
    uv run python tools/public_records_store.py stats
    uv run python tools/public_records_store.py restrict-case \
      --source-id us-wi-wcca --court-id wi-dane-circuit \
      --case-number 2025CV000001 --state sealed --reason "court direction"
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROPERTY_DB = PROJECT_ROOT / "datasets" / "property_records.db"
DEFAULT_COURT_DB = PROJECT_ROOT / "datasets" / "state_court_records.db"

SCHEMA_VERSION = 6

CASE_IDENTITY_NATIVE_PREFIX = "native:"
CASE_IDENTITY_NUMBER_PREFIX = "number:"

ACCESS_STATES = (
    "public",
    "restricted",
    "sealed",
    "expunged",
    "removed",
    "redacted",
    "unknown",
)

ASSERTION_KINDS = (
    "docket_metadata",
    "party_allegation",
    "charge",
    "sworn_declaration",
    "admission",
    "court_finding",
    "verdict",
    "judgment",
    "other",
)

RESTRICTION_EVENT_TYPES = (
    "restricted",
    "sealed",
    "expunged",
    "removed",
    "redacted",
    "restored",
    "other",
)

_ACCESS_STATE_ALIASES = {
    "public": "public",
    "publicly_available": "public",
    "unrestricted": "public",
    "visible": "public",
    "restored": "public",
    "unsealed": "public",
    "made_public": "public",
    "republished": "public",
    "restricted": "restricted",
    "made_nonpublic": "restricted",
    "made_non_public": "restricted",
    "nonpublic": "restricted",
    "non_public": "restricted",
    "confidential": "restricted",
    "protected": "restricted",
    "sealed": "sealed",
    "expunged": "expunged",
    "removed": "removed",
    "destroyed": "removed",
    "deleted": "removed",
    "purged": "removed",
    "redacted": "redacted",
    "unknown": "unknown",
}

_RESTRICTION_EVENT_ALIASES = {
    "restricted": "restricted",
    "made_nonpublic": "restricted",
    "made_non_public": "restricted",
    "nonpublic": "restricted",
    "non_public": "restricted",
    "confidential": "restricted",
    "protected": "restricted",
    "sealed": "sealed",
    "expunged": "expunged",
    "removed": "removed",
    "destroyed": "removed",
    "deleted": "removed",
    "purged": "removed",
    "redacted": "redacted",
    "restored": "restored",
    "unsealed": "restored",
    "made_public": "restored",
    "republished": "restored",
}


def _label_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")


def canonical_access_state(native_label: str) -> str:
    """Map a source-native access label to a serving-state category."""
    return _ACCESS_STATE_ALIASES.get(_label_key(native_label), "unknown")


def canonical_assertion_kind(native_label: str) -> str:
    """Map a source-native assertion label to an evidence category."""
    key = _label_key(native_label)
    return key if key in ASSERTION_KINDS else "other"


def canonical_restriction_event(native_label: str) -> str:
    """Map a source-native restriction label to an audit-event category."""
    return _RESTRICTION_EVENT_ALIASES.get(_label_key(native_label), "other")


PROPERTY_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jurisdiction (
    geoid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    jurisdiction_type TEXT NOT NULL,
    parent_geoid TEXT REFERENCES jurisdiction(geoid),
    state_code TEXT,
    county_code TEXT
);

CREATE TABLE IF NOT EXISTS record_office (
    office_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    jurisdiction_geoid TEXT NOT NULL REFERENCES jurisdiction(geoid),
    office_role TEXT NOT NULL,
    name TEXT NOT NULL,
    official_url TEXT,
    UNIQUE(source_id, jurisdiction_geoid, office_role)
);

CREATE TABLE IF NOT EXISTS source_observation (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    source_native_id TEXT,
    record_kind TEXT NOT NULL,
    query_fingerprint TEXT,
    source_url TEXT,
    retrieved_at TEXT NOT NULL,
    access_status TEXT NOT NULL,
    schema_fingerprint TEXT,
    raw_artifact_sha256 TEXT,
    raw_artifact_path TEXT,
    raw_json TEXT,
    warning_json TEXT,
    CHECK (access_status IN (
        'ok', 'no_results', 'partial', 'unavailable', 'restricted',
        'human_required', 'rate_limited', 'terms_blocked', 'source_changed'
    ))
);
CREATE INDEX IF NOT EXISTS idx_property_observation_source
    ON source_observation(source_id, retrieved_at);
CREATE INDEX IF NOT EXISTS idx_property_observation_query
    ON source_observation(query_fingerprint);
CREATE INDEX IF NOT EXISTS idx_property_observation_native_artifact
    ON source_observation(
        source_id, record_kind, source_native_id, raw_artifact_sha256
    );

CREATE TABLE IF NOT EXISTS parcel_snapshot (
    parcel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    jurisdiction_geoid TEXT NOT NULL REFERENCES jurisdiction(geoid),
    native_parcel_id TEXT NOT NULL,
    roll_year TEXT NOT NULL DEFAULT '',
    effective_from TEXT,
    effective_to TEXT,
    source_good_through TEXT,
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(source_id, jurisdiction_geoid, native_parcel_id, roll_year)
);
CREATE INDEX IF NOT EXISTS idx_parcel_native
    ON parcel_snapshot(jurisdiction_geoid, native_parcel_id);

CREATE TABLE IF NOT EXISTS parcel_alias (
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    alias_type TEXT NOT NULL,
    alias_value TEXT NOT NULL,
    source_id TEXT NOT NULL,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT,
    PRIMARY KEY(parcel_id, alias_type, alias_value, source_id, effective_from)
);
CREATE INDEX IF NOT EXISTS idx_parcel_alias_value
    ON parcel_alias(alias_value);
CREATE INDEX IF NOT EXISTS idx_parcel_alias_source_type_value
    ON parcel_alias(source_id, alias_type, alias_value);

CREATE TABLE IF NOT EXISTS parcel_address (
    address_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    address_role TEXT NOT NULL,
    raw_address TEXT NOT NULL,
    normalized_address TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT NOT NULL DEFAULT 'US',
    source_id TEXT NOT NULL,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT,
    CHECK (address_role IN ('situs', 'mailing', 'return', 'other'))
);
CREATE INDEX IF NOT EXISTS idx_property_address_normalized
    ON parcel_address(normalized_address);

CREATE TABLE IF NOT EXISTS parcel_geometry (
    geometry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    geometry_ref TEXT NOT NULL,
    geometry_format TEXT NOT NULL,
    crs TEXT,
    source_resolution TEXT,
    accuracy_disclaimer TEXT,
    source_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL DEFAULT '',
    UNIQUE(parcel_id, source_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS assessment (
    assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    tax_year TEXT NOT NULL,
    land_value_minor INTEGER,
    improvement_value_minor INTEGER,
    total_value_minor INTEGER,
    market_value_minor INTEGER,
    assessed_value_minor INTEGER,
    exempt_value_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    assessment_class TEXT,
    source_good_through TEXT,
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(parcel_id, source_id, tax_year)
);

CREATE TABLE IF NOT EXISTS tax_account_event (
    tax_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    tax_year TEXT,
    event_type TEXT NOT NULL,
    event_date TEXT,
    amount_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT,
    native_event_id TEXT NOT NULL DEFAULT '',
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(parcel_id, source_id, event_type, event_date, native_event_id)
);

CREATE TABLE IF NOT EXISTS sale_event (
    sale_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    native_sale_id TEXT NOT NULL DEFAULT '',
    sale_date TEXT,
    execution_date TEXT,
    recording_date TEXT,
    consideration_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    qualification_code TEXT,
    derivation TEXT NOT NULL,
    instrument_id INTEGER REFERENCES recorded_instrument(instrument_id),
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(parcel_id, source_id, native_sale_id, sale_date, derivation)
);

CREATE TABLE IF NOT EXISTS property_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    jurisdiction_geoid TEXT NOT NULL REFERENCES jurisdiction(geoid),
    native_event_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    event_type TEXT,
    description TEXT,
    status TEXT,
    status_category TEXT,
    event_date TEXT,
    normalized_case_number TEXT,
    submitted_date TEXT,
    approved_date TEXT,
    last_update_date TEXT,
    estimated_cost_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    address_raw TEXT,
    map_taxlot_candidate TEXT,
    longitude REAL,
    latitude REAL,
    geometry_crs TEXT,
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(source_id, jurisdiction_geoid, native_event_id, source_record_id)
);
CREATE INDEX IF NOT EXISTS idx_property_event_native
    ON property_event(jurisdiction_geoid, native_event_id);
CREATE INDEX IF NOT EXISTS idx_property_event_address
    ON property_event(address_raw);
CREATE INDEX IF NOT EXISTS idx_property_event_map_taxlot
    ON property_event(map_taxlot_candidate);

CREATE TABLE IF NOT EXISTS property_event_parcel_join_key (
    event_id INTEGER NOT NULL
        REFERENCES property_event(event_id) ON DELETE CASCADE,
    normalized_parcel_id TEXT NOT NULL,
    PRIMARY KEY(event_id, normalized_parcel_id)
);
CREATE INDEX IF NOT EXISTS idx_property_event_parcel_join_value
    ON property_event_parcel_join_key(normalized_parcel_id, event_id);

CREATE TABLE IF NOT EXISTS property_event_party (
    event_party_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES property_event(event_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    assertion_type TEXT,
    UNIQUE(event_id, sequence_no, role, raw_name)
);
CREATE INDEX IF NOT EXISTS idx_property_event_party_name
    ON property_event_party(raw_name);

CREATE TABLE IF NOT EXISTS property_event_parcel_link (
    event_id INTEGER PRIMARY KEY REFERENCES property_event(event_id) ON DELETE CASCADE,
    parcel_id INTEGER REFERENCES parcel_snapshot(parcel_id) ON DELETE SET NULL,
    map_taxlot_candidate TEXT,
    link_method TEXT NOT NULL,
    link_confidence REAL,
    evidence_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_property_event_parcel
    ON property_event_parcel_link(parcel_id);

CREATE TABLE IF NOT EXISTS property_event_representation (
    representation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES property_event(event_id) ON DELETE CASCADE,
    representation_kind TEXT NOT NULL,
    source_url TEXT NOT NULL,
    relationship TEXT,
    source_state TEXT,
    raw_json TEXT,
    UNIQUE(event_id, representation_kind, source_url)
);

CREATE TABLE IF NOT EXISTS property_event_relation (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL
        REFERENCES property_event(event_id) ON DELETE CASCADE,
    related_event_id INTEGER NOT NULL
        REFERENCES property_event(event_id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,
    independent_corroboration INTEGER NOT NULL DEFAULT 0
        CHECK (independent_corroboration IN (0, 1)),
    normalized_case_number TEXT,
    event_date TEXT,
    overlapping_parcels_json TEXT,
    evidence_json TEXT NOT NULL,
    CHECK (event_id < related_event_id),
    UNIQUE(event_id, related_event_id, relationship)
);
CREATE INDEX IF NOT EXISTS idx_property_event_relation_case_date
    ON property_event_relation(normalized_case_number, event_date);
CREATE INDEX IF NOT EXISTS idx_property_event_relation_related
    ON property_event_relation(related_event_id, relationship);

CREATE TABLE IF NOT EXISTS recorded_instrument (
    instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    jurisdiction_geoid TEXT NOT NULL REFERENCES jurisdiction(geoid),
    native_document_id TEXT NOT NULL,
    instrument_type TEXT,
    book TEXT,
    page TEXT,
    execution_date TEXT,
    recording_date TEXT,
    consideration_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'USD',
    legal_description_raw TEXT,
    source_url TEXT,
    observation_id INTEGER REFERENCES source_observation(observation_id),
    raw_json TEXT,
    UNIQUE(source_id, jurisdiction_geoid, native_document_id)
);
CREATE INDEX IF NOT EXISTS idx_instrument_recording_date
    ON recorded_instrument(recording_date);

CREATE TABLE IF NOT EXISTS instrument_party (
    instrument_party_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument_id INTEGER NOT NULL REFERENCES recorded_instrument(instrument_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    entity_kind TEXT,
    raw_address TEXT,
    core_entity_id INTEGER,
    resolution_confidence REAL,
    resolution_status TEXT NOT NULL DEFAULT 'unreviewed',
    UNIQUE(instrument_id, sequence_no, role, raw_name)
);
CREATE INDEX IF NOT EXISTS idx_instrument_party_raw_name
    ON instrument_party(raw_name);
CREATE INDEX IF NOT EXISTS idx_instrument_party_normalized_name
    ON instrument_party(normalized_name);

CREATE TABLE IF NOT EXISTS instrument_parcel (
    instrument_id INTEGER NOT NULL REFERENCES recorded_instrument(instrument_id) ON DELETE CASCADE,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    link_method TEXT NOT NULL,
    link_confidence REAL,
    legal_description_raw TEXT,
    PRIMARY KEY(instrument_id, parcel_id)
);

CREATE TABLE IF NOT EXISTS parcel_lineage (
    predecessor_parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id),
    successor_parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id),
    relationship TEXT NOT NULL,
    effective_date TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL,
    evidence_ref TEXT,
    PRIMARY KEY(predecessor_parcel_id, successor_parcel_id, relationship, effective_date),
    CHECK (predecessor_parcel_id <> successor_parcel_id),
    CHECK (relationship IN ('split', 'merge', 'renumbered', 'condominium_conversion', 'other'))
);

CREATE TABLE IF NOT EXISTS ownership_assertion (
    ownership_assertion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parcel_id INTEGER NOT NULL REFERENCES parcel_snapshot(parcel_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    assertion_type TEXT NOT NULL,
    raw_owner_name TEXT NOT NULL,
    normalized_owner_name TEXT,
    core_entity_id INTEGER,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT,
    confidence TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    observation_id INTEGER REFERENCES source_observation(observation_id),
    evidence_ref TEXT,
    source_quote TEXT,
    UNIQUE(parcel_id, source_id, assertion_type, raw_owner_name, effective_from),
    CHECK (assertion_type IN ('assessment_roll', 'recorded_instrument', 'tax_account', 'derived_chain')),
    CHECK (confidence IN ('low', 'medium', 'high', 'confirmed')),
    CHECK (
        NOT (assertion_type = 'derived_chain' AND confidence = 'confirmed')
    )
);
CREATE INDEX IF NOT EXISTS idx_ownership_raw_name
    ON ownership_assertion(raw_owner_name);
CREATE INDEX IF NOT EXISTS idx_ownership_normalized_name
    ON ownership_assertion(normalized_owner_name);

CREATE TABLE IF NOT EXISTS document_artifact (
    artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    jurisdiction_geoid TEXT NOT NULL REFERENCES jurisdiction(geoid),
    native_document_id TEXT NOT NULL,
    instrument_id INTEGER REFERENCES recorded_instrument(instrument_id) ON DELETE SET NULL,
    sha256 TEXT,
    mime_type TEXT,
    page_count INTEGER,
    storage_path TEXT,
    source_url TEXT,
    acquisition_method TEXT NOT NULL,
    rights_tier TEXT NOT NULL,
    access_state TEXT NOT NULL DEFAULT 'public',
    acquired_at TEXT,
    UNIQUE(source_id, jurisdiction_geoid, native_document_id, sha256),
    CHECK (access_state IN (
        'public', 'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'unknown'
    ))
);

CREATE TABLE IF NOT EXISTS evidence_representation (
    representation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES document_artifact(artifact_id) ON DELETE CASCADE,
    representation_type TEXT NOT NULL,
    content_hash TEXT,
    model_or_parser TEXT,
    model_or_parser_version TEXT,
    prompt_or_schema_version TEXT,
    extraction_confidence REAL,
    page_locator TEXT,
    region_locator TEXT,
    source_quote TEXT,
    structured_json TEXT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

"""

COURT_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_snapshot (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    query_fingerprint TEXT,
    source_url TEXT,
    retrieved_at TEXT NOT NULL,
    access_status TEXT NOT NULL,
    coverage_json TEXT,
    schema_fingerprint TEXT,
    raw_artifact_sha256 TEXT,
    raw_artifact_path TEXT,
    raw_json TEXT,
    warning_json TEXT,
    CHECK (access_status IN (
        'ok', 'no_results', 'partial', 'unavailable', 'restricted',
        'human_required', 'rate_limited', 'terms_blocked', 'source_changed'
    ))
);
CREATE INDEX IF NOT EXISTS idx_court_snapshot_source
    ON source_snapshot(source_id, retrieved_at);
CREATE INDEX IF NOT EXISTS idx_court_snapshot_query
    ON source_snapshot(query_fingerprint);

CREATE TABLE IF NOT EXISTS court_data_delivery_receipt (
    receipt_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT,
    system_name TEXT,
    publisher TEXT,
    delivery_version TEXT NOT NULL,
    received_at TEXT NOT NULL,
    received_at_basis TEXT,
    provider_reference TEXT,
    correction_state TEXT,
    delivery_scope_note TEXT,
    specification_refs_json TEXT,
    case_document_refs_json TEXT,
    artifact_root TEXT,
    artifact_set_sha256 TEXT NOT NULL,
    payload_lineage_key TEXT NOT NULL,
    file_count INTEGER NOT NULL,
    total_size_bytes INTEGER NOT NULL,
    interpretation_json TEXT,
    created_at TEXT,
    raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_court_delivery_payload
    ON court_data_delivery_receipt(
        product_id, delivery_version, artifact_set_sha256
    );
CREATE INDEX IF NOT EXISTS idx_court_delivery_lineage
    ON court_data_delivery_receipt(payload_lineage_key);

CREATE TABLE IF NOT EXISTS court_data_delivery_file (
    receipt_id TEXT NOT NULL
        REFERENCES court_data_delivery_receipt(receipt_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    absolute_path TEXT,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    format_observation_json TEXT,
    zip_members_json TEXT,
    raw_json TEXT NOT NULL,
    PRIMARY KEY(receipt_id, relative_path)
);
CREATE INDEX IF NOT EXISTS idx_court_delivery_file_sha
    ON court_data_delivery_file(sha256);

CREATE TABLE IF NOT EXISTS court (
    court_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    native_court_id TEXT NOT NULL,
    name TEXT NOT NULL,
    state_code TEXT NOT NULL,
    county_geoid TEXT,
    court_level TEXT,
    division TEXT,
    branch TEXT,
    parent_court_id TEXT REFERENCES court(court_id),
    official_url TEXT,
    UNIQUE(source_id, native_court_id)
);

CREATE TABLE IF NOT EXISTS case_record (
    case_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    court_id TEXT NOT NULL REFERENCES court(court_id),
    raw_case_number TEXT NOT NULL,
    display_case_number TEXT,
    source_internal_id TEXT,
    case_identity_key TEXT GENERATED ALWAYS AS (
        CASE
            WHEN NULLIF(TRIM(source_internal_id), '') IS NOT NULL
            THEN 'native:' || TRIM(source_internal_id)
            ELSE 'number:' || raw_case_number
        END
    ) STORED,
    caption TEXT,
    case_type TEXT,
    filing_date TEXT,
    disposition_date TEXT,
    status TEXT,
    access_state TEXT NOT NULL DEFAULT 'public',
    native_access_state TEXT,
    certified_record INTEGER NOT NULL DEFAULT 0,
    source_url TEXT,
    snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
    raw_json TEXT,
    UNIQUE(source_id, court_id, case_identity_key),
    CHECK (access_state IN (
        'public', 'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'unknown'
    )),
    CHECK (certified_record IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_case_raw_number
    ON case_record(raw_case_number);
CREATE INDEX IF NOT EXISTS idx_case_caption
    ON case_record(caption);
CREATE INDEX IF NOT EXISTS idx_case_filing_date
    ON case_record(filing_date);

CREATE TABLE IF NOT EXISTS case_source_occurrence (
    occurrence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    record_identity_source_id TEXT NOT NULL,
    snapshot_id INTEGER NOT NULL REFERENCES source_snapshot(snapshot_id),
    record_kind TEXT NOT NULL,
    source_internal_id TEXT,
    source_result_id TEXT NOT NULL,
    canonical_ref TEXT,
    matched_party_name TEXT,
    case_type TEXT,
    filing_date TEXT,
    filing_location TEXT,
    source_url TEXT,
    raw_json TEXT NOT NULL,
    UNIQUE(source_id, snapshot_id, source_result_id)
);
CREATE INDEX IF NOT EXISTS idx_case_source_occurrence_case
    ON case_source_occurrence(case_id, source_id);
CREATE INDEX IF NOT EXISTS idx_case_source_occurrence_party
    ON case_source_occurrence(matched_party_name);

CREATE TABLE IF NOT EXISTS case_claim (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    native_claim_id TEXT NOT NULL,
    sequence_no INTEGER,
    claim_type TEXT,
    claim_date TEXT,
    claimant_raw TEXT,
    amount_minor INTEGER,
    currency TEXT,
    status TEXT,
    limited_stub INTEGER,
    access_state TEXT,
    native_access_state TEXT,
    snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
    raw_json TEXT,
    UNIQUE(case_id, native_claim_id),
    CHECK (limited_stub IN (0, 1) OR limited_stub IS NULL),
    CHECK (
        access_state IS NULL OR access_state IN (
            'public', 'restricted', 'sealed', 'expunged', 'removed',
            'redacted', 'unknown'
        )
    )
);
CREATE INDEX IF NOT EXISTS idx_case_claim_sequence
    ON case_claim(case_id, sequence_no, claim_id);
CREATE INDEX IF NOT EXISTS idx_case_claim_native
    ON case_claim(source_id, native_claim_id);

CREATE TABLE IF NOT EXISTS case_party (
    case_party_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL DEFAULT 0,
    role TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    entity_kind TEXT,
    core_entity_id INTEGER,
    resolution_confidence REAL,
    resolution_status TEXT NOT NULL DEFAULT 'unreviewed',
    access_state TEXT NOT NULL DEFAULT 'public',
    native_access_state TEXT,
    UNIQUE(case_id, sequence_no, role, raw_name),
    CHECK (access_state IN (
        'public', 'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'unknown'
    ))
);
CREATE INDEX IF NOT EXISTS idx_case_party_raw_name
    ON case_party(raw_name);
CREATE INDEX IF NOT EXISTS idx_case_party_normalized_name
    ON case_party(normalized_name);

CREATE TABLE IF NOT EXISTS attorney (
    attorney_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    bar_id TEXT NOT NULL DEFAULT '',
    firm_name TEXT,
    UNIQUE(source_id, raw_name, bar_id)
);

CREATE TABLE IF NOT EXISTS case_representation (
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    case_party_id INTEGER NOT NULL REFERENCES case_party(case_party_id) ON DELETE CASCADE,
    attorney_id INTEGER NOT NULL REFERENCES attorney(attorney_id),
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT,
    source_entry_id TEXT,
    PRIMARY KEY(case_id, attorney_id, case_party_id, effective_from)
);

CREATE TABLE IF NOT EXISTS judicial_officer (
    judicial_officer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    raw_name TEXT NOT NULL,
    normalized_name TEXT,
    native_officer_id TEXT NOT NULL DEFAULT '',
    UNIQUE(source_id, raw_name, native_officer_id)
);

CREATE TABLE IF NOT EXISTS case_assignment (
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    judicial_officer_id INTEGER NOT NULL REFERENCES judicial_officer(judicial_officer_id),
    assignment_role TEXT NOT NULL,
    effective_from TEXT NOT NULL DEFAULT '',
    effective_to TEXT,
    PRIMARY KEY(case_id, judicial_officer_id, assignment_role, effective_from)
);

CREATE TABLE IF NOT EXISTS docket_entry (
    docket_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    native_entry_id TEXT NOT NULL,
    sequence_no TEXT,
    subsequence_no TEXT,
    event_code TEXT,
    raw_text TEXT,
    filed_date TEXT,
    entered_date TEXT,
    event_date TEXT,
    filer_raw TEXT,
    document_available INTEGER,
    access_state TEXT NOT NULL DEFAULT 'public',
    native_access_state TEXT,
    snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
    raw_json TEXT,
    UNIQUE(case_id, native_entry_id),
    CHECK (document_available IN (0, 1) OR document_available IS NULL),
    CHECK (access_state IN (
        'public', 'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'unknown'
    ))
);
CREATE INDEX IF NOT EXISTS idx_docket_case_sequence
    ON docket_entry(case_id, sequence_no, subsequence_no);

CREATE TABLE IF NOT EXISTS case_event (
    case_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    native_event_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    event_date TEXT,
    filed_date TEXT,
    entered_date TEXT,
    disposition TEXT,
    assertion_kind TEXT NOT NULL DEFAULT 'docket_metadata',
    native_assertion_kind TEXT,
    source_entry_id INTEGER REFERENCES docket_entry(docket_entry_id),
    snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
    raw_json TEXT,
    UNIQUE(case_id, source_id, event_type, event_date, native_event_id),
    CHECK (assertion_kind IN (
        'docket_metadata', 'party_allegation', 'charge', 'sworn_declaration',
        'admission', 'court_finding', 'verdict', 'judgment', 'other'
    ))
);

CREATE TABLE IF NOT EXISTS document_artifact (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    docket_entry_id INTEGER REFERENCES docket_entry(docket_entry_id) ON DELETE SET NULL,
    source_id TEXT NOT NULL,
    native_document_id TEXT NOT NULL,
    document_type TEXT,
    filed_date TEXT,
    source_url TEXT,
    sha256 TEXT,
    mime_type TEXT,
    page_count INTEGER,
    storage_path TEXT,
    ocr_status TEXT,
    certification_status TEXT,
    access_state TEXT NOT NULL DEFAULT 'public',
    native_access_state TEXT,
    acquired_at TEXT,
    UNIQUE(case_id, native_document_id, sha256),
    CHECK (access_state IN (
        'public', 'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'unknown'
    ))
);
CREATE INDEX IF NOT EXISTS idx_court_document_native
    ON document_artifact(source_id, native_document_id);

CREATE TABLE IF NOT EXISTS evidence_representation (
    representation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES document_artifact(document_id) ON DELETE CASCADE,
    representation_type TEXT NOT NULL,
    content_hash TEXT,
    model_or_parser TEXT,
    model_or_parser_version TEXT,
    prompt_or_schema_version TEXT,
    extraction_confidence REAL,
    page_locator TEXT,
    region_locator TEXT,
    source_quote TEXT,
    assertion_kind TEXT,
    native_assertion_kind TEXT,
    structured_json TEXT,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        assertion_kind IS NULL OR assertion_kind IN (
            'docket_metadata', 'party_allegation', 'charge', 'sworn_declaration',
            'admission', 'court_finding', 'verdict', 'judgment', 'other'
        )
    )
);

CREATE TABLE IF NOT EXISTS restriction_event (
    restriction_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    native_event_type TEXT NOT NULL DEFAULT '',
    effective_at TEXT NOT NULL,
    reason TEXT,
    direction_ref TEXT,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (event_type IN (
        'restricted', 'sealed', 'expunged', 'removed', 'redacted', 'restored',
        'other'
    ))
);
CREATE INDEX IF NOT EXISTS idx_restriction_case
    ON restriction_event(case_id, effective_at);

CREATE TABLE IF NOT EXISTS case_relation (
    from_case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    to_case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    evidence_ref TEXT,
    PRIMARY KEY(from_case_id, to_case_id, relation_type),
    CHECK (from_case_id <> to_case_id),
    CHECK (relation_type IN (
        'related', 'consolidated', 'transferred', 'removed_to', 'appealed_to', 'supersedes'
    ))
);
"""


def _column_names(db: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in db.execute(f'PRAGMA table_xinfo("{table}")')
    }


def _table_sql(db: sqlite3.Connection, table: str) -> str:
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return str(row["sql"] or "") if row is not None else ""


def _unique_index_columns(
    db: sqlite3.Connection,
    table: str,
) -> set[tuple[str, ...]]:
    unique_indexes: set[tuple[str, ...]] = set()
    for row in db.execute(f'PRAGMA index_list("{table}")'):
        if not bool(row["unique"]):
            continue
        name = str(row["name"]).replace('"', '""')
        columns = tuple(
            str(column["name"])
            for column in db.execute(f'PRAGMA index_info("{name}")')
        )
        unique_indexes.add(columns)
    return unique_indexes


def _create_case_record_table(
    db: sqlite3.Connection,
    table: str,
) -> None:
    identifier = table.replace('"', '""')
    db.execute(
        f"""
        CREATE TABLE "{identifier}" (
            case_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            court_id TEXT NOT NULL REFERENCES court(court_id),
            raw_case_number TEXT NOT NULL,
            display_case_number TEXT,
            source_internal_id TEXT,
            case_identity_key TEXT GENERATED ALWAYS AS (
                CASE
                    WHEN NULLIF(TRIM(source_internal_id), '') IS NOT NULL
                    THEN 'native:' || TRIM(source_internal_id)
                    ELSE 'number:' || raw_case_number
                END
            ) STORED,
            caption TEXT,
            case_type TEXT,
            filing_date TEXT,
            disposition_date TEXT,
            status TEXT,
            access_state TEXT NOT NULL DEFAULT 'public',
            native_access_state TEXT,
            certified_record INTEGER NOT NULL DEFAULT 0,
            source_url TEXT,
            snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
            raw_json TEXT,
            UNIQUE(source_id, court_id, case_identity_key),
            CHECK (access_state IN (
                'public', 'restricted', 'sealed', 'expunged', 'removed',
                'redacted', 'unknown'
            )),
            CHECK (certified_record IN (0, 1))
        )
        """
    )


def _create_case_indexes(db: sqlite3.Connection) -> None:
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_case_raw_number
        ON case_record(raw_case_number)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_case_caption
        ON case_record(caption)
        """
    )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_case_filing_date
        ON case_record(filing_date)
        """
    )


def _rebuild_case_record_identity(db: sqlite3.Connection) -> None:
    """Rebuild case identity while retaining stable case primary keys."""

    replacement = "case_record_schema_v4"
    db.execute(f'DROP TABLE IF EXISTS "{replacement}"')
    _create_case_record_table(db, replacement)
    db.execute(
        f"""
        INSERT INTO "{replacement}"(
            case_id, source_id, court_id, raw_case_number,
            display_case_number, source_internal_id, caption, case_type,
            filing_date, disposition_date, status, access_state,
            native_access_state, certified_record, source_url, snapshot_id,
            raw_json
        )
        SELECT
            case_id, source_id, court_id, raw_case_number,
            display_case_number, source_internal_id, caption, case_type,
            filing_date, disposition_date, status, access_state,
            native_access_state, certified_record, source_url, snapshot_id,
            raw_json
        FROM case_record
        ORDER BY case_id
        """
    )
    db.execute("DROP TABLE case_record")
    db.execute(
        f'ALTER TABLE "{replacement}" RENAME TO case_record'
    )
    _create_case_indexes(db)


def _rebuild_case_event(db: sqlite3.Connection) -> None:
    db.execute("ALTER TABLE case_event RENAME TO case_event_schema_v1")
    db.execute(
        """
        CREATE TABLE case_event (
            case_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            native_event_id TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL,
            event_date TEXT,
            filed_date TEXT,
            entered_date TEXT,
            disposition TEXT,
            assertion_kind TEXT NOT NULL DEFAULT 'docket_metadata',
            native_assertion_kind TEXT,
            source_entry_id INTEGER REFERENCES docket_entry(docket_entry_id),
            snapshot_id INTEGER REFERENCES source_snapshot(snapshot_id),
            raw_json TEXT,
            UNIQUE(case_id, source_id, event_type, event_date, native_event_id),
            CHECK (assertion_kind IN (
                'docket_metadata', 'party_allegation', 'charge', 'sworn_declaration',
                'admission', 'court_finding', 'verdict', 'judgment', 'other'
            ))
        )
        """
    )
    db.execute(
        """
        INSERT INTO case_event(
            case_event_id, case_id, source_id, native_event_id, event_type,
            event_date, filed_date, entered_date, disposition, assertion_kind,
            native_assertion_kind, source_entry_id, snapshot_id, raw_json
        )
        SELECT
            case_event_id, case_id, source_id, native_event_id, event_type,
            event_date, filed_date, entered_date, disposition, assertion_kind,
            assertion_kind, source_entry_id, snapshot_id, raw_json
        FROM case_event_schema_v1
        """
    )
    db.execute("DROP TABLE case_event_schema_v1")


def _rebuild_evidence_representation(db: sqlite3.Connection) -> None:
    db.execute(
        "ALTER TABLE evidence_representation "
        "RENAME TO evidence_representation_schema_v1"
    )
    db.execute(
        """
        CREATE TABLE evidence_representation (
            representation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL
                REFERENCES document_artifact(document_id) ON DELETE CASCADE,
            representation_type TEXT NOT NULL,
            content_hash TEXT,
            model_or_parser TEXT,
            model_or_parser_version TEXT,
            prompt_or_schema_version TEXT,
            extraction_confidence REAL,
            page_locator TEXT,
            region_locator TEXT,
            source_quote TEXT,
            assertion_kind TEXT,
            native_assertion_kind TEXT,
            structured_json TEXT,
            review_status TEXT NOT NULL DEFAULT 'unreviewed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (
                assertion_kind IS NULL OR assertion_kind IN (
                    'docket_metadata', 'party_allegation', 'charge',
                    'sworn_declaration', 'admission', 'court_finding',
                    'verdict', 'judgment', 'other'
                )
            )
        )
        """
    )
    db.execute(
        """
        INSERT INTO evidence_representation(
            representation_id, document_id, representation_type, content_hash,
            model_or_parser, model_or_parser_version, prompt_or_schema_version,
            extraction_confidence, page_locator, region_locator, source_quote,
            assertion_kind, native_assertion_kind, structured_json,
            review_status, created_at
        )
        SELECT
            representation_id, document_id, representation_type, content_hash,
            model_or_parser, model_or_parser_version, prompt_or_schema_version,
            extraction_confidence, page_locator, region_locator, source_quote,
            assertion_kind, assertion_kind, structured_json, review_status,
            created_at
        FROM evidence_representation_schema_v1
        """
    )
    db.execute("DROP TABLE evidence_representation_schema_v1")


def _rebuild_restriction_event(db: sqlite3.Connection) -> None:
    db.execute(
        "ALTER TABLE restriction_event RENAME TO restriction_event_schema_v1"
    )
    db.execute(
        """
        CREATE TABLE restriction_event (
            restriction_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES case_record(case_id) ON DELETE CASCADE,
            source_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            native_event_type TEXT NOT NULL DEFAULT '',
            effective_at TEXT NOT NULL,
            reason TEXT,
            direction_ref TEXT,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (event_type IN (
                'restricted', 'sealed', 'expunged', 'removed', 'redacted',
                'restored', 'other'
            ))
        )
        """
    )
    db.execute(
        """
        INSERT INTO restriction_event(
            restriction_event_id, case_id, source_id, event_type,
            native_event_type, effective_at, reason, direction_ref, applied_at
        )
        SELECT
            restriction_event_id, case_id, source_id, event_type, event_type,
            effective_at, reason, direction_ref, applied_at
        FROM restriction_event_schema_v1
        """
    )
    db.execute("DROP TABLE restriction_event_schema_v1")
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_restriction_case
        ON restriction_event(case_id, effective_at)
        """
    )


def _migrate_property_schema(db: sqlite3.Connection) -> None:
    """Apply additive property-event columns to existing sidecars."""

    columns = {
        str(row["name"])
        for row in db.execute("PRAGMA table_info(property_event)")
    }
    if "event_date" not in columns:
        db.execute("ALTER TABLE property_event ADD COLUMN event_date TEXT")
    if "normalized_case_number" not in columns:
        db.execute(
            "ALTER TABLE property_event ADD COLUMN normalized_case_number TEXT"
        )
    db.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_property_event_join
        ON property_event(
            source_id, jurisdiction_geoid, normalized_case_number, event_date
        )
        """
    )
    relation_columns = {
        str(row["name"]): int(row["notnull"])
        for row in db.execute(
            "PRAGMA table_info(property_event_relation)"
        )
    }
    optional_relation_fields = {
        "normalized_case_number",
        "event_date",
        "overlapping_parcels_json",
    }
    if any(
        relation_columns.get(field_name) == 1
        for field_name in optional_relation_fields
    ):
        db.execute("DROP INDEX IF EXISTS idx_property_event_relation_case_date")
        db.execute("DROP INDEX IF EXISTS idx_property_event_relation_related")
        db.execute(
            """
            ALTER TABLE property_event_relation
            RENAME TO property_event_relation_strict
            """
        )
        db.execute(
            """
            CREATE TABLE property_event_relation (
                relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL
                    REFERENCES property_event(event_id) ON DELETE CASCADE,
                related_event_id INTEGER NOT NULL
                    REFERENCES property_event(event_id) ON DELETE CASCADE,
                relationship TEXT NOT NULL,
                independent_corroboration INTEGER NOT NULL DEFAULT 0
                    CHECK (independent_corroboration IN (0, 1)),
                normalized_case_number TEXT,
                event_date TEXT,
                overlapping_parcels_json TEXT,
                evidence_json TEXT NOT NULL,
                CHECK (event_id < related_event_id),
                UNIQUE(event_id, related_event_id, relationship)
            )
            """
        )
        db.execute(
            """
            INSERT INTO property_event_relation(
                relation_id, event_id, related_event_id, relationship,
                independent_corroboration, normalized_case_number, event_date,
                overlapping_parcels_json, evidence_json
            )
            SELECT relation_id, event_id, related_event_id, relationship,
                   independent_corroboration, normalized_case_number,
                   event_date, overlapping_parcels_json, evidence_json
            FROM property_event_relation_strict
            """
        )
        db.execute("DROP TABLE property_event_relation_strict")
        db.execute(
            """
            CREATE INDEX idx_property_event_relation_case_date
            ON property_event_relation(normalized_case_number, event_date)
            """
        )
        db.execute(
            """
            CREATE INDEX idx_property_event_relation_related
            ON property_event_relation(related_event_id, relationship)
            """
        )
    violations = list(db.execute("PRAGMA foreign_key_check"))
    if violations:
        raise sqlite3.IntegrityError(
            "property schema migration produced "
            f"{len(violations)} foreign-key violations"
        )


def _migrate_court_schema(db: sqlite3.Connection) -> None:
    """Upgrade court sidecars while retaining native labels and child rows."""
    db.commit()
    db.execute("PRAGMA foreign_keys=OFF")
    try:
        db.execute("BEGIN")
        for table in (
            "case_record",
            "case_party",
            "docket_entry",
            "document_artifact",
        ):
            if "native_access_state" not in _column_names(db, table):
                db.execute(f'ALTER TABLE "{table}" ADD COLUMN native_access_state TEXT')
            db.execute(
                f"""
                UPDATE "{table}"
                SET native_access_state=access_state
                WHERE native_access_state IS NULL
                """
            )

        case_unique_indexes = _unique_index_columns(db, "case_record")
        expected_case_identity = (
            "source_id",
            "court_id",
            "case_identity_key",
        )
        legacy_raw_identity = (
            "source_id",
            "court_id",
            "raw_case_number",
        )
        case_record_sql = _table_sql(db, "case_record").lower()
        if (
            "case_identity_key"
            not in _column_names(db, "case_record")
            or expected_case_identity not in case_unique_indexes
            or legacy_raw_identity in case_unique_indexes
            or "'native:'" not in case_record_sql
            or "'number:'" not in case_record_sql
        ):
            _rebuild_case_record_identity(db)

        case_event_sql = _table_sql(db, "case_event").lower()
        if (
            "native_assertion_kind" not in _column_names(db, "case_event")
            or "'other'" not in case_event_sql
        ):
            _rebuild_case_event(db)

        representation_sql = _table_sql(db, "evidence_representation").lower()
        if (
            "native_assertion_kind"
            not in _column_names(db, "evidence_representation")
            or "'other'" not in representation_sql
        ):
            _rebuild_evidence_representation(db)

        restriction_sql = _table_sql(db, "restriction_event").lower()
        if (
            "native_event_type" not in _column_names(db, "restriction_event")
            or "'other'" not in restriction_sql
        ):
            _rebuild_restriction_event(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.execute("PRAGMA foreign_keys=ON")

    violations = list(db.execute("PRAGMA foreign_key_check"))
    if violations:
        raise sqlite3.IntegrityError(
            f"court schema migration produced {len(violations)} foreign-key violations"
        )


def _connect(path: Path | str, schema: str, domain: str) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(schema)
    if domain == "property":
        _migrate_property_schema(db)
    elif domain == "state_local_courts":
        _migrate_court_schema(db)
    db.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    db.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("domain", domain),
    )
    db.commit()
    return db


def connect_property(path: Path | str = DEFAULT_PROPERTY_DB) -> sqlite3.Connection:
    """Open the property sidecar and ensure its schema."""
    return _connect(path, PROPERTY_SCHEMA, "property")


def connect_courts(path: Path | str = DEFAULT_COURT_DB) -> sqlite3.Connection:
    """Open the state/local court sidecar and ensure its schema."""
    return _connect(path, COURT_SCHEMA, "state_local_courts")


def canonical_property_ref(
    source_id: str,
    jurisdiction_geoid: str,
    record_kind: str,
    native_id: str,
) -> str:
    """Return a stable, URL-safe property-record reference."""
    values = (source_id, jurisdiction_geoid, record_kind, native_id)
    if any(not value or not str(value).strip() for value in values):
        raise ValueError("property references require source, jurisdiction, kind, and native id")
    encoded = "/".join(quote(str(value).strip(), safe=".-_") for value in values)
    return f"PROPERTY:{encoded}"


def court_case_identity_key(
    raw_case_number: str,
    source_internal_id: str | None = None,
) -> str:
    """Return the namespaced identity stored for one source-native case."""

    raw_number = str(raw_case_number).strip()
    if not raw_number:
        raise ValueError("raw_case_number cannot be blank")
    if source_internal_id is not None:
        native_id = str(source_internal_id).strip()
        if native_id:
            return f"{CASE_IDENTITY_NATIVE_PREFIX}{native_id}"
    return f"{CASE_IDENTITY_NUMBER_PREFIX}{raw_number}"


def canonical_court_ref(
    source_id: str,
    court_id: str,
    case_number: str,
    record_kind: str = "case",
    native_id: str | None = None,
) -> str:
    """Return a stable, URL-safe state/local court reference."""
    values = (source_id, court_id, case_number, record_kind)
    if any(not value or not str(value).strip() for value in values):
        raise ValueError("court references require source, court, case number, and kind")
    parts = [*values]
    if native_id is not None:
        if not str(native_id).strip():
            raise ValueError("native id cannot be blank")
        parts.append(native_id)
    encoded = "/".join(quote(str(value).strip(), safe=".-_") for value in parts)
    return f"STATECOURT:{encoded}"


def apply_case_restriction(
    db: sqlite3.Connection,
    *,
    source_id: str,
    court_id: str,
    case_number: str,
    source_internal_id: str | None = None,
    event_type: str,
    effective_at: str,
    reason: str | None = None,
    direction_ref: str | None = None,
) -> int:
    """Record and propagate a court restriction or restoration.

    Restrictions update the case, claims, parties, docket entries, and
    document artifacts in one transaction. A restoration changes only the
    serving state; it does not erase the audit trail.
    """
    native_event_type = str(event_type).strip()
    if not native_event_type:
        raise ValueError("restriction event type cannot be blank")
    canonical_event_type = canonical_restriction_event(native_event_type)

    selector = source_internal_id
    if selector is not None:
        selector = str(selector).strip()
        if not selector:
            raise ValueError("source_internal_id cannot be blank")
    params: list[Any] = [source_id, court_id, case_number]
    internal_condition = ""
    if selector is not None:
        internal_condition = (
            " AND source_internal_id IS NOT NULL "
            "AND TRIM(source_internal_id) = ?"
        )
        params.append(selector)
    rows = db.execute(
        f"""
        SELECT case_id, source_internal_id
        FROM case_record
        WHERE source_id = ? AND court_id = ? AND raw_case_number = ?
        {internal_condition}
        ORDER BY case_id
        LIMIT 2
        """,
        params,
    ).fetchall()
    if not rows:
        suffix = f"/{selector}" if selector is not None else ""
        raise KeyError(
            f"case not found: {source_id}/{court_id}/{case_number}{suffix}"
        )
    if len(rows) > 1:
        raise ValueError(
            "case number is ambiguous; provide source_internal_id"
        )

    case_id = int(rows[0]["case_id"])
    if canonical_event_type == "restored":
        access_state = "public"
    elif canonical_event_type == "other":
        access_state = "unknown"
    else:
        access_state = canonical_event_type
    with db:
        cursor = db.execute(
            """
            INSERT INTO restriction_event(
                case_id, source_id, event_type, native_event_type, effective_at,
                reason, direction_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                source_id,
                canonical_event_type,
                native_event_type,
                effective_at,
                reason,
                direction_ref,
            ),
        )
        db.execute(
            """
            UPDATE case_record
            SET access_state = ?, native_access_state = ?
            WHERE case_id = ?
            """,
            (access_state, native_event_type, case_id),
        )
        db.execute(
            """
            UPDATE case_claim
            SET access_state = ?, native_access_state = ?
            WHERE case_id = ?
            """,
            (access_state, native_event_type, case_id),
        )
        db.execute(
            """
            UPDATE case_party
            SET access_state = ?, native_access_state = ?
            WHERE case_id = ?
            """,
            (access_state, native_event_type, case_id),
        )
        db.execute(
            """
            UPDATE docket_entry
            SET access_state = ?, native_access_state = ?
            WHERE case_id = ?
            """,
            (access_state, native_event_type, case_id),
        )
        db.execute(
            """
            UPDATE document_artifact
            SET access_state = ?, native_access_state = ?
            WHERE case_id = ?
            """,
            (access_state, native_event_type, case_id),
        )
    return int(cursor.lastrowid)


def _table_counts(db: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row["name"]
        for row in db.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]
    return {
        table: int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in tables
    }


def stats(
    property_path: Path | str = DEFAULT_PROPERTY_DB,
    court_path: Path | str = DEFAULT_COURT_DB,
) -> dict[str, Any]:
    """Return sidecar table counts."""
    property_db = connect_property(property_path)
    court_db = connect_courts(court_path)
    try:
        return {
            "schema_version": SCHEMA_VERSION,
            "property": _table_counts(property_db),
            "state_local_courts": _table_counts(court_db),
        }
    finally:
        property_db.close()
        court_db.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize and inspect public-record sidecars")
    parser.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    parser.add_argument("--court-db", default=str(DEFAULT_COURT_DB))
    parser.add_argument("--json", action="store_true", dest="json_out")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create or migrate both sidecar schemas")
    sub.add_parser("stats", help="Show row counts for both sidecars")

    restrict = sub.add_parser(
        "restrict-case",
        help="Record and propagate a sealing/removal/redaction/restoration event",
    )
    restrict.add_argument("--source-id", required=True)
    restrict.add_argument("--court-id", required=True)
    restrict.add_argument("--case-number", required=True)
    restrict.add_argument("--source-internal-id")
    restrict.add_argument(
        "--state",
        required=True,
        help="Canonical or source-native restriction/restoration label",
    )
    restrict.add_argument("--effective-at", required=True)
    restrict.add_argument("--reason")
    restrict.add_argument("--direction-ref")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    property_path = Path(args.property_db)
    court_path = Path(args.court_db)

    if args.command == "init":
        property_db = connect_property(property_path)
        court_db = connect_courts(court_path)
        property_db.close()
        court_db.close()
        result: dict[str, Any] = {
            "status": "ok",
            "schema_version": SCHEMA_VERSION,
            "property_db": str(property_path),
            "court_db": str(court_path),
        }
    elif args.command == "stats":
        result = stats(property_path, court_path)
    elif args.command == "restrict-case":
        court_db = connect_courts(court_path)
        try:
            event_id = apply_case_restriction(
                court_db,
                source_id=args.source_id,
                court_id=args.court_id,
                case_number=args.case_number,
                source_internal_id=args.source_internal_id,
                event_type=args.state,
                effective_at=args.effective_at,
                reason=args.reason,
                direction_ref=args.direction_ref,
            )
        finally:
            court_db.close()
        result = {"status": "ok", "restriction_event_id": event_id}
    else:  # pragma: no cover - argparse enforces this
        parser.error(f"unknown command: {args.command}")
        return

    if args.json_out:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
