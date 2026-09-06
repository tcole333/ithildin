import json
import sys

from tools import ingest_usvi


def test_search_accepts_output_after_subcommand(monkeypatch, tmp_path, capsys):
    output = tmp_path / "usvi-search.json"
    results = [
        {
            "entity_id": "581737",
            "entity_name": "Example LLC",
            "status": "In Good Standing",
        }
    ]
    monkeypatch.setattr(ingest_usvi, "_make_opener", object)
    monkeypatch.setattr(ingest_usvi, "_fetch", lambda opener, url: "<html></html>")
    monkeypatch.setattr(
        ingest_usvi,
        "_parse_search_results",
        lambda html: (results, 1, None, None),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_usvi.py",
            "search",
            "Example",
            "--output",
            str(output),
        ],
    )

    ingest_usvi.main()

    assert json.loads(output.read_text()) == results
    captured = capsys.readouterr()
    assert "1 results" in captured.out
    assert "Example LLC" not in captured.out


def test_detail_accepts_output_after_subcommand(monkeypatch, tmp_path):
    output = tmp_path / "usvi-detail.json"
    detail = {
        "Entity Identifier": "581737",
        "Entity Name": "Example LLC",
        "Entity Status": "In Good Standing",
    }
    monkeypatch.setattr(ingest_usvi, "search_and_detail", lambda **kwargs: detail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_usvi.py",
            "detail",
            "581737",
            "--name",
            "Example LLC",
            "--output",
            str(output),
        ],
    )

    ingest_usvi.main()

    assert json.loads(output.read_text()) == detail
