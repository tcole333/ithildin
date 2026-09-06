from __future__ import annotations

from pathlib import Path

import pytest

from tools import query_md_business_opinions
from tools import query_ny_statewide_parcels
from tools import query_property
from tools import query_state_courts
from tools.public_records_catalog import PublicRecordsCatalog


def test_property_router_bootstraps_a_tracked_source_into_a_stale_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "stale-property-catalog.db"
    sentinel = object()
    calls: list[object] = []

    def fake_execute(adapter_args):
        calls.append(adapter_args)
        return sentinel

    monkeypatch.setattr(
        query_ny_statewide_parcels,
        "execute",
        fake_execute,
    )
    args = query_property.build_parser().parse_args(
        [
            "owner",
            "EXAMPLE LLC",
            "--source",
            query_ny_statewide_parcels.SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--limit",
            "1",
        ]
    )

    result, invoked = query_property._live_result(args)

    assert result is sentinel
    assert invoked is True
    assert len(calls) == 1
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.machine_acquisition_decision(query_ny_statewide_parcels.SOURCE_ID)[
            "allowed"
        ]
        is True
    )
    detail = catalog.show_source(query_ny_statewide_parcels.SOURCE_ID)
    assert detail["source"]["source_status"] == "active"


def test_court_router_bootstraps_a_tracked_source_into_a_stale_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "stale-court-catalog.db"
    sentinel = object()
    calls: list[object] = []

    def fake_execute(adapter_args):
        calls.append(adapter_args)
        return sentinel

    monkeypatch.setattr(
        query_md_business_opinions,
        "execute",
        fake_execute,
    )
    args = query_state_courts.build_parser().parse_args(
        [
            "search",
            "LOCKHEED MARTIN",
            "--source",
            query_md_business_opinions.SOURCE_ID,
            "--catalog-db",
            str(catalog_path),
            "--limit",
            "1",
        ]
    )

    result, invoked = query_state_courts._live_result(args)

    assert result is sentinel
    assert invoked is True
    assert len(calls) == 1
    catalog = PublicRecordsCatalog(catalog_path)
    assert (
        catalog.machine_acquisition_decision(query_md_business_opinions.SOURCE_ID)[
            "allowed"
        ]
        is True
    )
    detail = catalog.show_source(query_md_business_opinions.SOURCE_ID)
    assert detail["source"]["source_status"] == "active"
