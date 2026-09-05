from __future__ import annotations

import copy
import json
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import pytest

from tools import query_broward_official_records as recorder


FIXTURE_DIR = Path(
    "tests/fixtures/public_records/broward_official_records"
)
GRID = json.loads((FIXTURE_DIR / "grid-name.json").read_text(encoding="utf-8"))
DETAIL_HTML = (FIXTURE_DIR / "detail.html").read_text(encoding="utf-8")


def _detail_payload() -> dict[str, Any]:
    exact_search = copy.deepcopy(GRID)
    exact_search["data"] = [
        row
        for row in exact_search["data"]
        if row["InstrumentNumber"] == "114957232"
    ][:1]
    exact_search.update(
        {
            "total": 1,
            "search_kind": "instrument",
            "exact_match_found": True,
            "search_window_total": 100,
            "search_window_first_instrument": "114957232",
            "search_window_last_instrument": "114957331",
        }
    )
    return {
        "found": True,
        "instrument_number": "114957232",
        "search": exact_search,
        "detail": {
            "source_url": (
                "https://officialrecords.broward.org/AcclaimWeb/Details/"
            ),
            "details_url": (
                "https://officialrecords.broward.org/AcclaimWeb/details/"
                "documentdetails/36534745/50/1/100"
            ),
            "details_html": DETAIL_HTML,
            "rendered": {
                "fields": {},
                "table_rows": [],
                "anchors": [
                    {
                        "text": "Property Appraiser",
                        "title": "",
                        "href": (
                            "https://web.bcpa.net/BcpaClient/#/Record-Search"
                        ),
                    },
                    {
                        "text": "Map",
                        "title": "",
                        "href": (
                            "https://gisweb-adapters.bcpa.net/bcpawebmap_ex/"
                            "bcpawebmap.aspx"
                        ),
                    },
                    {
                        "text": "Tax Collector",
                        "title": "",
                        "href": "https://broward.county-taxes.com/public/",
                    },
                ],
                "retrieval_token": "ephemeral-session-token",
            },
        },
        "image": {
            "available": True,
            "state": "public_pdf",
            "page_count": 3,
            "viewer_url": (
                "https://officialrecords.broward.org/AcclaimWeb/Image/"
                "DocumentImage1/ephemeral-session-token"
            ),
            "pdf_url": (
                "https://officialrecords.broward.org/AcclaimWeb/Image/"
                "DocumentPdfAllPages/ephemeral-pdf-token"
            ),
        },
    }


class FakeRunner:
    def __init__(
        self,
        *,
        grid: Mapping[str, Any] | None = None,
        detail: Mapping[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.grid = copy.deepcopy(grid or GRID)
        self.detail = copy.deepcopy(detail or _detail_payload())
        self.error = error
        self.calls: list[tuple[list[str], float]] = []

    def __call__(
        self,
        arguments: Sequence[str],
        timeout: float,
    ) -> Mapping[str, Any]:
        args = list(arguments)
        self.calls.append((args, timeout))
        if self.error is not None:
            raise self.error
        if args[0] in {"name", "parcel", "instrument"}:
            return copy.deepcopy(self.grid)
        if args[0] == "detail":
            return copy.deepcopy(self.detail)
        if args[0] == "download":
            return {
                "downloaded": True,
                "instrument_number": "114957232",
                "destination": "/tmp/114957232.pdf",
                "byte_count": 4321,
                "sha256": "a" * 64,
                "mime_type": "application/pdf",
                "page_count": 3,
                "source_url": recorder.SEARCH_URL,
            }
        if args[0] == "runtime-check":
            return {
                "ok": True,
                "node": "v20.0.0",
                "playwright_module": "playwright",
                "browser_channel": "chrome",
            }
        if args[0] == "probe":
            return {
                "ok": True,
                "source_url": recorder.SEARCH_URL,
                "coverage_statements": [
                    "All plats and maps, regardless of record date, are searchable."
                ],
            }
        raise AssertionError(f"unexpected helper operation: {args}")


def _parse(*values: str) -> Any:
    return recorder.build_parser().parse_args(list(values))


def _execute(
    args: Any,
    monkeypatch: Any,
    runner: FakeRunner | None = None,
):
    monkeypatch.setattr(recorder, "log_search", lambda *_args: None)
    return recorder.execute(args, helper_runner=runner or FakeRunner())


def test_grid_rows_group_by_instrument_without_using_party_row_as_identity():
    records = recorder.normalize_grid(GRID)

    assert len(records) == 2
    deed = next(
        record
        for record in records
        if record["instrument_number"] == "114957232"
    )
    assert deed["canonical_ref"] == (
        "PROPERTY:us-fl-broward-official-records/12011/"
        "instrument/114957232"
    )
    assert deed["native_document_id"] == "114957232"
    assert deed["recording_date"] == "2018-03-20"
    assert deed["consideration"] == 990000.0
    assert deed["parcel_ids"] == ["514223CB0580"]
    assert deed["legal_descriptions"] == [
        "DIPLOMAT OCEANFRONT RESIDENCES UNIT 1404"
    ]
    assert deed["source_query_observation_count"] == 2
    assert deed["source_locator"]["transaction_item_ids"] == [
        "36534745",
        "36534746",
    ]
    assert deed["source_locator"]["locator_role"] == "session_result_row"
    assert {
        (party["name"], party["role"])
        for party in deed["parties"]
    } == {
        ("EPSTEIN,JEFFREY M", "grantor"),
        ("SAKHUJA,SIMMI", "grantee"),
        ("EPSTEIN,JEFFREY M", "grantee"),
        ("SOUTH FLORIDA BANK", "grantor"),
    }


def test_grid_parser_does_not_treat_no_legal_marker_as_evidence():
    affidavit = next(
        record
        for record in recorder.normalize_grid(GRID)
        if record["instrument_number"] == "86249212"
    )

    assert affidavit["book"] == "13547"
    assert affidavit["page"] == "31"
    assert affidavit["legal_descriptions"] == []
    assert affidavit["parcel_ids"] == []


def test_detail_merges_exact_index_hit_fields_and_public_pdf_state():
    record = recorder.normalize_detail(_detail_payload())

    assert record is not None
    assert record["instrument_number"] == "114957232"
    assert record["document_type_code"] == "D"
    assert record["document_type"] == "Deed Transfers of Real Property"
    assert record["recording_date"] == "2018-03-20"
    assert record["page_count"] == 3
    assert record["consideration"] == 990000.0
    assert record["mortgage_assumption"] == 0.0
    assert record["parties"] == [
        {
            "name": "EPSTEIN,JEFFREY M",
            "role": "grantor",
            "native_role": "Grantor",
            "index_direction": "direct",
        },
        {
            "name": "SAKHUJA,SIMMI",
            "role": "grantee",
            "native_role": "Grantee",
            "index_direction": "reverse",
        },
    ]
    assert record["parcel_ids"] == ["514223CB0580"]
    assert record["image_access"]["status"] == "available_online"
    assert record["image_access"]["page_count"] == 3
    assert record["image_access"]["retrieval_url_ephemeral"] is True
    assert record["property_links"] == {
        "property_appraiser": (
            "https://web.bcpa.net/BcpaClient/#/Record-Search"
        ),
        "property_map": (
            "https://gisweb-adapters.bcpa.net/bcpawebmap_ex/"
            "bcpawebmap.aspx"
        ),
        "tax_collector": "https://broward.county-taxes.com/public/",
    }


def test_detail_rejects_a_mismatched_instrument():
    payload = _detail_payload()
    payload["detail"]["details_html"] = DETAIL_HTML.replace(
        "114957232",
        "114957233",
    )

    with pytest.raises(
        recorder.BrowardSourceChanged,
        match="does not match",
    ):
        recorder.normalize_detail(payload)


def test_name_execute_preserves_query_controls(monkeypatch):
    runner = FakeRunner()
    result = _execute(
        _parse(
            "name",
            "EPSTEIN, JEFFREY",
            "--direction",
            "grantor",
            "--from-date",
            "1977-01-01",
            "--to-date",
            "2026-07-30",
            "--max-pages",
            "4",
        ),
        monkeypatch,
        runner,
    )

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert runner.calls == [
        (
            [
                "name",
                "EPSTEIN, JEFFREY",
                "--direction",
                "grantor",
                "--max-pages",
                "4",
                "--from",
                "01/01/1977",
                "--to",
                "07/30/2026",
            ],
            300,
        )
    ]


def test_parcel_execute_exact_filters_source_configured_matches(monkeypatch):
    grid = copy.deepcopy(GRID)
    grid["data"].append(
        {
            **copy.deepcopy(grid["data"][0]),
            "InstrumentNumber": "114957999",
            "TransactionItemId": "36534999",
            "ParcelNumber": "514223CB058099",
        }
    )
    grid["total"] = len(grid["data"])
    runner = FakeRunner(grid=grid)

    result = _execute(
        _parse(
            "parcel",
            "5142-23-CB-0580",
            "--from-date",
            "1977-01-01",
            "--to-date",
            "2026-07-30",
            "--max-pages",
            "3",
        ),
        monkeypatch,
        runner,
    )

    assert result.status.value == "ok"
    assert {
        record["instrument_number"] for record in result.records
    } == {"114957232"}
    assert runner.calls == [
        (
            [
                "parcel",
                "5142-23-CB-0580",
                "--max-pages",
                "3",
                "--from",
                "01/01/1977",
                "--to",
                "07/30/2026",
            ],
            300,
        )
    ]
    assert result.query.query.parameters["exact_filter"] is True


def test_partial_grid_is_explicit_when_source_pages_remain(monkeypatch):
    grid = copy.deepcopy(GRID)
    grid.update({"total": 251, "truncated": True, "pages_retrieved": 2})

    result = _execute(
        _parse("name", "SMITH, JOHN", "--max-pages", "2"),
        monkeypatch,
        FakeRunner(grid=grid),
    )

    assert result.status.value == "partial"
    assert result.errors[0].code == "source_pages_remaining"
    assert result.errors[0].details["source_total_rows"] == 251
    assert len(result.records) == 2


def test_exact_instrument_empty_is_authoritative_no_results(monkeypatch):
    grid = copy.deepcopy(GRID)
    grid.update(
        {
            "data": [],
            "total": 0,
            "exact_match_found": False,
            "search_window_total": 100,
        }
    )

    result = _execute(
        _parse("instrument", "114957232"),
        monkeypatch,
        FakeRunner(grid=grid),
    )

    assert result.status.value == "no_results"
    assert not result.records


def test_download_receipt_uses_content_hash_as_artifact_identity(monkeypatch):
    result = _execute(
        _parse("download", "114957232", "/tmp/114957232.pdf"),
        monkeypatch,
    )

    record = result.records[0]
    assert record["canonical_ref"].endswith("/instrument/114957232")
    assert record["evidence_ref"] == f"BROWARD-OR-PDF:{'a' * 64}"
    assert record["mime_type"] == "application/pdf"
    assert record["page_count"] == 3
    assert result.raw_artifact_refs == ("/tmp/114957232.pdf",)


def test_browser_source_change_is_not_an_empty_result(monkeypatch):
    result = _execute(
        _parse("probe"),
        monkeypatch,
        FakeRunner(
            error=recorder.BrowardBrowserError(
                "grid contract changed",
                error_type="SourceChangedError",
            )
        ),
    )

    assert result.status.value == "source_changed"
    assert result.errors[0].category == "source_schema"


def test_bulk_release_joins_source_native_companion_rows():
    payload = recorder.parse_bulk_release(
        FIXTURE_DIR / "doc.txt",
        names_path=FIXTURE_DIR / "nme.txt",
        links_path=FIXTURE_DIR / "lnk.txt",
        legals_path=FIXTURE_DIR / "lgl.txt",
        range_path=FIXTURE_DIR / "rng.txt",
    )

    assert payload["instrument_range"] == {
        "begin_instrument": "119824010",
        "end_instrument": "119840339",
        "source_file": str(FIXTURE_DIR / "rng.txt"),
    }
    assert payload["orphan_rows"] == {}
    assert len(payload["records"]) == 4

    deed = next(
        record
        for record in payload["records"]
        if record["instrument_number"] == "119840338"
    )
    assert deed["document_type_code"] == "D"
    assert deed["document_type"] == "Deed Transfers of Real Property"
    assert deed["recording_date"] == "2024-10-09"
    assert deed["consideration"] == 75000.0
    assert deed["documentary_tax"] == 525.0
    assert deed["index_status"] == "verified_and_released"
    assert deed["access_state"] == "public"
    assert [party["role"] for party in deed["parties"]] == [
        "grantor",
        "grantor",
        "grantee",
    ]
    assert len(deed["legal_descriptions"]) == 2
    assert deed["parcel_ids"] == ["494126DD0410"]

    release = next(
        record
        for record in payload["records"]
        if record["instrument_number"] == "119831733"
    )
    link = release["linked_instruments"][0]
    assert link["prior_instrument_number"] == "114432744"
    assert link["prior_canonical_ref"].endswith(
        "/instrument/114432744"
    )
    assert link["keypunch"] == "O 114432744"

    sealed = next(
        record
        for record in payload["records"]
        if record["instrument_number"] == "119824010"
    )
    assert sealed["confidentiality"] == "sealed"
    assert sealed["access_state"] == "restricted"
    assert sealed["raw"]["document"]["case_number"] == "SEALED"


def test_bulk_layout_drift_is_explicit():
    with pytest.raises(
        recorder.BrowardSourceChanged,
        match="official layout defines 19",
    ):
        recorder.parse_bulk_release(FIXTURE_DIR / "bad-doc.txt")


def test_official_image_zip_joins_pages_without_extracting(tmp_path):
    archive_path = tmp_path / "10-09-2024img.ZIP"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("20241009/119840338.002.tif", b"page-two")
        archive.writestr("20241009/119840338.001.tif", b"page-one")
        archive.writestr("20241009/119840339.001.tif", b"mortgage")
        archive.writestr("20241009/readme.txt", b"not an image")

    payload = recorder.parse_bulk_release(
        FIXTURE_DIR / "doc.txt",
        images_path=archive_path,
    )

    deed = next(
        record
        for record in payload["records"]
        if record["instrument_number"] == "119840338"
    )
    assert deed["bulk_release_date"] is None
    assert deed["image_access"]["status"] == (
        "available_in_official_daily_zip"
    )
    assert deed["image_access"]["page_count"] == 2
    assert [
        member["page_number"]
        for member in deed["image_access"]["members"]
    ] == [1, 2]
    assert deed["image_access"]["members"][0]["native_artifact_id"] == (
        "BROWARD-OR:119840338:page:1"
    )
    assert len(deed["image_access"]["container_sha256"]) == 64
    assert payload["image_manifest"]["release_date"] == "2024-10-09"
    assert payload["image_manifest"]["unrecognized_members"] == [
        "20241009/readme.txt"
    ]


def test_bulk_orphan_rows_produce_partial_not_silent_drop(
    tmp_path,
    monkeypatch,
):
    names = tmp_path / "nme.txt"
    names.write_text(
        "999999999|ORPHAN,PARTY|D|1|\n",
        encoding="utf-8",
    )

    result = _execute(
        _parse(
            "bulk",
            str(FIXTURE_DIR / "doc.txt"),
            "--names",
            str(names),
        ),
        monkeypatch,
    )

    assert result.status.value == "partial"
    assert result.errors[0].code == "bulk_join_orphans"
    assert result.errors[0].details == {"NME": 1}
    assert len(result.records) == 4


def test_routes_assign_distinct_roles_and_join_keys(monkeypatch):
    result = _execute(_parse("routes"), monkeypatch)
    routes = result.records[0]

    assert routes["official_record_portal"]["coverage_statements"][
        "fully_searchable_other_records"
    ] == "from 1977-07-07 13:47 forward"
    assert routes["official_daily_release"]["rolling_availability"] == (
        "10 continuous days"
    )
    assert routes["official_daily_release"]["files"]["LNK"].startswith(
        "one record per source cross-reference"
    )
    complements = {
        item["kind"]: item for item in routes["complementary_routes"]
    }
    assert list(complements["broward_property_appraiser"]["join_keys"]) == [
        "parcel_id",
        "owner_name",
        "property_address",
    ]
    assert complements["broward_clerk_case_search"]["join_keys"][0] == (
        "case_number"
    )
    assert complements["broward_tax_deed"]["current_auction_url"] == (
        recorder.TAX_DEED_AUCTION_URL
    )
    assert complements["online_certified_copy_order"]["url"] == (
        recorder.ONLINE_ORDERS_URL
    )
    assert routes["official_record_portal"]["search_boundaries"][
        "property_address"
    ].startswith("use the Property Appraiser")


def test_runtime_and_probe_are_browser_backed_source_records(monkeypatch):
    runtime = _execute(_parse("runtime-check"), monkeypatch)
    probe = _execute(_parse("probe"), monkeypatch)

    assert runtime.records[0]["browser_channel"] == "chrome"
    assert probe.records[0]["record_kind"] == "source_probe"
    assert len(probe.records[0]["schema_fingerprint"]) == 64


def test_source_dates_accept_both_cli_formats_and_reject_other_formats():
    assert recorder._native_date("2026-07-30") == "07/30/2026"
    assert recorder._native_date("07/30/2026") == "07/30/2026"
    with pytest.raises(ValueError, match="dates must use"):
        recorder._native_date("30 July 2026")
