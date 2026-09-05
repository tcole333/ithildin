from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools import query_fl_dor_property, query_property
from tools.public_records_contract import PublicRecordsResult
from tools.seed_public_records_catalog import seed_catalog


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_parser_exposes_explicit_bulk_options_without_default_ceiling() -> None:
    releases = _parse(
        "releases",
        "--source",
        query_property.FL_SOURCE_ID,
        "--dataset-type",
        "nal",
        "--tax-year",
        "2026",
    )
    manifest = _parse(
        "manifest",
        "--source",
        query_property.FL_SOURCE_ID,
        "--dataset-type",
        "sdf",
        "--county",
        "Baker",
        "--tax-year",
        "2026",
    )

    translated_releases = query_property._fl_dor_property_args(
        releases,
        "list",
    )
    translated_manifest = query_property._fl_dor_property_args(
        manifest,
        "manifest",
    )

    assert translated_releases.command == "list"
    assert translated_releases.dataset_type == "nal"
    assert translated_releases.limit is None
    assert translated_manifest.command == "manifest"
    assert translated_manifest.county == "12"
    assert translated_manifest.limit is None


def test_shared_probe_and_download_translate_source_neutral_bulk_selectors(
    tmp_path: Path,
) -> None:
    probe = _parse(
        "probe",
        "--source",
        query_property.FL_SOURCE_ID,
        "--dataset-type",
        "gis-pin",
        "--county",
        "12003",
        "--tax-year",
        "2026",
        "--range-bytes",
        "512",
    )
    destination = tmp_path / "baker.zip"
    download = _parse(
        "download",
        "--source",
        query_property.FL_SOURCE_ID,
        "--dataset-type",
        "nal",
        "--county-code",
        "003",
        "--tax-year",
        "2026",
        "--destination",
        str(destination),
        "--no-resume",
        "--expected-sha256",
        "a" * 64,
        "--max-download-bytes",
        "2000000",
        "--chunk-size",
        "65536",
    )

    translated_probe = query_property._fl_dor_property_args(probe, "probe")
    translated_download = query_property._fl_dor_property_args(
        download,
        "download",
    )

    assert translated_probe.command == "probe"
    assert translated_probe.county == "12"
    assert translated_probe.range_bytes == 512
    assert translated_download.command == "download"
    assert translated_download.destination == str(destination)
    assert translated_download.resume is False
    assert translated_download.expected_sha256 == "a" * 64
    assert translated_download.max_download_bytes == 2_000_000
    assert translated_download.chunk_size == 65_536


def test_shared_download_requires_destination_and_does_not_overload_parcel() -> None:
    missing_destination = _parse(
        "download",
        "--source",
        query_property.FL_SOURCE_ID,
        "--dataset-type",
        "nal",
        "--county",
        "Baker",
    )
    parcel = _parse(
        "parcel",
        "011S20000000000032",
        "--source",
        query_property.FL_SOURCE_ID,
    )

    with pytest.raises(ValueError, match="requires --destination"):
        query_property._fl_dor_property_args(
            missing_destination,
            "download",
        )
    assert "parcel" not in query_property.LIVE_ROUTES[query_property.FL_SOURCE_ID]
    assert parcel.query == "011S20000000000032"


def test_guidance_reports_exact_bulk_operations_and_archive_ingester() -> None:
    guidance = query_property._source_guidance(query_property.FL_SOURCE_ID)

    assert guidance["mode"] == "unified_bulk_release"
    assert guidance["unified_operations"] == [
        "discovery",
        "download",
        "manifest",
        "probe",
        "releases",
    ]
    assert "query_fl_dor_property.py" in guidance["direct_tool"]
    assert "ingest_fl_dor_property.py" in guidance["archive_ingest"]


@pytest.mark.parametrize(
    ("operation", "direct_command"),
    [
        ("releases", "list"),
        ("discovery", "list"),
        ("manifest", "manifest"),
        ("probe", "probe"),
        ("download", "download"),
    ],
)
def test_shared_routes_invoke_the_truthful_direct_operation(
    tmp_path: Path,
    monkeypatch,
    operation: str,
    direct_command: str,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    calls = []

    def fake_execute(args, **_kwargs):
        calls.append(args)
        return PublicRecordsResult.success(
            query_fl_dor_property.build_query(args),
            [],
        )

    monkeypatch.setattr(query_fl_dor_property, "execute", fake_execute)
    monkeypatch.setattr(query_property, "log_search", lambda *_args: None)
    argv = [
        operation,
        "--source",
        query_property.FL_SOURCE_ID,
        "--catalog-db",
        str(catalog_path),
        "--dataset-type",
        "nal",
        "--tax-year",
        "2026",
    ]
    if operation in {"manifest", "probe", "download"}:
        argv.extend(["--county", "Baker"])
    if operation == "download":
        argv.extend(["--destination", str(tmp_path / "baker.zip")])

    payload = query_property.execute(_parse(*argv))

    assert payload["status"] == "no_results"
    assert calls[0].command == direct_command


def test_shared_ingest_preserves_manifest_snapshot_without_parcel_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    catalog_path = tmp_path / "catalog.db"
    property_path = tmp_path / "property.db"
    seed_catalog(db_path=catalog_path)

    def fake_execute(args, **_kwargs):
        return PublicRecordsResult.success(
            query_fl_dor_property.build_query(args),
            [
                {
                    "canonical_ref": "property:us-fl-dor-property-roll:12:bulk:fixture",
                    "dataset_type": "nal",
                    "county_name": "Baker",
                    "county_dor_number": 12,
                    "assessment_year": 2026,
                    "manifest": {
                        "manifest_fingerprint": "b" * 64,
                        "artifacts": [
                            {
                                "filename": "Baker 12 Preliminary NAL 2026.zip",
                                "expected_size": 1080740,
                            }
                        ],
                    },
                }
            ],
        )

    monkeypatch.setattr(query_fl_dor_property, "execute", fake_execute)
    monkeypatch.setattr(query_property, "log_search", lambda *_args: None)

    payload = query_property.execute(
        _parse(
            "manifest",
            "--source",
            query_property.FL_SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--property-db",
            str(property_path),
            "--dataset-type",
            "nal",
            "--county",
            "Baker",
            "--ingest",
        )
    )

    assert payload["status"] == "ok"
    assert payload["ingest"]["records_seen"] == 1
    assert payload["ingest"]["records_ingested"] == 0
    assert payload["ingest"]["records_preserved_without_projection"] == 1
    assert payload["ingest"]["projection_supported"] is False

    db = sqlite3.connect(property_path)
    try:
        assert (
            db.execute(
                """
                SELECT COUNT(*) FROM source_observation
                WHERE source_id=? AND record_kind='query_envelope'
                """,
                (query_property.FL_SOURCE_ID,),
            ).fetchone()[0]
            == 1
        )
        assert db.execute("SELECT COUNT(*) FROM parcel_snapshot").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM sale_event").fetchone()[0] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM parcel_geometry").fetchone()[0]
            == 0
        )
    finally:
        db.close()
