import json
from argparse import Namespace
from pathlib import Path

import pytest

from tools import query_nyscef
from tools.query_nyscef import _derive_person_fields, _filter_documents, _normalize_date


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "nyscef"


def _load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text())


def _search_args(command, output):
    shared = {"output": str(output), "json_out": False, "limit": 20}
    if command == "search":
        return Namespace(
            **shared,
            query="NoSuchParty",
            attorney=False,
            business=False,
            business_name=None,
            first=None,
            middle=None,
            last=None,
            county=None,
            case_type=None,
            after=None,
            before=None,
        )
    if command == "case":
        return Namespace(
            **shared,
            query="999999/2099",
            mode="index",
            county=None,
            case_type=None,
            after=None,
            before=None,
        )
    return Namespace(
        **shared,
        court="New York County Supreme Court",
        date="2099-01-01",
    )


def test_derive_person_fields_single_token_defaults_to_last_name():
    fields = _derive_person_fields("Epstein")
    assert fields == {"first_name": "", "middle_name": "", "last_name": "Epstein"}


def test_derive_person_fields_multi_token_splits_middle_name():
    fields = _derive_person_fields("Jeffrey Edward Epstein")
    assert fields == {
        "first_name": "Jeffrey",
        "middle_name": "Edward",
        "last_name": "Epstein",
    }


def test_normalize_date_accepts_iso_and_slashed_dates():
    assert _normalize_date("2019-07-10") == "2019-07-10"
    assert _normalize_date("07/10/2019") == "07/10/2019"


def test_filter_documents_matches_multiple_optional_filters():
    docs = [
        {
            "document_number": "1",
            "document_type": "PETITION",
            "filed_by": "SAURBORN, HENRY L",
            "motion_number": None,
            "status": "Processed",
        },
        {
            "document_number": "7",
            "document_type": "ORDER TO SHOW CAUSE ( PROPOSED )",
            "filed_by": "MOSKOWITZ, BENNET J",
            "motion_number": "002",
            "status": "Processed",
        },
    ]

    class Args:
        doc_type = "order to show cause"
        filed_by = "moskowitz"
        motion = "002"
        doc_number = None
        status = "processed"

    filtered = _filter_documents(docs, Args())
    assert len(filtered) == 1
    assert filtered[0]["document_number"] == "7"


@pytest.mark.parametrize(
    ("command", "command_name"),
    [
        (query_nyscef.cmd_search, "search"),
        (query_nyscef.cmd_case, "case"),
        (query_nyscef.cmd_new_cases, "new-cases"),
    ],
)
def test_challenge_response_is_unavailable_and_never_logged_as_zero(
    command, command_name, tmp_path, monkeypatch, capsys
):
    response = _load_fixture("challenge_response.json")
    logged = []
    monkeypatch.setattr(query_nyscef, "_run_helper", lambda *args, **kwargs: response)
    monkeypatch.setattr(query_nyscef, "log_search", lambda *args: logged.append(args))
    output = tmp_path / f"{command_name}.json"

    command(_search_args(command_name, output))

    artifact = json.loads(output.read_text())
    assert artifact["available"] is False
    assert artifact["source_available"] is False
    assert artifact["status"] == "unavailable"
    assert artifact["challenge_status"] == "challenged"
    assert artifact["reason"] == "captcha_or_anti_bot_challenge"
    assert artifact["results"] == []
    assert logged == []
    assert "results unavailable" in capsys.readouterr().out


def test_genuine_no_results_response_still_logs_zero(
    tmp_path, monkeypatch, capsys
):
    response = _load_fixture("no_results_response.json")
    logged = []
    monkeypatch.setattr(query_nyscef, "_run_helper", lambda *args, **kwargs: response)
    monkeypatch.setattr(query_nyscef, "log_search", lambda *args: logged.append(args))
    output = tmp_path / "no-results.json"

    query_nyscef.cmd_search(_search_args("search", output))

    assert json.loads(output.read_text()) == response
    assert logged == [("NoSuchParty", "nyscef", 0)]
    assert "0 results" in capsys.readouterr().out
