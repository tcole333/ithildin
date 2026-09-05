import hashlib
import json
import subprocess

import pytest

from scripts.repository_hygiene import (
    MAX_BLOB_BYTES,
    check,
    check_commit_message,
    inspect_blob,
)


def run_git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


@pytest.fixture
def repository(tmp_path):
    run_git(tmp_path, "init", "-b", "codex/test")
    run_git(tmp_path, "config", "user.name", "Fixture")
    run_git(tmp_path, "config", "user.email", "fixture@example.invalid")
    return tmp_path


@pytest.mark.parametrize("path", [
    ".env", "nested/.env.production", "datasets/evidence.json", "output/report.md",
    "tools/__pycache__/thing.pyc", "node_modules/example/index.js", "investigation.db-wal",
    "screen.png", "web/dist/index.html",
])
def test_local_artifacts_rejected(path):
    assert any(v.rule == "local-artifact" for v in inspect_blob(path, b"fixture"))


@pytest.mark.parametrize("path", [".env.example", "tests/fixtures/example.db", "design/assets/logo.png", "reports/example/report.md"])
def test_owned_small_assets_and_fixtures_allowed(path):
    assert not inspect_blob(path, b"fixture")


def test_credentials_report_only_path_and_rule():
    token = b"ghp_" + b"a" * 36
    failures = inspect_blob("tools/example.py", token)
    assert [v.rule for v in failures] == ["credential"]
    assert token.decode() not in str(failures)
    private_key = b"-----BEGIN " + b"PRIVATE KEY-----"
    assert inspect_blob("keys.pem", private_key)[0].rule == "credential"


def test_large_exception_is_bound_to_exact_content():
    data = b"x" * (MAX_BLOB_BYTES + 1)
    path = "web/public/source-artifacts/example.pdf"
    assert inspect_blob(path, data)[0].rule == "large-blob"
    exception = {path: {"reason": "Reviewed primary publication artifact", "sha256": hashlib.sha256(data).hexdigest()}}
    assert not inspect_blob(path, data, large_files=exception)
    assert inspect_blob(path, data + b"changed", large_files=exception)[0].rule == "large-blob"


def test_check_reads_index_instead_of_working_tree(repository):
    file_path = repository / "example.py"
    file_path.write_text("safe = True\n")
    run_git(repository, "add", "example.py")
    file_path.write_text("ghp_" + "a" * 36)
    assert check(repository) == []
    run_git(repository, "add", "example.py")
    file_path.write_text("safe = True\n")
    assert [v.rule for v in check(repository)] == ["credential"]


def test_check_reads_staged_policy_not_unstaged_exception(repository):
    folder = repository / "config"
    folder.mkdir()
    policy_file = folder / "repository_policy.json"
    policy_file.write_text('{"large_files": {}}')
    blob = b"x" * (MAX_BLOB_BYTES + 1)
    (repository / "example.data").write_bytes(blob)
    run_git(repository, "add", "config/repository_policy.json", "example.data")
    policy_file.write_text(json.dumps({"large_files": {"example.data": {
        "sha256": hashlib.sha256(blob).hexdigest(), "reason": "Not yet staged",
    }}}))
    assert [v.rule for v in check(repository)] == ["large-blob"]


def test_default_branch_blocks_local_commit_but_ci_can_check_content(repository):
    run_git(repository, "branch", "-m", "main")
    (repository / "example.py").write_text("safe = True\n")
    run_git(repository, "add", "example.py")
    assert [v.rule for v in check(repository)] == ["branch"]
    assert check(repository, check_branch=False) == []


def test_commit_diff_checks_head_blobs_in_detached_ci(repository):
    (repository / "example.py").write_text("safe = True\n")
    run_git(repository, "add", "example.py")
    run_git(repository, "commit", "-m", "test: create safe fixture")
    base = run_git(repository, "rev-parse", "HEAD").decode().strip()
    (repository / ".env").write_text("SECRET=fixture\n")
    run_git(repository, "add", ".env")
    run_git(repository, "commit", "-m", "test: create forbidden fixture")
    failures = check(repository, base=base, check_branch=False)
    assert [(v.path, v.rule) for v in failures] == [(".env", "local-artifact")]


@pytest.mark.parametrize("subject", ["fix(evidence): invalidate changed claims", "research(epstein): preserve court record provenance", "docs: define branch ownership"])
def test_clear_commit_subject_accepted(subject):
    assert check_commit_message(subject + "\n\nValidation: fixture tests passed.\n") is None


@pytest.mark.parametrize("subject", ["wip", "updates", "fix: x", "chore: " + "a" * 101])
def test_vague_or_oversized_commit_subject_rejected(subject):
    assert check_commit_message(subject)
