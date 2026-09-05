from __future__ import annotations

import hashlib
import sqlite3
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_vicourts
from tools.ingest_state_court_records import ingest_envelope


COURT_UUID = "87edff36-c02b-4073-aea4-c0652bc123d9"
CASE_UUID = "fc6d7243-dfc0-474e-bcc8-1c9e44545ba0"
DOCKET_UUID = "8f188e0d-b357-41f2-a845-fb0ad2e748a2"
DOCUMENT_UUID = "8313c772-8788-4b19-83c1-95be3fb60e2f"
PUBLICATION_UUID = "6cc28238-1986-4d34-a6bc-d6cb8c0de527"

COURT_ROW = {
    "resourceID": COURT_UUID,
    "externalIdentifier": "1",
    "displayName": "Superior Court of the Virgin Islands",
    "active": True,
    "locations": [],
}
CASE_HEADER = {
    "caseInstanceUUID": CASE_UUID,
    "caseNumber": "ST-2019-PB-00080",
    "caseTitle": "In the Matter of the Estate",
    "closedFlag": False,
    "caseClassification": "Probate",
    "courtID": "1",
    "filedDate": "2019-05-13T12:00:00.000+00:00",
}
DOCKET_ROW = {
    "docketEntryHeader": {
        "filedDate": "2021-01-15T12:00:00.000+00:00",
        "docketEntryType": "Filing",
        "docketEntrySubType": "Certificate of Death",
        "docketEntryDescription": "Certificate of Death",
        "documentCount": 1,
        "securedDocument": True,
        "docketEntryUUID": DOCKET_UUID,
    }
}
DOCUMENT_ROW = {
    "docketEntryUUID": DOCKET_UUID,
    "documentLinkUUID": DOCUMENT_UUID,
    "documentName": "Quarterly Accounting",
    "caseHeader": CASE_HEADER,
    "docketEntryHeader": {
        "docketEntryUUID": DOCKET_UUID,
        "filedDate": "2021-01-15T12:00:00.000+00:00",
    },
    "documentInfo": {
        "documentType": "Docket Entry",
        "contentType": "application/pdf",
        "fileExtension": "pdf",
        "pageCount": 7,
        "fileSize": 2_607_120,
    },
    "userDocumentState": query_vicourts.DOCUMENT_STATE_VIEWABLE,
}


def _hal(
    records: list[dict[str, Any]],
    *,
    page: int = 0,
    size: int = 100,
    total: int | None = None,
    total_pages: int | None = None,
    omit_embedded: bool = False,
) -> dict[str, Any]:
    total_elements = len(records) if total is None else total
    payload: dict[str, Any] = {
        "page": {
            "size": size,
            "totalElements": total_elements,
            "totalPages": (
                total_pages
                if total_pages is not None
                else (0 if total_elements == 0 else 1)
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
            raise AssertionError("unexpected VI Courts request")
        return self.responses.pop(0)


def _fetch(
    records,
    *,
    cursor=None,
    total=None,
    source_overflow=False,
):
    return query_vicourts.VICourtsFetch(
        records=tuple(records),
        next_cursor=cursor,
        schema={"kind": "fixture"},
        schema_fingerprint="a" * 64,
        pages_fetched=1,
        requests_made=1,
        total_elements=len(records) if total is None else total,
        source_overflow=source_overflow,
    )


def _court() -> query_vicourts.VICourt:
    return query_vicourts.VICourt(
        resource_uuid=COURT_UUID,
        external_id="1",
        display_name="Superior Court of the Virgin Islands",
        active=True,
        raw=COURT_ROW,
    )


def _args(command: str, **overrides) -> Namespace:
    values = {
        "command": command,
        "query": None,
        "field": "number",
        "match_mode": None,
        "court": None,
        "case_number": None,
        "docket_entry_uuid": None,
        "case_uuid": None,
        "document_uuid": None,
        "publication_uuid": None,
        "publication_number": None,
        "exact": None,
        "any_words": None,
        "all_words": None,
        "none_words": None,
        "item_id": None,
        "limit": None,
        "page_size": 100,
        "cursor": None,
        "destination": None,
        "overwrite": False,
        "timeout": 30.0,
        "minimum_interval": 0,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


def test_spring_pagination_is_zero_based_and_clamps_page_size():
    rows = [{"id": index} for index in range(3)]
    transport = QueueTransport(
        [
            FixtureResponse(
                _hal(rows[:2], page=0, size=2, total=3, total_pages=2)
            ),
            FixtureResponse(
                _hal(rows[2:], page=1, size=2, total=3, total_pages=2)
            ),
        ]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client._fetch_hal(
        query_vicourts.CASE_SEARCH_URL,
        page_size=800,
    )

    assert [row["id"] for row in fetched.records] == [0, 1, 2]
    assert [call["params"]["page"] for call in transport.calls] == [0, 1]
    assert all(call["params"]["size"] == 500 for call in transport.calls)
    assert fetched.next_cursor is None


def test_empty_spring_page_may_omit_embedded_results():
    transport = QueueTransport(
        [FixtureResponse(_hal([], total=0, omit_embedded=True))]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client._fetch_hal(
        query_vicourts.CASE_SEARCH_URL,
        page_size=100,
    )

    assert fetched.records == ()
    assert fetched.total_elements == 0


def test_live_external_court_id_is_resolved_to_resource_uuid_at_runtime():
    transport = QueueTransport(
        [
            FixtureResponse(_hal([COURT_ROW])),
            FixtureResponse(_hal([{"caseHeader": CASE_HEADER}])),
        ]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )

    fetched = client.search_cases(
        "ST-19-PB-80",
        field="number",
        match_mode="exact",
        court="1",
        requested_limit=1,
    )

    assert len(fetched.records) == 1
    params = transport.calls[1]["params"]
    assert params["caseHeader.courtID"] == COURT_UUID
    assert params["caseHeader.caseNumber"] == "ST-2019-PB-00080"
    assert params["caseHeader.caseNumberSearchType"] == "10462"


@pytest.mark.parametrize(
    ("legacy", "normalized"),
    [
        ("ST-19-PB-80", "ST-2019-PB-00080"),
        ("ST-21-RV-00005", "ST-2021-RV-00005"),
        ("ST-20-CV-14", "ST-2020-CV-00014"),
        ("ST-2019-PB-00080", "ST-2019-PB-00080"),
    ],
)
def test_legacy_case_number_normalization(legacy: str, normalized: str):
    assert query_vicourts.normalize_case_number(legacy) == normalized


def test_source_result_ceiling_is_an_explicit_partial_error():
    transport = QueueTransport(
        [
            FixtureResponse(
                _hal(
                    [{"caseHeader": CASE_HEADER}],
                    total=query_vicourts.SOURCE_RESULT_LIMIT,
                    total_pages=100,
                )
            )
        ]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)
    fetched = client._fetch_hal(
        query_vicourts.CASE_SEARCH_URL,
        requested_limit=1,
    )
    query = query_vicourts.build_query(
        _args("search", query="Estate", field="title", limit=1)
    )
    result = query_vicourts._fetch_result(
        query,
        fetched,
        [
            query_vicourts._case_record(
                client,
                CASE_HEADER,
                schema=fetched.schema_fingerprint,
            )
        ],
    )

    assert fetched.source_overflow is True
    assert result.status.value == "partial"
    assert result.errors[0].code == "source_overflow"
    assert result.errors[0].details["reported_total_elements"] == 10_000


def test_ctrack_pdf_is_validated_and_hashed_before_saving(tmp_path: Path):
    pdf_bytes = b"%PDF-1.7\nfixture"
    transport = QueueTransport(
        [
            FixtureResponse(_hal([DOCUMENT_ROW])),
            FixtureResponse(
                headers={
                    "Content-Type": "application/pdf;charset=UTF-8",
                    "Content-Disposition": 'inline; filename="Accounting.pdf"',
                },
                content=pdf_bytes,
            ),
        ]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)

    validated = client.download_document(
        "1",
        CASE_UUID,
        DOCUMENT_UUID,
    )
    destination = tmp_path / "document.pdf"
    saved, _ = query_vicourts._save_validated_pdf(
        validated,
        str(destination),
        overwrite=False,
    )

    assert validated.sha256 == hashlib.sha256(pdf_bytes).hexdigest()
    assert validated.filename == "Accounting.pdf"
    assert saved == destination.resolve()
    assert destination.read_bytes() == pdf_bytes
    assert transport.calls[1]["url"].endswith(
        f"/case/{CASE_UUID}/docketentrydocuments/{DOCUMENT_UUID}"
    )


def test_non_pdf_body_is_rejected_before_any_file_is_written(tmp_path: Path):
    transport = QueueTransport(
        [
            FixtureResponse(_hal([DOCUMENT_ROW])),
            FixtureResponse(
                headers={"Content-Type": "text/html"},
                content=b"<html>error</html>",
            ),
        ]
    )
    client = query_vicourts.VICourtsClient(
        transport=transport,
        minimum_interval=0,
    )
    client._courts = (_court(),)
    destination = tmp_path / "must-not-exist.pdf"

    with pytest.raises(query_vicourts.SourceSchemaError, match="not a PDF"):
        validated = client.download_document(
            "1",
            CASE_UUID,
            DOCUMENT_UUID,
        )
        query_vicourts._save_validated_pdf(
            validated,
            str(destination),
            overwrite=False,
        )

    assert not destination.exists()


class CaseClient:
    def __init__(self, *, documents=()):
        self.court = _court()
        self.documents = tuple(documents)

    def search_cases(self, *_args, **_kwargs):
        return _fetch([{"caseHeader": CASE_HEADER}])

    def court_by_external_id(self, external_id):
        assert str(external_id) == "1"
        return self.court

    def resolve_court(self, selector):
        assert selector in {"1", COURT_UUID}
        return self.court

    def get_case(self, court_uuid, case_uuid):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return {"caseHeader": CASE_HEADER}

    def docket_entries(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch([DOCKET_ROW])

    def case_documents(self, court_uuid, case_uuid, **_kwargs):
        assert (court_uuid, case_uuid) == (COURT_UUID, CASE_UUID)
        return _fetch(self.documents)


def test_secured_docket_row_survives_zero_document_access_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(query_vicourts, "log_search", lambda *args: None)
    result = query_vicourts.execute(
        _args(
            "documents",
            case_number="ST-19-PB-80",
            docket_entry_uuid=DOCKET_UUID,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=CaseClient(documents=()),
    )

    assert result.status.value == "ok"
    case = result.to_dict()["records"][0]
    assert case["canonical_ref"].endswith(
        f"/case/{CASE_UUID}"
    )
    assert case["raw_case_number"] == "ST-2019-PB-00080"
    assert len(case["docket_entries"]) == 1
    assert case["docket_entries"][0]["secured_document"] is True
    assert case["docket_entries"][0]["documents"] == []

    report = ingest_envelope(
        result.to_dict(),
        court_db=tmp_path / "state-courts.db",
    )
    assert report["projected"]["cases"] == 1
    assert report["projected"]["docket_entries"] == 1
    db = sqlite3.connect(tmp_path / "state-courts.db")
    try:
        assert db.execute(
            "SELECT raw_case_number FROM case_record"
        ).fetchone() == ("ST-2019-PB-00080",)
    finally:
        db.close()


class DownloadClient:
    def __init__(self, pdf: query_vicourts.ValidatedPDF):
        self.pdf = pdf
        self.court = _court()

    def resolve_court(self, selector):
        assert selector == "1"
        return self.court

    def download_document(self, court_uuid, case_uuid, document_uuid):
        assert (court_uuid, case_uuid, document_uuid) == (
            COURT_UUID,
            CASE_UUID,
            DOCUMENT_UUID,
        )
        return self.pdf

    def legacy_file(self, item_id):
        assert item_id == 16911884
        return self.pdf


def test_ctrack_and_legacy_ids_remain_separate_with_hash_only_dedupe(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_vicourts, "log_search", lambda *args: None)
    content = b"%PDF-1.7\nsame content"
    digest = hashlib.sha256(content).hexdigest()
    pdf = query_vicourts.ValidatedPDF(
        content=content,
        media_type="application/pdf",
        filename="fixture.pdf",
        sha256=digest,
        source_url="https://example.invalid/fixture.pdf",
    )
    client = DownloadClient(pdf)

    ctrack = query_vicourts.execute(
        _args(
            "download",
            court="1",
            case_uuid=CASE_UUID,
            document_uuid=DOCUMENT_UUID,
        ),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    ).to_dict()["records"][0]
    legacy = query_vicourts.execute(
        _args("legacy-file", item_id=16911884),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    ).to_dict()["records"][0]

    assert ctrack["canonical_ref"] == f"CTRACK_DOCUMENT:{DOCUMENT_UUID}"
    assert legacy["canonical_ref"] == "VICOURTS_ITEM:16911884"
    assert ctrack["backend"] == "ctrack"
    assert legacy["backend"] == "legacy_displayfile"
    assert ctrack["cross_system_dedupe_sha256"] == digest
    assert legacy["cross_system_dedupe_sha256"] == digest


def test_legacy_404_returns_source_changed_envelope(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_vicourts, "log_search", lambda *args: None)
    client = query_vicourts.VICourtsClient(
        transport=QueueTransport(
            [
                FixtureResponse(
                    status_code=404,
                    headers={"Content-Type": "text/html"},
                    text="Not Found",
                    content=b"<html>Not Found</html>",
                )
            ]
        ),
        minimum_interval=0,
    )

    result = query_vicourts.execute(
        _args("legacy-file", item_id=99_999_999),
        access_decision={"allowed": True, "limits": {}},
        client=client,
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_endpoint_changed"
    assert result.records == ()


def test_parser_exposes_all_commands_and_exact_argument_destinations():
    parser = query_vicourts.build_parser()
    search = parser.parse_args(
        [
            "search",
            "ST-19-PB-80",
            "--field",
            "number",
            "--match-mode",
            "exact",
            "--court",
            "1",
        ]
    )
    documents = parser.parse_args(
        ["documents", "ST-19-PB-80", DOCKET_UUID, "--court", "1"]
    )
    download = parser.parse_args(
        ["download", "1", CASE_UUID, DOCUMENT_UUID, "document.pdf"]
    )
    document_search = parser.parse_args(
        [
            "document-search",
            "--exact",
            "Jeffrey Epstein",
            "--any",
            "estate probate",
            "--none",
            "unrelated",
        ]
    )

    assert search.query == "ST-19-PB-80"
    assert search.field == "number"
    assert search.match_mode == "exact"
    assert documents.case_number == "ST-19-PB-80"
    assert documents.docket_entry_uuid == DOCKET_UUID
    assert download.case_uuid == CASE_UUID
    assert download.document_uuid == DOCUMENT_UUID
    assert document_search.exact == "Jeffrey Epstein"
    assert document_search.any_words == "estate probate"
    assert document_search.none_words == "unrelated"
    commands = parser._subparsers._group_actions[0].choices
    assert {
        "courts",
        "search",
        "case",
        "docket",
        "claims",
        "documents",
        "document-search",
        "download",
        "publications",
        "publication",
        "legacy-file",
        "probe",
    } <= set(commands)


def test_access_decision_injection_blocks_before_client_dispatch(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_vicourts, "log_search", lambda *args: None)
    result = query_vicourts.execute(
        _args("case", case_number="ST-19-PB-80"),
        access_decision={
            "allowed": False,
            "automation_disposition": "human_required",
            "reason_code": "review_required",
            "reason": "Review route",
        },
        client=object(),
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "review_required"


def test_execute_closes_only_an_owned_client(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(query_vicourts, "log_search", lambda *args: None)
    content = b"%PDF-1.7\nowned"
    owned = DownloadClient(
        query_vicourts.ValidatedPDF(
            content=content,
            media_type="application/pdf",
            filename="owned.pdf",
            sha256=hashlib.sha256(content).hexdigest(),
            source_url="https://example.invalid/owned.pdf",
        )
    )
    owned.closed = False
    owned.close = lambda: setattr(owned, "closed", True)
    monkeypatch.setattr(
        query_vicourts,
        "_make_client",
        lambda *_args, **_kwargs: owned,
    )

    result = query_vicourts.execute(
        _args("legacy-file", item_id=16911884),
        access_decision={"allowed": True, "limits": {}},
    )

    assert result.status.value == "ok"
    assert owned.closed is True
