from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.real_fixture
def test_normalize_dossier_evidence_refs_expands_packed_refs(
    copy_fixture_tree,
    run_python_script,
) -> None:
    dossier_dir = copy_fixture_tree("dossiers")
    dossier_path = dossier_dir / "check-sync.json"

    before = json.loads(dossier_path.read_text())
    before_refs = [row["evidence_ref"] for row in before["findings"][0]["evidence"]]
    assert before_refs == ["EFTA01324981,EFTA01325003"]

    result = run_python_script(
        "pipeline/normalize_dossier_evidence_refs.py",
        "--dossier-dir",
        str(dossier_dir),
        "--target",
        "check-sync",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "normalized check-sync.json" in result.stdout
    assert "done: 1 file(s) updated, 1 evidence block(s) rewritten" in result.stdout

    after = json.loads(dossier_path.read_text())
    refs = [row["evidence_ref"] for row in after["findings"][0]["evidence"]]
    assert refs == ["EFTA01324981", "EFTA01325003"]


@pytest.mark.integration
@pytest.mark.real_fixture
def test_normalize_dossier_evidence_refs_is_idempotent(copy_fixture_tree, run_python_script) -> None:
    dossier_dir = copy_fixture_tree("dossiers")

    first = run_python_script(
        "pipeline/normalize_dossier_evidence_refs.py",
        "--dossier-dir",
        str(dossier_dir),
        "--target",
        "check-sync",
    )
    assert first.returncode == 0, first.stderr or first.stdout

    second = run_python_script(
        "pipeline/normalize_dossier_evidence_refs.py",
        "--dossier-dir",
        str(dossier_dir),
        "--target",
        "check-sync",
    )
    assert second.returncode == 0, second.stderr or second.stdout
    assert "done: 0 file(s) updated, 0 evidence block(s) rewritten" in second.stdout


@pytest.mark.integration
def test_normalize_dossier_evidence_refs_missing_dir_returns_nonzero(
    run_python_script,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-dossiers"

    result = run_python_script(
        "pipeline/normalize_dossier_evidence_refs.py",
        "--dossier-dir",
        str(missing),
    )
    assert result.returncode != 0
    assert "Dossier directory not found" in result.stderr
