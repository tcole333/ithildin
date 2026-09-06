"""Exercise research skill commands against bounded fixtures, never live sources."""

import importlib.util
import json
from pathlib import Path
import re
import shlex
import sqlite3
import sys

import pytest

from tools import findings_tracker, lead_tracker, query_acris


ROOT = Path(__file__).resolve().parents[1]
RUNTIMES = (".claude", ".codex")


def _commands(runtime, skill, tool):
    text = (ROOT / runtime / "skills" / skill / "SKILL.md").read_text()
    commands = []
    for block in re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL):
        for line in block.replace("\\\n", " ").splitlines():
            if line.startswith(f"uv run python tools/{tool}.py "):
                commands.append(shlex.split(line)[3:])
    return commands


def _load_tool(tool):
    spec = importlib.util.spec_from_file_location(
        f"_research_skill_test_{tool}", ROOT / "tools" / f"{tool}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_documented_corpus_read_retains_decisive_text_after_preview(
    runtime, tmp_path, monkeypatch
):
    """The documented retrieval must preserve more than the 2,000-char preview."""
    tool = _load_tool("ingest_kabasshouse")
    db_path = tmp_path / "corpus.db"
    full_text = "Opening context. " * 250 + "DECISIVE QUALIFICATION AFTER PREVIEW."
    with sqlite3.connect(db_path) as db:
        db.execute(
            "CREATE TABLE documents "
            "(id TEXT, file_key TEXT, page_number INTEGER, full_text TEXT)"
        )
        db.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?)",
            ("row-1", "EFTA99999999", 1, full_text),
        )
    command, = [
        cmd for cmd in _commands(runtime, "deep-investigate", "ingest_kabasshouse")
        if cmd[1] == "doc"
    ]
    command = [
        value.replace("<EFTA_ID>", "EFTA99999999").replace("$WORKDIR", str(tmp_path))
        for value in command
    ]
    monkeypatch.setattr(tool, "DB_PATH", db_path)
    monkeypatch.setattr(sys, "argv", command)
    tool.main()
    output = Path(command[command.index("--output") + 1])
    records = json.loads(output.read_text())
    assert len(records) == 1
    assert records[0]["full_text"] == full_text


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_preflight_entity_lookup_uses_pinned_database(runtime, tmp_path, monkeypatch):
    """Run the copyable preflight with conflicting DB fixtures and a guarded open."""
    selected = tmp_path / "selected.db"
    other = tmp_path / "investigation.db"
    for file_path, entity_name in (
        (selected, "Target selected record"),
        (other, "Target unrelated record"),
    ):
        with sqlite3.connect(file_path) as db:
            db.execute(
                "CREATE TABLE entities "
                "(id INTEGER, name TEXT, entity_type TEXT, jurisdiction TEXT, "
                "ein TEXT, status TEXT, source TEXT, created_at TEXT)"
            )
            db.execute(
                "INSERT INTO entities VALUES (1, ?, 'corporation', 'us', NULL, "
                "'active', 'fixture', '2026-01-01')",
                (entity_name,),
            )
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(selected))
    tool = _load_tool("entity_tracker")
    real_connect = sqlite3.connect

    def guarded_connect(db_file, *args, **kwargs):
        assert Path(db_file) == selected, "Preflight escaped the pinned fixture database"
        return real_connect(db_file, *args, **kwargs)

    monkeypatch.setattr(tool.sqlite3, "connect", guarded_connect)
    # Schema migration is separately covered; this fixture exercises read routing.
    monkeypatch.setattr(lead_tracker, "_ensure_schema", lambda db: db)
    command, = [
        cmd for cmd in _commands(runtime, "deep-investigate", "entity_tracker")
        if cmd[1] == "lookup"
    ]
    command = [
        value.replace("<TARGET>", "Target").replace("$WORKDIR", str(tmp_path))
        for value in command
    ]
    monkeypatch.setattr(sys, "argv", command)
    tool.main()
    rows = json.loads(Path(command[command.index("--output") + 1]).read_text())
    assert [row["name"] for row in rows] == ["Target selected record"]


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_entity_trace_acris_command_is_target_scoped(runtime, tmp_path):
    """Interpret every ACRIS example with the real parser, without network calls."""
    commands = _commands(runtime, "trace-entity", "query_acris")
    assert commands
    for command in commands:
        command = [
            value.replace("<ENTITY>", "Selected Corporation")
            .replace("$WORKDIR", str(tmp_path))
            for value in command
        ]
        args = query_acris.build_parser().parse_args(command[1:])
        assert args.command == "party", "Single-target trace expanded to a batch operation"
        assert args.query == "Selected Corporation"


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(
    "skill",
    ("pursue-lead", "investigate-person", "trace-entity", "investigate-infra", "landscape-scan"),
)
def test_connection_examples_supply_valid_quoted_evidence(
    runtime, skill, monkeypatch
):
    """Quotes survive CLI parsing and every edge evidence ref has its own quote."""
    commands = [
        cmd for cmd in _commands(runtime, skill, "findings_tracker")
        if cmd[1] == "connect"
    ]
    assert commands
    captured = []

    def check_connection(**kwargs):
        refs = kwargs["evidence_ids"]
        quotes = kwargs["source_quotes"]
        assert refs
        assert set(quotes) == set(refs)
        for ref in refs:
            findings_tracker._validate_evidence_payload(
                ref, quotes[ref]["quote"], require_quote=True
            )
        captured.append(kwargs)
        return 1

    monkeypatch.setattr(findings_tracker, "add_connection", check_connection)
    for command in commands:
        command = [
            value.replace("<EVIDENCE_REF>", "https://example.org/source")
            .replace("<CERT_REF>", "https://example.org/certificate")
            .replace("<FINDING_ID>", "1")
            for value in command
        ]
        monkeypatch.setattr(sys, "argv", command)
        findings_tracker.main()
    assert len(captured) == len(commands)
