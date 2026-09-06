from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import ingest_property_records as property_ingest
from tools import query_oregon_helion_recorder as helion
from tools import query_oregon_marion_downloads as marion
from tools import query_property
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.public_records_store import connect_property
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
CURRENT_CLERK_SOURCE_ID = "us-or-marion-clerk-recorded-documents"
HISTORICAL_DEEDS_SOURCE_ID = "us-or-marion-clerk-historical-deeds"


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={"allowed": True, "limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=64,
    )


def test_monitor_keeps_schema_contract_separate_from_release_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = 1
    release = marion.Release(
        source_id=marion.SALES_SOURCE_ID,
        release_id="sales-2026",
        label="2026 Sales Data",
        url="https://example.test/2026SalesData.csv",
        coverage_start=2026,
        coverage_end=2026,
        publication_kind="weekly_current_year",
        format="csv",
        schema_profile="sales_csv_descriptive_v3",
    )
    snapshot = marion.ManifestSnapshot(
        releases=(release,),
        landing_sha256="a" * 64,
    )

    def fake_execute(args: Any, **_kwargs: Any) -> PublicRecordsResult:
        record = {
            **release.manifest_record(snapshot),
            "record_kind": "source_probe",
            "artifact_probe": {
                "url": release.url,
                "etag": f'"release-{marker}"',
                "last_modified": f"2026-07-{marker:02d}T06:00:00Z",
                "content_length": 2_700_000 + marker,
                "sample_sha256": str(marker) * 64,
            },
            "validator_occurrence_identity": {
                "validator_occurrence_id": str(marker) * 64,
            },
        }
        return PublicRecordsResult.success(
            marion._build_query(args),
            [record],
        )

    monkeypatch.setattr(marion, "execute", fake_execute)
    first = public_records_monitor.probe_oregon_marion_download(
        _context(marion.SALES_SOURCE_ID)
    )
    marker = 2
    second = public_records_monitor.probe_oregon_marion_download(
        _context(marion.SALES_SOURCE_ID)
    )

    assert first.status == "ok"
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 != second.artifact_sha256
    assert first.details["schema_profile"] == "sales_csv_descriptive_v3"
    assert first.details["release_id"] == "sales-2026"
    assert first.details["artifact_probe"] != second.details["artifact_probe"]


def test_catalog_census_monitor_and_alternative_source_manifests(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)

    sales = catalog.show_source(marion.SALES_SOURCE_ID)["current_manifest"]
    assessment = catalog.show_source(
        marion.ASSESSMENT_SOURCE_ID
    )["current_manifest"]
    current_clerk = catalog.show_source(
        CURRENT_CLERK_SOURCE_ID
    )["current_manifest"]
    historical_deeds = catalog.show_source(
        HISTORICAL_DEEDS_SOURCE_ID
    )["current_manifest"]

    assert sales["source_status"] == "active"
    assert sales["adapter_family"] == "oregon_marion_public_downloads"
    assert sales["coverage_start"] == "1940"
    assert sales["probe_evidence"]["recognized_artifact_count"] == 15
    assert sales["probe_evidence"]["historical_legacy_xls_workbooks"] == [
        "1940-1949",
        "1950-1959",
        "1960-1969",
        "1970-1979",
    ]
    assert sales["probe_evidence"]["historical_zip_archives"] == [
        "1980-1989",
        "1990-1999",
        "2000-2009",
        "2010-2019",
    ]

    assert assessment["source_status"] == "active"
    assert assessment["adapter_family"] == (
        "oregon_marion_public_downloads"
    )
    assert assessment["probe_evidence"]["owner_names_included"] is False
    assert assessment["probe_evidence"][
        "latest_sale_labels_establish_title"
    ] is False
    assert assessment["census_associations"][0][
        "jurisdiction_geoid"
    ] == "41047"
    targets = census.list_targets(
        state="OR",
        domain="property",
        role="assessment_roll",
    )
    assert any(
        marion.ASSESSMENT_SOURCE_ID in target["source_ids"]
        for target in targets
    )

    assert current_clerk["source_status"] == "active"
    assert current_clerk["record_identity_source_id"] == (
        CURRENT_CLERK_SOURCE_ID
    )
    assert current_clerk["adapter_family"] == "oregon_helion_recorder"
    assert current_clerk["automation_disposition"] == "allowed_with_limits"
    current_capabilities = {
        capability["name"]: capability["details"]
        for capability in current_clerk["capabilities"]
    }
    assert set(current_capabilities) == {
        "search_instruments",
        "fetch_instrument",
        "probe_source",
    }
    assert "retrieve_published_document_images" not in current_capabilities
    assert "image_link" not in current_capabilities["fetch_instrument"][
        "output_components"
    ]
    assert current_clerk["probe_evidence"]["official_coverage_label"] == (
        "1974_to_present"
    )
    assert current_clerk["probe_evidence"][
        "sampled_detail_document_delivery_state"
    ] == "no_direct_image_ocr_or_cart_link"
    assert historical_deeds["source_status"] == "candidate"
    assert historical_deeds["record_identity_source_id"] == (
        HISTORICAL_DEEDS_SOURCE_ID
    )
    assert historical_deeds["probe_evidence"][
        "official_coverage_label"
    ] == "1855_to_1976"
    assert historical_deeds["probe_evidence"][
        "portal_form_coverage_wording"
    ] == "1850_to_1976"
    assert historical_deeds["probe_evidence"][
        "overlap_with_current_index"
    ] == "1974_to_1976"
    land_record_targets = census.list_targets(
        state="OR",
        domain="property",
        role="land_records_index",
    )
    marion_land_record_sources = {
        source_id
        for target in land_record_targets
        for source_id in target["source_ids"]
    }
    assert {
        CURRENT_CLERK_SOURCE_ID,
        HISTORICAL_DEEDS_SOURCE_ID,
    }.issubset(marion_land_record_sources)

    for source_id in marion.SOURCE_IDS:
        handler = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert handler.handler is (
            public_records_monitor.probe_oregon_marion_download
        )
        assert handler.expected_requests == 3
        assert handler.sample_bytes == 64

    current_clerk_handler = public_records_monitor.HANDLER_REGISTRY[
        CURRENT_CLERK_SOURCE_ID
    ]
    assert current_clerk_handler.handler is (
        public_records_monitor.probe_oregon_helion_recorder_component
    )
    assert current_clerk_handler.endpoint == (
        helion.TENANTS_BY_SOURCE[CURRENT_CLERK_SOURCE_ID].search_url
    )

    audit = audit_catalog(db_path=catalog_path)
    mismatches = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert not (set(marion.SOURCE_IDS) & mismatches)
    assert CURRENT_CLERK_SOURCE_ID not in mismatches


def test_marion_helion_manifest_and_monitor_contract() -> None:
    config = yaml.safe_load(
        (
            ROOT / "config" / "public_records_sources.yaml"
        ).read_text(encoding="utf-8")
    )
    sources = {source["source_id"]: source for source in config["sources"]}
    current = sources[CURRENT_CLERK_SOURCE_ID]
    historical = sources[HISTORICAL_DEEDS_SOURCE_ID]

    assert current["source_status"] == "active"
    assert current["adapter_family"] == "oregon_helion_recorder"
    assert current["record_identity_source_id"] == CURRENT_CLERK_SOURCE_ID
    assert current["automation_disposition"] == "allowed_with_limits"
    assert current["endpoints"]["portal"] == (
        helion.TENANTS_BY_SOURCE[CURRENT_CLERK_SOURCE_ID].portal_root
    )
    assert current["census_associations"][0]["jurisdiction_geoid"] == "41"
    assert current["census_associations"][0]["role"] == "land_records_index"
    capability_names = {
        capability["name"] for capability in current["capabilities"]
    }
    assert capability_names == {
        "search_instruments",
        "fetch_instrument",
        "probe_source",
    }
    assert current["probe_evidence"][
        "sampled_detail_document_delivery_state"
    ] == "no_direct_image_ocr_or_cart_link"

    assert historical["record_identity_source_id"] == (
        HISTORICAL_DEEDS_SOURCE_ID
    )
    assert historical["probe_evidence"]["official_coverage_label"] == (
        "1855_to_1976"
    )
    assert historical["probe_evidence"][
        "portal_form_coverage_wording"
    ] == "1850_to_1976"
    assert historical["probe_evidence"][
        "overlap_with_current_index"
    ] == "1974_to_1976"
    assert historical["census_associations"][0]["jurisdiction_geoid"] == "41"

    handler = public_records_monitor.HANDLER_REGISTRY[
        CURRENT_CLERK_SOURCE_ID
    ]
    assert handler.handler is (
        public_records_monitor.probe_oregon_helion_recorder_component
    )
    assert handler.endpoint == (
        helion.TENANTS_BY_SOURCE[CURRENT_CLERK_SOURCE_ID].search_url
    )


def test_marion_helion_shared_route_and_projection(tmp_path: Path) -> None:
    tenant = helion.TENANTS_BY_SOURCE[CURRENT_CLERK_SOURCE_ID]
    assert CURRENT_CLERK_SOURCE_ID in query_property.OREGON_HELION_RECORDER_SOURCE_IDS
    assert set(property_ingest.OREGON_HELION_RECORDER_SCOPES) == set(
        helion.SOURCE_IDS
    )

    route = query_property.LIVE_ROUTES[CURRENT_CLERK_SOURCE_ID]["instrument"]
    unified_args = query_property.build_parser().parse_args(
        [
            "instrument",
            "2026-000001",
            "--source",
            CURRENT_CLERK_SOURCE_ID,
            "--jurisdiction",
            "41047",
        ]
    )
    adapter_args = route.translate(unified_args, route.adapter_command)
    assert adapter_args.source == CURRENT_CLERK_SOURCE_ID
    assert adapter_args.year == 2026
    assert adapter_args.document_from == 1
    assert adapter_args.document_to == 1
    guidance = query_property._source_guidance(CURRENT_CLERK_SOURCE_ID)
    assert "no direct image, OCR-text, or cart link" in guidance[
        "resource_observation"
    ]
    assert {
        complement["kind"] for complement in guidance["official_complements"]
    } == {
        "marion_historical_deed_search",
        "marion_assessor_property_records",
        "marion_official_copy_and_certification",
    }

    fixture = (
        ROOT
        / "tests"
        / "fixtures"
        / "public_records"
        / "oregon_helion_recorder"
        / "marion_detail.html"
    )
    source_url = (
        f"{tenant.portal_root}Document/Details?year=2026&document=1"
    )
    record = helion.parse_detail_html(
        fixture.read_text(encoding="utf-8"),
        tenant=tenant,
        source_url=source_url,
    )
    assert record["document_image"]["availability"] == "not_advertised"
    assert record["document_image"]["url"] is None
    assert record["text_alternative"]["url"] is None
    assert record["copy_options"] == []
    assert record["cart_metadata"] is None

    direct_args = helion.build_parser().parse_args(
        ["detail", "--source", CURRENT_CLERK_SOURCE_ID, "2026", "1"]
    )
    query = helion.build_query(
        direct_args,
        decision={"source_id": CURRENT_CLERK_SOURCE_ID, "allowed": True},
    )
    envelope = PublicRecordsResult.success(
        query,
        [record],
        retrieved_at="2026-07-30T12:00:00Z",
    ).to_dict()
    db_path = tmp_path / "property.db"
    result = property_ingest.ingest_property_envelope(
        envelope,
        db_path=db_path,
    )
    assert result["projection_supported"] is True
    assert result["records"][0]["parties_upserted"] == 2
    assert result["records"][0]["documents_upserted"] == 0

    db = connect_property(db_path)
    try:
        instrument = db.execute(
            """
            SELECT source_id, jurisdiction_geoid, native_document_id,
                   instrument_type, recording_date, consideration_minor
            FROM recorded_instrument
            """
        ).fetchone()
        assert tuple(instrument) == (
            CURRENT_CLERK_SOURCE_ID,
            "41047",
            "2026-00001",
            "Assignment",
            "2026-01-02",
            51_700_000,
        )
        assert db.execute(
            "SELECT COUNT(*) FROM document_artifact"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_citations_docs_and_iteration_learnings_cover_all_marion_sources() -> None:
    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[
        f"PROPERTY_SOURCE:{marion.SALES_SOURCE_ID}"
    ] == marion.LANDING_URL
    assert source_urls[
        f"PROPERTY_SOURCE:{marion.ASSESSMENT_SOURCE_ID}"
    ] == marion.LANDING_URL
    assert source_urls[
        f"PROPERTY_SOURCE:{CURRENT_CLERK_SOURCE_ID}"
    ] == marion.MARION_RECORDED_DOCUMENTS_URL
    assert source_urls[
        f"PROPERTY_SOURCE:{HISTORICAL_DEEDS_SOURCE_ID}"
    ] == marion.MARION_HISTORICAL_DEEDS_URL

    property_docs = (
        ROOT / "docs" / "modules" / "property.md"
    ).read_text(encoding="utf-8")
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    resources = (
        ROOT / "research" / "OSINT_RESOURCES.md"
    ).read_text(encoding="utf-8")
    for source_id in (
        *marion.SOURCE_IDS,
        CURRENT_CLERK_SOURCE_ID,
        HISTORICAL_DEEDS_SOURCE_ID,
    ):
        assert source_id in property_docs
        assert source_id in tool_reference

    assert "duplicate bulk headers by position" in roadmap
    assert "publisher-visible release slot" in roadmap
    assert "artifact and member grain" in roadmap
    assert "omitted bulk fields as a routing opportunity" in roadmap
    assert "Derive shared lifecycle registration" in roadmap
    assert CURRENT_CLERK_SOURCE_ID in resources
    assert "image/OCR/cart link" in resources
