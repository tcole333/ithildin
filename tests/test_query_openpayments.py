import argparse
import json
from urllib.error import HTTPError

import pytest

from tools import query_openpayments


class _Headers:
    def __init__(self, content_type="application/json"):
        self.content_type = content_type

    def get_content_type(self):
        return self.content_type


class _Response:
    def __init__(self, data, content_type="application/json"):
        self.body = json.dumps(data).encode()
        self.headers = _Headers(content_type)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=None):
        return self.body if limit is None else self.body[:limit]


def _args(**overrides):
    values = {
        "output": None,
        "json_out": False,
        "limit": 25,
        "offset": 0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_get_json_retries_429_and_declares_identity(monkeypatch):
    attempts = []
    sleeps = []

    def fake_urlopen(request, timeout):
        attempts.append((request, timeout))
        if len(attempts) == 1:
            raise HTTPError(request.full_url, 429, "rate limit", {}, None)
        return _Response({"results": []})

    monkeypatch.setattr(query_openpayments, "urlopen", fake_urlopen)
    monkeypatch.setattr(query_openpayments, "_pace", lambda: None)
    monkeypatch.setattr(query_openpayments.time, "sleep", sleeps.append)

    result = query_openpayments._get_json("/datastore/query/dataset/0", [("limit", 1)])

    assert result == {"results": []}
    assert len(attempts) == 2
    assert attempts[0][0].get_header("User-agent") == query_openpayments.USER_AGENT
    assert attempts[0][1] == query_openpayments.REQUEST_TIMEOUT
    assert sleeps == [0.5]


def test_get_json_rejects_non_json(monkeypatch):
    monkeypatch.setattr(
        query_openpayments,
        "urlopen",
        lambda *_args, **_kwargs: _Response({}, "text/html"),
    )
    monkeypatch.setattr(query_openpayments, "_pace", lambda: None)

    with pytest.raises(query_openpayments.OpenPaymentsError, match="content type"):
        query_openpayments._get_json("/test")


def test_query_dataset_builds_bounded_exact_conditions(monkeypatch):
    captured = {}

    def fake_get(path, params):
        captured["path"] = path
        captured["params"] = params
        return {"results": [{"recipient_id": "704135"}], "count": 1}

    monkeypatch.setattr(query_openpayments, "_get_json", fake_get)
    data = query_openpayments.query_dataset(
        "valid-dataset-id",
        [query_openpayments.Condition("recipient_id", "704135")],
        limit=50,
        offset=10,
    )

    assert data["count"] == 1
    assert captured["path"] == "/datastore/query/valid-dataset-id/0"
    assert captured["params"] == [
        ("limit", 50),
        ("offset", 10),
        ("conditions[0][property]", "recipient_id"),
        ("conditions[0][value]", "704135"),
        ("conditions[0][operator]", "="),
    ]


@pytest.mark.parametrize("limit", [0, 501])
def test_query_dataset_rejects_unbounded_limits(limit):
    with pytest.raises(query_openpayments.OpenPaymentsError, match="--limit"):
        query_openpayments.query_dataset("valid-dataset-id", limit=limit)


def test_catalog_summary_extracts_current_dkan_distribution():
    item = {
        "identifier": "abc",
        "title": "2025 General Payment Data",
        "issued": "2026-06-30",
        "distribution": [
            {
                "identifier": "distribution-id",
                "data": {
                    "format": "csv",
                    "downloadURL": "https://download.cms.gov/openpayments/general.csv",
                    "describedBy": "https://openpaymentsdata.cms.gov/api/dictionary",
                },
            }
        ],
    }

    summary = query_openpayments.summarize_dataset(item)

    assert summary["identifier"] == "abc"
    assert summary["format"] == "csv"
    assert summary["download_url"].startswith("https://download.cms.gov/openpayments/")
    assert summary["data_dictionary_url"].endswith("/dictionary")


def test_search_uses_exact_uppercase_name_filters_and_logs(monkeypatch, tmp_path):
    captured = {}

    def fake_query(dataset_id, conditions, **kwargs):
        captured["dataset_id"] = dataset_id
        captured["conditions"] = conditions
        captured.update(kwargs)
        return {
            "results": [{"covered_recipient_profile_id": "704135"}],
            "count": 1,
        }

    logs = []
    monkeypatch.setattr(query_openpayments, "query_dataset", fake_query)
    monkeypatch.setattr(query_openpayments, "log_search", lambda *values: logs.append(values))
    output = tmp_path / "profiles.json"

    query_openpayments.cmd_search(
        _args(
            query="Merkin",
            first_name="Michael",
            state="ny",
            output=str(output),
        )
    )

    assert captured["dataset_id"] == query_openpayments.PROFILE_DATASET_ID
    assert captured["conditions"] == [
        query_openpayments.Condition("covered_recipient_profile_last_name", "MERKIN"),
        query_openpayments.Condition("covered_recipient_profile_first_name", "MICHAEL"),
        query_openpayments.Condition("covered_recipient_profile_state", "NY"),
    ]
    assert logs == [("Merkin", "cms_openpayments_profiles", 1)]
    saved = json.loads(output.read_text())
    assert saved["results"][0]["covered_recipient_profile_id"] == "704135"
    assert saved["results"][0]["evidence_ref"] == "OPENPAYMENTS:704135"
    assert saved["results"][0]["profile_url"].endswith("/physician/704135")


def test_payments_combines_company_and_decoded_nature_summaries(monkeypatch, tmp_path):
    def fake_query(dataset_id, conditions, **_kwargs):
        assert conditions == [query_openpayments.Condition("recipient_id", "704135")]
        if dataset_id == query_openpayments.ALL_YEARS_COMPANY_DATASET_ID:
            return {
                "results": [
                    {
                        "recipient_id": "704135",
                        "payment_type": "General",
                        "amgpo_name": "Teva Pharmaceuticals USA, Inc.",
                        "total_amount": "110.67",
                    }
                ],
                "count": 1,
            }
        assert dataset_id == query_openpayments.ALL_YEARS_NATURE_DATASET_ID
        return {
            "results": [
                {
                    "recipient_id": "704135",
                    "nature_of_payment_type_code": "6",
                    "total_amount": "110.67",
                }
            ],
            "count": 1,
        }

    logs = []
    monkeypatch.setattr(query_openpayments, "query_dataset", fake_query)
    monkeypatch.setattr(query_openpayments, "log_search", lambda *values: logs.append(values))
    output = tmp_path / "payments.json"

    query_openpayments.cmd_payments(
        _args(profile_id="704135", year="all", limit=100, output=str(output))
    )

    data = json.loads(output.read_text())
    assert data["totals"] == {"reporting_entities": 1, "payment_natures": 1}
    assert data["evidence_ref"] == "OPENPAYMENTS:704135"
    assert data["truncated"] is False
    assert data["records"][0]["summary_kind"] == "reporting_entity"
    assert data["records"][0]["evidence_ref"] == "OPENPAYMENTS:704135"
    assert data["records"][1]["nature_of_payment"] == "Food and Beverage"
    assert logs == [("profile:704135:year:all", "cms_openpayments_payments", 2)]


def test_program_year_ids_are_discovered_by_exact_catalog_title(monkeypatch):
    monkeypatch.setattr(
        query_openpayments,
        "get_catalog",
        lambda: [
            {
                "identifier": "company-2025",
                "title": "2025 payments grouped by covered recipient and reporting entities",
            },
            {
                "identifier": "nature-2025",
                "title": "2025 payments grouped by covered recipient and nature of payments",
            },
        ],
    )

    assert query_openpayments._year_dataset_ids("2025") == (
        "company-2025",
        "nature-2025",
    )


def test_generic_where_parser_only_accepts_simple_exact_fields():
    assert query_openpayments._parse_where("recipient_id=704135") == query_openpayments.Condition(
        "recipient_id", "704135"
    )
    with pytest.raises(argparse.ArgumentTypeError):
        query_openpayments._parse_where("recipient-id=704135")
    with pytest.raises(argparse.ArgumentTypeError):
        query_openpayments._parse_where("recipient_id")
