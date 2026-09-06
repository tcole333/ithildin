import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from scripts import dispatcher
from tests.test_extract_sec_enforcement_parties import _create_source_database, _mention, _record
from tools import extract_sec_enforcement_parties as extraction


def test_dispatcher_inherits_model_without_changing_safety_limits():
    command = dispatcher.ClaudeBackend().build_command("task", dispatcher.DEFAULT_CONFIG, [])
    assert "--model" not in command
    assert "--permission-mode" in command
    assert "--allowedTools" in command
    assert dispatcher.DEFAULT_CONFIG["timeout_seconds"] == 3600
    assert dispatcher.DEFAULT_CONFIG["daily_budget_usd"] == 50.0
    config = json.loads(dispatcher.CONFIG_PATH.read_text())
    assert config["model"] is None
    override = dispatcher.deep_merge(dispatcher.DEFAULT_CONFIG, {"model": "chosen-model"})
    command = dispatcher.ClaudeBackend().build_command("task", override, [])
    assert command[command.index("--model") + 1] == "chosen-model"


def test_extraction_model_selection_preserves_explicit_and_configured_choices(tmp_path):
    (tmp_path / "config.toml").write_text('model = "configured-model"\n[features]\nhooks = true\n')
    environment = {"CODEX_HOME": str(tmp_path)}
    configured = extraction.resolve_model_selection(None, environ=environment)
    assert configured == {
        "requested_model": None, "selected_model": "configured-model",
        "selection_source": "user_config", "resolved_model": None,
    }
    explicit = extraction.resolve_model_selection("explicit-model", environ=environment)
    assert explicit["selected_model"] == "explicit-model"
    assert explicit["selection_source"] == "explicit"
    assert explicit["resolved_model"] is None


def test_no_configured_model_is_reported_as_unresolved_runtime_default(tmp_path):
    result = extraction.resolve_model_selection(None, environ={"CODEX_HOME": str(tmp_path)})
    assert result == {
        "requested_model": None, "selected_model": None,
        "selection_source": "runtime_default", "resolved_model": None,
    }


@pytest.mark.parametrize("contents", ['model = 10\n', 'model = "bad;model"\n', 'secret = "unterminated'])
def test_invalid_config_fails_without_exposing_contents(tmp_path, contents):
    (tmp_path / "config.toml").write_text(contents)
    with pytest.raises(extraction.PartyExtractionError) as error:
        extraction.resolve_model_selection(None, environ={"CODEX_HOME": str(tmp_path)})
    assert contents not in str(error.value)


@pytest.mark.parametrize("model", [None, "explicit-model"])
def test_codex_default_omits_model_flag_and_retains_isolation(monkeypatch, model):
    calls = []
    monkeypatch.setattr(extraction, "codex_auth_and_version", lambda **kw: ("chatgpt", "test", {}))

    def run(args, **kwargs):
        calls.append(args)
        response = Path(args[args.index("--output-last-message") + 1])
        response.write_text('{"records": []}')
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(extraction, "_run_command", run)
    result = extraction.run_codex_batch([], model=model, reasoning_effort="medium", codex_binary="codex")
    assert result.output == {"records": []}
    command = calls[0]
    if model is None:
        assert "--model" not in command
    else:
        assert command[command.index("--model") + 1] == model
    for flag in ("--ignore-user-config", "--ignore-rules", "--strict-config", "--ephemeral"):
        assert flag in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    pairs = set(zip(command, command[1:]))
    assert all(("--disable", feature) in pairs for feature in extraction.DISABLED_CODEX_FEATURES)


@pytest.mark.parametrize("configured", [False, True])
def test_runtime_default_provenance_is_persisted_and_unknown_choice_not_cached(tmp_path, monkeypatch, configured):
    source = tmp_path / "source.db"
    sidecar = tmp_path / "sidecar.db"
    _create_source_database(source)
    extraction.prepare_inputs(source_db_path=source, sidecar_db_path=sidecar, mode="all", sample_size=0)
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    if configured:
        codex_home.mkdir()
        (codex_home / "config.toml").write_text('model = "configured-model"\n')
    selected_model = "configured-model" if configured else None

    def run(evidence_records, **kwargs):
        assert kwargs["model"] == selected_model
        output = {"records": [
            _record(evidence, [
                _mention("Goldman, Sachs & Co.", party_type="entity"),
                _mention("Fabrice Tourre"),
            ]) for evidence in evidence_records
        ]}
        return extraction.CodexBatchResult(
            output=output, raw_text=json.dumps(output), exit_code=0,
            error_text=None, cli_version="test", auth_mode="chatgpt",
        )

    monkeypatch.setattr(extraction, "run_codex_batch", run)
    first = extraction.run_extractions(sidecar_db_path=sidecar)
    second = extraction.run_extractions(sidecar_db_path=sidecar)
    assert first["model"] == selected_model
    assert first["model_selection"]["resolved_model"] is None
    assert first["attempt_count"] == 1
    assert second["attempt_count"] == (0 if configured else 1)
    assert second["cache_hit_count"] == (1 if configured else 0)
    with sqlite3.connect(sidecar) as db:
        recorded, validation = db.execute(
            "SELECT model_name, validation_json FROM party_extraction_attempt LIMIT 1"
        ).fetchone()
    assert recorded == (selected_model or extraction.UNRESOLVED_RUNTIME_MODEL)
    assert json.loads(validation)["execution_context"]["model_selection"] == first["model_selection"]
