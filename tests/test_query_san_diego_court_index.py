from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_san_diego_court_index as san_diego
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/san_diego_court_index"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


PARTY_PAGE_1 = fixture("party_page_1.html")
PARTY_PAGE_2 = fixture("party_page_2.html")
CASE_RESULTS = fixture("case_results.html")
CASE_DETAIL = fixture("case_detail.html")
NO_RESULTS = fixture("no_results.html")
NEW_LANDING = fixture("new_filings_landing.html")
NEW_A = fixture("new_filings_a.html")
NEW_B = fixture("new_filings_b.html")
NEW_EMPTY = fixture("new_filings_empty.html")
CHALLENGE = fixture("challenge.html")


def parse_args(*values: str) -> Namespace:
    return san_diego.build_parser().parse_args(list(values))


@dataclass
class FixtureResponse:
    text: str
    url: str
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)


class MappingSession:
    def __init__(self, responses: dict[str, FixtureResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FixtureResponse:
        del kwargs
        self.calls.append(url)
        try:
            return self.responses[url]
        except KeyError as error:
            raise AssertionError(f"unexpected request: {url}") from error

    def close(self) -> None:
        self.closed = True


def test_parser_defaults_do_not_impose_collection_caps() -> None:
    party = parse_args(
        "party-search",
        "--case-type",
        "civil",
        "--last-name",
        "Epstein",
    )
    case = parse_args("case-search", "IC810023")
    filings = parse_args("new-filings")

    assert party.limit is None
    assert party.offset == 0
    assert party.begin_year == 1974
    assert party.end_year >= 2026
    assert case.limit is None
    assert case.case_type == "all"
    assert filings.limit is None
    assert filings.case_type == "all"


def test_party_result_parser_preserves_rows_and_native_pagination() -> None:
    page = san_diego.parse_index_results_page(
        PARTY_PAGE_1,
        source_url=(
            "https://courtindex.sdcourt.ca.gov/CISPublic/viewname"
            "?caseType=C&site=A&partyType=A&fileDateBegin=1974"
            "&fileDateEnd=2026&lastname=EPSTEIN&firstname=JEFFREY&page=1"
        ),
        search_kind="party",
    )

    assert page.current_page == 1
    assert page.total_pages == 2
    assert len(page.page_urls) == 2
    assert [row.case_number for row in page.rows] == ["IC810023", "696483"]
    assert page.rows[0].matched_party == "EPSTEIN, JEFFREY"
    assert page.rows[0].opposing_party == (
        "AMERICAN EXPRESS TRAVEL RELATED SERVICES COMPANY INC"
    )
    assert page.rows[0].filing_date == "2003-04-30"
    assert page.rows[0].detail_url == san_diego.PROBE_DETAIL_URL


def test_case_result_parser_preserves_named_sides() -> None:
    page = san_diego.parse_index_results_page(
        CASE_RESULTS,
        source_url=(
            "https://courtindex.sdcourt.ca.gov/CISPublic/viewcase"
            "?caseType=A&site=A&caseNumber=IC810023&page=1"
        ),
        search_kind="case",
    )

    assert len(page.rows) == 1
    row = page.rows[0]
    assert row.case_number == "IC810023"
    assert row.plaintiff_petitioner == (
        "AMERICAN EXPRESS TRAVEL RELATED SERVICES COMPANY INC"
    )
    assert row.defendant_respondent_party == "EPSTEIN, JEFFREY"
    assert row.case_location == "San Diego"


def test_authoritative_empty_and_challenge_are_distinct() -> None:
    empty = san_diego.parse_index_results_page(
        NO_RESULTS,
        source_url=(
            "https://courtindex.sdcourt.ca.gov/CISPublic/viewname?page=1"
        ),
        search_kind="party",
    )
    assert empty.authoritative_empty is True
    assert empty.rows == ()

    with pytest.raises(
        san_diego.SanDiegoCourtError,
        match="verification challenge",
    ) as captured:
        san_diego.parse_index_results_page(
            CHALLENGE,
            source_url=san_diego.PARTY_SEARCH_URL,
            search_kind="party",
        )
    assert captured.value.status is ResultStatus.HUMAN_REQUIRED


def test_case_detail_parser_preserves_category_parties_and_media_state() -> None:
    detail = san_diego.parse_case_detail(
        CASE_DETAIL,
        source_url=san_diego.PROBE_DETAIL_URL,
    )

    assert detail.case_number == "IC810023"
    assert detail.case_title == (
        "AMERICAN EXPRESS TRAVEL RELATED SERVICES COMPANY INC vs EPSTEIN"
    )
    assert detail.case_type == "Civil"
    assert detail.filing_date == "2003-04-30"
    assert detail.category_code == "A60301"
    assert detail.category_label == "Account Stated"
    assert [party.display_name for party in detail.parties] == [
        "AMERICAN EXPRESS TRAVEL RELATED SERVICES COMPANY INC",
        "EPSTEIN, JEFFREY",
    ]
    assert detail.file_location_available is True
    assert "Older Records Kiosks" in (detail.image_status or "")
    assert detail.microfilm == (
        {
            "microfilmid": "1",
            "location": "SD-OREC",
            "reelnumber": None,
            "framenumber": None,
        },
    )


def test_new_filings_landing_and_page_parsers_preserve_native_partitions() -> None:
    routes = san_diego.parse_new_filings_landing(NEW_LANDING)
    assert set(routes) == set(san_diego.NEW_FILING_TYPE_CODES)
    assert routes["civil"].endswith("nf_cv_a.html")

    page = san_diego.parse_new_filings_page(
        NEW_A,
        source_url=routes["civil"],
        case_type="civil",
    )
    assert page.last_updated == "July 29, 2026"
    assert page.partition == "a"
    assert {san_diego._new_filing_partition(url) for url in page.partition_urls} == {
        "a",
        "b",
        "xz",
        "ot",
    }
    assert page.parties[0].name == (
        "AAA AIR CONDITIONING AND HEATING SERVICES INC"
    )
    assert page.cases[0].filing_date == "2026-07-22"
    assert page.cases[0].location == "San Diego"


def test_empty_new_filing_partition_is_authoritative_when_timestamped() -> None:
    page = san_diego.parse_new_filings_page(
        NEW_EMPTY,
        source_url=(
            san_diego.NEW_FILINGS_BASE_URL + "nf_cv_xz.html"
        ),
        case_type="civil",
    )
    assert page.authoritative_empty is True
    assert page.parties == ()
    assert page.cases == ()


def test_new_filings_client_discovers_and_exhausts_all_native_partitions() -> None:
    landing_url = san_diego.NEW_FILINGS_LANDING_URL
    a_url = san_diego.NEW_FILINGS_BASE_URL + "nf_cv_a.html"
    b_url = san_diego.NEW_FILINGS_BASE_URL + "nf_cv_b.html"
    xz_url = san_diego.NEW_FILINGS_BASE_URL + "nf_cv_xz.html"
    ot_url = san_diego.NEW_FILINGS_BASE_URL + "nf_cv_ot.html"
    session = MappingSession(
        {
            landing_url: FixtureResponse(NEW_LANDING, landing_url),
            a_url: FixtureResponse(NEW_A, a_url),
            b_url: FixtureResponse(NEW_B, b_url),
            xz_url: FixtureResponse(NEW_EMPTY, xz_url),
            ot_url: FixtureResponse(NEW_EMPTY, ot_url),
        }
    )
    client = san_diego.NewFilingsClient(
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )

    result = client.collect(("civil",), limit=1)

    assert result.pages_discovered == 4
    assert result.pages_fetched == 4
    assert result.native_partitions_exhausted is True
    assert result.caller_limit == 1
    assert session.calls == [landing_url, a_url, b_url, ot_url, xz_url]

    records = san_diego.normalize_new_filings(result)
    assert len(records) == 1
    assert records[0]["search_metadata"][
        "caller_limit_applied_after_native_partition_collection"
    ] is True
    assert records[0]["search_metadata"]["native_partitions_exhausted"] is True


def test_browser_client_parses_all_returned_pages_before_caller_slicing() -> None:
    calls: list[tuple[dict[str, Any], dict[str, Any]]] = []

    def browser_runner(selection: dict[str, Any], **kwargs: Any):
        calls.append((dict(selection), dict(kwargs)))
        return {
            "ok": True,
            "pages": [
                {
                    "url": (
                        "https://courtindex.sdcourt.ca.gov/CISPublic/viewname"
                        "?caseType=C&site=A&partyType=A&fileDateBegin=1974"
                        "&fileDateEnd=2026&lastname=EPSTEIN"
                        "&firstname=JEFFREY&page=1"
                    ),
                    "html": PARTY_PAGE_1,
                },
                {
                    "url": (
                        "https://courtindex.sdcourt.ca.gov/CISPublic/viewname"
                        "?caseType=C&site=A&partyType=A&fileDateBegin=1974"
                        "&fileDateEnd=2026&lastname=EPSTEIN"
                        "&firstname=JEFFREY&page=2"
                    ),
                    "html": PARTY_PAGE_2,
                },
            ],
        }

    client = san_diego.SanDiegoCourtIndexClient(
        browser_runner=browser_runner,
        minimum_interval=0.5,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    result = client.party_search(
        {
            "case_type": "C",
            "site": "A",
            "party_type": "A",
            "begin_year": 1974,
            "end_year": 2026,
            "last_name": "Epstein",
            "first_name": "Jeffrey",
        },
        limit=1,
        offset=1,
    )

    assert result.native_rows_observed == 3
    assert result.pages_fetched == 2
    assert result.native_pages_discovered == 2
    assert result.native_pages_exhausted is True
    assert [row.case_number for row in result.rows] == ["696483"]
    assert calls[0][1]["minimum_interval"] == 0.5
    assert calls[0][1]["max_attempts"] == 2


class FakeIndexClient:
    def __init__(self, result: san_diego.IndexSearchResult) -> None:
        self.result = result
        self.calls: list[Any] = []

    def party_search(
        self,
        selection: dict[str, Any],
        *,
        limit: int | None,
        offset: int,
    ) -> san_diego.IndexSearchResult:
        self.calls.append(("party", dict(selection), limit, offset))
        return self.result

    def close(self) -> None:
        self.calls.append(("close",))


def _index_result() -> san_diego.IndexSearchResult:
    page = san_diego.parse_index_results_page(
        PARTY_PAGE_1,
        source_url=(
            "https://courtindex.sdcourt.ca.gov/CISPublic/viewname"
            "?caseType=C&site=A&partyType=A&fileDateBegin=1974"
            "&fileDateEnd=2026&lastname=EPSTEIN&firstname=JEFFREY&page=1"
        ),
        search_kind="party",
    )
    return san_diego.IndexSearchResult(
        rows=page.rows,
        native_rows_observed=2,
        pages_fetched=1,
        native_pages_discovered=1,
        native_pages_exhausted=True,
        max_rows_on_page=2,
        caller_limit=None,
        caller_offset=0,
        schema_fingerprint="a" * 64,
        source_url=page.source_url,
    )


def test_execute_returns_valid_envelope_and_precise_collection_metadata() -> None:
    result = san_diego.execute(
        parse_args(
            "party-search",
            "--case-type",
            "civil",
            "--last-name",
            "Epstein",
            "--first-name",
            "Jeffrey",
        ),
        index_client=FakeIndexClient(_index_result()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    validate_envelope(result.to_dict())
    assert {record["raw_case_number"] for record in result.records} == {
        "IC810023",
        "696483",
    }
    metadata = result.records[0]["search_metadata"]
    assert metadata["native_pages_exhausted"] is True
    assert metadata["caller_limit"] is None
    assert metadata["server_result_ceiling_disclosed"] is True
    assert metadata["server_result_ceiling_value"] is None
    assert metadata["server_result_ceiling_reached"] is None
    assert "browser navigation" in metadata["transport_batching"]


def test_party_year_selection_preserves_native_coverage_bounds() -> None:
    with pytest.raises(
        san_diego.SanDiegoSelectionError,
        match="begins in 1974",
    ):
        san_diego._party_selection(
            parse_args(
                "party-search",
                "--case-type",
                "civil",
                "--last-name",
                "Smith",
                "--begin-year",
                "1973",
            )
        )

    with pytest.raises(
        san_diego.SanDiegoSelectionError,
        match="not be earlier",
    ):
        san_diego._party_selection(
            parse_args(
                "party-search",
                "--case-type",
                "civil",
                "--last-name",
                "Smith",
                "--begin-year",
                "2025",
                "--end-year",
                "2024",
            )
        )


def test_case_detail_url_must_preserve_official_native_parameters() -> None:
    assert san_diego._validated_detail_url(
        san_diego.PROBE_DETAIL_URL
    ) == san_diego.PROBE_DETAIL_URL
    with pytest.raises(san_diego.SanDiegoSelectionError):
        san_diego._validated_detail_url(
            "https://example.com/CISPublic/casedetail"
            "?casenum=IC810023&casesite=SD&applcode=C"
        )
    with pytest.raises(
        san_diego.SanDiegoSelectionError,
        match="lacks required",
    ):
        san_diego._validated_detail_url(
            "https://courtindex.sdcourt.ca.gov/CISPublic/casedetail"
            "?casenum=IC810023"
        )


def test_alternative_inventory_preserves_route_identity_and_access_state() -> None:
    records = san_diego._alternatives()
    routes = {record["route_id"]: record for record in records}

    assert routes["family-register-of-actions"]["access_state"] == (
        "http_403_observed_2026-07-30"
    )
    assert routes["odyssey-register-of-actions"]["access_state"] == (
        "cloudflare_verification_observed_2026-07-30"
    )
    assert routes["five-day-court-calendar"]["access_state"] == (
        "stale_2020_closure_page_observed_2026-07-30"
    )
    assert routes["pre-1974-indexes"]["official"] is True
    assert (
        routes["commercial-state-court-aggregators"]["official"] is False
    )


def test_browser_helper_error_maps_human_verification() -> None:
    def browser_runner(selection: dict[str, Any], **kwargs: Any):
        del selection, kwargs
        raise san_diego.SanDiegoCourtError(
            "human_verification_required",
            "verification",
            status=ResultStatus.HUMAN_REQUIRED,
            category="access",
        )

    client = san_diego.SanDiegoCourtIndexClient(
        browser_runner=browser_runner
    )
    with pytest.raises(san_diego.SanDiegoCourtError) as captured:
        client.case_search(
            {
                "case_type": "A",
                "site": "A",
                "case_number": "IC810023",
            }
        )
    assert captured.value.status is ResultStatus.HUMAN_REQUIRED
