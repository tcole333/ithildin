from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import public_records_monitor
from tools import query_edva_bankruptcy as edva
from tools import query_state_courts
from tools.public_records_catalog import PublicRecordsCatalog
from tools.public_records_census import PublicRecordsCensus
from tools.public_records_contract import PublicRecordsResult, sha256_fingerprint
from tools.public_records_monitor import ProbeContext
from tools.seed_public_records_catalog import audit_catalog, seed_catalog


ROOT = Path(__file__).resolve().parents[1]
MONITOR_HASHES = {
    "monitor_stable_schema_sha256": (
        "710c11420b24f9f8ef361602bdb4b939bbc4129c0edb86850ac69c6c206915df"
    ),
    "monitor_stable_contract_sha256": (
        "26ed1c8b4c8c5a2c919e20d96037591053a7e6c3b89a7aa4ea219efdaf84d45b"
    ),
    "monitor_artifact_identity_sha256": (
        "9f6de0241e2f1b5f7a643f2416d6e8ba9d8c6b77d33d1772d7be0a8c9d490c5f"
    ),
}
RECAP_FETCH_FIELDS = [
    "court",
    "docket",
    "docket_number",
    "pacer_case_id",
    "pacer_password",
    "pacer_username",
    "recap_document",
    "request_type",
]


def _context() -> ProbeContext:
    return ProbeContext(
        source_id=edva.SOURCE_ID,
        catalog_decision={},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _probe_record(
    *,
    first_page_counts: tuple[int, int],
    first_page_has_next: tuple[bool, bool],
    date_suffix: str,
) -> dict[str, Any]:
    observations = []
    for index, sentinel in enumerate(edva.SENTINELS):
        observations.append(
            {
                "docket_number": sentinel["docket_number"],
                "courtlistener_docket_id": sentinel[
                    "courtlistener_docket_id"
                ],
                "pacer_case_id": sentinel["pacer_case_id"],
                "date_blocked": (
                    f"{sentinel['expected_date_blocked']}{date_suffix}"
                ),
                "first_page_entry_count": first_page_counts[index],
                "first_page_has_next": first_page_has_next[index],
                "matches_sentinel": True,
            }
        )
    return {
        "record_kind": "source_probe",
        "probe_scope": {
            "bounded": True,
            "docket_entry_pages_per_target": 1,
            "coverage_inference": False,
        },
        "sentinel_observations": observations,
        "recap_fetch_post_fields": RECAP_FETCH_FIELDS,
        "recap_fetch_contract_present": True,
        "healthy": True,
    }


def _run_fixture_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Any, Any, list[Any], list[Any]]:
    state = {
        "first_page_counts": (20, 16),
        "first_page_has_next": (True, False),
        "date_suffix": "",
    }
    clients: list[Any] = []
    calls: list[Any] = []

    class DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    def fake_execute(
        args: Any,
        *,
        client: Any,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert client is clients[-1]
        assert log_results is False
        calls.append(args)
        return PublicRecordsResult.success(
            edva._query("probe"),
            [_probe_record(**state)],
        )

    monkeypatch.setattr(edva, "EDVABankruptcyClient", DummyClient)
    monkeypatch.setattr(edva, "execute", fake_execute)

    first = public_records_monitor.probe_edva_bankruptcy(_context())
    state.update(
        first_page_counts=(18, 19),
        first_page_has_next=(False, True),
        date_suffix="T00:00:00Z",
    )
    second = public_records_monitor.probe_edva_bankruptcy(_context())
    return first, second, clients, calls


def test_monitor_is_read_only_and_separates_stable_from_rolling_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _context().catalog_decision == {}
    first, second, clients, calls = _run_fixture_monitor(monkeypatch)

    assert len(calls) == len(clients) == 2
    assert {call.command for call in calls} == {"probe"}
    assert all(client.closed for client in clients)
    assert all(
        set(client.kwargs) == {"timeout", "retry_policy"}
        for client in clients
    )
    assert all(client.kwargs["timeout"] == 5 for client in clients)
    assert all(
        client.kwargs["retry_policy"].max_attempts == 1
        for client in clients
    )

    assert first.status == second.status == "ok"
    assert first.result_count == second.result_count == 2
    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.details["stable_contract"] == second.details[
        "stable_contract"
    ]
    assert first.details["stable_contract_sha256"] == second.details[
        "stable_contract_sha256"
    ]
    assert first.details["schema_contract"] == second.details[
        "schema_contract"
    ]
    assert first.details["rolling_observation"] != second.details[
        "rolling_observation"
    ]
    assert first.schema_sha256 == sha256_fingerprint(
        first.details["schema_contract"]
    )
    assert first.details["stable_contract_sha256"] == sha256_fingerprint(
        first.details["stable_contract"]
    )
    request_contract = first.details["stable_contract"][
        "probe_request_contract"
    ]
    assert request_contract == {
        "sentinel_dockets": 2,
        "docket_entry_pages_per_target": 1,
        "requests_made": 5,
        "network_methods": ["GET", "OPTIONS"],
        "post_requests": 0,
        "document_retrieval_requests": 0,
    }
    assert first.details["requests_made"] == 5


def test_monitor_rejects_a_nonmatching_sentinel_after_closing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clients: list[Any] = []

    class DummyClient:
        def __init__(self, **_: Any) -> None:
            self.closed = False
            clients.append(self)

        def close(self) -> None:
            self.closed = True

    def fake_execute(
        args: Any,
        *,
        client: Any,
        log_results: bool,
    ) -> PublicRecordsResult:
        assert args.command == "probe"
        assert client is clients[-1]
        assert log_results is False
        record = _probe_record(
            first_page_counts=(1, 1),
            first_page_has_next=(False, False),
            date_suffix="",
        )
        record["sentinel_observations"][0]["matches_sentinel"] = False
        record["healthy"] = False
        return PublicRecordsResult.success(
            edva._query("probe"),
            [record],
        )

    monkeypatch.setattr(edva, "EDVABankruptcyClient", DummyClient)
    monkeypatch.setattr(edva, "execute", fake_execute)

    with pytest.raises(
        ValueError,
        match="EDVA bankruptcy probe contract changed",
    ):
        public_records_monitor.probe_edva_bankruptcy(_context())

    assert len(clients) == 1
    assert clients[0].closed is True


def test_catalog_census_shared_routes_and_complements_match_implementation(
    tmp_path: Path,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    catalog = PublicRecordsCatalog(catalog_path)
    census = PublicRecordsCensus(catalog_path)
    manifest = catalog.show_source(edva.SOURCE_ID)["current_manifest"]

    decision = catalog.require_machine_acquisition(edva.SOURCE_ID)
    assert decision["allowed"] is True
    assert decision["limits"] == {}
    assert manifest["record_identity_source_id"] == edva.SOURCE_ID
    assert manifest["roles"] == [
        "federal_bankruptcy_docket_archive",
        "exact_bankruptcy_case_resolution",
        "docket_entry_archive",
        "recap_document_metadata",
        "contributed_document_archive",
        "bankruptcy_access_route_inventory",
    ]

    capabilities = {
        item["name"]: item["details"] for item in manifest["capabilities"]
    }
    assert capabilities["query_shared_court_records"][
        "shared_operations"
    ] == [
        "case",
        "docket",
        "documents",
        "discovery",
        "probe",
    ]
    assert capabilities["query_shared_court_records"][
        "docket_and_documents_selector"
    ] == "positive_courtlistener_docket_id"
    assert sorted(query_state_courts.LIVE_ROUTES[edva.SOURCE_ID]) == [
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
    ]
    assert capabilities["ingest_state_court_records"][
        "source_occurrences"
    ] == ["docket", "docket_entry", "recap_document"]
    assert capabilities["ingest_state_court_records"][
        "document_access_states"
    ] == ["public_available_archive_document", "metadata_only"]
    assert capabilities["ingest_state_court_records"][
        "blocked_or_empty_archive_means_official_absence"
    ] is False
    assert capabilities["ingest_state_court_records"][
        "blocked_or_empty_archive_means_case_sealing"
    ] is False
    explicit = capabilities["request_explicit_recap_acquisition"]
    assert explicit["direct_commands"] == [
        "fetch-docket",
        "fetch-document",
        "fetch-status",
        "pray",
    ]
    assert explicit["shared_operations"] == []
    assert explicit["monitor_operations"] == []
    assert capabilities["probe_source"]["expected_requests"] == 5
    assert capabilities["probe_source"]["network_methods"] == [
        "GET",
        "OPTIONS",
    ]
    assert capabilities["probe_source"]["post_requests"] == 0
    assert capabilities["probe_source"]["document_retrieval_requests"] == 0
    assert {
        key: manifest["probe_evidence"][key] for key in MONITOR_HASHES
    } == MONITOR_HASHES

    publication = manifest["publication_contract"]
    assert publication["archive_is_official_pacer_docket"] is False
    assert publication[
        "empty_recap_entries_establish_official_empty_docket"
    ] is False
    assert publication[
        "courtlistener_date_blocked_establishes_case_sealing"
    ] is False
    assert publication["available_document_state"] == "public"
    assert publication["unavailable_document_state"] == "metadata_only"

    complements = {
        item["name"]: item for item in manifest["official_complements"]
    }
    assert set(complements) == {
        "PACER Case Locator",
        "E.D. Virginia CM/ECF and PACER",
        "E.D. Virginia Clerk copy request",
        "E.D. Virginia public access terminals",
        "National Archives and Federal Records Center court records",
    }
    assert all(
        item["dataset_equivalent"] is False
        for item in complements.values()
    )

    associations = manifest["census_associations"]
    assert len(associations) == 1
    assert associations[0]["jurisdiction_geoid"] == "51"
    assert associations[0]["role"] == "federal_bankruptcy_docket_archive"
    assert associations[0]["coverage"]["coverage_status"] == "partial"
    assert associations[0]["coverage"]["document_states"] == [
        "available",
        "metadata_only",
    ]
    assert edva.SOURCE_ID in next(
        target["source_ids"]
        for target in census.list_targets(
            state="VA",
            domain="court",
            role="federal_bankruptcy_docket_archive",
        )
        if edva.SOURCE_ID in target["source_ids"]
    )

    audit = audit_catalog(db_path=catalog_path)
    assert edva.SOURCE_ID not in {
        item["source_id"]
        for item in audit["shared_adapter_operation_mismatches"]
    }
    source_urls = json.loads(
        (ROOT / "web" / "src" / "data" / "source-urls.json").read_text(
            encoding="utf-8"
        )
    )
    assert source_urls[f"STATECOURT_SOURCE:{edva.SOURCE_ID}"] == (
        edva.RECAP_COVERAGE_URL
    )


def test_monitor_registry_and_lifecycle_documentation_are_source_specific(
) -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[edva.SOURCE_ID]
    assert spec.handler is public_records_monitor.probe_edva_bankruptcy
    assert spec.endpoint == edva.RECAP_COVERAGE_URL
    assert spec.expected_requests == 5
    assert spec.sentinel_record_count == 2

    legal = (ROOT / "docs" / "modules" / "legal.md").read_text(
        encoding="utf-8"
    )
    tool_reference = (ROOT / "docs" / "TOOL_REFERENCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (
        ROOT / "docs" / "PROPERTY_AND_LOCAL_COURT_RECORDS_ROADMAP.md"
    ).read_text(encoding="utf-8")
    citations = (ROOT / "web" / "src" / "lib" / "citations.ts").read_text(
        encoding="utf-8"
    )

    assert "## E.D. Virginia bankruptcy CourtListener/RECAP archive" in legal
    assert (
        "### E.D. Virginia bankruptcy RECAP archive adapter"
        in tool_reference
    )
    assert edva.SOURCE_ID in legal
    assert edva.SOURCE_ID in tool_reference
    assert "E.D. Virginia bankruptcy CourtListener/RECAP access" in roadmap
    assert "id: \"courtlistener_docket\"" in citations
    assert "CourtListener:docket(?:\\\\/|:)\\\\d+" in citations


@pytest.mark.live_data
def test_live_monitor_matches_stable_lifecycle_hashes() -> None:
    observation = public_records_monitor.probe_edva_bankruptcy(_context())

    assert observation.status == "ok"
    assert observation.result_count == 2
    assert observation.schema_sha256 == MONITOR_HASHES[
        "monitor_stable_schema_sha256"
    ]
    assert observation.details["stable_contract_sha256"] == MONITOR_HASHES[
        "monitor_stable_contract_sha256"
    ]
    assert observation.artifact_sha256 == MONITOR_HASHES[
        "monitor_artifact_identity_sha256"
    ]
    assert observation.details["requests_made"] == 5
    request_contract = observation.details["stable_contract"][
        "probe_request_contract"
    ]
    assert request_contract["post_requests"] == 0
    assert request_contract["document_retrieval_requests"] == 0
