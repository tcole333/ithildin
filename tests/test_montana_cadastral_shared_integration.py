from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_montana_cadastral as mt
from tools import query_property
from tools.public_records_contract import PublicRecordsResult


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_orion_county_prefixes_have_an_explicit_census_geoid_crosswalk() -> None:
    expected = {
        "Beaverhead": "30001",
        "Big Horn": "30003",
        "Blaine": "30005",
        "Broadwater": "30007",
        "Carbon": "30009",
        "Carter": "30011",
        "Cascade": "30013",
        "Chouteau": "30015",
        "Custer": "30017",
        "Daniels": "30019",
        "Dawson": "30021",
        "Deer Lodge": "30023",
        "Fallon": "30025",
        "Fergus": "30027",
        "Flathead": "30029",
        "Gallatin": "30031",
        "Garfield": "30033",
        "Glacier": "30035",
        "Golden Valley": "30037",
        "Granite": "30039",
        "Hill": "30041",
        "Jefferson": "30043",
        "Judith Basin": "30045",
        "Lake": "30047",
        "Lewis and Clark": "30049",
        "Liberty": "30051",
        "Lincoln": "30053",
        "McCone": "30055",
        "Madison": "30057",
        "Meagher": "30059",
        "Mineral": "30061",
        "Missoula": "30063",
        "Musselshell": "30065",
        "Park": "30067",
        "Petroleum": "30069",
        "Phillips": "30071",
        "Pondera": "30073",
        "Powder River": "30075",
        "Powell": "30077",
        "Prairie": "30079",
        "Ravalli": "30081",
        "Richland": "30083",
        "Roosevelt": "30085",
        "Rosebud": "30087",
        "Sanders": "30089",
        "Sheridan": "30091",
        "Silver Bow": "30093",
        "Stillwater": "30095",
        "Sweet Grass": "30097",
        "Teton": "30099",
        "Toole": "30101",
        "Treasure": "30103",
        "Valley": "30105",
        "Wheatland": "30107",
        "Wibaux": "30109",
        "Yellowstone": "30111",
    }

    assert {county.name: county.geoid for county in mt.COUNTIES} == expected
    assert mt.COUNTY_BY_PREFIX[1].geoid == "30093"
    assert mt.COUNTY_BY_PREFIX[55].geoid == "30069"
    assert mt._county_from_selector("069").prefix == 55
    assert mt._county_from_selector("30069").prefix == 55


def test_shared_routes_cover_live_bulk_spatial_and_discovery_surfaces() -> None:
    routes = query_property.LIVE_ROUTES[mt.SOURCE_ID]
    guidance = query_property._source_guidance(mt.SOURCE_ID)

    assert sorted(routes) == [
        "account",
        "address",
        "count",
        "discovery",
        "download",
        "manifest",
        "map",
        "owner",
        "parcel",
        "point",
        "probe",
        "releases",
        "search",
    ]
    assert guidance["mode"] == "unified_live_and_bulk_cadastral"
    assert guidance["unified_operations"] == sorted(routes)
    assert "ORION COUNTYCD is not Census FIPS" in guidance["note"]
    assert "nullable PARCELID alone joins a parcel" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "selector", "adapter_command", "native_command", "field"),
    [
        ("search", "RANCH", "search", "search", "query"),
        ("owner", "RANCH LLC", "owner", "owner", "name"),
        ("address", "1 MAIN ST", "address", "address", "query"),
        ("parcel", "56382732101040000", "parcel", "parcel", "identifier"),
        ("account", "100077", "account", "search", "property_id"),
        ("map", "56382732101040000", "map", "parcel", "identifier"),
    ],
)
def test_shared_live_routes_preserve_exact_selectors_county_cursor_and_geometry(
    operation: str,
    selector: str,
    adapter_command: str,
    native_command: str,
    field: str,
) -> None:
    values = [
        operation,
        selector,
        "--source",
        mt.SOURCE_ID,
        "--jurisdiction",
        "30069",
        "--tax-year",
        "2026",
        "--limit",
        "7",
        "--cursor",
        "cursor-1",
        "--page-size",
        "19",
    ]

    translated = query_property._montana_cadastral_args(
        _parse(*values),
        adapter_command,
    )

    assert translated.command == native_command
    assert getattr(translated, field) == selector
    assert translated.county == "30069"
    assert translated.tax_year == 2026
    assert translated.limit == 7
    assert translated.cursor == "cursor-1"
    assert translated.page_size == 19
    assert translated.geometry is (operation == "map")


def test_shared_search_field_count_and_point_translation() -> None:
    account_search = query_property._montana_cadastral_args(
        _parse(
            "search",
            "00077",
            "--source",
            mt.SOURCE_ID,
            "--search-field",
            "assessment-code",
            "--county-code",
            "069",
        ),
        "search",
    )
    count = query_property._montana_cadastral_args(
        _parse(
            "count",
            "RANCH",
            "--source",
            mt.SOURCE_ID,
            "--search-field",
            "owner",
            "--county",
            "Petroleum",
        ),
        "count",
    )
    point = query_property._montana_cadastral_args(
        _parse(
            "point",
            "--source",
            mt.SOURCE_ID,
            "--longitude",
            "-110.7",
            "--latitude",
            "46.9",
            "--county",
            "55",
        ),
        "point",
    )

    assert account_search.command == "search"
    assert account_search.property_id == "00077"
    assert account_search.county == "30069"
    assert count.command == "count"
    assert count.owner == "RANCH"
    assert count.county == "30069"
    assert point.command == "point"
    assert (point.longitude, point.latitude) == (-110.7, 46.9)
    assert point.county == "30069"
    assert point.geometry is True


def test_shared_bulk_routes_keep_exact_dataset_county_and_transfer_options(
    tmp_path: Path,
) -> None:
    manifest = query_property._montana_cadastral_args(
        _parse(
            "manifest",
            "Petroleum",
            "--source",
            mt.SOURCE_ID,
            "--dataset-type",
            "parcel-shp",
        ),
        "manifest",
    )
    probe = query_property._montana_cadastral_args(
        _parse(
            "probe",
            "30069",
            "--source",
            mt.SOURCE_ID,
            "--dataset-type",
            "parcel-gdb",
            "--range-bytes",
            "1024",
        ),
        "probe",
    )
    destination = tmp_path / "county55.zip"
    download = query_property._montana_cadastral_args(
        _parse(
            "download",
            "55",
            "--source",
            mt.SOURCE_ID,
            "--dataset-type",
            "orion",
            "--destination",
            str(destination),
            "--no-resume",
            "--expected-sha256",
            "a" * 64,
            "--max-download-bytes",
            "2000000000",
            "--chunk-size",
            "65536",
        ),
        "download",
    )

    assert (manifest.command, manifest.dataset_type, manifest.county) == (
        "manifest",
        "parcel-shp",
        "30069",
    )
    assert (probe.command, probe.dataset_type, probe.county) == (
        "artifact-probe",
        "parcel-gdb",
        "30069",
    )
    assert probe.range_bytes == 1024
    assert (download.command, download.dataset_type, download.county) == (
        "download",
        "orion",
        "30069",
    )
    assert download.destination == str(destination)
    assert download.resume is False
    assert download.expected_sha256 == "a" * 64
    assert download.max_download_bytes == 2_000_000_000
    assert download.chunk_size == 65_536


def test_shared_discovery_and_live_probe_are_distinct_from_bulk_probe() -> None:
    alternatives = query_property._montana_cadastral_args(
        _parse("discovery", "--source", mt.SOURCE_ID),
        "discovery",
    )
    counties = query_property._montana_cadastral_args(
        _parse("discovery", "counties", "--source", mt.SOURCE_ID),
        "discovery",
    )
    live_probe = query_property._montana_cadastral_args(
        _parse("probe", "--source", mt.SOURCE_ID),
        "probe",
    )

    assert alternatives.command == "alternatives"
    assert counties.command == "counties"
    assert live_probe.command == "probe"


def test_shared_validation_rejects_conflicting_or_non_montana_scope() -> None:
    conflicting = _parse(
        "manifest",
        "Petroleum",
        "--source",
        mt.SOURCE_ID,
        "--dataset-type",
        "parcel-shp",
        "--county",
        "Lincoln",
    )
    wrong_state = _parse(
        "owner",
        "SMITH",
        "--source",
        mt.SOURCE_ID,
        "--jurisdiction",
        "48201",
    )

    with pytest.raises(ValueError, match="selectors conflict"):
        query_property._montana_cadastral_args(conflicting, "manifest")
    with pytest.raises(ValueError, match="Montana context"):
        query_property._montana_cadastral_args(wrong_state, "owner")


def test_shared_execute_keeps_the_native_cursor_and_map_envelope(
    monkeypatch,
) -> None:
    observed = {}

    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == mt.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, source_id):
            assert source_id == mt.SOURCE_ID
            return {
                "allowed": True,
                "reason_code": "automated_access_supported",
            }

    def fake_execute(args, **_kwargs):
        observed["args"] = args
        result = PublicRecordsResult.success(
            mt.build_query(args),
            [
                {
                    "source_id": mt.SOURCE_ID,
                    "record_type": "parcel_feature_occurrence",
                    "source_record_id": "{feature-1}",
                    "geometry": {"rings": []},
                }
            ],
            next_cursor="mt-next",
            retrieved_at="2026-07-30T12:00:00Z",
        )
        observed["expected"] = result.to_dict()
        return result

    monkeypatch.setattr(query_property, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(mt, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "map",
            "56382732101040000",
            "--source",
            mt.SOURCE_ID,
            "--jurisdiction",
            "30069",
        )
    )

    assert observed["args"].command == "parcel"
    assert observed["args"].identifier == "56382732101040000"
    assert observed["args"].county == "30069"
    assert observed["args"].geometry is True
    assert payload == observed["expected"]
    assert payload["next_cursor"] == "mt-next"
