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


def _empty_pima_envelope(operation: str) -> dict[str, object]:
    query = PublicRecordsQuery(
        source=query_state_courts.query_pima_courts.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="04019",
            name="Pima County, Arizona",
            state_code="AZ",
            county_fips="04019",
        ),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, []).to_dict()


class _PimaCatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == query_state_courts.PIMA_SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Pima County Superior Court Agave Public Record Search",
                "official_url": (
                    "https://www.cosc.pima.gov/services/case-records/"
                ),
                "authority": "Pima County Clerk of the Superior Court",
                "platform_family": "pima_agave_aspnet_publicdocs",
            },
            "roles": ["superior_court_case_metadata", "docket_entries"],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == query_state_courts.PIMA_SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed",
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _PimaCatalog(),
    )


def test_pima_router_maps_party_search_and_caller_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PIMA_SOURCE_ID
    ]["search"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_pima_envelope("search")
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "MALLETT",
            "--source",
            query_state_courts.PIMA_SOURCE_ID,
            "--limit",
            "25",
            "--max-records",
            "7",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.last_name == "MALLETT"
    assert adapter_args.first_name is None
    assert adapter_args.limit == 7


@pytest.mark.parametrize("command", ["case", "docket", "documents"])
def test_pima_router_maps_case_scoped_operations(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PIMA_SOURCE_ID
    ][command]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_pima_envelope("case")
        ),
    )

    query_state_courts.execute(
        _parse(
            command,
            "C20256501",
            "--source",
            query_state_courts.PIMA_SOURCE_ID,
        )
    )

    assert calls[0].command == "case"
    assert calls[0].case_number == "C20256501"


def test_pima_router_maps_public_document_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.PIMA_SOURCE_ID
    ]["download"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_pima_envelope("document")
        ),
    )
    destination = tmp_path / "filing.pdf"

    query_state_courts.execute(
        _parse(
            "download",
            "pima:document-row:abc",
            "--case-number",
            "C20256501",
            "--destination",
            str(destination),
            "--source",
            query_state_courts.PIMA_SOURCE_ID,
        )
    )

    adapter_args = calls[0]
    assert adapter_args.command == "document"
    assert adapter_args.case_number == "C20256501"
    assert adapter_args.entry_id == "pima:document-row:abc"
    assert adapter_args.destination == str(destination)


def test_pima_source_guidance_lists_unified_and_fallback_surfaces() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.PIMA_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == [
        "case",
        "docket",
        "documents",
        "download",
        "search",
    ]
    assert "query_pima_courts.py" in guidance["direct_tool"]
    assert "known-party fallback" in guidance["note"]
