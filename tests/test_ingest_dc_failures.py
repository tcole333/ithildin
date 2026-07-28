import argparse

import pytest

from tools import ingest_dc


def test_arcgis_query_distinguishes_source_failure_from_no_results(monkeypatch):
    monkeypatch.setattr(ingest_dc, "_fetch_json", lambda *_args, **_kwargs: None)

    with pytest.raises(ingest_dc.DCSourceUnavailable):
        ingest_dc.arcgis_query("BUSINESS_NAME LIKE '%TEST%'")


def test_search_failure_is_nonzero_and_is_not_logged_or_written(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "results.json"
    logged = []
    written = []

    def unavailable(*_args, **_kwargs):
        raise ingest_dc.DCSourceUnavailable("temporary DNS failure")

    monkeypatch.setattr(ingest_dc, "search_by_name", unavailable)
    monkeypatch.setattr(ingest_dc, "log_search", lambda *args: logged.append(args))
    monkeypatch.setattr(
        ingest_dc,
        "write_output",
        lambda *args, **kwargs: written.append((args, kwargs)),
    )
    args = argparse.Namespace(
        query="Example",
        type=None,
        status=None,
        limit=10,
        output=str(output),
        json_out=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        ingest_dc.cmd_search(args)

    assert exc_info.value.code == 2
    assert logged == []
    assert written == []
    assert not output.exists()
    assert "not logged as a zero-result query" in capsys.readouterr().err
