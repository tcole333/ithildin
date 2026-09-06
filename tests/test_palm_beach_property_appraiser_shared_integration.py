from __future__ import annotations

import pytest

from tools import query_palm_beach_property_appraiser as palm
from tools import query_property


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_and_guidance_preserve_identity_and_source_roles() -> None:
    routes = query_property.LIVE_ROUTES[palm.SOURCE_ID]
    guidance = query_property._source_guidance(palm.SOURCE_ID)

    assert sorted(routes) == [
        "account",
        "address",
        "bbox",
        "count",
        "discovery",
        "map",
        "owner",
        "parcel",
        "point",
        "probe",
        "sale",
        "search",
        "subdivision",
    ]
    assert guidance["native_identity"] == {
        "feature_occurrence": "OBJECTID",
        "candidate_exact_tax_account_join": "PARCEL_NUMBER",
        "separate_geometry_or_group_identifier": "PARID",
        "identifier_uniqueness_assumed": False,
    }
    assert guidance["representations"][1]["independent_corroboration"] is False
    assert palm.CLERK_SOURCE_ID in {
        item.get("source_id")
        for item in guidance["official_complements"]
    }
    assert palm.FL_DOR_SOURCE_ID in {
        item.get("source_id")
        for item in guidance["official_complements"]
    }


@pytest.mark.parametrize(
    ("operation", "adapter_command", "selector", "native_command", "geometry"),
    [
        ("owner", "owner", "EXAMPLE", "owner", False),
        ("address", "address", "100 MAIN", "address", False),
        ("parcel", "parcel", "04364325000005040", "parcel", False),
        ("account", "parcel", "04-36-43-25-00-000-5040", "parcel", False),
        ("map", "parcel", "04364325000005040", "parcel", True),
        ("sale", "sale", "5021/1011", "sale", False),
        ("subdivision", "search", "EXAMPLE PLAT", "search", False),
        ("point", "point", "-80.1,26.7", "point", True),
        ("bbox", "bbox", "-80.2,26.6,-80.0,26.8", "bbox", True),
    ],
)
def test_shared_queries_translate_without_default_result_or_pacing_bounds(
    operation: str,
    adapter_command: str,
    selector: str,
    native_command: str,
    geometry: bool,
) -> None:
    translated = query_property._palm_beach_property_args(
        _parse(
            operation,
            selector,
            "--source",
            palm.SOURCE_ID,
            "--jurisdiction",
            palm.COUNTY_GEOID,
        ),
        adapter_command,
    )

    assert translated.command == native_command
    assert translated.limit is None
    assert translated.minimum_interval == 0
    spec = palm._query_spec(translated)
    assert spec.return_geometry is geometry
    if operation == "subdivision":
        assert translated.field == "subdivision"
    if operation == "account":
        assert spec.where == "PARCEL_NUMBER='04364325000005040'"


def test_shared_field_mapping_and_caller_selected_cursor() -> None:
    parid = query_property._palm_beach_property_args(
        _parse(
            "search",
            "GEOMETRY-GROUP-7",
            "--source",
            palm.SOURCE_ID,
            "--search-field",
            "parid",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
            "--minimum-interval",
            "0.6",
        ),
        "search",
    )
    book_page = query_property._palm_beach_property_args(
        _parse(
            "sale",
            "5021/1011",
            "--source",
            palm.SOURCE_ID,
            "--search-field",
            "book-page",
        ),
        "sale",
    )

    assert parid.field == "parid"
    assert parid.limit == 7
    assert parid.cursor == "cursor-value"
    assert parid.minimum_interval == 0.6
    assert book_page.field == "book-page"


def test_shared_scope_validation_is_county_specific() -> None:
    wrong_county = _parse(
        "parcel",
        "04364325000005040",
        "--source",
        palm.SOURCE_ID,
        "--county",
        "Broward",
    )
    wrong_state = _parse(
        "owner",
        "EXAMPLE",
        "--source",
        palm.SOURCE_ID,
        "--jurisdiction",
        "WA",
    )
    dated = _parse(
        "parcel",
        "04364325000005040",
        "--source",
        palm.SOURCE_ID,
        "--tax-year",
        "2025",
    )

    with pytest.raises(ValueError, match="Palm Beach"):
        query_property._palm_beach_property_args(wrong_county, "parcel")
    with pytest.raises(ValueError, match="Florida context"):
        query_property._palm_beach_property_args(wrong_state, "owner")
    with pytest.raises(ValueError, match="without a native tax-year"):
        query_property._palm_beach_property_args(dated, "parcel")
