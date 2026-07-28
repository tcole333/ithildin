import json

from tools.public_records_artifacts import PublicRecordsArtifactStore
from tools.public_records_extract import (
    EXTRACTION_SCHEMA_VERSION,
    decide_review,
    ingest_extraction,
    list_review_queue,
    review_history,
    validate_extraction,
)


def _seed_artifacts(tmp_path):
    artifact_db = tmp_path / "artifacts.db"
    artifact_store = tmp_path / "objects"
    document = tmp_path / "deed.pdf"
    document.write_bytes(b"%PDF-1.4 fixture")
    text = tmp_path / "deed.txt"
    text.write_text(
        "Document 2024-00123 was recorded on 2024-02-08. "
        "Consideration was $125,000.00.",
        encoding="utf-8",
    )
    with PublicRecordsArtifactStore(artifact_db, artifact_store) as store:
        put = store.put_file(
            document,
            source_id="us-test-recorder",
            canonical_ref="PROPERTY:us-test-recorder/001/instrument/2024-00123",
            media_type="application/pdf",
        )
        parent_sha = put["artifact"]["sha256"]
        acquisition_id = put["acquisition"]["acquisition_id"]
        rep = store.add_representation(
            parent_sha,
            text,
            representation_type="ocr_text",
            media_type="text/plain",
            acquisition_id=acquisition_id,
            ocr_engine="fixture-ocr",
            ocr_version="1",
            schema_id="plain-text",
            schema_version="1",
        )
        representation_id = rep["representation"]["representation_id"]
    return artifact_db, artifact_store, parent_sha, acquisition_id, representation_id


def _payload(parent_sha, acquisition_id, representation_id):
    return {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "artifact_sha256": parent_sha,
        "acquisition_id": acquisition_id,
        "representation_id": representation_id,
        "producer": {
            "name": "fixture-extractor",
            "version": "1",
            "prompt_id": "deed-fields",
            "prompt_version": "1",
            "schema_id": "recorded-instrument",
            "schema_version": "1",
        },
        "document": {"classification": "deed"},
        "fields": [
            {
                "name": "document_number",
                "value": "2024-00123",
                "page_number": 1,
                "exact_quote": "Document 2024-00123",
                "confidence": 0.99,
            },
            {
                "name": "recording_date",
                "value": "2024-02-08",
                "page_number": 1,
                "exact_quote": "recorded on 2024-02-08",
                "confidence": 0.98,
            },
            {
                "name": "consideration_amount",
                "value": {"amount_minor": 12_500_000, "currency": "USD"},
                "page_number": 1,
                "exact_quote": "Consideration was $125,000.00",
                "confidence": 0.97,
            },
        ],
    }


def test_validate_checks_quotes_dates_amounts_and_versions(tmp_path):
    artifact_db, store_root, parent, acquisition, representation = _seed_artifacts(
        tmp_path
    )
    result = validate_extraction(
        _payload(parent, acquisition, representation),
        artifact_db=artifact_db,
        artifact_store=store_root,
    )
    assert result["status"] == "ok"
    assert result["validation"]["summary"]["validation_states"] == {"valid": 3}
    assert result["validation"]["summary"]["representation_text_checked"] is True


def test_invalid_values_are_preserved_and_queued_for_review(tmp_path):
    artifact_db, store_root, parent, acquisition, representation = _seed_artifacts(
        tmp_path
    )
    payload = _payload(parent, acquisition, representation)
    payload["fields"].append(
        {
            "name": "judgment_date",
            "value": "2024-99-99",
            "page_number": 1,
            "exact_quote": "not present in OCR",
            "confidence": 0.7,
        }
    )
    review_db = tmp_path / "review.db"
    result = ingest_extraction(
        payload,
        artifact_db=artifact_db,
        artifact_store=store_root,
        review_db=review_db,
    )
    assert result["run"]["field_count"] == 4
    assert result["run"]["evidence_count"] == 4
    assert len(result["review_items"]) == 1
    assert set(result["review_items"][0]["reason_codes"]) == {
        "invalid_iso_date",
        "quote_not_found_in_representation",
    }
    queued = list_review_queue(review_db=review_db)
    assert queued["count"] == 1


def test_ingest_is_idempotent_and_review_decisions_are_append_only(tmp_path):
    artifact_db, store_root, parent, acquisition, representation = _seed_artifacts(
        tmp_path
    )
    payload = _payload(parent, acquisition, representation)
    payload["fields"][0]["exact_quote"] = "OCR mismatch"
    review_db = tmp_path / "review.db"
    first = ingest_extraction(
        payload,
        artifact_db=artifact_db,
        artifact_store=store_root,
        review_db=review_db,
    )
    second = ingest_extraction(
        payload,
        artifact_db=artifact_db,
        artifact_store=store_root,
        review_db=review_db,
    )
    assert second["deduplicated_run"] is True
    assert second["run"]["run_ref"] == first["run"]["run_ref"]

    review_ref = first["review_items"][0]["review_ref"]
    accepted = decide_review(
        review_ref,
        decision="accepted",
        decided_by="reviewer",
        review_db=review_db,
    )
    reopened = decide_review(
        review_ref,
        decision="pending",
        decided_by="reviewer",
        notes="inspect a better scan",
        review_db=review_db,
    )
    history = review_history(review_ref, review_db=review_db)
    assert accepted["event"]["supersedes_event_id"] is None
    assert reopened["event"]["supersedes_event_id"] == accepted["event"][
        "review_event_id"
    ]
    assert [event["decision"] for event in history["events"]] == [
        "accepted",
        "pending",
    ]


def test_cli_writes_structured_validation(tmp_path, capsys):
    artifact_db, store_root, parent, acquisition, representation = _seed_artifacts(
        tmp_path
    )
    source = tmp_path / "extraction.json"
    source.write_text(
        json.dumps(_payload(parent, acquisition, representation)),
        encoding="utf-8",
    )
    output = tmp_path / "validated.json"

    from tools.public_records_extract import main

    assert (
        main(
            [
                "validate",
                str(source),
                "--artifact-db",
                str(artifact_db),
                "--artifact-store",
                str(store_root),
                "--review-db",
                str(tmp_path / "review.db"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text())["status"] == "ok"
    assert "saved to" in capsys.readouterr().out
