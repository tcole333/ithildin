"""Shared validation for profile-scoped investigation thread IDs."""


def profile_thread_id_map(profile_id):
    """Return configured local-thread ID -> global database ID for a profile."""
    if not profile_id:
        return {}
    try:
        from tools.investigation_context import get_global_thread_ids, load_profile
    except ImportError:
        from investigation_context import get_global_thread_ids, load_profile

    try:
        return get_global_thread_ids(load_profile(profile_id))
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return {}


def profile_bridge_thread_ids(profile_id):
    """Return explicitly configured cross-profile global thread IDs."""
    if not profile_id:
        return set()
    try:
        from tools.investigation_context import load_profile
    except ImportError:
        from investigation_context import load_profile

    try:
        profile = load_profile(profile_id)
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        return set()

    bridge_ids = set()
    for value in profile.bridge_threads or []:
        try:
            bridge_ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return bridge_ids


def _row_value(row, key, index):
    try:
        return row[key]
    except (IndexError, TypeError):
        return row[index]


def resolve_profile_thread_id(
    db,
    thread_id,
    profile_id,
    *,
    local_thread_ids=None,
    bridge_thread_ids=None,
):
    """Resolve a profile-local thread number or validate a global thread ID.

    Profiles number threads locally in YAML, while the shared database assigns
    global primary keys. Explicit ``bridge_threads`` entries are global IDs and
    therefore take precedence over a colliding local thread number.
    """
    if thread_id is None or not profile_id:
        return thread_id

    row = db.execute(
        "SELECT id, profile_id FROM investigation_threads WHERE id = ?",
        (thread_id,),
    ).fetchone()
    if row is not None:
        owner = _row_value(row, "profile_id", 1)
        if owner in {None, profile_id}:
            return thread_id
        if bridge_thread_ids is None:
            bridge_thread_ids = profile_bridge_thread_ids(profile_id)
        elif callable(bridge_thread_ids):
            bridge_thread_ids = bridge_thread_ids()
        if thread_id in bridge_thread_ids:
            return thread_id

    if local_thread_ids is None:
        local_thread_ids = profile_thread_id_map(profile_id)
    elif callable(local_thread_ids):
        local_thread_ids = local_thread_ids()
    mapped_id = local_thread_ids.get(thread_id)
    if mapped_id is not None:
        mapped = db.execute(
            "SELECT id, profile_id FROM investigation_threads WHERE id = ?",
            (mapped_id,),
        ).fetchone()
        if mapped is not None:
            owner = _row_value(mapped, "profile_id", 1)
            if owner in {None, profile_id}:
                return mapped_id

    if row is None:
        raise ValueError(
            f"Unknown thread ID {thread_id} for profile '{profile_id}'. "
            "Use a configured local thread number or its global database ID."
        )
    owner = _row_value(row, "profile_id", 1)
    raise ValueError(
        f"Thread {thread_id} belongs to profile '{owner}', not '{profile_id}', "
        "and is not a configured local thread number for the requested profile."
    )
