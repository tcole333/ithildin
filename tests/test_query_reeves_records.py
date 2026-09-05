from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools import query_reeves_records as reeves
from tools.kofile_publicsearch import (
    KofileBootstrap,
    KofileNotFoundError,
    KofilePageImage,
    KofileRateLimitError,
    KofileSearchPage,
    KofileUnavailableError,
)
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/reeves_records")
SEARCH_RECORD = json.loads(
    (FIXTURE_DIR / "search_record.json").read_text(encoding="utf-8")
)
DOCUMENT_DETAIL = json.loads(
    (FIXTURE_DIR / "document_detail.json").read_text(encoding="utf-8")
)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.error = None
        self.closed = False
        self.search_page = KofileSearchPage(
            records=(SEARCH_RECORD,),
            total_count=4,
            statistics={
                "recorded-years": [{"label": "2018", "hits": 4}],
                "docTypes": [{"label": "ABS1", "hits": 1}],
            },
            offset=0,
            limit=1,
            next_offset=1,
            response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
        )
        self.bootstrap_value = KofileBootstrap(
            state={},
            auth_token="fixture-anonymous-token",
            ip="203.0.113.10",
            tenant_id="48389",
            department_codes=("RP", "FC", "CCM", "ASN", "MB", "PN"),
            department_date_ranges={"RP": {"recordedDateRange": "18840101,20260720"}},
        )

    def _maybe_raise(self):
        if self.error is not None:
            raise self.error

    def bootstrap(self, *, force=False):
        self._maybe_raise()
        self.calls.append(("bootstrap", force))
        return self.bootstrap_value

    def search(self, **kwargs):
        self._maybe_raise()
        self.calls.append(("search", kwargs))
        if (
            kwargs.get("workspace_id")
            == "ithildin-tx-reeves-recorder-probe"
        ):
            return KofileSearchPage(
                records=(SEARCH_RECORD,),
                total_count=1,
                statistics=self.search_page.statistics,
                offset=0,
                limit=1,
                next_offset=None,
                response_type=self.search_page.response_type,
            )
        return self.search_page

    def fetch_document(self, doc_id):
        self._maybe_raise()
        self.calls.append(("document", doc_id))
        return DOCUMENT_DETAIL

    def fetch_page_image(self, doc_id, page_number):
        self._maybe_raise()
        self.calls.append(("page", doc_id, page_number))
        return KofilePageImage(
            document=DOCUMENT_DETAIL,
            page_number=page_number,
            source_url=(
                "https://reeves.tx.publicsearch.us/files/documents/"
                "20798096/images/19747017_1.png?"
                "exp=2000000000&sig=ephemeral-page-token"
            ),
            media_type="image/png",
            content=b"\x89PNG\r\n\x1a\nfixture-page",
            etag='"fixture-page-etag"',
        )

    def close(self):
        self.closed = True


def _execute(args, monkeypatch, client):
    logged = []
    monkeypatch.setattr(
        reeves,
        "log_search",
        lambda *values: logged.append(values),
    )
    return reeves.execute(args, client=client), logged


def test_query_contract_exposes_caller_limit_and_source_offset_without_cap():
    args = reeves.build_parser().parse_args(
        [
            "search",
            "THREE RIVERS",
            "--limit",
            "10000",
            "--offset",
            "250",
        ]
    )

    query = reeves.build_query(args)

    assert query.source.source_id == reeves.SOURCE_ID
    assert query.jurisdiction.county_fips == "48389"
    assert query.query.requested_limit == 10000
    assert query.query.cursor is None
    assert query.query.parameters["offset"] == 250
    assert query.query.parameters["query"] == "THREE RIVERS"


def test_omitted_limit_exhausts_source_offsets(monkeypatch):
    class ExhaustiveClient(FakeClient):
        def search(self, **kwargs):
            self.calls.append(("search", kwargs))
            offset = kwargs["offset"]
            rows = []
            for index in range(offset, min(offset + 2, 3)):
                rows.append(
                    {
                        **SEARCH_RECORD,
                        "id": 20798096 + index,
                        "docId": 20798096 + index,
                        "instrumentNumber": f"18-0648{index + 1}",
                        "docNumber": f"18-0648{index + 1}",
                    }
                )
            next_offset = offset + len(rows)
            return KofileSearchPage(
                records=tuple(rows),
                total_count=3,
                statistics={},
                offset=offset,
                limit=kwargs["limit"],
                next_offset=next_offset if next_offset < 3 else None,
                response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
            )

    client = ExhaustiveClient()
    args = reeves.build_parser().parse_args(["search", "THREE RIVERS"])

    result, logged = _execute(args, monkeypatch, client)

    assert result.status is ResultStatus.OK
    assert result.query.query.requested_limit is None
    assert len(result.records) == 3
    assert result.next_cursor is None
    search_calls = [call for call in client.calls if call[0] == "search"]
    assert [call[1]["offset"] for call in search_calls] == [0, 2]
    assert all(
        call[1]["limit"] == reeves.DEFAULT_SEARCH_PAGE_SIZE
        for call in search_calls
    )
    assert [record["search_metadata"]["offset"] for record in result.records] == [
        0,
        0,
        2,
    ]
    assert logged[0][2] == 3


def test_shared_recorder_engine_uses_selected_tenant_identity(monkeypatch):
    tenant = reeves.RecorderTenant(
        key="pa-example",
        source_id="us-pa-example-recorder",
        name="Example County Recorder",
        authority="Example County Recorder",
        jurisdiction_name="Example County, Pennsylvania",
        county_geoid="42001",
        state_code="PA",
        department="RP",
        base_url="https://example.pa.publicsearch.us",
        official_linking_page="https://example.gov/recorder",
        coverage="Example County recorded instruments",
        probe_instrument_number="18-06481",
        probe_document_id=20798096,
    )
    client = FakeClient()
    args = reeves.build_parser().parse_args(
        ["search", "18-06481", "--limit", "1"]
    )
    monkeypatch.setattr(reeves, "log_search", lambda *_args: None)

    result = reeves.execute(args, client=client, tenant=tenant)

    record = result.to_dict()["records"][0]
    assert result.query.source.source_id == tenant.source_id
    assert result.query.jurisdiction.county_fips == tenant.county_geoid
    assert record["source_id"] == tenant.source_id
    assert record["canonical_ref"].startswith(
        "PROPERTY:us-pa-example-recorder/42001/"
    )
    assert record["source_url"] == (
        "https://example.pa.publicsearch.us/"
        "doc/20798096?department=RP"
    )
    assert record["official_linking_page"] == (
        "https://example.gov/recorder"
    )
    assert record["documents"][0]["source_url"] == record["source_url"]


def test_search_normalizes_transfer_parties_dates_and_native_locator(
    monkeypatch,
):
    client = FakeClient()
    args = reeves.build_parser().parse_args(
        ["search", "18-06481", "--limit", "1"]
    )

    result, logged = _execute(args, monkeypatch, client)

    assert result.status == ResultStatus.OK
    cursor = reeves._decode_search_cursor(result.next_cursor)
    assert cursor.offset == 1
    assert cursor.source_total_count == 4
    assert cursor.response_type == "@kofile/FETCH_DOCUMENTS_FULFILLED/v6"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-tx-reeves-county-clerk-official-records/"
        "48389/instrument/RP%3A20798096"
    )
    assert record["native_document_id"] == "RP:20798096"
    assert record["source_representation"] == "search_index"
    assert record["department_code"] == "RP"
    assert record["instrument_number"] == "18-06481"
    assert record["instrument_type"] == "ASSIGNMENT AND BILL OF SALE"
    assert record["instrument_type_code"] == "ABS1"
    assert record["instrument_type_label"] == "ASSIGNMENT AND BILL OF SALE"
    assert record["recording_date"] == "2018-04-19"
    assert record["execution_date"] == "2018-04-16"
    assert record["book_volume_page"] == "OPR/1576/664"
    assert record["grantors"] == [
        "THREE RIVERS ACQUISITION III LLC",
        "THREE RIVERS OPERATING CO III LLC",
    ]
    assert record["grantees"] == ["APR OPERATING LLC"]
    assert record["legal_descriptions"] == [
        {
            "description": "REMARKS: MULTIPLE PROPERTIES SEE INSTRUMENT",
            "native_type": "LegalDescription",
        }
    ]
    assert record["page_count"] == 36
    assert record["image_id"] == 19747017
    assert record["source_url"].endswith("/doc/20798096?department=RP")
    assert record["raw"]["signed_thumbnail_available"] is True
    serialized = json.dumps(record)
    assert "sig=" not in serialized
    assert "exp=" not in serialized
    assert logged[0][1:] == (reeves.SOURCE_ID, 1)
    assert client.calls[0][0] == "search"


def test_exact_document_preserves_code_when_detail_has_no_label(monkeypatch):
    client = FakeClient()
    args = reeves.build_parser().parse_args(
        ["document", str(reeves.PROBE_DOCUMENT_ID)]
    )

    result, _logged = _execute(args, monkeypatch, client)

    record = result.to_dict()["records"][0]
    assert record["source_representation"] == "document_detail"
    assert record["instrument_type"] == "ABS1"
    assert record["instrument_type_code"] == "ABS1"
    assert record["instrument_type_label"] is None
    assert record["raw"]["signed_page_url_count"] == 2
    assert record["raw"]["signed_thumbnail_url_count"] == 2
    serialized = json.dumps(record)
    assert "fixture-page-one" not in serialized
    assert "fixture-thumb-one" not in serialized


def test_non_real_property_departments_preserve_native_party_roles():
    ucc_tenant = replace(
        reeves.REEVES_TENANT,
        department="UCC",
        departments=("RP", "UCC"),
    )
    row = {
        **DOCUMENT_DETAIL,
        "department": "UCC",
        "parties": [
            {
                "name": "EXAMPLE DEBTOR LLC",
                "type": "DEBTOR",
                "partyTypeCode": "D",
                "isDirect": True,
            },
            {
                "name": "EXAMPLE BANK",
                "type": "SECURED PARTY",
                "partyTypeCode": "I",
                "isDirect": False,
            },
        ],
    }

    record = reeves.normalize_instrument(
        row,
        schema="fixture-ucc-schema",
        tenant=ucc_tenant,
    )

    assert record["department_code"] == "UCC"
    assert record["native_document_id"] == "UCC:20798096"
    assert [party["role"] for party in record["parties"]] == [
        "debtor",
        "secured_party",
    ]
    assert record["grantors"] == []
    assert record["grantees"] == []


def test_detail_department_mismatch_is_source_changed(monkeypatch):
    client = FakeClient()
    tenant = replace(
        reeves.REEVES_TENANT,
        department="UCC",
        departments=("RP", "UCC"),
    )
    args = reeves.build_parser().parse_args(
        ["document", str(reeves.PROBE_DOCUMENT_ID)]
    )
    monkeypatch.setattr(reeves, "log_search", lambda *_args: None)

    result = reeves.execute(args, client=client, tenant=tenant)

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "normalization_failed"
    assert "expected UCC, observed RP" in result.errors[0].message


def test_page_download_writes_selected_page_and_omits_signed_url(
    tmp_path,
    monkeypatch,
):
    client = FakeClient()
    destination = tmp_path / "instrument-page.png"
    args = reeves.build_parser().parse_args(
        [
            "page",
            str(reeves.PROBE_DOCUMENT_ID),
            "1",
            str(destination),
        ]
    )

    result, _logged = _execute(args, monkeypatch, client)

    assert destination.read_bytes() == b"\x89PNG\r\n\x1a\nfixture-page"
    payload = result.to_dict()
    record = payload["records"][0]
    artifact = record["documents"][0]
    assert artifact["source_locator"] == {
        "department_code": "RP",
        "doc_id": reeves.PROBE_DOCUMENT_ID,
        "page_number": 1,
    }
    assert artifact["source_url"].endswith(
        "/doc/20798096?department=RP"
    )
    assert record["page_download"]["signed_url_refreshed"] is True
    assert record["page_download"]["etag"] == '"fixture-page-etag"'
    assert payload["raw_artifact_refs"] == [str(destination.resolve())]
    serialized = json.dumps(payload)
    assert "ephemeral-page-token" not in serialized
    assert "sig=" not in serialized


def test_probe_verifies_tenant_search_and_exact_document(monkeypatch):
    client = FakeClient()
    args = reeves.build_parser().parse_args(["probe"])

    result, _logged = _execute(args, monkeypatch, client)

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["doc_id"] == reeves.PROBE_DOCUMENT_ID
    assert record["instrument_number"] == reeves.PROBE_INSTRUMENT_NUMBER
    assert record["instrument_type_label"] == "ASSIGNMENT AND BILL OF SALE"
    assert record["probe"]["tenant_id"] == "48389"
    assert "RP" in record["probe"]["department_codes"]
    serialized = json.dumps(record["probe"])
    assert "fixture-anonymous-token" not in serialized
    assert "203.0.113.10" not in serialized
    assert [call[0] for call in client.calls] == [
        "bootstrap",
        "search",
        "document",
    ]


def test_probe_rejects_nonunique_total_even_when_one_row_is_returned(
    monkeypatch,
):
    client = FakeClient()

    def nonunique_search(**kwargs):
        return KofileSearchPage(
            records=(SEARCH_RECORD,),
            total_count=2,
            statistics={},
            offset=0,
            limit=1,
            next_offset=1,
            response_type="@kofile/FETCH_DOCUMENTS_FULFILLED/v6",
        )

    monkeypatch.setattr(client, "search", nonunique_search)
    args = reeves.build_parser().parse_args(["probe"])
    result, _logged = _execute(args, monkeypatch, client)

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "probe_record_missing"
    assert result.errors[0].details["source_total_count"] == 2


def test_probe_not_found_is_source_changed_not_empty_success(monkeypatch):
    client = FakeClient()
    client.error = KofileNotFoundError(
        "fixture sentinel missing",
        code="source_document_not_found",
        retryable=False,
    )
    args = reeves.build_parser().parse_args(["probe"])
    result, _logged = _execute(args, monkeypatch, client)

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "probe_record_missing"


def test_search_selection_supports_date_only_and_ocr_text_date_range():
    date_only = reeves.build_parser().parse_args(
        [
            "search",
            "--date-from",
            "2018-01-01",
            "--date-to",
            "2018-12-31",
        ]
    )
    ocr_text = reeves.build_parser().parse_args(
        [
            "search",
            "gathering agreement",
            "--ocr",
            "--date-from",
            "2017-01-01",
            "--date-to",
            "2017-12-31",
        ]
    )

    assert reeves._search_selection(date_only) == (
        None,
        "20180101,20181231",
    )
    assert reeves._search_selection(ocr_text) == (
        "gathering agreement",
        "20170101,20171231",
    )


def test_incomplete_date_range_returns_explicit_query_failure(monkeypatch):
    client = FakeClient()
    args = reeves.build_parser().parse_args(
        ["search", "--date-from", "2018-01-01"]
    )

    result, _logged = _execute(args, monkeypatch, client)

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "incomplete_date_range"
    assert client.calls == []


class FlakySourceClient:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def fetch_document(self, doc_id):
        self.calls += 1
        if self.calls == 1:
            raise KofileUnavailableError(
                "temporary websocket failure",
                code="websocket_transport_error",
                retryable=True,
            )
        return DOCUMENT_DETAIL

    def close(self):
        self.closed = True


def test_client_retries_only_retryable_source_failures():
    source = FlakySourceClient()
    sleeps = []
    clock_values = iter([0.0, 0.0, 1.0, 1.0])
    client = reeves.ReevesRecordsClient(
        source_client=source,
        minimum_interval=0,
        max_attempts=2,
        retry_backoff=0.5,
        sleep=sleeps.append,
        monotonic=lambda: next(clock_values),
    )

    assert client.fetch_document(reeves.PROBE_DOCUMENT_ID) == DOCUMENT_DETAIL
    assert source.calls == 2
    assert sleeps == [0.5]


def test_rate_limit_is_not_reported_as_no_results(monkeypatch):
    client = FakeClient()
    client.error = KofileRateLimitError(
        "slow down",
        code="source_rate_limited",
        retryable=True,
    )
    args = reeves.build_parser().parse_args(["search", "THREE RIVERS"])

    result, logged = _execute(args, monkeypatch, client)

    assert result.status == ResultStatus.RATE_LIMITED
    assert result.errors[0].code == "source_rate_limited"
    assert logged[0][2] is None


def test_existing_page_destination_requires_explicit_overwrite(
    tmp_path,
    monkeypatch,
):
    client = FakeClient()
    destination = tmp_path / "existing.png"
    destination.write_bytes(b"existing")
    args = reeves.build_parser().parse_args(
        [
            "page",
            str(reeves.PROBE_DOCUMENT_ID),
            "1",
            str(destination),
        ]
    )

    result, _logged = _execute(args, monkeypatch, client)

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "page_write_failed"
    assert destination.read_bytes() == b"existing"


@pytest.mark.parametrize("limit", ["0", "-1"])
def test_main_parser_rejects_nonpositive_limit(limit):
    args = reeves.build_parser().parse_args(
        ["search", "THREE RIVERS", "--limit", limit]
    )
    assert args.limit <= 0
