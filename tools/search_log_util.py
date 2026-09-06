"""Stable search-log keys for CLI query modes and filter scopes."""

import json
import sys


def canonical_search_key(mode, query=None, **filters):
    """Return a deterministic key distinguishing a command mode and its filters."""
    payload = {"mode": mode}
    if query is not None:
        payload["query"] = query
    payload.update(
        {
            name: value
            for name, value in filters.items()
            if value is not None
        }
    )
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def log_search_result(query_key, source, returned_count):
    """Best-effort legacy audit logging, with visible storage failures.

    New callers pass a credential-free scoped key and actual returned count;
    unmigrated callers retain their legacy key/count semantics. This audit log
    alone does not establish reusable results.
    """
    try:
        from tools.lead_tracker import log_search
    except ImportError:
        from lead_tracker import log_search
    try:
        log_search(query_key, source, returned_count)
    except Exception as error:
        print(
            f"WARNING: {source} results were not recorded in search history "
            f"({type(error).__name__}); returned results remain available.",
            file=sys.stderr,
        )
