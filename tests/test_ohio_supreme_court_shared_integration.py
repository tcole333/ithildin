from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_supreme_court as ohio
from tools import query_state_courts
from tools import source_report
from tools.ingest_state_court_records import (
    _ohio_supreme_projection_records,
    ingest_envelope,
)
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_ohio_supreme_court,
)
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import (
    DEFAULT_CONFIG_PATH,
    seed_catalog,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_supreme_court"
)
SOURCE_ID = "us-oh-supreme-court-public-docket"


def _fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _case_record() -> dict[str, Any]:
    return ohio.normalize_case_payload(
        _fixture_json("case.json"),
        requested_case_number=ohio.PROBE_CASE_NUMBER,
    )


def _search_record() -> dict[str, Any]:
    case = _case_record()
    return ohio.normalize_search_row(
        {
            "ID": 0,
            "CaseNumber": case["case_number"],
            "Caption": case["caption"],
            "DateFiled": "2017-12-01T05:00:00",
            "Status": case["status"],
            "CaseType": case["case_type"],
            "PriorJurisdiction": "Third District Court of Appeals",
        }
    )


def _envelope(
    records: list[dict[str, Any]],
    *,
    operation: str,
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=ohio._source_metadata(),
        jurisdiction=ohio._jurisdiction(),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


class _OhioCatalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": ohio.SOURCE_NAME,
                "official_url": ohio.BASE_URL,
                "authority": "Supreme Court of Ohio",
                "platform_family": ohio.PLATFORM_FAMILY,
            },
            "roles": ["appellate_case_index"],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_document_index", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed",
        }


def _install_router_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _OhioCatalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


def _empty_result(operation: str) -> PublicRecordsResult:
    return PublicRecordsResult.success(
        PublicRecordsQuery(
            source=ohio._source_metadata(),
            jurisdiction=ohio._jurisdiction(),
            query=QueryMetadata(operation=operation, parameters={}),
        ),
        [],
    )


def test_shared_search_maps_native_fields_dates_and_only_explicit_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(ohio, "execute", fake_execute)
    for argv in (
        ["search", "Newsome", "--source", SOURCE_ID],
        [
            "search",
            "2017-1682",
            "--source",
            SOURCE_ID,
            "--search-field",
            "case-number",
            "--after",
            "2017-01-02",
            "--before",
            "2017-12-03",
        ],
        [
            "search",
            "Newsome",
            "--source",
            SOURCE_ID,
            "--limit",
            "9",
            "--max-records",
            "4",
        ],
        [
            "search",
            "Newsome",
            "--source",
            SOURCE_ID,
            "--max-records",
            "6",
        ],
    ):
        payload = query_state_courts.execute(
            query_state_courts.build_parser().parse_args(argv)
        )
        assert payload["status"] == "no_results"

    assert calls[0].caption == "Newsome"
    assert calls[0].case_number is None
    assert calls[0].limit is None
    assert calls[1].case_number == "2017-1682"
    assert calls[1].caption is None
    assert calls[1].filed_from == "01-02-2017"
    assert calls[1].filed_to == "12-03-2017"
    assert calls[1].limit is None
    assert calls[2].limit == 4
    assert calls[3].limit == 6


@pytest.mark.parametrize("command", ["case", "docket", "documents"])
def test_shared_exact_operations_use_one_case_detail_route(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(ohio, "execute", fake_execute)
    payload = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [command, "2017-1682", "--source", SOURCE_ID]
        )
    )

    assert payload["status"] == "no_results"
    assert calls[0].command == "case"
    assert calls[0].case_number == "2017-1682"


def test_shared_download_requires_and_preserves_explicit_section(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(ohio, "execute", fake_execute)
    destination = tmp_path / "filing.pdf"
    payload = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [
                "download",
                "835936.pdf",
                "--source",
                SOURCE_ID,
                "--case-number",
                "2017-1682",
                "--document-section",
                "DocketItems",
                "--destination",
                str(destination),
            ]
        )
    )

    assert payload["status"] == "no_results"
    assert calls[0].command == "document"
    assert calls[0].document_name == "835936.pdf"
    assert calls[0].case_number == "2017-1682"
    assert calls[0].section == "DocketItems"
    assert calls[0].destination == destination

    missing = query_state_courts.build_parser().parse_args(
        [
            "download",
            "835936.pdf",
            "--source",
            SOURCE_ID,
            "--case-number",
            "2017-1682",
            "--destination",
            str(destination),
        ]
    )
    with pytest.raises(ValueError, match="--document-section"):
        query_state_courts.execute(missing)


def test_search_and_detail_ingest_to_one_case_without_internal_id_split(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "state-courts.db"
    search_record = _search_record()
    case_record = _case_record()

    search_report = ingest_envelope(
        _envelope([search_record], operation="search"),
        court_db=court_db,
    )
    detail_report = ingest_envelope(
        _envelope([case_record], operation="case"),
        court_db=court_db,
    )
    repeated_report = ingest_envelope(
        _envelope([case_record], operation="case"),
        court_db=court_db,
    )

    assert search_record["canonical_ref"] == case_record["canonical_ref"]
    assert search_report["projected"]["cases"] == 1
    assert detail_report["projected"] == {
        "courts": 1,
        "related_courts": 0,
        "cases": 1,
        "related_cases": 0,
        "case_relations": 0,
        "parties": 2,
        "attorneys": 1,
        "representations": 1,
        "judicial_officers": 0,
        "assignments": 0,
        "claims": 0,
        "docket_entries": 3,
        "case_events": 1,
        "documents": 3,
        "restriction_events": 0,
    }
    assert repeated_report["status"] == "ingested"

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 3
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case["raw_case_number"] == "2017-1682"
        assert case["source_internal_id"] is None
        assert case["caption"] == case_record["caption"]
        raw_case = json.loads(case["raw_json"])
        assert raw_case["source_internal_case_locator"] == "100335"
        assert "source_internal_id" not in raw_case
        assert raw_case["source_search_id"] is None
        assert raw_case["prior_jurisdiction"]["prior_case_numbers"] == [
            {"Number": "9-17-42"}
        ]
        assert raw_case["case_issues"] == case_record["case_issues"]

        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 2
        attorney = db.execute(
            "SELECT raw_name, bar_id FROM attorney"
        ).fetchone()
        assert tuple(attorney) == ("Smith, Jane Example", "0012345")
        assert (
            db.execute("SELECT COUNT(*) FROM case_representation").fetchone()[0]
            == 1
        )

        docket_ids = {
            row["native_entry_id"]
            for row in db.execute("SELECT native_entry_id FROM docket_entry")
        }
        assert docket_ids == {"835936", "835937", "840001"}
        documents = {
            row["native_document_id"]: row["native_entry_id"]
            for row in db.execute(
                """
                SELECT d.native_document_id, de.native_entry_id
                FROM document_artifact AS d
                LEFT JOIN docket_entry AS de
                  ON de.docket_entry_id=d.docket_entry_id
                """
            )
        }
        assert documents == {
            "2017-1682:DocketItems:835936.pdf": "835936",
            "2017-1682:DocketItems:835937.pdf": "835937",
            "2017-1682:DecisionItems:214796.pdf": None,
        }
        decision = json.loads(
            db.execute("SELECT raw_json FROM case_event").fetchone()[0]
        )
        assert decision["event_type"] == "decision"
        assert decision["disposition"].startswith("Granted; cause dismissed.")
        assert decision["native_document_id"] == (
            "2017-1682:DecisionItems:214796.pdf"
        )
    finally:
        db.close()


def test_non_dispositive_decision_description_stays_source_metadata() -> None:
    record = _case_record()
    record["decisions"][0]["disposes_case"] = False

    projected = _ohio_supreme_projection_records(record)[0]

    assert projected["case_events"][0]["disposition"] is None
    assert projected["case_events"][0]["ohio_supreme_source_decision"][
        "description_text"
    ].startswith("Granted; cause dismissed.")


class _MonitorClient:
    def __init__(
        self,
        *,
        search_records: list[dict[str, Any]],
        case_record: dict[str, Any],
        recent_records: list[dict[str, Any]],
    ) -> None:
        self.search_records = search_records
        self.case_record = case_record
        self.recent_records = recent_records
        self.request_count = 5
        self.closed = False
        self.request_token = "monitor-secret-token"
        self.session_cookie = "monitor-secret-cookie"

    def search(self, parameters: dict[str, Any]):
        assert parameters["paramCaseCaption"] == ohio.PROBE_CASE_CAPTION
        return self.search_records

    def case(self, case_number: str):
        assert case_number == ohio.PROBE_CASE_NUMBER
        return self.case_record

    def recent(self, days: int):
        assert days == 1
        return self.recent_records

    def close(self) -> None:
        self.closed = True


def _probe_context() -> ProbeContext:
    return ProbeContext(
        source_id=SOURCE_ID,
        catalog_decision={"limits": {"minimum_interval_seconds": 0}},
        timeout=5,
        max_attempts=1,
        sample_bytes=None,
    )


def test_monitor_separates_stable_schema_and_rolling_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search = [_search_record()]
    case = _case_record()
    recent = [
        ohio.normalize_recent_row(value)
        for value in _fixture_json("recent.json")
    ]
    rolling_case = copy.deepcopy(case)
    rolling_case["status"] = "Reopened"
    rolling_recent = copy.deepcopy(recent)
    rolling_recent[0]["date_filed"] = "2026-07-31"
    schema_case = copy.deepcopy(case)
    schema_case["new_source_field"] = "new shape"
    queued = [
        (search, case, recent),
        (search, rolling_case, rolling_recent),
        (search, schema_case, recent),
        (search, case, recent),
    ]
    clients: list[_MonitorClient] = []

    def client_factory(**kwargs):
        assert kwargs["request_budget"] == 5
        assert kwargs["max_retries"] == 0
        values = queued.pop(0)
        client = _MonitorClient(
            search_records=values[0],
            case_record=values[1],
            recent_records=values[2],
        )
        clients.append(client)
        return client

    monkeypatch.setattr(ohio, "OhioSupremeCourtClient", client_factory)
    first = probe_ohio_supreme_court(_probe_context())
    second = probe_ohio_supreme_court(_probe_context())
    third = probe_ohio_supreme_court(_probe_context())
    monkeypatch.setattr(
        ohio,
        "AJAX_URL",
        f"{ohio.BASE_URL}changed-ajax-route",
    )
    fourth = probe_ohio_supreme_court(_probe_context())

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.schema_sha256 != third.schema_sha256
    assert first.artifact_sha256 == third.artifact_sha256
    assert first.schema_sha256 == fourth.schema_sha256
    assert first.artifact_sha256 != fourth.artifact_sha256
    assert all(client.closed for client in clients)
    assert first.result_count == 1
    assert first.details["rolling_observation"]["request_count"] == 5
    serialized = json.dumps(first.details)
    assert "monitor-secret-token" not in serialized
    assert "monitor-secret-cookie" not in serialized
    assert "source_internal_case_locator" not in first.details[
        "rolling_observation"
    ]


def test_monitor_registry_declares_fixed_five_request_contract() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]

    assert spec.capability == "probe_source"
    assert spec.expected_requests == 5
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is probe_ohio_supreme_court


def test_manifest_census_search_plan_source_report_and_citation(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    assert source["jurisdiction_geoids"] == ["39"]
    assert source["roles"][0] == "appellate_case_index"
    assert "trial_case_index" not in source["roles"]
    assert source["identity_contract"]["case_identity"] == (
        "CaseInfo.CaseNumber"
    )
    assert source["identity_contract"][
        "source_internal_case_locator_is_identity"
    ] is False
    assert source["coverage_contract"]["not_ohio_trial_court_coverage"] is True
    shared = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert shared["details"]["shared_operations"] == [
        "search",
        "case",
        "docket",
        "documents",
        "download",
    ]
    assert shared["details"]["direct_only_operations"] == ["recent"]
    assert source["census_associations"][0]["role"] == "appellate_case_index"
    complement_names = {
        row["name"] for row in source["official_complements"]
    }
    assert complement_names >= {
        "Reporter of Decisions",
        "Clerk's Journal",
        "Attorney Directory",
        "Judge Directory",
        "Ohio trial-court directory",
        "State court-statistics dashboards",
    }

    census = yaml.safe_load(
        Path("config/public_records_census.yaml").read_text(encoding="utf-8")
    )
    assert census["jurisdictions"]["OH"]["geoid"] == "39"
    assert "appellate_case_index" in census["roles"]["court"]

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == ohio.BASE_URL

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["39"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
    )
    planned_source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    assert planned_source["access"]["mode"] == "allowed_with_limits"
    tasks = {
        task["capability"]: task
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert set(tasks) == {
        "fetch_case",
        "fetch_document",
        "list_docket_entries",
        "list_document_index",
        "search_cases",
    }
    assert tasks["fetch_case"]["capability_details"][
        "requires_prior_selector"
    ] == "case_number"

    report = source_report.check_public_records_catalog(catalog_path)
    entry = report[
        "Public records / Supreme Court of Ohio Public Docket"
    ]
    assert entry["source_id"] == SOURCE_ID
    assert entry["query_tool"] == "tools/query_state_courts.py"
