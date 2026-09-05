from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_ojcin_products as ojcin


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_ojcin_products"
)


@dataclass
class FixtureResponse:
    text: str = ""
    content: bytes = b""
    status_code: int = 200
    url: str = ojcin.OJCIN_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=utf-8"}
    )


class MappingSession:
    def __init__(self, responses: dict[str, FixtureResponse]):
        self.responses = responses
        self.headers: dict[str, str] = {}
        self.calls: list[dict[str, Any]] = []

    def get(self, url, *, timeout=None, allow_redirects=None):
        self.calls.append(
            {
                "url": url,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        try:
            return self.responses[url]
        except KeyError as exc:
            raise AssertionError(f"unexpected request: {url}") from exc


def _html(name: str, url: str) -> FixtureResponse:
    text = (FIXTURE_DIR / name).read_text(encoding="utf-8")
    return FixtureResponse(text=text, content=text.encode(), url=url)


def _pdf(url: str) -> FixtureResponse:
    content = bytes.fromhex(
        (FIXTURE_DIR / "pdf-sample.hex").read_text(encoding="ascii").strip()
    )
    return FixtureResponse(
        content=content,
        url=url,
        headers={
            "Content-Type": "application/pdf",
            "Content-Length": str(len(content)),
        },
    )


def _session() -> MappingSession:
    return MappingSession(
        {
            ojcin.OJCIN_URL: _html("ojcin.html", ojcin.OJCIN_URL),
            ojcin.SIGNUP_URL: _html(
                "ojcin-signup.html",
                ojcin.SIGNUP_URL,
            ),
            ojcin.FEE_SCHEDULE_URL: _pdf(ojcin.FEE_SCHEDULE_URL),
            ojcin.CURRENT_CJO_URL: _pdf(ojcin.CURRENT_CJO_URL),
            ojcin.TERMS_URL: _pdf(ojcin.TERMS_URL),
            ojcin.CUSTOMER_FORM_URL: _pdf(ojcin.CUSTOMER_FORM_URL),
            ojcin.DOCUMENT_ACCESS_FORM_URL: _pdf(
                ojcin.DOCUMENT_ACCESS_FORM_URL
            ),
            ojcin.OECI_LOGIN_URL: _html(
                "oeci-login.html",
                ojcin.OECI_LOGIN_URL,
            ),
            ojcin.ACMS_LOGIN_URL: _html(
                "acms-login.html",
                ojcin.ACMS_LOGIN_URL,
            ),
            ojcin.RECORDS_REQUEST_URL: _html(
                "records-request.html",
                ojcin.RECORDS_REQUEST_URL,
            ),
            ojcin.OSCA_REQUEST_PORTAL_URL: _html(
                "govqa.html",
                ojcin.OSCA_REQUEST_PORTAL_URL,
            ),
            ojcin.CASE_COPY_REQUEST_URL: _html(
                "case-copy.html",
                ojcin.CASE_COPY_REQUEST_URL,
            ),
            ojcin.FREE_SEARCH_INFO_URL: _html(
                "free-search-info.html",
                ojcin.FREE_SEARCH_INFO_URL,
            ),
        }
    )


def _client(session: MappingSession) -> ojcin.OfficialEndpointClient:
    return ojcin.OfficialEndpointClient(
        session,
        minimum_interval=0,
        max_retries=0,
    )


def test_products_are_separately_attributable() -> None:
    records = ojcin.product_records()

    assert len(records) == 5
    assert len({record["product_id"] for record in records}) == 5
    assert all(
        record["source"]["source_id"] == record["product_id"]
        for record in records
    )
    assert all(record["official_evidence"] for record in records)


def test_product_scope_and_current_products_are_exact() -> None:
    oeci = ojcin.PRODUCTS["us-or-ojcin-oeci-subscription"].to_record()
    acms = ojcin.PRODUCTS["us-or-ojcin-acms-subscription"].to_record()
    reports = ojcin.PRODUCTS[
        "us-or-ojcin-standard-report-package"
    ].to_record()
    bulk = ojcin.PRODUCTS["us-or-ojcin-bulk-data-transfer"].to_record()

    assert "all 36 Oregon circuit courts" in oeci["coverage"]["courts"]
    assert acms["coverage"]["courts"] == (
        "Oregon Supreme Court and Oregon Court of Appeals"
    )
    assert reports["contents"] == [
        "criminal judgment index",
        "civil judgment index",
        "case index",
    ]
    assert reports["current_fees"]["monthly_add_on_usd"] == 29
    assert bulk["current_fees"]["initial_bulk_administrative_fee_usd"] == 1200
    assert bulk["current_fees"]["monthly_bulk_add_on_usd"] == 575


def test_statewide_request_handoff_keeps_complements_distinct() -> None:
    handoff = ojcin.handoff_record(
        "us-or-osca-statewide-court-data-request"
    )

    assert handoff["acquisition"]["online_portal_url"] == (
        ojcin.OSCA_REQUEST_PORTAL_URL
    )
    roles = {item["role"] for item in handoff["complements"]}
    assert "free_basic_case_and_calendar_discovery" in roles
    assert "separately_acquired_case_documents_and_audio" in roles
    copy_route = next(
        item
        for item in handoff["complements"]
        if item["role"] == "separately_acquired_case_documents_and_audio"
    )
    assert copy_route["documented_formats"] == ["PDF", "TIFF", "paper"]


def test_search_finds_product_without_collapsing_attribution() -> None:
    records = ojcin.search_products("criminal judgment index")

    assert [record["product_id"] for record in records] == [
        "us-or-ojcin-standard-report-package"
    ]


def test_probe_validates_all_official_representations() -> None:
    session = _session()

    result = ojcin.probe_all(_client(session))

    assert result["status"] == "ok"
    assert result["endpoint_count"] == 13
    assert result["ok_count"] == 13
    assert all(probe["representation_ok"] for probe in result["probes"])
    assert len(session.calls) == 13


def test_fee_schedule_is_attributed_only_to_ojcin_products() -> None:
    fee_schedule = next(
        endpoint
        for endpoint in ojcin.ENDPOINTS
        if endpoint.endpoint_id == "fee_schedule"
    )

    assert set(fee_schedule.source_ids) == {
        "us-or-ojcin-oeci-subscription",
        "us-or-ojcin-acms-subscription",
        "us-or-ojcin-standard-report-package",
        "us-or-ojcin-bulk-data-transfer",
    }
    assert (
        "us-or-osca-statewide-court-data-request"
        not in fee_schedule.source_ids
    )


def test_probe_reports_representation_change_without_losing_other_results() -> None:
    session = _session()
    session.responses[ojcin.SIGNUP_URL] = FixtureResponse(
        text="<html>changed</html>",
        content=b"<html>changed</html>",
        url=ojcin.SIGNUP_URL,
    )

    result = ojcin.probe_all(_client(session))

    assert result["status"] == "partial"
    changed = next(
        probe
        for probe in result["probes"]
        if probe["endpoint_id"] == "ojcin_signup"
    )
    assert changed["status"] == "representation_changed"
    assert result["ok_count"] == 12


def test_delivery_receipt_hashes_files_and_does_not_parse_rows(
    tmp_path: Path,
) -> None:
    delivery = tmp_path / "delivery"
    delivery.mkdir()
    csv_file = delivery / "case-index.csv"
    csv_file.write_text(
        "case_number,party\n26CV00001,Example LLC\n",
        encoding="utf-8",
    )
    zip_file = delivery / "documents.zip"
    with zipfile.ZipFile(zip_file, "w") as archive:
        archive.writestr("README.txt", "OJD delivery note")

    receipt = ojcin.inspect_delivery(
        "us-or-ojcin-bulk-data-transfer",
        delivery,
        delivery_version="2026-07",
        received_at="2026-07-29T12:30:00-04:00",
        provider_reference="OJD-EXAMPLE",
        correction_state="original",
        specification_refs=("delivery-spec.pdf",),
        case_document_refs=("OR-CASE:26CV00001:document-4",),
    )

    assert receipt["file_count"] == 2
    assert receipt["delivery"]["received_at"] == "2026-07-29T16:30:00Z"
    assert receipt["interpretation"]["records_parsed"] == 0
    assert receipt["interpretation"]["rows_interpreted"] is False
    csv_record = next(
        item
        for item in receipt["files"]
        if item["relative_path"] == "case-index.csv"
    )
    assert csv_record["sha256"] == hashlib.sha256(
        csv_file.read_bytes()
    ).hexdigest()
    zip_record = next(
        item
        for item in receipt["files"]
        if item["relative_path"] == "documents.zip"
    )
    assert zip_record["zip_members"][0]["member_path"] == "README.txt"


def test_cli_products_writes_public_records_envelope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "products.json"
    args = ojcin.build_parser().parse_args(
        ["products", "--output", str(output)]
    )

    assert ojcin.run(args) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert len(payload["records"]) == 5
    assert "5 results" in capsys.readouterr().out


def test_delivery_receipt_requires_timezone(tmp_path: Path) -> None:
    delivery = tmp_path / "delivery.csv"
    delivery.write_text("a,b\n1,2\n", encoding="utf-8")

    with pytest.raises(ojcin.DeliveryInspectionError, match="timezone"):
        ojcin.inspect_delivery(
            "us-or-ojcin-standard-report-package",
            delivery,
            delivery_version="sample",
            received_at="2026-07-29T12:00:00",
        )
