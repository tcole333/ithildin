from __future__ import annotations

import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from tools import query_usaspending


def test_award_detail_404_exits_nonzero_with_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing_award(*_args, **_kwargs):
        raise HTTPError(
            "https://api.usaspending.gov/api/v2/awards/CONT_AWD_missing/",
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"detail":"Not found."}'),
        )

    monkeypatch.setattr(query_usaspending, "urlopen", missing_award)
    output = tmp_path / "missing-award.json"
    args = SimpleNamespace(
        award_id="CONT_AWD_missing",
        output=str(output),
        json_out=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        query_usaspending.cmd_award_detail(args)

    assert exc_info.value.code == 1
    saved = json.loads(output.read_text())
    assert saved["status"] == "error"
    assert saved["results"] == []
    assert saved["errors"][0]["kind"] == "http"
    assert 'ERROR: HTTP 404: {"detail":"Not found."}' in capsys.readouterr().err


def test_award_detail_resolves_plain_piid_before_detail_fetch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    piid = "70CDCR26FR0000002"
    generated_id = "CONT_AWD_70CDCR26FR0000002_7012_-NONE-_-NONE-"
    search_payloads = []

    def fake_post(endpoint, payload):
        assert endpoint == "/search/spending_by_award/"
        search_payloads.append(payload)
        if payload["filters"]["award_type_codes"] == query_usaspending.CONTRACT_AWARD_TYPES:
            return {
                "results": [
                    {
                        "Award ID": piid,
                        "Recipient Name": "TEST RECIPIENT",
                        "Awarding Agency": "Department of Homeland Security",
                        "generated_internal_id": generated_id,
                    }
                ]
            }
        return {"results": []}

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_post)
    monkeypatch.setattr(
        query_usaspending,
        "_fetch_get",
        lambda endpoint: (
            {"generated_unique_award_id": generated_id}
            if endpoint == f"/awards/{generated_id}/"
            else pytest.fail(f"unexpected endpoint: {endpoint}")
        ),
    )
    output = tmp_path / "award.json"

    query_usaspending.cmd_award_detail(
        SimpleNamespace(
            award_id=piid,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text())["generated_unique_award_id"] == generated_id
    assert len(search_payloads) == 2
    for payload in search_payloads:
        assert payload["filters"]["award_ids"] == [piid]


def test_award_detail_reports_upstream_503_without_claiming_no_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unavailable_search(*_args, **_kwargs):
        raise HTTPError(
            "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            503,
            "Service Unavailable",
            {},
            io.BytesIO(b'{"detail":"Service temporarily unavailable."}'),
        )

    monkeypatch.setattr(query_usaspending, "urlopen", unavailable_search)
    output = tmp_path / "award.json"

    with pytest.raises(SystemExit) as exc_info:
        query_usaspending.cmd_award_detail(
            SimpleNamespace(
                award_id="FA857125C0052",
                output=str(output),
                json_out=False,
            )
        )

    assert exc_info.value.code == 1
    saved = json.loads(output.read_text())
    assert saved["status"] == "error"
    assert saved["results"] == []
    assert len(saved["errors"]) == 2
    stderr = capsys.readouterr().err
    assert stderr.count("ERROR: HTTP 503") == 2
    assert "2 USAspending award search request(s) failed" in stderr
    assert "No exact USAspending award matched" not in stderr


def test_transactions_cli_rejects_limit_above_advanced_search_max(
    run_python_script,
) -> None:
    completed = run_python_script(
        "tools/query_usaspending.py",
        "transactions",
        "TEST RECIPIENT",
        "--limit",
        "101",
    )

    assert completed.returncode == 2
    assert "limit must be between 1 and 100" in completed.stderr


def test_transactions_support_subtier_agency_and_disclose_uei_expansion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured = {}
    requested_uei = "JMLKZZ1NL2Z6"
    result_rows = [
        {
            "Award ID": "PRIME-1",
            "Recipient Name": "THE GEO GROUP, INC.",
            "Recipient UEI": requested_uei,
            "Transaction Amount": 100,
        },
        {
            "Award ID": "PRIME-2",
            "Recipient Name": "BI INCORPORATED",
            "Recipient UEI": "CHILDUEI1234",
            "Transaction Amount": 200,
        },
    ]

    def fake_post(endpoint, payload):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {
            "results": result_rows,
            "page_metadata": {
                "page": 3,
                "next": 4,
                "previous": 2,
                "hasNext": True,
                "hasPrevious": True,
            },
        }

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_post)
    output = tmp_path / "transactions.json"
    args = SimpleNamespace(
        query=None,
        uei=requested_uei,
        agency="U.S. Immigration and Customs Enforcement",
        agency_tier="subtier",
        date_range=None,
        grants=False,
        limit=100,
        page=3,
        output=str(output),
        json_out=False,
    )

    query_usaspending.cmd_transactions(args)

    assert captured["endpoint"] == "/search/spending_by_transaction/"
    assert captured["payload"]["filters"]["agencies"] == [
        {
            "type": "awarding",
            "tier": "subtier",
            "name": "U.S. Immigration and Customs Enforcement",
        }
    ]
    saved = json.loads(output.read_text())
    assert saved["query"]["recipient_scope_expansion_observed"] is True
    assert saved["pagination"]["reported_total"] is None
    assert saved["pagination"]["has_next"] is True
    assert saved["pagination"]["next_page"] == 4
    assert saved["results"] == result_rows
    assert saved["returned_recipients"] == [
        {
            "recipient_uei": "CHILDUEI1234",
            "recipient_name": "BI INCORPORATED",
        },
        {
            "recipient_uei": requested_uei,
            "recipient_name": "THE GEO GROUP, INC.",
        },
    ]


def test_top_recipients_uses_current_naics_filter_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured = {}

    def fake_post(endpoint, payload):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return {"results": []}

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_post)
    query_usaspending.cmd_top_recipients(
        SimpleNamespace(
            agency="Department of Homeland Security",
            naics="922140",
            date_range="2007-10-01,2026-07-14",
            grants=False,
            limit=100,
            output=str(tmp_path / "recipients.json"),
            json_out=False,
        )
    )

    assert captured["endpoint"] == "/search/spending_by_category/recipient/"
    assert captured["payload"]["filters"]["naics_codes"] == {
        "require": ["922140"],
        "exclude": [],
    }


def test_recipient_writes_structured_summary_to_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recipient = {
        "recipient_name": "PALANTIR TECHNOLOGIES INC.",
        "uei": "RN99S3S7N977",
        "duns": "123456789",
    }
    agency_rows = [
        {
            "name": "Department of Defense",
            "amount": 1234567.89,
        }
    ]

    def fake_fetch(endpoint, payload):
        if endpoint == "/autocomplete/recipient/":
            assert payload == {"search_text": "Palantir Technologies"}
            return {"results": [recipient]}
        assert endpoint == "/search/spending_by_category/awarding_agency/"
        assert payload["filters"]["recipient_search_text"] == [
            "RN99S3S7N977"
        ]
        return {"results": agency_rows}

    monkeypatch.setattr(query_usaspending, "_fetch_post", fake_fetch)
    output = tmp_path / "recipient.json"
    args = SimpleNamespace(
        query="Palantir Technologies",
        output=str(output),
        json_out=False,
    )

    query_usaspending.cmd_recipient(args)

    saved = json.loads(output.read_text())
    assert saved["recipient"] == recipient
    assert saved["spending_by_agency"] == agency_rows
    assert saved["results"] == [recipient]
    assert saved["status"] == "success"
    assert saved["errors"] == []
    stdout = capsys.readouterr().out
    assert "saved to" in stdout
    assert "Recipient: PALANTIR" not in stdout
