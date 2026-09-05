from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_oregon_lane_marion_parcels as lane_arcgis
from tools import query_oregon_lane_property as lane
from tools import query_property
from tools.ingest_property_records import ingest_property_envelope
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_store import connect_property


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_lane_property"
)
CATALOG = Path("config/public_records_sources.yaml")


def _shared(*values: str):
    return query_property.build_parser().parse_args(list(values))


def _envelope(
    source_id: str,
    records: list[dict[str, Any]],
    *,
    operation: str = "search",
) -> dict[str, Any]:
    return PublicRecordsResult.success(
        lane._query(source_id, operation, parameters={"fixture": True}),
        records,
        retrieved_at="2026-07-30T15:00:00Z",
    ).to_dict()


def _lane_arcgis_envelope() -> dict[str, Any]:
    source_id = lane_arcgis.LANE_PARCELS_SOURCE_ID
    config = lane_arcgis.SOURCES[source_id]
    feature = json.loads(
        (
            Path("tests/fixtures/public_records/oregon_lane_marion")
            / "lane_parcel.json"
        ).read_text(encoding="utf-8")
    )
    record = lane_arcgis._normalize_feature(
        config,
        feature,
        schema_value="lane-parcel-schema",
        geometry_requested=True,
    )
    record["native_parcel_id"] = "1605070001100"
    record["canonical_ref"] = (
        "PROPERTY:us-or-lane-county-assessor-parcels/"
        "41039/parcel/1605070001100"
    )
    record["alternate_parcel_ids"] = []
    record["assessment_account_ids"] = ["0057313"]
    query = lane_arcgis._build_query(
        config,
        operation="parcel",
        selector="1605070001100",
        search_field="parcel",
        limit=1,
        cursor=None,
        geometry=True,
    )
    return PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T16:00:00Z",
    ).to_dict()


def _multi_owner_search_records() -> list[dict[str, Any]]:
    rows = [
        {
            "AccountNumber": "0057313",
            "MapTaxLot": "1605070001100",
            "TaxPayer": "TAXPAYER LLC",
            "Owner": owner,
            "SitusAddress": "25745 HALL RD JUNCTION CITY 97448",
        }
        for owner in ("OWNER ALPHA", "OWNER BETA")
    ]
    return lane.parse_account_search(
        rows,
        f"{lane.ACCOUNT_API_URL}/accountnumbersearch/0057313",
    )


def test_catalog_promotes_both_sources_with_exact_lane_census_associations() -> None:
    config = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    sources = {source["source_id"]: source for source in config["sources"]}
    account = sources[lane.ACCOUNT_SOURCE_ID]
    tax_map = sources[lane.TAX_MAP_SOURCE_ID]

    assert account["source_status"] == tax_map["source_status"] == "active"
    assert account["adapter_family"] == tax_map["adapter_family"] == (
        "lane_county_property_sources"
    )
    assert {
        association["role"]
        for association in account["census_associations"]
    } == {"assessment_roll", "tax_collection"}
    assert {
        association["role"]
        for association in tax_map["census_associations"]
    } == {"parcel_geometry"}
    assert account["identity_contract"][
        "owner_index_and_taxpayer_are_distinct_roles"
    ] is True
    assert tax_map["identity_contract"][
        "locator_and_document_are_same_identity"
    ] is False
    assert {
        capability["name"] for capability in account["capabilities"]
    } >= {
        "search_property_accounts",
        "fetch_property_account",
        "probe_source",
    }
    assert {
        capability["name"] for capability in tax_map["capabilities"]
    } >= {"search_tax_maps", "fetch_tax_map", "probe_source"}


def test_shared_routes_translate_fields_and_keep_omitted_limit_exhaustive(
    tmp_path: Path,
) -> None:
    account_routes = query_property.LIVE_ROUTES[lane.ACCOUNT_SOURCE_ID]
    tax_map_routes = query_property.LIVE_ROUTES[lane.TAX_MAP_SOURCE_ID]
    assert set(account_routes) == {
        "search",
        "owner",
        "address",
        "parcel",
        "map",
        "account",
        "probe",
    }
    assert set(tax_map_routes) == {
        "search",
        "address",
        "parcel",
        "map",
        "download",
        "probe",
    }

    omitted = account_routes["owner"].translate(
        _shared(
            "owner",
            "NORTHWEST CLEARWOODS",
            "--source",
            lane.ACCOUNT_SOURCE_ID,
            "--jurisdiction",
            "41039",
        ),
        account_routes["owner"].adapter_command,
    )
    assert omitted.command == "search"
    assert omitted.field == "name"
    assert omitted.limit is None

    bounded = account_routes["parcel"].translate(
        _shared(
            "parcel",
            "1605070001100",
            "--source",
            lane.ACCOUNT_SOURCE_ID,
            "--limit",
            "8",
            "--max-records",
            "3",
        ),
        account_routes["parcel"].adapter_command,
    )
    assert bounded.field == "map_taxlot"
    assert bounded.limit == 3

    map_name = tax_map_routes["search"].translate(
        _shared(
            "search",
            "16050700",
            "--source",
            lane.TAX_MAP_SOURCE_ID,
            "--search-field",
            "map-name",
        ),
        tax_map_routes["search"].adapter_command,
    )
    assert map_name.field == "map_name"
    assert map_name.limit is None

    destination = tmp_path / "tax-map.pdf"
    download = tax_map_routes["download"].translate(
        _shared(
            "download",
            "326",
            "--source",
            lane.TAX_MAP_SOURCE_ID,
            "--destination",
            str(destination),
        ),
        tax_map_routes["download"].adapter_command,
    )
    assert download.command == "download-tax-map"
    assert download.document_id == "326"
    assert download.destination == str(destination)

    with pytest.raises(ValueError, match="Lane County"):
        account_routes["owner"].translate(
            _shared(
                "owner",
                "SMITH",
                "--source",
                lane.ACCOUNT_SOURCE_ID,
                "--jurisdiction",
                "41047",
            ),
            account_routes["owner"].adapter_command,
        )


def test_ingestion_reconciles_account_and_tax_map_to_lane_assessor_parcel(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "property.db"
    search_records = _multi_owner_search_records()
    search_report = ingest_property_envelope(
        _envelope(lane.ACCOUNT_SOURCE_ID, search_records),
        db_path=db_path,
    )
    shell_parcel_id = search_report["records"][0]["parcel_id"]
    assert search_report["records"][0]["parcel_placeholder_created"] == 1
    assert {
        record["source_occurrence_id"] for record in search_report["records"]
    } == {record["source_record_id"] for record in search_records}

    detail = lane.parse_account_detail(
        (FIXTURES / "account_detail.html").read_text(encoding="utf-8"),
        f"{lane.ACCOUNT_ROOT_URL}Account/0057313",
        expected_account="0057313",
        search_record=search_records,
    )
    detail_report = ingest_property_envelope(
        _envelope(
            lane.ACCOUNT_SOURCE_ID,
            [detail],
            operation="account",
        ),
        db_path=db_path,
    )
    assert detail_report["records"][0]["parcel_id"] == shell_parcel_id
    assert detail_report["records"][0]["owners_upserted"] == 2
    assert detail_report["records"][0]["assessments_upserted"] == len(
        detail["valuation_history"]
    )
    assert detail_report["records"][0]["tax_events_upserted"] == len(
        detail["recent_receipts"]
    )
    assert detail_report["records"][0][
        "source_representations_preserved"
    ] >= 6

    location_records = lane.parse_tax_map_search(
        (FIXTURES / "tax_map_location_results.html").read_text(
            encoding="utf-8"
        ),
        lane.TAX_MAP_SEARCH_URL,
    )
    map_name_records = lane.parse_tax_map_search(
        (FIXTURES / "tax_map_name_results.html").read_text(encoding="utf-8"),
        lane.TAX_MAP_SEARCH_URL,
    )
    tax_map_report = ingest_property_envelope(
        _envelope(
            lane.TAX_MAP_SOURCE_ID,
            [*location_records, *map_name_records],
        ),
        db_path=db_path,
    )
    assert tax_map_report["records"][0]["parcel_id"] == shell_parcel_id
    assert tax_map_report["records"][0]["locator_identity_preserved"] is True
    assert tax_map_report["records"][0]["document_identity_preserved"] is True
    assert tax_map_report["records_preserved_without_projection"] == 1
    assert tax_map_report["projection_skips"][0]["reason"] == (
        "lane_tax_map_locator_has_map_name_without_exact_map_taxlot"
    )

    assessor_report = ingest_property_envelope(
        _lane_arcgis_envelope(),
        db_path=db_path,
    )
    assert assessor_report["records"][0]["parcel_id"] == shell_parcel_id

    tax_map_path = tmp_path / "lane-tax-map-326.pdf"
    tax_map_path.write_bytes(b"%PDF-1.6\nfixture\n%%EOF\n")
    artifact_record = {
        "canonical_ref": (
            "PROPERTY:us-or-lane-tax-maps/41039/tax_map_document/326"
        ),
        "evidence_ref": (
            "PROPERTY:us-or-lane-tax-maps/41039/tax_map_document/326"
        ),
        "source_id": lane.TAX_MAP_SOURCE_ID,
        "source_url": (
            "https://apps.lanecounty.org/TaxMap/"
            "ViewFile.aspx?type=TM&id=326"
        ),
        "record_kind": "tax_map_document",
        "representation_kind": "official_pdf",
        "source_record_id": "326",
        "tax_map_document_id": "326",
        "media_type": "application/pdf",
        "size_bytes": tax_map_path.stat().st_size,
        "sha256": "a" * 64,
        "local_path": str(tax_map_path),
    }
    artifact_report = ingest_property_envelope(
        _envelope(
            lane.TAX_MAP_SOURCE_ID,
            [artifact_record],
            operation="download_tax_map",
        ),
        db_path=db_path,
    )
    assert artifact_report["records"][0]["locator_projected"] is False

    db = connect_property(db_path)
    try:
        parcel = db.execute(
            """
            SELECT parcel_id, source_id, native_parcel_id
            FROM parcel_snapshot
            """
        ).fetchall()
        assert [tuple(row) for row in parcel] == [
            (
                shell_parcel_id,
                lane_arcgis.LANE_PARCELS_SOURCE_ID,
                "1605070001100",
            )
        ]
        labels = {
            (row["assertion_type"], row["raw_owner_name"], row["source_id"])
            for row in db.execute(
                """
                SELECT assertion_type, raw_owner_name, source_id
                FROM ownership_assertion
                """
            )
        }
        assert (
            "assessment_roll",
            "OWNER ALPHA",
            lane.ACCOUNT_SOURCE_ID,
        ) in labels
        assert (
            "assessment_roll",
            "OWNER BETA",
            lane.ACCOUNT_SOURCE_ID,
        ) in labels
        assert (
            "tax_account",
            "TAXPAYER LLC",
            lane.ACCOUNT_SOURCE_ID,
        ) in labels
        assert db.execute(
            """
            SELECT COUNT(*) FROM assessment
            WHERE source_id=?
            """,
            (lane.ACCOUNT_SOURCE_ID,),
        ).fetchone()[0] == len(detail["valuation_history"])
        assert db.execute(
            """
            SELECT COUNT(*) FROM tax_account_event
            WHERE source_id=? AND event_type='property_tax_receipt'
            """,
            (lane.ACCOUNT_SOURCE_ID,),
        ).fetchone()[0] == len(detail["recent_receipts"])
        artifact = db.execute(
            """
            SELECT source_id, native_document_id, sha256, mime_type,
                   acquisition_method, rights_tier
            FROM document_artifact
            WHERE source_id=?
            """,
            (lane.TAX_MAP_SOURCE_ID,),
        ).fetchone()
        assert tuple(artifact) == (
            lane.TAX_MAP_SOURCE_ID,
            "326",
            "a" * 64,
            "application/pdf",
            "direct_source_pdf_download",
            "official_assessment_tax_map",
        )
        assert db.execute(
            "SELECT COUNT(*) FROM recorded_instrument"
        ).fetchone()[0] == 0
    finally:
        db.close()


def _monitor_context(source_id: str) -> public_records_monitor.ProbeContext:
    return public_records_monitor.ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=1,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_registers_both_sources_and_hashes_stable_semantics(
    monkeypatch,
) -> None:
    assert {
        lane.ACCOUNT_SOURCE_ID,
        lane.TAX_MAP_SOURCE_ID,
    } <= public_records_monitor.HANDLER_REGISTRY.keys()

    account_state = {"receipt_count": 6}

    def fake_execute(args, *, log_results=True):
        del log_results
        if args.source == lane.ACCOUNT_SOURCE_ID:
            record = {
                "canonical_ref": (
                    "LANE_PROPERTY_PROBE:"
                    f"{lane.ACCOUNT_SOURCE_ID}:{lane.ACCOUNT_SENTINEL}"
                ),
                "record_kind": "source_probe",
                "source_id": lane.ACCOUNT_SOURCE_ID,
                "anonymous_json_search_verified": True,
                "anonymous_session_detail_verified": True,
                "sentinel_account": lane.ACCOUNT_SENTINEL,
                "sentinel_map_taxlot": lane.MAP_TAXLOT_SENTINEL,
                "receipt_count": account_state["receipt_count"],
                "valuation_year_count": 11,
                "source_response_schema_fingerprint": "b" * 64,
            }
        else:
            record = {
                "canonical_ref": (
                    "LANE_PROPERTY_PROBE:"
                    f"{lane.TAX_MAP_SOURCE_ID}:{lane.TAX_MAP_DOCUMENT_SENTINEL}"
                ),
                "record_kind": "source_probe",
                "source_id": lane.TAX_MAP_SOURCE_ID,
                "anonymous_webforms_search_verified": True,
                "official_pdf_verified": True,
                "sentinel_map_taxlot": lane.MAP_TAXLOT_SENTINEL,
                "sentinel_map_name": "16050700",
                "sentinel_document_id": lane.TAX_MAP_DOCUMENT_SENTINEL,
                "document_size_bytes": 167041,
                "document_sha256": "c" * 64,
                "source_response_schema_fingerprint": "d" * 64,
            }
        return PublicRecordsResult.success(
            lane._query(args.source, "probe", parameters={}),
            [record],
            retrieved_at="2026-07-30T15:00:00Z",
        )

    monkeypatch.setattr(lane, "execute", fake_execute)
    first = public_records_monitor.probe_oregon_lane_property_source(
        _monitor_context(lane.ACCOUNT_SOURCE_ID)
    )
    account_state["receipt_count"] = 7
    second = public_records_monitor.probe_oregon_lane_property_source(
        _monitor_context(lane.ACCOUNT_SOURCE_ID)
    )
    tax_map = public_records_monitor.probe_oregon_lane_property_source(
        _monitor_context(lane.TAX_MAP_SOURCE_ID)
    )

    assert first.status == second.status == tax_map.status == "ok"
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["rolling_observation"]["receipt_count"] == 6
    assert second.details["rolling_observation"]["receipt_count"] == 7
    assert tax_map.details["rolling_observation"]["document_sha256"] == (
        "c" * 64
    )
    assert tax_map.details["stable_contract"]["identity_roles"] == [
        "locator_occurrence",
        "document",
    ]
