from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_harris_court_bulk as bulk


FIXTURE_DIR = Path("tests/fixtures/public_records/harris_court_bulk")
CATALOG = (FIXTURE_DIR / "catalog.html").read_text(encoding="utf-8")
XLSX_SAMPLE = bytes.fromhex(
    (FIXTURE_DIR / "xlsx-sample.hex").read_text(encoding="ascii").strip()
)


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    url: str = bulk.CATALOG_URL
    headers: dict[str, str] = field(default_factory=dict)
    closed: bool = False

    def iter_content(self, chunk_size=1):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset : offset + chunk_size]

    def close(self):
        self.closed = True


class QueueSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def request(
        self,
        method,
        url,
        *,
        timeout=None,
        allow_redirects=None,
        **kwargs,
    ):
        self.calls.append({
            "method": method,
            "url": url,
            "timeout": timeout,
            "allow_redirects": allow_redirects,
            **kwargs,
        })
        if not self.responses:
            raise AssertionError("unexpected District Clerk request")
        return self.responses.pop(0)


def fixture_client(session):
    return bulk.HarrisCourtBulkClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )


def allowed():
    return {
        "allowed": True,
        "access_class": "A",
        "automation_disposition": "allowed",
    }


def xlsx_response(content=XLSX_SAMPLE):
    return FixtureResponse(
        content=content,
        headers={
            "Content-Type": "text/plain",
            "Content-Disposition": (
                "attachment;filename=2024-08-15 FIELD_CODES.xlsx"
            ),
        },
    )


def test_parse_catalog_preserves_every_row_and_exact_native_locator():
    page = bulk.parse_catalog(CATALOG)

    assert len(page.artifacts) == 8
    assert page.hidden_fields["__VIEWSTATE"] == "fixture-viewstate"
    field_codes = page.artifacts[1]
    assert field_codes.section == "Civil"
    assert field_codes.published_date == "2024-08-15"
    assert field_codes.filename == "FIELD_CODES.xlsx"
    assert field_codes.native_locator == (
        r"Civil\2024-08-15 FIELD_CODES.xlsx"
    )
    assert field_codes.family == "schema_reference"
    assert field_codes.cadence == "reference"
    assert field_codes.format == "xlsx"

    historical = page.artifacts[3].to_record()
    assert historical["dataset_family"] == "case_summary"
    assert historical["cadence"] == "historical_segment"
    assert historical["coverage"] == {
        "basis": "filename_range",
        "start_year": 2000,
        "end_year": 2004,
        "raw": "2000-2004",
    }
    criminal_families = {
        item.filename: item.family
        for item in page.artifacts
        if item.section == "Criminal"
    }
    assert criminal_families["CrimDisposDaily_withHeadings.txt"] == (
        "dispositions"
    )
    assert criminal_families["CrimFilingsDaily_withHeadings.txt"] == (
        "filings"
    )
    assert criminal_families[
        "CrimFilingsWithFutureSettings_withHeadings.txt"
    ] == "future_settings"


def test_catalog_parser_rejects_missing_postback_contract():
    broken = CATALOG.replace('name="__VIEWSTATE"', 'name="OLD_VIEWSTATE"')

    with pytest.raises(
        bulk.HarrisCourtBulkSourceChanged,
        match="view state",
    ):
        bulk.parse_catalog(broken)


def test_catalog_parser_rejects_data_row_without_download_action():
    broken = CATALOG.replace(
        (
            "onclick=\"DownloadDoc('Criminal\\\\2026-07-29 "
            "CrimFilingsDaily_withHeadings.txt');\""
        ),
        "data-download-contract=\"changed\"",
    )

    with pytest.raises(
        bulk.HarrisCourtBulkSourceChanged,
        match="lacks its download action",
    ):
        bulk.parse_catalog(broken)


def test_resolver_accepts_exact_member_identifiers_not_constructed_paths():
    artifacts = bulk.parse_catalog(CATALOG).artifacts
    field_codes = artifacts[1]

    assert bulk.resolve_artifact(
        artifacts,
        field_codes.native_locator,
    ) == field_codes
    assert bulk.resolve_artifact(
        artifacts,
        field_codes.artifact_id,
    ) == field_codes
    assert bulk.resolve_artifact(
        artifacts,
        field_codes.filename,
    ) == field_codes
    with pytest.raises(bulk.HarrisCourtBulkNotFound):
        bulk.resolve_artifact(
            artifacts,
            r"Civil\2026-07-29 fabricated.zip",
        )


def test_list_has_no_default_cap_and_filters_after_full_catalog_parse():
    session = QueueSession([FixtureResponse(text=CATALOG)])
    client = fixture_client(session)

    all_rows = client.list_artifacts()

    assert len(all_rows) == 8
    assert client.list_artifacts  # no adapter pagination or implicit limit
    assert session.calls[0]["method"] == "GET"

    second_session = QueueSession([FixtureResponse(text=CATALOG)])
    civil = fixture_client(second_session).list_artifacts(
        section="Civil",
        family="case_summary",
    )
    assert [item.filename for item in civil] == [
        "CaseSummaryMods_Historical2000-2004.txt"
    ]


def test_direct_list_supports_shared_text_date_and_limit_filters():
    session = QueueSession([FixtureResponse(text=CATALOG)])
    args = bulk.build_parser().parse_args(
        [
            "list",
            "--section",
            "Civil",
            "--text-filter",
            "Historical",
            "--published-after",
            "2026-01-01",
            "--published-before",
            "2026-12-31",
            "--result-limit",
            "1",
        ]
    )

    result = bulk.execute(
        args,
        access_decision=allowed(),
        client=fixture_client(session),
    )

    assert len(result.records) == 1
    assert result.records[0]["filename"] == "Civil_Historical.zip"
    assert result.query.query.requested_limit == 1
    assert result.query.query.parameters == {
        "section": "Civil",
        "text_filter": "Historical",
        "published_after": "2026-01-01",
        "published_before": "2026-12-31",
    }


def test_inspect_gets_fresh_state_then_posts_exact_catalog_member():
    response = xlsx_response(XLSX_SAMPLE + b"x" * 100)
    session = QueueSession([
        FixtureResponse(text=CATALOG),
        response,
    ])

    receipt = fixture_client(session).inspect(
        "FIELD_CODES.xlsx",
        sample_bytes=16,
    )

    assert [call["method"] for call in session.calls] == ["GET", "POST"]
    post = session.calls[1]
    assert post["data"]["__VIEWSTATE"] == "fixture-viewstate"
    assert post["data"][bulk.DOWNLOAD_LOCATOR_FIELD] == (
        bulk.SENTINEL_LOCATOR
    )
    assert bulk.DOWNLOAD_BUTTON_FIELD in post["data"]
    assert receipt.sample == (XLSX_SAMPLE + b"x" * 100)[:16]
    assert receipt.response_filename == (
        "2024-08-15 FIELD_CODES.xlsx"
    )
    assert receipt.content_type == "text/plain"
    assert response.closed is True


def test_inspect_rejects_nonmember_before_download_post():
    session = QueueSession([FixtureResponse(text=CATALOG)])

    with pytest.raises(bulk.HarrisCourtBulkNotFound):
        fixture_client(session).inspect(
            r"Civil\2026-07-29 fabricated.zip"
        )

    assert [call["method"] for call in session.calls] == ["GET"]


def test_inspect_validates_magic_not_misleading_content_type():
    response = xlsx_response(b"<html>not a workbook</html>")
    session = QueueSession([
        FixtureResponse(text=CATALOG),
        response,
    ])

    with pytest.raises(
        bulk.HarrisCourtBulkSourceChanged,
        match="xlsx magic",
    ):
        fixture_client(session).inspect("FIELD_CODES.xlsx")


def test_download_streams_exact_member_and_returns_artifact_receipt(tmp_path):
    content = XLSX_SAMPLE + b"fixture workbook payload"
    session = QueueSession([
        FixtureResponse(text=CATALOG),
        xlsx_response(content),
    ])
    destination = tmp_path / "field-codes.xlsx"

    payload = fixture_client(session).download(
        bulk.SENTINEL_LOCATOR,
        destination,
    )

    assert destination.read_bytes() == content
    assert payload["artifact"].native_locator == bulk.SENTINEL_LOCATOR
    receipt = payload["artifact_receipt"]
    assert receipt["path"] == str(destination.resolve())
    assert receipt["size"] == len(content)
    assert receipt["sha256"] == hashlib.sha256(content).hexdigest()


def test_download_distinguishes_encoded_wire_length_from_artifact_size(
    tmp_path,
):
    content = XLSX_SAMPLE + b"decoded workbook payload"
    response = xlsx_response(content)
    response.headers.update({
        "Content-Encoding": "gzip",
        "Content-Length": "42",
    })
    session = QueueSession([
        FixtureResponse(text=CATALOG),
        response,
    ])
    destination = tmp_path / "field-codes.xlsx"

    payload = fixture_client(session).download(
        bulk.SENTINEL_LOCATOR,
        destination,
    )

    assert destination.read_bytes() == content
    receipt = payload["artifact_receipt"]
    assert receipt["size"] == len(content)
    assert receipt["content_encoding"] == "gzip"
    assert receipt["content_length_header"] == 42


def test_download_rejects_identity_transfer_length_mismatch(tmp_path):
    content = XLSX_SAMPLE + b"fixture workbook payload"
    response = xlsx_response(content)
    response.headers["Content-Length"] = str(len(content) + 1)
    session = QueueSession([
        FixtureResponse(text=CATALOG),
        response,
    ])

    with pytest.raises(
        bulk.HarrisCourtBulkSourceChanged,
        match="differs from Content-Length",
    ):
        fixture_client(session).download(
            bulk.SENTINEL_LOCATOR,
            tmp_path / "field-codes.xlsx",
        )


def test_execute_list_uses_shared_result_and_preserves_access_decision(
    monkeypatch,
):
    args = bulk.build_parser().parse_args(["list", "--section", "Civil"])
    artifacts = list(bulk.parse_catalog(CATALOG).artifacts[:4])

    class FakeClient:
        def list_artifacts(self, **kwargs):
            assert kwargs == {"section": "Civil", "family": None}
            return artifacts

    monkeypatch.setattr(bulk, "_log", lambda *_args: None)
    result = bulk.execute(
        args,
        access_decision=allowed(),
        client=FakeClient(),
    )

    assert result.status.value == "ok"
    assert len(result.records) == 4
    assert result.query.query.metadata["access_decision"]["allowed"] is True
    assert all(
        row["record_scope"] == "court_bulk_catalog_member"
        for row in result.records
    )


def test_execute_download_exposes_raw_artifact_reference(
    monkeypatch,
    tmp_path,
):
    args = bulk.build_parser().parse_args([
        "download",
        bulk.SENTINEL_LOCATOR,
        "--destination",
        str(tmp_path / "field-codes.xlsx"),
    ])
    artifact = bulk.parse_catalog(CATALOG).artifacts[1]
    destination = tmp_path / "field-codes.xlsx"

    class FakeClient:
        def download(self, selector, target, *, overwrite):
            assert selector == bulk.SENTINEL_LOCATOR
            assert target == destination
            assert overwrite is False
            return {
                "artifact": artifact,
                "artifact_receipt": {
                    "path": str(destination.resolve()),
                    "size": 123,
                    "sha256": "a" * 64,
                    "content_type": "text/plain",
                    "content_disposition": (
                        "attachment;filename="
                        "2024-08-15 FIELD_CODES.xlsx"
                    ),
                    "response_filename": (
                        "2024-08-15 FIELD_CODES.xlsx"
                    ),
                    "source_url": bulk.CATALOG_URL,
                },
            }

    monkeypatch.setattr(bulk, "_log", lambda *_args: None)
    result = bulk.execute(
        args,
        access_decision=allowed(),
        client=FakeClient(),
    )

    assert result.status.value == "ok"
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    assert result.records[0]["artifact_receipt"]["size"] == 123


def test_run_sentinel_checks_stable_catalog_member_and_ooxml_signature():
    artifact = bulk.parse_catalog(CATALOG).artifacts[1]

    class FakeClient:
        def inspect(self, selector, *, sample_bytes):
            assert selector == bulk.SENTINEL_LOCATOR
            assert sample_bytes == bulk.DEFAULT_SAMPLE_BYTES
            return bulk.ProbeReceipt(
                artifact=artifact,
                response_url=bulk.CATALOG_URL,
                content_type="text/plain",
                content_length=None,
                content_disposition=(
                    "attachment;filename=2024-08-15 FIELD_CODES.xlsx"
                ),
                response_filename="2024-08-15 FIELD_CODES.xlsx",
                sample=XLSX_SAMPLE,
                catalog_artifacts=bulk.parse_catalog(CATALOG).artifacts,
            )

    payload = bulk.run_sentinel(FakeClient())

    assert payload["status"] == "ok"
    assert payload["sentinel"]["native_locator"] == (
        bulk.SENTINEL_LOCATOR
    )
    assert payload["sentinel"]["signature_hex"] == "504b0304"
    assert payload["catalog"]["artifact_count"] == 8
    assert payload["catalog"]["section_counts"] == {
        "Civil": 4,
        "Criminal": 4,
    }
    assert len(payload["catalog"]["artifact_fingerprint"]) == 64


def test_execute_returns_structured_access_failure(monkeypatch):
    args = bulk.build_parser().parse_args(["list"])
    monkeypatch.setattr(bulk, "_log", lambda *_args: None)

    result = bulk.execute(
        args,
        access_decision={
            "allowed": False,
            "access_class": "C",
            "automation_disposition": "human_required",
            "reason_code": "fixture_denied",
            "reason": "fixture",
        },
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "fixture_denied"
