from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from tools import (
    public_records_monitor,
    query_ny_salesweb,
    query_ny_statewide_parcels,
    query_property,
)
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import DEFAULT_CONFIG_PATH, seed_catalog


FIXTURE_ROOT = Path(
    "tests/fixtures/public_records/ny_statewide_parcels"
)


def _normalized_component(component_key: str) -> dict:
    fixture = json.loads(
        (FIXTURE_ROOT / "features.json").read_text(encoding="utf-8")
    )
    component = query_ny_statewide_parcels.COMPONENTS[component_key]
    feature = fixture[component_key][0]
    snapshot = query_ny_statewide_parcels.SourceSnapshot(
        component=component_key,
        schema_fingerprint=component_key[0] * 64,
        dataset_title=f"2025 fixture {component_key}",
        assessment_year=2025,
        publication_date="May 2026",
        page_size=1_000,
        geometry_type=component.geometry_type,
    )
    batch = query_ny_statewide_parcels.TraversalBatch(
        records=(feature,),
        next_cursor=None,
        total_count=1,
        consumed_count=1,
        remaining_count=0,
        pages_fetched=1,
        snapshot=snapshot,
    )
    return query_ny_statewide_parcels._normalize_feature(
        feature,
        batch,
        component,
        geometry_requested=True,
    )


def _component_envelope(component_key: str) -> dict:
    record = _normalized_component(component_key)
    args = query_ny_statewide_parcels.build_parser().parse_args(
        [
            "parcel",
            record["native_id"],
            "--collection",
            component_key,
            "--geometry",
        ]
    )
    return PublicRecordsResult.success(
        query_ny_statewide_parcels.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _salesweb_record() -> dict:
    fixture_root = Path(
        "tests/fixtures/public_records/ny_salesweb"
    )
    detail_payload = json.loads(
        (fixture_root / "detail.json").read_text(encoding="utf-8")
    )["app"]["data"]
    row = detail_payload["oServiceResponse"]["data"]["salesWebRow"]
    references = detail_payload["aRefTblResponse"]["data"]
    return query_ny_salesweb._normalize_record(
        row,
        references,
        detail=True,
        include_raw=False,
        source_snapshot={
            "schema_fingerprint": "d" * 64,
            "reference_schema_fingerprint": "e" * 64,
        },
    )


def _salesweb_envelope() -> dict:
    record = _salesweb_record()
    args = query_ny_salesweb.build_parser().parse_args(
        ["detail", record["sale_record_id"]]
    )
    return PublicRecordsResult.success(
        query_ny_salesweb.build_query(args),
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()


def _shared_args(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_new_york_components_join_one_parcel_and_retain_each_observation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"

    reports = [
        ingest_property_envelope(
            _component_envelope(component),
            db_path=db_path,
        )
        for component in ("centroids", "public-parcels", "state-owned")
    ]

    assert all(report["records_ingested"] == 1 for report in reports)
    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, jurisdiction_geoid, native_parcel_id, roll_year,
                   raw_json
            FROM parcel_snapshot
            WHERE source_id=?
            """,
            (query_ny_statewide_parcels.SOURCE_ID,),
        ).fetchall()
        assert len(parcels) == 1
        assert tuple(parcels[0])[:4] == (
            parcels[0]["parcel_id"],
            "36001",
            "01010004100000021270000000",
            "2025",
        )
        assert '"component":"centroids"' in parcels[0]["raw_json"]

        observation_kinds = {
            row["record_kind"]
            for row in db.execute(
                """
                SELECT record_kind FROM source_observation
                WHERE source_id=? AND record_kind<>'query_envelope'
                """,
                (query_ny_statewide_parcels.SOURCE_ID,),
            )
        }
        assert observation_kinds == {
            "statewide_annual_parcel_assessment_centroid",
            "statewide_annual_public_parcel_polygon",
            "state_owned_parcel_polygon",
        }
        assert (
            db.execute(
                "SELECT COUNT(*) FROM ownership_assertion"
            ).fetchone()[0]
            == 1
        )
        geometry = db.execute(
            """
            SELECT geometry_format, crs, accuracy_disclaimer
            FROM parcel_geometry
            """
        ).fetchone()
        assert tuple(geometry) == (
            "esri_json",
            "EPSG:4326",
            (
                "County-contributed statewide parcel geometry is a mapping "
                "representation; consult the county source and recorded "
                "instruments for controlling boundary detail."
            ),
        )
        aliases = {
            row["alias_value"]
            for row in db.execute(
                "SELECT alias_value FROM parcel_alias"
            )
        }
        assert {
            "01010041.00-2-127",
            "01010031094",
            "010100",
            "04100000021270000000",
            "41.00-2-127",
        } <= aliases
    finally:
        db.close()


def test_salesweb_sale_joins_then_yields_to_statewide_parcel_snapshot(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    sale_record = _salesweb_record()
    parcel_id = sale_record["property"]["parcel_identifiers"][
        "swis_print_key_id"
    ]

    sale_report = ingest_property_envelope(
        _salesweb_envelope(),
        db_path=db_path,
    )
    centroid = _normalized_component("centroids")
    centroid["native_id"] = parcel_id
    centroid["native_id_type"] = "swis_print_key_id"
    centroid["parcel_identifiers"] = {
        **dict(centroid["parcel_identifiers"]),
        "swis": "012000",
        "print_key": "91.-1-30.11",
        "swis_sbl_id": None,
        "swis_print_key_id": parcel_id,
        "municipal_parcel_id": None,
    }
    centroid["cross_component_join_keys"] = [
        {"field": "SWIS_PRINT_KEY_ID", "value": parcel_id}
    ]
    centroid_args = query_ny_statewide_parcels.build_parser().parse_args(
        ["parcel", parcel_id]
    )
    centroid_envelope = PublicRecordsResult.success(
        query_ny_statewide_parcels.build_query(centroid_args),
        [centroid],
        retrieved_at="2026-07-30T12:05:00Z",
    ).to_dict()
    parcel_report = ingest_property_envelope(
        centroid_envelope,
        db_path=db_path,
    )

    assert sale_report["records"][0]["parcels_linked"] == 1
    assert sale_report["records"][0]["parcel_placeholder_created"] == 1
    assert sale_report["records"][0]["ownership_assertions_upserted"] == 0
    assert parcel_report["records"][0]["parcel_id"] == (
        sale_report["records"][0]["parcel_id"]
    )

    db = connect_property(db_path)
    try:
        parcels = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id, roll_year, raw_json
            FROM parcel_snapshot
            WHERE native_parcel_id=?
            """,
            (parcel_id,),
        ).fetchall()
        assert len(parcels) == 1
        assert tuple(parcels[0])[:4] == (
            parcels[0]["parcel_id"],
            query_ny_statewide_parcels.SOURCE_ID,
            parcel_id,
            "2025",
        )
        assert '"component":"centroids"' in parcels[0]["raw_json"]

        instrument = db.execute(
            """
            SELECT instrument_type, native_document_id, book, page,
                   consideration_minor
            FROM recorded_instrument
            WHERE source_id=?
            """,
            (query_ny_salesweb.SOURCE_ID,),
        ).fetchone()
        assert tuple(instrument) == (
            "rp5217_transfer_index_reference",
            sale_record["sale_record_id"],
            "2025",
            "19127",
            75_000_000,
        )
        parties = [
            tuple(row)
            for row in db.execute(
                """
                SELECT role, raw_name FROM instrument_party
                ORDER BY sequence_no
                """
            )
        ]
        assert {role for role, _name in parties} == {"grantor", "grantee"}
        link = db.execute(
            """
            SELECT link_method, link_confidence
            FROM instrument_parcel
            """
        ).fetchone()
        assert tuple(link) == ("exact_swis_print_key_id", 1.0)
        sale = db.execute(
            """
            SELECT native_sale_id, derivation, consideration_minor
            FROM sale_event WHERE source_id=?
            """,
            (query_ny_salesweb.SOURCE_ID,),
        ).fetchone()
        assert tuple(sale) == (
            sale_record["sale_record_id"],
            "state_taxation_transfer_report_index",
            75_000_000,
        )
        assert (
            db.execute(
                """
                SELECT COUNT(*) FROM ownership_assertion
                WHERE source_id=?
                """,
                (query_ny_salesweb.SOURCE_ID,),
            ).fetchone()[0]
            == 0
        )
    finally:
        db.close()


def test_new_york_shared_routes_select_component_field_and_book_page() -> None:
    routes = query_property.LIVE_ROUTES[
        query_ny_statewide_parcels.SOURCE_ID
    ]
    owner = routes["owner"].translate(
        _shared_args(
            "owner",
            "EXAMPLE HOLDINGS LLC",
            "--source",
            query_ny_statewide_parcels.SOURCE_ID,
            "--jurisdiction",
            "36027",
            "--tax-year",
            "2025",
            "--limit",
            "7",
        ),
        routes["owner"].adapter_command,
    )
    assert owner.command == "owner"
    assert owner.collection == "centroids"
    assert owner.county == "36027"
    assert owner.roll_year == 2025
    assert owner.limit == 7

    agency = routes["search"].translate(
        _shared_args(
            "search",
            "DEC",
            "--source",
            query_ny_statewide_parcels.SOURCE_ID,
            "--search-field",
            "agency",
        ),
        routes["search"].adapter_command,
    )
    assert agency.command == "agency"
    assert agency.collection == "state-owned"

    point = routes["point"].translate(
        _shared_args(
            "point",
            "--source",
            query_ny_statewide_parcels.SOURCE_ID,
            "--",
            "-73.868,42.721",
        ),
        routes["point"].adapter_command,
    )
    assert point.command == "point"
    assert point.collection == "public-parcels"
    assert (point.longitude, point.latitude) == (-73.868, 42.721)
    assert point.geometry is True

    deed = routes["instrument"].translate(
        _shared_args(
            "instrument",
            "3085/788",
            "--source",
            query_ny_statewide_parcels.SOURCE_ID,
        ),
        routes["instrument"].adapter_command,
    )
    assert deed.command == "deed"
    assert (deed.book, deed.page) == (3085, 788)


def test_salesweb_shared_routes_keep_party_sale_and_parcel_selectors() -> None:
    routes = query_property.LIVE_ROUTES[query_ny_salesweb.SOURCE_ID]
    buyer = routes["owner"].translate(
        _shared_args(
            "owner",
            "EXAMPLE LLC",
            "--source",
            query_ny_salesweb.SOURCE_ID,
            "--jurisdiction",
            "36001",
            "--tax-year",
            "2025",
            "--limit",
            "20",
        ),
        routes["owner"].adapter_command,
    )
    assert buyer.command == "search"
    assert buyer.buyer == "EXAMPLE LLC"
    assert buyer.seller is None
    assert buyer.county == ["Albany"]
    assert (buyer.sale_from, buyer.sale_to) == (
        "2025-01-01",
        "2025-12-31",
    )
    assert buyer.limit == 20

    seller = routes["owner"].translate(
        _shared_args(
            "owner",
            "PRIOR OWNER",
            "--source",
            query_ny_salesweb.SOURCE_ID,
            "--search-field",
            "seller",
        ),
        routes["owner"].adapter_command,
    )
    assert seller.seller == "PRIOR OWNER"
    assert seller.buyer is None

    parcel = routes["parcel"].translate(
        _shared_args(
            "parcel",
            "91.-1-30.11",
            "--source",
            query_ny_salesweb.SOURCE_ID,
        ),
        routes["parcel"].adapter_command,
    )
    assert parcel.tax_map == "91.-1-30.11"

    detail = routes["sale"].translate(
        _shared_args(
            "sale",
            "2047101021",
            "--source",
            query_ny_salesweb.SOURCE_ID,
        ),
        routes["sale"].adapter_command,
    )
    assert detail.command == "detail"
    assert detail.sale_transaction_number == 2047101021


def _coverage_result(component_count: int) -> PublicRecordsResult:
    args = query_ny_statewide_parcels.build_parser().parse_args(["coverage"])
    components = [
        {
            "component": key,
            "record_count": component_count + index,
            "dataset_title": f"2025 {key} fixture",
            "assessment_year": 2025,
            "publication_date": "May 2026",
            "schema_fingerprint": str(index + 1) * 64,
            "geometry_type": component.geometry_type,
            "native_max_record_count": 1_000,
        }
        for index, (key, component) in enumerate(
            query_ny_statewide_parcels.COMPONENTS.items()
        )
    ]
    record = {
        "source_id": query_ny_statewide_parcels.SOURCE_ID,
        "component_counts": components,
        "public_polygon_county_coverage": {
            "county_count": 2,
            "counties": [
                {
                    "county_name": "Albany",
                    "county_fips": "001",
                    "county_geoid": "36001",
                },
                {
                    "county_name": "Bronx",
                    "county_fips": "005",
                    "county_geoid": "36005",
                },
            ],
        },
        "cross_component_join_keys": [
            "SWIS_SBL_ID",
            "SWIS_PRINT_KEY_ID",
            "MUNI_PARCEL_ID",
        ],
    }
    return PublicRecordsResult.success(
        query_ny_statewide_parcels.build_query(args),
        [record],
    )


def test_new_york_monitor_separates_contract_from_rolling_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rolling_count = 100

    def fake_execute(_args):
        return _coverage_result(rolling_count)

    monkeypatch.setattr(
        public_records_monitor.query_ny_statewide_parcels,
        "execute",
        fake_execute,
    )
    context = public_records_monitor.ProbeContext(
        source_id=query_ny_statewide_parcels.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.1}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_new_york_statewide_parcels(context)
    rolling_count = 200
    second = public_records_monitor.probe_new_york_statewide_parcels(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    handler = public_records_monitor.HANDLER_REGISTRY[
        query_ny_statewide_parcels.SOURCE_ID
    ]
    assert handler.handler is (
        public_records_monitor.probe_new_york_statewide_parcels
    )
    assert handler.expected_requests == 24


def _salesweb_probe_result(total: int) -> PublicRecordsResult:
    args = query_ny_salesweb.build_parser().parse_args(["probe"])
    record = {
        "source_id": query_ny_salesweb.SOURCE_ID,
        "record_type": "source_probe",
        "reference_tables": {
            "counts": {
                "muniRef": 2_080,
                "schlRef": 700,
                "propRef": 519,
                "saleConRef": 20,
            },
            "schema_fingerprint": "a" * 64,
        },
        "bounded_search": {
            "municipality_code": "012000",
            "reported_total_matches": total,
            "returned_rows": 1,
            "schema_fingerprint": "b" * 64,
        },
        "detail": {
            "checked": True,
            "native_sale_transaction_number": 2_047_101_021 + total,
            "schema_fingerprint": "c" * 64,
            "sale_transaction_identity_present": True,
            "swis_print_key_join_present": True,
        },
        "requests_made": 3,
    }
    return PublicRecordsResult.success(
        query_ny_salesweb.build_query(args),
        [record],
    )


def test_salesweb_monitor_separates_contract_from_weekly_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    total = 10

    def fake_execute(_args):
        return _salesweb_probe_result(total)

    monkeypatch.setattr(
        public_records_monitor.query_ny_salesweb,
        "execute",
        fake_execute,
    )
    context = public_records_monitor.ProbeContext(
        source_id=query_ny_salesweb.SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0.1}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_new_york_salesweb(context)
    total = 12
    second = public_records_monitor.probe_new_york_salesweb(context)

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    handler = public_records_monitor.HANDLER_REGISTRY[
        query_ny_salesweb.SOURCE_ID
    ]
    assert handler.handler is public_records_monitor.probe_new_york_salesweb
    assert handler.expected_requests == 3


def test_new_york_catalog_models_partial_geometry_and_source_alternatives(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(
        DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")
    )
    sources = {
        source["source_id"]: source for source in config["sources"]
    }
    primary = sources[query_ny_statewide_parcels.SOURCE_ID]
    assert primary["source_status"] == "active"
    assert primary["automation_disposition"] == "allowed_with_limits"
    assert {
        "us-ny-statewide-parcels-bulk",
        "us-ny-county-parcel-resource-directory",
        "us-ny-orpts-sales-web",
        "us-nyc-acris",
        "us-ny-ogs-land-records",
        "us-ny-assessment-coordinate-lookup",
    } <= set(primary["complementary_source_ids"])
    associations = {
        association["role"]: association
        for association in primary["census_associations"]
    }
    assert associations["assessment_roll"]["coverage"]["statewide"] is True
    assert (
        associations["parcel_geometry"]["coverage"][
            "public_polygon_counties"
        ]
        == 38
    )
    assert (
        sources["us-ny-statewide-parcels-bulk"][
            "record_identity_source_id"
        ]
        == query_ny_statewide_parcels.SOURCE_ID
    )
    assert sources["us-ny-assessment-coordinate-lookup"][
        "probe_evidence"
    ]["assessment_output_fields_populated"] is False
    salesweb = sources[query_ny_salesweb.SOURCE_ID]
    assert salesweb["probe_evidence"]["native_sale_identity"] == (
        "saleTranNmbr"
    )
    assert salesweb["probe_evidence"]["exact_statewide_join"] == (
        "swisCd_plus_printKey_to_SWIS_PRINT_KEY_ID"
    )
    assert sources["us-ny-richmond-county-clerk-land-documents"][
        "census_associations"
    ][0]["coverage"]["county_geoids"] == ["36085"]

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    census = PublicRecordsCensus(catalog_path)
    assessment = census.list_targets(
        state="NY",
        domain="property",
        role="assessment_roll",
    )[0]
    geometry = census.list_targets(
        state="NY",
        domain="property",
        role="parcel_geometry",
    )[0]
    assert query_ny_statewide_parcels.SOURCE_ID in assessment["source_ids"]
    assert query_ny_statewide_parcels.SOURCE_ID in geometry["source_ids"]
