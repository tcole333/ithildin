import sqlite3
from pathlib import Path

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
