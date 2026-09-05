from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_hcad_gis as hcad_gis
from tools import query_property
from tools.public_records_contract import PublicRecordsResult


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_cover_bulk_and_queryable_representations() -> None:
    routes = query_property.LIVE_ROUTES[hcad_gis.SOURCE_ID]
    guidance = query_property._source_guidance(hcad_gis.SOURCE_ID)

    assert sorted(routes) == [
        "account",
        "address",
        "discovery",
        "download",
        "manifest",
        "map",
        "owner",
        "parcel",
        "probe",
        "releases",
        "search",
    ]
    assert guidance["mode"] == "unified_bulk_release_and_live_mapserver"
    assert guidance["unified_operations"] == sorted(routes)
    assert "separate freshness" in guidance["note"]
    assert "public_records_filegdb.py" in guidance["note"]
    assert "native-FID features" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "adapter_command", "expected_field", "geometry"),
    [
        ("search", "search", "legal", False),
        ("owner", "search", "owner", False),
        ("address", "search", "address", False),
        ("account", "account", "account", False),
        ("parcel", "account", "account", False),
        ("map", "account", "account", True),
    ],
)
def test_shared_live_routes_preserve_query_and_cursor_semantics(
    operation: str,
    adapter_command: str,
    expected_field: str,
    geometry: bool,
) -> None:
    values = [
        operation,
        "LT 749" if operation == "search" else "1144740190749",
        "--source",
        hcad_gis.SOURCE_ID,
        "--jurisdiction",
        "48201",
        "--limit",
        "7",
        "--cursor",
        "cursor-1",
        "--page-size",
        "19",
    ]
    if operation == "search":
        values.extend(["--search-field", "legal"])

    translated = query_property._hcad_gis_args(
        _parse(*values),
        adapter_command,
    )

    assert translated.command == adapter_command
    assert translated.query in {"LT 749", "1144740190749"}
    assert translated.field == expected_field
    assert translated.limit == 7
    assert translated.cursor == "cursor-1"
    assert translated.page_size == 19
    assert translated.geometry is geometry


def test_shared_historical_manifest_and_transfer_options(
    tmp_path: Path,
) -> None:
    manifest = query_property._hcad_gis_args(
        _parse(
            "manifest",
            "Parcels_2024_Oct.zip",
            "--source",
            hcad_gis.SOURCE_ID,
            "--tax-year",
            "2024",
        ),
        "manifest",
    )
    probe = query_property._hcad_gis_args(
        _parse(
            "probe",
            "--source",
            hcad_gis.SOURCE_ID,
            "--tax-year",
            "2025",
            "--range-bytes",
            "1024",
        ),
        "probe",
    )
    destination = tmp_path / "hcad-parcels.zip"
    download = query_property._hcad_gis_args(
        _parse(
            "download",
            "Parcels.zip",
            "--source",
            hcad_gis.SOURCE_ID,
            "--destination",
            str(destination),
            "--no-resume",
            "--expected-sha256",
            "a" * 64,
            "--max-download-bytes",
            "300000000",
            "--chunk-size",
            "65536",
        ),
        "download",
    )

    assert manifest.command == "manifest"
    assert manifest.year == 2024
    assert manifest.artifact_name == "Parcels_2024_Oct.zip"
    assert probe.command == "probe"
    assert probe.year == 2025
    assert probe.artifact_name is None
    assert probe.sample_bytes == 1024
    assert download.command == "download"
    assert download.artifact_name == "Parcels.zip"
    assert download.destination == str(destination)
    assert download.resume is False
    assert download.expected_sha256 == "a" * 64
    assert download.max_download_bytes == 300_000_000
    assert download.chunk_size == 65_536


def test_shared_hcad_gis_validation_rejects_mismatched_scope() -> None:
    wrong_county = _parse(
        "owner",
        "SMITH",
        "--source",
        hcad_gis.SOURCE_ID,
        "--county",
        "Dallas",
    )
    dated_live_query = _parse(
        "parcel",
        "1144740190749",
        "--source",
        hcad_gis.SOURCE_ID,
        "--tax-year",
        "2024",
    )
    local_artifact = _parse(
        "search",
        "WOODSMAN",
        "--source",
        hcad_gis.SOURCE_ID,
        "--artifact-path",
        "/tmp/hcad.zip",
    )

    with pytest.raises(ValueError, match="Harris County"):
        query_property._hcad_gis_args(wrong_county, "search")
    with pytest.raises(ValueError, match="current published"):
        query_property._hcad_gis_args(dated_live_query, "account")
    with pytest.raises(ValueError, match="direct adapter"):
        query_property._hcad_gis_args(local_artifact, "search")


def test_shared_execute_passes_catalog_contract_and_map_geometry(
    monkeypatch,
) -> None:
    decision = {
        "allowed": True,
        "reason_code": "automated_access_supported",
        "limits": {"maximum_page_size": 100},
    }
    observed = {}

    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == hcad_gis.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, source_id):
            assert source_id == hcad_gis.SOURCE_ID
            return decision

    def fake_execute(args, *, access_contract=None, **_kwargs):
        observed["args"] = args
        observed["access_contract"] = access_contract
        result = PublicRecordsResult.success(
            hcad_gis.build_query(args),
            [
                {
                    "source_id": hcad_gis.SOURCE_ID,
                    "record_kind": "parcel_assessment_geometry_snapshot",
                    "feature_ref": "property:hcad-gis:feature:1",
                    "geometry": {"rings": []},
                }
            ],
            retrieved_at="2026-07-30T12:00:00Z",
        )
        observed["expected"] = result.to_dict()
        return result

    monkeypatch.setattr(query_property, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(hcad_gis, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "map",
            "1144740190749",
            "--source",
            hcad_gis.SOURCE_ID,
        )
    )

    assert observed["args"].command == "account"
    assert observed["args"].geometry is True
    assert observed["access_contract"] is decision
    assert payload == observed["expected"]
