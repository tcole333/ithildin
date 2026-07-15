import pytest

from tools import ingest_california


def test_missing_california_api_key_points_to_keyless_paths(monkeypatch, capsys):
    monkeypatch.delenv("CA_SOS_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        ingest_california._get_api_key()

    assert exc_info.value.code == 1
    error = capsys.readouterr().err
    assert "CA SoS API key required" in error
    assert "query_california.py search" in error
    assert "infra request #130" in error
