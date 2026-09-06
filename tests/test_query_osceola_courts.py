from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_osceola_courts as osceola
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path("tests/fixtures/public_records/osceola_benchmark")


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _artifact(
    name: str,
    url: str,
    *,
    media_type: str = "text/html",
    status_code: int = 200,
    headers: Mapping[str, str] | None = None,
) -> osceola.Artifact:
    content = (FIXTURE_DIR / name).read_bytes()
    return osceola.Artifact(
        content=content,
        source_url=url,
        status_code=status_code,
        media_type=media_type,
        headers=dict(headers or {"content-type": media_type}),
    )


def _locator() -> osceola.BenchmarkCaseLocator:
    return osceola.parse_case_shell(
        _artifact(
            "case_shell.html",
            (osceola.PORTAL_BASE_URL + "CourtCase.aspx/Details/3284536?digest=fixture"),
        )
    )


def _bundle() -> osceola.BenchmarkCaseBundle:
    locator = _locator()
    summary = _artifact(
        "details_summary.html",
        osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsSummary/3284536",
    )
    record = osceola.parse_summary(summary, locator)
    dockets, locators = osceola.parse_dockets(
        _artifact(
            "case_dockets.html",
            osceola.PORTAL_BASE_URL + "CourtCase.aspx/CaseDockets/3284536",
        ),
        locator,
    )
    record["docket_entries"] = dockets
    record.update(
        osceola.parse_history(
            _artifact(
                "details_history.html",
                osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsHistory/3284536",
            )
        )
    )
    record["charge_details"] = osceola.parse_charge_details(
        _artifact(
            "details_charges.html",
            osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsCharges/3284536",
        )
    )
    record["source_bundle_sha256"] = "fixture-bundle"
    return osceola.BenchmarkCaseBundle(
        record=record,
        docket_locators=locators,
        source_document_sha256="fixture-bundle",
    )


def _args(*values: str) -> Any:
    return osceola.build_parser().parse_args(list(values))


@dataclass
class FakeResponse:
    url: str
    content: bytes = b""
    status_code: int = 200
    headers: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.text = self.content.decode("utf-8", errors="replace")


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _client(session: QueueSession) -> osceola.PioneerBenchmarkClient:
    return osceola.PioneerBenchmarkClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


class FixtureClient:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def search(
        self,
        query: str,
        *,
        native_mode: str,
        offset: int,
        limit: int,
    ) -> osceola.BenchmarkSearchPage:
        self.calls.append(("search", query, native_mode, offset, limit))
        payload = json.loads(_fixture("search_results.json"))
        headers = [
            "Summary",
            "Name",
            "Party Type",
            "Case Number",
            "Status",
            "Citation #",
        ]
        rows = payload["data"][offset : offset + limit]
        hits, row_count = osceola.parse_search_rows(
            {**payload, "data": rows},
            headers,
        )
        return osceola.BenchmarkSearchPage(
            hits=hits,
            source_row_count=row_count,
            total_reported=5000,
            offset=offset,
            too_broad=True,
            source_document_sha256="fixture-search",
        )

    def fetch_case(
        self,
        case_number: str,
    ) -> osceola.BenchmarkCaseBundle:
        self.calls.append(("fetch_case", case_number))
        return _bundle()

    def document_metadata(
        self,
        case_number: str,
        docket_id: str,
    ) -> list[dict[str, Any]]:
        self.calls.append(("document_metadata", case_number, docket_id))
        bundle = _bundle()
        return osceola.parse_document_pages(
            _artifact(
                "pages.json",
                (osceola.PORTAL_BASE_URL + f"CaseDocket.aspx/Pages?did={docket_id}"),
                media_type="json",
            ),
            case_number=case_number,
            case_id=str(bundle.record["source_internal_id"]),
            docket_id=docket_id,
        )

    def report(self, kind: str) -> osceola.Artifact:
        self.calls.append(("report", kind))
        url = osceola.CALENDAR_URL if kind == "calendar" else osceola.FORECLOSURE_URL
        return _artifact(
            "report.pdf",
            url,
            media_type="application/pdf",
            headers={
                "content-type": "application/pdf",
                "last-modified": "Thu, 30 Jul 2026 11:15:17 GMT",
                "etag": '"fixture"',
            },
        )

    def bootstrap(self) -> osceola.BenchmarkSearchForm:
        self.calls.append(("bootstrap",))
        return osceola.parse_search_form(
            _artifact(
                "landing.html",
                osceola.SEARCH_LANDING_URL,
            )
        )

    def report_head(self, kind: str) -> osceola.Artifact:
        self.calls.append(("report_head", kind))
        url = osceola.CALENDAR_URL if kind == "calendar" else osceola.FORECLOSURE_URL
        return osceola.Artifact(
            content=b"",
            source_url=url,
            status_code=200,
            media_type="application/pdf",
            headers={
                "content-type": "application/pdf",
                "content-length": "1234",
                "last-modified": "Thu, 30 Jul 2026 11:15:17 GMT",
                "etag": f'"{kind}"',
            },
        )


def test_parser_exposes_all_standalone_operations() -> None:
    assert _args("sources").command == "sources"
    assert _args("manifest").source == osceola.PORTAL_SOURCE_ID

    search = _args(
        "search",
        "ABC123",
        "--search-mode",
        "citation-number",
        "--limit",
        "7",
        "--output",
        "search.json",
    )
    assert search.search_mode == "citation-number"
    assert search.limit == 7
    assert search.output == "search.json"

    assert _args("case", "2023 CF 001540").case_number == ("2023 CF 001540")
    assert _args("docket", "2023 CF 001540").command == "docket"
    document = _args(
        "document-metadata",
        "2023 CF 001540",
        "56773534",
    )
    assert document.docket_id == "56773534"
    assert _args("reports").command == "reports"
    assert _args("report", "calendar").kind == "calendar"
    assert _args("request-handoff").command == "request-handoff"
    assert _args("probe").command == "probe"


def test_search_form_verifies_modes_token_version_and_challenge_state() -> None:
    form = osceola.parse_search_form(
        _artifact("landing.html", osceola.SEARCH_LANDING_URL)
    )

    assert form.action_url == osceola.CASE_SEARCH_URL
    assert form.hidden_fields["__RequestVerificationToken"] == (
        "fixture-verification-token"
    )
    assert set(form.native_search_modes) == osceola.NATIVE_SEARCH_MODES
    assert form.platform_version == "2.9.10.0"

    with pytest.raises(osceola.OsceolaCourtError) as caught:
        osceola.parse_search_form(
            _artifact("challenge.html", osceola.SEARCH_LANDING_URL)
        )
    assert caught.value.status == ResultStatus.HUMAN_REQUIRED
    assert caught.value.code == "human_verification"


def test_search_rows_merge_aliases_without_persisting_signed_digests() -> None:
    artifact = _artifact(
        "search_results_page.html",
        osceola.CASE_SEARCH_URL,
    )
    headers, total, too_broad = osceola.parse_search_results_page(artifact)
    hits, source_rows = osceola.parse_search_rows(
        json.loads(_fixture("search_results.json")),
        headers,
    )
    records = osceola.merge_search_hits(hits)

    assert total == 5000
    assert too_broad is True
    assert source_rows == 3
    assert len(records) == 2
    traffic = records[0]
    assert traffic["court"]["court_id"] == "fl-09-osceola-county"
    assert traffic["raw_case_number"] == "2026 TR 000101"
    assert traffic["source_result_row_count"] == 2
    assert [match["alias"] for match in traffic["search_matches"]] == [
        False,
        True,
    ]
    assert "SIGNED" not in json.dumps(records)

    empty_headers, empty_total, empty_broad = osceola.parse_search_results_page(
        _artifact(
            "empty_results_page.html",
            osceola.CASE_SEARCH_URL,
        )
    )
    assert (empty_headers, empty_total, empty_broad) == ([], 0, False)


def test_case_parsers_preserve_parties_charges_events_docket_states() -> None:
    bundle = _bundle()
    record = bundle.record

    assert record["raw_case_number"] == "2023 CF 001540"
    assert record["court"]["court_id"] == "fl-09-osceola-circuit"
    assert record["filing_date"] == "2023-05-22"
    assert record["status_date"] == "2023-11-16"
    assert record["waive_speedy_trial"] is True
    assert record["parties"][0]["raw_name"] == "SAMPLE, CASEY"
    assert record["attorneys"][0]["raw_name"] == "COUNSEL, AVERY"
    assert record["charges"][0]["native_charge_id"] == "3034861"
    assert record["charges"][0]["disposition_date"] == "2023-11-16"
    assert record["case_events"][0]["native_event_id"] == "684720"
    assert record["case_events"][0]["event_date"] == "2023-12-05T09:00"
    assert record["fees"][0]["balance"] == "$50.00"
    assert record["additional_cases"][0]["raw_case_number"] == ("2021 CF 000001")
    assert record["related_cases"][0]["relation"] == "LINKED"
    assert record["charge_details"][0]["phase"] == "FILED"

    public, requested, absent = record["docket_entries"]
    assert public["native_entry_id"] == "56773534"
    assert public["document_available"] is True
    assert public["documents"][0]["source_access_state"] == ("public_image_metadata")
    assert requested["source_document_state"] == "view_on_request"
    assert requested["request_handoff"]["submission_performed"] is False
    assert requested["request_handoff"]["request_fields"] == [
        "caseDocketID",
        "email",
    ]
    assert absent["source_document_state"] == "not_available_online"
    assert "fixture/docket+digest" not in json.dumps(record)


def test_document_page_metadata_keeps_stable_ids_and_source_states() -> None:
    records = osceola.parse_document_pages(
        _artifact(
            "pages.json",
            (osceola.PORTAL_BASE_URL + "CaseDocket.aspx/Pages?did=56773534"),
            media_type="json",
        ),
        case_number="2023 CF 001540",
        case_id="3284536",
        docket_id="56773534",
    )

    assert [row["native_document_id"] for row in records] == [
        "76951980",
        "76951981",
    ]
    assert records[0]["access_state"] == "public"
    assert records[0]["image_url"].endswith("Image.aspx/ShowImage?did=76951980&dr=0")
    assert records[1]["access_state"] == "restricted"
    assert records[1]["redact_status"] == 2
    assert records[0]["canonical_ref"] != records[1]["canonical_ref"]


def test_live_client_posts_verified_form_then_pages_datatables() -> None:
    session = QueueSession(
        [
            FakeResponse(
                osceola.SEARCH_LANDING_URL,
                (FIXTURE_DIR / "landing.html").read_bytes(),
            ),
            FakeResponse(
                osceola.CASE_SEARCH_URL,
                (FIXTURE_DIR / "search_results_page.html").read_bytes(),
            ),
            FakeResponse(
                osceola.RESULT_DATA_URL,
                (FIXTURE_DIR / "search_results.json").read_bytes(),
                headers={"Content-Type": "application/json"},
            ),
        ]
    )

    page = _client(session).search(
        "SAMPLE",
        native_mode="Name",
        offset=0,
        limit=3,
    )

    assert page.source_row_count == 3
    assert page.total_reported == 5000
    assert page.too_broad is True
    post = session.calls[1]
    assert post["method"] == "POST"
    assert post["url"] == osceola.CASE_SEARCH_URL
    assert post["allow_redirects"] is False
    assert post["data"]["__RequestVerificationToken"] == ("fixture-verification-token")
    assert post["data"]["courtTypes"] == "5,4,7"
    assert post["data"]["type"] == "Name"
    assert post["data"]["search"] == "SAMPLE"
    datatable = session.calls[2]
    assert datatable["url"] == osceola.RESULT_DATA_URL
    assert datatable["data"]["start"] == "0"
    assert datatable["data"]["length"] == "3"
    assert datatable["data"]["order[0][column]"] == "3"


def test_live_client_exact_redirect_fetches_case_bundle_sections() -> None:
    detail_url = (
        osceola.PORTAL_BASE_URL
        + "CourtCase.aspx/Details/3284536?digest=fixture%2Fcase%2Bdigest"
    )
    session = QueueSession(
        [
            FakeResponse(
                osceola.SEARCH_LANDING_URL,
                (FIXTURE_DIR / "landing.html").read_bytes(),
            ),
            FakeResponse(
                osceola.CASE_SEARCH_URL,
                status_code=302,
                headers={
                    "Content-Type": "text/html",
                    "Location": (
                        "/BenchmarkWeb/CourtCase.aspx/Details/3284536"
                        "?digest=fixture%2Fcase%2Bdigest"
                    ),
                },
            ),
            FakeResponse(
                detail_url,
                (FIXTURE_DIR / "case_shell.html").read_bytes(),
            ),
            FakeResponse(
                osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsSummary/3284536",
                (FIXTURE_DIR / "details_summary.html").read_bytes(),
            ),
            FakeResponse(
                osceola.PORTAL_BASE_URL + "CourtCase.aspx/CaseDockets/3284536",
                (FIXTURE_DIR / "case_dockets.html").read_bytes(),
            ),
            FakeResponse(
                osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsHistory/3284536",
                (FIXTURE_DIR / "details_history.html").read_bytes(),
            ),
            FakeResponse(
                osceola.PORTAL_BASE_URL + "CourtCase.aspx/DetailsCharges/3284536",
                (FIXTURE_DIR / "details_charges.html").read_bytes(),
            ),
        ]
    )

    bundle = _client(session).fetch_case("2023 CF 001540")

    assert bundle.record["raw_case_number"] == "2023 CF 001540"
    assert list(bundle.docket_locators) == [
        "56773534",
        "56770000",
        "56759615",
    ]
    assert len(session.calls) == 7
    section_urls = [call["url"] for call in session.calls[3:]]
    assert all("digest=fixture%2Fcase%2Bdigest" in url for url in section_urls)


def test_search_execute_marks_ceiling_partial_and_binds_cursor() -> None:
    client = FixtureClient()
    first = osceola.execute(
        _args("search", "SAMPLE", "--limit", "2"),
        client=client,
        log_results=False,
    )
    validate_envelope(first.to_dict())

    assert first.status == ResultStatus.PARTIAL
    assert len(first.records) == 1
    assert first.records[0]["source_result_row_count"] == 2
    assert first.next_cursor is not None
    assert first.errors[0].code == "source_result_ceiling"

    second = osceola.execute(
        _args(
            "search",
            "SAMPLE",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert client.calls[-1] == ("search", "SAMPLE", "Name", 2, 2)
    assert second.records[0]["raw_case_number"] == "2025 CA 000202"

    mismatch = osceola.execute(
        _args(
            "search",
            "DIFFERENT",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status == ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_case_docket_and_document_operations_return_valid_envelopes() -> None:
    client = FixtureClient()
    case = osceola.execute(
        _args("case", "2023 CF 001540"),
        client=client,
        log_results=False,
    )
    docket = osceola.execute(
        _args("docket", "2023 CF 001540"),
        client=client,
        log_results=False,
    )
    document = osceola.execute(
        _args(
            "document-metadata",
            "2023 CF 001540",
            "56773534",
        ),
        client=client,
        log_results=False,
    )

    for result in (case, docket, document):
        validate_envelope(result.to_dict())
        assert result.status == ResultStatus.OK
    assert case.records[0]["record_kind"] == "case"
    assert len(docket.records) == 3
    assert len(document.records) == 2


def test_reports_use_current_root_routes_and_validate_artifacts(
    tmp_path: Path,
) -> None:
    listed = osceola.execute(
        _args("reports"),
        client=FixtureClient(),
        log_results=False,
    )
    urls = [record["artifact_url"] for record in listed.records]

    assert urls == [osceola.CALENDAR_URL, osceola.FORECLOSURE_URL]
    assert all("/BenchmarkWeb/reports/" not in url for url in urls)

    output = tmp_path / "calendar.pdf"
    fetched = osceola.execute(
        _args(
            "report",
            "calendar",
            "--artifact-output",
            str(output),
        ),
        client=FixtureClient(),
        log_results=False,
    )
    pdf = (FIXTURE_DIR / "report.pdf").read_bytes()
    assert output.read_bytes() == pdf
    assert fetched.records[0]["artifact_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert fetched.records[0]["last_modified"].startswith("Thu, 30 Jul")


def test_request_handoff_models_routes_without_submitting() -> None:
    result = osceola.execute(
        _args(
            "request-handoff",
            "--case-number",
            "2023 CF 001540",
            "--docket-id",
            "56770000",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.records[0]

    assert record["submission_performed"] is False
    assert record["case_number"] == "2023 CF 001540"
    by_kind = {route["route_kind"]: route for route in record["routes"]}
    portal = by_kind["in_portal_view_on_request"]
    assert portal["request_url"] == osceola.DOCKET_REQUEST_URL
    assert portal["request_fields"] == ("caseDocketID", "email")
    assert portal["submission_performed"] is False
    assert (
        by_kind["older_or_not_online_public_record_request"]["request_url"]
        == osceola.JUSTFOIA_URL
    )
    assert by_kind["electronic_certified_copy"]["request_url"] == (
        osceola.ECERTIFIED_URL
    )
    assert (
        "bulk data purchases for specific court types"
        in by_kind["registered_and_bulk_data"]["coverage"]
    )


def test_manifests_and_probe_preserve_distinct_complementary_sources() -> None:
    portal = osceola.execute(
        _args("manifest"),
        client=FixtureClient(),
        log_results=False,
    )
    calendar = osceola.execute(
        _args(
            "manifest",
            "--source",
            osceola.CALENDAR_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    probe_client = FixtureClient()
    probe = osceola.execute(
        _args("probe"),
        client=probe_client,
        log_results=False,
    )

    assert portal.records[0]["platform_family"] == (osceola.PLATFORM_FAMILY)
    assert portal.records[0]["session_locator_fields_persisted"] == ()
    assert osceola.CALENDAR_SOURCE_ID in (portal.records[0]["complementary_source_ids"])
    assert calendar.records[0]["coverage"]["past_hearings"] is False
    probe_record = probe.records[0]
    assert probe_record["platform_version"] == "2.9.10.0"
    assert probe_record["verification_token_present"] is True
    assert probe_record["report_routes"]["calendar"]["media_type"] == (
        "application/pdf"
    )
    assert probe_client.calls == [
        ("bootstrap",),
        ("report_head", "calendar"),
        ("report_head", "foreclosure"),
    ]


def test_report_parser_rejects_non_pdf_bytes() -> None:
    artifact = copy.deepcopy(
        _artifact(
            "report.pdf",
            osceola.CALENDAR_URL,
            media_type="application/pdf",
        )
    )
    invalid = osceola.Artifact(
        content=b"<html>not a pdf</html>",
        source_url=artifact.source_url,
        status_code=200,
        media_type="application/pdf",
        headers=artifact.headers,
    )

    with pytest.raises(osceola.OsceolaCourtError) as caught:
        osceola.parse_report_artifact(invalid, kind="calendar")
    assert caught.value.code == "invalid_report_pdf"
