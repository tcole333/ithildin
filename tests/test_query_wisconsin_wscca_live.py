from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tools import query_wisconsin_wscca


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for official-source probes",
)

SENTINEL_CASE = "2025AP000699"
SENTINEL_DOCUMENT = "994970"


def _execute(args: Any, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        query_wisconsin_wscca,
        "log_search",
        lambda *_args: None,
    )
    return query_wisconsin_wscca.execute(args)


def test_live_rss_returns_source_native_event_guids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = query_wisconsin_wscca.build_parser().parse_args(
        ["rss", SENTINEL_CASE, "--attempts", "1", "--minimum-interval", "0"]
    )

    payload = _execute(args, monkeypatch).to_dict()

    assert payload["status"] == "ok"
    assert len(payload["records"]) >= 20
    ids = {row["native_entry_id"] for row in payload["records"]}
    assert "19" in ids
    brief = next(
        row
        for row in payload["records"]
        if row["native_entry_id"] == "19"
    )
    assert brief["native_rss_guid"] == f"{SENTINEL_CASE}-19"
    assert any(
        url.endswith(f"/document/{SENTINEL_DOCUMENT}")
        for url in brief["linked_source_urls"]
    )


def test_live_exact_case_is_data_or_explicit_source_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WSCCA_BROWSER_TIMEOUT_MS", "30000")
    args = query_wisconsin_wscca.build_parser().parse_args(
        [
            "case",
            SENTINEL_CASE,
            "--attempts",
            "1",
            "--minimum-interval",
            "0",
            "--timeout",
            "60",
        ]
    )

    payload = _execute(args, monkeypatch).to_dict()

    assert payload["status"] in {"ok", "human_required"}
    if payload["status"] == "ok":
        case = payload["records"][0]
        assert case["raw_case_number"] == SENTINEL_CASE
        assert any(
            document["native_document_id"] == SENTINEL_DOCUMENT
            for document in case["documents"]
        )
    else:
        assert payload["records"] == []
        assert payload["errors"][0]["code"] == "source_validation_required"
        assert payload["errors"][0]["details"]["case_number"] == SENTINEL_CASE


def test_live_document_is_pdf_or_explicit_source_challenge(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("WSCCA_BROWSER_TIMEOUT_MS", "30000")
    destination = tmp_path / "wscca-994970.pdf"
    args = query_wisconsin_wscca.build_parser().parse_args(
        [
            "download",
            SENTINEL_CASE,
            SENTINEL_DOCUMENT,
            "--document-output",
            str(destination),
            "--attempts",
            "1",
            "--minimum-interval",
            "0",
            "--timeout",
            "60",
        ]
    )

    payload = _execute(args, monkeypatch).to_dict()

    assert payload["status"] in {"ok", "human_required"}
    if payload["status"] == "ok":
        artifact = payload["records"][0]
        assert destination.read_bytes().startswith(b"%PDF-")
        assert artifact["byte_count"] == destination.stat().st_size
        assert len(artifact["sha256"]) == 64
    else:
        assert not destination.exists()
        assert payload["errors"][0]["code"] == "source_validation_required"
