from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import requests

from tools import query_usvi_property_tax as usvi
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "usvi_property_tax"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def response(
    body: str,
    *,
    url: str = usvi.SEARCH_URL,
    content_type: str = "text/html; charset=utf-8",
    status: int = 200,
) -> requests.Response:
    item = requests.Response()
    item.status_code = status
    item.url = url
    item.headers["content-type"] = content_type
    item._content = body.encode("utf-8")
    item.encoding = "utf-8"
    return item


class FakeSession:
    def __init__(self, responses: list[requests.Response]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None,
        timeout: float,
        allow_redirects: bool,
    ) -> requests.Response:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "data": dict(data or {}),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def client_for(*items: requests.Response) -> tuple[usvi.CaptureCAMAClient, FakeSession]:
    session = FakeSession(list(items))
    client = usvi.CaptureCAMAClient(
        session=session,  # type: ignore[arg-type]
        minimum_interval=0,
        retry_policy=usvi.RetryPolicy(max_attempts=1),
    )
    return client, session


def test_search_contract_is_live_selector_driven() -> None:
    contract = usvi.parse_search_contract(fixture("landing.html"))

    assert contract.tax_years == ("2027", "2026", "2025")
    assert contract.selected_tax_year == "2026"
    assert contract.page_sizes == (10, 50, 200)
    assert contract.session_guid == "256616a8-0cc4-4e22-beeb-c4c66be5c207"


def test_search_row_preserves_published_fields_and_observation_identity() -> None:
    records, total, has_next, argument = usvi.parse_search_page(
        fixture("search_page_1.html")
    )
    first = records[0]

    assert total == 3
    assert has_next is True
    assert argument == "Page$Next"
    assert first["observation_identity"] == {
        "formatted_parcel_number": "1-09801-0101-00",
        "tax_year": "2026",
        "native_id": "1-09801-0101-00|tax-year:2026",
    }
    assert first["source_internal_parcel_id"] == "1614772"
    assert (
        first["source_internal_parcel_id_role"]
        == "tax_year_specific_detail_locator"
    )
    current = first["current_published_observation"]
    assert current["owner_name"] == "GSJVI LLC"
    assert current["land_value"] == "$17,000,000"
    assert current["improvement_value"] == "$500,000"
    assert current["assessed_value"] == "$17,500,000"
    assert current["legal_description"].startswith("LOT: A-1,A-2")
    assert first["recorded_title_evidence"] is False
    assert first["published_rows"]
    assert {
        item["label"] for item in first["published_fields"]
    } >= {
        "OWNER NAME",
        "MAIL ADDRESS",
        "PROP ADDRESS",
        "LEGAL",
        "LAND VALUE",
        "IMP VALUE",
        "TOTAL DUE",
    }


def test_no_results_is_authoritative_only_for_published_empty_state() -> None:
    records, total, has_next, argument = usvi.parse_search_page(
        fixture("no_results.html")
    )
    assert records == []
    assert total == 0
    assert has_next is False
    assert argument == ""

    changed = fixture("no_results.html").replace(
        "No Records Found", "Please Refine"
    )
    with pytest.raises(usvi.USVICAMASourceChanged):
        usvi.parse_search_page(changed)


def test_exhausts_native_pages_before_applying_explicit_window() -> None:
    client, session = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_2.html")),
    )
    result = usvi.run_search(
        client,
        field="legal",
        term="ST JAMES",
        tax_year="2026",
        limit=1,
        cursor=None,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 1
    assert result.next_cursor
    assert client.current_session_guid == (
        "256616a8-0cc4-4e22-beeb-c4c66be5c207"
    )
    assert len(session.calls) == 3
    assert session.calls[1]["data"]["__EVENTTARGET"] == ""
    assert session.calls[1]["data"]["Search"] == "Search"
    assert session.calls[1]["data"]["RecordsDDL"] == "200"
    assert session.calls[2]["data"]["__EVENTTARGET"] == "GridView1"
    assert session.calls[2]["data"]["__EVENTARGUMENT"] == "Page$Next"
    assert session.calls[2]["data"]["__LASTFOCUS"] == ""
    assert (
        result.query.query.parameters["window_applied_after_exhaustion"]
        is True
    )
    assert result.query.query.parameters["native_pages_fetched"] == 2


def test_omitted_limit_returns_all_rows_and_no_cursor() -> None:
    client, _session = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_2.html")),
    )
    result = usvi.run_search(
        client,
        field="legal",
        term="ST JAMES",
        tax_year="2026",
        limit=None,
        cursor=None,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert usvi.build_parser().parse_args(
        ["search", "legal", "ST JAMES"]
    ).limit is None


def test_cursor_is_bound_to_query_tax_year_and_published_total() -> None:
    first_client, _ = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_2.html")),
    )
    first = usvi.run_search(
        first_client,
        field="legal",
        term="ST JAMES",
        tax_year="2026",
        limit=1,
        cursor=None,
    )
    assert first.next_cursor

    second_client, _ = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_2.html")),
    )
    second = usvi.run_search(
        second_client,
        field="legal",
        term="ST JAMES",
        tax_year="2026",
        limit=1,
        cursor=first.next_cursor,
    )
    assert second.records[0]["formatted_parcel_number"] == "1-09801-0102-00"

    mismatch_client, _ = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_2.html")),
    )
    mismatch = usvi.run_search(
        mismatch_client,
        field="legal",
        term="GREAT JAMES",
        tax_year="2026",
        limit=1,
        cursor=first.next_cursor,
    )
    assert mismatch.status == ResultStatus.UNAVAILABLE
    assert mismatch.errors[0].code == "cursor_mismatch"


def test_pager_stall_fails_visibly_instead_of_claiming_exhaustion() -> None:
    client, _ = client_for(
        response(fixture("landing.html")),
        response(fixture("search_page_1.html")),
        response(fixture("search_page_1.html")),
    )
    result = usvi.run_search(
        client,
        field="legal",
        term="ST JAMES",
        tax_year="2026",
        limit=None,
        cursor=None,
    )
    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "usvi_cama_pagination_stalled"


def test_blank_search_is_a_structured_query_result() -> None:
    client, _ = client_for()
    result = usvi.run_search(
        client,
        field="owner",
        term="   ",
        tax_year="2026",
        limit=None,
        cursor=None,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "invalid_query"
    assert result.errors[0].category == "query"


def test_valuation_children_have_separate_identity_domains() -> None:
    parsed = usvi.parse_valuation_component(
        fixture("valuation.html"),
        parcel_number="1-09801-0101-00",
    )
    statement = parsed["statements"][0]
    valuation = parsed["valuation_history"][0]
    payment = parsed["payment_transactions"][0]

    assert statement["record_kind"] == "property_tax_statement"
    assert statement["statement_identity"]["statement_number"] == "24457395"
    assert statement["artifact_selectors"][0]["record_kind"] == (
        "property_tax_bill_print_view"
    )
    assert statement["artifact_selectors"][0]["session_guid_persisted"] is False
    assert valuation["record_kind"] == "assessment_valuation_history"
    assert valuation["recorded_title_evidence"] is False
    assert payment["record_kind"] == "property_tax_payment_transaction"
    assert payment["payment_identity"] == {
        "formatted_parcel_number": "1-09801-0101-00",
        "transaction_id": "1786629",
        "invoice_number": "24372908",
        "record_year": "2025",
    }
    assert payment["artifact_selectors"][0]["record_kind"] == (
        "property_tax_payment_receipt"
    )
    selector_url = usvi._selector_url(  # noqa: SLF001
        selector=statement["artifact_selectors"][0],
        session_guid="live-guid",
    )
    assert selector_url.startswith(
        "https://propertytax.vi.gov/CAMA/CAPortal/CZ_ReceiptPrint.aspx?"
    )
    refs = {
        statement["canonical_ref"],
        valuation["canonical_ref"],
        payment["canonical_ref"],
        statement["artifact_selectors"][0]["canonical_ref"],
        payment["artifact_selectors"][0]["canonical_ref"],
    }
    assert len(refs) == 5


def test_detail_shell_and_navigation_only_publish_sessionless_routes() -> None:
    frames = usvi._parse_detail_shell(  # noqa: SLF001
        fixture("detail_shell.html"),
        expected_parcel_id="1614772",
    )
    assert "ParcelId=1614772" in frames["Iframe1"]
    navigation = usvi._parse_navigation(  # noqa: SLF001
        fixture("navigation.html"),
        parcel_number="1-09801-0101-00",
        tax_year="2026",
    )
    assert {
        "valuation",
        "land",
        "buildings",
        "sales",
        "photographs",
        "maps",
        "property_card",
    } <= set(navigation["component_routes"])


def test_artifact_validates_official_host_html_media_and_signature() -> None:
    client, _ = client_for(
        response(
            fixture("artifact.html"),
            url=(
                "https://propertytax.vi.gov/CAMA/CAPortal/Custom/"
                "CZ_ReceiptPrint54.aspx"
            ),
        )
    )
    item = client.fetch_print_artifact(
        "https://propertytax.vi.gov/CAMA/CAPortal/CZ_ReceiptPrint.aspx"
    )
    assert item.content.startswith(b"<!doctype html>")

    bad_host, _ = client_for(
        response(
            fixture("artifact.html"),
            url="https://example.com/receipt.html",
        )
    )
    with pytest.raises(usvi.USVICAMASourceChanged, match="official host"):
        bad_host.fetch_print_artifact(
            "https://propertytax.vi.gov/CAMA/CAPortal/CZ_ReceiptPrint.aspx"
        )

    bad_media, _ = client_for(
        response(
            "%PDF-1.7",
            content_type="application/pdf",
            url=(
                "https://propertytax.vi.gov/CAMA/CAPortal/Custom/"
                "CZ_ReceiptPrint54.aspx"
            ),
        )
    )
    with pytest.raises(
        usvi.USVICAMASourceChanged, match="changed media type"
    ):
        bad_media.fetch_print_artifact(
            "https://propertytax.vi.gov/CAMA/CAPortal/CZ_ReceiptPrint.aspx"
        )


def test_artifact_refuses_existing_destination_without_overwrite(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "existing.html"
    destination.write_text("keep me", encoding="utf-8")
    client, session = client_for()

    with pytest.raises(usvi.USVICAMAError, match="already exists") as caught:
        usvi.fetch_artifact(
            client,
            parcel_number="1-09801-0101-00",
            tax_year="2026",
            kind="bill",
            statement="24457395",
            transaction_id=None,
            destination=destination,
        )
    assert caught.value.code == "destination_exists"
    assert destination.read_text(encoding="utf-8") == "keep me"
    assert session.calls == []
    parsed = usvi.build_parser().parse_args(
        [
            "artifact",
            "1-09801-0101-00",
            "--kind",
            "bill",
            "--statement",
            "24457395",
            "--destination",
            str(destination),
            "--overwrite",
        ]
    )
    assert parsed.overwrite is True


def test_caller_owned_session_is_preserved_and_internal_session_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caller = FakeSession([])
    client = usvi.CaptureCAMAClient(
        session=caller,  # type: ignore[arg-type]
        minimum_interval=0,
    )
    client.close()
    assert caller.closed is False

    owned = FakeSession([])
    monkeypatch.setattr(usvi, "system_trust_session", lambda: owned)
    internal = usvi.CaptureCAMAClient(minimum_interval=0)
    internal.close()
    assert owned.closed is True


def test_source_metadata_marks_alias_as_failover_not_corroboration() -> None:
    source = usvi.source_record()
    metadata = source["source"]["metadata"]
    assert metadata["alternate_tenant_host"] == usvi.FAILOVER_HOST
    assert metadata["alternate_tenant_role"] == (
        "same_source_failover_not_corroboration"
    )
    assert source["source"]["source_role"].startswith("territory_parcel")
    assert usvi.OBSERVED_AT == "2026-07-30"
