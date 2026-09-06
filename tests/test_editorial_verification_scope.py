"""Offline boundary tests for current-content editorial verification."""
import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import evidence_audit as audit
from scripts import review_dossier_checks as reviews

ROOT = Path(__file__).resolve().parents[1]


def fixture_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE findings(id INTEGER PRIMARY KEY, profile_id TEXT, summary TEXT,
              claim_type TEXT, confidence TEXT, verification_status TEXT);
            CREATE TABLE finding_evidence(finding_id INTEGER, evidence_ref TEXT, source_quote TEXT);
            CREATE TABLE investigation_config(key TEXT, value TEXT);
            INSERT INTO investigation_config VALUES('active_profile','alpha');
        """)
        db.executemany("INSERT INTO findings VALUES(?,?,?,?,?,?)", [
            (1, "alpha", "A company filed a report", "direct_quote", "confirmed", "verified"),
            (2, "beta", "Unrelated broken evidence", "inference", "confirmed", "disputed"),
            (3, "alpha", "Another company filed a report", "direct_quote", "confirmed", "verified"),
        ])
        db.executemany("INSERT INTO finding_evidence VALUES(?,?,?)", [
            (1, "EFTA000001", "A company filed a report in January."),
            (2, "EFTA000002", None),
            (3, "EFTA000003", "A company filed a report in January and concealed the payment."),
        ])
    return path


@pytest.fixture
def sources(tmp_path):
    path = tmp_path / "documents.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE documents(bates_id TEXT, ocr_text TEXT)")
        db.executemany("INSERT INTO documents VALUES(?,?)", [
            ("EFTA000001", "Record: A company filed a report in January. It was accepted."),
            ("EFTA000003", "A company filed a report in January and disclosed every payment."),
        ])
    return path


def test_current_article_scope_excludes_other_profiles_and_uses_full_quote(tmp_path, sources):
    db = fixture_db(tmp_path / "selected.db")
    article = tmp_path / "new.mdx"
    article.write_text("A company filed a report [Finding #1].")
    result = audit.build_report(db, profile="alpha", article=article, documents_db=sources)
    assert result["scope"]["finding_ids"] == [1]
    assert result["scope"]["content_sha256"] == hashlib.sha256(article.read_bytes()).hexdigest()
    assert result["status"] == "passed"
    article.write_text("The company concealed a payment [EFTA000003].")
    result = audit.build_report(db, profile="alpha", article=article, documents_db=sources)
    assert result["scope"]["finding_ids"] == [3]
    assert result["cross_check_counts"] == {"match": 0, "mismatch": 1, "unknown": 0}
    assert result["status"] == "needs_review"


def test_unknown_missing_and_foreign_citations_do_not_pass(tmp_path):
    db = fixture_db(tmp_path / "selected.db")
    article = tmp_path / "article.mdx"
    article.write_text("Claim [Finding #1] [Finding #2] [SEC:unmapped].")
    missing_corpus = tmp_path / "absent.db"
    result = audit.build_report(db, profile="alpha", article=article, documents_db=missing_corpus)
    assert result["scope"]["missing_or_out_of_profile_finding_ids"] == [2]
    assert result["scope"]["unmapped_citations"] == ["SEC:unmapped"]
    assert result["cross_check_counts"]["unknown"] == 1
    assert result["checks_complete"] is False
    assert result["status"] != "passed"
    assert not missing_corpus.exists()
    article.write_text("No explicit citation.")
    assert audit.build_report(db, profile="alpha", article=article)["status"] == "incomplete"


@pytest.mark.parametrize("reference", ["990:123456789", "COURT-DATA:example", "OffshoreAlert:example",
                                      "LittleSis:1234", "SEC ADSH 0001234567-20-123456"])
def test_unresolved_citation_variants_remain_incomplete(tmp_path, sources, reference):
    db = fixture_db(tmp_path / "selected.db")
    article = tmp_path / "article.mdx"
    article.write_text(f"Claim [Finding #1]. Another claim [{reference}].")
    report = audit.build_report(db, profile="alpha", article=article, documents_db=sources)
    assert report["scope"]["unmapped_citations"] == [reference]
    assert report["status"] == "incomplete"


def test_shared_primary_record_is_overlap_not_duplicate_gate(tmp_path, sources):
    db = fixture_db(tmp_path / "selected.db")
    with sqlite3.connect(db) as conn:
        for ident in (4, 5):
            conn.execute("INSERT INTO findings VALUES(?, 'alpha', 'Different claim', 'paraphrase', 'high', 'verified')", (ident,))
            conn.execute("INSERT INTO finding_evidence VALUES(?, 'EFTA000001', 'A company filed a report in January.')", (ident,))
    article = tmp_path / "article.mdx"
    article.write_text("The record [EFTA000001].")
    result = audit.build_report(db, profile="alpha", article=article, documents_db=sources)
    assert result["status"] == "passed"
    assert len(result["source_overlap_candidates"]) == 1
    assert "not an adjudicated duplicate" in result["source_overlap_candidates"][0]["assessment"]


def test_non_efta_artifacts_and_inherited_database_are_used(tmp_path):
    db = fixture_db(tmp_path / "alternate.db")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE finding_evidence SET evidence_ref='SEC:example' WHERE finding_id=1")
    (tmp_path / "record.txt").write_text("A company filed a report in January.")
    manifest = tmp_path / "sources.json"
    manifest.write_text(json.dumps({"SEC:example": {"path": "record.txt"}}))
    output = tmp_path / "audit.json"
    before = db.read_bytes()
    env = {**os.environ, "ITHILDIN_DB_PATH": str(db), "ITHILDIN_PROFILE": "alpha"}
    run = subprocess.run([sys.executable, str(ROOT / "scripts/evidence_audit.py"), "report",
                          "--finding-id", "1", "--source-texts", str(manifest), "--output", str(output)],
                         cwd=tmp_path, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads(output.read_text())
    assert result["database"] == str(db)
    assert result["profile"] == "alpha"
    assert result["status"] == "passed"
    assert db.read_bytes() == before


def test_dossier_batch_materializes_current_hash_packets(tmp_path, monkeypatch):
    directory = tmp_path / "dossiers"
    directory.mkdir()
    (directory / "_index.json").write_text(json.dumps([
        {"name": "first", "slug": "first"}
    ]))
    for slug in ("first", "second"):
        (directory / f"{slug}.json").write_text(json.dumps({
            "name": slug, "slug": slug, "findings": [],
            "curation": {"lead": "<p>Reference prose.</p>", "sections": [
                {"id": "background", "title": "Background", "content": "<p>More prose.</p>", "viz": None}]},
        }))
    monkeypatch.setattr(reviews, "DOSSIER_DIR", directory)
    monkeypatch.setattr(reviews, "INDEX_PATH", directory / "_index.json")
    monkeypatch.setattr(reviews, "load_global_finding_statuses", lambda: {})
    monkeypatch.setattr(reviews, "record_review", lambda _: pytest.fail("read-only batch wrote DB"))
    packet_dir = tmp_path / "packets"
    aggregate = tmp_path / "batch.json"
    reviews.cmd_batch(argparse.Namespace(top=None, output=aggregate, no_record=True, packet_dir=packet_dir))
    results = json.loads(aggregate.read_text())
    assert {item["slug"] for item in results} == {"first", "second"}
    for item in results:
        packet = json.loads((packet_dir / f"automated-{item['slug']}.json").read_text())
        assert packet == item
        assert packet["content_sha256"] == reviews.dossier_content_sha256(item["slug"])


def test_discovery_snapshot_defaults_to_environment_database(tmp_path, monkeypatch):
    exporter_path = ROOT / ".codex/skills/discover-investigations/scripts/export_snapshot.py"
    spec = importlib.util.spec_from_file_location("editorial_export_snapshot", exporter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    db = fixture_db(tmp_path / "alternate.db")
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(db))
    monkeypatch.setattr(sys, "argv", [str(exporter_path), "--output", str(tmp_path / "out.json")])
    assert module.parse_args().db == str(db)
    before = db.read_bytes()
    result = module.build_snapshot(db, tmp_path)
    assert result["database"]["path"] == str(db)
    assert [item["id"] for item in result["data"]["findings"]] == [1, 2, 3]
    assert db.read_bytes() == before


def test_automated_packet_rejects_concurrent_content_change(tmp_path, monkeypatch):
    dossier = tmp_path / "example.json"
    dossier.write_text('{"version": 1}')
    monkeypatch.setattr(reviews, "DOSSIER_DIR", tmp_path)

    def change_while_checking(*_):
        dossier.write_text('{"version": 2}')
        return {"verdict": "PASS"}

    monkeypatch.setattr(reviews, "run_checks", change_while_checking)
    with pytest.raises(ValueError, match="changed during automated checks"):
        reviews.bound_checks("example")


def test_audit_output_cannot_overwrite_selected_database(tmp_path):
    db = fixture_db(tmp_path / "selected.db")
    before = db.read_bytes()
    run = subprocess.run([sys.executable, str(ROOT / "scripts/evidence_audit.py"), "report",
                          "--db", str(db), "--profile", "alpha", "--output", str(db)],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert "must not overwrite" in run.stderr
    assert db.read_bytes() == before


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_audit_output_cannot_create_sqlite_sidecar(tmp_path, suffix):
    db = fixture_db(tmp_path / "selected.db")
    output = Path(str(db) + suffix)
    before = db.read_bytes()
    run = subprocess.run([sys.executable, str(ROOT / "scripts/evidence_audit.py"), "report",
                          "--db", str(db), "--profile", "alpha", "--output", str(output)],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert "must not overwrite" in run.stderr
    assert not output.exists()
    assert db.read_bytes() == before


@pytest.mark.parametrize("kind", ["database", "article", "source", "sidecar"])
def test_audit_output_rejects_existing_hardlink_aliases(tmp_path, kind):
    database = tmp_path / "selected.db"
    database.write_bytes(b"untouched database")
    source = Path(str(database) + "-wal") if kind == "sidecar" else tmp_path / kind
    if kind == "database":
        source = database
    else:
        source.write_bytes(b"untouched source")
    output = tmp_path / "output-alias.json"
    os.link(source, output)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="must not overwrite"):
        audit.ensure_safe_output(output, [database, source] if kind != "sidecar" else [database],
                                 databases=[database])
    assert source.read_bytes() == before
    assert output.read_bytes() == before


def test_unattended_wrapper_dry_run_is_unique_and_never_launches_model(tmp_path):
    content = tmp_path / "content"
    dossiers = content / "dossiers"
    dossiers.mkdir(parents=True)
    (dossiers / "example.json").write_text('{}')
    slug_file = tmp_path / "slugs.txt"
    slug_file.write_text("example\nexample\n")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    marker = tmp_path / "model-was-called"
    stub = bindir / "claude"
    stub.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n')
    stub.chmod(0o755)
    env = {**os.environ, "ITHILDIN_PROFILE": "alpha", "ITHILDIN_DB_PATH": str(tmp_path / "unused.db"),
           "ITHILDIN_CONTENT_DIR": str(content), "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
           "TMPDIR": str(tmp_path)}
    script = str(ROOT / "scripts/batch_review_dossiers.sh")
    runs = [subprocess.run(["/bin/bash", script, "--dry-run", "2", str(slug_file)],
                          capture_output=True, text=True, env=env) for _ in range(2)]
    for run in runs:
        assert run.returncode == 0, run.stderr
    run_dirs = [Path(run.stdout.split("Run artifacts: ", 1)[1].splitlines()[0]) for run in runs]
    assert run_dirs[0] != run_dirs[1]
    for run_dir in run_dirs:
        prompts = list(run_dir.glob("*/prompt.txt"))
        assert len(prompts) == 1
        prompt = prompts[0].read_text()
        assert '/review-dossiers --target "example" --fix' in prompt
        assert "content_sha256" in prompt
        assert "coordinator will persist" in prompt
    assert not marker.exists()
    assert not (tmp_path / "unused.db").exists()
