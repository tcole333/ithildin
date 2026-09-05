"""Persistent transport framing/cleanup and raw-checkpoint recovery, without Chrome."""

import json
from pathlib import Path
import sys

import pytest

from tools import query_massachusetts_ucc as ucc


FIXTURES = Path(__file__).parent / "fixtures/massachusetts_ucc"


def fake_command(tmp_path, mode="normal"):
    program = tmp_path / "helper.py"
    fixture = FIXTURES / "empty.html"
    program.write_text(f'''
import json,os,sys,time
from pathlib import Path
for line in sys.stdin:
    request=json.loads(line)
    mode={mode!r}
    if mode == "timeout": time.sleep(30)
    if mode == "eof": sys.exit(1)
    if mode == "badjson": print("invalid",flush=True); continue
    sys.stderr.write("diagnostic " * 100000);sys.stderr.flush()
    payload=request["request"]
    raw={{"request_id":request["request_id"],"ok":True,
          "pages":[{{"html":Path({str(fixture)!r}).read_text(),
                    "url":"https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx"}}],
          "submitted":{{"limit":25,"search_type":"begins","role":"debtor",**payload}},
          "runtime":{{"pid":os.getpid()}},"captured_at":"2026-09-03T00:00:00Z"}}
    if mode == "wrongid": raw["request_id"]="not-the-request"
    if mode == "stale": raw["submitted"]["query"]="A DIFFERENT NAME"
    if mode == "challenge": raw={{"ok":False,"request_id":request["request_id"],"error":"access challenge"}}
    print(json.dumps(raw),flush=True)
''')
    return [sys.executable, str(program)]


def test_one_process_multiple_results_and_large_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(ucc, "log_search", lambda *_: None)
    with ucc.BrowserSession(2, command=fake_command(tmp_path)) as session:
        for index, name in enumerate(["FIRST", "SECOND"]):
            result = session.execute({"command": "search-org", "query": name, "limit": 25},
                                     tmp_path / f"raw-{index}.json")
            assert result["returned"] == 0
            assert Path(result["transport_capture"]["source_file"]).is_file()
        first, second = [json.loads((tmp_path / f"raw-{i}.json").read_text())["raw"] for i in range(2)]
        assert first["runtime"]["pid"] == second["runtime"]["pid"]
        process = session.process
        with pytest.raises(ucc.PortalError, match="limit"):
            session.execute({"command": "search-org", "query": "THIRD"}, tmp_path / "third.json")
    assert process.poll() is not None
    assert not (tmp_path / "third.json").exists()


@pytest.mark.parametrize("mode,match", [("wrongid", "ID mismatch"), ("badjson", "JSONL"),
                                        ("eof", "ended"), ("stale", "parameters differ"),
                                        ("challenge", "access challenge")])
def test_protocol_or_source_failure_closes_session(tmp_path, monkeypatch, mode, match):
    monkeypatch.setattr(ucc, "log_search", lambda *_: pytest.fail("Failed source must not enter search log"))
    session = ucc.BrowserSession(command=fake_command(tmp_path, mode))
    with pytest.raises(ucc.PortalError, match=match):
        session.execute({"command": "search-org", "query": "EXPECTED", "limit": 25}, tmp_path / "raw.json")
    assert session.process is None
    if mode in {"stale", "challenge"}:
        assert (tmp_path / "raw.json").exists()  # Preserve attributable failure response too.


def test_raw_recovery_uses_original_capture_timestamp_and_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(ucc, "log_search", lambda *_: None)
    payload = {"command": "search-org", "query": "TEST", "limit": 25}
    raw_path = tmp_path / "raw.json"
    with ucc.BrowserSession(command=fake_command(tmp_path)) as session:
        session.execute(payload, raw_path)
    recovered = ucc.recover_transport(raw_path, payload)
    assert recovered["retrieved_at"] == "2026-09-03T00:00:00Z"
    assert recovered["reported_count"] == 0
    with pytest.raises(ucc.PortalError, match="checkpoint query"):
        ucc.recover_transport(raw_path, {**payload, "lapsed": True})


def test_stale_source_criteria_rejected_even_with_correct_protocol_id(monkeypatch):
    monkeypatch.setattr(ucc, "log_search", lambda *_: pytest.fail("Stale page must not log"))
    with pytest.raises(ucc.PortalError, match="organization differs"):
        ucc.parse_response({"command": "search-org", "query": "NOT HARVARD", "limit": 25}, {
            "ok": True, "pages": [{"html": (FIXTURES / "search-1.html").read_text(),
                                     "url": "https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx"}],
        })
