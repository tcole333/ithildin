#!/usr/bin/env python3
"""Stream verified HCAD CAMA archives into the property-record sidecar.

The HCAD release adapter resolves and downloads official ZIP artifacts. This
tool is the explicit parsing stage: it validates live-observed tab-delimited
headers, preserves every selected row occurrence, and projects the subset that
has a truthful representation in the shared property schema.

Usage:
    uv run python tools/ingest_hcad_property.py ingest \
      --archive /tmp/Real_acct_owner.zip --tax-year 2026 \
      --release-id 2026:preliminary:2026-07-26 \
      --property-db /tmp/hcad-property.db \
      --output /tmp/hcad-ingest.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sqlite3
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import canonical_json, sha256_fingerprint
    from tools.public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from tools.query_harris_property import CODEBOOK_URL, SOURCE_ID
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import canonical_json, sha256_fingerprint
    from public_records_store import (
        DEFAULT_PROPERTY_DB,
        canonical_property_ref,
        connect_property,
    )
    from query_harris_property import CODEBOOK_URL, SOURCE_ID


JURISDICTION_GEOID = "48201"
CSV_FIELD_SIZE_LIMIT = 16 * 1024 * 1024
SOURCE_ENCODING = "cp437"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


class HCADIngestError(ValueError):
    """A downloaded HCAD artifact does not match its observed data contract."""


@dataclass(frozen=True)
class TableSpec:
    """Live-observed HCAD table header and its supported projection."""

    artifact_role: str
    header: tuple[str, ...]
    projection: str


TABLE_SPECS: dict[str, TableSpec] = {
    "deeds": TableSpec(
        "real_acct_owner",
        ("acct", "dos", "clerk_yr", "clerk_id", "deed_id"),
        "deed_reference",
    ),
    "owners": TableSpec(
        "real_acct_owner",
        ("acct", "ln_num", "name", "aka", "pct_own"),
        "owner",
    ),
    "parcel_tieback": TableSpec(
        "real_acct_owner",
        ("acct", "tp", "dscr", "related_acct", "pct"),
        "account_relation",
    ),
    "permits": TableSpec(
        "real_acct_owner",
        (
            "acct",
            "id",
            "agency_id",
            "status",
            "dscr",
            "dor_cd",
            "permit_type",
            "permit_tp_descr",
            "property_tp",
            "issue_date",
            "yr",
            "site_num",
            "site_pfx",
            "site_str",
            "site_tp",
            "site_sfx",
            "site_apt",
        ),
        "permit",
    ),
    "real_acct": TableSpec(
        "real_acct_owner",
        (
            "acct",
            "yr",
            "mailto",
            "mail_addr_1",
            "mail_addr_2",
            "mail_city",
            "mail_state",
            "mail_zip",
            "mail_country",
            "undeliverable",
            "str_pfx",
            "str_num",
            "str_num_sfx",
            "str",
            "str_sfx",
            "str_sfx_dir",
            "str_unit",
            "site_addr_1",
            "site_addr_2",
            "site_addr_3",
            "state_class",
            "school_dist",
            "map_facet",
            "key_map",
            "Neighborhood_Code",
            "Neighborhood_Grp",
            "Market_Area_1",
            "Market_Area_1_Dscr",
            "Market_Area_2",
            "Market_Area_2_Dscr",
            "econ_area",
            "econ_bld_class",
            "center_code",
            "yr_impr",
            "yr_annexed",
            "splt_dt",
            "dsc_cd",
            "nxt_bld",
            "bld_ar",
            "land_ar",
            "acreage",
            "Cap_acct",
            "shared_cad",
            "land_val",
            "bld_val",
            "x_features_val",
            "ag_val",
            "assessed_val",
            "tot_appr_val",
            "tot_mkt_val",
            "prior_land_val",
            "prior_bld_val",
            "prior_x_features_val",
            "prior_ag_val",
            "prior_tot_appr_val",
            "prior_tot_mkt_val",
            "new_construction_val",
            "tot_rcn_val",
            "value_status",
            "noticed",
            "notice_dt",
            "protested",
            "certified_date",
            "rev_dt",
            "rev_by",
            "new_own_dt",
            "lgl_1",
            "lgl_2",
            "lgl_3",
            "lgl_4",
            "jurs",
        ),
        "real_account",
    ),
    "real_neighborhood_code": TableSpec(
        "real_acct_owner",
        ("cd", "grp_cd", "dscr"),
        "secondary",
    ),
    "real_mnrl": TableSpec(
        "real_acct_owner",
        ("acct", "dor_cd", "Rail_leasenum", "Type_Interest", "Interest_Percent"),
        "secondary",
    ),
    "ownership_history": TableSpec(
        "real_acct_ownership_history",
        ("acct", "purchase_date", "name", "site_address"),
        "ownership_history",
    ),
    "building_other": TableSpec(
        "real_building_land",
        (
            "acct",
            "property_use_cd",
            "bld_num",
            "impr_tp",
            "impr_mdl_cd",
            "structure",
            "structure_dscr",
            "noticed_Depr_Val",
            "Depr_Val",
            "MS_replacement_cost",
            "cama_replacement_cost",
            "accrued_depr_pct",
            "qa_cd",
            "dscr",
            "date_erected",
            "eff",
            "yr_remodel",
            "yr_roll",
            "appr_by",
            "appr_dt",
            "notes",
            "im_sq_ft",
            "act_ar",
            "heat_ar",
            "gross_ar",
            "eff_ar",
            "base_ar",
            "perimeter",
            "pct",
            "category",
            "pgi_dscr",
            "prop_nm",
            "units",
            "nra",
            "lease_rt",
            "occ_rt",
            "tot_inc",
        ),
        "building_detail",
    ),
    "building_res": TableSpec(
        "real_building_land",
        (
            "acct",
            "property_use_cd",
            "bld_num",
            "impr_tp",
            "impr_mdl_cd",
            "structure",
            "structure_dscr",
            "dpr_val",
            "cama_replacement_cost",
            "accrued_depr_pct",
            "qa_cd",
            "dscr",
            "date_erected",
            "eff",
            "yr_remodel",
            "yr_roll",
            "appr_by",
            "appr_dt",
            "notes",
            "im_sq_ft",
            "act_ar",
            "heat_ar",
            "gross_ar",
            "eff_ar",
            "base_ar",
            "perimeter",
            "pct",
            "bld_adj",
            "rcnld",
            "size_index",
            "lump_sum_adj",
        ),
        "building_detail",
    ),
    "exterior": TableSpec(
        "real_building_land",
        ("acct", "bld_num", "sar_cd", "sar_dscr", "area"),
        "secondary",
    ),
    "extra_features": TableSpec(
        "real_building_land",
        (
            "acct",
            "bld_num",
            "count",
            "grade",
            "cd",
            "s_dscr",
            "l_dscr",
            "cat",
            "dscr",
            "note",
            "uts",
        ),
        "secondary",
    ),
    "extra_features_detail1": TableSpec(
        "real_building_land",
        (
            "acct",
            "cd",
            "dscr",
            "grade",
            "cond_cd",
            "bld_num",
            "length",
            "width",
            "units",
            "unit_price",
            "adj_unit_price",
            "pct_comp",
            "act_yr",
            "eff_yr",
            "roll_yr",
            "DT",
            "pct_cond",
            "dpr_val",
            "note",
            "asd_val",
        ),
        "secondary",
    ),
    "extra_features_detail2": TableSpec(
        "real_building_land",
        (
            "acct",
            "cd",
            "dscr",
            "grade",
            "cond_cd",
            "bld_num",
            "length",
            "width",
            "units",
            "unit_price",
            "adj_unit_price",
            "pct_comp",
            "act_yr",
            "eff_yr",
            "roll_yr",
            "DT",
            "pct_cond",
            "dpr_val",
            "note",
            "asd_val",
        ),
        "secondary",
    ),
    "fixtures": TableSpec(
        "real_building_land",
        ("acct", "bld_num", "type", "type_dscr", "units"),
        "secondary",
    ),
    "land": TableSpec(
        "real_building_land",
        (
            "acct",
            "num",
            "use_cd",
            "use_dscr",
            "inf_cd",
            "inf_dscr",
            "inf_adj",
            "tp",
            "uts",
            "sz_fact",
            "inf_fact",
            "cond",
            "ovr_dscr",
            "tot_adj",
            "unit_prc",
            "adj_unit_prc",
            "val",
            "ovr_val",
        ),
        "land_detail",
    ),
    "land_ag": TableSpec(
        "real_building_land",
        (
            "acct",
            "num",
            "use_cd",
            "use_dscr",
            "inf_cd",
            "inf_dscr",
            "inf_adj",
            "tp",
            "uts",
            "sz_fact",
            "inf_fact",
            "cond",
            "ovr_dscr",
            "tot_adj",
            "unit_prc",
            "adj_unit_prc",
            "val",
            "ovr_val",
        ),
        "land_detail",
    ),
    "structural_elem1": TableSpec(
        "real_building_land",
        (
            "acct",
            "bld_num",
            "code",
            "adj",
            "type",
            "type_dscr",
            "category_dscr",
            "dor_cd",
        ),
        "secondary",
    ),
    "structural_elem2": TableSpec(
        "real_building_land",
        (
            "acct",
            "bld_num",
            "code",
            "adj",
            "type",
            "type_dscr",
            "category_dscr",
            "dor_cd",
        ),
        "secondary",
    ),
}

TABLE_ORDER = tuple(TABLE_SPECS)


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


def _artifact_timestamp(path: Path, supplied: str | None) -> str:
    if supplied:
        return supplied
    return datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    for pattern in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _minor_units(value: Any) -> int | None:
    text = _text(value)
    if text is None:
        return None
    normalized = text.replace(",", "").replace("$", "")
    try:
        amount = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite():
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _sum_minor(*values: Any) -> int | None:
    parsed = [_minor_units(value) for value in values]
    present = [value for value in parsed if value is not None]
    return sum(present) if present else None


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


def _member_index(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    for member in archive.infolist():
        if member.is_dir():
            continue
        basename = Path(member.filename).name
        if basename != member.filename:
            raise HCADIngestError(
                f"HCAD archive member is not rooted at the archive top level: "
                f"{member.filename!r}"
            )
        if not basename.casefold().endswith(".txt"):
            continue
        table = Path(basename).stem
        if table in members:
            raise HCADIngestError(
                f"HCAD archive has duplicate table member {table!r}"
            )
        members[table] = member
    return members


def _selected_tables(
    args: argparse.Namespace,
    members: Mapping[str, zipfile.ZipInfo],
) -> tuple[str, ...]:
    requested = tuple(args.tables or ())
    if requested:
        missing = [table for table in requested if table not in members]
        if missing:
            raise HCADIngestError(
                "selected HCAD tables are absent from the archive: "
                + ", ".join(sorted(missing))
            )
        unknown = [table for table in requested if table not in TABLE_SPECS]
        if unknown:
            raise HCADIngestError(
                "selected HCAD tables have no verified schema: "
                + ", ".join(sorted(unknown))
            )
        return tuple(table for table in TABLE_ORDER if table in requested)
    selected = tuple(table for table in TABLE_ORDER if table in members)
    if not selected:
        raise HCADIngestError(
            "archive contains no HCAD table with a verified schema"
        )
    return selected


def _artifact_role(tables: Sequence[str]) -> str:
    roles = {TABLE_SPECS[table].artifact_role for table in tables}
    if len(roles) != 1:
        raise HCADIngestError(
            "selected HCAD tables span more than one official artifact family"
        )
    return next(iter(roles))


def _reader(
    archive: zipfile.ZipFile,
    member: zipfile.ZipInfo,
    *,
    table: str,
) -> tuple[io.TextIOWrapper, csv.DictReader, list[str]]:
    binary = archive.open(member)
    text = io.TextIOWrapper(
        binary,
        encoding=SOURCE_ENCODING,
        errors="strict",
        newline="",
    )
    reader = csv.DictReader(text, delimiter="\t")
    header = [str(field) for field in (reader.fieldnames or ())]
    if not header or any(not field for field in header):
        text.close()
        raise HCADIngestError(f"{table}.txt has an empty or blank header")
    if len(header) != len(set(header)):
        text.close()
        raise HCADIngestError(f"{table}.txt has duplicate header fields")
    missing = [
        field for field in TABLE_SPECS[table].header if field not in set(header)
    ]
    if missing:
        text.close()
        raise HCADIngestError(
            f"{table}.txt lacks live-verified columns: "
            + ", ".join(missing)
        )
    return text, reader, header


def _upsert_jurisdiction(db: sqlite3.Connection) -> None:
    db.execute(
        """
        INSERT INTO jurisdiction(
            geoid, name, jurisdiction_type, parent_geoid, state_code, county_code
        ) VALUES ('48', 'Texas', 'state', NULL, 'TX', NULL)
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
        ) VALUES ('48201', 'Harris County', 'county', '48', 'TX', '201')
        ON CONFLICT(geoid) DO UPDATE SET
            name=excluded.name,
            jurisdiction_type=excluded.jurisdiction_type,
            parent_geoid=excluded.parent_geoid,
            state_code=excluded.state_code,
            county_code=excluded.county_code
        """
    )


def _upsert_observation(
    db: sqlite3.Connection,
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
    existing = db.execute(
        """
        SELECT observation_id
        FROM source_observation
        WHERE source_id=? AND source_native_id=? AND record_kind=?
          AND raw_artifact_sha256=? AND schema_fingerprint=? AND raw_json=?
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
    if existing is not None:
        observation_id = int(existing["observation_id"])
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
    db: sqlite3.Connection,
    *,
    account: str,
    tax_year: str,
    observation_id: int,
    raw: Mapping[str, Any],
    authoritative: bool,
) -> int:
    db.execute(
        """
        INSERT INTO parcel_snapshot(
            source_id, jurisdiction_geoid, native_parcel_id, roll_year,
            effective_from, source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        (
            SOURCE_ID,
            JURISDICTION_GEOID,
            account,
            tax_year,
            tax_year,
            tax_year,
            observation_id,
            canonical_json(raw),
        ),
    )
    if authoritative:
        db.execute(
            """
            UPDATE parcel_snapshot
            SET effective_from=?, source_good_through=?,
                observation_id=?, raw_json=?
            WHERE source_id=? AND jurisdiction_geoid=?
              AND native_parcel_id=? AND roll_year=?
            """,
            (
                tax_year,
                tax_year,
                observation_id,
                canonical_json(raw),
                SOURCE_ID,
                JURISDICTION_GEOID,
                account,
                tax_year,
            ),
        )
    row = db.execute(
        """
        SELECT parcel_id
        FROM parcel_snapshot
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_parcel_id=? AND roll_year=?
        """,
        (SOURCE_ID, JURISDICTION_GEOID, account, tax_year),
    ).fetchone()
    assert row is not None
    return int(row["parcel_id"])


def _upsert_address(
    db: sqlite3.Connection,
    *,
    parcel_id: int,
    role: str,
    raw_address: str | None,
    city: str | None,
    state: str | None,
    postal_code: str | None,
    country: str | None,
    effective_from: str,
) -> int:
    raw = _text(raw_address)
    if raw is None:
        return 0
    normalized = raw.upper()
    country_value = _text(country) or "US"
    existing = db.execute(
        """
        SELECT address_id
        FROM parcel_address
        WHERE parcel_id=? AND address_role=? AND source_id=?
          AND effective_from=? AND effective_to IS NULL
          AND COALESCE(normalized_address, '')=?
          AND COALESCE(city, '')=?
          AND COALESCE(state, '')=?
          AND COALESCE(postal_code, '')=?
          AND COALESCE(country, 'US')=?
        LIMIT 1
        """,
        (
            parcel_id,
            role,
            SOURCE_ID,
            effective_from,
            normalized,
            _text(city) or "",
            _text(state) or "",
            _text(postal_code) or "",
            country_value,
        ),
    ).fetchone()
    if existing is not None:
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
            raw,
            normalized,
            _text(city),
            _text(state),
            _text(postal_code),
            country_value,
            SOURCE_ID,
            effective_from,
        ),
    )
    return 1


def _upsert_owner(
    db: sqlite3.Connection,
    *,
    parcel_id: int,
    raw_name: Any,
    effective_from: str,
    observation_id: int,
    evidence_ref: str,
) -> int:
    name = _text(raw_name)
    if name is None:
        return 0
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
            observation_id=excluded.observation_id,
            evidence_ref=excluded.evidence_ref,
            source_quote=excluded.source_quote
        """,
        (
            parcel_id,
            SOURCE_ID,
            name,
            name.upper(),
            effective_from,
            observation_id,
            evidence_ref,
            name,
        ),
    )
    return 1


def _upsert_assessment(
    db: sqlite3.Connection,
    *,
    parcel_id: int,
    tax_year: str,
    row: Mapping[str, Any],
    observation_id: int,
    normalized: Mapping[str, Any],
) -> int:
    assessment_raw = {
        **normalized,
        "assessment_projection": {
            "land_value_field": "land_val",
            "improvement_value_fields": [
                "bld_val",
                "x_features_val",
            ],
            "improvement_value_method": (
                "sum_of_published_building_and_extra_feature_values"
            ),
            "total_value_field": "tot_appr_val",
            "market_value_field": "tot_mkt_val",
            "assessed_value_field": "assessed_val",
            "currency": "USD",
        },
    }
    db.execute(
        """
        INSERT INTO assessment(
            parcel_id, source_id, tax_year, land_value_minor,
            improvement_value_minor, total_value_minor, market_value_minor,
            assessed_value_minor, currency, assessment_class,
            source_good_through, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
        ON CONFLICT(parcel_id, source_id, tax_year) DO UPDATE SET
            land_value_minor=excluded.land_value_minor,
            improvement_value_minor=excluded.improvement_value_minor,
            total_value_minor=excluded.total_value_minor,
            market_value_minor=excluded.market_value_minor,
            assessed_value_minor=excluded.assessed_value_minor,
            assessment_class=excluded.assessment_class,
            source_good_through=excluded.source_good_through,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            parcel_id,
            SOURCE_ID,
            tax_year,
            _minor_units(row.get("land_val")),
            _sum_minor(row.get("bld_val"), row.get("x_features_val")),
            _minor_units(row.get("tot_appr_val")),
            _minor_units(row.get("tot_mkt_val")),
            _minor_units(row.get("assessed_val")),
            _text(row.get("state_class")),
            tax_year,
            observation_id,
            canonical_json(assessment_raw),
        ),
    )
    return 1


def _upsert_sale_reference(
    db: sqlite3.Connection,
    *,
    parcel_id: int,
    native_sale_id: str,
    sale_date: str | None,
    observation_id: int,
    normalized: Mapping[str, Any],
) -> int:
    derivation = "hcad_appraisal_deed_reference"
    raw_json = canonical_json(normalized)
    existing = db.execute(
        """
        SELECT sale_event_id
        FROM sale_event
        WHERE parcel_id=? AND source_id=? AND native_sale_id=?
          AND COALESCE(sale_date, '')=COALESCE(?, '')
          AND derivation=?
        LIMIT 1
        """,
        (
            parcel_id,
            SOURCE_ID,
            native_sale_id,
            sale_date,
            derivation,
        ),
    ).fetchone()
    if existing is None:
        db.execute(
            """
            INSERT INTO sale_event(
                parcel_id, source_id, native_sale_id, sale_date,
                currency, derivation, instrument_id, observation_id, raw_json
            ) VALUES (?, ?, ?, ?, 'USD', ?, NULL, ?, ?)
            """,
            (
                parcel_id,
                SOURCE_ID,
                native_sale_id,
                sale_date,
                derivation,
                observation_id,
                raw_json,
            ),
        )
    else:
        db.execute(
            """
            UPDATE sale_event
            SET observation_id=?, raw_json=?, instrument_id=NULL
            WHERE sale_event_id=?
            """,
            (observation_id, raw_json, int(existing["sale_event_id"])),
        )
    return 1


def _upsert_property_event(
    db: sqlite3.Connection,
    *,
    native_event_id: str,
    source_record_id: str,
    record_kind: str,
    event_type: str | None,
    description: str | None,
    status: str | None,
    submitted_date: str | None,
    address: str | None,
    account: str,
    observation_id: int,
    raw: Mapping[str, Any],
    parcel_id: int,
    evidence_ref: str,
) -> int:
    db.execute(
        """
        INSERT INTO property_event(
            source_id, jurisdiction_geoid, native_event_id, source_record_id,
            record_kind, event_type, description, status, submitted_date,
            address_raw, map_taxlot_candidate, observation_id, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(
            source_id, jurisdiction_geoid, native_event_id, source_record_id
        ) DO UPDATE SET
            record_kind=excluded.record_kind,
            event_type=excluded.event_type,
            description=excluded.description,
            status=excluded.status,
            submitted_date=excluded.submitted_date,
            address_raw=excluded.address_raw,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            observation_id=excluded.observation_id,
            raw_json=excluded.raw_json
        """,
        (
            SOURCE_ID,
            JURISDICTION_GEOID,
            native_event_id,
            source_record_id,
            record_kind,
            event_type,
            description,
            status,
            submitted_date,
            address,
            account,
            observation_id,
            canonical_json(raw),
        ),
    )
    event = db.execute(
        """
        SELECT event_id
        FROM property_event
        WHERE source_id=? AND jurisdiction_geoid=?
          AND native_event_id=? AND source_record_id=?
        """,
        (
            SOURCE_ID,
            JURISDICTION_GEOID,
            native_event_id,
            source_record_id,
        ),
    ).fetchone()
    assert event is not None
    db.execute(
        """
        INSERT INTO property_event_parcel_link(
            event_id, parcel_id, map_taxlot_candidate,
            link_method, link_confidence, evidence_json
        ) VALUES (?, ?, ?, 'hcad_account_exact', 1.0, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            parcel_id=excluded.parcel_id,
            map_taxlot_candidate=excluded.map_taxlot_candidate,
            link_method=excluded.link_method,
            link_confidence=excluded.link_confidence,
            evidence_json=excluded.evidence_json
        """,
        (
            int(event["event_id"]),
            parcel_id,
            account,
            canonical_json({"evidence_ref": evidence_ref}),
        ),
    )
    return 1


def _permit_address(row: Mapping[str, Any]) -> str | None:
    fields = (
        "site_num",
        "site_pfx",
        "site_str",
        "site_tp",
        "site_sfx",
        "site_apt",
    )
    return _text(" ".join(str(row.get(field) or "") for field in fields))


def _real_account_projection(
    db: sqlite3.Connection,
    *,
    row: Mapping[str, Any],
    normalized: Mapping[str, Any],
    observation_id: int,
    account: str,
    tax_year: str,
    evidence_ref: str,
) -> dict[str, int]:
    row_year = _text(row.get("yr"))
    if row_year and row_year != tax_year:
        raise HCADIngestError(
            f"real_acct row year {row_year!r} conflicts with --tax-year {tax_year}"
        )
    parcel_id = _upsert_parcel(
        db,
        account=account,
        tax_year=tax_year,
        observation_id=observation_id,
        raw=normalized,
        authoritative=True,
    )
    mailing_lines = [
        value
        for value in (
            _text(row.get("mail_addr_1")),
            _text(row.get("mail_addr_2")),
        )
        if value
    ]
    addresses = _upsert_address(
        db,
        parcel_id=parcel_id,
        role="mailing",
        raw_address=" ".join(mailing_lines) or None,
        city=_text(row.get("mail_city")),
        state=_text(row.get("mail_state")),
        postal_code=_text(row.get("mail_zip")),
        country=_text(row.get("mail_country")),
        effective_from=tax_year,
    )
    addresses += _upsert_address(
        db,
        parcel_id=parcel_id,
        role="situs",
        raw_address=_text(row.get("site_addr_1")),
        city=_text(row.get("site_addr_2")),
        state="TX",
        postal_code=_text(row.get("site_addr_3")),
        country="US",
        effective_from=tax_year,
    )
    return {
        "parcels_projected": 1,
        "owners_projected": _upsert_owner(
            db,
            parcel_id=parcel_id,
            raw_name=row.get("mailto"),
            effective_from=tax_year,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        ),
        "addresses_projected": addresses,
        "assessments_projected": _upsert_assessment(
            db,
            parcel_id=parcel_id,
            tax_year=tax_year,
            row=row,
            observation_id=observation_id,
            normalized=normalized,
        ),
    }


def _project_row(
    db: sqlite3.Connection,
    *,
    table: str,
    row: Mapping[str, Any],
    normalized: Mapping[str, Any],
    observation_id: int,
    row_digest: str,
    duplicate_ordinal: int,
    tax_year: str,
    evidence_ref: str,
) -> dict[str, int]:
    projection = TABLE_SPECS[table].projection
    account = _text(row.get("acct"))
    if projection == "secondary" and account is None:
        return {"secondary_rows_preserved": 1}
    if account is None:
        return {"unresolved_rows_preserved": 1}
    if projection == "real_account":
        return _real_account_projection(
            db,
            row=row,
            normalized=normalized,
            observation_id=observation_id,
            account=account,
            tax_year=tax_year,
            evidence_ref=evidence_ref,
        )

    parcel_id = _upsert_parcel(
        db,
        account=account,
        tax_year=tax_year,
        observation_id=observation_id,
        raw=normalized,
        authoritative=False,
    )
    counts = {"parcels_projected": 1}

    if projection == "owner":
        counts["owners_projected"] = _upsert_owner(
            db,
            parcel_id=parcel_id,
            raw_name=row.get("name"),
            effective_from=tax_year,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        )
    elif projection == "ownership_history":
        effective_from = _date(row.get("purchase_date")) or ""
        counts["owners_projected"] = _upsert_owner(
            db,
            parcel_id=parcel_id,
            raw_name=row.get("name"),
            effective_from=effective_from,
            observation_id=observation_id,
            evidence_ref=evidence_ref,
        )
        counts["addresses_projected"] = _upsert_address(
            db,
            parcel_id=parcel_id,
            role="situs",
            raw_address=_text(row.get("site_address")),
            city=None,
            state="TX",
            postal_code=None,
            country="US",
            effective_from=effective_from,
        )
        counts["ownership_history_rows_projected"] = 1
    elif projection == "deed_reference":
        deed_id = _text(row.get("deed_id"))
        clerk_year = _text(row.get("clerk_yr"))
        clerk_id = _text(row.get("clerk_id"))
        deed_normalized = {
            **normalized,
            "appraisal_deed_observation": {
                "deed_id": deed_id,
                "date_of_sale_raw": _text(row.get("dos")),
                "date_of_sale": _date(row.get("dos")),
            },
            "instrument_reference": {
                "clerk_year": clerk_year,
                "clerk_id": clerk_id,
                "deed_id": deed_id,
                "reference_scope": "hcad_appraisal_observation",
                "recorded_title_evidence": False,
            },
        }
        native_sale_id = (
            f"deed:{deed_id}"
            if deed_id
            else f"deed-row:{row_digest[:20]}:{duplicate_ordinal}"
        )
        counts["sale_references_projected"] = _upsert_sale_reference(
            db,
            parcel_id=parcel_id,
            native_sale_id=native_sale_id,
            sale_date=_date(row.get("dos")),
            observation_id=observation_id,
            normalized=deed_normalized,
        )
        counts["clerk_pivots_preserved"] = int(bool(clerk_year or clerk_id))
        counts["recorded_instruments_projected"] = 0
    elif projection == "permit":
        permit_id = _text(row.get("id")) or row_digest[:20]
        counts["permits_projected"] = _upsert_property_event(
            db,
            native_event_id=f"permit:{permit_id}",
            source_record_id=f"account:{account}",
            record_kind="hcad_permit",
            event_type=_text(row.get("permit_type")),
            description=_text(row.get("dscr"))
            or _text(row.get("permit_tp_descr")),
            status=_text(row.get("status")),
            submitted_date=_date(row.get("issue_date")),
            address=_permit_address(row),
            account=account,
            observation_id=observation_id,
            raw=normalized,
            parcel_id=parcel_id,
            evidence_ref=evidence_ref,
        )
    elif projection == "account_relation":
        related = _text(row.get("related_acct"))
        native_event_id = (
            "account-relation:"
            + ":".join(
                value
                for value in (
                    account,
                    _text(row.get("tp")) or "unknown",
                    related or "unresolved",
                    row_digest[:12],
                )
            )
        )
        counts["account_relations_projected"] = _upsert_property_event(
            db,
            native_event_id=native_event_id,
            source_record_id=f"account:{account}",
            record_kind="hcad_account_relation",
            event_type=_text(row.get("tp")),
            description=_text(row.get("dscr")),
            status=None,
            submitted_date=None,
            address=None,
            account=account,
            observation_id=observation_id,
            raw=normalized,
            parcel_id=parcel_id,
            evidence_ref=evidence_ref,
        )
        if related:
            _upsert_parcel(
                db,
                account=related,
                tax_year=tax_year,
                observation_id=observation_id,
                raw=normalized,
                authoritative=False,
            )
            counts["related_accounts_resolved"] = 1
        else:
            counts["unresolved_rows_preserved"] = 1
    elif projection == "building_detail":
        counts["building_detail_rows_preserved"] = 1
    elif projection == "land_detail":
        counts["land_detail_rows_preserved"] = 1
    else:
        counts["secondary_rows_preserved"] = 1
    return counts


COUNT_KEYS = (
    "rows_seen",
    "rows_skipped_before_checkpoint",
    "rows_processed",
    "observations_inserted",
    "observations_reused",
    "parcels_projected",
    "owners_projected",
    "ownership_history_rows_projected",
    "addresses_projected",
    "assessments_projected",
    "sale_references_projected",
    "clerk_pivots_preserved",
    "recorded_instruments_projected",
    "permits_projected",
    "account_relations_projected",
    "related_accounts_resolved",
    "building_detail_rows_preserved",
    "land_detail_rows_preserved",
    "secondary_rows_preserved",
    "unresolved_rows_preserved",
)


def _empty_counts() -> dict[str, int]:
    return {key: 0 for key in COUNT_KEYS}


def _add_counts(target: dict[str, int], delta: Mapping[str, int]) -> None:
    for key, value in delta.items():
        target[key] = target.get(key, 0) + int(value)


def _archive_observation(
    db: sqlite3.Connection,
    *,
    release: Mapping[str, Any],
    archive_path: Path,
    artifact_sha256: str,
    source_url: str | None,
    retrieved_at: str,
    schema_fingerprint: str,
    schema: Mapping[str, Any],
    members: Sequence[Mapping[str, Any]],
) -> tuple[int, bool]:
    raw = {
        "record_kind": "hcad_cama_archive",
        "release": dict(release),
        "artifact": {
            "path": str(archive_path),
            "filename": archive_path.name,
            "size": archive_path.stat().st_size,
            "sha256": artifact_sha256,
        },
        "members": list(members),
        "schema": dict(schema),
        "codebook_url": CODEBOOK_URL,
    }
    return _upsert_observation(
        db,
        source_native_id=(
            f"release:{release['release_id']}:artifact:"
            f"{archive_path.name}:{artifact_sha256}"
        ),
        record_kind="hcad_cama_archive",
        source_url=source_url,
        retrieved_at=retrieved_at,
        schema_fingerprint=schema_fingerprint,
        artifact_path=str(archive_path),
        artifact_sha256=artifact_sha256,
        raw=raw,
    )


def execute(args: argparse.Namespace) -> dict[str, Any]:
    """Validate and ingest one caller-selected HCAD CAMA archive."""

    csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.is_file():
        raise HCADIngestError(f"archive does not exist: {archive_path}")
    artifact_sha256 = _sha256_path(archive_path)
    if args.expected_sha256 and (
        artifact_sha256.casefold() != args.expected_sha256.casefold()
    ):
        raise HCADIngestError(
            "archive SHA-256 does not match --expected-sha256"
        )
    retrieved_at = _artifact_timestamp(archive_path, args.retrieved_at)
    tax_year = str(args.tax_year)

    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as error:
        raise HCADIngestError(
            f"archive is not a readable ZIP: {archive_path}"
        ) from error

    with archive:
        members = _member_index(archive)
        selected_tables = _selected_tables(args, members)
        artifact_role = _artifact_role(selected_tables)
        if (
            args.artifact_role
            and args.artifact_role != artifact_role
        ):
            raise HCADIngestError(
                "archive members conflict with --artifact-role"
            )

        headers: dict[str, list[str]] = {}
        table_schemas: dict[str, dict[str, Any]] = {}
        for table in selected_tables:
            text, _table_reader, header = _reader(
                archive,
                members[table],
                table=table,
            )
            text.close()
            headers[table] = header
            table_schemas[table] = {
                "member": members[table].filename,
                "member_crc32": f"{members[table].CRC:08x}",
                "member_size": members[table].file_size,
                "header_fields": header,
                "header_field_count": len(header),
                "header_fingerprint": sha256_fingerprint(header),
                "required_live_verified_fields": list(
                    TABLE_SPECS[table].header
                ),
                "projection": TABLE_SPECS[table].projection,
                "additive_columns_accepted": True,
            }

        release_id = args.release_id or (
            f"{tax_year}:{args.certification_status}:"
            f"{artifact_role}:{artifact_sha256[:16]}"
        )
        release = {
            "release_id": release_id,
            "tax_year": args.tax_year,
            "certification_status": args.certification_status,
            "artifact_role": artifact_role,
            "artifact_filename": archive_path.name,
            "artifact_sha256": artifact_sha256,
            "manifest_fingerprint": args.manifest_fingerprint,
        }
        release["release_identity_sha256"] = sha256_fingerprint(release)
        schema = {
            "format": "zip_of_cp437_tab_delimited_text",
            "source_encoding": SOURCE_ENCODING,
            "encoding_verification": (
                "All bytes in the fully downloaded 2026 real-account, "
                "ownership-history, and building/land artifacts were decoded "
                "with CP437; observed literals include MUÑOZ, SEÑOR, and Ü."
            ),
            "artifact_role": artifact_role,
            "selected_tables": list(selected_tables),
            "tables": table_schemas,
            "codebook_url": CODEBOOK_URL,
            "ownership_history_key_note": (
                "The live 2026 member has acct, purchase_date, name, and "
                "site_address; no ln_num column is assumed."
            ),
        }
        schema_fingerprint = sha256_fingerprint(schema)
        archive_members = _zip_members(archive)

        counts = _empty_counts()
        table_counts = {table: _empty_counts() for table in selected_tables}
        db = connect_property(args.property_db)
        try:
            _upsert_jurisdiction(db)
            archive_observation_id, archive_observation_inserted = (
                _archive_observation(
                    db,
                    release=release,
                    archive_path=archive_path,
                    artifact_sha256=artifact_sha256,
                    source_url=args.source_url,
                    retrieved_at=retrieved_at,
                    schema_fingerprint=schema_fingerprint,
                    schema=schema,
                    members=archive_members,
                )
            )
            db.commit()

            exhausted = True
            global_row_index = 0
            pending = 0
            stop = False
            next_checkpoint: dict[str, Any] | None = None
            for table in selected_tables:
                text, reader, _header = _reader(
                    archive,
                    members[table],
                    table=table,
                )
                duplicate_ordinals: dict[str, int] = {}
                try:
                    for table_row_index, source_row in enumerate(reader):
                        if None in source_row:
                            raise HCADIngestError(
                                f"{table}.txt row {table_row_index + 1} has "
                                "more fields than its header"
                            )
                        raw_fields = {
                            str(key): (
                                value
                                if value is None or isinstance(value, str)
                                else str(value)
                            )
                            for key, value in source_row.items()
                        }
                        row_digest = hashlib.sha256(
                            canonical_json(raw_fields).encode("utf-8")
                        ).hexdigest()
                        duplicate_ordinal = duplicate_ordinals.get(row_digest, 0)
                        duplicate_ordinals[row_digest] = duplicate_ordinal + 1
                        counts["rows_seen"] += 1
                        table_counts[table]["rows_seen"] += 1

                        if global_row_index < args.start_row:
                            counts["rows_skipped_before_checkpoint"] += 1
                            table_counts[table][
                                "rows_skipped_before_checkpoint"
                            ] += 1
                            global_row_index += 1
                            continue
                        if (
                            args.limit is not None
                            and counts["rows_processed"] >= args.limit
                        ):
                            exhausted = False
                            stop = True
                            next_checkpoint = {
                                "global_row": global_row_index,
                                "table": table,
                                "table_row": table_row_index,
                            }
                            break

                        source_native_id = (
                            f"{release_id}:{artifact_sha256}:{table}:"
                            f"{table_row_index + 1}:{row_digest}:"
                            f"{duplicate_ordinal}"
                        )
                        evidence_ref = canonical_property_ref(
                            SOURCE_ID,
                            JURISDICTION_GEOID,
                            table,
                            source_native_id,
                        )
                        normalized = {
                            "record_kind": f"hcad_{table}_row",
                            "release": release,
                            "artifact": {
                                "filename": archive_path.name,
                                "sha256": artifact_sha256,
                                "role": artifact_role,
                            },
                            "table": table,
                            "member": members[table].filename,
                            "source_row_number": table_row_index + 1,
                            "global_row_index": global_row_index,
                            "row_sha256": row_digest,
                            "identical_row_ordinal": duplicate_ordinal,
                            "canonical_ref": evidence_ref,
                            "raw_fields": raw_fields,
                        }
                        observation_id, inserted = _upsert_observation(
                            db,
                            source_native_id=source_native_id,
                            record_kind=f"hcad_{table}_row",
                            source_url=args.source_url,
                            retrieved_at=retrieved_at,
                            schema_fingerprint=table_schemas[table][
                                "header_fingerprint"
                            ],
                            artifact_path=str(archive_path),
                            artifact_sha256=artifact_sha256,
                            raw=normalized,
                        )
                        delta = _project_row(
                            db,
                            table=table,
                            row=raw_fields,
                            normalized=normalized,
                            observation_id=observation_id,
                            row_digest=row_digest,
                            duplicate_ordinal=duplicate_ordinal,
                            tax_year=tax_year,
                            evidence_ref=evidence_ref,
                        )
                        base_delta = {
                            "rows_processed": 1,
                            (
                                "observations_inserted"
                                if inserted
                                else "observations_reused"
                            ): 1,
                        }
                        _add_counts(counts, base_delta)
                        _add_counts(counts, delta)
                        _add_counts(table_counts[table], base_delta)
                        _add_counts(table_counts[table], delta)
                        global_row_index += 1
                        pending += 1
                        if pending >= args.batch_size:
                            db.commit()
                            pending = 0
                finally:
                    text.close()
                if stop:
                    break
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return {
        "schema_version": "hcad-cama-archive-ingest/1.0",
        "status": "ok",
        "source_id": SOURCE_ID,
        "jurisdiction_geoid": JURISDICTION_GEOID,
        "release": release,
        "artifact": {
            "path": str(archive_path),
            "filename": archive_path.name,
            "size": archive_path.stat().st_size,
            "sha256": artifact_sha256,
        },
        "archive_observation_id": archive_observation_id,
        "archive_observation_inserted": archive_observation_inserted,
        "schema": schema,
        "schema_fingerprint": schema_fingerprint,
        "counts": counts,
        "table_counts": table_counts,
        "start_row": args.start_row,
        "caller_limit": args.limit,
        "next_checkpoint": next_checkpoint,
        "next_checkpoint_row": (
            None if exhausted else int(next_checkpoint["global_row"])
        ),
        "exhausted": exhausted,
        "property_db": str(Path(args.property_db)),
        "projection_notes": {
            "deeds": (
                "HCAD deed rows are appraisal observations and Clerk pivots; "
                "recorded_instruments_projected remains zero."
            ),
            "building_and_land": (
                "Raw detail rows are preserved as source observations joined "
                "by the HCAD account; the shared schema has no lossy generic "
                "building or land-detail table."
            ),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Stream a verified HCAD CAMA ZIP into the property sidecar"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    ingest = sub.add_parser("ingest", help="Validate and ingest one HCAD ZIP")
    ingest.add_argument("--archive", required=True)
    ingest.add_argument("--tax-year", type=int, required=True)
    ingest.add_argument("--property-db", default=str(DEFAULT_PROPERTY_DB))
    ingest.add_argument(
        "--table",
        dest="tables",
        action="append",
        choices=TABLE_ORDER,
        help=(
            "Selected member table; repeat for several. The default streams "
            "every verified table present in the artifact."
        ),
    )
    ingest.add_argument(
        "--artifact-role",
        choices=(
            "real_acct_owner",
            "real_acct_ownership_history",
            "real_building_land",
        ),
        help="Optional expected artifact family",
    )
    ingest.add_argument("--release-id")
    ingest.add_argument(
        "--certification-status",
        choices=("preliminary", "certified", "unknown"),
        default="unknown",
    )
    ingest.add_argument("--manifest-fingerprint")
    ingest.add_argument("--expected-sha256")
    ingest.add_argument("--source-url")
    ingest.add_argument("--retrieved-at")
    ingest.add_argument(
        "--start-row",
        type=int,
        default=0,
        help="Caller-selected zero-based checkpoint across selected tables",
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
    if args.tax_year <= 0:
        parser.error("--tax-year must be positive")
    if args.start_row < 0:
        parser.error("--start-row must not be negative")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    for field in ("expected_sha256", "manifest_fingerprint"):
        value = getattr(args, field)
        if value and not SHA256_RE.fullmatch(value):
            parser.error(
                f"--{field.replace('_', '-')} must be a SHA-256 hex digest"
            )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    _validate_args(parser, args)
    try:
        payload = execute(args)
    except (
        HCADIngestError,
        OSError,
        UnicodeError,
        csv.Error,
        sqlite3.Error,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    if write_output(
        payload,
        args,
        summary=(
            "HCAD CAMA archive ingest "
            f"({payload['counts']['rows_processed']} rows)"
        ),
    ):
        return
    print(json.dumps(payload, indent=2 if args.json_out else None, sort_keys=True))


if __name__ == "__main__":
    main()
