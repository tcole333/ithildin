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


def _empty_vi_envelope(operation: str) -> dict[str, object]:
    query = PublicRecordsQuery(
        source=query_state_courts.query_vicourts.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="78",
            name="United States Virgin Islands",
            state_code="VI",
        ),
        query=QueryMetadata(operation=operation, parameters={}),
    )
    return PublicRecordsResult.success(query, []).to_dict()


def _vi_claim_envelope() -> dict[str, object]:
    query = PublicRecordsQuery(
        source=query_state_courts.query_vicourts.SOURCE_METADATA,
        jurisdiction=JurisdictionMetadata(
            jurisdiction_id="78",
            name="United States Virgin Islands",
            state_code="VI",
        ),
        query=QueryMetadata(
            operation="claims",
            parameters={"case_number": "ST-2019-PB-00080"},
        ),
    )
    return PublicRecordsResult.success(
        query,
        [
            {
                "source_id": query_state_courts.VICOURTS_SOURCE_ID,
                "record_kind": "case",
                "court": {
                    "court_id": "court-uuid",
                    "native_court_id": "1",
                    "name": "Superior Court of the Virgin Islands",
                    "state_code": "VI",
                    "level": "superior",
                },
                "raw_case_number": "ST-2019-PB-00080",
                "source_internal_id": "case-uuid",
                "caption": "Estate of Example",
                "access_state": "public",
                "claims": [
                    {
                        "source_namespace_id": "CTRACK_CLAIM:7",
                        "sequence_no": 7,
                        "claim_type": "General Claim",
                        "claim_date": "2020-01-02",
                        "limited_stub": True,
                    }
                ],
            }
        ],
    ).to_dict()


class _VICatalog:
    def show_source(self, source_id: str) -> dict[str, object]:
        assert source_id == query_state_courts.VICOURTS_SOURCE_ID
        return {
            "source": {
                "source_id": source_id,
                "name": "Virgin Islands Judiciary C-Track",
                "official_url": "https://usvipublicaccess.vicourts.org/",
                "authority": "Judicial Branch of the Virgin Islands",
                "platform_family": "ctrack_public_api_and_vicourts_legacy_files",
            },
            "roles": ["court_docket", "probate_claims"],
            "capabilities": [
                {"name": "search_parties", "supported": True},
                {"name": "search_cases", "supported": True},
                {"name": "list_docket_entries", "supported": True},
                {"name": "list_probate_claims", "supported": True},
                {"name": "fetch_document", "supported": True},
            ],
            "latest_access_review": {"access_class": "B"},
        }

    def machine_acquisition_decision(
        self,
        source_id: str,
    ) -> dict[str, object]:
        assert source_id == query_state_courts.VICOURTS_SOURCE_ID
        return {
            "source_id": source_id,
            "allowed": True,
            "access_class": "B",
            "reason": "review permits machine acquisition",
            "reason_code": "allowed_with_limits",
            "limits": {"maximum_page_size": 500},
        }


def _install_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        query_state_courts,
        "PublicRecordsCatalog",
        lambda _path: _VICatalog(),
    )


def test_vi_router_maps_party_search_and_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.VICOURTS_SOURCE_ID
    ]["search"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_vi_envelope("search")
        ),
    )

    payload = query_state_courts.execute(
        _parse(
            "search",
            "Estate of Example",
            "--source",
            query_state_courts.VICOURTS_SOURCE_ID,
            "--court-id",
            "supreme-court",
            "--limit",
            "25",
            "--max-records",
            "7",
            "--page-size",
            "125",
            "--cursor",
            "ctrack:offset:50",
        )
    )

    assert payload["status"] == "no_results"
    adapter_args = calls[0]
    assert adapter_args.command == "search"
    assert adapter_args.field == "party"
    assert adapter_args.match_mode == "match"
    assert adapter_args.court == "supreme-court"
    assert adapter_args.limit == 7
    assert adapter_args.page_size == 125
    assert adapter_args.cursor == "ctrack:offset:50"


@pytest.mark.parametrize("command", ["case", "docket", "claims"])
def test_vi_router_maps_case_scoped_operations(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.VICOURTS_SOURCE_ID
    ][command]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_vi_envelope(command)
        ),
    )

    query_state_courts.execute(
        _parse(
            command,
            "ST-2019-PB-00080",
            "--source",
            query_state_courts.VICOURTS_SOURCE_ID,
            "--court-id",
            "superior-court",
        )
    )

    assert calls[0].command == command
    assert calls[0].case_number == "ST-2019-PB-00080"
    assert calls[0].court == "superior-court"


def test_vi_claims_can_ingest_and_query_from_local_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.VICOURTS_SOURCE_ID
    ]["claims"]
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda *_args, **_kwargs: _vi_claim_envelope(),
    )
    db_path = tmp_path / "courts.db"

    live = query_state_courts.execute(
        _parse(
            "claims",
            "ST-2019-PB-00080",
            "--source",
            query_state_courts.VICOURTS_SOURCE_ID,
            "--court-db",
            str(db_path),
            "--ingest",
        )
    )
    local = query_state_courts.execute(
        _parse(
            "claims",
            "ST-2019-PB-00080",
            "--court-db",
            str(db_path),
        )
    )

    assert live["ingest"]["projected"]["claims"] == 1
    assert local["status"] == "ok"
    assert local["records"] == [
        {
            "canonical_ref": (
                "STATECOURT:us-vi-c-track/court-uuid/"
                "ST-2019-PB-00080/claim/CTRACK_CLAIM%3A7"
            ),
            "case": {
                "canonical_ref": (
                    "STATECOURT:us-vi-c-track/court-uuid/"
                    "ST-2019-PB-00080/case/case-uuid"
                ),
                "case_id": 1,
                "source_id": "us-vi-c-track",
                "source_internal_id": "case-uuid",
                "court": {
                    "court_id": "court-uuid",
                    "native_court_id": "1",
                    "name": "Superior Court of the Virgin Islands",
                    "state_code": "VI",
                    "county_geoid": None,
                    "level": "superior",
                    "division": None,
                    "official_url": None,
                },
                "raw_case_number": "ST-2019-PB-00080",
                "display_case_number": None,
                "caption": "Estate of Example",
                "case_type": None,
                "filing_date": None,
                "disposition_date": None,
                "status": None,
                "access_state": "public",
                "certified_record": False,
                "source_url": None,
            },
            "claim_id": 1,
            "native_claim_id": "CTRACK_CLAIM:7",
            "sequence": 7,
            "claim_type": "General Claim",
            "claim_date": "2020-01-02",
            "claimant_raw": None,
            "amount_minor": None,
            "currency": None,
            "status": None,
            "limited_stub": True,
            "access_state": "public",
            "native_access_state": None,
        }
    ]


def test_vi_router_preserves_docket_entry_document_selector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.VICOURTS_SOURCE_ID
    ]["documents"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_vi_envelope("documents")
        ),
    )

    query_state_courts.execute(
        _parse(
            "documents",
            "ST-2019-PB-00080",
            "--docket-entry-uuid",
            "docket-uuid",
            "--source",
            query_state_courts.VICOURTS_SOURCE_ID,
        )
    )

    assert calls[0].case_number == "ST-2019-PB-00080"
    assert calls[0].docket_entry_uuid == "docket-uuid"


def test_vi_router_maps_native_download_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_catalog(monkeypatch)
    route = query_state_courts.LIVE_ROUTES[
        query_state_courts.VICOURTS_SOURCE_ID
    ]["download"]
    calls: list[argparse.Namespace] = []
    monkeypatch.setattr(
        route.adapter,
        "execute",
        lambda adapter_args, **_kwargs: (
            calls.append(adapter_args)
            or _empty_vi_envelope("download")
        ),
    )

    query_state_courts.execute(
        _parse(
            "download",
            "document-uuid",
            "--case-uuid",
            "case-uuid",
            "--court-id",
            "court-uuid",
            "--destination",
            "/tmp/vi-document.pdf",
            "--source",
            query_state_courts.VICOURTS_SOURCE_ID,
        )
    )

    adapter_args = calls[0]
    assert adapter_args.command == "download"
    assert adapter_args.document_uuid == "document-uuid"
    assert adapter_args.case_uuid == "case-uuid"
    assert adapter_args.court == "court-uuid"
    assert adapter_args.destination == "/tmp/vi-document.pdf"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            (
                "search",
                "Estate",
                "--after",
                "2020-01-01",
                "--source",
                query_state_courts.VICOURTS_SOURCE_ID,
            ),
            "--after",
        ),
        (
            (
                "documents",
                "ST-2019-PB-00080",
                "--source",
                query_state_courts.VICOURTS_SOURCE_ID,
            ),
            "--docket-entry-uuid",
        ),
        (
            (
                "download",
                "document-uuid",
                "--court-id",
                "court-uuid",
                "--source",
                query_state_courts.VICOURTS_SOURCE_ID,
            ),
            "--case-uuid",
        ),
        (
            (
                "download",
                "document-uuid",
                "--case-uuid",
                "case-uuid",
                "--source",
                query_state_courts.VICOURTS_SOURCE_ID,
            ),
            "--court-id",
        ),
    ],
)
def test_vi_router_rejects_unrepresentable_selections(
    monkeypatch: pytest.MonkeyPatch,
    values: tuple[str, ...],
    message: str,
) -> None:
    _install_catalog(monkeypatch)
    with pytest.raises(ValueError, match=message):
        query_state_courts.execute(_parse(*values))


def test_vi_guidance_exposes_direct_only_source_features() -> None:
    guidance = query_state_courts._source_guidance(
        query_state_courts.VICOURTS_SOURCE_ID
    )

    assert guidance["mode"] == "unified_live"
    assert guidance["unified_operations"] == [
        "case",
        "claims",
        "docket",
        "documents",
        "download",
        "search",
    ]
    assert "query_vicourts.py" in guidance["direct_tool"]
    assert "OCR document search" in guidance["note"]
