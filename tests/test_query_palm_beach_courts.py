from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools import query_palm_beach_courts
from tools.ingest_state_court_records import ingest_envelope, validate_envelope


FIXTURE_DIR = Path("tests/fixtures/public_records/palm_beach_courts")
HELPER_PATH = Path("tools/_pbc_court_browser_helper.js")
SEARCH_PAYLOAD = json.loads(
    (FIXTURE_DIR / "search_results.json").read_text(encoding="utf-8")
)
CASE_PAYLOAD = json.loads(
    (FIXTURE_DIR / "case_bundle.json").read_text(encoding="utf-8")
)
DOWNLOAD_PAYLOAD = json.loads(
    (FIXTURE_DIR / "download_receipt.json").read_text(encoding="utf-8")
)


class FakeRunner:
    def __init__(
        self,
        *,
        search: Mapping[str, Any] | None = None,
        case: Mapping[str, Any] | None = None,
        download: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.search = copy.deepcopy(search or SEARCH_PAYLOAD)
        self.case = copy.deepcopy(case or CASE_PAYLOAD)
        self.download = copy.deepcopy(download or DOWNLOAD_PAYLOAD)
        self.error = error
        self.calls: list[tuple[list[str], float]] = []

    def __call__(
        self,
        arguments: Sequence[str],
        timeout: float,
    ) -> Mapping[str, Any]:
        args = list(arguments)
        self.calls.append((args, timeout))
        if self.error is not None:
            raise self.error
        if args[0] == "search":
            return copy.deepcopy(self.search)
        if args[0] == "case":
            return copy.deepcopy(self.case)
        if args[0] == "download":
            return copy.deepcopy(self.download)
        if args[0] == "runtime-check":
            return {
                "ok": True,
                "node": "v22.0.0",
                "playwright_module": "playwright",
                "browser_channel": "chrome",
            }
        if args[0] == "probe":
            return {
                "ok": True,
                "source_url": query_palm_beach_courts.SEARCH_URL,
                "case_search_box_count": 1,
                "party_search_box_count": 1,
            }
        raise AssertionError(f"unexpected helper operation: {args}")


def _parse(*values: str) -> Any:
    return query_palm_beach_courts.build_parser().parse_args(list(values))


def _execute(args: Any, monkeypatch: Any, runner: FakeRunner | None = None):
    monkeypatch.setattr(
        query_palm_beach_courts,
        "log_search",
        lambda *_args: None,
    )
    return query_palm_beach_courts.execute(
        args,
        helper_runner=runner or FakeRunner(),
    )


def test_search_normalizes_case_identity_court_level_and_all_displayed_rows(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()

    result = _execute(_parse("search", "KRAFT"), monkeypatch, runner)
    payload = result.to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert payload["next_cursor"] is None
    assert len(payload["records"]) == 3
    county, circuit, fallback = payload["records"]
    assert county["raw_case_number"] == "50-2019-MM-002346-AXXX-NB"
    assert county["source_internal_id"] == county["raw_case_number"]
    assert county["court"]["court_id"] == (
        query_palm_beach_courts.COUNTY_COURT_ID
    )
    assert county["filing_date"] == "2019-02-25"
    assert county["arrest_date"] == "2019-02-26"
    assert circuit["court"]["court_id"] == (
        query_palm_beach_courts.CIRCUIT_COURT_ID
    )
    assert fallback["court"]["court_id"] == (
        query_palm_beach_courts.GENERIC_COURT_ID
    )
    assert runner.calls == (
        [
            (
                [
                    "search",
                    "KRAFT",
                    "--scope",
                    "party",
                    "--mode",
                    "exact",
                ],
                300,
            )
        ]
    )


def test_search_paginates_displayed_rows_without_an_adapter_total_cap(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()

    first = _execute(
        _parse("search", "KRAFT", "--limit", "2"),
        monkeypatch,
        runner,
    ).to_dict()
    second = _execute(
        _parse(
            "search",
            "KRAFT",
            "--limit",
            "2",
            "--cursor",
            "pbc:search:offset:2",
        ),
        monkeypatch,
        runner,
    ).to_dict()

    assert len(first["records"]) == 2
    assert first["next_cursor"] == "pbc:search:offset:2"
    assert len(second["records"]) == 1
    assert second["next_cursor"] is None


def test_source_ceiling_is_explicit_partial_not_a_silent_truncation(
    monkeypatch: Any,
) -> None:
    source_row = SEARCH_PAYLOAD["records"][0]
    search = {
        **SEARCH_PAYLOAD,
        "total_reported": 200,
        "source_ceiling_reached": True,
        "records": [
            {
                **source_row,
                "Case Number": f"50-2019-MM-{index:06d}-AXXX-NB",
            }
            for index in range(200)
        ],
    }

    payload = _execute(
        _parse("search", "SMITH", "--limit", "25"),
        monkeypatch,
        FakeRunner(search=search),
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "partial"
    assert len(payload["records"]) == 25
    assert payload["next_cursor"] == "pbc:search:offset:25"
    assert payload["errors"][0]["code"] == "source_result_ceiling"
    assert payload["errors"][0]["details"]["source_result_ceiling"] == 200


def test_case_preserves_actors_docket_states_charges_and_events(
    monkeypatch: Any,
) -> None:
    payload = _execute(
        _parse("case", "50-2019-MM-002346-AXXX-NB"),
        monkeypatch,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    case = payload["records"][0]
    assert case["source_access_level"] == "D"
    assert case["access_state"] == "public"
    assert case["parties"][0]["raw_name"] == "ROBERT KRAFT"
    assert case["parties"][0]["role"] == "defendant"
    assert [attorney["source_role"] for attorney in case["attorneys"]] == [
        "Defense Attorney",
        "State Attorney",
    ]
    assert case["judicial_assignments"][0]["officer"]["raw_name"] == (
        "LEONARD HANSSEN"
    )
    assert len(case["docket_entries"]) == 4
    public, requested, processing, absent = case["docket_entries"]
    assert public["native_entry_id"] == (
        "50-2019-MM-002346-AXXX-NB:5"
    )
    assert public["access_state"] == "public"
    assert public["documents"][0]["access_state"] == "public"
    assert public["documents"][0]["native_document_id"] == (
        "50-2019-MM-002346-AXXX-NB:5"
    )
    assert requested["access_state"] == "public"
    assert requested["documents"][0]["access_state"] == "restricted"
    assert requested["documents"][0]["source_access_state"] == (
        "view_on_request"
    )
    assert processing["documents"][0]["source_access_state"] == (
        "view_on_request_in_process"
    )
    assert absent["document_available"] is False
    assert absent["source_document_state"] == "not_available_online"
    assert absent["documents"] == []
    assert [charge["disposition"] for charge in case["charges"]] == [
        "NOLLE PROSSE",
        "NOLLE PROSSE",
    ]
    assert [event["event_type"] for event in case["case_events"]] == [
        "court_event",
        "charge",
        "charge",
    ]


def test_case_envelope_round_trips_through_court_ingest(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    envelope = _execute(
        _parse("case", "50-2019-MM-002346-AXXX-NB"),
        monkeypatch,
    ).to_dict()
    court_db = tmp_path / "courts.db"

    first = ingest_envelope(envelope, court_db=court_db)
    second = ingest_envelope(envelope, court_db=court_db)

    assert first["projected"] == {
        "courts": 1,
        "related_courts": 0,
        "cases": 1,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 1,
        "attorneys": 2,
        "representations": 0,
        "judicial_officers": 1,
        "assignments": 1,
        "claims": 0,
        "docket_entries": 4,
        "case_events": 3,
        "documents": 3,
        "restriction_events": 0,
    }
    assert second["canonical_refs"] == first["canonical_refs"]
    db = sqlite3.connect(court_db)
    try:
        case_row = db.execute(
            "SELECT access_state FROM case_record"
        ).fetchone()
        docket_states = db.execute(
            "SELECT DISTINCT access_state FROM docket_entry"
        ).fetchall()
        document_states = db.execute(
            """
            SELECT access_state, native_access_state
            FROM document_artifact
            ORDER BY native_document_id
            """
        ).fetchall()
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "case_record",
                "case_party",
                "attorney",
                "judicial_officer",
                "docket_entry",
                "case_event",
                "document_artifact",
            )
        }
    finally:
        db.close()
    assert case_row == ("public",)
    assert docket_states == [("public",)]
    assert document_states == [
        ("public", "View image"),
        ("restricted", "View On Request"),
        ("restricted", "View On Request In Process"),
    ]
    assert counts == {
        "case_record": 1,
        "case_party": 1,
        "attorney": 2,
        "judicial_officer": 1,
        "docket_entry": 4,
        "case_event": 3,
        "document_artifact": 3,
    }


def test_docket_and_documents_page_source_entries(
    monkeypatch: Any,
) -> None:
    docket = _execute(
        _parse(
            "docket",
            "50-2019-MM-002346-AXXX-NB",
            "--limit",
            "2",
        ),
        monkeypatch,
    ).to_dict()
    documents = _execute(
        _parse(
            "documents",
            "50-2019-MM-002346-AXXX-NB",
            "--limit",
            "2",
            "--cursor",
            "pbc:documents:offset:2",
        ),
        monkeypatch,
    ).to_dict()

    assert docket["next_cursor"] == "pbc:docket:offset:2"
    assert len(docket["records"][0]["docket_entries"]) == 2
    assert documents["next_cursor"] is None
    assert [
        entry["sequence_no"]
        for entry in documents["records"][0]["docket_entries"]
    ] == ["7", "8"]
    assert documents["records"][0]["source_document_count"] == 3


def test_download_returns_ingestible_document_and_artifact_reference(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()
    payload = _execute(
        _parse(
            "download",
            "50-2019-MM-002346-AXXX-NB",
            "5",
            "/tmp/502019MM002346AXXXNB-5.pdf",
        ),
        monkeypatch,
        runner,
    ).to_dict()
    validate_envelope(payload)

    assert payload["status"] == "ok"
    assert payload["raw_artifact_refs"] == [
        "/tmp/502019MM002346AXXXNB-5.pdf"
    ]
    document = payload["records"][0]["documents"][0]
    assert document["native_document_id"].endswith(":5")
    assert document["sha256"] == DOWNLOAD_PAYLOAD["sha256"]
    assert document["mime_type"] == "application/pdf"
    assert runner.calls[0][0] == [
        "download",
        "50-2019-MM-002346-AXXX-NB",
        "5",
        "/tmp/502019MM002346AXXXNB-5.pdf",
    ]


def test_document_state_failures_and_not_found_are_explicit(
    monkeypatch: Any,
) -> None:
    restricted = _execute(
        _parse(
            "download",
            "50-2019-MM-002346-AXXX-NB",
            "6",
            "/tmp/din-6.pdf",
        ),
        monkeypatch,
        FakeRunner(
            error=query_palm_beach_courts.PalmBeachBrowserError(
                "DIN 6 is view on request",
                error_type="DocumentStateError",
                document_state="view_on_request",
            )
        ),
    ).to_dict()
    unavailable = _execute(
        _parse(
            "download",
            "50-2019-MM-002346-AXXX-NB",
            "8",
            "/tmp/din-8.pdf",
        ),
        monkeypatch,
        FakeRunner(
            error=query_palm_beach_courts.PalmBeachBrowserError(
                "DIN 8 is not available online",
                error_type="DocumentStateError",
                document_state="not_available_online",
            )
        ),
    ).to_dict()
    missing = _execute(
        _parse("case", "50-1900-MM-000001-AXXX-NB"),
        monkeypatch,
        FakeRunner(
            error=query_palm_beach_courts.PalmBeachBrowserError(
                "case not found",
                error_type="DocumentStateError",
                document_state="case_not_found",
            )
        ),
    ).to_dict()

    assert restricted["status"] == "restricted"
    assert restricted["errors"][0]["code"] == "view_on_request"
    assert unavailable["status"] == "unavailable"
    assert unavailable["errors"][0]["code"] == "not_available_online"
    assert missing["status"] == "no_results"
    assert missing["errors"] == []


def test_runtime_probe_parser_and_explicit_access_decision(
    monkeypatch: Any,
) -> None:
    runner = FakeRunner()
    runtime = _execute(
        _parse("runtime-check", "--timeout", "4"),
        monkeypatch,
        runner,
    ).to_dict()
    probe = _execute(_parse("probe"), monkeypatch, runner).to_dict()

    assert runtime["records"][0]["playwright_module"] == "playwright"
    assert probe["records"][0]["case_search_box_count"] == 1
    assert runner.calls[0] == (["runtime-check"], 4)
    decision = {
        "allowed": False,
        "access_class": "C",
        "reason_code": "interactive_route_selected",
        "reason": "Use the interactive route",
    }
    denied_runner = FakeRunner()
    monkeypatch.setattr(
        query_palm_beach_courts,
        "log_search",
        lambda *_args: None,
    )
    denied = query_palm_beach_courts.execute(
        _parse("probe"),
        access_decision=decision,
        helper_runner=denied_runner,
    ).to_dict()
    assert denied["status"] == "human_required"
    assert denied_runner.calls == []


def test_invalid_cursor_is_a_structured_query_failure(
    monkeypatch: Any,
) -> None:
    payload = _execute(
        _parse("search", "KRAFT", "--cursor", "other:offset:1"),
        monkeypatch,
    ).to_dict()

    assert payload["status"] == "unavailable"
    assert payload["errors"][0]["code"] == "invalid_cursor"


def test_browser_route_waits_do_not_require_lingering_resources_to_finish(
) -> None:
    helper_source = HELPER_PATH.read_text(encoding="utf-8")

    assert helper_source.count("waitForURL(") == 3
    assert helper_source.count("waitUntil: 'commit'") == 3
