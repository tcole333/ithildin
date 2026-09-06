from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import PublicRecordsResult, ResultStatus
from tools.public_records_http import SourceSchemaError
from tools.public_records_store import connect_courts
from tools.query_qld_ecourts import (
    DETAIL_URL,
    SEARCH_URL,
    CaseDetail,
    QldECourtsClient,
    SearchBatch,
    SearchCriteria,
    build_parser,
    build_query,
    execute,
    fetch_search,
    parse_detail_page,
    parse_results_page,
    parse_search_form,
    qld_canonical_ref,
    qld_evidence_ref,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "qld_ecourts"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        url: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def client_for(
    responses: list[FakeResponse],
) -> tuple[QldECourtsClient, FakeSession]:
    session = FakeSession(responses)
    client = QldECourtsClient(
        session=session,
        rate_limiter=SimpleNamespace(wait=lambda: None),
    )
    return client, session


def test_parse_search_form_captures_live_selector_contract() -> None:
    parsed = parse_search_form(fixture("search_form.html"))
    assert parsed.action_url == SEARCH_URL
    assert parsed.options["court"]["SUPRE"] == "Supreme"
    assert parsed.options["originating_location"]["BRISB"] == "Brisbane"
    assert parsed.options["party_role"]["DEFEN"] == "Defendant"
    assert len(parsed.schema_fingerprint) == 64
    assert "fixture-search-state" not in parsed.schema_fingerprint


def test_parse_search_form_detects_missing_webforms_state() -> None:
    broken = fixture("search_form.html").replace(
        'name="__VIEWSTATEGENERATOR"',
        'name="OLD_VIEWSTATEGENERATOR"',
    )
    with pytest.raises(SourceSchemaError, match="WebForms state"):
        parse_search_form(broken)


def test_parse_result_page_preserves_registry_disambiguated_identity() -> None:
    page = parse_results_page(
        fixture("results_page_1.html"),
        "https://apps.courts.qld.gov.au/esearching/Results.aspx"
        "?Lastcompanyname=COSCOLLUELA",
    )
    assert (page.start_record, page.end_record, page.reported_total) == (1, 1, 2)
    assert page.next_target and page.next_target.endswith("NextTopLink")
    assert not page.native_ceiling_reached
    assert len(page.rows) == 1
    row = page.rows[0]
    assert row.file_number == "6819/11"
    assert row.court_code == "SUPRE"
    assert row.originating_location_code == "BRISB"
    assert row.parties[1].last_company_name == "COSCOLLUELA"
    assert row.parties[1].date_filed_iso == "2011-08-05"
    assert row.evidence_ref == "QLD-ECOURTS:SUPRE-BRISB-6819-2011"
    assert "%2F" in row.canonical_ref


def test_parse_result_page_distinguishes_empty_and_native_ceiling() -> None:
    empty = parse_results_page(fixture("no_results.html"))
    capped = parse_results_page(fixture("capped_results.html"))
    assert empty.reported_total == 0
    assert empty.rows == ()
    assert not empty.native_ceiling_reached
    assert capped.reported_total == 500
    assert capped.native_ceiling_reached
    assert capped.next_target is not None


def test_parse_result_page_detects_column_drift() -> None:
    broken = fixture("results_page_1.html").replace(
        "<th>Party role</th>",
        "<th>Capacity</th>",
    )
    with pytest.raises(SourceSchemaError, match="party columns changed"):
        parse_results_page(broken)


def test_parse_detail_extracts_acn_events_and_document_list() -> None:
    parsed = parse_detail_page(
        fixture("detail.html"),
        (
            f"{DETAIL_URL}?Location=BRISB&Court=SUPRE"
            "&Filenumber=6819%2F11"
        ),
    )
    assert isinstance(parsed, CaseDetail)
    assert parsed.hit.evidence_ref == "QLD-ECOURTS:SUPRE-BRISB-6819-2011"
    assert parsed.date_filed_iso == "2011-08-05"
    assert parsed.related_files == ()
    assert parsed.parties[1]["acn"] == "067302158"
    assert parsed.parties[1]["representative"] == (
        "CONRADIE & ASSOCIATES SOLICITORS"
    )
    assert parsed.events[0]["date_iso"] == "2012-08-31"
    assert parsed.events[0]["resource"] == "Atkinson J"
    assert len(parsed.documents) == 3
    assert parsed.documents[1]["document_type"] == "Judgment"
    assert parsed.documents[1]["pages"] == 12
    assert parsed.documents[2]["evidence_ref"].endswith(":DOC-32")
    assert parsed.documents[2]["document_available_online"] is False


def test_parse_detail_recognizes_authoritative_missing_file() -> None:
    assert parse_detail_page(fixture("missing_detail.html"), DETAIL_URL) is None


def test_client_posts_search_and_advances_webforms_pager() -> None:
    first_url = (
        "https://apps.courts.qld.gov.au/esearching/"
        "Results.aspx?Lastcompanyname=COSCOLLUELA"
    )
    client, session = client_for(
        [
            FakeResponse(fixture("search_form.html"), url=SEARCH_URL),
            FakeResponse(fixture("results_page_1.html"), url=first_url),
            FakeResponse(fixture("results_page_2.html"), url=first_url),
        ]
    )
    batch = client.first_page(
        SearchCriteria(last_company_name="COSCOLLUELA", court="Supreme")
    )
    page_two = client.next_page(batch.first_page)
    assert page_two.start_record == 2
    search_post = session.requests[1]
    search_data = search_post["data"]
    assert isinstance(search_data, dict)
    assert (
        search_data[
            "ctl00$ContentPlaceHolder1$LayoutPanel5$lastcompanyname"
        ]
        == "COSCOLLUELA"
    )
    assert (
        search_data["ctl00$ContentPlaceHolder1$LayoutPanel3$court"]
        == "SUPRE"
    )
    pager_data = session.requests[2]["data"]
    assert isinstance(pager_data, dict)
    assert pager_data["__EVENTTARGET"].endswith("NextTopLink")
    assert pager_data["__VIEWSTATE"] == "fixture-results-page-1"


def test_default_search_traverses_every_native_page() -> None:
    form = parse_search_form(fixture("search_form.html"))
    first = parse_results_page(fixture("results_page_1.html"))
    second = parse_results_page(fixture("results_page_2.html"))

    class FakeClient:
        request_count = 3

        def first_page(self, criteria: SearchCriteria) -> SearchBatch:
            return SearchBatch(criteria, form, first)

        def next_page(self, page: object) -> object:
            assert page is first
            return second

    collection = fetch_search(
        FakeClient(),
        SearchCriteria(last_company_name="COSCOLLUELA"),
    )
    assert [row.file_number for row in collection.hits] == [
        "6819/11",
        "712/12",
    ]
    assert collection.native_pages_fetched == 2
    assert collection.source_traversal_complete
    assert not collection.caller_bound_reached


def test_capped_search_adaptively_partitions_by_court() -> None:
    form = parse_search_form(fixture("search_form.html"))
    capped = parse_results_page(fixture("capped_results.html"))
    supreme_complete = replace(
        capped,
        reported_total=1,
        native_ceiling_reached=False,
        next_target=None,
    )
    district_complete = parse_results_page(fixture("results_page_2.html"))

    class AdaptiveClient:
        request_count = 6

        def first_page(self, criteria: SearchCriteria) -> SearchBatch:
            if criteria.court is None:
                return SearchBatch(criteria, form, capped)
            if criteria.court == "SUPRE":
                return SearchBatch(criteria, form, supreme_complete)
            if criteria.court == "DISTR":
                return SearchBatch(criteria, form, district_complete)
            raise AssertionError(criteria)

        def next_page(self, page: object) -> object:
            raise AssertionError("completed child partitions need no paging")

    collection = fetch_search(
        AdaptiveClient(),
        SearchCriteria(last_company_name="SMITH"),
    )
    assert collection.ceiling_splits == 1
    assert collection.partitions_fetched == 3
    assert collection.unresolved_ceiling_partitions == ()
    assert collection.source_traversal_complete
    assert {row.court_code for row in collection.hits} == {"SUPRE", "DISTR"}


def test_explicit_limit_is_distinct_from_source_ceiling() -> None:
    form = parse_search_form(fixture("search_form.html"))
    first = parse_results_page(fixture("results_page_1.html"))

    class LimitedClient:
        request_count = 2

        def first_page(self, criteria: SearchCriteria) -> SearchBatch:
            return SearchBatch(criteria, form, first)

        def next_page(self, page: object) -> object:
            raise AssertionError("caller limit should stop before page two")

    collection = fetch_search(
        LimitedClient(),
        SearchCriteria(last_company_name="COSCOLLUELA"),
        limit=1,
    )
    assert len(collection.hits) == 1
    assert collection.caller_bound_reached
    assert not collection.source_traversal_complete
    assert collection.unresolved_ceiling_partitions == ()


def test_query_metadata_marks_omitted_limit_as_exhaustive() -> None:
    parser = build_parser()
    exhaustive = build_query(
        parser.parse_args(["search", "--party-name", "SMITH"])
    )
    bounded = build_query(
        parser.parse_args(
            ["search", "--party-name", "SMITH", "--limit", "5"]
        )
    )
    assert exhaustive.query.requested_limit is None
    assert exhaustive.query.metadata["pagination"] == "exhaustive"
    assert bounded.query.requested_limit == 5
    assert bounded.query.metadata["pagination"] == "caller_bound"


def test_sources_inventory_distinguishes_complementary_roles() -> None:
    args = build_parser().parse_args(["sources"])
    result = execute(args, log_results=False)
    assert result.status == ResultStatus.OK
    records = [dict(value) for value in result.records]
    source_ids = {value["source_id"] for value in records}
    assert "au-qld-ecourts-civil" in source_ids
    assert "au-qld-court-record-copy-request" in source_ids
    assert "au-qld-criminal-case-lookup" in source_ids
    assert "au-qld-official-caselaw" in source_ids
    assert "au-qld-state-archives-court-records" in source_ids


def test_detail_execution_returns_no_results_for_valid_missing_file() -> None:
    class MissingClient:
        def detail(
            self,
            file_number: str,
            *,
            court: str,
            location: str,
        ) -> None:
            assert file_number == "999999/99"
            assert court == "SUPRE"
            assert location == "BRISB"
            return None

    args = build_parser().parse_args(
        [
            "detail",
            "999999/99",
            "--court",
            "SUPRE",
            "--location",
            "BRISB",
        ]
    )
    result = execute(args, client=MissingClient(), log_results=False)
    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()


def test_reference_helpers_include_registry_and_escape_file_slash() -> None:
    assert (
        qld_evidence_ref("SUPRE", "BRISB", "6819/11")
        == "QLD-ECOURTS:SUPRE-BRISB-6819-2011"
    )
    canonical = qld_canonical_ref("SUPRE", "BRISB", "6819/11")
    assert canonical.startswith("STATECOURT:")
    assert "%2F" in canonical


def test_detail_projects_registry_identity_parties_events_and_document_metadata(
    tmp_path: Path,
) -> None:
    detail = parse_detail_page(
        fixture("detail.html"),
        (
            f"{DETAIL_URL}?Location=BRISB&Court=SUPRE"
            "&Filenumber=6819%2F11"
        ),
    )
    assert detail is not None
    args = build_parser().parse_args(
        [
            "detail",
            "6819/11",
            "--court",
            "SUPRE",
            "--location",
            "BRISB",
        ]
    )
    envelope = PublicRecordsResult.success(
        build_query(args),
        [detail.to_record()],
        retrieved_at="2026-07-29T12:00:00Z",
    ).to_dict()
    court_db = tmp_path / "qld-courts.db"

    report = ingest_envelope(envelope, court_db=court_db)

    assert report["snapshot_only"]["record_count"] == 0
    assert report["projected"]["cases"] == 1
    assert report["projected"]["parties"] == 3
    assert report["projected"]["case_events"] == 2
    assert report["projected"]["documents"] == 3

    db = connect_courts(court_db)
    try:
        case = db.execute(
            """
            SELECT c.source_id, c.court_id, c.raw_case_number,
                   c.source_internal_id, c.caption, c.filing_date,
                   ct.state_code
            FROM case_record c
            JOIN court ct ON ct.court_id=c.court_id
            """
        ).fetchone()
        assert case is not None
        assert tuple(case) == (
            "au-qld-ecourts-civil",
            "qld-supreme-court",
            "6819/11",
            "SUPRE-BRISB-6819-2011",
            "GEHRKE -V- COSCOLLUELA & others",
            "2011-08-05",
            "QLD",
        )
        organization = db.execute(
            """
            SELECT raw_name, entity_kind
            FROM case_party
            WHERE raw_name='R C INSURANCE PTY LTD'
            """
        ).fetchone()
        assert organization is not None
        assert tuple(organization) == (
            "R C INSURANCE PTY LTD",
            "organization",
        )
        document = db.execute(
            """
            SELECT native_document_id, document_type, page_count,
                   access_state, native_access_state, source_url
            FROM document_artifact
            WHERE document_type='Judgment'
            """
        ).fetchone()
        assert document is not None
        assert tuple(document) == (
            "QLD-ECOURTS:SUPRE-BRISB-6819-2011:DOC-17",
            "Judgment",
            12,
            "public",
            "metadata_public_copy_request_required",
            None,
        )
    finally:
        db.close()
