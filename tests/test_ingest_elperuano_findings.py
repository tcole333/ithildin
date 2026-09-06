"""Synthetic ingestion checks: source quotes survive the real tracker CLI parser."""

import importlib
import json
import sqlite3
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from tools.findings_tracker import _parse_source_quote_args
from tools import findings_tracker, investigation_context, lead_tracker


@pytest.fixture
def ingestion(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "tools"))
    return importlib.import_module("ingest_elperuano")


@pytest.fixture
def document():
    return {
        "op": "2493140-1",
        "source": "elperuano",
        "metadata": {
            "nombreDispositivo": "001-2026-DE",
            "tipoDispositivo": "DECRETO SUPREMO",
            "fechaPublicacion": "2026-04-27",
            "sumilla": "Aprueban el convenio: cooperación técnica\nentre instituciones.",
        },
        "landingUrl": "https://busquedas.elperuano.pe/dispositivo/NL/2493140-1",
        "visorUrl": "https://busquedas.elperuano.pe/api/visor_html/2493140-1",
        "fullText": "Artículo 1.- Apruébase el convenio de cooperación técnica.",
        "visorHtml": "<p>Artículo 1.- Apruébase el convenio de cooperación técnica.</p>",
    }


def run_ingest(monkeypatch, ingestion, document, output, extra=()):
    monkeypatch.setattr(ingestion, "_fetch_one", lambda *_: document)
    monkeypatch.setattr(sys, "argv", [
        "ingest_elperuano.py", document["op"], "--output", str(output),
        "--finding", "Synthetic public document", *extra,
    ])
    ingestion.main()


def capture_tracker(monkeypatch, ingestion, *, returncode=0):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, returncode, "Created finding #1", "rejected evidence" if returncode else "")

    monkeypatch.setattr(ingestion.subprocess, "run", run)
    return calls


def parsed_evidence(command):
    refs = command[command.index("--evidence") + 1:command.index("--claim-type")]
    quote_args = command[command.index("--source-quote") + 1:command.index("--sources")]
    return refs, _parse_source_quote_args(quote_args, refs)


def test_cli_maps_verbatim_sumilla_to_its_source_and_preserves_output(
    monkeypatch, ingestion, document, tmp_path, capsys,
):
    calls = capture_tracker(monkeypatch, ingestion)
    output = tmp_path / "document.json"
    run_ingest(monkeypatch, ingestion, document, output)

    assert len(calls) == 1
    refs, quotes = parsed_evidence(calls[0])
    assert refs == [document["landingUrl"]]
    assert quotes == {refs[0]: {"quote": document["metadata"]["sumilla"]}}
    saved = json.loads(output.read_text())
    assert saved["metadata"] == document["metadata"]
    assert saved["fullText"] == document["fullText"]
    assert saved["landingUrl"] == document["landingUrl"]
    assert "Created finding #1" in capsys.readouterr().err


@pytest.mark.parametrize("explicit", [False, True])
def test_body_excerpt_uses_actual_visor_source(
    monkeypatch, ingestion, document, tmp_path, explicit,
):
    calls = capture_tracker(monkeypatch, ingestion)
    extra = ("--quote", "Apruébase el convenio") if explicit else ()
    if not explicit:
        document["metadata"]["sumilla"] = ""
    run_ingest(monkeypatch, ingestion, document, tmp_path / "document.json", extra)
    refs, quotes = parsed_evidence(calls[0])
    assert refs == [document["visorUrl"]]
    expected = extra[1] if explicit else document["fullText"]
    assert quotes == {refs[0]: {"quote": expected}}


@pytest.mark.parametrize("quote,empty_source,error", [
    (None, True, "nonblank quote"),
    ("  \n ", False, "nonblank quote"),
    ("Invented quotation", False, "does not occur"),
])
def test_invalid_quote_fails_before_tracker_and_keeps_fetched_artifact(
    monkeypatch, ingestion, document, tmp_path, capsys, quote, empty_source, error,
):
    calls = capture_tracker(monkeypatch, ingestion)
    if empty_source:
        document["metadata"]["sumilla"] = " \n "
        document["fullText"] = " \n "
    output = tmp_path / "document.json"
    extra = ("--quote", quote) if quote is not None else ()
    with pytest.raises(SystemExit) as exc:
        run_ingest(monkeypatch, ingestion, document, output, extra)
    assert exc.value.code == 1
    assert not calls
    assert json.loads(output.read_text())["metadata"] == document["metadata"]
    assert error in capsys.readouterr().err


def test_tracker_failure_is_reported_as_cli_failure_and_preserves_document(
    monkeypatch, ingestion, document, tmp_path, capsys,
):
    capture_tracker(monkeypatch, ingestion, returncode=2)
    output = tmp_path / "document.json"
    with pytest.raises(SystemExit) as exc:
        run_ingest(monkeypatch, ingestion, document, output)
    assert exc.value.code == 1
    assert json.loads(output.read_text())["fullText"] == document["fullText"]
    assert "findings_tracker exit 2: rejected evidence" in capsys.readouterr().err


def test_ingestion_command_persists_quote_through_real_tracker_cli(
    monkeypatch, ingestion, document, tmp_path,
):
    db_path = tmp_path / "findings.db"
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(db_path))
    monkeypatch.setenv("ITHILDIN_PROFILE", "producer-fixture")
    for module in (findings_tracker, investigation_context, lead_tracker):
        monkeypatch.setattr(module, "DB_PATH", db_path)
    monkeypatch.setattr(findings_tracker, "_schema_initialized", True)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        lead_tracker._ensure_schema(db)

    def run_tracker(command, **kwargs):
        stdout, stderr = StringIO(), StringIO()
        returncode = 0
        with monkeypatch.context() as invocation:
            invocation.setattr(sys, "argv", command[3:])
            with redirect_stdout(stdout), redirect_stderr(stderr):
                try:
                    findings_tracker.main()
                except SystemExit as exc:
                    returncode = exc.code
        return subprocess.CompletedProcess(command, returncode, stdout.getvalue(), stderr.getvalue())

    monkeypatch.setattr(ingestion.subprocess, "run", run_tracker)
    run_ingest(monkeypatch, ingestion, document, tmp_path / "document.json")

    with sqlite3.connect(db_path) as db:
        assert db.execute(
            "SELECT claim_type,confidence,verification_status,source_datasets,profile_id FROM findings"
        ).fetchall() == [("direct_quote", "confirmed", "unverified", '["elperuano"]', "producer-fixture")]
        assert db.execute(
            "SELECT evidence_ref,source_quote FROM finding_evidence"
        ).fetchall() == [(document["landingUrl"], document["metadata"]["sumilla"])]
