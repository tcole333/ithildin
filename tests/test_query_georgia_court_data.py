from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from tools import query_georgia_court_data as georgia


def _artifact(
    content: bytes | str,
    url: str,
    media_type: str,
) -> georgia.Artifact:
    return georgia.Artifact(
        content=content.encode() if isinstance(content, str) else content,
        source_url=url,
        media_type=media_type,
        headers={"content-type": media_type},
    )


def _data_artifact() -> georgia.Artifact:
    panels = []
    for index, court_class in enumerate(georgia.COURT_CLASSES, start=1):
        panels.append(
            '<div class="fusion-panel">'
            f'<span class="fusion-toggle-heading">'
            f"{court_class} Dashboard</span>"
            f'<iframe title="{court_class}" '
            f'src="https://app.powerbigov.us/view?r=token{index}"></iframe>'
            "</div>"
        )
    panels.append(
        '<div class="fusion-panel">'
        '<span class="fusion-toggle-heading">'
        "Caseload Dashboard User Guide</span>"
        '<iframe title="Embedded PDF" '
        'src="https://research.georgiacourts.gov/viewer.php?'
        "file=https://research.georgiacourts.gov/"
        'wp-content/uploads/Dashboard-Guide.pdf&amp;attachment_id=1">'
        "</iframe></div>"
    )
    workloads = []
    for year in range(2024, 2017, -1):
        suffix = (
            " (last updated October 1, 2020)"
            if year == 2019
            else ""
        )
        workloads.append(
            "<p>"
            f'<a href="/wp-content/uploads/{year}-workload.pdf">'
            f"{year} Superior Court Workload Assessment</a>"
            f"{suffix}</p>"
        )
    return _artifact(
        """
        <html><body>
        <h1>Data &amp; Statistics</h1>
        <p>The caseload data reported to the AOC is self-reported data by
        Georgia Courts and only consists of counts of cases. The Research
        Office does not collect data on individual cases. To receive exported
        data please
        <a href="/dashboard-export-request/">submit a request</a>.</p>
        """
        + "".join(panels)
        + "<h1>Superior Court Workload Assessments</h1>"
        + "".join(workloads)
        + "</body></html>",
        georgia.DATA_URL,
        "text/html",
    )


def _export_artifact() -> georgia.Artifact:
    classes = "".join(
        f'<input value="{court_class}">'
        for court_class in georgia.COURT_CLASSES
    )
    years = "".join(
        f'<input value="{year}">' for year in range(2021, 2026)
    )
    return _artifact(
        """
        <html><body><h1>Dashboard Export Request</h1>
        <form id="gform_1" action="/dashboard-export-request/">
          <fieldset id="field_1_19" class="gfield_contains_required">
            <legend class="gfield_label">Class of Court (Required)</legend>
        """
        + classes
        + """
          </fieldset>
          <fieldset id="field_1_20" class="gfield_contains_required">
            <legend class="gfield_label">Date Range (Required)</legend>
        """
        + years
        + """
          </fieldset>
          <div class="gfield_contains_required">
            <label class="gfield_label">Desired Data Format (Required)</label>
          </div>
          <div class="gfield_contains_required">
            <label class="gfield_label">Request Details (Required)</label>
          </div>
        </form></body></html>
        """,
        georgia.EXPORT_REQUEST_URL,
        "text/html",
    )


PDF_BYTES = b"%PDF-1.7\nfixture workload assessment\n%%EOF\n"


class FixtureClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        accept: str = "text/html,application/xhtml+xml",
        maximum_bytes: int = georgia.MAXIMUM_HTML_BYTES,
    ) -> georgia.Artifact:
        del accept, maximum_bytes
        self.calls.append(url)
        if url == georgia.DATA_URL:
            return _data_artifact()
        if url == georgia.EXPORT_REQUEST_URL:
            return _export_artifact()
        if url.endswith(".pdf"):
            return _artifact(PDF_BYTES, url, "application/pdf")
        raise AssertionError(f"unexpected URL {url}")


def _args(*values: str) -> Any:
    return georgia.build_parser().parse_args(list(values))


def test_catalog_separates_aggregate_dashboards_and_workload_pdfs() -> None:
    parsed = georgia.parse_data_catalog(_data_artifact())

    assert [row["court_class"] for row in parsed.dashboards] == list(
        georgia.COURT_CLASSES
    )
    assert all(
        row["data_scope"]["individual_case_records"] is False
        for row in parsed.dashboards
    )
    assert parsed.dashboard_user_guide_url.endswith(
        "/wp-content/uploads/Dashboard-Guide.pdf"
    )
    assert parsed.export_request_url == georgia.EXPORT_REQUEST_URL
    assert [row["publication_year"] for row in parsed.workloads] == list(
        range(2024, 2017, -1)
    )
    workload_2019 = next(
        row
        for row in parsed.workloads
        if row["publication_year"] == 2019
    )
    assert workload_2019["published_update_note"] == "October 1, 2020"


def test_dashboard_search_uses_source_bound_resumable_cursor() -> None:
    client = FixtureClient()
    first = georgia.execute(
        _args("dashboards", "*", "--limit", "2"),
        client=client,
        log_results=False,
    )
    second = georgia.execute(
        _args(
            "dashboards",
            "*",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert [row["court_class"] for row in first.records] == [
        "Superior Court",
        "State Court",
    ]
    assert [row["court_class"] for row in second.records] == [
        "Magistrate Court",
        "Probate Court",
    ]

    mismatch = georgia.execute(
        _args(
            "dashboards",
            "Superior",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_workload_listing_and_document_preserve_publication_identity(
    tmp_path: Path,
) -> None:
    listed = georgia.execute(
        _args("workloads", "--year", "2024"),
        client=FixtureClient(),
        log_results=False,
    )
    assert len(listed.records) == 1
    assert listed.records[0]["canonical_ref"].endswith(":2024")

    artifact_path = tmp_path / "workload.pdf"
    client = FixtureClient()
    document = georgia.execute(
        _args(
            "document",
            "2024",
            "--artifact-output",
            str(artifact_path),
        ),
        client=client,
        log_results=False,
    )
    record = document.records[0]

    assert record["record_kind"] == "annual_superior_court_workload_pdf"
    assert record["artifact_sha256"] == hashlib.sha256(
        PDF_BYTES
    ).hexdigest()
    assert record["artifact_byte_length"] == len(PDF_BYTES)
    assert artifact_path.read_bytes() == PDF_BYTES
    assert client.calls == [
        georgia.DATA_URL,
        "https://research.georgiacourts.gov/"
        "wp-content/uploads/2024-workload.pdf",
    ]


def test_export_handoff_preserves_form_scope_without_submission() -> None:
    result = georgia.execute(
        _args("handoff"),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.records[0]

    assert record["record_kind"] == (
        "aggregate_dashboard_export_acquisition_handoff"
    )
    assert set(record["available_court_classes"]) == set(
        georgia.COURT_CLASSES
    )
    assert record["available_years"] == tuple(range(2021, 2026))
    assert record["required_request_fields"] == (
        "Class of Court",
        "Date Range",
        "Desired Data Format",
        "Request Details",
    )
    assert record["submission_performed"] is False


def test_each_probe_has_bounded_source_specific_request_shape() -> None:
    dashboard_client = FixtureClient()
    dashboard = georgia.execute(
        _args(
            "probe",
            "--source",
            georgia.DASHBOARD_SOURCE_ID,
        ),
        client=dashboard_client,
        log_results=False,
    )
    workload_client = FixtureClient()
    workload = georgia.execute(
        _args(
            "probe",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
        ),
        client=workload_client,
        log_results=False,
    )

    assert dashboard.records[0]["dashboard_count"] == 6
    assert dashboard.records[0]["individual_case_records"] is False
    assert dashboard_client.calls == [georgia.DATA_URL]

    assert workload.records[0]["publication_count"] == 7
    assert workload.records[0]["latest_publication_year"] == 2024
    assert workload_client.calls == [
        georgia.DATA_URL,
        "https://research.georgiacourts.gov/"
        "wp-content/uploads/2024-workload.pdf",
    ]


def test_manifests_keep_aggregate_sources_and_complements_distinct() -> None:
    dashboard = georgia.execute(
        _args(
            "manifest",
            "--source",
            georgia.DASHBOARD_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )
    workload = georgia.execute(
        _args(
            "manifest",
            "--source",
            georgia.WORKLOAD_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert dashboard.records[0]["coverage"]["individual_case_records"] is False
    assert dashboard.records[0]["stable_identity"] == ("canonical_ref",)
    assert georgia.WORKLOAD_SOURCE_ID in (
        dashboard.records[0]["complementary_source_ids"]
    )
    assert workload.records[0]["coverage"]["baseline_years"] == tuple(
        range(2018, 2025)
    )
    assert workload.records[0]["stable_identity"] == ("canonical_ref",)


def test_access_decision_blocks_network_without_losing_source_identity() -> None:
    client = FixtureClient()
    result = georgia.execute(
        _args("dashboards"),
        client=client,
        access_decision={
            "allowed": False,
            "result_status": "restricted",
            "reason_code": "review_required",
            "reason": "review required",
        },
        log_results=False,
    )

    assert result.status.value == "restricted"
    assert result.query.source.source_id == georgia.DASHBOARD_SOURCE_ID
    assert result.errors[0].code == "review_required"
    assert client.calls == []
