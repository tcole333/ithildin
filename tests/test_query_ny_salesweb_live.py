from __future__ import annotations

import os

import pytest

from tools import query_ny_salesweb as salesweb
from tools import query_ny_statewide_parcels as parcels


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_PUBLIC_RECORDS") != "1",
    reason="set RUN_LIVE_PUBLIC_RECORDS=1 for bounded live probes",
)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        salesweb,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def _client() -> salesweb.SalesWebClient:
    return salesweb.SalesWebClient(
        timeout=20,
        minimum_interval=0,
        retry_attempts=2,
    )


def test_live_probe_verifies_reference_search_detail_and_identity():
    args = salesweb.build_parser().parse_args(["probe", "--minimum-interval", "0"])

    result = salesweb.execute(args, client=_client())

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["reference_tables"]["counts"]["muniRef"] > 2_000
    assert record["reference_tables"]["counts"]["schlRef"] >= 700
    assert record["reference_tables"]["county_count"] >= 57
    assert record["bounded_search"]["reported_total_matches"] > 0
    assert record["bounded_search"]["returned_rows"] == 1
    assert record["detail"]["sale_transaction_identity_present"] is True
    assert record["detail"]["swis_print_key_join_present"] is True


def test_live_search_returns_distinct_sale_and_parcel_identity():
    args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--limit",
            "2",
            "--minimum-interval",
            "0",
        ]
    )

    result = salesweb.execute(args, client=_client())

    assert result.status.value == "ok"
    assert len(result.records) == 2
    for record in result.records:
        assert record["sale_record_id"]
        exact = record["property"]["parcel_join"]["exact_join_fields"]
        assert exact["SWIS_PRINT_KEY_ID"] == exact["SWIS"] + exact["PRINT_KEY"]
        assert (
            record["canonical_ref"]
            != record["property"]["parcel_join"]["canonical_ref"]
        )


def test_live_salesweb_key_joins_statewide_parcel_centroid():
    args = salesweb.build_parser().parse_args(
        [
            "search",
            "--municipality",
            "012000",
            "--limit",
            "1",
            "--minimum-interval",
            "0",
        ]
    )
    result = salesweb.execute(args, client=_client())
    join_key = result.records[0]["property"]["parcel_identifiers"]["swis_print_key_id"]
    parcel_client = parcels.NYParcelClient(
        parcels.COMPONENTS["centroids"],
        page_size=5,
        timeout=20,
        minimum_interval=0,
        retry_attempts=2,
    )

    matches = parcel_client.fetch_page(
        where=f"SWIS_PRINT_KEY_ID='{join_key}'",
        record_count=5,
        return_geometry=False,
        spatial_parameters={},
    )

    assert matches
    assert {match["attributes"]["SWIS_PRINT_KEY_ID"] for match in matches} == {join_key}


def test_live_official_csv_export_is_parseable_and_bounded(tmp_path):
    destination = tmp_path / "salesweb.csv"
    args = salesweb.build_parser().parse_args(
        [
            "export",
            "--municipality",
            "012000",
            "--limit",
            "2",
            "--csv-output",
            str(destination),
            "--minimum-interval",
            "0",
        ]
    )

    result = salesweb.execute(args, client=_client())

    assert result.status.value == "ok"
    record = result.records[0]
    assert record["csv_record_count"] == 2
    assert destination.stat().st_size > 500
    assert "swis_cd" in record["csv_headers"]
    assert "print_key" in record["csv_headers"]
