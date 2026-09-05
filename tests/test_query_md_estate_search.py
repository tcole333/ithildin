from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_md_estate_search as md


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/md_estate_search"
)
RETRIEVED_AT = "2026-07-30T12:00:00Z"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _allowed() -> dict[str, Any]:
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {},
    }


def _args(*values: str) -> Any:
    return md.build_parser().parse_args(list(values))


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(md, "log_search", lambda *args, **kwargs: None)


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
        data: Mapping[str, str] | None,
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "data": dict(data) if data is not None else None,
                "timeout": timeout,
            }
        )
        return self.responses.pop(0)


class FixtureClient:
    def __init__(
        self,
        *,
        first: md.ResultsPage | None = None,
        next_pages: list[md.ResultsPage] | None = None,
        detail: md.DetailPage | None = None,
    ) -> None:
        self.first = first or md.parse_results_page(
            fixture("results_page_1.html")
        )
        self.next_pages = list(next_pages or [])
        self.detail_page = detail or md.parse_detail_page(
            fixture("detail.html"),
            f"{md.DETAIL_URL}?src=row&RecordId=1868548158",
        )
        self.criteria: list[md.SearchCriteria] = []
        self.postback_targets: list[str] = []
        self.detail_ids: list[str] = []

    def search(self, criteria: md.SearchCriteria) -> md.ResultsPage:
        self.criteria.append(criteria)
        return self.first

    def postback(
        self, page: md.ResultsPage, target: str
    ) -> md.ResultsPage:
        self.postback_targets.append(target)
        return self.next_pages.pop(0)

    def detail(self, record_id: str) -> md.DetailPage:
        self.detail_ids.append(record_id)
        return self.detail_page


def test_parse_search_form_discovers_webforms_contract_and_refresh() -> None:
    state = md.parse_search_form(fixture("search_form.html"))
    assert state.action_url == md.SEARCH_URL
    assert state.field_names["estate_number"] == "txtEstateNo"
    assert state.field_names["party_type"] == "cboPartyType"
    assert state.county_values["baltimore"] == "3"
    assert state.county_values["baltimore county"] == "3"
    assert state.county_values["baltimore city"] == "24"
    assert state.status_values["open"] == "OPEN"
    assert state.type_values["regular estate"] == "RE"
    assert state.party_values["personal representative"] == (
        "Personal Representative"
    )
    assert state.refresh.timestamp == "2026-07-29T20:00:00Z"
    assert state.refresh.instance == "rownetwebalt"
    assert len(state.schema_fingerprint) == 64


def test_criteria_materializes_role_dates_options_and_exact_match() -> None:
    state = md.parse_search_form(fixture("search_form.html"))
    criteria = md.SearchCriteria(
        operation="representative",
        last_name="Novak",
        first_name="Cynthia",
        exact_last_name=True,
        county="Baltimore County",
        status="Open",
        estate_type="Regular Estate",
        filed_from="2026-01-02",
        filed_to="2026-07-30",
    )
    data = criteria.form_data(state)
    assert data["txtLN"] == "Novak"
    assert data["txtFN"] == "Cynthia"
    assert data["chkExactMatchLastName"] == "on"
    assert data["cboCountyId"] == "3"
    assert data["cboStatus"] == "OPEN"
    assert data["cboType"] == "RE"
    assert data["cboPartyType"] == "Personal Representative"
    assert data["DateOfFilingFrom"] == "01/02/2026"
    assert data["DateOfFilingTo"] == "07/30/2026"
    assert data["cmdSearch"] == "Search"
    assert data["__VIEWSTATE"] == "form-viewstate"


def test_estate_number_criteria_uses_decedent_party_form_value() -> None:
    state = md.parse_search_form(fixture("search_form.html"))
    criteria = md.SearchCriteria(
        operation="estate",
        estate_number="238438",
        county="3",
    )
    data = criteria.form_data(state)
    assert data["txtEstateNo"] == "238438"
    assert data["txtLN"] == ""
    assert data["cboCountyId"] == "3"
    assert data["cboPartyType"] == "Decedent"


def test_criteria_rejects_cross_mode_dates_and_unknown_options() -> None:
    with pytest.raises(md.MarylandEstateSelectionError):
        md.SearchCriteria(
            operation="estate",
            estate_number="238438",
            last_name="Novak",
        )
    with pytest.raises(md.MarylandEstateSelectionError):
        md.SearchCriteria(
            operation="decedent",
            last_name="Novak",
            filing_date="2026-01-01",
            filed_from="2025-01-01",
        )
    state = md.parse_search_form(fixture("search_form.html"))
    with pytest.raises(md.MarylandEstateSelectionError):
        md.SearchCriteria(
            operation="decedent",
            last_name="Novak",
            county="Not a Maryland county",
        ).form_data(state)


def test_results_page_has_authoritative_count_dynamic_target_and_rows() -> None:
    page = md.parse_results_page(fixture("results_page_1.html"))
    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.total_count == 21
    assert len(page.rows) == 20
    assert page.page_targets[2] == "dgSearchResults$ctl24$ctl01"
    assert page.hidden_fields["__VIEWSTATE"] == "page-one-viewstate"
    first = page.rows[0]
    assert first.county == "Baltimore County"
    assert first.estate_number == "238438"
    assert first.record_id == "1868548158"
    assert first.detail_url.endswith(
        "frmDocketImages.aspx?src=row&RecordId=1868548158"
    )


def test_result_normalization_preserves_role_case_identity_and_old_date() -> None:
    page = md.parse_results_page(fixture("results_page_1.html"))
    criteria = md.SearchCriteria(
        operation="representative",
        last_name="Novak",
    )
    record = md.normalize_search_row(
        page.rows[1],
        criteria=criteria,
        refresh=page.refresh,
        schema_fingerprint=page.schema_fingerprint,
    )
    assert record["queried_party_role"] == "Personal Representative"
    assert record["decedent_name"] == "ALICE NOVAK"
    assert record["date_of_death"] == "1988-11-14"
    assert record["canonical_ref"] == record["canonical_case_ref"]
    assert "111602" in record["canonical_ref"]
    assert record["source_internal_id"] == "1868385636"
    assert record["stable_key_fields"] == ["county", "estate_number"]


def test_authoritative_empty_page_is_distinct_from_schema_failure() -> None:
    page = md.parse_results_page(fixture("results_empty.html"))
    assert page.total_count == 0
    assert page.rows == ()
    broken = fixture("results_empty.html").replace(
        "Search Criteria Returned No Results.",
        "The application is unavailable.",
    )
    with pytest.raises(md.MarylandEstateSourceChangedError):
        md.parse_results_page(broken)


def test_result_parser_rejects_row_count_conflict() -> None:
    broken = fixture("results_page_2.html").replace(
        "(21 RECORDS TOTAL)", "(22 RECORDS TOTAL)"
    )
    with pytest.raises(md.MarylandEstateSourceChangedError):
        md.parse_results_page(broken)


def test_detail_emits_case_parties_and_distinct_docket_events() -> None:
    detail = md.parse_detail_page(
        fixture("detail.html"),
        f"{md.DETAIL_URL}?src=row&RecordId=1868548158",
    )
    assert len(detail.records) == 4
    case = detail.records[0]
    assert case["record_kind"] == "estate_case_detail"
    assert case["estate_number"] == "238438"
    assert case["county"] == "Baltimore County"
    assert case["date_of_death"] == "2025-07-01"
    assert case["will_status"] == "PROBATED"
    assert case["aliases"] == [
        "PATRICIA R. NOVAK",
        "PATRICIA ANN NOVAK",
    ]
    assert case["personal_representatives"][0] == {
        "role": "personal_representative",
        "name": "CYNTHIA L. NOVAK",
        "address_raw": "16632 JM PEARCE RD, MONKTON, MD 21111-1726",
        "raw": (
            "CYNTHIA L. NOVAK "
            "[16632 JM PEARCE RD, MONKTON, MD 21111-1726]"
        ),
    }
    assert case["attorneys"][0]["name"] == "ALEX COUNSEL"
    assert case["docket_event_count"] == 3
    docket = detail.records[1]
    assert docket["record_kind"] == "estate_docket_event"
    assert docket["native_section_id"] == (
        "47005d96-f1d7-425d-83b8-5aa1538a08bf"
    )
    assert docket["page_count"] == 4
    assert docket["canonical_ref"] != case["canonical_ref"]
    assert docket["canonical_case_ref"] == case["canonical_ref"]
    fallback = detail.records[3]
    assert fallback["source_internal_id"].startswith("material-")
    assert fallback["copy_available"] is False


def test_detail_rejects_record_id_mismatch() -> None:
    with pytest.raises(md.MarylandEstateSourceChangedError):
        md.parse_detail_page(
            fixture("detail.html"),
            f"{md.DETAIL_URL}?src=row&RecordId=1868548158",
            expected_record_id="999",
        )


def test_stateful_client_posts_discovered_form_and_page_targets() -> None:
    session = QueueSession(
        [
            FakeResponse(fixture("search_form.html"), md.SEARCH_URL),
            FakeResponse(fixture("results_page_1.html"), md.SEARCH_URL),
            FakeResponse(fixture("results_page_2.html"), md.SEARCH_URL),
        ]
    )
    client = md.MarylandEstateClient(
        session=session,
        minimum_interval=0,
    )
    first = client.search(
        md.SearchCriteria(
            operation="decedent",
            last_name="Novak",
            county="Baltimore County",
        )
    )
    second = client.postback(first, first.page_targets[2])
    assert second.current_page == 2
    assert session.calls[1]["data"]["txtLN"] == "Novak"
    assert session.calls[1]["data"]["cboCountyId"] == "3"
    assert session.calls[2]["data"]["__EVENTTARGET"] == (
        "dgSearchResults$ctl24$ctl01"
    )
    assert session.calls[2]["data"]["__VIEWSTATE"] == "page-one-viewstate"
    assert "txtLN" not in session.calls[2]["data"]


def test_detail_client_fetches_direct_numeric_record_locator() -> None:
    url = f"{md.DETAIL_URL}?src=row&RecordId=1868548158"
    session = QueueSession([FakeResponse(fixture("detail.html"), url)])
    detail = md.MarylandEstateClient(
        session=session, minimum_interval=0
    ).detail("1868548158")
    assert detail.records[0]["estate_number"] == "238438"
    assert session.calls[0]["method"] == "GET"
    assert "RecordId=1868548158" in session.calls[0]["url"]
    with pytest.raises(md.MarylandEstateSelectionError):
        md.MarylandEstateClient(
            session=QueueSession([]), minimum_interval=0
        ).detail("../bad")


def test_execute_limit_returns_partial_and_cursor_within_page() -> None:
    result = md.execute(
        _args("decedent", "Novak", "--limit", "3"),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == md.ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert result.next_cursor is not None
    state = md._decode_cursor(result.next_cursor)
    assert state.page_number == 1
    assert state.row_offset == 3
    assert state.emitted_count == 3
    assert state.total_count == 21


def test_resume_rebuilds_search_and_navigates_from_live_target() -> None:
    first_client = FixtureClient()
    first_result = md.execute(
        _args("decedent", "Novak", "--limit", "20"),
        access_decision=_allowed(),
        client=first_client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert first_result.next_cursor is not None
    resume_client = FixtureClient(
        next_pages=[
            md.parse_results_page(fixture("results_page_2.html"))
        ]
    )
    resumed = md.execute(
        _args(
            "decedent",
            "Novak",
            "--limit",
            "5",
            "--cursor",
            first_result.next_cursor,
        ),
        access_decision=_allowed(),
        client=resume_client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert resumed.status == md.ResultStatus.OK
    assert [record["estate_number"] for record in resumed.records] == [
        "100021"
    ]
    assert resume_client.criteria[0].last_name == "Novak"
    assert resume_client.postback_targets == [
        "dgSearchResults$ctl24$ctl01"
    ]


def test_all_results_traverses_every_native_page() -> None:
    client = FixtureClient(
        next_pages=[
            md.parse_results_page(fixture("results_page_2.html"))
        ]
    )
    result = md.execute(
        _args("estate", "238438", "--all-results"),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == md.ResultStatus.OK
    assert len(result.records) == 21
    assert result.next_cursor is None
    assert client.postback_targets == ["dgSearchResults$ctl24$ctl01"]


def test_cursor_binds_criteria_source_refresh_and_count() -> None:
    initial = md.execute(
        _args("decedent", "Novak", "--limit", "3"),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert initial.next_cursor
    mismatched = md.execute(
        _args(
            "decedent",
            "Smith",
            "--limit",
            "3",
            "--cursor",
            initial.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert mismatched.status == md.ResultStatus.UNAVAILABLE
    assert mismatched.errors[0].code == "stale_or_invalid_cursor"

    first = md.parse_results_page(fixture("results_page_1.html"))
    changed_refresh = replace(
        first,
        refresh=md.RefreshMarker(
            raw="7/30/2026 4:00:00 PM (rownetwebalt)",
            timestamp="2026-07-30T20:00:00Z",
            instance="rownetwebalt",
        ),
    )
    stale = md.execute(
        _args(
            "decedent",
            "Novak",
            "--limit",
            "3",
            "--cursor",
            initial.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(first=changed_refresh),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert stale.status == md.ResultStatus.UNAVAILABLE
    assert "refreshed" in stale.errors[0].message

    changed_count = replace(first, total_count=22, total_pages=2)
    stale_count = md.execute(
        _args(
            "decedent",
            "Novak",
            "--limit",
            "3",
            "--cursor",
            initial.next_cursor,
        ),
        access_decision=_allowed(),
        client=FixtureClient(first=changed_count),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert stale_count.status == md.ResultStatus.UNAVAILABLE
    assert "count changed" in stale_count.errors[0].message


def test_sliding_pager_uses_forward_ellipsis_then_visible_target() -> None:
    first = md.parse_results_page(fixture("results_page_1.html"))
    page_1 = replace(
        first,
        total_count=201,
        total_pages=11,
        page_targets={2: "page-2"},
        forward_target="jump-11",
    )
    page_11 = replace(
        first,
        current_page=11,
        total_count=201,
        total_pages=11,
        page_targets={},
        forward_target=None,
    )
    client = FixtureClient(first=page_1, next_pages=[page_11])
    reached, _artifacts = md._navigate(client, page_1, 11)
    assert reached.current_page == 11
    assert client.postback_targets == ["jump-11"]


def test_execute_empty_is_authoritative_no_results() -> None:
    empty = md.parse_results_page(fixture("results_empty.html"))
    result = md.execute(
        _args("decedent", "NameThatDoesNotExist"),
        access_decision=_allowed(),
        client=FixtureClient(first=empty),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == md.ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_detail_and_probe_execution_preserve_distinct_roles() -> None:
    detail_client = FixtureClient()
    detail = md.execute(
        _args("detail", "1868548158"),
        access_decision=_allowed(),
        client=detail_client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert detail.status == md.ResultStatus.OK
    assert detail.records[0]["record_kind"] == "estate_case_detail"
    assert detail.records[1]["record_kind"] == "estate_docket_event"

    one = replace(
        detail_client.first,
        total_count=1,
        total_pages=1,
        rows=(detail_client.first.rows[0],),
        page_targets={},
    )
    probe_client = FixtureClient(first=one)
    probe = md.execute(
        _args("probe"),
        access_decision=_allowed(),
        client=probe_client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert probe.status == md.ResultStatus.OK
    assert probe.records[0]["record_kind"] == "source_probe"
    assert probe.records[0]["sentinel_estate_number"] == "238438"
    assert probe.records[0]["sentinel_docket_event_count"] == 3


def test_routes_map_missing_record_roles_to_join_keys() -> None:
    records = md.source_records()
    manifest = records[0]
    assert manifest["identity"]["estate_case"] == [
        "county",
        "estate_number",
    ]
    assert manifest["identity"]["docket_event"][-1] == "SecId"
    complements = records[1:]
    roles = {record["record_role"] for record in complements}
    assert {
        "official_estate_file_and_copy_route",
        "estate_claim_index",
        "estate_publication_and_creditor_notice",
        "judgment_and_lien_index",
        "estate_real_property_instruments",
        "parcel_assessment_and_deed_reference",
    }.issubset(roles)
    land = next(
        record
        for record in complements
        if record["source_id"] == "us-md-land-records"
    )
    assert "personal_representative_name" in land["join_keys"]
    assert "liber_folio" in land["join_keys"]


def test_http_failures_are_not_reported_as_no_results() -> None:
    session = QueueSession(
        [
            FakeResponse(
                "rate limited",
                md.SEARCH_URL,
                status_code=429,
            )
        ]
    )
    result = md.execute(
        _args("decedent", "Novak"),
        access_decision=_allowed(),
        client=md.MarylandEstateClient(
            session=session,
            minimum_interval=0,
        ),
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert result.status == md.ResultStatus.RATE_LIMITED
    assert result.records == ()
    assert result.errors[0].code == "rate_limited"
