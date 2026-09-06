from __future__ import annotations

import os

import pytest

from tools import query_md_business_opinions as md
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> md.MarylandBusinessOpinionsClient:
    return md.MarylandBusinessOpinionsClient(
        minimum_interval=0.2,
        timeout=45,
    )


def test_live_archive_directory_exposes_all_closed_year_routes() -> None:
    client = _client()
    try:
        routes = client.fetch_archive_directory()
    finally:
        client.close()

    assert routes.archive_years == (2008, 2007, 2006, 2005, 2004, 2003)
    assert all(
        routes.archive_urls[year].endswith(f"opinions_archive{year}")
        for year in routes.archive_years
    )


def test_live_current_table_preserves_source_omissions_and_link_anomalies() -> None:
    client = _client()
    try:
        current = client.fetch_current()
    finally:
        client.close()

    assert current.native_count >= 90
    assert sum(len(record["documents"]) for record in current.records) >= 100
    assert any(record["source_omissions"] for record in current.records)
    anomaly_codes = {
        anomaly["code"]
        for record in current.records
        for anomaly in record["source_link_anomalies"]
    }
    assert "attachment_url_shared_by_source_rows" in anomaly_codes
    assert "attachment_designation_mismatch_at_source" in anomaly_codes


def test_live_2008_archive_retains_orders_and_legacy_formats() -> None:
    client = _client()
    try:
        routes = client.fetch_archive_directory()
        archive = client.fetch_archive_year(
            2008,
            source_url=routes.archive_urls[2008],
        )
    finally:
        client.close()

    assert archive.native_count == 6
    assert sum(len(record["documents"]) for record in archive.records) == 14
    assert any("order" in record["document_types"] for record in archive.records)
    assert {"pdf", "doc", "wpd"}.issubset(
        {
            document["file_format"]
            for record in archive.records
            for document in record["documents"]
        }
    )
    assert any("filed_date" in record["source_omissions"] for record in archive.records)


def test_live_all_page_search_parses_every_closed_archive() -> None:
    result = md.execute(
        md.build_parser().parse_args(
            [
                "search",
                "--all-pages",
                "--limit",
                "500",
                "--minimum-interval",
                "0.2",
            ]
        ),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    assert len(result.records) >= 160
    counts = {
        year: sum(record["publication_year"] == year for record in result.records)
        for year in range(2003, 2009)
    }
    assert counts == {
        2003: 11,
        2004: 15,
        2005: 11,
        2006: 16,
        2007: 6,
        2008: 6,
    }
    assert any(record["date_precision"] == "month" for record in result.records)


def test_live_probe_validates_current_archive_and_one_pdf() -> None:
    result = md.execute(
        md.build_parser().parse_args(["probe", "--minimum-interval", "0.2"]),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["current_publication_count"] >= 90
    assert probe["archive_sample_year"] == 2003
    assert probe["archive_sample_count"] == 11
    assert probe["pdf_size_bytes"] > 1_000
    assert probe["pdf_media_type"] == "application/pdf"
