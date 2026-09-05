from __future__ import annotations

import argparse

import pytest

from tools import query_state_courts
from tools.public_records_contract import (
    JurisdictionMetadata,
    PublicRecordsQuery,
    PublicRecordsResult,
    QueryMetadata,
)


def _parse(*values: str) -> argparse.Namespace:
    return query_state_courts.build_parser().parse_args(list(values))


def _empty_bexar_envelope(
    operation: str = "search",
) -> dict[str, object]:
    query = PublicRecordsQuery(
        source=query_state_courts.query_bexar_courts.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="48029",
            name="Bexar County, Texas",
            state_code="TX",
            county_fips="48029",
        ),
        query=QueryMetadata(
            operation=operation,
            parameters={},
        ),
    )
    return PublicRecordsResult.success(query, []).to_dict()


class _BexarCatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Bexar County District Clerk Historical Cases",
                "official_url": (
                    "https://bexardistrict.tx.publicsearch.us/"
                ),
                "authority": "Bexar County District Clerk",
                "platform_family": "kofile_neumo_publicsearch_ws",
            },
            "roles": ["historical_case_index"],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed_with_limits",
        }


def test_bexar_router_translates_cursor_and_date_search_to_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _BexarCatalog(),
    )
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
    ]["search"]
    calls: list[tuple[argparse.Namespace, dict[str, object]]] = []

    def fake_execute(
        adapter_args: argparse.Namespace,
        *,
        access_decision: dict[str, object],
    ) -> dict[str, object]:
        calls.append((adapter_args, access_decision))
        return _empty_bexar_envelope()

    monkeypatch.setattr(route.adapter, "execute", fake_execute)

    payload = query_state_courts.execute(
        _parse(
            "search",
            "jury verdict",
            "--source",
            query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
            "--after",
            "1900-01-01",
            "--before",
            "1919-09-17",
            "--limit",
            "25",
            "--cursor",
            "kofile:offset:50",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args, decision = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.query == "jury verdict"
    assert adapter_args.ocr is True
    assert adapter_args.date_from == "1900-01-01"
    assert adapter_args.date_to == "1919-09-17"
    assert adapter_args.limit == 25
    assert adapter_args.offset == 50
    assert decision["allowed"] is True


def test_bexar_router_maps_documents_to_case_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _BexarCatalog(),
    )
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
    ]["documents"]
    captured: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            captured.append(adapter_args)
            or _empty_bexar_envelope("case")
        ),
    )

    query_state_courts.execute(
        _parse(
            "documents",
            "229791650",
            "--source",
            query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
        )
    )

    assert captured[0].command == "case"
    assert captured[0].doc_id == 229791650


def test_bexar_router_maps_page_download_without_hiding_page_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _BexarCatalog(),
    )
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
    ]["download"]
    captured: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            captured.append(adapter_args)
            or _empty_bexar_envelope("page")
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            "download",
            "229791650",
            "--page-number",
            "3",
            "--destination",
            "/tmp/bexar-page.png",
            "--source",
            query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
        )
    )

    assert captured[0].command == "page"
    assert captured[0].doc_id == 229791650
    assert captured[0].page_number == 3
    assert captured[0].destination == "/tmp/bexar-page.png"
    assert payload["status"] == "no_results"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            (
                "search",
                "SMITH",
                "--source",
                query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
                "--cursor",
                "offset:10",
            ),
            "kofile:offset:N",
        ),
        (
            (
                "search",
                "SMITH",
                "--source",
                query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
                "--after",
                "1900-01-01",
            ),
            "both --after and --before",
        ),
        (
            (
                "download",
                "229791650",
                "--source",
                query_state_courts.BEXAR_HISTORICAL_SOURCE_ID,
            ),
            "--page-number",
        ),
    ],
)
def test_bexar_router_rejects_unrepresentable_generic_selections(
    monkeypatch: pytest.MonkeyPatch,
    values: tuple[str, ...],
    message: str,
) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _BexarCatalog(),
    )
    with pytest.raises(ValueError, match=message):
        query_state_courts.execute(_parse(*values))


def test_bexar_source_guidance_exposes_unified_and_direct_capabilities() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.BEXAR_HISTORICAL_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == [
        "case",
        "documents",
        "download",
        "search",
    ]
    assert "query_bexar_courts.py" in guidance["direct_tool"]
