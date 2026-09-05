from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from tools import (
    public_records_monitor,
    query_property,
    query_virginia_parcels as va,
)
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.public_records_search_plan import build_search_plan
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog


FIXTURE_ROOT = Path("tests/fixtures/public_records/virginia_parcels")


def _load(name: str):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _normalized_parcel() -> dict:
    item = _load("item.json")
    layer = _load("layer.json")
    statistics = {
        "min_object_id": 1,
        "max_object_id": 1,
        "row_count": 1,
        "earliest_update": 1767916800000,
        "latest_update": 1767916800000,
    }
    snapshot = va._compatible_snapshot(
        item,
        layer,
        va.DEFAULT_LAYER_URL,
        statistics,
    )
    batch = va.TraversalBatch(
        records=(),
        next_cursor=None,
        total_count=1,
        remaining_count=1,
        pages_fetched=1,
        snapshot=snapshot,
    )
    return va._normalize_feature(
        _load("features.json")[0],
        batch,
        geometry_requested=True,
    )


def _parcel_envelope() -> dict:
    record = _normalized_parcel()
    args = va.build_parser().parse_args(
        [
            "parcel",
            record["vgin_qpid"],
            "--field",
            "vgin-qpid",
            "--fips",
            "51087",
            "--geometry",
        ]
    )
    return PublicRecordsResult.success(
        va.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _coverage_envelope() -> dict:
    coverage = {
        "source_id": va.SOURCE_ID,
        "record_type": "locality_coverage",
        "statewide_parcel_count": 4170691,
        "source_locality_group_count": 136,
        "expected_current_county_equivalent_count": 133,
        "observed_county_equivalent_count": 132,
        "missing_county_equivalent_geoids": ["51157"],
        "incorporated_town_code_count": 4,
        "incorporated_town_codes": [
            "5105544",
            "5118400",
            "5120752",
            "5127440",
        ],
        "oldest_locality_latest_update": {
            "source_locality_code": "51690",
            "locality_name": "Martinsville City",
            "latest_update": "2017-02-22",
            "latest_update_epoch_ms": 1487721600000,
        },
        "newest_locality_latest_update": {
            "source_locality_code": "51003",
            "locality_name": "Albemarle County",
            "latest_update": "2026-03-09",
            "latest_update_epoch_ms": 1773014400000,
        },
        "localities": [],
        "source_snapshot": {
            "resolved_layer_url": va.DEFAULT_LAYER_URL,
            "schema_fingerprint": "a" * 64,
            "data_fingerprint": "b" * 64,
            "arcgis_item_modified_epoch_ms": 1782934213000,
        },
    }
    args = va.build_parser().parse_args(["localities"])
    return PublicRecordsResult.success(
        va.build_query(args),
        [coverage],
        retrieved_at="2026-07-30T12:01:00Z",
    ).to_dict()


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_translate_vgin_identity_spatial_and_freshness() -> None:
    routes = query_property.LIVE_ROUTES[va.SOURCE_ID]

    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            va.PROBE_VGIN_QPID,
            "--source",
            va.SOURCE_ID,
            "--jurisdiction",
            "51087",
            "--search-field",
            "vgin-qpid",
            "--geometry",
            "--limit",
            "7",
        ),
        routes["parcel"].adapter_command,
    )
    assert parcel.command == "parcel"
    assert parcel.identifier == va.PROBE_VGIN_QPID
    assert parcel.field == "vgin-qpid"
    assert parcel.fips == "51087"
    assert parcel.geometry is True
    assert parcel.limit == 7

    local_parcel = routes["search"].translate(
        _shared_args(
            "search",
            "740-783-1825",
            "--source",
            va.SOURCE_ID,
            "--county-code",
            "51087",
            "--search-field",
            "parcel-id",
        ),
        routes["search"].adapter_command,
    )
    assert local_parcel.command == "parcel"
    assert local_parcel.field == "parcel-id"
    assert local_parcel.fips == "51087"
    assert local_parcel.limit is None

    point = routes["point"].translate(
        _shared_args(
            "point",
            "--source",
            va.SOURCE_ID,
            "--jurisdiction",
            "51",
            "--longitude",
            "-77.6104",
            "--latitude",
            "37.7099",
        ),
        routes["point"].adapter_command,
    )
    assert point.command == "point"
    assert (point.longitude, point.latitude) == (-77.6104, 37.7099)
    assert point.geometry is True

    freshness = routes["freshness"].translate(
        _shared_args(
            "freshness",
            "*",
            "--source",
            va.SOURCE_ID,
        ),
        routes["freshness"].adapter_command,
    )
    assert freshness.command == "localities"
    assert set(routes) == {
        "bbox",
        "count",
        "freshness",
        "map",
        "parcel",
        "point",
        "probe",
        "search",
    }


def test_vgin_projection_preserves_identity_locator_local_joins_and_coverage(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"

    parcel_report = ingest_property_envelope(
        _parcel_envelope(),
        db_path=db_path,
    )
    coverage_report = ingest_property_envelope(
        _coverage_envelope(),
        db_path=db_path,
    )

    assert parcel_report["records_ingested"] == 1
    projected = parcel_report["records"][0]
    assert projected["canonical_ref"] == (
        "PROPERTY:us-va-vgin-parcels/51087/parcel/5108700000001"
    )
    assert projected["vgin_qpid"] == "5108700000001"
    assert projected["object_id_locator"] == 1
    assert projected["source_locality_code"] == "51087"
    assert projected["geometry_upserted"] == 1

    assert coverage_report["records_ingested"] == 0
    assert coverage_report["records_preserved_without_projection"] == 1
    assert coverage_report["projection_skips"][0]["reason"] == (
        "vgin_row_is_not_a_parcel_geometry_observation"
    )

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT parcel_id, jurisdiction_geoid, native_parcel_id, roll_year,
                   effective_from, raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (va.SOURCE_ID,),
        ).fetchone()
        assert parcel is not None
        assert tuple(parcel)[:5] == (
            parcel["parcel_id"],
            "51087",
            "5108700000001",
            "",
            "2026-01-09",
        )
        parcel_raw = json.loads(parcel["raw_json"])
        assert parcel_raw["vgin_qpid"] == "5108700000001"
        assert parcel_raw["object_id"] == 1
        assert parcel_raw["jurisdiction"]["source_locality_code"] == "51087"
        assert parcel_raw["parcel_identifiers"] == {
            "parcel_id": "740-783-1825",
            "parcel_tax_map_id": "740-783-1825",
            "join_candidates": [
                {
                    "field": "PARCELID",
                    "value": "740-783-1825",
                    "source_locality_code": "51087",
                },
                {
                    "field": "PTM_ID",
                    "value": "740-783-1825",
                    "source_locality_code": "51087",
                },
            ],
        }
        assert parcel_raw["geometry"]["rings"]

        aliases = {
            (row["alias_type"], row["alias_value"])
            for row in db.execute(
                """
                SELECT alias_type, alias_value
                FROM parcel_alias
                WHERE parcel_id=?
                """,
                (parcel["parcel_id"],),
            )
        }
        assert {
            ("vgin_objectid_locator", "1"),
            ("vgin_locality_code", "51087"),
            ("vgin_parcelid", "740-783-1825"),
            ("vgin_ptm_id", "740-783-1825"),
            ("vgin_fips_parcelid", "51087:740-783-1825"),
            ("vgin_fips_ptm_id", "51087:740-783-1825"),
        } <= aliases

        geometry = db.execute(
            """
            SELECT geometry_ref, geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            WHERE parcel_id=?
            """,
            (parcel["parcel_id"],),
        ).fetchone()
        assert geometry is not None
        assert geometry["geometry_ref"].endswith("#/geometry")
        assert geometry["geometry_format"] == "esri_json"
        assert geometry["crs"] == "EPSG:4326"
        assert (
            "not legal descriptions or property surveys"
            in (geometry["accuracy_disclaimer"])
        )

        coverage = db.execute(
            """
            SELECT source_native_id, record_kind, raw_json
            FROM source_observation
            WHERE source_id=? AND record_kind='locality_coverage'
            """,
            (va.SOURCE_ID,),
        ).fetchone()
        assert coverage is not None
        coverage_raw = json.loads(coverage["raw_json"])
        assert coverage["source_native_id"] == "locality_coverage"
        assert coverage_raw["missing_county_equivalent_geoids"] == ["51157"]
        assert coverage_raw["observed_county_equivalent_count"] == 132
        assert coverage_raw["incorporated_town_code_count"] == 4
        assert (
            coverage_raw["oldest_locality_latest_update"]["locality_name"]
            == "Martinsville City"
        )
    finally:
        db.close()


def test_vgin_monitor_separates_stable_contract_from_rolling_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling = {
        "count": 4_170_691,
        "data_fingerprint": "b" * 64,
        "item_modified": 1_782_934_213_000,
        "layer_url": va.DEFAULT_LAYER_URL,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert log_results is False
        parcel = deepcopy(_normalized_parcel())
        snapshot = parcel["source_snapshot"]
        snapshot.update(
            {
                "resolved_layer_url": rolling["layer_url"],
                "data_fingerprint": rolling["data_fingerprint"],
                "arcgis_item_modified_epoch_ms": rolling["item_modified"],
                "dataset_statistics": {
                    **snapshot["dataset_statistics"],
                    "row_count": rolling["count"],
                },
            }
        )
        if args.command == "metadata":
            record = {
                "source_id": va.SOURCE_ID,
                "record_type": "source_contract",
                "official_arcgis_item_id": va.ITEM_ID,
                "official_arcgis_item_url": va.ITEM_PAGE_URL,
                "resolved_layer_url": rolling["layer_url"],
                "layer_name": va.SOURCE_LAYER_NAME,
                "geometry_type": va.SOURCE_GEOMETRY_TYPE,
                "object_id_field": "OBJECTID",
                "required_fields": list(va.REQUIRED_FIELDS),
                "schema_fingerprint": snapshot["schema_fingerprint"],
                "data_fingerprint": rolling["data_fingerprint"],
                "arcgis_item_modified_epoch_ms": rolling["item_modified"],
                "dataset_statistics": snapshot["dataset_statistics"],
                "identity_contract": {
                    "durable_source_key": "VGIN_QPID",
                    "transport_locator": "OBJECTID",
                    "local_join_fields": ["FIPS", "PARCELID", "PTM_ID"],
                },
            }
        elif args.command == "probe":
            record = parcel
        elif args.command == "localities":
            record = deepcopy(_coverage_envelope()["records"][0])
            record.update(
                {
                    "statewide_parcel_count": rolling["count"],
                    "source_locality_group_count": 1,
                    "localities": [
                        {
                            "source_locality_code": "51087",
                            "locality_name": "Henrico County",
                            "parcel_count": rolling["count"],
                            "latest_update": "2026-01-09",
                        }
                    ],
                }
            )
            record["source_snapshot"] = {
                "resolved_layer_url": rolling["layer_url"],
                "schema_fingerprint": snapshot["schema_fingerprint"],
                "data_fingerprint": rolling["data_fingerprint"],
                "arcgis_item_modified_epoch_ms": rolling["item_modified"],
            }
        else:  # pragma: no cover - monitor contract enumerates the operations
            raise AssertionError(args.command)
        return PublicRecordsResult.success(
            va.build_query(args),
            [record],
            retrieved_at="2026-07-30T12:00:00Z",
        )

    monkeypatch.setattr(va, "execute", fake_execute)
    context = ProbeContext(
        source_id=va.SOURCE_ID,
        catalog_decision={"allowed": True},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = public_records_monitor.probe_virginia_statewide_parcels(context)
    rolling.update(
        {
            "count": 4_170_700,
            "data_fingerprint": "c" * 64,
            "item_modified": 1_783_020_000_000,
            "layer_url": (
                "https://vginmaps.vdem.virginia.gov/arcgis/rest/services/"
                "VA_Base_Layers/VA_Parcels_2026Q3/FeatureServer/0"
            ),
        }
    )
    second = public_records_monitor.probe_virginia_statewide_parcels(context)

    assert first.status == "ok"
    assert first.result_count == 3
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]["dataset_statistics"]["row_count"]
        != second.details["rolling_observation"]["dataset_statistics"]["row_count"]
    )
    assert (
        first.details["rolling_observation"]["resolved_layer_url"]
        != second.details["rolling_observation"]["resolved_layer_url"]
    )


def test_vgin_catalog_planner_and_monitor_expose_complement_graph(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    detail = catalog.show_source(va.SOURCE_ID)
    assert detail["source"]["official_url"] == va.ITEM_PAGE_URL
    assert catalog.require_machine_acquisition(va.SOURCE_ID)["allowed"] is True
    assert {capability["name"] for capability in detail["capabilities"]} == {
        "search_parcels",
        "query_spatial",
        "count_parcels",
        "inspect_locality_coverage",
        "inspect_identity_contract",
        "list_complementary_property_routes",
        "ingest_property_records",
        "probe_source",
    }
    assert {
        "us-va-vgin-parcels-bulk",
        "us-va-local-property-systems",
        "us-va-arlington-property-map",
        "us-va-arlington-land-records-publicsearch",
        "us-va-secure-remote-access-land-records",
    } <= set(detail["current_manifest"]["complementary_source_ids"])

    bulk = catalog.show_source("us-va-vgin-parcels-bulk")
    assert bulk["current_manifest"]["record_identity_source_id"] == va.SOURCE_ID
    assert (
        bulk["current_manifest"]["probe_evidence"][
            "counts_as_independent_corroboration"
        ]
        is False
    )

    plan = build_search_plan(
        va.PROBE_VGIN_QPID,
        jurisdictions=["51"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing.db",
    )
    route_group = next(
        group
        for group in plan["complementary_routes"]
        if group["primary_source_id"] == va.SOURCE_ID
    )
    assert {
        "us-va-vgin-parcels-bulk",
        "us-va-local-property-systems",
        "us-va-secure-remote-access-land-records",
    } <= {route["source_id"] for route in route_group["complements"]}

    spec = public_records_monitor.HANDLER_REGISTRY[va.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_virginia_statewide_parcels
    assert spec.expected_requests == 18
    assert spec.sentinel_record_count == 3
