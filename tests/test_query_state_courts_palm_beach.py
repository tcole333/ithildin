from __future__ import annotations

import argparse
from pathlib import Path

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


def _empty_palm_beach_envelope(operation: str) -> dict[str, object]:
    query = PublicRecordsQuery(
        source=query_state_courts.query_palm_beach_courts.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="12099",
            name="Palm Beach County, Florida",
            state_code="FL",
            county_fips="12099",
        ),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, []).to_dict()


class _PalmBeachCatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == query_state_courts.PALM_BEACH_SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Palm Beach County Clerk eCaseView",
                "official_url": (
                    "https://appsgp.mypalmbeachclerk.com/ecaseview"
                ),
                "authority": "Palm Beach County Clerk",
                "platform_family": "palm_beach_ecaseview_browser",
            },
            "roles": ["party_index", "docket_entries", "public_documents"],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "C"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == query_state_courts.PALM_BEACH_SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "C",
            "reason": "review permits the browser-session adapter",
            "reason_code": "allowed",
            "limits": {"source_search_result_ceiling": 200},
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _PalmBeachCatalog(),
    )


def test_palm_beach_router_maps_exact_party_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PALM_BEACH_SOURCE_ID
    ]["search"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_palm_beach_envelope("search")
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "KRAFT",
            "--source",
            query_state_courts.PALM_BEACH_SOURCE_ID,
            "--limit",
            "25",
            "--max-records",
            "7",
            "--cursor",
            "pbc:search:offset:3",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.query == "KRAFT"
    assert adapter_args.search_scope == "party"
    assert adapter_args.match_mode == "exact"
    assert adapter_args.limit == 7
    assert adapter_args.cursor == "pbc:search:offset:3"


@pytest.mark.parametrize("command", ["case", "docket", "documents"])
def test_palm_beach_router_maps_case_scoped_operations(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PALM_BEACH_SOURCE_ID
    ][command]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_palm_beach_envelope(command)
        ),
    )

    query_state_courts.execute(
        _parse(
            command,
            "50-2019-MM-002346-AXXX-NB",
            "--source",
            query_state_courts.PALM_BEACH_SOURCE_ID,
            "--limit",
            "100",
        )
    )

    assert calls[0].command == command
    assert calls[0].case_number == "50-2019-MM-002346-AXXX-NB"
    if command != "case":
        assert calls[0].limit == 100


def test_palm_beach_router_maps_din_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PALM_BEACH_SOURCE_ID
    ]["download"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_palm_beach_envelope("download")
        ),
    )
    destination = tmp_path / "din-5.pdf"

    query_state_courts.execute(
        _parse(
            "download",
            "5",
            "--case-number",
            "50-2019-MM-002346-AXXX-NB",
            "--destination",
            str(destination),
            "--source",
            query_state_courts.PALM_BEACH_SOURCE_ID,
        )
    )

    adapter_args = calls[0]
    assert adapter_args.command == "download"
    assert adapter_args.case_number == "50-2019-MM-002346-AXXX-NB"
    assert adapter_args.din == "5"
    assert adapter_args.destination == destination


def test_palm_beach_source_guidance_exposes_browser_and_direct_surfaces() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.PALM_BEACH_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == [
        "case",
        "docket",
        "documents",
        "download",
        "search",
    ]
    assert "query_palm_beach_courts.py" in guidance["direct_tool"]
    assert "headed Playwright/Chrome" in guidance["note"]
