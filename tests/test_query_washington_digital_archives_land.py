from __future__ import annotations

import base64
import json
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_washington_digital_archives_land as adapter
from tools.public_records_contract import PublicRecordsResult, ResultStatus
from tools.public_records_http import RetryPolicy, SourceSchemaError, TransportError


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "washington_digital_archives_land"
)


def _fixture(name: str) -> str:
    return (FIXTURE_ROOT / f"{name}.html").read_text(encoding="utf-8")


def _args(command: str, **overrides: Any) -> Namespace:
    values = {
        "command": command,
        "county": "adams",
        "refresh": False,
        "details": False,
        "max_titles": None,
        "last_name": "SMITH",
        "first_name": None,
        "middle_name": None,
        "party_role": None,
        "addition": None,
        "start_year": 2020,
        "end_year": 2020,
        "soundex": False,
        "limit": None,
        "cursor": None,
        "page_size": 50,
        "sort": None,
        "direction": None,
        "record_id": "64742C2528B8C19D43FCC54D20DC97D0",
        "operations": "inventory,title,search,detail",
        "all_titles": False,
        "timeout": 30.0,
        "minimum_interval": 0.0,
        "retry_attempts": 1,
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return Namespace(**values)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "log_search", lambda *_args, **_kwargs: None)


class FakeResponse:
    def __init__(
        self,
        text: str,
        url: str,
        *,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        self.requests.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "data": dict(data or {}),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("fake response queue exhausted")
        return self.responses.pop(0)


def _result_record(index: int) -> dict[str, Any]:
    record_id = f"{index:032X}"
    return {
        "stable_id": f"WSDA:LAND:RESULT:{index}",
        "record_kind": "recorded_land_search_result",
        "native_record_id": record_id,
        "record_url": f"{adapter.BASE_URL}/Record/View/{record_id}",
        "native_row_index": index,
        "last_name": "SMITH",
        "first_name": f"PERSON {index}",
        "party_type": "Buyer",
        "document_type": "Deed",
        "year": 2020,
        "county": "Adams",
        "legal_description": f"LOT {index}",
        "image_exists": True,
        "image_state": "available",
        "evidence_lineage": adapter.EVIDENCE_LINEAGE,
        "provenance": {
            "source_id": adapter.SOURCE_ID,
            "source_url": f"{adapter.BASE_URL}/Search/ResultsTable/",
            "native_record_id": record_id,
        },
    }


def _page(
    page: int,
    records: list[dict[str, Any]],
    *,
    total: int,
    pages: int,
    schema_fingerprint: str = "a" * 64,
) -> adapter.ResultPage:
    first = (
        int(records[0]["native_row_index"])
        if records
        else None
    )
    last = first + len(records) - 1 if first is not None else None
    return adapter.ResultPage(
        records=tuple(records),
        total_count=total,
        page=page,
        page_count=pages,
        page_size=50,
        first_record=first,
        last_record=last,
        source_url=f"{adapter.BASE_URL}/Search/ResultsTable/?page={page}",
        retrieved_at="2026-07-30T00:00:00Z",
        schema_fingerprint=schema_fingerprint,
    )


class FakeClient:
    def __init__(
        self,
        *,
        pages: Mapping[int, adapter.ResultPage] | None = None,
    ) -> None:
        self.pages = dict(pages or {})
        self.search_payloads: list[dict[str, Any]] = []
        self.result_calls: list[dict[str, Any]] = []
        self.title_calls: list[int] = []
        self.detail_calls: list[str] = []

    def fetch_title_list(self) -> list[dict[str, Any]]:
        return adapter.parse_title_list(
            _fixture("title_list"),
            source_url=f"{adapter.BASE_URL}{adapter.TITLE_LIST_PATH}",
            retrieved_at="2026-07-30T00:00:00Z",
        )

    def fetch_title(self, title_id: int) -> dict[str, Any]:
        self.title_calls.append(title_id)
        return adapter.parse_title_detail(
            _fixture("title_93"),
            source_url=f"{adapter.BASE_URL}/Collections/TitleInfo/{title_id}",
            retrieved_at="2026-07-30T00:00:00Z",
        )

    def start_search(self, payload: Mapping[str, Any]) -> adapter.SearchHandle:
        self.search_payloads.append(dict(payload))
        return adapter.SearchHandle(
            search_id=1,
            source_url=f"{adapter.BASE_URL}/Collections/Search",
            retrieved_at="2026-07-30T00:00:00Z",
        )

    def fetch_results(
        self,
        search_id: int,
        *,
        page: int,
        page_size: int,
        sort_column: int = -1,
        direction: str = "null",
    ) -> adapter.ResultPage:
        self.result_calls.append(
            {
                "search_id": search_id,
                "page": page,
                "page_size": page_size,
                "sort_column": sort_column,
                "direction": direction,
            }
        )
        return self.pages[page]

    def fetch_detail(self, record_id: str) -> dict[str, Any]:
        self.detail_calls.append(record_id)
        return adapter.parse_record_detail(
            _fixture("record_detail"),
            record_id=record_id,
            source_url=f"{adapter.BASE_URL}/Record/View/{record_id}",
            retrieved_at="2026-07-30T00:00:00Z",
        )


def test_static_inventory_preserves_verified_family_totals() -> None:
    payload = adapter.execute(_args("sources"), log_results=False)

    assert payload["title_count"] == 26
    assert payload["covered_county_count"] == 26
    assert payload["record_count"] == 32_692_605
    assert payload["some_image_title_count"] == 18
    assert payload["image_unavailable_title_count"] == 8
    assert payload["county_gap_count"] == 13
    assert len(payload["titles"]) == 26


def test_static_inventory_preserves_title_identity_and_archive_lineage() -> None:
    adams = adapter.TITLES_BY_KEY["adams"].to_record()
    snohomish = adapter.TITLES_BY_KEY["snohomish"].to_record()
    skamania = adapter.TITLES_BY_KEY["skamania"].to_record()

    assert adams["stable_id"] == "WSDA:LAND:TITLE:93"
    assert adams["record_count"] == 89823
    assert adams["image_availability"] == "some_images"
    assert snohomish["coverage_label"] is None
    assert skamania["coverage_label"] == "2008-2013; 2016-Present"
    assert adams["evidence_lineage"] == adapter.EVIDENCE_LINEAGE
    assert "assessor" in adams["related_property_lineage"]


def test_all_archive_gaps_have_useful_recorder_operations() -> None:
    expected = {
        "asotin",
        "columbia",
        "douglas",
        "ferry",
        "garfield",
        "grant",
        "king",
        "kittitas",
        "lincoln",
        "san_juan",
        "skagit",
        "stevens",
        "wahkiakum",
    }

    assert set(adapter.ALTERNATIVES_BY_KEY) == expected
    for alternative in adapter.RECORDER_ALTERNATIVES:
        record = alternative.to_record()
        assert record["authority"]
        assert record["landing_url"].startswith("http")
        assert record["operations"]
        assert record["evidence_lineage"] == "county_auditor_recorded_instrument"
        for complement in record["complementary_sources"]:
            if complement["kind"] == "assessor_parcel_search":
                assert "separate" in complement["relationship"]


def test_gap_operations_preserve_observed_web_and_non_web_paths() -> None:
    douglas = adapter.ALTERNATIVES_BY_KEY["douglas"].to_record()
    ferry = adapter.ALTERNATIVES_BY_KEY["ferry"].to_record()
    wahkiakum = adapter.ALTERNATIVES_BY_KEY["wahkiakum"].to_record()

    assert "document_type_search" in douglas["operations"]
    assert "parcel_search" in douglas["operations"]
    assert ferry["operations"] == [
        "record_search_request",
        "recorded_document_copy_request",
    ]
    assert wahkiakum["operation_url"] is None
    assert "onsite_record_index_search" in wahkiakum["operations"]
    assert wahkiakum["observed_access_state"] == "county_page_live_no_online_search"


def test_source_metadata_models_transport_not_access_policy() -> None:
    source = adapter._source_metadata().to_dict()
    metadata = source["metadata"]

    assert metadata["transport"]["native_page_sizes"] == [50, 100, 200]
    assert metadata["transport"]["page_numbering"] == "one_based"
    assert metadata["transport"]["adapter_minimum_interval_seconds"] == 0.25
    assert metadata["observed_access"]["search_and_results"] == (
        "open_session_without_login"
    )
    assert metadata["observed_access"]["document_generation"]["state"] == (
        "site_recaptcha_queue"
    )
    assert "access_policy" not in metadata


def test_parse_title_list_preserves_known_and_new_title_ids() -> None:
    records = adapter.parse_title_list(
        _fixture("title_list"),
        source_url=f"{adapter.BASE_URL}{adapter.TITLE_LIST_PATH}",
        retrieved_at="2026-07-30T00:00:00Z",
    )

    assert [record["title_id"] for record in records] == [93, 1241, 9999]
    assert records[0]["county_key"] == "adams"
    assert records[0]["label_matches_inventory"] is True
    assert records[2]["county"] == "Example County"
    assert records[2]["known_inventory_title"] is False
    assert records[2]["stable_id"] == "WSDA:LAND:TITLE:9999"


def test_parse_title_list_rejects_unrecognized_source_shape() -> None:
    with pytest.raises(SourceSchemaError):
        adapter.parse_title_list(
            "<html><body>No titles</body></html>",
            source_url=f"{adapter.BASE_URL}{adapter.TITLE_LIST_PATH}",
        )


def test_parse_title_detail_preserves_search_and_instrument_metadata() -> None:
    record = adapter.parse_title_detail(
        _fixture("title_93"),
        source_url=f"{adapter.BASE_URL}/Collections/TitleInfo/93",
        retrieved_at="2026-07-30T00:00:00Z",
    )

    assert record["title_id"] == 93
    assert record["county_key"] == "adams"
    assert record["record_creator"] == "Adams County Government, Auditor"
    assert record["record_count"] == 89823
    assert record["image_availability"] == "some_images"
    assert "Deed Of Trust" in record["document_types_text"]
    assert record["instrument_vocabulary"]["representation"] == "source_text"
    assert record["search_operation"]["party_roles"] == ["Grantor", "Grantee"]
    assert record["search_operation"]["supports_browse"] is True
    assert {
        "LastName",
        "FirstName",
        "MiddleName",
        "PartyType",
        "Keywords",
        "StartYear",
        "EndYear",
        "UseSoundex",
    } <= set(record["search_operation"]["input_names"])


def test_parse_results_preserves_party_rows_stable_record_ids_and_images() -> None:
    page = adapter.parse_results_page(
        _fixture("results_page"),
        source_url=f"{adapter.BASE_URL}/Search/ResultsTable/?id=1&page=1",
        requested_page_size=50,
        retrieved_at="2026-07-30T00:00:00Z",
    )

    assert page.total_count == 3
    assert page.page == 1
    assert page.page_count == 1
    assert page.page_size == 50
    assert len(page.records) == 3
    assert page.records[0]["native_record_id"] == (
        "64742C2528B8C19D43FCC54D20DC97D0"
    )
    assert page.records[1]["native_record_id"] == (
        "64742C2528B8C19D43FCC54D20DC97D0"
    )
    assert (
        page.records[0]["ordinal_occurrence_key"]
        != page.records[1]["ordinal_occurrence_key"]
    )
    assert [record["native_result_ordinal"] for record in page.records] == [
        1,
        2,
        3,
    ]
    assert page.records[0]["party_type"] == "Borrower"
    assert page.records[0]["document_type"] == "Assignment Of Deed Of Trust"
    assert page.records[0]["image_exists"] is True
    assert page.records[2]["image_exists"] is False
    assert len(page.schema_fingerprint) == 64


def test_parse_results_preserves_exact_duplicate_native_occurrences() -> None:
    html = _fixture("results_page").replace(
        ">CRISTIANNE<",
        ">AMOS<",
    )

    page = adapter.parse_results_page(
        html,
        source_url=f"{adapter.BASE_URL}/Search/ResultsTable/?id=1&page=1",
        requested_page_size=50,
        retrieved_at="2026-07-30T00:00:00Z",
    )

    first, second = page.records[:2]
    assert adapter._indexed_party_identity(first) == (
        adapter._indexed_party_identity(second)
    )
    assert first["indexed_party_key"] == second["indexed_party_key"]
    assert first["native_result_ordinal"] == 1
    assert second["native_result_ordinal"] == 2
    assert first["ordinal_occurrence_key"] != second["ordinal_occurrence_key"]


def test_parse_authoritative_no_results_is_not_a_source_failure() -> None:
    page = adapter.parse_results_page(
        _fixture("no_results"),
        source_url=f"{adapter.BASE_URL}/Search/ResultsTable/?id=2&page=1",
        requested_page_size=50,
        retrieved_at="2026-07-30T00:00:00Z",
    )

    assert page.records == ()
    assert page.total_count == 0
    assert page.page_count == 0
    assert page.first_record is None


def test_parse_results_rejects_changed_columns() -> None:
    html = _fixture("results_page").replace("<th>Doc Type</th>", "<th>Instrument</th>")

    with pytest.raises(SourceSchemaError):
        adapter.parse_results_page(
            html,
            source_url=f"{adapter.BASE_URL}/Search/ResultsTable/",
            requested_page_size=50,
        )


def test_parse_record_detail_preserves_parties_legal_fields_and_object_state() -> None:
    record_id = "64742C2528B8C19D43FCC54D20DC97D0"
    record = adapter.parse_record_detail(
        _fixture("record_detail"),
        record_id=record_id,
        source_url=f"{adapter.BASE_URL}/Record/View/{record_id}",
        retrieved_at="2026-07-30T00:00:00Z",
    )

    assert record["stable_id"] == f"WSDA:LAND:RECORD:{record_id}"
    assert record["reference_number"] == "324744"
    assert record["recording_date"] == "06/19/2020"
    assert record["document_type"] == "Assignment Of Deed Of Trust"
    assert record["number_pages"] == 2
    assert record["related_document_number"] == "303526"
    assert record["document_id"] == "DOC201S934"
    assert len(record["parties"]) == 4
    assert record["parties"][1] == {
        "sequence_no": 2,
        "party_type": "Borrower",
        "first_name": "AMOS",
        "last_name": "SMITH",
    }
    assert record["legal"]["parcel"] == ";1-935-23-055-0101;"
    assert record["image_availability"] == "available"
    assert record["digital_objects"][0]["native_digital_object_id"] == (
        "910A2CA838DCC45F1AC4363BBCF36D5B"
    )
    assert record["document_delivery"]["state"] == "site_recaptcha_queue"
    assert record["document_delivery"]["direct_download_url"] is None
    assert record["source_of_transfer"] == (
        "Adams County Auditor Recording Department"
    )
    assert record["provenance"]["native_record_id"] == record_id


def test_parse_record_detail_distinguishes_unlisted_document_object() -> None:
    html = _fixture("record_detail").replace(
        (
            '<div\n        class="document-download"\n        data-download\n'
            '        data-format="PDF"\n'
            '        data-id="910A2CA838DCC45F1AC4363BBCF36D5B"\n'
            "      ></div>"
        ),
        "",
    )
    record = adapter.parse_record_detail(
        html,
        record_id="64742C2528B8C19D43FCC54D20DC97D0",
        source_url=(
            f"{adapter.BASE_URL}/Record/View/"
            "64742C2528B8C19D43FCC54D20DC97D0"
        ),
    )

    assert record["digital_objects"] == []
    assert record["image_availability"] == "not_listed_on_detail"
    assert record["document_delivery"]["state"] == "no_object_listed"


@pytest.mark.parametrize(
    ("html", "source_record_id", "message"),
    [
        (
            _fixture("record_detail"),
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "response URL",
        ),
        (
            _fixture("record_detail").replace(
                "/Record/View/64742C2528B8C19D43FCC54D20DC97D0",
                "/Record/View/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            ),
            "64742C2528B8C19D43FCC54D20DC97D0",
            "source path",
        ),
        (
            _fixture("record_detail").replace(
                ">Land Records<",
                ">Marriage Records<",
            ),
            "64742C2528B8C19D43FCC54D20DC97D0",
            "recorded-land record series",
        ),
        (
            _fixture("record_detail").replace(
                "<td>Adams</td>",
                "<td>Benton</td>",
            ),
            "64742C2528B8C19D43FCC54D20DC97D0",
            "county did not match",
        ),
    ],
)
def test_parse_record_detail_rejects_identity_drift(
    html: str,
    source_record_id: str,
    message: str,
) -> None:
    requested_record_id = "64742C2528B8C19D43FCC54D20DC97D0"

    with pytest.raises(SourceSchemaError, match=message):
        adapter.parse_record_detail(
            html,
            record_id=requested_record_id,
            source_url=(
                f"{adapter.BASE_URL}/Record/View/{source_record_id}"
            ),
        )


def test_native_search_payload_maps_archive_field_names_exactly() -> None:
    payload = adapter.build_search_payload(
        adapter.TITLES_BY_KEY["adams"],
        search_type="DetailedSearch",
        last_name="SMITH",
        first_name="AMOS",
        middle_name="J",
        party_role="grantor",
        addition="GREENE",
        start_year=2019,
        end_year=2020,
        soundex=True,
    )

    assert payload == {
        "RecordSeriesID": 14,
        "TitleID": 93,
        "SearchType": "DetailedSearch",
        "LastName": "SMITH",
        "FirstName": "AMOS",
        "MiddleName": "J",
        "PartyType": "Grantor",
        "Keywords": "GREENE",
        "StartYear": "2019",
        "EndYear": "2020",
        "UseSoundex": "true",
    }


def test_browse_payload_uses_native_browse_operation() -> None:
    payload = adapter.build_search_payload(
        adapter.TITLES_BY_KEY["skamania"],
        search_type="Browse",
    )

    assert payload["RecordSeriesID"] == 14
    assert payload["TitleID"] == 1188
    assert payload["SearchType"] == "Browse"
    assert payload["LastName"] == ""


def test_cursor_is_query_bound_and_preserves_native_row_offset() -> None:
    cursor = adapter.encode_cursor(
        fingerprint="f" * 64,
        page=2,
        row_offset=17,
        native_total_count=123,
        schema_fingerprint="a" * 64,
        page_fingerprint="b" * 64,
    )

    state = adapter.decode_cursor(
        cursor,
        expected_fingerprint="f" * 64,
    )
    assert state == adapter.CursorState(
        page=2,
        row_offset=17,
        native_total_count=123,
        schema_fingerprint="a" * 64,
        page_fingerprint="b" * 64,
    )
    with pytest.raises(ValueError, match="does not match"):
        adapter.decode_cursor(cursor, expected_fingerprint="0" * 64)


def test_cursor_rejects_mutated_position_with_stale_checksum() -> None:
    cursor = adapter.encode_cursor(
        fingerprint="f" * 64,
        page=2,
        row_offset=17,
        native_total_count=123,
        schema_fingerprint="a" * 64,
        page_fingerprint="b" * 64,
    )
    encoded = cursor.removeprefix(adapter.CURSOR_PREFIX)
    payload = json.loads(
        base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
    )
    payload["row_offset"] = 18
    tampered = adapter.CURSOR_PREFIX + (
        base64.urlsafe_b64encode(
            adapter.canonical_json(payload).encode()
        )
        .decode()
        .rstrip("=")
    )

    with pytest.raises(ValueError, match="checksum is invalid"):
        adapter.decode_cursor(
            tampered,
            expected_fingerprint="f" * 64,
        )


def test_http_client_preserves_session_search_id_and_native_paging_params() -> None:
    session = FakeSession(
        [
            FakeResponse(
                json.dumps({"Result": True, "Status": "success", "Redirect": 7}),
                f"{adapter.BASE_URL}/Collections/Search",
            ),
            FakeResponse(
                _fixture("results_page"),
                f"{adapter.BASE_URL}/Search/ResultsTable/?id=7&page=1",
            ),
        ]
    )
    client = adapter.DigitalArchivesClient(
        session=session,
        timeout=12,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )
    payload = adapter.build_search_payload(
        adapter.TITLES_BY_KEY["adams"],
        search_type="DetailedSearch",
        last_name="SMITH",
        start_year=2020,
        end_year=2020,
    )

    handle = client.start_search(payload)
    page = client.fetch_results(
        handle.search_id,
        page=1,
        page_size=100,
        sort_column=3,
        direction="ASC",
    )

    assert handle.search_id == 7
    assert page.total_count == 3
    assert session.requests[0]["method"] == "POST"
    assert session.requests[0]["data"]["TitleID"] == 93
    assert session.requests[1]["method"] == "GET"
    assert session.requests[1]["params"] == {
        "id": 7,
        "sortColumn": 3,
        "direction": "ASC",
        "pageSize": 100,
        "page": 1,
    }
    assert session.headers["User-Agent"] == adapter.DEFAULT_USER_AGENT


def test_http_client_retries_transient_status_with_bounded_policy() -> None:
    session = FakeSession(
        [
            FakeResponse("busy", f"{adapter.BASE_URL}/Collections/TitleInfo/93", status_code=503),
            FakeResponse(
                _fixture("title_93"),
                f"{adapter.BASE_URL}/Collections/TitleInfo/93",
            ),
        ]
    )
    client = adapter.DigitalArchivesClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
            max_backoff=0,
        ),
    )

    record = client.fetch_title(93)

    assert record["title_id"] == 93
    assert len(session.requests) == 2


def test_http_client_rejects_search_response_without_redirect_id() -> None:
    session = FakeSession(
        [
            FakeResponse(
                json.dumps({"Result": False, "Status": "validation"}),
                f"{adapter.BASE_URL}/Collections/Search",
            )
        ]
    )
    client = adapter.DigitalArchivesClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(SourceSchemaError):
        client.start_search({"RecordSeriesID": 14, "TitleID": 93})


def test_execute_metadata_static_and_live_instrument_vocabulary() -> None:
    client = FakeClient()
    static = adapter.execute(
        _args("metadata", refresh=False),
        client=client,
        log_results=False,
    )
    instruments = adapter.execute(
        _args("instruments"),
        client=client,
        log_results=False,
    )

    assert isinstance(static, PublicRecordsResult)
    assert static.status == ResultStatus.OK
    assert static.records[0]["title_id"] == 93
    assert client.title_calls == [93]
    assert instruments.status == ResultStatus.OK
    assert instruments.records[0]["record_kind"] == (
        "recorded_land_instrument_vocabulary"
    )
    assert "Statutory Warranty Deed" in (
        instruments.records[0]["document_types_text"]
    )


def test_execute_search_cursor_restarts_session_and_resumes_inside_page() -> None:
    pages = {
        1: _page(1, [_result_record(i) for i in range(1, 5)], total=6, pages=2),
        2: _page(2, [_result_record(i) for i in range(5, 7)], total=6, pages=2),
    }
    first_client = FakeClient(pages=pages)
    first = adapter.execute(
        _args("search", limit=3),
        client=first_client,
        log_results=False,
    )

    assert first.status == ResultStatus.OK
    assert [record["native_record_id"] for record in first.records] == [
        f"{index:032X}" for index in range(1, 4)
    ]
    assert first.next_cursor
    assert first_client.result_calls == [
        {
            "search_id": 1,
            "page": 1,
            "page_size": 50,
            "sort_column": -1,
            "direction": "null",
        }
    ]

    second_client = FakeClient(pages=pages)
    second = adapter.execute(
        _args("search", limit=3, cursor=first.next_cursor),
        client=second_client,
        log_results=False,
    )

    assert second.status == ResultStatus.OK
    assert [record["native_record_id"] for record in second.records] == [
        f"{index:032X}" for index in range(4, 7)
    ]
    assert second.next_cursor is None
    assert len(second_client.search_payloads) == 1
    assert [call["page"] for call in second_client.result_calls] == [1, 2]
    assert second.query.query.metadata["transport"][
        "search_session_recreated_for_cursor"
    ] is True
    full = adapter.execute(
        _args("search"),
        client=FakeClient(pages=pages),
        log_results=False,
    )
    resumed_records = [*first.records, *second.records]
    assert all(
        record["stable_id"] == record["source_occurrence_id"]
        == record["query_occurrence_id"]
        for record in resumed_records
    )
    assert [
        record["source_occurrence_id"] for record in resumed_records
    ] == [record["source_occurrence_id"] for record in full.records]
    assert [
        record["query_occurrence_id"] for record in resumed_records
    ] == [record["query_occurrence_id"] for record in full.records]
    assert [
        record["native_result_ordinal"] for record in resumed_records
    ] == list(range(1, 7))


def test_execute_search_primary_occurrence_identity_is_query_bound() -> None:
    page = _page(
        1,
        [_result_record(1), _result_record(1)],
        total=2,
        pages=1,
    )
    smith = adapter.execute(
        _args("search", last_name="SMITH"),
        client=FakeClient(pages={1: page}),
        log_results=False,
    )
    jones = adapter.execute(
        _args("search", last_name="JONES"),
        client=FakeClient(pages={1: page}),
        log_results=False,
    )

    assert (
        smith.records[0]["indexed_party_key"]
        == smith.records[1]["indexed_party_key"]
    )
    assert (
        smith.records[0]["source_occurrence_id"]
        != smith.records[1]["source_occurrence_id"]
    )
    assert {
        record["stable_id"] for record in smith.records
    }.isdisjoint({record["stable_id"] for record in jones.records})


@pytest.mark.parametrize("drift", ["total", "schema", "page_rows"])
def test_execute_search_cursor_rejects_native_snapshot_drift(
    drift: str,
) -> None:
    original_page = _page(
        1,
        [_result_record(i) for i in range(1, 5)],
        total=6,
        pages=2,
    )
    first = adapter.execute(
        _args("search", limit=3),
        client=FakeClient(pages={1: original_page}),
        log_results=False,
    )
    assert first.next_cursor

    changed_records = [_result_record(i) for i in range(1, 5)]
    changed_total = 6
    changed_schema = "a" * 64
    if drift == "total":
        changed_total = 7
    elif drift == "schema":
        changed_schema = "b" * 64
    else:
        changed_records[2] = _result_record(99)
    changed_page = _page(
        1,
        changed_records,
        total=changed_total,
        pages=2,
        schema_fingerprint=changed_schema,
    )

    resumed = adapter.execute(
        _args("search", limit=3, cursor=first.next_cursor),
        client=FakeClient(pages={1: changed_page}),
        log_results=False,
    )

    assert resumed.status == ResultStatus.SOURCE_CHANGED
    assert resumed.records == ()
    assert resumed.errors[0].code == "source_schema_changed"
    assert "snapshot changed" in resumed.errors[0].message


def test_execute_search_exhausts_native_pages_when_limit_is_omitted() -> None:
    pages = {
        1: _page(1, [_result_record(i) for i in range(1, 5)], total=6, pages=2),
        2: _page(2, [_result_record(i) for i in range(5, 7)], total=6, pages=2),
    }
    client = FakeClient(pages=pages)
    result = adapter.execute(
        _args("search"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == 6
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    assert [call["page"] for call in client.result_calls] == [1, 2]


def test_execute_search_preserves_native_sort_and_party_role() -> None:
    client = FakeClient(
        pages={1: _page(1, [_result_record(1)], total=1, pages=1)}
    )
    result = adapter.execute(
        _args(
            "search",
            limit=1,
            party_role="grantee",
            sort="document_type",
            direction="desc",
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert client.search_payloads[0]["PartyType"] == "Grantee"
    assert client.result_calls[0]["sort_column"] == 3
    assert client.result_calls[0]["direction"] == "DESC"


def test_execute_no_results_is_authoritative_empty_contract() -> None:
    client = FakeClient(pages={1: _page(1, [], total=0, pages=0)})
    result = adapter.execute(
        _args("search"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_execute_transport_failure_is_not_reported_as_no_results() -> None:
    class FailingClient(FakeClient):
        def start_search(self, payload: Mapping[str, Any]) -> adapter.SearchHandle:
            raise TransportError("fixture transport failure", url=adapter.BASE_URL)

    result = adapter.execute(
        _args("search"),
        client=FailingClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "transport_error"
    assert result.status != ResultStatus.NO_RESULTS


def test_execute_detail_returns_archive_record_and_provenance() -> None:
    client = FakeClient()
    result = adapter.execute(
        _args("detail"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records[0]["native_record_id"] == (
        "64742C2528B8C19D43FCC54D20DC97D0"
    )
    assert result.records[0]["title_id"] == 93
    assert result.records[0]["provenance"]["source_id"] == adapter.SOURCE_ID
    assert client.detail_calls == ["64742C2528B8C19D43FCC54D20DC97D0"]
    assert result.query.jurisdiction.jurisdiction_id == "53001"
    assert result.query.jurisdiction.locality == "Adams County"


def test_refresh_inventory_reports_known_new_and_missing_titles() -> None:
    payload = adapter.execute(
        _args("inventory", refresh=True),
        client=FakeClient(),
        log_results=False,
    )

    assert payload["status"] == "ok"
    assert payload["discovered_title_count"] == 3
    assert payload["expected_title_count"] == 26
    assert payload["new_title_ids"] == [9999]
    assert 4 in payload["missing_verified_title_ids"]
    assert payload["title_label_change_count"] == 0
    assert len(payload["county_gaps"]) == 13


def test_probe_runs_bounded_inventory_title_search_and_detail_components() -> None:
    client = FakeClient(
        pages={1: _page(1, [_result_record(1)], total=1, pages=1)}
    )
    payload = adapter.execute(
        _args("probe"),
        client=client,
        log_results=False,
    )

    assert payload["status"] == "ok"
    assert [component["operation"] for component in payload["components"]] == [
        "inventory",
        "title",
        "search",
        "detail",
    ]
    assert all(
        component["status"] == "ok" for component in payload["components"]
    )


def test_parser_exposes_source_specific_commands_and_native_page_sizes() -> None:
    parser = adapter.build_parser()
    search = parser.parse_args(
        [
            "search",
            "--county",
            "adams",
            "--last-name",
            "SMITH",
            "--page-size",
            "200",
            "--sort",
            "year",
            "--direction",
            "asc",
        ]
    )
    alternative = parser.parse_args(
        ["alternatives", "--county", "wahkiakum"]
    )

    assert search.page_size == 200
    assert search.limit is None
    assert search.sort == "year"
    assert search.direction == "asc"
    assert alternative.county == "wahkiakum"
