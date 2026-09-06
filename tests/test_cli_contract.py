"""Static interface inspection must keep uncertainty and runtime execution apart."""
import pytest

from scripts.cli_contract import inspect_contract, select_parser
from scripts.validate_skills import lint_markdown_file
from tools.tool_catalog import declarations


def inspect(tmp_path, source):
    path = tmp_path / 'cli.py'
    path.write_text(source)
    return inspect_contract(path)


def lint(tmp_path, command):
    document = tmp_path / 'example.md'
    document.write_text(f'```bash\nuv run python cli.py {command}\n```\n')
    return lint_markdown_file(document, tmp_path, False, False, {}, None)


def test_value_callbacks_and_choices_do_not_hide_unknown_flags(tmp_path):
    marker = tmp_path / 'callback-ran'
    contract = inspect(tmp_path, f'''
import argparse
from pathlib import Path
Path({str(marker)!r}).touch()
def validate(value):
    Path({str(marker)!r}).touch()
    return value
class Remember(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        Path({str(marker)!r}).touch()
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--number', type=validate, action=Remember)
    p.add_argument('--choice', choices=fetch_remote_choices())
    p.parse_args()
''')
    assert not contract.limitations
    assert len(contract.value_constraints) == 3
    assert lint(tmp_path, '--number 2 --choice sample') == []
    assert any('--typo' in issue.message for issue in lint(tmp_path, '--typo 2'))
    schema = declarations(tmp_path / 'cli.py', None)
    assert schema['inspection'] == 'declarative_argparse'
    assert schema['value_constraints'] == contract.value_constraints
    assert not marker.exists()


def test_boolean_optional_action_includes_negative_option(tmp_path):
    contract = inspect(tmp_path, '''import argparse
p = argparse.ArgumentParser()
p.add_argument('--enabled', action=argparse.BooleanOptionalAction)
p.parse_args()
''')
    assert not contract.limitations
    assert lint(tmp_path, '--no-enabled') == []
    assert any('--not-enabled' in issue.message for issue in lint(tmp_path, '--not-enabled'))


def test_literal_helpers_loops_and_conditions_keep_sibling_flags_separate(tmp_path):
    contract = inspect(tmp_path, '''import argparse
def build_parser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers()
    def common(parser):
        parser.add_argument('--output')
    for name, definition in {'first_item': {'label': 'First'}, 'second': {'label': 'Second'}}.items():
        child = sub.add_parser(name)
        child.add_argument(f"--{name.replace('_', '-')}", help=f"{definition['label']} choice")
        child.add_argument('--number', choices=range(1, 5))
        if name in {'first_item'}:
            child.add_argument('--first-only')
    for child in sub.choices.values():
        common(child)
    return p
''')
    assert not contract.limitations
    assert lint(tmp_path, 'first_item --first-item yes --first-only yes --output result.json') == []
    assert any('--first-only' in issue.message for issue in lint(tmp_path, 'second --first-only yes'))
    parser = select_parser(contract.parser, ['first_item'])
    assert list(parser._option_string_actions['--number'].choices) == [1, 2, 3, 4]


@pytest.mark.parametrize('different', [False, True])
def test_unknown_branch_must_have_equivalent_interfaces(tmp_path, different):
    flag = '--other' if different else '--one'
    contract = inspect(tmp_path, f'''import argparse
p = argparse.ArgumentParser()
if runtime_available():
    p.add_argument('--one')
    p.add_argument('--two')
else:
    p.add_argument('--two')
    p.add_argument({flag!r})
p.parse_args()
''')
    assert bool(contract.limitations) == different
    assert bool(lint(tmp_path, '--one value')) == different
    if not different:
        assert any('both branches' in note for note in contract.value_constraints)


@pytest.mark.parametrize('keyword', ['nargs=dynamic()', 'action=dynamic_action', '**dynamic_keywords()'])
def test_unknown_argument_shape_remains_a_failure(tmp_path, keyword):
    contract = inspect(tmp_path, f'''import argparse
p = argparse.ArgumentParser()
p.add_argument('--known', {keyword})
p.parse_args()
''')
    assert contract.limitations
    assert lint(tmp_path, '--known value')


@pytest.mark.parametrize('definition', [
    'class Custom(Mixin, argparse.ArgumentParser):\n    pass',
    'class Custom(argparse.ArgumentParser):\n    def parse_args(self):\n        self.add_argument("--injected")',
    'class Custom(argparse.ArgumentParser):\n    def __init__(self):\n        super().__init__()',
])
def test_custom_parser_declaration_behavior_is_not_claimed_complete(tmp_path, definition):
    contract = inspect(tmp_path, f'import argparse\n{definition}\np = Custom()\np.parse_args()\n')
    assert contract.limitations
    assert lint(tmp_path, '--injected value')


def test_nested_cursor_skips_option_values_equal_to_command(tmp_path):
    contract = inspect(tmp_path, '''import argparse
p = argparse.ArgumentParser()
p.add_argument('--label')
p.add_argument('--pair', nargs=2)
sub = p.add_subparsers()
document = sub.add_parser('document')
kinds = document.add_subparsers()
card = kinds.add_parser('card')
card.add_argument('--output')
p.parse_args()
''')
    assert not contract.limitations
    assert lint(tmp_path, '--label document document card --output result.json') == []
    assert lint(tmp_path, '--pair document card document card --output result.json') == []
