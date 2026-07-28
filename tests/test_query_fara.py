"""Regression tests for FARA bulk-cache freshness reporting."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from tools import query_fara


def _seed_registrant(db_path, *, status="Active"):
    original_db_path = query_fara.DB_PATH
    query_fara.DB_PATH = db_path
    try:
        db = query_fara._get_db()
        query_fara._create_tables(db)
        db.execute(
            """
            INSERT INTO fara_registrants (
                registration_number, registrant_name, status, raw_data
            ) VALUES (?, ?, ?, ?)
            """,
            ("7459", "Example Registrant", status, "{}"),
        )
        db.commit()
        db.close()
    finally:
        query_fara.DB_PATH = original_db_path


def test_detail_warns_and_saves_provenance_for_stale_active_status(
    monkeypatch, tmp_path, capsys
):
    db_path = tmp_path / "investigation.db"
    data_dir = tmp_path / "fara"
    data_dir.mkdir()
    output = tmp_path / "detail.json"
    _seed_registrant(db_path)

    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    source_path = data_dir / "registrants.csv.zip"
    source_path.write_bytes(b"cached bulk data")
    old_mtime = (now - timedelta(days=30)).timestamp()
    os.utime(source_path, (old_mtime, old_mtime))

    monkeypatch.setattr(query_fara, "DB_PATH", db_path)
    monkeypatch.setattr(query_fara, "DATA_DIR", data_dir)
    monkeypatch.setattr(query_fara, "_utc_now", lambda: now)

    query_fara.cmd_detail(
        SimpleNamespace(
            registration_number="7459",
            output=str(output),
            json_out=False,
        )
    )

    saved = json.loads(output.read_text())
    freshness = saved["dataset_freshness"]["registrants"]
    assert freshness["age_days"] == 30.0
    assert freshness["stale"] is True
    assert freshness["source_file_modified_at"] == "2026-06-28T00:00:00+00:00"
    assert len(saved["warnings"]) == 1
    assert "Local FARA status is Active" in saved["warnings"][0]
    stderr = capsys.readouterr().err
    assert "WARNING: Local FARA status is Active" in stderr
    assert "30.0 days old" in stderr


def test_detail_does_not_warn_for_recent_active_cache(monkeypatch, tmp_path, capsys):
    db_path = tmp_path / "investigation.db"
    data_dir = tmp_path / "fara"
    data_dir.mkdir()
    output = tmp_path / "detail.json"
    _seed_registrant(db_path)

    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    source_path = data_dir / "registrants.csv.zip"
    source_path.write_bytes(b"recent bulk data")
    recent_mtime = (now - timedelta(days=1)).timestamp()
    os.utime(source_path, (recent_mtime, recent_mtime))

    monkeypatch.setattr(query_fara, "DB_PATH", db_path)
    monkeypatch.setattr(query_fara, "DATA_DIR", data_dir)
    monkeypatch.setattr(query_fara, "_utc_now", lambda: now)

    query_fara.cmd_detail(
        SimpleNamespace(
            registration_number="7459",
            output=str(output),
            json_out=False,
        )
    )

    saved = json.loads(output.read_text())
    assert saved["dataset_freshness"]["registrants"]["stale"] is False
    assert saved["warnings"] == []
    assert capsys.readouterr().err == ""
