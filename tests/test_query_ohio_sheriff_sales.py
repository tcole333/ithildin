from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from tools import query_ohio_sheriff_sales as ohio_sales
from tools.public_records_contract import ResultStatus


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_sheriff_sales"
)


def _text_fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text()


def _json_fixture(name: str) -> dict[str, Any]:
    return json.loads(_text_fixture(name))


def _args(command: str, **overrides: Any) -> Namespace:
    values = {
        "command": command,
        "county": "delaware",
        "month": "2026-07",
        "date": None,
        "area": None,
        "case_number": None,
        "parcel": None,
        "address": None,
        "limit": None,
        "cursor": None,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


class FakeResponse:
    def __init__(
        self,
        text: str,
        url: str,
        *,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}


class FixtureSession:
    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        headers: dict[str, str] | None,
        timeout: float,
        allow_redirects: bool,
    ) -> FakeResponse:
        call = {
            "method": method,
            "url": url,
            "params": dict(params),
            "headers": headers,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        self.calls.append(call)
        if url.endswith("/") and not params:
            return FakeResponse(_text_fixture("splash.html"), url)
        if params.get("zmethod") == "CALENDAR":
            return FakeResponse(_text_fixture("calendar.html"), url)
        if params.get("Zmethod") == "PREVIEW":
            return FakeResponse(_text_fixture("preview.html"), url)
        if params.get("FNC") == "LOAD":
            page = int(params["bypassPage"]) or 1
            area = params["AREA"]
            fixture = (
                f"listing_waiting_page_{page}"
                if area == "W" and page in {1, 2}
                else "listing_empty"
            )
            return FakeResponse(_text_fixture(f"{fixture}.json"), url)
        if params.get("FNC") == "UPDATE":
            fixture = (
                "update_page_2.json"
                if params["ref"] == "54721,"
                else "update_page_1.json"
            )
            return FakeResponse(_text_fixture(fixture), url)
        raise AssertionError(f"unexpected request: {call}")


def test_source_contract_covers_three_official_tenants_and_complements() -> None:
    assert set(ohio_sales.TENANTS) == {"franklin", "delaware", "licking"}
    for tenant in ohio_sales.TENANTS.values():
        source = ohio_sales._source_record(tenant)
        assert source["source_id"] == tenant.source_id
        assert source["operator"] == "Realauction"
        assert source["observed_at"] == "2026-07-30"
        assert source["native_identity"]["key"] == "tenant_and_aid"
        assert source["access"]["listing_json"] == "anonymous"
        assert source["access"]["separate_aid_detail"] == "account"
        assert source["verification"]["routes_exercised"] == [
            "root_session_bootstrap",
            "monthly_calendar",
            "auction_preview",
            "listing_json",
            "status_json",
        ]
        assert source["official_alternatives_and_complements"]
        assert "plaintiff" in source["public_field_gaps"]

    licking = ohio_sales._source_record(ohio_sales.TENANTS["licking"])
    richer = licking["official_alternatives_and_complements"][0]
    assert richer["relationship"] == "county_archive_and_field_richer_fallback"
    assert {"purchaser", "purchase_price", "parcel"} <= set(richer["fields"])


def test_calendar_parser_preserves_counts_identity_and_source_date() -> None:
    records = ohio_sales.parse_calendar_page(
        _text_fixture("calendar.html"),
        tenant=ohio_sales.TENANTS["delaware"],
        requested_month="2026-07",
        source_url="https://example.test/calendar",
    )

    assert [record["auction_date"] for record in records] == [
        "2026-07-22",
        "2026-07-29",
    ]
    assert records[1]["scheduled_count"] == 3
    assert records[1]["active_count"] == 0
    assert records[1]["observed_at"] == "2026-07-30"
    assert records[1]["canonical_ref"].endswith(
        "/sheriff-sale-calendar/2026-07-29"
    )


def test_calendar_parser_rejects_month_or_schema_drift() -> None:
    with pytest.raises(ohio_sales.OhioSheriffSaleSourceChanged):
        ohio_sales.parse_calendar_page(
            _text_fixture("calendar.html"),
            tenant=ohio_sales.TENANTS["delaware"],
            requested_month="2026-08",
            source_url="https://example.test/calendar",
        )
    with pytest.raises(ohio_sales.OhioSheriffSaleSourceChanged):
        ohio_sales.parse_calendar_page(
            "<html><body>No calendar</body></html>",
            tenant=ohio_sales.TENANTS["delaware"],
            requested_month="2026-07",
            source_url="https://example.test/calendar",
        )


def test_listing_parser_decodes_native_fields_and_multi_parcel_identity() -> None:
    page = ohio_sales.parse_listing_payload(
        _json_fixture("listing_waiting_page_1.json"),
        tenant=ohio_sales.TENANTS["delaware"],
        auction_date="2026-07-29",
        area="W",
        page=1,
        source_url="https://example.test/listing",
    )

    first = page.records[0]
    assert page.auction_ids == ("54719", "54720")
    assert first["native_auction_id"] == "54719"
    assert first["case_number"] == "25-CVE-12-1480"
    assert first["source_case_sequence"] == "0"
    assert first["parcel_ids"] == [
        "318-132-03-036-000",
        "318-132-03-037-000",
    ]
    assert first["property_address"] == "6393 S OLD STATE ROAD"
    assert (first["city"], first["postal_code"]) == (
        "LEWIS CENTER",
        "43035",
    )
    assert first["appraised_value_amount"] == "534000.00"
    assert first["opening_bid_amount"] == "356000.00"
    assert first["deposit_requirement_amount"] == "10000.00"
    assert first["canonical_ref"].endswith("/sheriff-sale-auction/54719")


def test_listing_parser_rejects_missing_fields_and_membership_drift() -> None:
    missing = _json_fixture("listing_waiting_page_1.json")
    missing["retHTML"] = missing["retHTML"].replace(
        "Deposit Requirement:", "Security:"
    )
    with pytest.raises(ohio_sales.OhioSheriffSaleSourceChanged):
        ohio_sales.parse_listing_payload(
            missing,
            tenant=ohio_sales.TENANTS["delaware"],
            auction_date="2026-07-29",
            area="W",
            page=1,
            source_url="https://example.test/listing",
        )

    reordered = _json_fixture("listing_waiting_page_1.json")
    reordered["rlist"] = "54720,54719"
    with pytest.raises(ohio_sales.OhioSheriffSaleSnapshotChanged):
        ohio_sales.parse_listing_payload(
            reordered,
            tenant=ohio_sales.TENANTS["delaware"],
            auction_date="2026-07-29",
            area="W",
            page=1,
            source_url="https://example.test/listing",
        )


def test_status_parser_preserves_schedule_cancellation_and_sale_fields() -> None:
    first, counts = ohio_sales.parse_update_payload(
        _json_fixture("update_page_1.json"),
        expected_aids=("54719", "54720"),
    )
    second, _ = ohio_sales.parse_update_payload(
        _json_fixture("update_page_2.json"),
        expected_aids=("54721",),
    )

    assert counts == {"W": 2, "C": 0}
    assert first["54719"]["scheduled_or_status_datetime"] == (
        "2026-07-29T10:00:00-04:00"
    )
    assert first["54720"]["source_status_message"] == "Canceled per Order"
    assert second["54721"]["sold_amount"] == "244500.00"
    assert second["54721"]["sold_to_class"] == "3rd Party Bidder"
    assert second["54721"]["bid_history_available"] is True
    assert ohio_sales._derived_status("C", "Auction Status", "Unsold") == (
        "unsold"
    )


def test_client_bootstraps_and_traverses_every_native_page() -> None:
    session = FixtureSession()
    client = ohio_sales.OhioRealAuctionClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )
    fetched = client.auctions(
        ohio_sales.TENANTS["delaware"],
        "2026-07-29",
    )

    assert [record["native_auction_id"] for record in fetched.records] == [
        "54719",
        "54720",
        "54721",
    ]
    assert [record["auction_status"] for record in fetched.records] == [
        "scheduled",
        "canceled",
        "sold",
    ]
    assert fetched.pages_fetched == {"R": 1, "W": 2, "C": 1}
    assert fetched.source_page_counts == {"R": 1, "W": 2, "C": 0}
    load_calls = [
        call["params"]
        for call in session.calls
        if call["params"].get("FNC") == "LOAD"
    ]
    assert [(call["AREA"], call["bypassPage"]) for call in load_calls] == [
        ("R", 0),
        ("W", 0),
        ("C", 0),
        ("W", 2),
    ]
    assert session.calls[0]["url"].endswith("/")


def test_probe_exercises_calendar_preview_listing_and_status_routes() -> None:
    session = FixtureSession()
    client = ohio_sales.OhioRealAuctionClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )
    result = ohio_sales.execute(
        _args("probe"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.records[0]["probe"]
    assert probe["auction_date"] == "2026-07-29"
    assert probe["calendar_scheduled_count"] == 3
    assert probe["listing_count"] == 3
    assert probe["status_counts"] == {
        "scheduled": 1,
        "canceled": 1,
        "sold": 1,
    }
    methods = [
        call["params"].get("FNC")
        or call["params"].get("Zmethod")
        or call["params"].get("zmethod")
        or "BOOTSTRAP"
        for call in session.calls
    ]
    assert {"BOOTSTRAP", "CALENDAR", "PREVIEW", "LOAD", "UPDATE"} <= set(
        methods
    )


def test_continuation_is_selection_and_ordered_membership_bound() -> None:
    records = [
        {"native_auction_id": "1", "auction_status": "scheduled"},
        {"native_auction_id": "2", "auction_status": "scheduled"},
        {"native_auction_id": "3", "auction_status": "scheduled"},
    ]
    selection = {"county": "delaware", "date": "2026-07-29"}
    first, cursor = ohio_sales._window_records(
        records,
        selection=selection,
        limit=2,
        cursor=None,
    )
    assert [record["native_auction_id"] for record in first] == ["1", "2"]
    assert cursor is not None

    refreshed = [dict(record) for record in records]
    refreshed[1]["auction_status"] = "sold"
    second, next_cursor = ohio_sales._window_records(
        refreshed,
        selection=selection,
        limit=2,
        cursor=cursor,
    )
    assert [record["native_auction_id"] for record in second] == ["3"]
    assert next_cursor is None

    with pytest.raises(
        ohio_sales.OhioSheriffSaleSelectionError
    ) as mismatch:
        ohio_sales._window_records(
            records,
            selection={"county": "franklin", "date": "2026-07-29"},
            limit=2,
            cursor=cursor,
        )
    assert mismatch.value.code == "cursor_query_mismatch"

    with pytest.raises(
        ohio_sales.OhioSheriffSaleSelectionError
    ) as changed:
        ohio_sales._window_records(
            [records[0], records[2]],
            selection=selection,
            limit=2,
            cursor=cursor,
        )
    assert changed.value.code == "cursor_membership_changed"


def test_filters_and_limit_have_no_adapter_specific_text_or_result_ceiling() -> None:
    assert ohio_sales._positive_int("1000000000") == 1_000_000_000
    record = {
        "case_number": "25-CVE-12-1480",
        "parcel_id_raw": "318-132-03-036-000",
        "property_address": "6393 S OLD STATE ROAD",
        "city": "LEWIS CENTER",
        "postal_code": "43035",
    }
    assert ohio_sales._matches(
        record,
        case_number="CVE-12",
        parcel="132-03",
        address="old state road",
    )


def test_empty_listing_is_authoritative_no_results() -> None:
    class EmptyClient:
        def auctions(
            self,
            _tenant: ohio_sales.Tenant,
            _date: str,
            *,
            areas: tuple[str, ...],
        ) -> ohio_sales.AuctionFetch:
            assert areas == ohio_sales.DEFAULT_AREAS
            return ohio_sales.AuctionFetch(
                records=(),
                pages_fetched={"R": 1, "W": 1, "C": 1},
                source_page_counts={"R": 1, "W": 0, "C": 0},
                preview_url="https://example.test/preview",
                listing_schema_fingerprint=(
                    ohio_sales.LISTING_SCHEMA_FINGERPRINT
                ),
            )

    result = ohio_sales.execute(
        _args("auctions", date="2026-07-29"),
        client=EmptyClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.NO_RESULTS
    assert not result.errors


def test_observed_403_is_structured_as_access_response_not_policy() -> None:
    class RestrictedClient:
        def calendar(
            self,
            _tenant: ohio_sales.Tenant,
            _month: str,
        ) -> tuple[dict[str, Any], ...]:
            raise ohio_sales.OhioSheriffSaleHTTPError(
                403, "https://example.test/calendar"
            )

    result = ohio_sales.execute(
        _args("calendar"),
        client=RestrictedClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.RESTRICTED
    assert result.errors[0].code == "http_403"
    assert result.errors[0].details["access_characterization"] == (
        "observed_response_not_policy"
    )


def test_client_rejects_redirect_outside_selected_official_tenant() -> None:
    class RedirectedSession(FixtureSession):
        def request(self, *args: Any, **kwargs: Any) -> FakeResponse:
            response = super().request(*args, **kwargs)
            response.url = "https://unrelated.example/landing"
            return response

    client = ohio_sales.OhioRealAuctionClient(
        RedirectedSession(),
        minimum_interval=0,
        max_retries=0,
    )
    with pytest.raises(ohio_sales.OhioSheriffSaleSourceChanged):
        client.bootstrap(ohio_sales.TENANTS["delaware"])
