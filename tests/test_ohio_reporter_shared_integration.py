from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_reporter_decisions as reporter
from tools import query_state_courts
from tools import source_report
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_ohio_reporter_decisions,
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
    / "ohio_reporter_decisions"
)
SOURCE_ID = reporter.SOURCE_ID


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _publication_without_case() -> dict[str, Any]:
    return dict(
        reporter.parse_search_page(
            _fixture_text("publication.html")
        ).records[0]
    )


def _publication_with_case() -> dict[str, Any]:
    return dict(
        reporter.parse_search_page(
            _fixture_text("search-page-1.html")
        ).records[0]
    )


def _envelope(
    records: list[dict[str, Any]],
    *,
    operation: str = "search",
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=reporter._source_metadata(),
        jurisdiction=reporter._jurisdiction(),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


class _ReporterCatalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": reporter.SOURCE_NAME,
                "official_url": reporter.BASE_URL,
                "authority": "Supreme Court of Ohio",
                "platform_family": reporter.PLATFORM_FAMILY,
            },
            "roles": ["appellate_opinions"],
            "capabilities": [
                {"name": "search_publications", "supported": True},
                {"name": "fetch_publication", "supported": True},
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
        lambda _path: _ReporterCatalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


def _empty_result(operation: str) -> PublicRecordsResult:
    return PublicRecordsResult.success(
        PublicRecordsQuery(
            source=reporter._source_metadata(),
            jurisdiction=reporter._jurisdiction(),
            query=QueryMetadata(operation=operation, parameters={}),
        ),
        [],
    )


def test_shared_search_defaults_to_all_sources_and_has_no_implicit_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(reporter, "execute", fake_execute)
    arguments = (
        ["search", "public records", "--source", SOURCE_ID],
        [
            "search",
            "C-250425",
            "--source",
            SOURCE_ID,
            "--court-id",
            "oh-court-of-appeals-district-1",
            "--search-field",
            "case-number",
            "--limit",
            "9",
            "--max-records",
            "4",
        ],
        [
            "search",
            "public records",
            "--source",
            SOURCE_ID,
            "--max-records",
            "6",
        ],
    )
    for argv in arguments:
        payload = query_state_courts.execute(
            query_state_courts.build_parser().parse_args(argv)
        )
        assert payload["status"] == "no_results"

    assert calls[0].source == "all"
    assert calls[0].text == "public records"
    assert calls[0].limit is None
    assert calls[1].source == "district-1"
    assert calls[1].case_number == "C-250425"
    assert calls[1].text is None
    assert calls[1].limit == 4
    assert calls[2].limit == 6


def test_shared_detail_and_download_are_webcite_publication_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(reporter, "execute", fake_execute)
    detail = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            ["detail", "2018-Ohio-723", "--source", SOURCE_ID]
        )
    )
    destination = tmp_path / "2018-Ohio-723.pdf"
    download = query_state_courts.execute(
        query_state_courts.build_parser().parse_args(
            [
                "download",
                "2018-Ohio-723",
                "--source",
                SOURCE_ID,
                "--destination",
                str(destination),
            ]
        )
    )

    assert detail["status"] == "no_results"
    assert download["status"] == "no_results"
    assert calls[0].command == "publication"
    assert calls[0].webcite == "2018-Ohio-723"
    assert calls[1].command == "document"
    assert calls[1].webcite == "2018-Ohio-723"
    assert calls[1].destination == destination


def test_shared_publication_search_rejects_unmapped_exact_dates() -> None:
    args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "records",
            "--source",
            SOURCE_ID,
            "--after",
            "2026-01-01",
        ]
    )
    with pytest.raises(ValueError, match="does not apply --after"):
        query_state_courts._ohio_reporter_decisions_args(args, "search")


def test_ingest_preserves_webcite_and_only_projects_single_case_join(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "state-courts.db"
    valid = _publication_with_case()
    case_less = _publication_without_case()
    ambiguous = copy.deepcopy(valid)
    ambiguous["webcite"] = "2026-Ohio-9998"
    ambiguous["publication_identity"] = "2026-Ohio-9998"
    ambiguous["case_number"] = "C-250425, C-250426"
    ambiguous["canonical_ref"] = ambiguous["canonical_ref"].replace(
        "2026-Ohio-2912",
        "2026-Ohio-9998",
    )
    ambiguous["native_document_id"] = "2026-Ohio-9998.pdf"
    ambiguous["document_url"] = ambiguous["document_url"].replace(
        "2026-Ohio-2912",
        "2026-Ohio-9998",
    )
    document_record = {
        "source_id": SOURCE_ID,
        "record_kind": "judicial_publication_document",
        "webcite": valid["webcite"],
        "native_document_id": valid["native_document_id"],
    }

    report = ingest_envelope(
        _envelope([valid, case_less, ambiguous, document_record]),
        court_db=court_db,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["case_events"] == 1
    assert report["projected"]["documents"] == 1
    assert report["snapshot_only"] == {
        "record_count": 3,
        "record_kinds": {
            "judicial_publication": 2,
            "judicial_publication_document": 1,
        },
    }

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        cases = list(
            db.execute(
                """
                SELECT raw_case_number, source_internal_id, raw_json
                FROM case_record
                """
            )
        )
        assert len(cases) == 1
        assert cases[0]["raw_case_number"] == "C-250425"
        assert cases[0]["source_internal_id"] is None
        raw_case = json.loads(cases[0]["raw_json"])
        assert raw_case["publication_identity"] == valid["webcite"]
        assert raw_case["case_number_role"] == "optional_case_join"
        assert raw_case["independent_corroboration"] is False

        event = db.execute(
            "SELECT native_event_id, disposition, raw_json FROM case_event"
        ).fetchone()
        assert event["native_event_id"] == valid["webcite"]
        assert event["disposition"] is None
        assert json.loads(event["raw_json"])[
            "publication_identity"
        ] == valid["webcite"]

        document = db.execute(
            """
            SELECT native_document_id, mime_type
            FROM document_artifact
            """
        ).fetchone()
        assert document["native_document_id"] == (
            f"{valid['webcite']}.pdf"
        )
        assert document["mime_type"] == "application/pdf"
        assert raw_case["documents"][0][
            "independent_corroboration"
        ] is False

        snapshot = json.loads(
            db.execute("SELECT raw_json FROM source_snapshot").fetchone()[0]
        )
        assert {
            row["webcite"]
            for row in snapshot["records"]
            if row["record_kind"] == "judicial_publication"
        } == {
            valid["webcite"],
            case_less["webcite"],
            ambiguous["webcite"],
        }
    finally:
        db.close()


class _MonitorClient:
    def __init__(
        self,
        landing: reporter.ReporterPage,
        publication: dict[str, Any],
    ) -> None:
        self.landing_page = landing
        self.collection = reporter.ReporterCollection(
            records=(publication,),
            total_rows=1,
            page_size=reporter.NATIVE_PAGE_SIZE,
            total_pages=1,
            pages_fetched=1,
            selected_values=landing.selected_values,
            selected_labels=landing.selected_labels,
            source_urls=(reporter.BASE_URL,),
            schema_fingerprints=(landing.schema_fingerprint,),
        )
        self.request_count = 3
        self.closed = False
        self.viewstate = "monitor-secret-viewstate"
        self.session_cookie = "monitor-secret-cookie"

    def landing(self) -> reporter.ReporterPage:
        return self.landing_page

    def publication(self, webcite: str) -> reporter.ReporterCollection:
        assert webcite == reporter.PROBE_WEBCITE
        return self.collection

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


def test_monitor_separates_contract_schema_and_rolling_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    landing = reporter.parse_search_page(
        _fixture_text("publication.html")
    )
    publication = _publication_without_case()
    rolling = copy.deepcopy(publication)
    rolling["caption"] = "Changed rolling caption"
    schema = copy.deepcopy(publication)
    schema["new_source_field"] = "new shape"
    queued = [publication, rolling, schema, publication]
    clients: list[_MonitorClient] = []

    def client_factory(**kwargs):
        assert kwargs["request_budget"] == 3
        assert kwargs["max_retries"] == 0
        client = _MonitorClient(landing, queued.pop(0))
        clients.append(client)
        return client

    monkeypatch.setattr(
        reporter,
        "OhioReporterClient",
        client_factory,
    )
    first = probe_ohio_reporter_decisions(_probe_context())
    second = probe_ohio_reporter_decisions(_probe_context())
    third = probe_ohio_reporter_decisions(_probe_context())
    monkeypatch.setattr(
        reporter,
        "HELP_URL",
        f"{reporter.BASE_URL}ChangedHelp.aspx",
    )
    fourth = probe_ohio_reporter_decisions(_probe_context())

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.schema_sha256 != third.schema_sha256
    assert first.artifact_sha256 == third.artifact_sha256
    assert first.schema_sha256 == fourth.schema_sha256
    assert first.artifact_sha256 != fourth.artifact_sha256
    assert first.details["stable_contract"] != fourth.details[
        "stable_contract"
    ]
    assert all(client.closed for client in clients)
    serialized = json.dumps(first.details)
    assert "monitor-secret-viewstate" not in serialized
    assert "monitor-secret-cookie" not in serialized


def test_manifest_census_monitor_and_citation_contracts(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    assert source["roles"][0] == "appellate_opinions"
    assert source["jurisdiction_geoids"] == ["39"]
    assert source["identity_contract"]["publication_identity"] == "WebCite"
    assert source["identity_contract"]["case_number_is_publication_identity"] is False
    assert source["identity_contract"][
        "ambiguous_or_combined_case_number_behavior"
    ] == "preserve_publication_without_case_projection"
    assert source["source_response_contract"]["default_result_cap"] == "none"
    assert source["census_associations"][0]["role"] == "appellate_opinions"
    shared = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert shared["details"]["shared_operations"] == [
        "search",
        "detail",
        "download",
    ]

    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert spec.expected_requests == 3
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is probe_ohio_reporter_decisions

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == reporter.BASE_URL

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
        "fetch_document",
        "fetch_publication",
        "search_publications",
    }
    assert tasks["fetch_publication"]["capability_details"][
        "selector_mode"
    ] == "exact_webcite"

    report = source_report.check_public_records_catalog(catalog_path)
    entry = report[
        "Public records / Ohio Reporter of Decisions Opinions and Announcements"
    ]
    assert entry["source_id"] == SOURCE_ID
    assert entry["query_tool"] == "tools/query_state_courts.py"
