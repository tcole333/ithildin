"""CLI help checks must follow the selected nested command, not its siblings."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import pytest

from scripts import validate_skills as validator


@pytest.fixture
def contract_calls(monkeypatch):
    original = validator.inspect_contract
    calls = []

    def inspect(path):
        calls.append(path)
        return original(path)

    def forbidden(*args, **kwargs):
        pytest.fail('declaration checks must never execute runtime help')

    monkeypatch.setattr(validator, 'inspect_contract', inspect)
    monkeypatch.setattr(subprocess, "run", forbidden)
    return calls


@pytest.fixture
def command_workspace(tmp_path):
    script = tmp_path / "tools" / "query_fixture.py"
    script.parent.mkdir()
    script.write_text(
        """import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--root-option')
commands = parser.add_subparsers(dest='command', required=True)
document = commands.add_parser('document')
document.add_argument('--parent-option')
kinds = document.add_subparsers(dest='kind', required=True)
card = kinds.add_parser('appraisal-card')
card.add_argument('account')
card.add_argument('year')
card.add_argument('--destination')
card.add_argument('--output')
receipt = kinds.add_parser('tax-receipt')
receipt.add_argument('--tax-only')
export = kinds.add_parser('export')
formats = export.add_subparsers(dest='format', required=True)
csv = formats.add_parser('csv')
csv.add_argument('--delimiter')
parser.parse_args()
raise RuntimeError('help validation must never execute a source command')
""",
        encoding="utf-8",
    )
    return tmp_path


def lint_commands(workspace, doc_path, commands, cache=None):
    doc_path.write_text("```bash\n" + "\n".join(commands) + "\n```\n", encoding="utf-8")
    return validator.lint_markdown_file(
        doc_path,
        workspace=workspace,
        require_uv=False,
        include_hidden=False,
        help_cache={} if cache is None else cache,
        required_frontmatter_fields=None,
    )


def test_selected_nested_command_flags_and_help_cache(command_workspace, contract_calls):
    command = (
        "uv run python tools/query_fixture.py document appraisal-card 61623 2026 "
        "--destination /tmp/card.pdf --output /tmp/card.json"
    )
    cache = {}
    for index in range(2):
        assert lint_commands(
            command_workspace, command_workspace / f"example-{index}.md", [command], cache,
        ) == []

    assert contract_calls == [command_workspace / 'tools/query_fixture.py']
    paths = {key[1] for key in cache if isinstance(key[1], tuple)}
    assert paths == {(), ("document",), ("document", "appraisal-card")}


def test_nested_sibling_flags_and_misspellings_still_fail(command_workspace, contract_calls):
    commands = [
        "uv run python tools/query_fixture.py document tax-receipt --tax-only paid",
        "uv run python tools/query_fixture.py document appraisal-card tax-receipt 2026 "
        "--tax-only paid --destinaton /tmp/card.pdf",
    ]
    cache = {}
    issues = lint_commands(command_workspace, command_workspace / "examples.md", commands, cache)

    assert len(issues) == 2
    assert all(issue.level == "WARN" for issue in issues)
    assert any("`--tax-only`" in issue.message for issue in issues)
    assert any("`--destinaton`" in issue.message for issue in issues)
    assert all("subcommand `document appraisal-card`" in issue.message for issue in issues)
    assert ('tools/query_fixture.py', ("document", "appraisal-card", "tax-receipt")) not in cache


def test_declared_commands_can_be_nested_more_than_two_levels(command_workspace, contract_calls):
    cache = {}
    assert lint_commands(
        command_workspace,
        command_workspace / "example.md",
        ["uv run python tools/query_fixture.py document export csv --delimiter ','"],
        cache,
    ) == []
    assert ('tools/query_fixture.py', ("document", "export", "csv")) in cache


def test_current_lincoln_and_florida_examples_match_the_real_cli(tmp_path, contract_calls):
    workspace = Path(__file__).resolve().parents[1]
    text = (workspace / "docs" / "TOOL_REFERENCE.md").read_text(encoding="utf-8")
    prefixes = (
        "uv run python tools/query_oregon_lincoln_propertyweb.py document ",
        "uv run python tools/ingest_fl_dor_property.py ingest ",
    )
    commands = [
        line.strip()
        for line, _ in validator.join_line_continuations(text)
        if line.strip().startswith(prefixes)
    ]
    assert all(any(command.startswith(prefix) for command in commands) for prefix in prefixes)
    assert lint_commands(workspace, tmp_path / "current-examples.md", commands) == []

    for command in commands:
        if command.startswith(prefixes[1]):
            # Parsing this reconstructed standard-library parser cannot invoke
            # application imports, action callbacks, or source commands.
            contract = validator.inspect_contract(workspace / 'tools/ingest_fl_dor_property.py')
            assert not contract.limitations
            parsed = contract.parser.parse_args(shlex.split(command)[4:])
            assert parsed.dataset_type == "nal"
            assert str(parsed.archive).endswith("/fl-baker-nal.zip")
