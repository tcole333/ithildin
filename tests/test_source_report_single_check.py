from tools import public_records_catalog, source_report


def test_muckrock_check_does_not_probe_other_sources(monkeypatch):
    def unexpected_probe(*_args, **_kwargs):
        raise AssertionError("an unrelated source was probed")

    monkeypatch.setattr(source_report, "load_env_file", lambda: None)
    monkeypatch.delenv("MUCKROCK_USERNAME", raising=False)
    monkeypatch.delenv("MUCKROCK_PASSWORD", raising=False)
    monkeypatch.setattr(source_report.sqlite3, "connect", unexpected_probe)
    monkeypatch.setattr("urllib.request.urlopen", unexpected_probe)
    monkeypatch.setattr(
        public_records_catalog,
        "PublicRecordsCatalog",
        unexpected_probe,
    )

    result = source_report.quick_health_check("MuckRock")

    assert result["name"] == "MuckRock FOIA"
    assert result["status"] == "no_credentials"
