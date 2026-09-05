from __future__ import annotations

import os

import pytest

from tools import query_txgio_land_parcels as txgio
from tools.public_records_bulk import BulkArtifact, BulkTransferClient


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


def test_live_txgio_latest_collection_has_scoped_resources_and_zip_probe():
    client = txgio.TxGIODataHubClient(minimum_interval=0)
    releases = client.releases()
    assert releases

    latest = releases[0]
    resources = client.resources(latest["collection_id"])
    county_resources = [
        resource for resource in resources if resource["scope"] == "county"
    ]
    state_resources = [
        resource for resource in resources if resource["scope"] == "state"
    ]
    assert len(county_resources) == latest["county_count_declared"]
    assert len(state_resources) == 1
    assert len(resources) == len(county_resources) + len(state_resources)

    selected = min(county_resources, key=lambda resource: resource["expected_size"])
    artifact = BulkArtifact(
        artifact_id=selected["resource_id"],
        url=selected["url"],
        filename=selected["filename"],
        media_type="application/zip",
        archive_format="zip",
        expected_size=selected["expected_size"],
        metadata={
            "county_fips": selected["county_fips"],
            "county_name": selected["county_name"],
        },
    )
    probe = BulkTransferClient(
        user_agent=txgio.DOWNLOAD_USER_AGENT,
    ).probe(artifact, sample_bytes=64)

    assert probe.http_status in {200, 206}
    assert probe.content_length == selected["expected_size"]
    assert probe.format_hint == "zip"
