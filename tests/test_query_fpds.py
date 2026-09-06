"""Offline fixture tests for the FPDS-NG ATOM wrapper."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools import query_fpds


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "fpds_atom_70CDCR26FR0000014.xml"
)
PIID = "70CDCR26FR0000014"

# One live FPDS page for UEI HHZZRGNWPL44 (SAVVY PROFESSOR LLC), captured
# because it carries both payload roots: the <IDV> base award of the $1.6B UAC
# vehicle and one <award> delivery order placed against it.
IDV_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "fpds_atom_idv_HHZZRGNWPL44.xml"
)
IDV_PIID = "70CDCR26D00000045"
ORDER_PIID = "70CDCR26FR0000096"


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


def test_idv_entries_populate_fields_instead_of_parsing_to_nulls():
    actions, _next_url = query_fpds.parse_atom(IDV_FIXTURE.read_bytes())

    assert [row["record_type"] for row in actions] == ["IDV", "award"]

    vehicle = next(row for row in actions if row["record_type"] == "IDV")
    assert vehicle["piid"] == IDV_PIID
    assert vehicle["agency_id"] == "7012"
    assert vehicle["signed_date"] == "2026-06-02 00:00:00"
    assert vehicle["action_obligation"] == 0.0
    assert vehicle["base_and_all_options_value"] == 1596251500.0
    assert vehicle["vendor_name"] == "SAVVY PROFESSOR LLC"
    assert vehicle["uei"] == "HHZZRGNWPL44"
    assert vehicle["naics_code"] == "561611"
    assert vehicle["product_or_service_code"] == "R799"
    assert vehicle["contract_action_type_description"] == "IDC"
    assert vehicle["createdBy"] == "JCAPPELLO7012"
    assert vehicle["approvedBy"] == "ISOMPPI7012"


def test_idv_omits_award_only_fields_without_aliasing_them():
    actions, _next_url = query_fpds.parse_atom(IDV_FIXTURE.read_bytes())
    vehicle = next(row for row in actions if row["record_type"] == "IDV")

    # An IDV has no parent vehicle and no transaction number, and its
    # lastDateToOrder is not a completion date, so none may be populated.
    assert vehicle["referenced_idv_piid"] is None
    assert vehicle["transaction_number"] is None
    assert vehicle["current_completion_date"] is None
    assert vehicle["ultimate_completion_date"] is None


def test_delivery_order_still_references_its_parent_vehicle():
    actions, _next_url = query_fpds.parse_atom(IDV_FIXTURE.read_bytes())
    order = next(row for row in actions if row["record_type"] == "award")

    assert order["piid"] == ORDER_PIID
    assert order["referenced_idv_piid"] == IDV_PIID
    assert order["action_obligation"] == 4727750.0
    assert order["ultimate_completion_date"] == "2027-06-17 00:00:00"


def test_both_payload_roots_produce_the_same_record_shape():
    actions, _next_url = query_fpds.parse_atom(IDV_FIXTURE.read_bytes())

    assert len({tuple(row) for row in actions}) == 1
    identifying = ("piid", "signed_date", "vendor_name", "uei", "naics_code")
    for row in actions:
        assert all(row[field] is not None for field in identifying), row


def test_award_only_feed_is_tagged_as_award():
    actions, _next_url = query_fpds.parse_atom(FIXTURE.read_bytes())

    assert {row["record_type"] for row in actions} == {"award"}


def test_unrecognized_payload_root_is_flagged_not_silently_nulled():
    xml_text = IDV_FIXTURE.read_text()
    xml_text = xml_text.replace("ns1:IDV", "ns1:futureRoot")

    actions, _next_url = query_fpds.parse_atom(xml_text)

    unknown = next(row for row in actions if row["record_type"] is None)
    assert unknown["piid"] is None
    assert unknown["title"].startswith("New IDC")


def test_idv_from_file_cli_writes_both_records(run_python_script, tmp_path):
    output = tmp_path / "fpds-idv.json"

    completed = run_python_script(
        "tools/query_fpds.py",
        "search",
        'VENDOR_UEI:"HHZZRGNWPL44"',
        "--from-file",
        str(IDV_FIXTURE),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    actions = json.loads(output.read_text())
    assert [row["piid"] for row in actions] == [IDV_PIID, ORDER_PIID]
    assert "2 results" in completed.stdout


def _paging_responses(page_count):
    """Build ``page_count`` pages that each advertise a further next page."""
    pages = []
    for index in range(page_count):
        next_url = f"https://www.fpds.gov/ezsearch/FEEDS/ATOM?start={index + 1}0"
        pages.append(
            FIXTURE.read_text()
            .replace(
                "</title>",
                f'</title><link rel="next" href="{next_url}"/>',
                1,
            )
            .encode()
        )
    return pages


def _stub_feed(monkeypatch, responses):
    monkeypatch.setattr(
        query_fpds, "_fetch_atom_page", lambda url: responses.pop(0)
    )
    monkeypatch.setattr(query_fpds.time, "sleep", lambda seconds: None)


def test_fetch_feed_reports_truncation_when_page_cap_is_hit(monkeypatch):
    _stub_feed(monkeypatch, _paging_responses(2))

    result = query_fpds.fetch_feed("PIID:TEST", max_pages=2)

    assert result.truncated is True
    assert result.pages_fetched == 2
    assert result.next_url is not None
    assert len(result.actions) == 4


def test_fetch_feed_reports_complete_when_feed_ends(monkeypatch):
    _stub_feed(monkeypatch, [*_paging_responses(1), FIXTURE.read_bytes()])

    result = query_fpds.fetch_feed("PIID:TEST", max_pages=5)

    assert result.truncated is False
    assert result.next_url is None
    assert result.pages_fetched == 2


def test_fetch_actions_keeps_returning_a_plain_list(monkeypatch):
    _stub_feed(monkeypatch, [FIXTURE.read_bytes()])

    actions = query_fpds.fetch_actions("PIID:TEST", max_pages=1)

    assert isinstance(actions, list)
    assert len(actions) == 2


def test_cli_warns_and_exits_nonzero_when_results_are_truncated(
    monkeypatch, capsys, tmp_path
):
    output = tmp_path / "truncated.json"
    _stub_feed(monkeypatch, _paging_responses(1))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_fpds.py",
            "search",
            'VENDOR_UEI:"TEST"',
            "--max-pages",
            "1",
            "--with-metadata",
            "--output",
            str(output),
        ],
    )

    exit_code = query_fpds.main()

    assert exit_code == query_fpds.EXIT_TRUNCATED
    assert "--max-pages" in capsys.readouterr().err
    payload = json.loads(output.read_text())
    assert payload["truncated"] is True
    assert payload["pages_fetched"] == 1
    assert payload["next_url"] is not None
    assert len(payload["actions"]) == 2


def test_metadata_wrapper_marks_complete_results_from_file(
    run_python_script, tmp_path
):
    output = tmp_path / "wrapped.json"

    completed = run_python_script(
        "tools/query_fpds.py",
        "piid",
        PIID,
        "--from-file",
        str(FIXTURE),
        "--with-metadata",
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text())
    assert payload["truncated"] is False
    assert payload["next_url"] is None
    assert payload["record_count"] == 2
    assert payload["source"] == str(FIXTURE)
    assert "2 results" in completed.stdout
