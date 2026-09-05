from __future__ import annotations

from typing import Any, Mapping

from tools import query_georgia_court_access as court_access
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


def _artifact(content: str, url: str) -> court_access.HTMLArtifact:
    return court_access.HTMLArtifact(
        content=content.encode(),
        source_url=url,
        status_code=200,
        headers={"content-type": "text/html"},
    )


def _eaccess_artifact(*, marker: str = "") -> court_access.HTMLArtifact:
    return _artifact(
        f"""
        <html><body>
          <h1>E-Access to Court Records</h1>
          <p>You must have an account to search court records.</p>
          <table><tbody><tr>
            <td>
              <a href="{court_access.PEACHCOURT_URL}">
                Appling State Court
              </a>
            </td>
            <td>
              <a href="{court_access.EACCESS_VENDOR_PUBLISHED_URL}">
                Coweta Superior Court
              </a>
            </td>
            <td>
              <a href="http://researchga.tylerhost.net/CourtRecordsSearch/Home#!/home">
                Chatham Superior Court
              </a>
            </td>
          </tr></tbody></table>
          {marker}
        </body></html>
        """,
        court_access.EACCESS_URL,
    )


def _vendor_artifact() -> court_access.HTMLArtifact:
    return _artifact(
        f"""
        <html><body>
          <h1>Vendors</h1>
          <h2>Choose your e-Filing Vendor from the options below.</h2>
          <a href="{court_access.PEACHCOURT_URL}"
             aria-label="Access court records with Peach Court">
            <img alt="Peach Court">
          </a>
          <a href="{court_access.RESEARCHGA_URL}"
             aira-label="Case information and documents across 25 counties">
            <img alt="">
          </a>
        </body></html>
        """,
        court_access.EACCESS_VENDOR_URL,
    )


def _efile_artifact(*, marker: str = "") -> court_access.HTMLArtifact:
    return _artifact(
        f"""
        <html><body>
          <h1>E-File Court Records</h1>
          <p>You must have an account to initiate a new case filing.</p>
          <table>
            <tr>
              <th>Court by County</th>
              <th>Odyssey eFileGA</th>
              <th>Peach Court</th>
              <th>GreenFiling/InfoTrack</th>
            </tr>
            <tr>
              <td>Baker Superior Court</td>
              <td><a href="{court_access.ODYSSEY_EFILEGA_URL}">Mandatory</a></td>
              <td><a href="{court_access.PEACHCOURT_URL}">Mandatory</a></td>
              <td><a href="{court_access.GREENFILING_URL}">Available</a></td>
            </tr>
            <tr>
              <td>Appling State Court</td>
              <td></td>
              <td><a href="{court_access.PEACHCOURT_URL}">Mandatory</a></td>
              <td></td>
            </tr>
            <tr>
              <td>Chatham Superior Civil Court</td>
              <td><a href="{court_access.ODYSSEY_EFILEGA_URL}">Mandatory</a></td>
              <td></td>
              <td><a href="{court_access.GREENFILING_URL}">Available</a></td>
            </tr>
          </table>
          {marker}
        </body></html>
        """,
        court_access.EFILE_URL,
    )


class _FixtureClient:
    def __init__(
        self,
        *,
        eaccess_marker: str = "",
        efile_marker: str = "",
    ) -> None:
        self.eaccess_marker = eaccess_marker
        self.efile_marker = efile_marker
        self.request_count = 0
        self.calls: list[str] = []

    def page(self, url: str) -> court_access.HTMLArtifact:
        self.request_count += 1
        self.calls.append(url)
        if url == court_access.EACCESS_URL:
            return _eaccess_artifact(marker=self.eaccess_marker)
        if url == court_access.EACCESS_VENDOR_PUBLISHED_URL:
            return _vendor_artifact()
        if url == court_access.EFILE_URL:
            return _efile_artifact(marker=self.efile_marker)
        raise AssertionError(f"unexpected URL {url}")


class _Response:
    def __init__(
        self,
        content: str,
        *,
        status_code: int = 200,
        url: str = court_access.EFILE_URL,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.content = content.encode()
        self.text = content
        self.status_code = status_code
        self.url = url
        self.headers = dict(headers or {"content-type": "text/html"})


class _QueueSession:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout: float,
        allow_redirects: bool,
    ) -> _Response:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if not self.responses:
            raise AssertionError("fixture session has no response left")
        return self.responses.pop(0)


def _args(*values: str):
    return court_access.build_parser().parse_args(list(values))


def test_manifests_keep_handoff_filing_and_alternatives_distinct() -> None:
    eaccess = court_access.source_manifest(court_access.EACCESS_SOURCE_ID)
    efile = court_access.source_manifest(court_access.EFILE_SOURCE_ID)

    assert eaccess["access_contract"] == {
        "account_required": True,
        "case_search_completed": False,
    }
    assert eaccess["record_kind_emitted"] == (
        "case_access_acquisition_handoff"
    )
    assert efile["filing_contract"] == {
        "account_required_to_initiate": True,
        "filing_initiated": False,
        "case_evidence": False,
    }
    assert efile["published_states"] == [
        "mandatory",
        "available",
        "not_listed",
    ]
    assert all(
        item["dataset_equivalent"] is False
        for item in eaccess["official_complements"]
    )
    assert any(
        "e-Filing Vendor" in item["observation"]
        for item in eaccess["observed_source_anomalies"]
    )


def test_eaccess_preserves_direct_selection_and_http_routes() -> None:
    options = court_access.parse_eaccess_vendor_options(
        _vendor_artifact()
    )
    records = court_access.parse_eaccess_directory(
        _eaccess_artifact(),
        vendor_options=options,
        vendor_artifact=_vendor_artifact(),
    )
    by_label = {
        record["court"]["native_label"]: record for record in records
    }

    appling = by_label["Appling State Court"]
    assert appling["canonical_ref"] == (
        "GA-AOC-EACCESS:GA-COURT:13001:state"
    )
    assert appling["access"] == {
        "account_required": True,
        "directory_handoff": True,
        "case_search_completed": False,
    }
    assert appling["published_route"]["route_kind"] == "direct_provider"
    assert appling["projection"]["projectable_as_case"] is False

    coweta = by_label["Coweta Superior Court"]
    assert coweta["published_route"]["route_kind"] == (
        "provider_selection_page"
    )
    assert {
        route["provider_id"] for route in coweta["provider_routes"]
    } == {"peachcourt", "researchga"}
    assert all(
        route["route_relationship"] == "provider_selection_option"
        for route in coweta["provider_routes"]
    )
    assert {
        route["source_page_copy"] for route in coweta["provider_routes"]
    } == {"Choose your e-Filing Vendor from the options below."}

    chatham = by_label["Chatham Superior Court"]
    assert chatham["published_route"]["source_published_http"] is True
    assert chatham["published_route"]["url"].startswith("http://")


def test_efile_preserves_non_listings_states_and_civil_division() -> None:
    records = court_access.parse_efile_directory(_efile_artifact())
    by_label = {
        record["court"]["native_label"]: record for record in records
    }

    appling = by_label["Appling State Court"]
    states = {
        entry["provider_id"]: entry
        for entry in appling["provider_states"]
    }
    assert states["odyssey_efilega"]["published_state"] == "not_listed"
    assert states["odyssey_efilega"]["route_listed"] is False
    assert states["odyssey_efilega"]["account_required"] is None
    assert states["peachcourt"]["published_state"] == "mandatory"
    assert len(appling["provider_routes"]) == 1

    chatham = by_label["Chatham Superior Civil Court"]
    assert chatham["canonical_ref"] == (
        "GA-AOC-EFILE:GA-COURT:13051:superior"
    )
    assert chatham["court"]["canonical_label"] == (
        "Chatham Superior Court"
    )
    assert chatham["court"]["division"] == "civil"
    assert chatham["filing"] == {
        "account_required_to_initiate": True,
        "filing_initiated": False,
        "case_evidence": False,
    }
    odyssey = next(
        route
        for route in chatham["provider_routes"]
        if route["provider_id"] == "odyssey_efilega"
    )
    assert odyssey["source_published_http"] is True


def test_provider_summaries_count_published_states_not_failures() -> None:
    snapshot = court_access.load_source_snapshot(
        _FixtureClient(),
        court_access.EFILE_SOURCE_ID,
    )
    summaries = {
        row["provider_id"]: row
        for row in court_access._provider_summary_records(snapshot)
    }

    assert summaries["odyssey_efilega"]["listed_court_count"] == 2
    assert summaries["odyssey_efilega"]["state_counts"] == {
        "mandatory": 2,
        "not_listed": 1,
    }
    assert summaries["peachcourt"]["listed_court_count"] == 2
    assert summaries["peachcourt"]["state_counts"] == {
        "mandatory": 2,
        "not_listed": 1,
    }
    assert summaries["greenfiling_infotrack"]["state_counts"] == {
        "available": 2,
        "not_listed": 1,
    }


def test_search_cursor_binds_source_query_and_snapshot() -> None:
    first = court_access.execute(
        _args(
            "search",
            "*",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--limit",
            "2",
        ),
        client=_FixtureClient(),
        log_results=False,
    )
    assert first.status is ResultStatus.OK
    assert first.next_cursor is not None
    assert len(first.records) == 2

    second = court_access.execute(
        _args(
            "search",
            "*",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=_FixtureClient(),
        log_results=False,
    )
    assert second.status is ResultStatus.OK
    assert len(second.records) == 1
    assert second.next_cursor is None
    assert {
        row["canonical_ref"] for row in first.records
    }.isdisjoint(row["canonical_ref"] for row in second.records)

    query_mismatch = court_access.execute(
        _args(
            "search",
            "Baker",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--cursor",
            first.next_cursor,
        ),
        client=_FixtureClient(),
        log_results=False,
    )
    assert query_mismatch.status is ResultStatus.UNAVAILABLE
    assert query_mismatch.errors[0].code == "cursor_query_mismatch"

    snapshot_mismatch = court_access.execute(
        _args(
            "search",
            "*",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--cursor",
            first.next_cursor,
        ),
        client=_FixtureClient(efile_marker="<!-- refreshed -->"),
        log_results=False,
    )
    assert snapshot_mismatch.status is ResultStatus.UNAVAILABLE
    assert snapshot_mismatch.errors[0].code == "cursor_snapshot_mismatch"


def test_search_filters_provider_state_without_losing_non_listings() -> None:
    listed = court_access.execute(
        _args(
            "search",
            "*",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--provider",
            "odyssey_efilega",
            "--all",
        ),
        client=_FixtureClient(),
        log_results=False,
    )
    non_listed = court_access.execute(
        _args(
            "search",
            "*",
            "--source",
            court_access.EFILE_SOURCE_ID,
            "--provider",
            "odyssey_efilega",
            "--published-state",
            "not_listed",
            "--all",
        ),
        client=_FixtureClient(),
        log_results=False,
    )

    assert {
        row["court"]["native_label"] for row in listed.records
    } == {"Baker Superior Court", "Chatham Superior Civil Court"}
    assert [
        row["court"]["native_label"] for row in non_listed.records
    ] == ["Appling State Court"]


def test_probe_separates_contract_from_observations_and_stays_bounded() -> None:
    eaccess_client = _FixtureClient()
    eaccess = court_access.execute(
        _args(
            "probe",
            "--source",
            court_access.EACCESS_SOURCE_ID,
        ),
        client=eaccess_client,
        log_results=False,
    ).to_dict()["records"][0]
    efile_client = _FixtureClient()
    efile = court_access.execute(
        _args(
            "probe",
            "--source",
            court_access.EFILE_SOURCE_ID,
        ),
        client=efile_client,
        log_results=False,
    ).to_dict()["records"][0]

    assert eaccess_client.calls == [
        court_access.EACCESS_URL,
        court_access.EACCESS_VENDOR_PUBLISHED_URL,
    ]
    assert eaccess["requests_made"] == 2
    assert eaccess["stable_contract"]["access"][
        "case_search_completed"
    ] is False
    assert eaccess["rolling_observation"][
        "published_route_kind_counts"
    ] == {"direct_provider": 2, "provider_selection_page": 1}
    assert eaccess["rolling_observation"]["provider_selection_copy"] == [
        "Choose your e-Filing Vendor from the options below."
    ]
    assert "source_page_copy" in eaccess["schema_contract"][
        "provider_route_fields"
    ]

    assert efile_client.calls == [court_access.EFILE_URL]
    assert efile["requests_made"] == 1
    assert efile["stable_contract"]["blank_cell_semantics"] == (
        "not_listed"
    )
    assert efile["rolling_observation"]["provider_state_counts"][
        "odyssey_efilega"
    ] == {"mandatory": 2, "not_listed": 1}
    assert efile["rolling_observation"]["division_qualified_labels"] == [
        {
            "court_id": "GA-COURT:13051:superior",
            "native_label": "Chatham Superior Civil Court",
            "division": "civil",
        }
    ]
    assert len(eaccess["stable_schema_sha256"]) == 64
    assert len(efile["stable_schema_sha256"]) == 64


def test_http_client_uses_one_bounded_redirecting_get() -> None:
    session = _QueueSession(
        [
            _Response(
                _efile_artifact().text,
                url=court_access.EFILE_URL,
            )
        ]
    )
    client = court_access.GeorgiaCourtAccessClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )

    artifact = client.page(court_access.EFILE_URL)

    assert artifact.status_code == 200
    assert client.request_count == 1
    assert session.calls == [
        {
            "method": "GET",
            "url": court_access.EFILE_URL,
            "headers": {
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "Ithildin public-record source adapter",
            },
            "timeout": court_access.DEFAULT_TIMEOUT,
            "allow_redirects": True,
        }
    ]
