from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_property
from tools import query_santa_fe_property as santa_fe
from tools import source_report
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_http import PaginatedFetch
from tools.public_records_monitor import (
    ProbeContext,
    probe_santa_fe_property,
)
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


SOURCE_ID = santa_fe.SOURCE_ID
FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "santa_fe_property"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _record(*, geometry: bool = True) -> dict[str, Any]:
    feature = copy.deepcopy(_fixture("county_parcel.json")["features"][0])
    if not geometry:
        feature.pop("geometry", None)
    return santa_fe.normalize_feature(
        feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
    )


def _envelope(
    record: dict[str, Any],
    *,
    operation: str = "parcel",
) -> dict[str, Any]:
    query = santa_fe.build_query(
        operation,
        record.get("native_parcel_id") or record.get("native_feature_id"),
        limit=None,
        cursor=None,
        active_only=False,
        return_geometry="geometry" in record,
        max_records=None,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-31T12:00:00Z",
    ).to_dict()


def test_shared_router_preserves_native_search_modes_without_default_cap() -> None:
    routes = query_property.LIVE_ROUTES[SOURCE_ID]
    owner = routes["owner"].translate(
        _shared_args(
            "owner",
            "SANTA FE COUNTY",
            "--source",
            SOURCE_ID,
            "--jurisdiction",
            "35049",
        ),
        routes["owner"].adapter_command,
    )
    mailing = routes["search"].translate(
        _shared_args(
            "search",
            "PO BOX 276",
            "--source",
            SOURCE_ID,
            "--search-field",
            "mailing",
        ),
        routes["search"].adapter_command,
    )
    object_id = routes["search"].translate(
        _shared_args(
            "search",
            "249",
            "--source",
            SOURCE_ID,
            "--search-field",
            "objectid",
            "--limit",
            "3",
        ),
        routes["search"].adapter_command,
    )
    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            santa_fe.PROBE_PARCEL_NUMBER,
            "--source",
            SOURCE_ID,
            "--geometry",
        ),
        routes["parcel"].adapter_command,
    )
    mapped = routes["map"].translate(
        _shared_args("map", "249", "--source", SOURCE_ID),
        routes["map"].adapter_command,
    )
    route_map = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "routes",
            "--source",
            SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    metadata = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "metadata",
            "--source",
            SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )

    assert set(routes) == {
        "search",
        "owner",
        "address",
        "parcel",
        "map",
        "discovery",
        "freshness",
        "probe",
    }
    assert owner.command == "owner"
    assert owner.limit is None
    assert owner.max_records is None
    assert mailing.command == "mailing"
    assert mailing.limit is None
    assert object_id.command == "objectid"
    assert object_id.limit == 3
    assert parcel.command == "parcel"
    assert parcel.geometry is True
    assert mapped.command == "objectid"
    assert mapped.geometry is True
    assert route_map.command == "routes"
    assert metadata.command == "metadata"

    route_result = routes["discovery"].adapter.execute(route_map)
    assert route_result.records[0]["primary_adapter_source_id"] == SOURCE_ID

    guidance = query_property._source_guidance(SOURCE_ID)
    complements = {
        value["route_id"]: value
        for value in guidance["official_complements"]
    }
    assert complements[
        "us-nm-santa-fe-assessor-parcel-download"
    ]["independent_evidence"] is False
    assert complements[
        "us-nm-santa-fe-clerktrack-index"
    ]["independent_evidence"] is True
    assert complements[
        "us-nm-santa-fe-treasurer-paydici"
    ]["relationship_to_primary"] == "distinct_tax_record"


def test_ingestion_projects_durable_account_without_title_or_invented_years(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(
        _envelope(_record()),
        db_path=db_path,
    )
    projected = report["records"][0]

    assert report["records_ingested"] == 1
    assert projected["owner_assertion_basis"] == (
        "assessment_roll_observation"
    )
    assert projected["assessment_periods"] == [
        "source-period:current",
        "source-period:prior",
    ]
    assert projected["assessment_years_invented"] is False
    assert projected["recorded_instruments_upserted"] == 0
    assert projected["sales_upserted"] == 0
    assert projected["title_assertions_upserted"] == 0
    assert projected["recorder_hints_preserved_as_join_hints"] is True

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT native_parcel_id, roll_year, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        assessments = db.execute(
            """
            SELECT tax_year, land_value_minor, improvement_value_minor,
                   assessed_value_minor, exempt_value_minor
            FROM assessment
            WHERE source_id=?
            ORDER BY tax_year
            """,
            (SOURCE_ID,),
        ).fetchall()
        owner = db.execute(
            """
            SELECT assertion_type, raw_owner_name, confidence
            FROM ownership_assertion
            WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        addresses = db.execute(
            """
            SELECT address_role, raw_address
            FROM parcel_address
            WHERE source_id=?
            ORDER BY address_role
            """,
            (SOURCE_ID,),
        ).fetchall()
        aliases = db.execute(
            """
            SELECT alias_type, alias_value
            FROM parcel_alias
            WHERE source_id=?
            ORDER BY alias_value
            """,
            (SOURCE_ID,),
        ).fetchall()
        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchone()
        prohibited = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "recorded_instrument",
                "instrument_party",
                "instrument_parcel",
                "sale_event",
            )
        }
    finally:
        db.close()

    raw_snapshot = json.loads(parcel["raw_json"])
    assert tuple(parcel[:2]) == (
        santa_fe.PROBE_UPC,
        "",
    )
    assert raw_snapshot["legal"]["description_raw"].startswith("TR A-5-1")
    assert raw_snapshot["classification"]["property_class"] == "GOV"
    assert [tuple(row) for row in assessments] == [
        ("source-period:current", 2_125_000, 49_425_200, None, 51_550_200),
        ("source-period:prior", 2_000_000, 48_000_000, None, 50_000_000),
    ]
    assert tuple(owner) == (
        "assessment_roll",
        santa_fe.PROBE_OWNER,
        "high",
    )
    assert [tuple(row) for row in addresses] == [
        (
            "mailing",
            "PO BOX 276, SANTA FE, NM, 87504, UNITED STATES",
        ),
        (
            "situs",
            "18 DINKLE RD, EDGEWOOD, NM, 87015, UNITED STATES",
        ),
    ]
    assert [tuple(row) for row in aliases] == [
        ("assessor_alternate_parcel_id", "910002704"),
        ("assessor_alternate_parcel_id", "ALT-249"),
    ]
    assert geometry["geometry_format"] == "esri_json"
    assert geometry["crs"] == "EPSG:4326"
    assert "not a surveyed legal boundary" in geometry[
        "accuracy_disclaimer"
    ]
    assert prohibited == {
        "recorded_instrument": 0,
        "instrument_party": 0,
        "instrument_parcel": 0,
        "sale_event": 0,
    }


def test_objectid_only_feature_is_preserved_without_parcel_projection(
    tmp_path: Path,
) -> None:
    feature = _fixture("geometry_occurrence.json")["features"][0]
    record = santa_fe.normalize_feature(
        feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
    )
    db_path = tmp_path / "property.db"
    report = ingest_property_envelope(
        _envelope(record, operation="objectid"),
        db_path=db_path,
    )

    assert report["records_ingested"] == 0
    assert report["records_preserved_without_projection"] == 1
    assert report["projection_skips"][0]["reason"] == (
        "santa_fe_objectid_only_feature_has_no_durable_parcel_identity"
    )

    db = connect_property(db_path)
    try:
        parcel_count = db.execute(
            "SELECT COUNT(*) FROM parcel_snapshot"
        ).fetchone()[0]
        feature_observation = db.execute(
            """
            SELECT source_native_id, record_kind
            FROM source_observation
            WHERE source_id=? AND record_kind=?
            """,
            (SOURCE_ID, "parcel_geometry_feature_occurrence"),
        ).fetchone()
    finally:
        db.close()
    assert parcel_count == 0
    assert tuple(feature_observation) == (
        "feature:1",
        "parcel_geometry_feature_occurrence",
    )


def test_distinct_feature_occurrences_converge_on_one_durable_parcel(
    tmp_path: Path,
) -> None:
    first = _record()
    second_feature = copy.deepcopy(
        _fixture("county_parcel.json")["features"][0]
    )
    second_feature["attributes"]["OBJECTID"] = 250
    second = santa_fe.normalize_feature(
        second_feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
    )
    envelope = _envelope(first)
    envelope["records"] = [first, second]
    db_path = tmp_path / "property.db"

    report = ingest_property_envelope(envelope, db_path=db_path)

    assert report["records_ingested"] == 1
    assert report["records_preserved_without_projection"] == 1
    assert report["projection_skips"][0]["reason"] == (
        "santa_fe_active_feature_is_not_preferred_account_version"
    )
    assert report["projection_skips"][0][
        "preferred_native_feature_id"
    ] == "249"
    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT native_parcel_id
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (SOURCE_ID,),
        ).fetchall()
        occurrences = db.execute(
            """
            SELECT source_native_id
            FROM source_observation
            WHERE source_id=? AND record_kind='parcel_account_observation'
            ORDER BY source_native_id
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()
    assert [row["native_parcel_id"] for row in parcels] == [
        santa_fe.PROBE_UPC
    ]
    assert [row["source_native_id"] for row in occurrences] == [
        "feature:249",
        "feature:250",
    ]


def test_active_projection_is_independent_of_inactive_feature_order(
    tmp_path: Path,
) -> None:
    active = _record()
    inactive_feature = copy.deepcopy(
        _fixture("county_parcel.json")["features"][0]
    )
    inactive_feature["attributes"].update(
        {
            "OBJECTID": 248,
            "active_status": "I",
            "eff_from_date": 0,
            "eff_to_date": 315446400000,
            "owner_name": "FORMER ASSESSMENT OWNER",
            "situs_line_1": "FORMER SITUS",
            "owner_line_1": "FORMER MAILING",
            "current_assessed_land": 1.0,
            "current_assessed_imp": 2.0,
        }
    )
    inactive = santa_fe.normalize_feature(
        inactive_feature,
        response_schema_fingerprint="response-schema",
        layer_schema_fingerprint="layer-schema",
    )

    snapshots: list[dict[str, Any]] = []
    for index, records in enumerate(
        ([inactive, active], [active, inactive])
    ):
        envelope = _envelope(active)
        envelope["records"] = records
        db_path = tmp_path / f"property-{index}.db"
        report = ingest_property_envelope(envelope, db_path=db_path)

        assert report["records_ingested"] == 1
        assert report["records_preserved_without_projection"] == 1
        assert {
            row["reason"] for row in report["projection_skips"]
        } == {
            "santa_fe_inactive_or_closed_feature_preserved_without_"
            "current_projection"
        }
        db = connect_property(db_path)
        try:
            parcel = db.execute(
                """
                SELECT raw_json FROM parcel_snapshot
                WHERE source_id=?
                """,
                (SOURCE_ID,),
            ).fetchone()
            owner = db.execute(
                """
                SELECT raw_owner_name, effective_from, effective_to
                FROM ownership_assertion
                WHERE source_id=?
                """,
                (SOURCE_ID,),
            ).fetchall()
            addresses = db.execute(
                """
                SELECT address_role, raw_address, effective_from, effective_to
                FROM parcel_address
                WHERE source_id=?
                ORDER BY address_role
                """,
                (SOURCE_ID,),
            ).fetchall()
            current_assessment = db.execute(
                """
                SELECT land_value_minor, improvement_value_minor
                FROM assessment
                WHERE source_id=? AND tax_year='source-period:current'
                """,
                (SOURCE_ID,),
            ).fetchone()
            occurrences = db.execute(
                """
                SELECT source_native_id, record_kind
                FROM source_observation
                WHERE source_id=?
                  AND record_kind='parcel_account_observation'
                ORDER BY source_native_id
                """,
                (SOURCE_ID,),
            ).fetchall()
        finally:
            db.close()
        snapshots.append(
            {
                "parcel": json.loads(parcel["raw_json"]),
                "owner": [tuple(row) for row in owner],
                "addresses": [tuple(row) for row in addresses],
                "assessment": tuple(current_assessment),
                "occurrences": [tuple(row) for row in occurrences],
            }
        )

    assert snapshots[0] == snapshots[1]
    assert snapshots[0]["parcel"]["native_feature_id"] == "249"
    assert snapshots[0]["parcel"]["account_status"] == "A"
    assert snapshots[0]["owner"] == [
        (santa_fe.PROBE_OWNER, "1980-01-01", None)
    ]
    assert snapshots[0]["addresses"] == [
        (
            "mailing",
            "PO BOX 276, SANTA FE, NM, 87504, UNITED STATES",
            "1980-01-01",
            None,
        ),
        (
            "situs",
            "18 DINKLE RD, EDGEWOOD, NM, 87015, UNITED STATES",
            "1980-01-01",
            None,
        ),
    ]
    assert snapshots[0]["assessment"] == (2_125_000, 49_425_200)
    assert snapshots[0]["occurrences"] == [
        ("feature:248", "parcel_account_observation"),
        ("feature:249", "parcel_account_observation"),
    ]


def test_monitor_hash_excludes_rolling_owner_value_and_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "metadata": _fixture("layer_metadata.json"),
        "feature": _fixture("county_parcel.json")["features"][0],
    }

    class FakeClient:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.request_count = 0

        def metadata(self) -> dict[str, Any]:
            self.request_count += 1
            return copy.deepcopy(state["metadata"])

        def query(self, **_kwargs: Any) -> PaginatedFetch:
            self.request_count += 1
            return PaginatedFetch(
                records=(copy.deepcopy(state["feature"]),),
                next_cursor=None,
                schema={"kind": "test"},
                schema_fingerprint="response-schema",
                pages_fetched=1,
                requests_made=1,
            )

    monkeypatch.setattr(santa_fe, "SantaFeArcGISClient", FakeClient)
    context = ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.2}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = probe_santa_fe_property(context)

    state["feature"]["attributes"]["owner_name"] = "CHANGED OWNER"
    state["feature"]["attributes"]["current_assessed_land"] = 1.0
    rolling_routes = copy.deepcopy(santa_fe.SOURCE_ROUTES)
    rolling_routes[0]["observed_count"] += 11
    monkeypatch.setattr(santa_fe, "SOURCE_ROUTES", tuple(rolling_routes))
    rolling = probe_santa_fe_property(context)

    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != rolling.details["rolling_observation"]
    )
    assert first.details["stable_contract"]["monitor"] == {
        "request_budget": 2,
        "metadata_requests": 1,
        "exact_sentinel_requests": 1,
        "geometry_fetched": False,
        "document_artifacts_fetched": False,
    }

    state["metadata"]["fields"].append(
        {
            "name": "future_stable_source_field",
            "type": "esriFieldTypeString",
            "length": 32,
        }
    )
    schema_changed = probe_santa_fe_property(context)
    assert schema_changed.schema_sha256 != rolling.schema_sha256
    assert schema_changed.artifact_sha256 == rolling.artifact_sha256

    changed_routes = copy.deepcopy(rolling_routes)
    changed_routes[0]["technical_pagination"]["mechanism"] = (
        "changed-paging-contract"
    )
    monkeypatch.setattr(santa_fe, "SOURCE_ROUTES", tuple(changed_routes))
    changed = probe_santa_fe_property(context)
    assert changed.artifact_sha256 != schema_changed.artifact_sha256
    assert (
        public_records_monitor.HANDLER_REGISTRY[SOURCE_ID].expected_requests
        == 2
    )


def test_catalog_census_report_plan_and_citation_cover_santa_fe(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)

    db = sqlite3.connect(catalog_path)
    try:
        roles = db.execute(
            """
            SELECT t.role
            FROM source_census_target_sources a
            JOIN source_census_targets t USING(census_target_id)
            WHERE a.source_id=?
            ORDER BY t.role
            """,
            (SOURCE_ID,),
        ).fetchall()
    finally:
        db.close()
    assert [row[0] for row in roles] == [
        "assessment_roll",
        "parcel_geometry",
    ]

    report = source_report.check_public_records_catalog(catalog_path)
    report_row = next(
        value
        for value in report.values()
        if isinstance(value, dict) and value.get("source_id") == SOURCE_ID
    )
    assert report_row["query_tool"] == "tools/query_property.py"
    assert report_row["status"] == "configured"

    plan = build_search_plan(
        "EXAMPLE OWNER",
        jurisdictions=["35049"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    capabilities = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert source["requested_jurisdiction_coverage"]["status"] == "matched"
    assert {
        "search_owner",
        "search_address",
        "search_assessment_records",
        "search_parcels",
        "fetch_parcel",
        "fetch_geometry",
    } <= capabilities

    source_urls = json.loads(
        (
            Path(__file__).parents[1]
            / "web"
            / "src"
            / "data"
            / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[f"PROPERTY_SOURCE:{SOURCE_ID}"] == (
        santa_fe.OFFICIAL_ASSESSOR_URL
    )
