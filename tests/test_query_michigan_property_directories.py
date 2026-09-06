from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_michigan_property_directories as directory
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "michigan_property_directory"
)
DIRECTORY_HTML = (FIXTURE_DIR / "directory.html").read_text(encoding="utf-8")
SOURCE_CHANGED_HTML = (FIXTURE_DIR / "source_changed.html").read_text(
    encoding="utf-8"
)


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = DIRECTORY_HTML
    url: str = directory.DIRECTORY_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=utf-8"}
    )


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Michigan directory request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(
        self,
        page: directory.MichiganPropertyDirectoryPage,
    ) -> None:
        self.page = page
        self.calls = 0

    def fetch(self) -> directory.MichiganPropertyDirectoryPage:
        self.calls += 1
        return self.page


def parse_args(*values: str) -> argparse.Namespace:
    return directory.build_parser().parse_args(list(values))


def fixture_page() -> directory.MichiganPropertyDirectoryPage:
    return directory.parse_directory_page(
        DIRECTORY_HTML,
        require_complete=False,
    )


def full_page() -> directory.MichiganPropertyDirectoryPage:
    base = fixture_page()
    template = dict(base.records[0])
    records = []
    for county in directory.COUNTY_NAMES:
        county_fips = directory.COUNTY_FIPS[county]
        record = dict(template)
        record.update(
            {
                "canonical_ref": (
                    f"MI-DTMB-TAX-PARCEL-DIRECTORY:{county_fips}"
                ),
                "evidence_ref": (
                    f"MI-DTMB-TAX-PARCEL-DIRECTORY:{county_fips}"
                ),
                "county": county,
                "county_label": f"{county} County",
                "county_fips": county_fips,
            }
        )
        route = dict(template["route"])
        route.update(
            {
                "url": f"https://{county_fips}.example.test/parcels",
                "official_url": f"https://{county_fips}.example.test/parcels",
                "canonical_url_without_fragment": (
                    f"https://{county_fips}.example.test/parcels"
                ),
                "host": f"{county_fips}.example.test",
                "platform_family": "county_or_local_web",
            }
        )
        record["route"] = route
        record["official_url"] = route["url"]
        records.append(record)
    overrides = {
        "Arenac": (
            "https://bsaonline.com/?uid=1942",
            "bsaonline.com",
            "bsa_online",
            ["multi_role_property_platform"],
        ),
        "Genesee": (
            "https://www.geneseecountymi.gov/departments/register_of_deeds/online_records_search.php",
            "www.geneseecountymi.gov",
            "county_or_local_web",
            ["recording_office"],
        ),
    }
    by_county = {str(record["county"]): record for record in records}
    for county, (url, host, platform, signals) in overrides.items():
        record = by_county[county]
        record["official_url"] = url
        route = dict(record["route"])
        route.update(
            {
                "url": url,
                "canonical_url_without_fragment": url,
                "host": host,
                "platform_family": platform,
            }
        )
        record["route"] = route
        triage = dict(record["destination_triage"])
        triage["route_signals"] = signals
        record["destination_triage"] = triage
    return directory.MichiganPropertyDirectoryPage(
        records=tuple(records),
        source_url=base.source_url,
        source_statement=base.source_statement,
        schema_fingerprint=base.schema_fingerprint,
        snapshot_fingerprint=base.snapshot_fingerprint,
    )


def test_county_mapping_is_complete_unique_and_matches_known_geoids() -> None:
    assert len(directory.COUNTY_NAMES) == 83
    assert len(directory.COUNTY_FIPS) == 83
    assert len(set(directory.COUNTY_FIPS.values())) == 83
    assert directory.COUNTY_FIPS["Alcona"] == "26001"
    assert directory.COUNTY_FIPS["Genesee"] == "26049"
    assert directory.COUNTY_FIPS["Oakland"] == "26125"
    assert directory.COUNTY_FIPS["Wayne"] == "26163"
    assert directory.COUNTY_FIPS["Wexford"] == "26165"


def test_parser_preserves_links_and_separates_declared_from_verified_roles() -> None:
    page = fixture_page()

    assert len(page.records) == 5
    alcona = page.records[0]
    assert alcona["record_kind"] == "county_tax_parcel_route"
    assert alcona["county_fips"] == "26001"
    assert len(alcona["route"]["published_links"]) == 3
    assert len(alcona["route"]["published_unique_urls"]) == 1
    assert alcona["publisher_declared_role"]["role"] == "parcel_geometry"
    assert (
        alcona["role_separation"]["assessment_roll"]
        == "not_established_by_directory"
    )
    assert (
        alcona["destination_triage"]["signals_are_verified_capabilities"]
        is False
    )
    assert len(page.schema_fingerprint) == 64
    assert len(page.snapshot_fingerprint) == 64


def test_parser_detects_platforms_partial_coverage_and_role_mismatch() -> None:
    records = {str(record["county"]): record for record in fixture_page().records}

    assert records["Arenac"]["route"]["platform_family"] == "bsa_online"
    assert records["Iron"]["publisher_declared_role"]["coverage_note"] == (
        "partial coverage"
    )
    assert "publisher_reports_partial_coverage" in records["Iron"][
        "destination_triage"
    ]["review_flags"]
    assert "recording_office" in records["Genesee"]["destination_triage"][
        "route_signals"
    ]
    assert "parcel_map_or_gis" not in records["Genesee"][
        "destination_triage"
    ]["route_signals"]
    assert (
        "declared_parcel_role_destination_signal_mismatch"
        in records["Genesee"]["destination_triage"]["review_flags"]
    )
    assert (
        directory._platform_family(
            "https://home-ecgis.hub.arcgis.com/datasets/example"
        )
        == "arcgis_hub"
    )


def test_complete_validation_reports_missing_counties() -> None:
    with pytest.raises(
        directory.MichiganPropertyDirectoryChangedError
    ) as raised:
        directory.parse_directory_page(DIRECTORY_HTML)

    assert raised.value.code == "directory_coverage_changed"
    assert raised.value.details["observed_count"] == 5
    assert "Alger" in raised.value.details["missing_counties"]


def test_source_changed_semantics_is_not_an_empty_result() -> None:
    with pytest.raises(
        directory.MichiganPropertyDirectoryChangedError
    ) as raised:
        directory.parse_directory_page(
            SOURCE_CHANGED_HTML,
            require_complete=False,
        )

    assert raised.value.code == "directory_semantics_changed"
    assert raised.value.status is ResultStatus.SOURCE_CHANGED


def test_access_denied_is_explicit() -> None:
    with pytest.raises(directory.MichiganPropertyDirectoryError) as raised:
        directory.parse_directory_page(
            "<html><title>Access Denied</title>"
            "You don't have permission to access this page. "
            "errors.edgesuite.net</html>",
            require_complete=False,
        )

    assert raised.value.code == "access_denied"
    assert raised.value.status is ResultStatus.RESTRICTED


def test_client_retries_transient_response_and_uses_browser_headers() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse(text=DIRECTORY_HTML),
        ]
    )
    delays: list[float] = []
    client = directory.MichiganPropertyDirectoryClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=2, backoff_initial=0.01),
        sleeper=delays.append,
    )

    with pytest.raises(directory.MichiganPropertyDirectoryChangedError):
        client.fetch()

    assert len(session.calls) == 2
    assert delays == [0.01]
    assert session.headers["User-Agent"] == directory.DEFAULT_USER_AGENT
    assert "text/html" in session.headers["Accept"]


def test_list_accepts_name_county_suffix_and_fips_selectors() -> None:
    page = full_page()
    by_name = directory.execute(
        parse_args("list", "--county", "Oakland County"),
        client=FakeClient(page),
        log_results=False,
    )
    by_geoid = directory.execute(
        parse_args("list", "--county", "26125"),
        client=FakeClient(page),
        log_results=False,
    )
    by_county_code = directory.execute(
        parse_args("list", "--county", "125"),
        client=FakeClient(page),
        log_results=False,
    )

    assert [record["county"] for record in by_name.records] == ["Oakland"]
    assert [record["county"] for record in by_geoid.records] == ["Oakland"]
    assert [record["county"] for record in by_county_code.records] == [
        "Oakland"
    ]
    assert by_name.next_cursor is None


def test_search_and_platform_filters_return_authoritative_empty() -> None:
    page = full_page()
    matched = directory.execute(
        parse_args("search", "bsaonline"),
        client=FakeClient(page),
        log_results=False,
    )
    empty = directory.execute(
        parse_args("search", "no-such-platform-or-county"),
        client=FakeClient(page),
        log_results=False,
    )

    assert [record["county"] for record in matched.records] == ["Arenac"]
    assert empty.status is ResultStatus.NO_RESULTS
    assert empty.records == ()


def test_local_pagination_is_query_and_snapshot_bound() -> None:
    page = full_page()
    first = directory.execute(
        parse_args("list", "--limit", "2"),
        client=FakeClient(page),
        log_results=False,
    )
    second = directory.execute(
        parse_args(
            "list",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=FakeClient(page),
        log_results=False,
    )
    wrong_query = directory.execute(
        parse_args(
            "list",
            "--county",
            "Oakland",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=FakeClient(page),
        log_results=False,
    )

    assert [record["county"] for record in first.records] == [
        "Alcona",
        "Alger",
    ]
    assert first.next_cursor is not None
    assert [record["county"] for record in second.records] == [
        "Allegan",
        "Alpena",
    ]
    assert second.next_cursor is not None
    assert wrong_query.status is ResultStatus.SOURCE_CHANGED
    assert wrong_query.errors[0].code == "cursor_query_mismatch"


def test_invalid_limit_and_cursor_are_structured_pagination_errors() -> None:
    page = full_page()
    limit = directory.execute(
        parse_args("list", "--limit", "0"),
        client=FakeClient(page),
        log_results=False,
    )
    cursor = directory.execute(
        parse_args("list", "--cursor", "not-a-directory-cursor"),
        client=FakeClient(page),
        log_results=False,
    )

    assert limit.status is ResultStatus.UNAVAILABLE
    assert limit.errors[0].code == "invalid_limit"
    assert limit.errors[0].category == "pagination"
    assert cursor.status is ResultStatus.UNAVAILABLE
    assert cursor.errors[0].code == "invalid_cursor"
    assert cursor.errors[0].category == "pagination"


def test_unknown_county_and_platform_are_structured_query_errors() -> None:
    page = full_page()
    county = directory.execute(
        parse_args("list", "--county", "Atlantis"),
        client=FakeClient(page),
        log_results=False,
    )
    platform = directory.execute(
        parse_args("list", "--platform", "mystery-stack"),
        client=FakeClient(page),
        log_results=False,
    )

    assert county.status is ResultStatus.UNAVAILABLE
    assert county.errors[0].code == "unknown_county"
    assert county.errors[0].category == "query_selection"
    assert platform.status is ResultStatus.UNAVAILABLE
    assert platform.errors[0].code == "unknown_platform"


def test_manifest_sources_and_alternatives_are_network_free_and_role_specific() -> None:
    client = FakeClient(fixture_page())
    sources = directory.execute(
        parse_args("sources"),
        client=client,
        log_results=False,
    )
    manifest = directory.execute(
        parse_args("manifest"),
        client=client,
        log_results=False,
    )
    alternatives = directory.execute(
        parse_args("alternatives"),
        client=client,
        log_results=False,
    )

    assert client.calls == 0
    assert sources.records[0]["coverage"]["county_count"] == 83
    assert sources.records[0]["coverage"]["statewide_data_download"] is False
    assert manifest.records[0]["operations"]["network_free"] == (
        "sources",
        "manifest",
        "alternatives",
    )
    assert manifest.records[0]["role_matrix"]["land_records_index"][
        "primary_route"
    ] == "county_register_of_deeds"
    assert len(manifest.records[0]["official_alternatives"]) == 7
    by_id = {
        str(record["alternative_id"]): record
        for record in alternatives.records
    }
    assert (
        by_id["us-mi-treasury-register-of-deeds-directory"]["roles"]
        == ("land_records_office_directory",)
    )
    assert by_id["us-mi-dnr-lots-parcels"]["coverage"] == (
        "dnr_land_ownership_tracking_system"
    )
    assert "current_tax_parcel_layer" in by_id[
        "us-mi-dtmb-mi-plats-imagery"
    ]["not_equivalent_to"]


def test_platform_summary_supports_reusable_family_triage() -> None:
    result = directory.execute(
        parse_args("platforms"),
        client=FakeClient(full_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    by_platform = {
        str(record["platform_family"]): record
        for record in result.records
    }
    assert by_platform["county_or_local_web"]["county_count"] == 82
    assert by_platform["bsa_online"]["counties"] == ("Arenac",)


def test_discovery_preserves_evidence_strength_and_review_fields() -> None:
    result = directory.execute(
        parse_args("discovery", "--county", "Genesee"),
        client=FakeClient(full_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    candidate = result.records[0]
    assert candidate["candidate_kind"] == "official_county_tax_parcel_route"
    assert candidate["registry_identity"]["county_fips"] == "26049"
    assert candidate["capability_evidence"]["publisher_declared_roles"] == (
        "parcel_geometry",
    )
    assert candidate["capability_evidence"]["destination_verified_roles"] == ()
    assert "recording_office" in candidate["capability_evidence"][
        "route_signals"
    ]
    assert "tax_bill_balance_payment_and_delinquency" in candidate[
        "assessment_fields"
    ]


def test_probe_verifies_complete_coverage_and_platform_sentinels() -> None:
    result = directory.execute(
        parse_args("probe"),
        client=FakeClient(full_page()),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["county_count"] == 83
    assert probe["county_fips_count"] == 83
    assert probe["sentinels"]["Arenac"]["platform_family"] == "bsa_online"
    assert probe["sentinels"]["Genesee"]["county_fips"] == "26049"
    assert probe["sentinels"]["Oakland"]["county_fips"] == "26125"


def test_result_envelope_round_trips_as_json_safe_data() -> None:
    result = directory.execute(
        parse_args("list", "--county", "Alcona"),
        client=FakeClient(full_page()),
        log_results=False,
    )
    payload = result.to_dict()

    assert payload["status"] == "ok"
    assert payload["query"]["source"]["source_id"] == directory.SOURCE_ID
    assert payload["records"][0]["canonical_ref"].endswith(":26001")
    assert json_safe(payload)


def json_safe(value: Any) -> bool:
    import json

    json.dumps(value, allow_nan=False)
    return True
