import json
import sys

from tools import query_lmsband


def test_file_subcommand_writes_structured_output(tmp_path, monkeypatch):
    output = tmp_path / "file.json"
    monkeypatch.setattr(
        query_lmsband,
        "get_file",
        lambda _file_id: {
            "id": 104733,
            "filename": "example.eml",
            "text": {
                "char_count": 12,
                "method": "parsed",
                "extracted_text": "private body",
            },
            "entities": [],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "query_lmsband.py",
            "file",
            "104733",
            "--output",
            str(output),
        ],
    )

    query_lmsband.main()

    payload = json.loads(output.read_text())
    assert payload["id"] == 104733
    assert "extracted_text" not in payload["text"]
