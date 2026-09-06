from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tools import query_pa_ujs
from tools.ingest_state_court_records import ingest_envelope, validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/pa_ujs")
FORM_HTML = (FIXTURE_DIR / "case_search_form.html").read_text(encoding="utf-8")
CP_RESULTS_HTML = (FIXTURE_DIR / "cp_results.html").read_text(encoding="utf-8")
APPELLATE_RESULTS_HTML = (
    FIXTURE_DIR / "appellate_results.html"
).read_text(encoding="utf-8")
NO_RESULTS_HTML = (FIXTURE_DIR / "no_results.html").read_text(encoding="utf-8")
MISSING_GRID_HTML = (FIXTURE_DIR / "missing_grid.html").read_text(
    encoding="utf-8"
)


class FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        content: bytes = b"",
        url: str = query_pa_ujs.CASE_SEARCH_URL,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.text = text
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Pennsylvania UJS request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(
        self,
        pages: query_pa_ujs.PAUJSSearchPage
        | list[query_pa_ujs.PAUJSSearchPage],
        *,
        report: query_pa_ujs.PAUJSReport | None = None,
        error: query_pa_ujs.PAUJSError | None = None,
    ) -> None:
        self.pages = list(pages) if isinstance(pages, list) else [pages]
        self.report = report
        self.error = error
        self.searches: list[dict[str, str]] = []
        self.report_urls: list[str] = []

    def search(
        self,
        selection: dict[str, str],
    ) -> query_pa_ujs.PAUJSSearchPage:
        self.searches.append(dict(selection))
        if self.error is not None:
            raise self.error
        if not self.pages:
            raise AssertionError("unexpected Pennsylvania UJS search")
        return self.pages.pop(0)

    def fetch_report(self, source_url: str) -> query_pa_ujs.PAUJSReport:
        self.report_urls.append(source_url)
        if self.report is None:
            raise AssertionError("unexpected Pennsylvania UJS report fetch")
        return self.report


def _parse(*values: str) -> Any:
    return query_pa_ujs.build_parser().parse_args(list(values))


def test_bootstrap_contract_captures_native_modes_and_date_span() -> None:
    form = query_pa_ujs.parse_bootstrap(FORM_HTML)

    assert form.csrf_token == "fixture-antiforgery-token"
    assert form.action_url == query_pa_ujs.CASE_SEARCH_URL
    assert form.filed_date_max_span_days == 180
    assert {
        "AppellateCourtName",
        "DateFiled",
        "DocketNumber",
        "Organization",
        "ParticipantName",
    }.issubset(form.search_modes)
    assert "__RequestVerificationToken" in form.form_fields
    assert len(form.schema_fingerprint) == 64


def test_bootstrap_detects_native_contract_change() -> None:
    changed = FORM_HTML.replace(
        'data-aopc-maxAllowedLimit="180"',
        'data-aopc-maxAllowedLimit="181"',
    )

    with pytest.raises(query_pa_ujs.PAUJSSourceChangedError) as captured:
        query_pa_ujs.parse_bootstrap(changed)

    assert captured.value.code == "filed_date_span_changed"
    assert captured.value.status is ResultStatus.SOURCE_CHANGED


def test_common_pleas_rows_collapse_to_one_ingestible_case() -> None:
    page = query_pa_ujs.parse_search_page(CP_RESULTS_HTML)
    records = query_pa_ujs.normalize_records(
        page,
        selection={
            "SearchBy": "DocketNumber",
            "DocketNumber": query_pa_ujs.COMMON_PLEAS_SENTINEL,
        },
    )

    assert page.source_row_count == 2
    assert page.source_unique_case_count == 1
    assert page.unique_cases_by_system == {"Common Pleas": 1}
    assert page.threshold_systems == ()
    assert len(records) == 1
    record = records[0]
    assert record["raw_case_number"] == "CP-51-CR-0007622-2022"
    assert record["caption"] == "Comm. v. Perez, Junior"
    assert record["filing_date"] == "2022-10-26"
    assert record["court"] == {
        "id": "pa-ujs-cp_01_51_crim",
        "court_id": "pa-ujs-cp_01_51_crim",
        "native_court_id": "CP-01-51-Crim",
        "name": "Pennsylvania UJS Common Pleas (CP-01-51-Crim)",
        "court_system": "Common Pleas",
        "court_office": "CP-01-51-Crim",
        "court_level": "Common Pleas",
        "branch": "CP-01-51-Crim",
        "county": "Philadelphia",
        "state_code": "PA",
        "jurisdiction_id": "42",
        "official_url": query_pa_ujs.CASE_SEARCH_URL,
    }
    assert len(record["calendar_events"]) == 2
    assert record["calendar_events"][0]["native_event_id"] == "1507095448"
    assert record["calendar_events"][0]["event_date"] == "2025-07-07T13:00"
    assert record["calendar_events"][0]["assertion_kind"] == "docket_metadata"
    assert record["calendar_events"][0]["native_assertion_kind"] == (
        "calendar_event"
    )
    assert record["calendar_events"][1]["event_type"] == "Compliance Review"
    assert record["docket_sheet_url"].startswith(
        f"{query_pa_ujs.BASE_URL}/Report/CpDocketSheet"
    )
    assert record["court_summary_url"].startswith(
        f"{query_pa_ujs.BASE_URL}/Report/CpCourtSummary"
    )
    assert [
        document["native_document_id"]
        for document in record["documents"]
    ] == [
        "CP-51-CR-0007622-2022:court_summary",
        "CP-51-CR-0007622-2022:docket_sheet",
    ]
    assert {
        document["document_type"]: document["source_url"]
        for document in record["documents"]
    } == {
        "court_summary": record["court_summary_url"],
        "docket_sheet": record["docket_sheet_url"],
    }


def test_appellate_result_uses_nonempty_fallback_court_identity() -> None:
    page = query_pa_ujs.parse_search_page(APPELLATE_RESULTS_HTML)
    record = query_pa_ujs.normalize_records(
        page,
        selection={
            "SearchBy": "DocketNumber",
            "DocketNumber": query_pa_ujs.APPELLATE_SENTINEL,
        },
    )[0]

    assert record["raw_case_number"] == "69 WAL 2026"
    assert record["status"] == "Decided/Active"
    assert record["court"]["court_id"] == "pa-ujs-appellate"
    assert record["court"]["native_court_id"] == "Appellate"
    assert record["court"]["official_url"] == query_pa_ujs.CASE_SEARCH_URL
    assert record["calendar_events"] == []
    assert "/Report/PacDocketSheet?" in record["docket_sheet_url"]


def test_authoritative_empty_and_ambiguous_missing_grid_stay_distinct() -> None:
    empty = query_pa_ujs.parse_search_page(NO_RESULTS_HTML)

    assert empty.authoritative_empty is True
    assert empty.rows == ()

    with pytest.raises(query_pa_ujs.PAUJSQueryIncompleteError) as captured:
        query_pa_ujs.parse_search_page(MISSING_GRID_HTML)

    assert captured.value.status is ResultStatus.PARTIAL
    assert captured.value.code == "source_result_grid_missing"


def test_client_reuses_antiforgery_session_for_form_post() -> None:
    session = FakeSession(
        [
            FakeResponse(text=FORM_HTML),
            FakeResponse(text=CP_RESULTS_HTML),
        ]
    )
    client = query_pa_ujs.PAUJSClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    selection = {
        "SearchBy": "DocketNumber",
        "DocketNumber": query_pa_ujs.COMMON_PLEAS_SENTINEL,
    }

    page = client.search(selection)

    assert page.source_unique_case_count == 1
    assert [call[0] for call in session.calls] == ["GET", "POST"]
    post = session.calls[1]
    assert post[1] == query_pa_ujs.CASE_SEARCH_URL
    assert post[2]["data"] == {
        **selection,
        "__RequestVerificationToken": "fixture-antiforgery-token",
    }
    assert post[2]["headers"]["Origin"] == query_pa_ujs.BASE_URL


def test_native_selections_preserve_broad_searches_and_native_bounds() -> None:
    person = query_pa_ujs.native_selection(_parse("person", "PEREZ"))
    organization = query_pa_ujs.native_selection(
        _parse("organization", "WALMART")
    )
    filed = query_pa_ujs.native_selection(
        _parse("filed", "2026-01-01", "2026-06-30")
    )

    assert person == {
        "SearchBy": "ParticipantName",
        "ParticipantLastName": "PEREZ",
    }
    assert organization == {
        "SearchBy": "Organization",
        "OrganizationName": "WALMART",
    }
    assert filed["SearchBy"] == "DateFiled"
    assert _parse("filed", "2026-01-01", "2026-01-01").limit is None

    with pytest.raises(query_pa_ujs.PAUJSSelectionError) as captured:
        query_pa_ujs.native_selection(
            _parse("filed", "2026-01-01", "2026-07-01")
        )
    assert captured.value.code == "filed_date_span_exceeded"


def test_result_at_observed_source_threshold_is_partial_not_complete() -> None:
    parsed = query_pa_ujs.parse_search_page(CP_RESULTS_HTML)
    template = dict(parsed.rows[0])
    rows = tuple(
        {
            **template,
            "DocketNumber": f"CP-51-CR-{index:07d}-2026",
            "CalendarEventID": None,
            "CalendarEventType": None,
            "CalendarEventStatus": None,
            "CalendarEventDateTime": None,
            "CalendarEventLocation": None,
            "report_urls": {},
        }
        for index in range(query_pa_ujs.SOURCE_RESULT_THRESHOLD_PER_SYSTEM)
    )
    threshold_page = replace(
        parsed,
        rows=rows,
        unique_cases_by_system={
            "Common Pleas": query_pa_ujs.SOURCE_RESULT_THRESHOLD_PER_SYSTEM
        },
        threshold_systems=("Common Pleas",),
    )

    result = query_pa_ujs.execute(
        _parse("filed", "2026-07-28", "2026-07-28"),
        client=FakeClient(threshold_page),
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 501
    assert result.errors[0].code == "source_result_threshold_reached"
    assert result.next_cursor is None


def test_normalized_case_envelope_projects_into_shared_court_store(
    tmp_path: Path,
) -> None:
    page = query_pa_ujs.parse_search_page(CP_RESULTS_HTML)
    result = query_pa_ujs.execute(
        _parse("case", query_pa_ujs.COMMON_PLEAS_SENTINEL),
        client=FakeClient(page),
        log_results=False,
    )
    envelope = result.to_dict()
    validate_envelope(envelope)

    court_db = tmp_path / "courts.db"
    ingested = ingest_envelope(envelope, court_db=court_db)

    assert ingested["status"] == "ingested"
    assert ingested["projected"]["courts"] == 1
    assert ingested["projected"]["cases"] == 1
    assert ingested["projected"]["parties"] == 1
    assert ingested["projected"]["case_events"] == 2
    assert ingested["projected"]["documents"] == 2
    db = sqlite3.connect(court_db)
    try:
        court = db.execute(
            """
            SELECT court_id, native_court_id, name, state_code, official_url
            FROM court
            """
        ).fetchone()
        case_record = db.execute(
            """
            SELECT court_id, raw_case_number, caption, filing_date
            FROM case_record
            """
        ).fetchone()
        events = db.execute(
            """
            SELECT native_event_id, event_type, assertion_kind,
                   native_assertion_kind
            FROM case_event
            ORDER BY event_date, case_event_id
            """
        ).fetchall()
        documents = db.execute(
            """
            SELECT native_document_id, document_type, source_url
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
    finally:
        db.close()
    assert court == (
        "pa-ujs-cp_01_51_crim",
        "CP-01-51-Crim",
        "Pennsylvania UJS Common Pleas (CP-01-51-Crim)",
        "PA",
        query_pa_ujs.CASE_SEARCH_URL,
    )
    assert events == [
        (
            "1507095448",
            "Payment Plan Conference",
            "docket_metadata",
            "calendar_event",
        ),
        (
            "1507095449",
            "Compliance Review",
            "docket_metadata",
            "calendar_event",
        ),
    ]
    assert documents == [
        (
            "CP-51-CR-0007622-2022:court_summary",
            "court_summary",
            next(
                document["source_url"]
                for document in envelope["records"][0]["documents"]
                if document["document_type"] == "court_summary"
            ),
        ),
        (
            "CP-51-CR-0007622-2022:docket_sheet",
            "docket_sheet",
            next(
                document["source_url"]
                for document in envelope["records"][0]["documents"]
                if document["document_type"] == "docket_sheet"
            ),
        ),
    ]
    assert case_record == (
        "pa-ujs-cp_01_51_crim",
        "CP-51-CR-0007622-2022",
        "Comm. v. Perez, Junior",
        "2022-10-26",
    )


def test_report_command_writes_verified_pdf_and_preserves_case_context(
    tmp_path: Path,
) -> None:
    content = b"%PDF-1.7\nfixture Pennsylvania docket\n"
    report_url = (
        f"{query_pa_ujs.BASE_URL}/Report/CpDocketSheet"
        "?docketNumber=CP-51-CR-0007622-2022&dnh=fixture"
    )
    report = query_pa_ujs.PAUJSReport(
        content=content,
        source_url=report_url,
        media_type="application/pdf",
        sha256=hashlib.sha256(content).hexdigest(),
    )
    destination = tmp_path / "docket.pdf"
    client = FakeClient(
        query_pa_ujs.parse_search_page(CP_RESULTS_HTML),
        report=report,
    )

    result = query_pa_ujs.execute(
        _parse(
            "report",
            query_pa_ujs.COMMON_PLEAS_SENTINEL,
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == content
    record = result.to_dict()["records"][0]
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert record["court"]["native_court_id"] == "CP-01-51-Crim"
    assert record["case_index_record"]["raw_case_number"] == (
        query_pa_ujs.COMMON_PLEAS_SENTINEL
    )
    assert client.report_urls == [report_url]


def test_report_transport_accepts_only_official_pdf_response() -> None:
    pdf = b"%PDF-1.7\nfixture\n"
    report_url = f"{query_pa_ujs.BASE_URL}/Report/PacDocketSheet?dnh=fixture"
    session = FakeSession(
        [
            FakeResponse(
                content=pdf,
                url=report_url,
                content_type="application/pdf",
            )
        ]
    )
    client = query_pa_ujs.PAUJSClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    report = client.fetch_report(report_url)

    assert report.content == pdf
    assert report.sha256 == hashlib.sha256(pdf).hexdigest()

    with pytest.raises(query_pa_ujs.PAUJSSelectionError):
        client.fetch_report("https://example.com/Report/PacDocketSheet")
