from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from typing import Any

import pytest

from tools import query_oregon_marion_downloads as marion
from tools.public_records_contract import ResultStatus


def _sales_release(
    year: int,
    *,
    schema_profile: str,
    artifact_format: str = "csv",
) -> marion.Release:
    return marion.Release(
        source_id=marion.SALES_SOURCE_ID,
        release_id=f"sales-{year}",
        label=f"{year} sales",
        url=f"https://example.test/{year}sales.{artifact_format}",
        coverage_start=year,
        coverage_end=year,
        publication_kind="annual_csv",
        format=artifact_format,
        schema_profile=schema_profile,
    )


def _row(
    columns: tuple[str, ...],
    **values: Any,
) -> list[str]:
    row = [""] * len(columns)
    for name, value in values.items():
        row[columns.index(name)] = str(value)
    return row


def _official_manifest_html() -> str:
    links = [
        (
            marion.COMPREHENSIVE_URL,
            "Comprehensive Assessment Download",
        ),
        (
            "https://apps.co.marion.or.us/AO/SalesData/2026SalesData.csv",
            "2026 Sales Data",
        ),
    ]
    links.extend(
        (
            f"https://apps.co.marion.or.us/AO/SalesData/{year}sales.csv",
            f"{year} sales",
        )
        for year in range(2020, 2026)
    )
    links.extend(
        (
            (
                "https://apps.co.marion.or.us/AO/SalesData/"
                f"{start}-{start + 9}sales.zip"
            ),
            f"{start}-{start + 9} sales",
        )
        for start in range(1980, 2020, 10)
    )
    links.extend(
        (
            (
                "https://apps.co.marion.or.us/AO/SalesData/"
                f"{start}{start + 9}sales.xls"
            ),
            f"{start}-{start + 9} sales",
        )
        for start in range(1940, 1980, 10)
    )
    return "\n".join(
        f'<a href="{url}">{label}</a>' for url, label in links
    )


def test_manifest_discovers_all_sixteen_official_slots_and_contiguous_sales() -> None:
    snapshot = marion.parse_release_manifest(_official_manifest_html())

    sales = snapshot.by_source(marion.SALES_SOURCE_ID)
    assessment = snapshot.by_source(marion.ASSESSMENT_SOURCE_ID)

    assert len(snapshot.releases) == 16
    assert len(sales) == 15
    assert [release.release_id for release in assessment] == [
        "comprehensive-current"
    ]
    assert min(release.coverage_start for release in sales) == 1940
    assert max(release.coverage_end for release in sales) == 2026
    assert {
        release.schema_profile for release in sales
    } == {
        "sales_csv_duplicate_header_v1",
        "sales_csv_abbreviated_v2",
        "sales_csv_descriptive_v3",
        "sales_workbook_archive_legacy",
        "sales_workbook_legacy",
    }


def test_default_single_release_selection_uses_current_publisher_slots() -> None:
    snapshot = marion.parse_release_manifest(_official_manifest_html())

    sales = marion._one_release(
        snapshot=snapshot,
        source_id=marion.SALES_SOURCE_ID,
        release_id=None,
        year=None,
    )
    assessment = marion._one_release(
        snapshot=snapshot,
        source_id=marion.ASSESSMENT_SOURCE_ID,
        release_id=None,
        year=None,
    )

    assert sales.release_id == "sales-2026"
    assert sales.publication_kind == "weekly_current_year"
    assert assessment.release_id == "comprehensive-current"


def test_manifest_rejects_a_gap_in_historical_sales_coverage() -> None:
    html = _official_manifest_html().replace(
        (
            '<a href="https://apps.co.marion.or.us/AO/SalesData/'
            '19601969sales.xls">1960-1969 sales</a>'
        ),
        "",
    )

    with pytest.raises(
        marion.MarionDownloadError,
        match="calendar-year coverage gap",
    ):
        marion.parse_release_manifest(html)


def test_2020_duplicate_headers_are_mapped_by_position() -> None:
    columns = marion._sales_columns(
        "sales_csv_duplicate_header_v1",
        marion.SALES_V1_RAW_HEADER,
    )
    values = _row(
        columns,
        legacy_leading_sale_date="01/02/2020",
        sale_date="03/04/2020",
        statistical_classification_description="RESIDENTIAL",
        condition_description="CONFIRMED",
        account_number="510174",
        map_taxlot="032W290000400",
        instrument_number="2020-12345",
        sale_price="2545000",
    )
    record = marion._normalize_sale_row(
        values,
        raw_header=marion.SALES_V1_RAW_HEADER,
        canonical_columns=columns,
        release=_sales_release(
            2020,
            schema_profile="sales_csv_duplicate_header_v1",
        ),
        artifact_sha256="a" * 64,
        member_occurrence_id="member-2020",
        row_number=2,
    )

    assert columns[1] == "legacy_leading_sale_date"
    assert columns[25] == "sale_date"
    assert columns[18] == "statistical_classification_description"
    assert columns[27] == "condition_description"
    assert record["sale"]["sale_date"] == "2020-03-04"
    assert record["sale"]["legacy_leading_sale_date_raw"] == "01/02/2020"
    assert record["property_context"][
        "statistical_classification_description"
    ] == "RESIDENTIAL"
    assert record["sale"]["condition_description"] == "CONFIRMED"


def test_semantic_sale_identity_is_separate_from_party_and_occurrence_changes() -> None:
    columns = marion.SALES_V2_COLUMNS
    common = {
        "account_number": "510174",
        "map_taxlot": "032W290000400",
        "sale_date": "03/04/2021",
        "instrument_number": "2021-12345",
        "deed_reel_page": "4455/47",
        "sale_price": "2545000",
    }
    first_values = _row(
        columns,
        **common,
        grantor_name="SELLER ONE",
        grantee_name="BUYER ONE",
    )
    second_values = _row(
        columns,
        **common,
        grantor_name="SELLER ONE CORRECTED",
        grantee_name="BUYER ONE LLC",
    )
    release = _sales_release(
        2021,
        schema_profile="sales_csv_abbreviated_v2",
    )

    first = marion._normalize_sale_row(
        first_values,
        raw_header=marion.SALES_V2_RAW_HEADER,
        canonical_columns=columns,
        release=release,
        artifact_sha256="a" * 64,
        member_occurrence_id="member-first",
        row_number=2,
    )
    second = marion._normalize_sale_row(
        second_values,
        raw_header=marion.SALES_V2_RAW_HEADER,
        canonical_columns=columns,
        release=release,
        artifact_sha256="b" * 64,
        member_occurrence_id="member-second",
        row_number=9,
    )

    assert first["native_sale_id"] == second["native_sale_id"]
    assert first["source_occurrence_id"] != second["source_occurrence_id"]
    assert "grantor_name" not in first["sale_identity"]["semantic_components"]
    assert "grantee_name" not in first["sale_identity"]["semantic_components"]
    assert first["transaction_parties"] != second["transaction_parties"]


def test_comprehensive_row_keeps_latest_sale_labels_out_of_owner_and_title() -> None:
    raw_header = (
        "TYYYY",
        "RDATE",
        "TXID",
        "ACCOUNT_ID",
        "TXCD",
        "PCLS",
        "PCLSD",
        "AV",
        "RMVLAND",
        "RMVIMPR",
        "SITUSSTR",
        "SITUSCITY",
        "SITUSZIP",
        "BOOKPG",
        "SALEPR",
        "YRSOLD",
        "MOSOLD",
        "INSTRTYP",
        "SALEBK",
        "SALE_GRANTEE",
        "SALE_GRANTOR",
    )
    values = _row(
        raw_header,
        TYYYY="2026",
        RDATE="20260701",
        TXID="R10174",
        ACCOUNT_ID="510174",
        TXCD="001",
        PCLS="550",
        PCLSD="Farm",
        AV="276968",
        RMVLAND="1508580",
        RMVIMPR="325000",
        SITUSSTR="100 SAMPLE RD",
        SITUSCITY="SALEM",
        SITUSZIP="97301",
        BOOKPG="35450047",
        SALEPR="2545000",
        YRSOLD="2013",
        MOSOLD="9",
        INSTRTYP="WD",
        SALEBK="35450047",
        SALE_GRANTEE="KCK PARTNERS LLC",
        SALE_GRANTOR="SAMPLE FARMS LLC",
    )
    release = marion.Release(
        source_id=marion.ASSESSMENT_SOURCE_ID,
        release_id="comprehensive-current",
        label="Comprehensive",
        url=marion.COMPREHENSIVE_URL,
        coverage_start=None,
        coverage_end=None,
        publication_kind="monthly_current_snapshot",
        format="zip",
        schema_profile="comprehensive_assessment_v1",
    )

    record = marion._normalize_assessment_row(
        values,
        raw_header=raw_header,
        release=release,
        artifact_sha256="c" * 64,
        member_occurrence_id="primary-member",
        row_number=2,
    )

    assert record["source_vintage"]["rdate_iso"] == "2026-07-01"
    assert record["owners"] == []
    assert record["snapshot_complete"] is False
    assert record["latest_sale_labels"]["grantor_label"] == "SAMPLE FARMS LLC"
    assert record["latest_sale_labels"]["grantee_label"] == "KCK PARTNERS LLC"
    assert record["latest_sale_labels"]["establishes_current_owner"] is False
    assert record["latest_sale_labels"]["establishes_title"] is False
    assert record["latest_sale_labels"][
        "verifies_recorded_instrument"
    ] is False


def test_legacy_archive_reports_member_capabilities_without_family_failure(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "1980-1989sales.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("1980sales.xls", b"legacy-xls")
        archive.writestr("1981sales.xlsb", b"legacy-xlsb")
    release = marion.Release(
        source_id=marion.SALES_SOURCE_ID,
        release_id="sales-1980-1989",
        label="1980-1989 sales",
        url="https://example.test/1980-1989sales.zip",
        coverage_start=1980,
        coverage_end=1989,
        publication_kind="historical_decade_archive",
        format="zip",
        schema_profile="sales_workbook_archive_legacy",
    )

    inspection = marion.inspect_local_artifact(
        archive_path,
        release=release,
        scan_rows=False,
    )

    assert inspection["source_manifest_accessible"] is True
    assert inspection["row_search_supported_members"] == []
    assert inspection["unsupported_member_formats"] == ["xls", "xlsb"]
    assert {
        member["member_name"] for member in inspection["member_occurrences"]
    } == {"1980sales.xls", "1981sales.xlsb"}


def test_local_inspect_does_not_fetch_the_live_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "2022sales.csv"
    with artifact.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(marion.SALES_V3_RAW_HEADER)
        writer.writerow([""] * len(marion.SALES_V3_RAW_HEADER))

    def unexpected_fetch(**_kwargs: Any) -> marion.ManifestSnapshot:
        raise AssertionError("local inspect fetched the live manifest")

    monkeypatch.setattr(marion, "fetch_release_manifest", unexpected_fetch)
    args = marion.build_parser().parse_args(
        [
            "inspect",
            str(artifact),
            "--source",
            marion.SALES_SOURCE_ID,
            "--year",
            "2022",
        ]
    )

    result = marion.execute(args, log_results=False)

    assert result.status == ResultStatus.OK
    assert result.records[0]["record_kind"] == "local_artifact_inspection"
    assert result.raw_artifact_refs == (str(artifact),)
