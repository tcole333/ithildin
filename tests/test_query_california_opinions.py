from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

from tools import query_california_opinions as opinions
from tools.ingest_state_court_records import validate_envelope


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "california_opinions"
)


def _fixture_artifact(
    name: str,
    *,
    source_url: str,
    content_type: str = "text/html",
) -> opinions.Artifact:
    return opinions.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=source_url,
        media_type=content_type,
        headers={"content-type": content_type},
    )


def _listing_artifact(
    collection: str,
    *,
    body: bytes | None = None,
) -> opinions.Artifact:
    url = str(opinions.COLLECTIONS[collection]["url"])
    return opinions.Artifact(
        content=body or (FIXTURE_ROOT / f"{collection}.html").read_bytes(),
        source_url=f"{url}?items_per_page=50&page=0",
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


class FixtureClient:
    def __init__(self) -> None:
        self.listing_calls: list[dict[str, Any]] = []
        self.detail_calls: list[str] = []
        self.citings_calls: list[str] = []
        self.document_calls: list[str] = []
        self.published_body: bytes | None = None

    def listing(
        self,
        collection: str,
        *,
        page: int,
        page_size: int,
        court_native_id: str | None = None,
        case_number: str | None = None,
        title: str | None = None,
    ) -> opinions.Artifact:
        self.listing_calls.append(
            {
                "collection": collection,
                "page": page,
                "page_size": page_size,
                "court_native_id": court_native_id,
                "case_number": case_number,
                "title": title,
            }
        )
        return _listing_artifact(
            collection,
            body=(
                self.published_body
                if collection == "published"
                else None
            ),
        )

    def detail(self, url: str) -> opinions.Artifact:
        self.detail_calls.append(url)
        name = (
            "detail-unpublished.html"
            if "/unpublished/" in url
            else "detail-published.html"
        )
        return _fixture_artifact(name, source_url=url)

    def citings(self, url: str) -> opinions.Artifact:
        self.citings_calls.append(url)
        return _fixture_artifact("citings.html", source_url=url)

    def document(self, url: str) -> opinions.Artifact:
        self.document_calls.append(url)
        return opinions.Artifact(
            content=b"%PDF-1.7\nfixture opinion\n",
            source_url=url,
            media_type="application/pdf",
            headers={"content-type": "application/pdf"},
        )


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str,
        status_code: int = 200,
        content_type: str = "text/html; charset=UTF-8",
    ) -> None:
        self.content = body
        self.text = body.decode("utf-8", errors="replace")
        self.url = url
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any]]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.response

    def close(self) -> None:
        self.closed = True


def _args(*values: str) -> Any:
    return opinions.build_parser().parse_args(list(values))


def test_published_listing_preserves_slip_and_corrected_text_distinction() -> None:
    page = opinions.parse_listing_page(
        _listing_artifact("published"),
        collection="published",
        requested_page=0,
        requested_page_size=50,
    )

    assert page.total_count == 2
    assert page.total_pages == 1
    assert len(page.schema_fingerprint) == 64
    assert len(page.page_fingerprint) == 64
    assert page.source_taxonomy["103"] == "Supreme Court"
    first = page.records[0]
    assert first["case_number"] == "S287786"
    assert first["publication_status"] == "published"
    assert first["document_version"] == "slip_opinion_as_filed"
    assert first["corrected_official_reports_text_included"] is False
    assert first["official_reports_search_url"] == (
        opinions.OFFICIAL_REPORTS_SEARCH_URL
    )
    assert first["citings_archive_url"].endswith(
        "/opinion/citings-archive/2026-07-30/s287786"
    )
    assert first["documents"][0]["url"].endswith(
        "/opinions/documents/S287786.PDF"
    )
    assert first["projection"]["projectable_as_case"] is False


def test_modified_opinion_identifier_crosswalks_to_base_appellate_case() -> None:
    body = (
        (FIXTURE_ROOT / "published.html")
        .read_bytes()
        .replace(b"S287786", b"S287786M")
        .replace(b"s287786", b"s287786m")
        .replace(
            b"query_caseNumber=S287786M",
            b"query_caseNumber=S287786",
        )
    )

    page = opinions.parse_listing_page(
        _listing_artifact("published", body=body),
        collection="published",
        requested_page=0,
        requested_page_size=50,
    )

    first = page.records[0]
    assert first["case_number"] == "S287786"
    assert first["appellate_case_number"] == "S287786"
    assert first["opinion_identifier"] == "S287786M"
    assert first["opinion_identifier_suffix"] == "M"
    assert "/S287786/opinion/" in first["canonical_ref"]
    assert first["documents"][0]["url"].endswith("S287786M.PDF")


def test_unpublished_listing_preserves_non_citable_status_and_pdf_family() -> None:
    page = opinions.parse_listing_page(
        _listing_artifact("unpublished"),
        collection="unpublished",
        requested_page=0,
        requested_page_size=50,
    )

    assert "103" not in page.source_taxonomy
    first = page.records[0]
    assert first["case_number"] == "H052909"
    assert first["publication_status"] == "unpublished"
    assert first["citation_status"] == (
        "generally_non_citable_under_rule_8_1115"
    )
    assert first["document_version"] == (
        "unpublished_opinion_as_filed"
    )
    assert first["documents"][0]["url"].endswith(
        "/opinions/nonpub/H052909.PDF"
    )


def test_filtered_source_taxonomy_can_be_a_result_driven_subset() -> None:
    root = BeautifulSoup(
        """
        <div>
          <select name="field_opinion_source_target_id">
            <option value="All">- Any -</option>
            <option value="105">6th District Court of Appeal</option>
          </select>
        </div>
        """,
        "html.parser",
    ).div

    assert opinions._taxonomy(root, "unpublished") == {
        "105": "6th District Court of Appeal"
    }


def test_empty_listing_is_authoritative_no_results() -> None:
    client = FixtureClient()
    client.published_body = (FIXTURE_ROOT / "empty.html").read_bytes()

    result = opinions.execute(
        _args(
            "search",
            "--collection",
            "published",
            "--case-number",
            "ZZ999999",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    validate_envelope(result.to_dict())


def test_search_cursor_resumes_across_collections_without_duplicates() -> None:
    client = FixtureClient()
    first = opinions.execute(
        _args("search", "--collection", "both", "--limit", "1"),
        client=client,
        log_results=False,
    )
    second = opinions.execute(
        _args(
            "search",
            "--collection",
            "both",
            "--limit",
            "3",
            "--cursor",
            str(first.next_cursor),
        ),
        client=client,
        log_results=False,
    )

    assert [record["case_number"] for record in first.records] == [
        "S287786"
    ]
    assert [record["case_number"] for record in second.records] == [
        "E087240",
        "H052909",
        "D086666",
    ]
    assert first.next_cursor is not None
    assert second.next_cursor is None


def test_cursor_is_query_bound_and_page_fingerprint_bound() -> None:
    first_client = FixtureClient()
    first = opinions.execute(
        _args("search", "--collection", "published", "--limit", "1"),
        client=first_client,
        log_results=False,
    )

    mismatch = opinions.execute(
        _args(
            "search",
            "--collection",
            "published",
            "--title",
            "Different",
            "--cursor",
            str(first.next_cursor),
        ),
        client=FixtureClient(),
        log_results=False,
    )
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_query_mismatch"

    changed_client = FixtureClient()
    changed_client.published_body = (
        FIXTURE_ROOT / "published.html"
    ).read_bytes().replace(b"Sanmiguel", b"Sanmiguel-Changed")
    changed = opinions.execute(
        _args(
            "search",
            "--collection",
            "published",
            "--cursor",
            str(first.next_cursor),
        ),
        client=changed_client,
        log_results=False,
    )
    assert changed.status.value == "unavailable"
    assert changed.errors[0].code == "cursor_page_changed"


def test_native_filter_names_and_zero_based_page_are_forwarded() -> None:
    client = FixtureClient()

    result = opinions.execute(
        _args(
            "search",
            "--collection",
            "unpublished",
            "--court",
            "appeal-6",
            "--case-number",
            "H052909",
            "--title",
            "P. v. Li",
            "--page",
            "0",
            "--page-size",
            "100",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert client.listing_calls == [
        {
            "collection": "unpublished",
            "page": 0,
            "page_size": 100,
            "court_native_id": "105",
            "case_number": "H052909",
            "title": "P. v. Li",
        }
    ]


def test_http_client_uses_verified_get_parameters() -> None:
    response_url = (
        f"{opinions.UNPUBLISHED_URL}?"
        "items_per_page=100&page=0&"
        "field_opinion_source_target_id=105&"
        "field_case_number_plain_value=H052909&title=P.+v.+Li"
    )
    session = FakeSession(
        FakeResponse(
            (FIXTURE_ROOT / "unpublished.html").read_bytes(),
            url=response_url,
        )
    )
    client = opinions.CaliforniaOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    client.listing(
        "unpublished",
        page=0,
        page_size=100,
        court_native_id="105",
        case_number="H052909",
        title="P. v. Li",
    )

    method, url, kwargs = session.calls[0]
    assert method == "GET"
    assert url == opinions.UNPUBLISHED_URL
    assert kwargs["params"] == {
        "items_per_page": "100",
        "page": "0",
        "field_opinion_source_target_id": "105",
        "field_case_number_plain_value": "H052909",
        "title": "P. v. Li",
    }


def test_routine_recaptcha_asset_text_is_not_a_challenge() -> None:
    body = (
        (FIXTURE_ROOT / "published.html").read_bytes()
        + b"<!-- recaptcha/recaptcha library metadata -->"
    )
    session = FakeSession(
        FakeResponse(body, url=opinions.PUBLISHED_URL)
    )
    client = opinions.CaliforniaOpinionsClient(
        session=session,
        minimum_interval=0,
        sleeper=lambda _seconds: None,
    )

    artifact = client.get(opinions.PUBLISHED_URL)

    assert b"recaptcha/recaptcha" in artifact.content


@pytest.mark.parametrize(
    ("name", "url", "expected_status", "expected_case"),
    [
        (
            "detail-published.html",
            "https://courts.ca.gov/opinion/published/2026-07-30/s287786",
            "published",
            "S287786",
        ),
        (
            "detail-unpublished.html",
            "https://courts.ca.gov/opinion/unpublished/2026-07-30/h052909",
            "unpublished",
            "H052909",
        ),
    ],
)
def test_detail_inventory_includes_pdf_docx_and_case_information(
    name: str,
    url: str,
    expected_status: str,
    expected_case: str,
) -> None:
    record = opinions.parse_detail_page(
        _fixture_artifact(name, source_url=url)
    )

    assert record["case_number"] == expected_case
    assert record["publication_status"] == expected_status
    assert [item["format"] for item in record["formats"]] == [
        "pdf",
        "docx",
    ]
    assert "query_caseNumber=" + expected_case in (
        record["case_information_url"]
    )


def test_citings_archive_keeps_original_and_archived_urls_distinct() -> None:
    url = (
        "https://courts.ca.gov/opinion/"
        "citings-archive/2026-07-30/s287786"
    )
    record = opinions.parse_citings_page(
        _fixture_artifact("citings.html", source_url=url)
    )

    assert record["record_kind"] == "opinion_citings_archive"
    assert record["web_citing_count"] == 1
    citing = record["web_citings"][0]
    assert citing["original_url"].startswith(
        "https://newsroom.courts.ca.gov/"
    )
    assert citing["archived_copy_url"].endswith(
        "/system/files/opinion-citing/s287786-link1.pdf"
    )
    assert record["archive_role"] == (
        "preserved_copy_of_opinion_cited_web_material"
    )


def test_download_validates_and_hashes_exact_pdf(
    tmp_path: Path,
) -> None:
    client = FixtureClient()
    source_url = (
        "https://www.courts.ca.gov/opinions/documents/S287786.PDF"
    )
    destination = tmp_path / "S287786.PDF"

    result = opinions.execute(
        _args("download", source_url, str(destination)),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["case_number"] == "S287786"
    assert record["collection"] == "published"
    assert record["format"] == "pdf"
    assert record["sha256"] == hashlib.sha256(
        b"%PDF-1.7\nfixture opinion\n"
    ).hexdigest()
    assert destination.read_bytes().startswith(b"%PDF-")
    assert client.document_calls == [source_url]


def test_manifest_preserves_current_feeds_and_complementary_routes() -> None:
    result = opinions.execute(
        _args("manifest"),
        client=FixtureClient(),
        log_results=False,
    )

    manifest = result.records[0]
    assert manifest["observed_live_state"]["published_total"] == 243
    assert manifest["observed_live_state"]["unpublished_total"] == 1277
    assert manifest["collections"]["published"]["current_window_days"] == 120
    assert manifest["collections"]["unpublished"]["current_window_days"] == 60
    assert manifest["identity"]["publication_status_is_identity"] is False
    routes = {
        route["source_id"]: route
        for route in manifest["alternative_routes"]
    }
    assert routes["us-ca-official-reports-opinions"]["coverage"] == (
        "1850-present"
    )
    assert "post-filing corrections" in routes[
        "us-ca-official-reports-opinions"
    ]["adds"]
    assert "opinions after the 60-day unpublished feed window" in routes[
        "us-ca-appellate-case-information"
    ]["adds"]


def test_probe_reports_totals_schema_fingerprints_and_formats() -> None:
    result = opinions.execute(
        _args("probe"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    probe = result.records[0]
    assert probe["feed_totals"] == {
        "published": 2,
        "unpublished": 2,
    }
    assert len(probe["stable_contract_fingerprint"]) == 64
    assert len(probe["live_state_fingerprint"]) == 64
    assert probe["operations"]["published_detail"]["formats"] == (
        "pdf",
        "docx",
    )
    assert probe["operations"]["unpublished_detail"][
        "publication_status"
    ] == "unpublished"


def test_collection_specific_court_taxonomy_is_enforced() -> None:
    result = opinions.execute(
        _args(
            "search",
            "--collection",
            "unpublished",
            "--court",
            "supreme",
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "invalid_selection"


def test_unknown_result_court_is_source_change() -> None:
    changed = (FIXTURE_ROOT / "published.html").read_bytes().replace(
        b"Supreme Court \xe2\x80\xa2 Published Opinion",
        b"New Appellate Court \xe2\x80\xa2 Published Opinion",
        1,
    )

    with pytest.raises(opinions.SourceChangedError):
        opinions.parse_listing_page(
            _listing_artifact("published", body=changed),
            collection="published",
            requested_page=0,
            requested_page_size=50,
        )


def test_external_document_url_is_not_accepted() -> None:
    with pytest.raises(opinions.SelectionError):
        opinions._document_url_parts(
            "https://example.com/opinions/documents/S287786.PDF"
        )


def test_official_document_redirect_subdomain_is_accepted() -> None:
    assert opinions._document_url_parts(
        "https://www4.courts.ca.gov/opinions/nonpub/H052909.PDF"
    )[1:] == ("unpublished", "H052909", "pdf")
