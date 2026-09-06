"""Behavioral contracts for skill metadata, help checking, parity and discovery."""
from __future__ import annotations


import pytest

from scripts.audit_codex_skill_parity import audit
from scripts.skill_distribution import backup, check, inventory, tree_manifest
from pathlib import Path

from scripts.skill_metadata import normalized_runtime_text, runtime_for_path
from scripts.validate_skills import lint_markdown_file, main, read_help_options, split_segments, validate_skill_frontmatter


def skill(root, name='sample', body='Read the evidence.', runtime='.claude', metadata='user-invocable: true'):
    path = root / runtime / 'skills' / name / 'SKILL.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'---\nname: {name}\ndescription: Review evidence\n{metadata}\n---\n{body}\n')
    return path


@pytest.mark.parametrize('metadata', [
    'user-invocable: false\ndisable-model-invocation: true',
    'context: fork\nagent: Explore\nbackground: false\nmodel: inherit',
    'allowed-tools: [Read, Grep]\ndisallowed-tools: Bash\narguments: [target]\npaths: ["src/**"]',
    'when_to_use: Review source evidence\nargument-hint: "[target]"\neffort: high\nshell: bash\nhooks: {}',
])
def test_current_claude_metadata(metadata):
    text = f'---\nname: sample\ndescription: Review evidence\n{metadata}\n---\n'
    assert validate_skill_frontmatter(text, 'claude') == []


def test_runtime_fields_do_not_leak_into_codex():
    text = '---\nname: sample\ndescription: Review\ncontext: fork\n---\n'
    assert any('context' in error for error in validate_skill_frontmatter(text, 'codex'))
    assert any('user_invocable' in error for error in validate_skill_frontmatter(text.replace('context: fork', 'user_invocable: true'), 'claude'))


def test_uninspectable_help_is_visible_without_execution(tmp_path):
    marker = tmp_path / 'import-ran'
    script = tmp_path / 'broken.py'
    script.write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise ImportError("fixture")\n')
    result = read_help_options(tmp_path, 'broken.py', None, {})
    assert result.error and 'not executed' in result.error
    assert not marker.exists()


def test_help_checks_do_not_execute_documented_action(tmp_path):
    script = tmp_path / 'cli.py'
    marker = tmp_path / 'action-ran'
    script.write_text('import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser()\np.add_argument("--profile")\ns=p.add_subparsers(dest="command", required=True)\na=s.add_parser("search")\na.add_argument("--limit", type=int)\np.parse_args()\n' + f'Path({str(marker)!r}).touch()\n')
    md = skill(tmp_path, body='```bash\nuv run python cli.py --profile profile-a nonexistent\n```')
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert any('Invalid subcommand `nonexistent`' in issue.message for issue in issues)
    assert not marker.exists()
    md.write_text(md.read_text().replace('nonexistent', 'search --bad-flag'))
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert any('invalid flag `--bad-flag`' in issue.message for issue in issues)
    assert not marker.exists()


def test_failed_help_is_a_lint_issue(tmp_path):
    (tmp_path / 'broken.py').write_text('raise ImportError("fixture")\n')
    md = skill(tmp_path, body='```bash\nuv run python broken.py --bad-flag\n```')
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert any('No statically inspectable argparse contract' in issue.message for issue in issues)


def test_missing_requested_root_fails_strict(tmp_path):
    assert main(['--workspace', str(tmp_path), '--skills-dir', str(tmp_path / 'missing'), '--strict']) == 1


def test_parity_normalizes_runtime_but_preserves_evidence_changes(tmp_path):
    left = skill(tmp_path, body='# /sample\nRead CLAUDE.md. Preserve quotations.')
    right = skill(tmp_path, runtime='.codex', metadata='', body='# $sample\nRead AGENTS.md. Preserve quotations.')
    assert normalized_runtime_text(left.read_text(), {'sample'}) == normalized_runtime_text(right.read_text(), {'sample'})
    assert audit(tmp_path) == 0
    right.write_text(right.read_text().replace('Preserve quotations.', 'Discard quotations.'))
    assert audit(tmp_path) == 1


def test_parity_checks_bundled_references(tmp_path):
    skill(tmp_path)
    path = skill(tmp_path, runtime='.codex', metadata='')
    (path.parent / 'references').mkdir()
    (path.parent / 'references/policy.md').write_text('Evidence requirement')
    assert audit(tmp_path) == 1


def test_project_discovery_link(tmp_path):
    skill(tmp_path, runtime='.codex', metadata='')
    assert check(tmp_path)['status'] == 'error'
    (tmp_path / '.agents').mkdir()
    (tmp_path / '.agents/skills').symlink_to('../.codex/skills')
    assert check(tmp_path)['status'] == 'ok'


def test_inventory_and_backup_preserve_edited_and_unrelated_files(tmp_path):
    repo = tmp_path / 'repo'
    skill(repo, runtime='.codex', metadata='')
    personal = tmp_path / 'personal'
    edited = personal / 'sample'
    edited.mkdir(parents=True)
    (edited / 'SKILL.md').write_text('my edited skill')
    (edited / 'pointer').symlink_to('/unrelated/target')
    unrelated = personal / 'unrelated'
    unrelated.mkdir()
    (unrelated / 'SKILL.md').write_text('unrelated skill')
    before = tree_manifest(personal)
    report = inventory(repo, personal)
    assert report['collisions'][0]['status'] == 'different_preserve'
    assert report['unrelated_preserved'] == ['unrelated']
    destination = tmp_path / 'backup'
    assert backup(repo, personal, destination)['status'] == 'backed_up_originals_preserved'
    assert tree_manifest(personal) == before
    assert tree_manifest(destination / 'sample') == tree_manifest(edited)
    assert not (destination / 'unrelated').exists()
    with pytest.raises(FileExistsError):
        backup(repo, personal, destination)
    with pytest.raises(ValueError, match='outside'):
        backup(repo, personal, personal / 'backup')


def test_runtime_detection_inside_claude_worktree():
    assert runtime_for_path(Path('/repo/.claude/worktrees/task/.codex/skills/example/SKILL.md')) == 'codex'
    assert runtime_for_path(Path('/repo/.claude/worktrees/task/.claude/skills/example/SKILL.md')) == 'claude'


def test_shell_segmentation_preserves_quoted_evidence():
    import shlex
    segments = split_segments('uv run python tool.py --quote "A; B | C" && uv run python second.py')
    assert len(segments) == 2
    assert shlex.split(segments[0])[-1] == 'A; B | C'


def test_reference_commands_are_checked(tmp_path):
    path = skill(tmp_path)
    references = path.parent / 'references'
    references.mkdir()
    (references / 'commands.md').write_text('```bash\nuv run python missing.py search\n```')
    assert main(['--workspace', str(tmp_path), '--skills-dir', str(tmp_path / '.claude/skills')]) == 1


def test_wrapper_terminator_separates_child_flags(tmp_path):
    (tmp_path / 'wrapper.py').write_text('import argparse\np=argparse.ArgumentParser()\ns=p.add_subparsers()\nr=s.add_parser("run")\nr.add_argument("--profile")\nr.add_argument("command",nargs=argparse.REMAINDER)\np.parse_args()\n')
    (tmp_path / 'child.py').write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("--limit")\np.parse_args()\n')
    md = skill(tmp_path, body='```bash\nuv run python wrapper.py run --profile sample -- uv run python child.py --limit 5\n```')
    assert lint_markdown_file(md, tmp_path, True, False, {}, None, True) == []
    md.write_text(md.read_text().replace('--limit 5', '--bad-flag'))
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert any('invalid flag `--bad-flag` for `child.py`' in issue.message for issue in issues)
    assert not any('invalid flag' in issue.message and 'wrapper.py' in issue.message for issue in issues)


def test_cli_imports_and_custom_types_never_execute(tmp_path):
    marker = tmp_path / 'import-or-type-ran'
    (tmp_path / 'cli.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\nimport argparse\ndef unsafe_type(value):\n    Path({str(marker)!r}).touch()\n    return value\ndef main():\n    p=argparse.ArgumentParser()\n    p.add_argument("--number",type=unsafe_type)\n    p.parse_args()\n')
    md = skill(tmp_path, body='```bash\nuv run python cli.py --number 5\n```')
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert issues == []
    from scripts.cli_contract import inspect_contract
    contract = inspect_contract(tmp_path / 'cli.py')
    assert not contract.limitations
    assert any('dynamic type' in note for note in contract.value_constraints)
    assert not marker.exists()


def test_literal_import_choices_do_not_run_module(tmp_path):
    marker = tmp_path / 'import-ran'
    (tmp_path / 'constants.py').write_text(f'from pathlib import Path\nPath({str(marker)!r}).touch()\nCHOICES = ["a", "b"]\n')
    (tmp_path / 'cli.py').write_text('import argparse\nfrom constants import CHOICES\np=argparse.ArgumentParser()\np.add_argument("--choice",choices=CHOICES)\np.parse_args()\n')
    result = read_help_options(tmp_path, 'cli.py', None, {})
    assert result.error is None
    assert '--choice' in result.options
    assert not marker.exists()


def test_multiline_error_has_original_line_number(tmp_path):
    body = '# Intro\n\n```bash\nuv run python missing.py \\\n  --output results.json\n```'
    md = skill(tmp_path, body=body)
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    expected = next(i for i, line in enumerate(md.read_text().splitlines(), 1) if line.startswith('uv run'))
    assert issues[0].line == expected


@pytest.mark.parametrize('language', ['json', 'yaml', 'yml'])
def test_runtime_normalization_preserves_fenced_routing_data(language):
    body = f'# /sample\n```{language}\n{{"recommended_skill": "/sample"}}\n```\n'
    normalized = normalized_runtime_text(body, {'sample'})
    assert normalized.startswith('# $sample')
    assert '"recommended_skill": "/sample"' in normalized
    assert normalized != normalized_runtime_text(body.replace('"/sample"', '"$sample"'), {'sample'})


def test_snapshot_treats_fenced_routing_ids_as_data(tmp_path):
    import runpy
    root = Path(__file__).resolve().parents[1]
    snapshot = runpy.run_path(str(root / '.codex/skills/audit-skills/scripts/snapshot_skills.py'))
    md = skill(tmp_path, runtime='.codex', metadata='', body='# $sample\n```json\n{"recommended_skill": "/sample"}\n```')
    issues = []
    snapshot['inspect_variant'](md.parent, md.parent.parent, tmp_path, {'sample'}, issues)
    assert not any('invocation' in item['message'] for item in issues)


@pytest.mark.parametrize('statement', [
    'try:\n    p.add_argument("--needed")\nexcept Exception:\n    pass\n',
    'with unknown_context():\n    p.add_argument("--needed")\n',
])
def test_unsupported_control_flow_never_claims_complete_contract(tmp_path, statement):
    from tools.tool_catalog import declarations
    script = tmp_path / 'cli.py'
    script.write_text('import argparse\np=argparse.ArgumentParser()\n' + statement + 'p.parse_args()\n')
    result = read_help_options(tmp_path, 'cli.py', None, {})
    assert result.error and 'unsupported declaration statement' in result.error
    assert declarations(script, None)['inspection'] == 'partial'


def test_argparse_actions_not_help_prose_define_contract(tmp_path):
    (tmp_path / 'cli.py').write_text('import argparse\np=argparse.ArgumentParser()\np.add_argument("format",choices=["json","csv"],help="Use --child-only in another tool")\np.parse_args()\n')
    result = read_help_options(tmp_path, 'cli.py', None, {})
    assert result.error is None
    assert '--child-only' not in result.options
    assert result.subcommands == set()
    md = skill(tmp_path, body='```bash\nuv run python cli.py csv --child-only\n```')
    issues = lint_markdown_file(md, tmp_path, True, False, {}, None, True)
    assert any('invalid flag `--child-only`' in issue.message for issue in issues)
    assert not any('Invalid subcommand' in issue.message for issue in issues)


def test_distribution_report_cannot_overwrite_sources_or_aliases(tmp_path):
    from scripts.skill_distribution import validate_output_destination
    repo = tmp_path / 'repo'
    managed = skill(repo, runtime='.codex', metadata='')
    personal = tmp_path / 'personal'
    original = personal / 'sample/SKILL.md'
    original.parent.mkdir(parents=True)
    original.write_text('personal edits')
    symbolic = tmp_path / 'symbolic'
    symbolic.symlink_to(original)
    hardlink = tmp_path / 'hardlink'
    hardlink.hardlink_to(original)
    for output in [original, managed, symbolic, hardlink, personal / 'sample/new.json', repo / '.codex/skills/new.json']:
        with pytest.raises(ValueError):
            validate_output_destination(output, repo, personal)
    assert original.read_text() == 'personal edits'
    assert 'Review evidence' in managed.read_text()
    validate_output_destination(tmp_path / 'new-report.json', repo, personal)


def test_backup_output_is_checked_before_backup_creation(tmp_path, monkeypatch):
    import sys
    from scripts.skill_distribution import main as distribution_main
    repo = tmp_path / 'repo'
    skill(repo, runtime='.codex', metadata='')
    personal = tmp_path / 'personal'
    (personal / 'sample').mkdir(parents=True)
    (personal / 'sample/SKILL.md').write_text('personal edits')
    destination = tmp_path / 'backup'
    monkeypatch.setattr(sys, 'argv', ['skill_distribution.py', '--workspace', str(repo), 'backup',
                                    '--personal-root', str(personal), '--destination', str(destination),
                                    '--output', str(destination / 'sample/SKILL.md')])
    with pytest.raises(SystemExit) as exc:
        distribution_main()
    assert exc.value.code == 2
    assert not destination.exists()
    assert (personal / 'sample/SKILL.md').read_text() == 'personal edits'
