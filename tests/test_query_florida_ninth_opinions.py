from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import query_florida_ninth_opinions as ninth


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "florida_ninth_opinions"
)


def _artifact(name: str, *, page: int = 0) -> ninth.Artifact:
    return ninth.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=(
            f"{ninth.INDEX_URL}?search=Orange%20County&page={page}"
        ),
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


class FixtureClient:
    def __init__(self) -> None:
        self.index_calls: list[tuple[str | None, int]] = []
        self.document_calls: list[str] = []

    def index(self, query: str | None, *, page: int) -> ninth.Artifact:
        self.index_calls.append((query, page))
        return _artifact(f"page-{page}.html", page=page)

    def document(self, url: str) -> ninth.Artifact:
        self.document_calls.append(url)
        return ninth.Artifact(
            content=b"%PDF-1.7\nfixture",
            source_url=url,
            media_type="application/pdf",
            headers={"content-type": "application/pdf"},
        )


def _args(*values: str) -> Any:
    return ninth.build_parser().parse_args(list(values))


def test_index_parser_preserves_titles_pdf_routes_and_paging() -> None:
    parsed = ninth.parse_index_page(
        _artifact("page-0.html"),
        requested_page=0,
    )

    assert len(parsed.records) == 2
    assert parsed.last_page_index == 1
    assert parsed.has_next is True
    first = parsed.records[0]
    assert first["published_title"] == "Tasman vs DHSMV"
    assert first["source_file_name"] == "06-45.pdf"
    assert first["document_url"] == (
        "https://ninthcircuit.org/sites/default/files/06-45.pdf"
    )
    assert first["projection"]["projectable_as_case"] is False
    assert first["court"]["county_geoids"] == ["12095", "12097"]


def test_search_cursor_resumes_inside_page_then_crosses_page() -> None:
    client = FixtureClient()

    first = ninth.execute(
        _args("search", "Orange County", "--limit", "1"),
        client=client,
        log_results=False,
    )
    second = ninth.execute(
        _args(
            "search",
            "Orange County",
            "--limit",
            "2",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert [row["published_title"] for row in first.records] == [
        "Tasman vs DHSMV"
    ]
    assert [row["published_title"] for row in second.records] == [
        "Orange County vs Ortiz",
        "Edgar v. Orange Co.",
    ]
    assert second.next_cursor is None
    assert client.index_calls == [
        ("Orange County", 0),
        ("Orange County", 0),
        ("Orange County", 1),
    ]


def test_cursor_is_bound_to_keyword_query() -> None:
    client = FixtureClient()
    first = ninth.execute(
        _args("search", "Orange County", "--limit", "1"),
        client=client,
        log_results=False,
    )

    mismatch = ninth.execute(
        _args(
            "search",
            "State",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_empty_source_state_is_a_valid_no_results_page() -> None:
    parsed = ninth.parse_index_page(
        ninth.Artifact(
            content=(FIXTURE_ROOT / "empty.html").read_bytes(),
            source_url=f"{ninth.INDEX_URL}?search=missing&page=0",
            media_type="text/html",
            headers={},
        ),
        requested_page=0,
    )

    assert parsed.records == ()
    assert parsed.has_next is False


def test_download_saves_exact_pdf_with_hash(tmp_path: Path) -> None:
    client = FixtureClient()
    destination = tmp_path / "06-45.pdf"
    document_url = (
        "https://ninthcircuit.org/sites/default/files/06-45.pdf"
    )

    result = ninth.execute(
        _args("download", document_url, str(destination)),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["download_status"] == "saved"
    assert record["mime_type"] == "application/pdf"
    assert record["sha256"] == ninth.hashlib.sha256(
        b"%PDF-1.7\nfixture"
    ).hexdigest()
    assert destination.read_bytes() == b"%PDF-1.7\nfixture"
    assert client.document_calls == [document_url]


def test_manifest_keeps_archive_and_complementary_systems_distinct() -> None:
    result = ninth.execute(
        _args("manifest"),
        client=FixtureClient(),
        log_results=False,
    )

    manifest = result.records[0]
    assert manifest["coverage"]["general_trial_orders"] is False
    assert {
        item["source_id"]
        for item in manifest["complementary_sources"]
    } == {
        "us-fl-orange-clerk-my-eclerk",
        "us-fl-acis",
        "us-fl-appellate-opinions-search",
    }


def test_challenge_page_reports_human_verification() -> None:
    artifact = ninth.Artifact(
        content=(
            b"<html><title>Appellate Opinions</title>"
            b"<body>Enable JavaScript and cookies to continue</body></html>"
        ),
        source_url=ninth.INDEX_URL,
        media_type="text/html",
        headers={},
    )

    try:
        ninth.parse_index_page(artifact, requested_page=0)
    except ninth.FloridaNinthOpinionsError as error:
        assert error.code == "human_verification"
        assert error.status.value == "human_required"
    else:
        raise AssertionError("challenge page was accepted")
