from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_palm_beach_tax_deeds as tax_deeds


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/palm_beach_tax_deeds"
)
HOME = (FIXTURE_DIR / "home.html").read_text(encoding="utf-8")
LANDS_RESPONSE = (FIXTURE_DIR / "lands-response.html").read_text(
    encoding="utf-8"
)
DETAIL = (FIXTURE_DIR / "detail-43079.html").read_text(encoding="utf-8")
PDF = b"%PDF-1.7\nfixture tax deed document\n%%EOF"

LANDS_ROWS = [
    {
        "id": 43079,
        "cell": [
            "COUNTY OF PALM BEACH",
            "2023-0680TD",
            "10687-2015",
            "04-36-43-25-00-000-5040",
            "10/18/2023",
            "LANDS AVAILABLE",
            "$7,112.49",
            "$7,300.00",
            "$0.00",
            "~CAROLYN PRIEST (EST)~~DANNY PRIEST~~DONNA PRIEST",
        ],
    },
    {
        "id": 40146,
        "cell": [
            "CAPITAL ONE CLTRL ASSIGNEE OF FIG 2222 LLC",
            "40146",
            "18977-2016",
            "48-37-42-18-16-003-0050",
            "10/09/2024",
            "LANDS AVAILABLE",
            "$38,208.71",
            "$74,506.40",
            "$0.00",
            "~FELISIA C HILL~~ATTN: OCCUPANT",
        ],
    },
]


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    json_payload: Any = None

    def json(self):
        if self.json_payload is None:
            raise ValueError("fixture has no JSON")
        return self.json_payload


class QueueSession:
    def __init__(self, responses: list[FixtureResponse]):
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method,
        url,
        *,
        params=None,
        data=None,
        timeout=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "data": dict(data or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("unexpected Palm Beach tax-deed request")
        return self.responses.pop(0)


def fixture_client(responses):
    return tax_deeds.PalmBeachTaxDeedClient(
        QueueSession(responses),
        retry_attempts=1,
    )


def grid_payload(rows=LANDS_ROWS, *, total=1, records=2, page=1):
    return {
        "total": total,
        "page": page,
        "records": records,
        "rows": rows,
    }


def test_discovery_preserves_status_values_and_rolling_sale_dates():
    snapshot = tax_deeds.parse_discovery(HOME)
    record = snapshot.to_record()

    assert dict(
        (item["label"], item["native_value"])
        for item in snapshot.status_options
    ) == dict(tax_deeds.OBSERVED_STATUS_OPTIONS)
    assert record["sale_date_count"] == 3
    assert record["sale_dates"][0] == {
        "raw": "Wednesday, December 16, 2026 12:00 AM",
        "date": "2026-12-16",
    }
    assert record["sale_dates"][-1]["date"] == "1996-01-10"
    assert record["website_version"] == "1.1.7.0"
    assert record["native_page_sizes"] == [10, 25, 50, 100]


def test_native_form_payloads_use_live_status_and_sale_date_choices():
    discovery = tax_deeds.parse_discovery(HOME)

    status_payload, status_type = tax_deeds.build_search_payload(
        tax_deeds.SearchSpec(
            operation="status",
            value="LANDS AVAILABLE",
            from_date="2023-01-01",
            to_date="2024-12-31",
        ),
        discovery,
    )
    assert status_type == "Status"
    assert status_payload == {
        "buttonSubmitStatus": "Search",
        "SearchTypeStatus": "5",
        "dateFromStatus": "01/01/2023",
        "dateToStatus": "12/31/2024",
    }

    sale_payload, sale_type = tax_deeds.build_search_payload(
        tax_deeds.SearchSpec(
            operation="sale-date",
            from_date="2023-10-18",
            to_date="2023-10-18",
        ),
        discovery,
    )
    assert sale_type == "Sale Date"
    assert sale_payload["SearchSaleDateFrom"].startswith(
        "Wednesday, October 18, 2023"
    )
    assert sale_payload["SearchSaleDateTo"] == (
        sale_payload["SearchSaleDateFrom"]
    )


def test_post_response_must_publish_expected_tab_and_search_type():
    assert tax_deeds.parse_search_type(
        LANDS_RESPONSE,
        expected_tab="landsavailable",
    ) == "Lands Available"

    with pytest.raises(
        tax_deeds.PalmBeachTaxDeedSourceChanged,
        match="expected 'status'",
    ):
        tax_deeds.parse_search_type(
            LANDS_RESPONSE,
            expected_tab="status",
        )


def test_grid_row_keeps_all_identities_roles_money_and_status_separate():
    discovery = tax_deeds.parse_discovery(HOME)
    page = tax_deeds.parse_grid_page(grid_payload())
    record = tax_deeds.normalize_grid_row(
        page.rows[0],
        source_page=1,
        source_position=1,
        discovery=discovery,
        search_spec=tax_deeds.SearchSpec(
            operation="lands-available"
        ),
    )

    assert record["portal_row_id"] == "43079"
    assert record["case_number"] == "2023-0680TD"
    assert record["certificate_number"] == "10687-2015"
    assert record["parcel_id"] == "04-36-43-25-00-000-5040"
    assert record["parcel_id_normalized"] == "04364325000005040"
    assert record["native_event_id"] == "row-43079:auction-2023-10-18"
    assert record["status_observation"] == {
        "label": "LANDS AVAILABLE",
        "native_value": "5",
        "role": "clerk_published_tax_deed_lifecycle_status",
        "current_title_inference": False,
    }
    assert record["amounts"]["opening_bid"] == {
        "raw": "$7,112.49",
        "currency": "USD",
        "minor_units": 711249,
    }
    assert record["source_reported_property_owners"] == [
        "CAROLYN PRIEST (EST)",
        "DANNY PRIEST",
        "DONNA PRIEST",
    ]
    assert all(
        person["assertion_type"]
        != "current_recorded_title_owner"
        for person in record["people"]
    )


def test_native_limit_cursor_replays_same_query_and_page_snapshot():
    first_client = fixture_client(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(text=LANDS_RESPONSE),
            FixtureResponse(json_payload=grid_payload()),
        ]
    )
    first = first_client.search(
        tax_deeds.SearchSpec(operation="lands-available"),
        limit=1,
        cursor=None,
    )

    assert len(first.records) == 1
    assert first.records[0]["portal_row_id"] == "43079"
    assert first.complete is False
    assert first.next_cursor is not None
    assert first.records[0]["retrieval_completeness"][
        "source_reported_total"
    ] == 2

    second_client = fixture_client(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(text=LANDS_RESPONSE),
            FixtureResponse(json_payload=grid_payload()),
        ]
    )
    second = second_client.search(
        tax_deeds.SearchSpec(operation="lands-available"),
        limit=1,
        cursor=first.next_cursor,
    )

    assert [record["portal_row_id"] for record in second.records] == [
        "40146"
    ]
    assert second.complete is True
    assert second.next_cursor is None


def test_cursor_rejects_changed_first_page_snapshot():
    first_client = fixture_client(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(text=LANDS_RESPONSE),
            FixtureResponse(json_payload=grid_payload()),
        ]
    )
    first = first_client.search(
        tax_deeds.SearchSpec(operation="lands-available"),
        limit=1,
        cursor=None,
    )
    changed = [dict(row) for row in LANDS_ROWS]
    changed[0] = {
        **changed[0],
        "cell": [
            *changed[0]["cell"][:5],
            "SOLD",
            *changed[0]["cell"][6:],
        ],
    }
    second_client = fixture_client(
        [
            FixtureResponse(text=HOME),
            FixtureResponse(text=LANDS_RESPONSE),
            FixtureResponse(
                json_payload=grid_payload(rows=changed)
            ),
        ]
    )

    with pytest.raises(
        tax_deeds.PalmBeachTaxDeedSnapshotChanged,
        match="snapshot changed",
    ):
        second_client.search(
            tax_deeds.SearchSpec(operation="lands-available"),
            limit=1,
            cursor=first.next_cursor,
        )


def test_detail_preserves_document_occurrences_and_unavailable_images():
    record = tax_deeds.parse_detail(
        DETAIL,
        portal_row_id=tax_deeds.SENTINEL_ROW_ID,
    )

    assert record["case_number"] == "2023-0680TD"
    assert record["certificate_issued_date"] == "2015-05-31"
    assert record["auction_date"] == "2023-10-18"
    assert record["parcel_join_evidence"][
        "property_appraiser_parameter_matches"
    ] is True
    assert record["applicants"] == ["COUNTY OF PALM BEACH"]
    assert record["source_reported_property_owners"] == [
        "CAROLYN PRIEST (EST)",
        "DANNY PRIEST",
        "DONNA PRIEST",
    ]
    assert record["property_address_raw"] == ", FL"
    assert record["address"] is None
    assert record["amounts"]["high_bid"]["minor_units"] == 730000
    assert [document["access_state"] for document in record["documents"]] == [
        "public_pdf",
        "image_not_available",
        "public_pdf",
    ]
    assert record["documents"][0]["native_document_id"] == "24748216"
    assert record["documents"][1]["label"] == "Abstract"
    assert record["documents"][1]["native_document_id"] is None
    assert record["documents"][0]["document_occurrence_id"] == (
        "43079:document:1"
    )


def test_document_fetch_requires_case_inventory_and_hashes_public_pdf():
    case_record = tax_deeds.parse_detail(
        DETAIL,
        portal_row_id=tax_deeds.SENTINEL_ROW_ID,
    )
    client = fixture_client(
        [
            FixtureResponse(
                content=PDF,
                headers={
                    "Content-Type": "application/pdf",
                    "Content-Disposition": (
                        "inline; filename=something.pdf"
                    ),
                },
            )
        ]
    )

    document, artifact = client.document(
        case_record,
        tax_deeds.SENTINEL_DOCUMENT_ID,
    )

    assert document["label"] == "Tax Certificate"
    assert artifact.media_type == "application/pdf"
    assert artifact.content == PDF
    assert artifact.sha256 == hashlib.sha256(PDF).hexdigest()
    assert client.session.calls[0]["url"].endswith(
        "/Home/Image/24748216"
    )


def test_document_fetch_rejects_id_not_listed_on_case():
    case_record = tax_deeds.parse_detail(
        DETAIL,
        portal_row_id=tax_deeds.SENTINEL_ROW_ID,
    )
    client = fixture_client([])

    with pytest.raises(
        tax_deeds.PalmBeachTaxDeedQueryError,
        match="not a unique available document",
    ):
        client.document(case_record, "99999999")


def test_execute_zero_results_is_authoritative(monkeypatch):
    class FakeClient:
        def search(self, spec, *, limit, cursor):
            assert spec.operation == "lands-available"
            assert limit is None
            assert cursor is None
            return tax_deeds.SearchBatch(
                records=(),
                total_records=0,
                total_pages=0,
                snapshot_fingerprint="fixture",
                next_cursor=None,
                complete=True,
            )

    monkeypatch.setattr(tax_deeds, "_log", lambda *_args: None)
    args = tax_deeds.build_parser().parse_args(["lands-available"])

    result = tax_deeds.execute(args, client=FakeClient())

    assert result.status == tax_deeds.ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_execute_document_writes_separate_artifact(monkeypatch, tmp_path):
    case_record = tax_deeds.parse_detail(
        DETAIL,
        portal_row_id=tax_deeds.SENTINEL_ROW_ID,
    )
    selected_document = case_record["documents"][0]

    class FakeClient:
        def detail(self, portal_row_id):
            assert portal_row_id == "43079"
            return case_record

        def document(self, record, native_document_id):
            assert record["canonical_ref"] == case_record["canonical_ref"]
            assert native_document_id == "24748216"
            return selected_document, tax_deeds.PDFArtifact(
                content=PDF,
                media_type="application/pdf",
                content_disposition="inline; filename=something.pdf",
                sha256=hashlib.sha256(PDF).hexdigest(),
            )

    monkeypatch.setattr(tax_deeds, "_log", lambda *_args: None)
    destination = tmp_path / "tax-certificate.pdf"
    args = tax_deeds.build_parser().parse_args(
        [
            "document",
            "43079",
            "24748216",
            "--document-output",
            str(destination),
        ]
    )

    result = tax_deeds.execute(args, client=FakeClient())

    assert result.status == tax_deeds.ResultStatus.OK
    assert destination.read_bytes() == PDF
    artifact = result.records[0]
    assert artifact["record_kind"] == "tax_deed_document_artifact"
    assert artifact["native_document_id"] == "24748216"
    assert artifact["parent_canonical_ref"] == case_record["canonical_ref"]
    assert result.raw_artifact_refs == (str(destination),)


def test_official_routes_are_field_specific_and_keep_source_ids_separate():
    routes = tax_deeds.official_routes()
    by_kind = {route["kind"]: route for route in routes}

    assert by_kind["property_appraiser"]["source_id"] == (
        "us-fl-palm-beach-property-appraiser"
    )
    assert by_kind["tax_collector"]["source_id"] == (
        "us-fl-palm-beach-tax-collector"
    )
    assert by_kind["official_records"]["source_id"] == (
        "us-fl-palm-beach-official-records"
    )
    assert by_kind["ecaseview"]["source_id"] == (
        "us-fl-palm-beach-ecaseview"
    )
    assert by_kind["certified_official_record_copy"]["relationship"] == (
        "separate_order_and_payment_route"
    )
