from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from tools import query_washington_courts as washington
from tools.ingest_state_court_records import validate_envelope
from tools.public_records_contract import ResultStatus


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "washington_courts"
)


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def artifact(
    name: str,
    url: str,
    *,
    media_type: str = "text/html",
) -> washington.Artifact:
    return washington.Artifact(
        content=fixture(name),
        source_url=url,
        media_type=media_type,
        headers={"content-type": media_type},
    )


class QueueClient:
    def __init__(self, responses: list[washington.Artifact]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> washington.Artifact:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"unexpected request: {url}")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def parse_args(*values: str) -> Any:
    return washington.build_parser().parse_args(values)


def test_source_family_uses_distinct_components_and_canonical_jis_id():
    assert len(washington.COMPONENTS) == 10
    assert washington.JISLINK_SOURCE_ID == "us-wa-jis-link"
    assert washington.JISLINK_SOURCE_ID in washington.COMPONENTS
    assert len(set(washington.COMPONENTS)) == len(washington.COMPONENTS)

    result = washington.execute(
        parse_args("sources"),
        client=QueueClient([]),
        log_results=False,
    )
    validate_envelope(result.to_dict())

    assert result.status == ResultStatus.OK
    assert {record["source_id"] for record in result.records} == set(
        washington.COMPONENTS
    )


def test_manifest_scopes_challenges_to_result_execution_operations():
    result = washington.execute(
        parse_args("manifest"),
        client=QueueClient([]),
        log_results=False,
    )
    access = result.records[0]["operation_access_model"]

    assert access["case_form_and_court_codes"] == "open_static"
    assert access["case_result_execution"] == "interactive_captcha"
    assert access["appellate_document_form"] == "open_static_exact_case"
    assert (
        access["appellate_document_result_execution"]
        == "interactive_captcha"
    )
    assert access["opinion_lists_feeds_information_pdfs"] == "open_static"


def test_parser_exposes_optional_caller_bounds_and_exhaustive_defaults():
    directory = parse_args("directory-search", "Whedbee", "--limit", "7")
    exhaustive_directory = parse_args("directory-search", "Whedbee")
    opinion = parse_args(
        "opinions-list",
        "--scope",
        "year",
        "--year",
        "2026",
        "--court-level",
        "C",
        "--publication-status",
        "UNP",
    )
    case = parse_args(
        "case-search",
        "--court-level",
        "superior",
        "--court-code",
        "S01",
        "--search-type",
        "case",
        "--case-number",
        "26-2-00001-1",
    )
    probe = parse_args(
        "probe",
        "--component",
        washington.OPINIONS_SOURCE_ID,
    )

    assert directory.last_name == "Whedbee"
    assert directory.limit == 7
    assert exhaustive_directory.limit is None
    assert opinion.year == 2026
    assert opinion.publication_status == "UNP"
    assert opinion.limit is None
    assert case.case_number == "26-2-00001-1"
    assert probe.component == [washington.OPINIONS_SOURCE_ID]


def test_directory_parsers_preserve_people_orgs_and_county_routes():
    counties = washington.parse_directory_counties(
        artifact(
            "directory_counties.html",
            washington.DIRECTORY_COUNTY_URL,
        )
    )
    people, total = washington.parse_directory_people(
        artifact(
            "directory_master.html",
            washington.DIRECTORY_MASTER_URL,
        )
    )
    organization = washington.parse_directory_org(
        artifact(
            "directory_org.html",
            f"{washington.DIRECTORY_HOME_URL}orgs/190.html",
        ),
        "190",
        contact_limit=5,
    )

    assert len(counties) == 39
    assert counties[16]["county_name"] == "King"
    assert counties[16]["organization_id"] == "117"
    assert total == 2
    assert people[1]["person_id"] == "11139"
    assert people[1]["organization_id"] == "191"
    assert people[1]["organization"] == "King County: Superior Court"
    assert organization["heading"] == "King County Superior Court"
    assert organization["sections"] == ["Judicial Officers"]
    assert organization["contacts"][0]["email"] == "judge@example.wa.gov"
    assert organization["websites"][0]["url"].startswith(
        "https://kingcounty.gov/"
    )


def test_directory_search_uses_server_initial_then_local_name_filter():
    client = QueueClient(
        [
            artifact(
                "directory_master.html",
                washington.DIRECTORY_MASTER_URL,
            )
        ]
    )
    result = washington.execute(
        parse_args("directory-search", "Whedbee"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [record["person_id"] for record in result.records] == ["11139"]
    query = parse_qs(urlsplit(client.calls[0]["url"]).query)
    assert query["courtdir_lastname"] == ["W"]
    assert query["FromRec"] == ["1"]


def test_case_form_exposes_codes_while_case_execution_is_human_required():
    form_artifact = artifact("case_form.html", washington.CASE_FORM_URL)
    contract = washington.parse_case_form(form_artifact)

    assert len(contract["court_codes"]["superior"]) == 39
    assert len(contract["court_codes"]["appellate"]) == 4
    assert len(contract["court_codes"]["limited_jurisdiction"]) == 1
    assert contract["result_route_types"] == ["bname", "case", "name"]
    assert contract["operations"]["form_metadata"]["status"] == "ok"
    assert (
        contract["operations"]["result_execution"]["status"]
        == "human_required"
    )

    result = washington.execute(
        parse_args(
            "case-search",
            "--court-level",
            "superior",
            "--court-code",
            "S01",
            "--search-type",
            "case",
            "--case-number",
            "26-2-00001-1",
        ),
        client=QueueClient([form_artifact]),
        log_results=False,
    )
    validate_envelope(result.to_dict())

    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert not result.records
    assert len(result.errors) == 1
    assert result.errors[0].code == "case_result_captcha_required"
    route = result.errors[0].details["prepared_route"]
    assert route["operation_status"] == "human_required"
    assert route["result_route"].endswith("rtlist=case")


def test_current_record_routes_remain_distinct_vendor_complements():
    records = washington.parse_case_routes(
        artifact("case_home.html", washington.CASE_HOME_URL)
    )

    assert len(records) == 8
    assert {record["vendor_family"] for record in records} == {
        "odyssey",
        "king_superior",
        "pierce_linx",
        "king_district",
        "kitsap_district",
        "seattle_municipal",
        "spokane_municipal",
        "tyler_researchwa",
    }
    assert all(
        record["component_source_id"]
        == washington.CURRENT_ROUTES_SOURCE_ID
        for record in records
    )


def test_opinion_feed_list_and_information_sheet_form_deterministic_chain():
    feed = washington.parse_opinion_feed(
        artifact(
            "opinions_feed.xml",
            washington.RSS_FEEDS["div1-unpublished"][0],
            media_type="application/rss+xml",
        ),
        "div1-unpublished",
    )
    listing = washington.parse_opinion_list(
        artifact("opinions_year.html", washington.OPINIONS_INDEX_URL),
        scope="year",
        year=2026,
        court_level="C",
        publication_status="UNP",
        query_text="Farah",
        limit=10,
    )
    detail = washington.parse_opinion_info(
        artifact("opinion_info.html", washington.OPINIONS_INDEX_URL),
        "883666MAJ",
    )

    assert len(feed) == 1
    assert feed[0]["case_number"] == "88366-6"
    assert feed[0]["opinion_filename"] == "883666MAJ"
    assert feed[0]["pdf_url"].endswith("/opinions/pdf/883666.pdf")
    assert [record["case_number"] for record in listing] == ["88366-6"]
    assert listing[0]["caption"] == "Farah v. Seattle Children's Hospital"
    assert detail["case_number"] == "88366-6"
    assert detail["court"] == "Court of Appeals Division I"
    assert detail["fields"]["concurring"] == ["Ian Birk", "David Mann"]
    assert detail["pdf_urls"][0].endswith("/opinions/pdf/883666.pdf")


def test_opinion_download_is_atomic_hashed_and_traceable(tmp_path):
    pdf = b"%PDF-1.7\nfixture Washington opinion\n%%EOF\n"
    client = QueueClient(
        [
            artifact("opinion_info.html", washington.OPINIONS_INDEX_URL),
            washington.Artifact(
                content=pdf,
                source_url=f"{washington.OPINIONS_PDF_BASE}883666.pdf",
                media_type="application/pdf",
                headers={
                    "content-type": "application/pdf",
                    "last-modified": "Mon, 27 Jul 2026 07:00:00 GMT",
                },
            ),
        ]
    )
    destination = tmp_path / "88366-6.pdf"
    result = washington.execute(
        parse_args(
            "opinion-download",
            "88366-6",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert destination.read_bytes() == pdf
    assert result.raw_artifact_refs == (str(destination.resolve()),)
    assert result.records[0]["sha256"] == washington.hashlib.sha256(
        pdf
    ).hexdigest()
    assert result.records[0]["case_number"] == "88366-6"
    assert client.calls[1]["maximum_bytes"] == washington.MAXIMUM_PDF_BYTES


def test_bulk_products_preserve_current_omissions_as_separate_snapshot():
    records = washington.parse_data_products(
        artifact("data_products.html", washington.DATA_PRODUCTS_URL)
    )
    products = [
        record
        for record in records
        if record["record_kind"] == "court_bulk_index_product"
    ]
    coverage = records[-1]

    assert len(products) == 5
    assert products[0]["product_code"] == "PSCI"
    assert products[0]["annual_cost_usd"] == 3600.0
    assert products[-1]["product_code"] == "PROBATE"
    assert coverage["missing_court_count"] == 2
    assert coverage["missing_courts"] == [
        "King County Superior Court",
        "Seattle Municipal Court",
    ]
    assert coverage["local_complement_required"] is True


def test_custom_extract_and_jis_link_are_distinct_access_routes():
    request = washington.Artifact(
        content=(
            b"<html><body><h2>Forms</h2>"
            b'<a href="/datadis/requestForInfo.pdf">Request PDF</a>'
            b'<a href="/datadis/requestForInfoFillable.pdf">'
            b"Fillable Request</a></body></html>"
        ),
        source_url=washington.DATA_REQUEST_URL,
        media_type="text/html",
        headers={},
    )
    fee = washington.Artifact(
        content=(
            b"<html><body><h2>Fee Schedule</h2><ul>"
            b"<li>Research: $30.00 per hour</li>"
            b"<li>Extract: $1,000.00 minimum</li>"
            b"</ul></body></html>"
        ),
        source_url=washington.DATA_FEE_URL,
        media_type="text/html",
        headers={},
    )
    form = washington.Artifact(
        content=b"%PDF-1.7\nrequest\n%%EOF\n",
        source_url=f"{washington.COURTS_ORIGIN}/datadis/request.pdf",
        media_type="application/pdf",
        headers={},
    )
    custom = washington.parse_custom_extract(request, fee, form)
    jis = washington.parse_jislink(
        artifact("jislink.html", washington.JISLINK_URL)
    )

    assert len(custom["request_forms"]) == 2
    assert len(custom["current_fee_items"]) == 2
    assert custom["access_state"] == "formal_request"
    assert custom["fillable_form"]["media_type"] == "application/pdf"
    assert jis["source_id"] == "us-wa-jis-link"
    assert jis["access_state"] == "registered_subscription"
    assert len(jis["access_routes"]) == 3
    assert "filed documents" in jis["document_scope"]


def test_appellate_document_form_is_open_but_result_execution_is_scoped():
    portal_artifact = artifact(
        "appellate_document.html",
        washington.APPELLATE_DOCUMENT_URLS["appeals"],
    )
    parsed = washington.parse_appellate_document_form(
        portal_artifact,
        court="appeals",
        case_number="88366-6",
    )
    result = washington.execute(
        parse_args(
            "appellate-documents",
            "88366-6",
            "--court",
            "appeals",
        ),
        client=QueueClient([portal_artifact]),
        log_results=False,
    )

    assert parsed["operations"]["form_metadata"]["status"] == "ok"
    assert (
        parsed["operations"]["result_execution"]["status"]
        == "human_required"
    )
    assert parsed["current_exclusions"] == [
        "Documents from cases filed before January 1, 2020"
    ]
    assert result.status == ResultStatus.HUMAN_REQUIRED
    assert result.errors[0].code == "appellate_document_captcha_required"
    assert (
        result.errors[0].details["prepared_route"]["case_number"]
        == "88366-6"
    )


def test_appellate_brief_routes_add_exact_case_forms_without_collapsing_sources():
    records = washington.parse_appellate_complement(
        artifact(
            "appellate_briefs.html",
            washington.APPELLATE_COMPLEMENT_URLS["briefs"],
        ),
        kind="briefs",
        case_number="104108-0",
    )
    exact_routes = [
        record
        for record in records
        if record["record_kind"] == "appellate_brief_case_search_route"
    ]

    assert len(exact_routes) == 4
    assert {record["court_id"] for record in exact_routes} == {
        "A01",
        "A02",
        "A03",
        "A08",
    }
    assert all(
        record["component_source_id"]
        == washington.APPELLATE_COMPLEMENTS_SOURCE_ID
        for record in records
    )


def test_caseload_and_archive_are_typed_as_complements_not_case_evidence():
    caseload = washington.parse_caseload_routes(
        artifact("caseload.html", washington.CASELOAD_URL)
    )
    archive = washington.parse_archive_title(
        artifact(
            "archive_title.html",
            washington.DIGITAL_ARCHIVES_TITLE_BASE + "2778",
        ),
        "2778",
    )

    assert len(caseload) == 8
    assert {record["delivery_format"] for record in caseload} >= {
        "pdf",
        "excel",
        "interactive_dashboard",
        "html",
    }
    assert all(
        record["evidence_scope"]
        == "aggregate_activity_and_coverage_diagnostic"
        for record in caseload
    )
    assert archive["title_id"] == "2778"
    assert archive["record_count"] == 2_952_435
    assert archive["search"]["method"] == "POST"
    assert {
        field["name"] for field in archive["search"]["fields"]
    } >= {"TitleID", "CaseNumber", "Keywords"}
    assert archive["availability_scope"] == "per_title_and_operation"


def test_parser_contract_drift_is_an_explicit_source_changed_status():
    changed = fixture("case_form.html").replace(
        b'<div class="g-recaptcha"></div>',
        b"",
    ).replace(b"recaptcha", b"challenge")
    client = QueueClient(
        [
            washington.Artifact(
                content=changed,
                source_url=washington.CASE_FORM_URL,
                media_type="text/html",
                headers={},
            )
        ]
    )
    result = washington.execute(
        parse_args("case-form"),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "case_search_challenge_changed"


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official Washington probes",
)
def test_live_all_component_probe():
    result = washington.execute(
        parse_args(
            "probe",
            "--all",
            "--minimum-interval",
            "0",
            "--max-attempts",
            "1",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert len(result.records) == len(washington.COMPONENTS)
    assert all(record["status"] == "ok" for record in result.records)
    by_source = {record["source_id"]: record for record in result.records}
    assert (
        by_source[washington.CASE_DISCOVERY_SOURCE_ID]["operations"][
            "result_execution"
        ]
        == "human_required"
    )
    assert (
        by_source[washington.APPELLATE_DOCUMENTS_SOURCE_ID]["operations"][
            "result_execution"
        ]
        == "human_required"
    )
    assert (
        by_source[washington.OPINIONS_SOURCE_ID]["evidence"][
            "sentinel_case_number"
        ]
        == washington.KNOWN_OPINION_CASE
    )


@pytest.mark.skipif(
    os.environ.get("LIVE_PUBLIC_RECORDS") != "1",
    reason="set LIVE_PUBLIC_RECORDS=1 for official Washington probes",
)
def test_live_directory_name_search():
    result = washington.execute(
        parse_args(
            "directory-search",
            "Whedbee",
            "--minimum-interval",
            "0",
            "--max-attempts",
            "1",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert any(
        "Whedbee" in record["name_and_title"]
        for record in result.records
    )
