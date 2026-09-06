from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from tools import query_deschutes_dial as dial
from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError, TransportError


FIXTURES = Path(__file__).parent / "fixtures" / "public_records" / "deschutes_dial"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


URLS = {
    "summary": f"{dial.BASE_URL}/Real/Index/135278",
    "valuation": f"{dial.BASE_URL}/Real/Valuation/135278",
    "tax": f"{dial.BASE_URL}/Real/TaxInformation/135278",
    "sales": f"{dial.BASE_URL}/Real/Sales/135278",
    "improvements": f"{dial.BASE_URL}/Real/Improvements/135278",
    "special_assessments": (f"{dial.BASE_URL}/Real/SpecialAssessments/135278"),
    "taxlot_history": f"{dial.BASE_URL}/Real/TaxLotHistory/135278",
    "related_accounts": f"{dial.BASE_URL}/Real/RelatedAccounts/135278",
    "warnings": f"{dial.BASE_URL}/Real/Warnings/135278",
    "service_providers": f"{dial.BASE_URL}/Real/ServiceProviders/135278",
    "development_summary": (f"{dial.BASE_URL}/Real/DevelopmentSummary/135278"),
    "permits": f"{dial.BASE_URL}/Real/Permits/135278",
    "development_documents": (f"{dial.BASE_URL}/Real/DevelopmentDocs/135278"),
    "tax_payment_store": (f"{dial.TAX_STORE_BASE_URL}/Taxes/home/account/135278"),
}


PARSER_FIXTURES = {
    "valuation": (dial.parse_valuation_page, "valuation.html"),
    "tax": (dial.parse_tax_page, "tax.html"),
    "sales": (dial.parse_sales_page, "sales.html"),
    "improvements": (dial.parse_improvements_page, "improvements.html"),
    "special_assessments": (
        dial.parse_special_assessments_page,
        "special_assessments.html",
    ),
    "taxlot_history": (
        dial.parse_taxlot_history_page,
        "taxlot_history.html",
    ),
    "related_accounts": (
        dial.parse_related_accounts_page,
        "related_accounts_empty.html",
    ),
    "warnings": (dial.parse_warnings_page, "warnings.html"),
    "service_providers": (
        dial.parse_service_providers_page,
        "service_providers.html",
    ),
    "development_summary": (
        dial.parse_development_summary_page,
        "development_summary.html",
    ),
    "permits": (dial.parse_permits_page, "permits.html"),
    "development_documents": (
        dial.parse_development_documents_page,
        "development_documents.html",
    ),
    "tax_payment_store": (
        dial.parse_tax_store_page,
        "tax_store.html",
    ),
}


class FixtureClient:
    def __init__(
        self,
        *,
        search_page: dial.SearchPage | None = None,
        failed_components: set[str] | None = None,
    ) -> None:
        self.summary = dial.parse_summary_page(
            fixture("summary.html"),
            URLS["summary"],
        )
        self.search_page = search_page or dial.SearchPage(
            rows=(),
            source_url=URLS["summary"],
            schema_fingerprint=str(self.summary["schema_fingerprint"]),
            direct_summary=self.summary,
        )
        self.failed_components = failed_components or set()
        self.calls: list[tuple[Any, ...]] = []

    def search(self, query: str, field: str) -> dial.SearchPage:
        self.calls.append(("search", query, field))
        return self.search_page

    def get_html(self, url: str) -> dial.HTMLPage:
        self.calls.append(("get_html", url))
        return dial.HTMLPage(fixture("summary.html"), URLS["summary"])

    def component(
        self,
        account_id: str,
        key: str,
    ) -> tuple[dict[str, Any], str]:
        self.calls.append(("component", account_id, key))
        if key in self.failed_components:
            raise TransportError(
                "fixture transport failure",
                url=URLS[key],
            )
        parser, filename = PARSER_FIXTURES[key]
        return dict(parser(fixture(filename), URLS[key])), URLS[key]

    def permit_detail(
        self,
        account_id: str,
        permit_id: str,
        permit_type: str,
    ) -> tuple[dict[str, Any], str]:
        self.calls.append(("permit_detail", account_id, permit_id, permit_type))
        source_url = (
            f"{dial.BASE_URL}/Real/PermitDetails/{account_id}"
            f"?permitID={permit_id}&permitType={permit_type}"
        )
        return (
            dict(
                dial.parse_permit_detail_page(
                    fixture("permit_detail.html"),
                    source_url,
                )
            ),
            source_url,
        )

    def direct_report(self, *args: Any, **kwargs: Any) -> dial.DownloadedPDF:
        self.calls.append(("direct_report", args, kwargs))
        return dial.DownloadedPDF(
            content=b"%PDF-1.7\nfixture\n%%EOF\n",
            source_url=f"{dial.BASE_URL}/API/Real/GetReport/135278",
            media_type="application/pdf",
            filename="report.pdf",
        )

    def custom_report(self, *args: Any, **kwargs: Any) -> dial.DownloadedPDF:
        self.calls.append(("custom_report", args, kwargs))
        return dial.DownloadedPDF(
            content=b"%PDF-1.4\ncustom fixture\n%%EOF\n",
            source_url=f"{dial.BASE_URL}/api/real/downloadreport/job-123",
            media_type="application/pdf",
            filename=None,
            job_id="job-123",
        )


def parse_args(*values: str):
    return dial.build_parser().parse_args(list(values))


def test_search_parser_maps_official_twenty_column_schema() -> None:
    page = dial.parse_search_page(
        fixture("search_results.html"),
        f"{dial.BASE_URL}/results/ownername?value=VACH&m=0",
    )

    assert len(page.rows) == 2
    first = page.rows[0]
    assert first["native_parcel_id"] == "141031B000700"
    assert first["native_account_id"] == "135278"
    assert first["owner_name"] == "VACH, MARIE FLORENCE"
    assert first["situs_address"]["postal_code"] == "97759"
    assert first["source_columns"]["lot"] == "89"
    assert first["detail_url"] == f"{dial.BASE_URL}/Real/Index/135278"
    assert first["canonical_ref"].startswith("PROPERTY:")

    second = page.rows[1]
    assert second["source_columns"]["agent_name"] == "REGISTERED AGENT"
    assert second["source_columns"]["direction"] == "N"
    assert second["source_columns"]["unit"] == "2"


def test_search_parser_distinguishes_authoritative_empty_from_drift() -> None:
    empty = dial.parse_search_page(
        fixture("no_results.html"),
        f"{dial.BASE_URL}/results/account?value=999999999999999",
    )
    assert empty.authoritative_empty is True
    assert empty.rows == ()

    with pytest.raises(SourceSchemaError):
        dial.parse_search_page(
            "<html><body><p>Temporarily unavailable</p></body></html>",
            f"{dial.BASE_URL}/results/account?value=135278",
        )


def test_search_cursor_is_query_snapshot_schema_and_anchor_bound() -> None:
    source_page = dial.parse_search_page(
        fixture("search_results.html"),
        f"{dial.BASE_URL}/results/ownername?value=VACH&m=0",
    )
    client = FixtureClient(search_page=source_page)
    first_args = parse_args(
        "search",
        "VACH",
        "--field",
        "owner",
        "--limit",
        "1",
    )
    first = dial.execute(first_args, client=client)

    assert first.status == ResultStatus.OK
    assert len(first.records) == 1
    assert first.next_cursor is not None
    assert first.records[0]["native_account_id"] == "135278"

    second_args = parse_args(
        "search",
        "VACH",
        "--field",
        "owner",
        "--limit",
        "1",
        "--cursor",
        first.next_cursor,
    )
    second = dial.execute(second_args, client=client)
    assert second.status == ResultStatus.OK
    assert second.records[0]["native_account_id"] == "200001"
    assert second.next_cursor is None

    changed_rows = [dict(record) for record in source_page.rows]
    changed_rows[1]["owner_name"] = "CHANGED OWNER"
    changed_client = FixtureClient(
        search_page=dial.SearchPage(
            rows=tuple(changed_rows),
            source_url=source_page.source_url,
            schema_fingerprint=source_page.schema_fingerprint,
        )
    )
    changed = dial.execute(second_args, client=changed_client)
    assert changed.status == ResultStatus.SOURCE_CHANGED
    assert changed.errors[0].code == "cursor_snapshot_changed"


def test_summary_parses_values_and_separates_document_retrieval_states() -> None:
    summary = dial.parse_summary_page(
        fixture("summary.html"),
        URLS["summary"],
    )

    assert summary["account_id"] == "135278"
    assert summary["map_taxlot"] == "141031B000700"
    assert summary["tax_year"] == "2025-2026"
    assert summary["assessment"] == {
        "land_value": 323710,
        "improvement_value": 460800,
        "parcel_value": 784510,
        "maximum_assessed_value": 293430,
        "assessed_value": 293430,
        "veterans_exemption": None,
    }
    documents = {
        document["document_kind"]: document for document in summary["documents"]
    }
    assert documents["ownership"]["retrieval_state"] == "link_available"
    assert documents["tax_map"]["artifact_format"] == "pdf"
    recorder = documents["recording_image_reference"]
    assert recorder["retrieval_state"] == "external_viewer_link"
    assert recorder["recording_year"] == "1972"
    assert recorder["recording_item_id"] == "19"


def test_valuation_tax_and_sales_normalize_source_history() -> None:
    valuation = dial.parse_valuation_page(
        fixture("valuation.html"),
        URLS["valuation"],
    )
    assert valuation["assessment_history"][-1] == {
        "tax_year": "2025-2026",
        "land_value": 323710,
        "improvement_value": 460800,
        "parcel_value": 784510,
        "maximum_assessed_value": 293430,
        "assessed_value": 293430,
        "veterans_exemption": None,
    }

    tax = dial.parse_tax_page(fixture("tax.html"), URLS["tax"])
    assert tax["tax_code_area"] == "6008"
    assert tax["original_tax_amounts"][-1] == {
        "tax_year": "2025",
        "original_tax_amount": 4615.32,
    }
    assert tax["payment_history"][0]["transaction_date"] == "2026-05-04"
    assert tax["payment_history"][0]["tax_due_delta"] == -1538.44
    assert tax["payment_history"][0]["refund_interest"] == 0
    assert len(tax["payment_history"]) == 2
    assert "certified property tax" in tax["statement_scope_note"]

    sales = dial.parse_sales_page(fixture("sales.html"), URLS["sales"])
    assert sales["sale_history"][0]["sale_date"] == "2018-09-17"
    assert sales["sale_history"][0]["consideration"] == 395000
    assert sales["sale_history"][0]["source_document_ref"] == "2018-38616"
    assert sales["sale_history"][1]["consideration"] is None


def test_land_related_development_and_permit_components() -> None:
    improvements = dial.parse_improvements_page(
        fixture("improvements.html"),
        URLS["improvements"],
    )
    assert improvements["structures"][0]["native_improvement_id"] == "150617"
    assert improvements["structures"][0]["square_feet"] == 2187
    assert improvements["land_characteristics"][0]["acres"] == 0.5

    related = dial.parse_related_accounts_page(
        fixture("related_accounts.html"),
        URLS["related_accounts"],
    )
    assert related["related_accounts"] == [
        {
            "account_id": "164828",
            "description": "Personal Property",
            "owner": "TOLLGATE PROP OWNERS ASSN",
            "source_url": f"{dial.BASE_URL}/Personal/Index/164828",
        }
    ]
    empty = dial.parse_related_accounts_page(
        fixture("related_accounts_empty.html"),
        URLS["related_accounts"],
    )
    assert empty["authoritative_empty"] is True
    assert empty["related_accounts"] == []

    development = dial.parse_development_summary_page(
        fixture("development_summary.html"),
        URLS["development_summary"],
    )
    assert development["zoning"][0]["zone"] == "RR10"
    assert (
        development["county_development_details"]["subdivision_has_special_setbacks"]
        == "YES"
    )
    assert development["documents"][0]["source_system"] == (
        "deschutes_digital_research_room"
    )

    permits = dial.parse_permits_page(
        fixture("permits.html"),
        URLS["permits"],
    )
    assert len(permits["permits"]) == 2
    assert permits["permits"][0]["application_date"] == "2016-02-01"
    assert permits["permits"][1]["status"] == "Expired"


def test_development_documents_are_stable_external_viewer_references() -> None:
    parsed = dial.parse_development_documents_page(
        fixture("development_documents.html"),
        URLS["development_documents"],
    )

    first = parsed["development_documents"][0]
    assert first["native_document_id"] == "1383062"
    assert first["date_uploaded"] == "2025-11-24"
    assert first["file_number"] == "247-16-000505-SEP"
    assert first["retrieval_state"] == "external_viewer_link"
    assert first["source_system"] == "deschutes_cdd_weblink"
    assert (
        first["canonical_ref"]
        == dial.parse_development_documents_page(
            fixture("development_documents.html"),
            URLS["development_documents"],
        )["development_documents"][0]["canonical_ref"]
    )


def test_tax_store_and_permit_detail_add_complementary_current_state() -> None:
    tax_store = dial.parse_tax_store_page(
        fixture("tax_store.html"),
        URLS["tax_payment_store"],
    )
    assert tax_store["account_id"] == "135278"
    assert tax_store["tax_balance_due"] == 0
    assert "no taxes due" in tax_store["account_notice"]

    detail_url = (
        f"{dial.BASE_URL}/Real/PermitDetails/135278"
        "?permitID=247-16-000505-SEP&permitType=Septic"
    )
    permit = dial.parse_permit_detail_page(
        fixture("permit_detail.html"),
        detail_url,
    )
    assert permit["permit_type"] == "Septic"
    assert permit["fields"]["application_date"] == "2016-02-01"
    assert permit["fields"]["special_instructions"] == (
        "Major repair; a maintenance agreement is required."
    )
    assert [item["date"] for item in permit["inspections"]] == [
        "2016-02-09",
        "2016-03-10",
    ]


def test_full_account_preserves_component_provenance_and_property_shape() -> None:
    args = parse_args("account", "135278")
    result = dial.execute(args, client=FixtureClient())

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["native_parcel_id"] == "141031B000700"
    assert record["native_account_id"] == "135278"
    assert record["snapshot_complete"] is True
    assert record["assessment"]["assessed_value"] == 293430
    assert record["last_sale"]["source_document_ref"] == "2018-38616"
    assert record["tax_state"]["current_balance_due"] == 0
    assert record["tax_state"]["payment_history"][0]["tax_due_delta"] == -1538.44
    assert record["improvements"][0]["native_improvement_id"] == "150617"
    assert record["permits"][0]["native_permit_id"] == "247-16-000505-SEP"
    assert len(record["development_documents"]) == 2
    assert set(record["dial_components"]) == set(dial.DEFAULT_COMPONENTS)
    assert list(record["component_coverage"]["failed"]) == []
    states = {document["retrieval_state"] for document in record["documents"]}
    assert states == {"link_available", "external_viewer_link"}


def test_component_failure_returns_partial_record_without_erasing_successes() -> None:
    args = parse_args(
        "account",
        "135278",
        "--components",
        "summary,tax,tax_payment_store",
    )
    client = FixtureClient(failed_components={"tax_payment_store"})
    result = dial.execute(args, client=client)

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 1
    record = result.records[0]
    assert record["snapshot_complete"] is False
    assert set(record["dial_components"]) == {"summary", "tax"}
    assert record["tax_state"]["payment_history"]
    assert record["tax_state"]["current_balance_due"] is None
    assert list(record["component_coverage"]["failed"]) == ["tax_payment_store"]
    assert result.errors[0].details["component"] == "tax_payment_store"


def test_access_decision_is_injected_and_stops_before_source_call() -> None:
    source_page = dial.parse_search_page(
        fixture("search_results.html"),
        f"{dial.BASE_URL}/results/ownername?value=VACH&m=0",
    )
    client = FixtureClient(search_page=source_page)
    args = parse_args("search", "VACH", "--field", "owner")
    decision = {
        "source_id": dial.SOURCE_ID,
        "allowed": False,
        "reason": "review needed",
        "reason_code": "access_review_expired",
    }

    result = dial.execute(args, client=client, access_decision=decision)

    assert result.status == ResultStatus.UNAVAILABLE
    assert client.calls == []
    metadata = result.query.query.metadata
    assert metadata["access_decision"]["reason_code"] == "access_review_expired"


def test_download_writes_verified_pdf_and_receipt(tmp_path: Path) -> None:
    destination = tmp_path / "ownership.pdf"
    args = parse_args(
        "download",
        "135278",
        "ownership",
        "--destination",
        str(destination),
    )
    result = dial.execute(args, client=FixtureClient())

    expected = b"%PDF-1.7\nfixture\n%%EOF\n"
    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == expected
    record = result.records[0]
    assert record["retrieval_state"] == "retrieved"
    assert record["sha256"] == hashlib.sha256(expected).hexdigest()
    assert record["size_bytes"] == len(expected)
    assert result.raw_artifact_refs == (str(destination.resolve()),)


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        status_code: int,
        content: bytes = b"",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        self.content = content
        self._payload = payload
        self.headers = headers or {}
        self.history: list[FakeResponse] = []
        self.text = content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


class NoWait:
    def wait(self) -> None:
        return None


def test_custom_report_uses_verified_job_then_download_flow() -> None:
    job_id = "8dcfda52-d708-4d2d-82f8-08296f718402"
    generate_url = f"{dial.BASE_URL}/api/real/GenerateReport"
    download_url = f"{dial.BASE_URL}/api/real/downloadreport/{job_id}"
    session = FakeSession(
        [
            FakeResponse(
                url=generate_url,
                status_code=200,
                payload={"Id": job_id, "IsComplete": False},
                headers={"Content-Type": "application/json"},
            ),
            FakeResponse(url=download_url, status_code=500),
            FakeResponse(url=download_url, status_code=404),
            FakeResponse(
                url=download_url,
                status_code=200,
                content=b"%PDF-1.4\nasync\n%%EOF\n",
                headers={"Content-Type": "application/pdf"},
            ),
        ]
    )
    sleeps: list[float] = []
    client = dial.DialClient(
        session=session,
        rate_limiter=NoWait(),
        sleeper=sleeps.append,
    )

    artifact = client.custom_report(
        "135278",
        "basic-report",
        poll_attempts=4,
        poll_interval=1.25,
    )

    assert artifact.job_id == job_id
    assert artifact.content.startswith(b"%PDF-")
    assert [call["method"] for call in session.calls] == [
        "POST",
        "GET",
        "GET",
        "GET",
    ]
    assert session.calls[0]["data"] == {
        "id": "135278",
        "SelectedItems": "basic",
    }
    assert sleeps == [1.25, 1.25]


def test_future_balance_uses_unscoped_verified_report_route() -> None:
    report_url = f"{dial.BASE_URL}/API/Real/GetReport"
    session = FakeSession(
        [
            FakeResponse(
                url=report_url,
                status_code=200,
                content=b"%PDF-1.4\nfuture\n%%EOF\n",
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    client = dial.DialClient(session=session, rate_limiter=NoWait())

    artifact = client.direct_report(
        "135278",
        "future-balance",
        as_of_date="08/01/2026",
    )

    assert artifact.content.startswith(b"%PDF-")
    assert session.calls[0]["url"] == report_url
    assert session.calls[0]["params"] == {
        "report": "TaxSummary",
        "type": "R",
        "id": "135278",
        "asOfDate": "08/01/2026",
    }


def test_sources_describes_distinct_arcgis_join_and_link_states() -> None:
    payload = dial.execute(parse_args("sources"))

    assert payload["source_id"] == dial.SOURCE_ID
    assert payload["identity"]["taxlot_join_key"] == "map_taxlot"
    assert payload["identity"]["arcgis_complement_source_id"] == (
        "us-or-deschutes-county-taxlots"
    )
    assert payload["search"]["columns"] == list(dial.SEARCH_COLUMNS)
    assert "external_viewer_link" in payload["reports"]["retrieval_states"]
