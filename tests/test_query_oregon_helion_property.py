from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from tools import query_oregon_helion_property as pso
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = (
    Path(__file__).parent / "fixtures" / "public_records" / "oregon_helion_property"
)


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


class FixtureClient:
    def __init__(self) -> None:
        self.pages = {
            1: _fixture("search_morrow_smith_page1.json"),
            2: _fixture("search_morrow_smith_page2.json"),
        }
        self.detail_payload = _fixture("detail_morrow_171.json")
        self.probe_payload = _fixture("probe_tillamook.json")
        self.search_calls: list[tuple[str, str, str, int]] = []

    def search(
        self,
        tenant: pso.PropertyTenant,
        *,
        search_option: str,
        query: str,
        page: int,
    ) -> Mapping[str, Any]:
        self.search_calls.append((tenant.source_id, search_option, query, page))
        return self.pages[page]

    def detail(
        self,
        tenant: pso.PropertyTenant,
        *,
        account: str,
        roll_type: str,
    ) -> Mapping[str, Any]:
        assert tenant.source_id == "us-or-morrow-helion-property"
        assert account == "171"
        assert roll_type == "R"
        return self.detail_payload

    def probe(self, tenant: pso.PropertyTenant) -> Mapping[str, Any]:
        assert tenant.source_id == "us-or-tillamook-helion-property"
        return self.probe_payload

    def close(self) -> None:
        return None


def _args(*values: str):
    return pso.build_parser().parse_args(list(values))


def test_seven_tenants_remain_distinct_county_sources() -> None:
    assert len(pso.TENANTS) == 7
    assert len({tenant.source_id for tenant in pso.TENANTS}) == 7
    assert {tenant.county_fips for tenant in pso.TENANTS} == {
        "41059",
        "41049",
        "41053",
        "41057",
        "41009",
        "41011",
        "41003",
    }
    assert all(
        tenant.source.metadata["platform_family"] == pso.PLATFORM_FAMILY
        for tenant in pso.TENANTS
    )


def test_tenant_native_options_and_complements_are_explicit() -> None:
    columbia = pso.TENANTS_BY_SOURCE["us-or-columbia-helion-property"]
    coos = pso.TENANTS_BY_SOURCE["us-or-coos-helion-property"]
    tillamook = pso.TENANTS_BY_SOURCE["us-or-tillamook-helion-property"]
    benton = pso.TENANTS_BY_SOURCE["us-or-benton-helion-property"]

    assert columbia.search_options == {
        "account": "TaxAccountId",
        "name": "Name",
        "address": "Address",
        "map": "Map",
    }
    assert "legal" not in coos.search_options
    assert {complement["kind"] for complement in columbia.complements} == {
        "columbia_current_noncertified_webmaps",
        "columbia_certified_tax_roll_data",
        "columbia_quarterly_property_sales",
    }
    assert {complement["kind"] for complement in tillamook.complements} >= {
        "tillamook_prior_assessment_tax_rolls",
        "tillamook_tax_maps",
        "tillamook_sales_data",
        "tillamook_real_property_tax_foreclosure",
        "tillamook_county_real_property_sales",
    }
    assert (
        tillamook.access_observation["blazor_transport"]
        == "long_polling_after_websocket_handshake_200"
    )
    assert benton.search_options["legal"] == "Legal"
    assert {complement["kind"] for complement in benton.complements} == {
        "benton_assessment_search_and_history",
        "benton_taxlot_owner_arcgis_and_bulk",
        "benton_helion_recorder",
    }


def test_source_operation_returns_observed_metadata_without_browser() -> None:
    decision = {
        "source_id": "us-or-columbia-helion-property",
        "allowed": True,
        "automation_disposition": "allowed",
    }
    result = pso.execute(
        _args(
            "source",
            "--source",
            "us-or-columbia-helion-property",
        ),
        client=FixtureClient(),
        access_decision=decision,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert result.query.query.metadata["access_decision"] == decision
    record = result.to_dict()["records"][0]
    assert record["county_fips"] == "41009"
    assert record["native_search_options"]["account"] == "TaxAccountId"
    assert record["access_observation"]["outcome"] == ("public_search_and_detail_ready")


def test_search_normalizes_cards_and_resumes_from_bound_anchor() -> None:
    client = FixtureClient()
    first = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    assert first.status == ResultStatus.OK
    assert first.next_cursor
    first_records = first.to_dict()["records"]
    assert [record["native_account_id"] for record in first_records] == [
        "60316",
        "65471",
    ]
    assert first_records[0]["map_taxlot"] == "4N251700 01003"
    assert first_records[0]["owners"] == [{"raw_name": "70004 PAUL SMITH RD LLC"}]
    assert first_records[0]["tax_state"]["current_balance_due"] == "0.00"

    second = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert second.status == ResultStatus.OK
    assert [record["native_account_id"] for record in second.to_dict()["records"]] == [
        "6297",
        "7936",
    ]
    coverage = second.to_dict()["records"][0]["search_metadata"]["coverage"]
    assert coverage["cursor_anchor_verified"] is True
    assert coverage["first_returned_page"] == 1
    assert coverage["last_returned_page"] == 2
    assert client.search_calls == [
        ("us-or-morrow-helion-property", "Name", "smith", 1),
        ("us-or-morrow-helion-property", "Name", "smith", 1),
        ("us-or-morrow-helion-property", "Name", "smith", 2),
    ]


def test_cursor_is_bound_to_query_and_tenant() -> None:
    client = FixtureClient()
    first = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    assert first.next_cursor

    query_mismatch = pso.execute(
        _args(
            "search",
            "jones",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert query_mismatch.status == ResultStatus.SOURCE_CHANGED
    assert query_mismatch.errors[0].code == "cursor_query_mismatch"

    source_mismatch = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "name",
            "--source",
            "us-or-umatilla-helion-property",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert source_mismatch.status == ResultStatus.SOURCE_CHANGED
    assert source_mismatch.errors[0].code == "cursor_source_mismatch"


def test_detail_preserves_assessment_tax_payoff_sales_and_improvements() -> None:
    result = pso.execute(
        _args(
            "detail",
            "171",
            "--roll-type",
            "R",
            "--source",
            "us-or-morrow-helion-property",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["record_kind"] == "property_account"
    assert record["native_account_id"] == "171"
    assert record["map_taxlot"] == "2S2627-DA-02000"
    assert record["owners"] == [
        {
            "raw_name": "LESPERANCE, GLORENE WRIGHT ET AL",
            "role": "OWNER",
        }
    ]
    assert record["mailing_address"]["address_lines"][-1] == ("HEPPNER OR 97836-0887")
    assert record["assessment"]["real_market_value"] == "111680"
    assert record["assessment"]["maximum_assessed_value"] == "47420"
    assert record["assessment"]["assessed_value"] == "47420"
    assert record["tax_state"]["current_balance_due"] == "729.21"
    assert record["tax_state"]["payoff"]["tax_id"] == "171"
    assert record["tax_state"]["payoff"]["as_of_date"] == "2026-07-29"
    assert (
        record["tax_state"]["payoff"]["amount_due_by_month"][1]["payoff_amount"]
        == "738.43"
    )
    assert record["sale_history"][0]["sale_date"] == "1996-03-21"
    assert record["sale_history"][0]["sale_price"] == "25000"
    assert record["improvements"][0]["year_built"] == 1978
    assert record["improvements"][0]["livable_size"] == 1056
    assert record["physical_characteristics"]["legal_description"].startswith(
        "MT VERNON'S ADDITION"
    )
    assert len(record["documents"]) == 2
    assert len(record["response_schema_fingerprint"]) == 64


def test_tillamook_probe_reports_observed_long_polling_fallback() -> None:
    result = pso.execute(
        _args(
            "probe",
            "--source",
            "us-or-tillamook-helion-property",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["live_probe"]["access_outcome"] == "search_form_ready"
    assert record["live_probe"]["transport_events"] == [
        "websocket_failed",
        "long_polling_fallback",
    ]
    assert record["search_option_match"]["Legal"] == "Legal"


def test_unavailable_tenant_selector_is_an_explicit_outcome() -> None:
    client = FixtureClient()
    result = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "legal",
            "--source",
            "us-or-columbia-helion-property",
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "search_field_not_available"
    assert list(result.errors[0].details["available_fields"]) == [
        "account",
        "name",
        "address",
        "map",
    ]
    assert client.search_calls == []


def test_authoritative_empty_is_not_transport_failure() -> None:
    class EmptyClient(FixtureClient):
        def search(self, tenant, *, search_option, query, page):
            return {
                "ok": True,
                "operation": "search",
                "search_option": search_option,
                "search_value": query,
                "page_number": page,
                "total_pages": 1,
                "authoritative_empty": True,
                "records": [],
            }

    result = pso.execute(
        _args(
            "search",
            "unlikely-name",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
        ),
        client=EmptyClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.NO_RESULTS
    assert result.errors == ()


def test_browser_failure_never_becomes_no_results() -> None:
    class FailedClient(FixtureClient):
        def search(self, tenant, *, search_option, query, page):
            raise pso.BrowserHelperError(
                "source_http_503",
                "portal returned HTTP 503",
                details={"status_code": 503},
                retryable=True,
            )

    result = pso.execute(
        _args(
            "search",
            "smith",
            "--field",
            "name",
            "--source",
            "us-or-morrow-helion-property",
        ),
        client=FailedClient(),
        log_results=False,
    )
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "source_http_503"
    assert result.errors[0].retryable is True
