from __future__ import annotations

import copy
import json
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest

from tools import query_licking_foreclosure_archive as archive
from tools.public_records_contract import ResultStatus


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "licking_foreclosure_archive"
)


def _fixture(name: str) -> Any:
    return json.loads((FIXTURE_ROOT / name).read_text())


def _args(command: str, **overrides: Any) -> Namespace:
    values = {
        "command": command,
        "year": 2026,
        "case_number": None,
        "parcel": None,
        "address": None,
        "status": None,
        "sale_type": None,
        "purchaser": None,
        "limit": None,
        "cursor": None,
        "output": None,
        "json_out": False,
    }
    if command == "case":
        values["case_number"] = "25CV01926"
    if command == "probe":
        values["case_number"] = archive.PROBE_CASE_NUMBER
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
        self.headers = {"Content-Type": "application/json; charset=utf-8"}


class FixtureSession:
    def __init__(
        self,
        *,
        exact_not_found: bool = False,
        final_host: str = archive.EXPECTED_HOST,
    ) -> None:
        self.headers: dict[str, str] = {}
        self.exact_not_found = exact_not_found
        self.final_host = final_host
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any],
        timeout: float,
        allow_redirects: bool,
    ) -> FakeResponse:
        call = {
            "method": method,
            "url": url,
            "params": dict(params),
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        }
        self.calls.append(call)
        if url == archive.YEARS_URL:
            fixture = "years.json"
        elif url == archive.FORECLOSURES_URL:
            fixture = (
                "current.json"
                if params.get("year") == 0
                else f"year_{params['year']}.json"
            )
        elif url.startswith(f"{archive.DETAIL_URL_BASE}/"):
            fixture = (
                "case_not_found.json"
                if self.exact_not_found
                else "case_25CV01926.json"
            )
        else:
            raise AssertionError(f"unexpected request: {call}")
        response_url = url.replace(archive.EXPECTED_HOST, self.final_host)
        return FakeResponse(
            (FIXTURE_ROOT / fixture).read_text(),
            response_url,
        )


def _client(session: FixtureSession | None = None) -> archive.LickingForeclosureArchiveClient:
    return archive.LickingForeclosureArchiveClient(
        session or FixtureSession(),
        minimum_interval=0,
        max_retries=0,
    )


def test_source_contract_is_distinct_and_documents_join_semantics() -> None:
    source = archive._source_record()

    assert source["source_id"] == (
        "us-oh-licking-sheriff-foreclosure-archive"
    )
    assert source["native_identity"]["key"] == "case_number"
    assert source["native_identity"]["observed_rows_checked"] == 14_275
    assert source["inventory_observation"]["years"][0] == 2026
    assert source["inventory_observation"]["years"][-1] == 2000
    assert source["inventory_observation"]["total_records"] == 14_275
    assert source["temporal_views"]["year_0"]["complete_year"] is False
    assert source["temporal_views"]["maximum_inventory_year"]["mutable"] is True
    complement = source["official_complements"][0]
    assert complement["source_id"] == "us-oh-licking-sheriff-realauction"
    assert complement["join_keys"] == [
        "case_number",
        "parcel_id",
        "sale_date",
    ]
    assert complement["matched_outcome_evidence"].startswith(
        "same_underlying_event"
    )


def test_year_inventory_preserves_official_order_and_temporal_views() -> None:
    inventory = archive.parse_year_inventory(
        _fixture("years.json"),
        source_url=archive.YEARS_URL,
    )

    assert inventory.years == (2026, 2025, 2000)
    assert inventory.current_archive_year == 2026
    assert inventory.records[0]["temporal_view"] == "current_year_archive"
    assert inventory.records[-1]["temporal_view"] == (
        "historical_archive_year"
    )
    assert inventory.records[0]["canonical_ref"].endswith(
        "/foreclosure-archive-year/2026"
    )


def test_current_record_normalizes_field_rich_outcome_and_join_keys() -> None:
    records = archive.parse_year_payload(
        _fixture("year_2026.json"),
        source_url=f"{archive.FORECLOSURES_URL}?year=2026",
        year=2026,
        current_archive_year=2026,
    )

    sold = records[0]
    assert sold["native_case_number"] == "25CV01926"
    assert sold["sale_date"] == "2026-07-30"
    assert sold["appraised_value_amount"] == "125000.00"
    assert sold["required_deposit_amount"] == "5000.00"
    assert sold["status"] == "sold"
    assert sold["purchase_price_amount"] == "70680.00"
    assert sold["purchaser_address_text"] == (
        "24755 Chagrin Blvd. Suite 200, Cleveland, OH, 44122"
    )
    assert sold["realauction_join"]["keys"] == {
        "case_number": "25CV01926",
        "parcel_ids": ["034-105570-00.000"],
        "sale_date": "2026-07-30",
    }
    assert sold["canonical_ref"].endswith("/foreclosure-case/25CV01926")

    multi = records[2]
    assert multi["parcel_ids"] == [
        "054-269934-00.004",
        "054-223098-00.000",
    ]
    assert len(multi["parcel_links"]) == 2


def test_historical_record_preserves_contact_and_missing_modern_fields() -> None:
    records = archive.parse_year_payload(
        _fixture("year_2000.json"),
        source_url=f"{archive.FORECLOSURES_URL}?year=2000",
        year=2000,
        current_archive_year=2026,
    )
    record = records[0]

    assert record["temporal_view"] == "historical_archive_year"
    assert record["purchaser_contact_name"] == "Household Realty Corporation"
    assert record["purchase_price_amount"] == "23334.00"
    assert record["parcel_ids"] == []
    assert record["sale_type"] is None
    assert record["required_deposit_amount"] is None


def test_full_year_fetch_has_no_default_cap_and_supports_filters() -> None:
    result = archive.execute(
        _args("year"),
        client=_client(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    assert [record["case_number"] for record in result.records] == [
        "25CV01926",
        "26CV00605",
        "26CV00331",
    ]
    assert result.next_cursor is None
    assert all(
        record["retrieval"]["complete_selected_array_fetched"]
        for record in result.records
    )

    filtered = archive.execute(
        _args(
            "year",
            parcel="054-223098",
            sale_type="mort",
            purchaser="courthouse",
        ),
        client=_client(),
        log_results=False,
    )
    assert filtered.status == ResultStatus.OK
    assert [record["case_number"] for record in filtered.records] == [
        "26CV00331"
    ]


def test_year_limit_cursor_binds_source_query_membership_and_boundary() -> None:
    records = archive.parse_year_payload(
        _fixture("year_2026.json"),
        source_url=f"{archive.FORECLOSURES_URL}?year=2026",
        year=2026,
        current_archive_year=2026,
    )
    selection = archive._selection_payload(
        year=2026,
        case_number=None,
        parcel=None,
        address=None,
        status=None,
        sale_type=None,
        purchaser=None,
    )
    first, cursor = archive._window_records(
        records,
        selection=selection,
        limit=2,
        cursor=None,
    )
    assert [record["case_number"] for record in first] == [
        "25CV01926",
        "26CV00605",
    ]
    assert cursor is not None

    refreshed = copy.deepcopy(list(records))
    refreshed[0]["status"] = "corrected"
    second, final_cursor = archive._window_records(
        refreshed,
        selection=selection,
        limit=2,
        cursor=cursor,
    )
    assert [record["case_number"] for record in second] == ["26CV00331"]
    assert final_cursor is None

    other_selection = dict(selection)
    other_selection["year"] = 2025
    with pytest.raises(archive.LickingArchiveSelectionError) as mismatch:
        archive._window_records(
            records,
            selection=other_selection,
            limit=2,
            cursor=cursor,
        )
    assert mismatch.value.code == "cursor_query_mismatch"

    with pytest.raises(archive.LickingArchiveSelectionError) as changed:
        archive._window_records(
            (records[0], records[2]),
            selection=selection,
            limit=2,
            cursor=cursor,
        )
    assert changed.value.code == "cursor_membership_changed"

    decoded = archive._cursor_decode(cursor)
    tampered = dict(decoded)
    tampered["anchor_before"] = "another-case"
    with pytest.raises(archive.LickingArchiveSelectionError) as boundary:
        archive._window_records(
            records,
            selection=selection,
            limit=2,
            cursor=archive._cursor_encode(tampered),
        )
    assert boundary.value.code == "cursor_boundary_changed"


def test_exact_case_and_json_null_have_distinct_success_states() -> None:
    found = archive.execute(
        _args("case"),
        client=_client(),
        log_results=False,
    )
    assert found.status == ResultStatus.OK
    assert found.records[0]["case_number"] == "25CV01926"

    missing = archive.execute(
        _args("case", case_number="NO-SUCH-CASE"),
        client=_client(FixtureSession(exact_not_found=True)),
        log_results=False,
    )
    assert missing.status == ResultStatus.NO_RESULTS
    assert not missing.errors


def test_schema_identity_and_requested_year_drift_are_rejected() -> None:
    missing_field = _fixture("year_2026.json")
    del missing_field[0]["Terms"]
    with pytest.raises(archive.LickingArchiveSourceChanged):
        archive.parse_year_payload(
            missing_field,
            source_url="https://apps.lickingcounty.gov/year",
            year=2026,
            current_archive_year=2026,
        )

    duplicate = _fixture("year_2026.json")
    duplicate.append(copy.deepcopy(duplicate[0]))
    with pytest.raises(archive.LickingArchiveSourceChanged):
        archive.parse_year_payload(
            duplicate,
            source_url="https://apps.lickingcounty.gov/year",
            year=2026,
            current_archive_year=2026,
        )

    with pytest.raises(archive.LickingArchiveSourceChanged):
        archive.parse_year_payload(
            _fixture("year_2000.json"),
            source_url="https://apps.lickingcounty.gov/year",
            year=2026,
            current_archive_year=2026,
        )


def test_probe_exercises_inventory_year_current_and_detail_routes() -> None:
    session = FixtureSession()
    result = archive.execute(
        _args("probe"),
        client=_client(session),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    probe = result.records[0]["probe"]
    assert probe["routes_exercised"] == (
        "year_inventory",
        "explicit_full_year",
        "rolling_current_subset",
        "exact_case",
    )
    assert probe["probe_year_record_count"] == 3
    assert probe["rolling_current_record_count"] == 1
    assert probe["sentinel_case_number"] == "25CV01926"
    assert probe["sentinel_purchase_price_amount"] == "70680.00"
    assert [call["params"].get("year") for call in session.calls] == [
        None,
        2026,
        0,
        None,
    ]


def test_client_validates_final_host_for_source_provenance() -> None:
    client = _client(FixtureSession(final_host="unrelated.example"))
    with pytest.raises(archive.LickingArchiveSourceChanged):
        client.years()


def test_year_must_be_in_live_inventory() -> None:
    result = archive.execute(
        _args("year", year=1999),
        client=_client(),
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "year_not_in_inventory"
    assert result.errors[0].details["available_years"] == (2026, 2025, 2000)


def test_text_filters_and_explicit_limits_have_no_adapter_ceiling() -> None:
    long_selector = "CASE-" + ("X" * 20_000)
    parsed = archive.build_parser().parse_args(
        [
            "year",
            "--year",
            "2026",
            "--case-number",
            long_selector,
            "--limit",
            "1000000000",
        ]
    )
    assert parsed.case_number == long_selector
    assert parsed.limit == 1_000_000_000
