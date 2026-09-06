from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools import query_georgia_supreme_publications as publications


FIXTURE_ROOT = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "georgia_supreme_publications"
)


def _artifact(
    name: str,
    source_id: str,
    *,
    year: int = 2026,
    application_type: str | None = None,
) -> publications.Artifact:
    return publications.Artifact(
        content=(FIXTURE_ROOT / name).read_bytes(),
        source_url=publications._page_url(
            source_id,
            year,
            application_type=application_type,
        ),
        media_type="text/html",
        headers={"content-type": "text/html"},
    )


class FixtureClient:
    def __init__(self) -> None:
        self.index_calls: list[tuple[str, int, str | None]] = []
        self.document_calls: list[str] = []

    def index(
        self,
        source_id: str,
        year: int,
        *,
        application_type: str | None = None,
    ) -> publications.Artifact:
        self.index_calls.append((source_id, year, application_type))
        fixture = {
            (publications.OPINION_SOURCE_ID, None): "opinions-2026.html",
            (
                publications.CERT_GRANT_SOURCE_ID,
                None,
            ): "granted-2026.html",
            (
                publications.CERT_DENIAL_SOURCE_ID,
                None,
            ): "denied-2026.html",
            (
                publications.APPLICATION_GRANT_SOURCE_ID,
                "discretionary",
            ): "discretionary-2026.html",
            (
                publications.APPLICATION_GRANT_SOURCE_ID,
                "interlocutory",
            ): "interlocutory-2026.html",
        }[(source_id, application_type)]
        return _artifact(
            fixture,
            source_id,
            year=year,
            application_type=application_type,
        )

    def document(self, url: str) -> publications.Artifact:
        self.document_calls.append(url)
        return publications.Artifact(
            content=b"%PDF-1.7\nGeorgia Supreme fixture",
            source_url=url,
            media_type="application/pdf",
            headers={"content-type": "application/pdf"},
        )


def _args(*values: str) -> Any:
    return publications.build_parser().parse_args(list(values))


def test_source_inventory_keeps_four_publication_contracts_distinct() -> None:
    result = publications.execute(
        _args("sources"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert {record["source_id"] for record in result.records} == {
        publications.OPINION_SOURCE_ID,
        publications.CERT_GRANT_SOURCE_ID,
        publications.CERT_DENIAL_SOURCE_ID,
        publications.APPLICATION_GRANT_SOURCE_ID,
    }
    for record in result.records:
        attribution = record["separate_attribution"]
        assert (
            attribution[
                "cross_collection_matches_are_not_independent_corroboration"
            ]
            is True
        )


def test_opinion_manifest_preserves_version_hierarchy_and_complements() -> None:
    result = publications.execute(
        _args(
            "manifest",
            "--source",
            publications.OPINION_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    )

    manifest = result.records[0]
    assert manifest["verified_coverage"]["first_year"] == 2017
    assert manifest["verified_coverage"]["through_year"] == 2026
    assert "Final Copy" in manifest["opinion_version_notice"]
    assert "bound volumes" in manifest["opinion_version_notice"]
    assert {
        item.get("source_id") or item["name"]
        for item in manifest["complements"]
    } == {
        "us-ga-supreme-court-public-docket",
        "Supreme Court oral argument calendars",
        "Supreme Court case announcements",
    }


def test_opinion_parser_preserves_multi_case_summary_and_revision_state() -> None:
    parsed = publications.parse_opinions_page(
        _artifact(
            "opinions-2026.html",
            publications.OPINION_SOURCE_ID,
        ),
        year=2026,
    )

    assert len(parsed.records) == 4
    by_type = {}
    for record in parsed.records:
        by_type.setdefault(record["publication_type"], []).append(record)
    assert len(by_type["noteworthy_summary"]) == 1
    summary = by_type["noteworthy_summary"][0]
    assert summary["publication_date"] == "2026-05-05"
    assert summary["document"]["document_type"] == (
        "noteworthy_opinion_summary_packet"
    )

    rucker = next(
        record
        for record in by_type["opinion"]
        if record["primary_case_number"] == "S26A0035"
    )
    assert rucker["case_numbers"] == ["S26A0035", "S26A0036"]
    assert rucker["multi_case_publication"] is True
    assert len(rucker["case_canonical_refs"]) == 2

    clark = next(
        record
        for record in by_type["opinion"]
        if record["primary_case_number"] == "S26A0062"
    )
    assert clark["revision_note_raw"] == (
        "7-1-2026 Substitute opinion issued."
    )
    assert clark["revision_events"][0]["event_type"] == (
        "substitute_opinion_issued"
    )
    assert clark["revision_events"][0]["date_texts"] == ["7-1-2026"]
    assert clark["version_state"] == (
        "website_publication_with_revision_note"
    )
    assert "Final Copy" in parsed.authority_notice


def test_grant_parser_builds_supreme_to_appellate_chain() -> None:
    parsed = publications.parse_certiorari_grants_page(
        _artifact(
            "granted-2026.html",
            publications.CERT_GRANT_SOURCE_ID,
        ),
        year=2026,
    )

    assert len(parsed.records) == 2
    honda = parsed.records[0]
    assert honda["primary_case_number"] == "S26G0537"
    assert honda["supreme_court_document"]["native_document_id"].endswith(
        "s26c0537.pdf"
    )
    assert honda["appellate_chain"] == {
        "supreme_court_case_numbers": ["S26G0537"],
        "court_of_appeals_case_numbers": ["A25A1237"],
    }
    assert honda["lower_appellate_cases"][0]["originating_court"] == (
        "Court of Appeals of Georgia"
    )

    friendly = parsed.records[1]
    assert friendly["appellate_chain"]["court_of_appeals_case_numbers"] == [
        "A25A1902",
        "A25A1924",
    ]
    assert {
        item["document_url"] for item in friendly["lower_appellate_cases"]
    } == {
        "https://www.gasupreme.us/wp-content/uploads/2026/06/a25a1902.pdf"
    }


def test_denial_parser_keeps_html_entries_and_linked_supplements_distinct() -> None:
    parsed = publications.parse_certiorari_denials_page(
        _artifact(
            "denied-2026.html",
            publications.CERT_DENIAL_SOURCE_ID,
        ),
        year=2026,
    )

    assert len(parsed.records) == 3
    mosher = parsed.records[0]
    assert mosher["disposition"] == "denied"
    assert mosher["document_url"] is None
    assert mosher["list_entry_has_document"] is False
    assert mosher["appellate_chain"]["court_of_appeals_case_numbers"] == [
        "A25A1866"
    ]

    johnson = parsed.records[-1]
    assert johnson["list_entry_has_document"] is True
    assert johnson["supplemental_document"]["document_type"] == (
        "denial_related_publication"
    )
    assert johnson["revision_note_raw"] == "Concurral issued."
    assert johnson["revision_events"][0]["event_type"] == (
        "concurrence_issued"
    )


def test_application_parser_preserves_type_and_joint_case_order() -> None:
    discretionary = publications.parse_application_grants_page(
        _artifact(
            "discretionary-2026.html",
            publications.APPLICATION_GRANT_SOURCE_ID,
            application_type="discretionary",
        ),
        year=2026,
        application_type="discretionary",
    )
    interlocutory = publications.parse_application_grants_page(
        _artifact(
            "interlocutory-2026.html",
            publications.APPLICATION_GRANT_SOURCE_ID,
            application_type="interlocutory",
        ),
        year=2026,
        application_type="interlocutory",
    )

    assert discretionary.records[0]["case_numbers"] == [
        "S26D1454",
        "S26D1455",
        "S26D1456",
        "S26D1457",
    ]
    assert discretionary.records[0]["application_type"] == "discretionary"
    assert discretionary.records[0]["document"]["document_type"] == (
        "discretionary_application_grant_order"
    )
    assert interlocutory.records[0]["application_type"] == "interlocutory"
    assert interlocutory.records[0]["primary_case_number"] == "S26I1337"


def test_search_filters_and_pages_over_a_snapshot() -> None:
    client = FixtureClient()
    first = publications.execute(
        _args(
            "search",
            "*",
            "--source",
            publications.OPINION_SOURCE_ID,
            "--year",
            "2026",
            "--limit",
            "2",
        ),
        client=client,
        log_results=False,
    )
    second = publications.execute(
        _args(
            "search",
            "*",
            "--source",
            publications.OPINION_SOURCE_ID,
            "--year",
            "2026",
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
    assert first.next_cursor is not None
    assert second.next_cursor is None
    assert {
        record["canonical_ref"] for record in first.records
    }.isdisjoint(
        {record["canonical_ref"] for record in second.records}
    )
    assert client.index_calls == [
        (publications.OPINION_SOURCE_ID, 2026, None),
        (publications.OPINION_SOURCE_ID, 2026, None),
    ]


def test_search_can_filter_exact_case_date_and_publication_type() -> None:
    result = publications.execute(
        _args(
            "search",
            "*",
            "--source",
            publications.OPINION_SOURCE_ID,
            "--year",
            "2026",
            "--case-number",
            "S26A0036",
            "--date-from",
            "2026-06-01",
            "--publication-type",
            "opinion",
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["primary_case_number"] == "S26A0035"


def test_cursor_is_bound_to_query_identity() -> None:
    client = FixtureClient()
    first = publications.execute(
        _args(
            "search",
            "*",
            "--source",
            publications.OPINION_SOURCE_ID,
            "--limit",
            "1",
        ),
        client=client,
        log_results=False,
    )
    mismatch = publications.execute(
        _args(
            "search",
            "Clark",
            "--source",
            publications.OPINION_SOURCE_ID,
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )

    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_detail_returns_one_exact_publication_identity() -> None:
    client = FixtureClient()
    search = publications.execute(
        _args(
            "search",
            "Clark",
            "--source",
            publications.OPINION_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )
    publication_id = search.records[0]["publication_id"]

    detail = publications.execute(
        _args(
            "detail",
            publication_id,
            "--source",
            publications.OPINION_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )

    assert detail.status.value == "ok"
    assert detail.records[0]["publication_id"] == publication_id
    assert detail.records[0]["revision_note_raw"] == (
        "7-1-2026 Substitute opinion issued."
    )


def test_download_saves_validated_pdf_and_hash(tmp_path: Path) -> None:
    client = FixtureClient()
    destination = tmp_path / "s26a0062.pdf"
    url = (
        "https://www.gasupreme.us/wp-content/uploads/"
        "2026/07/s26a0062.pdf"
    )

    result = publications.execute(
        _args(
            "download",
            url,
            str(destination),
            "--source",
            publications.OPINION_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert result.records[0]["download_status"] == "saved"
    assert result.records[0]["sha256"] == publications.hashlib.sha256(
        b"%PDF-1.7\nGeorgia Supreme fixture"
    ).hexdigest()
    assert destination.read_bytes().startswith(b"%PDF-")
    assert client.document_calls == [url]


def test_application_probe_bounds_two_indexes_and_two_documents() -> None:
    client = FixtureClient()
    result = publications.execute(
        _args(
            "probe",
            "--source",
            publications.APPLICATION_GRANT_SOURCE_ID,
            "--year",
            "2026",
        ),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert {
        record["publication_component"] for record in result.records
    } == {
        "discretionary_application_grants",
        "interlocutory_application_grants",
    }
    assert sum(record["requests_made"] for record in result.records) == 4
    assert len(client.index_calls) == 2
    assert len(client.document_calls) == 2


def test_missing_opinion_version_notice_is_source_changed() -> None:
    artifact = publications.Artifact(
        content=(
            b"<html><h1 class='entry-title'>2026 Opinions and Summaries</h1>"
            b"<div class='post-content'><p>June 2, 2026</p><ul><li>"
            b"<a href='/wp-content/uploads/2026/06/s26a0001.pdf'>"
            b"S26A0001. TEST v. STATE</a></li></ul></div></html>"
        ),
        source_url=publications._page_url(
            publications.OPINION_SOURCE_ID,
            2026,
        ),
        media_type="text/html",
        headers={},
    )

    with pytest.raises(
        publications.GeorgiaSupremePublicationsError
    ) as captured:
        publications.parse_opinions_page(artifact, year=2026)

    assert captured.value.code == "opinion_version_notice_missing"
    assert captured.value.status.value == "source_changed"


def test_official_document_validation_rejects_other_hosts_and_routes() -> None:
    with pytest.raises(
        publications.GeorgiaSupremePublicationsError
    ) as other_host:
        publications._official_url(
            "https://example.com/wp-content/uploads/2026/06/test.pdf",
            document=True,
        )
    assert other_host.value.code == "unrecognized_official_url"

    with pytest.raises(
        publications.GeorgiaSupremePublicationsError
    ) as wrong_route:
        publications._official_url(
            "https://www.gasupreme.us/private/test.pdf",
            document=True,
        )
    assert wrong_route.value.code == "unrecognized_document_url"


def test_unsupported_year_returns_selection_failure() -> None:
    result = publications.execute(
        _args(
            "search",
            "*",
            "--source",
            publications.CERT_GRANT_SOURCE_ID,
            "--year",
            "2021",
        ),
        client=FixtureClient(),
        log_results=False,
    )

    assert result.status.value == "unavailable"
    assert result.errors[0].code == "unsupported_publication_year"
