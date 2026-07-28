import json
import sys

from tools import ingest_newyork


def test_search_accepts_output_and_suppresses_human_rows(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "new-york.json"
    monkeypatch.setattr(
        ingest_newyork,
        "_soda_request",
        lambda *_args, **_kwargs: [
            {
                "dos_id": "1234567",
                "current_entity_name": "NEXT JUMP INC.",
                "current_status": "ACTIVE",
            }
        ],
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ingest_newyork.py",
            "search",
            "NEXT JUMP",
            "--output",
            str(output),
        ],
    )

    ingest_newyork.main()

    assert json.loads(output.read_text())[0]["dos_id"] == "1234567"
    stdout = capsys.readouterr().out
    assert "saved to" in stdout
    assert "[NY]" not in stdout
