from __future__ import annotations

import argparse

import pytest

from tools import query_property
from tools.public_records_contract import (
    PublicRecordsError,
    PublicRecordsResult,
    ResultStatus,
)


def _shared_args(*argv: str) -> argparse.Namespace:
    return query_property.build_parser().parse_args(list(argv))


def test_family_and_leaf_routes_preserve_county_and_operation_semantics() -> None:
    umbrella = query_property.WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID
    adams = query_property.query_washington_taxsifter.TENANTS_BY_KEY["adams"]

    parcel_args = _shared_args(
        "parcel",
        "2038010000001",
        "--source",
        umbrella,
        "--county",
        "Adams County",
    )
    translated = query_property._washington_taxsifter_args(
        parcel_args,
        "detail",
    )

    assert translated.command == "detail"
    assert translated.query == "2038010000001"
    assert translated.source == adams.source_id
    assert translated.operations == "assessor,treasurer,appraisal"

    leaf_args = _shared_args(
        "account",
        "2038010000001",
        "--source",
        adams.source_id,
        "--jurisdiction",
        "53001",
    )
    leaf_translated = query_property._washington_taxsifter_args(
        leaf_args,
        "detail",
    )
    assert leaf_translated.source == adams.source_id

    with pytest.raises(ValueError, match="serves Adams County"):
        query_property._washington_taxsifter_args(
            _shared_args(
                "parcel",
                "2038010000001",
                "--source",
                adams.source_id,
                "--county",
                "Douglas",
            ),
            "detail",
        )
    with pytest.raises(ValueError, match="requires a county"):
        query_property._washington_taxsifter_args(
            _shared_args(
                "parcel",
                "2038010000001",
                "--source",
                umbrella,
            ),
            "detail",
        )


def test_general_search_and_sales_keep_native_limit_and_pagination_contracts() -> None:
    source_id = (
        query_property.query_washington_taxsifter.TENANTS_BY_KEY["adams"].source_id
    )
    owner = query_property._washington_taxsifter_args(
        _shared_args("owner", "HERCULES", "--source", source_id),
        "search",
    )
    assert owner.command == "search"
    assert owner.query == "HERCULES"
    assert owner.limit is None

    limited = query_property._washington_taxsifter_args(
        _shared_args(
            "address",
            "N BAKER AVE",
            "--source",
            source_id,
            "--limit",
            "7",
        ),
        "search",
    )
    assert limited.limit == 7

    sale = query_property._washington_taxsifter_args(
        _shared_args("sale", "2038010000001", "--source", source_id),
        "sales",
    )
    assert sale.parcel == "2038010000001"
    assert sale.limit is None

    routes = query_property.LIVE_ROUTES[source_id]
    assert set(routes) == {
        "account",
        "address",
        "discovery",
        "owner",
        "parcel",
        "probe",
        "sale",
        "search",
    }
    assert "instrument" not in routes
    assert "map" not in routes

    with pytest.raises(ValueError, match="cannot honor"):
        query_property._washington_taxsifter_args(
            _shared_args(
                "sale",
                "2038010000001",
                "--source",
                source_id,
                "--search-field",
                "owner",
            ),
            "sales",
        )


def test_mason_challenge_adds_distinct_official_alternatives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = query_property.query_washington_taxsifter
    mason = adapter.TENANTS_BY_KEY["mason"]
    challenge = PublicRecordsResult.failure(
        adapter._build_query(
            mason,
            operation="search",
            parameters={"criteria": "EXAMPLE"},
            requested_limit=None,
            cursor=None,
        ),
        ResultStatus.HUMAN_REQUIRED,
        [
            PublicRecordsError(
                code="source_challenge_required",
                message="interactive challenge",
                category="source_access",
                retryable=False,
                details={"response_state": "challenge"},
            )
        ],
    )
    monkeypatch.setattr(adapter, "execute", lambda args: challenge)

    result = query_property.WASHINGTON_TAXSIFTER_ADAPTER.execute(
        argparse.Namespace(source=mason.source_id)
    )

    alternatives = result.errors[0].details["official_alternatives"]
    by_kind = {item["kind"]: item for item in alternatives}
    assert by_kind["mason_county_tax_parcels_gis"]["lineage_id"] == (
        adapter.MAP_LINEAGE
    )
    assert "tax" not in by_kind["mason_county_tax_parcels_gis"]["operations"]
    assert by_kind["mason_county_auditor_eagleweb"]["lineage_id"] == (
        adapter.RECORDER_LINEAGE
    )
    assert by_kind["washington_digital_archives_recorded_land_title"][
        "title_id"
    ] == 56
    assert all(
        item.get("lineage_id") != adapter.TREASURER_LINEAGE
        for item in alternatives
    )


def test_metadata_discovery_routes_to_selected_leaf() -> None:
    umbrella = query_property.WASHINGTON_TAXSIFTER_UMBRELLA_SOURCE_ID
    translated = query_property._washington_taxsifter_args(
        _shared_args(
            "discovery",
            "--source",
            umbrella,
            "--county-fips",
            "047",
        ),
        "metadata",
    )
    assert translated.command == "metadata"
    assert translated.source == "us-wa-okanogan-county-taxsifter"
