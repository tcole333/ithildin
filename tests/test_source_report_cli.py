from __future__ import annotations

import sys
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.public_records_catalog import PublicRecordsCatalog
from tools import source_report


SOURCES = {
    "Example source": {
        "status": "available",
        "description": "Deterministic test source",
        "query_tool": "tools/query_example.py",
        "records": 3,
    }
}


def test_explicit_report_command_prints_coverage(monkeypatch, capsys):
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.setattr(source_report, "generate_report", lambda: SOURCES)
    monkeypatch.setattr("sys.argv", ["source_report.py", "report"])

    source_report.main()

    output = capsys.readouterr().out
    assert "OSINT DATA SOURCE REPORT" in output
    assert "Example source (3 records)" in output
    assert "Sources available: 1/1" in output


def test_bare_invocation_remains_report_alias(monkeypatch, capsys):
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.setattr(source_report, "generate_report", lambda: SOURCES)
    monkeypatch.setattr("sys.argv", ["source_report.py"])

    source_report.main()

    assert "Sources available: 1/1" in capsys.readouterr().out


def test_check_muckrock_reports_missing_credentials(monkeypatch):
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.delenv("MUCKROCK_USERNAME", raising=False)
    monkeypatch.delenv("MUCKROCK_PASSWORD", raising=False)

    result = source_report.check_muckrock()

    assert result["status"] == "no_credentials"
    assert "MUCKROCK_USERNAME" in result["start_cmd"]
    assert "MUCKROCK_PASSWORD" in result["start_cmd"]


def test_check_muckrock_authenticates_and_decodes_a_result(monkeypatch):
    captured = {}
    iterated = []

    class FakeResults:
        def __iter__(self):
            iterated.append(True)
            yield {"id": 1}

    class FakeRequests:
        @staticmethod
        def list(**params):
            captured["params"] = params
            return FakeResults()

    def fake_muckrock(**kwargs):
        captured["credentials"] = kwargs
        return SimpleNamespace(requests=FakeRequests())

    monkeypatch.setenv("MUCKROCK_USERNAME", "researcher")
    monkeypatch.setenv("MUCKROCK_PASSWORD", "secret")
    monkeypatch.setitem(
        sys.modules,
        "muckrock",
        SimpleNamespace(MuckRock=fake_muckrock),
    )

    result = source_report.check_muckrock()

    assert result == {"status": "available", "note": "Authenticated API v2"}
    assert captured["credentials"] == {
        "username": "researcher",
        "password": "secret",
    }
    assert captured["params"] == {"page_size": 1}
    assert iterated == [True]


def test_check_muckrock_loads_repo_env(monkeypatch):
    loaded = []

    def fake_load_env_file():
        loaded.append(True)
        monkeypatch.setenv("MUCKROCK_USERNAME", "researcher")
        monkeypatch.setenv("MUCKROCK_PASSWORD", "secret")

    class FakeResults:
        def __iter__(self):
            yield {"id": 1}

    def fake_muckrock(**_kwargs):
        return SimpleNamespace(
            requests=SimpleNamespace(list=lambda **_params: FakeResults())
        )

    monkeypatch.delenv("MUCKROCK_USERNAME", raising=False)
    monkeypatch.delenv("MUCKROCK_PASSWORD", raising=False)
    monkeypatch.setattr(source_report, "load_env_file", fake_load_env_file)
    monkeypatch.setitem(
        sys.modules,
        "muckrock",
        SimpleNamespace(MuckRock=fake_muckrock),
    )

    assert source_report.check_muckrock()["status"] == "available"
    assert loaded == [True]


def _catalog_manifest(
    source_id: str,
    *,
    name: str,
    domain: str,
    access_class: str,
    automation_disposition: str,
) -> dict:
    return {
        "source_id": source_id,
        "name": name,
        "domain": domain,
        "roles": ["assessment"] if domain == "property" else ["court"],
        "authority": f"{name} Authority",
        "operator": f"{name} Authority",
        "jurisdiction_geoids": ["37" if domain == "property" else "36"],
        "official_url": f"https://example.gov/{source_id}",
        "platform_family": "arcgis_rest" if domain == "property" else "human_action",
        "access_class": access_class,
        "automation_disposition": automation_disposition,
        "authentication": "none",
        "fees": "none",
        "stable_keys": ["native_record_id"],
        "source_status": "active",
        "capabilities": ["search_owner" if domain == "property" else "search_cases"],
    }


def test_public_records_catalog_reports_access_and_probe_states(tmp_path):
    now = "2026-07-28T12:00:00Z"
    catalog_path = tmp_path / "public_records_catalog.db"
    catalog = PublicRecordsCatalog(catalog_path)

    nc = _catalog_manifest(
        "us-nc-onemap-parcels",
        name="North Carolina OneMap Parcels",
        domain="property",
        access_class="B",
        automation_disposition="allowed_with_limits",
    )
    nyscef = _catalog_manifest(
        "us-ny-nyscef",
        name="NYSCEF",
        domain="court",
        access_class="C",
        automation_disposition="prohibited",
    )
    for manifest in (nc, nyscef):
        catalog.register_manifest(
            manifest,
            submitted_by="test:source-report",
            submitted_at=now,
        )

    catalog.evaluate_access(
        nc["source_id"],
        access_class="B",
        automation_disposition="allowed_with_limits",
        reviewed_by="test:reviewer",
        review_basis="Official bounded API.",
        reviewed_at=now,
        limits={"maximum_page_size": 1000},
    )
    catalog.record_probe(
        nc["source_id"],
        status="no_results",
        probed_by="test:source-report",
        probed_at=now,
        result_count=0,
    )
    catalog.evaluate_access(
        nyscef["source_id"],
        access_class="C",
        automation_disposition="prohibited",
        reviewed_by="test:reviewer",
        review_basis="Official terms prohibit automated extraction.",
        reviewed_at=now,
    )

    report = source_report.check_public_records_catalog(
        catalog_path,
        as_of=now,
    )

    assert report["Public Records Catalog"]["source_count"] == 2
    nc_report = report["Public records / North Carolina OneMap Parcels"]
    assert nc_report["status"] == "available"
    assert nc_report["probe_status"] == "no_results"
    assert nc_report["source_id"] == "us-nc-onemap-parcels"
    assert nc_report["query_tool"] == "tools/query_property.py"
    nyscef_report = report["Public records / NYSCEF"]
    assert nyscef_report["status"] == "human_required"
    assert nyscef_report["automation_disposition"] == "prohibited"


def test_public_records_catalog_missing_is_read_only(tmp_path):
    catalog_path = tmp_path / "missing" / "public_records_catalog.db"

    report = source_report.check_public_records_catalog(catalog_path)

    assert report["Public Records Catalog"]["status"] == "missing"
    assert not catalog_path.exists()


def test_public_records_catalog_direct_cli_uses_local_import_fallback(tmp_path):
    catalog_path = tmp_path / "public_records_catalog.db"
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = _catalog_manifest(
        "us-test-property",
        name="Test Property",
        domain="property",
        access_class="A",
        automation_disposition="allowed",
    )
    catalog.register_manifest(
        manifest,
        submitted_by="test:direct-cli",
        submitted_at="2026-07-28T12:00:00Z",
    )
    catalog.evaluate_access(
        manifest["source_id"],
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="test:direct-cli",
        review_basis="Fixture review.",
        reviewed_at="2026-07-28T12:00:00Z",
    )

    root = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [
            sys.executable,
            "tools/source_report.py",
            "-j",
            "check",
            "Public Records Catalog",
            "--public-records-db",
            str(catalog_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["available"] is True
    assert result["status"] == "available"


def test_check_cli_accepts_json_after_subcommand(tmp_path):
    catalog_path = tmp_path / "public_records_catalog.db"
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = _catalog_manifest(
        "us-test-property",
        name="Test Property",
        domain="property",
        access_class="A",
        automation_disposition="allowed",
    )
    catalog.register_manifest(
        manifest,
        submitted_by="test:subcommand-json",
        submitted_at="2026-07-30T12:00:00Z",
    )
    catalog.evaluate_access(
        manifest["source_id"],
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="test:subcommand-json",
        review_basis="Fixture review.",
        reviewed_at="2026-07-30T12:00:00Z",
    )

    root = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [
            sys.executable,
            "tools/source_report.py",
            "check",
            "us-test-property",
            "--json",
            "--public-records-db",
            str(catalog_path),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    assert result["available"] is True
    assert result["source_id"] == "us-test-property"


def test_quick_health_check_resolves_exact_public_record_source_id(
    tmp_path,
    monkeypatch,
):
    catalog_path = tmp_path / "public_records_catalog.db"
    catalog = PublicRecordsCatalog(catalog_path)
    manifest = _catalog_manifest(
        "us-test-property",
        name="Test Property",
        domain="property",
        access_class="A",
        automation_disposition="allowed",
    )
    catalog.register_manifest(
        manifest,
        submitted_by="test:source-id-check",
        submitted_at="2026-07-30T12:00:00Z",
    )
    catalog.evaluate_access(
        manifest["source_id"],
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="test:source-id-check",
        review_basis="Fixture review.",
        reviewed_at="2026-07-30T12:00:00Z",
    )
    monkeypatch.setattr(
        source_report,
        "generate_report",
        lambda: pytest.fail("exact catalog ID should not run the full report"),
    )

    result = source_report.quick_health_check(
        "US-TEST-PROPERTY",
        public_records_db=catalog_path,
    )

    assert result["available"] is True
    assert result["status"] == "configured"
    assert result["source_id"] == "us-test-property"
    assert result["name"] == "Public records / Test Property"
