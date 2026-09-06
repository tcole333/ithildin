from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.public_records_http import (
    RestrictedHTTPError,
    RetryPolicy,
    SourceSchemaError,
)
from tools.query_tax_court import (
    API_ROOT,
    CASE_RESULT_CEILING,
    DOCUMENT_SEARCH_RESULT_CEILING,
    TODAYS_OPINIONS_RESULT_CEILING,
    TaxCourtClient,
    TaxCourtDownload,
    TaxCourtNotFoundError,
    TaxCourtQueryError,
    build_parser,
    canonical_docket_number,
    execute,
    normalize_todays_orders_sort,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "tax_court"
)


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class FakeResponse:
    def __init__(
        self,
        payload: Any = None,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        content: bytes | None = None,
        text: str | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = content if content is not None else b""
        if text is not None:
            self.text = text
        elif payload is not None:
            self.text = json.dumps(payload)
        else:
            self.text = self.content.decode(errors="replace")

    def json(self) -> Any:
        if isinstance(self.payload, BaseException):
            raise self.payload
        return self.payload


class QueueSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        json: dict[str, Any] | None,
        headers: dict[str, str],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)


def client_for(*responses: FakeResponse, **kwargs: Any) -> TaxCourtClient:
    return TaxCourtClient(
        session=QueueSession(*responses),
        minimum_interval=0,
        sleeper=lambda _: None,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("455-22", "455-22"),
        ("455-22S", "455-22"),
        ("123-20SL", "123-20"),
        ("27904-15W", "27904-15"),
        ("custom-docket", "CUSTOM-DOCKET"),
    ],
)
def test_canonical_docket_number(raw: str, expected: str) -> None:
    assert canonical_docket_number(raw) == expected


def test_case_search_preserves_native_records_and_filters() -> None:
    session = QueueSession(
        FakeResponse(fixture("case_search_hagee.json")),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.search_cases(
        "Hagee",
        country_type="domestic",
        petitioner_state="TX",
        filed_after="2014-01-01",
        filed_before="2026-07-29",
        case_types=["Deficiency", "CDP (Lien/Levy)"],
        procedure_type="Small",
        limit=1,
    )

    assert result["records"][0]["docketNumberWithSuffix"] == "9072-14S"
    assert result["metadata"]["source_returned_count"] == 2
    assert result["metadata"]["returned_count"] == 1
    assert result["metadata"]["truncated_by_caller"] is True
    assert result["metadata"]["source_result_ceiling"] == CASE_RESULT_CEILING
    assert result["metadata"]["schema_fingerprint"]
    assert result["metadata"]["evidence_refs"] == [
        "TAXCOURT:9072-14",
    ]
    assert session.calls[0]["params"] == {
        "petitionerName": "Hagee",
        "countryType": "domestic",
        "petitionerState": "TX",
        "startDate": "01/01/2014",
        "endDate": "07/29/2026",
        "procedureType": "Small",
        "caseTypes[]": ["Deficiency", "CDP (Lien/Levy)"],
    }


def test_case_search_allows_date_only_enumeration() -> None:
    session = QueueSession(
        FakeResponse(fixture("case_search_hagee.json")),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.search_cases(
        filed_after="2026-07-28",
        filed_before="2026-07-28",
    )

    assert result["metadata"]["source_returned_count"] == 2
    assert session.calls[0]["params"] == {
        "startDate": "07/28/2026",
        "endDate": "07/28/2026",
    }


def test_case_search_rejects_invalid_limit_before_request() -> None:
    session = QueueSession(FakeResponse({}))
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    with pytest.raises(TaxCourtQueryError, match="5,000"):
        client.search_cases(limit=5001)

    assert session.calls == []


def test_case_detail_keeps_party_and_practitioner_metadata() -> None:
    client = client_for(FakeResponse(fixture("case_455-22S.json")))
    result = client.get_case("455-22S")

    assert result["resource"]["docketNumber"] == "455-22"
    assert result["metadata"]["case_record_url"] == (
        "https://dawson.ustaxcourt.gov/case-detail/455-22"
    )
    assert result["metadata"]["evidence_ref"] == "TAXCOURT:455-22"
    assert result["resource"]["petitioners"][1]["name"] == (
        "Letitia Hagee-Tucker"
    )
    assert result["resource"]["privatePractitioners"][0]["name"] == (
        "Marco A. Ramos"
    )
    assert result["resource"]["docketEntries"] == []


def test_docket_fixture_preserves_attachment_without_inventing_access() -> None:
    client = client_for(
        FakeResponse(fixture("docket_455-22S_page0.json"))
    )
    result = client.docket_entries("455-22S")

    assert result["metadata"]["native_page_size"] == 1000
    assert result["metadata"]["native_total_count"] == 12
    assert result["metadata"]["complete"] is True
    petition = next(
        record
        for record in result["records"]
        if record["eventCode"] == "P"
    )
    assert petition["isFileAttached"] is True
    assert "publicDownloadAvailable" not in petition


def test_docket_fetches_source_native_pages_until_reported_total() -> None:
    page_zero = {
        "docketEntries": [
            {"docketEntryId": "a"},
            {"docketEntryId": "b"},
        ],
        "page": 0,
        "pageSize": 2,
        "totalCount": 3,
    }
    page_one = {
        "docketEntries": [{"docketEntryId": "c"}],
        "page": 1,
        "pageSize": 2,
        "totalCount": 3,
    }
    session = QueueSession(FakeResponse(page_zero), FakeResponse(page_one))
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.docket_entries("1-26")

    assert [record["docketEntryId"] for record in result["records"]] == [
        "a",
        "b",
        "c",
    ]
    assert [call["params"]["page"] for call in session.calls] == [0, 1]
    assert result["metadata"]["complete"] is True


def test_docket_explicit_page_does_not_fan_out() -> None:
    payload = {
        "docketEntries": [{"docketEntryId": "later"}],
        "page": 3,
        "pageSize": 1000,
        "totalCount": 4000,
    }
    session = QueueSession(FakeResponse(payload))
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.docket_entries("1-26", page=3)

    assert result["metadata"]["returned_count"] == 1
    assert result["metadata"]["complete"] is False
    assert session.calls[0]["params"] == {"page": 3}


def test_docket_rejects_page_beyond_source_ceiling() -> None:
    with pytest.raises(TaxCourtQueryError, match="0 through 20"):
        client_for().docket_entries("1-26", page=21)


def test_order_search_uses_source_limit_and_suffixless_docket() -> None:
    session = QueueSession(
        FakeResponse(fixture("order_search_455-22.json")),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.search_orders(docket_number="455-22S", limit=2)

    assert result["metadata"]["returned_count"] == 2
    assert result["metadata"]["requested_limit_reached"] is True
    assert result["metadata"]["source_result_ceiling"] == (
        DOCUMENT_SEARCH_RESULT_CEILING
    )
    assert session.calls[0]["params"] == {
        "dateRange": "allDates",
        "limit": 2,
        "docketNumber": "455-22",
    }


def test_opinion_search_maps_labels_and_preserves_native_codes() -> None:
    session = QueueSession(
        FakeResponse(fixture("opinion_search_innocent_spouse.json")),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.search_opinions(
        keyword='"innocent spouse"',
        filed_after="2026-01-01",
        opinion_types=["summary", "TCOP"],
        limit=2,
    )

    assert [record["eventCode"] for record in result["records"]] == [
        "SOP",
        "TCOP",
    ]
    assert session.calls[0]["params"]["opinionTypes"] == "SOP,TCOP"
    assert session.calls[0]["params"]["dateRange"] == "customDates"
    assert session.calls[0]["params"]["startDate"] == "01/01/2026"


def test_document_search_allows_native_all_dates_enumeration() -> None:
    client = client_for(FakeResponse({"results": [], "total": 0}))

    result = client.search_orders(limit=1)

    assert result["query"] == {"dateRange": "allDates", "limit": 1}


def test_document_search_requires_start_date_with_end_date() -> None:
    with pytest.raises(TaxCourtQueryError, match="requires a start date"):
        client_for().search_opinions(filed_before="2026-01-01")


def test_document_search_exposes_real_source_ceiling() -> None:
    with pytest.raises(TaxCourtQueryError, match="5,000"):
        client_for().search_orders(keyword="tax", limit=5001)


def test_today_orders_follows_one_based_native_pagination() -> None:
    page_one_records = [
        {"docketEntryId": f"entry-{index}"}
        for index in range(100)
    ]
    page_two_records = [{"docketEntryId": "entry-100"}]
    session = QueueSession(
        FakeResponse({"results": page_one_records, "totalCount": 101}),
        FakeResponse({"results": page_two_records, "totalCount": 101}),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    result = client.todays_orders()

    assert result["metadata"]["returned_count"] == 101
    assert result["metadata"]["native_page_size"] == 100
    assert result["metadata"]["complete"] is True
    assert session.calls[0]["url"].endswith(
        "/todays-orders/1/FILING_DATE_DESC"
    )
    assert session.calls[1]["url"].endswith(
        "/todays-orders/2/FILING_DATE_DESC"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("filing-date-asc", "FILING_DATE_ASC"),
        ("filing-date-desc", "FILING_DATE_DESC"),
        ("page-count-asc", "NUMBER_OF_PAGES_ASC"),
        ("NUMBER_OF_PAGES_DESC", "NUMBER_OF_PAGES_DESC"),
        ("filingDate|desc", "FILING_DATE_DESC"),
    ],
)
def test_today_orders_uses_deployed_native_sort_tokens(
    value: str,
    expected: str,
) -> None:
    assert normalize_todays_orders_sort(value) == expected


def test_today_orders_rejects_unknown_sort_instead_of_source_fallback() -> None:
    with pytest.raises(TaxCourtQueryError, match="sort must be"):
        normalize_todays_orders_sort("judge|asc")


def test_today_orders_rejects_zero_page() -> None:
    with pytest.raises(TaxCourtQueryError, match="one-based"):
        client_for(FakeResponse({})).todays_orders(page=0)


def test_today_opinions_accepts_native_array() -> None:
    records = fixture("opinion_search_innocent_spouse.json")["results"]
    result = client_for(FakeResponse(records)).todays_opinions()
    assert result["metadata"]["returned_count"] == 2
    assert (
        result["metadata"]["source_result_ceiling"]
        == TODAYS_OPINIONS_RESULT_CEILING
    )
    assert result["metadata"]["source_ceiling_reached"] is False
    assert result["records"][1]["docketNumberWithSuffix"] == "27904-15W"


def test_judges_and_trial_session_preserve_complementary_metadata() -> None:
    judges = [
        {
            "entityName": "PublicUser",
            "name": "Leyden",
            "role": "specialTrialJudge",
            "judgeFullName": "Diana L. Leyden",
            "judgeTitle": "Special Trial Judge",
        }
    ]
    judge_result = client_for(FakeResponse(judges)).judges()
    session_result = client_for(
        FakeResponse(fixture("trial_session_detail.json"))
    ).trial_session("281ad5a0-5b57-4446-bc72-1f9cd41aca37")

    assert judge_result["records"][0]["judgeFullName"] == "Diana L. Leyden"
    assert session_result["metadata"]["calendared_case_count"] == 2
    assert session_result["resource"]["calendaredCases"][0][
        "docketNumber"
    ] == "10764-25"


def test_public_document_download_validates_pdf_and_expiry() -> None:
    signed_url = (
        "https://documents.example/order?"
        "X-Amz-Date=20260729T054941Z&X-Amz-Expires=120"
    )
    session = QueueSession(
        FakeResponse({"url": signed_url}),
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.7\nfixture",
        ),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    download = client.download_document(
        "455-22S",
        "8fbd790c-3af0-43fb-9059-9754310faa24",
    )

    assert download.content.startswith(b"%PDF-")
    assert download.signed_url_issued_at == "20260729T054941Z"
    assert download.signed_url_expires_seconds == 120
    assert session.calls[0]["url"].startswith(
        f"{API_ROOT}/public-api/455-22/"
    )


def test_private_attachment_403_is_preserved_as_restricted() -> None:
    session = QueueSession(
        FakeResponse(
            status_code=403,
            text="Unauthorized to access private document",
        )
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    with pytest.raises(RestrictedHTTPError):
        client.download_document(
            "455-22",
            "f52c862f-905a-47db-9cab-0b111185eaa4",
        )


def test_download_rejects_non_pdf_response() -> None:
    session = QueueSession(
        FakeResponse({"url": "https://documents.example/not-a-pdf"}),
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"<html>not a pdf</html>",
        ),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _: None,
    )

    with pytest.raises(SourceSchemaError, match="not a PDF"):
        client.download_document("455-22", "entry-id")


def test_printable_docket_job_polls_and_uses_suffixless_identifier() -> None:
    signed_url = (
        "https://documents.example/docket?"
        "X-Amz-Date=20260729T055707Z&X-Amz-Expires=120"
    )
    session = QueueSession(
        FakeResponse({"jobId": "job-123"}),
        FakeResponse({"status": "pending"}),
        FakeResponse({"status": "ready", "url": signed_url}),
        FakeResponse(
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=b"%PDF-1.7\nprintable docket",
        ),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        clock=lambda: 0.0,
        sleeper=lambda _: None,
    )

    download = client.generate_docket_pdf(
        "455-22S",
        poll_interval=0,
        poll_timeout=10,
    )

    assert download.job_id == "job-123"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["json"]["docketNumber"] == "455-22"
    assert session.calls[0]["url"].endswith(
        "/cases/455-22/generate-docket-record"
    )


def test_printable_docket_job_surfaces_source_not_found() -> None:
    session = QueueSession(
        FakeResponse({"jobId": "job-404"}),
        FakeResponse(
            {
                "status": "error",
                "statusCode": 404,
                "message": "Cases 455-22S not found",
            }
        ),
    )
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        clock=lambda: 0.0,
        sleeper=lambda _: None,
    )

    with pytest.raises(TaxCourtNotFoundError, match="not found"):
        client.generate_docket_pdf("455-22", poll_interval=0)


def test_transient_status_is_retried_with_bounded_policy() -> None:
    session = QueueSession(
        FakeResponse(status_code=503, text="deploying"),
        FakeResponse(
            {
                "cognito": True,
                "elasticsearch": True,
                "emailService": True,
                "s3": {},
            }
        ),
    )
    sleeps: list[float] = []
    client = TaxCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0.1,
            max_backoff=0.1,
        ),
        sleeper=sleeps.append,
    )

    result = client.health()

    assert result["resource"]["elasticsearch"] is True
    assert len(session.calls) == 2
    assert sleeps == [0.1]


def test_parser_accepts_output_after_subcommand_and_execute_skips_log() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "cases",
            "Hagee",
            "--limit",
            "1",
            "--output",
            "/tmp/tax-court.json",
        ]
    )
    client = client_for(
        FakeResponse(fixture("case_search_hagee.json"))
    )

    result = execute(args, client=client, log_results=False)

    assert args.output == "/tmp/tax-court.json"
    assert result["metadata"]["returned_count"] == 1


class _ExecuteDownloadClient:
    def download_document(self, _docket: str, _entry: str) -> TaxCourtDownload:
        return TaxCourtDownload(
            content=b"%PDF-1.7\norder",
            public_request_url="https://example.test/public-order",
            signed_url_issued_at="20260729T054941Z",
            signed_url_expires_seconds=120,
        )

    def generate_docket_pdf(self, _docket: str, **_kwargs) -> TaxCourtDownload:
        return TaxCourtDownload(
            content=b"%PDF-1.7\ndocket",
            public_request_url="https://example.test/docket-record",
            signed_url_issued_at="20260729T055707Z",
            signed_url_expires_seconds=120,
            job_id="job-123",
        )


def test_execute_download_receipts_keep_common_provenance(
    tmp_path: Path,
) -> None:
    parser = build_parser()
    order_args = parser.parse_args(
        [
            "download",
            "455-22S",
            "entry-123",
            str(tmp_path / "order.pdf"),
        ]
    )
    docket_args = parser.parse_args(
        [
            "docket-pdf",
            "455-22S",
            str(tmp_path / "docket.pdf"),
        ]
    )

    order = execute(
        order_args,
        client=_ExecuteDownloadClient(),
        log_results=False,
    )
    docket = execute(
        docket_args,
        client=_ExecuteDownloadClient(),
        log_results=False,
    )

    assert order["source"]["source_id"] == "us-tax-court-dawson"
    assert order["command"] == "download"
    assert order["query"] == {
        "docket_number": "455-22",
        "docket_entry_id": "entry-123",
    }
    assert order["evidence_ref"] == "TAXCOURT:455-22:entry-123"
    assert order["sha256"]
    assert order["warnings"] == []
    assert docket["command"] == "docket-pdf"
    assert docket["query"]["docket_number"] == "455-22"
    assert docket["evidence_ref"] == "TAXCOURT:455-22"
    assert docket["job_id"] == "job-123"


def test_fixture_files_are_valid_json() -> None:
    names = {
        "case_search_hagee.json",
        "case_455-22S.json",
        "docket_455-22S_page0.json",
        "order_search_455-22.json",
        "opinion_search_innocent_spouse.json",
        "trial_session_detail.json",
    }
    assert {path.name for path in FIXTURES.glob("*.json")} == names
    for name in names:
        assert fixture(name) is not None
