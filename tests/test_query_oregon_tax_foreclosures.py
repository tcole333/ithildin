from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfWriter

from tools import query_oregon_tax_foreclosures as oregon_tax


FIXTURE_DIR = Path("tests/fixtures/public_records/oregon_tax_foreclosures")


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _blank_pdf(path: Path, *, page_count: int = 1) -> Path:
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as stream:
        writer.write(stream)
    return path


def _args(*values: str) -> Any:
    return oregon_tax.build_parser().parse_args(list(values))


def test_sources_describe_stage_split_join_keys_and_complements():
    payload = oregon_tax.execute(_args("sources"))

    assert len(payload["sources"]) == 4
    multnomah = next(
        item
        for item in payload["sources"]
        if item["source"]["source_id"] == oregon_tax.MULTNOMAH_SOURCE_ID
    )
    assert {page["role"] for page in multnomah["landing_pages"]} == {
        "redemption_notice_index",
        "tax_title_publication_index",
    }
    assert "real_property_id" in multnomah["stable_join_keys"]
    assert {item["role"] for item in multnomah["complementary_sources"]} >= {
        "parcel_and_tax_account_context",
        "records_request_for_unpublished_material",
        "post_sale_surplus_notices",
    }
    assert multnomah["supported_process_stages"] == [
        oregon_tax.REDEMPTION_NOTICE_STAGE,
        oregon_tax.ANNOUNCED_IN_PROGRESS_STAGE,
        oregon_tax.TAX_TITLE_INVENTORY_STAGE,
        oregon_tax.SALE_AUTHORIZATION_STAGE,
    ]
    clackamas = next(
        item
        for item in payload["sources"]
        if item["source"]["source_id"] == oregon_tax.CLACKAMAS_SOURCE_ID
    )
    assert "newspaper" in clackamas["coverage_note"]
    assert oregon_tax.AUCTION_RESULTS_STAGE in payload["process_stages"]


def test_tillamook_and_marion_discovery_preserve_publication_cohorts():
    tillamook = oregon_tax._parse_anchor_page(
        oregon_tax.SOURCES[oregon_tax.TILLAMOOK_SOURCE_ID],
        _fixture("tillamook.html"),
        page=oregon_tax.SOURCES[oregon_tax.TILLAMOOK_SOURCE_ID].landing_pages[0],
    )
    assert [item["publication_year"] for item in tillamook] == [2025, 2024]
    assert {item["process_stage"] for item in tillamook} == {
        oregon_tax.FORECLOSURE_LIST_STAGE
    }
    assert tillamook[0]["document_url"].endswith(
        "foreclosure_list_2025_rev_1-15-2026.pdf"
    )

    marion = oregon_tax._parse_anchor_page(
        oregon_tax.SOURCES[oregon_tax.MARION_SOURCE_ID],
        _fixture("marion.html"),
        page=oregon_tax.SOURCES[oregon_tax.MARION_SOURCE_ID].landing_pages[0],
    )
    assert {item["process_stage"] for item in marion} == {
        oregon_tax.FORECLOSURE_LIST_STAGE,
        oregon_tax.END_REDEMPTION_STAGE,
    }
    redemption = next(
        item
        for item in marion
        if item["process_stage"] == oregon_tax.END_REDEMPTION_STAGE
    )
    assert redemption["publication_year"] == 2024
    assert redemption["publication_status"] == "published_artifact"


def test_multnomah_discovery_separates_in_progress_redemption_and_tax_title():
    config = oregon_tax.SOURCES[oregon_tax.MULTNOMAH_SOURCE_ID]
    foreclosure = oregon_tax._parse_anchor_page(
        config,
        _fixture("multnomah_foreclosure.html"),
        page=config.landing_pages[0],
    )
    assert {
        (item["process_stage"], item["publication_status"]) for item in foreclosure
    } == {
        (
            oregon_tax.REDEMPTION_NOTICE_STAGE,
            "published_artifact",
        ),
        (
            oregon_tax.ANNOUNCED_IN_PROGRESS_STAGE,
            "announced_in_progress",
        ),
    }
    pending = next(
        item
        for item in foreclosure
        if item["process_stage"] == oregon_tax.ANNOUNCED_IN_PROGRESS_STAGE
    )
    assert pending["document_url"] is None
    assert pending["court_case_number"] == "25CV-40782"

    tax_title = oregon_tax._parse_anchor_page(
        config,
        _fixture("multnomah_tax_title.html"),
        page=config.landing_pages[1],
    )
    assert {item["process_stage"] for item in tax_title} == {
        oregon_tax.TAX_TITLE_INVENTORY_STAGE,
        oregon_tax.SALE_AUTHORIZATION_STAGE,
    }
    inventory = next(
        item
        for item in tax_title
        if item["process_stage"] == oregon_tax.TAX_TITLE_INVENTORY_STAGE
    )
    assert inventory["publication_date"] == "2026-06-30"


def test_clackamas_discovery_exposes_post_deed_artifacts_without_inventing_list():
    config = oregon_tax.SOURCES[oregon_tax.CLACKAMAS_SOURCE_ID]
    process_page = oregon_tax._parse_anchor_page(
        config,
        _fixture("clackamas_foreclosures.html"),
        page=config.landing_pages[0],
    )
    assert process_page == []

    disposition = oregon_tax._parse_anchor_page(
        config,
        _fixture("clackamas_property.html"),
        page=config.landing_pages[1],
    )
    assert len(disposition) == 3
    current_results = next(
        item for item in disposition if item["publication_label"] == "Auction Results"
    )
    assert current_results["process_stage"] == (oregon_tax.AUCTION_RESULTS_STAGE)
    assert current_results["publication_date"] == "2025-12-18"
    historical = next(
        item for item in disposition if item["publication_label"].startswith("Sept.")
    )
    assert historical["publication_date"] == "2025-09-16"


def test_discover_source_fingerprints_each_landing_page():
    config = oregon_tax.SOURCES[oregon_tax.MULTNOMAH_SOURCE_ID]
    pages = {
        config.landing_pages[0].url: _fixture("multnomah_foreclosure.html").encode(),
        config.landing_pages[1].url: _fixture("multnomah_tax_title.html").encode(),
    }

    def fake_fetch(url: str, _timeout: float, _max_bytes: int) -> bytes:
        return pages[url]

    result = oregon_tax.discover_source(config, fetcher=fake_fetch)

    assert len(result["landing_page_observations"]) == 2
    assert len(result["publication_routes"]) == 4
    for observation in result["landing_page_observations"]:
        assert len(observation["page_sha256"]) == 64


def test_tillamook_parser_preserves_case_stage_dates_and_property_keys():
    records = oregon_tax.parse_tillamook_foreclosure_list(_fixture("tillamook.txt"))

    assert len(records) == 2
    first = records[0]
    assert first["tax_account"] == "787"
    assert first["property_map_id"] == "1N1005AB01100"
    assert first["published_name_lines"] == [
        "COOPER, CLARENCE C",
        "COOPER, JOSEPHINE L",
    ]
    assert first["court_case_number"] == "25-CV47055"
    assert first["general_judgment_date"] == "2026-01-15"
    assert first["advertising_date"] == "2025-08-26"
    assert first["deed_to_county_date"] == "2028-01-15"
    assert first["stable_property_key"] == ("25-CV47055:787:1N1005AB01100")


def test_marion_notice_parser_deduplicates_recipients_at_property_level():
    records = oregon_tax.parse_marion_end_redemption_notices(
        _fixture("marion_redemption.txt")
    )

    assert [record["tax_account"] for record in records] == [
        "334529",
        "517007",
    ]
    first = records[0]
    assert first["published_notice_copy_count"] == 2
    assert first["map_tax_lot"] == "081W34DD00300"
    assert first["court_case_number"] == "24CV41709"
    assert first["amounts"]["total_due_as_published"] == 33190.41
    assert first["notice_date"] == "2026-01-09"
    assert first["judgment_date"] == "2025-01-13"
    assert first["redemption_expiration_date"] == "2027-01-13"


def test_multnomah_notice_parser_deduplicates_notice_copies():
    records = oregon_tax.parse_multnomah_redemption_notices(
        _fixture("multnomah_redemption.txt")
    )

    assert len(records) == 2
    record = next(item for item in records if item["real_property_id"] == "R264159")
    assert record["published_notice_copy_count"] == 2
    assert record["court_case_number"] == "24CV-33052"
    assert record["owner_as_shown_on_tax_roll"] == "AHN,YOUNG HO"
    assert record["judgment_date"] == "2024-11-14"
    assert record["redemption_expiration_date"] == "2026-11-16"


def test_multnomah_inventory_parser_preserves_post_deed_stage_and_amounts():
    records = oregon_tax.parse_multnomah_tax_title_inventory(
        _fixture("multnomah_inventory.txt")
    )

    assert len(records) == 3
    first = records[0]
    assert first["real_property_id"] == "R552734"
    assert first["map_id"] == "1N1E34CB -40135"
    assert first["property_received_date"] == "2026-01-29"
    assert first["amounts"] == {
        "total_decree": 3969.96,
        "market_value_as_of_received_date": 35000.0,
        "currency": "USD",
    }
    third = records[2]
    assert third["size_square_feet"] == 19
    assert "triangular shaped parcel" in (third["comments"] or "")


def test_clackamas_parser_handles_same_line_item_map_and_stage_specific_amount():
    results = oregon_tax.parse_clackamas_auction(
        _fixture("clackamas_results.txt"),
        stage=oregon_tax.AUCTION_RESULTS_STAGE,
    )
    offering = oregon_tax.parse_clackamas_auction(
        _fixture("clackamas_flyer.txt"),
        stage=oregon_tax.AUCTION_OFFERING_STAGE,
    )

    assert len(results) == len(offering) == 2
    assert results[0]["auction_item"] == 1
    assert results[0]["map_tax_lot"] == "27E32DD00700"
    assert results[0]["final_bid"] == 5300
    assert results[0]["auction_result"] == "sold"
    assert results[1]["map_tax_lot"] == "42E3602400"
    assert results[1]["auction_result"] == "no_bid"
    assert results[1]["final_bid"] is None
    assert offering[0]["deposit_amount"] == 853.35
    assert "final_bid" not in offering[0]


def test_inspection_versions_pdf_and_derived_text_together(tmp_path: Path):
    artifact = _blank_pdf(tmp_path / "tillamook.pdf")
    text_artifact = tmp_path / "tillamook.txt"
    text_artifact.write_text(_fixture("tillamook.txt"), encoding="utf-8")

    inspection = oregon_tax.inspect_artifact(
        artifact,
        source_id=oregon_tax.TILLAMOOK_SOURCE_ID,
        process_stage=oregon_tax.FORECLOSURE_LIST_STAGE,
        document_url="https://www.tillamookcounty.gov/list.pdf",
        publication_label="2025 Foreclosure List",
        text_artifact=text_artifact,
        text_method="llm_transcription",
    )

    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    text_sha = hashlib.sha256(text_artifact.read_bytes()).hexdigest()
    assert inspection["text_state"] == "searchable"
    assert inspection["record_count"] == 2
    assert inspection["artifact"]["sha256"] == artifact_sha
    representation = inspection["publication"]["text_representation"]
    assert representation == {
        "method": "llm_transcription",
        "text_sha256": text_sha,
        "text_artifact_path": str(text_artifact),
        "parent_artifact_sha256": artifact_sha,
    }
    assert all(
        record["artifact_sha256"] == artifact_sha for record in inspection["records"]
    )
    publication_document_id = inspection["publication"][
        "publication_document_id"
    ]
    assert publication_document_id == oregon_tax._document_id(
        oregon_tax.TILLAMOOK_SOURCE_ID,
        oregon_tax.FORECLOSURE_LIST_STAGE,
        "https://www.tillamookcounty.gov/list.pdf",
        "2025 Foreclosure List",
    )
    assert inspection["publication"]["artifact_page_count"] == 1
    assert {
        record["publication_document_id"] for record in inspection["records"]
    } == {publication_document_id}

    result = oregon_tax.search_inspection(
        inspection,
        _args(
            "search",
            "--source",
            oregon_tax.TILLAMOOK_SOURCE_ID,
            "--artifact",
            str(artifact),
            "--text-artifact",
            str(text_artifact),
        ),
    )
    parameters = result.query.query.parameters
    assert parameters["requested_process_stage"] is None
    assert parameters["resolved_process_stage"] == (
        oregon_tax.FORECLOSURE_LIST_STAGE
    )
    assert parameters["publication"]["publication_document_id"] == (
        publication_document_id
    )
    assert parameters["publication"]["text_representation"][
        "parent_artifact_sha256"
    ] == artifact_sha


def test_image_only_pdf_is_not_reported_as_an_authoritative_empty_list(
    tmp_path: Path,
):
    artifact = _blank_pdf(tmp_path / "marion-current-list.pdf")

    inspection = oregon_tax.inspect_artifact(
        artifact,
        source_id=oregon_tax.MARION_SOURCE_ID,
        process_stage=oregon_tax.FORECLOSURE_LIST_STAGE,
    )
    result = oregon_tax.search_inspection(
        inspection,
        _args(
            "search",
            "--source",
            oregon_tax.MARION_SOURCE_ID,
            "--artifact",
            str(artifact),
            "--process-stage",
            oregon_tax.FORECLOSURE_LIST_STAGE,
        ),
    )

    assert inspection["text_state"] == "derived_text_needed"
    assert inspection["record_count"] == 0
    assert result.status.value == "partial"
    assert result.errors[0].code == "derived_text_needed"


def test_search_filters_and_cursor_bind_to_artifact_and_criteria(
    tmp_path: Path,
):
    artifact = _blank_pdf(tmp_path / "tillamook.pdf")
    text_artifact = tmp_path / "tillamook.txt"
    text_artifact.write_text(_fixture("tillamook.txt"), encoding="utf-8")
    common = (
        "search",
        "--source",
        oregon_tax.TILLAMOOK_SOURCE_ID,
        "--artifact",
        str(artifact),
        "--process-stage",
        oregon_tax.FORECLOSURE_LIST_STAGE,
        "--text-artifact",
        str(text_artifact),
        "--text-method",
        "layout_text",
        "--max-records",
        "1",
    )

    first = oregon_tax.execute(_args(*common))

    assert first.status.value == "partial"
    assert [item["tax_account"] for item in first.records] == ["787"]
    assert first.next_cursor

    resumed = oregon_tax.execute(_args(*common, "--cursor", first.next_cursor))
    assert resumed.status.value == "ok"
    assert [item["tax_account"] for item in resumed.records] == ["13924"]
    assert resumed.next_cursor is None

    with pytest.raises(
        oregon_tax.PublicationQueryError,
        match="does not match",
    ):
        oregon_tax.execute(
            _args(
                *common,
                "--owner",
                "COOPER",
                "--cursor",
                first.next_cursor,
            )
        )

    changed_artifact = _blank_pdf(tmp_path / "tillamook-two-pages.pdf", page_count=2)
    changed = list(common)
    changed[changed.index(str(artifact))] = str(changed_artifact)
    with pytest.raises(
        oregon_tax.PublicationQueryError,
        match="does not match",
    ):
        oregon_tax.execute(_args(*changed, "--cursor", first.next_cursor))


def test_search_cli_logs_query_text_before_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _blank_pdf(tmp_path / "tillamook.pdf")
    text_artifact = tmp_path / "tillamook.txt"
    text_artifact.write_text(_fixture("tillamook.txt"), encoding="utf-8")
    captured: list[tuple[str, str, int | None]] = []
    monkeypatch.setattr(
        oregon_tax,
        "log_search",
        lambda query, source, count: captured.append((query, source, count)),
    )

    exit_code = oregon_tax.main(
        [
            "search",
            "--source",
            oregon_tax.TILLAMOOK_SOURCE_ID,
            "--artifact",
            str(artifact),
            "--process-stage",
            oregon_tax.FORECLOSURE_LIST_STAGE,
            "--text-artifact",
            str(text_artifact),
            "--owner",
            "COOPER",
            "--output",
            str(tmp_path / "results.json"),
        ]
    )

    assert exit_code == 0
    assert captured == [
        (
            '{"owner":"COOPER"}',
            "oregon_tax_foreclosures",
            1,
        )
    ]


def test_invalid_pdf_is_reported_as_source_change(tmp_path: Path):
    artifact = tmp_path / "not-a-pdf.pdf"
    artifact.write_text("<html>maintenance</html>", encoding="utf-8")

    with pytest.raises(
        oregon_tax.PublicationChanged,
        match="not a readable PDF",
    ):
        oregon_tax.inspect_artifact(
            artifact,
            source_id=oregon_tax.TILLAMOOK_SOURCE_ID,
        )


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_OR_TAX_FORECLOSURES") != "1",
    reason="set RUN_LIVE_OR_TAX_FORECLOSURES=1 for official live probes",
)
@pytest.mark.parametrize("source_id", sorted(oregon_tax.SOURCES))
def test_live_official_discovery_probe(source_id: str):
    result = oregon_tax.discover_source(
        oregon_tax.SOURCES[source_id],
        timeout=60,
    )

    assert result["landing_page_observations"]
    assert all(
        len(item["page_sha256"]) == 64 for item in result["landing_page_observations"]
    )
    if source_id != oregon_tax.CLACKAMAS_SOURCE_ID:
        assert result["publication_routes"]
