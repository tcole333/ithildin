from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_ohio_supreme_court as ohio
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_supreme_court"
)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def fixture_pdf() -> bytes:
    return bytes.fromhex(fixture_text("document.pdf.hex").strip())


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str = "",
        content: bytes | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.content = (
            content if content is not None else text.encode("utf-8")
        )
        self.status_code = status_code
        self.headers = headers or {}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def api_response(name: str) -> FakeResponse:
    return FakeResponse(
        url=ohio.AJAX_URL,
        text=fixture_text(name),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def client_responses(*api_names: str) -> list[FakeResponse]:
    return [
        FakeResponse(
            url=ohio.BASE_URL,
            text=fixture_text("bootstrap.html"),
            headers={"Content-Type": "text/html; charset=utf-8"},
        ),
        FakeResponse(
            url=f"{ohio.BASE_URL}scripts/dist/site.min.js?ver=3",
            text=fixture_text("site.min.js"),
            headers={"Content-Type": "application/javascript"},
        ),
        *(api_response(name) for name in api_names),
    ]


def parser_args(*values: str):
    return ohio.build_parser().parse_args(list(values))


def test_case_number_and_document_url_preserve_source_identities() -> None:
    parsed = ohio.parse_case_number("2017-1682")
    assert parsed.normalized == "2017-1682"
    assert ohio.parse_case_number("2017 1682").normalized == "2017-1682"

    url = ohio.build_document_url(
        "2017-1682",
        "835936.pdf",
        "DocketItems",
    )
    assert url.startswith(ohio.PDF_VIEWER_URL)
    assert "pdf=835936.pdf" in url
    assert "subdirectory=2017-1682%5CDocketItems" in url
    assert "source=DL_Clerk" in url


def test_bootstrap_discovers_token_and_search_preserves_complete_array() -> None:
    session = FakeSession(client_responses("search.json"))
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    rows = client.search(
        {
            "paramCaseYear": "",
            "paramCaseNumber": "",
            "paramCaseCaption": "LaPilusa",
        }
    )

    assert len(rows) == 1
    assert rows[0]["case_number"] == "2026-0970"
    assert rows[0]["source_search_id"] == 0
    assert len(session.requests) == 3
    assert session.requests[1]["url"].endswith(
        "scripts/dist/site.min.js?ver=3"
    )
    post = session.requests[2]
    assert post["method"] == "POST"
    assert post["url"] == ohio.AJAX_URL
    assert post["headers"]["X-CSRF-TOKEN"] == "fixture-csrf-token"
    assert post["headers"]["X-Requested-With"] == "XMLHttpRequest"
    assert post["data"]["action"] == "CaseSearch"
    assert post["data"]["paramCaseCaption"] == "LaPilusa"


def test_exact_case_keeps_case_docket_and_document_identities_distinct() -> None:
    session = FakeSession(client_responses("case.json"))
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    record = client.case("2017-1682")

    assert record["source_internal_case_locator"] == "100335"
    assert record["case_number"] == "2017-1682"
    assert record["prior_jurisdiction"]["prior_case_numbers"] == [
        {"Number": "9-17-42"}
    ]
    assert record["parties"][1]["attorneys"][0] == {
        "name": "Smith, Jane Example",
        "attorney_registration_number": "0012345",
        "counsel_of_record": True,
    }

    first_docket = record["docket_entries"][0]
    first_document = record["documents"][0]
    assert first_docket["native_docket_entry_id"] == "835936"
    assert first_docket["native_document_id"] == (
        "2017-1682:DocketItems:835936.pdf"
    )
    assert first_document["native_document_id"] == (
        "2017-1682:DocketItems:835936.pdf"
    )
    assert first_docket["canonical_ref"] != first_document["canonical_ref"]
    assert record["decisions"][0]["description_text"].startswith(
        "Granted; cause dismissed."
    )
    assert record["decisions"][0]["linked_urls"] == [
        "https://supremecourt.ohio.gov/rod/docs/pdf/0/2018/"
        "2018-ohio-723.pdf"
    ]
    assert record["retrieval"] == {
        "docket_entry_count": 3,
        "decision_count": 1,
        "document_count": 3,
        "source_response_pagination": "none",
        "complete_exact_case_response": True,
    }
    search_ref = ohio.normalize_search_row(
        {
            "ID": 0,
            "CaseNumber": "2017-1682",
            "Caption": record["caption"],
            "DateFiled": "2017-12-01T05:00:00",
            "Status": "Disposed",
            "CaseType": "Original Action in Procedendo",
            "PriorJurisdiction": "Third District Court of Appeals",
        }
    )["canonical_ref"]
    assert record["canonical_ref"] == search_ref


def test_exact_case_fails_visibly_on_non_object_party_or_issue() -> None:
    party_payload = fixture_json("case.json")
    party_payload["Parties"].append("unexpected")
    with pytest.raises(
        ohio.OhioSupremeCourtSourceChanged,
        match="Parties contains a non-object row",
    ):
        ohio.normalize_case_payload(
            party_payload,
            requested_case_number="2017-1682",
        )

    issue_payload = fixture_json("case.json")
    issue_payload["CaseIssues"].append("unexpected")
    with pytest.raises(
        ohio.OhioSupremeCourtSourceChanged,
        match="CaseIssues contains a non-object row",
    ):
        ohio.normalize_case_payload(
            issue_payload,
            requested_case_number="2017-1682",
        )


def test_authoritative_empty_search_is_not_a_source_failure() -> None:
    class EmptyClient:
        def search(self, parameters: dict[str, Any]):
            assert parameters["paramCaseCaption"] == "ZZZQXYNONEXISTENT"
            return []

    result = ohio.execute(
        parser_args("search", "--caption", "ZZZQXYNONEXISTENT"),
        client=EmptyClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_source_refinement_text_is_structured_not_false_no_results() -> None:
    session = FakeSession(client_responses("refinement.json"))
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    with pytest.raises(
        ohio.OhioSupremeCourtRefinementRequired,
        match="did not resolve",
    ):
        client.case("2026-9999")

    class RefinementClient:
        def search(self, parameters: dict[str, Any]):
            raise ohio.OhioSupremeCourtRefinementRequired(
                operation="search",
                source_response="Too many results",
            )

    result = ohio.execute(
        parser_args("search", "--caption", "Example"),
        client=RefinementClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.records == ()
    assert result.errors[0].code == "source_requires_refinement"
    assert result.errors[0].details["source_response"] == "Too many results"
    assert (
        result.errors[0].details["source_response_semantics"]
        == "server_declined_or_could_not_resolve_selection"
    )


def _search_records(count: int) -> list[dict[str, Any]]:
    return [
        ohio.normalize_search_row(
            {
                "ID": 0,
                "CaseNumber": f"2025-{index:04d}",
                "Caption": f"Fixture case {index}",
                "DateFiled": "2025-01-01T05:00:00",
                "Status": "Disposed",
                "CaseType": "Jurisdictional Appeal",
                "PriorJurisdiction": "Fifth District Court of Appeals",
            }
        )
        for index in range(count)
    ]


def test_observed_thousand_row_source_boundary_is_explicit_partial() -> None:
    class BoundaryClient:
        def search(self, parameters: dict[str, Any]):
            return _search_records(ohio.OBSERVED_SEARCH_BOUNDARY)

    result = ohio.execute(
        parser_args("search", "--caption", "State"),
        client=BoundaryClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == ohio.OBSERVED_SEARCH_BOUNDARY
    assert result.next_cursor is None
    assert result.errors[0].code == "observed_source_result_boundary"
    assert result.errors[0].details["source_response_preserved"] is True
    assert result.records[0]["retrieval"]["caller_window_applied"] is False


def test_caller_limit_is_applied_after_response_and_cursor_is_bound() -> None:
    records = _search_records(5)

    class WindowClient:
        def search(self, parameters: dict[str, Any]):
            return records

    first = ohio.execute(
        parser_args(
            "search",
            "--caption",
            "Fixture",
            "--limit",
            "2",
        ),
        client=WindowClient(),
        log_results=False,
    )
    assert first.status == ResultStatus.OK
    assert [record["case_number"] for record in first.records] == [
        "2025-0000",
        "2025-0001",
    ]
    assert first.next_cursor

    second = ohio.execute(
        parser_args(
            "search",
            "--caption",
            "Fixture",
            "--limit",
            "2",
            "--cursor",
            str(first.next_cursor),
        ),
        client=WindowClient(),
        log_results=False,
    )
    assert [record["case_number"] for record in second.records] == [
        "2025-0002",
        "2025-0003",
    ]
    assert second.next_cursor

    changed_records = list(reversed(records))

    class ChangedClient:
        def search(self, parameters: dict[str, Any]):
            return changed_records

    changed = ohio.execute(
        parser_args(
            "search",
            "--caption",
            "Fixture",
            "--limit",
            "2",
            "--cursor",
            str(first.next_cursor),
        ),
        client=ChangedClient(),
        log_results=False,
    )
    assert changed.status == ResultStatus.UNAVAILABLE
    assert changed.errors[0].code == "cursor_membership_changed"


def test_recent_rows_preserve_document_but_explain_missing_docket_id() -> None:
    rows = [
        ohio.normalize_recent_row(value)
        for value in fixture_json("recent.json")
    ]

    assert len(rows) == 2
    assert rows[0]["native_document_id"] == (
        "2018-0542:DocketItems:1007002.pdf"
    )
    assert "do not publish DocketItems.ID" in rows[0][
        "docket_identity_note"
    ]
    assert rows[0]["listing_identity"] != rows[1]["listing_identity"]


def test_recent_fails_visibly_on_non_object_source_row() -> None:
    session = FakeSession(
        client_responses("empty.json")[:-1]
        + [
            FakeResponse(
                url=ohio.AJAX_URL,
                text='["unexpected"]',
                headers={"Content-Type": "application/json"},
            )
        ]
    )
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    with pytest.raises(
        ohio.OhioSupremeCourtSourceChanged,
        match="non-object row",
    ):
        client.recent(5)


def test_document_validates_pdf_media_signature_and_final_host() -> None:
    expected_url = ohio.build_document_url(
        "2017-1682",
        "835936.pdf",
        "DocketItems",
    )
    session = FakeSession(
        [
            FakeResponse(
                url=expected_url,
                content=fixture_pdf(),
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    artifact = client.document(
        "2017-1682",
        "835936.pdf",
        "DocketItems",
    )

    assert artifact.content == fixture_pdf()
    assert artifact.record["media_type"] == "application/pdf"
    assert artifact.record["signature"].startswith("%PDF-1.7")
    assert artifact.record["byte_size"] == len(fixture_pdf())
    assert artifact.record["final_url"] == expected_url
    assert session.requests[0]["url"] == expected_url


def test_document_rejects_redirect_outside_verified_host() -> None:
    session = FakeSession(
        [
            FakeResponse(
                url="https://example.com/835936.pdf",
                content=fixture_pdf(),
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    client = ohio.OhioSupremeCourtClient(
        session=session,
        minimum_interval=0,
        max_retries=0,
    )

    with pytest.raises(
        ohio.OhioSupremeCourtSourceChanged,
        match="outside the verified HTTPS host",
    ):
        client.document(
            "2017-1682",
            "835936.pdf",
            "DocketItems",
        )


def test_document_operation_writes_verified_artifact(tmp_path: Path) -> None:
    destination = tmp_path / "filing.pdf"

    class DocumentClient:
        def document(
            self,
            case_number: str,
            document_name: str,
            section: str,
        ) -> ohio.DocumentArtifact:
            return ohio.DocumentArtifact(
                record={
                    "source_id": ohio.SOURCE_ID,
                    "record_kind": "court_document",
                    "case_number": case_number,
                    "document_name": document_name,
                    "document_section": section,
                    "byte_size": len(fixture_pdf()),
                },
                content=fixture_pdf(),
            )

    result = ohio.execute(
        parser_args(
            "document",
            "2017-1682",
            "835936.pdf",
            str(destination),
        ),
        client=DocumentClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == fixture_pdf()
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    assert result.records[0]["local_path"] == str(destination.resolve())


def test_execute_closes_only_an_internally_created_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(client_responses("case.json"))
    monkeypatch.setattr(ohio.requests, "Session", lambda: session)

    result = ohio.execute(
        parser_args(
            "case",
            "2017-1682",
            "--minimum-interval",
            "0",
            "--retry-attempts",
            "0",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert session.closed is True

    caller_session = FakeSession(client_responses("case.json"))
    caller_client = ohio.OhioSupremeCourtClient(
        session=caller_session,
        minimum_interval=0,
        max_retries=0,
    )
    ohio.execute(
        parser_args("case", "2017-1682"),
        client=caller_client,
        log_results=False,
    )
    assert caller_session.closed is False


def test_source_contract_maps_components_without_conflating_roles() -> None:
    result = ohio.execute(
        parser_args("source"),
        client=object(),
        log_results=False,
    )
    record = result.records[0]

    assert result.status == ResultStatus.OK
    assert record["observed_at"] == "2026-07-30"
    assert record["identity"]["case"] == "CaseInfo.CaseNumber"
    assert record["identity"]["case_internal_locator"] == (
        "CaseInfo.ID (not the case identity)"
    )
    assert record["identity"]["docket_entry"] == "DocketItems.ID"
    assert record["identity"]["document"] == (
        "case_number + section + DocumentName"
    )
    assert {
        component["component"]
        for component in record["component_boundaries"]
    } == {
        "Reporter of Decisions",
        "Clerk's Journal",
        "Attorney Directory",
        "Oral Argument Calendar",
    }


def test_search_accepts_long_caller_text_without_a_local_text_cap() -> None:
    caption = "A" * 2000
    args = parser_args("search", "--caption", caption)
    parameters = ohio._search_parameters(args)
    assert parameters["paramCaseCaption"] == caption


def test_search_requires_meaningful_selector_but_not_a_result_limit() -> None:
    result = ohio.execute(
        parser_args("search", "--caption", "Fixture"),
        client=type(
            "Client",
            (),
            {"search": lambda self, parameters: _search_records(3)},
        )(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.query.query.requested_limit is None

    missing = ohio.execute(
        parser_args("search"),
        client=object(),
        log_results=False,
    )
    assert missing.status == ResultStatus.UNAVAILABLE
    assert missing.errors[0].code == "missing_search_selector"
