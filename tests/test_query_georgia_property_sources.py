from __future__ import annotations

from typing import Any

from tools import query_georgia_property_sources as georgia


def _artifact(
    content: str,
    url: str,
) -> georgia.Artifact:
    return georgia.Artifact(
        content=content.encode(),
        source_url=url,
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


def _directory_artifact() -> georgia.Artifact:
    rows = []
    for county in georgia.COUNTY_NAMES:
        if county == "White":
            continue
        slug = county.casefold().replace(" ", "")
        primary = f"http://qpublic.net/ga/{slug}/"
        description = f"http://www.qpublic.net/ga/{slug}/"
        if county == "Atkinson":
            primary = "http://www.qpublic.net/ga/atkinson/index.html"
            description = "http://www.qpublic.net/ga/bacon/"
        if county == "Dawson":
            primary = (
                "https://qpublic.schneidercorp.com/Application.aspx?"
                "App=DawsonCountyGA&Layer=Parcels&PageType=Search"
            )
            description = primary
        if county == "Fulton":
            primary = "https://fultonassessor.org/"
            description = primary
        rows.append(
            "<tr>"
            f'<td><a href="{primary}">{county}</a></td>'
            f'<td><a href="{description}">{description}</a></td>'
            "</tr>"
        )
    return _artifact(
        (
            "<html><head><title>Property Records Online</title></head>"
            "<body><h1>Property Records Online</h1>"
            '<table id="datatable"><thead><tr>'
            "<th>Link</th><th>Description</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></body></html>"
        ),
        georgia.DIRECTORY_URL,
    )


def _information_artifact() -> georgia.Artifact:
    return _artifact(
        """
        <html><title>Real Estate Index</title><body>
        <h1>Search Systems Real Estate Index</h1>
        <p>Each county maintains the official deed, lien and plat dockets.
        The Authority provides access to documents filed in all counties in
        Georgia. The deed index covers transactions since at least January 1,
        1999. Searches return names of the parties, property location, and
        book and page. Historical data is continually being added.</p>
        </body></html>
        """,
        georgia.GSCCCA_INFORMATION_URL,
    )


def _limited_artifact() -> georgia.Artifact:
    return _artifact(
        """
        <html><title>Limited Use</title><body>
        <h1>Limited-Use Account Charges</h1>
        <p>Users can search the Deed, Lien, Plat, and UCC indexes.</p>
        <p>There is no cost to create a Limited-Use account and there is no
        recurring monthly fee.</p>
        <ul><li>Cannot view images</li></ul>
        </body></html>
        """,
        georgia.GSCCCA_LIMITED_USE_URL,
    )


def _gate_artifact() -> georgia.Artifact:
    return _artifact(
        """
        <html><body>
        <form method="post"
          action="https://apps.gsccca.org/login.asp?Redirect=/realestate/names.asp">
          <input type="hidden" name="sFormAction" value="DeedNamesGo">
        </form>
        </body></html>
        """,
        georgia.GSCCCA_LOGIN_GATE_URL,
    )


class FixtureClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str) -> georgia.Artifact:
        self.calls.append(url)
        if url == georgia.DIRECTORY_URL:
            return _directory_artifact()
        if url == georgia.GSCCCA_INFORMATION_URL:
            return _information_artifact()
        if url == georgia.GSCCCA_LIMITED_USE_URL:
            return _limited_artifact()
        if url == georgia.GSCCCA_LOGIN_GATE_URL:
            return _gate_artifact()
        raise AssertionError(f"unexpected URL {url}")


def _args(*values: str) -> Any:
    return georgia.build_parser().parse_args(list(values))


def test_county_geoid_derivation_skips_retired_codes() -> None:
    assert len(georgia.COUNTY_GEOIDS) == 159
    assert georgia.COUNTY_GEOIDS["Appling"] == "13001"
    assert georgia.COUNTY_GEOIDS["Camden"] == "13039"
    assert georgia.COUNTY_GEOIDS["Candler"] == "13043"
    assert georgia.COUNTY_GEOIDS["White"] == "13311"
    assert georgia.COUNTY_GEOIDS["Worth"] == "13321"


def test_directory_preserves_missing_county_and_route_disagreement() -> None:
    parsed = georgia.parse_directory_page(_directory_artifact())

    assert len(parsed.records) == 158
    assert parsed.missing_counties == ("White",)
    assert parsed.unexpected_counties == ()
    assert parsed.route_disagreements == ("Atkinson",)
    atkinson = next(
        row
        for row in parsed.records
        if row["county_name"] == "Atkinson"
    )
    assert atkinson["county_geoid"] == "13003"
    assert atkinson["published_primary_url"].endswith(
        "/ga/atkinson/index.html"
    )
    assert atkinson["published_description_url"].endswith("/ga/bacon/")
    assert atkinson["route_target_disagreement"] is True


def test_directory_search_uses_query_bound_resumable_cursor() -> None:
    client = FixtureClient()
    first = georgia.execute(
        _args(
            "directory",
            "qpublic",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    second = georgia.execute(
        _args(
            "directory",
            "qpublic",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert first.status.value == "ok"
    assert len(first.records) == 2
    assert len(second.records) == 2
    assert {
        row["canonical_ref"]
        for row in first.records
    }.isdisjoint(
        row["canonical_ref"] for row in second.records
    )

    mismatch = georgia.execute(
        _args(
            "directory",
            "Fulton",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_county_and_platform_filters_use_canonical_county_identity() -> None:
    client = FixtureClient()
    county = georgia.execute(
        _args("directory", "--county", "13121"),
        client=client,
        log_results=False,
    )
    schneider = georgia.execute(
        _args(
            "directory",
            "--platform",
            "qpublic_schneider",
        ),
        client=client,
        log_results=False,
    )

    assert [row["county_name"] for row in county.records] == ["Fulton"]
    assert [row["county_name"] for row in schneider.records] == ["Dawson"]


def test_platform_summary_keeps_vendor_family_and_hosts_separate() -> None:
    result = georgia.execute(
        _args("platforms"),
        client=FixtureClient(),
        log_results=False,
    )

    by_platform = {
        row["platform_family"]: row
        for row in result.records
    }
    assert set(by_platform) == {
        "county_hosted",
        "qpublic_legacy",
        "qpublic_schneider",
    }
    assert by_platform["county_hosted"]["counties"] == ("Fulton",)
    assert by_platform["qpublic_schneider"]["counties"] == ("Dawson",)


def test_gsccca_handoff_preserves_coverage_and_free_summary_account() -> None:
    handoff = georgia.parse_gsccca_handoff(
        _information_artifact(),
        _limited_artifact(),
        _gate_artifact(),
    )

    assert handoff["source_id"] == georgia.GSCCCA_SOURCE_ID
    assert handoff["coverage"]["deed_index_since_at_least"] == "1999-01-01"
    assert handoff["access"]["search_requires_account"] is True
    assert handoff["access"]["limited_use_account_cost"] == "no_cost"
    assert handoff["access"]["limited_use_summary_index_access"] is True
    assert handoff["access"]["limited_use_document_images"] is False
    assert handoff["access"]["login_handoff_url"].startswith(
        "https://apps.gsccca.org/login.asp"
    )


def test_probe_keeps_each_source_identity_and_request_shape() -> None:
    directory_client = FixtureClient()
    directory = georgia.execute(
        _args(
            "probe",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
        ),
        client=directory_client,
        log_results=False,
    )
    gsccca_client = FixtureClient()
    gsccca = georgia.execute(
        _args(
            "probe",
            "--source",
            georgia.GSCCCA_SOURCE_ID,
        ),
        client=gsccca_client,
        log_results=False,
    )

    assert directory.records[0]["row_count"] == 158
    assert directory.records[0]["missing_counties"] == ("White",)
    assert directory.records[0]["route_disagreements"] == ("Atkinson",)
    assert directory_client.calls == [georgia.DIRECTORY_URL]
    assert gsccca.records[0]["access"]["limited_use_account_cost"] == "no_cost"
    assert gsccca_client.calls == [
        georgia.GSCCCA_INFORMATION_URL,
        georgia.GSCCCA_LIMITED_USE_URL,
        georgia.GSCCCA_LOGIN_GATE_URL,
    ]


def test_manifests_keep_routing_and_land_index_distinct() -> None:
    directory = georgia.execute(
        _args(
            "manifest",
            "--source",
            georgia.DIRECTORY_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    gsccca = georgia.execute(
        _args(
            "manifest",
            "--source",
            georgia.GSCCCA_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert directory.records[0]["coverage"]["expected_counties"] == 159
    assert directory.records[0]["complementary_source_ids"] == (
        georgia.GSCCCA_SOURCE_ID,
    )
    assert gsccca.records[0]["coverage"]["limited_use_summary_search"] == (
        "free_account"
    )
    assert gsccca.records[0]["stable_identity"] == ("canonical_ref",)
    assert gsccca.records[0]["complementary_source_ids"] == (
        georgia.DIRECTORY_SOURCE_ID,
    )
