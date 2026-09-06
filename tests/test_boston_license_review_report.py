"""Report affiliation counts preserve explicit analyst decisions and caveats."""

import hashlib
import json
import runpy
from pathlib import Path

import pytest


REPORT_BUILDER = (
    Path(__file__).resolve().parents[1]
    / "reports/boston-liquor-license-collateral-2026-09-03/full-review/build_review_data.py"
)
report_helpers = runpy.run_path(str(REPORT_BUILDER))
reviewed_affiliation = report_helpers["reviewed_affiliation"]


def test_explicit_affiliation_survives_unverified_dba_caveat():
    match = {
        "count_as_group_affiliated": True,
        "match_status": "verified_named_holder_operator_and_complex_current_dba_unverified",
        "match_note": "Current DBA remains unverified; holder and operator were separately reviewed.",
    }
    original = match.copy()
    assert reviewed_affiliation(match) is True
    assert match == original


@pytest.mark.parametrize("status", ["candidate", "verified_name_and_address"])
def test_explicit_exclusion_is_preserved(status):
    assert reviewed_affiliation({"count_as_group_affiliated": False, "match_status": status}) is False


@pytest.mark.parametrize("decision", ["false", "true", 0, 1, None])
def test_affiliation_decision_requires_a_real_boolean(decision):
    with pytest.raises(ValueError, match="must be a boolean"):
        reviewed_affiliation({"count_as_group_affiliated": decision})


@pytest.mark.parametrize(
    ("status", "expected"),
    [("venue_name_and_address_match", True), ("candidate", False), ("unresolved", False)],
)
def test_legacy_status_fallback_remains_compatible(status, expected):
    assert reviewed_affiliation({"match_status": status}) is expected


def test_source_manifest_counts_duplicate_content_once_and_retains_urls(tmp_path):
    document = tmp_path / "saved.pdf"
    document.write_bytes(b"Saved source bytes")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    records = [{"source_id": source_id, "url": url, "pdf_path": "saved.pdf", "sha256": digest, "page_count": 4}
               for source_id, url in (("source-a", "https://example.gov/a.pdf"), ("source-b", "https://example.gov/b.pdf"))]
    index = tmp_path / "source-index.json"
    index.write_text(json.dumps(records))
    result = report_helpers["source_manifest"](index)
    assert result["observed_source_entries"] == 2
    assert result["documents"] == 1
    assert result["pdf_pages"] == 4
    assert {item["url"] for item in result["source_records"]} == {record["url"] for record in records}
    document.write_bytes(b"Changed source bytes")
    with pytest.raises(ValueError, match="hash changed"):
        report_helpers["source_manifest"](index)


def test_event_window_provenance_does_not_mutate_original_event():
    event = {"event_id": "event-a", "source_id": "source-a", "source_sha256": "document-hash"}
    window = {"window_id": "old", "window_start": "2020-01-01", "window_end": "2023-12-31",
              "window_label": "2020–2023", "source_coverage_file": "/coverage.json", "source_coverage_sha256": "coverage-hash"}
    manifest = {"by_id": {"source-a": {"sha256": "document-hash", "resolved_source_file": "/source.pdf"}},
                "source_index_file": "/source-index.json", "source_index_sha256": "index-hash"}
    result = report_helpers["attach_window_provenance"]([event], window, manifest)
    assert "source_window_id" not in event
    assert result[0]["source_window_id"] == "old"
    assert result[0]["source_document_sha256"] == "document-hash"
    with pytest.raises(ValueError, match="hashes differ"):
        report_helpers["attach_window_provenance"]([{**event, "source_sha256": "different"}], window, manifest)


def test_unfinished_prior_window_is_not_loaded(monkeypatch):
    loader = report_helpers["load_history_windows"]
    calls = []

    def fake_window(folder, window_id, inventory, **kwargs):
        calls.append(window_id)
        return {bucket: [] for bucket in ("board_events", "ownership_events", "ownership_notices", "notices", "proposals")}

    monkeypatch.setitem(loader.__globals__, "load_history_window", fake_window)
    monkeypatch.setitem(loader.__globals__, "read_json", lambda *args: {"integration_status": "in_progress"})
    assert len(loader([])) == 1
    assert calls == ["2024-2026"]


def test_reprefixed_duplicate_source_item_is_rejected(monkeypatch):
    loader = report_helpers["load_history_windows"]

    def fake_window(folder, window_id, inventory, **kwargs):
        result = {bucket: [] for bucket in ("board_events", "ownership_events", "ownership_notices", "notices", "proposals")}
        result["board_events"] = [{
            "event_id": window_id + "-new-prefix",
            "source_window_id": window_id,
            "source_document_sha256": "same-physical-source",
            "page_start": 4,
            "item_number": "8",
            "action_subtype": "transfer_application_disposition",
        }]
        return result

    monkeypatch.setitem(loader.__globals__, "load_history_window", fake_window)
    monkeypatch.setitem(loader.__globals__, "read_json", lambda *args: {"integration_status": "qa_complete"})
    with pytest.raises(ValueError, match="Repeated physical source item"):
        loader([])


@pytest.mark.parametrize("failure", ["missing_artifact", "changed_artifact"])
def test_finalized_window_rejects_incomplete_or_changed_readiness_artifacts(tmp_path, failure):
    names = ("coverage.json", "source-index.json", "events.json", "ownership-interest-events.json",
             "ownership-interest-notices.json", "notices.json", "proposed-events.json")
    for name in names:
        (tmp_path / name).write_text(json.dumps({"integration_status": "qa_complete"} if name == "coverage.json" else []))
    hashes = {name: hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() for name in names}
    if failure == "missing_artifact":
        del hashes["notices.json"]
    else:
        (tmp_path / "events.json").write_text('[{"changed": true}]')
    (tmp_path / "readiness.json").write_text(json.dumps({"integration_status": "qa_complete", "artifacts": hashes}))
    with pytest.raises(ValueError, match="omits a required|artifact hash changed"):
        report_helpers["load_history_window"](tmp_path, "old", [], require_qa=True)
