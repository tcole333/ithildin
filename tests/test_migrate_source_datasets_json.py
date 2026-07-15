"""Regression coverage for the comma-joined source_datasets migration.

Dispatcher imports before 2026-04 stored findings.source_datasets as raw
comma-joined strings ("edgar,parazero_20f_2026"), which broke
`findings_tracker.py verify` with "source_datasets is not valid JSON".
"""

import json
import sqlite3

import pytest

from scripts import migrate_source_datasets_json as migration
from scripts.dispatcher import normalize_source_datasets_value
from tools import findings_tracker, lead_tracker

LEGACY_STRING = "edgar,parazero_20f_2026,scisparc_20f_2025,edgar_forms_345"
EVIDENCE_REF = "CourtListener:docket/12345"
EVIDENCE_QUOTE = "Defendants agreed to pay $2.5M under the settlement filing."


@pytest.fixture
def migration_db(tmp_path, monkeypatch):
    db_path = tmp_path / "investigation.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    findings_tracker.get_db().close()
    return db_path


def _seed_finding(db_path, *, source_datasets, profile_id="hfia",
                  verification_status="unverified", claim_type="paraphrase",
                  with_evidence=True):
    db = sqlite3.connect(db_path)
    try:
        cursor = db.execute(
            """
            INSERT INTO findings (target_name, finding_type, summary, detail,
                                  source_datasets, confidence, claim_type,
                                  verification_status, profile_id)
            VALUES (?, 'financial', ?, 'detail', ?, 'medium', ?, ?, ?)
            """,
            (
                "ParaZero Technologies",
                "Shared officers across HFIA-linked microcaps",
                source_datasets,
                claim_type,
                verification_status,
                profile_id,
            ),
        )
        finding_id = cursor.lastrowid
        if with_evidence:
            db.execute(
                """
                INSERT INTO finding_evidence (finding_id, evidence_type,
                                              evidence_ref, source_quote)
                VALUES (?, 'ref', ?, ?)
                """,
                (finding_id, EVIDENCE_REF, EVIDENCE_QUOTE),
            )
        db.commit()
        return finding_id
    finally:
        db.close()


def _fetch_finding(db_path, finding_id):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        return db.execute(
            "SELECT * FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
    finally:
        db.close()


def _fetch_corrections(db_path, finding_id):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        return db.execute(
            "SELECT * FROM corrections WHERE table_name = 'findings' "
            "AND record_id = ? AND field_name = 'source_datasets'",
            (finding_id,),
        ).fetchall()
    finally:
        db.close()


def test_verify_succeeds_on_previously_string_formatted_row(migration_db):
    """The regression: a comma-string row must be verifiable after migration."""
    finding_id = _seed_finding(migration_db, source_datasets=LEGACY_STRING)

    with pytest.raises(ValueError, match="not valid JSON"):
        findings_tracker.verify_finding(finding_id, verified_by="test")

    summary = migration.main(["--db", str(migration_db), "--apply"])
    assert summary["updated"] == 1

    row = _fetch_finding(migration_db, finding_id)
    stored = json.loads(row["source_datasets"])
    # Variant spelling maps onto the registered token; ad-hoc filing labels
    # are preserved verbatim rather than dropped.
    assert stored == ["edgar", "parazero_20f_2026", "scisparc_20f_2025"]
    assert row["profile_id"] == "hfia"
    assert row["verification_status"] == "unverified"

    findings_tracker.verify_finding(finding_id, verified_by="test")
    assert _fetch_finding(migration_db, finding_id)["verification_status"] == "verified"


def test_migration_writes_corrections_audit_row(migration_db):
    finding_id = _seed_finding(migration_db, source_datasets=LEGACY_STRING)
    migration.main(["--db", str(migration_db), "--apply"])

    corrections = _fetch_corrections(migration_db, finding_id)
    assert len(corrections) == 1
    correction = corrections[0]
    assert correction["old_value"] == LEGACY_STRING
    assert json.loads(correction["new_value"]) == [
        "edgar", "parazero_20f_2026", "scisparc_20f_2025",
    ]
    assert correction["corrected_by"] == migration.CORRECTED_BY
    assert correction["correction_type"] == "refinement"


def test_dry_run_writes_nothing(migration_db):
    finding_id = _seed_finding(migration_db, source_datasets=LEGACY_STRING)
    summary = migration.main(["--db", str(migration_db)])

    assert summary["updated"] == 1
    assert summary["applied"] is False
    assert _fetch_finding(migration_db, finding_id)["source_datasets"] == LEGACY_STRING
    assert _fetch_corrections(migration_db, finding_id) == []


def test_valid_json_rows_are_untouched(migration_db):
    finding_id = _seed_finding(migration_db, source_datasets='["edgar", "fec"]')
    summary = migration.main(["--db", str(migration_db), "--apply"])

    assert summary["affected"] == 0
    assert _fetch_finding(migration_db, finding_id)["source_datasets"] == '["edgar", "fec"]'
    assert _fetch_corrections(migration_db, finding_id) == []


def test_verified_status_and_profile_survive_migration(migration_db):
    finding_id = _seed_finding(
        migration_db,
        source_datasets="edgar,viewbix_10k_2026",
        verification_status="verified",
    )
    migration.main(["--db", str(migration_db), "--apply"])

    row = _fetch_finding(migration_db, finding_id)
    assert row["verification_status"] == "verified"
    assert row["profile_id"] == "hfia"
    assert json.loads(row["source_datasets"]) == ["edgar", "viewbix_10k_2026"]


def test_write_paths_still_reject_unregistered_tokens(migration_db):
    finding_id = _seed_finding(migration_db, source_datasets='["edgar"]')

    with pytest.raises(ValueError, match="Unsupported source token"):
        findings_tracker.update_finding(
            finding_id, "source_datasets", '["parazero_20f_2026"]',
            reason="attempt to store ad-hoc label",
        )
    with pytest.raises(ValueError, match="Unsupported source token"):
        findings_tracker.add_finding(
            target_name="ParaZero Technologies",
            summary="new finding with ad-hoc source token",
            source_datasets=["parazero_20f_2026"],
        )


def test_evidence_audit_warns_on_preserved_labels_and_errors_on_malformed(migration_db):
    migrated_id = _seed_finding(migration_db, source_datasets=LEGACY_STRING)
    malformed_id = _seed_finding(
        migration_db, source_datasets="doj_usao_mn,web_news", with_evidence=False,
    )
    migration.main(["--db", str(migration_db), "--apply"])

    # Re-break one row the way legacy data looked before migration.
    db = sqlite3.connect(migration_db)
    db.execute(
        "UPDATE findings SET source_datasets = 'doj_usao_mn,web_news' WHERE id = ?",
        (malformed_id,),
    )
    db.commit()
    db.close()

    report = findings_tracker.audit_finding_evidence(all_profiles=True)
    by_finding = {}
    for item in report["issues"]:
        by_finding.setdefault(item["finding_id"], []).append(item)

    preserved = [
        i for i in by_finding.get(migrated_id, [])
        if i["code"] == "unregistered_source_token"
    ]
    assert len(preserved) == 1
    assert preserved[0]["severity"] == "warning"
    assert "parazero_20f_2026" in preserved[0]["message"]

    malformed = [
        i for i in by_finding.get(malformed_id, [])
        if i["code"] == "invalid_source_datasets"
    ]
    assert len(malformed) == 1
    assert malformed[0]["severity"] == "error"


def test_canonicalize_token_maps_variants_and_preserves_labels():
    assert migration.canonicalize_token("edgar_forms_345") == "edgar"
    assert migration.canonicalize_token("sec_edgar_def14a") == "edgar"
    assert migration.canonicalize_token("sec_edgar") == "sec_edgar"  # registered as-is
    assert migration.canonicalize_token("opencorporates_us_ca") == "opencorporates"
    assert migration.canonicalize_token("courtlistener_recap") == "courtlistener"
    assert migration.canonicalize_token("kabasshouse") == "kabass"  # existing alias
    assert migration.canonicalize_token("websearch") == "web_search"
    assert migration.canonicalize_token("irs_990") == "990"
    # Document and publisher labels are information — preserved verbatim.
    assert migration.canonicalize_token("parazero_20f_2026") == "parazero_20f_2026"
    assert migration.canonicalize_token("startribune") == "startribune"
    assert migration.canonicalize_token("web_dailymail") == "web_dailymail"


def test_dispatcher_normalizes_source_datasets_on_import():
    assert normalize_source_datasets_value(None) is None
    assert normalize_source_datasets_value("   ") is None
    assert normalize_source_datasets_value("edgar,parazero_20f_2026") == json.dumps(
        ["edgar", "parazero_20f_2026"]
    )
    assert normalize_source_datasets_value(["edgar", "edgar", " fec "]) == json.dumps(
        ["edgar", "fec"]
    )
    assert normalize_source_datasets_value('["edgar", "fec"]') == json.dumps(
        ["edgar", "fec"]
    )
    assert normalize_source_datasets_value(990) == json.dumps(["990"])
