#!/usr/bin/env python3
"""Shared output utility for investigation tools.

Provides --output FILE flag that writes JSON to a file and prints a 1-line
summary to stdout, keeping agent conversation context lean.

Usage in tools:
    from tools.output_util import add_output_args, write_output

    # In argparse setup:
    add_output_args(parser)          # global flag
    add_output_args(search_parser)   # or per-subparser

    # In output section:
    if not write_output(results, args, summary="DOJ search 'bannon'"):
        # existing pretty-print code (unchanged)
        ...
"""

import json


# List-valued fields that represent returned rows rather than response metadata.
# Composite wrappers such as FARA and SAM may contain more than one of these, so
# their counts are summed. Nested wrappers cover responses such as EDGAR's
# ``hits.hits`` shape.
_RESULT_COLLECTION_KEYS = frozenset({
    "agents",
    "articles",
    "data",
    "entities",
    "exclusions",
    "foreign_principals",
    "filings",
    "grants",
    "hits",
    "items",
    "officers",
    "records",
    "registrants",
    "related_orgs",
    "results",
})
_UNAVAILABLE_STATUSES = frozenset({"blocked", "error", "failed", "failure", "unavailable"})


def _collection_count(data):
    """Return ``(found_collection, row_count)`` for known result containers."""
    if not isinstance(data, dict):
        return False, 0

    found = False
    count = 0
    for key, value in data.items():
        if key not in _RESULT_COLLECTION_KEYS:
            continue
        if isinstance(value, list):
            found = True
            count += len(value)
        elif isinstance(value, dict):
            nested_found, nested_count = _collection_count(value)
            if nested_found:
                found = True
                count += nested_count
    return found, count


def substantive_result_count(data):
    """Count returned rows, or return ``None`` when the source was unavailable.

    Unknown dictionaries retain the historical single-resource count of one.
    This prevents metadata keys in a detail response from being mistaken for
    rows while allowing known list wrappers to report a clean zero correctly.
    """
    if data is None:
        return None
    if isinstance(data, list):
        return len(data)
    if not isinstance(data, dict):
        return 1

    status = data.get("status")
    explicitly_unavailable = (
        data.get("available") is False
        or data.get("source_available") is False
        or (isinstance(status, str) and status.lower() in _UNAVAILABLE_STATUSES)
        or bool(data.get("error"))
    )
    if explicitly_unavailable:
        return None

    found, count = _collection_count(data)
    if found:
        return count
    return 1


def add_output_args(parser):
    """Add --output (and --json if missing) to an argparse parser."""
    existing = {a.dest for a in parser._actions}
    if "output" not in existing:
        parser.add_argument(
            "--output", metavar="FILE",
            help="Write JSON results to FILE (prints 1-line summary to stdout)",
        )
    if "json" not in existing and "json_out" not in existing:
        parser.add_argument(
            "--json", action="store_true", dest="json_out",
            help="Output raw JSON to stdout",
        )


def write_output(data, args, summary=None):
    """If --output is set, write JSON to file and print summary. Returns True if written.

    Args:
        data: The data to serialize (list, dict, or other JSON-serializable).
        args: Parsed argparse namespace (checks args.output).
        summary: Optional description for the summary line.
              If omitted, uses a generic count-based message.
    """
    output_path = getattr(args, "output", None)
    if not output_path:
        return False

    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Build summary line from substantive rows rather than wrapper keys.
    count = substantive_result_count(data)
    result_label = "results unavailable" if count is None else f"{count} results"
    desc = f" ({summary})" if summary else ""
    print(f"{result_label}{desc} saved to {output_path}")
    return True
