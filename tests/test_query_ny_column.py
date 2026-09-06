from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import query_ny_column as nyc


FIXTURES = Path(__file__).parent / "fixtures" / "ny_column"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_build_filters_exposes_exact_partition_inputs():
    filters, partition = nyc._build_filters(
        start_date="2026-10-01",
        end_date="2026-10-01",
        counties=["Oswego County"],
        notice_types=["Foreclosure Sale"],
        newspapers=["Palladium Times"],
        filers=["GMaDruzLL1Zoj8G3AhIl"],
    )

    assert filters == [
        {
            "publishedtimestamp": {
                "from": 1790812800000,
                "to": 1790899199999,
            }
        },
        {"state": ["New York"]},
        {"noticetype": ["Foreclosure Sale"]},
        {"newspapername": ["Palladium Times"]},
        {"county": ["Oswego", "Oswego County"]},
        {"filer": ["GMaDruzLL1Zoj8G3AhIl"]},
    ]
    assert partition == {
        "start_date": "2026-10-01",
        "end_date": "2026-10-01",
        "counties": ["Oswego County"],
        "notice_types": ["Foreclosure Sale"],
        "newspapers": ["Palladium Times"],
        "filers": ["GMaDruzLL1Zoj8G3AhIl"],
    }


def test_build_filters_rejects_inverted_dates():
    with pytest.raises(nyc.NyColumnError, match="cannot be after"):
        nyc._build_filters(
            start_date="2026-10-02",
            end_date="2026-10-01",
        )


def test_parse_response_retains_notice_and_publication_metadata():
    parsed = nyc.parse_search_response(fixture("search-page-1.json"))
    notice, pdf_notice = parsed["results"]

    assert notice["source"] == "us-ny-public-notices-column"
    assert notice["notice_id"] == nyc.SENTINEL_NOTICE_ID
    assert notice["notice_text"].startswith("CITY OF OSWEGO\n\nLEGAL NOTICE")
    assert nyc.SENTINEL_TEXT_MARKER in notice["notice_text"]
    assert notice["published_date"] == "2026-10-01"
    assert notice["notice_type"] == "Foreclosure Sale"
    assert notice["publication_name"] == "Palladium Times"
    assert notice["county"] == "Oswego"
    assert notice["filer_id"] == "GMaDruzLL1Zoj8G3AhIl"
    assert notice["source_url"] == (
        "https://newyork.column.us/"
        "?activeNotice=5r3wmbl7IAfYExOneLRQ-3"
    )
    assert notice["evidence_ref"] == (
        "NY_COLUMN:5r3wmbl7IAfYExOneLRQ-3"
    )
    assert notice["publication_metadata"]["newspaper"] == "Palladium Times"
    assert notice["filer_metadata"]["source_filer_id"] == (
        "GMaDruzLL1Zoj8G3AhIl"
    )
    assert notice["discovery_provenance"] == {
        "platform": "Column",
        "portal_url": nyc.PORTAL_URL,
        "search_endpoint": nyc.SEARCH_ENDPOINT,
        "record_class": "newspaper_public_notice",
        "investigative_role": "discovery",
        "court_record_status": "not_court_filing",
    }
    assert notice["raw_metadata"]["combo"] == 0
    assert "<em>foreclosure</em>" in notice["raw_metadata"]["highlighted_text"]

    assert pdf_notice["pdf_url"].endswith("cropped-116.pdf")
    assert pdf_notice["notice_text"].startswith("Order Confirmation")
    assert pdf_notice["notice_type"] is None
    assert pdf_notice["publication_name"] == "Post-Standard, The"
    assert pdf_notice["filer_id"] == "QDf166ayvYVHSTcx8kUL"


def test_search_retrieves_every_source_reported_page_by_default(monkeypatch):
    calls = []

    def fake_post(_session, body):
        calls.append(body)
        return fixture(f"search-page-{body['current']}.json")

    monkeypatch.setattr(nyc, "_post_search", fake_post)
    filters, partition = nyc._build_filters(
        counties=["Oswego"],
        notice_types=["Foreclosure Sale"],
    )
    payload = nyc.search_notices(
        object(),
        query="notice",
        all_filters=filters,
        partition=partition,
        page_size=2,
    )

    assert [call["current"] for call in calls] == [1, 2]
    assert [row["notice_id"] for row in payload["results"]] == [
        "5r3wmbl7IAfYExOneLRQ-3",
        "EPsOtDJ25veTV1LwZ1So-5",
        "public-hearing-notice-1",
    ]
    assert payload["coverage"] == {
        "source_reported_total_results": 3,
        "source_display_ceiling": 10000,
        "source_display_ceiling_reached": False,
        "source_reported_total_kind": "exact_within_partition",
        "returned_unique_results": 3,
        "raw_rows_received": 3,
        "duplicate_rows_removed": 0,
        "source_pages_exhausted": True,
        "user_limit": None,
        "truncated_by_user_limit": False,
    }
    assert payload["pagination"]["pages_fetched"] == [1, 2]
    assert payload["pagination"]["returned_all_source_reported_pages"] is True
    assert payload["results"][2]["raw_metadata"]["normalizedentities"] == {
        "organization": "Town Board"
    }


def test_user_limit_is_optional_and_reported_without_adapter_max(monkeypatch):
    calls = []

    def fake_post(_session, body):
        calls.append(body)
        return fixture("search-page-1.json")

    monkeypatch.setattr(nyc, "_post_search", fake_post)
    filters, partition = nyc._build_filters()
    payload = nyc.search_notices(
        object(),
        query="",
        all_filters=filters,
        partition=partition,
        page_size=25000,
        limit=1,
    )

    assert calls[0]["pageSize"] == 25000
    assert len(payload["results"]) == 1
    assert payload["coverage"]["user_limit"] == 1
    assert payload["coverage"]["truncated_by_user_limit"] is True
    assert payload["pagination"]["pages_fetched"] == [1]


def test_display_ceiling_is_preserved_as_source_reported_coverage(monkeypatch):
    monkeypatch.setattr(
        nyc,
        "_post_search",
        lambda _session, _body: fixture("display-ceiling.json"),
    )
    filters, partition = nyc._build_filters()
    payload = nyc.search_notices(
        object(),
        query="",
        all_filters=filters,
        partition=partition,
        page_size=1,
        limit=1,
    )

    assert payload["coverage"]["source_reported_total_results"] == 10000
    assert payload["coverage"]["source_display_ceiling"] == 10000
    assert payload["coverage"]["source_display_ceiling_reached"] is True
    assert payload["coverage"]["source_reported_total_kind"] == "display_ceiling"
    assert payload["pagination"]["source_reported_total_pages"] == 10000


def test_response_schema_errors_are_not_treated_as_empty_results():
    with pytest.raises(nyc.NyColumnError, match="missing results"):
        nyc.parse_search_response({"success": True, "page": {}})

    with pytest.raises(nyc.NyColumnError, match="reported failure"):
        nyc.parse_search_response({
            "success": False,
            "message": "query rejected",
        })


def test_live_sentinel_contract_with_offline_fixtures(monkeypatch):
    def fake_post(_session, body):
        if body["search"] == nyc.SENTINEL_QUERY:
            return fixture("search-page-1.json")
        if body["search"] == "":
            return fixture("display-ceiling.json")
        raise AssertionError(f"unexpected query: {body['search']!r}")

    monkeypatch.setattr(nyc, "_post_search", fake_post)
    payload = nyc.run_sentinel(session=object())

    assert payload["status"] == "ok"
    assert [check["name"] for check in payload["checks"]] == [
        "partitioned_notice",
        "display_ceiling",
    ]
    assert all(check["status"] == "ok" for check in payload["checks"])
    assert payload["exact_urls"] == {
        "portal": "https://newyork.column.us/",
        "search_endpoint": (
            "https://us-central1-enotice-production.cloudfunctions.net/"
            "api/search/public-notices"
        ),
        "sentinel_notice": (
            "https://newyork.column.us/"
            "?activeNotice=5r3wmbl7IAfYExOneLRQ-3"
        ),
    }


def test_cli_search_has_no_default_result_limit():
    parsed = nyc.build_parser().parse_args(["search", "foreclosure"])

    assert parsed.limit is None
    assert parsed.page_size == nyc.DEFAULT_PAGE_SIZE
