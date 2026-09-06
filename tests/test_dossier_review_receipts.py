import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from scripts import review_dossier_checks as reviews


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    content = tmp_path / "content"
    directory = content / "dossiers"
    directory.mkdir(parents=True)
    links = {f"Example {n}": f"example-{n}" for n in range(5)}
    index = [{"name": "Synthetic Subject", "slug": "synthetic-subject"}]
    index.extend({"name": name, "slug": slug} for name, slug in links.items())
    index_path = directory / "_index.json"
    index_path.write_text(json.dumps(index))
    prose_links = ", ".join(f'<a href="/dossiers/{slug}">{name}</a>' for name, slug in links.items())
    data = {
        "slug": "synthetic-subject", "name": "Synthetic Subject",
        "findings": [{"id": 1, "claim_type": "direct_quote", "confidence": "confirmed",
                      "verification_status": "verified", "summary": "A company was formed in 2020."}],
        "curation": {
            "lead": "<p>Synthetic Subject was convicted of fraud [Finding #1].</p>",
            "system_role": "Business owner", "applicable_models": [],
            "sections": [{"id": "background", "title": "Background", "viz": None,
                          "content": f"<p>Synthetic Subject bribed officials at {prose_links} [Finding #1].</p>"}],
        },
    }
    path = directory / "synthetic-subject.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(reviews, "DOSSIER_DIR", directory)
    monkeypatch.setattr(reviews, "INDEX_PATH", index_path)
    monkeypatch.setattr(reviews, "DB_PATH", tmp_path / "scratch.db")
    receipt_file = content / "dossier-review-receipts.json"
    monkeypatch.setattr(reviews, "RECEIPT_PATH", receipt_file)
    return {"path": path, "data": data, "receipt_file": receipt_file, "content": content}


def review(verdict="PASS"):
    # Test fixture judgments, never persisted to the repository's real content.
    issues = [] if verdict == "PASS" else [
        {"severity": "BLOCKING", "detail": "The cited finding does not support the crime allegations."}
    ]
    return {"slug": "synthetic-subject", "content_sha256": reviews.dossier_content_sha256("synthetic-subject"),
            "reviewer": "fixture-reviewer", "reviewed_at": "2020-01-01T00:00:00Z",
            "verdict": verdict, "llm_issues": issues}


def no_db(*args, **kwargs):
    raise AssertionError("portable receipt checks must not access a database")


def test_automated_pass_does_not_imply_semantic_pass(dossier, monkeypatch):
    monkeypatch.setattr(reviews, "load_global_finding_statuses", no_db)
    assert reviews.run_checks("synthetic-subject", static_only=True)["verdict"] == "PASS"
    result = reviews.validate_receipts(dossier["receipt_file"])
    assert result["status"] == "failed"
    reviews.store_receipt(review("FAIL"), dossier["receipt_file"])
    result = reviews.validate_receipts(dossier["receipt_file"])
    assert result["status"] == "failed"
    assert "semantic verdict=FAIL" in result["failures"][0]["reason"]


def test_exact_content_pass_and_edit_invalidation_are_db_free(dossier, monkeypatch):
    monkeypatch.setattr(reviews, "get_review_db", no_db)
    monkeypatch.setattr(reviews, "load_global_finding_statuses", no_db)
    reviews.store_receipt(review(), dossier["receipt_file"])
    assert reviews.validate_receipts(dossier["receipt_file"])["status"] == "passed"
    dossier["path"].write_text(dossier["path"].read_text() + "\n")
    result = reviews.validate_receipts(dossier["receipt_file"])
    assert result["status"] == "failed"
    assert "stale content_sha256" in result["failures"][0]["reason"]


def test_current_semantic_receipt_cannot_override_static_evidence_blocker(dossier):
    dossier["data"]["findings"][0]["verification_status"] = "unverified"
    dossier["path"].write_text(json.dumps(dossier["data"]))
    reviews.store_receipt(review(), dossier["receipt_file"])
    result = reviews.validate_receipts(dossier["receipt_file"])
    assert result["status"] == "failed"
    assert "static verdict=FAIL" in result["failures"][0]["reason"]


@pytest.mark.parametrize("field,value", [
    ("content_sha256", None), ("reviewer", ""), ("reviewed_at", ""),
    ("verdict", None), ("llm_issues", None),
    ("llm_issues", [{"severity": "UNKNOWN", "detail": "unparsed issue"}]),
    ("llm_issues", [{"severity": "BLOCKING", "detail": "Contradiction"}]),
])
def test_incomplete_or_contradictory_reviews_fail_closed(dossier, field, value):
    supplied = review()
    supplied[field] = value
    with pytest.raises(ValueError):
        reviews.record_llm_review(supplied)
    assert not reviews.DB_PATH.exists()


def test_legacy_database_review_stays_unbound(dossier):
    with sqlite3.connect(reviews.DB_PATH) as db:
        reviews.ensure_review_schema(db)
        db.execute("INSERT INTO dossier_llm_reviews(slug,issues_json) VALUES(?,?)",
                   ("synthetic-subject", "[]"))
    assert reviews.check_publish_gate()[0] is False
    reviews.record_llm_review(review("FAIL"))
    with sqlite3.connect(reviews.DB_PATH) as db:
        rows = db.execute("SELECT content_sha256, verdict FROM dossier_llm_reviews ORDER BY id").fetchall()
    assert rows[0] == (None, None)
    assert rows[1] == (reviews.dossier_content_sha256("synthetic-subject"), "FAIL")


def test_unindexed_curated_content_also_requires_receipt(dossier):
    reviews.store_receipt(review(), dossier["receipt_file"])
    extra = copy.deepcopy(dossier["data"])
    extra["slug"] = "another-subject"
    (dossier["path"].parent / "another-subject.json").write_text(json.dumps(extra))
    result = reviews.validate_receipts(dossier["receipt_file"])
    assert result["status"] == "failed"
    assert result["failures"][0]["slug"] == "another-subject"


def test_duplicate_receipts_are_rejected(dossier):
    dossier["receipt_file"].write_text(json.dumps({"schema_version": 1, "reviews": [review(), review()]}))
    assert "duplicate receipt" in reviews.validate_receipts(dossier["receipt_file"])["failures"][0]["reason"]


def test_cli_validates_selected_content_tree_without_creating_database(dossier, tmp_path):
    reviews.store_receipt(review(), dossier["receipt_file"])
    db_path = tmp_path / "must-not-exist.db"
    result = subprocess.run(
        [sys.executable, str(Path(reviews.__file__).resolve()), "validate-receipts", "--json"],
        env={**os.environ, "ITHILDIN_CONTENT_DIR": str(dossier["content"]),
             "ITHILDIN_DB_PATH": str(db_path)}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert json.loads(result.stdout)["status"] == "passed"
    assert not db_path.exists()
