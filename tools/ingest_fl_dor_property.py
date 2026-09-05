#!/usr/bin/env python3
"""Stream Florida DOR NAL, SDF, and GIS-PIN archives into the property sidecar.

The release query adapter deliberately stops at artifact receipts. This tool
is the explicit byte-parsing step: it validates one downloaded archive,
preserves release and row provenance, and projects only the fields represented
by that source file.

Usage:
    uv run python tools/ingest_fl_dor_property.py ingest \
      --type nal --archive /tmp/baker-nal.zip \
      --property-db /tmp/property.db --output /tmp/nal-ingest.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import re
import struct
import sys
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Mapping, Sequence

try:
    from tools.fl_dor_property_common import (
        COUNTY_BY_DOR_NUMBER,
        resolve_county,
    )
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.public_records_shapefile import (
        ParcelShapefileError,
        ShapefileDatasetInspection,
        inspect_shapefile_dataset,
        iter_shapefile_features,
    )
    from tools.public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from tools.query_fl_dor_property import (
        NAL_REQUIRED_PUBLIC_COLUMNS as NAL_REQUIRED_COLUMNS,
        SDF_REQUIRED_PUBLIC_COLUMNS as SDF_REQUIRED_COLUMNS,
        SOURCE_ID,
        SOURCE_OMISSIONS,
    )
except ImportError:
    from fl_dor_property_common import COUNTY_BY_DOR_NUMBER, resolve_county
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, sha256_fingerprint
    from public_records_shapefile import (
        ParcelShapefileError,
        ShapefileDatasetInspection,
        inspect_shapefile_dataset,
        iter_shapefile_features,
    )
    from public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from query_fl_dor_property import (
        NAL_REQUIRED_PUBLIC_COLUMNS as NAL_REQUIRED_COLUMNS,
        SDF_REQUIRED_PUBLIC_COLUMNS as SDF_REQUIRED_COLUMNS,
        SOURCE_ID,
        SOURCE_OMISSIONS,
    )


CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024
CSV_MEMBER_RE = re.compile(
    r"^(?P<dataset>NAL|SDF)(?P<county>\d{2})(?P<stage>[PF])"
    r"(?P<year>\d{4})(?P<sequence>\d{2})\.csv$",
    re.IGNORECASE,
)
GIS_DBF_RE = re.compile(
    r"^(?P<county>[a-z0-9_-]+)_(?P<year>\d{4})pin\.dbf$",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

class FloridaDORIngestError(ValueError):
    """A downloaded Florida DOR artifact does not match its declared schema."""


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _minor_units(value: Any) -> int | None:
    normalized = _text(value)
    if normalized is None:
        return None
    normalized = normalized.replace(",", "").replace("$", "")
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError) as error:
        raise FloridaDORIngestError(
            f"invalid Florida DOR monetary value: {value!r}"
        ) from error
    if not amount.is_finite():
        raise FloridaDORIngestError(
            f"non-finite Florida DOR monetary value: {value!r}"
        )
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _artifact_timestamp(path: Path, supplied: str | None) -> str:
    if supplied:
        return supplied
    return datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()


def _zip_members(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    return [
        {
            "name": member.filename,
            "size": member.file_size,
            "compressed_size": member.compress_size,
            "crc32": f"{member.CRC:08x}",
        }
        for member in archive.infolist()
        if not member.is_dir()
    ]


def _header(
    reader: csv.DictReader,
    *,
    required: frozenset[str],
    dataset_type: str,
) -> list[str]:
    fields = [str(value).strip() for value in (reader.fieldnames or [])]
    if not fields or any(not value for value in fields):
        raise FloridaDORIngestError(
            f"{dataset_type.upper()} CSV header is empty or has blank columns"
        )
    duplicates = sorted(
        {field for field in fields if fields.count(field) > 1}
    )
    if duplicates:
        raise FloridaDORIngestError(
            f"{dataset_type.upper()} CSV header has duplicate columns: "
            + ", ".join(duplicates)
        )
    missing = sorted(required - set(fields))
    if missing:
        raise FloridaDORIngestError(
            f"{dataset_type.upper()} CSV header lacks required columns: "
            + ", ".join(missing)
        )
    return fields


def _csv_identity(
    archive: zipfile.ZipFile,
    *,
    dataset_type: str,
) -> tuple[zipfile.ZipInfo, re.Match[str]]:
    members = [
        member
        for member in archive.infolist()
        if not member.is_dir() and member.filename.casefold().endswith(".csv")
    ]
    if len(members) != 1:
        raise FloridaDORIngestError(
            f"{dataset_type.upper()} archive must contain exactly one CSV member"
        )
    member = members[0]
    name = Path(member.filename).name
    match = CSV_MEMBER_RE.fullmatch(name)
    if match is None or match.group("dataset").casefold() != dataset_type:
        raise FloridaDORIngestError(
            f"CSV member {member.filename!r} does not identify a "
            f"{dataset_type.upper()} release"
        )
    return member, match


def _release_identity(
    *,
    dataset_type: str,
    county_number: int,
    assessment_year: int,
    stage: str,
    artifact_sha256: str,
    archive_name: str,
    release_fingerprint: str | None,
) -> dict[str, Any]:
    artifact_role = dataset_type
    release_id = (
        f"{dataset_type}:{assessment_year}{stage}:"
        f"{county_number:02d}:{artifact_role}"
    )
    identity = {
        "release_id": release_id,
        "dataset_type": dataset_type,
        "county_dor_number": county_number,
        "assessment_year": assessment_year,
        "submission_code": stage,
        "submission_stage": "preliminary" if stage == "P" else "final",
        "artifact_role": artifact_role,
        "archive_filename": archive_name,
        "artifact_sha256": artifact_sha256,
        "release_fingerprint": release_fingerprint,
    }
    identity["release_identity_sha256"] = sha256_fingerprint(identity)
    return identity


def _validate_requested_identity(
    args: argparse.Namespace,
    *,
    county_number: int,
    assessment_year: int,
    stage: str,
    release_id: str,
) -> tuple[str, str]:
    county_name, geoid = COUNTY_BY_DOR_NUMBER[county_number]
    if args.county:
        requested_number, _requested_name, _requested_geoid = resolve_county(
            args.county
        )
        if requested_number != county_number:
            raise FloridaDORIngestError(
                "archive county identity conflicts with --county"
            )
    if args.tax_year is not None and args.tax_year != assessment_year:
        raise FloridaDORIngestError(
            "archive assessment year conflicts with --tax-year"
        )
    if args.submission_stage:
        requested_stage = args.submission_stage[0].upper()
        if requested_stage != stage:
            raise FloridaDORIngestError(
                "archive submission stage conflicts with --submission-stage"
            )
    if args.release_id and args.release_id != release_id:
        raise FloridaDORIngestError(
            "derived archive release identity conflicts with --release-id"
        )
    return county_name, geoid


def _upsert_jurisdiction(
    db,
    *,
    geoid: str,
    county_name: str,
) -> None:
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES ('12', 'Florida', 'state', NULL, 'FL', NULL)
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
        ) VALUES (?, ?, 'county', '12', 'FL', ?)
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """,
        (geoid, f"{county_name} County", geoid[-3:]),
    )


def _upsert_observation(
    db,
    *,
    source_native_id: str,
    record_kind: str,
    source_url: str | None,
    retrieved_at: str,
    schema_fingerprint: str,
    artifact_path: str,
    artifact_sha256: str,
    raw: Mapping[str, Any],
) -> tuple[int, bool]:
    raw_json = canonical_json(raw)
    row = db.execute(
        """
        SELECT observation_id
        FROM source_observation
        WHERE source_id=? AND source_native_id=? AND record_kind=?
          AND raw_artifact_sha256=? AND schema_fingerprint=?
          AND raw_json=?
        ORDER BY observation_id
        LIMIT 1
        """,
        (
            SOURCE_ID,
            source_native_id,
            record_kind,
            artifact_sha256,
            schema_fingerprint,
            raw_json,
        ),
    ).fetchone()
    if row is not None:
        observation_id = int(row["observation_id"])
        db.execute(
            """
            UPDATE source_observation
            SET source_url=?, retrieved_at=?, raw_artifact_path=?
            WHERE observation_id=?
            """,
            (source_url, retrieved_at, artifact_path, observation_id),
        )
        return observation_id, False
    cursor = db.execute(
        """
        INSERT INTO source_observation(
            source_id, source_native_id, record_kind, query_fingerprint,
            source_url, retrieved_at, access_status, schema_fingerprint,
            raw_artifact_sha256, raw_artifact_path, raw_json, warning_json
        ) VALUES (?, ?, ?, NULL, ?, ?, 'ok', ?, ?, ?, ?, '[]')
        """,
        (
            SOURCE_ID,
            source_native_id,
            record_kind,
            source_url,
            retrieved_at,
            schema_fingerprint,
            artifact_sha256,
            artifact_path,
            raw_json,
        ),
    )
    return int(cursor.lastrowid), True


def _upsert_parcel(
    db,
    *,
    geoid: str,
    parcel_id: str,
    assessment_year: str,
    observation_id: int,
    raw: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year
        ) DO UPDATE SET
            effective_from=excluded.effective_from,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            SOURCE_ID,
            geoid,
            parcel_id,
            assessment_year,
            assessment_year,
            assessment_year,
            observation_id,
            canonical_json(raw),
        ),
    )
    row = db.execute(
        """
        SELECT parcel_id FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (SOURCE_ID, geoid, parcel_id, assessment_year),
    ).fetchone()
    assert row is not None
    return int(row["parcel_id"])


def _upsert_alias(
    db,
    *,
    parcel_id: int,
    alias_type: str,
    alias_value: Any,
    effective_from: str,
) -> int:
    value = _text(alias_value)
    if not value:
        return 0
    cursor = db.execute(
        """
        INSERT INTO parcel_alias(
            parcel_id, alias_type, alias_value, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        (parcel_id, alias_type, value, SOURCE_ID, effective_from),
    )
    return max(cursor.rowcount, 0)


def _address_values(
    *,
    first: Any,
    second: Any,
    city: Any,
    state: Any,
    postal_code: Any,
    default_state: str | None = None,
) -> dict[str, str | None] | None:
    lines = [value for value in (_text(first), _text(second)) if value]
    raw = " ".join(lines)
    if not raw:
        return None
    state_value = _text(state) or default_state
    return {
        "raw": raw,
        "normalized": " ".join(raw.upper().split()),
        "city": _text(city),
        "state": state_value,
        "postal_code": _text(postal_code),
        "country": "US",
    }


def _upsert_address(
    db,
    *,
    parcel_id: int,
    role: str,
    address: Mapping[str, Any] | None,
    effective_from: str,
) -> int:
    if address is None:
        return 0
    identity = (
        _text(address.get("normalized")),
        _text(address.get("city")),
        _text(address.get("state")),
        _text(address.get("postal_code")),
        _text(address.get("country")) or "US",
    )
    row = db.execute(
        """
        SELECT address_id FROM parcel_address
        WHERE parcel_id=? AND address_role=? AND source_id=?
          AND effective_from=? AND effective_to IS NULL
          AND COALESCE(normalized_address, '')=COALESCE(?, '')
          AND COALESCE(city, '')=COALESCE(?, '')
          AND COALESCE(state, '')=COALESCE(?, '')
          AND COALESCE(postal_code, '')=COALESCE(?, '')
          AND COALESCE(country, 'US')=COALESCE(?, 'US')
        LIMIT 1
        """,
        (
            parcel_id,
            role,
            SOURCE_ID,
            effective_from,
            *identity,
        ),
    ).fetchone()
    if row is not None:
        return 0
    db.execute(
        """
        INSERT INTO parcel_address(
            parcel_id, address_role, raw_address, normalized_address,
            city, state, postal_code, country, source_id, effective_from
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parcel_id,
            role,
            address["raw"],
            identity[0],
            identity[1],
            identity[2],
            identity[3],
            identity[4],
            SOURCE_ID,
            effective_from,
        ),
    )
    return 1


def _upsert_owner(
    db,
    *,
    parcel_id: int,
    raw_name: Any,
    effective_from: str,
    observation_id: int,
    evidence_ref: str,
) -> int:
    owner = _text(raw_name)
    if not owner:
        return 0
    normalized = " ".join(owner.upper().split())
    db.execute(
        """
        INSERT INTO ownership_assertion(
            parcel_id, source_id, assertion_type, raw_owner_name,
            normalized_owner_name, effective_from, confidence, claim_type,
            observation_id, evidence_ref, source_quote
        ) VALUES (
            ?, ?, 'assessment_roll', ?, ?, ?, 'high', 'direct_quote',
            ?, ?, ?
        )
        ON CONFLICT(
            parcel_id, source_id, assertion_type, raw_owner_name, effective_from
        ) DO UPDATE SET
            normalized_owner_name=excluded.normalized_owner_name,
            effective_to=NULL,
            confidence=excluded.confidence,
            observation_id=excluded.observation_id,
            evidence_ref=excluded.evidence_ref,
            source_quote=excluded.source_quote
        """,
        (
            parcel_id,
            SOURCE_ID,
            owner,
            normalized,
            effective_from,
            observation_id,
            evidence_ref,
            owner,
        ),
    )
    return 1


def _upsert_assessment(
    db,
    *,
    parcel_id: int,
    row: Mapping[str, Any],
    tax_year: str,
    observation_id: int,
    normalized: Mapping[str, Any],
) -> int:
    db.execute(
        """
        INSERT INTO assessment(
            parcel_id, source_id, tax_year, land_value_minor,
            market_value_minor, currency, assessment_class,
            source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, tax_year) DO UPDATE SET
            land_value_minor=excluded.land_value_minor,
            market_value_minor=excluded.market_value_minor,
            assessment_class=excluded.assessment_class,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            SOURCE_ID,
            tax_year,
            _minor_units(row.get("LND_VAL")),
            _minor_units(row.get("JV")),
            _text(row.get("DOR_UC")),
            tax_year,
            observation_id,
            canonical_json(normalized),
        ),
    )
    return 1


def _aliases(
    db,
    *,
    parcel_id: int,
    row: Mapping[str, Any],
    effective_from: str,
) -> int:
    return sum(
        _upsert_alias(
            db,
            parcel_id=parcel_id,
            alias_type=alias_type,
            alias_value=row.get(field),
            effective_from=effective_from,
        )
        for alias_type, field in (
            ("alternate_key", "ALT_KEY"),
            ("state_parcel_id", "STATE_PAR_ID"),
            ("state_parcel_id", "STATE_PARCEL_ID"),
            ("real_property_system_id", "RS_ID"),
            ("map_property_id", "MP_ID"),
        )
    )


def _validate_csv_row(
    row: Mapping[str | None, Any],
    *,
    row_number: int,
    member_county: int,
    assessment_year: int,
) -> dict[str, str | None]:
    if None in row:
        raise FloridaDORIngestError(
            f"CSV row {row_number} has more fields than its header"
        )
    raw_fields = {str(key): value for key, value in row.items()}
    county_value = _text(raw_fields.get("CO_NO"))
    year_value = _text(raw_fields.get("ASMNT_YR"))
    parcel_id = _text(raw_fields.get("PARCEL_ID"))
    if not county_value or not county_value.isdigit():
        raise FloridaDORIngestError(
            f"CSV row {row_number} lacks a numeric CO_NO"
        )
    if int(county_value) != member_county:
        raise FloridaDORIngestError(
            f"CSV row {row_number} county conflicts with archive member"
        )
    if year_value != str(assessment_year):
        raise FloridaDORIngestError(
            f"CSV row {row_number} assessment year conflicts with archive member"
        )
    if not parcel_id:
        raise FloridaDORIngestError(
            f"CSV row {row_number} lacks PARCEL_ID"
        )
    return raw_fields


def _nal_projection(
    db,
    *,
    row: Mapping[str, Any],
    row_number: int,
    geoid: str,
    county_number: int,
    county_name: str,
    assessment_year: int,
    release: Mapping[str, Any],
    schema_fingerprint: str,
    artifact_path: str,
    artifact_sha256: str,
    source_url: str | None,
    retrieved_at: str,
) -> dict[str, int]:
    tax_year = str(assessment_year)
    parcel_native_id = _text(row["PARCEL_ID"])
    assert parcel_native_id is not None
    owner_state = _text(row.get("OWN_STATE"))
    normalized = {
        "record_kind": "florida_dor_nal_row",
        "dataset_type": "nal",
        "release": dict(release),
        "jurisdiction": {
            "county_dor_number": county_number,
            "county_name": county_name,
            "county_geoid": geoid,
        },
        "native_parcel_id": parcel_native_id,
        "assessment_year": assessment_year,
        "land_use": {
            "dor_use_code": _text(row.get("DOR_UC")),
            "property_appraiser_use_code": _text(row.get("PA_UC")),
        },
        "building": {
            "effective_year_built": _text(row.get("EFF_YR_BLT")),
            "actual_year_built": _text(row.get("ACT_YR_BLT")),
        },
        "legal_description": _text(row.get("S_LEGAL")),
        "values": {
            "just_value": _text(row.get("JV")),
            "land_value": _text(row.get("LND_VAL")),
            "currency": "USD",
        },
        "source_omission_state": {
            **SOURCE_OMISSIONS,
            "owner_field_state": (
                "published_name"
                if _text(row.get("OWN_NAME"))
                else "blank_or_publisher_omitted"
            ),
        },
        "source_row_number": row_number,
        "raw_fields": dict(row),
    }
    source_native_id = (
        f"nal:{assessment_year}:{geoid}:{parcel_native_id}:"
        f"{_text(row.get('SEQ_NO')) or row_number}"
    )
    observation_id, observation_inserted = _upsert_observation(
        db,
        source_native_id=source_native_id,
        record_kind="florida_dor_nal_row",
        source_url=source_url,
        retrieved_at=retrieved_at,
        schema_fingerprint=schema_fingerprint,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        raw=normalized,
    )
    parcel_id = _upsert_parcel(
        db,
        geoid=geoid,
        parcel_id=parcel_native_id,
        assessment_year=tax_year,
        observation_id=observation_id,
        raw=normalized,
    )
    evidence_ref = canonical_property_ref(
        SOURCE_ID,
        geoid,
        "assessment-roll",
        f"{tax_year}:{parcel_native_id}",
    )
    owner_address = _address_values(
        first=row.get("OWN_ADDR1"),
        second=row.get("OWN_ADDR2"),
        city=row.get("OWN_CITY"),
        state=owner_state,
        postal_code=row.get("OWN_ZIPCD"),
    )
    situs_address = _address_values(
        first=row.get("PHY_ADDR1"),
        second=row.get("PHY_ADDR2"),
        city=row.get("PHY_CITY"),
        state=None,
        postal_code=row.get("PHY_ZIPCD"),
        default_state="FL",
    )
    return {
        "observations_inserted": int(observation_inserted),
        "parcels_upserted": 1,
        "aliases_inserted": _aliases(
            db,
            parcel_id=parcel_id,
            row=row,
            effective_from=tax_year,
        ),
        "owners_upserted": _upsert_owner(
            db,
            parcel_id=parcel_id,
            raw_name=row.get("OWN_NAME"),
            effective_from=tax_year,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        ),
        "addresses_inserted": (
            _upsert_address(
                db,
                parcel_id=parcel_id,
                role="mailing",
                address=owner_address,
                effective_from=tax_year,
            )
            + _upsert_address(
                db,
                parcel_id=parcel_id,
                role="situs",
                address=situs_address,
                effective_from=tax_year,
            )
        ),
        "assessments_upserted": _upsert_assessment(
            db,
            parcel_id=parcel_id,
            row=row,
            tax_year=tax_year,
            observation_id=observation_id,
            normalized=normalized,
        ),
    }


def _sale_date(row: Mapping[str, Any]) -> tuple[str | None, str | None]:
    year = _text(row.get("SALE_YR"))
    month = _text(row.get("SALE_MO"))
    if not year:
        return None, None
    if month and month.isdigit() and 1 <= int(month) <= 12:
        return f"{year}-{int(month):02d}", "month"
    return year, "year"


def _sdf_projection(
    db,
    *,
    row: Mapping[str, Any],
    row_number: int,
    geoid: str,
    county_number: int,
    county_name: str,
    assessment_year: int,
    release: Mapping[str, Any],
    schema_fingerprint: str,
    artifact_path: str,
    artifact_sha256: str,
    source_url: str | None,
    retrieved_at: str,
) -> dict[str, int]:
    tax_year = str(assessment_year)
    parcel_native_id = _text(row["PARCEL_ID"])
    assert parcel_native_id is not None
    sale_date, date_precision = _sale_date(row)
    instrument_reference = {
        "official_record_book": _text(row.get("OR_BOOK")),
        "official_record_page": _text(row.get("OR_PAGE")),
        "clerk_instrument_number": _text(row.get("CLERK_NO")),
        "representation": "assessment_sales_file_reference",
        "recorded_title_evidence": False,
    }
    normalized = {
        "record_kind": "florida_dor_sdf_sale_row",
        "dataset_type": "sdf",
        "release": dict(release),
        "jurisdiction": {
            "county_dor_number": county_number,
            "county_name": county_name,
            "county_geoid": geoid,
        },
        "native_parcel_id": parcel_native_id,
        "assessment_year": assessment_year,
        "sale": {
            "sale_identification_code": _text(row.get("SALE_ID_CD")),
            "sale_date": sale_date,
            "date_precision": date_precision,
            "sale_price": _text(row.get("SALE_PRC")),
            "qualification_code": _text(row.get("QUAL_CD")),
            "vacant_or_improved_code": _text(row.get("VI_CD")),
            "sale_change_code": _text(row.get("SAL_CHG_CD")),
            "multi_parcel_sale": _text(row.get("MULTI_PAR_SAL")),
            "instrument_reference": instrument_reference,
        },
        "source_row_number": row_number,
        "raw_fields": dict(row),
    }
    identity_fields = {
        key: row.get(key)
        for key in (
            "PARCEL_ID",
            "SALE_ID_CD",
            "SALE_YR",
            "SALE_MO",
            "SALE_PRC",
            "OR_BOOK",
            "OR_PAGE",
            "CLERK_NO",
            "QUAL_CD",
        )
    }
    native_sale_id = (
        "sdf:" + sha256_fingerprint(identity_fields)[:32]
    )
    observation_id, observation_inserted = _upsert_observation(
        db,
        source_native_id=f"{native_sale_id}:{geoid}",
        record_kind="florida_dor_sdf_sale_row",
        source_url=source_url,
        retrieved_at=retrieved_at,
        schema_fingerprint=schema_fingerprint,
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha256,
        raw=normalized,
    )
    parcel_id = _upsert_parcel(
        db,
        geoid=geoid,
        parcel_id=parcel_native_id,
        assessment_year=tax_year,
        observation_id=observation_id,
        raw=normalized,
    )
    existing_sale = db.execute(
        """
        SELECT sale_event_id
        FROM sale_event
        WHERE parcel_id=? AND source_id=? AND native_sale_id=?
          AND sale_date IS ? AND derivation='assessment_sales_file'
        ORDER BY sale_event_id
        LIMIT 1
        """,
        (parcel_id, SOURCE_ID, native_sale_id, sale_date),
    ).fetchone()
    sale_values = (
        _minor_units(row.get("SALE_PRC")),
        _text(row.get("QUAL_CD")),
        observation_id,
        canonical_json(normalized),
    )
    if existing_sale is None:
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date,
                consideration_minor, currency, qualification_code, derivation,
                observation_id, raw_json
            ) VALUES (
                ?, ?, ?, ?, ?, 'USD', ?, 'assessment_sales_file', ?, ?
            )
            """,
            (
                parcel_id,
                SOURCE_ID,
                native_sale_id,
                sale_date,
                *sale_values,
            ),
        )
    else:
        db.execute(
            """
            UPDATE sale_event SET
                consideration_minor=?,
                qualification_code=?,
                observation_id=?,
                raw_json=?
            WHERE sale_event_id=?
            """,
            (*sale_values, int(existing_sale["sale_event_id"])),
        )
    has_instrument_reference = any(
        instrument_reference.get(field)
        for field in (
            "official_record_book",
            "official_record_page",
            "clerk_instrument_number",
        )
    )
    return {
        "observations_inserted": int(observation_inserted),
        "parcels_upserted": 1,
        "aliases_inserted": _aliases(
            db,
            parcel_id=parcel_id,
            row=row,
            effective_from=tax_year,
        ),
        "sale_events_upserted": 1,
        "instrument_references_preserved": int(has_instrument_reference),
        "recorded_instruments_upserted": 0,
    }


def _empty_counts(dataset_type: str) -> dict[str, int]:
    counts = {
        "rows_seen": 0,
        "rows_processed": 0,
        "rows_deleted": 0,
        "observations_inserted": 0,
        "parcels_upserted": 0,
        "aliases_inserted": 0,
        "owners_upserted": 0,
        "addresses_inserted": 0,
        "assessments_upserted": 0,
        "sale_events_upserted": 0,
        "instrument_references_preserved": 0,
        "recorded_instruments_upserted": 0,
        "gis_join_rows_preserved": 0,
        "gis_unjoinable_rows_preserved": 0,
        "geometries_upserted": 0,
        "gis_null_geometry_occurrences": 0,
        "gis_joined_null_geometry_occurrences": 0,
    }
    if dataset_type == "gis-pin":
        counts["parcels_upserted"] = 0
    return counts


def _add_counts(total: dict[str, int], delta: Mapping[str, int]) -> None:
    for key, value in delta.items():
        total[key] = total.get(key, 0) + int(value)


def _archive_observation(
    db,
    *,
    release: Mapping[str, Any],
    archive_path: Path,
    archive_sha256: str,
    schema_fingerprint: str,
    source_url: str | None,
    retrieved_at: str,
    archive_members: Sequence[Mapping[str, Any]],
    schema: Mapping[str, Any],
) -> tuple[int, bool]:
    raw = {
        "record_kind": "florida_dor_bulk_archive",
        "release": dict(release),
        "artifact": {
            "path": str(archive_path.resolve()),
            "filename": archive_path.name,
            "size": archive_path.stat().st_size,
            "sha256": archive_sha256,
            "members": [dict(member) for member in archive_members],
        },
        "schema": dict(schema),
        "source_omissions": SOURCE_OMISSIONS,
    }
    return _upsert_observation(
        db,
        source_native_id=(
            f"archive:{release['release_id']}:{archive_sha256}"
        ),
        record_kind="florida_dor_bulk_archive",
        source_url=source_url,
        retrieved_at=retrieved_at,
        schema_fingerprint=schema_fingerprint,
        artifact_path=str(archive_path.resolve()),
        artifact_sha256=archive_sha256,
        raw=raw,
    )


def _ingest_csv(
    args: argparse.Namespace,
    *,
    archive_path: Path,
    archive_sha256: str,
    retrieved_at: str,
) -> dict[str, Any]:
    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    counts = _empty_counts(args.dataset_type)
    with zipfile.ZipFile(archive_path) as archive:
        members = _zip_members(archive)
        member, match = _csv_identity(
            archive,
            dataset_type=args.dataset_type,
        )
        county_number = int(match.group("county"))
        if county_number not in COUNTY_BY_DOR_NUMBER:
            raise FloridaDORIngestError(
                f"archive member uses unknown DOR county number {county_number}"
            )
        assessment_year = int(match.group("year"))
        stage = match.group("stage").upper()
        release = _release_identity(
            dataset_type=args.dataset_type,
            county_number=county_number,
            assessment_year=assessment_year,
            stage=stage,
            artifact_sha256=archive_sha256,
            archive_name=archive_path.name,
            release_fingerprint=args.release_fingerprint,
        )
        county_name, geoid = _validate_requested_identity(
            args,
            county_number=county_number,
            assessment_year=assessment_year,
            stage=stage,
            release_id=str(release["release_id"]),
        )

        required = (
            NAL_REQUIRED_COLUMNS
            if args.dataset_type == "nal"
            else SDF_REQUIRED_COLUMNS
        )
        with archive.open(member) as binary:
            with io.TextIOWrapper(
                binary,
                encoding="utf-8-sig",
                errors="strict",
                newline="",
            ) as text:
                reader = csv.DictReader(text)
                fields = _header(
                    reader,
                    required=required,
                    dataset_type=args.dataset_type,
                )
                schema_fingerprint = sha256_fingerprint(fields)
                schema = {
                    "dataset_type": args.dataset_type,
                    "member": member.filename,
                    "member_crc32": f"{member.CRC:08x}",
                    "encoding": "utf-8-sig",
                    "csv_field_size_limit": CSV_FIELD_SIZE_LIMIT,
                    "physical_field_count": len(fields),
                    "header_fields": fields,
                    "header_fingerprint": schema_fingerprint,
                    "required_columns": sorted(required),
                }
                db = connect_property(args.property_db)
                try:
                    _upsert_jurisdiction(
                        db,
                        geoid=geoid,
                        county_name=county_name,
                    )
                    archive_observation_id, archive_observation_inserted = (
                        _archive_observation(
                            db,
                            release=release,
                            archive_path=archive_path,
                            archive_sha256=archive_sha256,
                            schema_fingerprint=schema_fingerprint,
                            source_url=args.source_url,
                            retrieved_at=retrieved_at,
                            archive_members=members,
                            schema=schema,
                        )
                    )
                    db.commit()
                    projection = (
                        _nal_projection
                        if args.dataset_type == "nal"
                        else _sdf_projection
                    )
                    pending = 0
                    exhausted = True
                    for row_index, raw_row in enumerate(reader):
                        counts["rows_seen"] += 1
                        if row_index < args.start_row:
                            continue
                        if (
                            args.limit is not None
                            and counts["rows_processed"] >= args.limit
                        ):
                            exhausted = False
                            break
                        row_number = row_index + 2
                        row = _validate_csv_row(
                            raw_row,
                            row_number=row_number,
                            member_county=county_number,
                            assessment_year=assessment_year,
                        )
                        delta = projection(
                            db,
                            row=row,
                            row_number=row_number,
                            geoid=geoid,
                            county_number=county_number,
                            county_name=county_name,
                            assessment_year=assessment_year,
                            release=release,
                            schema_fingerprint=schema_fingerprint,
                            artifact_path=str(archive_path.resolve()),
                            artifact_sha256=archive_sha256,
                            source_url=args.source_url,
                            retrieved_at=retrieved_at,
                        )
                        counts["rows_processed"] += 1
                        _add_counts(counts, delta)
                        pending += 1
                        if pending >= args.batch_size:
                            db.commit()
                            pending = 0
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
    next_checkpoint = (
        None
        if exhausted
        else args.start_row + counts["rows_processed"]
    )
    return {
        "schema_version": "florida-dor-archive-ingest/1.0",
        "status": "ok",
        "source_id": SOURCE_ID,
        "dataset_type": args.dataset_type,
        "release": release,
        "artifact": {
            "path": str(archive_path.resolve()),
            "filename": archive_path.name,
            "size": archive_path.stat().st_size,
            "sha256": archive_sha256,
        },
        "archive_observation_id": archive_observation_id,
        "archive_observation_inserted": archive_observation_inserted,
        "schema": schema,
        "counts": counts,
        "start_row": args.start_row,
        "caller_limit": args.limit,
        "next_checkpoint_row": next_checkpoint,
        "exhausted": exhausted,
        "property_db": str(Path(args.property_db)),
    }


def _dbf_fields(
    handle: BinaryIO,
) -> tuple[int, int, int, list[dict[str, Any]]]:
    header = handle.read(32)
    if len(header) != 32:
        raise FloridaDORIngestError("GIS-PIN DBF header is truncated")
    record_count = struct.unpack_from("<I", header, 4)[0]
    header_length = struct.unpack_from("<H", header, 8)[0]
    record_length = struct.unpack_from("<H", header, 10)[0]
    if header_length < 33 or (header_length - 33) % 32:
        raise FloridaDORIngestError("GIS-PIN DBF header length is invalid")
    fields: list[dict[str, Any]] = []
    for _index in range((header_length - 33) // 32):
        descriptor = handle.read(32)
        if len(descriptor) != 32:
            raise FloridaDORIngestError(
                "GIS-PIN DBF field descriptor is truncated"
            )
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii", errors="strict")
        if not name:
            raise FloridaDORIngestError("GIS-PIN DBF has a blank field name")
        fields.append(
            {
                "name": name,
                "type": chr(descriptor[11]),
                "length": int(descriptor[16]),
                "decimal_count": int(descriptor[17]),
            }
        )
    terminator = handle.read(1)
    if terminator != b"\r":
        raise FloridaDORIngestError(
            "GIS-PIN DBF field descriptors lack a terminator"
        )
    consumed = 32 + len(fields) * 32 + 1
    if header_length > consumed:
        extension = handle.read(header_length - consumed)
        if len(extension) != header_length - consumed:
            raise FloridaDORIngestError(
                "GIS-PIN DBF extended header is truncated"
            )
    expected_record_length = 1 + sum(field["length"] for field in fields)
    if record_length != expected_record_length:
        raise FloridaDORIngestError(
            "GIS-PIN DBF record length conflicts with its field descriptors"
        )
    names = [field["name"] for field in fields]
    if len(names) != len(set(names)):
        raise FloridaDORIngestError("GIS-PIN DBF field names are duplicated")
    if "PARCELNO" not in names:
        raise FloridaDORIngestError("GIS-PIN DBF lacks required PARCELNO")
    return record_count, header_length, record_length, fields


def _dbf_rows(
    handle: BinaryIO,
    *,
    record_count: int,
    record_length: int,
    fields: Sequence[Mapping[str, Any]],
    encoding: str,
) -> Iterator[tuple[int, bool, dict[str, str | None]]]:
    for row_index in range(record_count):
        raw = handle.read(record_length)
        if len(raw) != record_length:
            raise FloridaDORIngestError(
                f"GIS-PIN DBF record {row_index} is truncated"
            )
        deleted = raw[:1] == b"*"
        if raw[:1] not in {b" ", b"*"}:
            raise FloridaDORIngestError(
                f"GIS-PIN DBF record {row_index} has an invalid deletion flag"
            )
        offset = 1
        row: dict[str, str | None] = {}
        for field in fields:
            length = int(field["length"])
            value = raw[offset : offset + length]
            offset += length
            decoded = value.decode(encoding, errors="strict").strip()
            row[str(field["name"])] = decoded or None
        yield row_index, deleted, row


def _gis_identity(
    archive: zipfile.ZipFile,
) -> tuple[
    zipfile.ZipInfo,
    re.Match[str],
    zipfile.ZipInfo,
    zipfile.ZipInfo | None,
]:
    dbf_members = [
        member
        for member in archive.infolist()
        if not member.is_dir() and member.filename.casefold().endswith(".dbf")
    ]
    if len(dbf_members) != 1:
        raise FloridaDORIngestError(
            "GIS-PIN archive must contain exactly one DBF member"
        )
    dbf_member = dbf_members[0]
    match = GIS_DBF_RE.fullmatch(Path(dbf_member.filename).name)
    if match is None:
        raise FloridaDORIngestError(
            f"DBF member {dbf_member.filename!r} is not a GIS-PIN artifact"
        )
    stem = str(Path(dbf_member.filename).with_suffix(""))
    prj_name = f"{stem}.prj".casefold()
    cpg_name = f"{stem}.cpg".casefold()
    by_name = {
        member.filename.casefold(): member
        for member in archive.infolist()
        if not member.is_dir()
    }
    try:
        prj_member = by_name[prj_name]
    except KeyError as error:
        raise FloridaDORIngestError(
            "GIS-PIN archive lacks a same-stem PRJ member"
        ) from error
    return dbf_member, match, prj_member, by_name.get(cpg_name)


def _gis_crs_label(inspection: ShapefileDatasetInspection) -> str:
    authorities = inspection.crs.authority_candidates
    if authorities:
        return "|".join(authorities)
    if inspection.crs.byte_sha256:
        return f"WKT-SHA256:{inspection.crs.byte_sha256}"
    return "published_native_crs_unspecified"


def _upsert_gis_geometry(
    db,
    *,
    parcel_id: int,
    geometry_ref: str,
    assessment_year: int,
    stage: str,
    geometry_format: str,
    source_resolution: str,
    crs: str,
) -> int:
    db.execute(
        """
        INSERT INTO parcel_geometry(
            parcel_id, geometry_ref, geometry_format, crs,
            source_resolution, accuracy_disclaimer, source_id, snapshot_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, snapshot_date) DO UPDATE SET
            geometry_ref=excluded.geometry_ref,
            geometry_format=excluded.geometry_format,
            crs=excluded.crs,
            source_resolution=excluded.source_resolution,
            accuracy_disclaimer=excluded.accuracy_disclaimer
        """,
        (
            parcel_id,
            geometry_ref,
            geometry_format,
            crs,
            source_resolution,
            (
                "Florida DOR GIS-PIN source geometry in its published native "
                "CRS. Repeated source feature occurrences are retained "
                "separately and are not dissolved into a surveyed boundary."
            ),
            SOURCE_ID,
            f"{assessment_year}{stage}",
        ),
    )
    return 1


def _reconcile_gis_geometry_projections(
    db,
    *,
    release: Mapping[str, Any],
    geoid: str,
    county_number: int,
    county_name: str,
    assessment_year: int,
    stage: str,
    archive_path: Path,
    archive_sha256: str,
    schema_fingerprint: str,
    source_url: str | None,
    retrieved_at: str,
    inspection: ShapefileDatasetInspection,
) -> dict[str, int]:
    """Project all currently preserved occurrences for one artifact.

    A parcel number may occur in more than one aligned feature. The source
    occurrences remain independent observations; this projection groups their
    native geometries without applying a spatial union or choosing a winner.
    """

    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    rows = db.execute(
        """
        SELECT observation_id, raw_json
        FROM source_observation
        WHERE source_id=?
          AND record_kind='florida_dor_gis_pin_feature_occurrence'
          AND raw_artifact_sha256=?
        ORDER BY observation_id
        """,
        (SOURCE_ID, archive_sha256),
    ).fetchall()
    for row in rows:
        raw = json.loads(row["raw_json"])
        if raw.get("release", {}).get("release_id") != release["release_id"]:
            continue
        parcelno = _text(raw.get("parcelno"))
        feature = raw.get("shapefile_feature")
        if (
            parcelno is None
            or not isinstance(feature, Mapping)
            or bool(feature.get("dbf_record", {}).get("deleted"))
        ):
            continue
        feature_occurrence = feature.get("feature_occurrence")
        if not isinstance(feature_occurrence, Mapping):
            continue
        occurrence_id = _text(feature_occurrence.get("occurrence_id"))
        if occurrence_id is None:
            continue
        grouped.setdefault(parcelno, {})[occurrence_id] = {
            "observation_id": int(row["observation_id"]),
            "occurrence_id": occurrence_id,
            "canonical_ref": feature.get("canonical_ref"),
            "evidence_ref": feature.get("evidence_ref"),
            "feature_ordinal": int(
                feature_occurrence["feature_ordinal"]
            ),
            "source_record_number": int(
                feature_occurrence["source_record_number"]
            ),
            "geometry_state": feature.get("geometry_state"),
            "has_geometry": feature.get("geometry") is not None,
        }

    counts = {
        "parcels_upserted": 0,
        "geometries_upserted": 0,
        "geometry_projection_observations_inserted": 0,
        "gis_repeated_join_parcels": 0,
        "gis_joined_null_geometry_occurrences": 0,
    }
    for parcelno, occurrence_map in sorted(grouped.items()):
        feature_rows = sorted(
            occurrence_map.values(),
            key=lambda item: int(item["feature_ordinal"]),
        )
        nonnull_geometry_rows = [
            item for item in feature_rows if item["has_geometry"]
        ]
        counts["gis_joined_null_geometry_occurrences"] += (
            len(feature_rows) - len(nonnull_geometry_rows)
        )
        if len(feature_rows) > 1:
            counts["gis_repeated_join_parcels"] += 1

        occurrence_lineage = [
            {
                "observation_id": item["observation_id"],
                "occurrence_id": item["occurrence_id"],
                "canonical_ref": item["canonical_ref"],
                "evidence_ref": item["evidence_ref"],
                "feature_ordinal": item["feature_ordinal"],
                "source_record_number": item["source_record_number"],
                "geometry_state": item["geometry_state"],
            }
            for item in feature_rows
        ]
        normalized: dict[str, Any] = {
            "record_kind": "florida_dor_gis_pin_parcel_geometry_projection",
            "dataset_type": "gis-pin",
            "release": dict(release),
            "jurisdiction": {
                "county_dor_number": county_number,
                "county_name": county_name,
                "county_geoid": geoid,
            },
            "native_parcel_id": parcelno,
            "assessment_year": assessment_year,
            "source_feature_occurrences": occurrence_lineage,
            "reconciliation": {
                "basis": "exact_publisher_declared_PARCELNO",
                "normalization": "whitespace_trim_only",
                "source_occurrences_preserved": True,
                "spatial_union_performed": False,
            },
        }
        if len(feature_rows) == 1:
            projection_observation_id = int(
                feature_rows[0]["observation_id"]
            )
            normalized["geometry"] = {
                "representation": "single_source_feature_reference",
                "native_crs": inspection.crs.to_dict(),
                "source_observation_id": projection_observation_id,
                "json_pointer": "/shapefile_feature/geometry",
                "feature_occurrence_count": 1,
                "geometry_occurrence_count": len(nonnull_geometry_rows),
                "union_or_dissolve_applied": False,
            }
            geometry_ref = (
                f"source-observation:{projection_observation_id}"
                "#/shapefile_feature/geometry"
            )
            geometry_format = "esri_shapefile_native_geometry_json"
            source_resolution = "publisher_feature_occurrence"
        else:
            geometry_features = []
            for item in feature_rows:
                feature_row = db.execute(
                    """
                    SELECT raw_json
                    FROM source_observation
                    WHERE observation_id=?
                    """,
                    (item["observation_id"],),
                ).fetchone()
                assert feature_row is not None
                feature_raw = json.loads(feature_row["raw_json"])[
                    "shapefile_feature"
                ]
                if feature_raw.get("geometry") is None:
                    continue
                geometry_features.append(
                    {
                        "occurrence_id": item["occurrence_id"],
                        "canonical_ref": item["canonical_ref"],
                        "evidence_ref": item["evidence_ref"],
                        "feature_ordinal": item["feature_ordinal"],
                        "source_record_number": item[
                            "source_record_number"
                        ],
                        "geometry": feature_raw["geometry"],
                        "geometry_state": item["geometry_state"],
                    }
                )
            normalized["geometry"] = {
                "representation": "source_feature_collection",
                "native_crs": inspection.crs.to_dict(),
                "features": geometry_features,
                "feature_occurrence_count": len(feature_rows),
                "geometry_occurrence_count": len(geometry_features),
                "union_or_dissolve_applied": False,
            }
            projection_observation_id, inserted = _upsert_observation(
                db,
                source_native_id=(
                    f"gis-pin:{release['release_id']}:{geoid}:"
                    f"parcel:{parcelno}:geometry"
                ),
                record_kind=(
                    "florida_dor_gis_pin_parcel_geometry_projection"
                ),
                source_url=source_url,
                retrieved_at=retrieved_at,
                schema_fingerprint=schema_fingerprint,
                artifact_path=str(archive_path.resolve()),
                artifact_sha256=archive_sha256,
                raw=normalized,
            )
            counts["geometry_projection_observations_inserted"] += int(
                inserted
            )
            geometry_ref = (
                f"source-observation:{projection_observation_id}#/geometry"
            )
            geometry_format = (
                "esri_shapefile_native_feature_collection_json"
            )
            source_resolution = "publisher_feature_occurrence_collection"
        parcel_id = _upsert_parcel(
            db,
            geoid=geoid,
            parcel_id=parcelno,
            assessment_year=str(assessment_year),
            observation_id=projection_observation_id,
            raw=normalized,
        )
        counts["parcels_upserted"] += 1
        if nonnull_geometry_rows:
            counts["geometries_upserted"] += _upsert_gis_geometry(
                db,
                parcel_id=parcel_id,
                geometry_ref=geometry_ref,
                assessment_year=assessment_year,
                stage=stage,
                geometry_format=geometry_format,
                source_resolution=source_resolution,
                crs=_gis_crs_label(inspection),
            )
    return counts


def _ingest_gis_pin(
    args: argparse.Namespace,
    *,
    archive_path: Path,
    archive_sha256: str,
    retrieved_at: str,
) -> dict[str, Any]:
    counts = _empty_counts("gis-pin")
    with zipfile.ZipFile(archive_path) as archive:
        members = _zip_members(archive)
        dbf_member, match, prj_member, cpg_member = _gis_identity(archive)
        county_number, county_name, geoid = resolve_county(match.group("county"))
        assessment_year = int(match.group("year"))
        stage = (
            args.submission_stage[0].upper()
            if args.submission_stage
            else "F"
        )
        release = _release_identity(
            dataset_type="gis-pin",
            county_number=county_number,
            assessment_year=assessment_year,
            stage=stage,
            artifact_sha256=archive_sha256,
            archive_name=archive_path.name,
            release_fingerprint=args.release_fingerprint,
        )
        county_name, geoid = _validate_requested_identity(
            args,
            county_number=county_number,
            assessment_year=assessment_year,
            stage=stage,
            release_id=str(release["release_id"]),
        )
        dataset_member = str(
            Path(dbf_member.filename).with_suffix("")
        )
        inspection = inspect_shapefile_dataset(
            archive_path,
            dataset_member=dataset_member,
            source_id=SOURCE_ID,
            release_id=str(release["release_id"]),
            parcel_fields=["PARCELNO"],
        )
        if inspection.members.dbf.casefold() != dbf_member.filename.casefold():
            raise FloridaDORIngestError(
                "GIS-PIN identity did not resolve to the inspected DBF member"
            )
        if inspection.members.prj is None or (
            inspection.members.prj.casefold() != prj_member.filename.casefold()
        ):
            raise FloridaDORIngestError(
                "GIS-PIN identity did not resolve to the inspected PRJ member"
            )
        if (
            cpg_member is not None
            and (
                inspection.members.cpg is None
                or inspection.members.cpg.casefold()
                != cpg_member.filename.casefold()
            )
        ):
            raise FloridaDORIngestError(
                "GIS-PIN identity did not resolve to the inspected CPG member"
            )
        if args.start_row > inspection.feature_count:
            raise FloridaDORIngestError(
                "--start-row exceeds the GIS-PIN feature count"
            )

        schema = {
            "dataset_type": "gis-pin",
            "record_count": inspection.feature_count,
            "shapefile": {
                "members": inspection.members.to_dict(),
                "shp": inspection.shp.to_dict(),
                "shx": inspection.shx.to_dict(),
                "dbf": inspection.dbf.to_dict(),
                "crs": inspection.crs.to_dict(),
                "parcel_join_fields": list(
                    inspection.parcel_join_fields
                ),
                "feature_count": inspection.feature_count,
                "alignment_state": inspection.alignment_state,
                "generic_schema_fingerprint": (
                    inspection.schema_fingerprint
                ),
            },
            "join": {
                "gis_field": "PARCELNO",
                "nal_field": "PARCEL_ID",
                "relationship": "publisher_declared_join_key",
            },
            "geometry_projection": {
                "status": "decoded_native_crs",
                "representation": (
                    "source_feature_occurrences_then_parcel_collection"
                ),
                "source_occurrences_preserved": True,
                "spatial_union_performed": False,
            },
        }
        schema_fingerprint = sha256_fingerprint(schema)
        db = connect_property(args.property_db)
        try:
            _upsert_jurisdiction(
                db,
                geoid=geoid,
                county_name=county_name,
            )
            archive_observation_id, archive_observation_inserted = (
                _archive_observation(
                    db,
                    release=release,
                    archive_path=archive_path,
                    archive_sha256=archive_sha256,
                    schema_fingerprint=schema_fingerprint,
                    source_url=args.source_url,
                    retrieved_at=retrieved_at,
                    archive_members=members,
                    schema=schema,
                )
            )
            db.commit()
            pending = 0
            feature_stream = iter_shapefile_features(
                archive_path,
                dataset_member=inspection.members.shp,
                source_id=SOURCE_ID,
                release_id=str(release["release_id"]),
                parcel_fields=["PARCELNO"],
                inspection=inspection,
                start_feature_ordinal=args.start_row,
            )
            if args.limit is not None:
                feature_stream = itertools.islice(
                    feature_stream,
                    args.limit,
                )
            for feature in feature_stream:
                feature_occurrence = feature["feature_occurrence"]
                row_index = int(feature_occurrence["feature_ordinal"])
                deleted = bool(feature["dbf_record"]["deleted"])
                selected_join = feature["parcel_join"].get("selected")
                parcelno = (
                    _text(selected_join.get("value"))
                    if isinstance(selected_join, Mapping)
                    else None
                )
                stable_feature = dict(feature)
                stable_lineage = dict(feature["source_lineage"])
                stable_lineage.pop("artifact_path", None)
                stable_feature["source_lineage"] = stable_lineage
                normalized = {
                    "record_kind": (
                        "florida_dor_gis_pin_feature_occurrence"
                    ),
                    "dataset_type": "gis-pin",
                    "release": release,
                    "jurisdiction": {
                        "county_dor_number": county_number,
                        "county_name": county_name,
                        "county_geoid": geoid,
                    },
                    "source_row_number": row_index,
                    "feature_record_number": feature_occurrence[
                        "source_record_number"
                    ],
                    "parcelno": parcelno,
                    "source_omission_state": {
                        "parcelno_field_state": (
                            "published"
                            if parcelno
                            else "blank_in_source_dbf"
                        ),
                    },
                    "join": {
                        "gis_field": "PARCELNO",
                        "gis_value": parcelno,
                        "nal_field": "PARCEL_ID",
                        "join_state": (
                            "join_key_present"
                            if parcelno
                            else feature["parcel_join"]["state"]
                        ),
                        "geometry_decoded": (
                            feature["geometry"] is not None
                        ),
                    },
                    "shapefile_feature": stable_feature,
                }
                _observation_id, inserted = _upsert_observation(
                    db,
                    source_native_id=(
                        f"gis-pin:{assessment_year}:{geoid}:"
                        f"feature:{row_index}:{parcelno or 'blank'}"
                    ),
                    record_kind=(
                        "florida_dor_gis_pin_feature_occurrence"
                    ),
                    source_url=args.source_url,
                    retrieved_at=retrieved_at,
                    schema_fingerprint=schema_fingerprint,
                    artifact_path=str(archive_path.resolve()),
                    artifact_sha256=archive_sha256,
                    raw=normalized,
                )
                counts["rows_seen"] += 1
                counts["rows_processed"] += 1
                counts["observations_inserted"] += int(inserted)
                if feature["geometry"] is None:
                    counts["gis_null_geometry_occurrences"] += 1
                if deleted:
                    counts["rows_deleted"] += 1
                elif parcelno:
                    counts["gis_join_rows_preserved"] += 1
                else:
                    counts["gis_unjoinable_rows_preserved"] += 1
                pending += 1
                if pending >= args.batch_size:
                    db.commit()
                    pending = 0
            db.commit()
            _add_counts(
                counts,
                _reconcile_gis_geometry_projections(
                    db,
                    release=release,
                    geoid=geoid,
                    county_number=county_number,
                    county_name=county_name,
                    assessment_year=assessment_year,
                    stage=stage,
                    archive_path=archive_path,
                    archive_sha256=archive_sha256,
                    schema_fingerprint=schema_fingerprint,
                    source_url=args.source_url,
                    retrieved_at=retrieved_at,
                    inspection=inspection,
                ),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    next_feature_ordinal = args.start_row + counts["rows_processed"]
    exhausted = next_feature_ordinal >= inspection.feature_count
    next_checkpoint = None if exhausted else next_feature_ordinal
    return {
        "schema_version": "florida-dor-archive-ingest/1.0",
        "status": "ok",
        "source_id": SOURCE_ID,
        "dataset_type": "gis-pin",
        "release": release,
        "artifact": {
            "path": str(archive_path.resolve()),
            "filename": archive_path.name,
            "size": archive_path.stat().st_size,
            "sha256": archive_sha256,
        },
        "archive_observation_id": archive_observation_id,
        "archive_observation_inserted": archive_observation_inserted,
        "schema": schema,
        "counts": counts,
        "start_row": args.start_row,
        "caller_limit": args.limit,
        "next_checkpoint_row": next_checkpoint,
        "exhausted": exhausted,
        "property_db": str(Path(args.property_db)),
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    """Validate and ingest one caller-selected Florida DOR archive."""

    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.is_file():
        raise FloridaDORIngestError(
            f"archive does not exist: {archive_path}"
        )
    archive_sha256 = _sha256_path(archive_path)
    if args.expected_sha256 and (
        archive_sha256.casefold() != args.expected_sha256.casefold()
    ):
        raise FloridaDORIngestError(
            "archive SHA-256 does not match --expected-sha256"
        )
    retrieved_at = _artifact_timestamp(archive_path, args.retrieved_at)
    try:
        if args.dataset_type in {"nal", "sdf"}:
            return _ingest_csv(
                args,
                archive_path=archive_path,
                archive_sha256=archive_sha256,
                retrieved_at=retrieved_at,
            )
        return _ingest_gis_pin(
            args,
            archive_path=archive_path,
            archive_sha256=archive_sha256,
            retrieved_at=retrieved_at,
        )
    except zipfile.BadZipFile as error:
        raise FloridaDORIngestError(
            f"archive is not a readable ZIP: {archive_path}"
        ) from error
    except ParcelShapefileError as error:
        raise FloridaDORIngestError(
            f"GIS-PIN shapefile validation failed: {error}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stream a downloaded Florida DOR archive into the property sidecar"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser(
        "ingest",
        help="Validate and ingest one NAL, SDF, or GIS-PIN ZIP",
    )
    ingest.add_argument(
        "--type",
        dest="dataset_type",
        choices=("nal", "sdf", "gis-pin"),
        required=True,
    )
    ingest.add_argument("--archive", required=True)
    ingest.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    ingest.add_argument(
        "--county",
        help="Optional expected county name, DOR number, FIPS suffix, or GEOID",
    )
    ingest.add_argument("--tax-year", type=int)
    ingest.add_argument(
        "--submission-stage",
        choices=("preliminary", "final", "P", "F"),
    )
    ingest.add_argument("--release-id")
    ingest.add_argument("--release-fingerprint")
    ingest.add_argument("--expected-sha256")
    ingest.add_argument("--source-url")
    ingest.add_argument("--retrieved-at")
    ingest.add_argument(
        "--start-row",
        type=int,
        default=0,
        help="Caller-selected zero-based row checkpoint",
    )
    ingest.add_argument(
        "--limit",
        type=int,
        help="Optional caller-selected row ceiling",
    )
    ingest.add_argument(
        "--batch-size",
        type=int,
        default=1_000,
        help="Rows committed per transaction; this is not a record ceiling",
    )
    add_output_args(ingest)
    return parser


def _validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    if args.start_row < 0:
        parser.error("--start-row must not be negative")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.tax_year is not None and args.tax_year <= 0:
        parser.error("--tax-year must be positive")
    for field in ("expected_sha256", "release_fingerprint"):
        value = getattr(args, field)
        if value and not SHA256_RE.fullmatch(value):
            parser.error(f"--{field.replace('_', '-')} must be a SHA-256 hex digest")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    try:
        payload = execute(args)
    except (FloridaDORIngestError, OSError, UnicodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    if write_output(
        payload,
        args,
        summary=(
            f"Florida DOR {payload['dataset_type']} archive ingest "
            f"({payload['counts']['rows_processed']} rows)"
        ),
    ):
        return
    print(json.dumps(payload, indent=2 if args.json_out else None, sort_keys=True))


if __name__ == "__main__":
    main()
