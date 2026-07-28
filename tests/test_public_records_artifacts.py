import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tools.public_records_artifacts import (
    ArtifactIntegrityError,
    PublicRecordsArtifactStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL = PROJECT_ROOT / "tools" / "public_records_artifacts.py"


@pytest.fixture
def artifact_store(tmp_path):
    with PublicRecordsArtifactStore(
        tmp_path / "artifacts.db", tmp_path / "objects"
    ) as store:
        yield store


def _put_source(store, tmp_path, content=b"primary document bytes"):
    source = tmp_path / "source.pdf"
    source.write_bytes(content)
    return store.put_file(
        source,
        source_id="us-test-recorder",
        canonical_ref="PROPERTY:us-test-recorder:document:123",
        source_url="https://records.example/document/123",
        retrieved_at="2026-07-28T12:00:00-04:00",
        retrieval_method="official_download",
        receipt_ref="receipt-123",
        rights_state="source_terms_recorded",
        retention_state="retain_with_receipt",
        restriction_state="source_public",
        media_type="application/pdf",
        retrieval={"http_status": 200},
        receipt={"request_id": "r-1"},
        rights={"terms_revision": "2026-06-01"},
        retention={"review_on": "2027-07-28"},
        restriction={"native_state": "public"},
        metadata={"county": "Example"},
    )


def test_store_initializes_wal_schema(tmp_path):
    db_path = tmp_path / "artifacts.db"
    with PublicRecordsArtifactStore(db_path, tmp_path / "objects") as store:
        assert store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert store.db.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0] == "1"
        tables = {
            row[0]
            for row in store.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "artifact",
            "acquisition_observation",
            "representation",
            "evidence",
            "restriction_event",
            "restriction_projection",
        } <= tables


def test_sha256_store_deduplicates_bytes_but_not_acquisitions(
    artifact_store, tmp_path
):
    first = _put_source(artifact_store, tmp_path)
    second = _put_source(artifact_store, tmp_path)

    digest = hashlib.sha256(b"primary document bytes").hexdigest()
    assert first["artifact"]["sha256"] == digest
    assert second["artifact"]["sha256"] == digest
    assert first["deduplicated_content"] is False
    assert second["deduplicated_content"] is True
    assert first["acquisition"]["observation_ref"] != second["acquisition"][
        "observation_ref"
    ]
    assert artifact_store.stats()["counts"] == {
        "artifacts": 1,
        "acquisitions": 2,
        "representations": 0,
        "evidence": 0,
        "restriction_events": 0,
        "current_restrictions": 0,
    }
    stored = artifact_store.artifact_path(digest)
    assert stored.read_bytes() == b"primary document bytes"
    assert first["acquisition"]["retrieved_at"] == "2026-07-28T16:00:00Z"
    assert first["acquisition"]["rights"] == {
        "terms_revision": "2026-06-01"
    }


def test_acquisition_and_provenance_rows_are_immutable(artifact_store, tmp_path):
    result = _put_source(artifact_store, tmp_path)
    acquisition_id = result["acquisition"]["acquisition_id"]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        artifact_store.db.execute(
            """
            UPDATE acquisition_observation
            SET rights_state = 'different'
            WHERE acquisition_id = ?
            """,
            (acquisition_id,),
        )


def test_versioned_representation_link_is_idempotent(artifact_store, tmp_path):
    source_result = _put_source(artifact_store, tmp_path)
    derived = tmp_path / "ocr.txt"
    derived.write_text("Recorded owner: EXAMPLE LLC", encoding="utf-8")

    kwargs = {
        "representation_type": "ocr_text",
        "media_type": "text/plain",
        "acquisition_id": source_result["acquisition"]["acquisition_id"],
        "ocr_engine": "tesseract",
        "ocr_version": "5.4.1",
        "parser_name": "deed-fields",
        "parser_version": "2",
        "model_name": "field-extractor",
        "model_version": "2026-07",
        "prompt_id": "deed-extract",
        "prompt_version": "3",
        "schema_id": "property-instrument",
        "schema_version": "1",
        "parameters": {"language": "eng"},
        "metadata": {"pages": [1]},
    }
    first = artifact_store.add_representation(
        source_result["artifact"]["sha256"], derived, **kwargs
    )
    second = artifact_store.add_representation(
        source_result["artifact"]["sha256"], derived, **kwargs
    )

    assert first["deduplicated_link"] is False
    assert second["deduplicated_link"] is True
    assert first["representation"]["derivation_fingerprint"] == second[
        "representation"
    ]["derivation_fingerprint"]
    assert first["representation"]["ocr_version"] == "5.4.1"
    assert first["representation"]["schema_version"] == "1"
    with pytest.raises(ValueError, match="provided together"):
        artifact_store.add_representation(
            source_result["artifact"]["sha256"],
            derived,
            representation_type="ocr_text",
            model_name="field-extractor",
        )


def test_evidence_preserves_exact_locator_and_validation(artifact_store, tmp_path):
    source_result = _put_source(artifact_store, tmp_path)
    derived = tmp_path / "ocr.txt"
    derived.write_text("Recorded owner: EXAMPLE LLC", encoding="utf-8")
    representation = artifact_store.add_representation(
        source_result["artifact"]["sha256"],
        derived,
        representation_type="ocr_text",
        ocr_engine="tesseract",
        ocr_version="5.4.1",
    )["representation"]

    kwargs = {
        "field_name": "grantee_name",
        "field_value": "EXAMPLE LLC",
        "validation_state": "format_validated",
        "validator_name": "party-name-validator",
        "validator_version": "1",
        "confidence": 0.88,
        "confidence_ceiling": 0.9,
        "acquisition_id": source_result["acquisition"]["acquisition_id"],
        "representation_id": representation["representation_id"],
        "page_number": 1,
        "page_label": "1",
        "region": {
            "x": 42.0,
            "y": 120.5,
            "width": 300.0,
            "height": 24.0,
            "coordinate_space": "pdf_points",
        },
        "exact_quote": "Recorded owner: EXAMPLE LLC",
        "validation_details": {"normalized_suffix": "LLC"},
    }
    first = artifact_store.add_evidence(
        representation["artifact_sha256"], **kwargs
    )
    second = artifact_store.add_evidence(
        representation["artifact_sha256"], **kwargs
    )

    evidence = first["evidence"]
    assert first["deduplicated_evidence"] is False
    assert second["deduplicated_evidence"] is True
    assert evidence["region"]["coordinate_space"] == "pdf_points"
    assert evidence["field_value"] == "EXAMPLE LLC"
    assert evidence["quote_sha256"] == hashlib.sha256(
        b"Recorded owner: EXAMPLE LLC"
    ).hexdigest()
    assert evidence["confidence"] == 0.88
    assert evidence["confidence_ceiling"] == 0.9


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"region": {"x": 1, "y": 2, "width": 3}}, "require x, y"),
        ({"confidence": 0.91, "confidence_ceiling": 0.9}, "cannot exceed"),
        (
            {
                "page_number": None,
                "region": None,
                "exact_quote": None,
                "page_label": None,
            },
            "requires a page",
        ),
    ],
)
def test_evidence_validation_rejects_incoherent_fields(
    artifact_store, tmp_path, changes, message
):
    result = _put_source(artifact_store, tmp_path)
    values = {
        "field_name": "recording_date",
        "field_value": "2026-07-01",
        "validation_state": "iso_date_valid",
        "validator_name": "iso-date",
        "validator_version": "1",
        "confidence": 0.9,
        "confidence_ceiling": 0.9,
        "page_number": 1,
        "page_label": None,
        "region": None,
        "exact_quote": "Recorded July 1, 2026",
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        artifact_store.add_evidence(result["artifact"]["sha256"], **values)


def test_restriction_events_keep_audit_history_and_latest_state(
    artifact_store, tmp_path
):
    result = _put_source(artifact_store, tmp_path)
    digest = result["artifact"]["sha256"]
    first = artifact_store.add_restriction(
        "artifact",
        digest,
        source_id="us-test-recorder",
        state="removed_from_source",
        effective_at="2026-07-10T12:00:00Z",
        reason="source_status_change",
        authority_ref="notice-17",
        details={"native_status": "removed"},
    )
    second = artifact_store.add_restriction(
        "artifact",
        digest,
        source_id="us-test-recorder",
        state="restored_by_source",
        effective_at="2026-07-20T12:00:00Z",
        details={"native_status": "available"},
    )
    older = artifact_store.add_restriction(
        "artifact",
        digest,
        source_id="us-test-recorder",
        state="source_review",
        effective_at="2026-07-15T12:00:00Z",
    )
    duplicate = artifact_store.add_restriction(
        "artifact",
        digest,
        source_id="us-test-recorder",
        state="restored_by_source",
        effective_at="2026-07-20T12:00:00Z",
        details={"native_status": "available"},
    )

    assert first["event"]["state"] == "removed_from_source"
    assert second["current"]["state"] == "restored_by_source"
    assert older["current"]["state"] == "restored_by_source"
    assert duplicate["deduplicated_event"] is True
    assert artifact_store.stats()["counts"]["restriction_events"] == 3
    shown = artifact_store.show("artifact", digest)
    assert shown["current_restriction"]["state"] == "restored_by_source"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        artifact_store.db.execute(
            """
            UPDATE restriction_event SET state = 'changed'
            WHERE restriction_event_id = ?
            """,
            (first["event"]["restriction_event_id"],),
        )


def test_verify_reports_hash_mismatch(artifact_store, tmp_path):
    result = _put_source(artifact_store, tmp_path)
    digest = result["artifact"]["sha256"]
    assert artifact_store.verify(digest)["status"] == "ok"

    artifact_store.artifact_path(digest).write_bytes(b"changed bytes")
    verification = artifact_store.verify(digest)
    assert verification["status"] == "failed"
    assert verification["results"][0]["status"] == "hash_mismatch"

    source = tmp_path / "same.pdf"
    source.write_bytes(b"primary document bytes")
    with pytest.raises(ArtifactIntegrityError, match="content address"):
        artifact_store.store_file(source)


def test_direct_script_cli_put_show_list_verify_and_output(tmp_path):
    db_path = tmp_path / "cli.db"
    store_path = tmp_path / "objects"
    source = tmp_path / "filing.txt"
    source.write_text("Complaint filed", encoding="utf-8")
    put_output = tmp_path / "put.json"

    put = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "put",
            str(source),
            "--source-id",
            "us-test-court",
            "--canonical-ref",
            "STATECOURT:us-test-court:case:1:document:1",
            "--retrieved-at",
            "2026-07-28T12:00:00Z",
            "--rights-json",
            '{"source_label":"public filing"}',
            "--db",
            str(db_path),
            "--store",
            str(store_path),
            "--output",
            str(put_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert put.returncode == 0, put.stderr
    stored = json.loads(put_output.read_text())
    digest = stored["artifact"]["sha256"]

    list_output = tmp_path / "list.json"
    listed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "list",
            "acquisitions",
            "--source-id",
            "us-test-court",
            "--db",
            str(db_path),
            "--store",
            str(store_path),
            "--output",
            str(list_output),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert json.loads(list_output.read_text())["count"] == 1

    verified = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "verify",
            "--artifact-sha256",
            digest,
            "--db",
            str(db_path),
            "--store",
            str(store_path),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["status"] == "ok"
