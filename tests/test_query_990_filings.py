from types import SimpleNamespace

from tools import query_990


def test_filings_accepts_numeric_formtype(monkeypatch, capsys):
    monkeypatch.setattr(
        query_990,
        "_pp_get_org",
        lambda _ein: {
            "filings_with_data": [
                {
                    "tax_prd_yr": 2023,
                    "formtype": 0,
                    "totrevenue": 100,
                    "totfuncexpns": 90,
                    "pdf_url": "https://example.test/filing.pdf",
                }
            ],
            "filings_without_data": [],
        },
    )
    captured = {}
    monkeypatch.setattr(
        query_990,
        "write_output",
        lambda data, _args, summary=None: captured.update(
            {"data": data, "summary": summary}
        ),
    )

    query_990.cmd_filings(SimpleNamespace(ein="03-0213226", output=None))

    assert "2023 (0     )" in capsys.readouterr().out
    assert captured["data"][0]["formtype"] == 0
    assert captured["summary"] == "990 filings for EIN 030213226"
