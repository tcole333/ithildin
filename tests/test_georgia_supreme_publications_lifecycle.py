from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_georgia_supreme_publications as publications
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import (
    PublicRecordsResult,
    sha256_fingerprint,
)
from tools.public_records_monitor import ProbeContext, compare_probes
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
SOURCE_IDS = tuple(publications.SOURCE_METADATA)
COMPONENTS = {
    publications.OPINION_SOURCE_ID: ("opinions_and_summaries",),
    publications.CERT_GRANT_SOURCE_ID: ("certiorari_grants",),
    publications.CERT_DENIAL_SOURCE_ID: ("certiorari_denials",),
    publications.APPLICATION_GRANT_SOURCE_ID: (
        "discretionary_application_grants",
        "interlocutory_application_grants",
    ),
}
MONITOR_HASHES = {
    publications.OPINION_SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "5dff0ca608d91f42d92962cef2e069b1e85d08bf3ee2b5e942f8c5a238671dc3"
        ),
        "monitor_stable_contract_sha256": (
            "5f69deb925ccfdfe708d716c278f60c2649c25c0e54533d45f8837cbf10158d7"
        ),
        "monitor_artifact_identity_sha256": (
            "828b98e56d377d57981ae63378abc6a98dacc787c7f76827701e3afbdd3245c1"
        ),
    },
    publications.CERT_GRANT_SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "7bb6b7effaa12ab3f614c0a72b593032cafbd59964bee53144e0ed11fb670ee1"
        ),
        "monitor_stable_contract_sha256": (
            "8ab782b018b5f130cac47f9ab093381b5faeefe69d8b7027337f23b79ef2fcdf"
        ),
        "monitor_artifact_identity_sha256": (
            "328ab591be41908a33c578abfdf8069189924823cd72ee71c0ae029effaaab04"
        ),
    },
    publications.CERT_DENIAL_SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "8868a610495f60c93419d06a39ed1bc22fd49100d305d1fe63c296dc412f739a"
        ),
        "monitor_stable_contract_sha256": (
            "4f8f68623b6eda013b3953b3f75356b0f617bbc32a01e89e6ea5c65d2aed0eec"
        ),
        "monitor_artifact_identity_sha256": (
            "1794fbb3990cd6f854c9c7dcc869180f73bf8277a130a1ad6c062d9d8c2d7530"
        ),
    },
    publications.APPLICATION_GRANT_SOURCE_ID: {
        "monitor_stable_schema_sha256": (
            "9b6cdefcd0f3d3824b4a4ceaef3a6dcd97da05113782bf4a2105bcc9158ad6c0"
        ),
        "monitor_stable_contract_sha256": (
            "4c8f3e75ececc306dc03e5705b8fafbd04e042ebf3f33d93b89e969ac56c464a"
        ),
        "monitor_artifact_identity_sha256": (
            "fae35c441476ceab75dca09f8b71f1d75ea699d3b8bd95a90ac616f4b0ff8e97"
        ),
    },
}


def _context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={
            "limits": {"minimum_interval_seconds": 0.5},
        },
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_records(source_id: str, marker: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, component in enumerate(COMPONENTS[source_id], start=1):
        application_type = (
            "discretionary"
            if component == "discretionary_application_grants"
            else "interlocutory"
            if component == "interlocutory_application_grants"
            else None
        )
        source_url = publications._page_url(
            source_id,
            publications.VERIFIED_THROUGH_YEAR,
            application_type=application_type,
        )
        records.append(
            {
                "record_kind": "source_probe",
                "source_id": source_id,
                "status": "ok",
                "publication_component": component,
                "publication_year": publications.VERIFIED_THROUGH_YEAR,
                "record_count": 10 + index,
                "document_record_count": 5 + index,
                "source_url": source_url,
                "source_document_sha256": marker * 64,
                "schema_fingerprint": str(index) * 64,
                "snapshot_fingerprint": marker * 64,
                "page_updated_at": f"July {index}, 2026",
                "document_probe": {
                    "document_url": (
                        "https://www.gasupreme.us/wp-content/uploads/"
                        f"2026/07/{marker}{index}.pdf"
                    ),
                    "mime_type": "application/pdf",
                    "byte_count": 1000 + index,
                    "sha256": marker * 64,
                },
                "requests_made": 2,
            }
        )
    return records


def test_monitors_keep_rolling_indexes_and_pdfs_out_of_drift_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    markers = {source_id: "a" for source_id in SOURCE_IDS}
    calls: list[tuple[str, list[int] | None]] = []

    def fake_execute(
        args: Any,
        **_: Any,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert args.minimum_interval == 0.5
        assert args.year == [publications.VERIFIED_THROUGH_YEAR]
        calls.append((args.source, args.year))
        return PublicRecordsResult.success(
            publications.build_query(args),
            _probe_records(args.source, markers[args.source]),
        )

    monkeypatch.setattr(publications, "execute", fake_execute)

    first = {
        source_id: public_records_monitor.probe_georgia_supreme_publication(
            _context(source_id)
        )
        for source_id in SOURCE_IDS
    }
    markers.update({source_id: "b" for source_id in SOURCE_IDS})
    second = {
        source_id: public_records_monitor.probe_georgia_supreme_publication(
            _context(source_id)
        )
        for source_id in SOURCE_IDS
    }

    assert len(calls) == len(SOURCE_IDS) * 2
    for source_id in SOURCE_IDS:
        before = first[source_id]
        after = second[source_id]
        assert before.status == after.status == "ok"
        assert before.schema_sha256 == after.schema_sha256
        assert before.artifact_sha256 == after.artifact_sha256
        assert before.details["stable_contract"] == (
            after.details["stable_contract"]
        )
        assert before.details["schema_contract"] == (
            after.details["schema_contract"]
        )
        assert before.details["rolling_observation"] != (
            after.details["rolling_observation"]
        )
        assert before.details["stable_contract_sha256"] == (
            sha256_fingerprint(before.details["stable_contract"])
        )
        assert before.details["stable_schema_sha256"] == (
            sha256_fingerprint(before.details["schema_contract"])
        )
        assert before.schema_sha256 == MONITOR_HASHES[source_id][
            "monitor_stable_schema_sha256"
        ]
        assert before.details["stable_contract_sha256"] == (
            MONITOR_HASHES[source_id][
                "monitor_stable_contract_sha256"
            ]
        )
        assert before.artifact_sha256 == MONITOR_HASHES[source_id][
            "monitor_artifact_identity_sha256"
        ]
        assert before.details["requests_made"] == (
            4
            if source_id == publications.APPLICATION_GRANT_SOURCE_ID
            else 2
        )
        assert compare_probes(
            {
                "probe_id": 1,
                "status": before.status,
                "schema_sha256": before.schema_sha256,
                "artifact_sha256": before.artifact_sha256,
            },
            {
                "probe_id": 2,
                "status": after.status,
                "schema_sha256": after.schema_sha256,
                "artifact_sha256": after.artifact_sha256,
            },
        )["drift_detected"] is False


def test_catalog_census_shared_operations_and_component_identity(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)

    expected_roles = {
        publications.OPINION_SOURCE_ID: {
            "appellate_opinions",
            "supreme_court_opinion_index",
            "noteworthy_opinion_summaries",
            "direct_pdf_documents",
            "publication_revision_metadata",
        },
        publications.CERT_GRANT_SOURCE_ID: {
            "appellate_orders",
            "certiorari_grants",
            "appellate_chain_crosswalks",
            "direct_pdf_documents",
        },
        publications.CERT_DENIAL_SOURCE_ID: {
            "appellate_orders",
            "certiorari_denials",
            "html_decision_lists",
            "conditional_pdf_documents",
            "appellate_chain_crosswalks",
        },
        publications.APPLICATION_GRANT_SOURCE_ID: {
            "appellate_orders",
            "application_grant_orders",
            "discretionary_application_grants",
            "interlocutory_application_grants",
            "direct_pdf_documents",
        },
    }
    for source_id in SOURCE_IDS:
        assert catalog.require_machine_acquisition(source_id)["allowed"] is True
        manifest = catalog.show_source(source_id)["current_manifest"]
        assert manifest["record_identity_source_id"] == source_id
        assert set(manifest["roles"]) == expected_roles[source_id]
        capabilities = {
            item["name"]: item["details"]
            for item in manifest["capabilities"]
        }
        assert capabilities["query_shared_court_records"][
            "shared_operations"
        ] == [
            "case",
            "discovery",
            "documents",
            "download",
            "probe",
            "search",
        ]
        assert capabilities["ingest_state_court_records"][
            "inferred_parties"
        ] is False
        association = manifest["census_associations"][0]
        assert association["jurisdiction_geoid"] == "13"
        assert association["role"] == "appellate_opinions"
        assert association["coverage"]["coverage_status"] == "partial"
        assert association["coverage_gaps"]
        assert manifest["publication_contract"][
            "comprehensive_historical_opinion_archive"
        ] is False
        assert manifest["identity_contract"][
            "cross_component_matches_are_independent_corroboration"
        ] is False
        assert {
            field: manifest["probe_evidence"][field]
            for field in MONITOR_HASHES[source_id]
        } == MONITOR_HASHES[source_id]

    opinions = catalog.show_source(
        publications.OPINION_SOURCE_ID
    )["current_manifest"]
    assert opinions["publication_contract"]["verified_publication_years"] == (
        list(range(2017, 2027))
    )
    assert opinions["publication_contract"]["opinion_version_hierarchy"] == {
        "website": "subject_to_reconsideration_and_editorial_revision",
        "final_copy": (
            "advance_sheet_version_replaces_prior_website_and_docket_versions"
        ),
        "bound_georgia_reports": "final_and_official_text",
    }
    grants = catalog.show_source(
        publications.CERT_GRANT_SOURCE_ID
    )["current_manifest"]
    assert grants["identity_contract"][
        "court_of_appeals_crosswalk_relation"
    ] == "originating_appellate_case"
    assert grants["capabilities"][5]["details"][
        "lower_appellate_representation_is_independent_corroboration"
    ] is False

    census = PublicRecordsCensus(catalog_path)
    target = census.list_targets(
        state="GA",
        domain="court",
        role="appellate_opinions",
    )[0]
    assert set(SOURCE_IDS) <= set(target["source_ids"])

    audit = audit_catalog(db_path=catalog_path)
    mismatched_sources = {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    assert not set(SOURCE_IDS) & mismatched_sources


def test_public_docket_now_links_integrated_publication_components(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(
        "us-ga-supreme-court-public-docket"
    )["current_manifest"]

    assert set(SOURCE_IDS) <= set(manifest["complementary_source_ids"])
    integrated = {
        item["source_id"]
        for item in manifest["official_complements"]
        if item.get("integration_status") == "integrated_as_separate_source"
    }
    assert integrated == set(SOURCE_IDS)
    assert "infra_request_313" not in json.dumps(manifest, sort_keys=True)


def test_monitor_registry_is_bounded_for_all_four_sources() -> None:
    for source_id in SOURCE_IDS:
        spec = public_records_monitor.HANDLER_REGISTRY[source_id]
        assert spec.capability == "probe_source"
        assert spec.endpoint == (
            publications.SOURCE_METADATA[source_id].base_url
        )
        assert spec.expected_requests == (
            4
            if source_id == publications.APPLICATION_GRANT_SOURCE_ID
            else 2
        )
        assert spec.sentinel_record_count == 1
        assert spec.handler is (
            public_records_monitor.probe_georgia_supreme_publication
        )


def test_citations_and_docs_cover_each_component_and_version_state() -> None:
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    for source_id in SOURCE_IDS:
        assert source_urls[f"STATECOURT_SOURCE:{source_id}"] == (
            publications.SOURCE_METADATA[source_id].base_url
        )

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    assert "## Supreme Court of Georgia decision publications" in legal
    assert (
        "### Supreme Court of Georgia decision publications"
        in tool_reference
    )
    for source_id in SOURCE_IDS:
        assert source_id in legal
        assert source_id in tool_reference
    for marker in ("Final Copy", "bound Georgia Reports", "2,938", "1,660"):
        assert marker in legal
        assert marker in tool_reference
