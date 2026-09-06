from __future__ import annotations

import json
from pathlib import Path

from tools import (
    public_records_monitor,
    query_dc_appellate_cases,
    query_md_judgment_liens,
    query_md_public_cases,
    query_state_courts,
)
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_ROOT = Path("tests/fixtures/public_records")


def _envelope(*, source, jurisdiction, operation: str, records: list[dict]):
    query = PublicRecordsQuery(
        source=source,
        jurisdiction=jurisdiction,
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, records).to_dict()


def _shared_args(*values: str):
    return query_state_courts.build_parser().parse_args(list(values))


def test_dc_ctrack_projects_case_children_documents_and_originating_matter(
    tmp_path: Path,
) -> None:
    fixture_dir = FIXTURE_ROOT / "dc_appellate_cases"
    record = query_dc_appellate_cases.parse_case_view(
        (fixture_dir / "case_view.html").read_text(encoding="utf-8"),
        source_url=(
            f"{query_dc_appellate_cases.BASE_URL}"
            f"{query_dc_appellate_cases.CASE_VIEW_PATH}?csIID=69335"
        ),
    )
    documents = query_dc_appellate_cases.parse_document_links(
        (fixture_dir / "document_links.dwr").read_text(encoding="utf-8"),
        case_number="24-BG-1045",
        case_internal_id="69335",
        event_id="1697111",
    )
    record["documents"] = documents
    for event in record["docket_events"]:
        if event["native_event_id"] == "1697111":
            event["documents"] = documents
            event["document_state"] = "resolved"

    db_path = tmp_path / "courts.db"
    report = ingest_envelope(
        _envelope(
            source=query_dc_appellate_cases.SOURCE_METADATA,
            jurisdiction=query_dc_appellate_cases.JURISDICTION,
            operation="case",
            records=[record],
        ),
        court_db=db_path,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["related_cases"] == 1
    assert report["projected"]["case_relations"] == 1
    assert report["projected"]["parties"] == 2
    assert report["projected"]["attorneys"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["documents"] == 1

    db = connect_courts(db_path)
    try:
        case = db.execute(
            """
            SELECT caption, status, filing_date
            FROM case_record
            WHERE source_id=? AND raw_case_number=?
              AND source_internal_id=?
            """,
            (
                query_dc_appellate_cases.SOURCE_ID,
                "24-BG-1045",
                "69335",
            ),
        ).fetchone()
        assert tuple(case) == (
            "IN RE MARC S. ALPERT, BAR REGISTRATION NO. 196386",
            "Decided/Dismissed",
            "2024-11-12",
        )

        relation = db.execute(
            """
            SELECT c.raw_case_number, r.relation_type
            FROM case_relation r
            JOIN case_record c ON c.case_id=r.from_case_id
            """
        ).fetchone()
        assert tuple(relation) == ("DDN 2024-D175", "appealed_to")

        document = db.execute(
            """
            SELECT d.native_document_id, e.native_entry_id
            FROM document_artifact d
            LEFT JOIN docket_entry e
              ON e.docket_entry_id=d.docket_entry_id
            """
        ).fetchone()
        assert tuple(document) == ("399765", "1697111")
    finally:
        db.close()


def test_maryland_recent_case_projects_parties_addresses_and_charge_stub(
    tmp_path: Path,
) -> None:
    source_record = {
        "record_kind": "recent_case_filing",
        "source_id": query_md_public_cases.SOURCE_ID,
        "court_id": "us-md-carroll",
        "court_name": "Carroll",
        "case_number": "D-102-CR-26-001528",
        "case_caption": "STATE OF MARYLAND v. RAY, LOGAN TYLER",
        "case_type": "Criminal - SOC - Application",
        "filing_date": "2026-07-29",
        "parties": [
            {
                "role": "plaintiff",
                "published_name": "STATE OF MARYLAND",
                "published_address": None,
            },
            {
                "role": "defendant",
                "published_name": "RAY, LOGAN TYLER",
                "published_address": "3815 SUNNYFIELD COURT HAMPSTEAD, MD 21074",
            },
        ],
        "charges": [
            {
                "charge_number": 1,
                "description": "ASSAULT-FIRST DEGREE",
            }
        ],
        "source_document_url": (
            "https://www.mdcourts.gov/data/case/file2026-07-30.pdf"
        ),
    }
    db_path = tmp_path / "courts.db"
    report = ingest_envelope(
        _envelope(
            source=query_md_public_cases.SOURCE_METADATA,
            jurisdiction=query_md_public_cases.JURISDICTION,
            operation="search",
            records=[source_record],
        ),
        court_db=db_path,
    )

    assert report["projected"]["cases"] == 1
    assert report["projected"]["parties"] == 2
    assert report["projected"]["claims"] == 1

    db = connect_courts(db_path)
    try:
        parties = db.execute(
            """
            SELECT raw_name
            FROM case_party
            JOIN case_record USING(case_id)
            WHERE case_record.source_id=?
            ORDER BY sequence_no
            """,
            (query_md_public_cases.SOURCE_ID,),
        ).fetchall()
        assert [row["raw_name"] for row in parties] == [
            "STATE OF MARYLAND",
            "RAY, LOGAN TYLER",
        ]
        case_raw = db.execute(
            "SELECT raw_json FROM case_record WHERE source_id=?",
            (query_md_public_cases.SOURCE_ID,),
        ).fetchone()
        case_source = json.loads(case_raw["raw_json"])[
            "maryland_report_source_occurrence"
        ]
        assert case_source["parties"][1]["published_address"].endswith(
            "MD 21074"
        )

        claim = db.execute(
            "SELECT native_claim_id, claim_type, limited_stub, raw_json "
            "FROM case_claim"
        ).fetchone()
        assert claim["native_claim_id"] == "charge:1"
        assert claim["claim_type"] == "criminal_charge"
        assert claim["limited_stub"] == 1
        assert json.loads(claim["raw_json"])["description"] == (
            "ASSAULT-FIRST DEGREE"
        )
    finally:
        db.close()


def test_maryland_judgment_detail_keeps_case_and_event_identities(
    tmp_path: Path,
) -> None:
    fixture = (
        FIXTURE_ROOT / "md_judgment_liens" / "detail.html"
    ).read_text(encoding="utf-8")
    records = query_md_judgment_liens.parse_detail_page(
        fixture,
        expected_case_number="03-L-12-005195",
    )
    db_path = tmp_path / "courts.db"
    report = ingest_envelope(
        _envelope(
            source=query_md_judgment_liens.SOURCE_METADATA,
            jurisdiction=query_md_judgment_liens.JURISDICTION,
            operation="detail",
            records=records,
        ),
        court_db=db_path,
    )

    assert report["projected"]["cases"] == 2
    assert report["projected"]["docket_entries"] == 2
    assert report["projected"]["claims"] == 2

    db = connect_courts(db_path)
    try:
        cases = db.execute(
            "SELECT raw_case_number FROM case_record WHERE source_id=?",
            (query_md_judgment_liens.SOURCE_ID,),
        ).fetchall()
        assert [row["raw_case_number"] for row in cases] == [
            "03-L-12-005195"
        ]
        events = db.execute(
            """
            SELECT event_code, event_date, status
            FROM docket_entry
            ORDER BY event_date
            """
        ).fetchall()
        assert [tuple(row) for row in events] == [
            ("original_judgment", "2012-03-27", None),
            ("judgment_modification", "2014-02-18", "SATISFIED"),
        ]
        claims = db.execute(
            """
            SELECT claim_type, amount_minor, status
            FROM case_claim ORDER BY claim_date
            """
        ).fetchall()
        assert claims[0]["claim_type"] == "judgment_or_lien_index_event"
        assert claims[0]["amount_minor"] == 991300
        assert claims[1]["status"] == "SATISFIED"
    finally:
        db.close()


def test_dc_and_maryland_unified_routes_preserve_source_selectors() -> None:
    dc_route = query_state_courts.LIVE_ROUTES[
        query_dc_appellate_cases.SOURCE_ID
    ]["search"]
    participant = dc_route.translate(
        _shared_args(
            "search",
            "Marc S Alpert",
            "--source",
            query_dc_appellate_cases.SOURCE_ID,
        ),
        dc_route.adapter_command,
    )
    assert participant.command == "participant"
    assert (participant.first_name, participant.middle_name, participant.last_name) == (
        "Marc",
        "S",
        "Alpert",
    )
    assert participant.all_pages is False

    originating = dc_route.translate(
        _shared_args(
            "search",
            "2022-CA-002124-M",
            "--source",
            query_dc_appellate_cases.SOURCE_ID,
            "--search-field",
            "originating-case-number",
            "--after",
            "2022-01-01",
            "--before",
            "2023-01-01",
        ),
        dc_route.adapter_command,
    )
    assert originating.command == "search"
    assert originating.originating_case_number == "2022-CA-002124-M"
    assert originating.date_from == "2022-01-01"
    assert originating.date_to == "2023-01-01"

    documents_route = query_state_courts.LIVE_ROUTES[
        query_dc_appellate_cases.SOURCE_ID
    ]["documents"]
    documents = documents_route.translate(
        _shared_args(
            "documents",
            "24-BG-1045",
            "--source",
            query_dc_appellate_cases.SOURCE_ID,
        ),
        documents_route.adapter_command,
    )
    assert documents.command == "case"
    assert documents.resolve_documents is True

    md_route = query_state_courts.LIVE_ROUTES[
        query_md_public_cases.SOURCE_ID
    ]["search"]
    md_search = md_route.translate(
        _shared_args(
            "search",
            "Midland Credit",
            "--source",
            query_md_public_cases.SOURCE_ID,
            "--after",
            "2026-07-28",
            "--before",
            "2026-07-30",
            "--county",
            "Carroll",
            "--limit",
            "25",
        ),
        md_route.adapter_command,
    )
    assert md_search.command == "search"
    assert md_search.name == "Midland Credit"
    assert md_search.court == "Carroll"
    assert md_search.filing_date_from == "2026-07-28"
    assert md_search.filing_date_to == "2026-07-30"
    assert md_search.all_current is True
    assert md_search.limit == 25

    judgments_route = query_state_courts.LIVE_ROUTES[
        query_md_judgment_liens.SOURCE_ID
    ]["search"]
    judgment_search = judgments_route.translate(
        _shared_args(
            "search",
            "Cobblestone Homeowners Assn Inc",
            "--source",
            query_md_judgment_liens.SOURCE_ID,
            "--entity-kind",
            "organization",
            "--county",
            "Montgomery",
            "--after",
            "2020-01-01",
            "--before",
            "2026-07-30",
        ),
        judgments_route.adapter_command,
    )
    assert judgment_search.command == "company"
    assert judgment_search.company_name == (
        "Cobblestone Homeowners Assn Inc"
    )
    assert judgment_search.county == "Montgomery"
    assert judgment_search.filed_from == "2020-01-01"
    assert judgment_search.filed_to == "2026-07-30"

    judgment_case_route = query_state_courts.LIVE_ROUTES[
        query_md_judgment_liens.SOURCE_ID
    ]["claims"]
    judgment_case = judgment_case_route.translate(
        _shared_args(
            "claims",
            "03-L-12-005195",
            "--source",
            query_md_judgment_liens.SOURCE_ID,
        ),
        judgment_case_route.adapter_command,
    )
    assert judgment_case.command == "detail"
    assert judgment_case.case_number == "03-L-12-005195"


def test_dc_and_maryland_monitor_handlers_are_registered() -> None:
    dc = public_records_monitor.HANDLER_REGISTRY[
        query_dc_appellate_cases.SOURCE_ID
    ]
    md = public_records_monitor.HANDLER_REGISTRY[
        query_md_public_cases.SOURCE_ID
    ]
    judgments = public_records_monitor.HANDLER_REGISTRY[
        query_md_judgment_liens.SOURCE_ID
    ]

    assert dc.handler is public_records_monitor.probe_dc_appellate_cases
    assert dc.expected_requests == 4
    assert md.handler is public_records_monitor.probe_maryland_public_cases
    assert md.expected_requests == 3
    assert judgments.handler is (
        public_records_monitor.probe_maryland_judgment_liens
    )
    assert judgments.expected_requests == 7
    assert judgments.sentinel_record_count == 2
