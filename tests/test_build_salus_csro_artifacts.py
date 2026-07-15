import json
from pathlib import Path

import pytest

from scripts import build_salus_csro_artifacts as builder


def test_relative_source_dir_and_external_report_dir(monkeypatch, tmp_path, capsys):
    source_dir = Path("investigations/geo-group/sources/2026-07-14-lead-62736")
    if not source_dir.is_dir():
        pytest.skip(f"Salus CSRO source archive not available at {source_dir}")

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_salus_csro_artifacts.py",
            "--source-dir",
            str(source_dir),
            "--report-dir",
            str(tmp_path),
        ],
    )
    builder.main()

    output = json.loads(capsys.readouterr().out)
    manifest_path = Path(output["manifest"])
    manifest = json.loads(manifest_path.read_text())
    assert manifest["source_root"] == str(source_dir)
    assert manifest["source_count"] == 93
    assert len(manifest["generated_artifacts"]) == 3
    assert all(Path(item["path"]).parent == tmp_path for item in manifest["generated_artifacts"])
