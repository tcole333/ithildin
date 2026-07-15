from __future__ import annotations

import argparse
import json
import sys

import pytest

from tools import ingest_uk_companies_house


@pytest.mark.parametrize(
    ("command", "handler", "arguments"),
    [
        ("search", "cmd_search", ["Example Ltd"]),
        ("company", "cmd_company", ["01234567"]),
        ("officers", "cmd_officers", ["01234567"]),
        ("psc", "cmd_psc", ["01234567"]),
        ("filings", "cmd_filings", ["01234567"]),
        ("officer-search", "cmd_officer_search", ["Example Person"]),
        (
            "officer-appointments",
            "cmd_officer_appointments",
            ["officer-id"],
        ),
        ("insolvency", "cmd_insolvency", ["01234567"]),
    ],
)
def test_read_only_subcommands_accept_standard_output_flag(
    tmp_path, monkeypatch, command, handler, arguments
):
    captured = {}
    output = tmp_path / f"{command}.json"

    def capture(args):
        captured["output"] = args.output

    monkeypatch.setattr(ingest_uk_companies_house, handler, capture)
    monkeypatch.setattr(
        sys,
        "argv",
        ["ingest_uk_companies_house.py", command, *arguments, "--output", str(output)],
    )

    ingest_uk_companies_house.main()

    assert captured["output"] == str(output)


@pytest.mark.parametrize(
    "arguments",
    [
        ["--json", "search", "Example Ltd"],
        ["search", "Example Ltd", "--json"],
    ],
)
def test_json_flag_remains_valid_before_or_after_subcommand(monkeypatch, arguments):
    captured = {}

    def capture(args):
        captured["json_out"] = args.json_out

    monkeypatch.setattr(ingest_uk_companies_house, "cmd_search", capture)
    monkeypatch.setattr(sys, "argv", ["ingest_uk_companies_house.py", *arguments])

    ingest_uk_companies_house.main()

    assert captured["json_out"] is True


def test_officer_search_writes_raw_api_response(tmp_path, monkeypatch, capsys):
    response = {
        "total_results": 1,
        "items": [
            {
                "title": "KARP, Brad S.",
                "appointment_count": 2,
                "links": {"self": "/officers/example/appointments"},
            }
        ],
    }
    monkeypatch.setattr(
        ingest_uk_companies_house,
        "_request",
        lambda path, params=None: response,
    )
    output = tmp_path / "officers.json"

    ingest_uk_companies_house.cmd_officer_search(
        argparse.Namespace(
            name="Brad Karp",
            limit=20,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == response
    stdout = capsys.readouterr().out
    assert "1 results" in stdout
    assert "Found 1 officer records" not in stdout


def test_empty_paginated_result_still_writes_requested_artifact(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(
        ingest_uk_companies_house,
        "_paginate",
        lambda path, max_results: [],
    )
    output = tmp_path / "officers.json"

    ingest_uk_companies_house.cmd_officers(
        argparse.Namespace(
            number="01234567",
            limit=20,
            output=str(output),
            json_out=False,
        )
    )

    assert json.loads(output.read_text()) == []
    stdout = capsys.readouterr().out
    assert "0 results" in stdout
    assert "No officers found" not in stdout


def test_json_mode_is_not_contaminated_by_human_output(monkeypatch, capsys):
    response = {"total_results": 0, "items": []}
    monkeypatch.setattr(
        ingest_uk_companies_house,
        "_request",
        lambda path, params=None: response,
    )

    ingest_uk_companies_house.cmd_search(
        argparse.Namespace(
            query="No Such Company",
            limit=20,
            output=None,
            json_out=True,
        )
    )

    assert json.loads(capsys.readouterr().out) == response
