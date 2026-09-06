from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.validate_release import file_manifest, stage_artifact, verify_artifact


def test_real_release_command_reports_missing_snapshot_before_build(tmp_path):
    content = tmp_path / "content"
    content.mkdir()
    (content / "readme.txt").write_text("Synthetic publication fixture")
    artifact = tmp_path / "artifact"
    result = subprocess.run(
        [sys.executable, "scripts/validate_release.py", "validate", "--content-dir", str(content), "--artifact-dir", str(artifact)],
        cwd=Path(__file__).parents[1], capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 1
    assert "missing_snapshot" in result.stdout
    assert "required: --output" not in result.stderr
    assert not artifact.exists()


def _artifact(tmp_path):
    content = tmp_path / "content"
    build = tmp_path / "dist"
    content.mkdir()
    build.mkdir()
    (content / "dossier.json").write_text('{"reviewed": true}')
    (build / "index.html").write_text("<h1>Reviewed content</h1>")
    artifact = tmp_path / "artifact"
    stage_artifact(content, build, artifact)
    return content, build, artifact


def test_stages_the_built_bytes_with_their_reviewed_content_hashes(tmp_path):
    content, build, artifact = _artifact(tmp_path)
    receipt = verify_artifact(artifact)
    assert receipt["content_sha256"] == file_manifest(content)
    assert receipt["files_sha256"] == file_manifest(build)
    assert (artifact / "site/index.html").read_bytes() == (build / "index.html").read_bytes()


@pytest.mark.parametrize("change", ["edit", "remove", "extra"])
def test_rejects_any_artifact_change_after_validation(tmp_path, change):
    _, _, artifact = _artifact(tmp_path)
    if change == "edit":
        (artifact / "site/index.html").write_text("unreviewed")
    elif change == "remove":
        (artifact / "site/index.html").unlink()
    else:
        (artifact / "site/new.html").write_text("unreviewed")
    with pytest.raises(ValueError):
        verify_artifact(artifact)


def test_rejects_symlinked_build_inputs_and_existing_output(tmp_path):
    content, build, artifact = _artifact(tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        stage_artifact(content, build, artifact)
    (build / "linked").symlink_to(content / "dossier.json")
    with pytest.raises(ValueError, match="symlinks"):
        stage_artifact(content, build, tmp_path / "another")


def test_rejects_unknown_receipt_format(tmp_path):
    _, _, artifact = _artifact(tmp_path)
    (artifact / "release-receipt.json").write_text(json.dumps({"schema_version": 99}))
    with pytest.raises(ValueError, match="Unsupported"):
        verify_artifact(artifact)
