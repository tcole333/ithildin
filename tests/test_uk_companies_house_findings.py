"""Insolvency findings distinguish generated prose from primary source strings."""

import argparse
import json
import sqlite3

import pytest

from tools import findings_tracker, ingest_uk_companies_house as ingestion, lead_tracker


def capture_findings(monkeypatch, cases, company):
    requests = []
    findings = []

    def request(path):
        requests.append(path)
        if path == "/company/01234567/insolvency":
            return {"cases": cases}
        assert path == "/company/01234567"
        return company

    def add_finding(**kwargs):
        findings.append(kwargs)
        return len(findings)

    monkeypatch.setattr(ingestion, "_request", request)
    monkeypatch.setattr(findings_tracker, "add_finding", add_finding)
    return requests, findings


def test_insolvency_summary_is_paraphrase_with_exact_values_and_labeled_record(monkeypatch):
    cases = [
        {
            "number": 1,
            "type": "creditors-voluntary-liquidation",
            "dates": [{"type": "wound-up-on", "date": "2025-01-03"}],
            "practitioners": [{"name": "Synthetic Practitioner", "address": {"locality": "London"}}],
        },
        {"number": 2, "type": "administration", "notes": ["Synthetic second case"]},
    ]
    company = {"company_name": "SYNTHETIC EXAMPLE LIMITED"}
    requests, findings = capture_findings(monkeypatch, cases, company)

    ingestion.cmd_ingest_insolvency(argparse.Namespace(number="01234567"))

    api = ingestion.BASE_URL
    assert requests == ["/company/01234567/insolvency", "/company/01234567"]
    assert len(findings) == 2
    for index, (finding, case) in enumerate(zip(findings, cases)):
        assert finding["claim_type"] == "paraphrase"
        assert finding["confidence"] == "high"
        assert finding["source_datasets"] == ["companies_house"]
        assert finding["evidence_ids"] == [f"{api}/company/01234567/insolvency", f"{api}/company/01234567"]
        quotes = finding["source_quotes"]
        case_quote = quotes[f"{api}/company/01234567/insolvency"]
        assert case_quote["quote"] == case["type"]
        assert case_quote["page"] == f"cases[{index}].type"
        assert "paraphrases the case fields" in case_quote["assessment"]
        assert quotes[f"{api}/company/01234567"]["quote"] == company["company_name"]
        preserved = finding["detail"].split("not a verbatim response excerpt):\n", 1)[1]
        assert json.loads(preserved) == case
    assert findings[0]["date_of_event"] == "2025-01-03"


def test_no_company_response_does_not_invent_a_company_name_quote(monkeypatch):
    _, findings = capture_findings(monkeypatch, [{"number": 1, "type": "administration"}], None)
    ingestion.cmd_ingest_insolvency(argparse.Namespace(number="01234567"))
    assert findings[0]["target_name"] == "01234567"
    assert findings[0]["evidence_ids"] == [f"{ingestion.BASE_URL}/company/01234567/insolvency"]
    assert len(findings[0]["source_quotes"]) == 1


@pytest.mark.parametrize("case_type", [None, "  ", 0])
def test_missing_case_type_does_not_fabricate_a_quote(monkeypatch, case_type):
    _, findings = capture_findings(monkeypatch, [{"number": 1, "type": case_type}], None)
    with pytest.raises(ValueError, match="has no source type to quote"):
        ingestion.cmd_ingest_insolvency(argparse.Namespace(number="01234567"))
    assert not findings


def test_insolvency_producer_persists_truthful_provenance_through_canonical_writer(monkeypatch, tmp_path):
    case = {"number": 1, "type": "administration"}
    company = {"company_name": "SYNTHETIC EXAMPLE LIMITED"}
    capture_findings(monkeypatch, [case], company)
    db_path = tmp_path / "findings.db"
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ITHILDIN_PROFILE", "producer-fixture")
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)

    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        lead_tracker._ensure_schema(db)
        monkeypatch.setattr(
            findings_tracker, "add_finding",
            lambda **kwargs: findings_tracker.add_finding_to_db(db, **kwargs),
        )
        ingestion.cmd_ingest_insolvency(argparse.Namespace(number="01234567"))
        finding = db.execute("SELECT * FROM findings").fetchone()
        assert finding["claim_type"] == "paraphrase"
        assert finding["confidence"] == "high"
        assert finding["verification_status"] == "unverified"
        assert finding["profile_id"] == "producer-fixture"
        assert json.loads(finding["source_datasets"]) == ["companies_house"]
        evidence = {tuple(row) for row in db.execute(
            "SELECT evidence_ref,source_quote,source_page FROM finding_evidence"
        )}
        api = ingestion.BASE_URL
        assert evidence == {
            (f"{api}/company/01234567/insolvency", case["type"], "cases[0].type"),
            (f"{api}/company/01234567", company["company_name"], "company_name"),
        }
