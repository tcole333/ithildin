"""Offline fixture tests for the USPTO trademark-register wrapper."""

from __future__ import annotations

import json
from pathlib import Path

from tools import query_trademarks


FIXTURES = Path(__file__).parent / "fixtures"
WORDMARK_FIXTURE = FIXTURES / "uspto_tm_wordmark_hc_standard.json"
OWNER_FIXTURE = FIXTURES / "uspto_tm_owner_global_emergency.json"
ZERO_FIXTURE = FIXTURES / "uspto_tm_zero_hits_data_bulldog.json"


def test_exact_phrase_mark_query_uses_match_phrase_not_loose_match():
    body = query_trademarks.build_query("mark", "HC STANDARD")

    clause = body["query"]["bool"]["must"][0]
    assert clause == {
        "match_phrase": {"WM": {"query": "HC STANDARD"}}
    }
    assert "match" not in clause
    assert body["size"] == 25
    assert body["from"] == 0
    assert body["track_total_hits"] is True


def test_owner_query_phrase_matches_full_owner_block():
    body = query_trademarks.build_query(
        "owner",
        "Global Emergency Resources",
        live_only=True,
        international_class="IC 042",
    )

    assert body["query"]["bool"]["must"] == [
        {
            "match_phrase": {
                "ownerFullText": {
                    "query": "Global Emergency Resources"
                }
            }
        }
    ]
    assert {"term": {"alive": True}} in body["query"]["bool"]["filter"]
    assert {
        "match_phrase": {
            "internationalClass": {"query": "IC 042"}
        }
    } in body["query"]["bool"]["filter"]


def test_parser_reads_source_not_standard_elasticsearch_source():
    payload = json.loads(WORDMARK_FIXTURE.read_text())

    records = query_trademarks.parse_response(payload)

    assert len(records) == 2
    assert records[0]["id"] == "78696538"
    assert records[1]["registrationId"] == "4531966"
    assert "_source" not in payload["hits"]["hits"][0]


def test_multi_owner_record_surfaces_registrant_and_last_listed_owner(
    capsys,
):
    records = query_trademarks.load_records(WORDMARK_FIXTURE)
    transferred = next(
        record for record in records if record["id"] == "85877492"
    )

    owners = query_trademarks.extract_owner_lines(transferred)
    assert any(line.startswith("(REGISTRANT)") for line in owners)
    assert any(
        line.startswith("(LAST LISTED OWNER)") for line in owners
    )

    query_trademarks.print_records([transferred])
    output = capsys.readouterr().out
    assert "(REGISTRANT) Global Emergency Resources, LLC" in output
    assert "(LAST LISTED OWNER) GLOBAL EMERGENCY RESPONSE INC." in output


def test_zero_hit_fixture_renders_cleanly(capsys):
    records = query_trademarks.load_records(ZERO_FIXTURE)

    query_trademarks.print_records(records)

    assert records == []
    assert capsys.readouterr().out == "0 results.\n"


def test_mark_from_file_cli_writes_structured_json(
    run_python_script, tmp_path
):
    output = tmp_path / "trademarks.json"

    completed = run_python_script(
        "tools/query_trademarks.py",
        "mark",
        "HC STANDARD",
        "--from-file",
        str(WORDMARK_FIXTURE),
        "--output",
        str(output),
    )

    assert completed.returncode == 0, completed.stderr
    records = json.loads(output.read_text())
    assert [record["id"] for record in records] == [
        "78696538",
        "85877492",
    ]
    assert "2 results" in completed.stdout


def test_owner_from_file_cli_filters_live_marks_without_network(
    run_python_script,
):
    completed = run_python_script(
        "tools/query_trademarks.py",
        "owner",
        "Global Emergency Resources",
        "--from-file",
        str(OWNER_FIXTURE),
        "--live-only",
        "--class",
        "042",
        "--json",
    )

    assert completed.returncode == 0, completed.stderr
    records = json.loads(completed.stdout)
    assert [record["id"] for record in records] == [
        "85877492",
        "86255449",
    ]
    assert all(record["alive"] is True for record in records)
