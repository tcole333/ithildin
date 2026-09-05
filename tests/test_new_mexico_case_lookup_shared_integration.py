from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools import query_new_mexico_case_lookup as nm
from tools import query_state_courts
from tools import public_records_monitor
from tools import source_report
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_monitor import (
    ProbeContext,
    probe_new_mexico_case_lookup,
)
from tools.public_records_search_plan import build_search_plan
from tools.seed_public_records_catalog import (
    DEFAULT_CONFIG_PATH,
    seed_catalog,
)


SOURCE_ID = nm.SOURCE_ID
CASE_NUMBER = nm.PROBE_CASE_NUMBER


class _Catalog:
    def show_source(self, source_id: str) -> dict[str, Any]:
        assert source_id == SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": nm.SOURCE_NAME,
                "official_url": nm.BASE_URL,
                "authority": "New Mexico Judiciary",
                "platform_family": nm.PLATFORM_FAMILY,
            },
            "roles": ["trial_case_index", "appellate_case_index"],
            "capabilities": [
                {"name": "search_parties", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_claims", "supported": True},
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
            "reason": "review permits the verified source operations",
            "reason_code": "allowed",
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _Catalog(),
    )
    monkeypatch.setattr(query_state_courts, "log_search", lambda *_args: None)


def _empty_result(operation: str) -> PublicRecordsResult:
    return PublicRecordsResult.success(
        PublicRecordsQuery(
            source=nm._source_metadata(),
            jurisdiction=nm._jurisdiction(),
            query=QueryMetadata(operation=operation, parameters={}),
        ),
        [],
    )


def _court() -> dict[str, Any]:
    return {
        "court_id": "nm-case-lookup-d-101",
        "name": "SANTA FE DISTRICT",
        "state_code": "NM",
        "level": "trial",
        "source_native_court_code": "D-101",
        "source_native_court_type": "D",
        "source_native_location_code": "101",
        "court_type_name": "District Court",
    }


def _search_hit() -> dict[str, Any]:
    return {
        "canonical_ref": "STATECOURT:NM:SEARCH-HIT",
        "source_id": SOURCE_ID,
        "record_kind": "case_party_search_hit",
        "case_number": CASE_NUMBER,
        "court": _court(),
        "caption": "OLIN PARTNERSHIP LTD V EPSTEIN",
        "filing_date": "1996-10-17",
        "current_judge": "Herrera, Steve",
        "matched_party": {
            "name": "EPSTEIN JEFFREY",
            "role": "Defendant",
            "party_number": "1",
            "date_of_birth_raw": None,
        },
        "source_occurrence_id": "search-occurrence-defendant",
        "source_url": nm.BASE_URL,
    }


def _detail_record() -> dict[str, Any]:
    parties = [
        ("CD", "Counter Defendant", "1", "OLIN PARTNERSHIP LTD", []),
        (
            "CP",
            "Counter Plaintiff",
            "1",
            "EPSTEIN JEFFREY",
            [{"name": "VADNAIS DOUGLAS R."}],
        ),
        (
            "D",
            "Defendant",
            "1",
            "EPSTEIN JEFFREY",
            [{"name": "VADNAIS DOUGLAS R."}],
        ),
        (
            "P",
            "Plaintiff",
            "1",
            "OLIN PARTNERSHIP LTD",
            [{"name": "VAN BUSKIRK TOM"}],
        ),
    ]
    register = [
        {
            "native_entry_id": f"derived:register-{index:02d}",
            "native_entry_id_kind": (
                "derived_from_published_row_fields_and_duplicate_ordinal"
            ),
            "event_date": (
                "1998-03-09" if index == 1 else f"1996-10-{index:02d}"
            ),
            "event_description": (
                "CLS: STIPULATED DISMISSAL"
                if index == 1
                else f"EVENT {index}"
            ),
            "event_result": None,
            "party_type": None,
            "party_number": None,
            "amount_raw": None,
            "detail_text": (
                "STIPULATION OF DISMISSAL"
                if index == 1
                else f"DETAIL {index}"
            ),
        }
        for index in range(1, 15)
    ]
    judge_history = [
        ("1996-10-17", "Herrera, Steve", "1", "INITIAL ASSIGNMENT"),
        (
            "1996-11-16",
            "Awaiting, Assignment",
            "2",
            "Judge Assignment Notice",
        ),
        (
            "1997-01-21",
            "Pfeffer, Stephen D.",
            "3",
            "Assigned Before Automation",
        ),
        ("1997-06-11", "Herrera, Steve", "4", "Transfer Assignment"),
    ]
    return {
        "canonical_ref": "STATECOURT:NM:CASE",
        "source_id": SOURCE_ID,
        "record_kind": "new_mexico_case_detail",
        "case_number": CASE_NUMBER,
        "court": _court(),
        "caption": "OLIN PARTNERSHIP LTD V EPSTEIN",
        "current_judge": "Herrera, Steve",
        "filing_date_raw": "10/17/1996",
        "filing_date": "1996-10-17",
        "parties": [
            {
                "name": name,
                "role_code": role_code,
                "role": role,
                "party_number": number,
                "attorneys": attorneys,
            }
            for role_code, role, number, name, attorneys in parties
        ],
        "complaint_records": [
            {
                "source_child_id": "derived:complaint-1",
                "fields": {
                    "complaint_date": "10/17/1996",
                    "complaint_seq": "1",
                    "complaint_description": "OPN: COMPLAINT",
                    "disposition": "",
                    "disposition_date": "",
                },
                "values": ["10/17/1996", "1", "OPN: COMPLAINT", "", ""],
            }
        ],
        "cause_records": [
            {
                "source_child_id": "derived:cause-breach-contract",
                "source_child_id_kind": (
                    "derived_from_published_fields_and_duplicate_ordinal"
                ),
                "fields": {
                    "coa_sequence": "1",
                    "coa_description": "Breach of Contract",
                },
                "values": ["1", "Breach of Contract"],
            }
        ],
        "disposition_records": [],
        "register_of_actions": register,
        "judge_assignment_history": [
            {
                "assignment_event_id": f"derived:judge-{sequence}",
                "assignment_event_id_kind": (
                    "derived_from_published_row_fields_and_duplicate_ordinal"
                ),
                "assignment_date": date,
                "judge_name": judge,
                "sequence_number": sequence,
                "assignment_event_description": description,
            }
            for date, judge, sequence, description in judge_history
        ],
        "case_detail_sections": [
            {
                "title": "Civil Complaint Detail",
                "groups": [
                    {
                        "headers": ["COA Sequence #", "COA Description"],
                        "records": [
                            {
                                "values": ["1", "Breach of Contract"],
                                "fields": {
                                    "coa_sequence": "1",
                                    "coa_description": "Breach of Contract",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
        "documents_available": False,
        "source_url": nm.BASE_URL,
        "source_internal_case_locator": None,
    }


def _envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    return PublicRecordsResult.success(
        PublicRecordsQuery(
            source=nm._source_metadata(),
            jurisdiction=nm._jurisdiction(),
            query=QueryMetadata(operation="case", parameters={}),
        ),
        records,
    ).to_dict()


def test_shared_search_has_no_implicit_limit_and_uses_native_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(nm, "execute", fake_execute)
    for argv in (
        ["search", "Epstein Jeffrey", "--source", SOURCE_ID],
        [
            "search",
            "Epstein",
            "--first-name",
            "Jeffrey",
            "--source",
            SOURCE_ID,
            "--limit",
            "35",
        ],
    ):
        payload = query_state_courts.execute(
            query_state_courts.build_parser().parse_args(argv)
        )
        assert payload["status"] == "no_results"

    assert calls[0].party_name == "Epstein Jeffrey"
    assert calls[0].limit is None
    assert calls[0].native_page_size == 20
    assert calls[1].party_name == "Epstein Jeffrey"
    assert calls[1].limit == 35
    assert calls[1].native_page_size == 40


def test_shared_exact_case_docket_and_claims_use_one_exact_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    calls: list[Any] = []

    def fake_execute(args):
        calls.append(args)
        return _empty_result(args.command)

    monkeypatch.setattr(nm, "execute", fake_execute)
    for operation in ("case", "docket", "claims"):
        payload = query_state_courts.execute(
            query_state_courts.build_parser().parse_args(
                [operation, CASE_NUMBER, "--source", SOURCE_ID]
            )
        )
        assert payload["status"] == "no_results"

    assert [call.command for call in calls] == ["case", "case", "case"]
    assert all(call.case_number == CASE_NUMBER for call in calls)
    guidance = query_state_courts._source_guidance(SOURCE_ID)
    assert guidance["unified_operations"] == [
        "case",
        "claims",
        "discovery",
        "docket",
        "probe",
        "search",
    ]
    assert "documents" not in guidance["unified_operations"]


def test_sparse_then_exact_ingest_reconciles_case_and_preserves_raw_children(
    tmp_path: Path,
) -> None:
    court_db = tmp_path / "state-courts.db"

    sparse = ingest_envelope(_envelope([_search_hit()]), court_db=court_db)
    exact = ingest_envelope(_envelope([_detail_record()]), court_db=court_db)

    assert sparse["projected"]["cases"] == 1
    assert exact["projected"]["cases"] == 1
    assert exact["projected"]["parties"] == 4
    assert exact["projected"]["docket_entries"] == 14
    assert exact["projected"]["claims"] == 1
    assert exact["projected"]["case_events"] == 4
    assert exact["projected"]["documents"] == 0

    db = sqlite3.connect(court_db)
    db.row_factory = sqlite3.Row
    try:
        case = db.execute(
            """
            SELECT raw_case_number, source_internal_id, caption, case_type,
                   disposition_date, status, raw_json
            FROM case_record
            """
        ).fetchone()
        assert case["raw_case_number"] == CASE_NUMBER
        assert case["source_internal_id"] is None
        assert case["caption"] == "OLIN PARTNERSHIP LTD V EPSTEIN"
        assert case["case_type"] == "CV"
        assert case["disposition_date"] is None
        assert case["status"] is None
        raw_case = json.loads(case["raw_json"])
        assert raw_case["documents_available"] is False
        assert raw_case["case_detail_sections"][0]["title"] == (
            "Civil Complaint Detail"
        )

        parties = list(
            db.execute(
                "SELECT role, raw_name FROM case_party ORDER BY sequence_no"
            )
        )
        assert [(row["role"], row["raw_name"]) for row in parties] == [
            ("Counter Defendant", "OLIN PARTNERSHIP LTD"),
            ("Counter Plaintiff", "EPSTEIN JEFFREY"),
            ("Defendant", "EPSTEIN JEFFREY"),
            ("Plaintiff", "OLIN PARTNERSHIP LTD"),
        ]
        assert db.execute(
            "SELECT COUNT(*) FROM attorney"
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM case_representation"
        ).fetchone()[0] == 3

        entries = list(
            db.execute(
                """
                SELECT native_entry_id, raw_text, status, document_available
                FROM docket_entry ORDER BY sequence_no
                """
            )
        )
        assert len(entries) == 14
        assert entries[0]["native_entry_id"] == "derived:register-01"
        assert "STIPULATION OF DISMISSAL" in entries[0]["raw_text"]
        assert entries[0]["status"] is None
        assert entries[0]["document_available"] == 0

        events = list(
            db.execute(
                "SELECT disposition, raw_json FROM case_event"
            )
        )
        assert len(events) == 4
        assert all(event["disposition"] is None for event in events)
        assert any(
            json.loads(event["raw_json"])["judge_name"]
            == "Awaiting, Assignment"
            for event in events
        )
        officers = {
            row["raw_name"]
            for row in db.execute(
                "SELECT raw_name FROM judicial_officer"
            )
        }
        assert officers == {"Herrera, Steve", "Pfeffer, Stephen D."}

        claim = db.execute(
            """
            SELECT native_claim_id, claim_type, status, raw_json
            FROM case_claim
            """
        ).fetchone()
        assert claim["native_claim_id"] == (
            "nm-case-lookup:cause:cause-breach-contract"
        )
        assert claim["claim_type"] == "civil_cause_of_action"
        assert claim["status"] is None
        assert json.loads(claim["raw_json"])["description"] == (
            "Breach of Contract"
        )
        assert db.execute(
            "SELECT COUNT(*) FROM document_artifact"
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_monitor_uses_fixed_exact_case_budget_and_separates_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail = _detail_record()
    live = {
        "detail": detail,
        "schema_fingerprint": "a" * 64,
    }
    calls: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)
            self.request_count = nm.PROBE_EXPECTED_REQUESTS
            self.closed = False

        def exact_case(self, case_number: str) -> nm.ExactCasePage:
            assert case_number == CASE_NUMBER
            return nm.ExactCasePage(
                record=live["detail"],
                source_url=nm.BASE_URL,
                schema_fingerprint=live["schema_fingerprint"],
                authoritative_no_results=False,
            )

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(nm, "NewMexicoCaseLookupClient", FakeClient)
    observation = probe_new_mexico_case_lookup(
        ProbeContext(
            source_id=SOURCE_ID,
            catalog_decision={
                "limits": {"minimum_interval_seconds": 0.4}
            },
            timeout=30,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert observation.status == "ok"
    assert observation.result_count == 1
    assert calls[0]["request_budget"] == nm.PROBE_EXPECTED_REQUESTS == 4
    assert calls[0]["minimum_interval"] == 0.4
    details = observation.details
    assert details["artifact_identity"]["sentinel_case_number"] == (
        CASE_NUMBER
    )
    assert details["stable_contract"]["documents"][
        "case_lookup_documents_available"
    ] is False
    assert details["rolling_observation"][
        "sentinel_register_entry_count"
    ] == 14
    assert details["schema_contract"]["live_schema_fingerprint"] == "a" * 64
    serialized = json.dumps(details)
    assert "csrfToken" not in serialized
    assert "session=T" not in serialized
    assert public_records_monitor.HANDLER_REGISTRY[
        SOURCE_ID
    ].expected_requests == 4

    changed_rolling_detail = copy.deepcopy(detail)
    changed_rolling_detail["caption"] = "UPDATED SENTINEL CAPTION"
    changed_rolling_detail["current_judge"] = "Updated, Judge"
    changed_rolling_detail["register_of_actions"] = (
        changed_rolling_detail["register_of_actions"][:-1]
    )
    live["detail"] = changed_rolling_detail
    changed_rolling = probe_new_mexico_case_lookup(
        ProbeContext(
            source_id=SOURCE_ID,
            catalog_decision={
                "limits": {"minimum_interval_seconds": 0.4}
            },
            timeout=30,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert changed_rolling.artifact_sha256 == observation.artifact_sha256
    assert changed_rolling.schema_sha256 == observation.schema_sha256
    assert changed_rolling.details["rolling_observation"][
        "sentinel_caption"
    ] == "UPDATED SENTINEL CAPTION"
    assert changed_rolling.details["rolling_observation"][
        "sentinel_register_entry_count"
    ] == 13

    monkeypatch.setattr(nm, "EXPECTED_PATH", "/caselookup/app-v2")
    changed_route_contract = probe_new_mexico_case_lookup(
        ProbeContext(
            source_id=SOURCE_ID,
            catalog_decision={
                "limits": {"minimum_interval_seconds": 0.4}
            },
            timeout=30,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert (
        changed_route_contract.artifact_sha256
        != observation.artifact_sha256
    )
    assert changed_route_contract.schema_sha256 == observation.schema_sha256

    monkeypatch.setattr(
        nm,
        "CASE_NUMBER_SEARCH_FORM_ID",
        "caseNumberSearchFormV2",
    )
    changed_schema_contract = probe_new_mexico_case_lookup(
        ProbeContext(
            source_id=SOURCE_ID,
            catalog_decision={
                "limits": {"minimum_interval_seconds": 0.4}
            },
            timeout=30,
            max_attempts=1,
            sample_bytes=None,
        )
    )

    assert (
        changed_schema_contract.artifact_sha256
        == changed_route_contract.artifact_sha256
    )
    assert (
        changed_schema_contract.schema_sha256
        != changed_route_contract.schema_sha256
    )


def test_ingest_rejects_court_and_child_identity_mismatches(
    tmp_path: Path,
) -> None:
    wrong_court = _detail_record()
    wrong_court["court"]["court_id"] = "nm-case-lookup-d-999"
    with pytest.raises(ValueError, match="court_id disagrees"):
        ingest_envelope(
            _envelope([wrong_court]),
            court_db=tmp_path / "wrong-court.db",
        )

    mutations = [
        ("register_of_actions", "native_entry_id_kind"),
        ("judge_assignment_history", "assignment_event_id_kind"),
        ("cause_records", "source_child_id_kind"),
    ]
    for index, (collection, field) in enumerate(mutations):
        record = copy.deepcopy(_detail_record())
        record[collection][0].pop(field)
        with pytest.raises(ValueError, match="identity"):
            ingest_envelope(
                _envelope([record]),
                court_db=tmp_path / f"wrong-child-{index}.db",
            )


def test_manifest_census_citation_catalog_and_search_plan(
    tmp_path: Path,
) -> None:
    config = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    source = next(
        row for row in config["sources"] if row["source_id"] == SOURCE_ID
    )
    assert source["roles"][:2] == [
        "trial_case_index",
        "appellate_case_index",
    ]
    assert source["jurisdiction_geoids"] == ["35"]
    assert source["identity_contract"]["case_identity"] == (
        "full_case_number_plus_derived_court"
    )
    assert source["identity_contract"]["tapestry_session_locator"] == (
        "transport_only"
    )
    assert source["source_response_contract"]["default_caller_result_cap"] is None
    assert source["source_response_contract"]["acquisition_grain"] == (
        "one_individual_electronic_case_record"
    )
    assert {
        association["role"]
        for association in source["census_associations"]
    } == {"trial_case_index", "appellate_case_index"}
    research_nm = next(
        complement
        for complement in source["official_complements"]
        if complement["name"] == "re:SearchNM"
    )
    assert research_nm["identity_relationship"] == (
        "overlapping_case_identity_with_additional_document_child_coverage"
    )
    assert research_nm["independent_evidence_when_same_record"] is False

    shared = next(
        capability
        for capability in source["capabilities"]
        if capability["name"] == "query_shared_state_courts"
    )
    assert shared["details"]["shared_operations"] == [
        "search",
        "case",
        "docket",
        "claims",
        "discovery",
        "probe",
    ]
    spec = public_records_monitor.HANDLER_REGISTRY[SOURCE_ID]
    assert spec.expected_requests == 4
    assert spec.sentinel_record_count == 1
    assert spec.sample_bytes is None
    assert spec.handler is probe_new_mexico_case_lookup

    source_urls = json.loads(
        Path("web/src/data/source-urls.json").read_text(encoding="utf-8")
    )
    assert source_urls[f"STATECOURT_SOURCE:{SOURCE_ID}"] == nm.BASE_URL

    catalog_path = tmp_path / "catalog.db"
    seed_catalog(db_path=catalog_path)
    plan = build_search_plan(
        "Example Person",
        jurisdictions=["35"],
        catalog_db=catalog_path,
        investigation_db=tmp_path / "missing-investigation.db",
    )
    planned_source = next(
        row for row in plan["sources"] if row["source_id"] == SOURCE_ID
    )
    assert planned_source["access"]["mode"] == "allowed_with_limits"
    tasks = {
        task["capability"]
        for stage in plan["workflow"]["stages"]
        if stage["stage_id"] == "court"
        for task in stage["tasks"]
        if task["source_id"] == SOURCE_ID
    }
    assert {
        "search_parties",
        "fetch_case",
        "list_docket_entries",
    }.issubset(tasks)

    report = source_report.check_public_records_catalog(catalog_path)
    entry = report[
        "Public records / New Mexico Judiciary Case Lookup"
    ]
    assert entry["source_id"] == SOURCE_ID
    assert entry["query_tool"] == "tools/query_state_courts.py"
