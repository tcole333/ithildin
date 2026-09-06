from __future__ import annotations

import subprocess
import sqlite3
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_florida_acis
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_http import PaginatedFetch


COURT_UUID = "68f021c4-6a44-4735-9a76-5360b2e8af13"
CASE_UUID = "197f956a-01c1-44f1-866f-47703f347ea3"
DOCKET_UUID = "c2df146c-5c3c-4628-8395-fb435115b3bc"
DOCUMENT_UUID = "a4c16c94-f015-4a5e-af16-fe097e195cfc"
EVENT_UUID = "39a9537b-2a08-4c3b-a78b-bb6acaaeb537"

COURT_ROW = {
    "resourceID": COURT_UUID,
    "externalIdentifier": "1",
    "displayName": "Supreme Court of Florida",
    "active": True,
    "locations": [
        {
            "locationID": 1000000,
            "locationName": "Supreme Court of Florida",
        }
    ],
}
CASE_HEADER = {
    "caseInstanceUUID": CASE_UUID,
    "caseNumber": "SC2026-0899",
    "caseTitle": "Publix Super Markets, Inc. v. ACE Property",
    "closedFlag": False,
    "caseClassification": "Discretionary Review",
    "courtID": "1",
    "filedDate": "2026-06-11T19:08:00.000+00:00",
}
PARTY_ROW = {
    "partyHeader": {
        "casePartyUUID": "party-uuid",
        "partyType": "Party",
        "partySubType": "Appellant",
        "partyStatus": "Active",
        "partyActorInstance": {
            "displayName": "Publix Super Markets, Inc.",
            "sortName": "Publix Super Markets, Inc.",
        },
    },
    "caseHeader": CASE_HEADER,
    "partyNumber": 4,
    "nonPublicFlag": False,
}
DOCKET_ROW = {
    "docketEntryHeader": {
        "filedDate": "2026-07-14T13:34:59.843+00:00",
        "docketEntryType": "Order",
        "docketEntrySubType": "Counsel Pro Hac Vice",
        "docketEntrySubTypeID": "1001201",
        "docketEntryDescription": "The motion is granted.",
        "documentCount": "1",
        "securedDocument": False,
        "docketEntryUUID": DOCKET_UUID,
    }
}
DOCUMENT_ROW = {
    "docketEntryUUID": DOCKET_UUID,
    "documentLinkUUID": DOCUMENT_UUID,
    "documentName": "Order - Non-dispositional",
    "caseHeader": CASE_HEADER,
    "documentInfo": {
        "documentType": "Docket Entry",
        "contentType": "application/pdf",
        "fileExtension": "pdf",
        "pageCount": 2,
        "fileSize": 76255,
    },
    "userDocumentState": query_florida_acis.DOCUMENT_STATE_VIEWABLE,
}
EVENT_ROW = {
    "eventUUID": EVENT_UUID,
    "eventName": "Oral Argument Example Panel",
    "courtID": "1",
    "courtAbbreviation": "Supreme Court of Florida",
    "courtSessionType": "Oral Argument",
    "panelFlag": True,
    "startDate": "2026-08-19T13:30:00.000+00:00",
}
HEARING_ROW = {
    "startDate": "2026-08-19T13:30:00.000+00:00",
    "hearingType": "Oral Argument",
    "hearingStatus": "Scheduled",
    "orderBy": 1,
    "event": {"panelFlag": True},
    "caseHeader": CASE_HEADER,
}
SESSION_TYPE_ROW = {
    "courtSessionTypeID": "1000003",
    "courtSessionTypeName": "Oral Argument",
    "courtSessionTypeComment": "Oral Argument",
}


def _hal(
    records: list[dict[str, Any]],
    *,
    page: int = 0,
    size: int = 100,
    total: int | None = None,
    omit_embedded: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "page": {
            "size": size,
            "totalElements": len(records) if total is None else total,
            "totalPages": (
                0
                if (len(records) if total is None else total) == 0
                else 1
            ),
            "number": page,
        }
    }
    if not omit_embedded:
        payload["_embedded"] = {"results": records}
    return payload


@dataclass
class FixtureResponse:
    payload: Any = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    content: bytes | None = None

    def json(self):
        return self.payload


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

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
            raise AssertionError("unexpected ACIS request")
        return self.responses.pop(0)


def _fetch(records, *, cursor=None, schema="a" * 64):
    return PaginatedFetch(
        records=tuple(records),
        next_cursor=cursor,
        schema={"kind": "fixture"},
        schema_fingerprint=schema,
        pages_fetched=1,
        requests_made=1,
    )


def _args(command: str, **overrides) -> Namespace:
    values = {
        "command": command,
        "query": "SC2026-0899",
        "party_name": None,
        "search_scope": "party",
        "match_mode": "match",
        "field": "auto",
        "text_mode": "any",
        "court": COURT_UUID,
        "court_resource_uuid": None,
        "case_uuid": None,
        "document_uuid": None,
        "publication_uuid": None,
        "publication_number": None,
        "case_number": None,
        "documents": False,
        "document_type": None,
        "session_type": None,
        "event_name": None,
        "events_only": False,
        "filed_after": None,
        "filed_before": None,
        "after": None,
        "before": None,
        "case_type": None,
        "case_type_id": None,
        "limit": 50,
        "page_size": 100,
        "cursor": None,
        "max_records": None,
        "destination": None,
        "overwrite": False,
        "timeout": 30.0,
        "minimum_interval": 0,
        "catalog_db": "unused.db",
        "catalog_config": "unused.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _court() -> query_florida_acis.ACISCourt:
    return query_florida_acis.ACISCourt(
        resource_uuid=COURT_UUID,
        external_id="1",
        display_name="Supreme Court of Florida",
        active=True,
        raw=COURT_ROW,
    )


def test_hal_pagination_accepts_source_empty_shape_without_embedded():
    transport = QueueTransport(
        [FixtureResponse(_hal([], total=0, omit_embedded=True))]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client._fetch_hal(
        query_florida_acis.CASE_SEARCH_URL,
        requested_limit=50,
        page_size=100,
    )

    assert fetched.records == ()
    assert fetched.next_cursor is None
    assert fetched.requests_made == 1


def test_hal_pagination_adapts_when_source_clamps_requested_page_size():
    rows = [{"id": index} for index in range(5)]
    transport = QueueTransport(
        [
            FixtureResponse(_hal(rows[:2], page=0, size=2, total=5)),
            FixtureResponse(_hal(rows[2:4], page=1, size=2, total=5)),
            FixtureResponse(_hal(rows[4:], page=2, size=2, total=5)),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client._fetch_hal(
        query_florida_acis.CASE_SEARCH_URL,
        requested_limit=5,
        page_size=1000,
    )

    assert [row["id"] for row in fetched.records] == [0, 1, 2, 3, 4]
    assert [call["params"]["page"] for call in transport.calls] == [0, 1, 2]
    assert fetched.requests_made == 3


def test_case_search_resolves_directory_external_id_to_resource_uuid_filter():
    transport = QueueTransport(
        [
            FixtureResponse(_hal([COURT_ROW], size=100)),
            FixtureResponse(_hal([{"caseHeader": CASE_HEADER}], size=25)),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search_cases(
        "SC2026-0899",
        field="number",
        match_mode="exact",
        court=COURT_UUID,
        case_type_id="1000042",
        filed_after="2026-01-01",
        filed_before="2026-07-31",
        requested_limit=1,
        page_size=25,
    )

    assert len(fetched.records) == 1
    search_call = transport.calls[1]
    assert search_call["params"]["caseHeader.courtID"] == COURT_UUID
    assert search_call["params"]["caseHeader.caseNumberSearchType"] == "10462"
    assert search_call["params"]["caseHeader.caseTypeID"] == "1000042"
    assert search_call["params"]["caseHeader.filedDateFrom"] == (
        "2026-01-01T00:00:00.000-05:00"
    )
    assert search_call["params"]["caseHeader.filedDateTo"] == (
        "2026-07-31T23:59:59.999-04:00"
    )


def test_search_page_size_is_clamped_to_verified_source_maximum():
    transport = QueueTransport(
        [
            FixtureResponse(_hal([COURT_ROW], size=100)),
            FixtureResponse(_hal([{"caseHeader": CASE_HEADER}], size=500)),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )

    client.search_cases(
        "SC2026-0899",
        field="number",
        match_mode="exact",
        court=COURT_UUID,
        requested_limit=1,
        page_size=750,
    )

    assert transport.calls[1]["params"]["size"] == 500


def test_full_iso_date_filter_is_preserved():
    value = "2026-01-01T08:30:00.000+00:00"

    assert query_florida_acis._acis_datetime(
        value,
        end_of_day=False,
    ) == value


def test_calendar_search_resolves_court_and_session_type_filters():
    transport = QueueTransport(
        [
            FixtureResponse(_hal([COURT_ROW], size=100)),
            FixtureResponse([SESSION_TYPE_ROW]),
            FixtureResponse(_hal([EVENT_ROW], size=25)),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search_calendar_events(
        court=COURT_UUID,
        after="2026-08-18",
        before="2026-08-19",
        session_type="Oral Argument",
        event_name="Example",
        requested_limit=1,
        page_size=25,
    )

    assert fetched.records == (EVENT_ROW,)
    request = transport.calls[2]
    assert request["url"] == query_florida_acis.EVENT_SEARCH_URL
    assert request["params"]["courtID"] == COURT_UUID
    assert request["params"]["courtSessionTypeID"] == "1000003"
    assert request["params"]["eventName"] == "Example"
    assert request["params"]["eventNameSearchType"] == "300054"
    assert request["params"]["startDateFrom"] == (
        "2026-08-18T00:00:00.000-04:00"
    )
    assert request["params"]["startDateTo"] == (
        "2026-08-19T23:59:59.999-04:00"
    )


def test_calendar_enriches_events_with_case_hearings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    transport = QueueTransport(
        [
            FixtureResponse(_hal([EVENT_ROW], size=100)),
            FixtureResponse(_hal([HEARING_ROW], size=100)),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)
    monkeypatch.setattr(query_florida_acis, "log_search", lambda *args: None)

    result = query_florida_acis.execute(
        _args(
            "calendar",
            query=None,
            court=None,
            after="2026-08-19",
            before="2026-08-19",
            limit=10,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.query.query.parameters["after"] == "2026-08-19"
    assert "filed_after" not in result.query.query.parameters
    event = result.records[0]
    assert event["record_kind"] == "calendar_event"
    assert event["native_event_id"] == EVENT_UUID
    assert event["hearing_detail_state"] == "complete"
    assert event["case_count"] == 1
    hearing = event["cases"][0]
    assert hearing["raw_case_number"] == "SC2026-0899"
    assert hearing["case_instance_uuid"] == CASE_UUID
    assert hearing["event_type"] == "Oral Argument"
    assert hearing["status"] == "Scheduled"
    assert hearing["source_url"].endswith(f"/case/{CASE_UUID}")
    assert transport.calls[1]["url"].endswith(
        f"/events/{EVENT_UUID}/hearings"
    )
    assert transport.calls[1]["params"]["sort"] == "orderBy,asc"

    court_db = tmp_path / "calendar-courts.db"
    report = ingest_envelope(result.to_dict(), court_db=court_db)
    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["snapshot_only"]["record_count"] == 0
    db = sqlite3.connect(court_db)
    try:
        assert db.execute(
            """
            SELECT c.raw_case_number, c.filing_date, d.event_type,
                   d.event_date, d.event_time, d.status
            FROM case_record AS c
            JOIN docket_entry AS d ON d.case_id = c.case_id
            """
        ).fetchone() == (
            "SC2026-0899",
            None,
            "Oral Argument",
            "2026-08-19",
            "13:30:00.000+00:00",
            "Scheduled",
        )
    finally:
        db.close()


def test_calendar_events_only_avoids_per_event_detail_requests(
    monkeypatch: pytest.MonkeyPatch,
):
    transport = QueueTransport(
        [FixtureResponse(_hal([EVENT_ROW], size=100))]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)
    monkeypatch.setattr(query_florida_acis, "log_search", lambda *args: None)

    result = query_florida_acis.execute(
        _args(
            "calendar",
            query=None,
            court=None,
            events_only=True,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "ok"
    assert result.records[0]["hearing_detail_state"] == "not_requested"
    assert not result.records[0]["cases"]
    assert len(transport.calls) == 1


def test_party_search_normalizes_to_ingestible_case_shape():
    client = query_florida_acis.FloridaACISClient(minimum_interval=0)
    client._courts = (_court(),)

    party = query_florida_acis._party_record(PARTY_ROW)
    record = query_florida_acis._case_record(
        client,
        CASE_HEADER,
        schema="b" * 64,
        parties=[party],
        search_hit=PARTY_ROW,
    )

    assert record["court"]["court_id"] == COURT_UUID
    assert record["court"]["native_court_id"] == "1"
    assert record["source_internal_id"] == CASE_UUID
    assert record["raw_case_number"] == "SC2026-0899"
    assert record["parties"][0]["role"] == "Appellant"
    assert record["parties"][0]["raw_name"] == (
        "Publix Super Markets, Inc."
    )


def test_party_search_fallback_sequence_is_stable_across_result_ranks():
    row = {
        **PARTY_ROW,
        "partyHeader": {
            key: value
            for key, value in PARTY_ROW["partyHeader"].items()
            if key != "casePartyUUID"
        },
    }
    row.pop("partyNumber", None)

    first = query_florida_acis._party_record(row)
    second = query_florida_acis._party_record(row)

    assert first["sequence_no"] == second["sequence_no"]
    assert first["sequence_source"] == "stable_party_identity"


class CaseClient:
    def __init__(self):
        self.court = _court()
        self.calls = []

    def search_cases(self, *_args, **kwargs):
        self.calls.append(("search_cases", kwargs))
        return _fetch([{"caseHeader": CASE_HEADER}])

    def court_by_external_id(self, external_id):
        assert str(external_id) == "1"
        return self.court

    def get_case(self, court_uuid, case_uuid):
        self.calls.append(("get_case", court_uuid, case_uuid))
        return {"caseHeader": CASE_HEADER}

    def case_parties(self, court_uuid, case_uuid, **kwargs):
        self.calls.append(("case_parties", court_uuid, case_uuid, kwargs))
        return _fetch([PARTY_ROW])

    def docket_entries(self, court_uuid, case_uuid, **kwargs):
        self.calls.append(("docket_entries", court_uuid, case_uuid, kwargs))
        return _fetch([DOCKET_ROW])

    def case_documents(self, court_uuid, case_uuid, **kwargs):
        self.calls.append(("case_documents", court_uuid, case_uuid, kwargs))
        return _fetch([DOCUMENT_ROW])


def test_case_document_envelope_projects_case_party_docket_and_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(query_florida_acis, "log_search", lambda *args: None)
    client = CaseClient()
    result = query_florida_acis.execute(
        _args("case", documents=True),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "ok"
    case = result.to_dict()["records"][0]
    assert len(case["parties"]) == 1
    assert len(case["docket_entries"]) == 1
    assert len(case["docket_entries"][0]["documents"]) == 1
    assert case["docket_entries"][0]["documents"][0][
        "access_state"
    ] == "public"

    report = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "state-courts.db",
    )
    assert report["projected"]["cases"] == 1
    assert report["projected"]["parties"] == 1
    assert report["projected"]["docket_entries"] == 1
    assert report["projected"]["documents"] == 1
    db = sqlite3.connect(tmp_path / "state-courts.db")
    try:
        assert db.execute(
            "SELECT access_state, native_access_state "
            "FROM document_artifact"
        ).fetchone() == ("public", "viewable")
    finally:
        db.close()


def test_exact_case_resolution_reports_cross_court_ambiguity():
    second = {
        **CASE_HEADER,
        "caseInstanceUUID": "second-case-uuid",
        "courtID": "2",
    }

    class AmbiguousClient:
        def search_cases(self, *_args, **_kwargs):
            return _fetch(
                [
                    {"caseHeader": CASE_HEADER},
                    {"caseHeader": second},
                ]
            )

    with pytest.raises(
        query_florida_acis.ACISSelectionError,
        match="matched multiple courts",
    ):
        query_florida_acis._resolve_case(
            AmbiguousClient(),
            "SC2026-0899",
            court=None,
            page_size=100,
        )


def test_document_download_checks_access_state_and_validates_pdf():
    pdf = b"%PDF-1.7\nfixture"
    transport = QueueTransport(
        [
            FixtureResponse(_hal([DOCUMENT_ROW])),
            FixtureResponse(
                payload=None,
                headers={
                    "Content-Type": "application/pdf;charset=UTF-8",
                    "Content-Disposition": 'inline; filename="Order.pdf"',
                },
                content=pdf,
            ),
        ]
    )
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)

    downloaded = client.download_document(
        COURT_UUID,
        CASE_UUID,
        DOCUMENT_UUID,
    )

    assert downloaded.content == pdf
    assert downloaded.media_type == "application/pdf"
    assert downloaded.filename == "Order.pdf"
    assert transport.calls[0]["url"].endswith(
        "/courts/cms/docketentrydocumentsaccess"
    )
    assert transport.calls[1]["url"].endswith(
        f"/case/{CASE_UUID}/docketentrydocuments/{DOCUMENT_UUID}"
    )


def test_nonviewable_document_returns_explicit_restricted_state():
    row = {
        **DOCUMENT_ROW,
        "userDocumentState": query_florida_acis.DOCUMENT_STATE_UNAVAILABLE,
    }
    transport = QueueTransport([FixtureResponse(_hal([row]))])
    client = query_florida_acis.FloridaACISClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)

    with pytest.raises(
        query_florida_acis.ACISSelectionError,
        match="unavailable",
    ) as captured:
        client.download_document(COURT_UUID, CASE_UUID, DOCUMENT_UUID)

    assert captured.value.status.value == "restricted"
    assert captured.value.code == "document_not_publicly_viewable"
    assert len(transport.calls) == 1


def test_document_search_hit_without_access_metadata_is_not_marked_public():
    row = {
        "documentLinkUUID": DOCUMENT_UUID,
        "documentName": "Search hit",
        "caseHeader": CASE_HEADER,
        "highlightsMap": {"text": ["matching words"]},
    }
    client = query_florida_acis.FloridaACISClient(minimum_interval=0)
    client._courts = (_court(),)

    normalized = query_florida_acis._document_record(
        client,
        row,
        link_to_docket=False,
    )

    assert normalized["access_state"] == "restricted"
    assert normalized["source_access_state"] == "unknown"
    assert normalized["source_url"] is None


def test_document_search_enriches_selected_hits_with_access_metadata(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_florida_acis, "log_search", lambda *args: None)
    search_hit = {
        "documentLinkUUID": DOCUMENT_UUID,
        "documentName": "Search hit",
        "caseHeader": CASE_HEADER,
        "docketEntryHeader": {"filedDate": "2026-07-14"},
        "highlightsMap": {"text": ["matching words"]},
    }

    class DocumentSearchClient:
        def __init__(self):
            self.court = _court()
            self.access_calls = []

        def search_documents(self, *_args, **_kwargs):
            return _fetch([search_hit])

        def court_by_external_id(self, external_id):
            assert str(external_id) == "1"
            return self.court

        def case_documents(self, court_uuid, case_uuid, **kwargs):
            self.access_calls.append((court_uuid, case_uuid, kwargs))
            return _fetch([DOCUMENT_ROW])

    client = DocumentSearchClient()
    result = query_florida_acis.execute(
        _args("document-search", query="motion"),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    document = result.to_dict()["records"][0]["documents"][0]
    assert result.status.value == "ok"
    assert document["access_state"] == "public"
    assert document["source_access_state"] == "viewable"
    assert document["highlights"] == {"text": ["matching words"]}
    assert client.access_calls[0][2]["document_uuid"] == DOCUMENT_UUID


def test_publication_detail_uses_route_identity_and_expands_items():
    client = query_florida_acis.FloridaACISClient(minimum_interval=0)
    client._courts = (_court(),)
    detail = {
        "courtAbbreviation": "Supreme Court of Florida",
        "publicationNumber": "SCPUB-0099",
        "publicationName": "FSC Dispositions Released for Publication",
        "publicationNote": "Weekly dispositions.",
        "publicationDate": "2026-07-20T14:40:21.583+00:00",
        "publicationItems": [
            {
                "publicationItemUUID": "item-uuid",
                "caseInstanceUUID": CASE_UUID,
                "caseNumber": "SC2026-0899",
                "title": "Publix v. ACE",
                "decision": "Opinion",
                "orderBy": 1,
            }
        ],
    }

    record = query_florida_acis._publication_record(
        client,
        detail,
        schema="c" * 64,
        publication_uuid="publication-uuid",
        court_hint=_court(),
    )

    assert record["publication_uuid"] == "publication-uuid"
    assert record["court_resource_uuid"] == COURT_UUID
    assert record["publication_items"][0]["case_instance_uuid"] == CASE_UUID
    assert record["publication_items"][0]["decision"] == "Opinion"


def test_catalog_decision_precedes_client_dispatch(
    monkeypatch: pytest.MonkeyPatch,
):
    logs = []
    monkeypatch.setattr(
        query_florida_acis,
        "log_search",
        lambda *args: logs.append(args),
    )

    result = query_florida_acis.execute(
        _args("case"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "automation_disposition": "human_required",
            "reason_code": "review_required",
            "reason": "Review source route",
        },
        client=object(),
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "review_required"
    assert len(logs) == 1


def test_generic_text_case_type_is_not_silently_ignored(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_florida_acis, "log_search", lambda *args: None)

    result = query_florida_acis.execute(
        _args("case-search", query="Publix", case_type="civil"),
        access_decision={"allowed": True, "limits": {}},
        client=object(),
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "case_type_id_required"
    assert result.errors[0].details["provided_case_type"] == "civil"


def test_direct_cli_exposes_all_tracked_operations():
    project_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "tools/query_florida_acis.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for command in (
        "courts",
        "calendar-types",
        "calendar",
        "case-search",
        "party-search",
        "case",
        "docket",
        "documents",
        "document-search",
        "download",
        "publications",
        "publication",
    ):
        assert command in result.stdout
