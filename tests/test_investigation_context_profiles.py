import json
import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

from tools import investigation_context


REPO_ROOT = Path(__file__).parents[1]
KNOWN_CORPUS_COMMANDS = {
    "tools/query_unified.py": {"emails", "docs", "entities", "triples", "cooccurrence", "stats"},
    "tools/query_lmsband.py": {"search", "entities", "cooccurrence", "file", "stats"},
    "tools/ingest_fbi_files.py": {"download", "ingest", "search", "doc", "stats", "overlap"},
}


def _write_profile(root, name, primary_subject):
    profile_dir = root / name
    profile_dir.mkdir()
    (profile_dir / "config.yaml").write_text(
        yaml.safe_dump({"name": name, "primary_subject": primary_subject})
    )


def test_profile_catalog_reconciles_configs_and_historical_data(monkeypatch, tmp_path):
    investigations_dir = tmp_path / "investigations"
    investigations_dir.mkdir()
    _write_profile(investigations_dir, "configured", "Configured Subject")

    db_path = tmp_path / "investigation.db"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY, profile_id TEXT)")
    db.execute("INSERT INTO findings(profile_id) VALUES ('historical')")
    db.commit()
    db.close()

    monkeypatch.setattr(investigation_context, "INVESTIGATIONS_DIR", investigations_dir)
    monkeypatch.setattr(investigation_context, "DB_PATH", db_path)

    reconciled = investigation_context._get_db()
    rows = reconciled.execute(
        "SELECT profile_id FROM investigation_profiles ORDER BY profile_id"
    ).fetchall()
    reconciled.close()
    assert [row["profile_id"] for row in rows] == ["configured"]

    profiles = investigation_context.list_profiles()
    assert [(profile["name"], profile["database_only"]) for profile in profiles] == [
        ("configured", False),
        ("historical", True),
    ]


def test_profile_catalog_reconciliation_is_idempotent(monkeypatch, tmp_path):
    investigations_dir = tmp_path / "investigations"
    investigations_dir.mkdir()
    _write_profile(investigations_dir, "configured", "Configured Subject")
    db_path = tmp_path / "investigation.db"

    monkeypatch.setattr(investigation_context, "INVESTIGATIONS_DIR", investigations_dir)
    monkeypatch.setattr(investigation_context, "DB_PATH", db_path)

    investigation_context._get_db().close()
    investigation_context._get_db().close()

    db = sqlite3.connect(db_path)
    assert db.execute(
        "SELECT COUNT(*) FROM investigation_profiles WHERE profile_id = 'configured'"
    ).fetchone()[0] == 1
    db.close()


def test_profile_reads_do_not_reconcile_or_write_catalog(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE investigation_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE investigation_threads (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            profile_id TEXT
        );
        INSERT INTO investigation_config(key, value)
        VALUES ('active_profile', 'alpha');
        INSERT INTO investigation_threads(id, title, profile_id)
        VALUES (81, 'Alpha Thread', 'alpha');
        """
    )
    db.commit()
    db.close()
    monkeypatch.setattr(investigation_context, "DB_PATH", db_path)
    monkeypatch.setattr(
        investigation_context,
        "_reconcile_profile_catalog",
        lambda *_args, **_kwargs: pytest.fail(
            "ordinary profile reads must not reconcile the catalog"
        ),
    )

    assert investigation_context.get_active_profile_name() == "alpha"
    profile = investigation_context.InvestigationProfile(
        name="alpha",
        primary_subject="Alpha",
        threads=[{"id": 1, "name": "Alpha Thread"}],
    )
    assert investigation_context.get_global_thread_ids(profile) == {1: 81}


def test_show_writes_active_profile_to_output(tmp_path, monkeypatch, capsys):
    investigations_dir = tmp_path / "investigations"
    investigations_dir.mkdir()
    _write_profile(investigations_dir, "alpha", "Alpha Subject")
    db_path = tmp_path / "investigation.db"
    db = sqlite3.connect(db_path)
    db.execute(
        "CREATE TABLE investigation_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    db.execute(
        "INSERT INTO investigation_config(key, value) VALUES ('active_profile', 'alpha')"
    )
    db.commit()
    db.close()

    output = tmp_path / "profile.json"
    monkeypatch.setattr(investigation_context, "INVESTIGATIONS_DIR", investigations_dir)
    monkeypatch.setattr(investigation_context, "DB_PATH", db_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["investigation_context.py", "show", "--output", str(output)],
    )

    investigation_context.main()

    assert json.loads(output.read_text())["name"] == "alpha"
    assert "saved to" in capsys.readouterr().out


def test_profile_corpus_metadata_only_advertises_supported_commands():
    for config_path in sorted((REPO_ROOT / "investigations").glob("*/config.yaml")):
        config = yaml.safe_load(config_path.read_text()) or {}
        for corpus_tool in config.get("corpus_tools", []):
            tool = corpus_tool.get("tool")
            supported = KNOWN_CORPUS_COMMANDS.get(tool)
            if supported is None:
                continue
            advertised = set(corpus_tool.get("commands", []))
            assert advertised <= supported, (
                f"{config_path}: {tool} advertises unsupported commands "
                f"{sorted(advertised - supported)}"
            )


def test_fink_profile_exposes_current_unified_and_fbi_workflows():
    config = yaml.safe_load(
        (REPO_ROOT / "investigations/fink/config.yaml").read_text()
    )
    commands = {
        corpus_tool["tool"]: corpus_tool["commands"]
        for corpus_tool in config["corpus_tools"]
    }

    assert commands["tools/query_unified.py"] == [
        "emails", "docs", "entities", "triples", "cooccurrence"
    ]
    assert commands["tools/ingest_fbi_files.py"] == ["search", "doc", "overlap"]


def test_allbirds_profile_uses_current_smartbird_identity_and_historical_aliases():
    config = yaml.safe_load(
        (REPO_ROOT / "investigations/allbirds/config.yaml").read_text()
    )

    assert config["primary_subject"].startswith("Smartbird, Inc.")
    assert "formerly Allbirds, Inc." in config["primary_subject"]
    assert "NewBird AI" in config["primary_subject"]
    assert "0001653909" in config["description"]
    targets = {
        target
        for thread in config["threads"]
        for target in thread.get("targets", [])
    }
    assert {"smartbird", "smartbird inc", "newbird ai"} <= targets
