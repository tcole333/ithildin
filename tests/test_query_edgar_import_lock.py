from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import sys

from tools import query_edgar


def test_edgartools_import_is_guarded_by_process_lock(monkeypatch):
    events = []
    filing = object()

    @contextmanager
    def fake_lock():
        events.append("lock-enter")
        yield
        events.append("lock-exit")

    class Company:
        def __init__(self, identifier):
            events.append(f"company:{identifier}")

        def get_filings(self, form):
            events.append(f"filings:{form}")
            return [filing]

    monkeypatch.setattr(query_edgar, "_edgartools_import_lock", fake_lock)
    monkeypatch.setattr(
        query_edgar,
        "_configure_edgartools_data_dir",
        lambda: events.append("configure") or "/tmp/edgar",
    )
    monkeypatch.setattr(
        query_edgar,
        "_ensure_edgartools_migration_markers",
        lambda data_dir: events.append(f"markers:{data_dir}"),
    )
    monkeypatch.setitem(sys.modules, "edgar", SimpleNamespace(Company=Company))

    result, _company = query_edgar._get_edgartools_filing(
        "GEO", form="10-K", index=0
    )

    assert result is filing
    assert events == [
        "configure",
        "lock-enter",
        "markers:/tmp/edgar",
        "lock-exit",
        "company:GEO",
        "filings:10-K",
    ]


def test_read_only_default_edgar_cache_uses_writable_temp_root(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("EDGAR_LOCAL_DATA_DIR", raising=False)
    monkeypatch.setattr(query_edgar.os.path, "expanduser", lambda _path: "/read-only/.edgar")
    monkeypatch.setattr(query_edgar.os.path, "isdir", lambda _path: True)
    monkeypatch.setattr(query_edgar.os, "access", lambda *_args: False)
    monkeypatch.setattr(query_edgar.tempfile, "gettempdir", lambda: str(tmp_path))

    configured = query_edgar._configure_edgartools_data_dir()

    assert configured == str(tmp_path / f"ithildin-edgar-data-{query_edgar.os.getuid()}")
    assert query_edgar.os.environ["EDGAR_LOCAL_DATA_DIR"] == configured
    assert (tmp_path / f"ithildin-edgar-data-{query_edgar.os.getuid()}").is_dir()


def test_migration_markers_are_idempotently_restored(tmp_path):
    query_edgar._ensure_edgartools_migration_markers(str(tmp_path))
    query_edgar._ensure_edgartools_migration_markers(str(tmp_path))

    cache_dir = tmp_path / "_tcache"
    assert (cache_dir / ".locale_fix_457_applied").is_file()
    assert (cache_dir / ".empty_response_fix_672_applied").is_file()
