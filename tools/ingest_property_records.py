#!/usr/bin/env python3
"""Normalize property-source envelopes into the property sidecar.

The adapter-neutral entry point dispatches canonical result envelopes from the
supported parcel and recorder adapters. It preserves the complete query
envelope and each normalized record as canonical JSON with SHA-256 hashes
before projecting stable fields into the shared property model.

Usage:
    uv run python tools/ingest_property_records.py ingest \
      --input /tmp/nc-parcels.json --output /tmp/ingest-summary.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, sha256_fingerprint
    from public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )


NC_ONEMAP_SOURCE_ID = "us-nc-onemap-parcels"
COOK_PROPERTY_SOURCE_ID = "us-il-cook-parcel-universe"
MD_PROPERTY_SOURCE_ID = "us-md-sdat-property-hidden"
ACRIS_SOURCE_ID = "us-nyc-acris"
INGESTABLE_STATUSES = frozenset({"ok", "no_results", "partial"})
OBSERVABLE_STATUSES = frozenset(
    {
        *INGESTABLE_STATUSES,
        "unavailable",
        "restricted",
        "human_required",
        "rate_limited",
        "terms_blocked",
        "source_changed",
    }
)
PROJECTED_SOURCE_IDS = frozenset(
    {
        NC_ONEMAP_SOURCE_ID,
        COOK_PROPERTY_SOURCE_ID,
        MD_PROPERTY_SOURCE_ID,
        ACRIS_SOURCE_ID,
    }
)

STATE_METADATA = {
    "17": ("Illinois", "IL"),
    "24": ("Maryland", "MD"),
    "36": ("New York", "NY"),
    "37": ("North Carolina", "NC"),
}

ACRIS_BOROUGH_METADATA = {
    "1": ("36061", "New York County (Manhattan)"),
    "2": ("36005", "Bronx County"),
    "3": ("36047", "Kings County (Brooklyn)"),
    "4": ("36081", "Queens County"),
    "5": ("36085", "Richmond County"),
}

ACRIS_PARTY_ROLES = {
    "1": "grantor",
    "2": "grantee",
    "3": "other",
}


class PropertyIngestError(ValueError):
    """Raised when an input envelope cannot be normalized."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _minor_units(value: Any) -> int | None:
    """Convert a source dollar value to integer cents without float rounding."""
    if value in (None, ""):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise PropertyIngestError(f"invalid monetary value: {value!r}") from error
    if not amount.is_finite():
        raise PropertyIngestError(f"non-finite monetary value: {value!r}")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _normalized_address(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.upper().split())


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PropertyIngestError(f"{field_name} must be an object")
    return dict(value)


def _source_id(envelope: Mapping[str, Any]) -> str:
    query = _mapping(envelope.get("query"), "query")
    source = _mapping(query.get("source"), "query.source")
    value = _text(source.get("source_id"))
    if not value:
        raise PropertyIngestError("query.source.source_id is required")
    return value


def _record_url(envelope: Mapping[str, Any]) -> str | None:
    query = envelope.get("query")
    if not isinstance(query, Mapping):
        return None
    source = query.get("source")
    if not isinstance(source, Mapping):
        return None
    return _text(source.get("base_url"))


def _roll_year(record: Mapping[str, Any]) -> str:
    raw = record.get("raw_attributes")
    if isinstance(raw, Mapping):
        value = _text(raw.get("reviseyear"))
        if value:
            return value[:4]
    revised = _text(record.get("source_revised_date"))
    if revised and len(revised) >= 4 and revised[:4].isdigit():
        return revised[:4]
    return ""


def _address_raw(address: Mapping[str, Any]) -> str | None:
    raw = _text(address.get("raw"))
    unit = _text(address.get("unit"))
    if raw and unit and unit.casefold() not in raw.casefold():
        return f"{raw} {unit}"
    return raw or unit


def _upsert_jurisdiction(db, record: Mapping[str, Any]) -> str:
    jurisdiction = _mapping(record.get("jurisdiction"), "record.jurisdiction")
    geoid = _text(jurisdiction.get("county_geoid")) or "37"
    if not geoid.isdigit() or len(geoid) not in {2, 5}:
        raise PropertyIngestError(f"invalid North Carolina jurisdiction GEOID: {geoid!r}")
    county_name = _text(jurisdiction.get("county_name"))
    name = f"{county_name} County" if county_name else "North Carolina"
    jurisdiction_type = "county" if len(geoid) == 5 else "state"
    parent = "37" if len(geoid) == 5 else None
    if parent:
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES ('37', 'North Carolina', 'state', 'NC')
            ON CONFLICT(geoid) DO UPDATE SET
                name=excluded.name,
                jurisdiction_type=excluded.jurisdiction_type,
                state_code=excluded.state_code
            """
        )
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES (?, ?, ?, ?, 'NC', ?)
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """,
        (geoid, name, jurisdiction_type, parent, geoid[-3:] if parent else None),
    )
    return geoid


def _insert_observation(
    db,
    *,
    source_id: str,
    source_native_id: str | None,
    record_kind: str,
    query_fingerprint: str | None,
    source_url: str | None,
    retrieved_at: str,
    access_status: str,
    schema_fingerprint: str | None,
    raw: Mapping[str, Any],
    raw_artifact_path: str | None,
    warnings: list[str],
    raw_artifact_sha256: str | None = None,
) -> tuple[int, str]:
    raw_json = canonical_json(raw)
    raw_hash = sha256_fingerprint(raw)
    cursor = db.execute(
        """
        INSERT INTO source_observation(
            source_id, source_native_id, record_kind, query_fingerprint,
            source_url, retrieved_at, access_status, schema_fingerprint,
            raw_artifact_sha256, raw_artifact_path, raw_json, warning_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            source_native_id,
            record_kind,
            query_fingerprint,
            source_url,
            retrieved_at,
            access_status,
            schema_fingerprint,
            raw_artifact_sha256 or raw_hash,
            raw_artifact_path,
            raw_json,
            canonical_json(warnings),
        ),
    )
    return int(cursor.lastrowid), raw_hash


def _upsert_address(
    db,
    *,
    parcel_id: int,
    source_id: str,
    role: str,
    address: Mapping[str, Any],
    effective_from: str,
) -> bool:
    raw_address = _address_raw(address)
    if not raw_address:
        return False
    params = (
        parcel_id,
        role,
        raw_address,
        _normalized_address(raw_address),
        _text(address.get("city")),
        _text(address.get("state")),
        _text(address.get("postal_code")),
        source_id,
        effective_from,
    )
    exists = db.execute(
        """
        SELECT 1 FROM parcel_address
        WHERE parcel_id=? AND address_role=? AND raw_address=?
          AND source_id=? AND effective_from=?
        """,
        (parcel_id, role, raw_address, source_id, effective_from),
    ).fetchone()
    if exists:
        return False
    db.execute(
        """
        INSERT INTO parcel_address(
            parcel_id, address_role, raw_address, normalized_address,
            city, state, postal_code, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        params,
    )
    return True


def _record_source_url(
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
) -> str | None:
    links = record.get("source_links")
    if isinstance(links, Mapping):
        for key in ("real_property_search", "finder", "record", "document"):
            value = _text(links.get(key))
            if value:
                return value
    master = record.get("master")
    if isinstance(master, Mapping):
        value = _text(master.get("document_url"))
        if value:
            return value
    return _record_url(envelope)


def _observation_context(
    envelope: Mapping[str, Any],
) -> tuple[str | None, str, str, list[str]]:
    query = _mapping(envelope.get("query"), "query")
    retrieved_at = _text(envelope.get("retrieved_at"))
    if not retrieved_at:
        raise PropertyIngestError("retrieved_at is required")
    status = _text(envelope.get("status"))
    if status not in OBSERVABLE_STATUSES:
        raise PropertyIngestError(f"unsupported ingestion source status {status!r}")
    warnings = envelope.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise PropertyIngestError("warnings must be a list of strings")
    return _text(query.get("fingerprint")), retrieved_at, status, list(warnings)


def _record_schema_fingerprint(record: Mapping[str, Any]) -> str | None:
    return _text(
        record.get("response_schema_fingerprint")
        or record.get("schema_fingerprint")
        or record.get("adapter_schema_fingerprint")
    )


def _assert_record_source(
    record: Mapping[str, Any],
    source_id: str,
) -> None:
    record_source_id = _text(record.get("source_id"))
    if record_source_id and record_source_id != source_id:
        raise PropertyIngestError(
            f"record source_id {record_source_id} does not match envelope {source_id}"
        )


def _upsert_jurisdiction_values(
    db,
    *,
    geoid: str,
    name: str,
    state_code: str,
    jurisdiction_type: str,
    parent_geoid: str | None = None,
) -> str:
    if parent_geoid:
        state_name, canonical_state_code = STATE_METADATA.get(
            parent_geoid,
            (state_code, state_code),
        )
        db.execute(
            """
            INSERT INTO jurisdiction(
                geoid, name, jurisdiction_type, state_code
            ) VALUES (?, ?, 'state', ?)
            ON CONFLICT(geoid) DO UPDATE SET
                name=excluded.name,
                jurisdiction_type=excluded.jurisdiction_type,
                state_code=excluded.state_code
            """,
            (parent_geoid, state_name, canonical_state_code),
        )
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """,
        (
            geoid,
            name,
            jurisdiction_type,
            parent_geoid,
            state_code,
            geoid[-3:] if parent_geoid and geoid.isdigit() else None,
        ),
    )
    return geoid


def _upsert_record_jurisdiction(
    db,
    record: Mapping[str, Any],
    *,
    fallback_geoid: str,
    fallback_name: str,
    fallback_state_code: str,
) -> str:
    jurisdiction = record.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        jurisdiction = {}
    geoid = _text(jurisdiction.get("county_geoid")) or fallback_geoid
    state_code = (
        _text(jurisdiction.get("state_code")) or fallback_state_code
    ).upper()
    county_name = _text(jurisdiction.get("county_name"))
    if geoid.isdigit() and len(geoid) == 5:
        name = county_name or fallback_name
        parent_geoid = geoid[:2]
        jurisdiction_type = "county"
    else:
        name = county_name or fallback_name
        parent_geoid = None
        jurisdiction_type = "state" if geoid.isdigit() and len(geoid) == 2 else "region"
    return _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=name,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        parent_geoid=parent_geoid,
    )


def _upsert_parcel_snapshot(
    db,
    *,
    source_id: str,
    jurisdiction_geoid: str,
    native_parcel_id: str,
    roll_year: str,
    effective_from: str | None,
    source_good_through: str | None,
    observation_id: int,
    record: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_parcel_id, roll_year)
        DO UPDATE SET
            effective_from=excluded.effective_from,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            native_parcel_id,
            roll_year,
            effective_from,
            source_good_through,
            observation_id,
            canonical_json(record),
        ),
    )
    row = db.execute(
        """
        SELECT parcel_id FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, jurisdiction_geoid, native_parcel_id, roll_year),
    ).fetchone()
    return int(row["parcel_id"])


def _upsert_alias(
    db,
    *,
    parcel_id: int,
    alias_type: str,
    alias_value: Any,
    source_id: str,
    effective_from: str,
) -> int:
    value = _text(alias_value)
    if not value:
        return 0
    cursor = db.execute(
        """
        INSERT OR IGNORE INTO parcel_alias(
            parcel_id, alias_type, alias_value, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (parcel_id, alias_type, value, source_id, effective_from),
    )
    return max(cursor.rowcount, 0)


def _upsert_assessment_projection(
    db,
    *,
    parcel_id: int,
    source_id: str,
    tax_year: str,
    land_value: Any = None,
    improvement_value: Any = None,
    total_value: Any = None,
    assessed_value: Any = None,
    assessment_class: Any = None,
    source_good_through: str | None,
    observation_id: int,
    raw: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO assessment(
            parcel_id, source_id, tax_year, land_value_minor,
            improvement_value_minor, total_value_minor, assessed_value_minor,
            currency, assessment_class, source_good_through, observation_id,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, tax_year) DO UPDATE SET
            land_value_minor=excluded.land_value_minor,
            improvement_value_minor=excluded.improvement_value_minor,
            total_value_minor=excluded.total_value_minor,
            assessed_value_minor=excluded.assessed_value_minor,
            assessment_class=excluded.assessment_class,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            source_id,
            tax_year,
            _minor_units(land_value),
            _minor_units(improvement_value),
            _minor_units(total_value),
            _minor_units(assessed_value),
            _text(assessment_class),
            source_good_through,
            observation_id,
            canonical_json(raw),
        ),
    )
    return 1


def _upsert_sale_projection(
    db,
    *,
    parcel_id: int,
    source_id: str,
    native_sale_id: str,
    sale_date: str | None,
    consideration: Any,
    derivation: str,
    observation_id: int,
    raw: Mapping[str, Any],
    instrument_id: int | None = None,
) -> int:
    db.execute(
        """
        INSERT INTO sale_event(
            parcel_id, source_id, native_sale_id, sale_date,
            consideration_minor, currency, derivation, instrument_id,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(
            parcel_id, source_id, native_sale_id, sale_date, derivation
        ) DO UPDATE SET
            consideration_minor=excluded.consideration_minor,
            currency=excluded.currency,
            instrument_id=excluded.instrument_id,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            source_id,
            native_sale_id,
            sale_date,
            _minor_units(consideration),
            derivation,
            instrument_id,
            observation_id,
            canonical_json(raw),
        ),
    )
    return 1


def _upsert_point_geometry(
    db,
    *,
    parcel_id: int,
    source_id: str,
    longitude: Any,
    latitude: Any,
    snapshot_date: str,
) -> int:
    if longitude in (None, "") or latitude in (None, ""):
        return 0
    point = {
        "type": "Point",
        "coordinates": [longitude, latitude],
    }
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, source_id, snapshot_date
        ) VALUES (?, ?, 'geojson_point', 'EPSG:4326', 'source_centroid', ?, ?)
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution
        """,
        (
            parcel_id,
            f"source-observation-sha256:{sha256_fingerprint(point)}",
            source_id,
            snapshot_date,
        ),
    )
    return 1


def _ingest_nc_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    record_source_id = _text(record.get("source_id"))
    if record_source_id and record_source_id != source_id:
        raise PropertyIngestError(
            f"record source_id {record_source_id} does not match envelope {source_id}"
        )
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("NC OneMap record lacks native_parcel_id")
    geoid = _upsert_jurisdiction(db, record)
    if not geoid.startswith("37"):
        raise PropertyIngestError(f"NC OneMap record has non-NC GEOID {geoid}")

    query = _mapping(envelope.get("query"), "query")
    query_fingerprint = _text(query.get("fingerprint"))
    retrieved_at = _text(envelope.get("retrieved_at"))
    if not retrieved_at:
        raise PropertyIngestError("retrieved_at is required")
    status = _text(envelope.get("status")) or "ok"
    warnings = envelope.get("warnings", [])
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise PropertyIngestError("warnings must be a list of strings")
    schema_fingerprint = _text(record.get("schema_fingerprint"))
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_parcel_id,
        record_kind="parcel_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_url(envelope),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=schema_fingerprint,
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )

    roll_year = _roll_year(record)
    effective_from = _text(record.get("source_revised_date")) or ""
    raw_json = canonical_json(record)
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_parcel_id, roll_year)
        DO UPDATE SET
            effective_from=excluded.effective_from,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            geoid,
            native_parcel_id,
            roll_year,
            effective_from or None,
            effective_from or None,
            observation_id,
            raw_json,
        ),
    )
    parcel_row = db.execute(
        """
        SELECT parcel_id FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (source_id, geoid, native_parcel_id, roll_year),
    ).fetchone()
    parcel_id = int(parcel_row["parcel_id"])

    aliases_inserted = 0
    for alias in record.get("alternate_parcel_ids", []):
        alias_text = _text(alias)
        if not alias_text or alias_text == native_parcel_id:
            continue
        cursor = db.execute(
            """
            INSERT OR IGNORE INTO parcel_alias(
                parcel_id, alias_type, alias_value, source_id, effective_from
            ) VALUES (?, 'source_alternate', ?, ?, ?)
            """,
            (parcel_id, alias_text, source_id, effective_from),
        )
        aliases_inserted += max(cursor.rowcount, 0)

    addresses_inserted = 0
    for role, field in (("situs", "situs_address"), ("mailing", "mailing_address")):
        address = record.get(field)
        if isinstance(address, Mapping):
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role=role,
                    address=address,
                    effective_from=effective_from,
                )
            )

    assessment = record.get("assessment")
    assessments_upserted = 0
    if isinstance(assessment, Mapping) and any(
        assessment.get(field) not in (None, "")
        for field in ("land_value", "improvement_value", "parcel_value")
    ):
        db.execute(
            """
            INSERT INTO assessment(
                parcel_id, source_id, tax_year, land_value_minor,
                improvement_value_minor, total_value_minor, currency,
                assessment_class, source_good_through, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, tax_year) DO UPDATE SET
                land_value_minor=excluded.land_value_minor,
                improvement_value_minor=excluded.improvement_value_minor,
                total_value_minor=excluded.total_value_minor,
                currency=excluded.currency,
                assessment_class=excluded.assessment_class,
                source_good_through=excluded.source_good_through,
                observation_id=excluded.observation_id,
                raw_json=excluded.raw_json
            """,
            (
                parcel_id,
                source_id,
                roll_year,
                _minor_units(assessment.get("land_value")),
                _minor_units(assessment.get("improvement_value")),
                _minor_units(assessment.get("parcel_value")),
                _text(assessment.get("currency")) or "USD",
                _text(assessment.get("value_type")),
                effective_from or None,
                observation_id,
                canonical_json(assessment),
            ),
        )
        assessments_upserted = 1

    owners_upserted = 0
    owners = record.get("owners", [])
    if not isinstance(owners, list):
        raise PropertyIngestError("record.owners must be a list")
    for owner in owners:
        owner = _mapping(owner, "record.owners[]")
        raw_name = _text(owner.get("raw_name"))
        if not raw_name:
            continue
        db.execute(
            """
            INSERT INTO ownership_assertion(
                parcel_id, source_id, assertion_type, raw_owner_name,
                normalized_owner_name, effective_from, confidence, claim_type,
                observation_id, evidence_ref, source_quote
            ) VALUES (?, ?, 'assessment_roll', ?, ?, ?, ?, 'direct_quote', ?, ?, ?)
            ON CONFLICT(
                parcel_id, source_id, assertion_type, raw_owner_name, effective_from
            ) DO UPDATE SET
                normalized_owner_name=excluded.normalized_owner_name,
                confidence=excluded.confidence,
                observation_id=excluded.observation_id,
                evidence_ref=excluded.evidence_ref,
                source_quote=excluded.source_quote
            """,
            (
                parcel_id,
                source_id,
                raw_name,
                " ".join(raw_name.upper().split()),
                effective_from,
                _text(owner.get("confidence")) or "high",
                observation_id,
                canonical_property_ref(source_id, geoid, "parcel", native_parcel_id),
                raw_name,
            ),
        )
        owners_upserted += 1

    sales_upserted = 0
    sale = record.get("last_sale")
    if isinstance(sale, Mapping):
        sale_date = _text(sale.get("sale_date"))
        source_document_date = _text(sale.get("source_document_date"))
        native_sale_id = _text(sale.get("source_document_ref"))
        if sale_date or source_document_date or native_sale_id:
            native_sale_id = native_sale_id or (
                f"assessor:{record.get('object_id', native_parcel_id)}:{sale_date or ''}"
            )
            db.execute(
                """
                INSERT INTO sale_event(
                    parcel_id, source_id, native_sale_id, sale_date,
                    recording_date, derivation, observation_id, raw_json
                ) VALUES (?, ?, ?, ?, ?, 'assessment_roll', ?, ?)
                ON CONFLICT(
                    parcel_id, source_id, native_sale_id, sale_date, derivation
                ) DO UPDATE SET
                    recording_date=excluded.recording_date,
                    observation_id=excluded.observation_id,
                    raw_json=excluded.raw_json
                """,
                (
                    parcel_id,
                    source_id,
                    native_sale_id,
                    sale_date,
                    source_document_date,
                    observation_id,
                    canonical_json(sale),
                ),
            )
            sales_upserted = 1

    geometry_upserted = 0
    geometry = record.get("geometry")
    if isinstance(geometry, Mapping):
        geometry_hash = sha256_fingerprint(geometry)
        snapshot_date = effective_from
        db.execute(
            """
            INSERT INTO parcel_geometry(
                parcel_id, geometry_ref, geometry_format, crs,
                accuracy_disclaimer, source_id, snapshot_date
            ) VALUES (?, ?, 'esri_json', 'source_defined', ?, ?, ?)
            ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
                geometry_ref=excluded.geometry_ref,
                geometry_format=excluded.geometry_format,
                crs=excluded.crs,
                accuracy_disclaimer=excluded.accuracy_disclaimer
            """,
            (
                parcel_id,
                f"source-observation-sha256:{geometry_hash}",
                _text(record.get("geometry_disclaimer")),
                source_id,
                snapshot_date,
            ),
        )
        geometry_upserted = 1

    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": owners_upserted,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
    }


def _ingest_cook_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    tax_year = _text(record.get("tax_year"))
    if not native_parcel_id or not tax_year:
        raise PropertyIngestError(
            "Cook County record requires native_parcel_id and tax_year"
        )
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="17031",
        fallback_name="Cook County",
        fallback_state_code="IL",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_native_id = _text(record.get("source_row_id")) or (
        f"{native_parcel_id}:{tax_year}"
    )
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=source_native_id,
        record_kind="parcel_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
        roll_year=tax_year,
        effective_from=None,
        source_good_through=None,
        observation_id=observation_id,
        record=record,
    )
    aliases_inserted = 0
    pin10 = _text(record.get("pin10"))
    if pin10 and pin10 != native_parcel_id:
        aliases_inserted += _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type="pin10",
            alias_value=pin10,
            source_id=source_id,
            effective_from=tax_year,
        )

    assessments_upserted = _upsert_assessment_projection(
        db,
        parcel_id=parcel_id,
        source_id=source_id,
        tax_year=tax_year,
        assessment_class=record.get("property_class"),
        source_good_through=None,
        observation_id=observation_id,
        raw={
            "tax_year": tax_year,
            "property_class": record.get("property_class"),
            "assessor_geography": record.get("assessor_geography"),
        },
    )
    location = record.get("situs_location")
    geometry_upserted = 0
    if isinstance(location, Mapping):
        centroid = location.get("centroid")
        if isinstance(centroid, Mapping):
            geometry_upserted = _upsert_point_geometry(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                longitude=centroid.get("longitude"),
                latitude=centroid.get("latitude"),
                snapshot_date=tax_year,
            )
    owner_observation = record.get("owner_observation")
    owner_state = (
        _text(owner_observation.get("state"))
        if isinstance(owner_observation, Mapping)
        else None
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": 0,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": 0,
        "owner_visibility_state": owner_state,
        "sales_upserted": 0,
        "geometry_upserted": geometry_upserted,
    }


def _maryland_sale_id(sale: Mapping[str, Any]) -> str:
    transfer_number = _text(sale.get("transfer_number"))
    if transfer_number:
        return f"transfer:{transfer_number}"
    deed = sale.get("deed_reference")
    if isinstance(deed, Mapping):
        liber = _text(deed.get("liber"))
        folio = _text(deed.get("folio"))
        if liber or folio:
            return f"deed:{liber or ''}:{folio or ''}"
    segment = _text(sale.get("segment")) or ""
    transfer_date = _text(sale.get("transfer_date")) or ""
    return f"segment:{segment}:{transfer_date}:{sha256_fingerprint(sale)[:16]}"


def _ingest_md_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    native_parcel_id = _text(record.get("native_parcel_id"))
    if not native_parcel_id:
        raise PropertyIngestError("Maryland record lacks native_parcel_id")
    geoid = _upsert_record_jurisdiction(
        db,
        record,
        fallback_geoid="24",
        fallback_name="Maryland",
        fallback_state_code="MD",
    )
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    source_good_through = _text(record.get("source_record_updated"))
    assessment = record.get("assessment")
    tax_year = (
        _text(assessment.get("cycle_year"))
        if isinstance(assessment, Mapping)
        else None
    ) or ""
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=native_parcel_id,
        record_kind="parcel_snapshot",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    parcel_id = _upsert_parcel_snapshot(
        db,
        source_id=source_id,
        jurisdiction_geoid=geoid,
        native_parcel_id=native_parcel_id,
        roll_year=tax_year,
        effective_from=source_good_through,
        source_good_through=source_good_through,
        observation_id=observation_id,
        record=record,
    )

    aliases_inserted = 0
    record_key = record.get("record_key")
    if isinstance(record_key, Mapping):
        account_number = _text(record_key.get("account_number"))
        if account_number and account_number != native_parcel_id:
            aliases_inserted += _upsert_alias(
                db,
                parcel_id=parcel_id,
                alias_type="account_number",
                alias_value=account_number,
                source_id=source_id,
                effective_from=source_good_through or tax_year,
            )

    addresses_inserted = 0
    situs_address = record.get("situs_address")
    if isinstance(situs_address, Mapping):
        addresses_inserted = int(
            _upsert_address(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                role="situs",
                address=situs_address,
                effective_from=source_good_through or tax_year,
            )
        )

    assessments_upserted = 0
    if isinstance(assessment, Mapping) and any(
        assessment.get(field) not in (None, "")
        for field in (
            "cycle_year",
            "current_land_value",
            "current_improvement_value",
            "current_total_assessment",
        )
    ):
        assessments_upserted = _upsert_assessment_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            tax_year=tax_year,
            land_value=assessment.get("current_land_value"),
            improvement_value=assessment.get("current_improvement_value"),
            total_value=assessment.get("current_total_assessment"),
            assessed_value=assessment.get("current_total_assessment"),
            source_good_through=source_good_through,
            observation_id=observation_id,
            raw=assessment,
        )

    sales = record.get("sales_history", [])
    if not isinstance(sales, list):
        raise PropertyIngestError("record.sales_history must be a list")
    sales_upserted = 0
    for index, sale_value in enumerate(sales):
        sale = _mapping(sale_value, f"record.sales_history[{index}]")
        sales_upserted += _upsert_sale_projection(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            native_sale_id=_maryland_sale_id(sale),
            sale_date=_text(sale.get("transfer_date")),
            consideration=sale.get("consideration"),
            derivation="assessment_sales_history",
            observation_id=observation_id,
            raw=sale,
        )

    location = record.get("location")
    geometry_upserted = 0
    if isinstance(location, Mapping):
        geometry_upserted = _upsert_point_geometry(
            db,
            parcel_id=parcel_id,
            source_id=source_id,
            longitude=location.get("longitude"),
            latitude=location.get("latitude"),
            snapshot_date=source_good_through or tax_year,
        )

    owner_visibility = record.get("owner_visibility")
    owner_state = (
        _text(owner_visibility.get("state"))
        if isinstance(owner_visibility, Mapping)
        else None
    )
    return {
        "parcel_id": parcel_id,
        "canonical_ref": canonical_property_ref(
            source_id, geoid, "parcel", native_parcel_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "aliases_inserted": aliases_inserted,
        "addresses_inserted": addresses_inserted,
        "assessments_upserted": assessments_upserted,
        "owners_upserted": 0,
        "owner_visibility_state": owner_state,
        "sales_upserted": sales_upserted,
        "geometry_upserted": geometry_upserted,
    }


def _date_prefix(value: Any) -> str | None:
    text = _text(value)
    return text[:10] if text else None


def _acris_query_jurisdiction(
    db,
    envelope: Mapping[str, Any],
) -> str:
    query = _mapping(envelope.get("query"), "query")
    jurisdiction = query.get("jurisdiction")
    if not isinstance(jurisdiction, Mapping):
        jurisdiction = {}
    geoid = _text(jurisdiction.get("jurisdiction_id")) or "nyc-acris"
    name = _text(jurisdiction.get("name")) or "New York City ACRIS coverage"
    state_code = _text(jurisdiction.get("state_code")) or "NY"
    parent_geoid = geoid[:2] if geoid.isdigit() and len(geoid) == 5 else None
    jurisdiction_type = "county" if parent_geoid else "region"
    return _upsert_jurisdiction_values(
        db,
        geoid=geoid,
        name=name,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        parent_geoid=parent_geoid,
    )


def _acris_party_address(party: Mapping[str, Any]) -> str | None:
    pieces = [
        _text(party.get(field))
        for field in (
            "address_1",
            "address_2",
            "city",
            "state",
            "zip",
            "country",
        )
    ]
    return ", ".join(piece for piece in pieces if piece) or None


def _acris_legal_parcel_id(legal: Mapping[str, Any]) -> str | None:
    borough = _text(legal.get("borough"))
    block = _text(legal.get("block"))
    lot = _text(legal.get("lot"))
    if not (borough and block and lot):
        return None
    return f"{borough}-{block}-{lot}"


def _ingest_acris_record(
    db,
    *,
    envelope: Mapping[str, Any],
    record: Mapping[str, Any],
    source_id: str,
    raw_artifact_path: str | None,
    raw_artifact_sha256: str | None,
) -> dict[str, Any]:
    _assert_record_source(record, source_id)
    document_id = _text(record.get("document_id"))
    if not document_id:
        raise PropertyIngestError("ACRIS record lacks document_id")
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    jurisdiction_geoid = _acris_query_jurisdiction(db, envelope)
    observation_id, record_hash = _insert_observation(
        db,
        source_id=source_id,
        source_native_id=document_id,
        record_kind="recorded_instrument",
        query_fingerprint=query_fingerprint,
        source_url=_record_source_url(envelope, record),
        retrieved_at=retrieved_at,
        access_status=status,
        schema_fingerprint=_record_schema_fingerprint(record),
        raw=record,
        raw_artifact_path=raw_artifact_path,
        raw_artifact_sha256=raw_artifact_sha256,
        warnings=warnings,
    )
    master_value = record.get("master")
    master = dict(master_value) if isinstance(master_value, Mapping) else {}
    legals_value = record.get("legals", [])
    if not isinstance(legals_value, list):
        raise PropertyIngestError("record.legals must be a list")
    legals = [
        _mapping(value, f"record.legals[{index}]")
        for index, value in enumerate(legals_value)
    ]
    legal_description = canonical_json(legals) if legals else None
    consideration = master.get("document_amt")
    db.execute(
        """
        INSERT INTO recorded_instrument(
            source_id, jurisdiction_geoid, native_document_id,
            instrument_type, book, page, execution_date, recording_date,
            consideration_minor, currency, legal_description_raw, source_url,
            observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(source_id, jurisdiction_geoid, native_document_id)
        DO UPDATE SET
            instrument_type=excluded.instrument_type,
            book=excluded.book,
            page=excluded.page,
            execution_date=excluded.execution_date,
            recording_date=excluded.recording_date,
            consideration_minor=excluded.consideration_minor,
            legal_description_raw=excluded.legal_description_raw,
            source_url=excluded.source_url,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            source_id,
            jurisdiction_geoid,
            document_id,
            _text(record.get("document_type") or master.get("doc_type")),
            _text(master.get("reel_nbr")),
            _text(master.get("reel_pg")),
            _date_prefix(master.get("document_date")),
            _date_prefix(master.get("recorded_datetime")),
            _minor_units(consideration),
            legal_description,
            _record_source_url(envelope, record),
            observation_id,
            canonical_json(record),
        ),
    )
    instrument_row = db.execute(
        """
        SELECT instrument_id FROM recorded_instrument
        WHERE source_id=? AND jurisdiction_geoid=? AND native_document_id=?
        """,
        (source_id, jurisdiction_geoid, document_id),
    ).fetchone()
    instrument_id = int(instrument_row["instrument_id"])

    parties_value = record.get("parties", [])
    if not isinstance(parties_value, list):
        raise PropertyIngestError("record.parties must be a list")
    parties_upserted = 0
    for index, party_value in enumerate(parties_value, start=1):
        party = _mapping(party_value, f"record.parties[{index - 1}]")
        raw_name = _text(party.get("name"))
        if not raw_name:
            continue
        party_type = _text(party.get("party_type"))
        role = ACRIS_PARTY_ROLES.get(
            party_type or "",
            f"party_type_{party_type}" if party_type else "other",
        )
        db.execute(
            """
            INSERT INTO instrument_party(
                instrument_id, sequence_no, role, raw_name, normalized_name,
                entity_kind, raw_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instrument_id, sequence_no, role, raw_name)
            DO UPDATE SET
                normalized_name=excluded.normalized_name,
                entity_kind=excluded.entity_kind,
                raw_address=excluded.raw_address
            """,
            (
                instrument_id,
                index,
                role,
                raw_name,
                " ".join(raw_name.upper().split()),
                _text(party.get("party_type_desc")),
                _acris_party_address(party),
            ),
        )
        parties_upserted += 1

    parcels_upserted = 0
    addresses_inserted = 0
    sales_upserted = 0
    parcel_ids: set[int] = set()
    effective_from = (
        _date_prefix(master.get("recorded_datetime"))
        or _date_prefix(master.get("document_date"))
        or ""
    )
    for legal in legals:
        native_parcel_id = _acris_legal_parcel_id(legal)
        if not native_parcel_id:
            continue
        borough = _text(legal.get("borough")) or ""
        legal_geoid, legal_name = ACRIS_BOROUGH_METADATA.get(
            borough,
            (jurisdiction_geoid, "New York City ACRIS coverage"),
        )
        _upsert_jurisdiction_values(
            db,
            geoid=legal_geoid,
            name=legal_name,
            state_code="NY",
            jurisdiction_type="county" if legal_geoid.isdigit() else "region",
            parent_geoid=(
                legal_geoid[:2]
                if legal_geoid.isdigit() and len(legal_geoid) == 5
                else None
            ),
        )
        parcel_id = _upsert_parcel_snapshot(
            db,
            source_id=source_id,
            jurisdiction_geoid=legal_geoid,
            native_parcel_id=native_parcel_id,
            roll_year="",
            effective_from=effective_from or None,
            source_good_through=None,
            observation_id=observation_id,
            record=legal,
        )
        parcel_ids.add(parcel_id)
        db.execute(
            """
            INSERT INTO instrument_parcel(
                instrument_id, parcel_id, link_method, link_confidence,
                legal_description_raw
            ) VALUES (?, ?, 'source_index_bbl', 1.0, ?)
            ON CONFLICT(instrument_id, parcel_id) DO UPDATE SET
                link_method=excluded.link_method,
                link_confidence=excluded.link_confidence,
                legal_description_raw=excluded.legal_description_raw
            """,
            (instrument_id, parcel_id, canonical_json(legal)),
        )
        street = " ".join(
            value
            for value in (
                _text(legal.get("street_number")),
                _text(legal.get("street_name")),
            )
            if value
        )
        if street:
            addresses_inserted += int(
                _upsert_address(
                    db,
                    parcel_id=parcel_id,
                    source_id=source_id,
                    role="situs",
                    address={
                        "raw": street,
                        "unit": legal.get("unit"),
                        "city": "New York",
                        "state": "NY",
                        "postal_code": None,
                    },
                    effective_from=effective_from,
                )
            )
        parcels_upserted += 1

    instrument_type = _text(record.get("document_type") or master.get("doc_type"))
    if instrument_type in {"DEED", "DEEDO"}:
        for parcel_id in parcel_ids:
            sales_upserted += _upsert_sale_projection(
                db,
                parcel_id=parcel_id,
                source_id=source_id,
                native_sale_id=document_id,
                sale_date=_date_prefix(master.get("document_date")),
                consideration=consideration,
                derivation="recorded_instrument",
                instrument_id=instrument_id,
                observation_id=observation_id,
                raw=master or record,
            )

    return {
        "instrument_id": instrument_id,
        "canonical_ref": canonical_property_ref(
            source_id, jurisdiction_geoid, "instrument", document_id
        ),
        "observation_id": observation_id,
        "record_sha256": record_hash,
        "parties_upserted": parties_upserted,
        "parcels_upserted": parcels_upserted,
        "addresses_inserted": addresses_inserted,
        "sales_upserted": sales_upserted,
    }


PROPERTY_RECORD_MAPPERS = {
    NC_ONEMAP_SOURCE_ID: _ingest_nc_record,
    COOK_PROPERTY_SOURCE_ID: _ingest_cook_record,
    MD_PROPERTY_SOURCE_ID: _ingest_md_record,
    ACRIS_SOURCE_ID: _ingest_acris_record,
}


def _artifact_details(
    raw_artifact_path: Path | str | None,
) -> tuple[str | None, str | None]:
    artifact_path = str(Path(raw_artifact_path).resolve()) if raw_artifact_path else None
    if not artifact_path:
        return None, None
    digest = hashlib.sha256()
    with Path(artifact_path).open("rb") as artifact:
        while chunk := artifact.read(1024 * 1024):
            digest.update(chunk)
    return artifact_path, digest.hexdigest()


def ingest_property_envelope(
    envelope: Mapping[str, Any],
    *,
    db_path: Path | str = DEFAULT_PROPERTY_DB,
    raw_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Preserve a canonical property envelope and project known record schemas."""
    envelope = _mapping(envelope, "envelope")
    source_id = _source_id(envelope)
    record_mapper = PROPERTY_RECORD_MAPPERS.get(source_id)
    query_fingerprint, retrieved_at, status, warnings = _observation_context(envelope)
    records_value = envelope.get("records")
    if not isinstance(records_value, list):
        raise PropertyIngestError("records must be a list")
    records = [
        _mapping(record, f"records[{index}]")
        for index, record in enumerate(records_value)
    ]
    if status == "no_results" and records:
        raise PropertyIngestError("no_results envelope cannot contain records")

    artifact_path, artifact_sha256 = _artifact_details(raw_artifact_path)
    envelope_hash = sha256_fingerprint(envelope)

    db = connect_property(db_path)
    try:
        with db:
            envelope_observation_id, _ = _insert_observation(
                db,
                source_id=source_id,
                source_native_id=None,
                record_kind="query_envelope",
                query_fingerprint=query_fingerprint,
                source_url=_record_url(envelope),
                retrieved_at=retrieved_at,
                access_status=status,
                schema_fingerprint=None,
                raw=envelope,
                raw_artifact_path=artifact_path,
                raw_artifact_sha256=artifact_sha256,
                warnings=warnings,
            )
            ingested = []
            if status in INGESTABLE_STATUSES and record_mapper is not None:
                ingested = [
                    record_mapper(
                        db,
                        envelope=envelope,
                        record=record,
                        source_id=source_id,
                        raw_artifact_path=artifact_path,
                        raw_artifact_sha256=artifact_sha256,
                    )
                    for record in records
                ]
    finally:
        db.close()

    return {
        "schema_version": "public-records-ingest/1.0",
        "status": "ok",
        "source_id": source_id,
        "source_status": status,
        "query_fingerprint": query_fingerprint,
        "envelope_sha256": envelope_hash,
        "raw_artifact_sha256": artifact_sha256 or envelope_hash,
        "envelope_observation_id": envelope_observation_id,
        "records_seen": len(records),
        "records_ingested": len(ingested),
        "records_preserved_without_projection": len(records) - len(ingested),
        "projection_supported": record_mapper is not None,
        "property_db": str(Path(db_path)),
        "records": ingested,
    }


def ingest_nc_envelope(
    envelope: Mapping[str, Any],
    *,
    db_path: Path | str = DEFAULT_PROPERTY_DB,
    raw_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Ingest one canonical NC OneMap result envelope transactionally."""
    envelope = _mapping(envelope, "envelope")
    source_id = _source_id(envelope)
    if source_id != NC_ONEMAP_SOURCE_ID:
        raise PropertyIngestError(
            f"nc-onemap ingestion requires source {NC_ONEMAP_SOURCE_ID}, got {source_id}"
        )
    status = _text(envelope.get("status"))
    if status not in INGESTABLE_STATUSES:
        raise PropertyIngestError(f"unsupported ingestion source status {status!r}")
    return ingest_property_envelope(
        envelope,
        db_path=db_path,
        raw_artifact_path=raw_artifact_path,
    )


def _read_json(path: str) -> tuple[dict[str, Any], str | None]:
    if path == "-":
        data = json.load(sys.stdin)
        return _mapping(data, "input"), None
    input_path = Path(path)
    with input_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return _mapping(data, "input"), str(input_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize property query envelopes"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    generic = sub.add_parser(
        "ingest",
        help="Dispatch a supported canonical property result envelope",
    )
    generic.add_argument(
        "--input",
        required=True,
        help="Envelope JSON path, or - for stdin",
    )
    generic.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    add_output_args(generic)
    nc = sub.add_parser("nc-onemap", help="Ingest an NC OneMap result envelope")
    nc.add_argument("--input", required=True, help="Envelope JSON path, or - for stdin")
    nc.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    add_output_args(nc)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    envelope, artifact_path = _read_json(args.input)
    if args.command == "nc-onemap":
        result = ingest_nc_envelope(
            envelope,
            db_path=args.property_db,
            raw_artifact_path=artifact_path,
        )
    else:
        result = ingest_property_envelope(
            envelope,
            db_path=args.property_db,
            raw_artifact_path=artifact_path,
        )
    if write_output(
        result,
        args,
        summary=f"normalized {result['source_id']} property records",
    ):
        return
    print(json.dumps(result, indent=2 if args.json_out else None, sort_keys=True))


if __name__ == "__main__":
    main()
