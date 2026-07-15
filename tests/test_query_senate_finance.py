import json
from types import SimpleNamespace

import pytest

from tools import query_senate_finance as senate_finance


SEARCH_HTML = """
<p class="sr-results-summary"><b>421</b> results found for <b>ministries</b>.</p>
<ol id="sr-listing">
  <li>
    <a class="sr-title" href="/ranking-members-news/example-release">
      Example <highlight>Media</highlight> - <highlight>based</highlight> Release
    </a>
    <div class="sr-metadata"><span class="sr-date">01/06/2011</span></div>
    <p class="sr-summary">An <highlight>official</highlight> archive result.</p>
  </li>
</ol>
"""


ITEM_HTML = """
<html><head>
  <link rel="canonical" href="https://www.finance.senate.gov/ranking-members-news/example-release">
</head><body>
  <div id="main_column"><div id="newscontent"><div id="pressrelease">
    <span class="date">January 06 ,2011</span>
    <h1 class="main_page_title">Example Release</h1>
    <p>First paragraph.</p><p>Second <strong>paragraph</strong>.</p>
  </div></div></div>
  <aside><h1>Related Files</h1><ul><li>
    <a href="/download/example-memo"><span>acrobat</span>Example memo.pdf</a>
  </li></ul></aside>
</body></html>
"""


def test_parse_search_page_returns_primary_source_references():
    total, results = senate_finance.parse_search_page(
        SEARCH_HTML,
        "https://www.finance.senate.gov/search/?q=ministries",
    )

    assert total == 421
    assert results == [{
        "title": "Example Media-based Release",
        "date": "01/06/2011",
        "summary": "An official archive result.",
        "url": "https://www.finance.senate.gov/ranking-members-news/example-release",
        "evidence_ref": "SENATE_FINANCE:ranking-members-news/example-release",
    }]


def test_parse_item_page_returns_text_and_related_files():
    item = senate_finance.parse_item_page(
        ITEM_HTML,
        "https://www.finance.senate.gov/ranking-members-news/example-release",
    )

    assert item["title"] == "Example Release"
    assert item["date"] == "January 06, 2011"
    assert item["paragraphs"] == ["First paragraph.", "Second paragraph."]
    assert item["evidence_ref"] == "SENATE_FINANCE:ranking-members-news/example-release"
    assert item["related_files"] == [{
        "title": "Example memo.pdf",
        "url": "https://www.finance.senate.gov/download/example-memo",
        "evidence_ref": "SENATE_FINANCE:download/example-memo",
    }]


def test_item_rejects_non_committee_hosts():
    with pytest.raises(senate_finance.SenateFinanceError, match="finance.senate.gov"):
        senate_finance._official_url("https://example.com/not-a-senate-page")


def test_download_reference_removes_legacy_refresh_switch():
    assert senate_finance._reference_for_url(
        "https://www.finance.senate.gov/download/example-hearing&download=1"
    ) == "SENATE_FINANCE:download/example-hearing"


def test_search_writes_bounded_output_and_logs(monkeypatch, tmp_path):
    output = tmp_path / "search.json"
    requested = []
    logged = []

    monkeypatch.setattr(senate_finance, "_session", lambda: object())
    monkeypatch.setattr(
        senate_finance,
        "_request_html",
        lambda session, url, params=None: (
            requested.append(params)
            or senate_finance.HtmlResponse(
                url="https://www.finance.senate.gov/search/?q=ministries&page=1",
                text=SEARCH_HTML,
            )
        ),
    )
    monkeypatch.setattr(senate_finance, "_log", lambda query, count: logged.append((query, count)))
    args = SimpleNamespace(
        query="ministries",
        limit=1,
        page=1,
        output=str(output),
        json_out=False,
    )

    senate_finance.cmd_search(args)

    payload = json.loads(output.read_text())
    assert len(payload["results"]) == 1
    assert payload["pages_fetched"] == 1
    assert requested == [{"q": "ministries", "page": 1}]
    assert logged == [("ministries", 1)]


def test_request_rejects_declared_oversized_html(monkeypatch):
    class OversizedResponse:
        url = "https://www.finance.senate.gov/search/"
        status_code = 200
        encoding = "utf-8"
        headers = {
            "Content-Type": "text/html; charset=UTF-8",
            "Content-Length": str(senate_finance.MAX_HTML_BYTES + 1),
        }

        def close(self):
            pass

    session = SimpleNamespace(get=lambda *args, **kwargs: OversizedResponse())
    monkeypatch.setattr(senate_finance, "REQUEST_DELAY", 0)

    with pytest.raises(senate_finance.SenateFinanceError, match="response limit"):
        senate_finance._request_html(session, senate_finance.SEARCH_URL)
