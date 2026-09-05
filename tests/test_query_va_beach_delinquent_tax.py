from __future__ import annotations

import base64
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_va_beach_delinquent_tax as va_tax


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/va_beach_delinquent_tax"
)
ITEM = json.loads((FIXTURE_DIR / "item.json").read_text(encoding="utf-8"))
LAYER = json.loads((FIXTURE_DIR / "layer.json").read_text(encoding="utf-8"))
PAGE_1 = json.loads(
    (FIXTURE_DIR / "page_1.json").read_text(encoding="utf-8")
)
PAGE_2 = json.loads(
    (FIXTURE_DIR / "page_2.json").read_text(encoding="utf-8")
)


def _allowed() -> dict[str, Any]:
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
        "limits": {},
    }


def _args(*values: str):
    return va_tax.build_parser().parse_args(list(values))


class FakeClient:
    def __init__(
        self,
        *,
        count: int = 3,
        pages: list[Mapping[str, Any]] | None = None,
        layers: list[Mapping[str, Any]] | None = None,
        item: Mapping[str, Any] | None = None,
    ) -> None:
        self.count_value = count
        self.pages = [
            copy.deepcopy(page) for page in (pages or [PAGE_1, PAGE_2])
        ]
        self.layers = [
            copy.deepcopy(layer) for layer in (layers or [LAYER, LAYER])
        ]
        self.item = copy.deepcopy(item or ITEM)
        self.count_calls: list[str] = []
        self.page_calls: list[tuple[str, int]] = []
        self.item_calls = 0
        self.layer_calls = 0

    def item_metadata(self) -> Mapping[str, Any]:
        self.item_calls += 1
        return copy.deepcopy(self.item)

    def layer_metadata(self) -> Mapping[str, Any]:
        index = min(self.layer_calls, len(self.layers) - 1)
        self.layer_calls += 1
        return copy.deepcopy(self.layers[index])

    def count(self, where: str) -> int:
        self.count_calls.append(where)
        return self.count_value

    def ordered_page(
        self,
        where: str,
        *,
        page_size: int,
    ) -> Mapping[str, Any]:
        self.page_calls.append((where, page_size))
        if not self.pages:
            return {"features": [], "fields": copy.deepcopy(LAYER["fields"])}
        payload = self.pages.pop(0)
        payload["features"] = payload["features"][:page_size]
        return payload


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        va_tax,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_layer_and_item_metadata_bind_the_verified_public_table():
    snapshot = va_tax.inspect_layer_metadata(LAYER)
    va_tax.inspect_item_metadata(ITEM)

    assert snapshot.data_last_edit_ms == 1785400787752
    assert snapshot.data_last_edit_iso == "2026-07-30T08:39:47.752000Z"
    assert snapshot.max_record_count == 2000
    assert len(snapshot.schema_fingerprint) == 64


def test_layer_metadata_rejects_missing_or_incompatible_fields():
    missing = copy.deepcopy(LAYER)
    missing["fields"] = [
        field
        for field in missing["fields"]
        if field["name"] != "Total_Delinquent_Amount_Due"
    ]
    with pytest.raises(
        va_tax.VirginiaBeachTaxSourceChanged,
        match="missing required field",
    ):
        va_tax.inspect_layer_metadata(missing)

    incompatible = copy.deepcopy(LAYER)
    next(
        field
        for field in incompatible["fields"]
        if field["name"] == "Tax_Due"
    )["type"] = "esriFieldTypeDate"
    with pytest.raises(
        va_tax.VirginiaBeachTaxSourceChanged,
        match="incompatible type",
    ):
        va_tax.inspect_layer_metadata(incompatible)


def test_query_schema_comparison_ignores_layer_only_field_properties():
    layer = copy.deepcopy(LAYER)
    for field in layer["fields"]:
        field["nullable"] = field["name"] != "OBJECTID"
        field["editable"] = field["name"] != "OBJECTID"
    snapshot = va_tax.inspect_layer_metadata(layer)

    features = va_tax._page_features(PAGE_1, snapshot)

    assert len(features) == 2


def test_where_builder_combines_filters_and_escapes_quotes():
    criteria = va_tax.SearchCriteria(
        query="Bay",
        owner="O'Brien",
        address="Ocean View",
        gpin="24170000010000",
        bill_number="1124000101",
        tax_year=2024,
        installment="1",
        district="D03",
        min_total_due=va_tax.Decimal("1000"),
        max_total_due=va_tax.Decimal("2000.50"),
    )

    where = va_tax.build_where(criteria)

    assert "UPPER(Owner_Name) LIKE '%O''BRIEN%'" in where
    assert "UPPER(Situs_Address) LIKE '%OCEAN VIEW%'" in where
    assert "GPIN = '24170000010000'" in where
    assert "Bill_Number = '1124000101'" in where
    assert "Tax_Year = '2024'" in where
    assert "Installment = '1'" in where
    assert "District = 'D03'" in where
    assert "Total_Delinquent_Amount_Due >= 1000" in where
    assert "Total_Delinquent_Amount_Due <= 2000.50" in where


def test_argument_normalization_preserves_flexible_district_input():
    criteria = va_tax._criteria_from_args(
        _args(
            "search",
            "--district",
            "3",
            "--tax-year",
            "2025",
            "--installment",
            "2",
        )
    )

    assert criteria.district == "D03"
    assert criteria.tax_year == 2025
    assert criteria.installment == "2"


def test_normalizer_preserves_join_keys_amounts_and_raw_evidence():
    snapshot = va_tax.inspect_layer_metadata(LAYER)
    record = va_tax.normalize_feature(
        PAGE_1["features"][0],
        snapshot=snapshot,
    )

    assert record["record_kind"] == "property_tax_delinquency"
    assert record["native_parcel_id"] == "14469645070000"
    assert record["native_account_id"] == "1125000027"
    assert record["native_event_id"] == (
        "1125000027:2:14469645070000:2025"
    )
    assert record["owner_observation"]["raw_name"] == "NOVAK JOSEPH"
    assert record["mailing_address"]["raw"] == (
        "900 SHERRY VIRGINIA BEACH VA 23455"
    )
    assert record["situs_address"]["raw"] == "900 SHERRY AVE"
    assert record["amounts"] == {
        "tax_due": 1193.1,
        "tax_due_minor": 119310,
        "penalty_due": 119.31,
        "penalty_due_minor": 11931,
        "interest_due": 144.37,
        "interest_due_minor": 14437,
        "fee_due": 0.0,
        "fee_due_minor": 0,
        "total_due": 1456.78,
        "total_due_minor": 145678,
        "component_total_minor": 145678,
        "component_difference_minor": 0,
        "currency": "USD",
    }
    assert record["join_keys"]["parcel_and_assessment"]["gpin"] == (
        "14469645070000"
    )
    assert record["canonical_ref"].endswith(
        "/tax-delinquency/"
        "1125000027%3A2%3A14469645070000%3A2025"
    )
    assert record["raw_attributes"]["Mailing_Address"] == "900    SHERRY"


def test_unbounded_search_traverses_the_authoritative_count_by_keyset():
    client = FakeClient()

    result = va_tax.execute(
        _args("search", "--page-size", "2"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 3
    assert result.next_cursor is None
    assert client.count_calls == ["1=1"]
    assert client.page_calls == [
        ("1=1", 2),
        ("(1=1) AND OBJECTID > 2", 1),
    ]
    assert [record["native_object_id"] for record in result.records] == [
        1,
        2,
        7,
    ]


def test_bounded_search_cursor_resumes_same_query_and_snapshot():
    first_client = FakeClient(pages=[PAGE_1])
    first = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=first_client,
    )

    assert first.status.value == "partial"
    assert first.next_cursor
    cursor = va_tax._decode_cursor(first.next_cursor)
    assert cursor.last_object_id == 2
    assert cursor.emitted_count == 2
    assert cursor.total_count == 3

    resumed_client = FakeClient(pages=[PAGE_2])
    resumed = va_tax.execute(
        _args("search", "--cursor", first.next_cursor),
        access_decision=_allowed(),
        client=resumed_client,
    )

    assert resumed.status.value == "ok"
    assert [record["native_object_id"] for record in resumed.records] == [7]
    assert resumed_client.page_calls == [
        ("(1=1) AND OBJECTID > 2", 1),
    ]


def test_reviewed_client_page_size_caps_each_live_request():
    client = FakeClient(pages=[PAGE_1])
    client.page_size = 1

    result = va_tax.execute(
        _args("search", "--limit", "1", "--page-size", "100"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "partial"
    assert [record["native_object_id"] for record in result.records] == [1]
    assert client.page_calls == [("1=1", 1)]


def test_cursor_is_bound_to_criteria():
    first = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=FakeClient(pages=[PAGE_1]),
    )

    mismatch = va_tax.execute(
        _args("owner", "NOVAK", "--cursor", first.next_cursor),
        access_decision=_allowed(),
        client=FakeClient(),
    )

    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_criteria_mismatch"


def test_cursor_rejects_mutated_paging_state():
    client = FakeClient(pages=[PAGE_1])
    first = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=client,
    )
    assert first.next_cursor

    encoded = first.next_cursor.removeprefix(va_tax.CURSOR_PREFIX)
    padding = "=" * (-len(encoded) % 4)
    payload = json.loads(
        base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
    )
    payload["last_object_id"] += 100
    mutated = (
        va_tax.CURSOR_PREFIX
        + base64.urlsafe_b64encode(
            va_tax.canonical_json(payload).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )

    with pytest.raises(
        va_tax.VirginiaBeachTaxCursorError,
        match="consistency check failed",
    ):
        va_tax._decode_cursor(mutated)


def test_cursor_detects_a_daily_refresh_before_resuming():
    first = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=FakeClient(pages=[PAGE_1]),
    )
    refreshed = copy.deepcopy(LAYER)
    refreshed["editingInfo"]["dataLastEditDate"] += 1

    stale = va_tax.execute(
        _args("search", "--cursor", first.next_cursor),
        access_decision=_allowed(),
        client=FakeClient(layers=[refreshed]),
    )

    assert stale.status.value == "unavailable"
    assert stale.errors[0].code == "cursor_snapshot_changed"
    assert stale.errors[0].retryable is True


def test_refresh_during_traversal_is_not_reported_as_a_complete_result():
    refreshed = copy.deepcopy(LAYER)
    refreshed["editingInfo"]["dataLastEditDate"] += 1

    result = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=FakeClient(
            pages=[PAGE_1],
            layers=[LAYER, refreshed],
        ),
    )

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "cursor_snapshot_changed"


def test_authoritative_zero_count_is_no_results_not_a_source_error():
    client = FakeClient(count=0, pages=[])

    result = va_tax.execute(
        _args("owner", "NO SUCH OWNER"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert client.page_calls == []
    assert client.layer_calls == 2


def test_non_monotonic_page_is_an_explicit_pagination_failure():
    changed_page = copy.deepcopy(PAGE_1)
    changed_page["features"].reverse()

    result = va_tax.execute(
        _args("search", "--limit", "2", "--page-size", "2"),
        access_decision=_allowed(),
        client=FakeClient(pages=[changed_page]),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "pagination_stalled"
    assert "strictly increasing" in result.errors[0].message


def test_probe_checks_item_identity_and_returns_one_sample():
    client = FakeClient(pages=[PAGE_1])

    result = va_tax.execute(
        _args("probe"),
        access_decision=_allowed(),
        client=client,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.next_cursor is None
    assert client.item_calls == 1
    assert client.count_calls == ["1=1"]
    assert client.page_calls == [("1=1", 1)]


def test_probe_rejects_an_item_redirected_to_another_service():
    changed_item = copy.deepcopy(ITEM)
    changed_item["url"] = "https://example.test/FeatureServer"

    result = va_tax.execute(
        _args("probe"),
        access_decision=_allowed(),
        client=FakeClient(item=changed_item),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "virginia_beach_tax_source_changed"


def test_routes_map_missing_roles_to_joinable_official_sources():
    result = va_tax.execute(_args("routes"))

    assert result.status.value == "ok"
    route_map = result.records[0]
    assert route_map["record_kind"] == "public_record_route_map"
    roles = {route["role"]: route for route in route_map["routes"]}
    assert "current_tax_account_detail_and_payment_history" in roles
    assert "assessment_and_current_owner_context" in roles
    assert "recorded_deeds_judgments_and_ucc" in roles
    assert "circuit_court_case_index" in roles
    assert "general_district_court_case_index" in roles
    assert "tax_sale_notices_and_auction_links" in roles
    assert "GPIN" in roles["recorded_deeds_judgments_and_ucc"]["join_keys"]


def test_invalid_district_and_amount_range_are_explicit_query_failures():
    invalid_district = va_tax.execute(
        _args("search", "--district", "north"),
        access_decision=_allowed(),
        client=FakeClient(),
    )
    invalid_range = va_tax.execute(
        _args(
            "search",
            "--min-total-due",
            "200",
            "--max-total-due",
            "100",
        ),
        access_decision=_allowed(),
        client=FakeClient(),
    )

    assert invalid_district.status.value == "unavailable"
    assert invalid_district.errors[0].code == "invalid_query"
    assert invalid_range.status.value == "unavailable"
    assert invalid_range.errors[0].code == "invalid_query"
