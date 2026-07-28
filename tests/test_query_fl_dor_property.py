from __future__ import annotations

from pathlib import Path

import yaml

from tools.public_records_bulk import ArtifactProbe, DownloadResult
from tools.query_fl_dor_property import (
    MAP_DATA_ROOT,
    SOURCE_ID,
    TAX_ROLL_ROOT,
    FloridaDORDirectoryClient,
    build_parser,
    execute,
)


NAL_RELEASE = {
    "Name": "2026P",
    "ServerRelativeUrl": f"{TAX_ROLL_ROOT}/NAL/2026P",
    "TimeLastModified": "2026-07-27T11:08:03Z",
    "ItemCount": 67,
}
SDF_RELEASE = {
    "Name": "2026P",
    "ServerRelativeUrl": f"{TAX_ROLL_ROOT}/SDF/2026P",
    "TimeLastModified": "2026-07-27T11:04:12Z",
    "ItemCount": 67,
}
GIS_RELEASE = {
    "Name": "2026F",
    "ServerRelativeUrl": f"{MAP_DATA_ROOT}/2026F",
    "TimeLastModified": "2026-04-28T14:00:31Z",
    "ItemCount": 2,
}
GIS_PIN_FOLDER = {
    "Name": "2026F PIN",
    "ServerRelativeUrl": f"{MAP_DATA_ROOT}/2026F/2026F PIN",
    "TimeLastModified": "2026-05-01T15:39:20Z",
    "ItemCount": 69,
}
GIS_PAR_FOLDER = {
    "Name": "2026F PAR",
    "ServerRelativeUrl": f"{MAP_DATA_ROOT}/2026F/2026F PAR",
    "TimeLastModified": "2026-04-28T14:00:16Z",
    "ItemCount": 0,
}
NAL_FILES = [
    {
        "Name": "Baker 12 Preliminary NAL 2026.zip",
        "ServerRelativeUrl": (
            f"{TAX_ROLL_ROOT}/NAL/2026P/"
            "Baker 12 Preliminary NAL 2026.zip"
        ),
        "TimeLastModified": "2026-07-27T11:05:21Z",
        "Length": "1080740",
    },
    {
        "Name": "Broward Preliminary NAL 2026.zip",
        "ServerRelativeUrl": (
            f"{TAX_ROLL_ROOT}/NAL/2026P/"
            "Broward Preliminary NAL 2026.zip"
        ),
        "TimeLastModified": "2026-07-27T11:05:30Z",
        "Length": "100",
    },
    {
        "Name": "Seminole 58 Preliminary NAL 2026.zip",
        "ServerRelativeUrl": (
            f"{TAX_ROLL_ROOT}/NAL/2026P/"
            "Seminole 58 Preliminary NAL 2026.zip"
        ),
        "TimeLastModified": "2026-07-27T11:07:30Z",
        "Length": "200",
    },
]
SDF_FILES = [
    {
        "Name": "Baker 12 Preliminary SDF 2026.zip",
        "ServerRelativeUrl": (
            f"{TAX_ROLL_ROOT}/SDF/2026P/"
            "Baker 12 Preliminary SDF 2026.zip"
        ),
        "TimeLastModified": "2026-07-27T11:03:39Z",
        "Length": "40698",
    }
]
GIS_PIN_FILES = [
    {
        "Name": "baker_2026pin.zip",
        "ServerRelativeUrl": (
            f"{MAP_DATA_ROOT}/2026F/2026F PIN/baker_2026pin.zip"
        ),
        "TimeLastModified": "2026-04-28T20:30:17Z",
        "Length": "2263260",
    },
    {
        "Name": "manatee_2026pin.shp.zip",
        "ServerRelativeUrl": (
            f"{MAP_DATA_ROOT}/2026F/2026F PIN/manatee_2026pin.shp.zip"
        ),
        "TimeLastModified": "2026-04-28T20:30:20Z",
        "Length": "123456",
    },
    {
        "Name": "miamidade_condos_2026.zip",
        "ServerRelativeUrl": (
            f"{MAP_DATA_ROOT}/2026F/2026F PIN/"
            "miamidade_condos_2026.zip"
        ),
        "TimeLastModified": "2026-04-29T13:50:13Z",
        "Length": "78143264",
    },
]


class FakeDirectoryClient:
    def __init__(self):
        self.folder_calls = []
        self.file_calls = []

    def list_folders(self, path):
        self.folder_calls.append(path)
        return {
            f"{TAX_ROLL_ROOT}/NAL": [NAL_RELEASE],
            f"{TAX_ROLL_ROOT}/SDF": [SDF_RELEASE],
            MAP_DATA_ROOT: [GIS_RELEASE],
            f"{MAP_DATA_ROOT}/2026F": [GIS_PAR_FOLDER, GIS_PIN_FOLDER],
        }.get(path, [])

    def list_files(self, path):
        self.file_calls.append(path)
        return {
            NAL_RELEASE["ServerRelativeUrl"]: NAL_FILES,
            SDF_RELEASE["ServerRelativeUrl"]: SDF_FILES,
            GIS_PIN_FOLDER["ServerRelativeUrl"]: GIS_PIN_FILES,
            GIS_PAR_FOLDER["ServerRelativeUrl"]: [],
        }.get(path, [])


class FakeBulkClient:
    def __init__(self):
        self.probe_calls = []
        self.download_calls = []

    def probe(self, artifact, *, sample_bytes):
        self.probe_calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=200,
            content_length=artifact.expected_size,
            media_type="application/x-zip-compressed",
            etag='"fixture"',
            last_modified=artifact.last_modified,
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="a" * 64,
            signature_hex="504b0304",
            format_hint="zip",
        )

    def download(self, artifact, destination, *, resume, max_bytes):
        self.download_calls.append(
            {
                "artifact": artifact,
                "destination": destination,
                "resume": resume,
                "max_bytes": max_bytes,
            }
        )
        return DownloadResult(
            path=str(destination),
            url=artifact.url,
            size=artifact.expected_size,
            sha256="b" * 64,
            expected_sha256=artifact.expected_sha256,
            etag='"fixture"',
            last_modified=artifact.last_modified,
            resumed_from=0,
            reused_existing=False,
        )


def no_log(monkeypatch):
    monkeypatch.setattr(
        "tools.query_fl_dor_property.log_search",
        lambda *_args, **_kwargs: None,
    )


def test_sharepoint_directory_url_preserves_query_fields():
    url = FloridaDORDirectoryClient._collection_url(
        f"{TAX_ROLL_ROOT}/NAL",
        "Folders",
    )

    assert "PTO%20Data%20Portal" in url
    assert "/Folders?$select=" in url
    assert "$orderby=Name" in url


def test_metadata_commands_have_no_default_record_ceiling():
    parser = build_parser()

    assert parser.parse_args(["list"]).limit is None
    assert parser.parse_args(["manifest"]).limit is None


def test_list_reports_current_release_directories_and_fingerprints(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(["list", "--type", "gis-pin", "--year", "2026"])

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    release = result.records[0]
    assert release["release_id"] == "gis-pin:2026F"
    assert release["artifact_count"] == 69
    assert len(release["release_fingerprint"]) == 64
    assert release["schema"]["minimum_fields"][2]["name"] == "PARCELNO"


def test_manifest_filters_county_and_builds_bulk_fingerprints(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        [
            "manifest",
            "--type",
            "sdf",
            "--county",
            "12",
            "--year",
            "2026",
        ]
    )

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["county_name"] == "Baker"
    assert record["county_dor_number"] == 12
    assert record["dataset_type"] == "sdf"
    assert record["manifest"]["release"]["release_id"] == "sdf:2026P:12:sdf"
    assert len(record["manifest"]["schema_fingerprint"]) == 64
    assert len(record["manifest"]["manifest_fingerprint"]) == 64
    assert (
        record["manifest"]["schema"]["fields"][12]["name"]
        == "CLERK_INSTRUMENT_NUMBER"
    )
    assert record["manifest"]["metadata"]["source_omissions"][
        "representation"
    ] == "publisher_omitted_records_remain_absent"


def test_published_filename_anomalies_are_preserved_not_silently_adopted(
    monkeypatch,
):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        ["manifest", "--type", "nal", "--year", "2026"]
    )

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
    )
    by_county = {record["county_name"]: record for record in result.records}

    assert by_county["Broward"]["county_dor_number"] == 16
    assert by_county["Broward"]["published_filename_county_number"] is None
    assert (
        by_county["Broward"]["published_filename_county_number_matches"] is None
    )
    assert by_county["Seminole"]["county_dor_number"] == 69
    assert by_county["Seminole"]["published_filename_county_number"] == 58
    assert (
        by_county["Seminole"]["published_filename_county_number_matches"]
        is False
    )


def test_gis_manifest_represents_related_tables_separately(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        ["manifest", "--type", "gis-pin", "--year", "2026"]
    )

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
    )
    roles = {record["artifact_role"] for record in result.records}

    assert roles == {"gis-pin", "gis-pin-related-table"}
    assert any(record["county_name"] == "Manatee" for record in result.records)
    related = next(
        record
        for record in result.records
        if record["artifact_role"] == "gis-pin-related-table"
    )
    assert related["county_name"] == "Dade"


def test_probe_is_bounded_and_returns_structured_artifact_metadata(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        [
            "probe",
            "--type",
            "sdf",
            "--county",
            "Baker",
            "--year",
            "2026",
            "--range-bytes",
            "256",
        ]
    )
    bulk = FakeBulkClient()

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["probe"]["sample_size"] == 256
    assert result.records[0]["probe"]["format_hint"] == "zip"
    assert bulk.probe_calls[0][1] == 256


def test_dry_run_resolves_download_without_transfer(monkeypatch, tmp_path):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        [
            "dry-run",
            "--type",
            "nal",
            "--county",
            "12",
            "--year",
            "2026",
            "--destination",
            str(tmp_path),
        ]
    )
    bulk = FakeBulkClient()

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["download"]["status"] == "planned"
    assert result.records[0]["download"]["resume"] is True
    assert bulk.download_calls == []


def test_empty_published_directory_is_authoritative_no_results(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        ["manifest", "--type", "gis-par", "--year", "2026"]
    )

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
    )

    assert result.status.value == "no_results"
    assert "currently contains no artifacts" in result.warnings[0]


def test_download_uses_shared_resumable_transfer(monkeypatch, tmp_path):
    no_log(monkeypatch)
    destination = tmp_path / "baker.zip"
    args = build_parser().parse_args(
        [
            "download",
            "--type",
            "sdf",
            "--county",
            "12",
            "--year",
            "2026",
            "--destination",
            str(destination),
            "--max-download-bytes",
            "50000",
        ]
    )
    bulk = FakeBulkClient()
    monkeypatch.setattr(
        "tools.query_fl_dor_property.inspect_zip",
        lambda path: type(
            "Inspection",
            (),
            {"to_dict": lambda self: {"path": str(path)}},
        )(),
    )

    result = execute(
        args,
        access_contract={},
        directory_client=FakeDirectoryClient(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert bulk.download_calls == [
        {
            "artifact": bulk.download_calls[0]["artifact"],
            "destination": str(destination),
            "resume": True,
            "max_bytes": 50000,
        }
    ]
    assert result.records[0]["download"]["sha256"] == "b" * 64


def test_tracked_source_has_verified_public_bulk_review():
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item for item in config["sources"] if item["source_id"] == SOURCE_ID
    )

    assert source["platform_family"] == "official_sharepoint_bulk"
    assert source["access_class"] == "A"
    assert source["automation_disposition"] == "allowed"
    assert source["authentication"] == "none"
    assert source["fees"] == "none"
    assert source["source_status"] == "active"
    assert source["access_review"]["access_class"] == "A"
    assert source["access_review"]["automation_disposition"] == "allowed"
