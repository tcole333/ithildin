import json
from pathlib import Path

import pytest

from tools import query_massachusetts_ucc as ucc
from tools import source_report


FIXTURES = Path(__file__).parent / "fixtures" / "massachusetts_ucc"
RESULTS_URL = "https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx"
HISTORY_URL = RESULTS_URL.replace("UCCSearchResults", "UCCFilingHistory")


def page(name, url=RESULTS_URL):
    return {"html": (FIXTURES / name).read_text(), "url": url}


def fake_helper(monkeypatch, *pages):
    monkeypatch.setattr(ucc, "run_helper", lambda _payload: {"ok": True, "pages": list(pages)})
    logs = []
    monkeypatch.setattr(ucc, "log_search", lambda *args: logs.append(args))
    return logs


def test_live_search_fixture_preserves_source_fields():
    data = ucc.parse_search_page(**page("search-1.html"))
    assert data["reported_count"] == 1
    row, = data["results"]
    assert row["name"] == "HARVARD BIOSCIENCE, INC."
    assert row["name_type"] == "DEBTOR"
    assert row["filing_number"] == row["original_filing_number"] == "202178754190"
    assert row["filing_date"] == "06/29/2021"
    assert row["filing_date_iso"] == "2021-06-29"
    assert row["citation"] == "MA-UCC:202178754190"
    assert row["history_url"].startswith(HISTORY_URL + "?sysvalue=")
    assert len(row["raw_cells"]) == 8
    assert data["search_criteria"]["Include"] == "DEBTORS,"


def test_history_keeps_per_filing_actions_and_parties():
    records = ucc.parse_filing_page(**page("filing.html", HISTORY_URL), requested_number="202516436650")
    assert [record["filing_number"] for record in records] == [
        "202061174700", "202412627170", "202516436650",
    ]
    assert [record["action"] for record in records] == [
        "Assignment", "Continuation", "TerminationSecuredParty",
    ]
    assert records[0]["filing_datetime_iso"] == "2020-01-02T16:26:00"
    for record in records:
        assert record["debtors"][0]["name"] == "HARVARD APARTMENTS LLC"
        assert record["secured_parties"][0]["name"] == "GREYSTONE SERVICING COMPANY LLC"
        assert record["assignees"][0]["name"] == "FANNIE MAE"
        assert record["collateral"] == []  # Unavailable; not borrowed from another record.
    assert records[0]["documents"][0]["page_count"] == 7
    assert records[-1]["documents"][0]["page_count"] == 1
    assert "UCCSearchViewPDF.aspx?Path=DRIVE1/2020/0102/" in records[0]["documents"][0]["viewer_url"]


def test_collateral_textarea_and_inline_corporation_type():
    record, = ucc.parse_filing_page(**page("collateral.html", HISTORY_URL), requested_number="202178754190")
    assert record["debtors"][0] == {
        "name": "HARVARD BIOSCIENCE, INC.",
        "address_lines": ["84 OCTOBER HILL RD", "HOLLISTON MA 01746"],
        "corporation_type": "CORPORATION",
        "raw_text": "HARVARD BIOSCIENCE, INC.\n84 OCTOBER HILL RD\nHOLLISTON MA 01746\nCorp Type: CORPORATION",
    }
    assert record["collateral"][0].startswith("One  - New Xerox C8145106180 ,\n")
    assert "This filing is for protective purposes only." in record["collateral"][0]


def test_history_must_include_requested_filing():
    with pytest.raises(ucc.PortalError, match="does not contain"):
        ucc.parse_filing_page(**page("filing.html", HISTORY_URL), requested_number="111111111111")


@pytest.mark.parametrize("html", [
    '<html><script src="/_Incapsula_Resource"></script></html>',
    '<h2>UCC Public Search</h2><p>No results</p>',
    '<h2>UCC Search Results</h2><table id="MainContent_grdSearchResults"></table><p>Number of records: 1</p>',
    '<h2>UCC Search Results</h2><table id="MainContent_grdSearchResults"><tr><td>Changed</td></tr></table><p>Number of records: 1</p>',
    '<h2>UCC Search Results</h2><span id="MainContent_lblMessage">Service unavailable</span>',
])
def test_challenges_and_changed_pages_are_errors_not_zero(html):
    with pytest.raises(ucc.PortalError):
        ucc.parse_search_page(html, RESULTS_URL)


def test_verified_empty_page_is_distinct_from_unavailable(monkeypatch):
    logs = fake_helper(monkeypatch, page("empty.html"))
    result = ucc.execute({"command": "search-org", "query": "ZZZZCODEXUCCNONMATCH", "limit": 25})
    assert result["reported_count"] == result["returned"] == 0
    assert result["truncated"] is False
    assert logs[0][2] == 0
    result = ucc.execute({"command": "filing", "query": "111111111111"})
    assert result["found"] is False
    assert result["filings"] == []


def test_two_page_limit_and_occurrences_are_preserved(monkeypatch):
    logs = fake_helper(monkeypatch, page("pagination-1.html"), page("pagination-2.html"))
    payload = {"command": "search-org", "query": "HARVARD", "limit": 26, "role": "debtor", "lapsed": True}
    result = ucc.execute(payload)
    assert result["reported_count"] == 238
    assert result["returned"] == 26
    assert result["pages_fetched"] == 2
    assert result["truncated"] is True
    assert result["scope"] == "lapsed"
    assert [row["occurrence"] for row in result["results"]] == list(range(1, 27))
    # Multiple amendments to the same initial filing remain separate occurrences.
    assert len([row for row in result["results"] if row["original_filing_number"] == "202061174700"]) == 3
    assert len(result["provenance"]) == 2
    assert all(len(item["sha256"]) == 64 for item in result["provenance"])
    key, source, count = logs[0]
    assert json.loads(key) == {"mode": "search-org", "query": "HARVARD", "limit": 26, "role": "debtor", "lapsed": True}
    assert source == "massachusetts_ucc" and count == 26


@pytest.mark.parametrize("names", [
    ("pagination-1.html",),
    ("pagination-1.html", "pagination-1.html"),
    ("pagination-1.html", "search-1.html"),
])
def test_stopped_replayed_or_drifting_pagination_fails(monkeypatch, names):
    logs = fake_helper(monkeypatch, *(page(name) for name in names))
    with pytest.raises(ucc.PortalError):
        ucc.execute({"command": "search-org", "query": "HARVARD", "limit": 50})
    assert logs == []


@pytest.mark.parametrize("argv", [
    ["search-org", ""],
    ["search-org", "A" * 176],
    ["search-individual", "A" * 36],
    ["search-individual", "SMITH", "--first", "A" * 26],
    ["search-org", "HARVARD", "--city", "A" * 36],
    ["search-org", "HARVARD", "--limit", "501"],
    ["search-org", "HARVARD", "--limit", "0"],
    ["search-org", "HARVARD", "--since", "2026-02-30"],
    ["search-org", "HARVARD", "--since", "20260903"],
    ["search-org", "HARVARD", "--state", "Massachusetts"],
    ["search-org", "HARVARD", "--role", "secured", "--search-type", "article9"],
    ["search-individual", "SMITH", "--search-type", "exact"],
    ["filing", "2021787541901"],
    ["filing", "not-a-number"],
])
def test_invalid_inputs_fail_before_browser(monkeypatch, argv):
    monkeypatch.setattr(ucc, "run_helper", lambda _: pytest.fail("Browser must not run"))
    with pytest.raises(SystemExit) as exc:
        ucc.main(argv)
    assert exc.value.code == 2


def test_cli_writes_filing_json(monkeypatch, tmp_path):
    fake_helper(monkeypatch, page("collateral.html", HISTORY_URL))
    output = tmp_path / "filing.json"
    assert ucc.main(["filing", "202178754190", "--output", str(output)]) == 0
    data = json.loads(output.read_text())
    assert data["found"] is True and data["returned"] == 1
    assert data["filings"][0]["filing_number"] == "202178754190"


def test_cli_unavailable_writes_error_artifact_and_no_search_log(monkeypatch, tmp_path):
    def blocked(_payload):
        raise ucc.PortalError("Browser challenge")
    monkeypatch.setattr(ucc, "run_helper", blocked)
    monkeypatch.setattr(ucc, "log_search", lambda *_args: pytest.fail("Cannot log unavailable as zero"))
    output = tmp_path / "error.json"
    assert ucc.main(["search-org", "HARVARD", "--output", str(output)]) == 1
    assert json.loads(output.read_text()) == {
        "source": "massachusetts_ucc", "status": "error",
        "source_available": False, "error": "Browser challenge",
    }


def test_probe_requires_real_form(monkeypatch):
    fake_helper(monkeypatch, {"url": ucc.SEARCH_URL, "html": "<h2>Browser challenge</h2>"})
    with pytest.raises(ucc.PortalError):
        ucc.execute({"command": "probe"})


def test_source_readiness_does_not_probe_other_sources(monkeypatch):
    monkeypatch.setattr(ucc, "runtime_check", lambda: {"ok": True, "runtime": {"channel": "chrome"}})
    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.setattr(source_report.sqlite3, "connect", lambda *_: pytest.fail("Unrelated DB access"))
    monkeypatch.setattr("urllib.request.urlopen", lambda *_: pytest.fail("Unrelated network access"))
    result = source_report.quick_health_check("Massachusetts UCC")
    assert result["status"] == "configured"
    assert "run query_massachusetts_ucc.py probe" in result["note"]
    readiness = source_report.check_massachusetts_ucc_runtime()
    assert readiness["live_checked"] is False
    assert readiness["runtime"]["ok"] is True
