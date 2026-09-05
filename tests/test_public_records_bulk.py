from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path
from urllib.error import HTTPError

import pytest

from tools.public_records_bulk import (
    ArchiveSafetyError,
    ArchiveSafetyPolicy,
    BulkArtifact,
    BulkDatasetManifest,
    BulkHTTPStatusError,
    BulkIntegrityError,
    BulkReleaseMetadata,
    BulkTransferClient,
    file_sha256,
    inspect_zip,
    safe_extract_zip,
)


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
    ):
        self._body = io.BytesIO(body)
        self.status = status
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def close(self) -> None:
        self._body.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class RecordingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, *, timeout):
        self.requests.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def make_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in members.items():
            archive.writestr(name, body)


def test_bulk_manifest_has_deterministic_schema_and_manifest_fingerprints():
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/M001.zip",
        archive_format="zip",
    )
    first = BulkDatasetManifest(
        source_id="us-ma-test",
        dataset_id="parcels",
        release=BulkReleaseMetadata(
            release_id="M001:FY2026",
            kind="snapshot",
            coverage={"town": "A", "fy": 2026},
        ),
        artifacts=[artifact],
        schema={"fields": {"B": "text", "A": "integer"}},
        metadata={"z": 2, "a": 1},
    )
    second = BulkDatasetManifest(
        source_id="us-ma-test",
        dataset_id="parcels",
        release=BulkReleaseMetadata(
            release_id="M001:FY2026",
            kind="snapshot",
            coverage={"fy": 2026, "town": "A"},
        ),
        artifacts=[artifact],
        schema={"fields": {"A": "integer", "B": "text"}},
        metadata={"a": 1, "z": 2},
    )

    assert first.schema_fingerprint == second.schema_fingerprint
    assert first.manifest_fingerprint == second.manifest_fingerprint
    assert first.to_dict()["release"]["kind"] == "snapshot"


def test_incremental_release_metadata_is_represented():
    release = BulkReleaseMetadata(
        release_id="delta-2",
        kind="incremental",
        base_release_id="snapshot-1",
        sequence=2,
    )
    assert release.to_dict() == {
        "release_id": "delta-2",
        "kind": "incremental",
        "effective_at": None,
        "base_release_id": "snapshot-1",
        "sequence": 2,
        "coverage": {},
    }


def test_probe_uses_head_and_bounded_range_and_reads_source_checksum():
    source_sha = "a" * 64
    opener = RecordingOpener(
        [
            FakeResponse(
                status=200,
                headers={
                    "Content-Length": "216380",
                    "Accept-Ranges": "bytes",
                    "ETag": '"v1"',
                    "X-Amz-Meta-Checksum-Sha256": source_sha,
                },
            ),
            FakeResponse(
                b"PK\x03\x04" + b"x" * 100,
                status=206,
                headers={"Content-Range": "bytes 0-15/216380"},
            ),
        ]
    )
    client = BulkTransferClient(opener=opener, sleeper=lambda _seconds: None)

    probe = client.probe("https://example.test/archive.zip", sample_bytes=16)

    assert probe.content_length == 216380
    assert probe.accept_ranges is True
    assert probe.source_sha256 == source_sha
    assert probe.sample_size == 16
    assert probe.format_hint == "zip"
    assert opener.requests[0][0].method == "HEAD"
    assert opener.requests[1][0].get_header("Range") == "bytes=0-15"


def test_probe_maps_http_status_to_explicit_error():
    error = HTTPError(
        "https://example.test/missing.zip",
        404,
        "missing",
        {},
        io.BytesIO(b"not found"),
    )
    client = BulkTransferClient(
        opener=RecordingOpener([error]),
        max_attempts=1,
    )

    with pytest.raises(BulkHTTPStatusError) as caught:
        client.probe("https://example.test/missing.zip", sample_bytes=0)

    assert caught.value.status_code == 404
    assert caught.value.result_status.value == "source_changed"


def test_download_computes_and_verifies_sha256(tmp_path):
    body = b"PK\x03\x04bulk fixture"
    digest = hashlib.sha256(body).hexdigest()
    opener = RecordingOpener(
        [
            FakeResponse(
                headers={
                    "Content-Length": str(len(body)),
                    "ETag": '"v1"',
                    "X-Amz-Meta-Checksum-Sha256": digest,
                }
            ),
            FakeResponse(body, headers={"Content-Length": str(len(body))}),
        ]
    )
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
    )
    destination = tmp_path / "archive.zip"

    result = BulkTransferClient(opener=opener).download(artifact, destination)

    assert destination.read_bytes() == body
    assert result.sha256 == digest
    assert result.expected_sha256 == digest
    assert result.resumed_from == 0
    assert not (tmp_path / "archive.zip.part").exists()
    assert not (tmp_path / "archive.zip.part.json").exists()


def test_download_resumes_validated_partial_transfer(tmp_path):
    full_body = b"hello world"
    digest = hashlib.sha256(full_body).hexdigest()
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
        expected_size=len(full_body),
        expected_sha256=digest,
    )
    destination = tmp_path / "archive.zip"
    partial = tmp_path / "archive.zip.part"
    state = tmp_path / "archive.zip.part.json"
    partial.write_bytes(b"hello ")
    state.write_text(
        json.dumps(
            {
                "url": artifact.url,
                "etag": '"v1"',
                "last_modified": None,
                "expected_size": len(full_body),
                "expected_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    opener = RecordingOpener(
        [
            FakeResponse(
                headers={
                    "Content-Length": str(len(full_body)),
                    "ETag": '"v1"',
                }
            ),
            FakeResponse(
                b"world",
                status=206,
                headers={"Content-Range": "bytes 6-10/11"},
            ),
        ]
    )

    result = BulkTransferClient(opener=opener).download(artifact, destination)

    assert destination.read_bytes() == full_body
    assert result.resumed_from == 6
    request = opener.requests[1][0]
    assert request.get_header("Range") == "bytes=6-"
    assert request.get_header("If-range") == '"v1"'


def test_checksum_mismatch_keeps_partial_for_diagnosis(tmp_path):
    body = b"wrong bytes"
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
        expected_size=len(body),
        expected_sha256="0" * 64,
    )
    opener = RecordingOpener(
        [
            FakeResponse(headers={"Content-Length": str(len(body))}),
            FakeResponse(body),
        ]
    )

    with pytest.raises(BulkIntegrityError):
        BulkTransferClient(opener=opener).download(
            artifact,
            tmp_path / "archive.zip",
        )

    assert (tmp_path / "archive.zip.part").read_bytes() == body
    assert not (tmp_path / "archive.zip").exists()


def test_existing_verified_download_is_reused(tmp_path):
    body = b"already present"
    destination = tmp_path / "archive.zip"
    destination.write_bytes(body)
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
        expected_size=len(body),
        expected_sha256=hashlib.sha256(body).hexdigest(),
    )
    opener = RecordingOpener(
        [FakeResponse(headers={"Content-Length": str(len(body))})]
    )

    result = BulkTransferClient(opener=opener).download(artifact, destination)

    assert result.reused_existing is True
    assert result.sha256 == file_sha256(destination)
    assert len(opener.requests) == 1


def test_existing_same_size_download_without_digest_is_refetched(tmp_path):
    destination = tmp_path / "archive.zip"
    destination.write_bytes(b"stale bytes")
    current_body = b"fresh bytes"
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
    )
    opener = RecordingOpener(
        [
            FakeResponse(headers={"Content-Length": str(len(current_body))}),
            FakeResponse(current_body),
        ]
    )

    result = BulkTransferClient(opener=opener).download(artifact, destination)

    assert destination.read_bytes() == current_body
    assert result.reused_existing is False
    assert result.resumed_from == 0
    assert len(opener.requests) == 2


def test_partial_without_digest_or_validator_restarts_from_zero(tmp_path):
    full_body = b"current publication"
    artifact = BulkArtifact.from_url(
        "shapefile",
        "https://example.test/archive.zip",
    )
    destination = tmp_path / "archive.zip"
    partial = tmp_path / "archive.zip.part"
    state = tmp_path / "archive.zip.part.json"
    partial.write_bytes(b"stale ")
    state.write_text(
        json.dumps(
            {
                "url": artifact.url,
                "etag": None,
                "last_modified": None,
                "expected_size": len(full_body),
                "expected_sha256": None,
            }
        ),
        encoding="utf-8",
    )
    opener = RecordingOpener(
        [
            FakeResponse(headers={"Content-Length": str(len(full_body))}),
            FakeResponse(full_body),
        ]
    )

    result = BulkTransferClient(opener=opener).download(artifact, destination)

    assert destination.read_bytes() == full_body
    assert result.resumed_from == 0
    request = opener.requests[1][0]
    assert request.get_header("Range") is None
    assert request.get_header("If-range") is None


def test_zip_inspection_fingerprints_schema_and_extracts_safely(tmp_path):
    archive = tmp_path / "parcels.zip"
    make_zip(
        archive,
        {
            "M109/L3_TAXPAR_POLY.shp": b"shape",
            "M109/L3_TAXPAR_POLY.dbf": b"table",
            "M109/readme.txt": b"metadata",
        },
    )

    inspection = inspect_zip(archive)
    extraction = safe_extract_zip(archive, tmp_path / "out")

    assert inspection.member_count == 3
    assert inspection.schema["shapefile_datasets"] == (
        "M109/L3_TAXPAR_POLY",
    )
    assert len(inspection.schema_fingerprint) == 64
    assert len(inspection.manifest_fingerprint) == 64
    assert (tmp_path / "out/M109/L3_TAXPAR_POLY.shp").read_bytes() == b"shape"
    assert extraction["extracted_members"] == [
        "M109/L3_TAXPAR_POLY.dbf",
        "M109/L3_TAXPAR_POLY.shp",
        "M109/readme.txt",
    ]


def test_zip_path_traversal_is_rejected(tmp_path):
    archive = tmp_path / "unsafe.zip"
    make_zip(archive, {"../outside.txt": b"escape"})

    with pytest.raises(ArchiveSafetyError):
        inspect_zip(archive)


def test_zip_symlink_is_rejected(tmp_path):
    archive = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(info, "../target")

    with pytest.raises(ArchiveSafetyError):
        inspect_zip(archive)


def test_archive_resource_policy_is_explicit_and_enforced(tmp_path):
    archive = tmp_path / "two.zip"
    make_zip(archive, {"a.txt": b"a", "b.txt": b"b"})
    policy = ArchiveSafetyPolicy(max_members=1)

    with pytest.raises(ArchiveSafetyError) as caught:
        inspect_zip(archive, policy=policy)

    assert caught.value.details["max_members"] == 1
