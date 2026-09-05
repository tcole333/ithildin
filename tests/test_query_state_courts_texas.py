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


def _empty_tames_envelope(operation: str) -> PublicRecordsResult:
    query = PublicRecordsQuery(
        source=query_state_courts.query_texas_appellate.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="48",
            name="Texas",
            state_code="TX",
        ),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, [])


class _TexasCatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == query_state_courts.TEXAS_TAMES_SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Texas Judicial Branch TAMES Appellate Case Search",
                "official_url": (
                    "https://search.txcourts.gov/CaseSearch.aspx?coa=cossup"
                ),
                "authority": "Texas Judicial Branch",
                "platform_family": "tames_webforms",
            },
            "roles": [
                "appellate_case_index",
                "docket_entries",
                "public_documents",
            ],
            "capabilities": [
                {"name": "search_cases", "supported": True},
                {"name": "fetch_case", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_documents", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == query_state_courts.TEXAS_TAMES_SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed",
            "limits": {
                "source_result_ceiling": 1000,
                "minimum_interval_seconds": 0.25,
            },
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _TexasCatalog(),
    )


def test_texas_router_maps_search_filters_and_caller_paging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.TEXAS_TAMES_SOURCE_ID
    ]["search"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_tames_envelope("search")
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "D-1-GN-24-008508",
            "--source",
            query_state_courts.TEXAS_TAMES_SOURCE_ID,
            "--search-scope",
            "trial-case-number",
            "--court-id",
            "tx-appellate-coa03",
            "--after",
            "2025-01-01",
            "--before",
            "2025-12-31",
            "--case-type",
            "civil",
            "--county",
            "Travis",
            "--trial-court",
            "250th District Court",
            "--originating-coa",
            "Third Court of Appeals",
            "--exclude-inactive",
            "--limit",
            "30",
            "--max-records",
            "7",
            "--cursor",
            "tx-tames:v1:page:2:offset:5:8cf35c52bb0c",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.scope == "trial-case-number"
    assert adapter_args.courts == ["coa03"]
    assert adapter_args.date_from == "2025-01-01"
    assert adapter_args.date_to == "2025-12-31"
    assert adapter_args.case_type == "civil"
    assert adapter_args.county == "Travis"
    assert adapter_args.trial_court == "250th District Court"
    assert adapter_args.originating_coa == "Third Court of Appeals"
    assert adapter_args.exclude_inactive is True
    assert adapter_args.limit == 7
    assert adapter_args.cursor.startswith("tx-tames:v1:")


@pytest.mark.parametrize("command", ["case", "docket", "documents"])
def test_texas_router_maps_case_scoped_operations(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.TEXAS_TAMES_SOURCE_ID
    ][command]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_tames_envelope(command)
        ),
    )

    query_state_courts.execute(
        _parse(
            command,
            "03-25-00287-CV",
            "--source",
            query_state_courts.TEXAS_TAMES_SOURCE_ID,
            "--court-id",
            "coa03",
        )
    )

    assert calls[0].command == command
    assert calls[0].case_number == "03-25-00287-CV"
    assert calls[0].court_code == "coa03"


def test_texas_router_maps_public_pdf_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.TEXAS_TAMES_SOURCE_ID
    ]["download"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_tames_envelope("download")
        ),
    )
    destination = tmp_path / "filing.pdf"

    query_state_courts.execute(
        _parse(
            "download",
            "bc16a831-998e-449f-9d28-84b61486178b",
            "--case-number",
            "03-25-00287-CV",
            "--court-id",
            "tx-appellate-coa03",
            "--destination",
            str(destination),
            "--source",
            query_state_courts.TEXAS_TAMES_SOURCE_ID,
        )
    )

    adapter_args = calls[0]
    assert adapter_args.command == "download"
    assert adapter_args.case_number == "03-25-00287-CV"
    assert adapter_args.document_id == (
        "bc16a831-998e-449f-9d28-84b61486178b"
    )
    assert adapter_args.destination == destination
    assert adapter_args.court_code == "coa03"


def test_texas_source_guidance_lists_unified_and_direct_surfaces() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.TEXAS_TAMES_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == [
        "case",
        "docket",
        "documents",
        "download",
        "search",
    ]
    assert "query_texas_appellate.py" in guidance["direct_tool"]
    assert "trial-case selectors" in guidance["note"]
