from __future__ import annotations

import pytest

from tools import query_mason_county_tax_parcels as mason
from tools import query_property
from tools.public_records_contract import PublicRecordsResult


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_and_guidance_preserve_source_scope() -> None:
    routes = query_property.LIVE_ROUTES[mason.SOURCE_ID]
    guidance = query_property._source_guidance(mason.SOURCE_ID)

    assert sorted(routes) == [
        "address",
        "bbox",
        "count",
        "discovery",
        "map",
        "owner",
        "parcel",
        "point",
        "probe",
        "search",
        "subdivision",
    ]
    assert guidance["mode"] == "unified_live_county_gis"
    assert guidance["county_geoid"] == "53045"
    assert guidance["native_identity"] == {
        "feature_occurrence": "FID",
        "parcel_join_candidates": ["PIN", "TERRA_PIN", "Taxlot"],
        "parcel_join_uniqueness": "not_assumed",
    }
    assert "does not publish recorder instruments or treasury balance/payment history" in (
        guidance["note"]
    )
    assert {
        item.get("source_id")
        for item in guidance["official_complements"]
        if item.get("source_id")
    } == {
        "us-wa-mason-county-taxsifter",
        "us-wa-state-archives-digital-recorded-land",
    }


@pytest.mark.parametrize(
    ("operation", "adapter_command", "selector", "native_command", "geometry"),
    [
        ("owner", "owner", "EXAMPLE", "owner", False),
        ("address", "address", "100 TEST", "address", False),
        ("parcel", "parcel", "219010090013", "parcel", False),
        ("map", "parcel", "219010090013", "parcel", True),
        ("subdivision", "search", "TEST PLAT", "search", False),
        ("point", "point", "-123.1,47.2", "point", True),
        ("bbox", "bbox", "-123.2,47.1,-123.0,47.3", "bbox", True),
    ],
)
def test_shared_queries_translate_without_an_adapter_default_limit(
    operation: str,
    adapter_command: str,
    selector: str,
    native_command: str,
    geometry: bool,
) -> None:
    translated = query_property._mason_county_tax_parcel_args(
        _parse(
            operation,
            selector,
            "--source",
            mason.SOURCE_ID,
            "--jurisdiction",
            "53045",
        ),
        adapter_command,
    )

    assert translated.command == native_command
    assert translated.limit is None
    assert translated.minimum_interval == 0
    assert mason._query_spec(translated).return_geometry is geometry
    if operation == "subdivision":
        assert translated.field == "subdivision"


def test_shared_bound_cursor_and_interval_are_caller_selected() -> None:
    translated = query_property._mason_county_tax_parcel_args(
        _parse(
            "owner",
            "EXAMPLE",
            "--source",
            mason.SOURCE_ID,
            "--county",
            "Mason County",
            "--limit",
            "7",
            "--cursor",
            "cursor-value",
            "--minimum-interval",
            "0.7",
        ),
        "owner",
    )

    assert translated.limit == 7
    assert translated.cursor == "cursor-value"
    assert translated.minimum_interval == 0.7


@pytest.mark.parametrize(
    ("command", "selector", "coordinates"),
    [
        ("point", "-123.1,47.2", (-123.1, 47.2)),
        ("point", "-123.1 47.2", (-123.1, 47.2)),
        ("bbox", "-123.2,47.1,-123.0,47.3", (-123.2, 47.1, -123.0, 47.3)),
    ],
)
def test_negative_spatial_selectors_preserve_options_before_and_after(
    command: str, selector: str, coordinates: tuple[float, ...]
) -> None:
    args = _parse(
        command, "--source", mason.SOURCE_ID, selector, "--limit", "3"
    )
    translated = query_property._mason_county_tax_parcel_args(args, command)
    assert args.query == selector
    assert translated.limit == 3
    if command == "point":
        assert (translated.longitude, translated.latitude) == coordinates
    else:
        assert (
            translated.west, translated.south, translated.east, translated.north
        ) == coordinates


def test_spatial_selector_handling_does_not_accept_unknown_options() -> None:
    with pytest.raises(SystemExit):
        _parse("point", "-123.1,47.2", "--limti", "3")
    with pytest.raises(SystemExit):
        _parse("point", "-123.1,47.2", "--longitude", "-123.1", "--latitude", "47.2")


def test_shared_discovery_count_and_spatial_selectors() -> None:
    discovery = query_property._mason_county_tax_parcel_args(
        _parse("discovery", "--source", mason.SOURCE_ID),
        "metadata",
    )
    count = query_property._mason_county_tax_parcel_args(
        _parse(
            "count",
            "EXAMPLE",
            "--source",
            mason.SOURCE_ID,
            "--search-field",
            "owner",
        ),
        "count",
    )
    point = query_property._mason_county_tax_parcel_args(
        _parse(
            "point",
            "--source",
            mason.SOURCE_ID,
            "--longitude",
            "-123.1",
            "--latitude",
            "47.2",
        ),
        "point",
    )

    assert discovery.command == "metadata"
    assert count.command == "count"
    assert count.query == "EXAMPLE"
    assert count.field == "owner"
    assert point.command == "point"
    assert (point.longitude, point.latitude) == (-123.1, 47.2)


def test_shared_scope_validation_rejects_another_county_or_dated_snapshot() -> None:
    wrong_county = _parse(
        "parcel",
        "219010090013",
        "--source",
        mason.SOURCE_ID,
        "--county",
        "King",
    )
    wrong_state = _parse(
        "owner",
        "EXAMPLE",
        "--source",
        mason.SOURCE_ID,
        "--jurisdiction",
        "OR",
    )
    dated = _parse(
        "parcel",
        "219010090013",
        "--source",
        mason.SOURCE_ID,
        "--tax-year",
        "2025",
    )

    with pytest.raises(ValueError, match="Mason County"):
        query_property._mason_county_tax_parcel_args(
            wrong_county,
            "parcel",
        )
    with pytest.raises(ValueError, match="Washington context"):
        query_property._mason_county_tax_parcel_args(
            wrong_state,
            "owner",
        )
    with pytest.raises(ValueError, match="without a source tax-year"):
        query_property._mason_county_tax_parcel_args(dated, "parcel")


def test_shared_execute_passes_catalog_contract_and_requests_map_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decision = {
        "allowed": True,
        "reason_code": "automated_access_supported",
        "limits": {},
    }
    observed = {}

    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == mason.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, source_id):
            assert source_id == mason.SOURCE_ID
            return decision

    def fake_execute(args, *, access_contract=None, **_kwargs):
        observed["args"] = args
        observed["access_contract"] = access_contract
        result = PublicRecordsResult.success(
            mason.build_query(args),
            [
                {
                    "source_id": mason.SOURCE_ID,
                    "record_kind": "parcel_assessment_geometry_snapshot",
                    "source_occurrence_id": "FID:0",
                    "geometry": {"rings": []},
                }
            ],
            retrieved_at="2026-07-30T12:00:00Z",
        )
        observed["expected"] = result.to_dict()
        return result

    monkeypatch.setattr(query_property, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(mason, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "map",
            "219010090013",
            "--source",
            mason.SOURCE_ID,
        )
    )

    assert observed["args"].command == "parcel"
    assert observed["args"].geometry is True
    assert observed["access_contract"] is decision
    assert payload == observed["expected"]
