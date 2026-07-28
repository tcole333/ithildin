"""Offline fixture tests for the FPDS-NG ATOM wrapper."""

from __future__ import annotations

import json
from pathlib import Path

from tools import query_fpds


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "fpds_atom_70CDCR26FR0000014.xml"
)
PIID = "70CDCR26FR0000014"


def test_fixture_extracts_workflow_fields_and_enumerates_modifications():
    actions, next_url = query_fpds.parse_atom(FIXTURE.read_bytes())

    assert next_url is None
    assert [row["modification_number"] for row in actions] == [
        "0",
        "P00001",
    ]

    base = next(row for row in actions if row["modification_number"] == "0")
    assert base["piid"] == PIID
    assert base["action_obligation"] == 348000.0
    assert base["createdBy"] == "JABYAD7012"
    assert base["lastModifiedBy"] == "JABYAD7012"
    assert base["approvedBy"] == "JABYAD7012"
    assert base["description"] == (
        "SKIP TRACING SERVICES TASK ORDER 5,000 CASES 90 DAY POP"
    )

    extension = next(
        row
        for row in actions
        if row["modification_number"] == "P00001"
    )
    assert extension["action_obligation"] == 0.0
    assert extension["createdBy"] == "JBOUDREAUX7012"
    assert extension["approvedBy"] == "SWRAY7012"


def test_parser_tolerates_changed_fpds_namespace_prefix():
    xml_text = FIXTURE.read_text()
    xml_text = xml_text.replace("xmlns:ns1", "xmlns:ns2")
    xml_text = xml_text.replace("<ns1:", "<ns2:")
    xml_text = xml_text.replace("</ns1:", "</ns2:")

    actions, _next_url = query_fpds.parse_atom(xml_text)

    assert len(actions) == 2
    assert actions[0]["createdBy"] == "JABYAD7012"
    assert actions[1]["modification_number"] == "P00001"


def test_live_path_follows_atom_next_link_with_page_delay(monkeypatch):
    next_url = "https://www.fpds.gov/ezsearch/FEEDS/ATOM?start=10"
    first_page = FIXTURE.read_text().replace(
        "</title>",
        f'</title><link rel="next" href="{next_url}"/>',
        1,
    )
    responses = [first_page.encode(), FIXTURE.read_bytes()]
    requested_urls = []
    sleeps = []

    def fake_fetch(url):
        requested_urls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(query_fpds, "_fetch_atom_page", fake_fetch)
    monkeypatch.setattr(
        query_fpds.time, "sleep", lambda seconds: sleeps.append(seconds)
    )

    actions = query_fpds.fetch_actions("PIID:TEST", max_pages=2)

    assert len(actions) == 4
    assert requested_urls[1] == next_url
    assert sleeps == [1]


def test_piid_from_file_cli_writes_structured_json(
    run_python_script, tmp_path
):
    output = tmp_path / "fpds-actions.json"

    completed = run_python_script(
        "tools/query_fpds.py",
        "piid",
        PIID,
        "--from-file",
        str(FIXTURE),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    actions = json.loads(output.read_text())
    assert len(actions) == 2
    assert actions[0]["createdBy"] == "JABYAD7012"
    assert actions[1]["modification_number"] == "P00001"
    assert "2 results" in completed.stdout


def test_search_from_file_cli_renders_workflow_table(run_python_script):
    completed = run_python_script(
        "tools/query_fpds.py",
        "search",
        f'PIID:"{PIID}"',
        "--from-file",
        str(FIXTURE),
    )

    assert completed.returncode == 0, completed.stderr
    assert "ACTION OBLIGATION" in completed.stdout
    assert "JABYAD7012" in completed.stdout
    assert "P00001" in completed.stdout
