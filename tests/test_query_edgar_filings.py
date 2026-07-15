from __future__ import annotations

import argparse
import json

from tools import query_edgar


def _filings(*, dates, forms, accessions, documents=None, descriptions=None):
    count = len(forms)
    return {
        "filingDate": dates,
        "form": forms,
        "accessionNumber": accessions,
        "primaryDocument": documents or ["primary.htm"] * count,
        "primaryDocDescription": descriptions or [""] * count,
    }


def _args(output, **overrides):
    values = {
        "cik": "42",
        "form": None,
        "limit": 30,
        "start": None,
        "end": None,
        "output": str(output),
        "json_out": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_filings_fetches_newest_history_segments_until_limit(
    tmp_path, monkeypatch
):
    main_url = f"{query_edgar.SUBMISSIONS_URL}/CIK0000000042.json"
    newer_url = f"{query_edgar.SUBMISSIONS_URL}/newer.json"
    calls = []

    responses = {
        main_url: {
            "name": "Example Co",
            "cik": "0000000042",
            "filings": {
                "recent": _filings(
                    dates=["2025-01-02", "2025-01-01"],
                    forms=["10-K", "8-K"],
                    accessions=["0000000042-25-000002", "0000000042-25-000001"],
                ),
                # Deliberately oldest-first: output must remain newest-first.
                "files": [
                    {
                        "name": "older.json",
                        "filingFrom": "2000-01-01",
                        "filingTo": "2009-12-31",
                    },
                    {
                        "name": "newer.json",
                        "filingFrom": "2010-01-01",
                        "filingTo": "2024-12-31",
                    },
                ],
            },
        },
        newer_url: _filings(
            dates=["2024-06-01", "2023-06-01", "2022-06-01"],
            forms=["10-K", "10-K", "10-K"],
            accessions=[
                "0000000042-24-000001",
                "0000000042-23-000001",
                "0000000042-22-000001",
            ],
        ),
    }

    def fake_request(url, **kwargs):
        calls.append((url, kwargs))
        return responses[url]

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    output = tmp_path / "filings.json"
    query_edgar.cmd_filings(_args(output, form="10-K", limit=3))

    payload = json.loads(output.read_text())
    assert [row["date"] for row in payload["filings"]] == [
        "2025-01-02",
        "2024-06-01",
        "2023-06-01",
    ]
    assert payload["total_recent_filings"] == 2
    assert payload["historical_files_fetched"] == 1
    assert payload["historical_filings_examined"] == 2
    assert payload["matched_filings"] == 3
    assert [url for url, _ in calls] == [main_url, newer_url]
    assert all(
        kwargs["max_bytes"] == query_edgar.MAX_SUBMISSIONS_BYTES
        for _, kwargs in calls
    )


def test_filings_skips_history_segments_outside_date_range(tmp_path, monkeypatch):
    main_url = f"{query_edgar.SUBMISSIONS_URL}/CIK0000000042.json"
    overlap_url = f"{query_edgar.SUBMISSIONS_URL}/overlap.json"
    calls = []
    responses = {
        main_url: {
            "name": "Example Co",
            "cik": "0000000042",
            "filings": {
                "recent": _filings(
                    dates=["2025-01-01"],
                    forms=["8-K"],
                    accessions=["0000000042-25-000001"],
                ),
                "files": [
                    {
                        "name": "too-new.json",
                        "filingFrom": "2010-01-01",
                        "filingTo": "2012-12-31",
                    },
                    {
                        "name": "overlap.json",
                        "filingFrom": "2008-01-01",
                        "filingTo": "2010-01-01",
                    },
                    {
                        "name": "too-old.json",
                        "filingFrom": "1990-01-01",
                        "filingTo": "1999-12-31",
                    },
                ],
            },
        },
        overlap_url: _filings(
            dates=["2009-06-01"],
            forms=["10-K"],
            accessions=["0000000042-09-000001"],
        ),
    }

    def fake_request(url, **kwargs):
        calls.append(url)
        return responses[url]

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    output = tmp_path / "filings.json"
    query_edgar.cmd_filings(
        _args(
            output,
            form="10-K",
            limit=5,
            start="2009-01-01",
            end="2009-12-31",
        )
    )

    payload = json.loads(output.read_text())
    assert [row["date"] for row in payload["filings"]] == ["2009-06-01"]
    assert payload["historical_files_fetched"] == 1
    assert calls == [main_url, overlap_url]


def test_filings_does_not_fetch_history_after_recent_limit(tmp_path, monkeypatch):
    main_url = f"{query_edgar.SUBMISSIONS_URL}/CIK0000000042.json"
    calls = []
    response = {
        "name": "Example Co",
        "cik": "0000000042",
        "filings": {
            "recent": _filings(
                dates=["2025-01-03", "2025-01-02", "2025-01-01"],
                forms=["8-K", "8-K", "8-K"],
                accessions=[
                    "0000000042-25-000003",
                    "0000000042-25-000002",
                    "0000000042-25-000001",
                ],
            ),
            "files": [
                {
                    "name": "older.json",
                    "filingFrom": "2000-01-01",
                    "filingTo": "2024-12-31",
                }
            ],
        },
    }

    def fake_request(url, **kwargs):
        calls.append(url)
        assert url == main_url
        return response

    monkeypatch.setattr(query_edgar, "_request", fake_request)
    output = tmp_path / "filings.json"
    query_edgar.cmd_filings(_args(output, limit=2))

    payload = json.loads(output.read_text())
    assert len(payload["filings"]) == 2
    assert payload["historical_files_fetched"] == 0
    assert calls == [main_url]
