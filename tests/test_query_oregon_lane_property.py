from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from tools.public_records_contract import ResultStatus
from tools.query_oregon_lane_property import (
    ACCOUNT_ROOT_URL,
    ACCOUNT_SOURCE_ID,
    BinaryDocument,
    LaneCountyPropertyClient,
    TAX_MAP_SEARCH_URL,
    TAX_MAP_SOURCE_ID,
    TextPage,
    build_parser,
    execute,
    parse_account_detail,
    parse_account_search,
    parse_tax_map_search,
    parse_webforms_hidden_fields,
    sources_payload,
)


FIXTURES = Path(__file__).parent / "fixtures" / "public_records" / "oregon_lane_property"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text()


def _json(name: str) -> Any:
    return json.loads(_text(name))


class FakeLaneClient:
    def __init__(self, account_rows: list[dict[str, Any]] | None = None) -> None:
        self.account_rows = (
            account_rows
            if account_rows is not None
            else _json("account_search.json")
        )

    def account_search(self, field: str, value: str) -> tuple[Any, str]:
        assert field in {"account", "map_taxlot", "address", "name"}
        assert value
        return self.account_rows, (
            f"{ACCOUNT_ROOT_URL}api/{field}search/{value}"
        )

    def account_detail(self, account: str) -> TextPage:
        return TextPage(
            text=_text("account_detail.html"),
            source_url=f"{ACCOUNT_ROOT_URL}Account/{account}",
            headers={"content-type": "text/html"},
        )

    def tax_map_search(
        self,
        field: str,
        value: str,
        *,
        city: str | None = None,
    ) -> TextPage:
        assert value
        assert city is None or field == "address"
        fixture = (
            "tax_map_name_results.html"
            if field == "map_name"
            else "tax_map_location_results.html"
        )
        return TextPage(
            text=_text(fixture),
            source_url=TAX_MAP_SEARCH_URL,
            headers={"content-type": "text/html"},
        )

    def tax_map_document(self, document_id: str) -> BinaryDocument:
        content = b"%PDF-1.6\nfixture tax map\n%%EOF\n"
        return BinaryDocument(
            content=content,
            source_url=(
                "https://apps.lanecounty.org/TaxMap/"
                f"ViewFile.aspx?type=TM&id={document_id}"
            ),
            headers={"content-type": "application/pdf"},
        )


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str = "",
        content: bytes | None = None,
        content_type: str = "text/html; charset=utf-8",
        payload: Any | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.content = content if content is not None else text.encode()
        self.headers = {"Content-Type": content_type}
        self.status_code = 200
        self.history: list[FakeResponse] = []
        self._payload = payload
        self.closed = False

    def json(self) -> Any:
        return self._payload

    def close(self) -> None:
        self.closed = True


class RecordingSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def _account_rows(count: int = 3) -> list[dict[str, str]]:
    return [
        {
            "AccountNumber": f"{index:07d}",
            "MapTaxLot": f"160507000{index:04d}",
            "TaxPayer": f"TAXPAYER {index}",
            "Owner": f"OWNER {index}",
            "SitusAddress": f"{index} EXAMPLE RD EUGENE 97401",
        }
        for index in range(1, count + 1)
    ]


def test_sources_keep_account_map_document_and_recorder_roles_distinct() -> None:
    payload = sources_payload()
    assert {source["source_id"] for source in payload["sources"]} == {
        ACCOUNT_SOURCE_ID,
        TAX_MAP_SOURCE_ID,
    }
    relationships = {
        (row["left"], row["right"]): row
        for row in payload["source_relationships"]
    }
    assert relationships[(ACCOUNT_SOURCE_ID, TAX_MAP_SOURCE_ID)][
        "independent_corroboration"
    ] is False
    assert any(
        route.get("adds", "").startswith("official full tax-map")
        for route in payload["official_complements"]
    )


def test_webforms_contract_requires_current_state_fields() -> None:
    fields = parse_webforms_hidden_fields(
        _text("tax_map_landing.html"),
        TAX_MAP_SEARCH_URL,
    )
    assert fields == {
        "__VIEWSTATE": "fixture-viewstate",
        "__VIEWSTATEGENERATOR": "F7C34448",
        "__EVENTVALIDATION": "fixture-validation",
    }
    with pytest.raises(Exception, match="WebForms state changed"):
        parse_webforms_hidden_fields(
            "<form id='Form1'><input name='__VIEWSTATE' value='x'></form>",
            TAX_MAP_SEARCH_URL,
        )


def test_account_search_preserves_taxpayer_and_owner_index_as_distinct_labels() -> None:
    records = parse_account_search(
        _json("account_search.json"),
        f"{ACCOUNT_ROOT_URL}api/accountnumbersearch/0057313",
    )
    assert len(records) == 1
    record = records[0]
    assert record["account_number"] == "0057313"
    assert record["map_taxlot"] == "1605070001100"
    assert record["taxpayer_name"] == "NORTHWEST CLEARWOODS INC"
    assert record["owner_index_name"] == "NORTHWEST CLEARWOODS INC"
    assert record["record_kind"] == "property_account_search_index"
    assert record["canonical_ref"] != record["evidence_ref"]
    assert record["source_record_id"] != record["account_number"]
    assert record["source_account_id"] == record["account_number"]
    assert "title" not in record


def test_account_search_occurrences_do_not_collapse_same_account_owner_rows() -> None:
    rows = [
        {
            "AccountNumber": "0057313",
            "MapTaxLot": "1605070001100",
            "TaxPayer": "TAXPAYER LLC",
            "Owner": "OWNER ALPHA",
            "SitusAddress": "25745 HALL RD",
        },
        {
            "AccountNumber": "0057313",
            "MapTaxLot": "1605070001100",
            "TaxPayer": "TAXPAYER LLC",
            "Owner": "OWNER BETA",
            "SitusAddress": "25745 HALL RD",
        },
    ]
    records = parse_account_search(rows, f"{ACCOUNT_ROOT_URL}api/accountnumbersearch")
    assert records[0]["canonical_ref"] == records[1]["canonical_ref"]
    assert records[0]["evidence_ref"] != records[1]["evidence_ref"]
    assert records[0]["source_record_id"] != records[1]["source_record_id"]

    parser = build_parser()
    first = execute(
        parser.parse_args(
            [
                "search",
                "0057313",
                "--source",
                ACCOUNT_SOURCE_ID,
                "--field",
                "account",
                "--limit",
                "1",
            ]
        ),
        client=FakeLaneClient(rows),
        log_results=False,
    )
    second = execute(
        parser.parse_args(
            [
                "search",
                "0057313",
                "--source",
                ACCOUNT_SOURCE_ID,
                "--field",
                "account",
                "--limit",
                "1",
                "--cursor",
                str(first.next_cursor),
            ]
        ),
        client=FakeLaneClient(rows),
        log_results=False,
    )
    assert first.records[0]["owner_index_name"] == "OWNER ALPHA"
    assert second.records[0]["owner_index_name"] == "OWNER BETA"


def test_account_detail_normalizes_receipts_values_and_related_representations() -> None:
    search_record = parse_account_search(
        _json("account_search.json"),
        f"{ACCOUNT_ROOT_URL}api/accountnumbersearch/0057313",
    )[0]
    detail = parse_account_detail(
        _text("account_detail.html"),
        f"{ACCOUNT_ROOT_URL}Account/0057313",
        expected_account="0057313",
        search_record=search_record,
    )
    assert detail["account_number"] == "0057313"
    assert detail["map_taxlot"] == "1605070001100"
    assert detail["situs_address"] == (
        "25745 HALL RD\nJUNCTION CITY, OREGON 97448"
    )
    assert detail["mailing_address"] == "PO BOX 1415\nEUGENE, OREGON 97440"
    assert detail["property_class"] == "401"
    assert detail["property_class_description"] == "Tract Improved"
    assert detail["recent_receipts"][0] == {
        "date_raw": "12/11/2025",
        "date_iso": "2025-12-11",
        "amount_received_raw": "$3,645.81",
        "amount_received": "3645.81",
        "tax_raw": "$3,645.81",
        "tax": "3645.81",
        "discount_raw": "$0.00",
        "discount": "0.00",
        "interest_raw": "$0.00",
        "interest": "0.00",
    }
    assert detail["valuation_history"][1]["tax_year"] == 2025
    assert detail["valuation_history"][1]["assessed_value"] == "306229"
    assert detail["valuation_history"][1]["real_market_value"] == "552226"
    links = {
        row["representation_kind"]: row
        for row in detail["related_representations"]
    }
    assert links["tax_map_pdf"]["tax_map_document_id"] == "326"
    assert links["tax_map_pdf"]["related_source_id"] == TAX_MAP_SOURCE_ID
    assert links["current_tax_statement"]["url"].endswith(
        "/ViewCurrentStatement/0057313"
    )
    assert links["prior_tax_statement_series"]["url"].endswith(
        "/ViewStatement/0057313/2025"
    )
    assert detail["owner_index_name"] == "NORTHWEST CLEARWOODS INC"
    assert detail["owner_index_names"] == ["NORTHWEST CLEARWOODS INC"]
    assert detail["taxpayer_names"] == ["NORTHWEST CLEARWOODS INC"]
    assert len(detail["search_index_observations"]) == 1
    assert "title_owner" not in detail


def test_account_detail_preserves_all_matching_search_index_observations() -> None:
    rows = [
        {
            "AccountNumber": "0057313",
            "MapTaxLot": "1605070001100",
            "TaxPayer": "NORTHWEST CLEARWOODS INC",
            "Owner": owner,
            "SitusAddress": "25745 HALL RD",
        }
        for owner in ("OWNER ALPHA", "OWNER BETA")
    ]
    search_records = parse_account_search(
        rows,
        f"{ACCOUNT_ROOT_URL}api/accountnumbersearch/0057313",
    )
    detail = parse_account_detail(
        _text("account_detail.html"),
        f"{ACCOUNT_ROOT_URL}Account/0057313",
        expected_account="0057313",
        search_record=search_records,
    )
    assert detail["owner_index_names"] == ["OWNER ALPHA", "OWNER BETA"]
    assert len(detail["search_index_observations"]) == 2
    assert {
        observation["evidence_ref"]
        for observation in detail["search_index_observations"]
    } == {record["evidence_ref"] for record in search_records}


def test_tax_map_location_result_separates_locator_and_pdf_identity() -> None:
    records = parse_tax_map_search(
        _text("tax_map_location_results.html"),
        TAX_MAP_SEARCH_URL,
    )
    assert len(records) == 1
    record = records[0]
    assert record["map_taxlot"] == "1605070001100"
    assert record["map_name"] == "16050700"
    assert record["tax_map_document_id"] == "326"
    assert record["record_kind"] == "tax_map_locator"
    assert "/tax_map_locator/" in record["canonical_ref"]
    assert "/tax_map_document/326" in record["tax_map_document_ref"]
    assert record["canonical_ref"] != record["tax_map_document_ref"]
    assert "owner" not in record
    assert "title" not in record


def test_tax_map_map_name_and_explicit_empty_outcomes() -> None:
    records = parse_tax_map_search(
        _text("tax_map_name_results.html"),
        TAX_MAP_SEARCH_URL,
    )
    assert records[0]["map_taxlot"] is None
    assert records[0]["map_name"] == "16050700"
    assert records[0]["tax_map_document_id"] == "326"
    assert (
        parse_tax_map_search(_text("tax_map_empty.html"), TAX_MAP_SEARCH_URL)
        == []
    )


def test_omitted_limit_returns_every_source_row() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "search",
            "000",
            "--source",
            ACCOUNT_SOURCE_ID,
            "--field",
            "account",
        ]
    )
    result = execute(
        args,
        client=FakeLaneClient(_account_rows()),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    assert result.records[0]["retrieval_coverage"][
        "complete_for_selected_query"
    ] is True


def test_search_passes_short_and_noncanonical_native_locators_through() -> None:
    parser = build_parser()
    account = execute(
        parser.parse_args(
            [
                "search",
                "1",
                "--source",
                ACCOUNT_SOURCE_ID,
                "--field",
                "account",
            ]
        ),
        client=FakeLaneClient(_account_rows(1)),
        log_results=False,
    )
    tax_map = execute(
        parser.parse_args(
            [
                "search",
                "16-05-07",
                "--source",
                TAX_MAP_SOURCE_ID,
                "--field",
                "map_lot",
            ]
        ),
        client=FakeLaneClient(),
        log_results=False,
    )
    assert account.status == ResultStatus.OK
    assert tax_map.status == ResultStatus.OK


def test_explicit_limit_uses_query_bound_anchored_continuation() -> None:
    parser = build_parser()
    first_args = parser.parse_args(
        [
            "search",
            "000",
            "--source",
            ACCOUNT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "2",
        ]
    )
    client = FakeLaneClient(_account_rows())
    first = execute(first_args, client=client, log_results=False)
    assert [row["account_number"] for row in first.records] == [
        "0000001",
        "0000002",
    ]
    assert first.next_cursor

    second_args = parser.parse_args(
        [
            "search",
            "000",
            "--source",
            ACCOUNT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "2",
            "--cursor",
            str(first.next_cursor),
        ]
    )
    second = execute(second_args, client=client, log_results=False)
    assert [row["account_number"] for row in second.records] == ["0000003"]
    assert second.next_cursor is None

    mismatched_args = parser.parse_args(
        [
            "search",
            "001",
            "--source",
            ACCOUNT_SOURCE_ID,
            "--field",
            "account",
            "--limit",
            "2",
            "--cursor",
            str(first.next_cursor),
        ]
    )
    mismatch = execute(mismatched_args, client=client, log_results=False)
    assert mismatch.status == ResultStatus.SOURCE_CHANGED
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_account_command_combines_index_and_detail_without_title_inference() -> None:
    args = build_parser().parse_args(["account", "0057313"])
    result = execute(args, client=FakeLaneClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert result.records[0]["account_number"] == "0057313"
    assert result.records[0]["owner_index_name"] == "NORTHWEST CLEARWOODS INC"
    assert "recorded-title" in result.warnings[0]


def test_download_tax_map_writes_verified_pdf_and_preserves_document_identity(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "tax-map.pdf"
    args = build_parser().parse_args(
        [
            "download-tax-map",
            "326",
            "--destination",
            str(destination),
        ]
    )
    result = execute(args, client=FakeLaneClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"%PDF-")
    record = result.records[0]
    assert record["record_kind"] == "tax_map_document"
    assert record["source_record_id"] == "326"
    assert record["sha256"] == hashlib.sha256(destination.read_bytes()).hexdigest()

    second = execute(args, client=FakeLaneClient(), log_results=False)
    assert second.status == ResultStatus.UNAVAILABLE
    assert second.errors[0].code == "destination_exists"


def test_client_account_detail_bootstraps_anonymous_session_and_referer() -> None:
    landing = FakeResponse(url=ACCOUNT_ROOT_URL, text="<html>search</html>")
    detail_url = f"{ACCOUNT_ROOT_URL}Account/0057313"
    detail = FakeResponse(url=detail_url, text=_text("account_detail.html"))
    session = RecordingSession([landing, detail])
    client = LaneCountyPropertyClient(
        session=session,
        rate_limiter=type("NoWait", (), {"wait": lambda self: None})(),
    )
    page = client.account_detail("0057313")
    assert page.source_url == detail_url
    assert [call["method"] for call in session.calls] == ["GET", "GET"]
    assert session.calls[1]["headers"]["Referer"] == ACCOUNT_ROOT_URL
    assert session.closed is False


def test_client_tax_map_posts_current_webforms_state_for_both_modes() -> None:
    landing_html = _text("tax_map_landing.html")
    location_session = RecordingSession(
        [
            FakeResponse(url=TAX_MAP_SEARCH_URL, text=landing_html),
            FakeResponse(
                url=TAX_MAP_SEARCH_URL,
                text=_text("tax_map_location_results.html"),
            ),
        ]
    )
    location_client = LaneCountyPropertyClient(
        session=location_session,
        rate_limiter=type("NoWait", (), {"wait": lambda self: None})(),
    )
    location_client.tax_map_search("map_lot", "1605070001100")
    location_post = location_session.calls[1]["data"]
    assert location_post["__VIEWSTATE"] == "fixture-viewstate"
    assert location_post["SearchOption"] == "0"
    assert location_post["MapLot"] == "1605070001100"

    map_name_session = RecordingSession(
        [
            FakeResponse(url=TAX_MAP_SEARCH_URL, text=landing_html),
            FakeResponse(url=TAX_MAP_SEARCH_URL, text=landing_html),
            FakeResponse(
                url=TAX_MAP_SEARCH_URL,
                text=_text("tax_map_name_results.html"),
            ),
        ]
    )
    map_name_client = LaneCountyPropertyClient(
        session=map_name_session,
        rate_limiter=type("NoWait", (), {"wait": lambda self: None})(),
    )
    map_name_client.tax_map_search("map_name", "16050700")
    mode_post = map_name_session.calls[1]["data"]
    search_post = map_name_session.calls[2]["data"]
    assert mode_post["__EVENTTARGET"] == "SearchOption$1"
    assert search_post["SearchOption"] == "1"
    assert search_post["MapName"] == "16050700"


def test_probe_verifies_each_source_representation() -> None:
    parser = build_parser()
    account_result = execute(
        parser.parse_args(["probe", "--source", ACCOUNT_SOURCE_ID]),
        client=FakeLaneClient(),
        log_results=False,
    )
    assert account_result.status == ResultStatus.OK
    assert account_result.records[0]["anonymous_json_search_verified"] is True
    assert account_result.records[0]["anonymous_session_detail_verified"] is True

    map_result = execute(
        parser.parse_args(["probe", "--source", TAX_MAP_SOURCE_ID]),
        client=FakeLaneClient(),
        log_results=False,
    )
    assert map_result.status == ResultStatus.OK
    assert map_result.records[0]["anonymous_webforms_search_verified"] is True
    assert map_result.records[0]["official_pdf_verified"] is True
