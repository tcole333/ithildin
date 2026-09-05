from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_new_jersey_dca_property as dca


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "new_jersey_dca_property"
)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        dca,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


class FixtureResponse:
    def __init__(
        self,
        *,
        payload: Any | None = None,
        text: str | None = None,
        status_code: int = 200,
    ) -> None:
        self.payload = payload
        self.text = text if text is not None else json.dumps(payload)
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> Any:
        return self.payload


class FixtureTransport:
    def __init__(
        self,
        *,
        rows: list[Mapping[str, Any]] | None = None,
        form_html: str | None = None,
    ) -> None:
        source = json.loads(
            (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
        )
        self.rows = list(source["value"] if rows is None else rows)
        self.form_html = form_html or (
            FIXTURE_DIR / "search-form.html"
        ).read_text(encoding="utf-8")
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> FixtureResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "params": dict(params or {}),
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if url == dca.SEARCH_PAGE_URL:
            return FixtureResponse(text=self.form_html)
        if url != dca.ODATA_URL:
            return FixtureResponse(status_code=404, text="not found")

        query = dict(params or {})
        filter_value = str(query.get("$filter", ""))
        rows = list(self.rows)
        registration_match = re.search(
            r"substringof\('([^']+)', "
            r"ultra_bhibuildingregistrationnum\)",
            filter_value,
        )
        if registration_match:
            selector = registration_match.group(1).replace("''", "'")
            rows = [
                row
                for row in rows
                if selector
                in str(row.get("ultra_bhibuildingregistrationnum", ""))
            ]
        block_match = re.search(
            r"substringof\('((?:''|[^'])+)', ultra_block\)",
            filter_value,
        )
        if block_match:
            selector = block_match.group(1).replace("''", "'")
            rows = [
                row
                for row in rows
                if selector in str(row.get("ultra_block", ""))
            ]
        lot_match = re.search(
            r"substringof\('((?:''|[^'])+)', ultra_lot\)",
            filter_value,
        )
        if lot_match:
            selector = lot_match.group(1).replace("''", "'")
            rows = [
                row
                for row in rows
                if selector in str(row.get("ultra_lot", ""))
            ]
        address_match = re.search(
            r"substringof\('((?:''|[^'])+)', ultra_addressline1\)",
            filter_value,
        )
        if address_match:
            selector = address_match.group(1).replace("''", "'")
            address_fields = (
                "ultra_addressline1",
                "ultra_akaaddress1",
                "ultra_akaaddress2",
                "ultra_akaaddress3",
                "ultra_akaaddress4",
            )
            rows = [
                row
                for row in rows
                if any(
                    selector in str(row.get(field, ""))
                    for field in address_fields
                )
            ]
        county_match = re.search(
            r"ultra_county/Id eq guid'([^']+)'",
            filter_value,
        )
        if county_match:
            county_id = county_match.group(1).casefold()
            rows = [
                row
                for row in rows
                if str(
                    (row.get("ultra_county") or {}).get("Id", "")
                ).casefold()
                == county_id
            ]
        municipality_match = re.search(
            r"ultra_municipality/Id eq guid'([^']+)'",
            filter_value,
        )
        if municipality_match:
            municipality_id = municipality_match.group(1).casefold()
            rows = [
                row
                for row in rows
                if str(
                    (row.get("ultra_municipality") or {}).get("Id", "")
                ).casefold()
                == municipality_id
            ]
        keyset_match = re.search(
            r"ultra_bhibuildingregistrationnum gt '([^']+)'",
            filter_value,
        )
        if keyset_match:
            rows = [
                row
                for row in rows
                if str(row["ultra_bhibuildingregistrationnum"])
                > keyset_match.group(1)
            ]
        rows.sort(key=lambda row: row["ultra_bhibuildingregistrationnum"])
        top = int(query.get("$top", len(rows) or 1))
        payload = {
            "odata.metadata": (
                "https://serviceportal.dca.nj.gov/_odata/"
                "$metadata#bhibuildings"
            ),
            "odata.count": str(len(rows)),
            "value": rows[:top],
        }
        if len(rows) > top:
            payload["odata.nextLink"] = (
                f"{dca.ODATA_URL}?$top=-99998&$skip=100000"
            )
        return FixtureResponse(payload=payload)


class FixtureClient(dca.DCAPropertyClient):
    def fetch_lookup_catalog(self) -> dca.LookupCatalog:
        response = self._request(dca.SEARCH_PAGE_URL, accept="text/html")
        return dca.parse_lookup_html(
            str(response.text),
            require_complete=False,
        )


class PageSequenceClient(dca.DCAPropertyClient):
    def __init__(self, pages: list[dca.ODataPage]) -> None:
        super().__init__(
            transport=FixtureTransport(),
            page_size=1,
            timeout=1,
            minimum_interval=0,
            retry_attempts=1,
        )
        self.pages = list(pages)

    def fetch_page(
        self,
        criteria: dca.SearchCriteria,
        *,
        last_building_registration: str | None,
        top: int,
    ) -> dca.ODataPage:
        assert criteria.mode == "registration"
        assert top == 1
        return self.pages.pop(0)


def _client(
    transport: FixtureTransport | None = None,
    *,
    page_size: int = 2,
) -> FixtureClient:
    return FixtureClient(
        transport=transport or FixtureTransport(),
        page_size=page_size,
        timeout=1,
        minimum_interval=0,
        retry_attempts=1,
    )


def _fixture_page() -> dca.ODataPage:
    payload = json.loads(
        (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
    )
    return dca.parse_odata_page(payload)


def test_lookup_parser_preserves_current_ids_and_county_relationships():
    catalog = dca.parse_lookup_html(
        (FIXTURE_DIR / "search-form.html").read_text(encoding="utf-8"),
        require_complete=False,
    )

    assert len(catalog.counties) == 2
    assert len(catalog.municipalities) == 3
    essex = catalog.resolve_county("Essex County")
    newark = catalog.resolve_municipality("newark city")
    assert essex.option_id == "fef3aaf2-63e4-e711-8125-1458d054d020"
    assert newark.option_id == "422d7521-162f-e811-8126-1458d04eb810"
    assert newark.county_id == essex.option_id
    assert len(catalog.fingerprint) == 64


def test_lookup_parser_rejects_incomplete_municipality_county_links():
    source = (FIXTURE_DIR / "search-form.html").read_text(encoding="utf-8")
    source = source.replace(
        'id="422d7521-162f-e811-8126-1458d04eb810"',
        'id="missing-link"',
        1,
    )

    with pytest.raises(
        dca.SourceSchemaError,
        match="municipality-to-county",
    ):
        dca.parse_lookup_html(source, require_complete=False)


def test_lookup_parser_rejects_municipality_link_to_unknown_county():
    source = (FIXTURE_DIR / "search-form.html").read_text(encoding="utf-8")
    source = source.replace(
        'value="fef3aaf2-63e4-e711-8125-1458d054d020"',
        'value="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"',
        1,
    )

    with pytest.raises(dca.SourceSchemaError, match="unknown county"):
        dca.parse_lookup_html(source, require_complete=False)


def test_source_filter_matches_the_three_official_search_branches():
    registration = dca.SearchCriteria(
        mode="registration",
        registration="0714002653",
    )
    parcel = dca.SearchCriteria(
        mode="parcel",
        block="44'1",
        lot="61",
        county_id="fef3aaf2-63e4-e711-8125-1458d054d020",
    )
    address = dca.SearchCriteria(
        mode="address",
        address="O'Neil Broadway",
        municipality_id="422d7521-162f-e811-8126-1458d04eb810",
    )

    assert dca.build_odata_filter(registration) == (
        "substringof('0714002653', ultra_bhibuildingregistrationnum)"
    )
    parcel_filter = dca.build_odata_filter(parcel)
    assert "substringof('44''1', ultra_block)" in parcel_filter
    assert "substringof('61', ultra_lot)" in parcel_filter
    assert "ultra_county/Id eq guid'fef3aaf2" in parcel_filter
    address_filter = dca.build_odata_filter(address)
    assert address_filter.count("O''Neil Broadway") == 5
    assert "ultra_akaaddress4" in address_filter
    assert "ultra_municipality/Id eq guid'422d7521" in address_filter


def test_keyset_filter_uses_verified_building_registration_order():
    criteria = dca.SearchCriteria(
        mode="registration",
        registration="0714",
    )
    filter_value = dca.build_odata_filter(
        criteria,
        last_building_registration="0714002810001",
    )

    assert filter_value.startswith("(")
    assert filter_value.endswith(
        "ultra_bhibuildingregistrationnum gt '0714002810001'"
    )


def test_odata_page_preserves_native_nextlink_but_rejects_schema_drift():
    page = _fixture_page()

    assert page.remaining_count == 3
    assert len(page.records) == 3
    assert "$top=-99998" in str(page.native_next_link)
    assert len(page.response_field_fingerprint) == 64

    changed = json.loads(
        (FIXTURE_DIR / "schema-drift.json").read_text(encoding="utf-8")
    )
    with pytest.raises(dca.SourceSchemaError, match="schema changed"):
        dca.parse_odata_page(changed)


def test_keyset_traversal_ignores_broken_native_nextlink():
    transport = FixtureTransport()
    client = _client(transport)
    criteria = dca.SearchCriteria(
        mode="registration",
        registration="0714",
    )

    fetched = client.search(
        criteria,
        requested_limit=None,
        max_records=None,
        cursor=None,
    )

    assert [
        row["ultra_bhibuildingregistrationnum"]
        for row in fetched.records
    ] == [
        "0714002653001",
        "0714003383001",
        "0714003383002",
    ]
    assert fetched.observed_total == 3
    assert fetched.pages_fetched == 2
    assert fetched.next_cursor is None
    odata_calls = [
        call for call in transport.calls if call["url"] == dca.ODATA_URL
    ]
    assert len(odata_calls) == 2
    assert " gt " not in odata_calls[0]["params"]["$filter"]
    assert "0714003383001" in odata_calls[1]["params"]["$filter"]
    assert "$skip" not in odata_calls[1]["params"]


def test_cursor_is_criteria_bound_and_resumes_without_duplicate_rows():
    transport = FixtureTransport()
    client = _client(transport)
    criteria = dca.SearchCriteria(
        mode="registration",
        registration="0714",
    )

    first = client.search(
        criteria,
        requested_limit=2,
        max_records=None,
        cursor=None,
    )
    second = client.search(
        criteria,
        requested_limit=2,
        max_records=None,
        cursor=first.next_cursor,
    )

    assert len(first.records) == 2
    assert first.next_cursor
    assert [row["ultra_bhibuildingregistrationnum"] for row in second.records] == [
        "0714003383002"
    ]
    assert second.emitted_count == 3
    assert second.next_cursor is None

    different = dca.SearchCriteria(
        mode="registration",
        registration="0714002653",
    )
    with pytest.raises(
        dca.DCASelectionError,
        match="does not match",
    ):
        dca.decode_cursor(first.next_cursor, different)


@pytest.mark.parametrize(
    "last_key",
    ["", "071400265300", "071400265300X"],
)
def test_cursor_rejects_malformed_building_key_as_invalid_cursor(last_key):
    criteria = dca.SearchCriteria(mode="registration", registration="0714")
    cursor = dca.encode_cursor(
        dca.CursorState(
            criteria_fingerprint=criteria.fingerprint,
            last_building_registration=last_key,
            emitted_count=1,
            observed_total=2,
        )
    )

    with pytest.raises(dca.DCASelectionError) as error:
        dca.decode_cursor(cursor, criteria)

    assert error.value.code == "invalid_cursor"


@pytest.mark.parametrize(
    ("emitted_count", "observed_total"),
    [(True, 2), (1, True)],
)
def test_cursor_rejects_boolean_counts(emitted_count, observed_total):
    criteria = dca.SearchCriteria(mode="registration", registration="0714")
    cursor = dca.encode_cursor(
        dca.CursorState(
            criteria_fingerprint=criteria.fingerprint,
            last_building_registration="0714002653001",
            emitted_count=emitted_count,
            observed_total=observed_total,
        )
    )

    with pytest.raises(dca.DCASelectionError) as error:
        dca.decode_cursor(cursor, criteria)

    assert error.value.code == "invalid_cursor"


def test_execute_classifies_malformed_cursor_as_invalid_cursor():
    criteria = dca.SearchCriteria(mode="registration", registration="0714")
    payload = {
        "version": dca.CURSOR_VERSION,
        "criteria_fingerprint": criteria.fingerprint,
        "last_building_registration": None,
        "emitted_count": 0,
        "observed_total": 2,
        "adapter_schema_fingerprint": dca.ADAPTER_SCHEMA_FINGERPRINT,
    }
    token = base64.urlsafe_b64encode(
        dca.canonical_json(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    args = dca.build_parser().parse_args(
        [
            "registration",
            "0714",
            "--cursor",
            f"{dca.CURSOR_PREFIX}{token}",
            "--minimum-interval",
            "0",
        ]
    )

    result = dca.execute(args, client=_client(), log_results=False)

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "invalid_cursor"


def test_cursor_does_not_expire_for_unrelated_lookup_catalog_changes():
    first = dca.SearchCriteria(
        mode="parcel",
        block="441",
        lot="61",
        county_name="Essex",
        county_id="fef3aaf2-63e4-e711-8125-1458d054d020",
        lookup_fingerprint="first-catalog-snapshot",
    )
    later = dca.SearchCriteria(
        mode="parcel",
        block="441",
        lot="61",
        county_name="Essex",
        county_id="fef3aaf2-63e4-e711-8125-1458d054d020",
        lookup_fingerprint="later-catalog-snapshot",
    )

    assert first.fingerprint == later.fingerprint


def test_multiple_count_drifts_keep_latest_observed_total():
    source = json.loads(
        (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
    )
    pages = [
        dca.parse_odata_page(
            {"odata.count": count, "value": [record]}
        )
        for count, record in zip(
            (3, 3, 1),
            source["value"],
            strict=True,
        )
    ]
    client = PageSequenceClient(pages)

    fetched = client.search(
        dca.SearchCriteria(mode="registration", registration="0714"),
        requested_limit=None,
        max_records=None,
        cursor=None,
    )

    assert fetched.observed_total == 3
    assert fetched.count_drift == {
        "initial_observed_total": 3,
        "latest_observed_total": 3,
        "changes": 2,
    }
    assert len(fetched.records) == 3


def test_normalization_preserves_building_and_property_identity_separately():
    page = _fixture_page()
    fetched = dca.SearchFetch(
        records=page.records,
        next_cursor=None,
        observed_total=3,
        emitted_count=3,
        pages_fetched=1,
        response_field_fingerprint=page.response_field_fingerprint,
    )
    records = [
        dca.normalize_building(record, fetch=fetched)
        for record in page.records
    ]

    assert records[1]["building_registration_number"] == "0714003383001"
    assert records[2]["building_registration_number"] == "0714003383002"
    assert records[1]["property_registration_number"] == "0714003383"
    assert records[2]["property_registration_number"] == "0714003383"
    assert records[1]["property_interest_id"] == records[2][
        "property_interest_id"
    ]
    assert records[1]["canonical_ref"] != records[2]["canonical_ref"]
    assert records[0]["parcel_coordinates"]["county_fips"] == "34013"
    assert records[0]["registered_owner"]["name"] == "NI PROPERTIES LLC"
    assert records[0]["registered_owner"]["role"].startswith(
        "DCA property-registration"
    )
    assert records[2]["building_address"]["aka"] == ["780 BROADWAY"]
    assert records[2]["building_registration_status"]["name"] == (
        "Vacant Boarded and Sealed"
    )
    assert records[0]["detail_url"].endswith(
        f"pid={dca.PROBE_PROPERTY_INTEREST_ID}"
    )


def test_canonical_identity_is_stable_when_county_metadata_changes():
    page = _fixture_page()
    fetched = dca.SearchFetch(
        records=page.records,
        next_cursor=None,
        observed_total=3,
        emitted_count=3,
        pages_fetched=1,
        response_field_fingerprint=page.response_field_fingerprint,
    )
    source = dict(page.records[0])
    without_county = dict(source)
    without_county["ultra_county"] = None

    with_county_record = dca.normalize_building(source, fetch=fetched)
    without_county_record = dca.normalize_building(
        without_county,
        fetch=fetched,
    )

    assert with_county_record["canonical_ref"] == without_county_record[
        "canonical_ref"
    ]
    assert "/34/building-registration/" in with_county_record["canonical_ref"]


def test_execute_registration_returns_bounded_result_and_cursor():
    args = dca.build_parser().parse_args(
        ["registration", "0714", "--limit", "2", "--minimum-interval", "0"]
    )

    result = dca.execute(args, client=_client(), log_results=False)

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert result.next_cursor
    assert result.records[0]["property_registration_number"] == "0714002653"
    assert result.records[0]["registered_owner_publication_state"] == (
        "published_in_search_index"
    )


def test_execute_parcel_resolves_county_from_official_form():
    source = json.loads(
        (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
    )
    bergen = json.loads(json.dumps(source["value"][0]))
    bergen["ultra_bhibuildingregistrationnum"] = "0714002653002"
    bergen["ultra_county"] = {
        "Id": "f4f3aaf2-63e4-e711-8125-1458d054d020",
        "Name": "BERGEN",
    }
    bergen["ultra_municipality"] = {
        "Id": "102c7521-162f-e811-8126-1458d04eb810",
        "Name": "NEW MILFORD BORO",
    }
    transport = FixtureTransport(rows=[source["value"][0], bergen])
    args = dca.build_parser().parse_args(
        [
            "parcel",
            "--county",
            "Essex County",
            "--block",
            "441",
            "--lot",
            "61",
            "--minimum-interval",
            "0",
        ]
    )

    result = dca.execute(
        args,
        client=_client(transport),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["building_registration_number"] == (
        "0714002653001"
    )
    odata_call = next(
        call for call in transport.calls if call["url"] == dca.ODATA_URL
    )
    assert "fef3aaf2-63e4-e711-8125-1458d054d020" in (
        odata_call["params"]["$filter"]
    )


def test_execute_address_filters_address_and_municipality():
    source = json.loads(
        (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
    )
    bergen = json.loads(json.dumps(source["value"][0]))
    bergen["ultra_bhibuildingregistrationnum"] = "0714002653002"
    bergen["ultra_county"] = {
        "Id": "f4f3aaf2-63e4-e711-8125-1458d054d020",
        "Name": "BERGEN",
    }
    bergen["ultra_municipality"] = {
        "Id": "102c7521-162f-e811-8126-1458d04eb810",
        "Name": "NEW MILFORD BORO",
    }
    transport = FixtureTransport(rows=[source["value"][0], bergen])
    args = dca.build_parser().parse_args(
        [
            "address",
            "BROADWAY",
            "--municipality",
            "Newark City",
            "--minimum-interval",
            "0",
        ]
    )

    result = dca.execute(
        args,
        client=_client(transport),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert [
        record["building_registration_number"] for record in result.records
    ] == ["0714002653001"]
    odata_call = next(
        call for call in transport.calls if call["url"] == dca.ODATA_URL
    )
    assert "ultra_addressline1" in odata_call["params"]["$filter"]
    assert "422d7521-162f-e811-8126-1458d04eb810" in (
        odata_call["params"]["$filter"]
    )


def test_execute_address_round_trips_escaped_odata_literal():
    source = json.loads(
        (FIXTURE_DIR / "search-results.json").read_text(encoding="utf-8")
    )
    record = json.loads(json.dumps(source["value"][0]))
    record["ultra_addressline1"] = "1 O'NEIL BROADWAY"
    transport = FixtureTransport(rows=[record])
    args = dca.build_parser().parse_args(
        ["address", "O'NEIL", "--minimum-interval", "0"]
    )

    result = dca.execute(
        args,
        client=_client(transport),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    odata_call = next(
        call for call in transport.calls if call["url"] == dca.ODATA_URL
    )
    assert "O''NEIL" in odata_call["params"]["$filter"]


def test_generic_address_without_municipality_does_not_load_lookups():
    args = dca.build_parser().parse_args(
        ["search", "--address", "Broadway"]
    )

    criteria = dca._criteria_from_args(args, ExplodingClient())

    assert criteria.mode == "address"
    assert criteria.address == "Broadway"
    assert criteria.lookup_fingerprint is None


def test_county_only_parcel_enumeration_remains_available():
    args = dca.build_parser().parse_args(
        ["parcel", "--county", "Essex County"]
    )

    criteria = dca._criteria_from_args(args, _client())

    assert criteria.mode == "parcel"
    assert criteria.block is None
    assert criteria.lot is None
    assert "ultra_county/Id eq guid" in dca.build_odata_filter(criteria)


def test_execute_empty_search_is_authoritative_no_results():
    args = dca.build_parser().parse_args(
        ["registration", "9999999999999", "--minimum-interval", "0"]
    )
    result = dca.execute(
        args,
        client=_client(FixtureTransport(rows=[])),
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert not result.records
    assert not result.errors


def test_max_records_is_an_explicit_partial_cap():
    args = dca.build_parser().parse_args(
        [
            "registration",
            "0714",
            "--max-records",
            "2",
            "--minimum-interval",
            "0",
        ]
    )
    result = dca.execute(args, client=_client(), log_results=False)

    assert result.status.value == "partial"
    assert len(result.records) == 2
    assert result.next_cursor
    assert any("max-records" in warning for warning in result.warnings)


def test_invalid_mixed_search_modes_are_explicit_failure_not_empty():
    args = dca.build_parser().parse_args(
        [
            "search",
            "--registration",
            "0714",
            "--address",
            "Broadway",
        ]
    )

    result = dca.execute(args, client=_client(), log_results=False)

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "mixed_search_modes"
    assert not result.records


class ExplodingClient:
    def __getattr__(self, name: str):
        raise AssertionError(f"network method accessed: {name}")


@pytest.mark.parametrize("command", ["manifest", "alternatives"])
def test_manifests_are_network_free(command):
    args = dca.build_parser().parse_args([command])

    result = dca.execute(
        args,
        client=ExplodingClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records


def test_source_manifest_keeps_operation_level_access_states_distinct():
    manifest = dca.source_manifest_record()
    access = manifest["operation_access"]

    assert access["search_registration"]["state"] == (
        "anonymous_machine_readable"
    )
    assert access["property_detail"]["state"] == "anonymous_html"
    assert access["detail_subgrids"]["state"] == (
        "anonymous_browser_session_post"
    )
    assert access["detail_subgrids"]["verification"]["state"] == (
        "browser_transport_observed"
    )
    assert access["published_certificates_and_documents"]["state"] == (
        "conditional_detail_interface"
    )
    assert "no sentinel document download" in access[
        "published_certificates_and_documents"
    ]["verification"]["observed"]
    assert access["registration_and_change_requests"]["state"] == (
        "interactive_portal_workflow"
    )


def test_alternatives_map_fields_and_gaps_instead_of_claiming_equivalence():
    routes = {
        record["source_id"]: record for record in dca.alternative_route_records()
    }

    assert set(routes) == {
        "us-nj-dca-bhi-active-buildings-opra",
        "us-nj-njgin-parcels-modiv",
        "us-nj-treasury-sr1a-sales",
        "us-nj-county-clerks-registers",
        "us-nj-local-assessors-tax-boards",
        "us-nj-opra-property-records",
    }
    assert "parcel geometry" in routes["us-nj-njgin-parcels-modiv"]["adds"]
    assert "grantor and grantee" in routes[
        "us-nj-treasury-sr1a-sales"
    ]["adds"]
    assert "deeds" in routes["us-nj-county-clerks-registers"]["adds"]
    bhi_opra = routes["us-nj-dca-bhi-active-buildings-opra"]
    assert "last cyclical inspection date" in bhi_opra["adds"]
    assert "active buildings" in bhi_opra["coverage"]
    assert bhi_opra["official_landing_url"] == dca.BHI_OFFICE_URL
    assert dca.DCA_OPRA_URL == "https://www.nj.gov/dca/home/opra.shtml"
    assert all(record["gap_relative_to_dca"] for record in routes.values())


def test_search_parser_has_no_hidden_default_result_ceiling():
    args = dca.build_parser().parse_args(
        ["registration", dca.PROBE_PROPERTY_REGISTRATION]
    )

    assert args.limit is None
    assert args.max_records is None
    assert args.cursor is None
