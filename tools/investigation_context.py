#!/usr/bin/env python3
"""Investigation profile system for Ithildin.

Manages investigation profiles stored as YAML files in investigations/<name>/config.yaml.
The active profile is tracked in investigation.db's investigation_config table.

Usage:
    uv run python tools/investigation_context.py show          # Show active profile
    uv run python tools/investigation_context.py show --json   # JSON output
    uv run python tools/investigation_context.py set epstein   # Set active profile
    uv run python tools/investigation_context.py list          # List available profiles
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

PROJECT_ROOT = Path(__file__).parent.parent
INVESTIGATIONS_DIR = PROJECT_ROOT / "investigations"
DB_PATH = Path(os.environ.get("ITHILDIN_DB_PATH", PROJECT_ROOT / "investigation.db"))
PROFILE_DATA_TABLES = (
    "connections",
    "event_timeline",
    "financial_disclosures",
    "findings",
    "investigation_threads",
    "leads",
)


@dataclass
class CorpusTool:
    """A document corpus tool available for this investigation."""
    tool: str          # path relative to project root, e.g. "tools/query_doj.py"
    name: str          # display name, e.g. "DOJ Vol 11"
    description: str   # brief description
    commands: list = field(default_factory=list)  # available subcommands


@dataclass
class ThreadDef:
    """An investigation thread definition."""
    id: int
    name: str
    description: str = ""
    targets: list = field(default_factory=list)    # lowercase target names for classification
    keywords: list = field(default_factory=list)   # regex patterns for classification


@dataclass
class KeyDate:
    """A key date in the investigation timeline."""
    date: str
    event: str
    category: str = "milestone"


@dataclass
class SeedPillar:
    """An institutional pillar to seed."""
    name: str
    pillar_type: str
    sub_type: str
    status: str = "active"
    founded: Optional[str] = None
    dissolved: Optional[str] = None
    jurisdiction: Optional[str] = None
    significance: str = ""


@dataclass
class InvestigationProfile:
    """Complete investigation profile loaded from YAML config."""
    name: str
    primary_subject: str
    description: str = ""

    # Key persons and addresses for priority escalation
    key_persons: list = field(default_factory=list)
    known_addresses: dict = field(default_factory=dict)  # pattern -> description

    # Investigation threads
    threads: list = field(default_factory=list)  # list of ThreadDef-like dicts

    # Document corpus tools specific to this investigation
    corpus_tools: list = field(default_factory=list)  # list of CorpusTool-like dicts

    # Timeline
    key_dates: list = field(default_factory=list)  # list of KeyDate-like dicts

    # Institutional pillars to seed
    seed_pillars: list = field(default_factory=list)  # list of SeedPillar-like dicts

    # Evidence system
    evidence_id_prefix: str = ""  # e.g. "EFTA" for Epstein DOJ docs

    # Graph display
    exclude_from_graph: str = ""  # primary subject name to optionally exclude

    # Source reliability overrides
    source_overrides: dict = field(default_factory=dict)

    # Bridge threads — thread IDs from other profiles to include in scoped queries
    bridge_threads: list = field(default_factory=list)


def _parse_yaml(path: Path) -> dict:
    """Parse YAML file, with fallback if PyYAML not installed."""
    text = path.read_text()
    if yaml is not None:
        return yaml.safe_load(text) or {}
    # Minimal fallback: try JSON (config.yaml could also be valid JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("ERROR: PyYAML not installed and file is not valid JSON.", file=sys.stderr)
        print("Install with: uv add pyyaml", file=sys.stderr)
        sys.exit(1)


def load_profile(name: str) -> InvestigationProfile:
    """Load an investigation profile from investigations/<name>/config.yaml."""
    _validate_profile_name(name)
    config_path = INVESTIGATIONS_DIR / name / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Investigation profile not found: {config_path}")

    data = _parse_yaml(config_path)

    return InvestigationProfile(
        name=data.get("name", name),
        primary_subject=data.get("primary_subject", ""),
        description=data.get("description", ""),
        key_persons=data.get("key_persons", []),
        known_addresses=data.get("known_addresses", {}),
        threads=data.get("threads", []),
        corpus_tools=data.get("corpus_tools", []),
        key_dates=data.get("key_dates", []),
        seed_pillars=data.get("seed_pillars", []),
        evidence_id_prefix=data.get("evidence_id_prefix", ""),
        exclude_from_graph=data.get("exclude_from_graph", ""),
        source_overrides=data.get("source_overrides", {}),
        bridge_threads=data.get("bridge_threads", []),
    )


def _get_db():
    """Get DB connection, ensuring profile metadata is present and reconciled."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("""
        CREATE TABLE IF NOT EXISTS investigation_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS investigation_profiles (
            profile_id   TEXT PRIMARY KEY,
            display_name TEXT,
            status       TEXT NOT NULL DEFAULT 'active',
            created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    _reconcile_profile_catalog(db)
    db.commit()
    return db


def _get_read_db():
    """Open profile state without schema/catalog writes during ordinary reads."""
    if not DB_PATH.exists():
        return _get_db()
    db = sqlite3.connect(str(DB_PATH), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=5000")
    return db


def _reconcile_profile_catalog(
    db: sqlite3.Connection, *, include_data_profiles: bool = False
) -> set[str]:
    """Catalog every configured or data-bearing profile without deleting history.

    YAML directories are the source of truth for profiles that can be activated.
    Database-only profile IDs may still own historical records, so reconciliation
    preserves and catalogs them rather than deleting or silently hiding them.
    """
    profile_ids = set()
    if INVESTIGATIONS_DIR.exists():
        profile_ids = {
            directory.name
            for directory in INVESTIGATIONS_DIR.iterdir()
            if directory.is_dir()
            and directory.name != "_template"
            and (directory / "config.yaml").exists()
        }

    if include_data_profiles:
        existing_tables = {
            row["name"] if isinstance(row, sqlite3.Row) else row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in PROFILE_DATA_TABLES:
            if table not in existing_tables:
                continue
            if "profile_id" not in {
                column["name"] if isinstance(column, sqlite3.Row) else column[1]
                for column in db.execute(f"PRAGMA table_info({table})").fetchall()
            }:
                continue
            rows = db.execute(
                f"SELECT DISTINCT profile_id FROM {table} "
                "WHERE profile_id IS NOT NULL AND trim(profile_id) != ''"
            ).fetchall()
            profile_ids.update(
                row["profile_id"] if isinstance(row, sqlite3.Row) else row[0]
                for row in rows
            )

    db.executemany(
        """INSERT OR IGNORE INTO investigation_profiles(profile_id, display_name)
           VALUES (?, ?)""",
        ((profile_id, profile_id) for profile_id in sorted(profile_ids)),
    )
    return profile_ids


def _validate_profile_name(name: str) -> str:
    """Accept a profile identifier, never a filesystem path or empty pin."""
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError(f"Invalid investigation profile identifier: {name!r}")
    return name


def get_active_profile_name() -> str:
    """Read a task's pinned profile before the interactive shared default."""
    pinned = os.environ.get("ITHILDIN_PROFILE")
    if pinned is not None:
        return _validate_profile_name(pinned)
    db = _get_read_db()
    row = db.execute(
        "SELECT value FROM investigation_config WHERE key = 'active_profile'"
    ).fetchone()
    db.close()

    if row:
        return row["value"]

    # No profile set — check if exactly one profile exists and use it
    if INVESTIGATIONS_DIR.exists():
        profiles = [d.name for d in INVESTIGATIONS_DIR.iterdir()
                    if d.is_dir() and d.name != "_template" and (d / "config.yaml").exists()]
        if len(profiles) == 1:
            return profiles[0]
    return ""


def task_environment(profile_id=None, db_path=None, *, environ=None) -> dict[str, str]:
    """Capture context once for a task and all of its child processes.

    Callers pass this environment to subprocesses instead of changing the
    shared interactive default. A later `set` in another task cannot change it.
    """
    environment = dict(os.environ if environ is None else environ)
    selected_profile = profile_id or environment.get("ITHILDIN_PROFILE")
    selected_db = Path(db_path or environment.get("ITHILDIN_DB_PATH") or DB_PATH).expanduser()
    if not selected_profile:
        # Resolve a custom database's default without opening the live database
        # or initializing a missing database as a side effect of launching work.
        if selected_db.exists():
            with sqlite3.connect(f"{selected_db.resolve().as_uri()}?mode=ro", uri=True) as db:
                try:
                    row = db.execute(
                        "SELECT value FROM investigation_config WHERE key='active_profile'"
                    ).fetchone()
                except sqlite3.OperationalError as exc:
                    if "no such table" not in str(exc):
                        raise
                    row = None
            selected_profile = row[0] if row else None
    if not selected_profile:
        raise ValueError("A task requires --profile or ITHILDIN_PROFILE")
    environment["ITHILDIN_PROFILE"] = _validate_profile_name(selected_profile)
    environment["ITHILDIN_DB_PATH"] = str(selected_db.expanduser().resolve())
    return environment


def get_active_profile_id() -> str:
    """Get the active profile ID (name). Convenience alias for get_active_profile_name()."""
    return get_active_profile_name()


def get_active_profile() -> InvestigationProfile:
    """Load the currently active investigation profile."""
    name = get_active_profile_name()
    if not name:
        # Return empty profile if none set
        return InvestigationProfile(name="", primary_subject="")
    return load_profile(name)


def set_active_profile(name: str):
    """Set the active investigation profile in DB."""
    _validate_profile_name(name)
    config_path = INVESTIGATIONS_DIR / name / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Investigation profile not found: {config_path}")

    db = _get_db()
    db.execute(
        """INSERT INTO investigation_config (key, value, updated_at)
           VALUES ('active_profile', ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (name,)
    )
    db.commit()
    db.close()


def list_profiles() -> list[dict]:
    """List configured profiles plus visible database-only historical profiles."""
    profiles = []
    configured_names = set()
    if INVESTIGATIONS_DIR.exists():
        for d in sorted(INVESTIGATIONS_DIR.iterdir()):
            if d.is_dir() and d.name != "_template" and (d / "config.yaml").exists():
                configured_names.add(d.name)
                try:
                    p = load_profile(d.name)
                    profiles.append(
                        {
                            "name": d.name,
                            "display_name": p.name,
                            "primary_subject": p.primary_subject,
                            "description": p.description,
                            "threads": len(p.threads),
                            "key_persons": len(p.key_persons),
                            "corpus_tools": len(p.corpus_tools),
                            "database_only": False,
                        }
                    )
                except Exception as e:
                    profiles.append(
                        {"name": d.name, "error": str(e), "database_only": False}
                    )

    db = _get_db()
    _reconcile_profile_catalog(db, include_data_profiles=True)
    db.commit()
    catalog_rows = db.execute(
        "SELECT profile_id, display_name, status FROM investigation_profiles ORDER BY profile_id"
    ).fetchall()
    db.close()
    for row in catalog_rows:
        if row["profile_id"] not in configured_names:
            profiles.append(
                {
                    "name": row["profile_id"],
                    "display_name": row["display_name"] or row["profile_id"],
                    "status": row["status"],
                    "database_only": True,
                }
            )
    profiles.sort(key=lambda profile: profile["name"])
    return profiles


def profile_to_dict(profile: InvestigationProfile) -> dict:
    """Convert profile to a JSON-serializable dict."""
    return asdict(profile)


def get_global_thread_ids(profile: InvestigationProfile) -> dict[int, int]:
    """Map profile-local thread numbers to global investigation_threads IDs."""
    if not profile.name or not profile.threads:
        return {}
    db = _get_read_db()
    try:
        rows = db.execute(
            "SELECT id, title FROM investigation_threads WHERE profile_id = ?",
            (profile.name,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        db.close()
    global_by_title = {row["title"]: row["id"] for row in rows}
    return {
        int(thread["id"]): global_by_title[thread["name"]]
        for thread in profile.threads
        if thread.get("id") is not None and thread.get("name") in global_by_title
    }


# ── CLI ──────────────────────────────────────────────────────

def cmd_show(args):
    """Show the active investigation profile."""
    try:
        profile = get_active_profile()
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not profile.name:
        print("No active investigation profile set.")
        print("Use: uv run python tools/investigation_context.py set <name>")
        return

    if args.json_out or args.output:
        data = profile_to_dict(profile)
        global_thread_ids = get_global_thread_ids(profile)
        for thread in data.get("threads", []):
            thread["global_id"] = global_thread_ids.get(thread.get("id"))
        if write_output(data, args, summary=f"investigation profile {profile.name}"):
            return
        print(json.dumps(data, indent=2))
        return

    print(f"Active Investigation: {profile.name}")
    print(f"  Primary Subject: {profile.primary_subject}")
    if profile.description:
        print(f"  Description: {profile.description[:100]}")
    print(f"  Key Persons: {len(profile.key_persons)}")
    print(f"  Known Addresses: {len(profile.known_addresses)}")
    print(f"  Threads: {len(profile.threads)}")
    print(f"  Corpus Tools: {len(profile.corpus_tools)}")
    print(f"  Key Dates: {len(profile.key_dates)}")
    print(f"  Seed Pillars: {len(profile.seed_pillars)}")
    if profile.evidence_id_prefix:
        print(f"  Evidence ID Prefix: {profile.evidence_id_prefix}")
    if profile.exclude_from_graph:
        print(f"  Exclude from Graph: {profile.exclude_from_graph}")

    if profile.threads:
        global_thread_ids = get_global_thread_ids(profile)
        print("\n  Threads:")
        for t in profile.threads:
            tid = t.get("id", "?")
            tname = t.get("name", "unnamed")
            global_id = global_thread_ids.get(tid)
            suffix = f" -> global {global_id}" if global_id is not None else " -> global unmapped"
            print(f"    [local {tid}{suffix}] {tname}")

    if profile.corpus_tools:
        print("\n  Corpus Tools:")
        for ct in profile.corpus_tools:
            cname = ct.get("name", ct.get("tool", "?"))
            print(f"    - {cname}")


def cmd_set(args):
    """Set the active investigation profile."""
    try:
        set_active_profile(args.name)
        profile = load_profile(args.name)
        print(f"Active profile set to: {args.name}")
        print(f"  Primary subject: {profile.primary_subject}")
        print(f"  {len(profile.threads)} threads, {len(profile.key_persons)} key persons, {len(profile.corpus_tools)} corpus tools")
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args):
    """List available investigation profiles."""
    profiles = list_profiles()
    active_name = get_active_profile_name()

    if not profiles:
        print("No investigation profiles found.")
        print(f"Create one at: {INVESTIGATIONS_DIR}/<name>/config.yaml")
        return

    for p in profiles:
        marker = " *" if p["name"] == active_name else "  "
        if "error" in p:
            print(f"{marker}{p['name']} (ERROR: {p['error']})")
        elif p.get("database_only"):
            print(f"{marker}{p['name']} (database-only; no config; status: {p['status']})")
        else:
            print(f"{marker}{p['name']} — {p['primary_subject']} ({p.get('threads', 0)} threads, {p.get('key_persons', 0)} key persons)")


def main():
    parser = argparse.ArgumentParser(description="Investigation profile management")
    sub = parser.add_subparsers(dest="command")

    show_p = sub.add_parser("show", help="Show active investigation profile")
    add_output_args(show_p)

    set_p = sub.add_parser("set", help="Set active investigation profile")
    set_p.add_argument("name", help="Profile name (directory under investigations/)")

    sub.add_parser("list", help="List available investigation profiles")

    run_p = sub.add_parser("run", help="Run a task with an immutable profile/database context")
    run_p.add_argument("--profile", help="Profile to pin; defaults to the selected database's current profile")
    run_p.add_argument("--db", type=Path, help="Investigation database inherited by every child command")
    run_p.add_argument("argv", nargs=argparse.REMAINDER, help="Command and arguments after --")

    args = parser.parse_args()

    if args.command == "show":
        cmd_show(args)
    elif args.command == "set":
        cmd_set(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "run":
        command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        if not command:
            parser.error("run requires a command after --")
        try:
            environment = task_environment(args.profile, args.db)
        except ValueError as exc:
            parser.error(str(exc))
        raise SystemExit(subprocess.run(command, env=environment, check=False).returncode)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
