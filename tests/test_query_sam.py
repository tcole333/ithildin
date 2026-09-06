"""Regression tests for the SAM.gov API wrapper."""

from __future__ import annotations

import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from tools import env_loader
from tools import query_sam


def test_missing_api_key_exits_nonzero_with_explicit_diagnostic(monkeypatch, capsys):
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "")

    with pytest.raises(SystemExit) as exc_info:
        query_sam._check_api_key()

    assert exc_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "ERROR: SAM_API_KEY not set" in stderr
    assert "export SAM_API_KEY" in stderr


def test_query_sam_loads_api_key_from_repo_env(monkeypatch, tmp_path):
    monkeypatch.delenv("SAM_API_KEY", raising=False)
    monkeypatch.setattr(env_loader, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text("SAM_API_KEY=test-sam-key\n")

    reloaded = importlib.reload(query_sam)

    assert reloaded.SAM_API_KEY == "test-sam-key"


def test_fetch_uses_bounded_connect_and_read_timeouts(monkeypatch):
    calls = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_get(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(query_sam.requests, "get", fake_get)

    result = query_sam._fetch("https://api.sam.gov/example", {"q": "GEO"})

    assert result == {"ok": True}
    assert calls["timeout"] == (10, 60)
    assert calls["params"] == {"q": "GEO", "api_key": "test-sam-key"}
    assert calls["headers"] == {"User-Agent": "OSINT-Research/1.0"}


def test_fetch_normalizes_204_to_explicit_zero_records(monkeypatch):
    class FakeResponse:
        status_code = 204

        def raise_for_status(self):
            return None

        def json(self):
            raise AssertionError("204 response must not be decoded")

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(query_sam.requests, "get", lambda _url, **_kwargs: FakeResponse())

    assert query_sam._fetch("https://api.sam.gov/example") == {"totalRecords": 0}


def test_fetch_timeout_is_diagnostic_and_redacts_key(monkeypatch, capsys):
    secret = "test-sam-key"

    def fake_get(_url, **_kwargs):
        raise query_sam.requests.Timeout(f"timed out with api_key={secret}")

    monkeypatch.setattr(query_sam, "SAM_API_KEY", secret)
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(query_sam.requests, "get", fake_get)

    assert query_sam._fetch("https://api.sam.gov/example") is None
    stderr = capsys.readouterr().err
    assert "SAM.gov request timed out" in stderr
    assert "[REDACTED]" in stderr
    assert secret not in stderr


def test_fetch_429_explains_quota_without_retrying(monkeypatch, capsys):
    calls = 0

    class FakeResponse:
        status_code = 429
        text = "daily request limit reached"

        def raise_for_status(self):
            raise query_sam.requests.HTTPError(response=self)

    def fake_get(_url, **_kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse()

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(query_sam.requests, "get", fake_get)

    assert query_sam._fetch("https://api.sam.gov/example") is None
    stderr = capsys.readouterr().err
    assert "rate limit exceeded (HTTP 429)" in stderr
    assert "10 requests/day" in stderr
    assert "1,000/day" in stderr
    assert calls == 1


def _contract_args(*, output=None):
    return SimpleNamespace(
        query=None,
        uei="JMLKZZ1NL2Z6",
        piid=None,
        naics=None,
        psc=None,
        agency=None,
        date_signed_from=None,
        date_signed_to=None,
        min_amount=None,
        sections=None,
        limit=100,
        output=output,
        json_out=False,
    )


def _current_contract_response():
    return {
        "awardSummary": [
            {
                "contractId": {"piid": "70CDCR24D00000001"},
                "coreData": {
                    "federalOrganization": {
                        "contractingInformation": {
                            "contractingDepartment": {"name": "DEPARTMENT OF HOMELAND SECURITY"},
                            "contractingOffice": {"name": "ICE DETENTION COMPLIANCE"},
                        }
                    },
                    "productOrServiceInformation": {
                        "productOrService": {"code": "S206"},
                        "principalNaics": [{"code": "561612"}],
                    },
                },
                "awardDetails": {
                    "dates": {"dateSigned": "2026-01-15T00:00:00Z"},
                    "dollars": {"actionObligation": "1500.25"},
                    "productOrServiceInformation": {
                        "descriptionOfContractRequirement": "Detention services"
                    },
                    "awardeeData": {
                        "awardeeHeader": {"legalBusinessName": "THE GEO GROUP, INC."},
                        "awardeeUEIInformation": {"uniqueEntityId": "JMLKZZ1NL2Z6"},
                    },
                },
            }
        ],
        "totalRecords": "4599",
        "limit": "100",
        "offset": "0",
    }


def test_contracts_saves_current_award_summary_records(monkeypatch, tmp_path):
    output = tmp_path / "contracts.json"
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: _current_contract_response())

    status = query_sam.cmd_contracts(_contract_args(output=str(output)))

    assert status is None
    saved = json.loads(output.read_text())
    assert len(saved) == 1
    assert saved[0]["contractId"]["piid"] == "70CDCR24D00000001"


def test_contracts_formats_current_nested_award_fields(monkeypatch, capsys):
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: _current_contract_response())

    query_sam.cmd_contracts(_contract_args())

    stdout = capsys.readouterr().out
    assert "PIID: 70CDCR24D00000001 | $2K | 2026-01-15T00:00:00Z" in stdout
    assert "Awardee: THE GEO GROUP, INC. (UEI: JMLKZZ1NL2Z6)" in stdout
    assert "Agency: DEPARTMENT OF HOMELAND SECURITY / ICE DETENTION COMPLIANCE" in stdout
    assert "NAICS: 561612 | PSC: S206" in stdout
    assert "Desc: Detention services" in stdout


def test_contract_cli_converts_iso_dates_to_sam_format(monkeypatch, tmp_path):
    calls = {}
    output = tmp_path / "contracts.json"

    def fake_fetch(_url, params):
        calls["params"] = params
        return {"awardSummary": [], "totalRecords": "0"}

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", fake_fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_sam.py",
            "contracts",
            "--uei",
            "JMLKZZ1NL2Z6",
            "--date-signed-from",
            "2025-09-01",
            "--date-signed-to",
            "2026-02-01",
            "--output",
            str(output),
        ],
    )

    assert query_sam.main() == 0
    assert calls["params"]["dateSigned"] == "[09/01/2025,02/01/2026]"
    assert json.loads(output.read_text()) == []


def test_contract_cli_rejects_non_iso_date_before_request(monkeypatch):
    called = False

    def fake_fetch(_url, _params):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", fake_fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sam.py", "contracts", "--uei", "JMLKZZ1NL2Z6", "--date-signed-from", "09/01/2025"],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 2
    assert called is False


def test_exclusions_uses_documented_uei_and_current_response_shape(monkeypatch, tmp_path):
    calls = {}
    output = tmp_path / "exclusions.json"
    response = {
        "totalRecords": 1,
        "excludedEntity": [
            {
                "exclusionDetails": {
                    "classificationType": "Firm",
                    "exclusionType": "Ineligible (Proceedings Completed)",
                    "excludingAgencyName": "DEPARTMENT OF JUSTICE",
                },
                "exclusionIdentification": {
                    "ueiSAM": "JMLKZZ1NL2Z6",
                    "entityName": "THE GEO GROUP, INC.",
                },
            }
        ],
    }

    def fake_fetch(url, params):
        calls["url"] = url
        calls["params"] = params
        return response

    args = SimpleNamespace(
        query=None,
        classification=None,
        type=None,
        agency=None,
        state=None,
        uei="JMLKZZ1NL2Z6",
        npi=None,
        output=str(output),
        json_out=False,
    )
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", fake_fetch)

    status = query_sam.cmd_exclusions(args)

    assert status is None
    assert calls["url"].endswith("/entity-information/v4/exclusions")
    assert calls["params"] == {"ueiSAM": "JMLKZZ1NL2Z6"}
    assert json.loads(output.read_text()) == response["excludedEntity"]


def test_exclusions_accepts_documented_v4_type(monkeypatch, tmp_path):
    calls = {}
    output = tmp_path / "exclusions.json"

    def fake_fetch(_url, params):
        calls["params"] = params
        return {"excludedEntity": [], "totalRecords": 0}

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", fake_fetch)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_sam.py",
            "exclusions",
            "--classification",
            "Firm",
            "--type",
            "Ineligible (Proceedings Completed)",
            "--output",
            str(output),
        ],
    )

    assert query_sam.main() == 0
    assert calls["params"]["classification"] == "Firm"
    assert calls["params"]["exclusionType"] == "Ineligible (Proceedings Completed)"
    assert json.loads(output.read_text()) == []


def test_api_failure_exits_nonzero_and_does_not_write_output(monkeypatch, tmp_path):
    output = tmp_path / "failed.json"
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sam.py", "exclusions", "--uei", "JMLKZZ1NL2Z6", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1
    assert not output.exists()


def test_entity_api_failure_exits_nonzero_and_does_not_write_output(
    monkeypatch, tmp_path
):
    output = tmp_path / "failed-entity.json"
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sam.py", "entity", "Critical Metals Corp", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1
    assert not output.exists()


def test_positive_total_with_unknown_contract_schema_exits_nonzero(monkeypatch, tmp_path):
    output = tmp_path / "unexpected.json"
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: {"totalRecords": 4599})
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sam.py", "contracts", "--uei", "JMLKZZ1NL2Z6", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1
    assert not output.exists()


def test_unknown_contract_schema_without_total_exits_nonzero(monkeypatch, tmp_path):
    output = tmp_path / "unexpected.json"
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: {"message": "unexpected"})
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_sam.py", "contracts", "--uei", "JMLKZZ1NL2Z6", "--output", str(output)],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1
    assert not output.exists()


@pytest.mark.parametrize(
    ("argv", "result"),
    [
        (["query_sam.py", "entity", "GEO"], {"totalRecords": 1}),
        (
            ["query_sam.py", "opportunities", "GEO", "--posted-from", "01/01/2026"],
            {"totalRecords": 1},
        ),
    ],
)
def test_positive_total_with_unknown_list_schema_exits_nonzero(monkeypatch, argv, result):
    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam, "_fetch", lambda _url, _params: result)
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1


def test_opportunities_timeout_exits_nonzero_with_diagnostic_and_no_output(
    monkeypatch, tmp_path, capsys
):
    """A failed opportunity request must not look like a successful empty run."""
    output = tmp_path / "opportunities.json"

    def fake_get(_url, **_kwargs):
        raise query_sam.requests.Timeout("simulated opportunity timeout")

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(query_sam.requests, "get", fake_get)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_sam.py",
            "opportunities",
            "--sol-num",
            "70CDCR20R00000002",
            "--posted-from",
            "01/01/2019",
            "--posted-to",
            "12/31/2020",
            "--limit",
            "100",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        query_sam.main()

    assert exc_info.value.code == 1
    assert not output.exists()
    stderr = capsys.readouterr().err
    assert "ERROR: SAM.gov request timed out" in stderr
    assert "test-sam-key" not in stderr


def test_opportunities_zero_results_writes_output_and_summary(
    monkeypatch, tmp_path, capsys
):
    output = tmp_path / "opportunities.json"

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"totalRecords": 0, "opportunitiesData": []}

    monkeypatch.setattr(query_sam, "SAM_API_KEY", "test-sam-key")
    monkeypatch.setattr(query_sam.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        query_sam.requests, "get", lambda _url, **_kwargs: FakeResponse()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_sam.py",
            "opportunities",
            "--sol-num",
            "70CDCR20R00000002",
            "--posted-from",
            "01/01/2019",
            "--posted-to",
            "12/31/2020",
            "--output",
            str(output),
        ],
    )

    assert query_sam.main() == 0
    assert json.loads(output.read_text()) == []
    stdout = capsys.readouterr().out
    assert "0 results" in stdout
    assert str(output) in stdout
