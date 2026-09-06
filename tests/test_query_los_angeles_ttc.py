from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_los_angeles_ttc as la_ttc
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy, SourceSchemaError


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "los_angeles_ttc"
)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def parse_args(*values: str) -> Any:
    return la_ttc.build_parser().parse_args(list(values))


class FixtureClient:
    def __init__(self, *, no_result: bool = False) -> None:
        self.no_result = no_result
        self.payment_pages: list[int] = []

    def assessor_exact(self, ain: str) -> dict[str, Any] | None:
        assert la_ttc.normalize_ain(ain) == la_ttc.PROBE_AIN
        return fixture_json("assessor_exact.json")["features"][0]["attributes"]

    def payment_bootstrap(self) -> la_ttc.PaymentBootstrap:
        return la_ttc.parse_payment_bootstrap_html(
            fixture_text("payment_bootstrap.html")
        )

    def payment_page(
        self,
        ain: str,
        page: int,
        *,
        bootstrap: la_ttc.PaymentBootstrap,
    ) -> la_ttc.PaymentPage:
        assert bootstrap.nonce == "fixture-nonce"
        self.payment_pages.append(page)
        if self.no_result:
            payload = fixture_json("payment_no_result.json")
        else:
            payload = fixture_json(f"payment_page_{page}.json")
        return la_ttc.parse_payment_response(
            payload,
            expected_ain=ain,
            native_page=page,
        )

    def html(self, url: str) -> str:
        if url == la_ttc.AUCTION_SCHEDULE_URL:
            return fixture_text("auction_schedule.html")
        if url == la_ttc.AUCTION_CONTACT_URL:
            return fixture_text("publications.html")
        raise AssertionError(url)

    def bytes(
        self,
        url: str,
        *,
        max_bytes: int,
    ) -> la_ttc.ResponseArtifact:
        assert url.endswith(
            "EP-Listing-Public-2025B-and-2025B-Follow-up.pdf"
        )
        content = b"%PDF-fixture"
        assert len(content) < max_bytes
        return la_ttc.ResponseArtifact(
            content=content,
            source_url=url,
            headers={
                "content-type": "application/pdf",
                "last-modified": "Wed, 13 May 2026 16:11:45 GMT",
            },
            status_code=200,
        )


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        payload: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        url: str = "https://ttc.lacounty.gov/result",
    ) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.content = content if content is not None else text.encode()
        self.headers = headers or {"content-type": "text/html"}
        self.url = url

    def json(self) -> dict[str, Any]:
        if self._payload is None:
            raise ValueError("fixture has no JSON")
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_sources_keep_assessor_payment_and_sale_provenance_distinct() -> None:
    payload = la_ttc.source_manifest()
    source_ids = {item["source_id"] for item in payload["sources"]}

    assert source_ids == {
        la_ttc.ASSESSOR_SOURCE_ID,
        la_ttc.PAYMENT_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    }
    assert payload["joins"] == [
        {
            "field": "ain",
            "normalization": "ten_digits",
            "formatted_example": "1234-567-890",
            "source_ids": [
                la_ttc.ASSESSOR_SOURCE_ID,
                la_ttc.PAYMENT_SOURCE_ID,
                la_ttc.SALE_SOURCE_ID,
            ],
            "relation": "candidate_join_not_merged_provenance",
        }
    ]
    assert payload["operations"]["history"]["pagination"] == "native_page"
    assert payload["operations"]["tax-default-status"]["url"] == (
        la_ttc.AUCTION_NOTICE_URL
    )
    route_names = {item["name"] for item in payload["complementary_routes"]}
    assert {
        "Annual Secured Property Tax Bill",
        "Secured Property Tax Information Request",
        "Current auction vendor",
    } <= route_names


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2004001003", "2004001003"),
        ("2004-001-003", "2004001003"),
        (" 2004001003 ", "2004001003"),
    ],
)
def test_ain_normalization_matches_ttc_contract(raw: str, expected: str) -> None:
    assert la_ttc.normalize_ain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "2004 001 003", "2004-01-003", "20040010030", "ABCDEFGHIJ"],
)
def test_ain_normalization_rejects_non_source_forms(raw: str) -> None:
    with pytest.raises(la_ttc.LATTCQueryError, match="ten digits"):
        la_ttc.normalize_ain(raw)


def test_payment_bootstrap_and_structured_not_found_parsers() -> None:
    bootstrap = la_ttc.parse_payment_bootstrap_html(
        fixture_text("payment_bootstrap.html")
    )
    assert bootstrap.ajax_url == la_ttc.PAYMENT_AJAX_URL
    assert bootstrap.nonce == "fixture-nonce"
    assert bootstrap.script_url.endswith("phf-script.js?v=1.2.1")
    assert len(bootstrap.schema_fingerprint) == 64

    no_result = la_ttc.parse_payment_response(
        fixture_json("payment_no_result.json"),
        expected_ain="0000000000",
        native_page=1,
    )
    assert no_result.no_result is True
    assert no_result.rows == ()
    assert no_result.native_state["status"] == 404
    assert no_result.native_state["title"] == "Not Found"


def test_payment_parser_requires_matching_ain_and_native_metadata() -> None:
    payload = fixture_json("payment_page_1.json")
    page = la_ttc.parse_payment_response(
        payload,
        expected_ain=la_ttc.PROBE_AIN,
        native_page=1,
    )
    assert len(page.rows) == 2
    assert page.meta["totalRecords"] == 3
    assert page.meta["totalPages"] == 2
    assert page.meta["lastUpdated"] == "2026-07-28"

    changed = fixture_json("payment_page_1.json")
    changed["data"]["data"][0]["ain"] = "1111111111"
    with pytest.raises(SourceSchemaError, match="differs"):
        la_ttc.parse_payment_response(
            changed,
            expected_ain=la_ttc.PROBE_AIN,
            native_page=1,
        )


def test_history_follows_native_pages_and_preserves_lossless_amounts() -> None:
    client = FixtureClient()
    args = parse_args("history", "2004-001-003")
    query = la_ttc.build_query(args)
    result = la_ttc.execute(
        args,
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert "max_pages" not in query.query.parameters
    assert client.payment_pages == [1, 2]
    assert len(result.records) == 3
    assert result.next_cursor is None
    record = result.records[0]
    assert record["source_id"] == la_ttc.PAYMENT_SOURCE_ID
    assert record["record_kind"] == "property_tax_payment"
    assert record["native_ids"]["payment_id"] == "7"
    assert record["tax_year"] == 2025
    assert record["installment_key"] == "2"
    assert record["effective_date"] == "2026-02-01"
    assert record["amounts"]["tax_paid"] == "6399.47"
    assert record["amounts_raw"]["tax_paid"] == "6,399.47"
    assert record["account_snapshot"]["source_last_updated"] == "2026-07-28"
    assert record["tax_default_status"]["status"] == (
        "not_asserted_by_payment_history"
    )
    assert record["join_candidates"]["ain"]["target_source_ids"] == (
        la_ttc.ASSESSOR_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    )


def test_history_page_bound_returns_resumable_partial_result() -> None:
    client = FixtureClient()
    result = la_ttc.execute(
        parse_args("history", la_ttc.PROBE_AIN, "--max-pages", "1"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert len(result.records) == 2
    assert result.next_cursor == (
        f"la-ttc:history:{la_ttc.PROBE_AIN}:page:2"
    )
    assert client.payment_pages == [1]

    resumed = la_ttc.execute(
        parse_args(
            "history",
            la_ttc.PROBE_AIN,
            "--cursor",
            result.next_cursor,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert resumed.status == ResultStatus.OK
    assert len(resumed.records) == 1
    assert resumed.records[0]["account_snapshot"]["native_page"] == 2


def test_history_distinguishes_authoritative_empty_and_invalid_query() -> None:
    no_result = la_ttc.execute(
        parse_args("history", "0000000000"),
        client=FixtureClient(no_result=True),
        log_results=False,
    )
    assert no_result.status == ResultStatus.NO_RESULTS
    assert no_result.errors == ()

    invalid = la_ttc.execute(
        parse_args("history", "not-an-ain"),
        client=FixtureClient(),
        log_results=False,
    )
    assert invalid.status == ResultStatus.UNAVAILABLE
    assert invalid.errors[0].code == "invalid_ain"
    assert invalid.errors[0].category == "query"

    wrong_cursor = la_ttc.execute(
        parse_args(
            "history",
            la_ttc.PROBE_AIN,
            "--cursor",
            "la-ttc:history:1111111111:page:2",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert wrong_cursor.status == ResultStatus.UNAVAILABLE
    assert wrong_cursor.errors[0].code == "invalid_history_cursor"


def test_assessor_route_is_separately_sourced_and_routes_to_ttc() -> None:
    result = la_ttc.execute(
        parse_args("route", "2004-001-003"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["source_id"] == la_ttc.ASSESSOR_SOURCE_ID
    assert record["native_ids"]["ain"] == la_ttc.PROBE_AIN
    assert record["native_ids"]["apn"] == "2004-001-003"
    assert record["situs_address"]["street"] == "8321 FAUST AVE"
    assert record["operation_state"] == "assessor_ain_verified"
    assert [item["source_id"] for item in record["next_operations"]] == [
        la_ttc.PAYMENT_SOURCE_ID,
        la_ttc.SALE_SOURCE_ID,
    ]


def test_auction_schedule_preserves_redemption_and_link_states() -> None:
    records = la_ttc.parse_auction_schedule_html(
        fixture_text("auction_schedule.html")
    )

    assert [(row["auction_cycle"], row["sale_phase"]) for row in records] == [
        ("2026A", "initial"),
        ("2026A", "follow_up"),
    ]
    initial, follow_up = records
    assert initial["schedule"]["start"]["normalized"] == (
        "2026-04-18T15:00:00-07:00"
    )
    assert initial["redemption"]["last_day_to_redeem"]["normalized"] == (
        "2026-04-17T17:00:00-07:00"
    )
    assert initial["routes"]["property_list"]["state"] == (
        "not_linked_on_current_official_schedule"
    )
    assert follow_up["routes"]["remaining_properties"]["url"].endswith(
        "/1396/browsestandard"
    )
    assert follow_up["routes"]["terms_and_conditions"]["url"].endswith(
        "2026A-Follow-Up-Terms-and-Conditions-Guide.pdf"
    )


def test_publication_index_separates_result_and_legacy_artifacts() -> None:
    artifacts = la_ttc.parse_publications_html(
        fixture_text("publications.html")
    )

    assert len(artifacts) == 4
    result_artifacts = [
        item
        for item in artifacts
        if item.kind == "sale_results_excess_proceeds"
    ]
    assert [item.cycle for item in result_artifacts] == ["2025C", "2025B"]
    assert result_artifacts[0].wordpress_upload_month == "2026-05"
    assert result_artifacts[1].phase_coverage == ("initial", "follow_up")
    sold = [item for item in artifacts if item.kind == "sold_parcels"]
    assert {item.cycle for item in sold} == {"2019B", "2018A"}


def test_sale_result_text_parser_preserves_ids_phases_and_amounts() -> None:
    rows, windows = la_ttc.parse_sale_results_text(
        fixture_text("sale_results_2025b.txt"),
        expected_cycle="2025B",
    )

    assert windows == {
        "initial": "October 18 - 21, 2025",
        "follow_up": "December 6 - 9, 2025",
    }
    assert len(rows) == 3
    assert rows[0].ain == "2190009032"
    assert rows[0].formatted_ain == "2190-009-032"
    assert rows[0].item == "1520"
    assert rows[0].phase == "follow_up"
    assert rows[0].purchase_price == "9900.00"
    assert rows[0].excess_proceeds == "1946.60"
    assert rows[1].phase == "initial"
    assert rows[2].purchase_price == "500200.00"


def test_sale_results_are_paginated_without_losing_publication_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        la_ttc,
        "extract_pdf_text",
        lambda _artifact: fixture_text("sale_results_2025b.txt"),
    )
    result = la_ttc.execute(
        parse_args("sale-results", "2025B", "--limit", "2"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.next_cursor == "la-ttc:sale:2025B:offset:2"
    assert len(result.records) == 2
    assert result.raw_artifact_refs[0].endswith(
        "EP-Listing-Public-2025B-and-2025B-Follow-up.pdf"
    )
    assert result.raw_artifact_refs[1].startswith("sha256:")
    record = result.records[0]
    assert record["record_kind"] == "property_tax_sale_result"
    assert record["sale_id"] == "2025B:follow_up:1520:2190009032"
    assert record["status"] == "sold_as_published"
    assert record["publication_date"] == "2026-05-13"
    assert record["publication_date_basis"] == "http_last_modified"
    assert record["amounts"]["purchase_price"] == "9900.00"
    assert record["excess_proceeds_state"]["status"] == (
        "positive_amount_published"
    )
    assert record["join_candidates"]["ain"]["target_source_ids"] == (
        la_ttc.ASSESSOR_SOURCE_ID,
        la_ttc.PAYMENT_SOURCE_ID,
    )


def test_client_uses_one_session_for_bootstrap_and_ajax_post() -> None:
    session = FakeSession(
        [
            FakeResponse(
                text=fixture_text("payment_bootstrap.html"),
                headers={"content-type": "text/html; charset=UTF-8"},
            ),
            FakeResponse(
                payload=fixture_json("payment_no_result.json"),
                headers={"content-type": "application/json"},
            ),
        ]
    )
    client = la_ttc.LosAngelesTTCClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )

    bootstrap = client.payment_bootstrap()
    page = client.payment_page(
        "0000000000",
        1,
        bootstrap=bootstrap,
    )

    assert page.no_result is True
    assert [call["method"] for call in session.calls] == ["GET", "POST"]
    assert session.calls[0]["url"] == la_ttc.PAYMENT_HISTORY_URL
    post = session.calls[1]
    assert post["url"] == la_ttc.PAYMENT_AJAX_URL
    assert post["data"] == {
        "action": la_ttc.PAYMENT_ACTION,
        "ain": "0000000000",
        "page": 1,
        "nonce": "fixture-nonce",
    }
    assert post["headers"]["Referer"] == la_ttc.PAYMENT_HISTORY_URL


def test_client_retries_bounded_transient_status() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503, text="temporary"),
            FakeResponse(
                text=fixture_text("payment_bootstrap.html"),
                headers={"content-type": "text/html"},
            ),
        ]
    )
    client = la_ttc.LosAngelesTTCClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
            max_backoff=0,
        ),
        sleeper=lambda _seconds: None,
    )

    assert "Payment History" in client.html(la_ttc.PAYMENT_HISTORY_URL)
    assert len(session.calls) == 2


def test_pdf_extractor_rejects_non_pdf_before_invoking_tool() -> None:
    artifact = la_ttc.ResponseArtifact(
        content=b"<html>not a pdf</html>",
        source_url="https://ttc.lacounty.gov/not-a-pdf",
        headers={},
        status_code=200,
    )
    with pytest.raises(SourceSchemaError, match="not a PDF"):
        la_ttc.extract_pdf_text(artifact, executable="/bin/false")
