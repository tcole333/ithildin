from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from tools import query_new_jersey_tax_court as tax_court


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "new_jersey_tax_court"
)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(
        tax_court,
        "log_search",
        lambda *_args, **_kwargs: None,
    )


def _snapshot() -> tax_court.ManifestSnapshot:
    return tax_court.parse_manifest_xml(
        (FIXTURE_DIR / "s3-list.xml").read_bytes()
    )


def _column_name(index: int) -> str:
    value = index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _xlsx(
    path: Path,
    *,
    sheet_name: str,
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
    extra_cell: str | None = None,
) -> Path:
    values = [*headers, *(value for row in rows for value in row)]
    if extra_cell is not None:
        values.append(extra_cell)
    shared: list[str] = []
    index: dict[str, int] = {}
    for value in values:
        if value not in index:
            index[value] = len(shared)
            shared.append(value)
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main" '
        f'count="{len(values)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{escape(value)}</t></si>" for value in shared)
        + "</sst>"
    )
    source_rows = [headers, *rows]
    row_xml: list[str] = []
    for row_number, row in enumerate(source_rows, 1):
        cells = [
            (
                f'<c r="{_column_name(column)}{row_number}" t="s">'
                f"<v>{index[value]}</v></c>"
            )
            for column, value in enumerate(row)
        ]
        if extra_cell is not None and row_number == 2:
            cells.append(
                f'<c r="I2" t="s"><v>{index[extra_cell]}</v></c>'
            )
        row_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    last_column = "I" if extra_cell is not None else "H"
    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main">'
        f'<dimension ref="A1:{last_column}{len(source_rows)}"/>'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/'
        'officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" '
        'r:id="rId1"/></sheets></workbook>'
    )
    relationships_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/'
        'package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            relationships_xml,
        )
        archive.writestr("xl/sharedStrings.xml", shared_xml)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)
    return path


DOCKETED_ROWS = [
    (
        "2026000001",
        "ALPHA & BETA HOLDINGS LLC V NEWARK CITY",
        "01/05/2026",
        "0100",
        "002.00",
        "",
        "2026",
        "Essex",
    ),
    (
        "2026000001",
        "ALPHA & BETA HOLDINGS LLC V NEWARK CITY",
        "01/05/2026",
        "101",
        "3",
        "U1",
        "2026",
        "Essex",
    ),
    (
        "2026000002",
        "BETA PROPERTIES V RIDGEFIELD",
        "02/01/2026",
        "500",
        "9",
        "",
        "2026",
        "Bergen",
    ),
    (
        "2026000002",
        "BETA PROPERTIES V RIDGEFIELD",
        "02/01/2026",
        "500",
        "9",
        "",
        "2026",
        "Bergen",
    ),
]
OPEN_ROWS = [
    DOCKETED_ROWS[0],
    (
        "2023006877",
        "244 CLINTON TERR. LLC V LYNDHURST",
        "04/28/2023",
        "10",
        "4",
        "",
        "2923",
        "Bergen",
    ),
    (
        "2018009730",
        "821 ELMORA CAPITAL GROUP V ELIZABETH CITY",
        "06/25/2018",
        "10",
        "1108",
        "",
        "2018",
        "Union",
    ),
]


def _workbooks(tmp_path: Path) -> dict[str, Path]:
    return {
        "docketed": _xlsx(
            tmp_path / "docketed.xlsx",
            sheet_name=tax_court.DATASET_SPECS["docketed"].sheet_name,
            headers=tax_court.DOCKETED_HEADERS,
            rows=DOCKETED_ROWS,
        ),
        "open": _xlsx(
            tmp_path / "open.xlsx",
            sheet_name=tax_court.DATASET_SPECS["open"].sheet_name,
            headers=tax_court.OPEN_HEADERS_WITH_ANOMALY,
            rows=OPEN_ROWS,
        ),
    }


def _local(
    snapshot: tax_court.ManifestSnapshot,
    dataset_id: str,
    path: Path,
) -> tax_court.LocalWorkbook:
    return tax_court._local_workbook_from_path(
        tax_court.DATASET_SPECS[dataset_id],
        snapshot.object_for(dataset_id, "xlsx"),
        path,
        manifest_fingerprint=snapshot.fingerprint,
    )


def test_manifest_selects_four_local_property_artifacts():
    snapshot = _snapshot()

    assert [item.key for item in snapshot.objects] == [
        "tax-reports/localtaxcases.pdf",
        "tax-reports/localtaxcases.xlsx",
        "tax-reports/localtaxcasesall.pdf",
        "tax-reports/localtaxcasesall.xlsx",
    ]
    assert snapshot.object_for("docketed", "xlsx").etag == (
        "b6a6f1bb5df03f08a34fe92ed0e5974d"
    )
    assert len(snapshot.fingerprint) == 64


def test_manifest_rejects_missing_expected_artifact():
    source = (FIXTURE_DIR / "s3-list.xml").read_text(encoding="utf-8")
    changed = source.replace(
        "<Key>tax-reports/localtaxcasesall.xlsx</Key>",
        "<Key>tax-reports/renamed.xlsx</Key>",
    )

    with pytest.raises(
        tax_court.ManifestContractError,
        match="omitted expected",
    ):
        tax_court.parse_manifest_xml(changed)


def test_manifest_cursor_is_snapshot_and_selector_bound():
    snapshot = _snapshot()
    first, cursor = tax_court.paginate_manifest(
        snapshot,
        snapshot.objects,
        limit=1,
        cursor=None,
    )

    assert first[0].key == "tax-reports/localtaxcases.pdf"
    assert cursor
    changed_object = copy.copy(snapshot.objects[0])
    changed = tax_court.ManifestSnapshot(
        objects=(
            tax_court.S3Object(
                key=changed_object.key,
                last_modified=changed_object.last_modified,
                etag="changed",
                size=changed_object.size,
            ),
            *snapshot.objects[1:],
        )
    )
    with pytest.raises(tax_court.CursorError, match="manifest changed"):
        tax_court.paginate_manifest(
            changed,
            changed.objects,
            limit=1,
            cursor=cursor,
        )
    with pytest.raises(tax_court.CursorError, match="selectors"):
        tax_court.paginate_manifest(
            snapshot,
            snapshot.objects[:2],
            limit=1,
            cursor=cursor,
        )


def test_open_workbook_records_observed_year_to_county_alias(tmp_path):
    path = _xlsx(
        tmp_path / "open.xlsx",
        sheet_name=tax_court.DATASET_SPECS["open"].sheet_name,
        headers=tax_court.OPEN_HEADERS_WITH_ANOMALY,
        rows=OPEN_ROWS,
    )

    descriptor = tax_court.describe_workbook(
        path,
        tax_court.DATASET_SPECS["open"],
    )

    assert descriptor.record_count == 3
    assert descriptor.raw_headers[-1] == "Year"
    assert descriptor.semantic_headers[-1] == "county"
    assert descriptor.header_aliases == {"Year": "county"}


def test_open_workbook_accepts_corrected_county_header(tmp_path):
    path = _xlsx(
        tmp_path / "open-corrected.xlsx",
        sheet_name=tax_court.DATASET_SPECS["open"].sheet_name,
        headers=tax_court.DOCKETED_HEADERS,
        rows=OPEN_ROWS,
    )

    descriptor = tax_court.describe_workbook(
        path,
        tax_court.DATASET_SPECS["open"],
    )

    assert descriptor.raw_headers[-1] == "County"
    assert descriptor.header_aliases == {}


def test_workbook_rejects_changed_header_and_extra_populated_column(tmp_path):
    changed_headers = (*tax_court.DOCKETED_HEADERS[:-1], "Municipality")
    changed = _xlsx(
        tmp_path / "changed.xlsx",
        sheet_name=tax_court.DATASET_SPECS["docketed"].sheet_name,
        headers=changed_headers,
        rows=DOCKETED_ROWS[:1],
    )
    with pytest.raises(
        tax_court.WorkbookContractError,
        match="headers",
    ):
        tax_court.describe_workbook(
            changed,
            tax_court.DATASET_SPECS["docketed"],
        )

    extra = _xlsx(
        tmp_path / "extra.xlsx",
        sheet_name=tax_court.DATASET_SPECS["docketed"].sheet_name,
        headers=tax_court.DOCKETED_HEADERS,
        rows=DOCKETED_ROWS[:1],
        extra_cell="unexpected",
    )
    with pytest.raises(
        tax_court.WorkbookContractError,
        match="unexpected populated",
    ):
        tax_court.describe_workbook(
            extra,
            tax_court.DATASET_SPECS["docketed"],
        )


def test_normalizer_preserves_case_parcel_and_artifact_coordinates(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    local = _local(snapshot, "docketed", paths["docketed"])
    position, row_number, values = next(tax_court.iter_workbook_rows(local))

    record = tax_court.normalize_row(
        values,
        local=local,
        position=position,
        row_number=row_number,
        include_raw_row=True,
    )

    assert record["case"]["docket_number_raw"] == "2026000001"
    assert record["case"]["docket_number"] == "000001-2026"
    assert record["case"]["entered_date"]["iso"] == "2026-01-05"
    assert record["property"] == {
        "county_name": "Essex",
        "county_fips": "34013",
        "block": "0100",
        "lot": "002.00",
        "unit": None,
        "assessment_year_raw": "2026",
        "assessment_year": 2026,
    }
    assert record["source_record"]["row_number"] == 2
    assert record["source_record"]["row_position"] == 0
    assert len(record["source_record"]["artifact_sha256"]) == 64
    assert record["source_record"]["raw_row"]["case_title"].startswith(
        "ALPHA & BETA"
    )


def test_case_identity_is_stable_while_duplicate_occurrences_are_distinct(
    tmp_path,
):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    local = _local(snapshot, "docketed", paths["docketed"])
    rows = list(tax_court.iter_workbook_rows(local))
    first = tax_court.normalize_row(
        rows[2][2],
        local=local,
        position=rows[2][0],
        row_number=rows[2][1],
    )
    duplicate = tax_court.normalize_row(
        rows[3][2],
        local=local,
        position=rows[3][0],
        row_number=rows[3][1],
    )

    assert first["case_canonical_ref"] == duplicate["case_canonical_ref"]
    assert first["source_record"]["row_sha256"] == (
        duplicate["source_record"]["row_sha256"]
    )
    assert first["source_occurrence_id"] != duplicate["source_occurrence_id"]
    assert first["canonical_ref"] != duplicate["canonical_ref"]


def test_omitted_limit_exhausts_both_snapshots_without_deduplication(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    args = tax_court.build_parser().parse_args(
        ["search", "--dataset", "both"]
    )

    result = tax_court.execute(
        args,
        manifest_snapshot=snapshot,
        workbook_paths=paths,
    )

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert len(result.records) == 7
    assert [record["dataset"]["id"] for record in result.records] == [
        "docketed",
        "docketed",
        "docketed",
        "docketed",
        "open",
        "open",
        "open",
    ]
    assert result.next_cursor is None


def test_filters_use_docket_county_parcel_year_and_entered_date(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    args = tax_court.build_parser().parse_args(
        [
            "search",
            "--dataset",
            "docketed",
            "--docket",
            "000001-2026",
            "--county",
            "Essex County",
            "--block",
            "100",
            "--lot",
            "2",
            "--assessment-year",
            "2026",
            "--entered-from",
            "2026-01-01",
            "--entered-to",
            "2026-01-31",
        ]
    )

    result = tax_court.execute(
        args,
        manifest_snapshot=snapshot,
        workbook_paths={"docketed": paths["docketed"]},
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["property"]["block"] == "0100"


def test_bounded_search_resumes_at_next_match_without_overlap(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    parser = tax_court.build_parser()
    first = tax_court.execute(
        parser.parse_args(
            [
                "search",
                " V ",
                "--field",
                "case-title",
                "--dataset",
                "both",
                "--limit",
                "3",
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths=paths,
    )

    assert len(first.records) == 3
    assert first.next_cursor
    second = tax_court.execute(
        parser.parse_args(
            [
                "search",
                " V ",
                "--field",
                "case-title",
                "--dataset",
                "both",
                "--limit",
                "3",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths=paths,
    )

    assert len(second.records) == 3
    assert second.next_cursor
    third = tax_court.execute(
        parser.parse_args(
            [
                "search",
                " V ",
                "--field",
                "case-title",
                "--dataset",
                "both",
                "--limit",
                "3",
                "--cursor",
                second.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths=paths,
    )

    all_ids = [
        record["source_occurrence_id"]
        for result in (first, second, third)
        for record in result.records
    ]
    assert len(all_ids) == 7
    assert len(set(all_ids)) == 7
    assert third.next_cursor is None


def test_search_cursor_rejects_changed_query_and_artifact(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    parser = tax_court.build_parser()
    first = tax_court.execute(
        parser.parse_args(
            [
                "search",
                "BETA",
                "--dataset",
                "docketed",
                "--limit",
                "1",
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths={"docketed": paths["docketed"]},
    )
    changed_query = tax_court.execute(
        parser.parse_args(
            [
                "search",
                "ALPHA",
                "--dataset",
                "docketed",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths={"docketed": paths["docketed"]},
    )

    assert changed_query.status.value == "source_changed"
    assert "selection fingerprint" in changed_query.errors[0].message

    changed_path = _xlsx(
        tmp_path / "docketed-changed.xlsx",
        sheet_name=tax_court.DATASET_SPECS["docketed"].sheet_name,
        headers=tax_court.DOCKETED_HEADERS,
        rows=[*DOCKETED_ROWS, OPEN_ROWS[-1]],
    )
    changed_artifact = tax_court.execute(
        parser.parse_args(
            [
                "search",
                "BETA",
                "--dataset",
                "docketed",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        workbook_paths={"docketed": changed_path},
    )

    assert changed_artifact.status.value == "source_changed"
    assert "artifact binding" in changed_artifact.errors[0].message


def test_validate_reports_duplicates_header_alias_and_live_style_anomaly(
    tmp_path,
):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    args = tax_court.build_parser().parse_args(
        ["validate", "--dataset", "both"]
    )

    result = tax_court.execute(
        args,
        manifest_snapshot=snapshot,
        workbook_paths=paths,
    )

    assert result.status.value == "ok"
    docketed, open_cases = result.records
    assert docketed["validation"]["records_traversed"] == 4
    assert docketed["validation"]["unique_dockets"] == 2
    assert docketed["validation"]["duplicate_docket_rows"] == 2
    assert docketed["validation"]["exact_duplicate_rows"] == 1
    assert open_cases["workbook"]["header_aliases"] == {"Year": "county"}
    assert open_cases["validation"][
        "normalization_issue_counts_by_field"
    ] == {"assessment_year": 1}


def test_no_results_is_authoritative_not_a_transport_failure(tmp_path):
    snapshot = _snapshot()
    paths = _workbooks(tmp_path)
    args = tax_court.build_parser().parse_args(
        ["search", "NO SUCH CASE", "--dataset", "open"]
    )

    result = tax_court.execute(
        args,
        manifest_snapshot=snapshot,
        workbook_paths={"open": paths["open"]},
    )

    assert result.status.value == "no_results"
    assert result.errors == ()


def test_manifest_execute_returns_shared_contract_and_cursor():
    snapshot = _snapshot()
    args = tax_court.build_parser().parse_args(
        ["manifest", "--dataset", "both", "--format", "all", "--limit", "2"]
    )

    result = tax_court.execute(args, manifest_snapshot=snapshot)

    assert result.status.value == "ok"
    assert len(result.records) == 2
    assert result.next_cursor
    assert result.records[0]["manifest_fingerprint"] == snapshot.fingerprint
    assert result.records[0]["access_state"]["current_reports"][
        "machine_enumerable"
    ] is True
    assert result.records[0]["access_state"]["historical_judgment_files"][
        "machine_enumerable"
    ] is False
    assert result.records[0]["join_guidance"][
        "missing_for_deterministic_njgin_sr1a_parcel_join"
    ] == ("municipality",)


def test_alternatives_cover_archives_similar_sources_and_join_fields():
    routes = {
        route["source_id"]: route
        for route in tax_court._alternative_routes()
    }

    assert "us-nj-tax-court-judgment-archives" in routes
    assert "us-nj-tax-court-current-object-versions" in routes
    assert "us-nj-govconnect-tax-notices" in routes
    assert "us-nj-tax-case-public-access" in routes
    assert "us-nj-tax-court-opinions" in routes
    assert "us-nj-property-tax-appeals" in routes
    assert "us-nj-county-tax-boards" in routes
    assert "us-nj-treasury-sr1a-sales" in routes
    assert routes["us-nj-tax-court-judgment-archives"][
        "verified_artifacts"
    ][0]["format"] == "xls"
    assert "block" in routes["us-nj-tax-case-public-access"]["join_fields"]


def test_source_manifest_record_is_stable_and_network_free():
    first = tax_court.source_manifest_record()
    second = tax_court.source_manifest_record()

    assert first == second
    assert first["schema_version"] == "public-record-source-family/1.0"
    assert first["family_id"] == tax_court.SOURCE_ID
    assert [item["dataset_id"] for item in first["datasets"]] == [
        "docketed",
        "open",
    ]
    assert first["operations"]["search"] == (
        "complete_or_cursor_bounded_xlsx_traversal"
    )
    assert first["access_state"]["current_key_versions"][
        "machine_enumerable"
    ] is True
    assert {
        route["source_id"] for route in first["complementary_routes"]
    } >= {
        "us-nj-tax-court-judgment-archives",
        "us-nj-tax-case-public-access",
    }


def test_execute_can_suppress_search_history_logging(monkeypatch):
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        tax_court,
        "log_search",
        lambda *args: calls.append(args),
    )
    args = tax_court.build_parser().parse_args(["alternatives"])

    result = tax_court.execute(args, log_results=False)

    assert result.status.value == "ok"
    assert calls == []


def test_search_parser_has_no_default_result_ceiling():
    args = tax_court.build_parser().parse_args(["search", "ACME"])

    assert args.limit is None
    assert args.dataset == "both"
