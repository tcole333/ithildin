"""Offline forward checks for runnable financial/source skill examples."""

import argparse
import json
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools import findings_tracker, lead_tracker, query_990, query_registry
from tools import query_usaspending

ROOT = Path(__file__).resolve().parents[1]


def _skill(runtime, name):
    return (ROOT / f".{runtime}/skills/{name}/SKILL.md").read_text()


def _block(runtime, name, language, contains):
    blocks = re.findall(
        rf"^```{language}\n(.*?)^```",
        _skill(runtime, name),
        flags=re.MULTILINE | re.DOTALL,
    )
    return next(block for block in blocks if contains in block)


@pytest.fixture
def findings_db(tmp_path, monkeypatch):
    db_path = tmp_path / "selected.db"
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ITHILDIN_PROFILE", "alpha")
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db
    db.close()


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_growth_finding_example_persists_exact_quote(
    runtime, findings_db, monkeypatch
):
    block = _block(runtime, "audit-contracts", "bash", "--source-quote")
    replacements = {
        "<COMPANY>": "Fixture Contractor",
        "<X>": "20",
        "<PREV>": "2024",
        "<CURR>": "2025",
        "<SCOPE_REF>": "fixture-uei-complete-fy2024-2025",
        "<exact fiscal-year and obligation rows>": "FY2024: 100; FY2025: 120",
    }
    for old, new in replacements.items():
        block = block.replace(old, new)
    args = shlex.split(block.replace("\\\n", ""))
    monkeypatch.setattr(sys, "argv", args[3:])

    findings_tracker.main()

    row = findings_db.execute(
        """SELECT f.profile_id, f.claim_type, f.confidence, e.evidence_ref,
                  e.source_quote
           FROM findings f JOIN finding_evidence e ON e.finding_id = f.id"""
    ).fetchone()
    assert dict(row) == {
        "profile_id": "alpha",
        "claim_type": "synthesis",
        "confidence": "medium",
        "evidence_ref": "USASPENDING:fixture-uei-complete-fy2024-2025",
        "source_quote": "FY2024: 100; FY2025: 120",
    }


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_registry_scaffold_preserves_id_children_and_source_url(runtime):
    namespace = {}
    exec(_block(runtime, "add-registry", "python", "upsert_registry_entity"), namespace)
    upsert = namespace["upsert_registry_entity"]
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    query_registry._ensure_schema(db)
    first_id = upsert(db, "xx", "source-1", "Fixture Company", "https://example.test/1")
    db.execute(
        "INSERT INTO registry_officers (entity_id, officer_name, title) VALUES (?, ?, ?)",
        (first_id, "Fixture Officer", "Director"),
    )
    repeated_id = upsert(db, "xx", "source-1", "Updated Company", None)
    other_id = upsert(db, "yy", "source-1", "Other Jurisdiction", None)

    assert repeated_id == first_id
    assert other_id != first_id
    assert db.execute(
        "SELECT entity_name, source_url FROM registry_entities WHERE id = ?", (first_id,)
    ).fetchone() == ("Updated Company", "https://example.test/1")
    assert db.execute(
        "SELECT entity_id, officer_name FROM registry_officers"
    ).fetchall() == [(first_id, "Fixture Officer")]
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    db.close()


def _seed_findings(db):
    db.executemany(
        "INSERT INTO investigation_threads (id, title, profile_id) VALUES (?, ?, ?)",
        [(73, "Selected local thread three", "alpha"),
         (74, "Different alpha thread", "alpha"),
         (3, "Foreign local thread three", "beta")],
    )
    db.executemany(
        """INSERT INTO findings
           (target_name, summary, finding_type, thread_id, profile_id)
           VALUES (?, ?, ?, ?, ?)""",
        [
            ("Wanted Contractor",
             "Wanted Contractor former government officer joined from agency; contract award.",
             "financial", 73, "alpha"),
            ("Foreign Contractor", "Wanted Contractor contract award in foreign profile",
             "financial", 3, "beta"),
            ("Outside Contractor", "Another contract award", "financial", 74, "alpha"),
        ],
    )
    db.commit()


def _run_bash(block, workdir, db_path, **replacements):
    for old, new in replacements.items():
        block = block.replace(old, new)
    environment = {
        **os.environ,
        "WORKDIR": str(workdir),
        "PROFILE": "alpha",
        "ITHILDIN_PROFILE": "alpha",
        "ITHILDIN_DB_PATH": str(db_path),
        "UV_NO_SYNC": "1",
    }
    return subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-c", "set -e\n" + block],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.mark.skipif(shutil.which("jq") is None, reason="Skill examples require jq")
@pytest.mark.parametrize("runtime", ["claude", "codex"])
@pytest.mark.parametrize("skill", ["screen-targets", "audit-contracts"])
def test_thread_example_maps_local_id_and_keeps_profile(
    runtime, skill, findings_db, tmp_path
):
    _seed_findings(findings_db)
    (tmp_path / "profile.json").write_text(json.dumps({
        "name": "alpha",
        "threads": [{"id": 3, "global_id": 73}],
    }))
    block = _block(runtime, skill, "bash", "LOCAL_THREAD_ID=")
    result = _run_bash(
        block, tmp_path, tmp_path / "selected.db",
        **{"<REQUESTED_LOCAL_THREAD_ID>": "3"},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "Wanted Contractor"
    payload = json.loads((tmp_path / "thread-findings.json").read_text())
    assert {row["thread_id"] for row in payload} == {73}
    assert {row["profile_id"] for row in payload} == {"alpha"}


@pytest.mark.skipif(shutil.which("jq") is None, reason="Skill examples require jq")
@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_unmapped_thread_example_stops_before_tracker(runtime, tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({
        "name": "alpha", "threads": [{"id": 3, "global_id": None}],
    }))
    block = _block(runtime, "audit-contracts", "bash", "LOCAL_THREAD_ID=")
    missing_db = tmp_path / "never-created.db"
    result = _run_bash(
        block, tmp_path, missing_db,
        **{"<REQUESTED_LOCAL_THREAD_ID>": "3"},
    )
    assert result.returncode != 0
    assert "No global mapping" in result.stderr
    assert not missing_db.exists()
    assert not (tmp_path / "thread-findings.json").exists()


@pytest.mark.skipif(shutil.which("jq") is None, reason="Skill examples require jq")
@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_revolving_door_example_handles_positive_matches(
    runtime, findings_db, tmp_path
):
    _seed_findings(findings_db)
    block = _block(runtime, "audit-contracts", "bash", "-existing-findings.json")
    result = _run_bash(
        block, tmp_path, tmp_path / "selected.db",
        **{"<COMPANY>": "Wanted Contractor", "<slug>": "wanted"},
    )
    assert result.returncode == 0, result.stderr
    assert "former government officer" in result.stdout
    payload = json.loads((tmp_path / "wanted-existing-findings.json").read_text())
    assert {row["profile_id"] for row in payload} == {"alpha"}
    assert len(payload) == 1


def _entity_db(path, name, ein):
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE entities (id INTEGER, name TEXT, ein TEXT)")
        if name:
            db.execute("INSERT INTO entities VALUES (1, ?, ?)", (name, ein))


def _grant_db(path):
    with sqlite3.connect(path) as db:
        db.execute(
            """CREATE TABLE grants (
                 filer_ein TEXT, filer_name TEXT, recipient_ein TEXT,
                 cash_amount INTEGER)"""
        )
        db.executemany(
            "INSERT INTO grants VALUES (?, ?, ?, ?)",
            [("111111111", "Selected Foundation", "333333333", 100),
             ("222222222", "Checkout Foundation", "333333333", 900)],
        )


def test_990_cross_ref_uses_runtime_pin_and_opens_readonly(tmp_path, monkeypatch):
    selected = tmp_path / "selected.db"
    checkout = tmp_path / "checkout.db"
    grants = tmp_path / "grants.db"
    _entity_db(selected, "Selected Foundation", "111111111")
    _entity_db(checkout, "Checkout Foundation", "222222222")
    _grant_db(grants)
    monkeypatch.setattr(query_990, "INVESTIGATION_DB", checkout)
    monkeypatch.setattr(query_990, "DB_PATH", grants)
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected))
    original_connect = sqlite3.connect
    opened = []

    def checked_connect(database, *args, **kwargs):
        opened.append((str(database), kwargs.copy()))
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(query_990.sqlite3, "connect", checked_connect)
    output = tmp_path / "cross-ref.json"
    query_990.cmd_cross_ref(argparse.Namespace(output=str(output), json_out=False))

    payload = json.loads(output.read_text())
    assert {row["entity_name"] for row in payload} == {"Selected Foundation"}
    assert {row["total_amount"] for row in payload} == {100}
    assert opened[0] == (selected.as_uri() + "?mode=ro", {"uri": True})
    assert all(str(checkout) not in opened_path for opened_path, _ in opened)


def test_990_cross_ref_empty_selected_database_writes_empty_artifact(
    tmp_path, monkeypatch
):
    selected = tmp_path / "empty.db"
    _entity_db(selected, None, None)
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected))
    monkeypatch.setattr(
        query_990, "get_db",
        lambda: pytest.fail("An empty entity set should not open the grant corpus"),
    )
    output = tmp_path / "cross-ref.json"

    query_990.cmd_cross_ref(argparse.Namespace(output=str(output), json_out=False))

    assert json.loads(output.read_text()) == []


def test_990_cross_ref_missing_pin_does_not_fall_back(tmp_path, monkeypatch):
    checkout = tmp_path / "checkout.db"
    _entity_db(checkout, "Checkout Foundation", "222222222")
    selected = tmp_path / "missing.db"
    monkeypatch.setattr(query_990, "INVESTIGATION_DB", checkout)
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected))

    with pytest.raises(SystemExit) as error:
        query_990.cmd_cross_ref(
            argparse.Namespace(output=str(tmp_path / "out.json"), json_out=False)
        )

    assert error.value.code == 1
    assert not selected.exists()
    assert not (tmp_path / "out.json").exists()


def test_recipient_example_retains_all_period_scope(tmp_path, monkeypatch):
    recipient = {"recipient_name": "Fixture Contractor", "uei": "FIXTUREUEI"}
    responses = iter([
        {"results": [recipient]},
        {"results": [{"name": "Agency", "amount": 300}],
         "page_metadata": {"hasNext": False}},
    ])
    monkeypatch.setattr(
        query_usaspending, "_fetch_post",
        lambda endpoint, payload: next(responses),
    )
    output = tmp_path / "recipient.json"
    query_usaspending.cmd_recipient(argparse.Namespace(
        query="Fixture Contractor", output=str(output), json_out=False,
    ))

    payload = json.loads(output.read_text())
    filters = payload["retrieval"]["requests"][1]["payload"]["filters"]
    assert filters["recipient_search_text"] == ["FIXTUREUEI"]
    assert set(filters) == {"recipient_search_text", "award_type_codes"}
    assert payload["spending_by_agency"] == [{"name": "Agency", "amount": 300}]
    for runtime in ("claude", "codex"):
        assert "**all available periods**" in _skill(runtime, "audit-contracts")
