from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_delaware_common_pleas as delaware
from tools import query_ohio_licking_common_pleas as licking
from tools import query_state_courts
from tools import source_report
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsError,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_delaware_ohio_common_pleas,
    probe_licking_common_pleas,
)
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import DEFAULT_CONFIG_PATH, seed_catalog


DELAWARE_SOURCE_ID = "us-oh-delaware-common-pleas-courtview"
LICKING_SOURCE_ID = "us-oh-licking-common-pleas-remote-records"
DELAWARE_FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_delaware_common_pleas"
)
LICKING_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_licking_common_pleas"
    / "probe.json"
)


def _delaware_fixture(name: str) -> dict[str, Any]:
    return json.loads(
        (DELAWARE_FIXTURES / name).read_text(encoding="utf-8")
    )


def _licking_fixture() -> dict[str, Any]:
    return json.loads(LICKING_FIXTURE.read_text(encoding="utf-8"))


def _query(
    adapter: Any,
    operation: str,
    parameters: dict[str, Any] | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=adapter.SOURCE_METADATA,
        jurisdiction=adapter.JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters or {},
        ),
    )


class _OhioCountyCourtCatalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        if source_id == DELAWARE_SOURCE_ID:
            return {
                "source": {
                    "source_id": source_id,
                    "name": "Delaware County Common Pleas CourtView eServices",
                    "official_url": delaware.HOME_URL,
                    "authority": "Delaware County Clerk of Courts",
                    "platform_family": delaware.ADAPTER_FAMILY,
                },
                "roles": [
                    "trial_case_index",
                    "party_name_index",
                    "docket_entries",
                    "source_published_filing_copies",
                ],
                "capabilities": [
                    {"name": "search_cases", "supported": True},
                    {"name": "fetch_case", "supported": True},
                    {"name": "list_docket_entries", "supported": True},
                    {"name": "list_document_index", "supported": True},
                    {"name": "fetch_document", "supported": True},
                ],
                "latest_access_review": {"access_class": "C"},
            }
        if source_id == LICKING_SOURCE_ID:
            return {
                "source": {
                    "source_id": source_id,
                    "name": "Licking County Common Pleas Remote Court Records",
                    "official_url": licking.OFFICIAL_LANDING_URL,
                    "authority": "Licking County Clerk of Courts",
                    "platform_family": licking.ADAPTER_FAMILY,
                },
                "roles": [
                    "trial_case_index",
                    "targeted_browser_handoff",
                    "bulk_distribution_request",
                ],
                "capabilities": [
                    {"name": "describe_source", "supported": True},
                    {"name": "probe_source", "supported": True},
                ],
                "latest_access_review": {"access_class": "C"},
            }
        raise AssertionError(f"unexpected source: {source_id}")

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, Any]:
        assert source_id in {DELAWARE_SOURCE_ID, LICKING_SOURCE_ID}
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "C",
            "reason": "review permits the configured acquisition route",
            "reason_code": "allowed",
        }


def _install_router_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _OhioCountyCourtCatalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


def _install_delaware_fixture_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, list[str], dict[str, Any]]]:
    original_execute = delaware.execute
    calls: list[tuple[str, list[str], dict[str, Any]]] = []
    case_packet = _delaware_fixture("case.json")
    search_packet = _delaware_fixture("search.json")

    def runner(
        operation: str,
        arguments: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        calls.append((operation, list(arguments), dict(kwargs)))
        if operation == "search":
            return copy.deepcopy(search_packet)
        if operation == "case":
            return copy.deepcopy(case_packet)
        if operation == "probe":
            return _delaware_fixture("probe.json")
        if operation == "document":
            row = case_packet["case"]["docket"][0]
            return {
                "operation": "document",
                "status": "ok",
                "requested_document_id": arguments[1],
                "case": {
                    "case_number": arguments[0],
                    "caption": case_packet["case"]["caption"],
                },
                "document": copy.deepcopy(row),
                "artifact": {
                    "output_path": arguments[2],
                    "content_type": "application/pdf",
                    "byte_size": 21355,
                    "sha256": "a" * 64,
                },
            }
        raise AssertionError(f"unexpected helper operation: {operation}")

    def execute_with_fixture(args):
        return original_execute(args, helper_runner=runner)

    monkeypatch.setattr(delaware, "execute", execute_with_fixture)
    return calls


def test_delaware_shared_search_preserves_selectors_limit_and_bound_cursor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_router_catalog(monkeypatch)
    helper_calls = _install_delaware_fixture_execute(monkeypatch)
    common = [
        "search",
        "Smith",
        "--source",
        DELAWARE_SOURCE_ID,
        "--first-name",
        "J",
        "--case-type",
        "CV",
        "--case-status",
        "Closed",
        "--party-type",
        "Defendant",
        "--after",
        "2020-01-02",
        "--limit",
        "2",
    ]

    first = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(common)
    )
    cursor = first["next_cursor"]
    second = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [*common, "--cursor", cursor]
        )
    )
    company = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [
                "search",
                "ACME LLC",
                "--source",
                DELAWARE_SOURCE_ID,
                "--entity-kind",
                "organization",
            ]
        )
    )
    mismatch = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [
                "search",
                "Jones",
                "--source",
                DELAWARE_SOURCE_ID,
                "--limit",
                "2",
                "--cursor",
                cursor,
            ]
        )
    )

    assert first["status"] == "ok"
    assert cursor.startswith(delaware.CURSOR_PREFIX)
    assert [
        record["exhaustive_occurrence_ordinal"] for record in first["records"]
    ] == [1, 2]
    assert [
        record["exhaustive_occurrence_ordinal"] for record in second["records"]
    ] == [3, 4]
    assert second["next_cursor"] is None
    assert company["status"] == "ok"
    assert mismatch["status"] == "unavailable"
    assert mismatch["errors"][0]["code"] == "cursor_query_mismatch"

    first_helper = helper_calls[0]
    assert first_helper[0] == "search"
    assert first_helper[1] == [
        "--mode",
        "person",
        "--last",
        "Smith",
        "--first",
        "J",
        "--case-type",
        "CV",
        "--case-status",
        "Closed",
        "--party-type",
        "Defendant",
        "--filed-from",
        "01/02/2020",
    ]
    assert helper_calls[1][1] == first_helper[1]
    assert helper_calls[2][1] == [
        "--mode",
        "company",
        "--company",
        "ACME LLC",
    ]
    assert all(call[2] == {"timeout": delaware.DEFAULT_BROWSER_TIMEOUT} for call in helper_calls)


@pytest.mark.parametrize(
    ("operation", "record_kind", "record_count"),
    [
        ("case", "case", 1),
        ("docket", "docket_entry", 3),
        ("documents", "case_document_listing", 2),
    ],
)
def test_delaware_shared_exact_case_views(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    record_kind: str,
    record_count: int,
) -> None:
    _install_router_catalog(monkeypatch)
    helper_calls = _install_delaware_fixture_execute(monkeypatch)
    args = query_state_courts.build_parser().parse_args(
        [operation, "16 CV C 06 0330", "--source", DELAWARE_SOURCE_ID]
    )

    payload = query_state_courts.execute(args)

    assert payload["status"] == "ok"
    assert len(payload["records"]) == record_count
    assert {record["record_kind"] for record in payload["records"]} == {
        record_kind
    }
    assert helper_calls == [
        (
            "case",
            ["16 CV C 06 0330"],
            {"timeout": delaware.DEFAULT_BROWSER_TIMEOUT},
        )
    ]


def test_delaware_shared_download_maps_derived_document_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_router_catalog(monkeypatch)
    helper_calls = _install_delaware_fixture_execute(monkeypatch)
    case_packet = _delaware_fixture("case.json")
    document_id = delaware.derive_document_id(
        "16 CV C 06 0330",
        case_packet["case"]["docket"][0],
    )
    destination = tmp_path / "filing.pdf"
    args = query_state_courts.build_parser().parse_args(
        [
            "download",
            document_id,
            "--source",
            DELAWARE_SOURCE_ID,
            "--case-number",
            "16 CV C 06 0330",
            "--destination",
            str(destination),
        ]
    )

    payload = query_state_courts.execute(args)

    assert payload["status"] == "ok"
    artifact = payload["records"][0]
    assert artifact["record_kind"] == "case_document_artifact"
    assert artifact["document_id"] == document_id
    assert artifact["artifact_sha256"] == "a" * 64
    assert helper_calls == [
        (
            "document",
            [
                "16 CV C 06 0330",
                document_id,
                str(destination.resolve()),
            ],
            {"timeout": delaware.DEFAULT_BROWSER_TIMEOUT},
        )
    ]


def _delaware_offline_results(
    tmp_path: Path,
) -> dict[str, PublicRecordsResult]:
    search_packet = _delaware_fixture("search.json")
    case_packet = _delaware_fixture("case.json")

    def run(values: list[str], packet: dict[str, Any]) -> PublicRecordsResult:
        args = delaware.build_parser().parse_args(values)
        return delaware.execute(
            args,
            helper_runner=lambda *_args, **_kwargs: copy.deepcopy(packet),
        )

    results = {
        "search": run(
            ["search-party", "--last-name", "Smith", "--first-name", "J"],
            search_packet,
        ),
        "case": run(["case", "16 CV C 06 0330"], case_packet),
        "docket": run(["docket", "16 CV C 06 0330"], case_packet),
        "documents": run(
            ["documents", "16 CV C 06 0330"],
            case_packet,
        ),
    }
    docket_row = case_packet["case"]["docket"][0]
    document_id = delaware.derive_document_id(
        "16 CV C 06 0330",
        docket_row,
    )
    artifact = delaware.normalize_document_packet(
        {
            "operation": "document",
            "status": "ok",
            "requested_document_id": document_id,
            "case": {
                "case_number": "16 CV C 06 0330",
                "caption": case_packet["case"]["caption"],
            },
            "document": docket_row,
            "artifact": {
                "output_path": str(tmp_path / "filing.pdf"),
                "content_type": "application/pdf",
                "byte_size": 21355,
                "sha256": "a" * 64,
            },
        }
    )
    assert artifact is not None
    results["artifact"] = PublicRecordsResult.success(
        _query(
            delaware,
            "document",
            {
                "case_number": "16 CV C 06 0330",
                "document_id": document_id,
            },
        ),
        [artifact],
    )
    return results


def test_delaware_ingestion_preserves_occurrences_and_unifies_case_views(
    tmp_path: Path,
) -> None:
    results = _delaware_offline_results(tmp_path)
    court_db = tmp_path / "state-courts.db"

    reports = {
        name: ingest_envelope(result.to_dict(), court_db=court_db)
        for name, result in results.items()
    }

    assert reports["search"]["projected"]["cases"] == 4
    assert reports["search"]["projected"]["parties"] == 4
    assert reports["case"]["projected"]["cases"] == 1
    assert reports["case"]["projected"]["parties"] == 2
    assert reports["case"]["projected"]["attorneys"] == 2
    assert reports["case"]["projected"]["docket_entries"] == 3
    assert reports["case"]["projected"]["documents"] == 2
    assert reports["docket"]["projected"]["docket_entries"] == 3
    assert reports["documents"]["projected"]["documents"] == 2
    assert reports["artifact"]["projected"]["documents"] == 1

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 5
        assert db.execute("SELECT COUNT(*) FROM case_source_occurrence").fetchone()[0] == 4
        duplicate_occurrences = db.execute(
            """
            SELECT source_result_id, raw_json
            FROM case_source_occurrence
            WHERE matched_party_name='SMITH, J D'
            ORDER BY occurrence_id
            """
        ).fetchall()
        assert len(duplicate_occurrences) == 2
        assert len(
            {row["source_result_id"] for row in duplicate_occurrences}
        ) == 2
        assert {
            json.loads(row["raw_json"])["native_occurrence_id"]
            for row in duplicate_occurrences
        } == {row["source_result_id"] for row in duplicate_occurrences}
        assert db.execute(
            "SELECT COUNT(*) FROM case_party WHERE raw_name='SMITH, J D'"
        ).fetchone()[0] == 1

        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 3
        exact_case = db.execute(
            """
            SELECT case_id, raw_case_number, display_case_number
            FROM case_record
            WHERE display_case_number='16 CV C 06 0330'
            """
        ).fetchall()
        assert len(exact_case) == 1
        assert exact_case[0]["raw_case_number"] == "16CVC060330"
        exact_case_id = exact_case[0]["case_id"]
        assert db.execute(
            "SELECT COUNT(*) FROM docket_entry WHERE case_id=?",
            (exact_case_id,),
        ).fetchone()[0] == 3

        documents = db.execute(
            """
            SELECT native_document_id, docket_entry_id, sha256,
                   mime_type, storage_path
            FROM document_artifact
            WHERE case_id=?
            ORDER BY native_document_id
            """,
            (exact_case_id,),
        ).fetchall()
        assert len(documents) == 3
        assert len({row["native_document_id"] for row in documents}) == 2
        assert sum(row["sha256"] is None for row in documents) == 2
        acquired = next(row for row in documents if row["sha256"] is not None)
        assert acquired["sha256"] == "a" * 64
        assert acquired["mime_type"] == "application/pdf"
        assert acquired["storage_path"] == str(tmp_path / "filing.pdf")
        assert acquired["docket_entry_id"] is not None
    finally:
        db.close()


def _probe_context(source_id: str) -> ProbeContext:
    return ProbeContext(
        source_id=source_id,
        catalog_decision={"limits": {}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def _human_required_result(
    adapter: Any,
    *,
    code: str,
    message: str,
    details: dict[str, Any],
) -> PublicRecordsResult:
    return PublicRecordsResult.failure(
        _query(adapter, "probe"),
        ResultStatus.HUMAN_REQUIRED,
        [
            PublicRecordsError(
                code=code,
                message=message,
                category="access",
                details=details,
            )
        ],
    )


def test_delaware_monitor_ok_and_human_required_each_use_one_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok_result = PublicRecordsResult.success(
        _query(delaware, "probe"),
        [delaware.normalize_probe(_delaware_fixture("probe.json"))],
    )
    human_result = _human_required_result(
        delaware,
        code="captcha_required",
        message="CourtView presented its visible challenge",
        details={"access": {"interactive_challenge": True}},
    )
    queued = [ok_result, human_result]
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return queued.pop(0)

    monkeypatch.setattr(delaware, "execute", fake_execute)
    ok = probe_delaware_ohio_common_pleas(
        _probe_context(DELAWARE_SOURCE_ID)
    )
    human = probe_delaware_ohio_common_pleas(
        _probe_context(DELAWARE_SOURCE_ID)
    )

    assert len(calls) == 2
    assert all(call.command == "probe" for call in calls)
    assert ok.status == "ok"
    assert ok.result_count == 1
    assert ok.details["browser_helper_invocations"] == 1
    assert ok.details["stable_contract"]["paging"] == {
        "native_page_sizes": [25, 50, 75, 100],
        "default": "exhaustive",
        "shared_cursor": "query_bound_offset_replay",
    }
    assert human.status == "human_required"
    assert human.result_count == 0
    assert human.details["browser_helper_invocations"] == 1
    assert human.details["errors"][0]["code"] == "captcha_required"

    spec = public_records_monitor.HANDLER_REGISTRY[DELAWARE_SOURCE_ID]
    assert spec.expected_requests == 1
    assert spec.sentinel_record_count == 1
    assert spec.handler is probe_delaware_ohio_common_pleas


def test_licking_shared_routes_only_discovery_and_anonymous_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_router_catalog(monkeypatch)
    original_execute = licking.execute
    calls: list[Any] = []

    def execute_with_fixture(args):
        calls.append(args)
        if args.command == "source":
            return original_execute(args)
        assert args.command == "probe"
        return PublicRecordsResult.success(
            _query(licking, "probe"),
            [licking.normalize_probe(_licking_fixture())],
        )

    monkeypatch.setattr(licking, "execute", execute_with_fixture)
    discovery = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            ["discovery", "source", "--source", LICKING_SOURCE_ID]
        )
    )
    probe = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            ["probe", "contract", "--source", LICKING_SOURCE_ID]
        )
    )
    search = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            ["search", "Jane Smith", "--source", LICKING_SOURCE_ID]
        )
    )

    assert discovery["status"] == "ok"
    assert discovery["records"][0]["record_kind"] == "source_manifest"
    assert probe["status"] == "ok"
    assert probe["records"][0]["request_count"] == 6
    assert [call.command for call in calls] == ["source", "probe"]
    assert set(query_state_courts.LIVE_ROUTES[LICKING_SOURCE_ID]) == {
        "discovery",
        "probe",
    }
    assert query_state_courts._source_guidance(LICKING_SOURCE_ID)[
        "unified_operations"
    ] == ["discovery", "probe"]
    assert search["status"] == "unavailable"
    assert search["errors"][0]["code"] == "capability_not_supported"


def test_licking_monitor_ok_human_required_and_six_request_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ok_result = PublicRecordsResult.success(
        _query(licking, "probe"),
        [licking.normalize_probe(_licking_fixture())],
    )
    human_result = _human_required_result(
        licking,
        code="interactive_verification_required",
        message="The Tyler route presented human verification",
        details={"portal_url": licking.PORTAL_URL},
    )
    queued = [ok_result, human_result]
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return queued.pop(0)

    monkeypatch.setattr(licking, "execute", fake_execute)
    ok = probe_licking_common_pleas(_probe_context(LICKING_SOURCE_ID))
    human = probe_licking_common_pleas(_probe_context(LICKING_SOURCE_ID))

    assert len(calls) == 2
    assert all(call.command == "probe" for call in calls)
    assert ok.status == "ok"
    assert ok.result_count == 1
    assert ok.details["request_count"] == 6
    assert ok.details["stable_contract"]["targeted_search_access"] == (
        "human_verification_and_sign_in_required"
    )
    assert ok.details["stable_contract"][
        "max_export_is_search_page_ceiling"
    ] is False
    assert human.status == "human_required"
    assert human.result_count == 0
    assert human.details["access_state"] == (
        "interactive_verification_required"
    )
    assert human.details["errors"][0]["code"] == (
        "interactive_verification_required"
    )

    spec = public_records_monitor.HANDLER_REGISTRY[LICKING_SOURCE_ID]
    assert spec.expected_requests == 6
    assert spec.sentinel_record_count == 1
    assert spec.handler is probe_licking_common_pleas


def test_catalog_census_citations_search_plan_and_source_report(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    sources = {row["source_id"]: row for row in config["sources"]}
    delaware_source = sources[DELAWARE_SOURCE_ID]
    licking_source = sources[LICKING_SOURCE_ID]

    assert delaware_source["jurisdiction_geoids"] == ["39041"]
    assert "party_name_index" in delaware_source["roles"]
    assert delaware_source["stable_keys"] == [
        "normalized_display_case_number",
        "query_fingerprint_plus_response_ordinal",
        "case_scoped_docket_occurrence",
        "derived_case_docket_document_identity",
    ]
    delaware_search = next(
        capability
        for capability in delaware_source["capabilities"]
        if capability["name"] == "search_cases"
    )
    assert delaware_search["details"]["caller_window"] == (
        "query_bound_offset_cursor_when_limit_is_supplied"
    )
    assert delaware_search["details"]["duplicates_preserved"] is True
    delaware_shared = next(
        capability
        for capability in delaware_source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert delaware_shared["details"]["shared_operations"] == [
        "search",
        "case",
        "docket",
        "documents",
        "download",
        "discovery",
        "probe",
    ]

    assert licking_source["jurisdiction_geoids"] == ["39089"]
    assert licking_source["stable_keys"] == [
        "county_tenant_identity",
        "handoff_kind_and_source_selector",
    ]
    licking_shared = next(
        capability
        for capability in licking_source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert licking_shared["details"]["shared_operations"] == [
        "discovery",
        "probe",
    ]
    assert not any(
        capability["name"] == "search_cases"
        for capability in licking_source["capabilities"]
    )
    licking_probe = next(
        capability
        for capability in licking_source["capabilities"]
        if capability["name"] == "probe_source"
    )
    assert licking_probe["details"]["expected_requests"] == 6

    census = yaml.safe_load(
        Path("config/public_records_census.yaml").read_text(encoding="utf-8")
    )
    court_targets = {
        target["jurisdiction_geoid"]: target
        for target in census["additional_targets"]
        if target["domain"] == "court"
        and target["role"] == "trial_case_index"
        and target["jurisdiction_geoid"] in {"39041", "39089"}
    }
    assert "party index" in court_targets["39041"]["description"]
    assert "bulk-distribution" in court_targets["39089"]["description"]

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{DELAWARE_SOURCE_ID}"] == (
        delaware.HOME_URL
    )
    assert source_urls[f"STATECOURT_SOURCE:{LICKING_SOURCE_ID}"] == (
        licking.OFFICIAL_LANDING_URL
    )

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["39041", "39089"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
    )
    planned_sources = {row["source_id"]: row for row in plan["sources"]}
    assert planned_sources[DELAWARE_SOURCE_ID]["access"]["mode"] == (
        "allowed_with_limits"
    )
    assert planned_sources[LICKING_SOURCE_ID]["access"]["mode"] == (
        "allowed_with_limits"
    )
    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
        if task["source_id"] == DELAWARE_SOURCE_ID
    }
    assert set(tasks) == {
        "search_cases",
        "fetch_case",
        "list_docket_entries",
        "list_document_index",
        "fetch_document",
    }
    assert tasks["search_cases"]["capability_details"]["duplicates_preserved"] is True
    assert not any(
        task["source_id"] == LICKING_SOURCE_ID
        for stage in plan["workflow"]["stages"]
        for task in stage["tasks"]
    )
    complement_groups = {
        group["primary_source_id"]: group
        for group in plan["complementary_routes"]
    }
    assert {
        row["source_id"]
        for row in complement_groups[DELAWARE_SOURCE_ID]["complements"]
    } >= {
        "us-oh-delaware-sheriff-realauction",
        "us-oh-delaware-county-recorder-pax",
        "us-oh-delaware-county-auditor-property",
    }
    assert {
        row["source_id"]
        for row in complement_groups[LICKING_SOURCE_ID]["complements"]
    } >= {
        "us-oh-licking-sheriff-foreclosure-archive",
        "us-oh-licking-sheriff-realauction",
        "us-oh-licking-county-recorder-pax",
        "us-oh-licking-county-auditor-gis",
    }

    report = source_report.check_public_records_catalog(catalog_path)
    delaware_entry = report[
        "Public records / Delaware County Common Pleas CourtView eServices"
    ]
    licking_entry = report[
        "Public records / Licking County Common Pleas Remote Court Records"
    ]
    assert delaware_entry["source_id"] == DELAWARE_SOURCE_ID
    assert licking_entry["source_id"] == LICKING_SOURCE_ID
    assert delaware_entry["query_tool"] == "tools/query_state_courts.py"
    assert licking_entry["query_tool"] == "tools/query_state_courts.py"
