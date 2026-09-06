from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import yaml

from tools.public_records_bulk import ArtifactProbe
from tools.public_records_http import PaginatedFetch
from tools.query_massgis_property import (
    SOURCE_ID,
    build_parser,
    execute,
    normalize_manifest_feature,
)


FEATURE = {
    "attributes": {
        "OBJECTID": 310,
        "TOWN": "GOSNOLD",
        "TOWN_ID": 109,
        "SHAPE_LINK": (
            "https://s3.us-east-1.amazonaws.com/"
            "download.massgis.digital.mass.gov/shapefiles/l3parcels/"
            "L3_SHP_M109_GOSNOLD.zip"
        ),
        "FGDB_LINK": (
            "https://s3.us-east-1.amazonaws.com/"
            "download.massgis.digital.mass.gov/gdbs/l3parcels/"
            "M109_parcels_gdb.zip"
        ),
        "FY": 2024,
        "NOTE": None,
    }
}


class FakeManifestClient:
    def __init__(self, records=(FEATURE,)):
        self.records = records
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        return PaginatedFetch(
            records=self.records,
            next_cursor=None,
            schema={"kind": "arcgis_declared", "fields": []},
            schema_fingerprint="1" * 64,
            pages_fetched=1,
            requests_made=1,
        )


class FakeBulkClient:
    def __init__(self):
        self.probe_calls = []
        self.download_calls = []

    def probe(self, artifact, *, sample_bytes):
        self.probe_calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=200,
            content_length=216380,
            media_type="application/octet-stream",
            etag='"d497"',
            last_modified="Tue, 31 Mar 2026 15:20:06 GMT",
            accept_ranges=True,
            source_sha256="2" * 64,
            sample_size=sample_bytes,
            sample_sha256="3" * 64,
            signature_hex="504b0304",
            format_hint="zip",
        )

    def download(self, *args, **kwargs):
        self.download_calls.append((args, kwargs))
        raise AssertionError("dry-run must not download an artifact")


def no_log(monkeypatch):
    monkeypatch.setattr(
        "tools.query_massgis_property.log_search",
        lambda *_args, **_kwargs: None,
    )


def test_normalize_manifest_feature_builds_snapshot_and_fingerprints():
    record = normalize_manifest_feature(
        FEATURE,
        source_manifest_schema_fingerprint="1" * 64,
    )

    assert record["town"] == "GOSNOLD"
    assert record["assessor_fiscal_year"] == 2024
    assert record["release_kind"] == "snapshot"
    assert record["canonical_ref"].endswith("/M109%3AFY2024")
    manifest = record["manifest"]
    assert manifest["release"]["release_id"] == "M109:FY2024"
    assert {item["artifact_id"] for item in manifest["artifacts"]} == {
        "shapefile",
        "file_geodatabase",
    }
    assert len(manifest["manifest_fingerprint"]) == 64
    assert len(manifest["schema_fingerprint"]) == 64


def test_manifest_command_returns_canonical_envelope(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        ["manifest", "--town", "Gosnold", "--limit", "1"]
    )
    client = FakeManifestClient()

    result = execute(args, access_contract={}, manifest_client=client)

    assert result.status.value == "ok"
    assert result.records[0]["town"] == "GOSNOLD"
    assert client.calls[0]["where"] == "TOWN = 'GOSNOLD'"
    assert result.query.fingerprint


def test_probe_command_is_bounded_and_returns_source_metadata(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        ["probe", "--town", "GOSNOLD", "--range-bytes", "128"]
    )
    bulk = FakeBulkClient()

    result = execute(
        args,
        access_contract={},
        manifest_client=FakeManifestClient(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["probe"]["content_length"] == 216380
    assert result.records[0]["probe"]["format_hint"] == "zip"
    assert bulk.probe_calls[0][1] == 128


def test_download_dry_run_resolves_release_without_downloading(monkeypatch, tmp_path):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        [
            "download",
            "--town",
            "GOSNOLD",
            "--destination",
            str(tmp_path / "gosnold.zip"),
            "--dry-run",
        ]
    )
    bulk = FakeBulkClient()

    result = execute(
        args,
        access_contract={},
        manifest_client=FakeManifestClient(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["download"]["status"] == "planned"
    assert result.records[0]["download"]["resume"] is True
    assert bulk.download_calls == []


def test_local_inspect_command_uses_shared_archive_safety(monkeypatch, tmp_path):
    no_log(monkeypatch)
    archive = tmp_path / "parcel.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("parcel.shp", b"shape")
    args = build_parser().parse_args(["inspect", str(archive)])

    result = execute(args)

    assert result.status.value == "ok"
    assert result.records[0]["archive"]["member_count"] == 1
    assert (
        result.records[0]["archive"]["archive_sha256"]
        == hashlib.sha256(archive.read_bytes()).hexdigest()
    )


def test_tracked_massgis_source_has_factual_bulk_access_review():
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item for item in config["sources"] if item["source_id"] == SOURCE_ID
    )

    assert source["access_class"] == "A"
    assert source["automation_disposition"] == "allowed"
    assert source["source_status"] == "active"
    assert source["access_review"]["access_class"] == "A"
    assert source["access_review"]["automation_disposition"] == "allowed"
