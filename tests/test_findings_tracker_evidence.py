from tools.findings_tracker import (
    _classify_evidence_ref,
    _normalize_event_date,
    _parse_source_quote_args,
)


def test_url_is_classified_before_path_separator():
    assert _classify_evidence_ref("https://example.gov/record/123") == "url"
    assert _classify_evidence_ref("data/case/record.pdf") == "file"
    assert _classify_evidence_ref("EFTA01315387") == "efta"


def test_source_quote_parser_preserves_colons_in_canonical_ref():
    evidence = ["FL-SunBiz:L10000130392"]
    parsed = _parse_source_quote_args(
        ["FL-SunBiz:L10000130392:BIER GARDEN LLC; RAMON L. COSCOLLUELA"],
        evidence,
    )
    assert parsed == {
        "FL-SunBiz:L10000130392": {
            "quote": "BIER GARDEN LLC; RAMON L. COSCOLLUELA",
        }
    }


def test_normalize_event_date_populates_iso_and_precision():
    assert _normalize_event_date("2010-12-22") == ("2010-12-22", "day")
    assert _normalize_event_date(None) == (None, None)
