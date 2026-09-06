from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_helion_recorder as helion


FIXTURE_DIR = Path("tests/fixtures/public_records/oregon_helion_recorder")


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _tenant(source_id: str = "us-or-umatilla-helion-recorder"):
    return helion.TENANTS_BY_SOURCE[source_id]


def _search_args(
    *,
    source: str = "us-or-umatilla-helion-recorder",
    limit: int = 2,
    cursor: str | None = None,
    document_to: int = 5,
):
    argv = [
        "search",
        "--source",
        source,
        "--year",
        "2026",
        "--document-from",
        "1",
        "--document-to",
        str(document_to),
        "--limit",
        str(limit),
    ]
    if cursor is not None:
        argv.extend(["--cursor", cursor])
    return helion.build_parser().parse_args(argv)


def _allowed(source_id: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "allowed": True,
        "automation_disposition": "allowed_with_limits",
        "limits": {"minimum_interval_seconds": 0},
    }


def test_tenants_are_distinct_county_components():
    assert len(helion.TENANTS) == 15
    assert len(helion.SOURCE_IDS) == 15
    assert len({tenant.county_fips for tenant in helion.TENANTS}) == 15
    assert {tenant.key for tenant in helion.TENANTS} == {
        "benton",
        "crook",
        "deschutes",
        "hood-river",
        "jackson",
        "jefferson",
        "lincoln",
        "marion",
        "multnomah",
        "polk",
        "tillamook",
        "umatilla",
        "wasco",
        "wheeler",
        "yamhill",
    }
    for tenant in helion.TENANTS:
        metadata = tenant.source_metadata.to_dict()
        assert metadata["source_id"] == tenant.source_id
        assert metadata["metadata"]["county_fips"] == tenant.county_fips
        assert metadata["metadata"]["platform_family"] == (
            "helion_digital_research_room"
        )


def test_yamhill_source_preserves_live_joinable_recorder_observations():
    tenant = _tenant("us-or-yamhill-helion-recorder")
    args = helion.build_parser().parse_args(["source", "--source", tenant.source_id])
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        client=object(),
        log_results=False,
    )

    assert tenant.county_fips == "41071"
    assert tenant.captcha_observed is False
    assert (
        "yamhill"
        in tenant.source_metadata.to_dict()["metadata"]["family_route_contract"][
            "live_verified_tenants"
        ]
    )

    record = result.to_dict()["records"][0]
    assert record["official_linking_page"] == (
        "https://yamhillcounty.gov/404/Clerk-Records-Elections"
    )
    assert "2026-003177" in record["resource_observation"]
    complements = {item["kind"]: item for item in record["complement_observations"]}
    assert complements["yamhill_ascendweb_property"]["relationship"] == (
        "parcel_sale_and_tax_context_complement"
    )
    assert "recording_number" in complements["yamhill_county_taxlots"]["join_keys"]


def test_lincoln_source_preserves_verified_resources_and_complements():
    tenant = _tenant("us-or-lincoln-helion-recorder")
    args = helion.build_parser().parse_args(["source", "--source", tenant.source_id])
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        client=object(),
        log_results=False,
    )

    assert tenant.key == "lincoln"
    assert tenant.county_fips == "41041"
    assert tenant.authority == "Lincoln County Clerk"
    assert tenant.captcha_observed is False
    assert "395 tenant-native subtype options" in tenant.access_observation
    assert (
        "lincoln"
        in tenant.source_metadata.to_dict()["metadata"]["family_route_contract"][
            "live_verified_tenants"
        ]
    )

    record = result.to_dict()["records"][0]
    assert record["official_linking_page"] == (
        "https://www.co.lincoln.or.us/962/Document-Recording-Information-and-Docum"
    )
    assert "direct PDF image" in record["resource_observation"]
    assert "2026-01-01" in record["resource_observation"]
    complements = {item["kind"]: item for item in record["complement_observations"]}
    assert complements["lincoln_propertyweb"]["relationship"] == (
        "parcel_sale_and_instrument_context_complement"
    )
    assert "sale_instrument" in complements["lincoln_propertyweb"]["join_keys"]
    assert complements["lincoln_taxlot_wfs"]["relationship"] == (
        "parcel_geometry_and_owner_complement"
    )
    assert (
        complements["lincoln_clerk_recording_information_and_copy"]["relationship"]
        == "copy_and_official_guidance_complement"
    )


def test_marion_source_keeps_current_and_historical_indexes_distinct():
    tenant = _tenant("us-or-marion-clerk-recorded-documents")
    args = helion.build_parser().parse_args(["source", "--source", tenant.source_id])
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        client=object(),
        log_results=False,
    )

    assert tenant.key == "marion"
    assert tenant.county_fips == "41047"
    assert tenant.captcha_observed is False
    assert (
        "marion"
        in tenant.source_metadata.to_dict()["metadata"]["family_route_contract"][
            "live_verified_tenants"
        ]
    )

    record = result.to_dict()["records"][0]
    assert record["official_linking_page"] == (
        "https://www.co.marion.or.us/CO/Pages/Records.aspx"
    )
    assert "1974 to present" in record["coverage_observation"]
    assert "07/28/2026" in record["coverage_observation"]
    assert "2026-00001" in record["resource_observation"]

    complements = {item["kind"]: item for item in record["complement_observations"]}
    historical = complements["marion_historical_deed_search"]
    assert historical["coverage_label"] == "1855-1976"
    assert historical["overlap_with_current_index"] == "1974-1976"
    assert historical["relationship"] == "historical_deed_index_complement"
    assert historical["selectors"] == [
        "file_date_start",
        "file_date_end",
        "instrument_type",
        "direct_party_grantor",
        "indirect_party_grantee",
    ]
    assessor = complements["marion_assessor_property_records"]
    assert assessor["join_keys"] == [
        "account_number",
        "map_tax_lot",
        "situs_address",
        "subdivision",
    ]
    copies = complements["marion_official_copy_and_certification"]
    assert copies["retrieval_routes"] == ["counter", "mail"]
    assert copies["relationship"] == (
        "official_copy_and_certification_complement"
    )


def test_source_record_preserves_access_and_complement_observations():
    args = helion.build_parser().parse_args(
        [
            "source",
            "--source",
            "us-or-deschutes-helion-recorder",
        ]
    )
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        client=object(),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["captcha_observed"] is True
    assert "reCAPTCHA" in record["access_observation"]
    complements = {item["kind"]: item for item in record["complement_observations"]}
    assert complements["deschutes_assessor_dial"]["relationship"] == (
        "parcel_and_sale_context_complement"
    )
    assert "recording_number" in complements["county_copy_order"]["join_keys"]


def test_parse_search_results_preserves_parties_map_fields_and_references():
    batch = helion.parse_search_html(
        _fixture("search_results.html"),
        tenant=_tenant(),
        source_url=("https://public.co.umatilla.or.us/DigitalResearchRoomPublic/"),
    )

    assert batch.total_results == 3
    assert batch.start_position == 1
    assert batch.end_position == 3
    assert batch.search_id == "307579"
    assert len(batch.records) == 3
    first = batch.records[0]
    assert first["canonical_ref"] == "ORREC:41059:2026:1"
    assert first["native_detail_key"] == {
        "year": 2026,
        "document": 1,
        "title": None,
    }
    assert first["recording_date_local_iso"] == "2026-01-02T09:03:00"
    assert first["document_type"] == "TRUST DEED - MODIFICATION"
    assert first["parties"] == [
        {
            "party_type": "DIRECT",
            "name": "MARMOLEJO JARAMILLO, JOAQUIN",
        },
        {"party_type": "INDIRECT", "name": "BANNER BANK"},
    ]
    assert first["map_legal_fields"] == [
        {"field": "Subdivision", "value": "ROYER RANCHETTES"},
        {"field": "Lot", "value": "4"},
    ]
    assert first["references"][0]["native_detail_key"] == {
        "year": 2025,
        "document": 4860,
        "title": None,
    }


def test_parse_marion_search_supports_current_span_and_div_markup():
    tenant = _tenant("us-or-marion-clerk-recorded-documents")
    batch = helion.parse_search_html(
        _fixture("marion_search_results.html"),
        tenant=tenant,
        source_url=tenant.search_url,
    )

    assert batch.total_results == 2
    assert batch.start_position == 1
    assert batch.end_position == 2
    assert batch.search_id == "501995"
    first = batch.records[0]
    assert first["canonical_ref"] == "ORREC:41047:2026:1"
    assert first["instrument_number"] == "2026-00001"
    assert first["recording_date_local_iso"] == "2026-01-02T08:36:00"
    assert first["document_type"] == "Assignment"
    assert first["parties"] == [
        {
            "party_type": "DIRECT",
            "name": "MORTGAGE ELECTRONIC REGISTRATION SYSTEMS INC",
        },
        {
            "party_type": "INDIRECT",
            "name": "LAKEVIEW LOAN SERVICING LLC",
        },
    ]
    assert first["references"][0] == {
        "instrument_number": "2023-01093",
        "detail_url": (
            "https://lrmw-marioncountygcc.msappproxy.net/"
            "DigitalResearchRoomPublic/Document/Details?year=2023&document=1093"
        ),
        "native_detail_key": {
            "year": 2023,
            "document": 1093,
            "title": None,
        },
    }


def test_parse_polk_title_rows_does_not_collapse_one_document():
    tenant = _tenant("us-or-polk-helion-recorder")
    batch = helion.parse_search_html(
        _fixture("polk_title_results.html"),
        tenant=tenant,
        source_url=tenant.search_url,
    )

    assert [record["instrument_number"] for record in batch.records] == [
        "2026-000001",
        "2026-000001 (2)",
    ]
    assert [record["title_selector"] for record in batch.records] == [1, 2]
    assert [record["canonical_ref"] for record in batch.records] == [
        "ORREC:41053:2026:1:T1",
        "ORREC:41053:2026:1:T2",
    ]
    assert all(
        record["document_image"]["availability"] == "viewable"
        for record in batch.records
    )
    assert all(
        record["text_alternative"]["availability"] == "viewable"
        for record in batch.records
    )


def test_parse_purchasable_detail_preserves_native_and_cart_keys():
    tenant = _tenant()
    record = helion.parse_detail_html(
        _fixture("detail_purchasable.html"),
        tenant=tenant,
        source_url=(
            "https://public.co.umatilla.or.us/"
            "DigitalResearchRoomPublic/Document/Details"
            "?year=2026&document=1"
        ),
    )

    assert record["canonical_ref"] == "ORREC:41059:2026:1"
    assert record["recording_date_local_iso"] == "2026-01-02T09:03:01"
    assert record["e_recorded"] is True
    assert record["consideration_amount"] is None
    assert record["page_count"] == 3
    assert record["return_to_lines"] == [
        "LIEN SOLUTIONS",
        "330 N. BRAND BLVD, SUITE 700",
        "GLENDALE, CA 91203",
    ]
    assert record["document_image"] == {
        "availability": "purchasable",
        "url": None,
        "format": None,
    }
    assert record["cart_metadata"]["system_id"] == "1033835"
    assert record["cart_metadata"]["add_item_url"].endswith("/Cart/AddRecording")
    assert record["copy_options"][1]["label"] == "Non-Certified Copy"
    assert record["legal_descriptions"] == [
        {"Subdivision": "ROYER RANCHETTES", "Lot": "4"}
    ]
    assert record["references_from_document"][0]["system_id"] == 1028459
    assert record["references_to_document"] == []


def test_parse_yamhill_detail_supports_current_semantic_markup():
    tenant = _tenant("us-or-yamhill-helion-recorder")
    record = helion.parse_detail_html(
        _fixture("yamhill_detail.html"),
        tenant=tenant,
        source_url=(
            "https://clerkwebapp.co.yamhill.or.us/DigitalResearchRoom/"
            "Document/Details?year=2026&document=3177"
        ),
    )

    assert record["canonical_ref"] == "ORREC:41071:2026:3177"
    assert record["recording_date_local_iso"] == "2026-04-07T08:43:36"
    assert record["document_type"] == "DEED"
    assert record["return_to_lines"] == [
        "MICHAEL G GUNN",
        "ATTORNEY",
        "PO BOX 272",
        "DUNDEE, OR 97115",
    ]
    assert record["parties"] == [
        {"party_type": "DIRECT", "name": "LUTZE, ALBERT L"},
        {"party_type": "DIRECT", "name": "LUTZE, JUDY A"},
        {"party_type": "INDIRECT", "name": "LUTZE, ALBERT L TRUSTEE"},
        {"party_type": "INDIRECT", "name": "LUTZE, JUDY A TRUSTEE"},
    ]
    assert record["legal_descriptions"] == [
        {"Sct": "18", "Twn": "3S", "Rng": "2W"}
    ]
    assert record["references_from_document"][0]["instrument_number"] == (
        "2024-000119"
    )
    assert record["references_to_document"] == []


def test_parse_marion_detail_supports_current_heading_and_party_markup():
    tenant = _tenant("us-or-marion-clerk-recorded-documents")
    record = helion.parse_detail_html(
        _fixture("marion_detail.html"),
        tenant=tenant,
        source_url=(
            "https://lrmw-marioncountygcc.msappproxy.net/"
            "DigitalResearchRoomPublic/Document/Details?year=2026&document=1"
        ),
    )

    assert record["canonical_ref"] == "ORREC:41047:2026:1"
    assert record["recording_date_local_iso"] == "2026-01-02T08:36:07"
    assert record["document_type"] == "Assignment"
    assert record["consideration_amount"] == "517000.00"
    assert record["return_to_lines"] == ["RECORDED ELECTRONICALLY"]
    assert record["parties"] == [
        {
            "party_type": "DIRECT",
            "name": "MORTGAGE ELECTRONIC REGISTRATION SYSTEMS INC",
        },
        {
            "party_type": "INDIRECT",
            "name": "LAKEVIEW LOAN SERVICING LLC",
        },
    ]
    assert record["titles"][0]["title_label"] == "Title 1"
    assert record["references_from_document"][0]["instrument_number"] == (
        "2023-01093"
    )
    assert record["references_from_document"][0]["system_id"] == 5402623
    assert record["references_to_document"] == []
    assert record["document_image"]["availability"] == "not_advertised"
    assert record["text_alternative"]["availability"] == "not_advertised"


def test_parse_viewable_detail_keeps_pdf_and_ocr_as_separate_resources():
    tenant = _tenant("us-or-wasco-helion-recorder")
    record = helion.parse_detail_html(
        _fixture("detail_viewable.html"),
        tenant=tenant,
        source_url=(
            "https://public.co.wasco.or.us/"
            "DigitalResearchRoomPublic/Document/Details"
            "?year=2026&document=1"
        ),
    )

    assert record["consideration_amount"] == "1200000.00"
    assert record["document_image"]["availability"] == "viewable"
    assert "DocumentImage/2026-000001" in record["document_image"]["url"]
    assert record["text_alternative"]["availability"] == "viewable"
    assert "DocumentText/2026-000001" in record["text_alternative"]["url"]
    assert record["legal_descriptions"][0]["Property ID"] == "13399"
    assert record["cart_metadata"]["system_id"] == "500001"


def test_parse_multititle_detail_keeps_title_scoped_relationships():
    tenant = _tenant("us-or-polk-helion-recorder")
    record = helion.parse_detail_html(
        _fixture("detail_multititle.html"),
        tenant=tenant,
        source_url=(
            "https://apps2.co.polk.or.us/"
            "DigitalResearchRoom/Document/Details"
            "?year=2026&document=1"
        ),
    )

    assert record["canonical_ref"] == "ORREC:41053:2026:1"
    assert record["title_count"] == 2
    assert record["document_type"] is None
    assert record["document_types"] == [
        "DR: DEED OF RECONVEYANCE",
        "APT: APPOINTMENT SUCCESSOR TRUSTEE",
    ]
    assert [title["canonical_ref"] for title in record["titles"]] == [
        "ORREC:41053:2026:1:T1",
        "ORREC:41053:2026:1:T2",
    ]
    assert record["titles"][0]["parties"][0] == {
        "party_type": "DIRECT",
        "name": "PETTIT, DAVID C",
    }
    assert record["titles"][1]["parties"][0] == {
        "party_type": "DIRECT",
        "name": "MERS",
    }
    assert record["titles"][0]["legal_descriptions"] == [
        {"Subdivision": "SAMPLE ACRES", "Lot": "1"}
    ]
    assert record["titles"][1]["legal_descriptions"] == []
    assert len(record["references_from_document"]) == 1


def test_parse_authoritative_no_match_is_not_a_transport_success():
    batch = helion.parse_search_html(
        _fixture("no_results.html"),
        tenant=_tenant(),
        source_url=_tenant().search_url,
    )

    assert batch.authoritative_empty is True
    assert batch.total_results == 0
    assert batch.records == ()


def test_parse_unknown_page_is_explicit_source_change():
    with pytest.raises(helion.HelionSourceChanged):
        helion.parse_search_html(
            "<html><body><h1>Maintenance</h1></body></html>",
            tenant=_tenant(),
            source_url=_tenant().search_url,
        )


class FixtureClient:
    def __init__(self, *, total: int = 5) -> None:
        parsed = helion.parse_search_html(
            _fixture("search_results.html"),
            tenant=_tenant(),
            source_url=_tenant().search_url,
        )
        template = dict(parsed.records[0])
        self.records: list[dict[str, Any]] = []
        for number in range(1, total + 1):
            record = deepcopy(template)
            record.update(
                {
                    "canonical_ref": f"ORREC:41059:2026:{number}",
                    "instrument_number": f"2026-{number:07d}",
                    "document_selector": number,
                    "native_detail_key": {
                        "year": 2026,
                        "document": number,
                        "title": None,
                    },
                    "search_position": number,
                }
            )
            self.records.append(record)
        self.search_calls: list[int] = []
        self.detail_calls: list[tuple[int, int, int | None]] = []

    def search(
        self,
        tenant,
        selectors: Mapping[str, Any],
        *,
        start: int,
        number_to_show: int,
    ) -> helion.SearchBatch:
        assert tenant.source_id == "us-or-umatilla-helion-recorder"
        assert selectors["year"] == 2026
        assert number_to_show == 50
        self.search_calls.append(start)
        records = tuple(self.records[start - 1 : start - 1 + 50])
        end = start + len(records) - 1 if records else 0
        return helion.SearchBatch(
            records=records,
            total_results=len(self.records),
            start_position=start if records else 0,
            end_position=end,
            source_url=tenant.search_url,
            search_id="fixture-search",
            schema_fingerprint="fixture-schema",
        )

    def detail(
        self,
        tenant,
        *,
        year: int,
        document: int,
        title: int | None,
    ):
        self.detail_calls.append((year, document, title))
        return helion.parse_detail_html(
            _fixture("detail_purchasable.html"),
            tenant=tenant,
            source_url=(
                f"{tenant.portal_root}Document/Details?year={year}&document={document}"
            ),
        )

    def probe(self, tenant):
        return {
            "canonical_ref": f"ORREC_PROBE:{tenant.county_fips}",
            "source_id": tenant.source_id,
            "record_kind": "source_probe",
        }


class EmptyClient(FixtureClient):
    def search(
        self,
        tenant,
        selectors: Mapping[str, Any],
        *,
        start: int,
        number_to_show: int,
    ) -> helion.SearchBatch:
        return helion.SearchBatch(
            records=(),
            total_results=0,
            start_position=0,
            end_position=0,
            source_url=tenant.search_url,
            search_id=None,
            schema_fingerprint="empty-schema",
            authoritative_empty=True,
        )


class HumanRequiredClient(FixtureClient):
    def search(
        self,
        tenant,
        selectors: Mapping[str, Any],
        *,
        start: int,
        number_to_show: int,
    ) -> helion.SearchBatch:
        raise helion.HelionHumanRequired(
            "fixture CAPTCHA",
            url=f"{tenant.portal_root}Disclaimer",
        )


def test_execute_cursor_is_query_bound_and_anchor_verified():
    client = FixtureClient()
    page_one = helion.execute(
        _search_args(limit=2),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=client,
        log_results=False,
    )
    assert page_one.status.value == "ok"
    assert [
        record["instrument_number"] for record in page_one.to_dict()["records"]
    ] == ["2026-0000001", "2026-0000002"]
    assert page_one.next_cursor is not None

    page_two = helion.execute(
        _search_args(limit=2, cursor=page_one.next_cursor),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=client,
        log_results=False,
    )
    assert page_two.status.value == "ok"
    assert [
        record["instrument_number"] for record in page_two.to_dict()["records"]
    ] == ["2026-0000003", "2026-0000004"]
    coverage = page_two.to_dict()["records"][0]["search_metadata"]["coverage"]
    assert coverage["cursor_anchor_verified"] is True
    assert coverage["returned_start_position"] == 3
    assert client.search_calls == [1, 2]

    changed_query = helion.execute(
        _search_args(
            limit=2,
            cursor=page_one.next_cursor,
            document_to=6,
        ),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=client,
        log_results=False,
    )
    assert changed_query.status.value == "source_changed"
    assert changed_query.errors[0].code == "cursor_query_mismatch"


def test_omitted_limit_exhausts_native_windows_and_large_limit_is_supported():
    unbounded_args = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-umatilla-helion-recorder",
            "--year",
            "2026",
            "--document-from",
            "1",
            "--document-to",
            "125",
        ]
    )
    unbounded_client = FixtureClient(total=125)
    unbounded = helion.execute(
        unbounded_args,
        catalog_decision=_allowed(unbounded_args.source),
        client=unbounded_client,
        log_results=False,
    )

    assert len(unbounded.records) == 125
    assert unbounded.next_cursor is None
    assert unbounded_client.search_calls == [1, 51, 101]
    coverage = unbounded.records[0]["search_metadata"]["coverage"]
    assert coverage["caller_limit"] is None
    assert coverage["completion_mode"] == "source_reported_total"
    assert coverage["complete_for_selected_query"] is True

    limited_client = FixtureClient(total=125)
    limited = helion.execute(
        _search_args(limit=75, document_to=125),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=limited_client,
        log_results=False,
    )
    assert len(limited.records) == 75
    assert limited.next_cursor is not None
    assert limited_client.search_calls == [1, 51]


def test_execute_authoritative_empty_uses_no_results_status():
    result = helion.execute(
        _search_args(),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=EmptyClient(total=0),
        log_results=False,
    )

    assert result.status.value == "no_results"
    assert result.records == ()
    assert result.errors == ()


def test_execute_detail_preserves_native_title_selector():
    client = FixtureClient()
    args = helion.build_parser().parse_args(
        [
            "detail",
            "--source",
            "us-or-umatilla-helion-recorder",
            "2026",
            "1",
            "--title",
            "2",
        ]
    )
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        client=client,
        log_results=False,
    )

    assert result.status.value == "ok"
    assert client.detail_calls == [(2026, 1, 2)]
    assert result.query.query.parameters["native_detail_key"] == {
        "year": 2026,
        "document": 1,
        "title": 2,
    }


def test_access_decision_blocks_before_dispatch_and_checks_source():
    args = _search_args()
    blocked = helion.execute(
        args,
        access_decision={
            "source_id": args.source,
            "allowed": False,
            "automation_disposition": "human_required",
            "reason_code": "browser_session_required",
            "reason": "Complete the live browser session.",
        },
        client=object(),
        log_results=False,
    )
    mismatch = helion.execute(
        args,
        catalog_decision={
            "source_id": "us-or-wasco-helion-recorder",
            "allowed": True,
        },
        client=object(),
        log_results=False,
    )

    assert blocked.status.value == "human_required"
    assert blocked.errors[0].code == "browser_session_required"
    assert mismatch.status.value == "unavailable"
    assert mismatch.errors[0].code == "catalog_decision_source_mismatch"
    with pytest.raises(ValueError, match="not both"):
        helion.execute(
            args,
            catalog_decision={"allowed": True},
            access_decision={"allowed": True},
            client=object(),
            log_results=False,
        )


def test_live_human_step_is_not_reported_as_no_results():
    result = helion.execute(
        _search_args(),
        catalog_decision=_allowed("us-or-umatilla-helion-recorder"),
        client=HumanRequiredClient(),
        log_results=False,
    )

    assert result.status.value == "human_required"
    assert result.errors[0].code == "recaptcha_session_required"
    assert result.records == ()


def test_invalid_date_and_missing_selector_fail_before_client_dispatch():
    invalid_date = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-umatilla-helion-recorder",
            "--recorded-from",
            "07/01/2026",
        ]
    )
    missing = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-umatilla-helion-recorder",
        ]
    )
    invalid_limit = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-umatilla-helion-recorder",
            "--recorded-from",
            "01/02/2026",
            "--limit",
            "0",
        ]
    )

    invalid_result = helion.execute(
        invalid_date,
        catalog_decision=_allowed(invalid_date.source),
        client=object(),
        log_results=False,
    )
    missing_result = helion.execute(
        missing,
        catalog_decision=_allowed(missing.source),
        client=object(),
        log_results=False,
    )
    invalid_limit_result = helion.execute(
        invalid_limit,
        catalog_decision=_allowed(invalid_limit.source),
        client=object(),
        log_results=False,
    )

    assert invalid_result.errors[0].code == "invalid_date_selector"
    assert missing_result.errors[0].code == "missing_search_selector"
    assert invalid_limit_result.errors[0].code == "invalid_limit"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_marion_exact_document_sentinel():
    args = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-marion-clerk-recorded-documents",
            "--year",
            "2026",
            "--document-from",
            "1",
            "--document-to",
            "1",
            "--limit",
            "1",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(args, log_results=False)

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41047:2026:1"
    assert record["instrument_number"] == "2026-00001"
    assert record["document_type"] == "Assignment"
    assert record["references_from_document"][0]["instrument_number"] == (
        "2023-01093"
    )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_umatilla_exact_document_and_cursor_sentinel():
    exact = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-umatilla-helion-recorder",
            "--year",
            "2026",
            "--document-from",
            "1",
            "--document-to",
            "1",
            "--limit",
            "1",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(exact, log_results=False)

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41059:2026:1"
    assert record["instrument_number"] == "2026-0000001"
    assert record["cart_metadata"]["system_id"] == "1033835"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_wasco_direct_image_sentinel():
    args = helion.build_parser().parse_args(
        [
            "detail",
            "--source",
            "us-or-wasco-helion-recorder",
            "2023",
            "2123",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(args, log_results=False)

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41065:2023:2123"
    assert record["consideration_amount"] == "1200000.00"
    assert record["document_image"]["availability"] == "viewable"


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_polk_multititle_sentinel():
    args = helion.build_parser().parse_args(
        [
            "search",
            "--source",
            "us-or-polk-helion-recorder",
            "--year",
            "2026",
            "--document-from",
            "1",
            "--document-to",
            "1",
            "--limit",
            "1",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(args, log_results=False)

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41053:2026:1"
    assert record["title_count"] == 2
    assert [title["title_selector"] for title in record["titles"]] == [1, 2]


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_lincoln_direct_image_and_text_cutoff_sentinel():
    args = helion.build_parser().parse_args(
        [
            "detail",
            "--source",
            "us-or-lincoln-helion-recorder",
            "2025",
            "1695",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(args, log_results=False)

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41041:2025:1695"
    assert record["instrument_number"] == "2025-001695"
    assert record["recording_date_local_iso"] == "2025-03-19T16:09:52"
    assert record["document_type"] == "Warranty Deed"
    assert record["consideration_amount"] == "115.00"
    assert {party["party_type"] for party in record["parties"]} == {
        "DIRECT",
        "INDIRECT",
    }
    assert record["return_to_lines"] == [
        "EUGENE L. SCRUTTON AND",
        "KAREN L. SCRUTTON, LLC.",
        "3264 NW JETTY AVENUE",
        "LINCOLN CITY, OR 97367",
    ]
    assert record["document_image"]["availability"] == "viewable"
    assert record["document_image"]["format"] == "pdf"
    assert record["text_alternative"] == {
        "availability": "not_available",
        "url": None,
        "format": None,
        "message": (
            "Text alternatives are only available for documents recorded "
            "01/01/2026 or later."
        ),
    }


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_HELION") != "1",
    reason="set RUN_LIVE_OR_HELION=1 for official county sentinels",
)
def test_live_yamhill_assessor_sale_join_sentinel():
    args = helion.build_parser().parse_args(
        [
            "detail",
            "--source",
            "us-or-yamhill-helion-recorder",
            "2026",
            "3177",
            "--minimum-interval",
            "0",
        ]
    )
    result = helion.execute(
        args,
        catalog_decision=_allowed(args.source),
        log_results=False,
    )

    assert result.status.value == "ok"
    record = result.to_dict()["records"][0]
    assert record["canonical_ref"] == "ORREC:41071:2026:3177"
    assert record["instrument_number"] == "2026-003177"
    assert record["recording_date_local_iso"] == "2026-04-07T08:43:36"
    assert record["document_type"] == "DEED"
    assert {party["party_type"] for party in record["parties"]} == {
        "DIRECT",
        "INDIRECT",
    }
    assert record["references_from_document"][0]["instrument_number"] == (
        "2024-000119"
    )
