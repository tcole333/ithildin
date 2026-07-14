#!/usr/bin/env python3
"""Tiny front door for recording and resolving repository friction.

Papercuts are stored as ``friction`` entries in methodology_observations so the
existing methodology review and pattern detection workflows continue to work.

Examples:
    uv run python tools/papercut.py "query_foo.py returned a misleading 404"
    uv run python tools/papercut.py "rg glob missed files" \
        --command "rg --glob *.json term" --expected "Search nested JSON files"
    uv run python tools/papercut.py --list
    uv run python tools/papercut.py --resolve 12 --resolution "Quote zsh globs in docs"
"""

from __future__ import annotations

import argparse
import os
import sys

try:
    from tools.output_util import write_output
except ImportError:
    from output_util import write_output

try:
    from tools.methodology_tracker import (
        add_observation,
        get_observation,
        list_observations,
        mark_duplicate,
        promote_to_infra,
        update_status,
    )
except ImportError:
    from methodology_tracker import (
        add_observation,
        get_observation,
        list_observations,
        mark_duplicate,
        promote_to_infra,
        update_status,
    )


def format_description(
    message: str,
    *,
    command: str | None = None,
    expected: str | None = None,
    context: str | None = None,
) -> str:
    """Build a compact observation that remains readable in generic tooling."""
    parts = [message.strip()]
    if command:
        parts.append(f"Command/tool: {command.strip()}")
    if expected:
        parts.append(f"Expected: {expected.strip()}")
    if context:
        parts.append(f"Context: {context.strip()}")
    return " | ".join(parts)


def _print_open(limit: int, *, output: str | None = None) -> None:
    observations = list_observations(category="friction", status="open", limit=limit)
    if write_output(
        observations,
        argparse.Namespace(output=output),
        summary="open papercuts",
    ):
        return
    if not observations:
        print("No open papercuts")
        return

    print(f"Open papercuts ({len(observations)})")
    for item in observations:
        print(f"#{item['id']}  {item['description']}")


def _require_existing(obs_id: int) -> dict:
    observation = get_observation(obs_id)
    if not observation or observation["category"] != "friction":
        print(f"Papercut #{obs_id} not found", file=sys.stderr)
        raise SystemExit(1)
    return observation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record small repository friction instead of silently routing around it"
    )
    parser.add_argument("message", nargs="?", help="What got in the way")
    parser.add_argument("--command", help="Command or tool call that exposed the friction")
    parser.add_argument("--expected", help="What should have happened")
    parser.add_argument("--context", help="Small amount of reproduction context")
    parser.add_argument("--skill", help="Skill or workflow being used")
    parser.add_argument("--lead-id", type=int, help="Related investigation lead ID")
    parser.add_argument("--agent", default=os.environ.get("CODEX_AGENT_ID"), help="Agent identifier")
    parser.add_argument("--target", help="Investigation target")
    parser.add_argument("--list", action="store_true", help="List open papercuts")
    parser.add_argument("--limit", type=int, default=50, help="Maximum items to list")
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Write --list results as JSON to FILE (prints a 1-line summary to stdout)",
    )
    parser.add_argument("--resolve", type=int, metavar="ID", help="Mark a papercut addressed")
    parser.add_argument("--resolution", help="Root-cause fix that addressed the papercut")
    parser.add_argument("--dismiss", type=int, metavar="ID", help="Dismiss a papercut")
    parser.add_argument("--reason", help="Why the papercut is not actionable")
    parser.add_argument("--duplicate", type=int, metavar="ID", help="Mark a papercut duplicate")
    parser.add_argument("--of", type=int, metavar="ID", help="Canonical papercut ID")
    parser.add_argument("--promote", type=int, metavar="ID", help="Promote a papercut to infra")
    parser.add_argument("--infra-id", type=int, metavar="ID", help="Infrastructure request ID")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    actions = sum((
        bool(args.message),
        args.list,
        args.resolve is not None,
        args.dismiss is not None,
        args.duplicate is not None,
        args.promote is not None,
    ))
    if actions != 1:
        parser.error(
            "provide exactly one of MESSAGE, --list, --resolve ID, --dismiss ID, "
            "--duplicate ID, or --promote ID"
        )
    if args.output and not args.list:
        parser.error("--output requires --list")

    if args.list:
        _print_open(args.limit, output=args.output)
        return

    if args.resolve is not None:
        if not args.resolution:
            parser.error("--resolve requires --resolution")
        _require_existing(args.resolve)
        update_status(args.resolve, "addressed", resolution=args.resolution.strip())
        print(f"Papercut #{args.resolve} addressed: {args.resolution.strip()}")
        return

    if args.dismiss is not None:
        if not args.reason:
            parser.error("--dismiss requires --reason")
        _require_existing(args.dismiss)
        update_status(args.dismiss, "dismissed", resolution=args.reason.strip())
        print(f"Papercut #{args.dismiss} dismissed: {args.reason.strip()}")
        return

    if args.duplicate is not None:
        if args.of is None:
            parser.error("--duplicate requires --of ID")
        _require_existing(args.duplicate)
        _require_existing(args.of)
        try:
            mark_duplicate(args.duplicate, args.of)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Papercut #{args.duplicate} marked duplicate of #{args.of}")
        return

    if args.promote is not None:
        if args.infra_id is None:
            parser.error("--promote requires --infra-id ID")
        _require_existing(args.promote)
        try:
            promote_to_infra(args.promote, args.infra_id)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"Papercut #{args.promote} promoted to infra request #{args.infra_id}")
        return

    description = format_description(
        args.message,
        command=args.command,
        expected=args.expected,
        context=args.context,
    )
    if not description:
        parser.error("MESSAGE cannot be blank")
    obs_id = add_observation(
        category="friction",
        description=description,
        skill=args.skill,
        lead_id=args.lead_id,
        agent=args.agent,
        target=args.target,
    )
    print(f"Papercut #{obs_id} logged")


if __name__ == "__main__":
    main()
