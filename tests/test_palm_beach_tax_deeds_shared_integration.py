from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_palm_beach_tax_deeds as tax_deeds
from tools import query_property


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_and_guidance_preserve_tax_deed_identities() -> None:
    routes = query_property.LIVE_ROUTES[tax_deeds.SOURCE_ID]
    guidance = query_property._source_guidance(tax_deeds.SOURCE_ID)

    assert sorted(routes) == [
        "discovery",
        "download",
        "event",
        "owner",
        "parcel",
        "probe",
        "sale",
        "search",
    ]
    assert guidance["native_identity"]["case_occurrence_locator"] == (
        "portal row ID"
    )
    assert guidance["native_identity"]["parcel_join"] == (
        "reversible 17-digit Property Control Number"
    )
    assert guidance["native_identity"]["document_occurrence"] == [
        "portal row ID",
        "document inventory sequence",
        "image ID when available",
    ]
    complement_ids = {
        value.get("source_id")
        for value in guidance["official_complements"]
    }
    assert {
        "us-fl-palm-beach-property-appraiser",
        "us-fl-palm-beach-tax-collector",
        "us-fl-palm-beach-official-records",
        "us-fl-palm-beach-ecaseview",
    } <= complement_ids


@pytest.mark.parametrize(
    ("operation", "selector", "adapter_command", "native_command"),
    [
        ("search", "2023-0680TD", "search", "case"),
        (
            "parcel",
            tax_deeds.SENTINEL_PARCEL_ID,
            "parcel",
            "parcel",
        ),
        ("sale", "2023-10-18", "sale-date", "sale-date"),
        ("event", tax_deeds.SENTINEL_ROW_ID, "detail", "detail"),
        ("discovery", "all", "discovery", "discovery"),
        ("probe", "all", "probe", "probe"),
    ],
)
def test_shared_routes_add_no_default_result_cap(
    operation: str,
    selector: str,
    adapter_command: str,
    native_command: str,
) -> None:
    translated = query_property._palm_beach_tax_deeds_args(
        _parse(
            operation,
            selector,
            "--source",
            tax_deeds.SOURCE_ID,
            "--jurisdiction",
            tax_deeds.COUNTY_GEOID,
        ),
        adapter_command,
    )

    assert translated.command == native_command
    if native_command in tax_deeds.SEARCH_CONTRACTS:
        assert translated.limit is None
        assert translated.cursor is None
    assert not hasattr(translated, "minimum_interval")


def test_shared_native_fields_dates_cursor_and_document_translate(
    tmp_path: Path,
) -> None:
    owner = query_property._palm_beach_tax_deeds_args(
        _parse(
            "search",
            "PRIEST",
            "--source",
            tax_deeds.SOURCE_ID,
            "--search-field",
            "owner",
            "--from-date",
            "2023-01-01",
            "--to-date",
            "2024-12-31",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
        ),
        "search",
    )
    output_path = tmp_path / "certificate.pdf"
    document = query_property._palm_beach_tax_deeds_args(
        _parse(
            "download",
            f"{tax_deeds.SENTINEL_ROW_ID}:{tax_deeds.SENTINEL_DOCUMENT_ID}",
            "--source",
            tax_deeds.SOURCE_ID,
            "--destination",
            str(output_path),
        ),
        "document",
    )

    assert owner.command == "owner"
    assert owner.from_date == "2023-01-01"
    assert owner.to_date == "2024-12-31"
    assert owner.limit == 7
    assert owner.cursor == "cursor-value"
    assert document.command == "document"
    assert document.portal_row_id == tax_deeds.SENTINEL_ROW_ID
    assert document.native_document_id == tax_deeds.SENTINEL_DOCUMENT_ID
    assert document.document_output == str(output_path)


def test_shared_max_records_is_a_caller_selected_bound() -> None:
    translated = query_property._palm_beach_tax_deeds_args(
        _parse(
            "search",
            tax_deeds.SENTINEL_CASE_NUMBER,
            "--source",
            tax_deeds.SOURCE_ID,
            "--max-records",
            "50",
        ),
        "search",
    )

    assert translated.limit == 50


def test_shared_scope_and_native_date_requirements_are_explicit() -> None:
    wrong_county = _parse(
        "parcel",
        tax_deeds.SENTINEL_PARCEL_ID,
        "--source",
        tax_deeds.SOURCE_ID,
        "--county",
        "Broward",
    )
    owner_without_dates = _parse(
        "owner",
        "PRIEST",
        "--source",
        tax_deeds.SOURCE_ID,
    )

    with pytest.raises(ValueError, match="Palm Beach"):
        query_property._palm_beach_tax_deeds_args(
            wrong_county,
            "parcel",
        )
    with pytest.raises(ValueError, match="from-date"):
        query_property._palm_beach_tax_deeds_args(
            owner_without_dates,
            "owner",
        )
