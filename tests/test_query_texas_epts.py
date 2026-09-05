from __future__ import annotations

import base64
import csv
import json
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from tools import query_texas_epts as epts


def representative_values(**overrides: object) -> list[object]:
    values: dict[str, object] = {header: "" for header in epts.EXPECTED_HEADERS}
    values.update(
        {
            "CAD_ID": "101",
            "TU_ID": "101901",
            "PROP_CATG_CD": "A",
            "PROP_SHT_ID": "SHORT-1",
            "PROP_ID1_TX": "ACCOUNT-0001",
            "PROP_ID2_TX": "LOT 1 BLOCK 2 EXAMPLE ADDITION",
            "PRCL_AD_TX": "100 MAIN ST",
            "SALE_DT": "09/15/2025",
            "PROP_SALE_AM": "147500",
            "DEED_DT": "09/12/2025",
            "DEED_VOL_NR": "123",
            "DEED_PAGE_NR": "456",
            "DEED_NR": "2025-009876",
            "DEED_TY_CD": "WD",
            "MULT_ACCT_CD": "Y",
            "ADDNL_PROPS": "ACCOUNT-0002",
            "GNTE_FRST_NM": "ALICE",
            "GNTE_LST_BUS_NM": "BUYER",
            "GNTE_LINE_1_AD_TX": "200 BUYER AVE",
            "GNTE_LINE_2_AD_TX": "UNIT 3",
            "GNTE_CITY_NM": "AUSTIN",
            "GNTE_ST_CD": "TX",
            "GNTE_AD_ZP": "787011234",
            "GNTR_FRST_NM": "BOB",
            "GNTR_LST_BUS_NM": "SELLER",
            "GNTR_LINE_1_AD_TX": "300 SELLER RD",
            "GNTR_LINE_2_AD_TX": "",
            "GNTR_CITY_NM": "AUSTIN",
            "GNTR_ST_CD": "TX",
            "GNTR_AD_ZP": "78702",
            "CAD_SALE_SRC_CD": "APP",
            "VALD_CD": "Y",
            "CNFD_CD": "Q",
            "FRZN_CHAR_CD": "N",
            "CERT_VAL_YR": "2025",
            "ARB_VAL_CD": "N",
            "PROP_RPTD_LAND_AM": "50000",
            "PROP_RPTD_IMPV_AM": "90000",
            "PROP_RPTD_PPROP_AM": "0",
            "PROP_RPTD_TOTL_AM": "140000",
            "PCT_OWNSHP": ".500000",
            "PCT_COMP": "99.50",
            "SQFT_IMPV_QY": "1750",
            "BUILT_YR": "1999",
            "LAND_UNIT_TY_CD": "SF",
            "LAND_UNIT_QY": "7500.0000",
            "FNC_CD": "CASH",
            "DY_ON_MRKT_QY": "18",
            "PREV_RPTD_LAND_AM": "45000",
            "PREV_RPTD_IMPV_AM": "85000",
            "CAD_LINE_1_CMNT_TX": "LOCAL APPRAISER REPORT",
            "CAD_LINE_2_CMNT_TX": "SECOND COMMENT",
        }
    )
    values.update(overrides)
    return [values[header] for header in epts.EXPECTED_HEADERS]


def write_delimited(
    path: Path,
    rows: list[list[object]],
    *,
    delimiter: str = ",",
    header: list[object] | None = None,
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(header or epts.EXPECTED_HEADERS)
        writer.writerows(rows)
    return path


def write_xlsx(path: Path, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "EPTS"
    worksheet.append(list(epts.EXPECTED_HEADERS))
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    workbook.close()
    return path


def normalized_record(path: Path, **overrides: object) -> dict[str, object]:
    write_delimited(path, [representative_values(**overrides)])
    page = epts.query_artifact(path, operation="parse", limit=10)
    return page["records"][0]


def test_schema_has_exact_official_52_fields_and_current_a_to_q_codes() -> None:
    schema = epts.schema_record()

    assert schema["field_count"] == 52
    assert [field["number"] for field in schema["fields"]] == list(range(1, 53))
    assert [field["header"] for field in schema["fields"]] == list(
        epts.EXPECTED_HEADERS
    )
    assert schema["manual_publication"] == "September 2025"
    assert {
        code: tuple(data["field_numbers"])
        for code, data in schema["code_sets"]["confidentiality"].items()
    } == {
        "A": (7,),
        "B": (9,),
        "C": (19, 20),
        "D": (26, 27),
        "E": (7, 9),
        "F": (7, 19, 20),
        "G": (7, 26, 27),
        "H": (9, 19, 20),
        "I": (9, 26, 27),
        "J": (19, 20, 26, 27),
        "K": (7, 9, 19, 20),
        "L": (7, 9, 26, 27),
        "M": (7, 19, 20, 26, 27),
        "N": (9, 19, 20, 26, 27),
        "O": (7, 9, 19, 20, 26, 27),
        "P": (),
        "Q": (),
    }
    assert (
        schema["code_sets"]["confidentiality"]["P"]["description"]
        == "other confidential information"
    )
    assert (
        schema["code_sets"]["confidentiality"]["Q"]["description"]
        == "no confidential information"
    )


def test_request_plan_handoff_uses_official_routes_without_submission() -> None:
    discovery = epts.source_discovery_record()
    plan = epts.request_plan_record(
        cad_ids=["101", "227"],
        start_date="2024-01-01",
        end_date="2025-12-31",
    )

    assert discovery["official_sources"]["current_manual"] == epts.MANUAL_URL
    assert discovery["official_sources"]["request_portal"] == epts.CRRS_URL
    assert discovery["specimen_state"]["delivered_epts_artifact_reviewed"] is False
    assert plan["submission_performed"] is False
    assert plan["state"] == "prepared_for_human_review"
    assert plan["scope"]["cad_ids"] == ["101", "227"]
    assert len(plan["scope"]["requested_headers"]) == 52
    assert all(route["submission_performed"] is False for route in plan["routes"])
    assert {route["route_kind"] for route in plan["routes"]} == {
        "comptroller_record_request_system",
        "open_records_email",
    }


@pytest.mark.parametrize(
    ("suffix", "delimiter", "expected_name"),
    [
        (".csv", ",", ","),
        (".txt", "\t", "\t"),
    ],
)
def test_delimited_inspection_and_normalization_preserve_source_row(
    tmp_path: Path,
    suffix: str,
    delimiter: str,
    expected_name: str,
) -> None:
    artifact = write_delimited(
        tmp_path / f"101EPTS093025{suffix}",
        [representative_values()],
        delimiter=delimiter,
    )

    inspection = epts.inspect_artifact(artifact)
    page = epts.query_artifact(artifact, operation="parse", limit=10)
    record = page["records"][0]

    assert inspection["schema_valid"] is True
    assert inspection["record_count"] == 1
    assert inspection["distinct_cad_ids"] == ["101"]
    assert inspection["filename_metadata"][0]["submission_date"] == "2025-09-30"
    assert inspection["selected_members"][0]["delimiter"] == expected_name
    assert record["source_occurrence"]["source_row_number"] == 2
    assert record["source_occurrence"]["physical_line_start"] == 2
    assert record["source_occurrence"]["artifact_sha256"] == inspection["artifact"][
        "sha256"
    ]
    assert record["raw_values"]["PROP_SALE_AM"] == "147500"
    assert record["transaction"]["sale_date"]["iso"] == "2025-09-15"
    assert record["transaction"]["consideration"]["value"] == 147500
    assert record["property"]["account_number"] == "ACCOUNT-0001"
    assert record["parties"][0]["role"] == "grantee"
    assert record["parties"][1]["role"] == "grantor"
    assert record["appraisal"]["current_values"]["total"]["value"] == 140000
    assert record["appraisal"]["previous_values"]["land"]["value"] == 45000
    assert record["ownership_and_improvements"]["year_built"]["value"] == 1999


def test_deed_fields_are_clerk_pivots_not_instrument_or_title(tmp_path: Path) -> None:
    record = normalized_record(tmp_path / "epts.csv")
    locator = record["transaction"]["deed_locator"]

    assert locator["deed_number"] == "2025-009876"
    assert locator["volume"] == "123"
    assert locator["page"] == "456"
    assert locator["locator_role"] == "county_clerk_search_pivot"
    assert locator["recorded_instrument_copy"] is False
    assert locator["title_determination"] is False
    assert record["source_semantics"]["recorded_instrument_copy"] is False
    assert record["parties"][0]["current_title_determination"] is False


def test_confidentiality_blank_redaction_p_and_q_states(tmp_path: Path) -> None:
    blank = normalized_record(
        tmp_path / "blank.csv",
        CNFD_CD="A",
        PRCL_AD_TX="",
    )
    marker = normalized_record(
        tmp_path / "marker.csv",
        CNFD_CD="B",
        PROP_SALE_AM="[WITHHELD]",
    )
    other = normalized_record(
        tmp_path / "other.csv",
        CNFD_CD="P",
        PRCL_AD_TX="",
    )
    none = normalized_record(
        tmp_path / "none.csv",
        CNFD_CD="Q",
        PRCL_AD_TX="",
    )
    missing_code = normalized_record(
        tmp_path / "missing-code.csv",
        CNFD_CD="",
        PRCL_AD_TX="",
    )

    assert (
        blank["field_states"]["PRCL_AD_TX"]["state"]
        == "publisher_blank_confidential_field"
    )
    assert (
        marker["field_states"]["PROP_SALE_AM"]["state"]
        == "publisher_redaction_marker"
    )
    assert marker["transaction"]["consideration"]["value"] is None
    assert other["reporting"]["confidentiality"][
        "other_confidential_information"
    ] is True
    assert other["field_states"]["PRCL_AD_TX"]["state"] == "blank"
    assert none["reporting"]["confidentiality"][
        "no_confidential_information"
    ] is True
    assert none["field_states"]["PRCL_AD_TX"]["state"] == "blank"
    assert missing_code["reporting"]["confidentiality"]["state"] == "blank"
    assert missing_code["reporting"]["confidentiality"]["scope"] == "unknown"


def test_xlsx_sheet_and_cell_occurrence_are_preserved(tmp_path: Path) -> None:
    artifact = write_xlsx(
        tmp_path / "delivery.xlsx",
        [representative_values(PROP_ID1_TX="XLSX-ACCOUNT")],
    )

    identity, members, rejected = epts.discover_artifact_members(artifact)
    page = epts.query_artifact(
        artifact,
        operation="search",
        selector="xlsx-account",
        search_field="account",
        limit=10,
        member="EPTS",
    )
    record = page["records"][0]

    assert identity.container_format == "xlsx"
    assert rejected == []
    assert members[0].member_id == "artifact#sheet=EPTS"
    assert record["source_occurrence"]["member"]["sheet_name"] == "EPTS"
    assert record["source_occurrence"]["source_row_number"] == 2
    assert record["source_occurrence"]["cell_metadata"]["PROP_ID1_TX"][
        "coordinate"
    ] == "E2"


def test_zip_members_are_distinct_and_selectable(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.txt"
    write_delimited(first, [representative_values(PROP_ID1_TX="FIRST")])
    write_delimited(
        second,
        [representative_values(PROP_ID1_TX="SECOND")],
        delimiter="\t",
    )
    artifact = tmp_path / "delivery.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.write(first, "district/first.csv")
        archive.writestr("README.md", "delivery notes")
        archive.write(second, "district/second.txt")

    identity, members, _ = epts.discover_artifact_members(artifact)
    page = epts.query_artifact(
        artifact,
        operation="parse",
        member="district/second.txt",
        limit=10,
    )

    assert identity.container_format == "zip"
    assert [member.archive_member for member in members] == [
        "district/first.csv",
        "district/second.txt",
    ]
    assert page["records"][0]["property"]["account_number"] == "SECOND"
    assert page["records"][0]["source_occurrence"]["member"][
        "archive_member_index"
    ] == 2


@pytest.mark.parametrize("field_count", [51, 53])
def test_wrong_data_row_width_is_rejected(
    tmp_path: Path,
    field_count: int,
) -> None:
    row = representative_values()[:field_count]
    if field_count > 52:
        row.append("EXTRA")
    artifact = write_delimited(tmp_path / f"width-{field_count}.csv", [row])

    with pytest.raises(epts.EPTSLayoutError, match="expected 52"):
        epts.inspect_artifact(artifact)


def test_header_must_match_all_52_official_fields(tmp_path: Path) -> None:
    header = list(epts.EXPECTED_HEADERS)
    header[32] = "OLD_CONFIDENTIAL_FIELD"
    artifact = write_delimited(
        tmp_path / "bad-header.csv",
        [representative_values()],
        header=header,
    )

    with pytest.raises(epts.EPTSLayoutError, match="official 52-field"):
        epts.inspect_artifact(artifact)


def test_execute_reports_layout_failure_as_source_changed(tmp_path: Path) -> None:
    header = list(epts.EXPECTED_HEADERS)
    header[0] = "NOT_CAD_ID"
    artifact = write_delimited(
        tmp_path / "bad-header.csv",
        [representative_values()],
        header=header,
    )
    args = epts.build_parser().parse_args(["inspect", str(artifact)])

    result = epts.execute(args)

    assert result.status == epts.ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "epts_layout_mismatch"
    assert result.errors[0].category == "source_schema"


def test_multiple_account_rows_are_retained_with_layered_candidates(
    tmp_path: Path,
) -> None:
    artifact = write_delimited(
        tmp_path / "multi.csv",
        [
            representative_values(
                PROP_ID1_TX="ACCOUNT-0001",
                ADDNL_PROPS="ACCOUNT-0002",
            ),
            representative_values(
                PROP_ID1_TX="ACCOUNT-0002",
                ADDNL_PROPS="ACCOUNT-0001",
            ),
        ],
    )

    page = epts.query_artifact(artifact, operation="parse", limit=10)
    first, second = page["records"]

    assert len(page["records"]) == 2
    assert first["record_id"] != second["record_id"]
    assert (
        first["identity_candidates"]["transaction_group"]["candidate_key"]
        == second["identity_candidates"]["transaction_group"]["candidate_key"]
    )
    assert (
        first["identity_candidates"]["transaction_account"]["candidate_key"]
        != second["identity_candidates"]["transaction_account"]["candidate_key"]
    )
    assert first["identity_candidates"]["multiple_account_rows_must_be_retained"]
    assert page["automatic_deduplication"] is False


def test_cursor_pages_occurrences_and_binds_artifact_query_schema_and_member(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = write_delimited(
        tmp_path / "page.csv",
        [
            representative_values(PROP_ID1_TX="ACCOUNT-1"),
            representative_values(PROP_ID1_TX="ACCOUNT-2"),
            representative_values(PROP_ID1_TX="ACCOUNT-3"),
        ],
    )
    first = epts.query_artifact(artifact, operation="parse", limit=1)
    cursor = first["next_cursor"]
    second = epts.query_artifact(
        artifact,
        operation="parse",
        limit=1,
        cursor=cursor,
    )

    assert first["records"][0]["property"]["account_number"] == "ACCOUNT-1"
    assert second["records"][0]["property"]["account_number"] == "ACCOUNT-2"
    assert second["records"][0]["source_occurrence"][
        "artifact_occurrence_index"
    ] == 1

    changed = write_delimited(
        tmp_path / "changed.csv",
        [representative_values(PROP_ID1_TX="CHANGED")],
    )
    with pytest.raises(epts.EPTSCursorError, match="artifact_sha256"):
        epts.query_artifact(
            changed,
            operation="parse",
            limit=1,
            cursor=cursor,
        )
    with pytest.raises(epts.EPTSCursorError, match="criteria_fingerprint"):
        epts.query_artifact(
            artifact,
            operation="search",
            selector="ACCOUNT",
            search_field="account",
            limit=1,
            cursor=cursor,
        )

    monkeypatch.setattr(epts, "SCHEMA_FINGERPRINT", "0" * 64)
    with pytest.raises(epts.EPTSCursorError, match="schema_fingerprint"):
        epts.query_artifact(
            artifact,
            operation="parse",
            limit=1,
            cursor=cursor,
        )


def test_cursor_checksum_rejects_tampering(tmp_path: Path) -> None:
    artifact = write_delimited(
        tmp_path / "page.csv",
        [
            representative_values(PROP_ID1_TX="ACCOUNT-1"),
            representative_values(PROP_ID1_TX="ACCOUNT-2"),
        ],
    )
    page = epts.query_artifact(artifact, operation="parse", limit=1)
    cursor = page["next_cursor"]
    encoded = cursor[len(epts.CURSOR_PREFIX) :]
    envelope = json.loads(
        base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    )
    envelope["payload"]["next_occurrence_index"] = 999
    tampered = epts.CURSOR_PREFIX + base64.urlsafe_b64encode(
        json.dumps(envelope).encode()
    ).decode().rstrip("=")

    with pytest.raises(epts.EPTSCursorError, match="checksum"):
        epts.query_artifact(
            artifact,
            operation="parse",
            limit=1,
            cursor=tampered,
        )


def test_cursor_binds_selected_archive_member(tmp_path: Path) -> None:
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    write_delimited(
        first,
        [
            representative_values(PROP_ID1_TX="FIRST-1"),
            representative_values(PROP_ID1_TX="FIRST-2"),
        ],
    )
    write_delimited(
        second,
        [
            representative_values(PROP_ID1_TX="SECOND-1"),
            representative_values(PROP_ID1_TX="SECOND-2"),
        ],
    )
    artifact = tmp_path / "members.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.write(first, "first.csv")
        archive.write(second, "second.csv")

    page = epts.query_artifact(
        artifact,
        operation="parse",
        member="first.csv",
        limit=1,
    )

    with pytest.raises(epts.EPTSCursorError, match="criteria_fingerprint"):
        epts.query_artifact(
            artifact,
            operation="parse",
            member="second.csv",
            limit=1,
            cursor=page["next_cursor"],
        )


def test_legacy_xls_reports_honest_format_gap(tmp_path: Path) -> None:
    artifact = tmp_path / "delivery.xls"
    artifact.write_bytes(b"not an xls workbook")

    with pytest.raises(epts.EPTSLayoutError, match="legacy XLS"):
        epts.artifact_identity(artifact)
