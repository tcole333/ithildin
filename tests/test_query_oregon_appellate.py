from __future__ import annotations

import json
import os
import sqlite3
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_appellate
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_http import HTTPStatusError


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_appellate"
)
COURT_UUID = query_oregon_appellate.COURT_OF_APPEALS_UUID
CASE_UUID = "b56815c0-766d-4c8f-835f-62e34713d15f"


def _fixture(name: str) -> Any:
    return json.loads((FIXTURE_DIR / name).read_text())


def _hal(
    records: list[dict[str, Any]],
    *,
    page: int = 0,
    size: int = 2,
    total: int | None = None,
    omit_embedded: bool = False,
) -> dict[str, Any]:
    total_elements = len(records) if total is None else total
    payload: dict[str, Any] = {
        "page": {
            "size": size,
            "totalElements": total_elements,
            "totalPages": (
                0
                if total_elements == 0
                else (total_elements + size - 1) // size
            ),
            "number": page,
        }
    }
    if not omit_embedded:
        payload["_embedded"] = {"results": records}
    return payload


def _case_row(case_uuid: str, number: str) -> dict[str, Any]:
    return {
        "caseHeader": {
            "caseInstanceUUID": case_uuid,
            "caseNumber": number,
            "caseTitle": f"State v. {number}",
            "courtID": "1",
            "filedDate": "2026-01-01T00:00:00.000+00:00",
        }
    }


@dataclass
class FixtureResponse:
    payload: Any = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""

    def json(self):
        return self.payload


class QueueTransport:
    def __init__(self, responses: list[FixtureResponse]):
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method, url, *, params=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected Oregon appellate request")
        return self.responses.pop(0)


def _court() -> query_oregon_appellate.OregonAppellateCourt:
    return query_oregon_appellate.OregonAppellateCourt(
        resource_uuid=COURT_UUID,
        external_id="1",
        display_name="Oregon Court of Appeals",
        active=True,
        raw=_fixture("courts.json")["_embedded"]["results"][0],
    )


def _fetch(
    records: list[dict[str, Any]],
    *,
    next_cursor: str | None = None,
    total: int | None = None,
    source_ceiling: bool = False,
) -> query_oregon_appellate.SpringFetch:
    total_elements = len(records) if total is None else total
    return query_oregon_appellate.SpringFetch(
        records=tuple(records),
        next_cursor=next_cursor,
        schema={"kind": "fixture"},
        schema_fingerprint="a" * 64,
        pages_fetched=1,
        requests_made=1,
        total_elements=total_elements,
        total_pages=0 if total_elements == 0 else 1,
        page_size=100,
        start_offset=0,
        end_offset=len(records),
        source_ceiling=source_ceiling,
        complete=not source_ceiling and len(records) >= total_elements,
        cursor_anchor_verified=False,
        count_changed_since_cursor=False,
    )


def _args(command: str, **overrides: Any) -> Namespace:
    values = {
        "command": command,
        "query": None,
        "case_number": None,
        "field": "auto",
        "match_mode": "contains",
        "court": None,
        "filed_after": None,
        "filed_before": None,
        "after": None,
        "before": None,
        "docket_entry_uuid": None,
        "document_uuid": None,
        "limit": None,
        "page_size": 100,
        "cursor": None,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "max_attempts": 1,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_official_fixtures_preserve_courts_and_case_relations():
    transport = QueueTransport(
        [
            FixtureResponse(_fixture("courts.json")),
            FixtureResponse(_fixture("case_search_a182332.json")),
        ]
    )
    client = query_oregon_appellate.OregonAppellateClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search_cases(
        "A182332",
        field="number",
        match_mode="exact",
        court="coa",
        requested_limit=1,
        page_size=5,
    )
    record = query_oregon_appellate._case_record(
        client,
        query_oregon_appellate._case_header(fetched.records[0]),
        schema=fetched.schema_fingerprint,
        retrieval=query_oregon_appellate._fetch_metadata(fetched),
    )

    assert record["raw_case_number"] == "A182332"
    assert record["court"]["court_id"] == COURT_UUID
    assert record["case_relations"] == [
        {
            "relation_type": "originating_trial_case",
            "raw_case_number": "23CR01926",
            "court_name": "Coos County Circuit Court",
            "county": "Coos",
            "access_state": "public",
            "source_url": query_oregon_appellate.PORTAL_SEARCH,
            "raw": {
                "originatingCourtName": "Coos County Circuit Court",
                "originatingCaseNumber": "23CR01926",
            },
        }
    ]
    params = transport.calls[1]["params"]
    assert params["caseHeader.courtID"] == COURT_UUID
    assert params["caseHeader.caseNumberSearchType"] == "10462"
    assert params["page"] == 0


def test_query_bound_cursor_verifies_anchor_before_continuing():
    rows = [
        _case_row("00000000-0000-0000-0000-000000000001", "A000001"),
        _case_row("00000000-0000-0000-0000-000000000002", "A000002"),
        _case_row("00000000-0000-0000-0000-000000000003", "A000003"),
    ]
    params = {
        "caseHeader.caseTitle": "State",
        "caseHeader.caseTitleSearchType": "10463",
        "sort": (
            "caseHeader.filedDate,desc",
            "caseHeader.caseInstanceUUID,asc",
        ),
    }
    transport = QueueTransport(
        [FixtureResponse(_hal(rows[:2], size=2, total=3))]
    )
    client = query_oregon_appellate.OregonAppellateClient(
        transport=transport,
        minimum_interval=0,
    )
    first = client._fetch_hal(
        query_oregon_appellate.CASE_SEARCH_URL,
        params=params,
        requested_limit=1,
        page_size=2,
        anchor_kind="case",
    )
    assert first.next_cursor is not None
    assert first.end_offset == 1

    transport.responses.extend(
        [
            FixtureResponse(_hal(rows[:2], size=2, total=3)),
            FixtureResponse(_hal(rows[:2], size=2, total=3)),
        ]
    )
    second = client._fetch_hal(
        query_oregon_appellate.CASE_SEARCH_URL,
        params=params,
        requested_limit=1,
        page_size=2,
        cursor=first.next_cursor,
        anchor_kind="case",
    )

    assert second.cursor_anchor_verified is True
    assert second.records[0]["caseHeader"]["caseNumber"] == "A000002"
    assert second.start_offset == 1
    assert [call["params"]["page"] for call in transport.calls] == [0, 0, 0]


def test_cursor_rejects_query_reuse_and_changed_boundary():
    rows = [
        _case_row("00000000-0000-0000-0000-000000000001", "A000001"),
        _case_row("00000000-0000-0000-0000-000000000002", "A000002"),
    ]
    params = {"query": "one", "sort": "caseHeader.caseInstanceUUID,asc"}
    client = query_oregon_appellate.OregonAppellateClient(
        transport=QueueTransport(
            [FixtureResponse(_hal(rows, size=2, total=2))]
        ),
        minimum_interval=0,
    )
    first = client._fetch_hal(
        query_oregon_appellate.CASE_SEARCH_URL,
        params=params,
        requested_limit=1,
        page_size=2,
        anchor_kind="case",
    )
    assert first.next_cursor

    with pytest.raises(
        query_oregon_appellate.OregonAppellateSelectionError,
        match="different Oregon appellate query",
    ):
        client._fetch_hal(
            query_oregon_appellate.CASE_SEARCH_URL,
            params={"query": "two"},
            requested_limit=1,
            page_size=2,
            cursor=first.next_cursor,
            anchor_kind="case",
        )

    changed = [
        _case_row("00000000-0000-0000-0000-000000000099", "A999999"),
        rows[1],
    ]
    client.transport = QueueTransport(
        [FixtureResponse(_hal(changed, size=2, total=2))]
    )
    with pytest.raises(
        query_oregon_appellate.OregonAppellateSelectionError,
        match="ordering changed",
    ):
        client._fetch_hal(
            query_oregon_appellate.CASE_SEARCH_URL,
            params=params,
            requested_limit=1,
            page_size=2,
            cursor=first.next_cursor,
            anchor_kind="case",
        )


def test_source_ceiling_is_explicit_partial_with_completeness_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    row = _case_row(CASE_UUID, "A182332")
    client = query_oregon_appellate.OregonAppellateClient(
        transport=QueueTransport(
            [
                FixtureResponse(
                    _hal(
                        [row],
                        size=1,
                        total=query_oregon_appellate.SOURCE_RESULT_LIMIT,
                    )
                )
            ]
        ),
        minimum_interval=0,
    )
    client._courts = (_court(),)
    monkeypatch.setattr(query_oregon_appellate, "log_search", lambda *args: None)

    result = query_oregon_appellate.execute(
        _args(
            "search-case",
            query="A182332",
            field="number",
            match_mode="exact",
            limit=1,
            page_size=1,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "partial"
    assert result.errors[0].code == "source_result_ceiling"
    record = result.to_dict()["records"][0]
    assert record["retrieval"]["source_ceiling_reached"] is True
    assert record["retrieval"]["completeness"] == "bounded_by_native_ceiling"


def test_party_search_without_case_party_uuid_gets_stable_derived_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    row = {
        "partyHeader": {
            "partySubType": "Appellant",
            "partyActorInstance": {
                "displayName": "Wesley Blane Wear",
                "sortName": "Wear, Wesley Blane",
            },
        },
        "caseHeader": _fixture("case_detail_a182332.json")["caseHeader"],
        "namedPartyFlag": True,
        "nonPublicFlag": False,
    }
    client = query_oregon_appellate.OregonAppellateClient(
        transport=QueueTransport(
            [FixtureResponse(_hal([row], size=1, total=1))]
        ),
        minimum_interval=0,
    )
    client._courts = (_court(),)
    monkeypatch.setattr(query_oregon_appellate, "log_search", lambda *args: None)

    result = query_oregon_appellate.execute(
        _args(
            "search-party",
            query="Wesley Blane Wear",
            match_mode="match",
            limit=1,
            page_size=1,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "ok"
    party = result.to_dict()["records"][0]["parties"][0]
    assert party["source_identity_derived"] is True
    assert party["source_internal_id"].startswith("derived:")
    assert len(party["source_internal_id"]) == len("derived:") + 64


class CaseClient:
    def __init__(self):
        self.court = _court()
        self.case_search = _fixture("case_search_a182332.json")
        self.case_detail = _fixture("case_detail_a182332.json")
        self.docket = _fixture("docket_a182332.json")
        self.parties = _fixture("parties_a182332.json")
        self.documents = _fixture("documents_a182332.json")

    def search_cases(self, *_args, **_kwargs):
        return _fetch(self.case_search["_embedded"]["results"])

    def court_by_external_id(self, external_id):
        assert str(external_id) == "1"
        return self.court

    def resolve_court(self, selector):
        assert selector in {"1", "coa", COURT_UUID}
        return self.court

    def get_case(self, court_uuid, case_uuid):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return self.case_detail

    def case_parties(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch(self.parties["_embedded"]["results"])

    def docket_entries(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch(self.docket["_embedded"]["results"])

    def case_hearings(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch([])

    def case_judgments(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        raise HTTPStatusError(
            500,
            url=(
                f"{query_oregon_appellate.API_ROOT}/courts/{COURT_UUID}/cms/"
                f"cases/{CASE_UUID}/judgments"
            ),
            response_text='{"message":"Unexpected error"}',
        )

    def case_groups(self, court_uuid, case_uuid):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return ()

    def case_documents(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch(self.documents["_embedded"]["results"])


def test_case_preserves_successful_components_when_judgments_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(query_oregon_appellate, "log_search", lambda *args: None)
    result = query_oregon_appellate.execute(
        _args("case", case_number="A182332", court="coa"),
        catalog_decision={
            "source_id": query_oregon_appellate.SOURCE_ID,
            "allowed": True,
            "limits": {},
        },
        client=CaseClient(),
    )

    assert result.status.value == "partial"
    assert [error.code for error in result.errors] == [
        "judgments_http_status"
    ]
    case = result.to_dict()["records"][0]
    assert case["components"]["judgments"]["status"] == "unavailable"
    assert case["components"]["docket"]["complete"] is True
    assert len(case["parties"]) == 2
    assert len(case["docket_entries"]) == 2
    assert sum(
        len(entry["documents"]) for entry in case["docket_entries"]
    ) == 2
    file_states = {
        document["document_name"]: document["file_availability"]
        for entry in case["docket_entries"]
        for document in entry["documents"]
    }
    assert file_states == {
        "Brief - Answering": "unavailable",
        "Court Issued - Miscellaneous": "viewable",
    }

    report = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "state-courts.db",
    )
    assert report["projected"]["cases"] == 1
    assert report["projected"]["related_cases"] == 1
    assert report["projected"]["parties"] == 2
    assert report["projected"]["attorneys"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["documents"] == 2
    db = sqlite3.connect(tmp_path / "state-courts.db")
    try:
        assert db.execute(
            "SELECT raw_case_number FROM case_record "
            "WHERE source_internal_id=?",
            (CASE_UUID,),
        ).fetchone() == ("A182332",)
    finally:
        db.close()


def test_document_metadata_and_file_state_remain_separate():
    client = CaseClient()
    rows = client.documents["_embedded"]["results"]
    unavailable = query_oregon_appellate._document_record(client, rows[0])
    viewable = query_oregon_appellate._document_record(client, rows[1])

    assert unavailable["metadata_available"] is True
    assert unavailable["file_availability"] == "unavailable"
    assert unavailable["file_retrievable"] is False
    assert unavailable["source_url"] is None
    assert viewable["metadata_available"] is True
    assert viewable["file_availability"] == "viewable"
    assert viewable["file_retrievable"] is True
    assert viewable["source_url"].endswith(
        f"/case/{CASE_UUID}/docketentrydocuments/"
        "09a169c7-17bf-4eb5-9796-adac2d565c40"
    )


def test_calendar_uses_verified_date_filters_and_stable_sort(
    monkeypatch: pytest.MonkeyPatch,
):
    transport = QueueTransport(
        [
            FixtureResponse(_fixture("calendar.json")),
            FixtureResponse(_fixture("courts.json")),
        ]
    )
    client = query_oregon_appellate.OregonAppellateClient(
        transport=transport,
        minimum_interval=0,
    )
    monkeypatch.setattr(query_oregon_appellate, "log_search", lambda *args: None)

    result = query_oregon_appellate.execute(
        _args(
            "calendar",
            after="2026-01-01",
            before="2026-12-31",
            limit=1,
            page_size=1,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["event_date"] == "2026-01-06T17:00:00.000+00:00"
    params = transport.calls[0]["params"]
    assert params["startDateFrom"].startswith("2026-01-01T00:00:00")
    assert params["startDateTo"].startswith("2026-12-31T23:59:59")
    assert params["sort"] == ("startDate,asc", "eventUUID,asc")


def test_parser_exposes_required_commands_and_arguments():
    parser = query_oregon_appellate.build_parser()
    search = parser.parse_args(
        [
            "search-case",
            "A182332",
            "--field",
            "number",
            "--match-mode",
            "exact",
            "--court",
            "coa",
        ]
    )
    documents = parser.parse_args(
        [
            "document-metadata",
            "A182332",
            "--docket-entry-uuid",
            "f31aefc9-dff1-41e0-b813-64fa110a07bd",
        ]
    )
    calendar = parser.parse_args(
        ["calendar", "--after", "2026-01-01", "--court", "supreme"]
    )

    assert search.query == "A182332"
    assert search.field == "number"
    assert search.match_mode == "exact"
    assert documents.case_number == "A182332"
    assert documents.docket_entry_uuid.startswith("f31aefc9")
    assert calendar.after == "2026-01-01"
    commands = parser._subparsers._group_actions[0].choices
    assert {
        "courts",
        "search-case",
        "search-party",
        "case",
        "docket",
        "parties",
        "calendar",
        "document-metadata",
        "probe",
    } <= set(commands)


def test_access_decision_injection_blocks_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_oregon_appellate, "log_search", lambda *args: None)
    result = query_oregon_appellate.execute(
        _args("case", case_number="A182332"),
        access_decision={
            "source_id": query_oregon_appellate.SOURCE_ID,
            "allowed": False,
            "automation_disposition": "human_required",
            "reason_code": "review_required",
            "reason": "Review route",
        },
        client=object(),
    )
    mismatch = query_oregon_appellate.execute(
        _args("case", case_number="A182332"),
        catalog_decision={
            "source_id": "different-source",
            "allowed": True,
        },
        client=object(),
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "review_required"
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "catalog_decision_source_mismatch"
    with pytest.raises(ValueError, match="not both"):
        query_oregon_appellate.execute(
            _args("case", case_number="A182332"),
            catalog_decision={"allowed": True},
            access_decision={"allowed": True},
            client=object(),
        )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_APPELLATE") != "1",
    reason="set RUN_LIVE_OR_APPELLATE=1 for the official A182332 sentinel",
)
def test_live_a182332_exact_case_sentinel():
    args = query_oregon_appellate.build_parser().parse_args(
        [
            "search-case",
            "A182332",
            "--field",
            "number",
            "--match-mode",
            "exact",
            "--court",
            "coa",
            "--limit",
            "1",
            "--page-size",
            "5",
        ]
    )
    result = query_oregon_appellate.execute(args, log_results=False)

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.to_dict()["records"][0]
    assert record["raw_case_number"] == "A182332"
    assert record["source_internal_id"] == CASE_UUID
    assert record["court"]["court_id"] == COURT_UUID
