from __future__ import annotations

import copy
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import public_records_monitor
from tools import query_ohio_franklin_courts as franklin
from tools import query_state_courts
from tools import source_report
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import ProbeContext, probe_franklin_cio
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import (
    DEFAULT_CONFIG_PATH,
    seed_catalog,
)


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "ohio_franklin_courts"
)
SOURCE_ID = "us-oh-franklin-common-pleas-cio"


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _fixture_json(name: str) -> dict[str, Any]:
    return json.loads(_fixture_text(name))


def _fixture_case_record() -> dict[str, Any]:
    requested = franklin.parse_case_number("22CV3098")
    parsed = franklin.parse_case_detail_initial(
        _fixture_text("case_detail.html"),
        requested_case=requested,
    )
    continuation, next_key = franklin.parse_docket_ajax(
        _fixture_json("docket_page_2.json"),
        source_page_no=2,
    )
    assert next_key is None
    return dict(
        franklin.finalize_case_page(
            parsed,
            all_docket_rows=[*parsed.docket_rows, *continuation],
            native_page_count=2,
        ).record
    )


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=franklin.SOURCE_METADATA,
        jurisdiction=franklin.JURISDICTION,
        query=QueryMetadata(
            operation="case",
            parameters={"case_number": "22CV3098"},
        ),
    )
    return PublicRecordsResult.success(query, records).to_dict()


class _FranklinCatalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Franklin County Clerk of Courts CIO",
                "official_url": franklin.BASE_URL,
                "authority": "Franklin County Clerk of Courts",
                "platform_family": franklin.PLATFORM_FAMILY,
            },
            "roles": [
                "trial_case_index",
                "party_name_index",
                "docket_entries",
            ],
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
        lambda _path: _FranklinCatalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


@pytest.mark.parametrize("command", ["case", "docket", "documents"])
def test_shared_router_maps_exact_case_operations(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return PublicRecordsResult.success(
            PublicRecordsQuery(
                source=franklin.SOURCE_METADATA,
                jurisdiction=franklin.JURISDICTION,
                query=QueryMetadata(operation="case", parameters={}),
            ),
            [],
        )

    monkeypatch.setattr(franklin, "execute", fake_execute)
    args = query_state_courts.build_parser().parse_args(
        [command, "22CV3098", "--source", SOURCE_ID]
    )

    payload = query_state_courts.execute(args)

    assert payload["status"] == "no_results"
    assert calls[0].command == "case"
    assert calls[0].case_number == "22CV3098"
    assert not hasattr(calls[0], "result_cap")


def test_shared_router_maps_document_identity_and_party_name_route(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_router_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return PublicRecordsResult.success(
            PublicRecordsQuery(
                source=franklin.SOURCE_METADATA,
                jurisdiction=franklin.JURISDICTION,
                query=QueryMetadata(operation="document", parameters={}),
            ),
            [],
        )

    monkeypatch.setattr(franklin, "execute", fake_execute)
    destination = tmp_path / "filing.pdf"
    args = query_state_courts.build_parser().parse_args(
        [
            "download",
            "franklin:document:abc",
            "--case-number",
            "22CV3098",
            "--destination",
            str(destination),
            "--source",
            SOURCE_ID,
        ]
    )

    query_state_courts.execute(args)

    assert calls[0].command == "document"
    assert calls[0].case_number == "22CV3098"
    assert calls[0].document_id == "franklin:document:abc"
    assert calls[0].destination == str(destination)
    assert query_state_courts._source_guidance(SOURCE_ID)[
        "unified_operations"
    ] == [
        "case",
        "discovery",
        "docket",
        "documents",
        "download",
        "probe",
        "search",
    ]
    assert "search" in query_state_courts.LIVE_ROUTES[SOURCE_ID]

    search_args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "WEXNER",
            "--source",
            SOURCE_ID,
            "--first-name",
            "LESLIE",
            "--after",
            "2020-05-19",
            "--before",
            "2020-05-19",
            "--courthouse",
            "civil",
            "--limit",
            "12",
        ]
    )
    search_payload = query_state_courts.execute(search_args)
    assert search_payload["status"] == "no_results"
    search_call = calls[1]
    assert search_call.command == "name"
    assert search_call.last_name == "WEXNER"
    assert search_call.first_name == "LESLIE"
    assert search_call.court == "civil"
    assert search_call.filed_from == "2020-05-19"
    assert search_call.filed_to == "2020-05-19"
    assert search_call.native_row_count == 25
    assert search_call.exhaustive is True
    assert search_call.shared_requested_limit == 12


def test_shared_router_rejects_filters_the_exact_case_route_cannot_apply() -> None:
    args = query_state_courts.build_parser().parse_args(
        [
            "case",
            "22CV3098",
            "--source",
            SOURCE_ID,
            "--after",
            "2026-01-01",
        ]
    )

    with pytest.raises(ValueError, match="--after"):
        query_state_courts._franklin_cio_args(args, "case")


def test_ingestion_is_idempotent_and_preserves_all_document_links(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "state-courts.db"
    record = _fixture_case_record()
    shared_document = next(
        document
        for document in record["documents"]
        if len(document["docket_entry_ids"]) == 2
    )
    envelope = _envelope([record])

    first = ingest_envelope(envelope, court_db=court_db)
    second = ingest_envelope(envelope, court_db=court_db)

    assert first["projected"]["cases"] == 1
    assert first["projected"]["parties"] == 2
    assert first["projected"]["case_events"] == 2
    assert first["projected"]["docket_entries"] == 6
    assert first["projected"]["documents"] == 2
    assert first["projected"]["attorneys"] == 0
    assert second["status"] == "ingested"

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_party").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM attorney").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM case_event").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM docket_entry").fetchone()[0] == 6
        assert (
            db.execute("SELECT COUNT(*) FROM document_artifact").fetchone()[0]
            == 2
        )

        case_row = db.execute(
            "SELECT caption, raw_json FROM case_record"
        ).fetchone()
        assert case_row["caption"] is None
        raw_case = json.loads(case_row["raw_json"])
        stored_document = next(
            document
            for document in raw_case["documents"]
            if document["native_document_id"]
            == shared_document["native_document_id"]
        )
        assert stored_document["docket_entry_ids"] == (
            shared_document["docket_entry_ids"]
        )
        assert stored_document["docket_entry_native_id"] == (
            shared_document["docket_entry_ids"][0]
        )
        assert raw_case["parties"][0]["attorney_summary"]
        assert "attorneys" not in raw_case["parties"][0]

        linked = db.execute(
            """
            SELECT de.native_entry_id
            FROM document_artifact AS d
            LEFT JOIN docket_entry AS de
              ON de.docket_entry_id=d.docket_entry_id
            WHERE d.native_document_id=?
            """,
            (shared_document["native_document_id"],),
        ).fetchone()
        assert linked["native_entry_id"] == (
            shared_document["docket_entry_ids"][0]
        )

        docket_raw = json.loads(
            db.execute(
                """
                SELECT raw_json FROM docket_entry
                WHERE native_entry_id=?
                """,
                (shared_document["docket_entry_ids"][0],),
            ).fetchone()["raw_json"]
        )
        assert docket_raw["document_ids"] == [
            shared_document["native_document_id"]
        ]
        assert docket_raw["franklin_source_entry"]["documents"]

        schedule_rows = [
            json.loads(row["raw_json"])
            for row in db.execute(
                "SELECT raw_json FROM case_event ORDER BY case_event_id"
            )
        ]
        assert {row["description"] for row in schedule_rows} == {
            "CASE FILED",
            "FINAL PRETRIAL CONFERENCE",
        }
        assert {row["event_date"] for row in schedule_rows} == {
            "2022-05-09",
            None,
        }
    finally:
        db.close()


def test_authoritative_no_results_ingests_snapshot_without_case(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "state-courts.db"

    report = ingest_envelope(_envelope([]), court_db=court_db)

    assert report["source_status"] == "no_results"
    assert report["projected"]["cases"] == 0
    db = sqlite3.connect(court_db)
    try:
        assert db.execute("SELECT COUNT(*) FROM source_snapshot").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM case_record").fetchone()[0] == 0
    finally:
        db.close()


class _FakeResponse:
    def __init__(
        self,
        *,
        text: str = "",
        url: str,
        payload: Any = None,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = 200
        self.headers: dict[str, str] = {}
        self.content = text.encode()
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.requests.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {method} {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_adapter_monitor_probe_stops_after_first_known_continuation() -> None:
    continuation = _fixture_json("docket_page_2.json")
    continuation["nextKey"] = "opaque-next-key-not-emitted"
    session = _FakeSession(
        [
            _FakeResponse(text=_fixture_text("disclaimer.html"), url=franklin.BASE_URL),
            _FakeResponse(
                text=_fixture_text("welcome.html"),
                url=f"{franklin.BASE_URL}Welcome.jsp",
            ),
            _FakeResponse(
                text=_fixture_text("name_results_complete.html"),
                url=franklin.NAME_SEARCH_URL,
            ),
            _FakeResponse(
                text=_fixture_text("case_detail.html"),
                url=franklin.CASE_SEARCH_URL,
            ),
            _FakeResponse(
                text=json.dumps(continuation),
                payload=continuation,
                url=franklin.DOCKET_URL,
            ),
        ]
    )
    client = franklin.FranklinCourtClient(
        session=session,
        minimum_interval=0,
        request_budget=5,
    )

    snapshot = client.probe_contract()
    client.close()

    assert snapshot.request_count == 5
    assert snapshot.party_sentinel_case_number == "20CV003259"
    assert snapshot.party_matching_count == 1
    assert snapshot.party_coverage_complete is True
    assert snapshot.party_result_field_names[:3] == (
        "CASE",
        "CASE TYPE",
        "NAME",
    )
    assert "recs" in snapshot.party_search_field_names
    assert snapshot.initial_next_key_present is True
    assert snapshot.continuation_next_key_present is True
    assert snapshot.record["docket_retrieval"]["exhausted"] is False
    assert len(session.requests) == 5
    assert session.closed is True
    serialized = json.dumps(snapshot.record)
    assert "fixture-session-token" not in serialized
    assert "fixture-coordinate" not in serialized
    assert "opaque-next-key" not in serialized


def _monitor_snapshot() -> franklin.FranklinProbeSnapshot:
    return franklin.FranklinProbeSnapshot(
        record=_fixture_case_record(),
        disclaimer_path="/CaseInformationOnline/acceptDisclaimer",
        disclaimer_method="POST",
        disclaimer_field_names=("Accept", "fromPage"),
        party_search_field_names=(
            "advFlag",
            "attyNum",
            "caseSeq",
            "caseSeq_h",
            "caseType",
            "caseType_h",
            "caseYear",
            "caseYear_h",
            "fname",
            "lname",
            "mint",
            "personType",
            "reallySubmit",
            "recs",
            "selType",
            "txtCalendar1",
            "txtCalendar2",
        ),
        party_result_field_names=(
            "CASE",
            "CASE TYPE",
            "NAME",
            "PARTY TYPE",
            "FILED",
            "STATUS",
        ),
        party_sentinel_case_number="20CV003259",
        party_matching_count=1,
        party_coverage_complete=True,
        case_search_field_names=(
            "advFlag",
            "attyNum",
            "caseSeq",
            "caseSeq_h",
            "caseType",
            "caseType_h",
            "caseYear",
            "caseYear_h",
            "fname",
            "lname",
            "mint",
            "personType",
            "reallySubmit",
            "selType",
            "txtCalendar1",
            "txtCalendar2",
        ),
        docket_request_field_names=(
            "caseSeq",
            "caseType",
            "caseYear",
            "docketdatekey",
            "docketdir",
        ),
        docket_response_field_names=(
            "data",
            "imageArray",
            "nextKey",
            "priorKey",
        ),
        initial_next_key_present=True,
        continuation_next_key_present=False,
        request_count=5,
    )


class _MonitorClient:
    def __init__(self, snapshot: franklin.FranklinProbeSnapshot) -> None:
        self.snapshot = snapshot
        self.closed = False

    def probe_contract(self, case_number: str):
        assert case_number == franklin.PROBE_CASE_NUMBER
        return self.snapshot

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


def test_monitor_hashes_stable_contract_separately_from_rolling_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _monitor_snapshot()
    rolling_record = copy.deepcopy(dict(base.record))
    rolling_record["status"] = "REOPENED"
    rolling_record["judge"] = "ANOTHER JUDGE"
    rolling_record["docket_entries"].append(
        {
            **copy.deepcopy(rolling_record["docket_entries"][-1]),
            "native_entry_id": "franklin:docket:rolling",
            "sequence_no": 7,
            "filed_date": "2026-07-31",
        }
    )
    rolling = replace(
        base,
        record=rolling_record,
        continuation_next_key_present=True,
    )
    schema_changed = replace(
        base,
        docket_response_field_names=(
            *base.docket_response_field_names,
            "newField",
        ),
    )
    queued = [base, rolling, schema_changed, base]
    clients: list[_MonitorClient] = []

    def client_factory(**kwargs):
        assert kwargs["request_budget"] == 5
        client = _MonitorClient(queued.pop(0))
        clients.append(client)
        return client

    monkeypatch.setattr(franklin, "FranklinCourtClient", client_factory)
    first = probe_franklin_cio(_probe_context())
    second = probe_franklin_cio(_probe_context())
    third = probe_franklin_cio(_probe_context())
    monkeypatch.setattr(
        franklin,
        "DOCKET_URL",
        f"{franklin.BASE_URL}changed-docket-route",
    )
    fourth = probe_franklin_cio(_probe_context())

    assert first.schema_sha256 == second.schema_sha256
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.schema_sha256 != third.schema_sha256
    assert first.artifact_sha256 == third.artifact_sha256
    assert first.schema_sha256 == fourth.schema_sha256
    assert first.artifact_sha256 != fourth.artifact_sha256
    assert all(client.closed for client in clients)
    assert first.result_count == 1
    details = json.dumps(first.details)
    for opaque in (
        "fixture-session-token",
        "fixture-coordinate",
        "797786999950000",
    ):
        assert opaque not in details
    assert first.details["rolling_observation"]["request_count"] == 5
    assert first.details["rolling_observation"][
        "party_sentinel_case_number"
    ] == "20CV003259"


def test_monitor_registry_declares_fixed_five_request_contract() -> None:
    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]

    assert spec.capability == "probe_source"
    assert spec.expected_requests == 5
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is probe_franklin_cio


def test_manifest_census_search_plan_source_report_and_citation(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    assert source["jurisdiction_geoids"] == ["39049"]
    assert source["roles"][0] == "trial_case_index"
    assert "party_name_index" in source["roles"]
    assert "trial_court_rulings" not in source["roles"]
    assert source["stable_keys"] == [
        "normalized_case_number",
        "party_query_fingerprint_plus_response_ordinal",
        "native_entry_id",
        "native_document_id",
    ]
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
        "discovery",
        "probe",
    ]
    assert "search" in shared["details"]["shared_operations"]
    assert source["census_associations"][0]["role"] == "trial_case_index"

    census = yaml.safe_load(
        Path("config/public_records_census.yaml").read_text(encoding="utf-8")
    )
    assert any(
        target["jurisdiction_geoid"] == "39049"
        and target["domain"] == "court"
        and target["role"] == "trial_case_index"
        for target in census["additional_targets"]
    )

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == franklin.BASE_URL

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["39049"],
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
        "search_cases",
        "fetch_case",
        "fetch_document",
        "list_docket_entries",
        "list_document_index",
    }
    assert tasks["fetch_case"]["capability_details"][
        "requires_prior_selector"
    ] == "raw_case_number"
    prior_input = next(
        value
        for value in tasks["fetch_case"]["runtime_inputs"]
        if value["name"] == "declared_prior_selectors"
    )
    assert prior_input["fields"] == ["case_number", "raw_case_number"]
    assert any(
        SOURCE_ID_PART in task_id
        for task_id in prior_input["from_tasks"]
        for SOURCE_ID_PART in ("us-oh-franklin-sheriff-realauction",)
    )
    complements = next(
        group
        for group in plan["complementary_routes"]
        if group["primary_source_id"] == SOURCE_ID
    )
    assert {
        row["source_id"] for row in complements["complements"]
    } >= {
        "us-oh-franklin-sheriff-realauction",
        "us-oh-franklin-county-recorder-publicsearch",
        "us-oh-franklin-county-auditor-property",
    }

    report = source_report.check_public_records_catalog(catalog_path)
    entry = report[
        "Public records / Franklin County Clerk of Courts "
        "Case Information Online"
    ]
    assert entry["source_id"] == SOURCE_ID
    assert entry["query_tool"] == "tools/query_state_courts.py"
