import json
import sys

import pytest

from tools import findings_tracker


@pytest.fixture
def findings_db(tmp_path, monkeypatch):
    from tools import lead_tracker

    db_path = tmp_path / "findings.db"
    monkeypatch.setattr(lead_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(lead_tracker, "_schema_initialized", False)
    monkeypatch.setattr(findings_tracker, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", False)
    db = lead_tracker.get_db()
    yield db
    db.close()


@pytest.mark.parametrize("blank_quote", ["", "   \t"])
def test_add_rejects_explicit_blank_quote_metadata_atomically(
    findings_db, monkeypatch, capsys, blank_quote
):
    ref = "COURTLISTENER:docket/123"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py",
            "add",
            "--target",
            "Blank Quote Target",
            "--summary",
            "Blank quote must not be stored",
            "--evidence",
            ref,
            "--source-quote",
            f"{ref}:{blank_quote}",
            "--sources",
            "gao",
            "--claim-type",
            "synthesis",
            "--profile",
            "test",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        findings_tracker.main()

    assert exc.value.code == 2
    assert "requires a non-empty source_quote" in capsys.readouterr().err
    assert findings_db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    assert (
        findings_db.execute("SELECT COUNT(*) FROM finding_evidence").fetchone()[0]
        == 0
    )


def test_add_rejects_blank_unmapped_quote_argument_atomically(
    findings_db, monkeypatch, capsys
):
    ref = "COURTLISTENER:docket/123"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "findings_tracker.py",
            "add",
            "--target",
            "Blank Quote Target",
            "--summary",
            "Unmapped blank quote must not be ignored",
            "--evidence",
            ref,
            "--source-quote",
            "",
            "--sources",
            "gao",
            "--claim-type",
            "synthesis",
            "--profile",
            "test",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        findings_tracker.main()

    assert exc.value.code == 2
    assert "Expected '<evidence_ref>:<value>'" in capsys.readouterr().err
    assert findings_db.execute("SELECT COUNT(*) FROM findings").fetchone()[0] == 0
    assert (
        findings_db.execute("SELECT COUNT(*) FROM finding_evidence").fetchone()[0]
        == 0
    )


def test_evidence_add_rejects_explicit_blank_quote_atomically(findings_db):
    finding_id = findings_tracker.add_finding(
        "Blank Quote Target",
        "The audit identifies the subject.",
        source_datasets=["gao"],
        evidence_ids=["https://www.gao.gov/fixture-report"],
        source_quotes={"https://www.gao.gov/fixture-report": {"quote": "The audit identifies the subject."}},
        profile_id="test",
    )

    with pytest.raises(ValueError, match="requires a non-empty source_quote"):
        findings_tracker.add_finding_evidence(
            finding_id,
            "COURTLISTENER:docket/123",
            source_quote=" \t ",
            reason="Attempt to attach blank quote",
        )

    assert (
        findings_db.execute(
            "SELECT COUNT(*) FROM finding_evidence WHERE finding_id=? AND evidence_ref=?",
            (finding_id, "COURTLISTENER:docket/123"),
        ).fetchone()[0]
        == 0
    )
    assert (
        findings_db.execute(
            "SELECT COUNT(*) FROM corrections WHERE record_id=?",
            (finding_id,),
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    ("source_tokens", "canonical_tokens"),
    [
        (
            ["gao", "dhs_oig", "oversight_gov", "ice_foia"],
            ["gao", "dhs_oig", "oversight_gov", "ice_foia"],
        ),
        (
            ["louisiana_legislative_auditor"],
            ["louisiana_legislative_auditor"],
        ),
        (["senate_lda", "lda"], ["lda"]),
        (["gao", "dhs_pia"], ["gao", "dhs_pia"]),
        (["oge_form_278e", "propublica_disclosures"], ["oge", "propublica_disclosures"]),
        (["dhs"], ["dhs"]),
        (
            [
                "ice.gov",
                "justice.gov",
                "ecfr.gov",
                "oge.gov",
                "gao.gov",
                "uscode.house.gov",
            ],
            ["dhs", "justice_gov", "ecfr", "oge", "gao", "us_code"],
        ),
        (
            ["supremecourt.gov", "scotus_filing", "supreme_court"],
            ["supreme_court"],
        ),
        (
            ["ice_foia", "montgomery_county"],
            ["ice_foia", "montgomery_county_tx"],
        ),
        (["sec"], ["sec"]),
        (
            ["oversight_gov", "dhs_oig", "ice_foia", "ice_detention_statistics"],
            ["oversight_gov", "dhs_oig", "ice_foia", "ice_detention_statistics"],
        ),
        (
            ["wa_registry", "irs_teos", "990", "investigations_db"],
            ["wa_registry", "irs_teos", "990", "investigations_db"],
        ),
        (["indiana_mycase"], ["indiana_mycase"]),
        (["ssa_oig", "congress"], ["ssa_oig", "congress_gov"]),
        (["courtlistener", "justia", "cadc"], ["courtlistener", "justia", "cadc"]),
        (
            [
                "england_wales_high_court",
                "icc_arbitration",
                "dominica_cbiu",
            ],
            ["ewhc", "icc_arbitration", "dominica_cbiu"],
        ),
        (["irs_990_xml", "irs_index", "990"], ["990"]),
        (
            [
                "fdacs",
                "mn_court_appeals",
                "fjc",
                "nlrb",
                "usms",
                "massachusetts_governor",
                "val_verde_county",
                "internet_archive",
            ],
            [
                "fdacs",
                "mn_court_appeals",
                "fjc",
                "nlrb",
                "usms",
                "massachusetts_governor",
                "val_verde_county",
                "internet_archive",
            ],
        ),
    ],
)
def test_government_provenance_tokens_validate_canonically(
    source_tokens, canonical_tokens
):
    assert findings_tracker._validate_source_datasets(source_tokens) == canonical_tokens


@pytest.mark.parametrize(
    ("source_tokens", "canonical_tokens"),
    [
        (
            ["sec_iapd", "asic_financial_advisers"],
            ["sec_iapd", "asic_financial_advisers"],
        ),
        (
            ["judiciary.uk", "5rb.com", "exor.com"],
            ["uk_judiciary", "official_website", "exor"],
        ),
        (
            ["california-superior-court", "justia"],
            ["ca_superior_court", "justia"],
        ),
        (
            ["sec", "paul_weiss", "paulweiss", "harvard_clp"],
            ["sec", "paul_weiss", "official_website"],
        ),
        (["irs990", "doj_epstein"], ["990", "doj"]),
        (["web_official"], ["official_website"]),
        (
            [
                "courtlistener_recap",
                "sam",
                "sam_public_extract",
                "sam_local",
                "florida_sunbiz",
                "colorado_sos",
            ],
            [
                "courtlistener",
                "sam_gov",
                "sam_bulk",
                "fl_sunbiz",
                "co_sos",
            ],
        ),
    ],
)
def test_authoritative_source_tokens_normalize_without_retrieval_labels(
    source_tokens, canonical_tokens
):
    assert findings_tracker._validate_source_datasets(source_tokens) == canonical_tokens


@pytest.mark.parametrize("token", ["capella", "ipi", "web", "direct_url", "browser"])
def test_unknown_or_retrieval_source_tokens_get_actionable_guidance(token):
    with pytest.raises(ValueError) as exc:
        findings_tracker._validate_source_datasets([token])

    message = str(exc.value)
    assert "official_website" in message
    assert "preserve the exact URL in --evidence" in message
    assert "findings_tracker.py sources" in message


def test_artifact_specific_fec_source_token_recommends_canonical_source():
    with pytest.raises(ValueError) as exc:
        findings_tracker._validate_source_datasets(["fec_mur_7180"])

    message = str(exc.value)
    assert "Use 'fec' for FEC matters" in message
    assert "preserve the MUR number" in message
    assert "document URL in --evidence" in message


def test_add_help_points_to_source_vocabulary(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        ["findings_tracker.py", "add", "--help"],
    )

    with pytest.raises(SystemExit) as exc:
        findings_tracker.main()

    assert exc.value.code == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "findings_tracker.py sources" in output
    assert "official_website" in output


def test_sources_command_exposes_canonical_tokens_aliases_and_guidance(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        sys,
        "argv",
        ["findings_tracker.py", "sources", "--json"],
    )

    findings_tracker.main()

    payload = json.loads(capsys.readouterr().out)
    assert "official_website" in payload["canonical"]
    assert payload["aliases"]["california-superior-court"] == "ca_superior_court"
    assert payload["aliases"]["irs990"] == "990"
    assert "retrieval method" in payload["guidance"]
