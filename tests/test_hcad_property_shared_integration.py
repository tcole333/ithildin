from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_harris_property, query_property
from tools.public_records_contract import PublicRecordsResult
from tools.seed_public_records_catalog import seed_catalog


def _parse(*values: str):
    return query_property.build_parser().parse_args(list(values))


def test_shared_release_and_manifest_translate_hcad_native_scope() -> None:
    releases = _parse(
        "releases",
        "--source",
        query_property.HARRIS_SOURCE_ID,
    )
    manifest = _parse(
        "manifest",
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--jurisdiction",
        "48201",
        "--dataset-type",
        "real",
        "--tax-year",
        "2026",
    )

    translated_releases = query_property._hcad_property_args(
        releases,
        "list",
    )
    translated_manifest = query_property._hcad_property_args(
        manifest,
        "manifest",
    )

    assert translated_releases.command == "list"
    assert translated_manifest.command == "manifest"
    assert translated_manifest.year == 2026
    assert translated_manifest.group == "real-property"


def test_shared_probe_and_download_preserve_artifact_selector(
    tmp_path: Path,
) -> None:
    probe = _parse(
        "probe",
        "Real_acct_ownership_history.zip",
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--dataset-type",
        "real-property",
        "--tax-year",
        "2026",
        "--range-bytes",
        "2048",
    )
    destination = tmp_path / "owner.zip"
    download = _parse(
        "download",
        "Real_acct_owner.zip",
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--tax-year",
        "2026",
        "--destination",
        str(destination),
        "--no-resume",
        "--expected-sha256",
        "a" * 64,
        "--max-download-bytes",
        "220000000",
        "--chunk-size",
        "65536",
    )

    translated_probe = query_property._hcad_property_args(probe, "probe")
    translated_download = query_property._hcad_property_args(
        download,
        "download",
    )

    assert translated_probe.command == "probe"
    assert translated_probe.artifact == "Real_acct_ownership_history.zip"
    assert translated_probe.range_bytes == 2048
    assert translated_download.command == "download"
    assert translated_download.artifact == "Real_acct_owner.zip"
    assert translated_download.destination == str(destination)
    assert translated_download.resume is False
    assert translated_download.expected_sha256 == "a" * 64
    assert translated_download.max_download_bytes == 220_000_000
    assert translated_download.chunk_size == 65_536


def test_shared_hcad_routes_are_bulk_only_and_guidance_names_ingester() -> None:
    routes = query_property.LIVE_ROUTES[query_property.HARRIS_SOURCE_ID]
    guidance = query_property._source_guidance(query_property.HARRIS_SOURCE_ID)

    assert sorted(routes) == [
        "discovery",
        "download",
        "manifest",
        "probe",
        "releases",
    ]
    assert "parcel" not in routes
    assert "owner" not in routes
    assert guidance["mode"] == "unified_bulk_release"
    assert guidance["unified_operations"] == sorted(routes)
    assert "ingest_hcad_property.py" in guidance["archive_ingest"]


def test_shared_hcad_bulk_validation_requires_exact_release_inputs(
    tmp_path: Path,
) -> None:
    missing_year = _parse(
        "manifest",
        "--source",
        query_property.HARRIS_SOURCE_ID,
    )
    missing_artifact = _parse(
        "probe",
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--tax-year",
        "2026",
    )
    missing_destination = _parse(
        "download",
        "Real_acct_owner.zip",
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--tax-year",
        "2026",
    )

    with pytest.raises(ValueError, match="requires --tax-year"):
        query_property._hcad_property_args(missing_year, "manifest")
    with pytest.raises(ValueError, match="requires a published artifact"):
        query_property._hcad_property_args(missing_artifact, "probe")
    with pytest.raises(ValueError, match="requires --destination"):
        query_property._hcad_property_args(missing_destination, "download")


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
def test_shared_routes_invoke_truthful_hcad_direct_operation(
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
            query_harris_property.build_query(args),
            [],
        )

    monkeypatch.setattr(query_harris_property, "execute", fake_execute)
    monkeypatch.setattr(query_property, "log_search", lambda *_args: None)
    argv = [
        operation,
        "--source",
        query_property.HARRIS_SOURCE_ID,
        "--catalog-db",
        str(catalog_path),
    ]
    if operation in {"manifest", "probe", "download"}:
        argv.extend(["--tax-year", "2026"])
    if operation in {"probe", "download"}:
        argv.insert(1, "Real_acct_owner.zip")
    if operation == "download":
        argv.extend(["--destination", str(tmp_path / "owner.zip")])

    payload = query_property.execute(_parse(*argv))

    assert payload["status"] == "no_results"
    assert calls[0].command == direct_command
