from __future__ import annotations

import os
from datetime import date

import pytest

from tools import query_md_opinions as md
from tools.public_records_contract import ResultStatus


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def _client() -> md.MarylandOpinionsClient:
    return md.MarylandOpinionsClient(
        minimum_interval=0.1,
        timeout=45,
    )


def test_live_route_discovery_exposes_both_official_collections() -> None:
    client = _client()
    try:
        reported = client.fetch_reported_landing()
        unreported = client.fetch_unreported_directory()
    finally:
        client.close()

    assert reported.years[0] == date.today().year
    assert reported.years[-1] == 1995
    assert {"both", "coa", "cosa"}.issubset(reported.native_courts)
    assert len(unreported.months) > 250
    assert unreported.months == tuple(sorted(unreported.months, reverse=True))


def test_live_current_reported_index_has_sequential_linked_records() -> None:
    client = _client()
    try:
        index = client.fetch_reported(
            native_court="both",
            year=str(date.today().year),
            native_order="bydate",
        )
    finally:
        client.close()

    assert index.native_count > 25
    assert all(record["pdf_url"] for record in index.records)
    assert {record["court"]["court_key"] for record in index.records}.issubset(
        {"supreme", "appellate"}
    )
    assert [
        record["provenance"]["native_line_number"] for record in index.records
    ] == list(range(1, index.native_count + 1))


def test_live_latest_unreported_month_preserves_pdf_identity() -> None:
    client = _client()
    try:
        directory = client.fetch_unreported_directory()
        index = client.fetch_unreported_month(directory.months[0])
    finally:
        client.close()

    assert index.records
    assert all(
        record["source_month"].replace("-", "") == directory.months[0]
        for record in index.records
    )
    linked = [record for record in index.records if record["pdf_url"]]
    assert linked
    assert all(
        record["native_document_id"].startswith("unreported-opinions/")
        for record in linked
    )


def test_live_probe_validates_indexes_and_pdf_in_one_envelope() -> None:
    result = md.execute(
        md.build_parser().parse_args(["probe", "--minimum-interval", "0.1"]),
        log_results=False,
    )

    assert result.status is ResultStatus.OK
    probe = result.records[0]
    assert probe["reported_sample_count"] > 0
    assert probe["unreported_sample_count"] > 0
    assert probe["pdf_size_bytes"] > 1_000
    assert probe["pdf_media_type"] == "application/pdf"
