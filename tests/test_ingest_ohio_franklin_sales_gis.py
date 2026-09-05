from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import query_ohio_franklin_auditor_bulk as franklin_bulk
from tools import query_ohio_franklin_sales_gis as franklin_sales
from tools import query_ohio_statewide_parcels as ogrip
from tools.ingest_property_records import (
    OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
    OHIO_FRANKLIN_SALES_GIS_SOURCE_ID,
    ingest_property_envelope,
)
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


SOURCE_ID = OHIO_FRANKLIN_SALES_GIS_SOURCE_ID
ITEM_ID = "1ce134b7dabe45bdad4121193934a38d"
LAYER_URL = (
    "https://gis.franklincountyohio.gov/hosting/rest/services/"
    "RealEstate/Sales_Information/FeatureServer/0"
)
OGRIP_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_statewide_parcels"
    / "features.json"
)
SALES_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_sales_gis"
    / "features.json"
)


def _record(
    *,
    object_id: int,
    global_id: str | None = None,
    parcel_id: str | None = "010-042534",
    conveyance_number: str | None = "2025-000123",
    sale_date: str | None = "2025-07-16",
    price: Any = 250_000,
    valid_sale: str | None = "N",
    grantors: list[str] | None = None,
    grantees: list[str] | None = None,
    instrument: str | None = "WD",
    sale_type: str | None = "LAND AND BUILDING",
) -> dict[str, Any]:
    occurrence_id = global_id or f"{ITEM_ID}:0:OBJECTID:{object_id}"
    usable_parcel = bool(parcel_id and parcel_id.strip())
    usable_conveyance = bool(
        conveyance_number and conveyance_number.strip()
    )
    return {
        "record_kind": "county_auditor_sale_feature_occurrence",
        "source_id": SOURCE_ID,
        "source_record_id": str(object_id),
        "native_id": occurrence_id,
        "canonical_ref": f"PROPERTY:{SOURCE_ID}/feature/{occurrence_id}",
        "occurrence_identity": {
            "native_id": occurrence_id,
            "identity_basis": (
                "GlobalID" if global_id else "service_item_layer_object_id"
            ),
            "global_id": global_id,
            "object_id": object_id,
            "service_item_id": ITEM_ID,
            "layer_id": 0,
            "canonical_ref": f"PROPERTY:{SOURCE_ID}/feature/{occurrence_id}",
        },
        "parcel_identity": (
            {
                "parcel_id": parcel_id,
                "canonical_ref": f"PROPERTY:{SOURCE_ID}/parcel/{parcel_id}",
                "identity_role": "published_business_join_candidate",
            }
            if usable_parcel
            else None
        ),
        "sale_identity": (
            {
                "conveyance_number": conveyance_number,
                "parcel_id": parcel_id,
                "canonical_ref": (
                    f"PROPERTY:{SOURCE_ID}/sale/{conveyance_number}:{parcel_id}"
                ),
                "identity_role": "published_business_sale_join",
            }
            if usable_parcel and usable_conveyance
            else None
        ),
        "jurisdiction": {
            "state_code": "OH",
            "state_fips": "39",
            "county_name": "Franklin County",
            "county_geoid": "39049",
        },
        "parcel_id": parcel_id,
        "low_parcel_id": "010-042534-00",
        "conveyance_number": conveyance_number,
        "parcel_count": 2,
        "sale": {
            "date_raw": 1_752_624_000_000 if sale_date else None,
            "date_iso": sale_date,
            "year": "2025",
            "price": price,
            "currency": "USD",
            "instrument": instrument,
            "sale_type": sale_type,
            "valid_sale": valid_sale,
            "qualification_preserved": True,
        },
        "parties": {
            "grantor_names": grantors or ["SELLER ONE", "SELLER TWO"],
            "grantee_names": grantees or ["BUYER ONE", "BUYER TWO"],
        },
        "situs_address_observation": {
            "raw": "84 W DODRIDGE ST",
            "postal_code": "43202",
            "subdivision_or_condominium": "DODRIDGE SUB",
        },
        "land_and_classification": {
            "stated_area": 0.12,
            "acres": 0.12,
            "property_class_code": "510",
        },
        "improvements": {
            "residential_area_above_grade_sq_ft": 1_500,
            "residential_area_total_sq_ft": 1_800,
            "year_built": 1925,
            "bedrooms": 3,
        },
        "activity": {
            "is_parcel_active": "Y",
            "last_update_raw": 1_752_710_400_000,
            "last_update_iso": "2025-07-17",
        },
        "coordinates_native": {
            "x": 1_820_000.0,
            "y": 720_000.0,
            "crs": "EPSG:3735",
        },
        "geometry": {"x": -83.01, "y": 40.01},
        "geometry_format": "esri_json",
        "geometry_crs": "EPSG:4326",
        "geometry_role": "county_auditor_sale_location_point",
        "source_layer_url": LAYER_URL,
        "source_response_schema_fingerprint": "a" * 64,
        "raw_attributes": {
            "OBJECTID": object_id,
            "GlobalID": global_id,
            "PARCELID": parcel_id,
            "ConveyanceNum": conveyance_number,
            "ParcelCount": 2,
            "ValidSale": valid_sale,
        },
    }


def _envelope(
    records: list[dict[str, Any]],
    *,
    retrieved_at: str = "2026-07-31T12:00:00Z",
) -> dict[str, Any]:
    return {
        "schema_version": "public-records-result/1.0",
        "status": "ok",
        "retrieved_at": retrieved_at,
        "query": {
            "source": {
                "source_id": SOURCE_ID,
                "base_url": LAYER_URL,
            },
            "operation": "search",
            "parameters": {},
            "fingerprint": "b" * 64,
        },
        "records": records,
        "next_cursor": None,
        "raw_artifact_refs": [],
        "warnings": [],
        "errors": [],
    }


def _ogrip_envelope(parcel_id: str) -> dict[str, Any]:
    feature = deepcopy(
        json.loads(OGRIP_FIXTURE.read_text(encoding="utf-8"))["features"][0]
    )
    feature["attributes"].update(
        {
            "LocalParcelID": parcel_id,
            "StateParcelID": f"39049-{parcel_id}",
        }
    )
    record = ogrip._normalize_feature(
        feature,
        schema_fingerprint="c" * 64,
        geometry_requested=False,
    )
    args = ogrip.build_parser().parse_args(["parcel", f"39049-{parcel_id}"])
    return PublicRecordsResult.success(
        ogrip._build_query(args),
        [record],
        retrieved_at="2026-07-20T12:00:00Z",
    ).to_dict()


def _bulk_envelope(
    tmp_path: Path,
    *,
    parcel_id: str,
) -> tuple[dict[str, Any], Path]:
    artifact_path = tmp_path / "sales.xlsx"
    artifact_path.write_bytes(b"Franklin sales fixture")
    artifact_sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    release_id = "appraisal-2026-07-15"
    occurrence = f"{release_id}:{artifact_sha256}:sales.xlsx:row:2"
    native_id = hashlib.sha256(occurrence.encode("utf-8")).hexdigest()
    record = {
        "source_id": franklin_bulk.SOURCE_ID,
        "record_kind": "sales_row_observation",
        "canonical_ref": f"BULK:{franklin_bulk.SOURCE_ID}/row/{native_id}",
        "evidence_ref": f"BULK:{franklin_bulk.SOURCE_ID}/row/{native_id}",
        "native_document_id": native_id,
        "native_occurrence": occurrence,
        "release_id": release_id,
        "release_date": "2026-07-15",
        "artifact_filename": artifact_path.name,
        "artifact_sha256": artifact_sha256,
        "artifact_size": artifact_path.stat().st_size,
        "artifact_source_url": "https://apps.franklincountyauditor.com/fixture",
        "worksheet": "Sheet1",
        "source_row_number": 2,
        "header_row_number": 1,
        "raw_headers": ["PARCELID", "SALEDT", "SALEPRICE", "INSTRUNO"],
        "raw_values": [parcel_id, "2025-07-16", 250_000, "2025-000123"],
        "source_fields": {
            "PARCELID": parcel_id,
            "SALEDT": "2025-07-16",
            "SALEPRICE": 250_000,
            "INSTRUNO": "2025-000123",
        },
        "parsed_fields": {
            "record_family": "sales",
            "parcel_id": parcel_id,
            "event_date": "2025-07-16",
            "amount": 250_000,
            "instrument": "WD",
            "instrument_number": "2025-000123",
            "sale_validity": "N",
        },
        "join_candidates": {
            "county_geoid": "39049",
            "parcel_id": parcel_id,
            "normalized_parcel_id": "".join(
                character for character in parcel_id if character.isalnum()
            ),
        },
        "same_authority_lineage": "us-oh-franklin-county-auditor-property",
    }
    args = franklin_bulk.build_parser().parse_args(
        [
            "rows",
            str(artifact_path),
            "--record-family",
            "sales",
            "--release-id",
            release_id,
        ]
    )
    envelope = PublicRecordsResult.success(
        franklin_bulk.build_query(args),
        [record],
        raw_artifact_refs=(str(artifact_path),),
        retrieved_at="2026-07-31T11:00:00Z",
    ).to_dict()
    return envelope, artifact_path


def test_occurrences_remain_distinct_while_business_sale_collapses(
    tmp_path: Path,
) -> None:
    records = [
        _record(
            object_id=101,
            global_id="{11111111-1111-1111-1111-111111111111}",
        ),
        _record(
            object_id=102,
            global_id="{22222222-2222-2222-2222-222222222222}",
        ),
    ]
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope(records), db_path=db_path)

    db = connect_property(db_path)
    try:
        occurrence_rows = db.execute(
            """
            SELECT source_native_id, raw_json FROM source_observation
            WHERE source_id=? AND record_kind=? ORDER BY source_native_id
            """,
            (SOURCE_ID, "county_auditor_sale_feature_occurrence"),
        ).fetchall()
        sales = db.execute(
            """
            SELECT se.native_sale_id, se.consideration_minor,
                   se.qualification_code, p.source_id AS parcel_source_id,
                   p.roll_year
            FROM sale_event se
            JOIN parcel_snapshot p ON p.parcel_id=se.parcel_id
            WHERE se.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        events = db.execute(
            """
            SELECT native_event_id, source_record_id, status, raw_json
            FROM property_event WHERE source_id=? ORDER BY source_record_id
            """,
            (SOURCE_ID,),
        ).fetchall()
        parties = db.execute(
            """
            SELECT role, raw_name, assertion_type
            FROM property_event_party ORDER BY event_id, sequence_no
            """
        ).fetchall()
        address_count = db.execute(
            "SELECT COUNT(*) FROM parcel_address WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()[0]
        geometry_count = db.execute(
            "SELECT COUNT(*) FROM parcel_geometry WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()[0]
        unsupported = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("recorded_instrument", "ownership_assertion")
        }
    finally:
        db.close()

    assert report["records_ingested"] == 2
    assert len(occurrence_rows) == 2
    assert {row["source_native_id"] for row in occurrence_rows} == {
        records[0]["native_id"],
        records[1]["native_id"],
    }
    assert len(sales) == 1
    assert tuple(sales[0]) == (
        "parcel:010042534:conveyance:2025000123",
        25_000_000,
        "N",
        OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
        "",
    )
    assert len(events) == 2
    assert len({row["native_event_id"] for row in events}) == 1
    assert [row["source_record_id"] for row in events] == [
        records[0]["native_id"],
        records[1]["native_id"],
    ]
    assert {row["role"] for row in parties} == {"grantor", "grantee"}
    assert all(
        row["assertion_type"] == "auditor_transaction_party_observation"
        for row in parties
    )
    assert len(parties) == 8
    assert address_count == 1
    assert geometry_count == 1
    assert unsupported == {"recorded_instrument": 0, "ownership_assertion": 0}
    assert all(item["structure_observation_projected"] for item in report["records"])
    preserved = json.loads(events[0]["raw_json"])
    assert preserved["parcel_count"] == 2
    assert preserved["improvements"]["year_built"] == 1925


def test_actual_adapter_normalization_ingests_without_translation(
    tmp_path: Path,
) -> None:
    feature = json.loads(SALES_FIXTURE.read_text(encoding="utf-8"))["features"][0]
    record = franklin_sales._normalize_feature(
        feature,
        schema_fingerprint="d" * 64,
        geometry_requested=True,
    )
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope([record]), db_path=db_path)

    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT se.consideration_minor, se.qualification_code,
                   p.native_parcel_id, p.source_id AS parcel_source_id
            FROM sale_event se
            JOIN parcel_snapshot p ON p.parcel_id=se.parcel_id
            WHERE se.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        occurrence = db.execute(
            """
            SELECT source_native_id FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (SOURCE_ID, "county_auditor_sale_feature_occurrence"),
        ).fetchone()
    finally:
        db.close()

    assert report["records_ingested"] == 1
    assert tuple(sale) == (
        80_000_000,
        "Y",
        "010-000006",
        OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID,
    )
    assert occurrence["source_native_id"] == (
        "{0A9D3B4A-060D-4B4F-A84B-DF332C586A1F}"
    )


@pytest.mark.parametrize("parcel_id", [None, "   ", "N/A", "000-000000"])
def test_unusable_parcel_identifiers_remain_observations_only(
    tmp_path: Path,
    parcel_id: str | None,
) -> None:
    record = _record(object_id=201, parcel_id=parcel_id)
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope([record]), db_path=db_path)

    db = connect_property(db_path)
    try:
        occurrence_count = db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (SOURCE_ID, "county_auditor_sale_feature_occurrence"),
        ).fetchone()[0]
        projection_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "parcel_snapshot",
                "parcel_address",
                "parcel_geometry",
                "property_event",
                "sale_event",
            )
        }
    finally:
        db.close()

    assert report["records_ingested"] == 0
    assert report["projection_skips"][0]["reason"] == (
        "franklin_sales_gis_occurrence_has_no_usable_parcel_join"
    )
    assert occurrence_count == 1
    assert set(projection_counts.values()) == {0}


def test_objectid_fallback_and_strong_semantic_sale_fallback(
    tmp_path: Path,
) -> None:
    record = _record(
        object_id=301,
        global_id=None,
        conveyance_number="  ",
    )
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope([record]), db_path=db_path)

    db = connect_property(db_path)
    try:
        observation = db.execute(
            """
            SELECT source_native_id FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (SOURCE_ID, "county_auditor_sale_feature_occurrence"),
        ).fetchone()
        sale = db.execute(
            "SELECT native_sale_id FROM sale_event WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()
    finally:
        db.close()

    assert observation["source_native_id"] == f"{ITEM_ID}:0:OBJECTID:301"
    assert report["records"][0]["business_identity_basis"] == (
        "parcel_plus_dated_price_instrument_type_and_bilateral_parties"
    )
    assert ":semantic:" in sale["native_sale_id"]


@pytest.mark.parametrize("conveyance_number", [None, "", "NULL", "0000"])
def test_unsafe_transaction_fallback_does_not_create_sale_or_parties(
    tmp_path: Path,
    conveyance_number: str | None,
) -> None:
    record = _record(
        object_id=401,
        conveyance_number=conveyance_number,
        grantees=[],
    )
    # The helper's default only applies to None/empty lists, so make the empty
    # party side explicit in the normalized record.
    record["parties"]["grantee_names"] = []
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope([record]), db_path=db_path)

    db = connect_property(db_path)
    try:
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("source_observation", "property_event", "sale_event")
        }
        parcel = db.execute(
            "SELECT source_id, roll_year FROM parcel_snapshot"
        ).fetchone()
    finally:
        db.close()

    assert report["records"][0]["business_sale_id"] is None
    assert report["records"][0]["sale_projection_eligible"] is False
    assert counts["source_observation"] == 2  # envelope plus raw feature
    assert counts["property_event"] == 0
    assert counts["sale_event"] == 0
    assert tuple(parcel) == (OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID, "")


@pytest.mark.parametrize("valid_sale", ["N", "INVALID", "99 - RMS INVALID", None])
def test_dated_positive_price_projects_with_raw_validity_qualification(
    tmp_path: Path,
    valid_sale: str | None,
) -> None:
    record = _record(
        object_id=501,
        valid_sale=valid_sale,
        price=325_000,
    )
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(_envelope([record]), db_path=db_path)

    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT consideration_minor, qualification_code, derivation
            FROM sale_event WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        event = db.execute(
            "SELECT status FROM property_event WHERE source_id=?",
            (SOURCE_ID,),
        ).fetchone()
    finally:
        db.close()

    assert report["records"][0]["sale_projection_eligible"] is True
    assert tuple(sale) == (
        32_500_000,
        valid_sale,
        "franklin_auditor_sales_gis_transaction",
    )
    assert event["status"] == valid_sale


@pytest.mark.parametrize("newest_first", [False, True])
def test_duplicate_business_sale_uses_source_lastupdate_in_either_order(
    tmp_path: Path,
    newest_first: bool,
) -> None:
    old = _record(
        object_id=551,
        global_id="{55555555-5555-5555-5555-555555555551}",
        price=200_000,
        valid_sale="OLD QUALIFICATION",
    )
    old["activity"]["last_update_iso"] = "2025-07-17"
    new = _record(
        object_id=552,
        global_id="{55555555-5555-5555-5555-555555555552}",
        price=275_000,
        valid_sale="NEW QUALIFICATION",
    )
    new["activity"]["last_update_iso"] = "2025-08-01"
    db_path = tmp_path / f"property-{newest_first}.db"
    order = ((new, "2026-07-01T12:00:00Z"), (old, "2026-08-01T12:00:00Z"))
    if not newest_first:
        order = tuple(reversed(order))
    for record, retrieved_at in order:
        ingest_property_envelope(
            _envelope([record], retrieved_at=retrieved_at),
            db_path=db_path,
        )

    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT consideration_minor, qualification_code, raw_json
            FROM sale_event WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        occurrence_count = db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (SOURCE_ID, "county_auditor_sale_feature_occurrence"),
        ).fetchone()[0]
    finally:
        db.close()

    assert tuple(sale[:2]) == (27_500_000, "NEW QUALIFICATION")
    assert json.loads(sale["raw_json"])["activity"]["last_update_iso"] == (
        "2025-08-01"
    )
    assert occurrence_count == 2


@pytest.mark.parametrize("newest_first", [False, True])
def test_mutable_occurrence_event_and_parties_use_full_source_timestamp(
    tmp_path: Path,
    newest_first: bool,
) -> None:
    occurrence_id = "{56565656-5656-5656-5656-565656565656}"
    old = _record(
        object_id=561,
        global_id=occurrence_id,
        price=210_000,
        valid_sale="OLDER",
        grantors=["OLDER SELLER"],
        grantees=["OLDER BUYER"],
    )
    old["activity"]["last_update_iso"] = "2025-08-01T09:00:00Z"
    new = _record(
        object_id=561,
        global_id=occurrence_id,
        price=290_000,
        valid_sale="NEWER",
        grantors=["NEWER SELLER"],
        grantees=["NEWER BUYER"],
    )
    new["activity"]["last_update_iso"] = "2025-08-01T17:00:00Z"
    db_path = tmp_path / f"mutable-{newest_first}.db"
    order = ((new, "2026-07-01T12:00:00Z"), (old, "2026-08-01T12:00:00Z"))
    if not newest_first:
        order = tuple(reversed(order))
    for record, retrieved_at in order:
        ingest_property_envelope(
            _envelope([record], retrieved_at=retrieved_at),
            db_path=db_path,
        )

    db = connect_property(db_path)
    try:
        sale = db.execute(
            """
            SELECT consideration_minor, qualification_code
            FROM sale_event WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        event = db.execute(
            """
            SELECT status, event_type, last_update_date, raw_json
            FROM property_event WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        parties = db.execute(
            """
            SELECT role, raw_name FROM property_event_party
            ORDER BY sequence_no
            """
        ).fetchall()
        occurrence_count = db.execute(
            """
            SELECT COUNT(*) FROM source_observation
            WHERE source_id=? AND record_kind=? AND source_native_id=?
            """,
            (
                SOURCE_ID,
                "county_auditor_sale_feature_occurrence",
                occurrence_id,
            ),
        ).fetchone()[0]
    finally:
        db.close()

    assert tuple(sale) == (29_000_000, "NEWER")
    assert tuple(event[:3]) == (
        "NEWER",
        "auditor_sale_feature_observation",
        "2025-08-01T17:00:00Z",
    )
    assert json.loads(event["raw_json"])["sale"]["price"] == 290_000
    assert [tuple(row) for row in parties] == [
        ("grantor", "NEWER SELLER"),
        ("grantee", "NEWER BUYER"),
    ]
    assert occurrence_count == 2


@pytest.mark.parametrize("sales_first", [False, True])
def test_bulk_and_ogrip_arrival_order_keeps_one_franklin_anchor(
    tmp_path: Path,
    sales_first: bool,
) -> None:
    parcel_id = "010-042534"
    db_path = tmp_path / f"property-{sales_first}.db"
    bulk_envelope, artifact_path = _bulk_envelope(
        tmp_path,
        parcel_id=parcel_id,
    )
    sales_envelope = _envelope([_record(object_id=601, parcel_id=parcel_id)])

    if sales_first:
        ingest_property_envelope(sales_envelope, db_path=db_path)
        ingest_property_envelope(_ogrip_envelope(parcel_id), db_path=db_path)
        ingest_property_envelope(
            bulk_envelope,
            db_path=db_path,
            raw_artifact_path=artifact_path,
        )
    else:
        ingest_property_envelope(
            bulk_envelope,
            db_path=db_path,
            raw_artifact_path=artifact_path,
        )
        ingest_property_envelope(_ogrip_envelope(parcel_id), db_path=db_path)
        ingest_property_envelope(sales_envelope, db_path=db_path)

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT source_id, native_parcel_id, roll_year, observation_id,
                   raw_json
            FROM parcel_snapshot ORDER BY source_id, roll_year
            """
        ).fetchall()
        gis_sale = db.execute(
            """
            SELECT p.source_id AS parcel_source_id, p.roll_year
            FROM sale_event se
            JOIN parcel_snapshot p ON p.parcel_id=se.parcel_id
            WHERE se.source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        raw_counts = {
            source: db.execute(
                "SELECT COUNT(*) FROM source_observation WHERE source_id=?",
                (source,),
            ).fetchone()[0]
            for source in (SOURCE_ID, franklin_bulk.SOURCE_ID, ogrip.SOURCE_ID)
        }
    finally:
        db.close()

    by_source = {}
    for row in parcels:
        by_source.setdefault(row["source_id"], []).append(row)
    assert len(by_source[OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID]) == 1
    assert by_source[OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID][0]["roll_year"] == ""
    assert by_source[OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID][0]["observation_id"] is None
    anchor_raw = json.loads(
        by_source[OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID][0]["raw_json"]
    )
    assert anchor_raw["record_kind"] == "franklin_auditor_cross_roll_parcel_anchor"
    assert len(by_source[ogrip.SOURCE_ID]) == 1
    assert SOURCE_ID not in by_source
    assert tuple(gis_sale) == (OHIO_FRANKLIN_AUDITOR_BULK_SOURCE_ID, "")
    assert all(count >= 2 for count in raw_counts.values())  # envelope + record
