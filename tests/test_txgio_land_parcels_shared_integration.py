from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_property
from tools import query_txgio_land_parcels as txgio
from tools.public_records_contract import PublicRecordsResult


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_routes_separate_bulk_acquisition_from_local_archive_scan() -> None:
    routes = query_property.LIVE_ROUTES[txgio.SOURCE_ID]
    guidance = query_property._source_guidance(txgio.SOURCE_ID)

    assert sorted(routes) == [
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
    assert "account" not in routes
    assert guidance["mode"] == (
        "unified_bulk_release_and_local_archive_scan"
    )
    assert guidance["unified_operations"] == sorted(routes)
    assert "not an indexed statewide service" in guidance["note"]
    assert "without decoding or projecting coordinates" in guidance["note"]


@pytest.mark.parametrize(
    ("operation", "expected_field", "expected_match"),
    [
        ("search", "legal", "contains"),
        ("owner", "owner", "contains"),
        ("address", "address", "contains"),
        ("parcel", "parcel", "exact"),
        ("map", "parcel", "exact"),
    ],
)
def test_shared_local_routes_preserve_artifact_scan_semantics(
    operation: str,
    expected_field: str,
    expected_match: str,
) -> None:
    values = [
        operation,
        "RANCH" if operation != "parcel" else "131-0001",
        "--source",
        txgio.SOURCE_ID,
        "--jurisdiction",
        "48",
        "--artifact-path",
        "/tmp/txgio-kenedy.zip",
        "--limit",
        "7",
        "--cursor",
        "cursor-1",
    ]
    if operation == "search":
        values.extend(["--search-field", "legal"])

    translated = query_property._txgio_land_parcel_args(
        _parse(*values),
        "search",
    )

    assert translated.command == "search"
    assert translated.artifact == "/tmp/txgio-kenedy.zip"
    assert translated.field == expected_field
    assert translated.match == expected_match
    assert translated.limit == 7
    assert translated.cursor == "cursor-1"


def test_shared_manifest_preserves_historical_collection_and_scope() -> None:
    collection_id = "d0f7da13-ab09-4994-a16f-d52589e2476e"
    county = query_property._txgio_land_parcel_args(
        _parse(
            "manifest",
            "--source",
            txgio.SOURCE_ID,
            "--jurisdiction",
            "48",
            "--collection-id",
            collection_id,
            "--county",
            "Kenedy County",
        ),
        "manifest",
    )
    statewide = query_property._txgio_land_parcel_args(
        _parse(
            "probe",
            "Texas",
            "--source",
            txgio.SOURCE_ID,
            "--collection-id",
            collection_id,
            "--range-bytes",
            "1024",
        ),
        "probe",
    )
    county_geoid = query_property._txgio_land_parcel_args(
        _parse(
            "probe",
            "--source",
            txgio.SOURCE_ID,
            "--jurisdiction",
            "48261",
        ),
        "probe",
    )

    assert county.command == "manifest"
    assert county.collection_id == collection_id
    assert county.county == "Kenedy County"
    assert statewide.command == "probe"
    assert statewide.collection_id == collection_id
    assert statewide.county == "Texas"
    assert statewide.sample_bytes == 1024
    assert county_geoid.county == "48261"


def test_shared_download_preserves_statewide_archive_and_transfer_options(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "texas-parcels.zip"
    translated = query_property._txgio_land_parcel_args(
        _parse(
            "download",
            "--source",
            txgio.SOURCE_ID,
            "--county",
            "48",
            "--destination",
            str(destination),
            "--no-resume",
            "--expected-sha256",
            "a" * 64,
            "--max-download-bytes",
            "3000000000",
            "--chunk-size",
            "65536",
        ),
        "download",
    )

    assert translated.command == "download"
    assert translated.county == "48"
    assert translated.destination == str(destination)
    assert translated.resume is False
    assert translated.expected_sha256 == "a" * 64
    assert translated.max_download_bytes == 3_000_000_000
    assert translated.chunk_size == 65_536


def test_shared_txgio_validation_rejects_unrepresented_scope() -> None:
    missing_artifact = _parse(
        "owner",
        "SMITH",
        "--source",
        txgio.SOURCE_ID,
    )
    missing_county = _parse(
        "probe",
        "--source",
        txgio.SOURCE_ID,
        "--jurisdiction",
        "48",
    )
    conflicting_counties = _parse(
        "manifest",
        "Kenedy",
        "--source",
        txgio.SOURCE_ID,
        "--county",
        "King",
    )

    with pytest.raises(ValueError, match="--artifact-path"):
        query_property._txgio_land_parcel_args(
            missing_artifact,
            "search",
        )
    with pytest.raises(ValueError, match="requires --county"):
        query_property._txgio_land_parcel_args(
            missing_county,
            "probe",
        )
    with pytest.raises(ValueError, match="selectors conflict"):
        query_property._txgio_land_parcel_args(
            conflicting_counties,
            "manifest",
        )


def test_shared_execute_keeps_direct_local_raw_envelope(
    monkeypatch,
) -> None:
    decision = {
        "allowed": True,
        "reason_code": "automated_access_supported",
    }
    observed = {}

    class FakeCatalog:
        def __init__(self, _path):
            pass

        def show_source(self, source_id):
            assert source_id == txgio.SOURCE_ID
            return {"source_id": source_id}

        def machine_acquisition_decision(self, source_id):
            assert source_id == txgio.SOURCE_ID
            return decision

    def fake_execute(args, *, access_contract=None, **_kwargs):
        observed["args"] = args
        observed["access_contract"] = access_contract
        result = PublicRecordsResult.success(
            txgio.build_query(args),
            [
                {
                    "source_id": txgio.SOURCE_ID,
                    "record_kind": "parcel_assessment_geometry_snapshot",
                    "feature_ref": "property:txgio:feature:1",
                }
            ],
            next_cursor="txgio-next",
            retrieved_at="2026-07-30T12:00:00Z",
            raw_artifact_refs=["/tmp/txgio-kenedy.zip"],
        )
        observed["expected"] = result.to_dict()
        return result

    monkeypatch.setattr(query_property, "PublicRecordsCatalog", FakeCatalog)
    monkeypatch.setattr(txgio, "execute", fake_execute)

    payload = query_property.execute(
        _parse(
            "owner",
            "KING RANCH",
            "--source",
            txgio.SOURCE_ID,
            "--artifact-path",
            "/tmp/txgio-kenedy.zip",
        )
    )

    assert observed["args"].command == "search"
    assert observed["args"].field == "owner"
    assert observed["access_contract"] is decision
    assert payload == observed["expected"]
    assert payload["raw_artifact_refs"] == ["/tmp/txgio-kenedy.zip"]

