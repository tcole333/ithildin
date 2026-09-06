from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools import query_wisconsin_wscca
from tools.ingest_state_court_records import validate_envelope


FIXTURE_DIR = Path("tests/fixtures/public_records/wisconsin_wscca")
SEARCH_PAYLOAD = json.loads(
    (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
)
CASE_PAYLOAD = json.loads(
    (FIXTURE_DIR / "case.json").read_text(encoding="utf-8")
)
DOWNLOAD_PAYLOAD = json.loads(
    (FIXTURE_DIR / "download-receipt.json").read_text(encoding="utf-8")
)
RSS_BYTES = (FIXTURE_DIR / "case-rss.xml").read_bytes()


class FakeRunner:
    def __init__(
        self,
        *,
        search: Mapping[str, Any] | None = None,
        case: Mapping[str, Any] | None = None,
        download: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.search = copy.deepcopy(search or SEARCH_PAYLOAD)
        self.case = copy.deepcopy(case or CASE_PAYLOAD)
        self.download = copy.deepcopy(download or DOWNLOAD_PAYLOAD)
        self.error = error
        self.calls: list[tuple[list[str], float]] = []

    def __call__(
        self,
        arguments: Sequence[str],
        timeout: float,
    ) -> Mapping[str, Any]:
        args = list(arguments)
        self.calls.append((args, timeout))
        if self.error is not None:
            raise self.error
        if args[0] == "search":
            return copy.deepcopy(self.search)
        if args[0] == "case":
            return copy.deepcopy(self.case)
        if args[0] == "download":
            return copy.deepcopy(self.download)
        if args[0] == "runtime-check":
            return {
                "ok": True,
                "node": "v22.0.0",
                "playwright_module": "playwright",
                "browser_channel": "chrome",
            }
        if args[0] == "probe":
            return {
                "ok": True,
                "operation": "probe",
                "case_found": True,
                "canonical_case_number": "2025AP000699",
                "past_event_count": 28,
                "document_count": 2,
            }
        raise AssertionError(f"unexpected helper operation: {args}")


def _parse(*values: str) -> Any:
    return query_wisconsin_wscca.build_parser().parse_args(list(values))


def _execute(
    args: Any,
    monkeypatch: Any,
    runner: FakeRunner | None = None,
):
    monkeypatch.setattr(
        query_wisconsin_wscca,
        "log_search",
        lambda *_args: None,
    )
    return query_wisconsin_wscca.execute(
        args,
        helper_runner=runner or FakeRunner(),
    )


def test_business_search_preserves_supreme_and_appellate_case_identity(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()

    payload = _execute(
        _parse(
            "search",
            "Wisconsin Voter Alliance",
            "--scope",
            "business",
        ),
        monkeypatch,
        runner,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 2
    supreme, appeals = payload["records"]
    assert supreme["raw_case_number"] == "2023AP000036"
    assert supreme["source_internal_id"] == "2023AP000036"
    assert supreme["court"]["court_id"] == (
        query_wisconsin_wscca.SUPREME_COURT_ID
    )
    assert supreme["public_domain_citations"] == ["2025 WI 2", "2026 WI 27"]
    assert appeals["court"]["court_id"] == (
        query_wisconsin_wscca.COURT_OF_APPEALS_ID
    )
    assert appeals["court"]["division"] == "District 4"
    assert appeals["filing_date"] == "2022-10-12"
    assert runner.calls[0][0] == [
        "search",
        "--scope",
        "business",
        "--query",
        "Wisconsin Voter Alliance",
        "--minimum-interval",
        "0.5",
    ]


def test_search_applies_caller_pagination_without_an_adapter_result_cap(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()

    first = _execute(
        _parse(
            "search",
            "Wisconsin Voter Alliance",
            "--scope",
            "business",
            "--limit",
            "1",
        ),
        monkeypatch,
        runner,
    ).to_dict()
    second = _execute(
        _parse(
            "search",
            "Wisconsin Voter Alliance",
            "--scope",
            "business",
            "--limit",
            "1",
            "--cursor",
            "wscca:search:offset:1",
        ),
        monkeypatch,
        runner,
    ).to_dict()

    assert [row["raw_case_number"] for row in first["records"]] == [
        "2023AP000036"
    ]
    assert first["next_cursor"] == "wscca:search:offset:1"
    assert [row["raw_case_number"] for row in second["records"]] == [
        "2022AP001749"
    ]
    assert second["next_cursor"] is None


def test_source_reported_count_larger_than_payload_is_explicit_partial(
    monkeypatch: Any,
) -> None:
    source = copy.deepcopy(SEARCH_PAYLOAD)
    source["total_reported"] = 3

    payload = _execute(
        _parse(
            "search",
            "Wisconsin Voter Alliance",
            "--scope",
            "business",
        ),
        monkeypatch,
        FakeRunner(search=source),
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "partial"
    assert len(payload["records"]) == 2
    assert payload["errors"][0]["code"] == "source_window_incomplete"
    assert payload["errors"][0]["details"]["total_reported"] == 3


def test_authoritative_empty_exact_case_is_no_results(
    monkeypatch: Any,
) -> None:
    source = {
        **CASE_PAYLOAD,
        "found": False,
        "source_status": 404,
        "result": None,
    }

    payload = _execute(
        _parse("case", "2099AP999999"),
        monkeypatch,
        FakeRunner(case=source),
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "no_results"
    assert payload["records"] == []
    assert payload["errors"] == []


def test_case_preserves_parties_circuit_link_events_documents_and_anomalies(
    monkeypatch: Any,
) -> None:
    payload = _execute(
        _parse("case", "2025AP000699"),
        monkeypatch,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    case = payload["records"][0]
    assert case["canonical_ref"].startswith(
        "STATECOURT:us-wi-wscca-public/wi-court-of-appeals/"
    )
    assert case["disposition"] == "Reversed and remanded"
    assert case["disposition_date"] == "2026-05-29"
    assert case["source_confidential_flag"] is False
    assert case["parties"][0]["raw_name"] == "Khider A.K. Elnimeiry"
    assert case["parties"][0]["native_visibility_state"] == "Visible"
    assert case["attorneys"][0]["raw_name"] == "John T. Fields"
    assert case["linked_circuit_cases"][0]["raw_case_number"] == "2021FA000731"
    assert case["linked_circuit_cases"][0]["native_county_number"] == 13
    assert case["linked_circuit_cases"][0]["source_id"] == "us-wi-wcca-public"
    assert [row["native_event_sequence"] for row in case["past_events"]] == [
        40,
        30,
        19,
    ]
    assert case["upcoming_events"][0]["due_date"] == "2025-12-05"
    assert case["upcoming_events"][0]["phase"] == "upcoming"
    brief = case["documents"][0]
    assert brief["native_document_id"] == "994970"
    assert brief["page_range_raw"] == "1-12"
    assert brief["page_count"] == 12
    brief_event = case["past_events"][2]
    assert brief_event["linked_documents"][0]["native_document_id"] == "994970"
    assert case["opinion_documents"][0]["source_id"] == (
        "us-wi-court-opinions"
    )


def test_docket_and_document_views_retain_native_ids_and_paginate(
    monkeypatch: Any,
) -> None:
    docket = _execute(
        _parse(
            "docket",
            "2025AP000699",
            "--limit",
            "2",
        ),
        monkeypatch,
    ).to_dict()
    documents = _execute(
        _parse(
            "documents",
            "2025AP000699",
            "--limit",
            "1",
            "--cursor",
            "wscca:documents:offset:1",
        ),
        monkeypatch,
    ).to_dict()

    assert [row["native_event_sequence"] for row in docket["records"]] == [
        40,
        30,
    ]
    assert docket["next_cursor"] == "wscca:docket:offset:2"
    assert documents["records"][0]["native_document_id"] == "948283"
    assert documents["records"][0]["native_event_sequence"] == 14
    assert documents["next_cursor"] is None


def test_download_emits_separate_artifact_identity_and_parent_reference(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    payload = _execute(
        _parse(
            "download",
            "2025AP000699",
            "994970",
            "--document-output",
            str(tmp_path / "brief.pdf"),
        ),
        monkeypatch,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    artifact = payload["records"][0]
    assert artifact["record_kind"] == "document_artifact"
    assert artifact["native_document_id"] == "994970"
    assert "/document_artifact/994970" in artifact["canonical_ref"]
    assert "/document/994970" in artifact["parent_document_ref"]
    assert artifact["byte_count"] == 2339634
    assert artifact["media_type"] == "application/pdf"
    assert artifact["sha256"] == (
        "a6229dee9660c009d4c06ce82e11cf4f639931507f33f76630f06bad231e71b6"
    )
    assert artifact["source_url"].endswith(
        "/api/case/2025AP000699/document/994970"
    )


def test_unlisted_document_is_human_required_with_alternate_routes(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    error = query_wisconsin_wscca.WSCCABrowserError(
        "The requested document ID is not listed",
        error_type="DocumentStateError",
        details={
            "case_number": "2025AP000699",
            "requested_document_id": "123",
            "listed_document_ids": [994970, 948283],
        },
    )
    payload = _execute(
        _parse(
            "download",
            "2025AP000699",
            "123",
            "--document-output",
            str(tmp_path / "missing.pdf"),
        ),
        monkeypatch,
        FakeRunner(error=error),
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "human_required"
    assert payload["errors"][0]["code"] == "document_not_listed"
    assert payload["errors"][0]["details"]["listed_document_ids"] == [
        994970,
        948283,
    ]
    assert any(
        route["source_id"] == "us-wi-state-law-library-briefs"
        for route in payload["errors"][0]["details"]["alternatives"]
    )


def test_rss_preserves_native_guid_description_and_document_link(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        query_wisconsin_wscca,
        "_fetch_rss",
        lambda *_args, **_kwargs: RSS_BYTES,
    )

    payload = _execute(
        _parse("rss", "2025AP000699"),
        monkeypatch,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert [row["native_entry_id"] for row in payload["records"]] == [
        "40",
        "19",
    ]
    brief = payload["records"][1]
    assert brief["native_rss_guid"] == "2025AP000699-19"
    assert brief["native_event_sequence"] == 19
    assert brief["court"]["court_id"] == (
        query_wisconsin_wscca.COURT_OF_APPEALS_ID
    )
    assert brief["canonical_ref"].endswith(
        "/2025AP000699/docket_entry/19"
    )
    assert brief["published_at"].startswith("2025-08-06T00:00:00")
    assert brief["linked_source_urls"] == [
        "https://wscca.wicourts.gov/api/case/2025AP000699/document/994970"
    ]
    assert "Brief of Appellant" in brief["description"]


def test_routes_keep_distinct_evidentiary_roles(monkeypatch: Any) -> None:
    payload = _execute(_parse("routes"), monkeypatch).to_dict()

    assert payload["status"] == "ok"
    by_source = {row["source_id"]: row for row in payload["records"]}
    assert by_source[query_wisconsin_wscca.SOURCE_ID]["operations"] == [
        "search_cases",
        "fetch_case",
        "list_docket_entries",
        "list_documents",
        "fetch_document",
        "case_rss",
    ]
    assert by_source["us-wi-wcca-public"]["adds"].startswith(
        "Circuit case metadata"
    )
    assert by_source["us-wi-uw-law-historical-briefs"]["gaps"].startswith(
        "Historical collection ends"
    )
    assert by_source["us-wi-wcca-rest"]["operations"] == [
        "obtain_feed",
        "sync_circuit_case_metadata",
    ]


def test_runtime_probe_and_challenge_failure_are_structured(
    monkeypatch: Any,
) -> None:
    runtime = _execute(
        _parse("runtime-check"),
        monkeypatch,
    ).to_dict()
    probe = _execute(
        _parse("probe"),
        monkeypatch,
    ).to_dict()
    challenge = query_wisconsin_wscca.WSCCABrowserError(
        "Source validation remained interactive",
        error_type="SourceChallengeError",
        details={"case_number": "2025AP000699"},
    )
    failed = _execute(
        _parse("case", "2025AP000699"),
        monkeypatch,
        FakeRunner(error=challenge),
    ).to_dict()

    assert runtime["status"] == "ok"
    assert runtime["records"][0]["playwright_module"] == "playwright"
    assert probe["records"][0]["document_count"] == 2
    assert failed["status"] == "human_required"
    assert failed["errors"][0]["code"] == "source_validation_required"


def test_source_specific_browser_helper_is_present_and_session_native() -> None:
    source = query_wisconsin_wscca.HELPER_PATH.read_text(encoding="utf-8")

    assert "case-search" in source
    assert "/api/case/" in source
    assert "captcha/validate/search" in source
    assert "context.request.get" in source
    assert "cookie-list" not in source
    assert "storageState" not in source
