from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import build_all, curate_dossier, export_network, publication_snapshot


@pytest.fixture
def network_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "network.db"
    with sqlite3.connect(db_path) as db:
        db.executescript("""
          CREATE TABLE entities(id INTEGER, name TEXT, entity_type TEXT, jurisdiction TEXT, status TEXT);
          CREATE TABLE name_aliases(canonical_name TEXT,alias TEXT,alias_type TEXT,entity_id INTEGER);
          CREATE TABLE connections(id INTEGER,person_a TEXT,person_b TEXT,relationship_type TEXT,
            description TEXT,strength TEXT,date_range TEXT,verification_status TEXT,profile_id TEXT,finding_id INTEGER);
          CREATE TABLE connection_evidence(connection_id INTEGER,evidence_type TEXT,evidence_ref TEXT,
            source_quote TEXT,source_page TEXT,assessment TEXT);
          CREATE TABLE entity_roles(id INTEGER,entity_id INTEGER,person_name TEXT,role TEXT,date_start TEXT,date_end TEXT,source TEXT);
          CREATE TABLE entity_relations(id INTEGER,entity_a_id INTEGER,entity_b_id INTEGER,relation_type TEXT,description TEXT,source TEXT);
          CREATE TABLE findings(id INTEGER,target_name TEXT,verification_status TEXT,profile_id TEXT,
            claim_type TEXT,source_datasets TEXT,confidence TEXT);
          CREATE TABLE finding_evidence(finding_id INTEGER,evidence_type TEXT,evidence_ref TEXT,source_quote TEXT);
          INSERT INTO findings VALUES(10,'A','verified','b','paraphrase','["official_website"]','high');
          INSERT INTO finding_evidence VALUES(10,'url','https://example.test/attendance','A and B attended the conference.');
          INSERT INTO connections VALUES(1,'A','B','alleged_payment','Payment allegation','weak','2020','unverified','a',NULL);
          INSERT INTO connections VALUES(2,'A','B','co_attendance','Conference attendance','strong','2021','verified','b',10);
          INSERT INTO connections VALUES(3,'B','A','retracted_payment','Old allegation','strong','2019','retracted','b',NULL);
          INSERT INTO connection_evidence VALUES(2,'url','https://example.test/record','Exact source quote',NULL,NULL);
          INSERT INTO entities VALUES(11,'Entity','company','US','active');
          INSERT INTO entity_roles VALUES(12,11,'A','officer',NULL,NULL,'https://example.test/role');
        """)
    return db_path


def test_network_preserves_each_claim_and_its_own_verification(network_db: Path) -> None:
    graph = export_network.export_network(network_db, include_unverified=True)
    edges = {edge["id"]: edge for edge in graph["edges"]}
    assert edges["connection:1"]["verified"] is False
    assert edges["connection:1"]["strength"] == "weak"
    assert edges["connection:1"]["profile_ids"] == ["a"]
    assert edges["connection:2"]["relationship_type"] == "co_attendance"
    assert edges["connection:2"]["verified"] is True
    assert edges["connection:2"]["evidence"][0]["source_quote"] == "Exact source quote"
    assert "connection:3" not in edges
    assert edges["entity_role:12"]["verified"] is False


def test_public_network_is_verified_evidence_gated_and_profile_scoped(network_db: Path) -> None:
    graph = export_network.export_network(network_db)
    assert [edge["id"] for edge in graph["edges"]] == ["connection:2"]
    assert {node["id"] for node in graph["nodes"]} == {"A", "B"}
    assert export_network.export_network(network_db, profile_id="a")["edges"] == []
    with sqlite3.connect(network_db) as db:
        db.execute("UPDATE findings SET verification_status='retracted' WHERE id=10")
    assert export_network.export_network(network_db)["edges"] == []


def test_profile_research_does_not_include_global_structural_claims(network_db: Path) -> None:
    graph = export_network.export_network(network_db, include_unverified=True, profile_id="a")
    assert [edge["id"] for edge in graph["edges"]] == ["connection:1"]


@pytest.mark.parametrize("invalid_upstream", ["missing_evidence", "unquoted", "missing_sources", "over_confident"])
def test_public_network_rechecks_verified_upstream_provenance(network_db: Path, invalid_upstream: str) -> None:
    with sqlite3.connect(network_db) as db:
        if invalid_upstream == "missing_evidence":
            db.execute("DELETE FROM finding_evidence WHERE finding_id=10")
        elif invalid_upstream == "unquoted":
            db.execute("UPDATE finding_evidence SET source_quote=NULL WHERE finding_id=10")
        elif invalid_upstream == "missing_sources":
            db.execute("UPDATE findings SET source_datasets=NULL WHERE id=10")
        else:
            db.execute("UPDATE findings SET confidence='confirmed' WHERE id=10")
    assert export_network.export_network(network_db)["edges"] == []


@pytest.mark.parametrize("viz_only", [False, True])
def test_curation_preserves_open_ended_authored_fields(tmp_path: Path, viz_only: bool) -> None:
    curation = {"lead": "Authored", "sections": [{"id": "s", "content": "Evidence prose"}],
                "custom_editorial_note": {"approved_by": "editor"}, "key_finding_ids": [999]}
    payload = {"name": "Fixture", "findings": [], "connections": [], "entities": [],
               "curation": curation, "viz_data": {"custom_chart": {"preserve": True}}}
    file_path = tmp_path / "fixture.json"
    file_path.write_text(json.dumps(payload))
    result = curate_dossier.curate_dossier(file_path, viz_only=viz_only)
    assert result["curation"]["custom_editorial_note"] == curation["custom_editorial_note"]
    assert result["curation"]["sections"] == curation["sections"]
    assert result["viz_data"]["custom_chart"] == {"preserve": True}
    if viz_only:
        assert result["curation"] == curation


def test_curator_returns_failure_for_per_dossier_error(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "broken.json").write_text("{invalid")
    monkeypatch.setattr("sys.argv", ["curate_dossier.py", "--all", "--dossier-dir", str(tmp_path)])
    assert curate_dossier.main() == 1


def test_staging_failure_leaves_authored_tree_unchanged_and_stops(tmp_path: Path, monkeypatch) -> None:
    content = tmp_path / "source"
    content.mkdir()
    (content / "authored.json").write_text('{"lead":"retain"}')
    db = tmp_path / "input.db"
    db.write_bytes(b"fixture")
    calls = []
    monkeypatch.setattr(build_all, "export_steps", lambda *args: [(["step1"], "First"), (["step2"], "Second")])

    def run(cmd, *, cwd, env, check):
        calls.append(cmd)
        assert cwd == build_all.ROOT
        assert Path(env["ITHILDIN_CONTENT_DIR"]) != content
        Path(env["ITHILDIN_CONTENT_DIR"], "authored.json").write_text("partial export")
        return SimpleNamespace(returncode=2)

    monkeypatch.setattr(build_all.subprocess, "run", run)
    stage = tmp_path / "candidate"
    with pytest.raises(RuntimeError, match="First failed"):
        build_all.build_candidate(stage, source_content=content, source_public=tmp_path / "none", db_path=db)
    assert calls == [["step1"]]
    assert (content / "authored.json").read_text() == '{"lead":"retain"}'
    assert json.loads((stage / "export-result.json").read_text())["ok"] is False


def test_stage_rejects_existing_output_before_any_export(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="already exists"):
        build_all.build_candidate(tmp_path)


def test_pipeline_curator_cli_contract(tmp_path: Path) -> None:
    steps = build_all.export_steps(tmp_path, tmp_path / "db")
    curator = next(command for command, _ in steps if any(part.endswith("curate_dossier.py") for part in command))
    assert curator[-1] == "--all"
    assert "--all-profiles" not in curator
    assert all(Path(command[3]).is_absolute() for command, _ in steps)


@pytest.fixture
def content_fixture(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "content"
    (root / "dossiers").mkdir(parents=True)
    (root / "articles").mkdir()
    record = {"id": 1, "summary": "Recorded fact", "finding_type": "financial", "confidence": "high",
              "claim_type": "paraphrase", "verification_status": "verified", "date_of_event": "2024-01-01",
              "source_datasets": ["courtlistener"],
              "evidence": [{"evidence_type": "url", "evidence_ref": "https://example.test/record", "source_quote": "Exact source text"}]}
    (root / "dossiers/fixture.json").write_text(json.dumps({"name": "Fixture", "findings": [record], "curation": {"lead": "Claim [Finding #1]."}}))
    (root / "articles/fixture.mdx").write_text("---\ntitle: Fixture\n---\nClaim [Finding #1].")
    return root, record


def write_snapshot(root: Path) -> Path:
    findings, hashes, issues = publication_snapshot.collect_content(root)
    assert issues == []
    output = root / "finding-catalog.json"
    output.write_text(json.dumps({"schema_version": 1, "findings": findings, "source_hashes": hashes}))
    return output


def test_snapshot_is_self_contained_and_detects_prose_changes(content_fixture) -> None:
    root, _ = content_fixture
    snapshot = write_snapshot(root)
    assert publication_snapshot.validate_snapshot(root, snapshot)["ok"] is True
    (root / "articles/fixture.mdx").write_text("Changed prose [Finding #1].")
    report = publication_snapshot.validate_snapshot(root, snapshot)
    assert report["ok"] is False
    assert "snapshot_content_changed" in {issue["code"] for issue in report["issues"]}


def test_snapshot_rejects_retracted_and_conflicting_records(content_fixture) -> None:
    root, record = content_fixture
    record = {**record, "verification_status": "retracted"}
    (root / "articles/fixture-findings.json").write_text(json.dumps({"1": record}))
    _, _, issues = publication_snapshot.collect_content(root)
    assert {issue["code"] for issue in issues} >= {"non_verified_finding", "conflicting_finding"}


def test_snapshot_rejects_missing_cited_finding(content_fixture) -> None:
    root, _ = content_fixture
    (root / "articles/fixture.mdx").write_text("New claim [Finding #999].")
    _, _, issues = publication_snapshot.collect_content(root)
    assert any(issue["code"] == "missing_cited_finding" and issue["finding_id"] == "999" for issue in issues)


def test_snapshot_live_audit_detects_same_timestamp_summary_correction(content_fixture, tmp_path: Path) -> None:
    root, record = content_fixture
    snapshot = write_snapshot(root)
    db_path = tmp_path / "findings.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE findings(id INTEGER,summary TEXT,finding_type TEXT,confidence TEXT,claim_type TEXT,verification_status TEXT,date_of_event TEXT,source_datasets TEXT)")
        db.execute("INSERT INTO findings VALUES(1,'Corrected fact','financial','high','paraphrase','verified','2024-01-01','[\"courtlistener\"]')")
        db.execute("CREATE TABLE finding_evidence(finding_id INTEGER,evidence_type TEXT,evidence_ref TEXT,source_quote TEXT)")
        db.execute("INSERT INTO finding_evidence VALUES(1,'url','https://example.test/record','Exact source text')")
    report = publication_snapshot.validate_snapshot(root, snapshot, db_path)
    assert any(issue["code"] == "database_drift" and "summary" in issue["changed_fields"] for issue in report["issues"])


@pytest.mark.parametrize("current_sources,code", [
    ('["dehashed"]', "confidence_exceeds_cap"),
    ('["intelx"]', "confidence_exceeds_cap"),
    (None, "invalid_source_datasets"),
    ('[]', "invalid_source_datasets"),
    ('["unsupported-source"]', "invalid_source_datasets"),
])
def test_snapshot_database_audit_rechecks_sources_excluded_from_fingerprint(
    content_fixture, tmp_path, current_sources, code,
):
    root, record = content_fixture
    snapshot = write_snapshot(root)
    db_path = tmp_path / "current-provenance.db"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE findings(id INTEGER,summary TEXT,finding_type TEXT,confidence TEXT,claim_type TEXT,verification_status TEXT,date_of_event TEXT,source_datasets TEXT)")
        db.execute("INSERT INTO findings VALUES(1,'Recorded fact','financial','high','paraphrase','verified','2024-01-01','[\"courtlistener\"]')")
        db.execute("CREATE TABLE finding_evidence(finding_id INTEGER,evidence_type TEXT,evidence_ref TEXT,source_quote TEXT)")
        db.execute("INSERT INTO finding_evidence VALUES(1,'url','https://example.test/record','Exact source text')")
    assert publication_snapshot.validate_snapshot(root, snapshot, db_path)["ok"] is True
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE findings SET source_datasets=? WHERE id=1", (current_sources,))
    before = db_path.read_bytes()

    report = publication_snapshot.validate_snapshot(root, snapshot, db_path)

    assert report["ok"] is False
    issue = next(issue for issue in report["issues"] if issue["code"] == code)
    assert (issue["finding_id"], issue["file"], issue["scope"], issue["location"]) == (
        "1", str(db_path), "database", "findings[1]",
    )
    if code == "confidence_exceeds_cap":
        assert issue["max_confidence"] == "medium"
    assert not any(issue["code"] == "database_drift" for issue in report["issues"])
    assert db_path.read_bytes() == before
    assert "source_datasets" not in publication_snapshot.normalize_finding(record)


@pytest.mark.parametrize("payload,code,location", [
    (None, "invalid_content_shape", None),
    ([], "invalid_content_shape", None),
    ({"findings": None}, "invalid_finding_collection", None),
    ({"citation_findings": None}, "invalid_finding_collection", None),
    ({"findings": [None]}, "invalid_finding_record", "findings[0]"),
])
def test_snapshot_reports_malformed_content_at_its_file(content_fixture, payload, code, location):
    root, _ = content_fixture
    (root / "dossiers/broken.json").write_text(json.dumps(payload))
    _, _, issues = publication_snapshot.collect_content(root)
    issue = next(issue for issue in issues if issue["code"] == code)
    assert issue["file"] == "dossiers/broken.json"
    if location:
        assert issue["location"] == location


@pytest.mark.parametrize("evidence,code", [
    (None, "invalid_evidence_collection"),
    ({}, "invalid_evidence_collection"),
    ([None], "invalid_evidence_record"),
    ([], "missing_finding_evidence"),
    ([{"evidence_type": "url", "evidence_ref": "", "source_quote": "Exact words"}], "invalid_evidence_ref"),
    ([{"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": None}], "missing_source_quote"),
    ([{"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": "  "}], "missing_source_quote"),
    ([{"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": ["Exact words"]}], "missing_source_quote"),
    ([{"evidence_type": "file", "evidence_ref": "https://example.test/source", "source_quote": "Exact words"}], "evidence_type_mismatch"),
    ([{"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": "Exact words", "assessment": []}], "invalid_evidence_field"),
    ([{"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": "First excerpt"},
      {"evidence_type": "url", "evidence_ref": "https://example.test/source", "source_quote": "Second excerpt"}], "duplicate_evidence_ref"),
])
def test_snapshot_rejects_verified_records_with_malformed_provenance(content_fixture, evidence, code):
    root, record = content_fixture
    record["evidence"] = evidence
    (root / "dossiers/fixture.json").write_text(json.dumps({"findings": [record]}))
    findings, _, issues = publication_snapshot.collect_content(root)
    issue = next(issue for issue in issues if issue["code"] == code)
    assert issue["file"] == "dossiers/fixture.json"
    assert issue["finding_id"] == "1"
    assert issue["location"] == "findings[0]"
    assert "1" not in findings


def test_snapshot_reports_missing_evidence_field(content_fixture):
    root, record = content_fixture
    del record["evidence"]
    (root / "dossiers/fixture.json").write_text(json.dumps({"findings": [record]}))
    findings, _, issues = publication_snapshot.collect_content(root)
    assert not findings
    assert any(issue["code"] == "invalid_evidence_collection" and issue["finding_id"] == "1" for issue in issues)


@pytest.mark.parametrize("updates,code", [
    ({"claim_type": "inference", "confidence": "confirmed"}, "confidence_exceeds_cap"),
    ({"claim_type": "synthesis", "confidence": "high"}, "confidence_exceeds_cap"),
    ({"claim_type": "paraphrase", "confidence": "confirmed"}, "confidence_exceeds_cap"),
    ({"claim_type": "direct_quote", "confidence": "high", "source_datasets": ["dehashed"]}, "confidence_exceeds_cap"),
    ({"source_datasets": '["intelx"]'}, "confidence_exceeds_cap"),
    ({"source_datasets": None}, "invalid_source_datasets"),
    ({"source_datasets": "courtlistener"}, "invalid_source_datasets"),
    ({"source_datasets": ["unsupported-source"]}, "invalid_source_datasets"),
    ({"confidence": "certain"}, "invalid_confidence"),
    ({"claim_type": "unknown"}, "invalid_claim_type"),
    ({"summary": None}, "missing_finding_summary"),
    ({"summary": []}, "invalid_finding_field"),
    ({"id": None}, "invalid_finding_id"),
])
def test_snapshot_rejects_verified_legacy_metadata_and_caps_without_rewriting(content_fixture, updates, code):
    root, record = content_fixture
    record.update(updates)
    path = root / "dossiers/fixture.json"
    raw = json.dumps({"findings": [record]})
    path.write_text(raw)
    findings, _, issues = publication_snapshot.collect_content(root)
    assert not findings
    assert any(issue["code"] == code and issue["file"] == "dossiers/fixture.json" for issue in issues)
    assert path.read_text() == raw


def test_snapshot_validation_uses_only_exported_policy_metadata(content_fixture, monkeypatch):
    root, record = content_fixture
    record["evidence"] = [{"evidence_type": "efta", "evidence_ref": "EFTA00000001", "source_quote": "Exact corpus words"}]
    # Source metadata is absent from some historical exports and is not part of
    # schema 1. Preserve its fingerprint shape while checking metadata supplied.
    del record["source_datasets"]
    (root / "dossiers/fixture.json").write_text(json.dumps({"findings": [record]}))

    def unexpected_read(*args, **kwargs):
        raise AssertionError("Static snapshot validation must not query a DB or source corpus")

    monkeypatch.setattr(sqlite3, "connect", unexpected_read)
    monkeypatch.setattr(publication_snapshot.finding_policy, "_load_evidence_text", unexpected_read)
    findings, _, issues = publication_snapshot.collect_content(root)
    assert issues == []
    assert "source_datasets" not in findings["1"]
    assert findings["1"] == publication_snapshot.normalize_finding(record)


@pytest.mark.parametrize("raw,code", [("{broken", "invalid_snapshot_json"), ("null", "invalid_snapshot_shape"), ("[]", "invalid_snapshot_shape")])
def test_snapshot_reports_invalid_snapshot_artifact(content_fixture, raw, code):
    root, _ = content_fixture
    snapshot = root / "finding-catalog.json"
    snapshot.write_text(raw)
    report = publication_snapshot.validate_snapshot(root, snapshot)
    assert report["ok"] is False
    assert any(issue["code"] == code and issue["file"] == str(snapshot) for issue in report["issues"])


@pytest.mark.parametrize("updates,code", [
    ({"evidence": None}, "invalid_evidence_collection"),
    ({"confidence": "confirmed"}, "confidence_exceeds_cap"),
])
def test_snapshot_build_cannot_materialize_verified_invalid_claims(content_fixture, monkeypatch, capsys, updates, code):
    root, record = content_fixture
    record.update(updates)
    (root / "dossiers/fixture.json").write_text(json.dumps({"findings": [record]}))
    output = root / "candidate.json"
    output.write_text("preserve prior artifact")
    monkeypatch.setattr(sys, "argv", ["publication_snapshot.py", "build", "--content-dir", str(root), "--output", str(output)])
    assert publication_snapshot.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert any(issue["code"] == code and issue["finding_id"] == "1" for issue in report["issues"])
    assert output.read_text() == "preserve prior artifact"


def test_snapshot_citations_distinguish_invalid_records_from_absent_records(content_fixture):
    root, record = content_fixture
    record["evidence"] = None
    (root / "dossiers/fixture.json").write_text(json.dumps({"findings": [record]}))
    (root / "articles/fixture.mdx").write_text("Invalid [Finding #1]. Repeated [Finding #1]. Absent [Finding #999].")
    _, _, issues = publication_snapshot.collect_content(root)
    citations = [issue for issue in issues if issue["code"] in {"missing_cited_finding", "unpublishable_cited_finding"}]
    assert citations == [
        {"code": "unpublishable_cited_finding", "finding_id": "1", "file": "articles/fixture.mdx"},
        {"code": "missing_cited_finding", "finding_id": "999", "file": "articles/fixture.mdx"},
    ]


def test_snapshot_reports_invalid_json_at_its_content_file(content_fixture):
    root, _ = content_fixture
    (root / "articles/broken-findings.json").write_text("{broken")
    _, _, issues = publication_snapshot.collect_content(root)
    assert any(issue["code"] == "invalid_content_json" and issue["file"] == "articles/broken-findings.json" for issue in issues)


def test_snapshot_preserves_root_cli_output_contract(content_fixture, monkeypatch, capsys):
    root, _ = content_fixture
    snapshot = write_snapshot(root)
    monkeypatch.setattr(sys, "argv", ["publication_snapshot.py", "check", "--content-dir", str(root), "--snapshot", str(snapshot)])
    assert publication_snapshot.main() == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    monkeypatch.setattr(sys, "argv", ["publication_snapshot.py", "build", "--content-dir", str(root)])
    with pytest.raises(SystemExit) as exc:
        publication_snapshot.main()
    assert exc.value.code == 2
    assert "build requires --output" in capsys.readouterr().err
