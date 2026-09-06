from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_harris_recorder as recorder


FIXTURE_DIR = Path("tests/fixtures/public_records/harris_recorder")
SEARCH_FORM = (FIXTURE_DIR / "search-form.html").read_text(encoding="utf-8")
EXACT_RESULT = (FIXTURE_DIR / "exact-result.html").read_text(encoding="utf-8")
NO_RESULTS = (FIXTURE_DIR / "no-results.html").read_text(encoding="utf-8")
FORM_ERROR = (FIXTURE_DIR / "form-error.html").read_text(encoding="utf-8")
SOURCE_DRIFT = (FIXTURE_DIR / "source-drift.html").read_text(encoding="utf-8")
RESULT_URL = (
    "https://www.cclerk.hctx.net/Applications/WebSearch/"
    "RP_R.aspx?ID=fixture%2Bresult%3D"
)


@dataclass
class FixtureResponse:
    text: str
    status_code: int = 200
    url: str = recorder.SEARCH_URL
    headers: dict[str, str] = field(default_factory=dict)


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
        data=None,
        timeout=None,
        allow_redirects=None,
    ):
        self.calls.append({
            "method": method,
            "url": url,
            "data": dict(data or {}),
            "timeout": timeout,
            "allow_redirects": allow_redirects,
        })
        if not self.responses:
            raise AssertionError("unexpected Harris recorder request")
        return self.responses.pop(0)


def fixture_client(session):
    return recorder.HarrisRecorderClient(
        session,
        request_delay=0,
        max_retries=0,
    )


def test_parse_exact_result_preserves_instrument_parties_and_legal_fields():
    payload = recorder.parse_results(
        EXACT_RESULT,
        RESULT_URL,
        selectors={"file_number": recorder.SENTINEL_FILE_NUMBER},
    )

    assert payload["status"] == "ok"
    assert payload["source"] == recorder.SOURCE_ID
    assert payload["query"] == {
        "file_number": recorder.SENTINEL_FILE_NUMBER
    }
    assert payload["coverage"] == {
        "source_rows_returned": 1,
        "source_reported_total_results": None,
        "observed_result_ceiling": 200,
        "ceiling_status": "observed_not_published",
        "possible_source_ceiling_reached": False,
        "completeness": "single_source_result_page_no_published_total",
    }

    record = payload["results"][0]
    assert record["canonical_ref"] == (
        "PROPERTY:us-tx-harris-clerk-real-property/48201/"
        "instrument/RP-2026-72194"
    )
    assert record["evidence_ref"] == record["canonical_ref"]
    assert record["record_kind"] == "recorded_instrument"
    assert record["record_scope"] == "instrument_index_metadata"
    assert record["recording_date"] == "2026-02-26"
    assert record["recording_date_raw"] == "02/26/2026"
    assert record["file_date"] == "2026-02-26"
    assert record["file_date_raw"] == "02/26/2026"
    assert record["instrument_type"] == "W/D"
    assert record["instrument_type_code"] == "W/D"
    assert record["book"] is None
    assert record["page_count"] == 4
    assert record["document_locator"] == "RP-2026-72194"
    assert record["grantors"] == [
        "MARTINEZ CHRIS",
        "MARTINEZ ESPERANZA",
    ]
    assert record["grantees"] == ["HOME LIQUIDATORS 2 LLC"]
    assert record["parties"][0] == {
        "name": "MARTINEZ CHRIS",
        "role": "grantor",
        "raw_role": "Grantor",
    }
    assert record["legal_descriptions"] == [{
        "source_group": "0",
        "description": "GALENA OAKS",
        "lot": "5",
        "block": "107",
    }]
    assert record["legal_description_raw"] == (
        "GALENA OAKS | Lot: 5 | Block: 107"
    )
    assert record["jurisdiction"] == {
        "geoid": "48201",
        "name": "Harris County, Texas",
        "state_code": "TX",
    }
    assert record["document_access"]["link_present"] is True
    assert record["document_access"]["authentication"] == "registered_account"
    assert record["document_access"]["watermarked_view_fee_usd"] == 0
    assert record["document_access"]["document_url"] == (
        "https://www.cclerk.hctx.net/Applications/WebSearch/"
        "EComm/ViewEdocs.aspx?ID=fixture%2Bopaque%3D"
    )


def test_parse_no_results_is_a_clean_empty_source_page():
    payload = recorder.parse_results(NO_RESULTS, RESULT_URL)

    assert payload["status"] == "ok"
    assert payload["results"] == []
    assert payload["coverage"]["source_rows_returned"] == 0
    assert payload["coverage"]["possible_source_ceiling_reached"] is False


def test_real_property_title_without_no_result_marker_is_source_drift():
    with pytest.raises(
        recorder.HarrisRecorderSourceChanged,
        match="neither index rows nor a no-result marker",
    ):
        recorder.parse_results(SOURCE_DRIFT, RESULT_URL)


def test_data_shaped_row_without_file_number_is_source_drift():
    broken = EXACT_RESULT.replace(
        "id=\"ctl00_ContentPlaceHolder1_ListView1_ctrl0_lblFileNo\"",
        "id=\"ctl00_ContentPlaceHolder1_ListView1_ctrl0_missingFileNo\"",
    )

    with pytest.raises(
        recorder.HarrisRecorderSourceChanged,
        match="lacks its file-number field",
    ):
        recorder.parse_results(broken, RESULT_URL)


def test_observed_ceiling_is_flagged_without_claiming_a_published_total(
    monkeypatch,
):
    monkeypatch.setattr(recorder, "OBSERVED_RESULT_CEILING", 1)

    payload = recorder.parse_results(EXACT_RESULT, RESULT_URL)

    coverage = payload["coverage"]
    assert coverage["source_rows_returned"] == 1
    assert coverage["source_reported_total_results"] is None
    assert coverage["ceiling_status"] == "observed_not_published"
    assert coverage["possible_source_ceiling_reached"] is True
    assert coverage["completeness"] == "unknown_at_observed_ceiling"


def test_client_bootstraps_aspnet_state_posts_native_fields_and_follows_result():
    session = QueueSession([
        FixtureResponse(SEARCH_FORM),
        FixtureResponse(
            "",
            status_code=302,
            headers={"Location": RESULT_URL},
        ),
        FixtureResponse(EXACT_RESULT, url=RESULT_URL),
    ])
    client = fixture_client(session)

    payload = client.search({
        "file_number": "RP-2026-72194",
        "grantee": "HOME LIQUIDATORS 2 LLC",
    })

    assert len(payload["results"]) == 1
    assert [call["method"] for call in session.calls] == ["GET", "POST", "GET"]
    post = session.calls[1]
    assert post["url"] == recorder.SEARCH_URL
    assert post["allow_redirects"] is False
    assert post["data"]["__VIEWSTATE"] == "fixture-viewstate"
    assert post["data"]["__EVENTVALIDATION"] == "fixture-eventvalidation"
    assert post["data"][recorder.FORM_FIELDS["file_number"]] == (
        "RP-2026-72194"
    )
    assert post["data"][recorder.FORM_FIELDS["grantee"]] == (
        "HOME LIQUIDATORS 2 LLC"
    )
    assert post["data"][recorder.SEARCH_BUTTON] == "Search"
    assert session.calls[2]["url"] == RESULT_URL


def test_source_validation_message_survives_nonredirected_form_response():
    session = QueueSession([
        FixtureResponse(SEARCH_FORM),
        FixtureResponse(FORM_ERROR),
    ])

    with pytest.raises(
        recorder.HarrisRecorderError,
        match="Please enter valid search criteria",
    ):
        fixture_client(session).search({"grantor": "A"})


def test_date_arguments_accept_iso_and_native_without_changing_selector_scope():
    args = recorder.build_parser().parse_args([
        "search",
        "--from-date",
        "2026-02-01",
        "--to-date",
        "02/26/2026",
        "--lot",
        "5",
    ])

    selectors = recorder._selectors_from_args(args)

    assert selectors["from_date"] == "02/01/2026"
    assert selectors["to_date"] == "02/26/2026"
    assert selectors["lot"] == "5"


def test_user_limit_only_slices_after_the_full_source_page(monkeypatch):
    source_payload = recorder.parse_results(EXACT_RESULT, RESULT_URL)
    source_payload["results"] = source_payload["results"] * 2

    class FakeClient:
        def search(self, selectors):
            assert selectors["grantee"] == "HOME LIQUIDATORS 2 LLC"
            return source_payload

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    args = recorder.build_parser().parse_args([
        "search",
        "--grantee",
        "HOME LIQUIDATORS 2 LLC",
        "--limit",
        "1",
    ])

    result = recorder.execute(
        args,
        access_decision={"allowed": True},
        client=FakeClient(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.query.query.requested_limit == 1
    assert result.records[0]["search_metadata"]["coverage"][
        "source_rows_returned"
    ] == 1


def test_products_keep_search_images_copy_fees_and_bulk_exports_distinct():
    payload = recorder.access_and_product_metadata()

    assert payload["index_search"]["authentication"] == "anonymous"
    assert payload["index_search"]["ceiling_status"] == (
        "observed_not_published"
    )
    assert payload["document_images"]["registration_required"] is True
    assert payload["document_images"]["watermarked_view_fee_usd"] == 0
    assert payload["copy_fees"]["paper_noncertified_per_page_usd"] == 1.0
    assert payload["copy_fees"]["certification_per_document_usd"] == 5.0
    bulk = payload["bulk_data_sales"]
    assert bulk["index"]["format"] == "pipe_delimited_text"
    assert bulk["images"]["format"] == "TIFF"
    assert bulk["index"]["purchase"] == "separate_from_images"
    assert bulk["daily_ftp"]["purchase_period"] == "monthly"
    assert bulk["posted_price"] is None


def test_contract_execute_includes_catalog_decision_and_normalized_records(
    monkeypatch,
):
    args = recorder.build_parser().parse_args([
        "search",
        "--file-number",
        recorder.SENTINEL_FILE_NUMBER,
    ])
    decision = {
        "allowed": True,
        "access_class": "B",
        "automation_disposition": "allowed_with_limits",
        "reason_code": "reviewed_machine_route",
        "limits": {"minimum_interval_seconds": 0.2},
    }
    payload = recorder.parse_results(
        EXACT_RESULT,
        RESULT_URL,
        selectors={"file_number": recorder.SENTINEL_FILE_NUMBER},
    )

    class FakeClient:
        def search(self, selectors):
            assert selectors["file_number"] == recorder.SENTINEL_FILE_NUMBER
            return payload

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    result = recorder.execute(
        args,
        access_decision=decision,
        client=FakeClient(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["record_kind"] == "recorded_instrument"
    assert result.records[0]["canonical_ref"].startswith("PROPERTY:")
    assert result.records[0]["search_metadata"]["coverage"][
        "source_rows_returned"
    ] == 1
    assert result.query.query.metadata["access_decision"]["allowed"] is True
    assert result.query.query.metadata["access_decision"][
        "automation_disposition"
    ] == "allowed_with_limits"


def test_contract_execute_preserves_authoritative_no_results(monkeypatch):
    args = recorder.build_parser().parse_args([
        "search",
        "--file-number",
        "RP-1900-DOES-NOT-EXIST",
    ])
    payload = recorder.parse_results(NO_RESULTS, RESULT_URL)

    class FakeClient:
        def search(self, _selectors):
            return payload

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    result = recorder.execute(
        args,
        access_decision={"allowed": True},
        client=FakeClient(),
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_contract_execute_marks_observed_boundary_partial(
    monkeypatch,
):
    monkeypatch.setattr(recorder, "OBSERVED_RESULT_CEILING", 1)
    args = recorder.build_parser().parse_args([
        "search",
        "--grantee",
        "HOME LIQUIDATORS 2 LLC",
    ])
    payload = recorder.parse_results(EXACT_RESULT, RESULT_URL)

    class FakeClient:
        def search(self, _selectors):
            return payload

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    result = recorder.execute(
        args,
        access_decision={"allowed": True},
        client=FakeClient(),
    )

    assert result.status.value == "partial"
    assert len(result.records) == 1
    assert any("observed boundary" in warning for warning in result.warnings)


def test_contract_execute_returns_catalog_denial_without_calling_source(
    monkeypatch,
):
    args = recorder.build_parser().parse_args([
        "search",
        "--file-number",
        recorder.SENTINEL_FILE_NUMBER,
    ])
    decision = {
        "allowed": False,
        "access_class": "D",
        "automation_disposition": "unclear",
        "reason_code": "licensed_contract_required",
        "reason": "data-sales arrangement required for the reviewed bulk route",
    }

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    result = recorder.execute(args, access_decision=decision)

    assert result.status.value == "restricted"
    assert result.records == ()
    assert result.errors[0].code == "licensed_contract_required"
    assert result.errors[0].details["access_decision"]["allowed"] is False
    assert result.query.query.metadata["access_decision"]["reason_code"] == (
        "licensed_contract_required"
    )


def test_contract_execute_maps_source_schema_failure(monkeypatch):
    args = recorder.build_parser().parse_args([
        "search",
        "--file-number",
        recorder.SENTINEL_FILE_NUMBER,
    ])

    class FakeClient:
        def search(self, _selectors):
            raise recorder.HarrisRecorderSourceChanged("fixture schema drift")

    monkeypatch.setattr(recorder, "_log", lambda *_args: None)
    result = recorder.execute(
        args,
        access_decision={"allowed": True},
        client=FakeClient(),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].category == "source_schema"


def test_sentinel_checks_index_image_login_and_bulk_product_page():
    record = recorder.parse_results(EXACT_RESULT, RESULT_URL)["results"][0]

    class FakeClient:
        def search(self, selectors):
            assert selectors == {
                "file_number": recorder.SENTINEL_FILE_NUMBER
            }
            return {"results": [record]}

        def probe_document_access(self, document_url):
            assert document_url == record["document_access"]["document_url"]
            return {
                "source_url": document_url,
                "http_status": 302,
                "redirect_url": recorder.LOGIN_URL + "?ReturnUrl=fixture",
                "anonymous_status": "login_required",
                "registration_required": True,
            }

        def get(self, url):
            assert url == recorder.PUBLIC_RECORDS_URL
            return FixtureResponse(
                "Data Sales pipe delimited index TIFF images FTP access",
                url=recorder.PUBLIC_RECORDS_URL,
            )

    payload = recorder.run_sentinel(FakeClient())

    assert payload["status"] == "ok"
    assert [check["name"] for check in payload["checks"]] == [
        "anonymous_exact_index",
        "registered_document_boundary",
        "official_bulk_products",
    ]
    assert all(check["status"] == "ok" for check in payload["checks"])


def test_products_execute_emits_shared_envelope_without_network(monkeypatch):
    args = recorder.build_parser().parse_args(["products", "--json"])
    monkeypatch.setattr(recorder, "_log", lambda *_args: None)

    result = recorder.execute(
        args,
        access_decision={
            "allowed": True,
            "access_class": "B",
            "automation_disposition": "allowed_with_limits",
        },
    )

    payload = result.to_dict()
    assert payload["status"] == "ok"
    assert payload["query"]["query"]["metadata"]["access_decision"][
        "allowed"
    ] is True
    record = payload["records"][0]
    assert record["source_id"] == recorder.SOURCE_ID
    assert record["bulk_data_sales"]["index"]["format"] == (
        "pipe_delimited_text"
    )


@pytest.mark.parametrize(
    ("argv", "function_name"),
    [
        (
            ["search", "--file-number", recorder.SENTINEL_FILE_NUMBER],
            "cmd_search",
        ),
        (["products"], "cmd_products"),
        (["sentinel"], "cmd_sentinel"),
    ],
)
def test_direct_cli_commands_route_through_contract_execute(
    argv,
    function_name,
    monkeypatch,
):
    args = recorder.build_parser().parse_args(argv)
    query = recorder.build_query(
        args,
        access_decision={"allowed": True},
    )
    result = recorder.PublicRecordsResult.success(
        query,
        [{
            "source_id": recorder.SOURCE_ID,
            "record_kind": "source_health_check",
            "native_document_id": "fixture",
        }],
    )
    calls = []
    monkeypatch.setattr(
        recorder,
        "execute",
        lambda received: calls.append(("execute", received)) or result,
    )
    monkeypatch.setattr(
        recorder,
        "_emit_contract",
        lambda received, received_args, summary: calls.append(
            ("emit", received, received_args, summary)
        ),
    )

    assert getattr(recorder, function_name)(args) == 0
    assert calls[0] == ("execute", args)
    assert calls[1][0] == "emit"
    assert calls[1][1] is result
