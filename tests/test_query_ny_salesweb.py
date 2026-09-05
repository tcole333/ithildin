from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import query_ny_salesweb as salesweb
from tools.public_records_http import SourceResponseError


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "public_records" / "ny_salesweb"


def _load(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _references():
    return _load("references.json")["app"]["data"]


def _search_rows():
    return _load("search.json")["app"]["data"]["oServiceResponse"]["salesWebList"]


def _detail():
    payload = _load("detail.json")["app"]["data"]
    return (
        payload["oServiceResponse"]["data"]["salesWebRow"],
        payload["aRefTblResponse"]["data"],
    )


class FakeSalesWebClient:
    def __init__(
        self,
        *,
        rows=None,
        full_length: int | None = None,
        full_length_sequence=None,
        empty_at_offset: int | None = None,
    ):
        self.references = copy.deepcopy(_references())
        self.rows = copy.deepcopy(rows if rows is not None else _search_rows())
        self.full_length = len(self.rows) if full_length is None else full_length
        self.full_length_sequence = list(full_length_sequence or [])
        self.empty_at_offset = empty_at_offset
        self.search_calls = []
        self.reference_calls = 0
        self.detail_calls = []
        self.download_calls = []
        self.request_count = 0

    def fetch_references(self, *, refresh=False):
        self.reference_calls += 1
        self.request_count += 1
        return copy.deepcopy(self.references)

    def search(self, request):
        self.search_calls.append(copy.deepcopy(request))
        self.request_count += 1
        offset = request["offset"]
        limit = request["limit"]
        if self.empty_at_offset == offset:
            records = []
        else:
            records = self.rows[offset : offset + limit]
        full_length = (
            self.full_length_sequence.pop(0)
            if self.full_length_sequence
            else self.full_length
        )
        return salesweb.SearchPage(
            records=tuple(copy.deepcopy(records)),
            full_length=full_length,
            schema_fingerprint=salesweb._record_schema_fingerprint(records),
        )

    def detail(self, sale_transaction_number):
        self.detail_calls.append(sale_transaction_number)
        self.request_count += 1
        row, refs = _detail()
        row = copy.deepcopy(row)
        row["saleTranNmbr"] = sale_transaction_number
        return row, copy.deepcopy(refs)

    def download(self, request):
        self.download_calls.append(copy.deepcopy(request))
        self.request_count += 1
        return (FIXTURE_DIR / "export.csv").read_bytes()


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        salesweb,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def test_source_id_matches_canonical_catalog_identity():
    assert salesweb.SOURCE_ID == "us-ny-orpts-sales-web"
    assert salesweb.SOURCE_METADATA.source_id == salesweb.SOURCE_ID


def test_reference_index_resolves_names_codes_and_two_digit_county_prefix():
    index = salesweb.ReferenceIndex(_references())

    assert index.resolve_counties(["Albany", "02"]) == ["010000", "020000"]
    assert index.resolve_municipalities(["Berne"], ["010000"]) == ["012000"]
    assert index.resolve_schools(["012001"]) == ["012001"]


def test_ambiguous_municipality_returns_choices_instead_of_guessing():
    index = salesweb.ReferenceIndex(_references())

    with pytest.raises(salesweb.NYSalesWebError) as caught:
        index.resolve_municipalities(["Colonie"], ["010000"])

    assert caught.value.code == "ambiguous_reference"
    assert {choice["code"] for choice in caught.value.details["choices"]} == {
        "012600",
        "012601",
    }


def test_build_search_request_matches_verified_spa_payload():
    args = salesweb.build_parser().parse_args(
        [
            "search",
            "--county",
            "Albany",
            "--municipality",
            "012000",
            "--school",
            "Berne-Knox-Westerlo",
            "--seller",
            "OWNER",
            "--book",
            "2025",
            "--page",
            "19127",
            "--tax-map",
            "91.-1",
            "--tax-map-mode",
            "begins",
            "--sale-from",
            "2025-01-01",
            "--sale-to",
            "2025-12-31",
            "--price-min",
            "100000",
            "--price-max",
            "900000",
            "--arms-length",
            "yes",
            "--property-class",
            "210,240",
            "--sort",
            "sale-price:descending",
        ]
    )

    request = salesweb.build_search_request(
        args,
        _references(),
        offset=25,
        limit=100,
    )

    assert request["counties"] == ["010000"]
    assert request["munis"] == ["012000"]
    assert request["schools"] == ["012001"]
    assert request["offset"] == 25
    assert request["limit"] == 100
    assert request["sortBy"] == [{"fieldName": "salePrice", "value": "descending"}]
    assert {"fieldName": "seller", "value": "OWNER"} in request["criterias"]
    assert {
        "fieldName": "bookPage",
        "book": "2025",
        "page": "19127",
    } in request["criterias"]
    assert {
        "fieldName": "taxMapId",
        "operator": "BEGIN_WITH",
        "value": "91.-1",
    } in request["criterias"]


def test_search_keeps_sale_identity_separate_from_exact_parcel_join():
    args = salesweb.build_parser().parse_args(
        ["search", "--municipality", "012000", "--limit", "1"]
    )

    result = salesweb.execute(args, client=FakeSalesWebClient())

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["sale_record_id"] == "2047101021"
    assert record["native_record_id"] == "2047101021"
    assert record["record_identity"]["source_native_key"] == "saleTranNmbr"
    parcel_ids = record["property"]["parcel_identifiers"]
    assert parcel_ids["swis_print_key_id"] == "01200091.-1-30.11"
    assert record["property"]["parcel_join"]["exact_join_fields"] == {
        "SWIS": "012000",
        "PRINT_KEY": "91.-1-30.11",
        "SWIS_PRINT_KEY_ID": "01200091.-1-30.11",
    }
    assert tuple(
        record["property"]["parcel_join"]["statewide_parcel_query"]["arguments"]
    ) == (
        "parcel",
        "01200091.-1-30.11",
        "--id-type",
        "swis-print-key",
    )
    assert record["canonical_ref"] != record["property"]["parcel_join"]["canonical_ref"]


def test_bounded_search_paginates_and_resumes_with_bound_cursor():
    first_args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--limit",
            "2",
            "--page-size",
            "1",
        ]
    )
    first_client = FakeSalesWebClient()

    first = salesweb.execute(first_args, client=first_client)

    assert [record["sale_record_id"] for record in first.records] == [
        "2047101021",
        "2047101022",
    ]
    assert [call["offset"] for call in first_client.search_calls] == [0, 1]
    assert first.next_cursor

    second_args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--limit",
            "2",
            "--page-size",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )
    second_client = FakeSalesWebClient()
    second = salesweb.execute(second_args, client=second_client)

    assert [record["sale_record_id"] for record in second.records] == ["2047101023"]
    assert second_client.search_calls[0]["offset"] == 2
    assert second.next_cursor is None


def test_all_records_exhausts_native_full_length():
    args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--all",
            "--page-size",
            "2",
        ]
    )
    client = FakeSalesWebClient()

    result = salesweb.execute(args, client=client)

    assert result.status.value == "ok"
    assert len(result.records) == 3
    assert [call["offset"] for call in client.search_calls] == [0, 2]
    assert result.next_cursor is None


def test_cursor_rejects_changed_criteria():
    first_args = salesweb.build_parser().parse_args(
        ["search", "--municipality", "012000", "--limit", "1"]
    )
    first = salesweb.execute(first_args, client=FakeSalesWebClient())

    changed_args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--seller",
            "DIFFERENT",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )
    changed = salesweb.execute(changed_args, client=FakeSalesWebClient())

    assert changed.status.value == "source_changed"
    assert changed.errors[0].code == "stale_cursor"


def test_cursor_rejects_weekly_result_count_change():
    first_args = salesweb.build_parser().parse_args(
        ["search", "--municipality", "012000", "--limit", "1"]
    )
    first = salesweb.execute(first_args, client=FakeSalesWebClient())
    resume_args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ]
    )

    resumed = salesweb.execute(
        resume_args,
        client=FakeSalesWebClient(full_length=4),
    )

    assert resumed.status.value == "source_changed"
    assert resumed.errors[0].code == "stale_cursor"


def test_empty_page_before_reported_end_is_not_no_results():
    args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--all",
            "--page-size",
            "2",
        ]
    )

    result = salesweb.execute(
        args,
        client=FakeSalesWebClient(empty_at_offset=2),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "pagination_stalled"


def test_authoritative_empty_search_is_no_results():
    args = salesweb.build_parser().parse_args(
        ["search", "--municipality", "012000", "--limit", "1"]
    )

    result = salesweb.execute(
        args,
        client=FakeSalesWebClient(rows=[], full_length=0),
    )

    assert result.status.value == "no_results"
    assert result.errors == ()


def test_detail_preserves_parties_deed_flags_and_source_dates():
    args = salesweb.build_parser().parse_args(["detail", "2047101021", "--include-raw"])

    result = salesweb.execute(args, client=FakeSalesWebClient())

    record = result.records[0]
    assert record["transaction"]["deed"] == {
        "book": 2025,
        "page": 19127,
        "document_number": "DOC-2025-19127",
        "deed_date": {
            "raw": "2025-10-21T04:00:00Z[UTC]",
            "iso": "2025-10-21",
        },
    }
    assert record["parties"]["buyer"]["name"] == "BUYER LLC, BETA"
    assert record["parties"]["buyer"]["mailing_address"]["city"] == "BERNE"
    assert record["related_professionals"]["attorney"]["phone"] == "5185550100"
    assert record["transaction"]["usability"]["arms_length"]["boolean"] is True
    assert record["transaction"]["condition_flags"]["CompanySale"]["boolean"] is True
    assert record["source_processing"]["load_date"]["iso"] == "2025-11-06"
    assert record["raw_source_record"]["saleTranNmbr"] == 2047101021


def test_export_writes_verified_csv_artifact_and_reports_missing_sale_id(tmp_path):
    destination = tmp_path / "sales.csv"
    args = salesweb.build_parser().parse_args(
        [
            "export",
            "--municipality",
            "012000",
            "--limit",
            "1",
            "--csv-output",
            str(destination),
        ]
    )
    client = FakeSalesWebClient()

    result = salesweb.execute(args, client=client)

    assert result.status.value == "ok"
    record = result.records[0]
    assert destination.read_bytes() == (FIXTURE_DIR / "export.csv").read_bytes()
    assert record["csv_record_count"] == 1
    assert len(record["artifact_sha256"]) == 64
    assert "saleTranNmbr" in record["sale_identity_note"]
    assert client.download_calls[0]["limit"] == 1


def test_alternatives_cover_nyc_staten_island_older_records_and_parcel_join():
    args = salesweb.build_parser().parse_args(["alternatives"])

    result = salesweb.execute(args)

    routes = {record["route_id"]: record for record in result.records}
    assert routes["nyc-acris-recorded-documents"]["search_url"].startswith(
        "https://a836-acris.nyc.gov/"
    )
    assert routes["richmond-county-land-documents"]["url"] == (
        salesweb.RICHMOND_CLERK_URL
    )
    assert (
        routes["ny-statewide-parcel-map"]["exact_join"]["parcel_map"][-1]
        == "SWIS_PRINT_KEY_ID"
    )
    assert "older transfers" in routes["county-clerk-recorded-instruments"]["coverage"]


def test_probe_is_bounded_and_checks_reference_search_detail():
    args = salesweb.build_parser().parse_args(["probe"])
    client = FakeSalesWebClient()

    result = salesweb.execute(args, client=client)

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["bounded_search"]["municipality_code"] == "012000"
    assert record["bounded_search"]["returned_rows"] == 1
    assert record["detail"]["sale_transaction_identity_present"] is True
    assert record["detail"]["swis_print_key_join_present"] is True
    assert client.search_calls[0]["limit"] == 1


class FakeResponse:
    def __init__(self, payload, *, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.headers = {}

    def json(self):
        return copy.deepcopy(self.payload)


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        return self.response


def test_http_client_uses_official_post_envelope_and_origin():
    session = FakeSession(FakeResponse(_load("search.json")))
    client = salesweb.SalesWebClient(
        session=session,
        minimum_interval=0,
        retry_attempts=1,
    )
    request = {
        "counties": [],
        "munis": ["012000"],
        "schools": [],
        "criterias": [],
        "sortBy": [],
        "offset": 0,
        "limit": 2,
    }

    page = client.search(request)

    assert page.full_length == 3
    assert len(page.records) == 3
    url, kwargs = session.calls[0]
    assert url == f"{salesweb.API_ROOT}/{salesweb.SEARCH_ACTION}"
    assert kwargs["json"] == {"data": request}
    assert kwargs["headers"]["Origin"] == salesweb.APP_URL


def test_source_error_response_is_not_treated_as_empty():
    payload = {
        "status": "success",
        "app": {
            "data": {
                "oServiceResponse": {
                    "status": "ERROR",
                    "fullLength": 0,
                    "salesWebList": [],
                }
            }
        },
    }
    client = salesweb.SalesWebClient(
        session=FakeSession(FakeResponse(payload)),
        minimum_interval=0,
        retry_attempts=1,
    )

    with pytest.raises(SourceResponseError):
        client.search(
            {
                "counties": [],
                "munis": ["012000"],
                "schools": [],
                "criterias": [],
                "sortBy": [],
                "offset": 0,
                "limit": 1,
            }
        )
