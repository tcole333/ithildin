from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlencode

import pytest

import tools.query_eugene_municipal_court as tyler
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_tyler_municipal_tenants"
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def page(name: str, url: str) -> tyler.FetchedHTML:
    text = fixture(name)
    return tyler.FetchedHTML(
        url=url,
        text=text,
        status_code=200,
        content_type="text/html; charset=utf-8",
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


class FakeResponse:
    def __init__(
        self,
        text: str,
        *,
        url: str,
        status_code: int = 200,
    ) -> None:
        self.text = text
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


class FakeSession:
    def __init__(self, responses: dict[str, str | FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        params=None,
        headers=None,
        timeout=None,
        allow_redirects=None,
    ) -> FakeResponse:
        del headers, timeout, allow_redirects
        full_url = f"{url}?{urlencode(params)}" if params else url
        self.calls.append(full_url)
        response = self.responses[url]
        if isinstance(response, FakeResponse):
            return response
        return FakeResponse(response, url=full_url)

    def close(self) -> None:
        return None


def client(
    tenant: tyler.MunicipalRecordSearchTenant,
    responses: dict[str, str | FakeResponse],
) -> tyler.EugeneMunicipalCourtClient:
    return tyler.EugeneMunicipalCourtClient(
        tenant=tenant,
        session=FakeSession(responses),
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
    )


def test_configured_oregon_tenants_preserve_identity_access_and_deep_probes():
    assert list(tyler.OREGON_TENANTS) == [
        "clackamas",
        "corvallis",
        "eugene",
        "grand-ronde",
        "hermiston",
        "linn-county",
        "medford",
        "springfield",
    ]
    assert tyler.HERMISTON_TENANT.verified_selectors == (
        "Name",
        "CitationNumber",
        "DocketNumber",
        "VehiclePlate",
    )
    assert tyler.LINN_COUNTY_TENANT.verified_selectors == (
        "Name",
        "CitationNumber",
    )
    assert tyler.MEDFORD_TENANT.observed_upcoming_docket_count == 141
    assert tyler.SPRINGFIELD_TENANT.observed_upcoming_docket_count == 155
    for tenant in (
        tyler.HERMISTON_TENANT,
        tyler.LINN_COUNTY_TENANT,
        tyler.MEDFORD_TENANT,
        tyler.SPRINGFIELD_TENANT,
    ):
        assert tenant.case_access_state == "public"
        assert tenant.docket_access_state == "public"
        assert tenant.verified_components == (
            "case_form",
            "docket_index",
            "docket_detail",
            "case_detail",
        )


@pytest.mark.parametrize(
    ("tenant", "fixture_name"),
    [
        (tyler.HERMISTON_TENANT, "hermiston_cases_form.html"),
        (tyler.LINN_COUNTY_TENANT, "linn_county_cases_form.html"),
        (tyler.MEDFORD_TENANT, "medford_cases_form.html"),
        (tyler.SPRINGFIELD_TENANT, "springfield_cases_form.html"),
    ],
)
def test_verified_selector_fixtures_match_each_direct_tenant_probe(
    tenant: tyler.MunicipalRecordSearchTenant,
    fixture_name: str,
):
    soup = tyler.BeautifulSoup(fixture(fixture_name), "html.parser")

    observed = tyler._search_options(
        soup,
        tenant.url("Cases"),
        tenant=tenant,
    )

    assert tuple(observed) == tenant.verified_selectors


def test_directory_claims_remain_separate_from_direct_access_verification():
    parsed = tyler.parse_tenant_directory(
        page("tenant_directory.html", tyler.HOST_URL + "/")
    )

    assert parsed["tenant_count"] == 9
    assert parsed["case_search_tenant_count"] == 9
    assert parsed["docket_tenant_count"] == 7
    assert len(parsed["oregon_tenants"]) == 8
    clackamas_entry = next(
        value
        for value in parsed["tenants"]
        if value["slug"] == tyler.CLACKAMAS_TENANT.slug
    )
    assert clackamas_entry["case_search"] is True
    assert clackamas_entry["upcoming_dockets"] is False
    assert parsed["directory_claims"][tyler.CLACKAMAS_TENANT.slug] == {
        "basis": "tenant_directory_navigation_link",
        "case_search_link": True,
        "upcoming_dockets_link": False,
        "direct_component_verification": False,
    }
    assert tyler.CLACKAMAS_TENANT.case_access_state == "login_required"
    assert tyler.CLACKAMAS_TENANT.docket_access_state == "not_found"


def test_renewable_directory_reconciliation_retains_all_rows_and_eight_configs():
    source_client = client(
        tyler.EUGENE_TENANT,
        {tyler.HOST_URL + "/": fixture("tenant_directory.html")},
    )

    records, refs = source_client.tenants()

    family, *configured = records
    assert family["tenant_count"] == 9
    assert len(family["tenants"]) == 9
    assert family["configured_missing_from_directory"] == []
    assert len(configured) == 8
    assert {record["tenant_slug"] for record in configured} == set(
        tyler.TENANTS_BY_SLUG
    )
    assert refs == (tyler.HOST_URL + "/",)


def test_medford_search_parser_has_no_eugene_identity_or_canonical_provenance():
    parsed = tyler.parse_case_search(
        page(
            "medford_case_search_results.html",
            tyler.MEDFORD_TENANT.url("Cases/Search")
            + "?SearchBy=CitationNumber",
        ),
        expected_search_by="CitationNumber",
        request_parameters={
            "SearchBy": "CitationNumber",
            "SearchByCriteria.CitationNumber": "M100",
        },
        tenant=tyler.MEDFORD_TENANT,
    )

    record = parsed.records[0]
    assert record["canonical_ref"] == (
        "STATECOURT:us-or-medford-municipal-record-search/"
        "or-medford-municipal-court/M100-01/case"
    )
    assert record["source_id"] == tyler.MEDFORD_TENANT.source_id
    assert record["court"]["name"] == "Medford Municipal Court"
    assert record["detail_url"].startswith(
        tyler.MEDFORD_TENANT.url("Cases/Detail")
    )
    assert record["source_provenance"]["tenant_slug"] == "medfordor"
    assert record["source_provenance"]["source_id"] == (
        tyler.MEDFORD_TENANT.source_id
    )


def test_hermiston_docket_index_and_detail_use_hermiston_provenance():
    index = tyler.parse_docket_index(
        page("hermiston_dockets.html", tyler.HERMISTON_TENANT.url("Dockets")),
        tenant=tyler.HERMISTON_TENANT,
    )
    detail = tyler.parse_docket_detail(
        page(
            "hermiston_docket_detail.html",
            tyler.HERMISTON_TENANT.url("Dockets/Detail"),
        ),
        native_date="20260730090000",
        calendar_code="ARR",
        room_code="1",
        tenant=tyler.HERMISTON_TENANT,
    )

    assert index.records[0]["source_id"] == tyler.HERMISTON_TENANT.source_id
    assert index.records[0]["court"]["court_id"] == (
        tyler.HERMISTON_TENANT.court_id
    )
    assert detail.record["canonical_ref"].startswith(
        "STATECOURT:us-or-hermiston-municipal-record-search/"
        "or-hermiston-municipal-court/"
    )
    assert detail.record["cases"][0]["case_ref"].endswith("/H200-01/case")
    assert detail.record["source_provenance"]["tenant_slug"] == "hermistonor"


def test_medford_case_detail_builds_medford_routes_and_request_complement():
    parsed = tyler.parse_case_detail(
        page(
            "medford_case_detail.html",
            tyler.MEDFORD_TENANT.url("Cases/Detail")
            + "?citationNumber=M100&violationNumber=01",
        ),
        citation_number="M100",
        violation_number="01",
        tenant=tyler.MEDFORD_TENANT,
    )

    record = parsed.record
    assert record["source_id"] == tyler.MEDFORD_TENANT.source_id
    assert record["detail_url"].startswith(
        tyler.MEDFORD_TENANT.url("Cases/Detail")
    )
    assert record["court"]["county_fips"] == "41029"
    assert record["related_routes"]["documents"].startswith(
        tyler.MEDFORD_TENANT.base_url
    )
    assert record["document_request"] == {
        "kind": "official_alternative_routes",
        "routes": [],
        "distinct_from_case_index": True,
    }


def test_grand_ronde_is_attributed_to_the_tribal_court_and_audiences_stay_distinct():
    tenant = tyler.GRAND_RONDE_TENANT
    court = tyler._court_payload(tenant)
    chain = tyler._official_chain(tenant)
    routes = {
        str(route["role"]): route for route in tenant.alternative_routes
    }

    assert tenant.source_id == "us-tribal-grand-ronde-record-search"
    assert tenant.jurisdiction_id == "tribal:grand-ronde"
    assert court["court_type"] == "tribal_court"
    assert court["court_level"] == "tribal"
    assert court["county_fips"] is None
    assert not any(item["role"] == "state_official_registry" for item in chain)
    assert routes["tribal_court_records_request_form"]["audience"] == (
        "court_record_requesters"
    )
    assert routes["tribal_records_center_request_form"]["audience"] == (
        "tribal_members"
    )


def _login_response(tenant: tyler.MunicipalRecordSearchTenant) -> FakeResponse:
    return FakeResponse(
        fixture("login.html"),
        url=(
            f"{tyler.HOST_URL}/Account/Login?"
            f"returnUrl=%2F{tenant.slug}%2FCases"
        ),
    )


def test_login_gated_tenants_probe_to_observed_states_and_keep_alternatives():
    corvallis = client(
        tyler.CORVALLIS_TENANT,
        {
            tyler.CORVALLIS_TENANT.url("Cases"): _login_response(
                tyler.CORVALLIS_TENANT
            ),
            tyler.CORVALLIS_TENANT.url("Dockets"): _login_response(
                tyler.CORVALLIS_TENANT
            ),
        },
    )
    corvallis_probe, _ = corvallis.probe()

    assert corvallis_probe["component_access"]["cases"]["state"] == (
        "login_required"
    )
    assert corvallis_probe["component_access"]["dockets"]["state"] == (
        "login_required"
    )
    corvallis_roles = {
        route["role"]
        for route in corvallis_probe["request_complement"]["routes"]
    }
    assert {
        "city_public_records_request_form",
        "city_records_archive",
        "municipal_court_payment_and_violation_lookup",
    }.issubset(corvallis_roles)

    clackamas = client(
        tyler.CLACKAMAS_TENANT,
        {
            tyler.CLACKAMAS_TENANT.url("Cases"): _login_response(
                tyler.CLACKAMAS_TENANT
            ),
            tyler.CLACKAMAS_TENANT.url("Dockets"): FakeResponse(
                "not found",
                url=tyler.CLACKAMAS_TENANT.url("Dockets"),
                status_code=404,
            ),
        },
    )
    clackamas_probe, _ = clackamas.probe()

    assert clackamas_probe["component_access"]["cases"]["state"] == (
        "login_required"
    )
    assert clackamas_probe["component_access"]["dockets"]["state"] == "not_found"
    clackamas_roles = {
        route["role"]
        for route in clackamas_probe["request_complement"]["routes"]
    }
    assert "justice_court_public_records_request_form" in clackamas_roles
    assert "county_public_records_routing" in clackamas_roles


def test_cli_tenant_selection_changes_query_and_result_identity(monkeypatch):
    monkeypatch.setattr(tyler, "log_search", lambda *args, **kwargs: None)
    args = tyler.build_parser().parse_args(
        [
            "search",
            "--citation",
            "M100",
            "--tenant",
            "medford",
        ]
    )
    source_client = client(
        tyler.MEDFORD_TENANT,
        {
            tyler.MEDFORD_TENANT.url("Cases/Search"): fixture(
                "medford_case_search_results.html"
            )
        },
    )

    result = tyler.execute(args, client=source_client)

    assert result.status == ResultStatus.OK
    assert result.query.source.source_id == tyler.MEDFORD_TENANT.source_id
    assert result.query.jurisdiction.county_fips == "41029"
    assert result.query.query.parameters["tenant_slug"] == "medfordor"
    assert result.records[0]["source_id"] == tyler.MEDFORD_TENANT.source_id


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official Oregon tenant probes",
)
@pytest.mark.parametrize(
    "tenant",
    [
        tyler.HERMISTON_TENANT,
        tyler.LINN_COUNTY_TENANT,
        tyler.MEDFORD_TENANT,
        tyler.SPRINGFIELD_TENANT,
    ],
)
def test_live_public_tenant_case_and_docket_probe(tenant):
    source_client = tyler.EugeneMunicipalCourtClient(
        tenant=tenant,
        minimum_interval=0.4,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    try:
        record, _ = source_client.probe()
    finally:
        source_client.close()

    assert record["component_access"]["cases"]["state"] == "public"
    assert record["component_access"]["dockets"]["state"] == "public"
    assert tuple(record["available_search_options"]) == tenant.verified_selectors
    assert record["upcoming_docket_count"] > 0


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official gated-tenant probes",
)
@pytest.mark.parametrize(
    ("tenant", "case_state", "docket_state"),
    [
        (tyler.CLACKAMAS_TENANT, "login_required", "not_found"),
        (tyler.CORVALLIS_TENANT, "login_required", "login_required"),
        (tyler.GRAND_RONDE_TENANT, "login_required", "login_required"),
    ],
)
def test_live_gated_tenant_component_states(tenant, case_state, docket_state):
    source_client = tyler.EugeneMunicipalCourtClient(
        tenant=tenant,
        minimum_interval=0.4,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    try:
        record, _ = source_client.probe()
    finally:
        source_client.close()

    assert record["component_access"]["cases"]["state"] == case_state
    assert record["component_access"]["dockets"]["state"] == docket_state
    assert record["request_complement"]["routes"]


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for an official Medford deep-path probe",
)
def test_live_medford_docket_detail_and_case_detail():
    source_client = tyler.EugeneMunicipalCourtClient(
        tenant=tyler.MEDFORD_TENANT,
        minimum_interval=0.4,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    try:
        sessions = source_client.dockets()
        detail = None
        for session in sessions.records[:5]:
            candidate = source_client.docket(
                native_date=session["native_date"],
                calendar_code=session["calendar_code"],
                room_code=session["room_code"],
            )
            if candidate.record["cases"]:
                detail = candidate
                break
        assert detail is not None
        first_case = detail.record["cases"][0]
        case = source_client.case(
            citation_number=first_case["citation_number"],
            violation_number=first_case["violation_number"],
        )
    finally:
        source_client.close()

    assert detail.record["source_id"] == tyler.MEDFORD_TENANT.source_id
    assert case.record["source_id"] == tyler.MEDFORD_TENANT.source_id
