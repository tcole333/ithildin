from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_pa_opinions
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURE_DIR = Path("tests/fixtures/public_records/pa_opinions")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(
        self,
        *,
        payload: Any | None = None,
        content: bytes = b"",
        url: str = query_pa_opinions.API_URL,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        self.payload = payload
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def json(self) -> Any:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if not self.responses:
            raise AssertionError("unexpected Pennsylvania opinions request")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(
        self,
        collection: query_pa_opinions.PAOpinionsCollection,
        *,
        page: query_pa_opinions.PAOpinionsPage | None = None,
        pdf: query_pa_opinions.PAOpinionPDF | None = None,
    ) -> None:
        self.collection = collection
        self.page = page
        self.pdf = pdf
        self.all_calls: list[dict[str, str]] = []
        self.page_calls: list[tuple[dict[str, str], int]] = []
        self.pdf_calls: list[str] = []

    def fetch_all(
        self,
        selection: Mapping[str, str],
    ) -> query_pa_opinions.PAOpinionsCollection:
        self.all_calls.append(dict(selection))
        return self.collection

    def fetch_page(
        self,
        selection: Mapping[str, str],
        *,
        page_number: int,
    ) -> query_pa_opinions.PAOpinionsPage:
        self.page_calls.append((dict(selection), page_number))
        if self.page is None:
            raise AssertionError("unexpected page fetch")
        return self.page

    def fetch_pdf(self, source_url: str) -> query_pa_opinions.PAOpinionPDF:
        self.pdf_calls.append(source_url)
        if self.pdf is None:
            raise AssertionError("unexpected PDF fetch")
        return self.pdf


class NeverClient:
    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"source dispatch should not occur: {name}")


def _parse(*values: str) -> Any:
    return query_pa_opinions.build_parser().parse_args(list(values))


def _collection(
    *pages: query_pa_opinions.PAOpinionsPage,
    incomplete_error: query_pa_opinions.PAOpinionsError | None = None,
) -> query_pa_opinions.PAOpinionsCollection:
    first = pages[0]
    return query_pa_opinions.PAOpinionsCollection(
        items=tuple(item for page in pages for item in page.items),
        pages_fetched=len(pages),
        page_size=first.page_size,
        total_items=first.total_items,
        total_pages=first.total_pages,
        source_urls=tuple(page.source_url for page in pages),
        schema_fingerprints=tuple(
            page.schema_fingerprint for page in pages
        ),
        incomplete_error=incomplete_error,
    )


def test_page_parser_validates_native_pagination_and_schema() -> None:
    page = query_pa_opinions.parse_page(_fixture("supreme_page_1.json"))

    assert page.page_number == 1
    assert page.page_size == 1
    assert page.total_items == 2
    assert page.total_pages == 2
    assert page.has_next is True
    assert page.has_previous is False
    assert page.items[0]["Id"] == 85654
    assert len(page.schema_fingerprint) == 64


def test_source_change_fixture_becomes_explicit_source_changed_result() -> None:
    session = FakeSession(
        [FakeResponse(payload=_fixture("source_changed.json"))]
    )
    client = query_pa_opinions.PAOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    result = query_pa_opinions.execute(
        _parse("list", "--court", "supreme", "--year", "2026"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "pagination_fields_changed"
    assert result.records == ()


def test_client_exhausts_every_native_page_without_adapter_cap() -> None:
    first = _fixture("supreme_page_1.json")
    second = _fixture("supreme_page_2.json")
    session = FakeSession(
        [
            FakeResponse(payload=first, url=f"{query_pa_opinions.API_URL}?p=1"),
            FakeResponse(payload=second, url=f"{query_pa_opinions.API_URL}?p=2"),
        ]
    )
    client = query_pa_opinions.PAOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )
    selection = {
        "year": "2026",
        "month": "",
        "courtType": "SUPREME",
    }

    collection = client.fetch_all(selection)

    assert collection.incomplete_error is None
    assert collection.pages_fetched == 2
    assert collection.total_items == 2
    assert [item["Id"] for item in collection.items] == [85654, 85648]
    assert session.calls[0][1]["params"] == selection
    assert session.calls[1][1]["params"] == {
        **selection,
        "pageNumber": 2,
    }


def test_supreme_posting_normalizes_identity_docket_dates_and_pdf() -> None:
    first = query_pa_opinions.parse_page(
        _fixture("supreme_page_1.json")
    )
    second = query_pa_opinions.parse_page(
        _fixture("supreme_page_2.json")
    )
    records = query_pa_opinions.normalize_collection(
        _collection(first, second),
        court_key="supreme",
        selection={"courtType": "SUPREME", "year": "2026"},
    )

    assert len(records) == 2
    record = records[0]
    assert record["record_kind"] == "appellate_opinion_posting"
    assert record["native_opinion_id"] == "85654"
    assert record["native_posting_id"] == "94487"
    assert record["canonical_ref"].endswith(
        "/supreme/85654/94487"
    )
    assert record["court"] == {
        "court_id": "pa-supreme-court",
        "native_court_id": "SUPREME",
        "name": "Supreme Court of Pennsylvania",
        "state_code": "PA",
        "court_level": "appellate",
        "official_url": query_pa_opinions.COURTS["supreme"]["page_url"],
    }
    assert record["docket_number"] == "69 WAL 2026"
    assert record["decision_date"] == "2026-07-28"
    assert record["posted_date"] == "2026-07-28"
    assert record["author"] == "Per Curiam"
    assert record["posting_type_code"] == "paa"
    assert record["posting_type"] == "Petitions for Allowance of Appeal"
    assert record["publication_type"] is None
    assert record["pdf_url"] == (
        f"{query_pa_opinions.BASE_URL}/assets/opinions/Supreme/out/"
        "69WAL2026%20-%20106867381367916784.pdf?cb=1"
    )
    assert record["source_scope"]["complete_docket"] is False
    assert record["source_scope"]["underlying_party_filings"] is False


def test_superior_and_commonwealth_metadata_variants_normalize() -> None:
    superior_page = query_pa_opinions.parse_page(
        _fixture("superior_page.json")
    )
    commonwealth_page = query_pa_opinions.parse_page(
        _fixture("commonwealth_page.json")
    )

    superior = query_pa_opinions.normalize_collection(
        _collection(superior_page),
        court_key="superior",
        selection={"courtType": "SUPERIOR", "year": "2026"},
    )[0]
    commonwealth = query_pa_opinions.normalize_collection(
        _collection(commonwealth_page),
        court_key="commonwealth",
        selection={"courtType": "COMMONWEALTH", "year": "2026"},
    )[0]

    assert superior["docket_number"] == "983 EDA 2026"
    assert superior["author"] == "Olson, J."
    assert superior["posting_type_code"] == "6"
    assert superior["posting_type"] == "Judgment Order"
    assert superior["publication_type"] == "Non-Precedential"
    assert superior["rendered_date"] is None
    assert commonwealth["docket_number"] == "276 C.D. 2025"
    assert commonwealth["author"] == "McCullough, J."
    assert commonwealth["posting_type"] == "Majority Opinion"
    assert commonwealth["publication_type"] == "Precedential"
    assert commonwealth["native_posting_id"] != "0"
    repeated = query_pa_opinions.normalize_collection(
        _collection(commonwealth_page),
        court_key="commonwealth",
        selection={"courtType": "COMMONWEALTH", "year": "2026"},
    )[0]
    assert repeated["native_posting_id"] == commonwealth["native_posting_id"]


def test_authoritative_zero_item_fixture_is_no_results() -> None:
    page = query_pa_opinions.parse_page(_fixture("no_results.json"))
    client = FakeClient(_collection(page))

    result = query_pa_opinions.execute(
        _parse(
            "list",
            "--court",
            "supreme",
            "--year",
            "1998",
            "--caption",
            "ZZZ-NO-SUCH-OPINION-999",
        ),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.NO_RESULTS
    assert result.records == ()
    assert result.errors == ()


def test_native_selection_supports_date_filters_and_exact_docket_year() -> None:
    listing = query_pa_opinions.native_selection(
        _parse(
            "list",
            "--court",
            "superior",
            "--date-from",
            "2026-07-01",
            "--date-to",
            "2026-07-31",
            "--caption",
            "Williams",
            "--author",
            "Olson",
            "--post-type",
            "6",
            "--post-type",
            "7",
            "--publication-type",
            "Non-Precedential",
            "--sort",
            "oldest",
        )
    )
    docket = query_pa_opinions.native_selection(
        _parse(
            "docket",
            "69 WAL 2026",
            "--court",
            "supreme",
        )
    )

    assert listing == {
        "startDate": "2026-07-01",
        "endDate": "2026-07-31",
        "courtType": "SUPERIOR",
        "captionText": "Williams",
        "authorName": "Olson",
        "publicationType": "Non-Precedential",
        "postTypes": "6,7",
        "sortDirection": "1",
    }
    assert docket == {
        "year": "2026",
        "month": "",
        "courtType": "SUPREME",
        "captionText": "69 WAL 2026",
        "sortDirection": "-1",
    }
    assert (
        _parse("list", "--court", "supreme", "--year", "2026").limit
        is None
    )


def test_month_without_year_and_reversed_dates_are_selection_errors() -> None:
    with pytest.raises(
        query_pa_opinions.PAOpinionsSelectionError
    ) as month_error:
        query_pa_opinions.native_selection(
            _parse(
                "list",
                "--court",
                "supreme",
                "--date-from",
                "2026-07-01",
                "--date-to",
                "2026-07-31",
                "--month",
                "7",
            )
        )
    assert month_error.value.code == "month_requires_year"

    with pytest.raises(
        query_pa_opinions.PAOpinionsSelectionError
    ) as range_error:
        query_pa_opinions.native_selection(
            _parse(
                "list",
                "--court",
                "supreme",
                "--date-from",
                "2026-07-31",
                "--date-to",
                "2026-07-01",
            )
        )
    assert range_error.value.code == "date_range_reversed"


def test_catalog_denial_stops_before_source_dispatch() -> None:
    result = query_pa_opinions.execute(
        _parse("docket", "69 WAL 2026", "--court", "supreme"),
        access_decision={
            "allowed": False,
            "access_class": "C",
            "reason_code": "route_unavailable",
            "reason": "Use another acquisition route",
        },
        client=NeverClient(),
        log_results=False,
    )

    assert result.status is ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "route_unavailable"
    assert result.records == ()


def test_partial_native_pagination_preserves_fetched_records() -> None:
    first = query_pa_opinions.parse_page(
        _fixture("supreme_page_1.json")
    )
    incomplete = query_pa_opinions.PAOpinionsPaginationError(
        "page two failed",
        details={"page_number": 2},
    )
    client = FakeClient(_collection(first, incomplete_error=incomplete))

    result = query_pa_opinions.execute(
        _parse("list", "--court", "supreme", "--year", "2026"),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.PARTIAL
    assert len(result.records) == 1
    assert result.errors[0].code == "native_pagination_incomplete"
    assert (
        result.records[0]["source_scope"]["native_pagination_exhausted"]
        is False
    )


def test_download_writes_pdf_and_returns_hash_receipt(tmp_path: Path) -> None:
    source_url = (
        f"{query_pa_opinions.BASE_URL}/assets/opinions/Supreme/out/"
        "69WAL2026%20-%20106867381367916784.pdf?cb=1"
    )
    content = b"%PDF-1.7\nfixture Pennsylvania opinion\n"
    pdf = query_pa_opinions.PAOpinionPDF(
        content=content,
        source_url=source_url,
        media_type="application/pdf",
        sha256=hashlib.sha256(content).hexdigest(),
        court_key="supreme",
    )
    page = query_pa_opinions.parse_page(_fixture("no_results.json"))
    client = FakeClient(_collection(page), pdf=pdf)
    destination = tmp_path / "opinion.pdf"

    result = query_pa_opinions.execute(
        _parse("download", source_url, str(destination)),
        client=client,
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert destination.read_bytes() == content
    record = result.to_dict()["records"][0]
    assert record["sha256"] == hashlib.sha256(content).hexdigest()
    assert record["byte_length"] == len(content)
    assert record["media_type"] == "application/pdf"
    assert record["court"]["court_id"] == "pa-supreme-court"
    assert result.raw_artifact_refs == (str(destination),)
    assert client.pdf_calls == [source_url]


def test_pdf_transport_rejects_non_pdf_and_nonofficial_route() -> None:
    official_url = (
        f"{query_pa_opinions.BASE_URL}/assets/opinions/Supreme/out/test.pdf"
    )
    session = FakeSession(
        [
            FakeResponse(
                content=b"<html>not a PDF</html>",
                url=official_url,
                content_type="text/html",
            )
        ]
    )
    client = query_pa_opinions.PAOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    with pytest.raises(
        query_pa_opinions.PAOpinionsSourceChangedError
    ) as invalid_pdf:
        client.fetch_pdf(official_url)
    assert invalid_pdf.value.code == "pdf_response_invalid"

    with pytest.raises(query_pa_opinions.PAOpinionsSelectionError):
        client.fetch_pdf("https://example.com/opinion.pdf")


def test_sentinel_checks_metadata_identity_and_pdf() -> None:
    first = query_pa_opinions.parse_page(
        _fixture("supreme_page_1.json")
    )
    second = query_pa_opinions.parse_page(
        _fixture("supreme_page_2.json")
    )
    content = b"%PDF-1.7\nsentinel\n"
    source_url = (
        f"{query_pa_opinions.BASE_URL}/assets/opinions/Supreme/out/"
        "69WAL2026%20-%20106867381367916784.pdf?cb=1"
    )
    client = FakeClient(
        _collection(first, second),
        pdf=query_pa_opinions.PAOpinionPDF(
            content=content,
            source_url=source_url,
            media_type="application/pdf",
            sha256=hashlib.sha256(content).hexdigest(),
            court_key="supreme",
        ),
    )

    result = query_pa_opinions.execute(
        _parse("sentinel"),
        client=client,
        log_results=False,
    )
    payload = result.to_dict()
    validate_envelope(payload)

    assert result.status is ResultStatus.OK
    assert len(result.records) == 1
    record = result.records[0]
    assert record["sentinel"] is True
    assert record["native_opinion_id"] == "85654"
    assert record["native_posting_id"] == "94487"
    assert record["sentinel_pdf_sha256"] == hashlib.sha256(
        content
    ).hexdigest()
    assert client.pdf_calls == [source_url]

