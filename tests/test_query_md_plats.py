from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_md_plats as md
from tools.public_records_contract import ResultStatus


FIXTURE_ROOT = (
    Path(__file__).parent / "fixtures" / "public_records" / "md_plats"
)
COUNTY_URL = "https://plats.msa.maryland.gov/pages/plats.aspx?cid=MO"
RESULTS_URL = (
    "https://plats.msa.maryland.gov/pages/"
    "results.aspx?cid=MO&adv=1&id=fixture"
)


def fixture(name: str) -> str:
    return (FIXTURE_ROOT / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(
        self,
        *,
        url: str,
        text: str = "<html></html>",
        content: bytes | None = None,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.url = url
        self.text = text
        self.content = content if content is not None else text.encode()
        self.status_code = status_code
        self.headers = dict(headers or {})


class QueueSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.headers: dict[str, str] = {}
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, str] | None,
        headers: Mapping[str, str],
        timeout: float,
        allow_redirects: bool,
    ) -> FakeResponse:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "data": dict(data) if data is not None else None,
                "headers": dict(headers),
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        if not self.responses:
            raise AssertionError("fake response queue exhausted")
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def client_with(
    *responses: FakeResponse,
) -> tuple[md.MarylandPlatsClient, QueueSession]:
    session = QueueSession(list(responses))
    client = md.MarylandPlatsClient(
        session=session,
        minimum_interval=0,
        retry_policy=md.RetryPolicy(max_attempts=1),
        sleeper=lambda _seconds: None,
    )
    return client, session


def county_response(name: str = "county_form.html") -> FakeResponse:
    return FakeResponse(url=COUNTY_URL, text=fixture(name))


def redirect_response() -> FakeResponse:
    return FakeResponse(
        url=COUNTY_URL,
        text="",
        status_code=302,
        headers={"Location": RESULTS_URL},
    )


def results_response(name: str) -> FakeResponse:
    return FakeResponse(url=RESULTS_URL, text=fixture(name))


def advanced_selection(
    *,
    description: str = "Estate",
    include_no_images: bool = True,
) -> md.SearchSelection:
    return md.SearchSelection(
        county_code="MO",
        mode="advanced",
        description=description,
        include_no_images=include_no_images,
    )


def parsed_results(name: str = "results_page1.html") -> md.ResultsPage:
    selection = advanced_selection()
    return md.parse_results_page(
        fixture(name),
        source_url=RESULTS_URL,
        county_code="MO",
        county_name="Montgomery County",
        selection_fingerprint=selection.fingerprint,
    )


def test_search_form_discovers_all_counties_series_and_contract() -> None:
    form = md.parse_search_form(
        fixture("county_form.html"),
        source_url=COUNTY_URL,
    )
    switched = md.parse_search_form(
        fixture("county_form_s.html"),
        source_url=COUNTY_URL,
    )

    assert form.action_url == COUNTY_URL
    assert len(form.counties) == 24
    assert form.counties[0].code == "AL"
    assert next(item for item in form.counties if item.code == "MO").name == (
        "Montgomery County"
    )
    assert form.selected_qualifier == "C"
    assert form.series_options == ("1136", "2134", "2139")
    assert switched.selected_qualifier == "S"
    assert switched.series_options == ("1249",)
    assert switched.contract_fingerprint == form.contract_fingerprint
    series = {
        (item.qualifier, item.series): item for item in form.series_catalog
    }
    assert series[("C", "1136")].name == "Plats, MO"
    assert series[("S", "1249")].coverage_dates == "1894-"


def test_search_payloads_follow_the_three_published_forms() -> None:
    form = md.parse_search_form(
        fixture("county_form.html"),
        source_url=COUNTY_URL,
    )
    basic = md._search_form_payload(
        form,
        md.SearchSelection(
            county_code="MO",
            mode="basic",
            plat_number="21732",
        ),
    )
    advanced = md._search_form_payload(
        form,
        md.SearchSelection(
            county_code="MO",
            mode="advanced",
            filed_date="1900/02/09",
            description="Blair Estate",
            sort="reference",
        ),
    )
    series = md._search_form_payload(
        form,
        md.SearchSelection(
            county_code="MO",
            mode="series",
            qualifier="C",
            series="1136",
            unit="1",
        ),
    )

    assert basic["ctl00$body$txtPlatNo"] == "21732"
    assert basic["ctl00$body$btnSearch2"] == "Search"
    assert advanced["ctl00$body$txtDate"] == "1900/02/09"
    assert advanced["ctl00$body$txtDescription"] == "Blair Estate"
    assert advanced["ctl00$body$ddlsort"] == "ref"
    assert series["ctl00$body$ddlqualslct"] == "C"
    assert series["ctl00$body$ddlseriesslct"] == "1136"
    assert series["ctl00$body$txtseriesunit"] == "1"


def test_result_parser_separates_record_reference_occurrence_and_view() -> None:
    page = parsed_results()

    assert page.current_page == 1
    assert page.total_pages == 2
    assert page.image_result_count == 1
    assert page.total_result_count == 3
    assert page.include_no_images is True
    assert page.has_next is True
    assert len(page.records) == 2

    image_record, metadata_record = page.records
    assert image_record["record_identity"] == {
        "county_code": "MO",
        "archive_qualifier": "C",
        "archive_series": "1136",
        "archive_unit": "1",
        "msa_accession": "MSA C1136-1",
    }
    assert image_record["filed_date"]["iso"] == "1900-02-09"
    assert image_record["description"].startswith("Blair Estate")
    assert image_record["developer_owner"] is None
    image_view = image_record["source_result_representation"]
    assert image_view["published_scan_count"] == 1
    assert image_view["source_result_detail_link"].endswith(
        "series=1136&unit=1&page=adv1&id=fixture"
    )

    assert metadata_record["archive_accession"]["normalized"] == (
        "MSA C2139-140"
    )
    assert metadata_record["archive_accession"]["raw"] == "MSA C 2139-140"
    assert metadata_record["developer_owner"] == (
        "Elliott, Robert P. and Carol Ann Elliott"
    )
    assert metadata_record["book_page_plat_reference"]["plat_number"] == (
        "22281"
    )
    metadata_view = metadata_record["source_result_representation"]
    assert metadata_view["image_availability"] == "metadata_only"
    assert metadata_view["source_result_detail_link"] is None
    assert metadata_view["exact_detail_url"].endswith(
        "qualifier=C&series=2139&unit=140"
    )
    assert image_view["representation_identity"] != (
        metadata_view["representation_identity"]
    )
    assert image_record["result_occurrence"]["absolute_position"] == 1
    assert metadata_record["result_occurrence"]["absolute_position"] == 2
    assert image_record["result_occurrence"]["occurrence_identity"] != (
        image_view["representation_identity"]
    )


def test_result_parser_keeps_authoritative_empty_distinct_from_schema_change() -> None:
    empty = parsed_results("results_empty.html")
    assert empty.records == ()
    assert empty.total_result_count == 0
    assert empty.image_result_count == 0
    assert empty.has_next is False

    changed = fixture("results_page1.html").replace(
        "<th>Reference</th>",
        "<th>Plat Reference</th>",
    )
    with pytest.raises(md.MarylandPlatsSourceChangedError):
        md.parse_results_page(
            changed,
            source_url=RESULTS_URL,
            county_code="MO",
            county_name="Montgomery County",
            selection_fingerprint=advanced_selection().fingerprint,
        )


def test_detail_parser_keeps_compiled_and_direct_artifacts_distinct() -> None:
    record = md.parse_plat_detail(
        fixture("detail_image.html"),
        source_url=(
            f"{md.UNIT_URL}?cid=MO&qualifier=C&series=1136&unit=1"
        ),
        county_code="MO",
        expected_qualifier="C",
        expected_series="1136",
        expected_unit="1",
    )

    assert record["record_identity"]["archive_unit"] == "1"
    assert record["archive_accession"]["series_name"] == "Plats"
    assert record["filed_date"]["iso"] == "1900-02-09"
    assert record["published_artifact_count"] == 2
    artifacts = {item["artifact_role"]: item for item in record["artifacts"]}
    assert set(artifacts) == {"compiled_pdf", "direct_scan"}
    assert artifacts["compiled_pdf"]["file_format"] == "pdf"
    assert artifacts["direct_scan"]["file_format"] == "tif"
    assert artifacts["compiled_pdf"]["artifact_identity"] != (
        artifacts["direct_scan"]["artifact_identity"]
    )
    assert artifacts["compiled_pdf"]["representation_locator"][
        "observed_path_date"
    ] == "2026-07-30"
    assert artifacts["direct_scan"]["source_url"].endswith("p21898a.tif")


def test_detail_parser_retains_metadata_when_no_images_are_published() -> None:
    record = md.parse_plat_detail(
        fixture("detail_no_image.html"),
        source_url=(
            f"{md.UNIT_URL}?cid=MO&qualifier=C&series=2139&unit=140"
        ),
        county_code="MO",
        expected_qualifier="C",
        expected_series="2139",
        expected_unit="140",
    )

    assert record["image_availability"] == "metadata_only"
    assert record["published_artifact_count"] == 0
    assert record["artifacts"] == []
    assert record["description"] == "Timberland Estates, Block B, Lot 14"
    assert record["book_page_plat_reference"]["plat_number"] == "22281"


def test_unbounded_search_traverses_the_complete_source_result_set() -> None:
    client, session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_page1.html"),
        results_response("results_page2.html"),
    )

    result = client.search(advanced_selection(), limit=None)

    assert [
        record["archive_accession"]["normalized"]
        for record in result.records
    ] == [
        "MSA C1136-1",
        "MSA C2139-140",
        "MSA C2139-136",
    ]
    assert result.next_cursor is None
    assert result.pages_fetched == 2
    assert result.requests_made == 4
    assert result.source_total_result_count == 3
    assert result.source_image_result_count == 1
    assert result.source_total_pages == 2
    next_post = session.calls[3]
    assert next_post["method"] == "POST"
    assert next_post["data"]["ctl00$body$imgButtonNext.x"] == "12"
    assert next_post["data"]["ctl00$body$imgButtonNext.y"] == "12"
    assert next_post["data"]["ctl00$body$ddlPage"] == "1"


def test_native_page_redirect_is_followed_and_counted() -> None:
    page_redirect = FakeResponse(
        url=RESULTS_URL,
        text="",
        status_code=302,
        headers={"Location": RESULTS_URL},
    )
    client, session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_page1.html"),
        page_redirect,
        results_response("results_page2.html"),
    )

    result = client.search(advanced_selection(), limit=None)

    assert len(result.records) == 3
    assert result.requests_made == 5
    assert session.calls[3]["method"] == "POST"
    assert session.calls[4]["method"] == "GET"


def test_cursor_resumes_inside_a_page_then_across_native_pages() -> None:
    selection = advanced_selection()
    first_client, _first_session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_page1.html"),
    )
    first = first_client.search(selection, limit=1)
    assert first.records[0]["archive_accession"]["normalized"] == (
        "MSA C1136-1"
    )
    assert first.next_cursor is not None

    second_client, _second_session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_page1.html"),
    )
    second = second_client.search(
        selection,
        limit=1,
        cursor=first.next_cursor,
    )
    assert second.records[0]["archive_accession"]["normalized"] == (
        "MSA C2139-140"
    )
    assert second.next_cursor is not None

    third_client, third_session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_page1.html"),
        results_response("results_page2.html"),
    )
    third = third_client.search(
        selection,
        limit=1,
        cursor=second.next_cursor,
    )
    assert third.records[0]["archive_accession"]["normalized"] == (
        "MSA C2139-136"
    )
    assert third.next_cursor is None
    assert third_session.calls[3]["data"][
        "ctl00$body$imgButtonNext.x"
    ] == "12"

    changed_selection = advanced_selection(description="Different estate")
    with pytest.raises(
        md.MarylandPlatsSelectionError,
        match="different PLATS.NET search criteria",
    ):
        md._decode_cursor(
            first.next_cursor,
            selection_fingerprint=changed_selection.fingerprint,
        )


def test_include_no_images_uses_the_source_checkbox_postback() -> None:
    unchecked = fixture("results_page1.html").replace(
        'value="on" checked',
        'value="on"',
    )
    client, session = client_with(
        county_response(),
        redirect_response(),
        FakeResponse(url=RESULTS_URL, text=unchecked),
        results_response("results_page1.html"),
    )

    result = client.search(advanced_selection(), limit=1)

    assert len(result.records) == 1
    assert result.requests_made == 4
    toggle = session.calls[3]
    assert toggle["data"]["__EVENTTARGET"] == "ctl00$body$ckhide"
    assert toggle["data"]["ctl00$body$ckhide"] == "on"


def test_series_search_performs_the_verified_qualifier_postback() -> None:
    selection = md.SearchSelection(
        county_code="MO",
        mode="series",
        qualifier="S",
        series="1249",
        unit="27636",
    )
    client, session = client_with(
        county_response(),
        county_response("county_form_s.html"),
        redirect_response(),
        results_response("results_series_s.html"),
    )

    result = client.search(selection, limit=1)

    assert len(result.records) == 1
    assert result.requests_made == 4
    switch = session.calls[1]["data"]
    submit = session.calls[2]["data"]
    assert switch["__EVENTTARGET"] == "ctl00$body$ddlqualslct"
    assert switch["ctl00$body$ddlqualslct"] == "S"
    assert submit["ctl00$body$ddlqualslct"] == "S"
    assert submit["ctl00$body$ddlseriesslct"] == "1249"
    assert submit["ctl00$body$txtseriesunit"] == "27636"
    assert submit["ctl00$body$btnadvsearch3"] == "Search"


def test_exact_plat_fetches_without_a_search_session() -> None:
    source_url = (
        f"{md.UNIT_URL}?cid=MO&qualifier=C&series=1136&unit=1"
    )
    client, session = client_with(
        FakeResponse(url=source_url, text=fixture("detail_image.html"))
    )

    record = client.fetch_plat("MO", "C", "1136", "1")

    assert record["archive_accession"]["normalized"] == "MSA C1136-1"
    assert len(session.calls) == 1
    assert session.calls[0]["method"] == "GET"
    assert session.calls[0]["url"] == source_url


def test_artifact_fetch_verifies_format_and_hashes_content() -> None:
    source_url = (
        "https://plats.msa.maryland.gov/plats/2026-07-30/"
        "MSA_C1136_1/MSA_C1136_1.pdf"
    )
    content = b"%PDF-1.4\nfixture plat\n%%EOF\n"
    client, _session = client_with(
        FakeResponse(
            url=source_url,
            content=content,
            headers={
                "Content-Type": "application/pdf",
                "ETag": '"fixture-etag"',
            },
        )
    )

    artifact = client.fetch_artifact(source_url)

    assert artifact.content == content
    assert artifact.media_type == "application/pdf"
    assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert artifact.etag == '"fixture-etag"'

    with pytest.raises(md.MarylandPlatsSourceChangedError):
        md._official_artifact_url(
            "https://example.com/not-a-plats-artifact.pdf"
        )


def test_empty_search_envelope_preserves_source_reported_boundaries() -> None:
    client, _session = client_with(
        county_response(),
        redirect_response(),
        results_response("results_empty.html"),
    )
    args = md.build_parser().parse_args(
        [
            "search",
            "MO",
            "--mode",
            "advanced",
            "--description",
            "Source-specific impossible phrase",
        ]
    )

    result = md.execute(args, client=client, log_results=False)

    assert result.status == ResultStatus.NO_RESULTS
    assert result.records == ()
    metadata = result.query.query.metadata
    assert metadata["source_total_result_count"] == 0
    assert metadata["source_image_result_count"] == 0
    assert metadata["source_total_pages"] == 1
    assert metadata["return_bound"] == (
        "complete_source_reported_result_set"
    )


def test_sources_keeps_related_maryland_systems_separately_attributed() -> None:
    args = md.build_parser().parse_args(["sources"])
    result = md.execute(args, log_results=False)

    assert result.status == ResultStatus.OK
    manifest = result.records[0]
    related = {
        item["source_id"] for item in manifest["complementary_sources"]
    }
    assert related == {
        "us-md-land-records",
        "us-md-mdp-parcel-points",
        "us-md-mdp-cama-downloads",
        "us-md-mdp-property-sales-downloads",
    }
    assert manifest["operations"]["search"]["omitted_limit"] == (
        "complete source-reported result set"
    )


def test_cli_omits_limit_to_request_the_complete_source_result_set() -> None:
    args = md.build_parser().parse_args(
        [
            "search",
            "MO",
            "--mode",
            "advanced",
            "--description",
            "Estate",
        ]
    )

    assert args.limit is None
    selection = md._search_selection(args)
    assert selection.description == "Estate"
    assert selection.include_no_images is False
