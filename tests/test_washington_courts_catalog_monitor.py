from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_washington_courts as washington
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_contract import PublicRecordsResult
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import seed_catalog


def _probe_record(
    source_id: str,
    *,
    checked_at: str,
    count: int,
    pdf_bytes: int,
    pdf_sha256: str,
) -> dict[str, Any]:
    if source_id == washington.DIRECTORY_SOURCE_ID:
        operations = {
            "county_index": "ok",
            "organization_detail": "ok",
            "pdf": "ok",
            "person_search": "ok",
        }
        evidence = {
            "county_count": count,
            "sentinel_org_heading": "Washington Supreme Court",
            "pdf_bytes": pdf_bytes,
            "pdf_sha256": pdf_sha256,
            "pdf_matches_observed_sentinel": False,
        }
    else:
        operations = {
            "rss": "ok",
            "information_sheet": "ok",
            "pdf": "ok",
            "by_year_enumeration": "ok",
            "general_search": "degraded_not_required",
        }
        evidence = {
            "feed_item_count": count,
            "sentinel_case_number": washington.KNOWN_OPINION_CASE,
            "pdf_bytes": pdf_bytes,
            "pdf_sha256": pdf_sha256,
            "pdf_matches_observed_sentinel": False,
        }
    return {
        "record_kind": "source_health_check",
        "source_id": source_id,
        "component_source_id": source_id,
        "adapter_family": washington.ADAPTER_FAMILY,
        "canonical_ref": f"WACOURT:PROBE:{source_id}:2026-07-30",
        "status": "ok",
        "checked_at": checked_at,
        "operations": operations,
        "evidence": evidence,
    }


@pytest.mark.parametrize(
    ("source_id", "first_count", "second_count"),
    [
        (washington.DIRECTORY_SOURCE_ID, 39, 40),
        (washington.OPINIONS_SOURCE_ID, 12, 14),
    ],
)
def test_monitor_keeps_rolling_washington_observations_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    first_count: int,
    second_count: int,
) -> None:
    rolling = {
        "checked_at": "2026-07-30T12:00:00Z",
        "count": first_count,
        "pdf_bytes": 1000,
        "pdf_sha256": "a" * 64,
    }

    def fake_execute(
        args: Any,
        *,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.component == [source_id]
        assert log_results is False
        return PublicRecordsResult.success(
            washington.build_query(args),
            [_probe_record(source_id, **rolling)],
        )

    monkeypatch.setattr(washington, "execute", fake_execute)
    context = ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )

    first = public_records_monitor.probe_washington_court_component(context)
    rolling.update(
        checked_at="2026-07-31T12:00:00Z",
        count=second_count,
        pdf_bytes=1200,
        pdf_sha256="b" * 64,
    )
    second = public_records_monitor.probe_washington_court_component(context)

    assert first.status == "ok"
    assert first.result_count == 1
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert (
        first.details["rolling_observation"]
        != second.details["rolling_observation"]
    )
    provenance = first.details["stable_contract"]["publisher_and_transport"]
    assert provenance == {
        "authority": "Washington State Judiciary",
        "publisher": "Washington State Administrative Office of the Courts",
        "retrieval_transport": "direct official HTTPS",
        "publisher_transport_distinct": False,
        "counts_as_independent_corroboration": False,
    }
    assert first.details["schema_contract"]["output_schema_version"] == (
        washington.OUTPUT_SCHEMA_VERSION
    )


def test_catalog_exposes_washington_sources_complements_and_census_roles(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    directory_decision = catalog.require_machine_acquisition(
        washington.DIRECTORY_SOURCE_ID
    )
    opinions_decision = catalog.require_machine_acquisition(
        washington.OPINIONS_SOURCE_ID
    )
    assert directory_decision["allowed"] is True
    assert opinions_decision["allowed"] is True
    assert directory_decision["limits"]["minimum_interval_seconds"] == 0.2
    assert opinions_decision["limits"]["minimum_interval_seconds"] == 0.2

    directory = catalog.show_source(washington.DIRECTORY_SOURCE_ID)[
        "current_manifest"
    ]
    opinions = catalog.show_source(washington.OPINIONS_SOURCE_ID)[
        "current_manifest"
    ]
    assert directory["identity_contract"]["shared_ingest_semantics"] == (
        "snapshot_only"
    )
    assert directory["publication_contract"]["publisher"] == (
        "Washington State Administrative Office of the Courts"
    )
    assert opinions["identity_contract"]["multi_docket_policy"] == (
        "one_case_projection_per_published_docket"
    )
    assert opinions["publication_contract"][
        "slip_opinion_may_be_replaced_by_final_published_report"
    ] is True
    assert {
        item["role"] for item in directory["census_associations"]
    } == {"court_directory"}
    assert {
        item["role"] for item in opinions["census_associations"]
    } == {"appellate_opinions"}

    expected_components = set(washington.COMPONENTS)
    for source_id in expected_components:
        manifest = catalog.show_source(source_id)["current_manifest"]
        assert manifest["source_status"] == "active"

    case_discovery = catalog.show_source(
        washington.CASE_DISCOVERY_SOURCE_ID
    )["current_manifest"]
    assert {
        item["role"] for item in case_discovery["census_associations"]
    } == {"trial_case_index", "appellate_case_index"}
    data_products = catalog.show_source(washington.DATA_PRODUCTS_SOURCE_ID)[
        "current_manifest"
    ]
    assert {
        item["role"] for item in data_products["census_associations"]
    } == {"bulk_data_program"}
    assert data_products["access_class"] == "D"
    assert data_products["automation_disposition"] == "not_applicable"

    directory_spec = public_records_monitor.HANDLER_REGISTRY[
        washington.DIRECTORY_SOURCE_ID
    ]
    opinions_spec = public_records_monitor.HANDLER_REGISTRY[
        washington.OPINIONS_SOURCE_ID
    ]
    assert directory_spec.handler is (
        public_records_monitor.probe_washington_court_component
    )
    assert opinions_spec.handler is (
        public_records_monitor.probe_washington_court_component
    )
    assert directory_spec.expected_requests == 3
    assert opinions_spec.expected_requests == 3


def test_washington_source_family_preserves_component_publishers() -> None:
    archive_metadata = washington.SOURCE_METADATA[
        washington.DIGITAL_ARCHIVES_SOURCE_ID
    ].to_dict()["metadata"]
    assert archive_metadata["authority"] == "Washington Secretary of State"
    assert archive_metadata["publisher"] == "Washington State Archives"

    for source_id in (
        washington.DIRECTORY_SOURCE_ID,
        washington.OPINIONS_SOURCE_ID,
        washington.CASE_DISCOVERY_SOURCE_ID,
    ):
        metadata = washington.SOURCE_METADATA[source_id].to_dict()["metadata"]
        assert metadata["authority"] == "Washington State Judiciary"
        assert metadata["publisher"] == (
            "Washington State Administrative Office of the Courts"
        )

    manifest_components = {
        item["source_id"]: item
        for item in washington._manifest_record()["components"]
    }
    assert manifest_components[washington.DIGITAL_ARCHIVES_SOURCE_ID][
        "publisher"
    ] == "Washington State Archives"
    assert manifest_components[washington.OPINIONS_SOURCE_ID]["publisher"] == (
        "Washington State Administrative Office of the Courts"
    )


def test_washington_source_and_complement_citation_urls_are_registered() -> None:
    source_urls_path = (
        Path(__file__).parents[1] / "web" / "src" / "data" / "source-urls.json"
    )
    source_urls = json.loads(source_urls_path.read_text(encoding="utf-8"))
    expected = {
        washington.DIRECTORY_SOURCE_ID: washington.DIRECTORY_HOME_URL,
        washington.OPINIONS_SOURCE_ID: washington.OPINIONS_HOME_URL,
        washington.CASE_DISCOVERY_SOURCE_ID: washington.CASE_FORM_URL,
        washington.CURRENT_ROUTES_SOURCE_ID: washington.CASE_HOME_URL,
        washington.APPELLATE_DOCUMENTS_SOURCE_ID: (
            washington.APPELLATE_DOCUMENT_URLS["appeals"]
        ),
        washington.DATA_PRODUCTS_SOURCE_ID: washington.DATA_PRODUCTS_URL,
        washington.JISLINK_SOURCE_ID: washington.JISLINK_URL,
        washington.APPELLATE_COMPLEMENTS_SOURCE_ID: (
            washington.APPELLATE_COMPLEMENT_URLS["briefs"]
        ),
        washington.CASELOAD_SOURCE_ID: washington.CASELOAD_URL,
        washington.DIGITAL_ARCHIVES_SOURCE_ID: (
            washington.DIGITAL_ARCHIVES_TITLE_BASE
        ),
    }
    for source_id, expected_url in expected.items():
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == expected_url
