"""Reconstruct declarative argparse interfaces without importing application code.

Only literal values, standard parser constructors, parser configuration methods,
and local declaration helpers are interpreted. No eval/exec, application import,
argument parsing, user-defined action/type, file read callback or command runs.
Dynamic declarations are reported as incomplete instead of guessed.
"""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class Unresolved(ValueError):
    pass


@dataclass
class Contract:
    parser: argparse.ArgumentParser | None
    limitations: list[str] = field(default_factory=list)


class Inspector:
    def __init__(self, tree: ast.Module, script: Path):
        self.tree = tree
        self.script = script
        self.workspace = next((p for p in script.parents if (p / "tools").is_dir() and (p / "scripts").is_dir()), script.parent)
        self.parser_classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef) and any(isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id == "argparse" and base.attr == "ArgumentParser" for base in n.bases)}
        self.functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.constants: dict[str, Any] = {'__doc__': ast.get_docstring(tree) or ''}
        self.parsers: list[argparse.ArgumentParser] = []
        self.limitations: set[str] = set()
        self.active: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and not any(isinstance(part, ast.Call) for part in ast.walk(node)):
                try:
                    self.assign(node, self.constants)
                except Unresolved:
                    pass

    def note(self, node: ast.AST, detail: str) -> None:
        self.limitations.add(f'line {getattr(node, "lineno", 1)}: {detail}')

    def value(self, node: ast.AST, env: dict) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in env:
                return env[node.id]
            if node.id in self.constants:
                return self.constants[node.id]
            if node.id in {'str', 'int', 'float', 'Path'}:
                return {'str': str, 'int': int, 'float': float, 'Path': Path}[node.id]
            return self.imported_literal(node.id)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            items = [self.value(n, env) for n in node.elts]
            return tuple(items) if isinstance(node, ast.Tuple) else set(items) if isinstance(node, ast.Set) else items
        if isinstance(node, ast.Dict):
            if any(key is None for key in node.keys):
                raise Unresolved('dictionary expansion')
            return {self.value(k, env): self.value(v, env) for k, v in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = self.value(node.operand, env)
            if type(value) not in (int, float):
                raise Unresolved('non-numeric unary expression')
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'argparse':
            allowed = {'SUPPRESS', 'REMAINDER', 'RawDescriptionHelpFormatter', 'RawTextHelpFormatter', 'ArgumentDefaultsHelpFormatter'}
            if node.attr in allowed:
                return getattr(argparse, node.attr)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {'sorted', 'list', 'tuple', 'set'} and len(node.args) == 1 and not node.keywords:
                value = self.value(node.args[0], env)
                if type(value) not in (list, tuple, set, dict):
                    raise Unresolved('non-literal collection')
                return {'sorted': sorted, 'list': list, 'tuple': tuple, 'set': set}[node.func.id](value)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {'items', 'keys', 'values'} and not node.args and not node.keywords:
                value = self.value(node.func.value, env)
                if type(value) is dict:
                    return list(getattr(value, node.func.attr)())
            return self.call(node, env)
        raise Unresolved(type(node).__name__)

    def imported_literal(self, name: str) -> Any:
        # Resolve only literal exported constants in repository Python files.
        # Import statements are inspected as text; modules never run.
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            imported = next((item.name for item in node.names if (item.asname or item.name) == name), None)
            if imported is None:
                continue
            candidates = [self.workspace.joinpath(*node.module.split('.')).with_suffix('.py'),
                          self.script.parent.joinpath(*node.module.split('.')).with_suffix('.py')]
            for candidate in candidates:
                if not candidate.is_file() or not candidate.resolve().is_relative_to(self.workspace.resolve()):
                    continue
                for statement in ast.parse(candidate.read_text()).body:
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target] if isinstance(statement, ast.AnnAssign) else []
                    if any(isinstance(target, ast.Name) and target.id == imported for target in targets):
                        try:
                            value = ast.literal_eval(statement.value)
                            self.constants[name] = value
                            return value
                        except (ValueError, TypeError):
                            pass
        raise Unresolved(name)

    def bind(self, target: ast.AST, value: Any, env: dict) -> None:
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(value, (tuple, list)) and len(target.elts) == len(value):
            for item, element in zip(target.elts, value):
                self.bind(item, element, env)
        else:
            raise Unresolved('assignment target')

    def assign(self, node: ast.Assign | ast.AnnAssign, env: dict) -> None:
        value = self.value(node.value, env)
        for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
            self.bind(target, value, env)

    def local_function(self, name: str, args: list[Any], kwargs: dict | None = None) -> Any:
        if name in self.active:
            raise Unresolved('recursive parser helper')
        function = self.functions[name]
        names = [arg.arg for arg in function.args.args]
        if len(args) > len(names):
            raise Unresolved('helper arguments')
        env = {}
        for parameter, default in zip(names[len(names) - len(function.args.defaults):], function.args.defaults):
            try:
                env[parameter] = self.value(default, env)
            except Unresolved:
                pass
        for parameter, default in zip(function.args.kwonlyargs, function.args.kw_defaults):
            if default is not None:
                try:
                    env[parameter.arg] = self.value(default, env)
                except Unresolved:
                    pass
        env.update(zip(names, args))
        env.update(kwargs or {})
        self.active.add(name)
        try:
            return self.statements(function.body, env)
        finally:
            self.active.remove(name)

    def call(self, node: ast.Call, env: dict) -> Any:
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name in self.parser_classes:
                self.note(node, 'custom ArgumentParser behavior was not executed')
                clone = ast.Call(func=ast.Attribute(value=ast.Name(id='argparse'), attr='ArgumentParser'), args=node.args, keywords=node.keywords)
                ast.copy_location(clone, node)
                return self.call(clone, env)
            if name in self.functions:
                args = [self.value(arg, env) for arg in node.args]
                function = self.functions[name]
                declaration_helper = any(isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute) and part.func.attr in {'ArgumentParser', 'add_argument', 'add_parser'} for part in ast.walk(function))
                if not declaration_helper and not any(isinstance(arg, (argparse.ArgumentParser, argparse._SubParsersAction)) for arg in args):
                    raise Unresolved(f'non-declaration helper {name}')
                kwargs = {kw.arg: self.value(kw.value, env) for kw in node.keywords if kw.arg is not None}
                return self.local_function(name, args, kwargs)
            if name == 'add_output_args' and len(node.args) == 1:
                # Reuse the owned helper's literal declarations, without even
                # importing it. Its conditional only avoids duplicate flags.
                parser = self.value(node.args[0], env)
                if isinstance(parser, argparse.ArgumentParser):
                    helper_path = Path(__file__).resolve().parents[1] / 'tools/output_util.py'
                    helper_tree = ast.parse(helper_path.read_text())
                    helper = next(n for n in helper_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'add_output_args')
                    for part in ast.walk(helper):
                        if isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute) and part.func.attr == 'add_argument':
                            flags = [self.value(arg, {}) for arg in part.args]
                            if not any(flag in parser._option_string_actions for flag in flags):
                                self.call(part, {'parser': parser})
                    return None
            raise Unresolved(f'helper {name}')
        if not isinstance(node.func, ast.Attribute):
            raise Unresolved('dynamic call')
        method = node.func.attr
        constructor = isinstance(node.func.value, ast.Name) and node.func.value.id == 'argparse' and method == 'ArgumentParser'
        if constructor:
            receiver = None
        else:
            receiver = self.value(node.func.value, env)
            if not isinstance(receiver, (argparse.ArgumentParser, argparse._SubParsersAction, argparse._ArgumentGroup)):
                raise Unresolved('non-parser receiver')
        allowed = {'add_subparsers', 'add_parser', 'add_argument', 'add_argument_group', 'add_mutually_exclusive_group', 'set_defaults'}
        if not constructor and method not in allowed:
            raise Unresolved(f'non-declaration parser method {method}')
        if method == 'set_defaults':
            return None  # Handler/default evaluation is unnecessary for syntax.
        args = [self.value(arg, env) for arg in node.args]
        kwargs = {}
        for kw in node.keywords:
            if kw.arg in {'default', 'epilog', 'description', 'prog'}:
                continue
            try:
                value = self.value(kw.value, env)
            except Unresolved:
                if kw.arg not in {'help', 'metavar', 'formatter_class'}:
                    self.note(node, f'dynamic {kw.arg or "keyword expansion"}')
                continue
            if kw.arg is None:
                if not isinstance(value, dict):
                    raise Unresolved('keyword expansion')
                kwargs.update(value)
            else:
                kwargs[kw.arg] = value
        if kwargs.get('type') not in (None, str, int, float, Path):
            self.note(node, 'custom argument type was not evaluated')
            kwargs.pop('type', None)
        if 'action' in kwargs and kwargs['action'] not in {'store', 'store_const', 'store_true', 'store_false', 'append', 'append_const', 'extend', 'count', 'help', 'version'}:
            self.note(node, 'custom argument action was not evaluated')
            kwargs.pop('action')
        if constructor:
            # Never permit response files or a custom parser/action factory.
            kwargs.pop('fromfile_prefix_chars', None)
            parser = argparse.ArgumentParser(*args, **kwargs)
            self.parsers.append(parser)
            return parser
        kwargs.pop('parser_class', None)
        return getattr(receiver, method)(*args, **kwargs)

    def mentions_parser(self, node: ast.AST, env: dict) -> bool:
        names = {name for name, value in env.items() if isinstance(value, (argparse.ArgumentParser, argparse._SubParsersAction, argparse._ArgumentGroup))}
        return any(isinstance(part, ast.Name) and part.id in names for part in ast.walk(node))

    def statements(self, statements: list[ast.stmt], env: dict) -> Any:
        for node in statements:
            # Stop before parse_args: nothing after the parse boundary belongs
            # to the declaration contract, regardless of the action requested.
            parse_call = next((part for part in ast.walk(node)
                               if isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute)
                               and part.func.attr in {'parse_args', 'parse_known_args', 'parse_intermixed_args'}), None) if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr, ast.Return)) else None
            if parse_call:
                try:
                    return self.value(parse_call.func.value, env)
                except Unresolved:
                    return None
            try:
                if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                    self.assign(node, env)
                elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    self.call(node.value, env)
                elif isinstance(node, ast.For):
                    values = self.value(node.iter, env)
                    if type(values) not in (tuple, list, dict, set) or len(values) > 2000:
                        raise Unresolved('dynamic/unbounded parser loop')
                    for value in values:
                        self.bind(node.target, value, env)
                        self.statements(node.body, env)
                elif isinstance(node, ast.Return):
                    return self.value(node.value, env) if node.value else None
                elif isinstance(node, ast.If):
                    value = self.value(node.test, env)
                    self.statements(node.body if value else node.orelse, env)
                elif not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass)):
                    declaration = any(isinstance(part, ast.Call) and isinstance(part.func, ast.Attribute)
                                      and part.func.attr in {'ArgumentParser', 'add_argument', 'add_parser', 'add_subparsers', 'set_defaults'}
                                      for part in ast.walk(node))
                    if declaration or self.mentions_parser(node, env):
                        self.note(node, f'unsupported declaration statement {type(node).__name__}')
            except (Unresolved, TypeError, ValueError, argparse.ArgumentError) as exc:
                if self.mentions_parser(node, env) or isinstance(node, ast.For):
                    self.note(node, f'unsupported declaration ({exc})')
        return None

    def inspect(self) -> Contract:
        function = next((name for name in ('build_parser', 'parse_args', 'main') if name in self.functions), None)
        if function:
            parser = self.local_function(function, [])
        else:
            parser = self.statements(self.tree.body, {})
        if not isinstance(parser, argparse.ArgumentParser):
            parser = self.parsers[-1] if self.parsers else None
        return Contract(parser, sorted(self.limitations))


def inspect_contract(script: Path) -> Contract:
    try:
        return Inspector(ast.parse(script.read_text()), script).inspect()
    except (OSError, SyntaxError, UnicodeError, Unresolved, TypeError, ValueError, argparse.ArgumentError) as exc:
        return Contract(None, [f'Cannot inspect CLI declarations: {type(exc).__name__}: {exc}'])


def select_parser(parser: argparse.ArgumentParser, subcommands: list[str]) -> argparse.ArgumentParser | None:
    for name in subcommands:
        sub = next((action for action in parser._actions if isinstance(action, argparse._SubParsersAction)), None)
        if sub is None or name not in sub.choices:
            return None
        parser = sub.choices[name]
    return parser
