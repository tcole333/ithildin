#!/usr/bin/env python3
"""Discover repository CLIs offline using existing code and module inventories.

list --domain legal --query court --json
 describe query_courtlistener search --json

This catalog reads source text only. It never imports query tools, opens source
DBs, reads credentials, or probes endpoints. Health stays an explicit operation
of source_report.py. Static declarations are not proof of complete runtime
argument validation; dynamic declarations are labeled for --help inspection.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
try:
    from scripts.cli_contract import inspect_contract, select_parser
except ModuleNotFoundError as exc:
    raise RuntimeError("Run the catalog from its repository checkout") from exc

TOOL_RE = re.compile(r'(?:tools/)?([a-z][a-z0-9_]+)\.py')


def literal(node: ast.AST | None) -> Any:
    try:
        return ast.literal_eval(node) if node is not None else None
    except (ValueError, TypeError, SyntaxError):
        return None


def source_inventory(workspace: Path) -> dict[str, list[str]]:
    """Reuse source_report's declared query_tool links without its live checks."""
    result: dict[str, list[str]] = {}
    source = workspace / 'tools/source_report.py'
    if not source.exists():
        return result
    for node in ast.walk(ast.parse(source.read_text())):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        labels = [literal(t.slice) for t in node.targets if isinstance(t, ast.Subscript)
                  and isinstance(t.value, ast.Name) and t.value.id == 'sources']
        for key, value in zip(node.value.keys, node.value.values):
            if literal(key) != 'query_tool' or not isinstance(literal(value), str):
                continue
            for match in TOOL_RE.finditer(literal(value)):
                result.setdefault(match.group(1), []).extend(label for label in labels if isinstance(label, str))
    return result


def documentation_index(workspace: Path) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for path in sorted((workspace / 'docs/modules').glob('*.md')):
        heading = ''
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith('#'):
                heading = line.lstrip('# ').strip()
            for match in TOOL_RE.finditer(line):
                item = {'path': str(path.relative_to(workspace)), 'line': line_no,
                        'section': heading, 'domain': path.stem}
                items = result.setdefault(match.group(1), [])
                if not any(i['path'] == item['path'] for i in items):
                    items.append(item)
    return result


def catalog(workspace: Path) -> list[dict]:
    sources, docs = source_inventory(workspace), documentation_index(workspace)
    result = []
    for path in sorted((workspace / 'tools').glob('*.py')):
        if path.name.startswith('_'):
            continue
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError):
            continue
        public = any(isinstance(n, ast.If) and '__name__' in ast.unparse(n.test)
                     and '__main__' in ast.unparse(n.test) for n in tree.body)
        if not public:
            continue
        first = next((line.strip() for line in (ast.get_docstring(tree) or '').splitlines() if line.strip()), '')
        result.append({'id': path.stem, 'path': str(path.relative_to(workspace)),
                       'description': first[:180], 'sources': sorted(set(sources.get(path.stem, []))),
                       'domains': sorted({d['domain'] for d in docs.get(path.stem, [])}),
                       'documentation': docs.get(path.stem, [])})
    return result


def declarations(path: Path, operation: str | None) -> dict:
    """Use the same safe declaration contract as the repository linter."""
    contract = inspect_contract(path)
    if contract.parser is None:
        return {'inspection': 'unavailable', 'limitations': contract.limitations,
                'detail': 'No static argparse contract. Runtime --help was not executed.'}
    selected = select_parser(contract.parser, operation.split()) if operation else contract.parser
    if selected is None:
        raise ValueError(f'No statically declared operation {operation!r}; inspect tool --help for dynamic operations')

    def arguments(parser):
        rows = []
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                continue
            item = {'names': action.option_strings or [action.dest], 'required': action.required,
                    'nargs': action.nargs, 'help': action.help}
            if action.choices is not None:
                item['choices'] = list(action.choices)
            if action.type in (str, int, float):
                item['type'] = action.type.__name__
            rows.append(item)
        return rows

    sub = next((action for action in selected._actions if isinstance(action, argparse._SubParsersAction)), None)
    commands = [{'name': name, 'arguments': arguments(parser)} for name, parser in sub.choices.items()] if sub else []
    if operation:
        commands = [{'name': operation, 'arguments': arguments(selected)}]
    return {'inspection': 'partial' if contract.limitations else 'declarative_argparse',
            'global_arguments': arguments(contract.parser), 'commands': commands,
            'limitations': contract.limitations, 'value_constraints': contract.value_constraints,
            'limitation': 'Flags and subcommands are inspected statically. Argument values, defaults, callbacks, and runtime availability are not verified; see value_constraints and shape limitations.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=ROOT, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest='command', required=True)
    listing = sub.add_parser('list', help='List compact CLI entries without health probes')
    listing.add_argument('--domain')
    listing.add_argument('--query', default='')
    listing.add_argument('--limit', type=int, default=30)
    listing.add_argument('--offset', type=int, default=0)
    describe = sub.add_parser('describe', help='Read one CLI, its documentation routes and static arguments')
    describe.add_argument('tool')
    describe.add_argument('operation', nargs='?')
    for command in (listing, describe):
        command.add_argument('--json', action='store_true')
        command.add_argument('--output', type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    entries = catalog(workspace)
    if args.command == 'list':
        if args.limit < 1 or args.offset < 0:
            parser.error('--limit must be positive and --offset nonnegative')
        matches = [item for item in entries if (not args.domain or args.domain in item['domains'])
                   and args.query.casefold() in json.dumps(item).casefold()]
        result = {'status': 'ok', 'total': len(matches), 'offset': args.offset,
                  'items': matches[args.offset:args.offset + args.limit],
                  'next_offset': args.offset + args.limit if args.offset + args.limit < len(matches) else None}
    else:
        name = Path(args.tool).stem
        entry = next((item for item in entries if item['id'] == name), None)
        if entry is None:
            parser.error(f'Unknown CLI {args.tool!r}; use list --query TERM')
        try:
            schema = declarations(workspace / entry['path'], args.operation)
        except ValueError as exc:
            parser.error(str(exc))
        result = {'status': 'ok', **entry, **schema,
                  'help_command': f"uv run python {entry['path']}" + (f' {args.operation}' if args.operation else '') + ' --help',
                  'health': 'not_checked; use source_report.py check with an applicable source name'}
    payload = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload)
        print(f"Catalog {args.command} saved to {args.output}")
    elif args.json:
        print(payload, end='')
    elif args.command == 'list':
        for entry in result['items']:
            print(f"{entry['id']}: {entry['description']}")
        print(f"Showing {len(result['items'])} of {result['total']}; next_offset={result['next_offset']}")
    else:
        print(payload, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
