from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tools import query_ohio_franklin_probate as probate
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_probate"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


class IndexFixtureClient:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def index_page(self, operation: str, url: str) -> probate.IndexPage:
        self.calls.append(url)
        return probate.parse_index_page(
            self.pages[url],
            source_url=url,
            operation=operation,
        )


class FailingSecondPageClient(IndexFixtureClient):
    def __init__(self, pages: dict[str, str], failed_url: str) -> None:
        super().__init__(pages)
        self.failed_url = failed_url

    def index_page(self, operation: str, url: str) -> probate.IndexPage:
        if url == self.failed_url:
            raise probate.FranklinProbateError(
                "fixture_transport",
                "fixture second page failed",
                category="transport",
                retryable=True,
            )
        return super().index_page(operation, url)


@dataclass
class FixtureResponse:
    text: str
    url: str
    status_code: int = 200


class MappingSession:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, **_: Any) -> FixtureResponse:
        self.calls.append(url)
        return FixtureResponse(self.pages[url], url)

    def close(self) -> None:
        pass


def test_source_capabilities_publish_verified_routes_and_selector_grammar() -> None:
    args = probate.build_parser().parse_args(["source", "--json"])

    result = probate.execute(args)

    assert result.status is ResultStatus.OK
    source = result.records[0]
    assert source["source_id"] == "us-oh-franklin-probate-netdata"
    assert {route["operation"] for route in source["routes"]} >= {
        "name",
        "number",
        "opened",
        "type",
        "attorney",
        "fiduciary",
        "case",
        "docket",
        "fiduciaries",
    }
    assert source["paging"]["default"] == (
        "follow_source_forward_keys_to_exhaustion"
    )
    assert source["selector_grammar"]["blank_fixed_width_character"] == ";"


def test_landing_parser_preserves_methods_forms_and_operational_notices() -> None:
    landing = probate.parse_landing_page(fixture("landing.html"))

    assert [item["value"] for item in landing["search_methods"]] == [
        "CaseName",
        "CaseOpenDate",
        "CaseNumberSuffix",
        "CaseTypeSubtype",
        "AttorneyName",
        "FiduciaryName",
    ]
    assert len(landing["notices"]) == 2
    open_date = next(form for form in landing["forms"] if form["id"] == "CaseOpenDate")
    assert open_date["action_url"] == (
        "https://probatesearch.franklincountyohio.gov/"
        "netdata/PBODateInx.ndm/input"
    )


def test_case_index_parser_preserves_native_row_status_and_detail_route() -> None:
    page = probate.parse_index_page(
        fixture("name-page-1.html"),
        source_url=probate._index_url("name", "LUPO"),
        operation="name",
    )

    assert len(page.records) == 2
    assert page.next_url is not None
    assert page.previous_url is not None
    first = page.records[0]
    assert first["case_number"] == "617503"
    assert first["case_type_code"] == "E"
    assert first["status_code"] == "03"
    assert first["source_row"] == {
        "Case Number": "617503",
        "Case Name": "LUPO, THERESA E.",
        "Type": "ESTATE",
        "SubType": "ANCILLARY ADMINISTRATION",
        "Status": "03",
        "Opened": "01/04/2023",
        "Closed": "",
    }
    second = page.records[1]
    assert second["case_suffix"] == "A"
    assert second["case_type_code"] == "GA"
    assert second["detail_href_raw"].startswith("http://")
    assert second["detail_url"].startswith("https://")


def test_exact_number_not_found_marker_is_authoritative_empty() -> None:
    html = """
    <table>
      <tr><th>Case Number</th><th>Case Name</th><th>Type</th><th>SubType</th><th>Status</th><th>Opened</th><th>Closed</th></tr>
      <tr><td>999999</td><td>CASE IS NOT FOUND</td><td></td><td></td><td></td><td></td><td></td></tr>
    </table>
    """

    page = probate.parse_index_page(
        html,
        source_url=probate._index_url("number", "999999!="),
        operation="number",
    )

    assert page.records == ()
    assert page.next_url is None


def test_attorney_and_fiduciary_discovery_keep_distinct_native_rows() -> None:
    attorney = probate.parse_index_page(
        fixture("attorney-index.html"),
        source_url=probate._index_url("attorney", "ARTZ"),
        operation="attorney",
    ).records[0]
    fiduciary = probate.parse_index_page(
        fixture("fiduciary-index.html"),
        source_url=probate._index_url("fiduciary", "ARTZ"),
        operation="fiduciary",
    ).records[0]

    assert attorney["record_kind"] == "probate_attorney_index"
    assert attorney["attorney_number"] == "0002003"
    assert attorney["attorney_profile_url"].endswith("?string=0002003")
    assert fiduciary["record_kind"] == "probate_case_index"
    assert fiduciary["fiduciary_name"] == "ARTZ, BRIAN S."
    assert fiduciary["case_name"] == "LUPO, THERESA E."
    assert fiduciary["attorney_name"] == "ARTZ, BRIAN S."


def test_default_collection_exhausts_native_forward_pages() -> None:
    first_url = probate._index_url("name", "SMITH")
    first = probate.parse_index_page(
        fixture("name-page-1.html"),
        source_url=first_url,
        operation="name",
    )
    assert first.next_url is not None
    client = IndexFixtureClient(
        {
            first_url: fixture("name-page-1.html"),
            first.next_url: fixture("name-page-2.html"),
        }
    )

    collected = probate.collect_index(
        client,
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
    )

    assert [row["case_number"] for row in collected.records] == [
        "617503",
        "620001",
        "620002",
        "620003",
    ]
    assert collected.native_pages_exhausted is True
    assert collected.next_cursor is None
    assert client.calls == [first_url, first.next_url]


def test_explicit_caller_window_resumes_inside_native_page_then_across_page() -> None:
    first_url = probate._index_url("name", "SMITH")
    first = probate.parse_index_page(
        fixture("name-page-1.html"),
        source_url=first_url,
        operation="name",
    )
    assert first.next_url is not None
    pages = {
        first_url: fixture("name-page-1.html"),
        first.next_url: fixture("name-page-2.html"),
    }

    first_window = probate.collect_index(
        IndexFixtureClient(pages),
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
        limit=1,
    )
    assert [row["case_number"] for row in first_window.records] == ["617503"]
    assert first_window.next_cursor is not None

    second_client = IndexFixtureClient(pages)
    second_window = probate.collect_index(
        second_client,
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
        limit=2,
        cursor=first_window.next_cursor,
    )
    assert [row["case_number"] for row in second_window.records] == [
        "620001",
        "620002",
    ]
    assert second_window.next_cursor is not None
    assert second_client.calls == [first_url, first.next_url]

    final_window = probate.collect_index(
        IndexFixtureClient(pages),
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
        limit=2,
        cursor=second_window.next_cursor,
    )
    assert [row["case_number"] for row in final_window.records] == ["620003"]
    assert final_window.next_cursor is None
    assert final_window.native_pages_exhausted is True


def test_cursor_is_bound_to_original_query() -> None:
    first_url = probate._index_url("name", "SMITH")
    client = IndexFixtureClient({first_url: fixture("name-page-1.html")})
    first_window = probate.collect_index(
        client,
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
        limit=1,
    )
    assert first_window.next_cursor

    with pytest.raises(probate.FranklinProbateSelectionError, match="does not belong"):
        probate.collect_index(
            client,
            operation="name",
            initial_url=probate._index_url("name", "JONES"),
            parameters={"term": "JONES"},
            cursor=first_window.next_cursor,
        )


def test_later_page_failure_preserves_rows_and_a_resumable_cursor() -> None:
    first_url = probate._index_url("name", "SMITH")
    first = probate.parse_index_page(
        fixture("name-page-1.html"),
        source_url=first_url,
        operation="name",
    )
    assert first.next_url is not None
    pages = {
        first_url: fixture("name-page-1.html"),
        first.next_url: fixture("name-page-2.html"),
    }
    client = FailingSecondPageClient(pages, first.next_url)

    with pytest.raises(probate.FranklinProbatePartialCollection) as captured:
        probate.collect_index(
            client,
            operation="name",
            initial_url=first_url,
            parameters={"term": "SMITH"},
        )

    partial = captured.value
    assert [row["case_number"] for row in partial.records] == [
        "617503",
        "620001",
    ]
    resumed = probate.collect_index(
        IndexFixtureClient(pages),
        operation="name",
        initial_url=first_url,
        parameters={"term": "SMITH"},
        cursor=partial.next_cursor,
    )
    assert [row["case_number"] for row in resumed.records] == [
        "620002",
        "620003",
    ]


def test_published_search_selector_encodings_are_preserved() -> None:
    parser = probate.build_parser()

    _, opened_parameters, opened_url = probate._index_spec(
        parser.parse_args(["opened", "01/04/2023"])
    )
    _, type_parameters, type_url = probate._index_spec(
        parser.parse_args(["type", "E", "--subtype", "01"])
    )
    _, number_parameters, number_url = probate._index_spec(
        parser.parse_args(["number", "617503"])
    )

    assert opened_parameters == {"open_date": "2023-01-04"}
    assert opened_url.endswith("?string=20230104")
    assert type_parameters == {"case_type": "E", "case_subtype": "01"}
    assert type_url.endswith("?string=E%2001")
    assert number_parameters == {"case_number": "617503", "case_suffix": None}
    assert number_url.endswith("?string=617503!=")


@pytest.mark.parametrize(
    ("route", "case_type", "expected"),
    [
        ("PBCaseTypeE.ndm/ESTATE_DETAIL", "ESTATE", "E"),
        ("PBCaseTypeC.ndm/CIVIL_DETAIL", "CIVIL", "C"),
        ("PBCaseTypeT.ndm/TRUST_DETAIL", "TRUST", "T"),
        ("PBCaseTypeG.ndm/GUARD_DETAIL", "GUARDIANSHIP ADULT", "GA"),
        ("PBCaseTypeG.ndm/GUARD_DETAIL", "GUARDIANSHIP MINOR", "GM"),
        ("PBCaseTypeM.ndm/MISC_DETAIL", "MISCELLANEOUS", "M"),
        ("PBCaseTypeSTG.ndm/input", "SENTINAL TRUST", "ST"),
    ],
)
def test_all_published_case_type_detail_routes_are_identified(
    route: str,
    case_type: str,
    expected: str,
) -> None:
    url = probate._detail_url(route, "617503;;")

    assert probate._type_code_from_detail_url(url, case_type) == expected


def test_case_detail_preserves_alias_amount_related_case_and_native_links() -> None:
    detail_url = probate._detail_url(
        "PBCaseTypeE.ndm/ESTATE_DETAIL",
        "617503;;",
    )
    detail = probate.parse_detail_page(
        fixture("case-detail.html"),
        source_url=detail_url,
    )

    assert detail is not None
    assert detail["case_number"] == "617503"
    assert detail["case_type_code"] == "E"
    assert detail["aka_raw"] == "THERESA E. LUPO; THERESA LUPO"
    assert detail["bond_amount_raw"] == "$25,000.00"
    assert detail["date_closed_raw"] == "Case is Open"
    assert detail["related_cases_raw"] == ["617503 A"]
    assert detail["fields"]["Decedent Street"] == "2895 12TH STREET NORTH"
    assert detail["links"][0]["href_raw"].startswith("http://")
    assert detail["links"][0]["url"].endswith("?caseno=617503;;")


def test_docket_parser_groups_wrapped_continuations_and_keeps_source_rows() -> None:
    records = probate.parse_docket_page(
        fixture("docket.html"),
        source_url=probate._detail_url("PBDocket.ndm/input", "617503;;"),
        case_number="617503",
    )

    assert len(records) == 3
    first, second, summary = records
    assert first["description"] == (
        "Application to Extend Time To File Objections To Magistrate's Findings"
    )
    assert len(first["source_rows"]) == 3
    assert first["cost_raw"] == ".00"
    assert second["description"] == "Entry Extending Time To File Objections"
    assert second["reference_raw"] == "06/08/2026"
    assert second["receipt_raw"] == "R-101"
    assert summary["record_kind"] == "probate_docket_summary"
    assert summary["description"] == "DEPOSIT REMAINING"
    assert summary["cost_raw"] == "170.21"


def test_fiduciary_rows_repair_fixed_width_detail_selectors_but_keep_raw_links() -> None:
    records = probate.parse_fiduciaries_page(
        fixture("fiduciaries.html"),
        source_url=probate._detail_url("PBFidy.ndm/input", "617503;;"),
        case_number="617503",
    )

    assert len(records) == 1
    record = records[0]
    assert record["fiduciary_number"] == "02"
    assert record["title_code"] == "10"
    assert record["attorney_number"] == "0002003"
    assert record["fiduciary_detail_href_raw"].endswith("caseno=61750302")
    assert record["fiduciary_detail_url"].endswith("caseno=617503;;02")
    assert record["attorney_detail_url"].endswith("caseno=617503;;02")


def test_fiduciary_and_attorney_detail_fields_remain_source_native() -> None:
    fiduciary = probate.parse_detail_page(
        fixture("fiduciary-detail.html"),
        source_url=probate._detail_url(
            "PBFidDetail.ndm/FID_DETAIL",
            "617503;;02",
        ),
        record_kind="probate_fiduciary_detail",
    )
    attorney = probate.parse_detail_page(
        fixture("attorney-detail.html"),
        source_url=probate._detail_url(
            "PBAttyDetail.ndm/ATTY_DETAIL",
            "617503;;02",
        ),
        record_kind="probate_attorney_detail",
    )

    assert fiduciary is not None
    assert fiduciary["fiduciary_name"] == "ARTZ, BRIAN S."
    assert fiduciary["fiduciary_title_code"] == "10"
    assert fiduciary["fields"]["Street"] == "560 E TOWN STREET"
    assert attorney is not None
    assert attorney["attorney_number"] == "0002003"
    assert attorney["fields"]["E-mail Address"] == "bartz@example.test"


def test_http_client_sends_literal_semicolon_case_selector() -> None:
    expected_url = probate._detail_url("PBDocket.ndm/input", "617503;;")
    session = MappingSession({expected_url: fixture("docket.html")})
    client = probate.FranklinProbateClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    records = client.docket("617503", "")

    assert records
    assert session.calls == [expected_url]
    assert session.calls[0].endswith("?caseno=617503;;")


def test_not_on_file_detail_is_authoritative_empty() -> None:
    html = "<html><body><script>document.write('617503 02...NOT On File')</script></body></html>"

    assert (
        probate.parse_detail_page(
            html,
            source_url=probate._detail_url(
                "PBFidDetail.ndm/FID_DETAIL",
                "61750302",
            ),
            record_kind="probate_fiduciary_detail",
        )
        is None
    )
