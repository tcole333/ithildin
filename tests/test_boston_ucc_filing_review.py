import json

from tools.boston_ucc_filing_review import (
    Builder, attachment_state, name_assessment, original_number,
)


def builder(tmp_path):
    holder = {"holder_id": "H1", "business_name": "Example, Inc.",
              "name_variants": ["Example, Inc."], "license_numbers": ["LB-1"],
              "query_proposal": {"command": "search-org", "query": "Example"},
              "searches": {"current": {"state": "pending", "attempts": []}}}
    path = tmp_path / "queue.json"
    path.write_text(json.dumps({"as_of": "2026-09-03", "holders": [holder]}))
    return Builder(path)


def row(number="202600000001", original="202600000001", kind="UCC-1"):
    return {"name": "EXAMPLE INC", "name_type": "DEBTOR", "city": "BOSTON", "state": "MA",
            "filing_type": kind, "filing_number": number, "original_filing_number": original,
            "filing_date": "01/01/2026"}


def test_originals_not_occurrences_and_duplicate_capture_provenance(tmp_path):
    queue = builder(tmp_path)
    event = {"holder_id": "H1", "scope": "current", "query": "Example", "reported_count": 3,
             "retrieved_at": "2026-09-03T00:00:00Z", "state": "complete",
             "occurrences": [row(), row(), row("202600000002", kind="UCC-3 TERMINATION")]}
    queue.observation(event, {"path": "capture-a"})
    queue.observation(event, {"path": "capture-b"})
    result = queue.result()
    assert result["summary"]["original_filing_families"] == 1
    assert len(result["filings"][0]["index_occurrences"]) == 3  # repeated source rows retained
    assert len(result["index_observations"][0]["provenance"]) == 2
    assert result["filings"][0]["history_state"] == "not_started"
    assert "UCC-3 TERMINATION" in result["filings"][0]["observed_actions"]
    assert "loan_count" not in result["summary"]


def test_missing_original_on_amendment_is_unresolved(tmp_path):
    assert original_number(row("202600000002", "", "UCC-3 CONTINUATION")) is None
    assert original_number(row(original="")) == "202600000001"
    queue = builder(tmp_path)
    queue.observation({"holder_id": "H1", "scope": "current", "occurrences": [
        row("202600000002", "", "UCC-3 CONTINUATION")
    ]}, {"path": "capture"})
    result = queue.result()
    assert not result["filings"]
    assert len(result["unresolved_index_rows"]) == 1


def test_prior_index_summary_without_rows_does_not_become_empty_search(tmp_path):
    queue = builder(tmp_path)
    queue.observation({"holder_id": "H1", "scope": "current", "state": "complete",
                       "reported_count": 12, "returned_count": 12}, {"path": "prior-summary"})
    observed = queue.result()["index_observations"][0]
    assert observed["reported_count"] == observed["returned_count"] == 12
    assert observed["captured_occurrence_rows"] == 0
    assert observed["occurrence_rows_supplied"] is False


def test_corporate_suffix_difference_is_not_exact_match():
    holder = {"business_name": "Example, Inc."}
    assert name_assessment("EXAMPLE INC", holder)["category"] == "exact_normalized_legal_name"
    assert name_assessment("EXAMPLE LLC", holder)["category"] == "legal_ending_variant_requires_evidence"
    assert not name_assessment("EXAMPLE INC", holder)["identity_verified"]


def test_pdf_urls_quotes_and_false_flags_are_not_completed_review():
    assert attachment_state({"pdf_url": "x", "collateral_quote": "All assets"}) == "listed_review_unknown"
    assert attachment_state({"pdf_url": "x", "pdf_visually_verified": False}) == "not_visually_inspected_opening_unknown"
    assert attachment_state({"pdf_review": "Not separately opened; collateral text present in history."}) == "not_opened"
    assert attachment_state({"collateral_note": "No collateral text; six-page original PDF not read."}) == "unread_opening_unknown"
    assert attachment_state({"pdf_review": "Exhibit A pages 2–3 visually reviewed."}) == "partial_original_pdf_as_reported"
    assert attachment_state({"pdf_review": "Both pages visually read using CUA PDF viewer"}) == "complete_original_pdf_as_reported"


def test_reviewed_original_does_not_clear_amendment_pdf_or_successor_identity(tmp_path):
    queue = builder(tmp_path)
    samples = {"results": [{"sample_id": "S1", "license_number": "LB-1",
        "original_filing_numbers": [], "candidate_original_filing_numbers": ["202600000001"],
        "successor_ucc_record_found": True, "corporate_chain_evidence": "source.json",
        "filings_reviewed": [{"filing_number": "202600000001", "pdf_url": "original.pdf",
            "pdf_review": "Both pages visually read using CUA PDF viewer",
            "debtor_as_recorded": "Example LLC", "debtor_business_address": "1 Main Street",
            "history_events": [{"filing_number": "202600000001", "action": "InitialFiling"},
                               {"filing_number": "202600000002", "action": "Continuation"}]}]}]}
    path = tmp_path / "samples.json"
    path.write_text(json.dumps(samples))
    queue.samples(path)
    result = queue.result()
    filing = result["filings"][0]
    assert filing["candidates"][0]["relationship"] == "documented_successor_as_reported"
    assert filing["history_state"] == "reviewed_prior_sample"
    assert [t["state"] for t in filing["document_review_tasks"]] == [
        "complete_original_pdf_as_reported", "locate_and_review_document"]
    assert "resolve_holder_identity" in filing["pending_actions"]
    assert "attachment_inventory_and_remaining_pages_review" in filing["pending_actions"]


def test_invalid_raw_capture_is_explicit_not_empty_search(tmp_path):
    queue = builder(tmp_path)
    directory = tmp_path / "observations"
    directory.mkdir()
    (directory / "bad.json").write_text(json.dumps({"results": [{"holder_id": "H1"}]}))
    queue.raw_observations(directory)
    result = queue.result()
    assert result["summary"]["unparsed_sources_or_records"] == 1
    assert not result["index_observations"]


def test_explicit_false_positive_is_retained_with_evidence(tmp_path):
    queue = builder(tmp_path)
    queue.observation({"holder_id": "H1", "scope": "current", "occurrences": [row()]}, {"path": "source"})
    path = tmp_path / "decisions.json"
    path.write_text(json.dumps([{"original_filing_number": "202600000001", "holder_id": "H1",
                                "decision": "rejected_false_positive", "note": "Different entity",
                                "evidence": ["registry.json"]}]))
    queue.decisions(path)
    result = queue.result()
    assert len(result["filings"]) == 1
    assert len(result["filings"][0]["index_occurrences"]) == 1
    assert result["filings"][0]["pending_actions"] == []
    assert result["filings"][0]["priority_score"] == 0


def test_saved_query_tool_history_is_available_but_not_review_certified(tmp_path):
    queue = builder(tmp_path)
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"query": {"command": "filing", "query": "202600000001"},
        "filings": [{"filing_type": "UCC-1 Standard", "action": "InitialFiling",
                     "filing_number": "202600000001", "debtors": [
                         {"name": "EXAMPLE INC", "address_lines": ["1 Main Street", "Boston MA"]}],
                     "documents": [{"viewer_url": "original.pdf", "page_count": 1}]}]}))
    queue.tool_history(path)
    result = queue.result()
    filing = result["filings"][0]
    assert filing["history_capture_state"] == "available"
    assert filing["history_state"] == "not_started"
    assert filing["document_review_tasks"][0]["observed_urls"] == ["original.pdf"]
    assert filing["candidates"][0]["debtor_history_addresses"] == [["1 Main Street", "Boston MA"]]
