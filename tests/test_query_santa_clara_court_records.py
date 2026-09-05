from __future__ import annotations

import argparse
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest

from tools import query_santa_clara_court_records as santa_clara
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus
from tools.public_records_http import RetryPolicy


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "santa_clara_court_records"
)


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


PDF_BYTES = b"%PDF-1.7\nSanta Clara fixture\n%%EOF\n"


@dataclass
class FakeResponse:
    status_code: int = 200
    text: str = ""
    content: bytes = b""
    url: str = santa_clara.TENTATIVE_URL
    headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "text/html; charset=UTF-8"}
    )


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Santa Clara request")
        return self.responses.pop(0)


class FakeClient:
    def __init__(self) -> None:
        self.directory = santa_clara.parse_departments(
            fixture("departments.html"),
            require_complete=False,
        )
        self.ruling_index = santa_clara.parse_ruling_artifacts(
            fixture("department_1.html"),
            department=1,
            source_url=(
                f"{santa_clara.TENTATIVE_URL}/"
                "department-1-tentative-rulings"
            ),
        )
        self.civil = santa_clara.parse_product_page(
            fixture("civil_product.html"),
            product_kind="civil",
        )
        self.criminal = santa_clara.parse_product_page(
            fixture("criminal_product.html"),
            product_kind="criminal",
        )
        self.calls: list[tuple[Any, ...]] = []

    def departments(self) -> santa_clara.DepartmentDirectory:
        self.calls.append(("departments",))
        return self.directory

    def ruling_artifacts(
        self,
        record: dict[str, Any],
    ) -> santa_clara.RulingArtifactIndex:
        self.calls.append(("ruling_artifacts", record["department"]))
        return replace(
            self.ruling_index,
            department=int(record["department"]),
        )

    def product(self, kind: str) -> santa_clara.ProductPage:
        self.calls.append(("product", kind))
        return self.civil if kind == "civil" else self.criminal

    def pdf(self, url: str) -> santa_clara.PDFArtifact:
        self.calls.append(("pdf", url))
        return santa_clara.PDFArtifact(
            source_url=url,
            content=PDF_BYTES,
            media_type="application/pdf",
            sha256=__import__("hashlib").sha256(PDF_BYTES).hexdigest(),
        )


def parse_args(*values: str) -> argparse.Namespace:
    return santa_clara.build_parser().parse_args(list(values))


def test_sources_keep_open_publications_distinct_from_portal_forms() -> None:
    client = FakeClient()
    result = santa_clara.execute(
        parse_args("sources"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert client.calls == []
    assert {record["source_id"] for record in result.records} == {
        santa_clara.TENTATIVE_SOURCE_ID,
        santa_clara.CIVIL_INDEX_SOURCE_ID,
        santa_clara.CRIMINAL_INDEX_SOURCE_ID,
        santa_clara.PORTAL_SOURCE_ID,
    }
    portal = next(
        record
        for record in result.records
        if record["source_id"] == santa_clara.PORTAL_SOURCE_ID
    )
    assert {
        operation["name"] for operation in portal["operations"]
    } == {
        "case_number_search",
        "party_search",
        "business_search",
        "filing_date_search",
        "calendar_selection",
    }
    assert set(portal["open_alternatives"]) == {
        santa_clara.TENTATIVE_SOURCE_ID,
        santa_clara.CIVIL_INDEX_SOURCE_ID,
        santa_clara.CRIMINAL_INDEX_SOURCE_ID,
    }


def test_department_parser_preserves_judge_schedule_and_route() -> None:
    directory = santa_clara.parse_departments(
        fixture("departments.html"),
        require_complete=False,
    )

    assert len(directory.records) == 2
    first = directory.records[0]
    assert first["department"] == 1
    assert first["judge"] == "Eunice W. Lee"
    assert first["ruling_calendar"] == "Civil Law and Motion"
    assert first["scheduled_hearings"] == "Tuesdays & Thursdays"
    assert first["department_url"].endswith(
        "/department-1-tentative-rulings"
    )
    assert len(directory.schema_fingerprint) == 64


def test_department_complete_set_is_an_integrity_invariant() -> None:
    with pytest.raises(santa_clara.SantaClaraSourceChangedError) as raised:
        santa_clara.parse_departments(fixture("departments.html"))

    assert raised.value.code == "department_coverage_changed"
    assert raised.value.details["observed"] == [1, 2]


def test_ruling_index_only_includes_tentative_ruling_pdfs() -> None:
    index = santa_clara.parse_ruling_artifacts(
        fixture("department_1.html"),
        department=1,
        source_url=(
            f"{santa_clara.TENTATIVE_URL}/"
            "department-1-tentative-rulings"
        ),
    )

    assert len(index.artifacts) == 2
    assert {
        artifact["label"] for artifact in index.artifacts
    } == {
        "Tentative rulings for Tuesday",
        "Tentative rulings for Thursday",
    }
    assert all(
        "/system/files/tentative-ruling/" in artifact["source_url"]
        for artifact in index.artifacts
    )
    assert all(
        artifact["publication_state"] == "current_until_replaced"
        for artifact in index.artifacts
    )


def test_product_pages_validate_distinct_fields_and_artifacts() -> None:
    civil = santa_clara.parse_product_page(
        fixture("civil_product.html"),
        product_kind="civil",
    )
    criminal = santa_clara.parse_product_page(
        fixture("criminal_product.html"),
        product_kind="criminal",
    )
    civil_record = santa_clara._product_record(civil)  # noqa: SLF001
    criminal_record = santa_clara._product_record(criminal)  # noqa: SLF001

    assert civil.source_id == santa_clara.CIVIL_INDEX_SOURCE_ID
    assert len(civil.artifacts) == 2
    assert "counsel_name_and_address" in civil_record["included_fields"]
    assert "scheduled_event_information" in civil_record["included_fields"]
    assert criminal.source_id == santa_clara.CRIMINAL_INDEX_SOURCE_ID
    assert len(criminal.artifacts) == 3
    assert criminal_record["included_fields"] == [
        "case_number",
        "filing_date",
        "party_name",
    ]
    assert civil_record["acquisition"]["route"] == "court_request"


def test_changed_product_page_is_not_an_empty_product() -> None:
    with pytest.raises(santa_clara.SantaClaraSourceChangedError) as raised:
        santa_clara.parse_product_page(
            fixture("source_changed.html"),
            product_kind="civil",
        )

    assert raised.value.code == "product_markers_changed"


def test_client_retries_then_reports_incomplete_fixture_coverage() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse(text=fixture("departments.html")),
        ]
    )
    delays: list[float] = []
    client = santa_clara.SantaClaraCourtClient(
        session=session,
        minimum_interval=0,
        retry_policy=RetryPolicy(max_attempts=2, backoff_initial=0.01),
        sleeper=delays.append,
    )

    with pytest.raises(santa_clara.SantaClaraSourceChangedError):
        client.departments()

    assert len(session.calls) == 2
    assert delays == [0.01]
    assert session.headers["User-Agent"] == santa_clara.DEFAULT_USER_AGENT


def test_client_validates_pdf_signature() -> None:
    good = FakeSession(
        [
            FakeResponse(
                content=PDF_BYTES,
                url=(
                    f"{santa_clara.BASE_URL}/system/files/"
                    "tentative-ruling/dept-1-tues.pdf"
                ),
                headers={"Content-Type": "application/pdf"},
            )
        ]
    )
    pdf = santa_clara.SantaClaraCourtClient(
        session=good,
        minimum_interval=0,
    ).pdf(
        f"{santa_clara.BASE_URL}/system/files/"
        "tentative-ruling/dept-1-tues.pdf"
    )
    assert pdf.content == PDF_BYTES
    assert len(pdf.sha256) == 64

    bad = FakeSession(
        [
            FakeResponse(
                content=b"<html>moved</html>",
                url=santa_clara.REQUEST_FORM_URL,
            )
        ]
    )
    with pytest.raises(santa_clara.SantaClaraSourceChangedError):
        santa_clara.SantaClaraCourtClient(
            session=bad,
            minimum_interval=0,
        ).pdf(santa_clara.REQUEST_FORM_URL)


def test_execute_departments_and_rulings_use_tentative_source() -> None:
    client = FakeClient()
    departments = santa_clara.execute(
        parse_args("departments"),
        client=client,
        log_results=False,
    )
    rulings = santa_clara.execute(
        parse_args("rulings", "--department", "1"),
        client=client,
        log_results=False,
    )

    assert departments.query.source.source_id == (
        santa_clara.TENTATIVE_SOURCE_ID
    )
    assert len(departments.records) == 2
    assert rulings.status is ResultStatus.OK
    assert len(rulings.records) == 2
    validate_envelope(rulings.to_dict())


def test_unknown_department_is_structured_selection_error() -> None:
    result = santa_clara.execute(
        parse_args("rulings", "--department", "99"),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "unknown_department"
    assert result.errors[0].category == "query_selection"


def test_products_preserve_source_identity_and_no_default_cap() -> None:
    result = santa_clara.execute(
        parse_args("products"),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) == 2
    assert {record["source_id"] for record in result.records} == {
        santa_clara.CIVIL_INDEX_SOURCE_ID,
        santa_clara.CRIMINAL_INDEX_SOURCE_ID,
    }
    assert "limit" not in result.query.query.parameters


def test_download_writes_validated_pdf_and_hash(tmp_path: Path) -> None:
    destination = tmp_path / "ruling.pdf"
    result = santa_clara.execute(
        parse_args(
            "download",
            (
                f"{santa_clara.BASE_URL}/system/files/"
                "tentative-ruling/dept-1-tues.pdf"
            ),
            str(destination),
        ),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == PDF_BYTES
    assert result.records[0]["sha256"] == __import__("hashlib").sha256(
        PDF_BYTES
    ).hexdigest()
    assert result.query.source.source_id == santa_clara.TENTATIVE_SOURCE_ID


def test_probe_checks_open_artifact_and_both_product_routes() -> None:
    result = santa_clara.execute(
        parse_args("probe"),
        client=FakeClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["department_count"] == 2
    assert probe["ruling_artifact_count"] == 2
    assert probe["ruling_pdf"]["media_type"] == "application/pdf"
    assert {product["product_kind"] for product in probe["products"]} == {
        "civil",
        "criminal",
    }
    assert probe["portal_operation_observation"][
        "search_and_calendar_forms"
    ] == "recaptcha"
