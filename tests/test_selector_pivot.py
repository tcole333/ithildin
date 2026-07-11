"""Tests for the selector-pivot orchestrator.

Covers the deterministic logic: selector typing, adapter routing + paid/leak
gating, dry-run write-safety, and normalization (via a monkeypatched runner so
no network or subprocess is touched).
"""
from __future__ import annotations

import pytest

from tools.selector_pivot import (
    ADAPTERS,
    CandidateEntity,
    PivotRecord,
    detect_selector_type,
    emit,
    select_adapters,
    _prepare_workdir,
    _norm_dehashed,
    _norm_opensanctions,
)


@pytest.mark.parametrize("value,expected", [
    ("jane@example.com", "email"),
    ("192.168.0.1", "ip"),
    ("acme-corp.com", "domain"),
    ("Vladimir Putin", "name"),
    ("0x" + "a" * 40, "eth"),
    ("jdoe_99", "username"),
])
def test_detect_selector_type(value, expected):
    assert detect_selector_type(value) == expected


def test_select_adapters_routes_by_type():
    names = {a.name for a in select_adapters("company", enable_paid=False)}
    assert {"opensanctions", "gleif", "icij", "littlesis"} <= names
    # crtsh/maigret handle domain/username, not company
    assert "crtsh" not in names and "maigret" not in names


def test_paid_and_leak_adapters_are_gated():
    free = {a.name for a in select_adapters("email", enable_paid=False)}
    paid = {a.name for a in select_adapters("email", enable_paid=True)}
    assert "intelx" not in free and "dehashed" not in free
    assert {"intelx", "dehashed"} <= paid


def test_paid_adapter_availability_follows_env(monkeypatch):
    by_name = {a.name: a for a in ADAPTERS}
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    monkeypatch.delenv("INTELX_API_KEY", raising=False)
    assert by_name["dehashed"].available()[0] is False
    assert by_name["intelx"].available()[0] is False
    monkeypatch.setenv("DEHASHED_API_KEY", "k")
    assert by_name["dehashed"].available()[0] is True
    # Both are flagged leak_class so emission applies the leak-aggregator stamp.
    assert by_name["dehashed"].leak_class and by_name["intelx"].leak_class


def test_norm_dehashed_harvests_linked_selectors_and_entities(monkeypatch):
    canned = {"entries": [
        {"id": "1", "email": ["a@x.com"], "username": ["alice"], "phone": ["555"],
         "name": ["Alice Doe"], "ip_address": ["1.2.3.4"], "database_name": "BreachX"},
        {"id": "2", "email": "null", "username": ["bob"], "name": "null",
         "database_name": "BreachY"},
    ]}
    monkeypatch.setenv("DEHASHED_API_KEY", "testkey")
    monkeypatch.setattr("tools.selector_pivot._run_tool",
                        lambda argv, wd, timeout=150: (canned, None))
    rec = _norm_dehashed("seed@x.com", "email", "/tmp")
    assert rec.source == "dehashed" and rec.leak_class is True and rec.error is None
    links = set(rec.linked_selectors)
    assert ("a@x.com", "email") in links
    assert ("alice", "username") in links and ("bob", "username") in links
    assert ("555", "phone") in links and ("1.2.3.4", "ip") in links
    # "null" string fields are skipped, not emitted as selectors/entities
    names = {e.name for e in rec.entities}
    assert "Alice Doe" in names and "null" not in names
    assert all(e.entity_type == "person" for e in rec.entities)


def test_norm_dehashed_requires_key(monkeypatch):
    monkeypatch.delenv("DEHASHED_API_KEY", raising=False)
    rec = _norm_dehashed("x@y.com", "email", "/tmp")
    assert rec.error == "no DEHASHED_API_KEY"


def test_emit_dry_run_makes_no_db_writes():
    rec = PivotRecord("opensanctions", "Acme", "company")
    rec.entities.append(CandidateEntity(name="Acme Subsidiary", entity_type="company"))
    out = emit([rec], profile_id="test", dry_run=True)
    assert out["dry_run"] is True
    assert out["leads"] == []
    assert out["entities"][0]["action"] == "DRY_RUN"


def test_prepare_workdir_creates_caller_supplied_directory(tmp_path):
    requested = tmp_path / "nested" / "pivot"
    assert not requested.exists()
    assert _prepare_workdir(requested) == str(requested)
    assert requested.is_dir()


def test_norm_opensanctions_parses(monkeypatch):
    canned = [{
        "id": "NK-1", "caption": "ACME OOO", "schema": "Company",
        "countries": ["ru"], "topics": ["sanction"], "names": ["ACME"],
        "properties": {},
    }]
    monkeypatch.setattr("tools.selector_pivot._run_tool",
                        lambda argv, wd, timeout=150: (canned, None))
    rec = _norm_opensanctions("ACME", "company", "/tmp")
    assert rec.source == "opensanctions"
    assert rec.error is None
    assert rec.entities[0].name == "ACME OOO"
    assert rec.entities[0].entity_type == "company"
    assert rec.entities[0].jurisdiction == "ru"
    assert "sanction" in rec.entities[0].tags


def test_norm_opensanctions_handles_tool_error(monkeypatch):
    monkeypatch.setattr("tools.selector_pivot._run_tool",
                        lambda argv, wd, timeout=150: (None, "boom"))
    rec = _norm_opensanctions("ACME", "company", "/tmp")
    assert rec.error == "boom"
    assert rec.entities == []
