from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from tools.search_reuse import check_reusable, record_result


@pytest.fixture
def search(tmp_path):
    artifact = tmp_path / "results.json"
    artifact.write_text('{"results": []}')
    return {
        "request": {"source": "fixture", "operation": "search", "query": "Example",
                    "filters": {"jurisdiction": "ny", "limit": 25}},
        "artifact": artifact, "db_path": tmp_path / "scratch.db",
        "now": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


def record(search, **overrides):
    args = {**search, "outcome": "success", "result_count": 0, **overrides}
    request = args.pop("request")
    record_result(request, **args)


def check(search, **overrides):
    args = {key: value for key, value in search.items() if key != "artifact"}
    args.update(max_age_seconds=86400)
    args.update(overrides)
    request = args.pop("request")
    return check_reusable(request, **args)


def test_zero_result_reuses_only_fresh_successful_scope(search):
    record(search)
    assert check(search)["reusable"]
    assert not check(search, now=search["now"] + timedelta(days=2))["reusable"]
    for changed in (
        {**search["request"], "operation": "officers"},
        {**search["request"], "filters": {"jurisdiction": "fl", "limit": 25}},
        {**search["request"], "filters": {"jurisdiction": "ny", "limit": 50}},
    ):
        assert not check(search, request=changed)["reusable"]


def test_filter_order_does_not_change_identity(search):
    record(search)
    request = {**search["request"], "filters": {"limit": 25, "jurisdiction": "ny"}}
    assert check(search, request=request)["reusable"]


def test_static_corpus_requires_exact_version(search):
    request = {**search["request"], "source_version": "sha256:fixture-v1"}
    record(search, request=request)
    assert check(search, request=request, max_age_seconds=None,
                 now=search["now"] + timedelta(days=800))["reusable"]
    assert not check(search, request={**request, "source_version": "sha256:fixture-v2"},
                     max_age_seconds=None)["reusable"]
    assert not check(search)["reusable"]


def test_dynamic_source_without_freshness_is_never_reused(search):
    record(search)
    assert not check(search, max_age_seconds=None)["reusable"]
    assert not check(search, now=search["now"] - timedelta(hours=1))["reusable"]


@pytest.mark.parametrize("outcome", ["failed", "partial", "unavailable"])
def test_incomplete_latest_attempt_invalidates_old_success(search, outcome):
    record(search)
    record(search, outcome=outcome, artifact=None, result_count=None)
    result = check(search)
    assert not result["reusable"]
    assert outcome in result["reason"]


def test_changed_or_deleted_artifact_cannot_be_reused(search):
    record(search)
    search["artifact"].write_text('{"error": "access denied"}')
    assert not check(search)["reusable"]
    search["artifact"].unlink()
    assert not check(search)["reusable"]


def test_legacy_history_is_not_a_cache_hit(search):
    with sqlite3.connect(search["db_path"]) as db:
        db.execute("CREATE TABLE search_log(query_text, source, result_count)")
        db.execute("INSERT INTO search_log VALUES('Example', 'fixture', 0)")
    assert not check(search)["reusable"]
    with sqlite3.connect(search["db_path"]) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='search_reuse'").fetchone() is None


def test_invalid_success_cannot_create_reuse_record(search):
    with pytest.raises(ValueError, match="count and an existing"):
        record(search, artifact=None)
    assert not search["db_path"].exists()
    with pytest.raises(ValueError, match="nonnegative integer"):
        record(search, result_count=-1)


def test_db_override_is_respected(search, monkeypatch):
    monkeypatch.setenv("ITHILDIN_DB_PATH", str(search["db_path"]))
    record(search, db_path=None)
    assert check(search, db_path=None)["reusable"]
