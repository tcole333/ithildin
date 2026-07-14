from types import SimpleNamespace

from tools import query_fec


def test_committee_lookup_uses_singular_fec_endpoint(monkeypatch, capsys):
    seen = {}

    def fake_fetch(endpoint, params):
        seen["endpoint"] = endpoint
        return ([{"committee_id": "C00825851", "name": "MAGA INC."}], {})

    monkeypatch.setattr(query_fec, "_fetch", fake_fetch)
    args = SimpleNamespace(
        committee_id="C00825851",
        output=None,
        json_out=False,
    )

    query_fec.cmd_committee(args)

    assert seen["endpoint"] == "/committee/C00825851/"
    assert "MAGA INC." in capsys.readouterr().out


def test_donor_output_still_logs_search(monkeypatch, tmp_path):
    logged = []

    monkeypatch.setattr(
        query_fec,
        "_fetch",
        lambda endpoint, params, max_pages: ([{"sub_id": "1"}], {"count": 7}),
    )
    monkeypatch.setattr(query_fec, "_log", lambda query, source, count: logged.append((query, source, count)))
    args = SimpleNamespace(
        query="Example Donor",
        employer=None,
        min_amount=None,
        max_amount=None,
        cycle=None,
        state=None,
        limit=100,
        output=str(tmp_path / "fec.json"),
        json_out=False,
    )

    query_fec.cmd_donor(args)

    assert logged == [("Example Donor", "fec", 7)]
    assert (tmp_path / "fec.json").exists()
