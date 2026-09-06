from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from tools import query_ny_law_reports as nylr


FIXTURES = Path(__file__).parent / "fixtures" / "ny_law_reports"
RSS_URL = nylr.COLLECTIONS["other"]["rss_url"]
CURRENT_INDEX_URL = nylr.COLLECTIONS["other"]["current_index_url"]
ARCHIVE_URL = nylr.COLLECTIONS["other"]["archive_index_url"]


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def response(url: str, body: str) -> nylr.TextResponse:
    return nylr.TextResponse(
        url=url,
        text=body,
        content_type="text/html; charset=utf-8",
        status_code=200,
    )


def args(**overrides) -> argparse.Namespace:
    values = {
        "collection": "other",
        "year": None,
        "month": None,
        "feed": False,
        "limit": None,
        "match_mode": "phrase",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_parse_rss_preserves_source_metadata_and_all_rows():
    payload = nylr.parse_rss(fixture("misc.xml"), RSS_URL, "other")

    assert payload["coverage"] == {
        "kind": "source_feed_window",
        "description": "all entries present in the source-provided RSS response",
        "item_count": 2,
    }
    assert payload["pagination"]["returned_all_source_rows"] is True
    assert [row["document_format"] for row in payload["results"]] == ["html", "pdf"]
    first = payload["results"][0]
    assert first["caption"] == nylr.SENTINEL_CAPTION
    assert first["court"] == "Civil Court of the City of New York, New York County"
    assert first["decision_date_iso"] == "2026-07-20"
    assert first["citation"] == nylr.SENTINEL_CITATION
    assert first["evidence_ref"] == "NY_LAW_REPORTS:2026_26113"
    assert "<table>" in first["raw_metadata"]["description_html"]


def test_parse_archive_index_uses_only_source_native_month_links():
    payload = nylr.parse_archive_index(
        fixture("archive-index.html"),
        ARCHIVE_URL,
        "other",
    )

    assert payload["coverage"] == {
        "kind": "source_month_index",
        "first_period": "2025-12",
        "last_period": "2026-06",
        "period_count": 3,
    }
    assert [row["period"] for row in payload["results"]] == [
        "2025-12",
        "2026-01",
        "2026-06",
    ]
    assert payload["results"][0]["source_url"] == (
        "https://www.nycourts.gov/reporter/slipidx/"
        "miscolo_2025_december.shtml"
    )


def test_parse_decision_index_returns_every_row_without_adapter_cap():
    payload = nylr.parse_decision_index(
        fixture("current-index.html"),
        CURRENT_INDEX_URL,
        "other",
        period="current",
    )

    assert payload["coverage"]["row_count"] == 2
    assert payload["pagination"]["returned_all_source_rows"] is True
    assert len(payload["results"]) == 2
    assert payload["results"][0]["raw_metadata"]["posted_group"] == (
        "Cases Posted July 28, 2026"
    )
    assert payload["results"][1]["caption"] == (
        "FORA Financial Advance LLC v Example Corp."
    )
    assert payload["results"][1]["document_format"] == "pdf"


def test_parse_opinion_preserves_case_fields_body_and_raw_metadata():
    payload = nylr.parse_opinion(fixture("opinion.html"), nylr.SENTINEL_OPINION_URL)

    assert payload["caption"] == nylr.SENTINEL_CAPTION
    assert payload["court"] == "Civil Court of the City of New York, New York County"
    assert payload["decision_date"] == "July 20, 2026"
    assert payload["decision_date_iso"] == "2026-07-20"
    assert payload["citation"] == nylr.SENTINEL_CITATION
    assert payload["judge"] == "Karen May Bacdayan, J."
    assert payload["index_number"] == "LT-305123-25/NY"
    assert payload["source_url"] == nylr.SENTINEL_OPINION_URL
    assert nylr.SENTINEL_BODY_MARKER in payload["body_text"]
    assert "Leonard Ledereich" in payload["body_text"]
    assert "Footnote 1" in payload["body_text"]
    assert nylr.SENTINEL_CAPTION not in payload["body_text"]
    assert payload["raw_metadata"]["digest"].startswith("Landlord and Tenant")
    assert payload["raw_metadata"]["parties"]
    assert payload["raw_metadata"]["counsel"]


def test_decode_body_prefers_utf8_bom_over_text_html_default():
    raw = b"\xef\xbb\xbf<p>Judiciary Law \xc2\xa7 431</p>"

    assert nylr._decode_body(raw, "text/html") == "<p>Judiciary Law § 431</p>"


def test_parse_opinion_identifies_access_challenge():
    with pytest.raises(nylr.NyLawReportsAccessChallenge):
        nylr.parse_opinion(
            "<html><body>Performing security verification</body></html>",
            nylr.SENTINEL_OPINION_URL,
        )


def test_index_command_defaults_to_all_source_rows(monkeypatch):
    monkeypatch.setattr(nylr, "_session", object)
    monkeypatch.setattr(
        nylr,
        "_request_text",
        lambda _session, url: response(url, fixture("current-index.html")),
    )
    monkeypatch.setattr(nylr, "_log", lambda *_args: None)
    emitted = {}
    monkeypatch.setattr(
        nylr,
        "_emit",
        lambda payload, _args, _summary: emitted.update(payload=payload),
    )

    assert nylr.cmd_index(args()) == 0
    assert len(emitted["payload"]["results"]) == 2
    assert emitted["payload"]["pagination"]["returned_all_source_rows"] is True


def test_body_search_finds_nonparty_text_and_reports_pdf_gap(monkeypatch):
    def fake_request(_session, url):
        if url == CURRENT_INDEX_URL:
            return response(url, fixture("current-index.html"))
        if url == nylr.SENTINEL_OPINION_URL:
            return response(url, fixture("opinion.html"))
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr(nylr, "_session", object)
    monkeypatch.setattr(nylr, "_request_text", fake_request)
    monkeypatch.setattr(nylr, "_log", lambda *_args: None)
    emitted = {}
    monkeypatch.setattr(
        nylr,
        "_emit",
        lambda payload, _args, _summary: emitted.update(payload=payload),
    )

    assert nylr.cmd_search(args(query="Leonard Ledereich")) == 0
    payload = emitted["payload"]
    assert payload["documents_discovered"] == 2
    assert payload["html_documents_discovered"] == 1
    assert payload["pdf_documents_skipped"] == 1
    assert payload["documents_fetched"] == 1
    assert payload["truncated"] is False
    assert len(payload["results"]) == 1
    assert payload["results"][0]["matched_fields"] == ["body_text"]
    assert "Leonard Ledereich" in payload["results"][0]["match_snippet"]


def test_live_sentinel_contract_with_offline_source_fixtures(monkeypatch):
    def fake_request(_session, url):
        fixtures = {
            RSS_URL: ("misc.xml", "application/rss+xml"),
            nylr.COLLECTIONS["commercial"]["rss_url"]: (
                "misc.xml",
                "application/rss+xml",
            ),
            CURRENT_INDEX_URL: ("current-index.html", "text/html"),
            nylr.COLLECTIONS["commercial"]["current_index_url"]: (
                "current-index.html",
                "text/html",
            ),
            ARCHIVE_URL: ("archive-index.html", "text/html"),
            nylr.COLLECTIONS["commercial"]["archive_index_url"]: (
                "archive-index.html",
                "text/html",
            ),
            nylr.SENTINEL_OPINION_URL: ("opinion.html", "text/html"),
        }
        name, content_type = fixtures[url]
        result = response(url, fixture(name))
        return nylr.TextResponse(
            url=result.url,
            text=result.text,
            content_type=content_type,
            status_code=result.status_code,
        )

    monkeypatch.setattr(nylr, "_request_text", fake_request)
    payload = nylr.run_sentinel(session=object())

    assert payload["status"] == "ok"
    assert len(payload["checks"]) == 7
    assert all(check["status"] == "ok" for check in payload["checks"])
    assert payload["exact_urls"] == {
        "other_rss": RSS_URL,
        "commercial_rss": nylr.COLLECTIONS["commercial"]["rss_url"],
        "other_current_index": CURRENT_INDEX_URL,
        "commercial_current_index": (
            nylr.COLLECTIONS["commercial"]["current_index_url"]
        ),
        "other_archive_index": ARCHIVE_URL,
        "commercial_archive_index": (
            nylr.COLLECTIONS["commercial"]["archive_index_url"]
        ),
        "opinion": nylr.SENTINEL_OPINION_URL,
    }
