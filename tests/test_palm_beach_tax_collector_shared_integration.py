from __future__ import annotations

import pytest

from tools import query_palm_beach_tax_collector as tax
from tools import query_property


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_and_guidance_keep_account_identities_distinct() -> None:
    routes = query_property.LIVE_ROUTES[tax.SOURCE_ID]
    guidance = query_property._source_guidance(tax.SOURCE_ID)

    assert sorted(routes) == [
        "account",
        "address",
        "discovery",
        "event",
        "owner",
        "parcel",
        "probe",
        "search",
    ]
    assert guidance["native_identity"]["parcel_join"] == (
        "17-digit Property Control Number"
    )
    assert guidance["native_identity"]["tax_account_locator"] == "AlternateKey"
    assert guidance["source_search_boundary"] == {
        "publisher_setting": "maximumRecords",
        "observed_value": 300,
        "equal_total_is_partial": True,
        "adapter_selected_cap": False,
    }
    assert "refresh" in guidance["direct_only_operations"]
    complement_ids = {
        value.get("source_id")
        for value in guidance["official_complements"]
    }
    assert "us-fl-palm-beach-property-appraiser" in complement_ids
    assert "us-fl-palm-beach-official-records" in complement_ids


@pytest.mark.parametrize(
    ("operation", "selector", "adapter_command", "native_command"),
    [
        ("search", "SMITH", "search", "search"),
        ("owner", "SMITH", "owner", "owner"),
        ("address", "100 MAIN", "address", "address"),
        ("parcel", tax.SENTINEL_PCN, "parcel", "parcel"),
        ("account", tax.SENTINEL_PCN, "account", "account"),
        ("event", tax.SENTINEL_PCN, "bills", "bills"),
        ("discovery", "all", "discovery", "discovery"),
        ("probe", "all", "probe", "probe"),
    ],
)
def test_shared_queries_do_not_add_default_caps_or_pacing(
    operation: str,
    selector: str,
    adapter_command: str,
    native_command: str,
) -> None:
    translated = query_property._palm_beach_tax_args(
        _parse(
            operation,
            selector,
            "--source",
            tax.SOURCE_ID,
            "--jurisdiction",
            tax.COUNTY_GEOID,
        ),
        adapter_command,
    )

    assert translated.command == native_command
    assert translated.minimum_interval == 0
    if native_command in {"search", "owner", "address", "parcel"}:
        assert translated.limit is None
        assert translated.cursor is None


def test_shared_fields_tax_year_and_native_cursors_translate() -> None:
    owner = query_property._palm_beach_tax_args(
        _parse(
            "search",
            "EXAMPLE OWNER",
            "--source",
            tax.SOURCE_ID,
            "--search-field",
            "owner",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
            "--minimum-interval",
            "0.6",
        ),
        "search",
    )
    payments = query_property._palm_beach_tax_args(
        _parse(
            "event",
            tax.SENTINEL_PCN,
            "--source",
            tax.SOURCE_ID,
            "--search-field",
            "payment-history",
            "--tax-year",
            "2024",
            "--limit",
            "9",
        ),
        "bills",
    )

    assert owner.command == "search"
    assert owner.field == "owner"
    assert owner.limit == 7
    assert owner.cursor == "cursor-value"
    assert owner.minimum_interval == 0.6
    assert payments.command == "payments"
    assert payments.tax_year == 2024
    assert payments.limit == 9


def test_shared_max_records_is_a_caller_bound_not_the_source_boundary() -> None:
    translated = query_property._palm_beach_tax_args(
        _parse(
            "search",
            "SMITH",
            "--source",
            tax.SOURCE_ID,
            "--max-records",
            "50",
        ),
        "search",
    )

    assert translated.limit == 50


def test_shared_scope_and_geometry_controls_are_source_specific() -> None:
    wrong_county = _parse(
        "parcel",
        tax.SENTINEL_PCN,
        "--source",
        tax.SOURCE_ID,
        "--county",
        "Miami-Dade",
    )
    geometry = _parse(
        "map",
        tax.SENTINEL_PCN,
        "--source",
        tax.SOURCE_ID,
    )
    with pytest.raises(ValueError, match="Palm Beach"):
        query_property._palm_beach_tax_args(wrong_county, "parcel")
    with pytest.raises(ValueError, match="does not publish parcel geometry"):
        query_property._palm_beach_tax_args(geometry, "parcel")
