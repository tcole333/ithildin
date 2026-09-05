from __future__ import annotations

import argparse
from typing import Any

import pytest

from tools import query_new_mexico_case_lookup as nm
from tools.public_records_contract import ResultStatus


def _disclaimer_html() -> str:
    return f"""
    <html><head><title>Caselookup - Disclaimer</title></head><body>
      <p>{nm.DISCLAIMER_TEXT}</p>
      <form id="disclaimerForm"
            action="/caselookup/app;jsessionid=TESTSESSION123"
            method="post">
        <input type="hidden" name="component" value="disclaimerForm">
        <input type="hidden" name="session" value="T">
        <input type="submit" name="Submit" value="I Accept">
      </form>
    </body></html>
    """


def _name_search_html() -> str:
    result_options = "".join(
        f'<option value="{index}">{size}</option>'
        for index, size in enumerate((20, 10, 30, 40, 50))
    )
    return f"""
    <html><head><title>Caselookup - Name Search</title></head><body>
      <a href="/caselookup/app?component=dl2&amp;page=NameSearch&amp;service=direct"
         id="dl2">Case Number Search</a>
      <form id="nameSearchForm" action="/caselookup/app" method="post">
        <input type="hidden" name="component" value="nameSearchForm">
        <input type="hidden" name="session" value="T">
        <input type="hidden" name="csrfToken" value="transient-token">
        <input name="partyName" value="">
        <input name="driversLicense" value="">
        <select name="dlState"><option value="">- ALL STATES -</option>
          <option value="NM">NM</option></select>
        <input name="dob" value="">
        <input name="yearOnlyDob" value="">
        <select name="dol"></select>
        <input name="caseCategory" value="">
        <select name="results">{result_options}</select>
        <input type="submit" name="Submit" value="Name Search">
      </form>
    </body></html>
    """


def _case_search_html() -> str:
    return """
    <html><head><title>Caselookup - Case Number Search</title></head><body>
      <form id="caseNumberSearchForm" action="/caselookup/app" method="post">
        <input type="hidden" name="component" value="caseNumberSearchForm">
        <input type="hidden" name="session" value="T">
        <input type="hidden" name="csrfToken" value="case-token">
        <input name="courtType" value="">
        <input name="courtLocation" value="0">
        <input name="caseCategory" value="">
        <input name="caseNumber" value="0">
        <input type="submit" name="Submit" value="Case Number Search">
      </form>
    </body></html>
    """


def _search_results_html(*, total: int = 3, pages: int = 1) -> str:
    headers = "".join(f"<th>{header}</th>" for header in nm.SEARCH_HEADERS)
    rows = [
        (
            "D-101-CV-199602449",
            "EPSTEIN JEFFREY",
            "",
            "Defendant",
            "1",
            "OLIN PARTNERSHIP LTD V EPSTEIN",
            "Herrera, Steve",
            "SANTA FE DISTRICT",
            "10/17/1996",
        ),
        (
            "D-101-CV-199602449",
            "EPSTEIN JEFFREY",
            "",
            "Counter Plaintiff",
            "1",
            "OLIN PARTNERSHIP LTD V EPSTEIN",
            "Herrera, Steve",
            "SANTA FE DISTRICT",
            "10/17/1996",
        ),
        (
            "D-132-CV-308500230",
            "EPSTEIN JEFFREY",
            "",
            "Defendant",
            "8",
            "MARI-MAC G-VS-OHLSEN",
            "Garcia, Lorenzo F.",
            "LOS ALAMOS DISTRICT",
            "05/02/1985",
        ),
    ]
    body_rows = []
    for values in rows:
        first, *rest = values
        cells = [
            (
                '<td><a title="View detail." '
                'href="/caselookup/app?component=cnLink&amp;session=T'
                f'&amp;sp=S{first}">{first}</a></td>'
            ),
            *(f"<td>{value}</td>" for value in rest),
        ]
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    paginator = "".join(f"<a>{page}</a>" for page in range(1, pages + 1))
    return f"""
    <html><head><title>Caselookup - Search Results</title></head><body>
      <p class="total">{total} records retrieved</p>
      <span class="paginator"><b>1</b>{paginator}</span>
      <table id="cl"><tr>{headers}</tr>{''.join(body_rows)}</table>
      <p class="total">{total} records retrieved</p>
    </body></html>
    """


def _case_detail_html() -> str:
    register_rows = [
        (
            "03/09/1998",
            "CLS: STIPULATED DISMISSAL",
            "",
            "",
            "",
            "",
            "STIPULATION OF DISMISSAL",
        ),
        *[
            (
                f"10/{day:02d}/1996",
                f"EVENT {day}",
                "",
                "",
                "",
                "",
                f"DETAIL {day}",
            )
            for day in range(1, 14)
        ],
    ]
    register_html = "".join(
        (
            "<tr>"
            f"<td>{date}</td><td>{description}</td><td>{result}</td>"
            f"<td>{party_type}</td><td>{party_number}</td><td>{amount}</td>"
            "</tr>"
            f'<tr><td></td><td colspan="5">{detail}</td></tr>'
        )
        for (
            date,
            description,
            result,
            party_type,
            party_number,
            amount,
            detail,
        ) in register_rows
    )
    return f"""
    <html><head><title>Caselookup - Case Detail</title></head><body>
      <h2>OLIN PARTNERSHIP LTD V EPSTEIN</h2>
      <table class="details">
        <tr class="caption"><td colspan="4">Case Detail</td></tr>
        <tr><th>Case Number</th><th>Current Judge</th>
          <th>Filing Date</th><th>Court</th></tr>
        <tr><td>D-101-CV-199602449</td><td>Herrera, Steve</td>
          <td>10/17/1996</td><td>SANTA FE DISTRICT</td></tr>
      </table>
      <table class="details">
        <tr class="caption"><td colspan="4">Parties to this Case</td></tr>
        <tr><th>Party Type</th><th>Party Description</th>
          <th>Party #</th><th>Party Name</th></tr>
        <tr><td>CD</td><td>Counter Defendant</td><td>1</td>
          <td>OLIN PARTNERSHIP LTD</td></tr>
        <tr><td>CP</td><td>Counter Plaintiff</td><td>1</td>
          <td>EPSTEIN JEFFREY</td></tr>
        <tr><td></td><td>ATTORNEY: VADNAIS DOUGLAS R.</td></tr>
        <tr><td>D</td><td>Defendant</td><td>1</td>
          <td>EPSTEIN JEFFREY</td></tr>
        <tr><td></td><td>ATTORNEY: VADNAIS DOUGLAS R.</td></tr>
        <tr><td>P</td><td>Plaintiff</td><td>1</td>
          <td>OLIN PARTNERSHIP LTD</td></tr>
        <tr><td></td><td>ATTORNEY: VAN BUSKIRK TOM</td></tr>
      </table>
      <table class="details">
        <tr class="caption"><td colspan="5">Civil Complaint Detail</td></tr>
        <tr><th>Complaint Date</th><th>Complaint Seq #</th>
          <th>Complaint Description</th><th>Disposition</th>
          <th>Disposition Date</th></tr>
        <tr><td>10/17/1996</td><td>1</td><td>OPN: COMPLAINT</td>
          <td></td><td></td></tr>
        <tr><th>COA Sequence #</th><th>COA Description</th></tr>
        <tr><td>1</td><td>Breach of Contract</td></tr>
        <tr><th>Party Name</th><th>Party Type</th><th>Party #</th></tr>
        <tr><td>OLIN PARTNERSHIP LTD</td><td>P</td><td>1</td></tr>
        <tr><td>EPSTEIN JEFFREY</td><td>D</td><td>1</td></tr>
      </table>
      <table class="details">
        <tr class="caption"><td colspan="6">Register of Actions Activity</td></tr>
        <tr><th>Event Date</th><th>Event Description</th>
          <th>Event Result</th><th>Party Type</th>
          <th>Party #</th><th>Amount</th></tr>
        {register_html}
      </table>
      <table class="details">
        <tr class="caption"><td colspan="4">Judge Assignment History</td></tr>
        <tr><th>Assignment Date</th><th>Judge Name</th>
          <th>Sequence #</th><th>Assignment Event Description</th></tr>
        <tr><td>10/17/1996</td><td>Herrera, Steve</td><td>1</td>
          <td>INITIAL ASSIGNMENT</td></tr>
        <tr><td>11/16/1996</td><td>Awaiting, Assignment</td><td>2</td>
          <td>Judge Assignment Notice</td></tr>
        <tr><td>01/21/1997</td><td>Pfeffer, Stephen D.</td><td>3</td>
          <td>Assigned Before Automation</td></tr>
        <tr><td>06/11/1997</td><td>Herrera, Steve</td><td>4</td>
          <td>Transfer Assignment</td></tr>
      </table>
    </body></html>
    """


class FakeResponse:
    def __init__(self, text: str, *, url: str = nm.BASE_URL) -> None:
        self.text = text
        self.content = text.encode()
        self.url = url
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}


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


def _client(responses: list[FakeResponse]) -> nm.NewMexicoCaseLookupClient:
    return nm.NewMexicoCaseLookupClient(
        session=FakeSession(responses),
        minimum_interval=0,
        max_retries=0,
    )


def _args(*values: str) -> argparse.Namespace:
    return nm.build_parser().parse_args(list(values))


def test_successful_form_controls_omit_empty_dynamic_select() -> None:
    soup = nm.BeautifulSoup(_name_search_html(), "html.parser")
    values = nm._form_values(nm._form(soup, "nameSearchForm"))

    assert "dol" not in values
    assert values["results"] == "0"
    assert values["csrfToken"] == "transient-token"


def test_party_search_preserves_occurrences_without_session_locator() -> None:
    page = nm.parse_party_search_page(_search_results_html())

    assert page.total_records == 3
    assert len(page.records) == 3
    assert [record["matched_party"]["role"] for record in page.records[:2]] == [
        "Defendant",
        "Counter Plaintiff",
    ]
    assert page.records[0]["case_number"] == "D-101-CV-199602449"
    assert page.records[0]["court"]["court_id"] == "nm-case-lookup-d-101"
    assert page.records[0]["source_occurrence_id"] != (
        page.records[1]["source_occurrence_id"]
    )
    assert "locator" not in page.records[0]
    assert "session=T" not in str(page.records)


def test_exact_case_parser_preserves_children_and_does_not_infer_outcome() -> None:
    page = nm.parse_case_detail_page(
        _case_detail_html(),
        requested_case_number=nm.PROBE_CASE_NUMBER,
    )
    record = page.record

    assert record is not None
    assert record["case_number"] == nm.PROBE_CASE_NUMBER
    assert record["caption"] == "OLIN PARTNERSHIP LTD V EPSTEIN"
    assert len(record["parties"]) == 4
    assert record["parties"][1]["attorneys"] == [
        {
            "name": "VADNAIS DOUGLAS R.",
            "source_text": "ATTORNEY: VADNAIS DOUGLAS R.",
        }
    ]
    assert len(record["register_of_actions"]) == 14
    assert record["register_of_actions"][0]["detail_text"] == (
        "STIPULATION OF DISMISSAL"
    )
    assert len(record["judge_assignment_history"]) == 4
    assert record["cause_records"][0]["fields"]["coa_description"] == (
        "Breach of Contract"
    )
    assert record["disposition_records"] == []
    assert "status" not in record
    assert record["documents_available"] is False
    assert record["source_internal_case_locator"] is None
    assert page.schema_fingerprint is not None


def test_published_child_identities_survive_unrelated_insertions() -> None:
    original = nm.parse_case_detail_page(
        _case_detail_html(),
        requested_case_number=nm.PROBE_CASE_NUMBER,
    ).record
    inserted_html = _case_detail_html().replace(
        "<tr><td>CD</td><td>Counter Defendant</td><td>1</td>",
        (
            "<tr><td>I</td><td>Intervenor</td><td>7</td>"
            "<td>UNRELATED PARTY</td></tr>"
            "<tr><td>CD</td><td>Counter Defendant</td><td>1</td>"
        ),
    ).replace(
        (
            "<tr><td>10/17/1996</td><td>Herrera, Steve</td><td>1</td>"
            "<td>INITIAL ASSIGNMENT</td></tr>"
        ),
        (
            "<tr><td>01/01/1990</td><td>Earlier, Judge</td><td>0</td>"
            "<td>LEGACY ASSIGNMENT</td></tr>"
            "<tr><td>10/17/1996</td><td>Herrera, Steve</td><td>1</td>"
            "<td>INITIAL ASSIGNMENT</td></tr>"
        ),
    )
    inserted = nm.parse_case_detail_page(
        inserted_html,
        requested_case_number=nm.PROBE_CASE_NUMBER,
    ).record
    assert original is not None and inserted is not None

    original_parties = {
        (party["role_code"], party["party_number"], party["name"]): party[
            "canonical_ref"
        ]
        for party in original["parties"]
    }
    inserted_parties = {
        (party["role_code"], party["party_number"], party["name"]): party[
            "canonical_ref"
        ]
        for party in inserted["parties"]
        if party["name"] != "UNRELATED PARTY"
    }
    assert inserted_parties == original_parties

    original_judges = {
        (
            event["assignment_date_raw"],
            event["judge_name"],
            event["sequence_number"],
        ): event["assignment_event_id"]
        for event in original["judge_assignment_history"]
    }
    inserted_judges = {
        (
            event["assignment_date_raw"],
            event["judge_name"],
            event["sequence_number"],
        ): event["assignment_event_id"]
        for event in inserted["judge_assignment_history"]
        if event["judge_name"] != "Earlier, Judge"
    }
    assert inserted_judges == original_judges
    assert original["cause_records"][0]["source_child_id"] == (
        inserted["cause_records"][0]["source_child_id"]
    )


def test_exact_case_no_results_is_authoritative() -> None:
    page = nm.parse_case_detail_page(
        (
            "<html><head><title>Caselookup - Case Detail</title></head>"
            f"<body>{nm.NO_RESULTS_TEXT}</body></html>"
        ),
        requested_case_number="D-101-CV-999999999",
    )

    assert page.record is None
    assert page.authoritative_no_results is True


def test_exact_case_client_uses_four_requests_and_dynamic_routes() -> None:
    client = _client(
        [
            FakeResponse(_disclaimer_html()),
            FakeResponse(_name_search_html()),
            FakeResponse(_case_search_html()),
            FakeResponse(_case_detail_html()),
        ]
    )

    page = client.exact_case(nm.PROBE_CASE_NUMBER)

    assert page.record is not None
    assert client.request_count == nm.PROBE_EXPECTED_REQUESTS == 4
    session = client.session
    assert [request["method"] for request in session.requests] == [
        "GET",
        "POST",
        "GET",
        "POST",
    ]
    assert session.requests[1]["url"].endswith(
        "/caselookup/app;jsessionid=TESTSESSION123"
    )
    assert "component=dl2" in session.requests[2]["url"]
    exact_payload = session.requests[3]["data"]
    assert exact_payload["courtType"] == "D"
    assert exact_payload["courtLocation"] == "101"
    assert exact_payload["caseCategory"] == "CV"
    assert exact_payload["caseNumber"] == "199602449"


def test_source_route_accepts_only_opaque_tapestry_session_suffix() -> None:
    nm._validate_source_url(
        f"{nm.BASE_URL};jsessionid=ABC_123.test-4",
        label="test URL",
    )

    with pytest.raises(
        nm.NewMexicoCaseLookupSourceChanged,
        match="verified New Mexico Case Lookup route",
    ):
        nm._validate_source_url(
            f"{nm.BASE_URL};jsessionid=ABC/other",
            label="test URL",
        )


def test_party_search_is_one_native_page_and_partial_is_explicit() -> None:
    client = _client(
        [
            FakeResponse(_disclaimer_html()),
            FakeResponse(_name_search_html()),
            FakeResponse(_search_results_html(total=102, pages=6)),
        ]
    )

    result = nm.execute(
        _args("search", "Epstein"),
        client=client,
        log_results=False,
    )

    assert client.request_count == 3
    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert result.errors[0].code == (
        "additional_native_result_pages_not_traversed"
    )
    posted = client.session.requests[2]["data"]
    assert posted["partyName"] == "Epstein"
    assert "dol" not in posted


def test_request_budget_is_internal_and_source_command_needs_no_network() -> None:
    source = nm.execute(
        _args("source"),
        client=object(),
        log_results=False,
    )
    assert source.status == ResultStatus.OK
    assert source.records[0]["access"]["source_acquisition_grain"] == (
        "one_individual_electronic_case_record"
    )

    client = nm.NewMexicoCaseLookupClient(
        session=FakeSession([FakeResponse(_disclaimer_html())]),
        minimum_interval=0,
        max_retries=0,
        request_budget=1,
    )
    with pytest.raises(
        nm.NewMexicoCaseLookupSelectionError,
        match="budget",
    ):
        client.exact_case(nm.PROBE_CASE_NUMBER)
    assert client.request_count == 1
