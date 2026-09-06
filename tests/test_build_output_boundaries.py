from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from pipeline import build_all
from scripts.validate_release import file_manifest, stage_artifact, validate, verify_artifact


@pytest.fixture
def inputs(tmp_path: Path):
    content = tmp_path / "content"
    public = tmp_path / "public"
    build = tmp_path / "dist"
    for root in (content, public, build):
        root.mkdir()
        (root / "fixture.txt").write_text(f"Preserve {root.name}")
    db = tmp_path / "input.db"
    db.write_bytes(b"synthetic")
    return content, public, build, db


@pytest.mark.parametrize("source_index", [0, 1])
@pytest.mark.parametrize("relationship", ["same", "child", "ancestor", "symlink_child"])
def test_candidate_rejects_overlapping_input_before_writes(inputs, tmp_path, monkeypatch, source_index, relationship):
    content, public, _, db = inputs
    source = (content, public)[source_index]
    output = source
    if relationship == "child":
        output = source / "candidate"
    elif relationship == "ancestor":
        output = source.parent
    elif relationship == "symlink_child":
        alias = tmp_path / "input-alias"
        alias.symlink_to(source, target_is_directory=True)
        output = alias / "candidate"
    before = (file_manifest(content), file_manifest(public))
    monkeypatch.setattr(build_all, "export_steps", lambda *args: pytest.fail("Overlap must fail before exporting"))
    with pytest.raises(ValueError, match="must not overlap"):
        build_all.build_candidate(output, source_content=content, source_public=public, db_path=db)
    assert before == (file_manifest(content), file_manifest(public))
    assert not (source / "candidate").exists()


def test_candidate_allows_fresh_sibling_output(inputs, tmp_path, monkeypatch):
    content, public, _, db = inputs
    monkeypatch.setattr(build_all, "export_steps", lambda *args: [])
    output = build_all.build_candidate(tmp_path / "candidate", source_content=content, source_public=public, db_path=db)
    assert (output / "content/fixture.txt").read_bytes() == (content / "fixture.txt").read_bytes()
    assert (output / "public/content/fixture.txt").read_bytes() == (public / "fixture.txt").read_bytes()
    assert json.loads((output / "export-result.json").read_text())["ok"] is True


@pytest.mark.parametrize("source_index", [0, 2])
@pytest.mark.parametrize("relationship", ["same", "child", "ancestor", "symlink_child"])
def test_artifact_rejects_overlapping_input_before_writes(inputs, tmp_path, source_index, relationship):
    content, _, build, _ = inputs
    source = inputs[source_index]
    output = source
    if relationship == "child":
        output = source / "release"
    elif relationship == "ancestor":
        output = source.parent
    elif relationship == "symlink_child":
        alias = tmp_path / "input-alias"
        alias.symlink_to(source, target_is_directory=True)
        output = alias / "release"
    before = (file_manifest(content), file_manifest(build))
    with pytest.raises(ValueError, match="must not overlap"):
        stage_artifact(content, build, output)
    assert before == (file_manifest(content), file_manifest(build))
    assert not (source / "release").exists()


@pytest.mark.parametrize("source_index", [0, 2])
def test_artifact_rejects_symlinked_input_root(inputs, tmp_path, source_index):
    content, _, build, _ = inputs
    alias = tmp_path / "input-alias"
    alias.symlink_to(inputs[source_index], target_is_directory=True)
    output = tmp_path / "artifact"
    with pytest.raises(ValueError, match="symlinks"):
        stage_artifact(alias if source_index == 0 else content, alias if source_index == 2 else build, output)
    assert not output.exists()


@pytest.mark.parametrize("component", ["artifact", "site", "receipt"])
def test_verification_rejects_symlinked_artifact_roots_and_receipt(inputs, tmp_path, component):
    content, _, build, _ = inputs
    artifact = tmp_path / "artifact"
    stage_artifact(content, build, artifact)
    if component == "artifact":
        alias = tmp_path / "artifact-alias"
        alias.symlink_to(artifact, target_is_directory=True)
        artifact = alias
    elif component == "site":
        (artifact / "site").rename(tmp_path / "external-site")
        (artifact / "site").symlink_to(tmp_path / "external-site", target_is_directory=True)
    else:
        receipt = artifact / "release-receipt.json"
        receipt.rename(tmp_path / "external-receipt.json")
        receipt.symlink_to(tmp_path / "external-receipt.json")
    with pytest.raises(ValueError, match="symlinks"):
        verify_artifact(artifact)


def test_validation_rejects_symlinked_content_before_resolving_it(inputs, tmp_path):
    content, _, _, _ = inputs
    alias = tmp_path / "content-alias"
    alias.symlink_to(content, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        validate(Namespace(content_dir=alias))


@pytest.mark.parametrize("payload", [None, [], "invalid", {"schema_version": True, "files_sha256": {}}])
def test_verification_reports_malformed_receipt_as_validation_failure(inputs, tmp_path, payload):
    content, _, build, _ = inputs
    artifact = tmp_path / "artifact"
    stage_artifact(content, build, artifact)
    (artifact / "release-receipt.json").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Unsupported or invalid"):
        verify_artifact(artifact)
