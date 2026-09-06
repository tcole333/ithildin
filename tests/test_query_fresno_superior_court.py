from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_fresno_superior_court as fresno
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "fresno_superior_court"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


CALENDAR_URL = (
    "https://www.fresno.courts.ca.gov/system/files/general/"
    "merged-calendar-07302026.pdf"
)
RULING_URL = (
    "https://www.fresno.courts.ca.gov/system/files/tentative-rulings/"
    "07-30-26-dept-501-gsf.pdf"
)
PDF_BYTES = b"%PDF-1.7\nFresno fixture\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = fresno.CALENDAR_INDEX_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=UTF-8"}
    )


class FakeSession:
    def __init__(
        self,
        get_responses: list[FakeResponse],
        post_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.get_responses = list(get_responses)
        self.post_responses = list(post_responses or [])
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", url, kwargs))
        if not self.get_responses:
            raise AssertionError("unexpected Fresno GET")
        return self.get_responses.pop(0)

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", url, kwargs))
        if not self.post_responses:
            raise AssertionError("unexpected Fresno POST")
        return self.post_responses.pop(0)


class FakeClient:
    def __init__(self, *, no_probate_results: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.no_probate_results = no_probate_results

    def portal(self) -> dict[str, Any]:
        self.calls.append(("portal",))
        return dict(
            fresno.parse_portal_state(
                fixture("portal_home.html"),
                fixture("portal_register.html"),
            )
        )

    def calendar_index(self) -> fresno.ArtifactIndex:
        self.calls.append(("calendar_index",))
        return fresno.parse_calendar_index(fixture("calendar_index.html"))

    def rulings_index(self) -> fresno.ArtifactIndex:
        self.calls.append(("rulings_index",))
        return fresno.parse_rulings_index(fixture("rulings_index.html"))

    def pdf(self, url: str, *, family: str) -> fresno.PDFArtifact:
        self.calls.append(("pdf", url, family))
        text = (
            fixture("calendar_text.txt")
            if family == "calendar"
            else fixture("tentative_text.txt")
        )
        return fresno.PDFArtifact(
            source_url=url,
            content=PDF_BYTES,
            sha256="a" * 64,
            text=text,
        )

    def probate_notes(
        self,
        case_number: str,
        *,
        hearing_date: str | None = None,
    ) -> fresno.ProbateResults:
        self.calls.append(("probate_notes", case_number, hearing_date))
        search = fresno.parse_probate_search_page(
            fixture("probate_search.html")
        )
        response_fixture = (
            "probate_no_results.html"
            if self.no_probate_results
            else "probate_results.html"
        )
        return fresno.parse_probate_results(
            fixture(response_fixture),
            requested_case_number=case_number,
            search_schema_fingerprint=search.schema_fingerprint,
        )


def parse_args(*values: str) -> argparse.Namespace:
    return fresno.build_parser().parse_args(list(values))


def test_sources_keep_distinct_lineage_and_do_not_add_policy_keys() -> None:
    result = fresno.execute(
        parse_args("sources"),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert {record["source_id"] for record in result.records} == {
        fresno.PORTAL_SOURCE_ID,
        fresno.CALENDAR_SOURCE_ID,
        fresno.RULINGS_SOURCE_ID,
        fresno.PROBATE_SOURCE_ID,
        fresno.INDEX_SOURCE_ID,
        fresno.RECORDS_SOURCE_ID,
    }
    assert "access_policy" not in json.dumps(result.to_dict())
    probate = next(
        record
        for record in result.records
        if record["source_id"] == fresno.PROBATE_SOURCE_ID
    )
    assert (
        probate["record_lineage"]
        == "examiner_note_not_part_of_official_court_file"
    )


def test_portal_parser_inspects_elements_not_css_names() -> None:
    home = fixture("portal_home.html").replace(
        "</head>",
        "<style>#ecp-searchform-form { display: block; }</style></head>",
    )
    record = fresno.parse_portal_state(
        home,
        fixture("portal_register.html"),
    )

    assert record["system"] == "Journal Technologies e-Court"
    assert record["anonymous_case_search_control_present"] is False
    assert record["home_form_count"] == 0
    fields = {
        field["name"]: field
        for field in record["registration"]["visible_fields"]
    }
    assert fields["profile_firstName"]["required"] is False
    assert fields["profile_lastName"]["required"] is True
    assert fields["profile_phone"]["required"] is True
    assert fields["terms_of_use"]["required"] is True
    assert record["registration"]["requires_email_confirmation"] is True


def test_portal_registration_shape_change_is_explicit() -> None:
    registration = fixture("portal_register.html").replace(
        'name="profile_phone"',
        'name="different_phone"',
    )

    with pytest.raises(fresno.FresnoSourceChangedError) as raised:
        fresno.parse_portal_state(
            fixture("portal_home.html"),
            registration,
        )

    assert raised.value.code == "registration_fields_changed"


def test_calendar_index_returns_every_matching_pdf_without_cap() -> None:
    links = "".join(
        (
            '<a href="/system/files/general/'
            f'merged-calendar-{month:02d}{day:02d}2026.pdf">'
            f"July {day}, 2026</a>"
        )
        for month in (7,)
        for day in range(1, 29)
    )

    index = fresno.parse_calendar_index(f"<html><body>{links}</body></html>")

    assert len(index.records) == 28
    assert index.records[0]["publication_date"] == "2026-07-01"
    assert index.records[-1]["publication_date"] == "2026-07-28"
    assert len(index.schema_fingerprint) == 64


def test_current_calendar_index_ignores_unrelated_documents() -> None:
    index = fresno.parse_calendar_index(fixture("calendar_index.html"))

    assert len(index.records) == 3
    assert {
        record["publication_date"] for record in index.records
    } == {
        "2026-07-28",
        "2026-07-29",
        "2026-07-30",
    }
    assert all(
        record["document_type"] == "daily_hearing_calendar"
        for record in index.records
    )


def test_rulings_index_preserves_all_departments_dates_and_urls() -> None:
    index = fresno.parse_rulings_index(fixture("rulings_index.html"))

    assert len(index.records) == 6
    assert {record["department"] for record in index.records} == {
        403,
        501,
        502,
        503,
    }
    assert sum(
        record["department"] == 501 for record in index.records
    ) == 2
    assert all(
        "/system/files/tentative-rulings/" in record["source_url"]
        for record in index.records
    )


def test_verified_official_pdf_url_can_outlive_current_index_link() -> None:
    index = fresno.parse_rulings_index(fixture("rulings_index.html"))
    historical_url = (
        "https://www.fresno.courts.ca.gov/system/files/tentative-rulings/"
        "07-22-26-dept-501-hgk.pdf"
    )

    selected = fresno._artifact_by_selector(  # noqa: SLF001
        index,
        url=historical_url,
        publication_date=None,
        department=501,
    )

    assert selected["source_url"] == historical_url
    assert selected["publication_date"] == "2026-07-22"
    assert selected["currently_linked"] is False


def test_calendar_parser_covers_both_layouts_and_every_case_row() -> None:
    records = fresno.parse_calendar_text(
        fixture("calendar_text.txt"),
        source_url=CALENDAR_URL,
        artifact_sha256="c" * 64,
    )

    assert len(records) == 5
    assert {record["case_number"] for record in records} == {
        "F26900874",
        "26M06356",
        "M23902196",
        "M24915661",
        "25CEFL00998",
    }
    trial = next(
        record for record in records if record["case_number"] == "F26900874"
    )
    assert trial["calendar_layout"] == "trial_calendar"
    assert trial["hearing_type"] == "Jury Trial"
    assert trial["jail_id"] == "1153153"
    assert trial["booking_number"] == "80421"
    assert trial["interpreter"] == "Spanish"
    assert trial["deputy_district_attorney"] == "David Devencenzi"
    assert trial["filing_or_prosecuting_agency_number"] == "26-4299 SA"
    master = next(
        record for record in records if record["case_number"] == "M23902196"
    )
    assert master["hearing_time"] == "9:00 AM"
    assert master["status_or_custody"] == "Warrant"
    assert master["attorney"] == "Public Defender"
    assert master["filing_or_prosecuting_agency_number"] == "22-18198 M"


def test_master_calendar_time_carries_across_page_and_changes_in_page() -> None:
    records = fresno.parse_calendar_text(
        fixture("calendar_text.txt"),
        source_url=CALENDAR_URL,
        artifact_sha256="c" * 64,
    )
    by_case = {record["case_number"]: record for record in records}

    assert by_case["26M06356"]["hearing_time"] == "8:30 AM"
    assert by_case["M23902196"]["hearing_time"] == "9:00 AM"
    assert by_case["M24915661"]["hearing_time"] == "9:00 AM"
    assert by_case["25CEFL00998"]["department"] == "FCS Investigations"
    assert (
        by_case["25CEFL00998"]["case_style"]
        == "Jammie Wilson, JR vs Denise Wilson"
    )
    assert by_case["25CEFL00998"]["hearing_type"] == "FCS Investigation"


def test_calendar_changed_document_is_not_an_empty_result() -> None:
    with pytest.raises(fresno.FresnoSourceChangedError) as raised:
        fresno.parse_calendar_text(
            "This is not a Fresno calendar.",
            source_url=CALENDAR_URL,
            artifact_sha256="c" * 64,
        )

    assert raised.value.code == "calendar_records_missing"


def test_tentative_parser_preserves_rulings_and_exception_sections() -> None:
    records = fresno.parse_tentative_rulings_text(
        fixture("tentative_text.txt"),
        source_url=RULING_URL,
        artifact_sha256="d" * 64,
    )

    assert len(records) == 4
    by_kind = {}
    for record in records:
        by_kind.setdefault(record["record_kind"], []).append(record)
    assert by_kind["tentative_ruling_must_appear"][0]["case_number"] == (
        "25CECG00001"
    )
    continuance = by_kind["tentative_ruling_continuance"][0]
    assert continuance["case_number"] == "25CECG03846"
    assert continuance["continued_to_date"] == "2026-08-20"
    assert continuance["continued_to_time"] == "3:30 p.m."
    assert continuance["continued_to_department"] == 501
    rulings = by_kind["tentative_ruling"]
    assert [record["matter_number"] for record in rulings] == [34, 41]
    first = rulings[0]
    assert first["case_style"] == "Martin v. Central Unified School District"
    assert first["issued_by_initials"] == "KCK"
    assert first["issued_date"] == "2026-07-27"
    assert first["oral_argument"]["time"] == "3:00 p.m."
    assert "sign the proposed order" in first["tentative_ruling"]
    second = rulings[1]
    assert second["motion"].endswith("Portions of Complaint")
    assert "vehicle pursuit" in second["explanation"]
    assert second["provenance"]["page_number"] == 3


def test_tentative_structured_matter_shape_change_is_explicit() -> None:
    changed = fixture("tentative_text.txt").replace(
        "Motion:",
        "Application:",
        1,
    )

    with pytest.raises(fresno.FresnoSourceChangedError) as raised:
        fresno.parse_tentative_rulings_text(
            changed,
            source_url=RULING_URL,
            artifact_sha256="d" * 64,
        )

    assert raised.value.code == "tentative_matter_changed"


def test_probate_search_parser_requires_webforms_request_token() -> None:
    search = fresno.parse_probate_search_page(
        fixture("probate_search.html")
    )

    assert set(fresno._PROBATE_REQUIRED_HIDDEN).issubset(  # noqa: SLF001
        search.hidden_fields
    )
    assert search.hidden_fields["__ncforminfo"] == "fixture-forminfo"
    assert len(search.schema_fingerprint) == 64

    changed = fixture("probate_search.html").replace(
        'name="__ncforminfo"',
        'name="different_token"',
    )
    with pytest.raises(fresno.FresnoSourceChangedError) as raised:
        fresno.parse_probate_search_page(changed)
    assert raised.value.code == "probate_hidden_fields_changed"


def test_probate_results_return_every_note_and_stable_distinct_ids() -> None:
    search = fresno.parse_probate_search_page(
        fixture("probate_search.html")
    )
    results = fresno.parse_probate_results(
        fixture("probate_results.html"),
        requested_case_number="19CEPR00967",
        search_schema_fingerprint=search.schema_fingerprint,
    )

    assert results.notes_found == 3
    assert len(results.records) == 3
    assert results.case_style == "Celestino Perales (Estate)"
    assert results.date_printed == "2026-07-30"
    assert results.records[0]["hearing_date"] == "2026-04-01"
    assert results.records[0]["reviewer_initials"] == "CVN"
    assert results.records[2]["reviewer_initials"] == "SKM"
    same_date = [
        record
        for record in results.records
        if record["hearing_date"] == "2025-10-07"
    ]
    assert len(same_date) == 2
    assert len({record["canonical_ref"] for record in same_date}) == 2
    assert all(
        record["record_lineage"]
        == "examiner_note_not_part_of_official_court_file"
        for record in results.records
    )


def test_probate_explicit_no_notes_is_authoritative_empty() -> None:
    results = fresno.parse_probate_results(
        fixture("probate_no_results.html"),
        requested_case_number="99CEPR99999",
    )

    assert results.notes_found == 0
    assert results.records == ()
    assert results.no_results_message == (
        "No notes found for Case Number: 99CEPR99999"
    )


def test_probate_count_mismatch_is_not_silently_truncated() -> None:
    changed = fixture("probate_results.html").replace(
        "<td>3</td>",
        "<td>4</td>",
        1,
    )

    with pytest.raises(fresno.FresnoSourceChangedError) as raised:
        fresno.parse_probate_results(
            changed,
            requested_case_number="19CEPR00967",
        )

    assert raised.value.code == "probate_result_count_mismatch"
    assert raised.value.details == {"summary_count": 4, "row_count": 3}


def test_probate_client_posts_every_transient_field_and_optional_date() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture("probate_search.html"),
                url=fresno.PROBATE_NOTES_URL,
            )
        ],
        [
            FakeResponse(
                text=fixture("probate_results.html"),
                url=fresno.PROBATE_NOTES_URL,
            )
        ],
    )
    client = fresno.FresnoSuperiorCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    results = client.probate_notes(
        "19CEPR00967",
        hearing_date="04/01/2026",
    )

    assert len(results.records) == 3
    assert [call[0] for call in session.calls] == ["get", "post"]
    post_kwargs = session.calls[1][2]
    payload = post_kwargs["data"]
    assert payload["__VIEWSTATE"] == "fixture-viewstate"
    assert payload["__EVENTVALIDATION"] == "fixture-validation"
    assert payload["__ncforminfo"] == "fixture-forminfo"
    assert payload["CaseNumberTextBox"] == "19CEPR00967"
    assert payload["EventDateTextBox"] == "04/01/2026"
    assert payload["SearchButton"] == "Search"
    assert post_kwargs["headers"]["Referer"] == fresno.PROBATE_NOTES_URL


def test_pdf_client_hashes_and_extracts_layout_text(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession(
        [
            FakeResponse(
                content=PDF_BYTES,
                url=CALENDAR_URL,
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    calls: list[dict[str, Any]] = []

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=fixture("calendar_text.txt").encode(),
            stderr=b"",
        )

    monkeypatch.setattr(fresno.subprocess, "run", fake_run)
    client = fresno.FresnoSuperiorCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    artifact = client.pdf(CALENDAR_URL, family="calendar")

    assert artifact.content == PDF_BYTES
    assert len(artifact.sha256) == 64
    assert "Master Calendar Report" in artifact.text
    assert calls[0]["args"][0] == ["pdftotext", "-layout", "-", "-"]
    assert calls[0]["kwargs"]["input"] == PDF_BYTES


@pytest.mark.parametrize(
    ("command", "expected_count"),
    [
        (("calendar-index",), 3),
        (("calendar", "--date", "2026-07-30"), 5),
        (("rulings-index",), 6),
        (
            ("rulings", "--department", "501", "--date", "2026-07-30"),
            4,
        ),
        (("probate-notes", "--case-number", "19CEPR00967"), 3),
        (("alternatives",), 7),
    ],
)
def test_execute_operations_emit_valid_envelopes(
    command: tuple[str, ...],
    expected_count: int,
) -> None:
    result = fresno.execute(
        parse_args(*command),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == expected_count
    lineage = validate_envelope(result.to_dict())
    assert lineage["source_id"] == result.query.source.source_id
    assert len(lineage["records"]) == expected_count


def test_execute_probate_no_notes_uses_no_results_not_failure() -> None:
    result = fresno.execute(
        parse_args(
            "probate-notes",
            "--case-number",
            "99CEPR99999",
        ),
        client=FakeClient(no_probate_results=True),
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_probe_covers_all_anonymous_data_operations() -> None:
    client = FakeClient()
    result = fresno.execute(
        parse_args("probe"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["portal"]["anonymous_case_search_control_present"] is False
    assert probe["calendar"]["index_artifact_count"] == 3
    assert probe["calendar"]["parsed_record_count"] == 5
    assert probe["tentative_rulings"]["index_artifact_count"] == 6
    assert list(probe["tentative_rulings"]["departments"]) == [
        403,
        501,
        502,
        503,
    ]
    assert probe["tentative_rulings"]["parsed_record_count"] == 4
    assert probe["probate_examiner_notes"]["parsed_record_count"] == 3
    assert ("probate_notes", "19CEPR00967", None) in client.calls


def test_alternatives_preserve_scope_fields_and_route_distinctions() -> None:
    records = fresno._alternatives()  # noqa: SLF001
    case_index = next(
        record
        for record in records
        if record["record_kind"] == "court_data_product"
    )
    archive = next(
        record
        for record in records
        if record["canonical_ref"] == "FRESNO-RECORDS:ARCHIVES"
    )
    administrative = next(
        record
        for record in records
        if record["record_kind"] == "administrative_record_request_route"
    )
    appellate = next(
        record
        for record in records
        if record["record_kind"] == "appellate_case_information_complement"
    )

    assert case_index["form_price"] == {
        "amount_usd": 70,
        "unit": "per_report_per_month",
    }
    assert case_index["published_fields"]["family_law"] is None
    assert case_index["published_fields"]["probate"] is None
    assert "probate" in archive["holdings"]
    assert "case-record copies" in administrative["scope_distinction"]
    assert "not a substitute" in appellate["coverage_relation"]


def test_cli_exposes_no_implicit_result_limit() -> None:
    parser = fresno.build_parser()

    for command in (
        ("calendar-index",),
        ("calendar",),
        ("rulings-index",),
        ("rulings", "--department", "501"),
        ("probate-notes", "--case-number", "19CEPR00967"),
    ):
        args = parser.parse_args(list(command))
        assert not hasattr(args, "limit")


def test_transport_failure_is_not_reported_as_no_results() -> None:
    session = FakeSession([FakeResponse(status_code=503)])
    client = fresno.FresnoSuperiorCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(fresno.FresnoCourtError) as raised:
        client.text(fresno.CALENDAR_INDEX_URL)

    assert raised.value.code == "http_error"
    assert raised.value.status is ResultStatus.UNAVAILABLE
