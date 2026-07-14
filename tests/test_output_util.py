import json
from argparse import Namespace

import pytest

from tools.output_util import substantive_result_count, write_output


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"registrants": [], "foreign_principals": []}, 0),
        ({"registrants": [{"id": 1}], "foreign_principals": [{"id": 2}]}, 2),
        ({"query": "missing", "entities": [], "exclusions": []}, 0),
        ({"grants": [{"id": 1}], "related_orgs": [{"id": 2}, {"id": 3}]}, 3),
        ({"hits": {"total": {"value": 0}, "hits": []}}, 0),
        ({"hits": {"total": {"value": 2}, "hits": [{}, {}]}}, 2),
    ],
)
def test_substantive_result_count_for_source_wrappers(payload, expected):
    assert substantive_result_count(payload) == expected


def test_substantive_result_count_preserves_single_resource_dicts():
    assert substantive_result_count({"uei": "ABC123", "legal_business_name": "Example"}) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"available": False, "results": []},
        {"status": "unavailable", "results": []},
        {"error": "source timed out", "results": []},
    ],
)
def test_substantive_result_count_marks_source_unavailable(payload):
    assert substantive_result_count(payload) is None


def test_write_output_reports_clean_zero_and_preserves_payload(tmp_path, capsys):
    payload = {"registrants": [], "foreign_principals": []}
    output_path = tmp_path / "fara.json"

    assert write_output(payload, Namespace(output=str(output_path)), summary="FARA search")

    assert capsys.readouterr().out == (
        f"0 results (FARA search) saved to {output_path}\n"
    )
    assert json.loads(output_path.read_text()) == payload


def test_write_output_distinguishes_unavailable_source(tmp_path, capsys):
    output_path = tmp_path / "unavailable.json"

    assert write_output(
        {"available": False, "results": []},
        Namespace(output=str(output_path)),
        summary="remote source",
    )

    assert capsys.readouterr().out == (
        f"results unavailable (remote source) saved to {output_path}\n"
    )
