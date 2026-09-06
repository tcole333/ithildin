from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_colorado_court_data as court_data


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "colorado_court_data"
)
ANNUAL_HTML = (FIXTURE_DIR / "annual-reports.html").read_text(
    encoding="utf-8"
)
SELF_REPRESENTED_HTML = (
    FIXTURE_DIR / "self-represented.html"
).read_text(encoding="utf-8")
EVICTION_HTML = (FIXTURE_DIR / "eviction.html").read_text(
    encoding="utf-8"
)
CJD_HTML = (FIXTURE_DIR / "cjd-index.html").read_text(encoding="utf-8")
POWER_BI_HTML = (FIXTURE_DIR / "power-bi.html").read_text(
    encoding="utf-8"
)
PDF_SAMPLE = bytes.fromhex(
    (FIXTURE_DIR / "pdf-sample.hex").read_text(encoding="ascii").strip()
)


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    url: str = court_data.BASE_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=utf-8"}
    )
    closed: bool = False

    def iter_content(self, chunk_size=1):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self):
        self.closed = True


class MappingSession:
    def __init__(self, responses: dict[str, FixtureResponse]):
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method,
        url,
        *,
        timeout=None,
        allow_redirects=None,
        stream=None,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
                "stream": stream,
            }
        )
        try:
            response = self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"unexpected request: {url}") from exc
        return response


def html_response(url: str, text: str) -> FixtureResponse:
    return FixtureResponse(text=text, url=url)


def pdf_response(
    requested_url: str = court_data.ADDENDUM_A_URL,
) -> FixtureResponse:
    del requested_url
    return FixtureResponse(
        content=PDF_SAMPLE,
        url=(
            f"{court_data.BASE_URL}"
            "/sites/default/files/2023-07/Addendum-A.pdf"
        ),
        headers={
            "Content-Type": "application/pdf",
            "Content-Length": str(len(PDF_SAMPLE)),
            "ETag": '"fixture-etag"',
            "Last-Modified": "Wed, 31 Jan 2024 19:38:44 GMT",
        },
    )


def catalog_session(
    *,
    include_probe_artifacts: bool = False,
) -> MappingSession:
    responses = {
        court_data.ANNUAL_REPORTS_URL: html_response(
            court_data.ANNUAL_REPORTS_URL,
            ANNUAL_HTML,
        ),
        court_data.SELF_REPRESENTED_URL: html_response(
            court_data.SELF_REPRESENTED_URL,
            SELF_REPRESENTED_HTML,
        ),
        court_data.EVICTION_DASHBOARD_URL: html_response(
            court_data.EVICTION_DASHBOARD_URL,
            EVICTION_HTML,
        ),
        court_data.CJD_INDEX_URL: html_response(
            court_data.CJD_INDEX_URL,
            CJD_HTML,
        ),
    }
    if include_probe_artifacts:
        responses[court_data.ADDENDUM_A_URL] = pdf_response()
        responses[
            "https://app.powerbigov.us/view?r=eviction"
        ] = html_response(
            "https://app.powerbigov.us/view?r=eviction",
            POWER_BI_HTML,
        )
    return MappingSession(responses)


def client(session: MappingSession) -> court_data.ColoradoCourtDataClient:
    return court_data.ColoradoCourtDataClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )


def allowed() -> dict[str, Any]:
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
    }


def args(command: str, **overrides: Any) -> argparse.Namespace:
    values: dict[str, Any] = {
        "command": command,
        "query": None,
        "component_source": None,
        "report_type": None,
        "fiscal_year": None,
        "artifact": None,
        "destination": None,
        "overwrite": False,
        "timeout": 30.0,
        "minimum_interval": 0,
        "catalog_db": "unused.db",
        "catalog_config": "unused.yaml",
        "output": None,
        "json_out": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_annual_parser_preserves_all_dashboards_and_archived_reports():
    artifacts = court_data.parse_annual_reports(ANNUAL_HTML)

    assert len(artifacts) == 9
    dashboards = [
        artifact
        for artifact in artifacts
        if artifact.artifact_kind == "interactive_dashboard"
    ]
    reports = [
        artifact
        for artifact in artifacts
        if artifact.artifact_kind == "statistical_report"
    ]
    assert len(dashboards) == 5
    assert {artifact.report_type for artifact in dashboards} == {
        "supreme_court_statistics",
        "court_of_appeals_statistics",
        "trial_court_statistics",
        "judicial_branch_financial_information",
        "probation_statistics",
    }
    assert [artifact.fiscal_year for artifact in reports] == [
        2024,
        2023,
        2022,
        2021,
    ]
    assert reports[0].artifact_id == "annual-statistical-report-fy-2024"
    assert reports[0].downloadable is True
    assert reports[0].source_url == (
        f"{court_data.BASE_URL}"
        "/sites/default/files/2025-06/"
        "FY2024-Annual-Statistical-Report.pdf"
    )
    assert all(
        artifact.component_source_id
        == court_data.ANNUAL_REPORTS_SOURCE_ID
        for artifact in artifacts
    )


def test_self_represented_parser_keeps_media_alias_and_every_year():
    artifacts = court_data.parse_self_represented_reports(
        SELF_REPRESENTED_HTML
    )

    assert [artifact.fiscal_year for artifact in artifacts] == [
        2025,
        2024,
        2023,
    ]
    assert artifacts[0].source_url == f"{court_data.BASE_URL}/media/18031"
    record = artifacts[0].to_record()
    assert record["source_id"] == court_data.SELF_REPRESENTED_SOURCE_ID
    assert record["adapter_source_id"] == court_data.SOURCE_ID
    assert record["canonical_ref"] == (
        "COURT-DATA:"
        f"{court_data.SELF_REPRESENTED_SOURCE_ID}/"
        "case-parties-without-representation-fy-2025"
    )
    assert record["artifact_url"] == f"{court_data.BASE_URL}/media/18031"
    assert record["coverage"]["denver_county_court_included"] is False


def test_eviction_parser_is_a_discovery_record_not_a_claimed_export():
    artifact = court_data.parse_eviction_dashboard(EVICTION_HTML)
    record = artifact.to_record()

    assert artifact.artifact_id == court_data.EVICTION_ARTIFACT_ID
    assert artifact.source_url == (
        "https://app.powerbigov.us/view?r=eviction"
    )
    assert artifact.downloadable is False
    assert record["access_mode"] == "public_interactive_dashboard"
    assert record["metadata"]["machine_artifact_route"] is None
    assert record["landing_url"] == court_data.EVICTION_DASHBOARD_URL
    assert record["dashboard_url"] == artifact.source_url
    assert "interactive dashboard" in record["description"]
    assert record["coverage"]["courts"] == [
        "Colorado state courts",
        "Denver County Court",
    ]


def test_cjd_parser_discovers_current_effective_policy_artifact():
    artifact = court_data.parse_cjd_05_01(CJD_HTML)

    assert artifact.artifact_id == "cjd-05-01-effective-2025-11-10"
    assert artifact.effective_date == "2025-11-10"
    assert artifact.source_url.endswith(
        "CJD05-01%20Amendments%20Effective%2011.10.2025"
        "%20signed%20WEB%20A11Y.pdf"
    )
    assert artifact.component_source_id == (
        court_data.COMPILED_REQUEST_SOURCE_ID
    )


@pytest.mark.parametrize(
    ("parser", "html", "message"),
    [
        (
            court_data.parse_annual_reports,
            ANNUAL_HTML.replace("Previous Fiscal Year Reports", "Old Reports"),
            "fiscal-year report list",
        ),
        (
            court_data.parse_self_represented_reports,
            SELF_REPRESENTED_HTML.replace(
                "without Attorney Representation",
                "Historical Reports",
            ),
            "fiscal-year report list",
        ),
        (
            court_data.parse_eviction_dashboard,
            EVICTION_HTML.replace("FED_Filings", "Changed_Dashboard"),
            "FED filings dashboard",
        ),
        (
            court_data.parse_cjd_05_01,
            CJD_HTML.replace("05-01 Access", "05-99 Access"),
            "lacks CJD 05-01",
        ),
    ],
)
def test_parsers_distinguish_source_change_from_empty_catalog(
    parser,
    html,
    message,
):
    with pytest.raises(
        court_data.ColoradoCourtDataSourceChanged,
        match=message,
    ):
        parser(html)


def test_catalog_exposes_distinct_components_and_request_workflow():
    source_client = client(catalog_session())

    snapshot = source_client.catalog()

    assert len(snapshot.artifacts) == 16
    assert len(
        {
            (artifact.component_source_id, artifact.artifact_id)
            for artifact in snapshot.artifacts
        }
    ) == 16
    assert {
        artifact.component_source_id
        for artifact in snapshot.artifacts
    } == set(court_data.COMPONENT_SOURCE_IDS)

    workflow = court_data.resolve_artifact(
        snapshot.artifacts,
        court_data.WORKFLOW_ARTIFACT_ID,
    ).to_record()
    assert workflow["access_mode"] == "request"
    assert workflow["metadata"]["submission_email"] == (
        court_data.DATA_REQUEST_EMAIL
    )
    assert workflow["metadata"]["policy_sections"]["4.30"].startswith(
        "defines bulk data"
    )
    assert workflow["coverage"]["monthly_civil_judgment_report"][
        "fields"
    ] == [
        "case number",
        "creditor name",
        "creditor address when entered",
        "debtor name",
        "debtor address when entered",
        "judgment date",
        "total judgment amount",
        "satisfaction date when applicable",
    ]


def test_filters_return_complete_matching_catalog_without_default_cap():
    snapshot = client(catalog_session()).catalog()

    all_records = court_data.filter_artifacts(snapshot.artifacts)
    annual = court_data.filter_artifacts(
        snapshot.artifacts,
        component_source_id=court_data.ANNUAL_REPORTS_SOURCE_ID,
    )
    fy_2024 = court_data.filter_artifacts(
        snapshot.artifacts,
        fiscal_year=2024,
    )
    eviction = court_data.filter_artifacts(
        snapshot.artifacts,
        query="eviction",
    )

    assert len(all_records) == 16
    assert len(annual) == 9
    assert {artifact.component_source_id for artifact in fy_2024} == {
        court_data.ANNUAL_REPORTS_SOURCE_ID,
        court_data.SELF_REPRESENTED_SOURCE_ID,
    }
    assert [artifact.artifact_id for artifact in eviction] == [
        court_data.EVICTION_ARTIFACT_ID
    ]


def test_resolver_accepts_only_exact_live_catalog_members():
    snapshot = client(catalog_session()).catalog()
    annual = court_data.resolve_artifact(
        snapshot.artifacts,
        "annual-statistical-report-fy-2024",
    )

    assert court_data.resolve_artifact(
        snapshot.artifacts,
        annual.canonical_ref,
    ) == annual
    assert court_data.resolve_artifact(
        snapshot.artifacts,
        annual.source_url,
    ) == annual
    with pytest.raises(court_data.ColoradoCourtDataNotFound):
        court_data.resolve_artifact(
            snapshot.artifacts,
            "https://www.coloradojudicial.gov/fabricated.pdf",
        )


def test_download_streams_exact_pdf_and_records_hash(tmp_path):
    artifact = court_data.addendum_a_artifact()
    response = pdf_response()
    source_client = client(
        MappingSession({court_data.ADDENDUM_A_URL: response})
    )
    destination = tmp_path / "addendum-a.pdf"

    receipt = source_client.download(artifact, destination)

    assert destination.read_bytes() == PDF_SAMPLE
    assert receipt == {
        "size": len(PDF_SAMPLE),
        "sha256": hashlib.sha256(PDF_SAMPLE).hexdigest(),
        "content_type": "application/pdf",
        "etag": '"fixture-etag"',
        "last_modified": "Wed, 31 Jan 2024 19:38:44 GMT",
        "requested_url": court_data.ADDENDUM_A_URL,
        "final_url": (
            f"{court_data.BASE_URL}"
            "/sites/default/files/2023-07/Addendum-A.pdf"
        ),
        "path": str(destination.resolve()),
    }
    assert response.closed is True


def test_download_rejects_dashboard_without_requesting_it(tmp_path):
    dashboard = court_data.parse_eviction_dashboard(EVICTION_HTML)
    session = MappingSession({})

    with pytest.raises(
        court_data.ColoradoCourtDataNotDownloadable,
        match="not a verified PDF artifact",
    ):
        client(session).download(
            dashboard,
            tmp_path / "dashboard.pdf",
        )

    assert session.calls == []


def test_download_rejects_html_response_and_removes_partial_file(tmp_path):
    artifact = court_data.addendum_a_artifact()
    response = FixtureResponse(
        content=b"<html>changed</html>",
        url=court_data.ADDENDUM_A_URL,
        headers={
            "Content-Type": "text/html",
            "Content-Length": "20",
        },
    )
    destination = tmp_path / "addendum-a.pdf"

    with pytest.raises(
        court_data.ColoradoCourtDataSourceChanged,
        match="did not return a PDF signature",
    ):
        client(
            MappingSession({court_data.ADDENDUM_A_URL: response})
        ).download(artifact, destination)

    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []


def test_probe_has_stable_source_identity_and_component_evidence():
    source_client = client(catalog_session(include_probe_artifacts=True))

    first = court_data.run_probe(source_client)

    assert first["status"] == "ok"
    assert first["source_id"] == court_data.SOURCE_ID
    assert first["source_url"] == court_data.ANNUAL_REPORTS_URL
    assert first["canonical_ref"] == (
        "COURT-DATA:us-co-judicial-data-reports/"
        "source-health-live-probe"
    )
    assert first["result_count"] == 16
    assert set(first["component_counts"]) == set(
        court_data.COMPONENT_SOURCE_IDS
    )
    assert len(first["artifact_identity"]) == 64
    assert first["schema_fingerprint"] == (
        court_data.ADAPTER_SCHEMA_FINGERPRINT
    )
    assert first["sentinels"]["addendum_a"]["sha256"] == (
        hashlib.sha256(PDF_SAMPLE).hexdigest()
    )
    assert first["sentinels"]["eviction_dashboard"][
        "anonymous_get"
    ] == "http_200"


def test_execute_uses_shared_contract_and_preserves_component_identity(
    monkeypatch,
):
    log_calls = []
    monkeypatch.setattr(
        court_data,
        "_log",
        lambda *_args: log_calls.append(_args),
    )
    source_client = client(catalog_session())

    result = court_data.execute(
        args(
            "search",
            query="judgment amount",
            component_source=court_data.COMPILED_REQUEST_SOURCE_ID,
        ),
        access_decision=allowed(),
        client=source_client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert [record["artifact_id"] for record in result.records] == [
        court_data.WORKFLOW_ARTIFACT_ID
    ]
    assert result.records[0]["source_id"] == (
        court_data.COMPILED_REQUEST_SOURCE_ID
    )
    assert result.query.source.source_id == court_data.SOURCE_ID
    assert log_calls == []


def test_execute_reports_no_results_separately_from_source_failure(
    monkeypatch,
):
    monkeypatch.setattr(court_data, "_log", lambda *_args: None)

    empty = court_data.execute(
        args("search", query="definitely absent phrase"),
        access_decision=allowed(),
        client=client(catalog_session()),
    )
    changed = court_data.execute(
        args("catalog"),
        access_decision=allowed(),
        client=client(
            MappingSession(
                {
                    court_data.ANNUAL_REPORTS_URL: html_response(
                        court_data.ANNUAL_REPORTS_URL,
                        "<html>changed</html>",
                    )
                }
            )
        ),
    )

    assert empty.status.value == "no_results"
    assert empty.errors == ()
    assert changed.status.value == "source_changed"
    assert changed.errors[0].code == "source_schema_changed"


def test_cli_surfaces_have_no_implicit_result_limit():
    parser = court_data.build_parser()

    catalog = parser.parse_args(["catalog"])
    search = parser.parse_args(["search", "civil judgments"])

    assert not hasattr(catalog, "limit")
    assert not hasattr(search, "limit")
    assert catalog.component_source is None
    assert search.query == "civil judgments"


def test_official_url_rejects_unlisted_hosts():
    with pytest.raises(
        court_data.ColoradoCourtDataSourceChanged,
        match="unexpected host",
    ):
        court_data._official_url("https://example.com/report.pdf")
