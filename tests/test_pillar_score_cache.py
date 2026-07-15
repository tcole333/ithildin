import sys

import pytest

from tools import pillar_tracker


def test_score_cache_uses_analysis_run_instead_of_fake_person(monkeypatch, tmp_path):
    calls = []
    output = tmp_path / "scores.json"

    monkeypatch.setattr(
        pillar_tracker,
        "start_analysis_run",
        lambda skill: calls.append(("start", skill)) or 41,
    )
    monkeypatch.setattr(
        pillar_tracker,
        "compute_scores",
        lambda **kwargs: calls.append(("compute", kwargs)) or [],
    )
    monkeypatch.setattr(
        pillar_tracker,
        "complete_analysis_run",
        lambda run_id, **kwargs: calls.append(("complete", run_id, kwargs)),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["pillar_tracker.py", "score", "--cache", "--output", str(output)],
    )

    pillar_tracker.main()

    assert calls == [
        ("start", "pillar_tracker:score"),
        ("compute", {"person_name": None, "top": 30, "run_id": 41}),
        ("complete", 41, {"notes": "Cached 0 orchestrator score rows"}),
    ]


def test_score_cache_marks_analysis_run_failed(monkeypatch):
    failures = []
    monkeypatch.setattr(pillar_tracker, "start_analysis_run", lambda _skill: 42)
    monkeypatch.setattr(
        pillar_tracker,
        "compute_scores",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("score failed")),
    )
    monkeypatch.setattr(
        pillar_tracker,
        "fail_analysis_run",
        lambda run_id, message: failures.append((run_id, message)),
    )
    monkeypatch.setattr(sys, "argv", ["pillar_tracker.py", "score", "--cache"])

    with pytest.raises(RuntimeError, match="score failed"):
        pillar_tracker.main()

    assert failures == [(42, "score failed")]
