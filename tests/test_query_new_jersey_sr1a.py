from __future__ import annotations

import copy
import zipfile
from pathlib import Path

import pytest

from tools import query_new_jersey_sr1a as sr1a


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "new_jersey_sr1a"
)


@pytest.fixture(autouse=True)
def _disable_search_log(monkeypatch):
    monkeypatch.setattr(sr1a, "log_search", lambda *_args, **_kwargs: None)


def _snapshot() -> sr1a.ManifestSnapshot:
    return sr1a.parse_release_manifest(
        (FIXTURE_DIR / "manifest.html").read_text(encoding="utf-8")
    )


def _put(row: bytearray, field_name: str, value: str) -> None:
    spec = sr1a.FIELD_BY_NAME[field_name]
    encoded = value.encode("ascii")
    assert len(encoded) <= spec.width
    row[spec.byte_slice] = encoded.ljust(spec.width, b" ")


def _row(
    *,
    grantor: str = "ALPHA OWNER LLC",
    grantee: str = "BETA BUYER LLC",
    property_location: str = "123 MAIN ST",
    serial: str = "1234567",
    fee: str = "000035000",
    county: str = "12",
    district: str = "25",
    block: str = "299",
    lot: str = "1.02",
    recorded: str = "250617",
    reported_price: str = "000750000",
    verified_price: str = "000745000",
    additional_block: str = "",
    additional_lot: str = "",
) -> bytes:
    row = bytearray(b" " * sr1a.RECORD_WIDTH)
    values = {
        "county_code": county,
        "district_code": district,
        "total_assessment": "000000500000",
        "operator_initials": "ABC",
        "last_update_date": "062025",
        "un_type": "U",
        "sr_nu_code": "NU1",
        "reported_sales_price": reported_price,
        "verified_sales_price": verified_price,
        "main_value_land": "000150000",
        "main_value_building": "000350000",
        "main_value_total": "000500000",
        "sales_ratio": "07450",
        "realty_transfer_fee": fee,
        "rtf_error_flag": "",
        "rtf_exempt_code": "",
        "serial_number": serial,
        "grantor_name": grantor,
        "grantor_street": "10 OLD ROAD",
        "grantor_city_state": "NEWARK NJ",
        "grantor_zip": "071011234",
        "grantee_name": grantee,
        "grantee_street": "20 NEW ROAD",
        "grantee_city_state": "EDISON NJ",
        "grantee_zip": "088171234",
        "property_location": property_location,
        "aging_date": "250625",
        "deed_book": "A123",
        "deed_page": "0042",
        "deed_date": "250610",
        "date_recorded": recorded,
        "block": block,
        "block_suffix": "",
        "lot": lot,
        "lot_suffix": "",
        "etc": "",
        "additional_block_1": additional_block,
        "additional_lot_1": additional_lot,
        "additional_qualifier_1": "C01" if additional_block else "",
        "additional_value_land_1": (
            "000025000" if additional_block else "000000000"
        ),
        "additional_value_building_1": "000000000",
        "additional_value_total_1": (
            "000025000" if additional_block else "000000000"
        ),
        "qualification_codes": "Q1",
        "assess_year": "25",
        "property_class": "2",
        "class_4_type": "",
        "assessor_number_code": "007",
        "field_status_code": "F",
        "field_date": "190625",
        "critical_error_flag": "",
        "year_built": "1998",
        "living_space": "0002450",
    }
    for index in range(2, 6):
        values.update(
            {
                f"additional_block_{index}": "",
                f"additional_lot_{index}": "",
                f"additional_qualifier_{index}": "",
                f"additional_value_land_{index}": "000000000",
                f"additional_value_building_{index}": "000000000",
                f"additional_value_total_{index}": "000000000",
            }
        )
    for field_name, value in values.items():
        _put(row, field_name, value)
    return bytes(row)


def _archive(path: Path, member: str, rows: list[bytes]) -> Path:
    content = b"".join(row + b"\r\n" for row in rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, content)
    return path


def _release(
    snapshot: sr1a.ManifestSnapshot,
    release_id: str,
) -> sr1a.Release:
    return next(
        release
        for release in snapshot.releases
        if release.release_id == release_id
    )


def test_manifest_discovers_current_and_annual_release_links():
    snapshot = _snapshot()

    assert [release.release_id for release in snapshot.releases] == [
        "sr1a-ytd-2026",
        "sr1a-annual-2025",
        "sr1a-annual-2024",
    ]
    assert snapshot.releases[0].url == (
        "https://www.nj.gov/treasury/taxation/lpt/statdata/"
        "YTDSR1A2026.zip"
    )
    assert snapshot.layout_url == sr1a.LAYOUT_URL
    assert len(snapshot.fingerprint) == 64


def test_manifest_fingerprint_tracks_artifacts_not_cosmetic_link_text():
    original = _snapshot()
    changed_label = sr1a.ManifestSnapshot(
        releases=tuple(
            sr1a.Release(
                release_id=release.release_id,
                year=release.year,
                series=release.series,
                label=f"renamed {release.label}",
                url=release.url,
            )
            for release in original.releases
        ),
        layout_url=original.layout_url,
    )

    assert changed_label.fingerprint == original.fingerprint


def test_manifest_rejects_page_without_release_links():
    with pytest.raises(
        sr1a.NewJerseySR1AError,
        match="did not expose any SR1A",
    ):
        sr1a.parse_release_manifest("<html><body>No files</body></html>")


def test_declared_layout_covers_exact_published_end_position():
    assert sr1a.FIELD_BY_NAME["county_code"].start == 1
    assert sr1a.FIELD_BY_NAME["realty_transfer_fee"].byte_slice == slice(87, 96)
    assert sr1a.FIELD_BY_NAME["additional_value_total_5"].end == 619
    assert sr1a.FIELD_BY_NAME["living_space"].end == sr1a.RECORD_WIDTH


def test_normalizer_preserves_parties_deed_parcel_and_assessment(tmp_path):
    snapshot = _snapshot()
    release = _release(snapshot, "sr1a-annual-2025")
    row = _row(additional_block="300", additional_lot="2")
    archive_path = _archive(tmp_path / "annual.zip", "Sales2025.txt", [row])
    local = sr1a._local_release_from_path(release, archive_path)

    record = sr1a.normalize_row(row, local=local, row_index=0)

    assert record["jurisdiction"] == {
        "state_code": "NJ",
        "state_fips": "34",
        "county_code": "12",
        "county_name": "Middlesex",
        "county_geoid": "34023",
        "district_code": "25",
        "municipality_code": "1225",
    }
    assert record["parties"]["grantor"]["name"] == "ALPHA OWNER LLC"
    assert record["parties"]["grantee"]["mailing_address"][
        "postal_code"
    ] == "08817-1234"
    assert record["deed"]["recorded_date"]["iso"] == "2025-06-17"
    assert record["deed"]["recorded_date"]["source_format"] == "YYMMDD"
    assert record["source_processing"]["last_update_date"] == {
        "raw": "062025",
        "source_format": "MMDDYY",
        "iso": "2025-06-20",
    }
    assert record["source_processing"]["aging_date"]["iso"] == "2025-06-25"
    assert record["source_processing"]["field_date"] == {
        "raw": "190625",
        "source_format": "DDMMYY",
        "iso": "2025-06-19",
    }
    assert record["property"]["parcel"]["block"] == "299"
    assert record["property"]["additional_parcels"][0]["block"] == "300"
    assert record["property"]["main_assessed_value_dollars"]["total"] == 500_000
    assert record["property"]["year_built"] == 1998
    assert record["property"]["living_space_square_feet"] == 2_450
    assert record["transaction"]["sales_ratio"]["percent"] == "74.50"
    assert record["source_record"]["row_number"] == 1
    assert record["source_record"]["record_width_bytes"] == 663
    assert len(record["source_record"]["record_sha256"]) == 64
    assert "raw_fixed_width" not in record["source_record"]


def test_sale_identity_is_stable_across_release_occurrences(tmp_path):
    snapshot = _snapshot()
    row = _row()
    ytd_release = _release(snapshot, "sr1a-ytd-2026")
    annual_release = _release(snapshot, "sr1a-annual-2025")
    ytd_path = _archive(tmp_path / "ytd.zip", "YTDSR1A2026.txt", [row])
    annual_path = _archive(tmp_path / "annual.zip", "Sales2025.txt", [row])

    ytd = sr1a.normalize_row(
        row,
        local=sr1a._local_release_from_path(ytd_release, ytd_path),
        row_index=0,
    )
    annual = sr1a.normalize_row(
        row,
        local=sr1a._local_release_from_path(annual_release, annual_path),
        row_index=0,
    )

    assert ytd["sale_record_id"] == annual["sale_record_id"]
    assert ytd["canonical_ref"] == annual["canonical_ref"]
    assert ytd["source_occurrence_id"] != annual["source_occurrence_id"]
    assert ytd["native_record_id"] == ytd["source_occurrence_id"]


@pytest.mark.parametrize(
    ("raw_fee", "expected_cents", "expected_rule"),
    [
        ("000035000", 35_000, "implied_two_decimals"),
        ("0000350.0", 35_000, "explicit_decimal"),
    ],
)
def test_transfer_fee_handles_both_observed_release_encodings(
    tmp_path,
    raw_fee,
    expected_cents,
    expected_rule,
):
    snapshot = _snapshot()
    release = _release(snapshot, "sr1a-ytd-2026")
    row = _row(fee=raw_fee)
    archive_path = _archive(tmp_path / "fee.zip", "YTDSR1A2026.txt", [row])
    local = sr1a._local_release_from_path(release, archive_path)

    record = sr1a.normalize_row(row, local=local, row_index=0)
    fee = record["transaction"]["realty_transfer_fee"]

    assert fee == {
        "raw": raw_fee,
        "cents": expected_cents,
        "dollars": "350.00",
        "normalization": expected_rule,
    }


def test_raw_line_is_available_on_request(tmp_path):
    snapshot = _snapshot()
    release = _release(snapshot, "sr1a-ytd-2026")
    row = _row()
    archive_path = _archive(tmp_path / "raw.zip", "YTDSR1A2026.txt", [row])
    local = sr1a._local_release_from_path(release, archive_path)

    record = sr1a.normalize_row(
        row,
        local=local,
        row_index=0,
        include_raw_line=True,
    )

    assert record["source_record"]["raw_fixed_width"].encode("latin-1") == row


def test_archive_descriptor_rejects_incompatible_record_size(tmp_path):
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Sales2025.txt", b"too short\r\n")

    with pytest.raises(
        sr1a.ArchiveContractError,
        match="incompatible",
    ):
        sr1a.describe_archive(path)


def test_row_iterator_detects_changed_line_framing(tmp_path):
    snapshot = _snapshot()
    release = _release(snapshot, "sr1a-ytd-2026")
    row = _row()
    path = tmp_path / "bad-framing.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("YTDSR1A2026.txt", row + b"\nX")
    local = sr1a._local_release_from_path(release, path)

    with pytest.raises(
        sr1a.ArchiveContractError,
        match="CRLF",
    ):
        list(sr1a.iter_archive_rows(local))


def test_omitted_limit_exhausts_matches_across_selected_releases(tmp_path):
    snapshot = _snapshot()
    ytd_path = _archive(
        tmp_path / "ytd.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", grantee="MATCH BUYER"),
            _row(serial="1000002", grantee="OTHER BUYER"),
        ],
    )
    annual_path = _archive(
        tmp_path / "annual.zip",
        "Sales2025.txt",
        [_row(serial="2000001", grantor="MATCH SELLER")],
    )
    args = sr1a.build_parser().parse_args(
        [
            "search",
            "MATCH",
            "--field",
            "party",
            "--year",
            "2026",
            "--year",
            "2025",
        ]
    )

    result = sr1a.execute(
        args,
        manifest_snapshot=snapshot,
        archive_paths={
            "sr1a-ytd-2026": ytd_path,
            "sr1a-annual-2025": annual_path,
        },
    )

    assert result.status.value == "ok"
    assert result.query.query.requested_limit is None
    assert [
        record["transaction"]["serial_number"]
        for record in result.records
    ] == ["1000001", "2000001"]
    assert result.next_cursor is None


def test_bounded_search_resumes_without_overlap(tmp_path):
    snapshot = _snapshot()
    ytd_path = _archive(
        tmp_path / "ytd.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", grantor="MATCH ONE"),
            _row(serial="1000002", grantor="MATCH TWO"),
        ],
    )
    annual_path = _archive(
        tmp_path / "annual.zip",
        "Sales2025.txt",
        [_row(serial="2000001", grantor="MATCH THREE")],
    )
    archive_paths = {
        "sr1a-ytd-2026": ytd_path,
        "sr1a-annual-2025": annual_path,
    }
    parser = sr1a.build_parser()
    first = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "MATCH",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--year",
                "2025",
                "--limit",
                "2",
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths=archive_paths,
    )

    assert [
        record["transaction"]["serial_number"]
        for record in first.records
    ] == ["1000001", "1000002"]
    assert first.next_cursor

    second = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "MATCH",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--year",
                "2025",
                "--limit",
                "2",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths=archive_paths,
    )

    assert second.status.value == "ok"
    assert [
        record["transaction"]["serial_number"]
        for record in second.records
    ] == ["2000001"]
    assert second.next_cursor is None


def test_search_cursor_rejects_changed_artifact(tmp_path):
    snapshot = _snapshot()
    original_path = _archive(
        tmp_path / "original.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", grantor="MATCH ONE"),
            _row(serial="1000002", grantor="MATCH TWO"),
        ],
    )
    parser = sr1a.build_parser()
    first = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "MATCH",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--limit",
                "1",
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-ytd-2026": original_path},
    )
    changed_path = _archive(
        tmp_path / "changed.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", grantor="MATCH ONE"),
            _row(serial="1000003", grantor="MATCH CHANGED"),
        ],
    )

    second = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "MATCH",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-ytd-2026": changed_path},
    )

    assert second.status.value == "source_changed"
    assert second.errors[0].code == "nj_sr1a_cursor_invalid"
    assert "artifact binding" in second.errors[0].message


def test_search_cursor_rejects_different_selector(tmp_path):
    snapshot = _snapshot()
    path = _archive(
        tmp_path / "rows.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", grantor="MATCH ONE"),
            _row(serial="1000002", grantor="MATCH TWO"),
        ],
    )
    parser = sr1a.build_parser()
    first = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "MATCH",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--limit",
                "1",
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-ytd-2026": path},
    )

    second = sr1a.execute(
        parser.parse_args(
            [
                "search",
                "OTHER",
                "--field",
                "grantor",
                "--year",
                "2026",
                "--limit",
                "1",
                "--cursor",
                first.next_cursor,
            ]
        ),
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-ytd-2026": path},
    )

    assert second.status.value == "source_changed"
    assert "selection fingerprint" in second.errors[0].message


def test_block_lot_filter_matches_additional_parcel(tmp_path):
    snapshot = _snapshot()
    path = _archive(
        tmp_path / "rows.zip",
        "Sales2025.txt",
        [
            _row(
                serial="1000001",
                additional_block="0300",
                additional_lot="02.00",
            ),
            _row(serial="1000002"),
        ],
    )
    args = sr1a.build_parser().parse_args(
        [
            "search",
            "--year",
            "2025",
            "--municipality-code",
            "1225",
            "--block",
            "300",
            "--lot",
            "2",
        ]
    )

    result = sr1a.execute(
        args,
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-annual-2025": path},
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    assert result.records[0]["transaction"]["serial_number"] == "1000001"


def test_date_and_price_filters_are_applied_to_source_fields(tmp_path):
    snapshot = _snapshot()
    path = _archive(
        tmp_path / "rows.zip",
        "Sales2025.txt",
        [
            _row(
                serial="1000001",
                recorded="250601",
                reported_price="000900000",
            ),
            _row(
                serial="1000002",
                recorded="250701",
                reported_price="000500000",
            ),
        ],
    )
    args = sr1a.build_parser().parse_args(
        [
            "search",
            "--year",
            "2025",
            "--recorded-from",
            "2025-06-15",
            "--reported-price-max",
            "600000",
        ]
    )

    result = sr1a.execute(
        args,
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-annual-2025": path},
    )

    assert result.status.value == "ok"
    assert [
        record["transaction"]["serial_number"]
        for record in result.records
    ] == ["1000002"]


def test_validate_command_traverses_release_without_emitting_sale_rows(tmp_path):
    snapshot = _snapshot()
    path = _archive(
        tmp_path / "rows.zip",
        "YTDSR1A2026.txt",
        [
            _row(serial="1000001", fee="000035000"),
            _row(serial="1000002", fee="0000350.0"),
        ],
    )
    args = sr1a.build_parser().parse_args(
        [
            "validate",
            "--year",
            "2026",
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )

    result = sr1a.execute(
        args,
        manifest_snapshot=snapshot,
        archive_paths={"sr1a-ytd-2026": path},
    )

    assert result.status.value == "ok"
    assert len(result.records) == 1
    record = result.records[0]
    assert record["record_type"] == "release_validation"
    assert record["validation"]["complete_archive_traversal"] is True
    assert record["validation"]["records_traversed"] == 2
    assert record["validation"]["transfer_fee_normalizations"] == {
        "explicit_decimal": 1,
        "implied_two_decimals": 1,
    }
    assert record["validation"]["normalization_issue_counts_by_field"] == {}


def test_manifest_cursor_is_bound_to_release_listing():
    snapshot = _snapshot()
    first, cursor = sr1a.paginate_manifest(
        snapshot,
        snapshot.releases,
        limit=1,
        cursor=None,
    )
    changed_release = copy.copy(snapshot.releases[0])
    changed = sr1a.ManifestSnapshot(
        releases=(
            sr1a.Release(
                release_id=changed_release.release_id,
                year=changed_release.year,
                series=changed_release.series,
                label=changed_release.label,
                url=changed_release.url + "?revised=1",
            ),
            *snapshot.releases[1:],
        ),
        layout_url=snapshot.layout_url,
    )

    assert [release.release_id for release in first] == ["sr1a-ytd-2026"]
    assert cursor
    with pytest.raises(sr1a.CursorError, match="listing changed"):
        sr1a.paginate_manifest(
            changed,
            changed.releases,
            limit=1,
            cursor=cursor,
        )


def test_manifest_cursor_is_bound_to_release_selectors():
    snapshot = _snapshot()
    _first, cursor = sr1a.paginate_manifest(
        snapshot,
        snapshot.releases[:2],
        limit=1,
        cursor=None,
    )

    with pytest.raises(sr1a.CursorError, match="release selectors"):
        sr1a.paginate_manifest(
            snapshot,
            snapshot.releases,
            limit=1,
            cursor=cursor,
        )


def test_alternatives_cover_parcels_deeds_assessors_and_tax_court():
    routes = {
        route["source_id"]: route
        for route in sr1a._alternative_routes()
    }

    assert "us-nj-njgin-parcels-modiv" in routes
    assert "us-nj-county-clerks-registers" in routes
    assert "us-nj-local-assessors-tax-boards" in routes
    assert routes["us-nj-tax-court-property-cases"]["join_fields"] == [
        "party",
        "county",
        "municipality",
        "block",
        "lot",
        "assessment year",
    ]
    assert "us-nj-dca-property-registration" in routes


def test_search_parser_has_no_default_result_ceiling():
    args = sr1a.build_parser().parse_args(
        ["search", "ACME", "--field", "party"]
    )

    assert args.limit is None
    assert args.year is None
    assert args.release is None
