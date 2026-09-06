from __future__ import annotations

from typing import Any

import pytest

from tools import query_edva_bankruptcy
from tools import query_state_courts


def _shared_args(*values: str) -> Any:
    return query_state_courts.build_parser().parse_args(list(values))


def test_shared_routes_cover_read_only_docket_and_source_operations() -> None:
    routes = query_state_courts.LIVE_ROUTES[query_edva_bankruptcy.SOURCE_ID]

    assert set(routes) == {
        "case",
        "docket",
        "documents",
        "discovery",
        "probe",
    }
    assert "search" not in routes
    assert "download" not in routes

    exact_case = routes["case"].translate(
        _shared_args(
            "case",
            "05-39367",
            "--source",
            query_edva_bankruptcy.SOURCE_ID,
            "--court-id",
            query_edva_bankruptcy.COURT_ID,
            "--limit",
            "25",
            "--cursor",
            "edva-bankruptcy:v2:fixture",
        ),
        routes["case"].adapter_command,
    )
    assert exact_case.command == "case"
    assert exact_case.docket_number == "05-39367"
    assert exact_case.entry_limit == 25
    assert exact_case.cursor == "edva-bankruptcy:v2:fixture"

    for operation in ("docket", "documents"):
        translated = routes[operation].translate(
            _shared_args(
                operation,
                "49921079",
                "--source",
                query_edva_bankruptcy.SOURCE_ID,
                "--court-id",
                query_edva_bankruptcy.COURTLISTENER_COURT_ID,
                "--max-records",
                "40",
            ),
            routes[operation].adapter_command,
        )
        assert translated.command == "entries"
        assert translated.docket_id == 49921079
        assert translated.limit == 40
        assert translated.cursor is None

    discovery = routes["discovery"].translate(
        _shared_args(
            "discovery",
            "--source",
            query_edva_bankruptcy.SOURCE_ID,
        ),
        routes["discovery"].adapter_command,
    )
    probe = routes["probe"].translate(
        _shared_args(
            "probe",
            "--source",
            query_edva_bankruptcy.SOURCE_ID,
        ),
        routes["probe"].adapter_command,
    )
    assert discovery.command == "sources"
    assert probe.command == "probe"


def test_shared_docket_selector_requires_a_courtlistener_docket_id() -> None:
    route = query_state_courts.LIVE_ROUTES[
        query_edva_bankruptcy.SOURCE_ID
    ]["docket"]

    with pytest.raises(ValueError, match="CourtListener numeric docket ID"):
        route.translate(
            _shared_args(
                "docket",
                "05-39367",
                "--source",
                query_edva_bankruptcy.SOURCE_ID,
            ),
            route.adapter_command,
        )
    with pytest.raises(ValueError, match="must be positive"):
        route.translate(
            _shared_args(
                "docket",
                "0",
                "--source",
                query_edva_bankruptcy.SOURCE_ID,
            ),
            route.adapter_command,
        )


def test_shared_adapter_preserves_the_native_result_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = query_state_courts.LIVE_ROUTES[
        query_edva_bankruptcy.SOURCE_ID
    ]["documents"]
    translated = route.translate(
        _shared_args(
            "documents",
            "49921079",
            "--source",
            query_edva_bankruptcy.SOURCE_ID,
        ),
        route.adapter_command,
    )
    expected = object()
    observed: dict[str, Any] = {}

    def fake_execute(args: Any) -> object:
        observed["args"] = args
        return expected

    monkeypatch.setattr(query_edva_bankruptcy, "execute", fake_execute)

    result = route.adapter.execute(
        translated,
        access_decision={"allowed": True},
    )

    assert result is expected
    assert observed["args"].command == "entries"
    assert observed["args"].docket_id == 49921079


def test_source_guidance_keeps_archive_and_official_roles_distinct() -> None:
    guidance = query_state_courts._source_guidance(
        query_edva_bankruptcy.SOURCE_ID
    )

    assert guidance["unified_operations"] == [
        "case",
        "discovery",
        "docket",
        "documents",
        "probe",
    ]
    assert guidance["source_roles"] == {
        "courtlistener_recap": (
            "archive metadata and contributed or acquired documents"
        ),
        "pacer_ecf": "official docket and document access",
        "clerk": "official copy request",
    }
    assert "fetch" in guidance["note"]
    assert "empty official docket" in guidance["note"]
