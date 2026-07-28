"""Stable search-log keys for CLI query modes and filter scopes."""

import json


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
