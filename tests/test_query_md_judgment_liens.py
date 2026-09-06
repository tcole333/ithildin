from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import query_md_judgment_liens as md


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "md_judgment_liens"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text()


class FakeResponse:
    def __init__(
        self,
        text: str,
        url: str,
        *,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.content = text.encode()
        self.url = url
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None,
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "data": data,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


def _result_row(item: int) -> str:
    return f"""
      <tr>
        <td><a href="/judgment/details.jsf?selectedCaseId=24-L-26-{item:06d}">
          24-L-26-{item:06d}</a></td>
        <td><span class="Value">Creditor {item}</span></td>
        <td><span class="Value">Debtor {item}</span></td>
        <td>BALTIMORE CITY</td><td>Entered</td><td>${item}.00</td>
        <td>00001/{item:05d}</td><td>07/30/2026</td>
      </tr>
    """


def result_html(
    *,
    total: int,
    start: int,
    count: int,
    form_name: str,
    view_state: str,
    omit_result_tbody: bool = False,
) -> str:
    end = start + count - 1 if count else 0
    paginator = ""
    if total > count:
        paginator = f"""
          <a href="#" id="{form_name}:scrollidx2"
            onclick="return submit(null,[['{form_name}:scroll','idx2']]);">
            2
          </a>
        """
    rows = "".join(_result_row(item) for item in range(start, start + count))
    result_rows = rows if omit_result_tbody else f"<tbody>{rows}</tbody>"
    return f"""
      <html><body>
        <form id="{form_name}" name="{form_name}" method="post"
          action="/judgment/judgementResults.jsf;jsessionid={form_name}">
          <div>{total} items found, displaying {start} to {end}</div>
          {paginator}
          <table class="results">
            <thead><tr>
              <th>Case Number</th><th>Name For</th><th>Name Against</th>
              <th>Court</th><th>Case Status</th><th>Judgment Amount</th>
              <th>Book Page</th><th>Entry Date</th>
            </tr></thead>
            {result_rows}
          </table>
          <input type="hidden" name="javax.faces.ViewState"
            value="{view_state}" />
        </form>
      </body></html>
    """


def collection(
    records: list[dict[str, Any]],
    *,
    total: int | None = None,
    ceiling: bool = False,
) -> md.SearchCollection:
    return md.SearchCollection(
        records=tuple(records),
        total_count=len(records) if total is None else total,
        pages_fetched=1,
        transport_page_size=md.NATIVE_PAGE_SIZE,
        source_ceiling_reached=ceiling,
        raw_artifact_refs=(md.SEARCH_URL, md.RESULTS_URL),
        form_schema_fingerprint="a" * 64,
    )


class FixtureClient:
    def __init__(
        self,
        *,
        search_collection: md.SearchCollection | None = None,
        detail_records: list[dict[str, Any]] | None = None,
    ) -> None:
        self.search_collection = search_collection
        self.detail_records = detail_records
        self.criteria: md.SearchCriteria | None = None

    def search(self, criteria: md.SearchCriteria) -> md.SearchCollection:
        self.criteria = criteria
        assert self.search_collection is not None
        return self.search_collection

    def detail(
        self,
        case_number: str,
    ) -> tuple[list[dict[str, Any]], str]:
        assert case_number
        assert self.detail_records is not None
        return self.detail_records, (
            f"{md.DETAIL_URL}?selectedCaseId={case_number}"
        )


def test_source_manifest_maps_bounds_and_distinct_record_roles() -> None:
    records = md.source_records()
    primary = next(
        row for row in records if row["source_id"] == md.SOURCE_ID
    )
    assert primary["coverage"]["courts"] == "all Maryland circuit courts"
    assert primary["bounds"]["source_result_ceiling"] == 500
    complements = [
        row for row in records if row["record_kind"] == "complementary_source"
    ]
    assert {
        "case_parties_status_events_and_case_detail",
        "underlying_case_file_and_certified_copies",
        "recorded_real_property_instruments_and_some_liens",
        "parcel_assessment_situs_and_deed_reference",
        "property_tax_and_municipal_lien_status",
    }.issubset({row["record_role"] for row in complements})
    land = next(
        row for row in complements if row["source_id"] == "us-md-land-records"
    )
    assert "book_page" in land["join_keys"]
    assert "property_address" in land["join_keys"]


def test_parse_person_form_discovers_fields_counties_and_session_action() -> None:
    state = md.parse_search_form(
        fixture("search_person.html"),
        page_url=md.SEARCH_URL,
    )
    assert state.mode == "person"
    assert state.form_name == "searchForm"
    assert state.field_names["last_name"] == "searchForm:lastName"
    assert state.county_values["BALTIMORE CITY"] == "Baltimore City"
    assert state.action_url.endswith(";jsessionid=PERSONSESSION")
    assert len(state.schema_fingerprint) == 64


def test_parse_company_form_discovers_mode_specific_field() -> None:
    state = md.parse_search_form(
        fixture("search_company.html"),
        page_url=md.SEARCH_URL,
    )
    assert state.mode == "company"
    assert state.field_names["company_name"] == "searchForm:companyName"
    assert "last_name" not in state.field_names


def test_criteria_materializes_source_dates_county_and_exact_checkbox() -> None:
    state = md.parse_search_form(fixture("search_person.html"))
    criteria = md.SearchCriteria(
        mode="person",
        last_name="Dalton",
        first_name="David",
        exact_last_name=True,
        county="Baltimore County",
        filed_from="2026-01-02",
        filed_to="2026-07-30",
    )
    payload = criteria.form_data(state)
    assert payload["searchForm:lastName"] == "Dalton"
    assert payload["searchForm:wantsExactMatch"] == "on"
    assert payload["searchForm:county"] == "BALTIMORE COUNTY"
    assert payload["searchForm:filingStartDate"] == "01/02/2026"
    assert payload["searchForm:filingEndDate"] == "07/30/2026"
    assert payload["javax.faces.ViewState"] == "person-view-state"


def test_criteria_rejects_ambiguous_or_cross_mode_fields() -> None:
    with pytest.raises(md.MarylandSelectionError):
        md.SearchCriteria(
            mode="company",
            company_name="Example LLC",
            exact_last_name=True,
        )
    with pytest.raises(md.MarylandSelectionError):
        md.SearchCriteria(
            mode="person",
            last_name="Dalton",
            filing_date="2026-01-01",
            filed_from="2025-01-01",
        )


def test_parse_results_preserves_aliases_money_and_separate_events() -> None:
    page = md.parse_results_page(fixture("results.html"))
    assert page.total_count == 2
    assert len(page.records) == 2
    entered, satisfied = page.records
    assert entered["case_number"] == "24-L-18-002266"
    assert entered["names_for"] == [
        "State of Maryland",
        "(AKA) Comptroller of Maryland",
    ]
    assert entered["judgment_amount"] == "11567.82"
    assert entered["judgment_amount_minor_units"] == 1_156_782
    assert entered["book"] == "00044"
    assert entered["page"] == "00958"
    assert ";jsessionid" not in entered["detail_url"]
    assert entered["canonical_case_ref"] == satisfied["canonical_case_ref"]
    assert entered["canonical_ref"] != satisfied["canonical_ref"]
    assert satisfied["case_status"] == "Satisfied"
    assert satisfied["book"] is None


def test_parse_results_recognizes_authoritative_empty() -> None:
    page = md.parse_results_page(fixture("results_empty.html"))
    assert page.total_count == 0
    assert page.records == ()
    assert (page.display_start, page.display_end) == (0, 0)


def test_parse_results_rejects_changed_columns() -> None:
    changed = fixture("results.html").replace(
        "<th>Entry Date</th>",
        "<th>Indexed Date</th>",
    )
    with pytest.raises(md.MarylandSourceChangedError):
        md.parse_results_page(changed)


def test_parse_detail_preserves_original_and_modification_events() -> None:
    records = md.parse_detail_page(
        fixture("detail.html"),
        expected_case_number="03-L-12-005195",
    )
    assert len(records) == 2
    original, modification = records
    assert original["event_kind"] == "original_judgment"
    assert original["event_date"] == "2012-03-27"
    assert original["status"] is None
    assert original["names_for"] == [
        "State Of Maryland",
        "(AKA) Comptroller",
    ]
    assert modification["event_kind"] == "judgment_modification"
    assert modification["status"] == "SATISFIED"
    assert modification["status_date"] == "2014-02-18"
    assert modification["county"] == "BALTIMORE COUNTY"
    assert original["canonical_ref"] != modification["canonical_ref"]
    assert ";jsessionid" not in str(original["case_search_url"])


def test_parse_detail_rejects_a_different_returned_case() -> None:
    with pytest.raises(md.MarylandSourceChangedError):
        md.parse_detail_page(
            fixture("detail.html"),
            expected_case_number="DIFFERENT-CASE",
        )


def test_client_submits_company_toggle_before_company_search() -> None:
    session = QueueSession(
        [
            FakeResponse(fixture("search_person.html"), md.SEARCH_URL),
            FakeResponse(
                fixture("search_company.html"),
                f"{md.SEARCH_URL};jsessionid=COMPANYSESSION",
            ),
            FakeResponse(
                fixture("results.html"),
                f"{md.RESULTS_URL}?companyName=Example+LLC",
            ),
        ]
    )
    client = md.MarylandJudgmentClient(
        session=session,
        minimum_interval=0,
    )
    found = client.search(
        md.SearchCriteria(
            mode="company",
            company_name="Example LLC",
            county="Baltimore City",
        )
    )
    assert found.total_count == 2
    assert [call["method"] for call in session.calls] == [
        "GET",
        "POST",
        "POST",
    ]
    assert session.calls[1]["data"] == {
        "searchForm": "searchForm",
        "searchForm:companyIndicatorRadio": "Y",
        "javax.faces.ViewState": "person-view-state",
    }
    assert (
        session.calls[2]["data"]["searchForm:companyName"]
        == "Example LLC"
    )
    assert (
        session.calls[2]["data"]["searchForm:county"]
        == "BALTIMORE CITY"
    )


def test_client_toggles_a_persisted_company_session_back_to_person() -> None:
    session = QueueSession(
        [
            FakeResponse(fixture("search_company.html"), md.SEARCH_URL),
            FakeResponse(fixture("search_person.html"), md.SEARCH_URL),
        ]
    )
    client = md.MarylandJudgmentClient(
        session=session,
        minimum_interval=0,
    )
    state = client.search_form(company=False)
    assert state.mode == "person"
    assert session.calls[1]["data"] == {
        "searchForm": "searchForm",
        "searchForm:companyIndicatorRadio": "N",
        "javax.faces.ViewState": "company-view-state",
    }


def test_client_discovers_dynamic_pagination_prefix_and_exhausts_pages() -> None:
    first = result_html(
        total=26,
        start=1,
        count=25,
        form_name="alpha77",
        view_state="first-page-state",
    )
    second = result_html(
        total=26,
        start=26,
        count=1,
        form_name="beta92",
        view_state="second-page-state",
        omit_result_tbody=True,
    )
    session = QueueSession(
        [
            FakeResponse(fixture("search_person.html"), md.SEARCH_URL),
            FakeResponse(first, md.RESULTS_URL),
            FakeResponse(second, md.RESULTS_URL),
        ]
    )
    client = md.MarylandJudgmentClient(
        session=session,
        minimum_interval=0,
    )
    found = client.search(
        md.SearchCriteria(mode="person", last_name="Example")
    )
    assert found.total_count == 26
    assert found.pages_fetched == 2
    assert len(found.records) == 26
    assert session.calls[2]["data"] == {
        "alpha77": "alpha77",
        "alpha77:scroll": "idx2",
        "javax.faces.ViewState": "first-page-state",
    }


def test_client_detects_pagination_that_does_not_advance() -> None:
    first = result_html(
        total=26,
        start=1,
        count=25,
        form_name="alpha77",
        view_state="first-page-state",
    )
    session = QueueSession(
        [
            FakeResponse(fixture("search_person.html"), md.SEARCH_URL),
            FakeResponse(first, md.RESULTS_URL),
            FakeResponse(first, md.RESULTS_URL),
        ]
    )
    client = md.MarylandJudgmentClient(
        session=session,
        minimum_interval=0,
    )
    with pytest.raises(md.MarylandSourceChangedError):
        client.search(
            md.SearchCriteria(mode="person", last_name="Example")
        )


def test_execute_issues_query_bound_cursor_and_resumes() -> None:
    records = list(md.parse_results_page(fixture("results.html")).records)
    records.append(
        {
            **records[0],
            "canonical_ref": "MDJUDGMENT:INDEX:THIRD",
            "case_number": "24-L-26-000003",
        }
    )
    client = FixtureClient(search_collection=collection(records))
    parser = md.build_parser()
    first_args = parser.parse_args(["person", "Dalton", "--limit", "2"])
    first = md.execute(
        first_args,
        client=client,
        log_results=False,
        retrieved_at=RETRIEVED_AT,
    )
    assert first.status.value == "ok"
    assert len(first.records) == 2
    assert first.next_cursor
    second_args = parser.parse_args(
        [
            "person",
            "Dalton",
            "--limit",
            "2",
            "--cursor",
            str(first.next_cursor),
        ]
    )
    second = md.execute(
        second_args,
        client=client,
        log_results=False,
        retrieved_at=RETRIEVED_AT,
    )
    assert len(second.records) == 1
    assert second.next_cursor is None


def test_execute_marks_source_ceiling_as_partial_without_dropping_rows() -> None:
    records = list(md.parse_results_page(fixture("results.html")).records)
    client = FixtureClient(
        search_collection=collection(
            records,
            total=500,
            ceiling=True,
        )
    )
    args = md.build_parser().parse_args(
        ["person", "S", "--all-results"]
    )
    result = md.execute(
        args,
        client=client,
        log_results=False,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "partial"
    assert len(result.records) == 2
    assert result.errors[0].code == "source_result_ceiling_reached"
    coverage = result.query.query.metadata["coverage"]
    assert coverage["source_result_ceiling_reached"] is True


def test_execute_preserves_authoritative_empty_result() -> None:
    client = FixtureClient(search_collection=collection([]))
    args = md.build_parser().parse_args(
        ["company", "No Such Company", "--all-results"]
    )
    result = md.execute(
        args,
        client=client,
        log_results=False,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "no_results"
    assert not result.errors


def test_execute_detail_returns_all_source_events() -> None:
    records = md.parse_detail_page(fixture("detail.html"))
    client = FixtureClient(detail_records=records)
    args = md.build_parser().parse_args(
        ["detail", "03-L-12-005195"]
    )
    result = md.execute(
        args,
        client=client,
        log_results=False,
        retrieved_at=RETRIEVED_AT,
    )
    assert result.status.value == "ok"
    assert [record["event_kind"] for record in result.records] == [
        "original_judgment",
        "judgment_modification",
    ]


def test_application_error_is_not_misreported_as_no_results() -> None:
    error_html = """
      <html><body><span class="error">
        An unexpected error (500) occurred. Please try again later.
      </span></body></html>
    """
    with pytest.raises(md.MarylandSourceResponseError):
        md.parse_results_page(error_html)
