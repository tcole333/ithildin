from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import query_florida_court_directory_data as florida
from tools.public_records_contract import ResultStatus


def _artifact(
    payload: Any,
    *,
    url: str,
    media_type: str = "application/json",
) -> florida.Artifact:
    content = (
        payload
        if isinstance(payload, bytes)
        else json.dumps(payload).encode()
    )
    return florida.Artifact(
        content=content,
        source_url=url,
        media_type=media_type,
        headers={"Content-Type": media_type},
    )


def _location_item(
    *,
    name: str,
    node_id: int,
    region: str | None,
) -> dict[str, Any]:
    published_region: dict[str, Any] | list[Any]
    if region is None:
        published_region = []
    else:
        published_region = {
            "identifier": region,
            "name": florida.EXPECTED_DISTRICTS[region],
        }
    return {
        "name": name,
        "node_id": node_id,
        "object_id": node_id + 1000,
        "parent_node_id": 2,
        "location": {
            "address": f"{node_id} Court Street Example, FL 32000",
            "city": "Example",
            "state": "FL",
            "zip": "32000",
            "county": name,
            "geolocation": {
                "latitude": 28.0,
                "longitude": -82.0,
                "contentobject_modified": 1700000000,
            },
            "region": published_region,
        },
        "url": f"/Courts-System/court-locations/{name}",
        "view": f"/poi/mapinfo/{node_id}",
        "court_site": {
            "link": f"https://court{node_id}.example/",
            "text": "Visit Court Website",
        },
        "clerk_site": {
            "link": f"https://clerk{node_id}.example/",
            "text": "Visit Clerk Website",
        },
        "jury": {
            "link": f"https://jury{node_id}.example/",
            "text": "Jury Duty Page",
        },
    }


def _location_payload() -> list[dict[str, Any]]:
    counties = {
        "1dca": "Alachua",
        "2dca": "Charlotte",
        "3dca": "Miami-Dade",
        "4dca": "Broward",
        "5dca": "Flagler",
        "6dca": "Orange",
    }
    payload: list[dict[str, Any]] = []
    for index, (district, district_name) in enumerate(
        florida.EXPECTED_DISTRICTS.items(),
        start=1,
    ):
        region = "5dca" if district == "6dca" else district
        items = [
            _location_item(
                name=counties[district],
                node_id=index,
                region=region,
            )
        ]
        if district == "1dca":
            items.append(
                _location_item(
                    name="First District DCA",
                    node_id=100,
                    region=None,
                )
            )
            items.append(
                _location_item(
                    name="Supreme Court",
                    node_id=101,
                    region=None,
                )
            )
        payload.append(
            {
                "category_id": district,
                "content": {
                    "category": {
                        "identifier": district,
                        "name": district_name,
                    },
                    "items_count": len(items),
                    "items": items,
                },
            }
        )
    return payload


def _virtual_payload() -> dict[str, Any]:
    return {
        "items": [
            {
                "location_id": 10,
                "content_id": 20,
                "name": "Lee County Judge George",
                "youtube_id": "channel-one",
                "stream": {"live": False, "tags": []},
                "counties": ["Lee County"],
                "all_counties": ["Lee County"],
                "judge": "Judge Devin S. George",
                "court": "20th Judicial Circuit",
                "jurisdiction_link": "https://www.ca.cjis20.org/",
            },
            {
                "location_id": 11,
                "content_id": 21,
                "name": "Circuit Livestream",
                "youtube_id": "channel-two",
                "stream": {
                    "live": True,
                    "tags": ["court"],
                    "link": "https://youtube.example/live",
                },
                "counties": ["Leon County", "Wakulla County"],
                "all_counties": ["Leon County", "Wakulla County"],
                "judge": "",
                "court": "2nd Judicial Circuit",
                "jurisdiction_link": "https://2ndcircuit.example/",
            },
        ]
    }


def _next_page(page_data: dict[str, Any], *, url: str) -> florida.Artifact:
    payload = {"props": {"pageProps": {"pageData": page_data}}}
    body = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload)}"
        "</script></html>"
    )
    return florida.Artifact(
        content=body.encode(),
        source_url=url,
        media_type="text/html",
        headers={"Content-Type": "text/html"},
    )


def _request_page() -> florida.Artifact:
    return _next_page(
        {
            "name": "Public Records",
            "description": {
                "html5": (
                    "<p>Direct inquiries to "
                    '<a href="mailto:oscapio@flcourts.org">'
                    "oscapio@flcourts.org</a>.</p>"
                    "<p>If email is unavailable, call (850) 922-1187. "
                    "Applicable fees are provided in an estimate.</p>"
                )
            },
        },
        url=florida.PUBLIC_RECORDS_URL,
    )


def _statistics_page() -> florida.Artifact:
    metadata_one = json.dumps(
        {
            "fileName": "2024-25-overall.pdf",
            "downloadUrl": (
                "https://flcourts-media.ccplatform.net/content/"
                "download/101/file/2024-25-overall.pdf"
            ),
            "fileSize": "1 MB",
            "mimeType": "application/pdf",
            "linkTitle": "2024-25 overall",
        }
    )
    metadata_two = json.dumps(
        {
            "fileName": "2024-25-civil.pdf",
            "downloadUrl": (
                "https://flcourts-media.ccplatform.net/content/"
                "download/102/file/2024-25-civil.pdf"
            ),
            "fileSize": "2 MB",
            "mimeType": "application/pdf",
            "linkTitle": "2024-25 civil",
        }
    )
    metadata_three = json.dumps(
        {
            "fileName": "2023-24-overall.pdf",
            "downloadUrl": (
                "https://flcourts-media.ccplatform.net/content/"
                "download/201/file/2023-24-overall.pdf"
            ),
            "fileSize": "3 MB",
            "mimeType": "application/pdf",
            "linkTitle": "2023-24 overall",
        }
    )
    description = f"""
        <h2>Fiscal Year 2024-25</h2>
        <p><strong>Statistics</strong></p>
        <ul>
          <li>Overall Statistics -
            <a href="/content/download/101/file/2024-25-overall.pdf"
               data-content='{metadata_one}'>PDF</a>
          </li>
          <li>Circuit Civil Statistics -
            <a href="/content/download/102/file/2024-25-civil.pdf"
               data-content='{metadata_two}'>PDF</a>
          </li>
        </ul>
        <h2>Fiscal Year 2023-24</h2>
        <p><strong>Statistics</strong></p>
        <ul>
          <li>Overall Statistics -
            <a href="/content/download/201/file/2023-24-overall.pdf"
               data-content='{metadata_three}'>PDF</a>
          </li>
        </ul>
    """
    return _next_page(
        {
            "name": "Trial Court Statistical Reference Guide",
            "description": {"html5": description},
        },
        url=florida.STATISTICS_CATALOG_URL,
    )


class FakeClient:
    def __init__(self) -> None:
        self.virtual_calls: list[tuple[str | None, str | None]] = []
        self.get_calls: list[str] = []

    def locations(self) -> florida.Artifact:
        return _artifact(
            _location_payload(),
            url=florida.LOCATION_API_URL,
        )

    def virtual(
        self,
        *,
        county: str | None = None,
        judge: str | None = None,
    ) -> florida.Artifact:
        self.virtual_calls.append((county, judge))
        return _artifact(
            _virtual_payload(),
            url=(
                florida.VIRTUAL_API_URL
                + "?"
                + ("judge=George" if judge else "county=All")
            ),
        )

    def page(self, url: str) -> florida.Artifact:
        if url == florida.PUBLIC_RECORDS_URL:
            return _request_page()
        if url == florida.STATISTICS_CATALOG_URL:
            return _statistics_page()
        raise AssertionError(f"unexpected page URL: {url}")

    def get(self, url: str, **_kwargs: Any) -> florida.Artifact:
        self.get_calls.append(url)
        return florida.Artifact(
            content=b"%PDF-1.7\nfixture",
            source_url=url,
            media_type="application/pdf",
            headers={"Content-Type": "application/pdf"},
        )


def test_location_parser_preserves_source_region_anomaly() -> None:
    records = florida.parse_location_directory(
        _artifact(
            _location_payload(),
            url=florida.LOCATION_API_URL,
        )
    )
    assert len(records) == 8
    orange = next(record for record in records if record["name"] == "Orange")
    assert orange["county_geoid"] == "12095"
    assert orange["appellate_map_category"]["identifier"] == "6dca"
    assert orange["published_region"]["identifier"] == "5dca"
    assert orange["published_region_matches_map_category"] is False
    first_dca = next(
        record for record in records if record["name"] == "First District DCA"
    )
    assert first_dca["record_kind"] == "district_court_of_appeal_location"
    assert first_dca["county_geoid"] is None
    assert first_dca["county"] is None
    assert first_dca["published_region"] is None
    supreme = next(
        record for record in records if record["name"] == "Supreme Court"
    )
    assert supreme["record_kind"] == "state_supreme_court_location"
    assert supreme["county"] is None
    assert supreme["published_location_county"] == "Supreme Court"


def test_location_parser_rejects_advertised_count_drift() -> None:
    payload = _location_payload()
    payload[0]["content"]["items_count"] = 99
    with pytest.raises(florida.SourceChangedError, match="count"):
        florida.parse_location_directory(
            _artifact(payload, url=florida.LOCATION_API_URL)
        )


def test_location_parser_rejects_unknown_category() -> None:
    payload = _location_payload()
    payload[-1]["category_id"] = "7dca"
    with pytest.raises(florida.SourceChangedError, match="categories changed"):
        florida.parse_location_directory(
            _artifact(payload, url=florida.LOCATION_API_URL)
        )


def test_virtual_parser_preserves_partial_judicial_roster_semantics() -> None:
    records = florida.parse_virtual_directory(
        _artifact(
            _virtual_payload(),
            url=florida.VIRTUAL_API_URL + "?county=All",
        )
    )
    assert len(records) == 2
    assert records[0]["judge_or_hearing_officer"] == "Judge Devin S. George"
    assert records[0]["stream"]["url"].endswith("/channel/channel-one")
    assert records[1]["judge_or_hearing_officer"] is None
    assert records[1]["stream"]["live"] is True
    assert records[1]["stream"]["url"] == "https://youtube.example/live"


def test_virtual_parser_rejects_non_boolean_live_state() -> None:
    payload = _virtual_payload()
    payload["items"][0]["stream"]["live"] = "false"
    with pytest.raises(florida.SourceChangedError, match="live state"):
        florida.parse_virtual_directory(
            _artifact(payload, url=florida.VIRTUAL_API_URL)
        )


def test_data_request_parser_extracts_osca_route() -> None:
    record = florida.parse_data_request_program(_request_page())
    assert record["source_id"] == florida.PUBLIC_RECORDS_SOURCE_ID
    assert record["request_scope"] == "records_held_by_osca"
    assert record["request_methods"] == [
        {"method": "email", "address": "oscapio@flcourts.org"},
        {"method": "telephone_assistance", "number": "(850) 922-1187"},
    ]
    assert record["fee_estimate_notice_published"] is True


def test_statistics_catalog_keeps_year_and_section_occurrences() -> None:
    records = florida.parse_statistics_catalog(_statistics_page())
    assert len(records) == 3
    assert records[0]["native_document_id"] == "101"
    assert records[0]["fiscal_year"] == "2024-25"
    assert records[0]["catalog_section"] == "Statistics"
    assert records[0]["title"] == "Overall Statistics"
    assert records[0]["filename"] == "2024-25-overall.pdf"
    assert records[-1]["native_document_id"] == "201"
    assert records[-1]["fiscal_year"] == "2023-24"


def test_statistics_catalog_rejects_invalid_link_metadata() -> None:
    page = _statistics_page()
    page = florida.Artifact(
        content=page.content.replace(
            b"data-content='{",
            b"data-content='not-json{",
            1,
        ),
        source_url=page.source_url,
        media_type=page.media_type,
        headers=page.headers,
    )
    with pytest.raises(florida.SourceChangedError, match="invalid JSON"):
        florida.parse_statistics_catalog(page)


def test_sources_and_manifest_keep_distinct_source_identities() -> None:
    client = FakeClient()
    sources_args = florida.build_parser().parse_args(["sources"])
    sources = florida.execute(
        sources_args,
        client=client,
        log_results=False,
    )
    assert sources.status == ResultStatus.OK
    assert {record["source_id"] for record in sources.records} == set(
        florida.COMPONENTS
    )

    manifest_args = florida.build_parser().parse_args(["manifest"])
    manifest = florida.execute(
        manifest_args,
        client=client,
        log_results=False,
    )
    assert manifest.status == ResultStatus.OK
    record = manifest.records[0]
    assert record["source_relationships"]["appellate_cases"] == (
        "covered separately by us-fl-acis"
    )
    alternatives = record["bulk_and_request_landscape"]
    assert any(item["url"] == florida.JDMS_URL for item in alternatives)
    assert any(
        item.get("useful_substitute") == florida.STATISTICS_SOURCE_ID
        for item in alternatives
    )


def test_location_execution_filters_and_uses_location_identity() -> None:
    args = florida.build_parser().parse_args(
        ["locations", "--query", "Miami", "--kind", "county"]
    )
    result = florida.execute(args, client=FakeClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert result.query.source.source_id == florida.LOCATION_SOURCE_ID
    assert [record["name"] for record in result.records] == ["Miami-Dade"]


def test_virtual_execution_passes_judge_and_filters_live() -> None:
    client = FakeClient()
    args = florida.build_parser().parse_args(
        ["virtual", "--judge", "George", "--query", "George"]
    )
    result = florida.execute(args, client=client, log_results=False)
    assert result.status == ResultStatus.OK
    assert result.query.source.source_id == florida.VIRTUAL_SOURCE_ID
    assert client.virtual_calls == [(None, "George")]
    assert [record["native_record_id"] for record in result.records] == ["10"]

    live_args = florida.build_parser().parse_args(
        ["virtual", "--live-only"]
    )
    live = florida.execute(live_args, client=client, log_results=False)
    assert [record["native_record_id"] for record in live.records] == ["11"]


def test_statistics_execution_filters_year_section_and_limit() -> None:
    args = florida.build_parser().parse_args(
        [
            "statistics",
            "--fiscal-year",
            "2024-25",
            "--section",
            "statistics",
            "--query",
            "Statistics",
            "--limit",
            "1",
        ]
    )
    result = florida.execute(args, client=FakeClient(), log_results=False)
    assert result.status == ResultStatus.OK
    assert result.query.source.source_id == florida.STATISTICS_SOURCE_ID
    assert len(result.records) == 1
    assert result.records[0]["fiscal_year"] == "2024-25"


def test_download_resolves_exact_content_id_and_writes_pdf(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "overall.pdf"
    client = FakeClient()
    args = florida.build_parser().parse_args(
        ["download", "101", str(destination)]
    )
    result = florida.execute(args, client=client, log_results=False)
    assert result.status == ResultStatus.OK
    assert destination.read_bytes().startswith(b"%PDF-")
    assert client.get_calls == [
        (
            "https://flcourts-media.ccplatform.net/content/"
            "download/101/file/2024-25-overall.pdf"
        )
    ]
    assert result.records[0]["native_document_id"] == "101"


def test_download_rejects_ambiguous_title(tmp_path: Path) -> None:
    args = florida.build_parser().parse_args(
        ["download", "Overall Statistics", str(tmp_path / "x.pdf")]
    )
    result = florida.execute(args, client=FakeClient(), log_results=False)
    assert result.status == ResultStatus.UNAVAILABLE
    assert result.errors[0].code == "artifact_selector_ambiguous"


def test_source_change_is_not_reported_as_no_results() -> None:
    class BrokenClient(FakeClient):
        def locations(self) -> florida.Artifact:
            return _artifact({}, url=florida.LOCATION_API_URL)

    args = florida.build_parser().parse_args(["locations"])
    result = florida.execute(args, client=BrokenClient(), log_results=False)
    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.records == ()
    assert result.errors[0].code == "location_payload_invalid"


def test_parser_enforces_mutually_exclusive_virtual_selectors() -> None:
    with pytest.raises(SystemExit):
        florida.build_parser().parse_args(
            ["virtual", "--county", "Lee", "--judge", "George"]
        )
