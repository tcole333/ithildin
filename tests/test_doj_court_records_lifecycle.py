from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_doj_court_records as doj_courts
from tools import query_state_courts
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=doj_courts.SOURCE_ID,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=5,
    )


def _run_fixture_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Any, list[Any]]:
    state = {
        "case_count": 38,
        "document_count": 11,
        "has_next": True,
        "http_status": 206,
    }
    clients: list[Any] = []

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

        def fetch_index(self) -> tuple[dict[str, Any], ...]:
            sentinel = {
                "record_kind": "doj_court_case_listing",
                "canonical_ref": "DOJ-COURT-CASE:sentinel",
                "case_title": "United States v. Epstein, No. 119-cr-00490",
                "docket_number": "119-cr-00490",
                "case_page_url": doj_courts.SENTINEL_CASE_URL,
                "index_url": doj_courts.INDEX_URL,
                "publisher": "United States Department of Justice",
                "coverage_role": "official_release_case_group",
            }
            extras = [
                {
                    **sentinel,
                    "canonical_ref": f"DOJ-COURT-CASE:extra-{index}",
                    "case_title": f"Additional release group {index}",
                    "case_page_url": (
                        f"{doj_courts.INDEX_URL}/court-records-extra-{index}"
                    ),
                }
                for index in range(state["case_count"] - 1)
            ]
            return (sentinel, *extras)

        def fetch_case(
            self,
            case_url: str,
            *,
            one_page: bool,
        ) -> doj_courts.DocumentCollection:
            assert case_url == doj_courts.SENTINEL_CASE_URL
            assert one_page is True
            sentinel = {
                "record_kind": "doj_released_court_document",
                "efta_id": doj_courts.SENTINEL_EFTA,
            }
            documents = [
                sentinel,
                *[
                    {
                        "record_kind": "doj_released_court_document",
                        "efta_id": f"EFTA{index:08d}",
                    }
                    for index in range(1, state["document_count"])
                ],
            ]
            return doj_courts.DocumentCollection(
                case_title="United States v. Epstein",
                documents=tuple(documents),
                pages_fetched=1,
                source_urls=(doj_courts.SENTINEL_CASE_URL,),
                next_cursor="fixture-next" if state["has_next"] else None,
            )

    def fake_pdf_probe(
        url: str,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        assert url == doj_courts.SENTINEL_PDF_URL
        assert timeout == 5
        return {
            "source_url": doj_courts.SENTINEL_PDF_URL,
            "retrieved_url": doj_courts.SENTINEL_PDF_URL,
            "http_status": state["http_status"],
            "content_type": "application/pdf",
            "magic": "%PDF-",
            "bytes_read": 5,
        }

    monkeypatch.setattr(
        doj_courts,
        "DOJCourtRecordsClient",
        DummyClient,
    )
    monkeypatch.setattr(doj_courts, "probe_pdf_magic", fake_pdf_probe)

    first = public_records_monitor.probe_doj_epstein_court_records(
        _context()
    )
    state.update(
        case_count=41,
        document_count=14,
        has_next=False,
        http_status=200,
    )
    second = public_records_monitor.probe_doj_epstein_court_records(
        _context()
    )
    return first, second, clients


def test_monitor_keeps_rolling_release_counts_out_of_stable_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second, clients = _run_fixture_monitor(monkeypatch)

    assert first.status == second.status == "ok"
    assert first.result_count == 38
    assert second.result_count == 41
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["artifact_identity"] == second.details[
        "artifact_identity"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.details["requests_made"] == 3
    assert first.details["request_breakdown"] == {
        "release_index": 1,
        "sentinel_case_page": 1,
        "sentinel_pdf_range": 1,
    }
    assert first.details["stable_contract"]["probe_request_contract"] == {
        "requests_made": 3,
        "network_methods": ["GET"],
        "index_pages": 1,
        "case_pages": 1,
        "pdf_bytes_read": 5,
        "post_requests": 0,
        "request_breakdown": {
            "release_index": 1,
            "sentinel_case_page": 1,
            "sentinel_pdf_range": 1,
        },
    }
    assert all(
        client.kwargs["minimum_interval"] == 0 for client in clients
    )
    assert all(client.closed for client in clients)


def test_catalog_shared_routes_and_release_semantics_match_implementation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = catalog.show_source(doj_courts.SOURCE_ID)[
        "current_manifest"
    ]

    decision = catalog.require_machine_acquisition(doj_courts.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    assert manifest["record_identity_source_id"] == doj_courts.SOURCE_ID
    assert manifest["jurisdiction_geoids"] == ["US"]
    assert manifest["stable_keys"] == [
        "case_page_url",
        "efta_id",
        "indexed_source_url",
    ]
    assert manifest["identity_contract"][
        "case_group_identity_field"
    ] == "case_page_url"
    assert manifest["identity_contract"][
        "official_document_url_field"
    ] == "indexed_source_url"
    assert manifest["publication_contract"][
        "release_case_group_is_complete_underlying_docket"
    ] is False
    assert manifest["publication_contract"][
        "empty_release_result_establishes_no_underlying_court_record"
    ] is False
    assert manifest["publication_contract"][
        "normalized_case_projection"
    ] is False

    capabilities = {
        item["name"]: item["details"]
        for item in manifest["capabilities"]
    }
    assert capabilities["query_shared_court_records"][
        "shared_operations"
    ] == ["search", "documents", "discovery", "probe"]
    assert capabilities["query_shared_court_records"][
        "normalized_case_ingestion"
    ] is False
    assert "ingest_state_court_records" not in capabilities
    assert set(
        query_state_courts.LIVE_ROUTES[doj_courts.SOURCE_ID]
    ) == {"search", "documents", "discovery", "probe"}
    assert capabilities["probe_source"]["expected_requests"] == 3
    assert capabilities["probe_source"]["post_requests"] == 0
    assert capabilities["probe_source"]["downloaded_pdf_bytes"] == 5
    assert capabilities["probe_source"]["request_breakdown"] == {
        "release_index": 1,
        "sentinel_case_page": 1,
        "sentinel_pdf_range": 1,
    }

    complements = {
        item["name"]: item
        for item in manifest["official_complements"]
    }
    assert set(complements) == {
        "PACER and CM/ECF",
        "CourtListener and RECAP",
        "Named court clerk",
        "Local EFTA corpus",
    }
    assert all(
        item["dataset_equivalent"] is False
        for item in complements.values()
    )

    audit = audit_catalog(db_path=catalog_path)
    assert doj_courts.SOURCE_ID not in {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    source_urls = json.loads(
        (
            ROOT / "web" / "src" / "data" / "source-urls.json"
        ).read_text(encoding="utf-8")
    )
    assert source_urls[
        f"STATECOURT_SOURCE:{doj_courts.SOURCE_ID}"
    ] == doj_courts.INDEX_URL
    assert source_urls[
        f"DOJCOURT:{doj_courts.SENTINEL_EFTA}"
    ] == doj_courts.SENTINEL_PDF_URL


def test_monitor_registry_and_citation_type_are_source_specific() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[
        doj_courts.SOURCE_ID
    ]
    assert spec.handler is (
        public_records_monitor.probe_doj_epstein_court_records
    )
    assert spec.endpoint == doj_courts.INDEX_URL
    assert spec.expected_requests == 3
    assert spec.sample_bytes == 5

    citations = (
        ROOT / "web" / "src" / "lib" / "citations.ts"
    ).read_text(encoding="utf-8")
    citation_tests = (
        ROOT / "web" / "scripts" / "test-citations.mjs"
    ).read_text(encoding="utf-8")
    assert 'id: "doj_court_release"' in citations
    assert "DOJCOURT:EFTA\\\\d{8}" in citations
    assert "DOJCOURT:EFTA02824136" in citation_tests
    assert doj_courts.SOURCE_ID in citation_tests

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (
        ROOT / "docs" / "TOOL_REFERENCE.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")

    assert "## DOJ Epstein court-record release corpus" in legal
    assert "Three-request lifecycle probe" in legal
    assert "Omitted pacing is `0.0` seconds" in legal
    assert "### DOJ Epstein court-record release adapter" in tool_reference
    assert "[DOJCOURT:EFTA02824136]" in tool_reference
    assert "`0.0`-second interval" in tool_reference
    assert "### DOJ Epstein court-record release stack" in roadmap
    assert "publisher release corpus rather than a surrogate docket" in (
        roadmap
    )
