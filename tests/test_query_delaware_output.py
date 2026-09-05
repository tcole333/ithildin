import json
import sys

from tools import query_delaware


def _entity_result():
    return {
        "name": "TEST HOLDINGS, LLC",
        "company_number": "1234567",
        "company_type": "Domestic Limited Liability Company",
        "incorporation_date": "2020-01-01",
        "agent_name": "TEST AGENT",
        "officers": [],
        "filings_count": 0,
    }


def test_entity_output_writes_requested_json(monkeypatch, tmp_path, capsys):
    output_path = tmp_path / "entity.json"
    monkeypatch.setattr(query_delaware, "get_company", lambda _number: _entity_result())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_delaware.py",
            "entity",
            "1234567",
            "--output",
            str(output_path),
        ],
    )

    query_delaware.main()

    assert json.loads(output_path.read_text()) == _entity_result()
    assert f"saved to {output_path}" in capsys.readouterr().out


def test_entity_json_flag_emits_raw_json(monkeypatch, capsys):
    monkeypatch.setattr(query_delaware, "get_company", lambda _number: _entity_result())
    monkeypatch.setattr(
        sys,
        "argv",
        ["query_delaware.py", "entity", "1234567", "--json"],
    )

    query_delaware.main()

    assert json.loads(capsys.readouterr().out) == _entity_result()
