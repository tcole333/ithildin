from pathlib import Path
import json
import subprocess
import sys

import yaml

from tools.public_records_catalog import PublicRecordsCatalog
from tools.seed_public_records_catalog import ensure_catalog_source, seed_catalog


def _config(path: Path):
    data = {
        "schema_version": 1,
        "submitted_by": "test-bootstrap",
        "sources": [
            {
                "source_id": "us-nc-test-parcels",
                "name": "Test Parcels",
                "domain": "property",
                "roles": ["assessment"],
                "authority": "Test Authority",
                "operator": "Test Authority",
                "jurisdiction_geoids": ["37"],
                "official_url": "https://example.gov/parcels",
                "platform_family": "arcgis_rest",
                "access_class": "B",
                "automation_disposition": "allowed_with_limits",
                "authentication": "none",
                "fees": "none",
                "stable_keys": ["native_parcel_id"],
                "adapter_family": "arcgis_rest",
                "adapter_version": 1,
                "capabilities": ["fetch_parcel"],
                "access_review": {
                    "access_class": "B",
                    "automation_disposition": "allowed_with_limits",
                    "reviewed_by": "test-reviewer",
                    "review_basis": "documented official API",
                    "limits": {"maximum_page_size": 1000},
                },
            },
            {
                "source_id": "us-ny-test-court",
                "name": "Test Court",
                "domain": "court",
                "roles": ["court"],
                "authority": "Test Court",
                "operator": "Test Court",
                "jurisdiction_geoids": ["36"],
                "official_url": "https://example.gov/court",
                "platform_family": "browser_portal",
                "access_class": "C",
                "automation_disposition": "prohibited",
                "authentication": "guest",
                "fees": "none",
                "stable_keys": ["raw_case_number"],
                "adapter_family": "human_action",
                "adapter_version": 1,
                "capabilities": ["search_cases"],
                "access_review": {
                    "access_class": "C",
                    "automation_disposition": "prohibited",
                    "reviewed_by": "test-reviewer",
                    "review_basis": "official terms prohibit bots",
                },
            },
        ],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_seed_is_idempotent_and_preserves_gate_separation(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)

    first = seed_catalog(db_path=db_path, config_path=config_path)
    second = seed_catalog(db_path=db_path, config_path=config_path)

    assert first["sources_seen"] == 2
    assert first["manifests_registered"] == 2
    assert first["access_reviews_recorded"] == 2
    assert second["manifests_registered"] == 0
    assert second["access_reviews_recorded"] == 0
    assert second["access_reviews_unchanged"] == 2

    catalog = PublicRecordsCatalog(db_path)
    assert catalog.require_machine_acquisition("us-nc-test-parcels")["allowed"] is True
    assert catalog.machine_acquisition_decision("us-ny-test-court")["allowed"] is False


def test_adapter_bootstrap_preserves_newer_catalog_review(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)
    seed_catalog(db_path=db_path, config_path=config_path)
    catalog = PublicRecordsCatalog(db_path)
    operator_review = catalog.evaluate_access(
        "us-nc-test-parcels",
        access_class="A",
        automation_disposition="allowed",
        reviewed_by="operator",
        review_basis="Current endpoint observation supersedes tracked bootstrap.",
    )

    returned = ensure_catalog_source(
        "us-nc-test-parcels",
        db_path=db_path,
        config_path=config_path,
    )

    latest = returned.show_source("us-nc-test-parcels")["latest_access_review"]
    assert latest["access_review_id"] == operator_review["access_review_id"]
    assert latest["review_basis"] == (
        "Current endpoint observation supersedes tracked bootstrap."
    )


def test_adapter_bootstrap_registers_only_requested_missing_source(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    _config(config_path)

    catalog = ensure_catalog_source(
        "us-nc-test-parcels",
        db_path=db_path,
        config_path=config_path,
    )

    assert [row["source_id"] for row in catalog.list_sources()] == [
        "us-nc-test-parcels"
    ]
    assert catalog.require_machine_acquisition("us-nc-test-parcels")["allowed"]


def test_direct_cli_supports_standard_output_file(tmp_path):
    config_path = tmp_path / "sources.yaml"
    db_path = tmp_path / "catalog.db"
    output_path = tmp_path / "seed.json"
    _config(config_path)
    root = Path(__file__).resolve().parent.parent

    completed = subprocess.run(
        [
            sys.executable,
            "tools/seed_public_records_catalog.py",
            "--db",
            str(db_path),
            "--config",
            str(config_path),
            "--output",
            str(output_path),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["sources_seen"] == 2
    assert "catalog seed: 2 sources" in completed.stdout
