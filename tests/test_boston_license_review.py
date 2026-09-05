import copy
import csv

import pytest

from tools.boston_license_review import (
    BUSINESS_FIELDS,
    classify_type,
    coverage,
    holder_id,
    inventory,
    merge_events,
    normalized_holder,
    validate_queue,
)


def make_queue(tmp_path):
    path = tmp_path / "roster.csv"
    first = dict.fromkeys(BUSINESS_FIELDS, "")
    first.update(license_num="LB-1", business_name="Sample, LLC", status="Active",
                 license_type="CV7 All Alc.", expires="2025-12-31",
                 descpremadd="License pledged to Example Bank")
    duplicate = {**first, "comments": "different retained source row"}
    second = {**first, "license_num": "LB-2", "business_name": "Sample Inc.",
              "license_type": "BYOB Bring Your Own Bottle"}
    excluded = {**first, "license_num": "LB-3", "license_type": "Common Victualler"}
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=BUSINESS_FIELDS)
        writer.writeheader()
        writer.writerows([first, duplicate, second, excluded])
    return inventory(path, "2026-09-03")


def event(queue, **overrides):
    return {
        "holder_id": queue["holders"][0]["holder_id"], "scope": "current", "state": "complete",
        "query": {"query": "Sample", "role": "debtor", "city": None, "state": None, "since": None},
        "reported_count": 0, "returned_count": 0, "truncated": False,
        "source_file": "saved.json", "capture_method": "test observation", **overrides,
    }


def test_inventory_preserves_lineage_and_corporate_endings(tmp_path):
    summary, rows, queue = make_queue(tmp_path)
    assert summary["raw_rows"] == 4
    assert summary["included_rows"] == 3
    assert summary["included_legal_holder_groups"] == 2
    assert summary["included_expired_unique_licenses"] == 2
    assert len(rows) == 4
    assert validate_queue(queue)["source_rows"] == 3
    assert normalized_holder("Sample, LLC") != normalized_holder("Sample Inc.")
    assert holder_id(normalized_holder("SAMPLE LLC")) == holder_id(normalized_holder("Sample, LLC"))
    assert rows[0]["raw_row_sha256"] != rows[1]["raw_row_sha256"]
    assert rows[0]["financing_marker_fields"] == {"descpremadd": ["pledge"]}
    assert rows[0]["pledge_any_field_marker"] is True
    assert rows[0]["pledge_comment_marker"] is False


@pytest.mark.parametrize("kind,expected", [
    ("Common Victualler", "excluded_non_alcohol"),
    ("Inn. All Alc.", "alcohol_license"),
    ("BYOB Bring Your Own Bottle", "byob_separate"),
    ("SPCMWA", "category_needs_verification"),
    ("Future new category", "unknown_type_needs_verification"),
])
def test_scope_boundaries(kind, expected):
    assert classify_type(kind) == expected


@pytest.mark.parametrize("override", [
    {"truncated": True}, {"reported_count": 5, "returned_count": 2},
    {"reported_count": None}, {"source_file": ""},
    {"query": {"role": "debtor", "city": "Boston"}},
])
def test_incomplete_or_filtered_evidence_cannot_complete_queue(tmp_path, override):
    queue = make_queue(tmp_path)[2]
    with pytest.raises(ValueError):
        merge_events(queue, [event(queue, **override)])


def test_replay_idempotent_and_archive_and_document_coverage_separate(tmp_path):
    queue = make_queue(tmp_path)[2]
    attempt = event(queue, review={"reviewed_filing_numbers": ["123456789012"]})
    updated = merge_events(queue, [attempt, attempt])
    current = updated["holders"][0]["searches"]["current"]
    assert len(current["attempts"]) == 1
    assert current["state"] == "complete"
    assert updated["holders"][0]["searches"]["lapsed"]["state"] == "pending"
    assert updated["holders"][0]["document_review"]["state"] == "partial_prior_evidence"
    updated = merge_events(updated, [event(queue, state="blocked", error="access challenge")])
    assert updated["holders"][0]["searches"]["current"]["state"] == "complete"
    assert coverage(updated)["both_scopes_complete"] == 0
    assert queue["holders"][0]["searches"]["current"]["state"] == "pending"


def test_false_completion_and_wrong_holder_event_rejected(tmp_path):
    queue = make_queue(tmp_path)[2]
    broken = copy.deepcopy(queue)
    broken["holders"][0]["searches"]["current"]["state"] = "complete"
    with pytest.raises(ValueError):
        validate_queue(broken)
    with pytest.raises(ValueError):
        merge_events(queue, [event(queue, holder_id="unknown")])
