from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tools import query_denver_delinquent_tax as denver_tax


pytestmark = [
    pytest.mark.live_data,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_DENVER_TAX") != "1",
        reason="set RUN_LIVE_DENVER_TAX=1 for the official live probe",
    ),
]


def test_denver_delinquent_tax_live_release_and_workbook_contract():
    client = denver_tax.DenverDelinquentTaxClient(
        minimum_interval=0.25,
    )
    release = client.discover()

    assert release.tax_year >= 2024
    assert urlsplit(release.url).hostname == "www.denvergov.org"
    assert release.url.endswith(".xlsx")

    probe = client.probe(release, sample_bytes=4096)
    assert probe["http_status"] == 200
    assert probe["signature_hex"].startswith("504b0304")
    assert probe["sample_sha256"]

    with tempfile.TemporaryDirectory(
        prefix="osint-denver-tax-live-",
        dir="/tmp",
    ) as workdir:
        payload = client.download_verified(
            release,
            Path(workdir) / release.filename,
            overwrite=False,
            max_bytes=32 * 1024 * 1024,
            archive_policy=denver_tax.ArchiveSafetyPolicy(
                max_members=denver_tax.DEFAULT_MAX_ARCHIVE_MEMBERS,
                max_total_uncompressed_bytes=(
                    denver_tax.DEFAULT_MAX_UNCOMPRESSED_BYTES
                ),
                max_member_uncompressed_bytes=(
                    denver_tax.DEFAULT_MAX_MEMBER_UNCOMPRESSED_BYTES
                ),
                max_compression_ratio=(
                    denver_tax.DEFAULT_MAX_COMPRESSION_RATIO
                ),
            ),
        )

    receipt = payload["artifact_receipt"]
    inspection = payload["workbook_inspection"]
    assert len(receipt["sha256"]) == 64
    assert receipt["size"] > 100_000
    assert inspection["schema"]["headers"] == list(
        denver_tax.EXPECTED_HEADERS
    )
    assert inspection["data_row_count"] > 1_000
    assert inspection["rows_by_tax_year"]
