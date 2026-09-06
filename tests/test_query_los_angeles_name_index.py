from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import query_los_angeles_name_index as index
from tools.ingest_state_court_records import ingest_envelope
from tools.public_records_contract import (
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
    ResultStatus,
    SourceMetadata,
)
from tools.public_records_store import connect_courts


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/los_angeles_name_index"
)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        url: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = headers or {
            "Content-Type": "text/html; charset=utf-8"
        }


class FakeSession:
    def __init__(
        self,
        *,
        get_responses: list[FakeResponse] | None = None,
        post_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("get", {"url": url, **kwargs}))
        response = self.get_responses.pop(0)
        if response.url is None:
            response.url = url
        return response

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("post", {"url": url, **kwargs}))
        response = self.post_responses.pop(0)
        if response.url is None:
            response.url = url
        return response

    def close(self) -> None:
        self.closed = True


def _client(session: FakeSession) -> index.LANameIndexClient:
    return index.LANameIndexClient(
        session=session,
        timeout=11,
        minimum_interval=0,
        sleeper=lambda _delay: None,
    )


def _parse(*values: str):
    return index.build_parser().parse_args(list(values))


def test_landing_parser_preserves_every_native_case_type_period() -> None:
    parsed = index.parse_civil_index_html(_fixture("civil_index.html"))

    assert parsed["updated_daily"] is True
    assert parsed["coverage"] == [
        {"case_type": "Unlimited Civil", "source_date_range": "1983 - Present"},
        {"case_type": "Probate", "source_date_range": "1983 - Present"},
        {"case_type": "Family Law", "source_date_range": "1983 - Present"},
        {"case_type": "Limited Civil", "source_date_range": "1991 - Present"},
        {"case_type": "Small Claims", "source_date_range": "1992 - Present"},
    ]
    assert parsed["archive_url"] == index.ARCHIVES_URL


def test_fee_parser_preserves_guest_and_all_registered_tiers() -> None:
    parsed = index.parse_fee_html(_fixture("fees.html"))

    fees = parsed["name_search_fees"]
    assert len(fees) == 6
    assert [row["amount_usd"] for row in fees if row["account_type"] == "guest"] == [
        4.75
    ]
    assert [row["amount_usd"] for row in fees if row["account_type"] == "registered"] == [
        1.0,
        4.75,
        4.5,
        4.25,
        4.0,
    ]


def test_search_form_parser_tracks_exact_source_fields() -> None:
    form = index.parse_search_form_html(_fixture("search.html"))

    assert form.token == "search-token"
    assert form.method == "post"
    assert form.action_url == index.SEARCH_URL
    assert form.remark_max_length == 30
    assert form.field_names == (
        "LastName",
        "FirstName",
        "CompanyName",
        "Remark",
        "FilingDateStart",
        "FilingDateEnd",
        "__RequestVerificationToken",
    )


def test_guest_parser_recovers_transaction_and_source_action_id() -> None:
    guest = index.parse_guest_html(_fixture("guest_transactions.html"))

    assert guest.no_valid_receipts is False
    assert len(guest.transactions) == 1
    transaction = guest.transactions[0]
    assert transaction.receipt_number == "PA-2026-123456789"
    assert transaction.action_id == "IDX"
    assert transaction.case_type == "Civil"
    assert transaction.description == 'Civil Name Search For "ACME HOLDINGS LLC"'


def test_result_parser_and_normalizer_keep_collision_qualifiers() -> None:
    page = index.parse_results_html(_fixture("results.html"))
    records = index.normalize_matches(page)

    assert len(records) == 3
    assert records[0]["raw_case_number"] == "24STCV01234"
    assert records[0]["matched_party_name"] == "ACME HOLDINGS LLC"
    assert records[0]["case_type"] == "Unlimited Civil"
    assert records[0]["filing_date"] == "2024-07-01"
    assert records[0]["source_filing_date_raw"] == "07/01/2024"
    assert records[0]["filing_location"] == "Stanley Mosk Courthouse"
    assert records[0]["available_imaged_document_count"] == 12
    assert records[0]["case_canonical_ref"] == records[1]["case_canonical_ref"]
    assert records[0]["canonical_ref"] != records[1]["canonical_ref"]
    assert records[0]["source_internal_id"] == records[1]["source_internal_id"]
    assert records[0]["source_result_id"] != records[1]["source_result_id"]
    assert records[0]["record_identity_source_id"] == index.CORE_CIVIL_SOURCE_ID
    assert records[0]["court"]["court_id"] == index.CORE_CIVIL_COURT_ID
    assert records[0]["identity_basis"]["duplicate_ordinal"] == 0
    assert records[1]["identity_basis"]["duplicate_ordinal"] == 1
    assert records[2]["filing_location"] == "Pomona Courthouse South"
    assert records[2]["record_identity_source_id"] == index.PROBATE_SOURCE_ID
    assert records[2]["court"]["court_id"] == index.PROBATE_COURT_ID
    assert records[0]["parties"] == [
        {
            "name": "ACME HOLDINGS LLC",
            "role": "litigant",
            "native_role": "litigant",
            "source_match": "civil_party_name_index",
        }
    ]


def test_result_parser_distinguishes_authoritative_empty_page() -> None:
    page = index.parse_results_html(_fixture("no_results.html"))

    assert page.matches == ()
    assert page.no_results_message == "No match found for the supplied name."


def test_case_family_identity_maps_every_advertised_index_family() -> None:
    assert index._case_family_identity("Unlimited Civil") == (
        index.CORE_CIVIL_SOURCE_ID,
        index.CORE_CIVIL_COURT_ID,
        "civil",
    )
    assert index._case_family_identity("Limited Civil") == (
        index.CORE_CIVIL_SOURCE_ID,
        index.CORE_CIVIL_COURT_ID,
        "civil",
    )
    assert index._case_family_identity("Family Law") == (
        index.FAMILY_SOURCE_ID,
        index.FAMILY_COURT_ID,
        "family_law",
    )
    assert index._case_family_identity("Small Claims") == (
        index.SMALL_CLAIMS_SOURCE_ID,
        index.SMALL_CLAIMS_COURT_ID,
        "small_claims",
    )
    assert index._case_family_identity("Probate") == (
        index.PROBATE_SOURCE_ID,
        index.PROBATE_COURT_ID,
        "probate",
    )


def test_prepare_uses_one_guest_session_and_stops_at_cart_summary() -> None:
    checkout_url = (
        "https://ww2.lacourt.org/ShoppingCart/v3/Home/Index/"
        "?appid=PAOS&cartid=fixture&security=signed"
    )
    session = FakeSession(
        get_responses=[
            FakeResponse(_fixture("guest_empty.html")),
            FakeResponse(_fixture("civil_index.html")),
            FakeResponse(_fixture("search.html")),
            FakeResponse(
                "",
                status_code=302,
                url=index.PAYMENT_URL,
                headers={"Location": checkout_url},
            ),
            FakeResponse(
                _fixture("cart.html"),
                url=checkout_url,
            ),
        ],
        post_responses=[
            FakeResponse(
                "",
                status_code=302,
                url=index.SEARCH_URL,
                headers={"Location": index.PAYMENT_URL},
            )
        ],
    )
    criteria = index._query_criteria(
        first_name=None,
        last_name=None,
        company="ACME HOLDINGS LLC",
        filing_date_start="01/01/2020",
        filing_date_end="12/31/2025",
        remark="fixture",
    )

    prepared = _client(session).prepare(criteria)

    assert prepared.cart.total_usd == 4.75
    assert prepared.checkout_url == checkout_url
    assert [name for name, _kwargs in session.calls] == [
        "get",
        "get",
        "get",
        "post",
        "get",
        "get",
    ]
    post = session.calls[3][1]
    assert post["url"] == index.SEARCH_URL
    assert post["allow_redirects"] is False
    assert post["data"] == {
        "LastName": "",
        "FirstName": "",
        "CompanyName": "ACME HOLDINGS LLC",
        "Remark": "fixture",
        "FilingDateStart": "01/01/2020",
        "FilingDateEnd": "12/31/2025",
        "__RequestVerificationToken": "search-token",
    }


def test_receipt_recovery_posts_verified_idx_action_then_normalizes() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(_fixture("guest_empty.html"))],
        post_responses=[
            FakeResponse(_fixture("guest_transactions.html")),
            FakeResponse(
                _fixture("results.html"),
                url=f"{index.CIVIL_INDEX_URL}/Results",
            ),
        ],
    )

    transaction, page = _client(session).retrieve_receipt_search(
        "PA-2026-123456789",
        "1234",
    )

    assert transaction.action_id == "IDX"
    assert len(page.matches) == 3
    attach = session.calls[1][1]["data"]
    retrieve = session.calls[2][1]["data"]
    assert attach["ActionToPerform"] == "addreceipt"
    assert attach["Last4CC"] == "1234"
    assert retrieve == {
        "ReceiptNumber": "",
        "Last4CC": "",
        "ActionToPerform": "IDX",
        "ActionDocumentID": "",
        "ActionReceiptNumber": "PA-2026-123456789",
        "SecurityKey": "",
        "__RequestVerificationToken": "attached-token",
    }


def test_invalid_receipt_is_explicit_failure_not_no_results() -> None:
    session = FakeSession(
        get_responses=[FakeResponse(_fixture("guest_empty.html"))],
        post_responses=[FakeResponse(_fixture("guest_empty.html"))],
    )

    result = index.execute(
        _parse("receipt", "PA-2026-00000000", "0000"),
        client=_client(session),
        log_results=False,
    )

    assert result.status is ResultStatus.RESTRICTED
    assert result.errors[0].code == "receipt_not_attached"
    assert result.records == ()


def test_sources_inventory_keeps_substitutes_distinct() -> None:
    records = index.source_records()
    route_ids = {record["route_id"] for record in records}
    source_ids = {
        record["route_id"]: record["source_id"] for record in records
    }

    assert route_ids == {
        "civil_party_name_index",
        "exact_case_summary",
        "case_document_images",
        "archives_and_clerk",
        "divorce_judgment_orders",
        "tentative_rulings",
        "california_appellate_case_information",
        "trellis_los_angeles",
    }
    exact = next(
        record
        for record in records
        if record["route_id"] == "exact_case_summary"
    )
    assert exact["gap"] == "requires a known case number"
    assert source_ids == {
        "civil_party_name_index": index.SOURCE_ID,
        "exact_case_summary": index.CORE_CIVIL_SOURCE_ID,
        "case_document_images": index.DOCUMENT_IMAGES_SOURCE_ID,
        "archives_and_clerk": index.ARCHIVES_SOURCE_ID,
        "divorce_judgment_orders": index.DIVORCE_JUDGMENT_SOURCE_ID,
        "tentative_rulings": index.CORE_CIVIL_SOURCE_ID,
        "california_appellate_case_information": (
            index.SECOND_DISTRICT_SOURCE_ID
        ),
        "trellis_los_angeles": index.TRELLIS_SOURCE_ID,
    }


def test_result_envelope_projects_cases_without_splitting_duplicate_rows(
    tmp_path: Path,
) -> None:
    args = _parse(
        "parse-results",
        str(FIXTURE_DIR / "results.html"),
    )
    result = index.execute(args, log_results=False)

    court_db = tmp_path / "court_records.db"
    receipt = ingest_envelope(
        result.to_dict(),
        court_db=court_db,
    )

    assert receipt["projected"]["cases"] == 3
    assert receipt["projected"]["parties"] == 0
    assert len(receipt["canonical_refs"]) == 3
    assert len(set(receipt["canonical_refs"])) == 2

    db = connect_courts(court_db)
    try:
        cases = db.execute(
            """
            SELECT case_id, source_id, court_id, raw_case_number,
                   source_internal_id
            FROM case_record
            ORDER BY source_id, raw_case_number
            """
        ).fetchall()
        assert len(cases) == 2
        assert {
            (row["source_id"], row["court_id"], row["raw_case_number"])
            for row in cases
        } == {
            (
                index.CORE_CIVIL_SOURCE_ID,
                index.CORE_CIVIL_COURT_ID,
                "24STCV01234",
            ),
            (
                index.PROBATE_SOURCE_ID,
                index.PROBATE_COURT_ID,
                "22PSTB00456",
            ),
        }
        assert {row["source_internal_id"] for row in cases} == {None}

        occurrences = db.execute(
            """
            SELECT o.source_id, o.record_identity_source_id,
                   o.source_result_id, o.matched_party_name,
                   o.case_type, o.filing_location, c.raw_case_number
            FROM case_source_occurrence o
            JOIN case_record c ON c.case_id = o.case_id
            ORDER BY o.occurrence_id
            """
        ).fetchall()
        assert len(occurrences) == 3
        assert {row["source_id"] for row in occurrences} == {
            index.SOURCE_ID
        }
        assert {
            row["record_identity_source_id"] for row in occurrences
        } == {
            index.CORE_CIVIL_SOURCE_ID,
            index.PROBATE_SOURCE_ID,
        }
        assert len(
            {row["source_result_id"] for row in occurrences}
        ) == 3
        assert [row["raw_case_number"] for row in occurrences[:2]] == [
            "24STCV01234",
            "24STCV01234",
        ]
    finally:
        db.close()

    exact_query = PublicRecordsQuery(
        source=SourceMetadata(
            source_id=index.CORE_CIVIL_SOURCE_ID,
            name="Los Angeles Superior Court Civil Case Summary",
            source_role="county_superior_civil_exact_case",
            base_url=index.EXACT_CASE_URL,
        ),
        jurisdiction=index.JURISDICTION,
        query=QueryMetadata(
            operation="case",
            parameters={"case_number": "24STCV01234"},
        ),
    )
    exact_record = {
        "source_id": index.CORE_CIVIL_SOURCE_ID,
        "court": {
            "court_id": index.CORE_CIVIL_COURT_ID,
            "native_court_id": index.CORE_CIVIL_COURT_ID,
            "name": index.COURT_NAME,
            "state_code": "CA",
            "county_geoid": index.COUNTY_GEOID,
        },
        "raw_case_number": "24STCV01234",
        "display_case_number": "24STCV01234",
        "caption": "ACME HOLDINGS LLC v. EXAMPLE DEFENDANT",
        "case_type": "Unlimited Civil",
        "filing_date": "2024-07-01",
        "access_state": "public",
        "parties": [
            {
                "raw_name": "ACME HOLDINGS LLC",
                "role": "plaintiff",
            }
        ],
    }
    ingest_envelope(
        PublicRecordsResult.success(
            exact_query,
            [exact_record],
        ).to_dict(),
        court_db=court_db,
    )

    db = connect_courts(court_db)
    try:
        civil = db.execute(
            """
            SELECT case_id, caption, snapshot_id
            FROM case_record
            WHERE source_id=? AND court_id=? AND raw_case_number=?
            """,
            (
                index.CORE_CIVIL_SOURCE_ID,
                index.CORE_CIVIL_COURT_ID,
                "24STCV01234",
            ),
        ).fetchone()
        assert civil["caption"] == (
            "ACME HOLDINGS LLC v. EXAMPLE DEFENDANT"
        )
        assert db.execute(
            "SELECT COUNT(*) FROM case_record"
        ).fetchone()[0] == 2
        assert db.execute(
            """
            SELECT COUNT(*) FROM case_source_occurrence
            WHERE case_id=?
            """,
            (civil["case_id"],),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM case_party WHERE case_id=?",
            (civil["case_id"],),
        ).fetchone()[0] == 1
    finally:
        db.close()
