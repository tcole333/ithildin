from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlencode

import pytest

import tools.query_eugene_municipal_court as eugene
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURES = (
    Path(__file__).parent / "fixtures" / "public_records" / "eugene_municipal_court"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def page(name: str, url: str) -> eugene.FetchedHTML:
    text = fixture(name)
    return eugene.FetchedHTML(
        url=url,
        text=text,
        status_code=200,
        content_type="text/html; charset=utf-8",
        sha256=eugene.hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        url: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(
        self,
        responses: dict[str, str | FakeResponse | list[FakeResponse]],
    ) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        params=None,
        headers=None,
        timeout=None,
        allow_redirects=None,
    ) -> FakeResponse:
        del headers, timeout, allow_redirects
        full_url = url
        if params:
            full_url = f"{url}?{urlencode(params)}"
        self.calls.append(full_url)
        response = self.responses[url]
        if isinstance(response, list):
            selected = response.pop(0)
            return selected
        if isinstance(response, FakeResponse):
            return response
        return FakeResponse(response, url=full_url)

    def close(self) -> None:
        return None


def make_client(session: FakeSession) -> eugene.EugeneMunicipalCourtClient:
    return eugene.EugeneMunicipalCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_eugene_form_exposes_tenant_specific_selectors_not_warrant():
    soup = eugene.BeautifulSoup(fixture("cases_form.html"), "html.parser")

    options = eugene._search_options(soup, eugene.CASES_URL)

    assert options == {
        "Name": "Name",
        "CitationNumber": "Citation Number",
        "DocketNumber": "Docket Number",
        "CaseNumber": "PD Case Number",
        "VehiclePlate": "Vehicle Plate",
        "VIN": "VIN",
    }
    assert "WarrantNumber" not in options
    assert soup.select_one("[name='SearchByCriteria.WarrantNumber']") is not None


def test_case_search_preserves_stable_ids_links_raw_fields_and_provenance():
    request_parameters = {
        "SearchBy": "CitationNumber",
        "SearchByCriteria.CitationNumber": "E018359",
    }
    parsed = eugene.parse_case_search(
        page("case_search_results.html", eugene.CASE_SEARCH_URL),
        expected_search_by="CitationNumber",
        request_parameters=request_parameters,
    )

    assert len(parsed.records) == 2
    first = parsed.records[0]
    assert first["canonical_ref"] == (
        "STATECOURT:us-or-eugene-municipal-record-search/"
        "or-eugene-municipal-court/E018359-01/case"
    )
    assert first["raw_case_number"] == "E018359-01"
    assert first["docket_number"] == "2605632"
    assert first["defendant"] == {
        "full_name": "GREGORY ANDERSON",
        "first_name": "GREGORY",
        "last_name": "ANDERSON",
    }
    assert first["violation_date"] == "2026-07-06"
    assert first["status_date"] == "2026-08-13"
    assert first["detail_url"].startswith(
        "https://www.municipalrecordsearch.com/eugeneor/Cases/Detail?"
    )
    assert first["source_fields"]["data_attributes"]["data-sort-offense"] == (
        "FL TO RENEW VEH REG"
    )
    assert first["source_provenance"]["request_parameters"] == (request_parameters)
    assert len(first["source_provenance"]["source_snapshot"]["sha256"]) == 64
    assert parsed.records[1]["warrant"]["active"] is True


def test_case_search_authoritative_empty_and_unavailable_selector():
    parsed = eugene.parse_case_search(
        page("case_search_no_results.html", eugene.CASE_SEARCH_URL),
        expected_search_by="CitationNumber",
        request_parameters={
            "SearchBy": "CitationNumber",
            "SearchByCriteria.CitationNumber": "NONE",
        },
    )

    assert parsed.records == ()
    assert parsed.metadata["authoritative_no_results"] is True
    with pytest.raises(
        eugene.EugeneCourtSelectionError,
        match="does not expose",
    ):
        eugene.parse_case_search(
            page("case_search_no_results.html", eugene.CASE_SEARCH_URL),
            expected_search_by="WarrantNumber",
            request_parameters={
                "SearchBy": "WarrantNumber",
                "SearchByCriteria.WarrantNumber": "NONE",
            },
        )


def test_docket_index_and_snapshot_cursor_round_trip():
    parsed = eugene.parse_docket_index(page("dockets.html", eugene.DOCKETS_URL))

    assert len(parsed.records) == 3
    assert parsed.records[0]["native_session_id"] == ("20260729083000|TRAR|1")
    assert parsed.records[0]["date"] == "2026-07-29"
    assert parsed.records[0]["start_at"].startswith("2026-07-29T08:30:00-07:00")
    assert parsed.records[1]["judge"] == "JUDGE SAMPLE"
    assert parsed.records[2]["detail_url"].endswith(
        "date=20260730130000&calendarCode=VIRT&roomCode=9"
    )

    first, cursor = eugene._paginate(
        parsed.records,
        operation="dockets",
        parameters={"date_from": None, "date_to": None},
        limit=2,
        cursor_value=None,
    )
    second, next_cursor = eugene._paginate(
        parsed.records,
        operation="dockets",
        parameters={"date_from": None, "date_to": None},
        limit=2,
        cursor_value=cursor,
    )

    assert [record["native_session_id"] for record in first] == [
        "20260729083000|TRAR|1",
        "20260729110000|JAIL|3",
    ]
    assert [record["native_session_id"] for record in second] == [
        "20260730130000|VIRT|9"
    ]
    assert next_cursor is None


def test_cursor_rejects_changed_snapshot_and_other_query():
    parsed = eugene.parse_docket_index(page("dockets.html", eugene.DOCKETS_URL))
    _, cursor = eugene._paginate(
        parsed.records,
        operation="dockets",
        parameters={"date_from": None, "date_to": None},
        limit=1,
        cursor_value=None,
    )
    changed = [dict(record) for record in parsed.records]
    changed[1]["judge"] = "DIFFERENT"

    with pytest.raises(
        eugene.EugeneCourtSelectionError,
        match="changed since",
    ) as error:
        eugene._paginate(
            changed,
            operation="dockets",
            parameters={"date_from": None, "date_to": None},
            limit=1,
            cursor_value=cursor,
        )
    assert error.value.status == ResultStatus.SOURCE_CHANGED

    with pytest.raises(
        eugene.EugeneCourtSelectionError,
        match="another Eugene query",
    ):
        eugene._paginate(
            parsed.records,
            operation="dockets",
            parameters={
                "date_from": "2026-07-30",
                "date_to": None,
            },
            limit=1,
            cursor_value=cursor,
        )


def test_docket_detail_preserves_session_and_underlying_case_links():
    parsed = eugene.parse_docket_detail(
        page(
            "docket_detail.html",
            (
                f"{eugene.DOCKETS_URL}/Detail?"
                "date=20260729083000&calendarCode=TRAR&roomCode=1"
            ),
        ),
        native_date="20260729083000",
        calendar_code="TRAR",
        room_code="1",
    )

    record = parsed.record
    assert record["docket_name"] == "TRAFFIC ARRAIGNMENTS"
    assert record["time_raw"] == "7/29/2026 8:30-8:31am"
    assert record["judge"] == "JUDGE SAMPLE"
    assert record["courtroom"] == "COURTROOM 1"
    assert record["case_count"] == 2
    assert record["cases"][0]["case_ref"].endswith("/E018359-01/case")
    assert record["cases"][0]["canonical_ref"].endswith(
        "/E018359-01/calendar_case/20260729083000%7CTRAR%7C1"
    )
    assert record["cases"][1]["attorney"] == "COUNSEL EXAMPLE"
    assert "citationNumber=E018360" in record["cases"][1]["detail_url"]


def test_case_detail_preserves_sections_payment_document_and_json_routes():
    parsed = eugene.parse_case_detail(
        page(
            "case_detail.html",
            (
                f"{eugene.BASE_URL}Cases/Detail?"
                "citationNumber=E018359&violationNumber=01"
            ),
        ),
        citation_number="E018359",
        violation_number="01",
    )

    record = parsed.record
    assert record["raw_case_number"] == "E018359-01"
    assert record["caption"] == "GREGORY HARLAND ANDERSON"
    assert record["docket_number"] == "2605632"
    assert record["filed_date"] == "2026-07-06"
    assert record["police_case_number"] == "26-12345"
    assert record["fees"]["Unpaid Balance"] == "$216.00"
    assert record["document_available"] is True
    assert record["documents"][0]["url"].endswith("/ViolationDocuments/Download/abc123")
    assert record["payment_urls"] == [
        "https://www.municipalonlinepayments.com/eugeneor/court/"
        "search/api?citation=E018359"
    ]
    assert "ViolationPriors" in record["related_routes"]["priors"]
    assert "ViolationHistory" in record["related_routes"]["history"]
    assert "ViolationDocuments" in record["related_routes"]["documents"]
    assert record["document_request"]["municipal_court_form_url"] == (
        eugene.JUSTFOIA_MUNICIPAL_COURT_FORM_URL
    )


def test_reusable_tenant_directory_preserves_per_tenant_capabilities():
    parsed = eugene.parse_tenant_directory(
        page("tenant_directory.html", eugene.HOST_URL + "/")
    )

    assert parsed["tenant_count"] == 2
    assert parsed["case_search_tenant_count"] == 2
    assert parsed["docket_tenant_count"] == 2
    assert parsed["eugene"] == {
        "slug": "eugeneor",
        "name": "Eugene, OR",
        "tenant_url": "https://www.municipalrecordsearch.com/eugeneor/",
        "case_search": True,
        "upcoming_dockets": True,
    }
    assert [tenant["slug"] for tenant in parsed["tenants"]] == [
        "abilenetx",
        "eugeneor",
    ]


def test_client_retries_transient_response_once():
    session = FakeSession(
        {
            eugene.CASES_URL: [
                FakeResponse(
                    "temporary",
                    url=eugene.CASES_URL,
                    status_code=500,
                ),
                FakeResponse(
                    fixture("cases_form.html"),
                    url=eugene.CASES_URL,
                ),
            ]
        }
    )
    delays: list[float] = []
    client = eugene.EugeneMunicipalCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0.01,
        ),
        sleeper=delays.append,
    )

    fetched = client._get(eugene.CASES_URL)

    assert fetched.status_code == 200
    assert client.request_count == 2
    assert delays == [0.01]


def test_execute_search_returns_contract_and_cursor(monkeypatch):
    monkeypatch.setattr(eugene, "log_search", lambda *args, **kwargs: None)
    args = eugene.build_parser().parse_args(
        [
            "search",
            "--citation",
            "E018359",
            "--limit",
            "1",
        ]
    )
    session = FakeSession({eugene.CASE_SEARCH_URL: fixture("case_search_results.html")})

    result = eugene.execute(args, client=make_client(session))

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    assert result.next_cursor is not None
    assert result.query.query.parameters["search_by"] == "CitationNumber"
    assert result.raw_artifact_refs[0].startswith(eugene.CASE_SEARCH_URL + "?")

    continued = eugene.build_parser().parse_args(
        [
            "search",
            "--citation",
            "E018359",
            "--limit",
            "1",
            "--cursor",
            result.next_cursor,
        ]
    )
    next_result = eugene.execute(
        continued,
        client=make_client(
            FakeSession({eugene.CASE_SEARCH_URL: fixture("case_search_results.html")})
        ),
    )
    assert [record["raw_case_number"] for record in next_result.records] == [
        "E018360-02"
    ]
    assert next_result.next_cursor is None


def test_execute_empty_search_is_no_results(monkeypatch):
    monkeypatch.setattr(eugene, "log_search", lambda *args, **kwargs: None)
    args = eugene.build_parser().parse_args(["search", "--citation", "NONE"])
    result = eugene.execute(
        args,
        client=make_client(
            FakeSession(
                {eugene.CASE_SEARCH_URL: fixture("case_search_no_results.html")}
            )
        ),
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_missing_plate_state_is_structured_selection_failure(monkeypatch):
    monkeypatch.setattr(eugene, "log_search", lambda *args, **kwargs: None)
    args = eugene.build_parser().parse_args(["search", "--plate", "ABC123"])

    result = eugene.execute(args, client=object())

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "plate_state_required"


def test_discovery_reports_family_official_chain_and_request_complement():
    session = FakeSession(
        {
            eugene.HOST_URL + "/": fixture("tenant_directory.html"),
            eugene.BASE_URL: "<html><title>Home | Eugene</title></html>",
            eugene.CASES_URL: fixture("cases_form.html"),
            eugene.DOCKETS_URL: fixture("dockets.html"),
            eugene.OFFICIAL_COURT_URL: fixture("official.html"),
            eugene.JUSTFOIA_MUNICIPAL_COURT_FORM_URL: fixture("justfoia_form.html"),
        }
    )

    records, refs = make_client(session).discovery()

    primary, family, complement = records
    assert primary["official_links_verified"] == {
        "record_search_linked": True,
        "record_request_linked": True,
    }
    assert primary["capabilities"]["case_search"]["selectors"]["CaseNumber"] == (
        "PD Case Number"
    )
    assert primary["capabilities"]["case_search"]["warrant_selector_available"] is False
    assert primary["capabilities"]["direct_documents"]["state"] == ("not_observed")
    assert primary["capabilities"]["bulk_products"]["state"] == ("not_observed")
    assert family["tenant_count"] == 2
    assert family["tenants"][1]["name"] == "Eugene, OR"
    assert family["reusable_contract"]["case_search"] == ("/{tenant}/Cases/Search")
    assert complement["municipal_court_form_url"] == (
        eugene.JUSTFOIA_MUNICIPAL_COURT_FORM_URL
    )
    assert complement["distinct_from_case_index"] is True
    assert len(refs) == 6


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official Eugene probes",
)
def test_live_eugene_probe_search_and_dockets(monkeypatch):
    monkeypatch.setattr(eugene, "log_search", lambda *args, **kwargs: None)
    parser = eugene.build_parser()

    probe = eugene.execute(
        parser.parse_args(
            [
                "probe",
                "--minimum-interval",
                "0.4",
                "--max-attempts",
                "2",
            ]
        )
    )
    assert probe.status == ResultStatus.OK
    assert "CitationNumber" in probe.records[0]["available_search_options"]
    assert probe.records[0]["warrant_search_available"] is False

    search = eugene.execute(
        parser.parse_args(
            [
                "search",
                "--citation",
                "E018359",
                "--limit",
                "1",
                "--minimum-interval",
                "0.4",
                "--max-attempts",
                "2",
            ]
        )
    )
    assert search.status in {ResultStatus.OK, ResultStatus.NO_RESULTS}

    dockets = eugene.execute(
        parser.parse_args(
            [
                "dockets",
                "--limit",
                "1",
                "--minimum-interval",
                "0.4",
                "--max-attempts",
                "2",
            ]
        )
    )
    assert dockets.status == ResultStatus.OK
    assert dockets.records[0]["record_kind"] == "calendar_session"
