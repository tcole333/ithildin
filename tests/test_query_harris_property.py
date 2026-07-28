from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tools.public_records_bulk import ArtifactProbe, DownloadResult
from tools.public_records_http import RetryPolicy, SourceSchemaError, TransportError
from tools.query_harris_property import (
    CERTIFICATION_ENDPOINT,
    DOWNLOADS_ENDPOINT,
    SOURCE_ID,
    TAX_YEARS_ENDPOINT,
    HCADManifestClient,
    build_parser,
    execute,
    normalize_release,
)


FIXTURE_DIR = Path("tests/fixtures/public_records/harris")
FIXTURE = json.loads(
    (FIXTURE_DIR / "hcad_2026_release.json").read_text(encoding="utf-8")
)
GOLDEN = json.loads(
    (FIXTURE_DIR / "hcad_2026_release_golden.json").read_text(encoding="utf-8")
)


class FakeResponse:
    def __init__(self, payload, *, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


class FixtureTransport:
    def __init__(self, *, downloads=None, tax_years=None):
        self.downloads = (
            FIXTURE["real_property_downloads"]
            if downloads is None
            else downloads
        )
        self.tax_years = FIXTURE["tax_years"] if tax_years is None else tax_years
        self.calls = []

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        if url == TAX_YEARS_ENDPOINT:
            return FakeResponse(self.tax_years)
        if url == CERTIFICATION_ENDPOINT:
            return FakeResponse(FIXTURE["certification"])
        if url == DOWNLOADS_ENDPOINT:
            return FakeResponse(self.downloads)
        raise AssertionError(f"unexpected URL: {url}")


def fixture_client(transport=None):
    return HCADManifestClient(
        transport=transport or FixtureTransport(),
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )


class FakeBulkClient:
    def __init__(self):
        self.probe_calls = []
        self.download_calls = []

    def probe(self, artifact, *, sample_bytes):
        self.probe_calls.append((artifact, sample_bytes))
        return ArtifactProbe(
            url=artifact.url,
            http_status=206,
            content_length=210533035,
            media_type="application/x-zip-compressed",
            etag='"21b34a9451ddd1:0"',
            last_modified="Sun, 26 Jul 2026 21:28:11 GMT",
            accept_ranges=True,
            source_sha256=None,
            sample_size=sample_bytes,
            sample_sha256="3" * 64,
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
            size=210533035,
            sha256="4" * 64,
            expected_sha256=artifact.expected_sha256,
            etag='"21b34a9451ddd1:0"',
            last_modified="Sun, 26 Jul 2026 21:28:11 GMT",
            resumed_from=0,
            reused_existing=False,
        )


def no_log(monkeypatch):
    monkeypatch.setattr(
        "tools.query_harris_property.log_search",
        lambda *_args, **_kwargs: None,
    )


def normalized_fixture_release():
    client = fixture_client()
    certification = client.certification(2026)
    downloads = client.downloads(2026, "real-property")
    return normalize_release(2026, "real-property", certification, downloads)


def test_release_normalization_matches_golden_fingerprints_and_native_ids():
    record = normalized_fixture_release()
    manifest = record["manifest"]

    assert record["canonical_ref"] == GOLDEN["canonical_ref"]
    assert manifest["release"]["release_id"] == GOLDEN["release_id"]
    assert [item["artifact_id"] for item in manifest["artifacts"]] == (
        GOLDEN["artifact_ids"]
    )
    assert manifest["schema_fingerprint"] == GOLDEN["schema_fingerprint"]
    assert manifest["manifest_fingerprint"] == GOLDEN["manifest_fingerprint"]
    assert manifest["artifacts"][0]["metadata"]["native_tax_year"] == "2026"


def test_list_returns_every_published_year_without_local_truncation(monkeypatch):
    no_log(monkeypatch)
    transport = FixtureTransport()
    args = build_parser().parse_args(["list"])

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(transport),
    )

    assert result.status.value == "ok"
    assert [row["tax_year"] for row in result.records] == [2026, 2025, 2024]
    assert transport.calls[0]["params"] == {}


def test_manifest_uses_official_group_and_year_parameters(monkeypatch):
    no_log(monkeypatch)
    transport = FixtureTransport()
    args = build_parser().parse_args(
        ["manifest", "--year", "2026", "--group", "real-property"]
    )

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(transport),
    )

    assert result.status.value == "ok"
    assert result.records[0]["certification"]["certification_status"] == (
        "preliminary"
    )
    download_call = next(
        item for item in transport.calls if item["url"] == DOWNLOADS_ENDPOINT
    )
    assert download_call["params"] == {
        "t": 2026,
        "c": "CAMA",
        "s": "Real Property",
    }


def test_probe_reads_only_the_requested_sample(monkeypatch):
    no_log(monkeypatch)
    bulk = FakeBulkClient()
    args = build_parser().parse_args(
        [
            "probe",
            "--year",
            "2026",
            "--artifact",
            "Real_acct_owner",
            "--range-bytes",
            "512",
        ]
    )

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["probe"]["content_length"] == 210533035
    assert result.records[0]["probe"]["format_hint"] == "zip"
    assert bulk.probe_calls[0][1] == 512


def test_dry_run_never_starts_a_transfer(monkeypatch, tmp_path):
    no_log(monkeypatch)
    bulk = FakeBulkClient()
    destination = tmp_path / "Real_acct_owner.zip"
    args = build_parser().parse_args(
        [
            "dry-run",
            "--year",
            "2026",
            "--artifact",
            "Real_acct_owner.zip",
            "--destination",
            str(destination),
        ]
    )

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.records[0]["download"]["status"] == "planned"
    assert result.records[0]["download"]["destination"] == str(destination)
    assert bulk.download_calls == []


def test_download_uses_shared_transfer_and_preserves_expected_hash(
    monkeypatch,
    tmp_path,
):
    no_log(monkeypatch)
    bulk = FakeBulkClient()
    destination = tmp_path / "hcad.zip"
    expected = "a" * 64
    args = build_parser().parse_args(
        [
            "download",
            "--year",
            "2026",
            "--artifact",
            "Real_acct_owner.zip",
            "--destination",
            str(destination),
            "--expected-sha256",
            expected,
        ]
    )

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(),
        bulk_client=bulk,
    )

    assert result.status.value == "ok"
    assert result.raw_artifact_refs == (str(destination),)
    assert bulk.download_calls[0]["artifact"].expected_sha256 == expected
    assert result.records[0]["download"]["sha256"] == "4" * 64


def test_empty_official_manifest_is_no_results_not_a_failure(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(["manifest", "--year", "1900"])

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(FixtureTransport(downloads=[])),
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_unknown_artifact_selector_is_an_authoritative_empty_result(monkeypatch):
    no_log(monkeypatch)
    args = build_parser().parse_args(
        [
            "probe",
            "--year",
            "2026",
            "--artifact",
            "not-published.zip",
        ]
    )

    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=fixture_client(),
        bulk_client=FakeBulkClient(),
    )

    assert result.status.value == "no_results"
    assert result.errors == ()


def test_manifest_schema_drift_is_explicit():
    changed = [dict(FIXTURE["real_property_downloads"][0])]
    changed[0].pop("filename")
    client = fixture_client(FixtureTransport(downloads=changed))

    with pytest.raises(SourceSchemaError) as caught:
        client.downloads(2026, "real-property")

    assert caught.value.result_status.value == "source_changed"
    assert caught.value.details["fields"] == ["filename"]


def test_duplicate_release_year_is_explicit_schema_drift():
    client = fixture_client(
        FixtureTransport(
            tax_years=[{"taxyears": "2026"}, {"taxyears": "2026"}]
        )
    )

    with pytest.raises(SourceSchemaError):
        client.list_tax_years()


def test_transport_error_is_not_reported_as_no_results(monkeypatch):
    no_log(monkeypatch)

    class FailingClient:
        def list_tax_years(self):
            raise TransportError(
                "manifest unavailable",
                url=TAX_YEARS_ENDPOINT,
            )

    args = build_parser().parse_args(["list"])
    result = execute(
        args,
        access_contract={"allowed": True},
        manifest_client=FailingClient(),
    )

    assert result.status.value == "unavailable"
    assert result.records == ()
    assert result.errors[0].code == "transport_error"


def test_catalog_has_factual_hcad_bulk_review():
    config = yaml.safe_load(
        Path("config/public_records_sources.yaml").read_text(encoding="utf-8")
    )
    source = next(
        item for item in config["sources"] if item["source_id"] == SOURCE_ID
    )

    assert source["official_url"].startswith("https://hcad.org/pdata/")
    assert source["access_class"] == "A"
    assert source["automation_disposition"] == "allowed"
    assert source["authentication"] == "none"
    assert source["access_review"]["limits"] == {}
    assert source["probe_evidence"]["sample_bytes"] == 4096
    assert source["probe_evidence"]["signature_hex"] == "504b0304"


def test_direct_script_help_works():
    completed = subprocess.run(
        [sys.executable, "tools/query_harris_property.py", "--help"],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Harris Central Appraisal District" in completed.stdout
