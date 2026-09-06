from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_md_estate_notices_claims as md


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/md_estate_notices_claims"
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
    args = md.build_parser().parse_args(list(values))
    md._normalize_boolean_args(args)
    return args


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(md, "log_search", lambda *args, **kwargs: None)


class FakeResponse:
    def __init__(self, text: str, url: str) -> None:
        self.text = text
        self.content = text.encode()
        self.url = url
        self.status_code = 200
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
    def __init__(self) -> None:
        self.notice_page = md.parse_notice_results_page(
            fixture("notice_results.html")
        )
        self.claim_criteria = md.ClaimCriteria(
            role="decedent",
            last_name="Smith",
        )
        self.claim_page = md.parse_claim_results_page(
            fixture("claim_results.html"),
            effective_parameters=self.claim_criteria.parameters(),
        )
        self.detail_page = md.parse_claim_detail(
            fixture("claim_detail.html"),
            f"{md.CLAIM_DETAIL_URL}?src=row&RecordId=270350434",
        )
        self.notice_searches: list[md.NoticeCriteria] = []
        self.claim_searches: list[md.ClaimCriteria] = []
        self.detail_ids: list[tuple[str, str]] = []

    def search_notices(
        self,
        criteria: md.NoticeCriteria,
    ) -> md.NoticeResultsPage:
        self.notice_searches.append(criteria)
        return self.notice_page

    def postback_notices(
        self,
        page: md.NoticeResultsPage,
        target: str,
    ) -> md.NoticeResultsPage:
        raise AssertionError((page, target))

    def search_claims(
        self,
        criteria: md.ClaimCriteria,
    ) -> md.ClaimResultsPage:
        self.claim_searches.append(criteria)
        return self.claim_page

    def postback_claims(
        self,
        page: md.ClaimResultsPage,
        target: str,
    ) -> md.ClaimResultsPage:
        raise AssertionError((page, target))

    def claim_detail(
        self,
        record_id: str,
        source_partition: str,
    ) -> md.ClaimDetail:
        self.detail_ids.append((record_id, source_partition))
        return self.detail_page


def test_notice_form_discovers_filters_defaults_and_counties() -> None:
    form = md.parse_notice_form(fixture("notice_results.html"))
    assert form.action_url == md.NOTICE_SEARCH_URL
    assert form.field_names["party_type"] == "PartyType"
    assert form.county_values["montgomery"] == "15"
    assert form.county_values["montgomery county"] == "15"
    assert form.party_values["representative"] == "PersonalRepresentative"
    assert form.default_published_from_raw == "06/30/2026"
    assert form.default_published_to_raw == "07/30/2026"
    assert len({value for value in form.county_values.values() if value}) == 24


def test_notice_criteria_materializes_dates_party_role_and_sort() -> None:
    form = md.parse_notice_form(fixture("notice_results.html"))
    criteria = md.NoticeCriteria(
        county="Montgomery County",
        published_from="2026-07-01",
        published_to="2026-07-30",
        death_date="2026-06-11",
        party_type="representative",
        last_name="Taylor",
        first_name="Patrick",
        sort="County ASC",
    )
    data = criteria.form_data(form)
    assert data["cboCountyId"] == "15"
    assert data["txtDoPFrom"] == "07/01/2026"
    assert data["txtDoPTo"] == "07/30/2026"
    assert (data["txtDODM"], data["txtDODD"], data["txtDODY"]) == (
        "06",
        "11",
        "2026",
    )
    assert data["PartyType"] == "PersonalRepresentative"
    assert data["ddlSortField"] == "County ASC"


def test_notice_parser_preserves_full_text_variants_and_occurrence_identity() -> None:
    page = md.parse_notice_results_page(fixture("notice_results.html"))
    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.total_count == 21
    assert page.page_targets[2] == "dgSearchResults$ctl24$ctl01"
    first = md.normalize_notice_row(page.rows[0], page=page)
    assert first["notice_id"] == "177286"
    assert first["estate_number"] == "W127316"
    assert first["decedent_name"] == "SUSAN S TAYLOR"
    assert first["decedent_aliases"] == ["SUSAN SPURNEY TAYLOR"]
    assert first["publication_date"] == "2026-07-30"
    assert first["date_of_death"] == "2026-06-11"
    assert first["notice_variant"].startswith("notice_of_appointment")
    assert "<strong>W127316</strong>" in first["full_notice_html"]
    assert "PERSONAL REPRESENTATIVE" in first["full_notice_text"]
    assert first["canonical_ref"].endswith("/notice/177286")
    assert first["occurrence_identity"] == {
        "source_id": md.NOTICE_SOURCE_ID,
        "notice_id": "177286",
    }
    caveat = md.normalize_notice_row(page.rows[1], page=page)
    assert caveat["notice_title"] == "PUBLIC NOTICE OF CAVEAT"
    assert caveat["notice_id"] != first["notice_id"]


def test_notice_empty_result_is_authoritative() -> None:
    page = md.parse_notice_results_page(fixture("notice_empty.html"))
    assert page.total_count == 0
    assert page.rows == ()
    broken = fixture("notice_empty.html").replace(
        "Search Criteria Returned No Results.",
        "Service unavailable.",
    )
    with pytest.raises(md.MarylandEstateSupplementSourceChangedError):
        md.parse_notice_results_page(broken)


def test_claim_form_discovers_roles_person_company_flags_and_freshness() -> None:
    form = md.parse_claim_form(fixture("claim_form.html"))
    assert form.action_url == md.CLAIM_SEARCH_URL
    assert form.role_values["claimant"] == "Filed By"
    assert form.type_values["secured debt"] == "SECURED DEBT"
    assert form.status_values["partially disallowed"] == (
        "PARTIALLY DISALLOWED"
    )
    assert form.linked_values["yes"] == "yes"
    assert form.migrated_values["no"] == "no"
    assert form.refresh.timestamp == "2026-07-29T20:00:00Z"
    assert form.refresh.instance == "rownetwebalt"


def test_claim_criteria_preserves_role_entity_fields_status_and_flags() -> None:
    form = md.parse_claim_form(fixture("claim_form.html"))
    criteria = md.ClaimCriteria(
        role="claimant",
        last_name="Olade",
        exact_last_name=True,
        first_name="Yadira",
        corporation="UNIV OF MD MEDICAL SYSTEM",
        estate_number="28355",
        filed_date="2026-07-28",
        county="Charles County",
        claim_type="DEBT",
        claim_status="OPEN",
        linked_to_estate=True,
        migrated_to_estate=False,
    )
    data = criteria.form_data(form)
    assert data["rblSearchNameBy"] == "Filed By"
    assert data["txtLN"] == "Olade"
    assert data["chkExactMatchLastName"] == "on"
    assert data["txtCorpName"] == "UNIV OF MD MEDICAL SYSTEM"
    assert data["txtDOF"] == "07/28/2026"
    assert data["cboCountyId"] == "8"
    assert data["cboType"] == "DEBT"
    assert data["cboStatus"] == "OPEN"
    assert data["rblLinkedToEstate"] == "yes"
    assert data["rblMigratedToEstate"] == "no"
    assert criteria.parameters()["migrated_to_estate"] is False


def test_claim_result_detail_and_normalization_preserve_source_grain() -> None:
    criteria = md.ClaimCriteria(role="decedent", last_name="Smith")
    page = md.parse_claim_results_page(
        fixture("claim_results.html"),
        effective_parameters=criteria.parameters(),
    )
    assert page.total_count == 21
    assert page.page_targets[2] == "dgSearchResults$ctl24$ctl01"
    row = page.rows[0]
    assert row.record_id == "270350434"
    assert row.source_partition == "row"
    assert row.county == "Charles County"
    detail = md.parse_claim_detail(
        fixture("claim_detail.html"),
        row.detail_url,
        expected_record_id=row.record_id,
        expected_partition=row.source_partition,
    )
    record = md.normalize_claim_row(
        row,
        criteria=criteria,
        page=page,
        detail=detail,
    )
    assert record["claim_identity"] == {
        "source_id": md.CLAIM_SOURCE_ID,
        "source_partition": "row",
        "record_id": "270350434",
    }
    assert record["estate_number"] == "28355"
    assert record["filed_date"] == "2026-07-28"
    assert record["claimant_person_name"] == "OLADE, YADIRA"
    assert record["claimant_organization_name"] == (
        "UNIV OF MD MEDICAL SYSTEM"
    )
    assert record["claimant_entity_types"] == ["person", "organization"]
    assert record["claim_amount"] == "750.00"
    assert record["claim_type"] == "DEBT"
    assert record["source_reported_claim_status"] == "OPEN"
    assert record["linked_to_estate"] is None
    assert record["linked_to_estate_basis"] == "not_published"
    assert record["migrated_to_estate"] is None
    assert record["interpretation"][
        "filing_is_not_allowance_or_adjudication"
    ] is True


def test_claim_linked_flag_comes_from_source_query_filter_not_estate_number() -> None:
    criteria = md.ClaimCriteria(
        role="decedent",
        last_name="Smith",
        linked_to_estate=True,
    )
    page = md.parse_claim_results_page(
        fixture("claim_results.html"),
        effective_parameters=criteria.parameters(),
    )
    row = page.rows[0]
    detail = md.parse_claim_detail(
        fixture("claim_detail.html"),
        row.detail_url,
        expected_record_id=row.record_id,
        expected_partition=row.source_partition,
    )

    record = md.normalize_claim_row(
        row,
        criteria=criteria,
        page=page,
        detail=detail,
    )

    assert record["estate_number"] == "28355"
    assert record["linked_to_estate"] is True
    assert record["linked_to_estate_basis"] == "source_query_filter"


def test_claim_empty_result_is_authoritative_and_refresh_preserved() -> None:
    page = md.parse_claim_results_page(
        fixture("claim_empty.html"),
        effective_parameters={"last_name": "ZZZZZQNONEXISTENT"},
    )
    assert page.rows == ()
    assert page.total_count == 0
    assert page.refresh.raw == "7/29/2026 4:00:00 PM (rownetwebalt)"


def test_stateful_clients_post_discovered_forms_and_dynamic_targets() -> None:
    notice_session = QueueSession(
        [
            FakeResponse(fixture("notice_results.html"), md.NOTICE_SEARCH_URL),
            FakeResponse(fixture("notice_results.html"), md.NOTICE_SEARCH_URL),
        ]
    )
    notice_client = md.MarylandEstateSupplementClient(
        session=notice_session,
        minimum_interval=0,
    )
    notice_page = notice_client.search_notices(
        md.NoticeCriteria(county="Montgomery", last_name="Taylor")
    )
    assert notice_session.calls[1]["data"]["cboCountyId"] == "15"
    assert notice_session.calls[1]["data"]["txtLN"] == "Taylor"
    assert notice_page.rows[0].notice_id == "177286"

    claim_session = QueueSession(
        [
            FakeResponse(fixture("claim_form.html"), md.CLAIM_SEARCH_URL),
            FakeResponse(fixture("claim_results.html"), md.CLAIM_SEARCH_URL),
            FakeResponse(fixture("claim_detail.html"), (
                f"{md.CLAIM_DETAIL_URL}?src=row&RecordId=270350434"
            )),
        ]
    )
    claim_client = md.MarylandEstateSupplementClient(
        session=claim_session,
        minimum_interval=0,
    )
    criteria = md.ClaimCriteria(
        role="decedent",
        last_name="Smith",
        claim_status="OPEN",
    )
    claim_page = claim_client.search_claims(criteria)
    assert claim_session.calls[1]["data"]["txtLN"] == "Smith"
    assert claim_page.effective_parameters == criteria.parameters()
    detail = claim_client.claim_detail("270350434", "row")
    assert detail.record["claim_type"] == "DEBT"


def test_execute_limits_are_optional_and_cursors_bind_source_query_snapshot() -> None:
    client = FixtureClient()
    notices = md.execute(
        _args("notices", "--limit", "1"),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert notices.status == md.ResultStatus.PARTIAL
    assert len(notices.records) == 1
    assert notices.next_cursor
    notice_cursor = md._decode_cursor(notices.next_cursor)
    assert notice_cursor.source_id == md.NOTICE_SOURCE_ID
    assert notice_cursor.emitted_count == 1
    assert notices.errors[0].code == "caller_result_limit"
    assert notices.errors[0].details == {"source_total": 21, "emitted_through": 1}

    claims = md.execute(
        _args(
            "claims",
            "--last-name",
            "Smith",
            "--limit",
            "1",
        ),
        access_decision=_allowed(),
        client=client,
        retrieved_at=RETRIEVED_AT,
        log_results=False,
    )
    assert claims.status == md.ResultStatus.PARTIAL
    assert claims.records[0]["record_id"] == "270350434"
    assert client.detail_ids == [("270350434", "row")]
    claim_cursor = md._decode_cursor(claims.next_cursor)
    assert claim_cursor.source_id == md.CLAIM_SOURCE_ID
    assert claim_cursor.effective_criteria_fingerprint == (
        md._effective_fingerprint(client.claim_page)
    )
    assert claims.errors[0].code == "caller_result_limit"


class PagedFixtureClient(FixtureClient):
    """Complete synthetic 20+1 pages built from the parsed source row shapes."""

    def __init__(self) -> None:
        super().__init__()
        self.notice_rows = tuple(
            replace(self.notice_page.rows[0], notice_id=str(177286 + index), source_page=1 if index < 20 else 2)
            for index in range(21)
        )
        self.claim_rows = tuple(
            replace(
                self.claim_page.rows[0], record_id=str(270350434 + index),
                detail_url=f"{md.CLAIM_DETAIL_URL}?src=row&RecordId={270350434 + index}",
                source_page=1 if index < 20 else 2,
            )
            for index in range(21)
        )
        self.notice_page = replace(self.notice_page, rows=self.notice_rows[:20])
        self.claim_page = replace(self.claim_page, rows=self.claim_rows[:20])

    def search_notices(self, criteria: md.NoticeCriteria) -> md.NoticeResultsPage:
        page = super().search_notices(criteria)
        return replace(page, effective_parameters={**page.effective_parameters, **criteria.parameters()})

    def search_claims(self, criteria: md.ClaimCriteria) -> md.ClaimResultsPage:
        page = super().search_claims(criteria)
        return replace(page, effective_parameters=criteria.parameters())

    def postback_notices(self, page: md.NoticeResultsPage, target: str) -> md.NoticeResultsPage:
        assert page.current_page == 1 and target == page.page_targets[2]
        return replace(page, current_page=2, rows=self.notice_rows[20:], page_targets={}, forward_target=None)

    def postback_claims(self, page: md.ClaimResultsPage, target: str) -> md.ClaimResultsPage:
        assert page.current_page == 1 and target == page.page_targets[2]
        return replace(page, current_page=2, rows=self.claim_rows[20:], page_targets={}, forward_target=None)

    def claim_detail(self, record_id: str, source_partition: str) -> md.ClaimDetail:
        detail = super().claim_detail(record_id, source_partition)
        return replace(
            detail,
            record={**detail.record, "record_id": record_id, "source_partition": source_partition},
            url=f"{md.CLAIM_DETAIL_URL}?src={source_partition}&RecordId={record_id}",
        )


def _paged_execute(command: str, client: PagedFixtureClient, *options: str):
    return md.execute(
        _args(command, *options), access_decision=_allowed(), client=client,
        retrieved_at=RETRIEVED_AT, log_results=False,
    )


@pytest.mark.parametrize("command", ["notices", "claims"])
def test_limit_continuation_crosses_native_page_without_skips_or_duplicates(command: str) -> None:
    client = PagedFixtureClient()
    first = _paged_execute(command, client, "--limit", "1")
    assert first.status == md.ResultStatus.PARTIAL
    middle = _paged_execute(command, client, "--limit", "19", "--cursor", first.next_cursor)
    assert middle.status == md.ResultStatus.PARTIAL
    position = md._decode_cursor(middle.next_cursor)
    assert (position.emitted_count, position.page_number, position.row_offset) == (20, 2, 0)
    assert middle.errors[0].details == {"source_total": 21, "emitted_through": 20}
    final = _paged_execute(command, client, "--cursor", middle.next_cursor)
    assert final.status == md.ResultStatus.OK
    assert final.next_cursor is None and not final.errors
    key, first_id = ("notice_id", 177286) if command == "notices" else ("record_id", 270350434)
    records = first.records + middle.records + final.records
    assert [record[key] for record in records] == [str(first_id + index) for index in range(21)]
    if command == "claims":
        assert client.detail_ids == [(str(first_id + index), "row") for index in range(21)]


@pytest.mark.parametrize("command", ["notices", "claims"])
@pytest.mark.parametrize("limit", [None, "21"])
def test_complete_traversal_is_ok_with_omitted_or_exact_limit(command: str, limit: str | None) -> None:
    options = ("--limit", limit) if limit else ()
    result = _paged_execute(command, PagedFixtureClient(), *options)
    assert result.status == md.ResultStatus.OK
    assert len(result.records) == 21
    assert result.next_cursor is None and not result.errors


@pytest.mark.parametrize("command", ["notices", "claims"])
@pytest.mark.parametrize("change", ["source", "query", "snapshot", "schema", "count"])
def test_limited_cursor_rejects_changed_source_query_or_snapshot(command: str, change: str) -> None:
    client = PagedFixtureClient()
    first = _paged_execute(command, client, "--limit", "1")
    options = ["--cursor", first.next_cursor]
    if change == "source":
        command = "claims" if command == "notices" else "notices"
    elif change == "query":
        options.extend(["--last-name", "Different"])
    else:
        attribute = "notice_page" if command == "notices" else "claim_page"
        page = getattr(client, attribute)
        fields = {
            "snapshot": {"snapshot_marker": "changed"},
            "schema": {"schema_fingerprint": "changed"},
            "count": {"total_count": 22},
        }
        setattr(client, attribute, replace(page, **fields[change]))
    result = _paged_execute(command, client, *options)
    assert result.status not in {md.ResultStatus.OK, md.ResultStatus.PARTIAL, md.ResultStatus.NO_RESULTS}
    assert result.records == () and result.next_cursor is None
    assert result.errors[0].code == "stale_or_invalid_cursor"


def test_source_records_keep_notices_claims_and_estate_routes_separate() -> None:
    records = md.source_records()
    manifests = {
        record["source_id"]: record
        for record in records
        if record["record_kind"] == "source_manifest"
    }
    assert set(manifests) == {
        md.NOTICE_SOURCE_ID,
        md.CLAIM_SOURCE_ID,
    }
    assert manifests[md.NOTICE_SOURCE_ID]["identity"][
        "notice_occurrence"
    ] == ["notice_id"]
    assert manifests[md.CLAIM_SOURCE_ID]["identity"][
        "claim_occurrence"
    ] == ["source_partition", "RecordId"]
    complements = {
        record["source_id"]
        for record in records
        if record["record_kind"] == "complementary_source"
    }
    assert {
        "us-md-estate-search",
        "us-md-register-of-wills-offices",
        "us-md-land-records",
        "us-md-sdat-real-property",
    } <= complements
