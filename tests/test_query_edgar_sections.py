from __future__ import annotations

import argparse
import json
import sys

import pytest

from tools import query_edgar


class _Filing:
    form = "10-K"
    filing_date = "2026-03-01"
    accession_no = "0000000000-26-000001"
    homepage_url = "https://www.sec.gov/Archives/edgar/data/1/2/"

    def __init__(self, obj, text="complete fallback text"):
        self._obj = obj
        self._text = text

    def obj(self):
        if isinstance(self._obj, Exception):
            raise self._obj
        return self._obj

    def text(self):
        return self._text


class _Sections:
    business = "Business line one\nBusiness line two\nBusiness line three"


class _CurrentLegalSections:
    part_i_item_3 = "Current Item 3 legal proceedings"


def _args(output, section="business"):
    return argparse.Namespace(
        ticker="GEO",
        section=section,
        form="10-K",
        index=0,
        lines=1,
        output=str(output),
        json_out=False,
    )


def test_text_section_output_writes_complete_text_without_flooding_stdout(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "business.json"
    monkeypatch.setattr(
        query_edgar,
        "_get_edgartools_filing",
        lambda *_args, **_kwargs: (_Filing(_Sections()), type("Company", (), {"name": "GEO"})()),
    )

    query_edgar.cmd_sections(_args(output))

    payload = json.loads(output.read_text())
    assert payload["retrieval"] == "edgartools-section"
    assert payload["text"] == _Sections.business
    assert "Business line" not in capsys.readouterr().out


def test_section_parse_fallback_honors_output(tmp_path, monkeypatch):
    output = tmp_path / "fallback.json"
    monkeypatch.setattr(
        query_edgar,
        "_get_edgartools_filing",
        lambda *_args, **_kwargs: (
            _Filing(ValueError("cannot parse"), text="full filing\nlate line"),
            type("Company", (), {"name": "GEO"})(),
        ),
    )

    query_edgar.cmd_sections(_args(output))

    payload = json.loads(output.read_text())
    assert payload["retrieval"] == "edgartools-full-text-fallback"
    assert payload["text"] == "full filing\nlate line"


def test_legal_alias_uses_current_part_i_item_3_attribute(tmp_path, monkeypatch):
    output = tmp_path / "legal.json"
    monkeypatch.setattr(
        query_edgar,
        "_get_edgartools_filing",
        lambda *_args, **_kwargs: (
            _Filing(_CurrentLegalSections()),
            type("Company", (), {"name": "GEO"})(),
        ),
    )

    query_edgar.cmd_sections(_args(output, section="legal"))

    payload = json.loads(output.read_text())
    assert payload["retrieval"] == "edgartools-section"
    assert payload["text"] == _CurrentLegalSections.part_i_item_3


def test_sections_cli_exits_nonzero_without_output_after_initial_retrieval_failure(
    tmp_path, monkeypatch
):
    output = tmp_path / "sections.json"

    def fail_retrieval(*_args, **_kwargs):
        raise RuntimeError("retrieval unavailable")

    monkeypatch.setattr(query_edgar, "_get_edgartools_filing", fail_retrieval)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_edgar.py",
            "sections",
            "GEO",
            "--section",
            "business",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        query_edgar.main()

    assert exc.value.code == 2
    assert not output.exists()
