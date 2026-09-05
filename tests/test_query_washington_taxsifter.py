from __future__ import annotations

import base64
import json
import subprocess
import sys
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import pytest
from bs4 import BeautifulSoup

from tools import query_washington_taxsifter as adapter
from tools.public_records_contract import PublicRecordsResult, ResultStatus
from tools.public_records_http import RetryPolicy, SourceSchemaError


FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures" / "public_records" / "washington_taxsifter"
)


def _fixture(name: str) -> str:
    return (FIXTURE_ROOT / f"{name}.html").read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        text: str,
        url: str,
        *,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        history: tuple[Any, ...] = (),
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.history = history


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


def _page(
    fixture: str,
    operation: str,
    url: str,
) -> adapter.SourcePage:
    return adapter._source_page(
        FakeResponse(_fixture(fixture), url),
        operation=operation,
    )


def _args(command: str, **overrides: Any) -> Namespace:
    values = {
        "command": command,
        "county": "adams",
        "source": None,
        "query": "2038010000001",
        "data_link": None,
        "operations": "assessor,treasurer,appraisal",
        "limit": 100,
        "cursor": None,
        "parcel": None,
        "date_from": None,
        "date_to": None,
        "price_from": None,
        "price_to": None,
        "acres_from": None,
        "acres_to": None,
        "year_built_from": None,
        "year_built_to": None,
        "map_number": None,
        "verified": False,
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


def test_parser_defaults_to_exhaustive_result_collection() -> None:
    search = adapter.build_parser().parse_args(["search", "SMITH", "--county", "ferry"])
    sales = adapter.build_parser().parse_args(["sales", "--county", "ferry"])

    assert search.limit is None
    assert sales.limit is None


def test_source_family_retains_all_counties_with_ten_live() -> None:
    payload = adapter.execute(_args("sources"), log_results=False)

    assert payload["source_count"] == 11
    assert payload["live_verified_count"] == 10
    assert set(adapter.VERIFIED_TENANT_KEYS) == {
        "adams",
        "douglas",
        "ferry",
        "franklin",
        "kittitas",
        "lincoln",
        "okanogan",
        "pacific",
        "skamania",
        "whitman",
    }
    assert {source["county_key"] for source in payload["sources"]} == {
        "adams",
        "douglas",
        "ferry",
        "franklin",
        "kittitas",
        "lincoln",
        "mason",
        "okanogan",
        "pacific",
        "skamania",
        "whitman",
    }


def test_mason_challenge_state_is_deployment_specific() -> None:
    assert adapter.TENANTS_BY_KEY["mason"].access_state == "challenge_observed"
    assert {
        tenant.key
        for tenant in adapter.TENANTS
        if tenant.access_state != "live_verified"
    } == {"mason"}


def test_corrected_roots_retain_legacy_discovery_aliases() -> None:
    lincoln = adapter.TENANTS_BY_KEY["lincoln"]
    okanogan = adapter.TENANTS_BY_KEY["okanogan"]
    pacific = adapter.TENANTS_BY_KEY["pacific"]

    assert lincoln.portal_root == "https://lincolnwa-taxsifter.publicaccessnow.com/"
    assert set(lincoln.observed_hosts) == {
        "lincolnwa.taxsifter.com",
        "lincolnwa-taxsifter.publicaccessnow.com",
    }
    assert okanogan.portal_root == "https://okanoganwa-taxsifter.publicaccessnow.com/"
    assert set(okanogan.observed_hosts) == {
        "okanoganwa.taxsifter.com",
        "okanoganwa-taxsifter.publicaccessnow.com",
    }
    assert set(pacific.observed_hosts) == {
        "pacificwa.taxsifter.com",
        "pacificwa-taxsifter.publicaccessnow.com",
    }
    for url, expected in (
        (
            "https://lincolnwa-taxsifter.publicaccessnow.com/"
            "Search/results.aspx?q=2836010000000",
            lincoln,
        ),
        (
            "https://lincolnwa.taxsifter.com/Search/results.aspx?q=2836010000000",
            lincoln,
        ),
        (
            "https://okanoganwa-taxsifter.publicaccessnow.com/"
            "Search/results.aspx?q=4030014005",
            okanogan,
        ),
        (
            "http://okanoganwa.taxsifter.com/Search/results.aspx?q=4030014005",
            okanogan,
        ),
        (
            "https://pacificwa-taxsifter.publicaccessnow.com/"
            "Assessor.aspx?keyId=788382&parcelNumber=15111821012&typeID=1",
            pacific,
        ),
    ):
        assert adapter.discover_data_link(url).tenant == expected


@pytest.mark.parametrize("tenant", adapter.TENANTS)
def test_every_official_data_link_discovers_its_tenant(
    tenant: adapter.TenantConfig,
) -> None:
    discovered = adapter.discover_data_link(tenant.observed_data_link)

    assert discovered.tenant == tenant
    assert discovered.operation in {
        adapter.Operation.SEARCH,
        adapter.Operation.ASSESSOR,
    }
    assert discovered.search_query or discovered.parcel_number


def test_discovery_preserves_nested_path_and_string_parcel() -> None:
    mason = adapter.discover_data_link(
        "https://property.masoncountywa.gov/TaxSifter/Search/Results.aspx?q=001-02-003"
    )
    whitman = adapter.discover_data_link(
        "https://terrascan.whitmancounty.net/Taxsifter/"
        "Assessor.aspx?keyId=77&parcelNumber=0000123&typeID=1"
    )

    assert mason.path_prefix == "/TaxSifter/"
    assert mason.search_query == "001-02-003"
    assert whitman.path_prefix == "/Taxsifter/"
    assert whitman.parcel_number == "0000123"
    assert isinstance(whitman.parcel_number, str)


def test_unknown_data_link_is_an_observation_not_a_false_match() -> None:
    discovered = adapter.discover_data_link(
        "https://example.gov/Assessor.aspx?parcelNumber=0001"
    )

    assert discovered.tenant is None
    assert discovered.operation == adapter.Operation.ASSESSOR
    assert discovered.parcel_number == "0001"


@pytest.mark.parametrize(
    ("fixture", "operation", "state"),
    [
        ("disclaimer", "search", adapter.ResponseState.DISCLAIMER),
        ("search_page_1", "search", adapter.ResponseState.LIVE),
        ("no_results", "search", adapter.ResponseState.NO_RESULT),
        ("assessor_detail", "assessor", adapter.ResponseState.LIVE),
        ("treasurer_detail", "treasurer", adapter.ResponseState.LIVE),
        ("appraisal_detail", "appraisal", adapter.ResponseState.LIVE),
        ("sales_form", "sales", adapter.ResponseState.LIVE),
        ("challenge", "search", adapter.ResponseState.CHALLENGE),
        ("maintenance", "search", adapter.ResponseState.MAINTENANCE),
        ("unexpected", "search", adapter.ResponseState.SCHEMA_ERROR),
    ],
)
def test_response_state_classifier(
    fixture: str,
    operation: str,
    state: adapter.ResponseState,
) -> None:
    url = (
        "https://example.test/Disclaimer.aspx"
        if fixture == "disclaimer"
        else f"https://example.test/{operation}.aspx"
    )
    assert (
        adapter.classify_response(
            _fixture(fixture),
            url=url,
            operation=operation,
        )
        == state
    )


def test_client_establishes_ordinary_disclaimer_session() -> None:
    target = "https://adamswa-taxsifter.publicaccessnow.com/Search/Results.aspx?q=SMITH"
    session = FakeSession(
        [
            FakeResponse(
                _fixture("disclaimer"),
                "https://adamswa-taxsifter.publicaccessnow.com/Disclaimer.aspx",
            ),
            FakeResponse(
                _fixture("unexpected"),
                "https://adamswa-taxsifter.publicaccessnow.com/",
            ),
            FakeResponse(_fixture("search_page_1"), target),
        ]
    )
    client = adapter.TaxSifterClient(
        adapter.TENANTS_BY_KEY["adams"],
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )

    page = client.fetch_page(target, operation=adapter.Operation.SEARCH)

    assert page.state == adapter.ResponseState.LIVE
    assert [request["method"] for request in session.requests] == [
        "GET",
        "POST",
        "GET",
    ]
    post = session.requests[1]["data"]
    assert post["__VIEWSTATE"] == "fixture-viewstate"
    assert post["ctl00$cphContent$btnAgree"] == "I Agree"
    assert any("Disclaimer.aspx" in url for url in page.transition_urls)


def test_client_retries_transient_status_without_unbounded_loop() -> None:
    target = "https://adamswa-taxsifter.publicaccessnow.com/Search/Results.aspx?q=SMITH"
    session = FakeSession(
        [
            FakeResponse("busy", target, status_code=503),
            FakeResponse(_fixture("search_page_1"), target),
        ]
    )
    client = adapter.TaxSifterClient(
        adapter.TENANTS_BY_KEY["adams"],
        session=session,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_initial=0,
            max_backoff=0,
        ),
        minimum_interval=0,
    )

    page = client.fetch_page(target, operation=adapter.Operation.SEARCH)

    assert page.state == adapter.ResponseState.LIVE
    assert len(session.requests) == 2


def test_challenge_maps_to_human_required_not_no_results() -> None:
    target = adapter.TENANTS_BY_KEY["mason"].observed_data_link
    session = FakeSession([FakeResponse(_fixture("challenge"), target)])
    client = adapter.TaxSifterClient(
        adapter.TENANTS_BY_KEY["mason"],
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )

    with pytest.raises(adapter.SourceChallengeError) as captured:
        client.fetch_page(target, operation=adapter.Operation.SEARCH)

    assert captured.value.result_status == ResultStatus.HUMAN_REQUIRED
    assert captured.value.details["response_state"] == "challenge"


def test_maintenance_maps_to_unavailable_not_no_results() -> None:
    target = adapter.TENANTS_BY_KEY["adams"].observed_data_link
    session = FakeSession([FakeResponse(_fixture("maintenance"), target)])
    client = adapter.TaxSifterClient(
        adapter.TENANTS_BY_KEY["adams"],
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )

    with pytest.raises(adapter.SourceMaintenanceError) as captured:
        client.fetch_page(target, operation=adapter.Operation.SEARCH)

    assert captured.value.result_status == ResultStatus.UNAVAILABLE
    assert captured.value.details["response_state"] == "maintenance"


def test_search_parser_extracts_deterministic_links_and_provenance() -> None:
    tenant = adapter.TENANTS_BY_KEY["ferry"]
    page = _page(
        "search_page_1",
        adapter.Operation.SEARCH,
        "https://ferrywa-taxsifter.publicaccessnow.com/"
        "Search/Results.aspx?q=SMITH&page=1",
    )

    parsed = adapter.parse_search_page(page, tenant, native_page=1)

    assert parsed.total_count == 3
    assert parsed.maximum_page == 2
    assert len(parsed.records) == 2
    first = parsed.records[0]
    assert first["native_parcel_id"] == "001-000-000"
    assert first["key_id"] == "77"
    assert first["type_id"] == "1"
    assert first["account_occurrence"] == {
        "source_id": tenant.source_id,
        "key_id": "77",
        "type_id": "1",
        "native_id": "keyId=77;typeID=1",
    }
    assert first["parcel_join"] == {
        "county_geoid": tenant.county_geoid,
        "parcel_number": "001-000-000",
    }
    assert "keyId%3D77%3BtypeID%3D1" in first["canonical_ref"]
    assert first["operation_links"]["treasurer"].endswith(
        "parcelNumber=001-000-000&typeID=1"
    )
    assert first["provenance"]["lineage_id"] == adapter.ASSESSOR_LINEAGE
    assert (
        first["native_joins"][adapter.STATEWIDE_PARCEL_SOURCE_ID][
            "lineage_interpretation"
        ]
        == "same_county_assessor_origin_not_independent_corroboration"
    )
    assert any(
        pivot["kind"] == "mapsifter_parcel_map" for pivot in first["external_pivots"]
    )


def test_search_account_occurrence_does_not_conflate_duplicate_parcel() -> None:
    tenant = adapter.TENANTS_BY_KEY["ferry"]
    html = _fixture("search_page_1").replace(
        "00000000000002",
        "001-000-000",
    )
    page = adapter._source_page(
        FakeResponse(
            html,
            "https://ferrywa-taxsifter.publicaccessnow.com/"
            "Search/Results.aspx?q=SMITH&page=1",
        ),
        operation=adapter.Operation.SEARCH,
    )

    records = adapter.parse_search_page(
        page,
        tenant,
        native_page=1,
    ).records

    assert records[0]["parcel_join"] == records[1]["parcel_join"]
    assert records[0]["account_occurrence"] != records[1]["account_occurrence"]
    assert records[0]["canonical_ref"] != records[1]["canonical_ref"]


def test_search_parser_authoritative_empty() -> None:
    page = _page(
        "no_results",
        adapter.Operation.SEARCH,
        "https://adamswa-taxsifter.publicaccessnow.com/Search/Results.aspx?q=NOTFOUND",
    )

    parsed = adapter.parse_search_page(
        page,
        adapter.TENANTS_BY_KEY["adams"],
        native_page=1,
    )

    assert parsed.records == ()
    assert parsed.total_count == 0
    assert parsed.source_page.state == adapter.ResponseState.NO_RESULT


def test_search_schema_error_is_not_empty_result() -> None:
    page = _page(
        "unexpected",
        adapter.Operation.SEARCH,
        "https://adamswa-taxsifter.publicaccessnow.com/Search/Results.aspx",
    )

    with pytest.raises(SourceSchemaError):
        adapter.parse_search_page(
            page,
            adapter.TENANTS_BY_KEY["adams"],
            native_page=1,
        )


class FixturePagingClient:
    search = adapter.TaxSifterClient.search

    def __init__(self) -> None:
        self.tenant = adapter.TENANTS_BY_KEY["ferry"]
        self.calls: list[int] = []

    def search_page(self, selector: str, *, page: int = 1) -> adapter.SearchPage:
        self.calls.append(page)
        fixture = "search_page_1" if page == 1 else "search_page_2"
        source_page = _page(
            fixture,
            adapter.Operation.SEARCH,
            "https://ferrywa-taxsifter.publicaccessnow.com/"
            f"Search/Results.aspx?q={selector}&page={page}",
        )
        return adapter.parse_search_page(
            source_page,
            self.tenant,
            native_page=page,
        )


def test_search_cursor_resumes_inside_native_page() -> None:
    client = FixturePagingClient()

    first = client.search("SMITH", limit=1)
    second = client.search("SMITH", limit=1, cursor=first.next_cursor)
    third = client.search("SMITH", limit=1, cursor=second.next_cursor)

    assert [row["parcel_number"] for row in first.records] == ["001-000-000"]
    assert [row["parcel_number"] for row in second.records] == ["00000000000002"]
    assert [row["parcel_number"] for row in third.records] == ["00000000000003"]
    assert first.next_cursor
    assert second.next_cursor
    assert third.next_cursor is None
    assert client.calls == [1, 1, 1, 2]


def test_search_without_limit_exhausts_native_pages() -> None:
    client = FixturePagingClient()

    batch = client.search("SMITH", limit=None)

    assert [row["parcel_number"] for row in batch.records] == [
        "001-000-000",
        "00000000000002",
        "00000000000003",
    ]
    assert batch.next_cursor is None
    assert client.calls == [1, 2]


def test_search_cursor_binds_county_and_selector() -> None:
    client = FixturePagingClient()
    first = client.search("SMITH", limit=1)

    with pytest.raises(adapter.SourceSelectionError) as captured:
        client.search("JONES", limit=1, cursor=first.next_cursor)

    assert captured.value.code == "cursor_query_mismatch"


def test_search_cursor_contains_integrity_contract() -> None:
    client = FixturePagingClient()

    first = client.search("SMITH", limit=1)
    payload = adapter._decode_cursor(first.next_cursor)

    assert set(payload) == {
        "v",
        "source",
        "criteria",
        "schema",
        "page",
        "offset",
        "total",
        "ordered_page_digest",
        "last_emitted_identity",
    }
    assert payload["source"] == client.tenant.source_id
    assert payload["offset"] == 1
    assert payload["last_emitted_identity"].endswith("keyId=77|typeID=1")


def test_search_cursor_rejects_checksum_tampering() -> None:
    client = FixturePagingClient()
    first = client.search("SMITH", limit=1)
    token = first.next_cursor[len(adapter.CURSOR_PREFIX) :]
    envelope = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    envelope["offset"] = 2
    tampered_token = (
        base64.urlsafe_b64encode(adapter.canonical_json(envelope).encode())
        .decode()
        .rstrip("=")
    )

    with pytest.raises(adapter.SourceSelectionError) as captured:
        client.search(
            "SMITH",
            limit=1,
            cursor=f"{adapter.CURSOR_PREFIX}{tampered_token}",
        )

    assert captured.value.code == "invalid_cursor"


def test_search_cursor_binds_leaf_source() -> None:
    client = FixturePagingClient()
    first = client.search("SMITH", limit=1)
    other = FixturePagingClient()
    other.tenant = adapter.TENANTS_BY_KEY["adams"]

    with pytest.raises(adapter.SourceSelectionError) as captured:
        other.search("SMITH", limit=1, cursor=first.next_cursor)

    assert captured.value.code == "cursor_query_mismatch"


class DriftingPagingClient(FixturePagingClient):
    def __init__(self, drift: str) -> None:
        super().__init__()
        self.drift = drift
        self.resume = False

    def search_page(self, selector: str, *, page: int = 1) -> adapter.SearchPage:
        parsed = super().search_page(selector, page=page)
        if not self.resume or page != 1:
            return parsed
        if self.drift == "order":
            return replace(parsed, records=tuple(reversed(parsed.records)))
        if self.drift == "schema":
            return replace(
                parsed,
                source_page=replace(
                    parsed.source_page,
                    schema_fingerprint="changed-schema",
                ),
            )
        if self.drift == "total":
            return replace(parsed, total_count=parsed.total_count + 1)
        raise AssertionError(self.drift)


@pytest.mark.parametrize("drift", ("order", "schema", "total"))
def test_search_cursor_rejects_source_drift_with_same_query(drift: str) -> None:
    client = DriftingPagingClient(drift)
    first = client.search("SMITH", limit=1)
    client.resume = True

    with pytest.raises(SourceSchemaError):
        client.search("SMITH", limit=1, cursor=first.next_cursor)


def test_search_cursor_rejects_changed_boundary_and_offset() -> None:
    client = FixturePagingClient()
    first = client.search("SMITH", limit=1)
    payload = adapter._decode_cursor(first.next_cursor)

    changed_boundary = adapter._encode_cursor(
        {**payload, "last_emitted_identity": "changed"}
    )
    with pytest.raises(SourceSchemaError):
        client.search("SMITH", limit=1, cursor=changed_boundary)

    invalid_offset = adapter._encode_cursor({**payload, "offset": 99})
    with pytest.raises(adapter.SourceSelectionError) as captured:
        client.search("SMITH", limit=1, cursor=invalid_offset)
    assert captured.value.code == "invalid_cursor"


def test_search_cursor_rejects_v1_prefix() -> None:
    with pytest.raises(adapter.SourceSelectionError) as captured:
        adapter._decode_cursor("washington-taxsifter:v1:e30")

    assert captured.value.code == "invalid_cursor"


def test_assessor_parser_normalizes_dynamic_year_and_distinct_joins() -> None:
    tenant = adapter.TENANTS_BY_KEY["douglas"]
    page = _page(
        "assessor_detail",
        adapter.Operation.ASSESSOR,
        "https://douglaswa-taxsifter.publicaccessnow.com/"
        "Assessor.aspx?keyId=1088458&parcelNumber=07000000504&typeID=1",
    )

    record = adapter.parse_assessor_detail(page, tenant)

    assert record["native_parcel_id"] == "07000000504"
    assert isinstance(record["native_parcel_id"], str)
    assert record["account_occurrence"]["native_id"] == ("keyId=1088458;typeID=1")
    assert record["parcel_join"] == {
        "county_geoid": "53017",
        "parcel_number": "07000000504",
    }
    assert "07000000504" not in record["canonical_ref"]
    assert record["parcel"]["owner_name"] == "EXAMPLE OWNER LLC"
    assert record["parcel"]["mailing_address"]["postal_code"] == "98802-0000"
    assert record["parcel"]["legal_description"] == "LOT 1; EXAMPLE SHORT PLAT"
    assert record["market_value"]["tax_year"] == "2027"
    assert record["market_value"]["fields"]["total"]["amount"] == 371800
    assert record["taxable_value"]["fields"]["total"]["amount"] == 340000
    assert record["sales_history"][0]["sale_date_iso"] == "2017-02-07"
    assert record["sales_history"][0]["price_money"]["amount"] == 275000
    assert (
        record["sales_history"][0]["recording_join"]["lineage_id"]
        == adapter.RECORDER_LINEAGE
    )
    assert record["building_permits"][0]["date_iso"] == "2016-10-12"
    assert record["building_permits"][0]["amount_money"]["amount"] == 1250
    assert record["valuation_history"][0]["total_money"]["amount"] == 371800
    assert record["provenance"]["data_current_as"] == "7/29/2026 3:37 PM"
    assert record["provenance"]["roll_year"] == "2027"
    assert record["provenance"]["lineage_id"] == adapter.ASSESSOR_LINEAGE
    assert (
        record["native_joins"]["county_auditor_recorded_instrument"]["relationship"]
        == "independent_recorded_instrument_candidate"
    )


def test_treasurer_parser_keeps_tax_lineage_and_dynamic_year() -> None:
    tenant = adapter.TENANTS_BY_KEY["adams"]
    page = _page(
        "treasurer_detail",
        adapter.Operation.TREASURER,
        "https://adamswa-taxsifter.publicaccessnow.com/"
        "Treasurer.aspx?keyId=593482&parcelNumber=2038010000001&typeID=1",
    )

    record = adapter.parse_treasurer_detail(page, tenant)

    assert record["native_parcel_id"] == "2038010000001"
    assert record["account_occurrence"]["native_id"] == ("keyId=593482;typeID=1")
    assert record["tax_year"] == "2027"
    assert record["current_tax_year"][0]["gross_tax_money"]["amount"] == 1280.42
    assert record["balances_due"][0]["interest_due_money"]["amount"] == 1.5
    assert record["balances_due"][0]["balance_s_due_money"]["amount"] == 68.12
    assert record["payment_receipts"][0]["receipt_date_iso"] == "2027-05-05"
    assert record["statement_links"][0]["statement_number"] == "20272038010000001"
    assert record["provenance"]["lineage_id"] == adapter.TREASURER_LINEAGE


def test_appraisal_parser_retains_source_native_sections() -> None:
    tenant = adapter.TENANTS_BY_KEY["adams"]
    page = _page(
        "appraisal_detail",
        adapter.Operation.APPRAISAL,
        "https://adamswa-taxsifter.publicaccessnow.com/"
        "AppraisalDetails.aspx?keyId=593482&parcelNumber=2038010000001&typeID=1",
    )

    record = adapter.parse_appraisal_detail(page, tenant)

    assert record["native_parcel_id"] == "2038010000001"
    assert record["account_occurrence"]["native_id"] == ("keyId=593482;typeID=1")
    assert record["sections"][0]["id"] == "grdLand"
    assert record["sections"][0]["rows"][0]["units"] == "440.00000000"
    assert record["provenance"]["representation"] == "appraisal_detail"


def test_sales_form_negotiates_native_prefix_and_options() -> None:
    page = _page(
        "sales_form",
        adapter.Operation.SALES,
        "https://adamswa-taxsifter.publicaccessnow.com/SalesSearch/SalesSearch.aspx",
    )

    form = adapter.parse_sales_form(page)

    assert form.fields["parcel"] == "ctl77$Main$txtparcelNumber"
    assert form.fields["date_from"] == "ctl77$Main$txtdateFrom"
    assert form.fields["page_index"] == "ctl77$Main$hdfSelectedPageIndex"
    assert form.fields["submit"] == "ctl77$Main$searchbutton"
    assert form.options["sale_type"][1]["label"] == "Valid sale"
    assert form.options["building_type"][0]["selected"] is True
    assert "ctl77$Main$ddlSliceType" not in form.defaults
    assert form.defaults["__VIEWSTATE"] == "sales-viewstate"


def test_sales_client_posts_negotiated_fields_without_serializing_state() -> None:
    tenant = adapter.TENANTS_BY_KEY["adams"]
    form_url = (
        "https://adamswa-taxsifter.publicaccessnow.com/SalesSearch/SalesSearch.aspx"
    )
    session = FakeSession(
        [
            FakeResponse(_fixture("sales_form"), form_url),
            FakeResponse(_fixture("sales_results"), form_url),
        ]
    )
    client = adapter.TaxSifterClient(
        tenant,
        session=session,
        retry_policy=RetryPolicy(max_attempts=1),
        minimum_interval=0,
    )

    form, result_page = client.fetch_sales(
        {"parcel": "0000123", "date_from": "01/01/2020"}
    )
    records = adapter.parse_sales_results(result_page, tenant)

    assert session.requests[1]["data"]["ctl77$Main$txtparcelNumber"] == "0000123"
    assert session.requests[1]["data"]["ctl77$Main$txtdateFrom"] == "01/01/2020"
    assert session.requests[1]["data"]["ctl77$Main$searchbutton"] == "Search"
    assert records[0]["native_parcel_id"] == "2038010000001"
    serialized = json.dumps(records)
    assert "sales-viewstate" not in serialized
    assert "__VIEWSTATE" not in serialized
    assert form.source_page.state == adapter.ResponseState.LIVE


def test_sales_parser_builds_independent_recorder_candidate() -> None:
    tenant = adapter.TENANTS_BY_KEY["adams"]
    page = _page(
        "sales_results",
        adapter.Operation.SALES,
        "https://adamswa-taxsifter.publicaccessnow.com/SalesSearch/SalesSearch.aspx",
    )

    records = adapter.parse_sales_results(page, tenant)

    assert len(records) == 1
    sale = records[0]["sale"]
    assert sale["sale_date_iso"] == "2012-10-31"
    assert sale["price_money"]["amount"] == 250000
    assert sale["recording_join"]["instrument_number"] == "WD-302329"
    assert sale["recording_join"]["excise_number"] == "28671"
    assert (
        records[0]["native_joins"]["county_auditor_recorded_instrument"]["lineage_id"]
        == adapter.RECORDER_LINEAGE
    )


def test_live_shaped_sale_aliases_produce_distinct_stable_identities() -> None:
    tenant = adapter.TENANTS_BY_KEY["okanogan"]
    url = (
        "https://okanoganwa-taxsifter.publicaccessnow.com/SalesSearch/SalesSearch.aspx"
    )
    html = _fixture("sales_results_okanogan_collision")
    page = adapter._source_page(
        FakeResponse(html, url),
        operation=adapter.Operation.SALES,
    )
    records = adapter.parse_sales_results(page, tenant)

    assert len(records) == 2
    assert {record["sale"]["sale_date_iso"] for record in records} == {
        "1984-10-01",
        "1992-06-15",
    }
    assert {record["sale"]["sale_document"] for record in records} == {
        "54-2535",
        "92-10876",
    }
    assert len({record["canonical_ref"] for record in records}) == 2
    assert {record["sale_identity"]["strategy"] for record in records} == {
        "normalized_native_fields"
    }

    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table.dataGrid")
    assert table is not None
    rows = table.find_all("tr", recursive=False)
    for row in rows[1:]:
        row.extract()
    for row in reversed(rows[1:]):
        table.append(row)
    reordered_page = adapter._source_page(
        FakeResponse(str(soup), url),
        operation=adapter.Operation.SALES,
    )
    reordered = adapter.parse_sales_results(reordered_page, tenant)

    before = {
        record["sale"]["sale_document"]: record["canonical_ref"] for record in records
    }
    after = {
        record["sale"]["sale_document"]: record["canonical_ref"] for record in reordered
    }
    assert after == before


def test_sale_fallback_hash_excludes_native_position() -> None:
    tenant = adapter.TENANTS_BY_KEY["okanogan"]
    first = adapter._normalize_sale_rows(
        [{"owner": "EXAMPLE", "price": "$100", "native_position": 1}],
        tenant=tenant,
    )[0]
    moved = adapter._normalize_sale_rows(
        [{"owner": "EXAMPLE", "price": "$100", "native_position": 99}],
        tenant=tenant,
    )[0]

    first_id, first_identity = adapter._sale_identity(first)
    moved_id, moved_identity = adapter._sale_identity(moved)

    assert first_identity["strategy"] == "canonical_row_hash"
    assert moved_identity["strategy"] == "canonical_row_hash"
    assert moved_id == first_id


def test_sales_pagination_limitation_is_factual_and_direct_search_remains_live() -> (
    None
):
    client = FakeDetailClient()

    result = adapter.execute(
        _args("sales", parcel="07000000504", limit=None),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.records
    pagination = result.records[0]["retrieval_snapshot"]["native_pagination"]
    assert pagination["state"] == adapter.SALES_PAGINATION_STATE
    assert pagination["continuation_verified"] is False
    assert pagination["current_response_exhaustive"] is True


def test_sales_pagination_marks_truncated_native_response() -> None:
    form = adapter.parse_sales_form(
        _page(
            "sales_form",
            adapter.Operation.SALES,
            "https://okanoganwa-taxsifter.publicaccessnow.com/"
            "SalesSearch/SalesSearch.aspx",
        )
    )
    html = _fixture("sales_results_okanogan_collision").replace(
        "2 records found.",
        "3 records found.",
    )
    page = adapter._source_page(
        FakeResponse(
            html,
            "https://okanoganwa-taxsifter.publicaccessnow.com/"
            "SalesSearch/SalesSearch.aspx",
        ),
        operation=adapter.Operation.SALES,
    )

    observation = adapter._sales_pagination_observation(
        form,
        page,
        returned_records=2,
    )

    assert observation["published_result_count"] == 3
    assert observation["returned_native_records"] == 2
    assert observation["current_response_exhaustive"] is False
    assert observation["continuation_verified"] is False


class FakeSearchClient:
    def __init__(
        self,
        *,
        batch: adapter.SearchBatch | None = None,
        error: Exception | None = None,
    ) -> None:
        self.batch = batch
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def search(self, selector: str, *, limit: int, cursor: str | None = None):
        self.calls.append({"selector": selector, "limit": limit, "cursor": cursor})
        if self.error:
            raise self.error
        return self.batch


def test_execute_search_returns_public_records_contract() -> None:
    tenant = adapter.TENANTS_BY_KEY["ferry"]
    parsed = adapter.parse_search_page(
        _page(
            "search_page_1",
            adapter.Operation.SEARCH,
            "https://ferrywa-taxsifter.publicaccessnow.com/"
            "Search/Results.aspx?q=SMITH&page=1",
        ),
        tenant,
        native_page=1,
    )
    client = FakeSearchClient(
        batch=adapter.SearchBatch(
            records=parsed.records,
            total_count=parsed.total_count,
            next_cursor="cursor-value",
            pages_fetched=1,
            native_page_size=20,
            source_urls=(parsed.source_page.url,),
        )
    )

    result = adapter.execute(
        _args("search", county="ferry", query="SMITH", limit=2),
        client=client,
        log_results=False,
    )

    assert isinstance(result, PublicRecordsResult)
    assert result.status == ResultStatus.OK
    assert result.next_cursor == "cursor-value"
    assert result.query.source.source_id == tenant.source_id
    assert result.query.jurisdiction.county_fips == "019"
    assert result.records[0]["retrieval_snapshot"]["pages_fetched"] == 1


def test_execute_authoritative_empty_is_no_results() -> None:
    client = FakeSearchClient(
        batch=adapter.SearchBatch(
            records=(),
            total_count=0,
            next_cursor=None,
            pages_fetched=1,
            native_page_size=20,
            source_urls=("https://example.test/results",),
        )
    )

    result = adapter.execute(
        _args("search", query="NOTFOUND"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_detail_authoritative_empty_is_no_results() -> None:
    client = FakeSearchClient(
        batch=adapter.SearchBatch(
            records=(),
            total_count=0,
            next_cursor=None,
            pages_fetched=1,
            native_page_size=20,
            source_urls=("https://example.test/results",),
        )
    )

    result = adapter.execute(
        _args("detail", query="NOTFOUND"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_execute_challenge_is_human_required() -> None:
    error = adapter.SourceChallengeError(
        "challenge",
        url="https://property.masoncountywa.gov/TaxSifter/Search/Results.aspx",
        details={"response_state": "challenge"},
    )
    client = FakeSearchClient(error=error)

    result = adapter.execute(
        _args("search", county="mason"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "source_challenge_required"
    assert result.errors[0].details["response_state"] == "challenge"


class FakeDetailClient:
    def __init__(self, *, treasurer_error: Exception | None = None) -> None:
        tenant = adapter.TENANTS_BY_KEY["adams"]
        search_html = (
            _fixture("search_page_1")
            .replace(
                "001-000-000",
                "07000000504",
            )
            .replace(
                "keyId=77",
                "keyId=1088458",
            )
        )
        search_page = adapter.parse_search_page(
            adapter._source_page(
                FakeResponse(
                    search_html,
                    "https://adamswa-taxsifter.publicaccessnow.com/"
                    "Search/Results.aspx?q=07000000504&page=1",
                ),
                operation=adapter.Operation.SEARCH,
            ),
            tenant,
            native_page=1,
        )
        self.search_record = search_page.records[0]
        self.treasurer_error = treasurer_error

    def search(self, selector: str, *, limit: int, cursor: str | None = None):
        return adapter.SearchBatch(
            records=(self.search_record,),
            total_count=1,
            next_cursor=None,
            pages_fetched=1,
            native_page_size=20,
            source_urls=(self.search_record["source_url"],),
        )

    def fetch_operation(self, url: str, *, operation: str):
        if operation == adapter.Operation.ASSESSOR:
            return _page(
                "assessor_detail",
                operation,
                "https://adamswa-taxsifter.publicaccessnow.com/"
                "Assessor.aspx?keyId=1088458&parcelNumber=07000000504&typeID=1",
            )
        if operation == adapter.Operation.TREASURER:
            if self.treasurer_error:
                raise self.treasurer_error
            return adapter._source_page(
                FakeResponse(
                    _fixture("treasurer_detail")
                    .replace(
                        "2038010000001",
                        "07000000504",
                    )
                    .replace(
                        "keyId=593482",
                        "keyId=1088458",
                    ),
                    "https://adamswa-taxsifter.publicaccessnow.com/"
                    "Treasurer.aspx?keyId=1088458"
                    "&parcelNumber=07000000504&typeID=1",
                ),
                operation=operation,
            )
        if operation == adapter.Operation.APPRAISAL:
            return adapter._source_page(
                FakeResponse(
                    _fixture("appraisal_detail")
                    .replace(
                        "2038010000001",
                        "07000000504",
                    )
                    .replace(
                        "keyId=593482",
                        "keyId=1088458",
                    ),
                    "https://adamswa-taxsifter.publicaccessnow.com/"
                    "AppraisalDetails.aspx?keyId=1088458"
                    "&parcelNumber=07000000504&typeID=1",
                ),
                operation=operation,
            )
        raise AssertionError(operation)

    def fetch_sales(self, _filters):
        form_page = _page(
            "sales_form",
            adapter.Operation.SALES,
            "https://adamswa-taxsifter.publicaccessnow.com/"
            "SalesSearch/SalesSearch.aspx",
        )
        result_page = _page(
            "sales_results",
            adapter.Operation.SALES,
            "https://adamswa-taxsifter.publicaccessnow.com/"
            "SalesSearch/SalesSearch.aspx",
        )
        return adapter.parse_sales_form(form_page), result_page


def test_detail_bundle_keeps_representations_and_lineages_distinct() -> None:
    result = adapter.execute(
        _args(
            "detail",
            query="07000000504",
            operations="all",
        ),
        client=FakeDetailClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    bundle = result.records[0]
    assert bundle["native_parcel_id"] == "07000000504"
    assert set(bundle["representations"]) == {
        "assessor",
        "permits",
        "treasurer",
        "appraisal",
        "sales",
    }
    assert (
        bundle["representations"]["assessor"]["provenance"]["lineage_id"]
        == adapter.ASSESSOR_LINEAGE
    )
    assert (
        bundle["representations"]["treasurer"]["provenance"]["lineage_id"]
        == adapter.TREASURER_LINEAGE
    )
    assert bundle["representations"]["sales"]["lineage_id"] == adapter.ASSESSOR_LINEAGE
    assert (
        bundle["lineage_contract"]["recorder"]["lineage_id"] == adapter.RECORDER_LINEAGE
    )
    assert bundle["account_occurrence"]["native_id"] == ("keyId=1088458;typeID=1")
    assert bundle["parcel_join"] == {
        "county_geoid": "53001",
        "parcel_number": "07000000504",
    }


class MismatchedDetailClient(FakeDetailClient):
    def fetch_operation(self, url: str, *, operation: str):
        page = super().fetch_operation(url, operation=operation)
        if operation != adapter.Operation.ASSESSOR:
            return page
        return replace(
            page,
            url=page.url.replace("keyId=1088458", "keyId=9999999"),
        )


def test_detail_rejects_parcel_key_or_type_drift() -> None:
    result = adapter.execute(
        _args("detail", query="07000000504"),
        client=MismatchedDetailClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"
    assert result.errors[0].details["field"] == "key_id"


def test_operation_failure_yields_partial_bundle_with_typed_state() -> None:
    error = adapter.SourceMaintenanceError(
        "maintenance",
        url="https://example.test/Treasurer.aspx",
        details={"response_state": "maintenance"},
    )

    result = adapter.execute(
        _args("detail", query="07000000504"),
        client=FakeDetailClient(treasurer_error=error),
        log_results=False,
    )

    assert result.status == ResultStatus.PARTIAL
    assert result.errors[0].code == "source_maintenance"
    treasurer = result.records[0]["representations"]["treasurer"]
    assert treasurer["response_state"] == "maintenance"
    assert result.records[0]["representations"]["appraisal"]["sections"]


def test_bounded_probe_exercises_requested_operation_graph() -> None:
    result = adapter.execute(
        _args("probe", operations="all"),
        client=FakeDetailClient(),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    observations = result.records[0]["operation_observations"]
    assert set(observations) == {
        "search",
        "assessor",
        "treasurer",
        "appraisal",
        "sales",
    }
    assert observations["treasurer"]["balance_rows"] == 1
    assert observations["appraisal"]["section_count"] == 1
    assert observations["sales"]["response_state"] == "live"
    assert observations["sales"]["result_count"] == 1


def test_metadata_exposes_capability_and_lineage_without_hidden_state() -> None:
    result = adapter.execute(
        _args("metadata", county="adams"),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.records[0]
    assert record["access_state"] == "live_verified"
    assert "tax_due" in record["observed_capabilities"]
    assert (
        record["metadata"]["operation_lineages"]["treasurer"]["lineage_id"]
        == adapter.TREASURER_LINEAGE
    )
    serialized = result.to_json()
    assert "__VIEWSTATE" not in serialized
    assert "ASP.NET_SessionId" not in serialized


def test_cli_sources_and_metadata_write_output(tmp_path: Path) -> None:
    sources_path = tmp_path / "sources.json"
    metadata_path = tmp_path / "metadata.json"
    subprocess.run(
        [
            sys.executable,
            "tools/query_washington_taxsifter.py",
            "sources",
            "--output",
            str(sources_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "tools/query_washington_taxsifter.py",
            "metadata",
            "--county",
            "adams",
            "--output",
            str(metadata_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(sources_path.read_text())["source_count"] == 11
    metadata = json.loads(metadata_path.read_text())
    assert metadata["status"] == "ok"
    assert metadata["records"][0]["county_key"] == "adams"
