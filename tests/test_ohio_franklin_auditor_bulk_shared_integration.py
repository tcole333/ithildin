from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_franklin_auditor_bulk as franklin
from tools import query_ohio_statewide_parcels as ogrip
from tools import query_property
from tools.ingest_property_records import (
    PropertyIngestError,
    ingest_property_envelope,
)
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = franklin.SOURCE_ID
OGRIP_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_statewide_parcels"
    / "features.json"
)


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_translate_release_artifact_and_local_row_selectors(
    tmp_path: Path,
) -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    artifact = tmp_path / "daily.xlsx"
    daily = routes["search"].translate(
        _shared_args(
            "search",
            "NEW OWNER",
            "--source",
            SOURCE_ID,
            "--county",
            "Franklin County",
            "--artifact-path",
            str(artifact),
            "--artifact-source-url",
            "https://apps.franklincountyauditor.com/Daily_Conveyances/DailyConveyances_20260723.xlsx",
            "--dataset-type",
            "daily-conveyance",
            "--collection-id",
            "daily-conveyance-2026-07-01-to-2026-07-23",
            "--from-date",
            "2026-07-01",
            "--to-date",
            "2026-07-23",
            "--limit",
            "17",
        ),
        routes["search"].adapter_command,
    )
    historical = routes["releases"].translate(
        _shared_args(
            "releases",
            "1997",
            "--source",
            SOURCE_ID,
            "--dataset-type",
            "parcel-csv",
        ),
        routes["releases"].adapter_command,
    )
    manifest = routes["manifest"].translate(
        _shared_args(
            "manifest",
            "current",
            "--source",
            SOURCE_ID,
            "--dataset-type",
            "gis",
            "--collection-id",
            "gis-current-2026-07-29",
        ),
        routes["manifest"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "parcel",
        "releases",
        "manifest",
        "download",
        "discovery",
        "probe",
    }
    assert daily.command == "rows"
    assert daily.artifact == artifact
    assert daily.record_family == "daily-conveyance"
    assert daily.release_id.endswith("2026-07-23")
    assert daily.release_date == "2026-07-23"
    assert daily.source_url == (
        "https://apps.franklincountyauditor.com/Daily_Conveyances/"
        "DailyConveyances_20260723.xlsx"
    )
    assert daily.query == "NEW OWNER"
    assert daily.limit == 17
    assert historical.command == "releases"
    assert historical.family == "parcel-csv"
    assert historical.year == 1997
    assert manifest.command == "artifacts"
    assert manifest.family == "gis-shapefiles"
    assert manifest.release == "gis-current-2026-07-29"


def test_shared_routes_reject_cross_county_scope() -> None:
    route = query_property.LIVE_ROUTES[SOURCE_ID]["parcel"]
    with pytest.raises(ValueError, match="does not serve county"):
        route.translate(
            _shared_args(
                "parcel",
                "010-000001-00",
                "--source",
                SOURCE_ID,
                "--county",
                "Licking",
                "--artifact-path",
                "/tmp/parcel.csv",
                "--dataset-type",
                "parcel",
                "--collection-id",
                "parcel-csv-1997-01",
            ),
            route.adapter_command,
        )


def test_catalog_census_monitor_and_citation_share_one_source_contract(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    manifest = next(
        source for source in config["sources"] if source["source_id"] == SOURCE_ID
    )
    associations = {
        (item["jurisdiction_geoid"], item["role"])
        for item in manifest["census_associations"]
    }

    assert manifest["source_status"] == "active"
    assert manifest["jurisdiction_geoids"] == ["39049"]
    shared = next(
        capability
        for capability in manifest["capabilities"]
        if capability["name"] == "query_shared_property_records"
    )
    assert shared["details"]["local_row_selection"] == {
        "artifact": "--artifact-path",
        "artifact_source_url": "--artifact-source-url",
        "record_family": "--dataset-type",
        "release_identity": "--collection-id",
    }
    assert associations == {
        ("39049", "assessment_roll"),
        ("39049", "tax_collection"),
        ("39049", "parcel_geometry"),
    }

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog_manifest = PublicRecordsCatalog(catalog_path).show_source(SOURCE_ID)[
        "current_manifest"
    ]
    assert catalog_manifest["record_identity_source_id"] == SOURCE_ID

    census = PublicRecordsCensus(catalog_path)
    for role in ("assessment_roll", "tax_collection", "parcel_geometry"):
        target = census.list_targets(
            state="OH",
            domain="property",
            role=role,
        )
        franklin_target = next(
            item for item in target if item["geoid"] == "39049"
        )
        assert SOURCE_ID in franklin_target["source_ids"]

    handler = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert handler.handler is public_records_monitor.probe_ohio_franklin_auditor_bulk
    assert handler.expected_requests == 9
    assert handler.sample_bytes == 64

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == franklin.DATA_LANDING_URL


def _row_record(
    *,
    family: str,
    release_id: str,
    artifact_sha256: str,
    parsed_fields: dict[str, Any],
    row_number: int,
    release_date: str | None = None,
) -> dict[str, Any]:
    source_fields = {
        key: value
        for key, value in parsed_fields.items()
        if key not in {"record_family", "source_sale_flags"}
    }
    occurrence = (
        f"{release_id}:{artifact_sha256}:fixture-{family}:row:{row_number}"
    )
    native_id = hashlib.sha256(occurrence.encode("utf-8")).hexdigest()
    evidence_ref = f"BULK:{SOURCE_ID}/row/{native_id}"
    parcel_id = parsed_fields.get("parcel_id")
    return {
        "source_id": SOURCE_ID,
        "record_kind": f"{family.replace('-', '_')}_row_observation",
        "canonical_ref": evidence_ref,
        "evidence_ref": evidence_ref,
        "native_document_id": native_id,
        "native_occurrence": occurrence,
        "release_id": release_id,
        "release_date": release_date,
        "artifact_filename": f"fixture-{family}.xlsx",
        "artifact_sha256": artifact_sha256,
        "artifact_size": 23,
        "artifact_source_url": "https://apps.franklincountyauditor.com/fixture",
        "worksheet": "Sheet1",
        "source_row_number": row_number,
        "header_row_number": 1,
        "raw_headers": list(source_fields),
        "raw_values": list(source_fields.values()),
        "source_fields": source_fields,
        "parsed_fields": {"record_family": family, **parsed_fields},
        "join_candidates": {
            "county_geoid": "39049",
            "parcel_id": parcel_id,
            "normalized_parcel_id": (
                "".join(character for character in str(parcel_id) if character.isalnum())
                if parcel_id
                else None
            ),
        },
        "same_authority_lineage": (
            "us-oh-franklin-county-auditor-property"
        ),
    }


def _envelope(
    records: list[dict[str, Any]],
    *,
    artifact_path: Path,
    retrieved_at: str = "2026-07-31T12:00:00Z",
) -> dict[str, Any]:
    first = records[0]
    family = first.get("parsed_fields", {}).get("record_family", "parcel")
    release_id = first.get("release_id", "fixture-release")
    args = franklin.build_parser().parse_args(
        [
            "rows",
            str(artifact_path),
            "--record-family",
            family,
            "--release-id",
            release_id,
        ]
    )
    return PublicRecordsResult.success(
        franklin.build_query(args),
        records,
        raw_artifact_refs=(str(artifact_path),),
        retrieved_at=retrieved_at,
    ).to_dict()


def _ogrip_envelope(parcel: str) -> dict[str, Any]:
    feature = deepcopy(
        json.loads(OGRIP_FIXTURE.read_text(encoding="utf-8"))["features"][0]
    )
    feature["attributes"].update(
        {
            "LocalParcelID": parcel,
            "StateParcelID": f"39049-{parcel}",
        }
    )
    record = ogrip._normalize_feature(
        feature,
        schema_fingerprint="a" * 64,
        geometry_requested=False,
    )
    args = ogrip.build_parser().parse_args(["parcel", f"39049-{parcel}"])
    return PublicRecordsResult.success(
        ogrip._build_query(args),
        [record],
        retrieved_at="2026-07-20T12:00:00Z",
    ).to_dict()


def test_ingestion_preserves_bulk_lineage_and_projects_only_supported_facts(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "auditor-fixture.xlsx"
    artifact_path.write_bytes(b"Franklin Auditor fixture")
    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    parcel = "010-000001-00"
    rows = [
        _row_record(
            family="parcel",
            release_id="appraisal-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "owner_names": ["ASSESSMENT OWNER LLC"],
            },
            row_number=2,
        ),
        _row_record(
            family="payment",
            release_id="tax-accounting-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-07-01",
                "tax_year": 2025,
                "bill_type": "REAL",
                "amount": 100.25,
            },
            row_number=3,
        ),
        _row_record(
            family="sales",
            release_id="appraisal-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-06-30",
                "amount": 400_000,
                "is_exempt": "N",
                "sale_validity": "0 - VALID",
                "source_sale_flags": {
                    "is_exempt": "N",
                    "sale_validity": "0 - VALID",
                },
            },
            row_number=4,
        ),
        _row_record(
            family="sales",
            release_id="appraisal-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-06-29",
                "amount": 399_999,
                "sale_validity": "99 - RMS INVALID",
                "source_sale_flags": {
                    "sale_validity": "99 - RMS INVALID",
                },
            },
            row_number=5,
        ),
        _row_record(
            family="sales",
            release_id="appraisal-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-06-28",
                "amount": 399_998,
                "sale_validity": None,
                "source_sale_flags": {"sale_validity": None},
            },
            row_number=6,
        ),
        _row_record(
            family="daily-conveyance",
            release_id="daily-conveyance-2026-07-23",
            release_date="2026-07-23",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-07-23",
                "amount": 450_000,
                "is_exempt": "NON-EXEMPT",
                "sale_type": "LAND AND BUILDING",
                "source_sale_flags": {
                    "is_exempt": "NON-EXEMPT",
                    "sale_type": "LAND AND BUILDING",
                },
            },
            row_number=7,
        ),
        _row_record(
            family="daily-conveyance",
            release_id="daily-conveyance-2026-07-23",
            release_date="2026-07-23",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-07-23",
                "amount": 1,
                "is_exempt": "EXEMPT",
                "sale_type": "LAND AND BUILDING",
                "source_sale_flags": {
                    "is_exempt": "EXEMPT",
                    "sale_type": "LAND AND BUILDING",
                },
            },
            row_number=8,
        ),
        _row_record(
            family="transfer",
            release_id="tax-accounting-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": parcel,
                "event_date": "2026-07-02",
                "amount": 999,
            },
            row_number=9,
        ),
        _row_record(
            family="value",
            release_id="tax-accounting-2026-07-15",
            release_date="2026-07-15",
            artifact_sha256=artifact_sha256,
            parsed_fields={"parcel_id": parcel, "amount": 750_000},
            row_number=10,
        ),
    ]
    metadata_record = {
        "source_id": SOURCE_ID,
        "record_kind": "bulk_dataset_release",
        "native_document_id": "appraisal-2026-07-15",
        "release_id": "appraisal-2026-07-15",
        "release_date": "2026-07-15",
        "directory_url": franklin.OUTSIDE_USER_ROOT,
    }
    db_path = tmp_path / "property.db"

    metadata_report = ingest_property_envelope(
        _envelope([metadata_record], artifact_path=artifact_path),
        db_path=db_path,
        raw_artifact_path=artifact_path,
    )
    report = ingest_property_envelope(
        _envelope(rows, artifact_path=artifact_path),
        db_path=db_path,
        raw_artifact_path=artifact_path,
    )

    assert metadata_report["records_ingested"] == 0
    assert metadata_report["projection_skips"][0]["reason"] == (
        "franklin_auditor_bulk_release_or_artifact_observation"
    )
    assert report["records_ingested"] == len(rows)
    assert [item["sale_projection_eligible"] for item in report["records"]] == [
        False,
        False,
        True,
        True,
        True,
        True,
        False,
        False,
        False,
    ]

    db = connect_property(db_path)
    try:
        owner = db.execute(
            """
            SELECT raw_owner_name, effective_from, observation_id
            FROM ownership_assertion WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        payment = db.execute(
            """
            SELECT tax_year, event_type, event_date, amount_minor
            FROM tax_account_event WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        sales = db.execute(
            """
            SELECT sale_date, consideration_minor, qualification_code,
                   derivation
            FROM sale_event WHERE source_id=? ORDER BY sale_date
            """,
            (SOURCE_ID,),
        ).fetchall()
        invalid_observation = db.execute(
            """
            SELECT raw_artifact_sha256, source_url, raw_json
            FROM source_observation
            WHERE source_id=? AND source_native_id=?
            """,
            (SOURCE_ID, rows[3]["native_document_id"]),
        ).fetchone()
        blank_observation = db.execute(
            """
            SELECT raw_json FROM source_observation
            WHERE source_id=? AND source_native_id=?
            """,
            (SOURCE_ID, rows[4]["native_document_id"]),
        ).fetchone()
        unsupported_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("assessment", "recorded_instrument")
        }
    finally:
        db.close()

    assert tuple(owner[:2]) == ("ASSESSMENT OWNER LLC", "2026-07-15")
    assert "2026-07-31" not in owner["effective_from"]
    assert tuple(payment) == (
        "2025",
        "tax_payment_observation",
        "2026-07-01",
        10_025,
    )
    assert [tuple(item) for item in sales] == [
        (
            "2026-06-28",
            39_999_800,
            None,
            "franklin_auditor_assessor_sale",
        ),
        (
            "2026-06-29",
            39_999_900,
            "99 - RMS INVALID",
            "franklin_auditor_assessor_sale",
        ),
        (
            "2026-06-30",
            40_000_000,
            "0 - VALID",
            "franklin_auditor_assessor_sale",
        ),
        (
            "2026-07-23",
            45_000_000,
            "NON-EXEMPT",
            "franklin_auditor_daily_conveyance",
        ),
    ]
    assert invalid_observation["raw_artifact_sha256"] == artifact_sha256
    assert invalid_observation["source_url"] == (
        "https://apps.franklincountyauditor.com/fixture"
    )
    preserved = json.loads(invalid_observation["raw_json"])
    assert preserved["native_occurrence"] == rows[3]["native_occurrence"]
    assert preserved["release_id"] == "appraisal-2026-07-15"
    assert preserved["parsed_fields"]["source_sale_flags"][
        "sale_validity"
    ] == "99 - RMS INVALID"
    blank_preserved = json.loads(blank_observation["raw_json"])
    assert blank_preserved["parsed_fields"]["sale_validity"] is None
    assert unsupported_counts == {"assessment": 0, "recorded_instrument": 0}
    assert "semantic:" in report["records"][2]["normalized_sale_id"]
    assert "semantic:" in report["records"][5]["normalized_sale_id"]


def test_ingestion_rejects_mismatched_row_and_raw_artifact_digests(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "sales.xlsx"
    artifact_path.write_bytes(b"actual artifact")
    record = _row_record(
        family="sales",
        release_id="appraisal-2026-07-15",
        release_date="2026-07-15",
        artifact_sha256="f" * 64,
        parsed_fields={
            "parcel_id": "010-000001-00",
            "event_date": "2026-06-30",
            "amount": 400_000,
            "instrument_number": "2026000001",
        },
        row_number=2,
    )

    with pytest.raises(PropertyIngestError, match="does not match"):
        ingest_property_envelope(
            _envelope([record], artifact_path=artifact_path),
            db_path=tmp_path / "property.db",
            raw_artifact_path=artifact_path,
        )


@pytest.mark.parametrize(
    ("family", "business_field", "business_value", "derivation"),
    [
        (
            "sales",
            "instrument_number",
            "2026-000001",
            "franklin_auditor_assessor_sale",
        ),
        (
            "daily-conveyance",
            "conveyance_number",
            "C-100",
            "franklin_auditor_daily_conveyance",
        ),
    ],
)
@pytest.mark.parametrize("newest_first", [False, True])
def test_repeated_sale_releases_collapse_to_newest_business_event(
    tmp_path: Path,
    family: str,
    business_field: str,
    business_value: str,
    derivation: str,
    newest_first: bool,
) -> None:
    parcel = "010-000001-00"
    artifacts = {
        "old": tmp_path / f"{family}-old.xlsx",
        "new": tmp_path / f"{family}-new.xlsx",
    }
    artifacts["old"].write_bytes(b"older release")
    artifacts["new"].write_bytes(b"newer release")
    rows: dict[str, dict[str, Any]] = {}
    for label, amount, qualification, release_date in (
        ("old", 100_000, "99 - RMS INVALID", "2025-07-15"),
        ("new", 200_000, "0 - VALID", "2026-08-15"),
    ):
        digest = hashlib.sha256(artifacts[label].read_bytes()).hexdigest()
        parsed_fields = {
            "parcel_id": parcel,
            "event_date": "2020-01-02",
            "amount": amount,
            business_field: business_value,
        }
        if family == "sales":
            parsed_fields["sale_validity"] = qualification
            parsed_fields["instrument"] = "WD"
        else:
            parsed_fields["is_exempt"] = "NON-EXEMPT"
            parsed_fields["instrument"] = "WD"
        rows[label] = _row_record(
            family=family,
            release_id=f"{family}-{release_date}",
            release_date=release_date,
            artifact_sha256=digest,
            parsed_fields=parsed_fields,
            row_number=2,
        )

    db_path = tmp_path / f"{family}-{newest_first}.db"
    order = ("new", "old") if newest_first else ("old", "new")
    reports = {}
    for label in order:
        reports[label] = ingest_property_envelope(
            _envelope(
                [rows[label]],
                artifact_path=artifacts[label],
                retrieved_at=(
                    "2026-08-16T12:00:00Z"
                    if label == "new"
                    else "2026-09-16T12:00:00Z"
                ),
            ),
            db_path=db_path,
            raw_artifact_path=artifacts[label],
        )

    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT se.native_sale_id, se.consideration_minor,
                   se.qualification_code, se.derivation, so.retrieved_at,
                   so.raw_json, p.roll_year
            FROM sale_event se
            JOIN source_observation so
              ON so.observation_id=se.observation_id
            JOIN parcel_snapshot p ON p.parcel_id=se.parcel_id
            WHERE se.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        raw_occurrences = db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind LIKE '%_row_observation'
            """,
            (SOURCE_ID,),
        ).fetchone()[0]
    finally:
        db.close()

    assert len(sale) == 1
    assert raw_occurrences == 2
    assert sale[0]["consideration_minor"] == 20_000_000
    assert sale[0]["qualification_code"] == (
        "0 - VALID" if family == "sales" else "NON-EXEMPT"
    )
    assert sale[0]["derivation"] == derivation
    assert sale[0]["retrieved_at"] == "2026-08-16T12:00:00Z"
    assert json.loads(sale[0]["raw_json"])["release_date"] == "2026-08-15"
    assert sale[0]["roll_year"] == ""
    assert business_value.replace("-", "") in sale[0]["native_sale_id"]
    assert reports["new"]["records"][0]["sales_upserted"] == 1
    if newest_first:
        assert reports["old"]["records"][0]["sales_upserted"] == 0


def test_semantic_fallback_does_not_merge_distinct_same_day_sales(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "sales.xlsx"
    artifact_path.write_bytes(b"same-day sales")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    common = {
        "parcel_id": "010-000001-00",
        "event_date": "2020-01-02",
        "instrument": "WD",
        "sale_type": "LAND AND BUILDING",
        "sale_validity": "0 - VALID",
        "owner_names": ["NEW OWNER"],
        "prior_owner_names": ["PRIOR OWNER"],
    }
    rows = [
        _row_record(
            family="sales",
            release_id="appraisal-2026-08-15",
            release_date="2026-08-15",
            artifact_sha256=digest,
            parsed_fields={**common, "amount": amount},
            row_number=row_number,
        )
        for row_number, amount in ((2, 100_000), (3, 200_000))
    ]

    report = ingest_property_envelope(
        _envelope([*rows], artifact_path=artifact_path),
        db_path=tmp_path / "property.db",
        raw_artifact_path=artifact_path,
    )

    db = connect_property(tmp_path / "property.db")
    try:
        sales = db.execute(
            """
            SELECT native_sale_id, consideration_minor FROM sale_event
            WHERE source_id=? ORDER BY consideration_minor
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()

    assert len(sales) == 2
    assert [row["consideration_minor"] for row in sales] == [
        10_000_000,
        20_000_000,
    ]
    assert len({row["native_sale_id"] for row in sales}) == 2
    assert all(
        "semantic:" in item["normalized_sale_id"] for item in report["records"]
    )


@pytest.mark.parametrize("ogrip_first", [False, True])
def test_ogrip_arrival_order_does_not_move_franklin_bulk_projections(
    tmp_path: Path,
    ogrip_first: bool,
) -> None:
    parcel = "010-042534"
    artifacts = {
        "old": tmp_path / "franklin-2025.xlsx",
        "new": tmp_path / "franklin-2026.xlsx",
    }
    artifacts["old"].write_bytes(b"franklin 2025")
    artifacts["new"].write_bytes(b"franklin 2026")
    waves: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for label, release_date, owner, amount, qualification in (
        ("old", "2025-07-15", "2025 OWNER", 100_000, "99 - RMS INVALID"),
        ("new", "2026-08-15", "2026 OWNER", 200_000, "0 - VALID"),
    ):
        digest = hashlib.sha256(artifacts[label].read_bytes()).hexdigest()
        waves[label] = (
            _row_record(
                family="parcel",
                release_id=f"appraisal-{release_date}",
                release_date=release_date,
                artifact_sha256=digest,
                parsed_fields={
                    "parcel_id": parcel,
                    "owner_names": [owner],
                },
                row_number=2,
            ),
            _row_record(
                family="sales",
                release_id=f"appraisal-{release_date}",
                release_date=release_date,
                artifact_sha256=digest,
                parsed_fields={
                    "parcel_id": parcel,
                    "event_date": "2020-01-02",
                    "amount": amount,
                    "instrument": "WD",
                    "instrument_number": "2020-000001",
                    "sale_validity": qualification,
                },
                row_number=3,
            ),
        )

    db_path = tmp_path / f"ogrip-order-{ogrip_first}.db"

    def ingest_wave(label: str) -> None:
        for record in waves[label]:
            ingest_property_envelope(
                _envelope(
                    [record],
                    artifact_path=artifacts[label],
                    retrieved_at=(
                        "2026-07-16T12:00:00Z"
                        if label == "old"
                        else "2026-08-16T12:00:00Z"
                    ),
                ),
                db_path=db_path,
                raw_artifact_path=artifacts[label],
            )

    if ogrip_first:
        ingest_property_envelope(_ogrip_envelope(parcel), db_path=db_path)
        ingest_wave("old")
    else:
        ingest_wave("old")
        ingest_property_envelope(_ogrip_envelope(parcel), db_path=db_path)
    ingest_wave("new")

    db = connect_property(db_path)
    try:
        bulk_parcels = db.execute(
            """
            SELECT roll_year FROM parcel_snapshot
            WHERE source_id=? ORDER BY roll_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        ogrip_parcels = db.execute(
            """
            SELECT COUNT(*) FROM parcel_snapshot WHERE source_id=?
            """,
            (ogrip.SOURCE_ID,),
        ).fetchone()[0]
        owners = db.execute(
            """
            SELECT oa.raw_owner_name, p.source_id, p.roll_year
            FROM ownership_assertion oa
            JOIN parcel_snapshot p ON p.parcel_id=oa.parcel_id
            WHERE oa.source_id=? ORDER BY p.roll_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        sales = db.execute(
            """
            SELECT se.consideration_minor, se.qualification_code,
                   p.source_id, p.roll_year
            FROM sale_event se
            JOIN parcel_snapshot p ON p.parcel_id=se.parcel_id
            WHERE se.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        raw_rows = db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind LIKE '%_row_observation'
            """,
            (SOURCE_ID,),
        ).fetchone()[0]
    finally:
        db.close()

    assert [row["roll_year"] for row in bulk_parcels] == ["", "2025", "2026"]
    assert ogrip_parcels == 1
    assert [tuple(row) for row in owners] == [
        ("2025 OWNER", SOURCE_ID, "2025"),
        ("2026 OWNER", SOURCE_ID, "2026"),
    ]
    assert [tuple(row) for row in sales] == [
        (20_000_000, "0 - VALID", SOURCE_ID, "")
    ]
    assert raw_rows == 4


def test_historical_release_month_keeps_distinct_parcel_shells(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "parcel.csv"
    artifact_path.write_bytes(b"historical parcel fixture")
    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    db_path = tmp_path / "property.db"
    records = [
        _row_record(
            family="parcel",
            release_id="parcel-csv-1997-01",
            release_date=None,
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": "010-000099-00",
                "owner_names": ["1997 OWNER"],
            },
            row_number=2,
        ),
        _row_record(
            family="parcel",
            release_id="parcel-csv-2025-07",
            release_date=None,
            artifact_sha256=artifact_sha256,
            parsed_fields={
                "parcel_id": "010-000099-00",
                "owner_names": ["2025 OWNER"],
            },
            row_number=3,
        ),
    ]

    for index, record in enumerate(records):
        ingest_property_envelope(
            _envelope(
                [record],
                artifact_path=artifact_path,
                retrieved_at=f"2026-07-3{index}T12:00:00Z",
            ),
            db_path=db_path,
            raw_artifact_path=artifact_path,
        )

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT roll_year, effective_from, source_good_through
            FROM parcel_snapshot WHERE source_id=? ORDER BY roll_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        owners = db.execute(
            """
            SELECT raw_owner_name, o.effective_from, p.roll_year
            FROM ownership_assertion o
            JOIN parcel_snapshot p USING(parcel_id)
            WHERE o.source_id=? ORDER BY p.roll_year
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()

    assert [tuple(item) for item in parcels] == [
        ("1997", "1997-01", "1997-01"),
        ("2025", "2025-07", "2025-07"),
    ]
    assert [tuple(item) for item in owners] == [
        ("1997 OWNER", "1997-01", "1997"),
        ("2025 OWNER", "2025-07", "2025"),
    ]


def _monitor_context() -> public_records_monitor.ProbeContext:
    return public_records_monitor.ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=1,
        max_attempts=1,
        sample_bytes=64,
    )


def test_monitor_separates_rolling_releases_and_validates_daily_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, Any] = {
        "date": "2026-07-30",
        "size": 36_542,
        "probe_size": 36_542,
        "signature_hex": "504b030414000000",
        "format_hint": "zip",
        "etag": '"first"',
        "root_fingerprint": "a" * 64,
        "bulk_requests": 1,
    }

    class FakeDirectoryClient:
        def __init__(self, **_kwargs: Any) -> None:
            self.request_count = 0

        def listing(self, url: str):
            assert url == franklin.DIRECTORY_ROOT
            self.request_count = 8
            entries = tuple(
                franklin.DirectoryEntry(
                    name=name,
                    url=f"{url}{name}/",
                    relative_path=f"/{name}/",
                    is_directory=True,
                    size=None,
                    modified_raw="7/30/2026 1:00 PM",
                    modified_at="2026-07-30T13:00-04:00",
                )
                for name in (
                    "Daily_Conveyances",
                    "GIS_Shapefiles",
                    "Outside_User_Files",
                    "Parcel_CSV",
                )
            )
            return franklin.DirectoryListing(
                url=url,
                path="/",
                entries=entries,
                fingerprint=state["root_fingerprint"],
            )

    def fake_discover(_client: Any, family: str):
        date = state["date"]
        return [
            franklin.Release(
                family=family,
                release_id=f"{family}-{date}",
                directory_url=f"{franklin.DIRECTORY_ROOT}{family}/",
                release_date=date,
                release_date_basis="fixture",
                path_period=date[:7],
                directory_modified_raw="fixture",
                directory_modified_at=f"{date}T12:00:00-04:00",
            )
        ]

    def fake_artifacts(_client: Any, release: franklin.Release):
        compact = state["date"].replace("-", "")
        return [
            {
                "source_id": SOURCE_ID,
                "record_kind": "bulk_dataset_artifact",
                "native_document_id": f"Daily_Conveyances/{compact}.xlsx",
                "artifact_id": compact,
                "family": release.family,
                "release_id": release.release_id,
                "release_date": state["date"],
                "filename": f"DailyConveyances_{compact}.xlsx",
                "relative_path": f"/Daily_Conveyances/{compact}.xlsx",
                "artifact_url": f"https://example.test/{compact}.xlsx",
                "format": "xlsx",
                "media_type": franklin.XLSX_MEDIA_TYPE,
                "archive_format": "xlsx",
                "directory_size": state["size"],
                "directory_modified_at": f"{state['date']}T12:00:00-04:00",
            }
        ]

    def fake_bulk_probe(_artifact: Any, context: Any):
        return (
            {
                "http_status": 206,
                "content_length": state["probe_size"],
                "media_type": franklin.XLSX_MEDIA_TYPE,
                "etag": state["etag"],
                "last_modified": f"{state['date']}T12:00:00-04:00",
                "accept_ranges": True,
                "sample_size": context.sample_bytes,
                "sample_sha256": "f" * 64,
                "signature_hex": state["signature_hex"],
                "format_hint": state["format_hint"],
                "headers": {},
            },
            state["bulk_requests"],
        )

    monkeypatch.setattr(franklin, "FranklinDirectoryClient", FakeDirectoryClient)
    monkeypatch.setattr(franklin, "discover_releases", fake_discover)
    monkeypatch.setattr(franklin, "artifacts_for_release", fake_artifacts)
    monkeypatch.setattr(
        public_records_monitor,
        "_counted_bulk_probe",
        fake_bulk_probe,
    )

    first = public_records_monitor.probe_ohio_franklin_auditor_bulk(
        _monitor_context()
    )
    state.update(
        date="2026-07-31",
        size=37_000,
        probe_size=37_000,
        etag='"second"',
        root_fingerprint="b" * 64,
    )
    second = public_records_monitor.probe_ohio_franklin_auditor_bulk(
        _monitor_context()
    )

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details["stable_contract"]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 9

    state["bulk_requests"] = 2
    with pytest.raises(ValueError, match="request count changed"):
        public_records_monitor.probe_ohio_franklin_auditor_bulk(
            _monitor_context()
        )

    state["bulk_requests"] = 1
    state["probe_size"] = 37_001
    with pytest.raises(franklin.FranklinSourceChanged, match="size differs"):
        public_records_monitor.probe_ohio_franklin_auditor_bulk(
            _monitor_context()
        )

    state.update(
        probe_size=37_000,
        signature_hex="3c68746d6c3e",
        format_hint="html",
    )
    with pytest.raises(
        franklin.FranklinSourceChanged,
        match="ZIP container signature",
    ):
        public_records_monitor.probe_ohio_franklin_auditor_bulk(
            _monitor_context()
        )
