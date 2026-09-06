"""Offline forward checks for documented analysis commands and export coverage."""

import importlib.util
import json
from pathlib import Path
import re
import shlex
import sqlite3
import sys

import pytest

from tools import analysis_export, findings_tracker


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def entity_network_db(tmp_path):
    db_path = tmp_path / "network.db"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY, name TEXT, entity_type TEXT,
                jurisdiction TEXT, status TEXT, ein TEXT, address TEXT,
                source TEXT, notes TEXT, date_formed TEXT
            );
            CREATE TABLE findings (id INTEGER PRIMARY KEY, target_name TEXT, profile_id TEXT);
            CREATE TABLE finding_entities (finding_id INTEGER, entity_id INTEGER);
            CREATE TABLE entity_roles (
                entity_id INTEGER, person_name TEXT, role TEXT,
                date_start TEXT, date_end TEXT, source TEXT
            );
            CREATE TABLE entity_relations (
                entity_a_id INTEGER, entity_b_id INTEGER, relation_type TEXT,
                description TEXT, source TEXT
            );
            CREATE TABLE entity_addresses (
                entity_id INTEGER, address TEXT, address_type TEXT,
                date_observed TEXT, source TEXT
            );
            INSERT INTO findings VALUES (1, 'Selected', 'selected'), (2, 'Other', 'other');
            INSERT INTO finding_entities VALUES (1, 1), (2, 3);
            INSERT INTO entity_relations VALUES (1, 2, 'owns', 'Recorded relationship', 'registry');
        """)
        db.executemany(
            "INSERT INTO entities (id, name, entity_type, date_formed) VALUES (?, ?, 'llc', ?)",
            [(1, "Selected", "2019-02-03"), (2, "Related", "2019-02"),
             (3, "Other", "2007"), (4, "Unknown", None)],
        )
    return db_path


@pytest.mark.parametrize("all_profiles", [False, True])
def test_entity_export_preserves_formation_dates_and_scope(
    entity_network_db, monkeypatch, all_profiles
):
    def open_fixture():
        db = sqlite3.connect(entity_network_db)
        db.row_factory = sqlite3.Row
        return db

    monkeypatch.setattr(analysis_export, "get_analysis_db", open_fixture)
    result = analysis_export.export_entity_network(
        profile_id="selected", all_profiles=all_profiles
    )
    dates = {entity["name"]: entity["date_formed"] for entity in result["entities"]}
    expected = {"Selected": "2019-02-03", "Related": "2019-02"}
    if all_profiles:
        expected.update({"Other": "2007", "Unknown": None})
    assert dates == expected


def _tracker_commands(runtime, skill="analyze-case"):
    text = (ROOT / runtime / "skills" / skill / "SKILL.md").read_text()
    blocks = re.findall(
        r"^[ \t]*```bash[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
        text, flags=re.DOTALL | re.MULTILINE,
    )
    commands = []
    for block in blocks:
        commands.extend(
            line for line in block.replace("\\\n", " ").splitlines()
            if line.startswith("uv run python tools/findings_tracker.py ")
        )
    return commands


@pytest.mark.parametrize("runtime", [".claude", ".codex"])
def test_cross_case_example_maps_two_typed_refs_to_exact_quotes(runtime, monkeypatch):
    command = next(
        command for command in _tracker_commands(runtime)
        if "--claim-type inference" in command
    ).replace("<CLUSTER_ID_1>", "101").replace("<CLUSTER_ID_2>", "202")
    captured = []

    def validate_write(**kwargs):
        assert kwargs["evidence_ids"] == [
            "CourtListener:opinion/101", "CourtListener:opinion/202"
        ]
        assert set(kwargs["source_quotes"]) == set(kwargs["evidence_ids"])
        for ref, metadata in kwargs["source_quotes"].items():
            findings_tracker._validate_evidence_payload(
                ref, metadata["quote"], claim_type=kwargs["claim_type"]
            )
        assert kwargs["confidence"] == "medium"
        captured.append(kwargs)
        return 1

    monkeypatch.setattr(findings_tracker, "add_finding", validate_write)
    monkeypatch.setattr(sys, "argv", shlex.split(command)[3:])
    findings_tracker.main()
    assert len(captured) == 1


@pytest.mark.parametrize("runtime", [".claude", ".codex"])
def test_documented_case_financial_lookup_uses_pinned_database_and_profile(
    runtime, tmp_path, monkeypatch
):
    selected_path = tmp_path / "selected.db"
    decoy_path = tmp_path / "investigation.db"
    for db_path in (selected_path, decoy_path):
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE findings (id INTEGER, target_name TEXT, "
                       "finding_type TEXT, profile_id TEXT, summary TEXT, created_at TEXT)")
            rows = [(1, "Shared Party", "financial", "selected", "selected fact", "2026-01-01"),
                    (2, "Shared Party", "financial", "other", "foreign fact", "2026-01-02")]
            if db_path == decoy_path:
                rows = [(3, "Shared Party", "financial", "selected", "decoy fact", "2026-01-03")]
            db.executemany("INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?)", rows)

    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected_path))
    monkeypatch.setenv("ITHILDIN_PROFILE", "selected")
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location("case_fixture_tracker", findings_tracker.__file__)
    tracker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tracker)
    tracker._schema_initialized = True  # Deliberate minimal fixture; never migrate production.
    assert tracker.DB_PATH == selected_path
    output_path = tmp_path / "financial-xref-party.json"
    command = next(command for command in _tracker_commands(runtime) if " list --target " in command)
    command = command.replace("<PARTY>", "Shared Party")
    command = command.replace("$WORKDIR/financial-xref-<slug>.json", str(output_path))
    monkeypatch.setattr(sys, "argv", shlex.split(command)[3:])
    tracker.main()
    result = json.loads(output_path.read_text())
    assert [row["summary"] for row in result] == ["selected fact"]


@pytest.mark.parametrize("runtime", [".claude", ".codex"])
def test_documented_filing_connections_use_pinned_database_and_profile(
    runtime, tmp_path, monkeypatch
):
    selected_path = tmp_path / "selected.db"
    decoy_path = tmp_path / "investigation.db"
    for db_path in (selected_path, decoy_path):
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE connections (id INTEGER, person_a TEXT, "
                       "person_b TEXT, relationship_type TEXT, profile_id TEXT)")
            rows = [(1, "Shared Party", "Selected associate", "corporate", "selected"),
                    (2, "Shared Party", "Foreign associate", "corporate", "other")]
            if db_path == decoy_path:
                rows = [(3, "Shared Party", "Decoy associate", "corporate", "selected")]
            db.executemany("INSERT INTO connections VALUES (?, ?, ?, ?, ?)", rows)

    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected_path))
    monkeypatch.setenv("ITHILDIN_PROFILE", "selected")
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location("filing_fixture_tracker", findings_tracker.__file__)
    tracker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tracker)
    tracker._schema_initialized = True
    assert tracker.DB_PATH == selected_path
    output_path = tmp_path / "connections-party.json"
    command = next(command for command in _tracker_commands(runtime, "analyze-filing")
                   if " connections " in command)
    command = command.replace("<NAME>", "Shared Party")
    command = command.replace("$WORKDIR/connections-<slug>.json", str(output_path))
    monkeypatch.setattr(sys, "argv", shlex.split(command)[3:])
    tracker.main()
    result = json.loads(output_path.read_text())
    assert [row["person_b"] for row in result] == ["Selected associate"]
