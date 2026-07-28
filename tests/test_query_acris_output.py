import json

from tools import query_acris
from tools.public_records_contract import PublicRecordsResult


def test_zero_result_party_search_writes_requested_envelope(tmp_path, monkeypatch):
    output = tmp_path / "acris-empty.json"
    args = query_acris.build_parser().parse_args(
        [
            "party",
            "MERKIN EZRA",
            "--exact",
            "--output",
            str(output),
        ]
    )
    query = query_acris.build_query(
        "party",
        {"name": "MERKIN EZRA", "exact_only": True},
        borough=None,
        requested_limit=100,
        cursor=None,
    )
    monkeypatch.setattr(
        query_acris,
        "execute",
        lambda _args: PublicRecordsResult.success(query, []),
    )

    query_acris.cmd_party(args)

    data = json.loads(output.read_text())
    assert data["status"] == "no_results"
    assert data["records"] == []
    assert data["errors"] == []


def test_history_output_suppresses_full_transaction_and_warning_text(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "acris-history.json"
    args = query_acris.build_parser().parse_args(
        [
            "history",
            "--borough",
            "1",
            "--block",
            "1124",
            "--lot",
            "27",
            "--output",
            str(output),
        ]
    )
    query = query_acris.build_query(
        "history",
        {"borough": "1", "block": "1124", "lot": "27"},
        borough="1",
        requested_limit=50,
        cursor=None,
    )
    result = PublicRecordsResult.success(
        query,
        [{"document_id": "2024001", "master": {"doc_type": "DEED"}}],
        warnings=["upstream result set was truncated"],
    )
    monkeypatch.setattr(query_acris, "execute", lambda _args: result)

    query_acris.cmd_history(args)

    data = json.loads(output.read_text())
    captured = capsys.readouterr()
    assert data["records"][0]["document_id"] == "2024001"
    assert captured.out.count("\n") == 1
    assert "saved to" in captured.out
    assert "Document:" not in captured.out
    assert captured.err == ""
