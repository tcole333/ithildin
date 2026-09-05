from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from tools import public_records_monitor
from tools import public_records_search_plan
from tools import query_property
from tools import query_wy_dor_parcels as wyoming
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import (
    ProbeContext,
    compare_probes,
    probe_wyoming_dor_statewide_parcels,
)
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import seed_catalog
from tools.source_report import check_public_records_catalog


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "wy_dor_parcels"
)
SOURCE_CONFIG = Path("config/public_records_sources.yaml")
CENSUS_CONFIG = Path("config/public_records_census.yaml")
CITATION_CONFIG = Path("web/src/data/source-urls.json")
WYOMING_COUNTY_GEOIDS = {
    f"56{county['fips']}" for county in wyoming.COUNTIES.values()
}
SHARED_OPERATIONS = {
    "account",
    "address",
    "bbox",
    "county",
    "discovery",
    "fid",
    "geometry",
    "jurisdiction",
    "legal",
    "mailing",
    "map",
    "owner",
    "parcel",
    "point",
    "probe",
    "search",
    "situs",
}


def _shared_args(*values: str) -> Any:
    return query_property.build_parser().parse_args(list(values))


def _translated(*values: str) -> Any:
    args = _shared_args(*values)
    route = query_property.LIVE_ROUTES[wyoming.SOURCE_ID][args.command]
    return route.translate(args, route.adapter_command)


def _feature(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _normalized(feature: Mapping[str, Any]) -> dict[str, Any]:
    return wyoming.normalize_feature(
        feature,
        response_schema_fingerprint="a" * 64,
        layer_schema_fingerprint="b" * 64,
        source_version={
            "data_last_edit": "2026-06-10T19:35:27Z",
            "schema_last_edit": "2026-06-10T19:35:27Z",
        },
    )


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = wyoming.build_query(
        "parcel",
        selector="37181840001700",
        parameters={"jurisdiction": "LINCOLN"},
        limit=None,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        records,
        retrieved_at="2026-07-31T12:00:00Z",
    ).to_dict()


def _source_manifest() -> dict[str, Any]:
    payload = yaml.safe_load(SOURCE_CONFIG.read_text(encoding="utf-8"))
    return next(
        source
        for source in payload["sources"]
        if source["source_id"] == wyoming.SOURCE_ID
    )


def test_shared_routes_cover_every_standalone_operation() -> None:
    routes = query_property.LIVE_ROUTES[wyoming.SOURCE_ID]
    guidance = query_property._source_guidance(wyoming.SOURCE_ID)

    assert set(routes) == SHARED_OPERATIONS
    assert guidance["occurrence_identity"] == "release-scoped FID"
    assert guidance["direct_default"] == "all_matching_ordered_FID_offset_pages"
    assert set(guidance["shared_selectors"]) == SHARED_OPERATIONS - {"search"}

    cases = (
        (("search", "STATE", "--search-field", "owner"), "owner"),
        (("owner", "STATE"), "owner"),
        (("parcel", "49720332401200"), "parcel"),
        (("account", "R0059774"), "account"),
        (("county", "56005"), "county"),
        (("jurisdiction", "Campbell"), "jurisdiction"),
        (("address", "KETTLESON"), "situs"),
        (("situs", "KETTLESON"), "situs"),
        (("mailing", "BISHOP"), "mailing"),
        (("legal", "LEGACY RIDGE"), "legal"),
        (("fid", "30558"), "fid"),
        (("map", "49720332401200"), "parcel"),
        (("geometry", "30558"), "geometry"),
        (
            (
                "point",
                "--longitude",
                "-105.5013",
                "--latitude",
                "44.2526",
            ),
            "point",
        ),
        (("bbox", "1,2,3,4"), "bbox"),
        (("discovery", "agreement"), "discovery"),
        (("probe",), "probe"),
    )
    for shared_values, expected_command in cases:
        translated = _translated(
            *shared_values,
            "--source",
            wyoming.SOURCE_ID,
        )
        assert translated.command == expected_command

    assert _translated(
        "county",
        "56005",
        "--source",
        wyoming.SOURCE_ID,
    ).query == "Campbell"
    assert _translated(
        "map",
        "49720332401200",
        "--source",
        wyoming.SOURCE_ID,
    ).geometry is True


def test_shared_translation_has_no_implicit_cap_and_preserves_caller_window() -> None:
    exhaustive = _translated(
        "owner",
        "STATE OF WYOMING",
        "--source",
        wyoming.SOURCE_ID,
        "--jurisdiction",
        "56005",
    )
    bounded = _translated(
        "owner",
        "STATE OF WYOMING",
        "--source",
        wyoming.SOURCE_ID,
        "--county",
        "Campbell",
        "--tax-year",
        "2026",
        "--limit",
        "7",
        "--cursor",
        "arcgis:offset:7",
        "--max-records",
        "21",
        "--page-size",
        "777",
    )

    assert exhaustive.jurisdiction == "CAMPBELL"
    assert exhaustive.limit is None
    assert exhaustive.cursor is None
    assert exhaustive.max_records is None
    assert bounded.jurisdiction == "CAMPBELL"
    assert bounded.tax_year == "2026"
    assert bounded.limit == 7
    assert bounded.cursor == "arcgis:offset:7"
    assert bounded.max_records == 21
    assert bounded.page_size == 777


def _projected_state(db_path: Path) -> dict[str, Any]:
    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT jurisdiction_geoid, native_parcel_id, roll_year, raw_json
            FROM parcel_snapshot WHERE source_id=?
            """,
            (wyoming.SOURCE_ID,),
        ).fetchone()
        geometry = db.execute(
            """
            SELECT geometry_ref, geometry_format, crs, snapshot_date
            FROM parcel_geometry WHERE source_id=?
            """,
            (wyoming.SOURCE_ID,),
        ).fetchone()
        aliases = [
            tuple(row)
            for row in db.execute(
                """
                SELECT alias_type, alias_value FROM parcel_alias
                WHERE source_id=? ORDER BY alias_type, alias_value
                """,
                (wyoming.SOURCE_ID,),
            )
        ]
        observations = [
            tuple(row)
            for row in db.execute(
                """
                SELECT source_native_id, record_kind FROM source_observation
                WHERE source_id=? ORDER BY source_native_id
                """,
                (wyoming.SOURCE_ID,),
            )
        ]
        owners = [
            tuple(row)
            for row in db.execute(
                """
                SELECT assertion_type, raw_owner_name, claim_type, source_quote
                FROM ownership_assertion WHERE source_id=?
                ORDER BY raw_owner_name
                """,
                (wyoming.SOURCE_ID,),
            )
        ]
        assessments = [
            tuple(row)
            for row in db.execute(
                """
                SELECT tax_year, market_value_minor, assessed_value_minor,
                       currency
                FROM assessment WHERE source_id=? ORDER BY tax_year
                """,
                (wyoming.SOURCE_ID,),
            )
        ]
        addresses = [
            tuple(row)
            for row in db.execute(
                """
                SELECT address_role, raw_address, city, state, postal_code
                FROM parcel_address WHERE source_id=? ORDER BY address_role
                """,
                (wyoming.SOURCE_ID,),
            )
        ]
        assertion_counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("sale_event", "recorded_instrument")
        }
    finally:
        db.close()

    raw = json.loads(parcel["raw_json"])
    return {
        "parcel": tuple(parcel[:3]),
        "representative_fid": raw["native_feature_id"],
        "representative_complete": raw["snapshot_completeness"],
        "geometry": tuple(geometry),
        "aliases": aliases,
        "observations": observations,
        "owners": owners,
        "assessments": assessments,
        "addresses": addresses,
        "assertion_counts": assertion_counts,
    }


def test_methodology_2169_projection_is_order_independent_and_retains_all_fids(
    tmp_path: Path,
) -> None:
    features = _feature("multipart_features.json")
    for feature in features:
        fid = feature["attributes"]["FID"]
        feature["geometry"] = {
            "rings": [
                [
                    [-105.0, 44.0],
                    [-105.0, 44.1],
                    [-104.9, 44.1],
                    [-105.0, 44.0],
                ]
            ],
            "fixture_fid": fid,
        }
    records = [_normalized(feature) for feature in features]
    occurrence_only = _normalized(_feature("blank_feature.json"))
    states = []

    for name, ordered in (
        ("ascending", records),
        ("descending", list(reversed(records))),
    ):
        db_path = tmp_path / f"{name}.db"
        report = ingest_property_envelope(
            _envelope([*ordered, occurrence_only]),
            db_path=db_path,
        )
        assert report["records_ingested"] == 3
        assert report["records_preserved_without_projection"] == 1
        assert report["projection_skips"][0]["source_native_id"] == "FID:107174"
        states.append(_projected_state(db_path))

    assert states[0] == states[1]
    state = states[0]
    assert state["parcel"][0] == "56023"
    assert state["parcel"][2] == "2026"
    assert state["representative_fid"] == "195144"
    assert state["representative_complete"] == {
        "all_FID_occurrences_retained": True,
        "annual_join": "tax_year_jurisdiction_parcel_account",
        "representative_rule": "lowest_numeric_FID",
    }
    assert state["geometry"] == (
        "source-occurrence:us-wy-dor-statewide-parcels:FID:195144#/geometry",
        "esri_json",
        "EPSG:4326",
        "2026-01-01",
    )
    assert {
        value
        for alias_type, value in state["aliases"]
        if alias_type == "wy_dor_fid_occurrence"
    } == {"FID:195144", "FID:195145", "FID:195146"}
    assert set(state["observations"]) == {
        (None, "query_envelope"),
        ("FID:107174", "wy_dor_unresolved_geometry_occurrence"),
        ("FID:195144", "wy_dor_annual_parcel_geometry_occurrence"),
        ("FID:195145", "wy_dor_annual_parcel_geometry_occurrence"),
        ("FID:195146", "wy_dor_annual_parcel_geometry_occurrence"),
    }
    assert state["owners"] == [
        (
            "assessment_roll",
            "BRIDGE-TARGHEE PLACE LLC",
            "direct_quote",
            "BRIDGE-TARGHEE PLACE LLC",
        )
    ]
    assert state["assessments"] == [("2026", 1_200_296_400, 114_028_100, "USD")]
    assert len(state["addresses"]) == 2
    assert state["assertion_counts"] == {
        "sale_event": 0,
        "recorded_instrument": 0,
    }


def _probe_result(
    *,
    release_year: str,
    fid: int,
    owner: str,
    actual_value: int,
    count: int,
    extra_schema_field: str | None = None,
) -> PublicRecordsResult:
    feature = _feature("sentinel_feature.json")
    feature["attributes"].update(
        {
            "FID": fid,
            "taxyear": release_year,
            "ownername1": owner,
            "actualvalu": actual_value,
        }
    )
    record = _normalized(feature)
    required_fields = {
        field: {"name": field, "type": "esriFieldTypeString"}
        for field in wyoming.REQUIRED_FIELDS
    }
    if extra_schema_field:
        required_fields[extra_schema_field] = {
            "name": extra_schema_field,
            "type": "esriFieldTypeString",
        }
    record["source_probe"] = {
        "root_application_agreement": {
            "app_identity": {
                "id": wyoming.ROOT_APP_ITEM_ID,
                "type": "Web Mapping Application",
                "owner": "dave.chapman@wyo.gov",
                "access": "public",
            },
            "app_data": {
                "app_item_id": wyoming.ROOT_APP_ITEM_ID,
                "title": wyoming.ROOT_APP_DATA_TITLE,
                "subtitle": f"Current as of January 1, {release_year}",
                "web_map_item_id": "982879668f2847c79211d6d91de9418a",
            },
            "parcel_query_routes": [
                {
                    "widget_id": "queryWidget",
                    "widget_label": "Query",
                    "query_name": "Parcel Number",
                    "url": wyoming.LAYER_URL,
                    "fields": ["accountno", "parcelnb"],
                }
            ],
            "implemented_layer_url": wyoming.LAYER_URL,
        },
        "layer_validation": {
            "native_page_size": 2_000,
            "schema": {
                "identity": {"type": "Feature Layer"},
                "supports_pagination": True,
                "supports_order_by": True,
                "required_fields": required_fields,
            },
        },
        "statewide_occurrence_count": count,
    }
    query = wyoming.build_query(
        "probe",
        selector={"parcel_number": wyoming.PROBE_PARCEL},
        parameters={"bounded_exact_sentinel": True},
        limit=None,
        cursor=None,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-31T12:00:00Z",
    )


def test_monitor_separates_stable_contracts_from_rolling_release_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {
        "release_year": "2026",
        "fid": 30_558,
        "owner": "STATE OF WYOMING",
        "actual_value": 424_342,
        "count": 373_666,
        "extra_schema_field": None,
    }

    def fake_execute(_args: Any, **_kwargs: Any) -> PublicRecordsResult:
        return _probe_result(**state)

    monkeypatch.setattr(wyoming, "execute", fake_execute)
    context = ProbeContext(
        source_id=wyoming.SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )
    first = probe_wyoming_dor_statewide_parcels(context)
    state.update(
        release_year="2027",
        fid=40_001,
        owner="WYOMING GAME AND FISH COMMISSION",
        actual_value=430_000,
        count=374_100,
    )
    rolling = probe_wyoming_dor_statewide_parcels(context)
    rolling_comparison = compare_probes(first.to_dict(), rolling.to_dict())

    assert set(first.details["stable_fingerprints"]) == {
        "app",
        "layer",
        "schema",
        "identity",
        "paging",
    }
    assert first.schema_sha256 == rolling.schema_sha256
    assert first.artifact_sha256 == rolling.artifact_sha256
    assert rolling_comparison["drift_detected"] is False
    assert first.details["rolling_observation"] != rolling.details[
        "rolling_observation"
    ]

    state["extra_schema_field"] = "future_required_field"
    changed = probe_wyoming_dor_statewide_parcels(context)
    stable_comparison = compare_probes(rolling.to_dict(), changed.to_dict())
    assert changed.schema_sha256 != rolling.schema_sha256
    assert changed.artifact_sha256 != rolling.artifact_sha256
    assert stable_comparison["drift_detected"] is True


def test_monitor_registry_matches_five_request_probe() -> None:
    handler = public_records_monitor.HANDLER_REGISTRY[wyoming.SOURCE_ID]

    assert handler.expected_requests == 5
    assert handler.sentinel_record_count == 1
    assert handler.sample_bytes is None
    assert handler.handler is probe_wyoming_dor_statewide_parcels


def test_catalog_census_search_plan_source_report_and_citation(
    tmp_path: Path,
) -> None:
    manifest = _source_manifest()
    census = yaml.safe_load(CENSUS_CONFIG.read_text(encoding="utf-8"))
    county_inventory = manifest["county_inventory"]
    associations = {
        (row["jurisdiction_geoid"], row["role"])
        for row in manifest["census_associations"]
    }
    jurisdictions = {
        row["geoid"]: row for row in census["additional_jurisdictions"]
    }
    targets = {
        (row["jurisdiction_geoid"], row["domain"], row["role"])
        for row in census["additional_targets"]
    }

    assert set(manifest["jurisdiction_geoids"]) == {
        "56",
        *WYOMING_COUNTY_GEOIDS,
    }
    assert set(county_inventory) == WYOMING_COUNTY_GEOIDS
    assert len(associations) == 46
    assert associations == {
        (geoid, role)
        for geoid in WYOMING_COUNTY_GEOIDS
        for role in ("assessment_roll", "parcel_geometry")
    }
    assert manifest["process_learnings"][0].startswith(
        "methodology_observation_2169"
    )
    assert manifest["access_review"]["limits"]["bounded_probe_requests"] == 5
    probe_capability = next(
        capability
        for capability in manifest["capabilities"]
        if capability["name"] == "probe_source"
    )
    assert probe_capability["details"]["expected_requests"] == 5
    for geoid in WYOMING_COUNTY_GEOIDS:
        assert jurisdictions[geoid]["parent_geoid"] == "56"
        assert (geoid, "property", "assessment_roll") in targets
        assert (geoid, "property", "parcel_geometry") in targets

    catalog_path = tmp_path / "catalog.db"
    seeded = seed_catalog(db_path=catalog_path)
    assert seeded["manifests_registered"] > 0
    plan = public_records_search_plan.build_search_plan(
        "STATE OF WYOMING",
        jurisdictions=("56005",),
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
        profiles_dir=tmp_path / "profiles",
    )
    tasks = {
        task["task_id"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "property"
        for task in stage["tasks"]
        if task["source_id"] == wyoming.SOURCE_ID
    }
    assert tasks == {
        f"property.{wyoming.SOURCE_ID}.fetch_account",
        f"property.{wyoming.SOURCE_ID}.fetch_geometry",
        f"property.{wyoming.SOURCE_ID}.fetch_parcel",
        f"property.{wyoming.SOURCE_ID}.search_address",
        f"property.{wyoming.SOURCE_ID}.search_assessment_records",
        f"property.{wyoming.SOURCE_ID}.search_owner",
        f"property.{wyoming.SOURCE_ID}.search_parcels",
    }

    report = check_public_records_catalog(catalog_path)
    source_report = next(
        value
        for value in report.values()
        if value.get("source_id") == wyoming.SOURCE_ID
    )
    assert source_report["status"] == "configured"
    assert source_report["query_tool"] == "tools/query_property.py"

    citations = json.loads(CITATION_CONFIG.read_text(encoding="utf-8"))
    assert citations[f"PROPERTY_SOURCE:{wyoming.SOURCE_ID}"] == wyoming.ROOT_APP_URL
