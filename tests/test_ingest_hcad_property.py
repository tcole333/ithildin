from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from tools import ingest_hcad_property


def _table_bytes(
    table: str,
    rows: list[dict[str, str]],
) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(ingest_hcad_property.TABLE_SPECS[table].header),
        delimiter="\t",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def _archive(
    path: Path,
    tables: dict[str, list[dict[str, str]]],
) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for table, rows in tables.items():
            archive.writestr(f"{table}.txt", _table_bytes(table, rows))
    return path


def _core_archive(path: Path) -> Path:
    real_account = {
        "acct": "0010010000013             ",
        "yr": "2026",
        "mailto": "ALPHA OWNER",
        "mail_addr_1": "PO  BOX  10",
        "mail_addr_2": "SUITE 2",
        "mail_city": "HOUSTON",
        "mail_state": "TX",
        "mail_zip": "77001",
        "mail_country": "US",
        "site_addr_1": "100 MAIN ST",
        "site_addr_2": "HOUSTON",
        "site_addr_3": "77002",
        "state_class": "A1",
        "land_val": "100000",
        "bld_val": "200000",
        "x_features_val": "25000",
        "assessed_val": "280000",
        "tot_appr_val": "300000",
        "tot_mkt_val": "325000",
        "lgl_1": "LOT 1",
    }
    owner_alpha = {
        "acct": "0010010000013",
        "ln_num": "1",
        "name": "ALPHA OWNER",
        "aka": "",
        "pct_own": "0.6000",
    }
    owner_beta = {
        "acct": "0010010000013",
        "ln_num": "2",
        "name": "BETA OWNER",
        "aka": "BETA LLC",
        "pct_own": "0.4000",
    }
    deed = {
        "acct": "0010010000013",
        "dos": "",
        "clerk_yr": "2020",
        "clerk_id": "RP-123",
        "deed_id": "1",
    }
    relation = {
        "acct": "0010010000013",
        "tp": "UM",
        "dscr": "Undivided Interest Master",
        "related_acct": "7010010000014",
        "pct": "1.000000",
    }
    permit = {
        "acct": "0010010000013",
        "id": "P-10",
        "agency_id": "061",
        "status": "C",
        "dscr": "REMODEL",
        "dor_cd": "A1",
        "permit_type": "50",
        "permit_tp_descr": "Building permit",
        "property_tp": "R",
        "issue_date": "05/14/2025",
        "yr": "2026",
        "site_num": "100",
        "site_pfx": "",
        "site_str": "MAIN",
        "site_tp": "ST",
        "site_sfx": "",
        "site_apt": "",
    }
    return _archive(
        path,
        {
            "deeds": [deed, dict(deed)],
            "owners": [owner_alpha, owner_beta, dict(owner_beta)],
            "parcel_tieback": [relation],
            "permits": [permit],
            "real_acct": [real_account],
        },
    )


def _args(
    archive: Path,
    property_db: Path,
    *extra: str,
) -> object:
    return ingest_hcad_property.build_parser().parse_args(
        [
            "ingest",
            "--archive",
            str(archive),
            "--tax-year",
            "2026",
            "--release-id",
            "2026:preliminary:2026-07-26",
            "--certification-status",
            "preliminary",
            "--property-db",
            str(property_db),
            "--retrieved-at",
            "2026-07-30T00:00:00Z",
            *extra,
        ]
    )


def _counts(path: Path) -> dict[str, int]:
    db = sqlite3.connect(path)
    try:
        return {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "source_observation",
                "parcel_snapshot",
                "parcel_address",
                "ownership_assertion",
                "assessment",
                "sale_event",
                "property_event",
                "recorded_instrument",
            )
        }
    finally:
        db.close()


def test_core_archive_preserves_occurrences_and_projects_without_title_claim(
    tmp_path: Path,
) -> None:
    archive = _core_archive(tmp_path / "Real_acct_owner.zip")
    property_db = tmp_path / "property.db"
    args = _args(archive, property_db, "--batch-size", "1")

    first = ingest_hcad_property.execute(args)
    first_counts = _counts(property_db)
    second = ingest_hcad_property.execute(args)

    assert first["release"]["artifact_role"] == "real_acct_owner"
    assert first["counts"]["rows_processed"] == 8
    assert first["counts"]["observations_inserted"] == 8
    assert first["counts"]["recorded_instruments_projected"] == 0
    assert first["counts"]["clerk_pivots_preserved"] == 2
    assert first["counts"]["permits_projected"] == 1
    assert first["counts"]["account_relations_projected"] == 1
    assert first["counts"]["related_accounts_resolved"] == 1
    assert first["exhausted"] is True
    assert second["archive_observation_inserted"] is False
    assert second["counts"]["observations_inserted"] == 0
    assert second["counts"]["observations_reused"] == 8
    assert _counts(property_db) == first_counts
    assert first_counts == {
        "source_observation": 9,
        "parcel_snapshot": 2,
        "parcel_address": 2,
        "ownership_assertion": 2,
        "assessment": 1,
        "sale_event": 1,
        "property_event": 2,
        "recorded_instrument": 0,
    }

    db = sqlite3.connect(property_db)
    db.row_factory = sqlite3.Row
    try:
        sale = db.execute(
            "SELECT sale_date, instrument_id, raw_json FROM sale_event"
        ).fetchone()
        assert sale["sale_date"] is None
        assert sale["instrument_id"] is None
        sale_raw = json.loads(sale["raw_json"])
        assert sale_raw["raw_fields"]["clerk_id"] == "RP-123"
        assert sale_raw["instrument_reference"] == {
            "clerk_id": "RP-123",
            "clerk_year": "2020",
            "deed_id": "1",
            "recorded_title_evidence": False,
            "reference_scope": "hcad_appraisal_observation",
        }

        duplicate_rows = db.execute(
            """
            SELECT source_native_id, raw_json
            FROM source_observation
            WHERE record_kind='hcad_owners_row'
              AND json_extract(raw_json, '$.raw_fields.name')='BETA OWNER'
            ORDER BY source_native_id
            """
        ).fetchall()
        assert len(duplicate_rows) == 2
        assert {
            json.loads(row["raw_json"])["identical_row_ordinal"]
            for row in duplicate_rows
        } == {0, 1}

        parcel_raw = json.loads(
            db.execute(
                """
                SELECT raw_json FROM parcel_snapshot
                WHERE native_parcel_id='0010010000013'
                """
            ).fetchone()["raw_json"]
        )
        assert parcel_raw["raw_fields"]["mail_addr_1"] == "PO  BOX  10"
        assessment = db.execute(
            """
            SELECT land_value_minor, improvement_value_minor,
                   total_value_minor, market_value_minor, assessed_value_minor
            FROM assessment
            """
        ).fetchone()
        assert tuple(assessment) == (
            10_000_000,
            22_500_000,
            30_000_000,
            32_500_000,
            28_000_000,
        )
    finally:
        db.close()


def test_ownership_history_uses_actual_four_column_header_and_null_date_identity(
    tmp_path: Path,
) -> None:
    row = {
        "acct": "0010010000013             ",
        "purchase_date": "",
        "name": "HISTORIC OWNER",
        "site_address": "100 MAIN ST",
    }
    archive = _archive(
        tmp_path / "Real_acct_ownership_history.zip",
        {"ownership_history": [row, dict(row)]},
    )
    property_db = tmp_path / "history.db"
    args = _args(archive, property_db)

    first = ingest_hcad_property.execute(args)
    before = _counts(property_db)
    second = ingest_hcad_property.execute(args)

    assert first["schema"]["tables"]["ownership_history"]["header_fields"] == [
        "acct",
        "purchase_date",
        "name",
        "site_address",
    ]
    assert "ln_num" not in first["schema"]["tables"]["ownership_history"][
        "header_fields"
    ]
    assert first["counts"]["rows_processed"] == 2
    assert first["counts"]["ownership_history_rows_projected"] == 2
    assert before["ownership_assertion"] == 1
    assert before["parcel_address"] == 1
    assert second["counts"]["observations_reused"] == 2
    assert _counts(property_db) == before


def test_live_observed_cp437_owner_literals_decode_without_replacement(
    tmp_path: Path,
) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(
            ingest_hcad_property.TABLE_SPECS["owners"].header
        ),
        delimiter="\t",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerow(
        {
            "acct": "1245260020049",
            "ln_num": "1",
            "name": "MUÑOZ GABRIEL",
            "aka": "SEÑOR TAQUERO",
            "pct_own": "1.0000",
        }
    )
    archive_path = tmp_path / "cp437-owner.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "owners.txt",
            output.getvalue().encode("cp437"),
        )
    property_db = tmp_path / "cp437.db"

    result = ingest_hcad_property.execute(
        _args(archive_path, property_db)
    )

    assert result["schema"]["source_encoding"] == "cp437"
    db = sqlite3.connect(property_db)
    try:
        assert db.execute(
            "SELECT raw_owner_name FROM ownership_assertion"
        ).fetchone()[0] == "MUÑOZ GABRIEL"
        raw_json = db.execute(
            """
            SELECT raw_json FROM source_observation
            WHERE record_kind='hcad_owners_row'
            """
        ).fetchone()[0]
        assert json.loads(raw_json)["raw_fields"]["aka"] == "SEÑOR TAQUERO"
    finally:
        db.close()


def test_building_and_land_rows_are_joined_and_preserved_without_lossy_events(
    tmp_path: Path,
) -> None:
    archive = _archive(
        tmp_path / "Real_building_land.zip",
        {
            "building_res": [
                {
                    "acct": "0010010000013",
                    "property_use_cd": "A1",
                    "bld_num": "1",
                    "structure": "R",
                    "structure_dscr": "Residential",
                    "date_erected": "2019",
                    "im_sq_ft": "2534",
                }
            ],
            "land": [
                {
                    "acct": "0010010000013",
                    "num": "1",
                    "use_cd": "8005",
                    "use_dscr": "Land Neighborhood Section 5",
                    "tp": "SF",
                    "uts": "9775.0000",
                    "unit_prc": "60.00",
                    "val": "381225",
                }
            ],
        },
    )
    property_db = tmp_path / "building.db"

    result = ingest_hcad_property.execute(_args(archive, property_db))

    assert result["counts"]["rows_processed"] == 2
    assert result["counts"]["building_detail_rows_preserved"] == 1
    assert result["counts"]["land_detail_rows_preserved"] == 1
    assert result["counts"]["parcels_projected"] == 2
    counts = _counts(property_db)
    assert counts["parcel_snapshot"] == 1
    assert counts["source_observation"] == 3
    assert counts["property_event"] == 0


def test_unresolved_and_secondary_rows_remain_source_observations(
    tmp_path: Path,
) -> None:
    archive = _archive(
        tmp_path / "unresolved-owner.zip",
        {
            "owners": [
                {
                    "acct": "",
                    "ln_num": "1",
                    "name": "UNRESOLVED OWNER",
                    "aka": "",
                    "pct_own": "1.0000",
                }
            ],
            "real_neighborhood_code": [
                {
                    "cd": "5900.05",
                    "grp_cd": "0",
                    "dscr": "Central Business District",
                }
            ],
        },
    )
    property_db = tmp_path / "unresolved.db"

    result = ingest_hcad_property.execute(_args(archive, property_db))

    assert result["counts"]["rows_processed"] == 2
    assert result["counts"]["unresolved_rows_preserved"] == 1
    assert result["counts"]["secondary_rows_preserved"] == 1
    counts = _counts(property_db)
    assert counts["source_observation"] == 3
    assert counts["parcel_snapshot"] == 0
    assert counts["ownership_assertion"] == 0


def test_caller_checkpoint_has_no_hidden_default_row_ceiling(
    tmp_path: Path,
) -> None:
    archive = _core_archive(tmp_path / "Real_acct_owner.zip")
    property_db = tmp_path / "checkpoint.db"

    first = ingest_hcad_property.execute(
        _args(
            archive,
            property_db,
            "--table",
            "owners",
            "--limit",
            "1",
        )
    )
    second = ingest_hcad_property.execute(
        _args(
            archive,
            property_db,
            "--table",
            "owners",
            "--start-row",
            "1",
        )
    )

    assert first["counts"]["rows_processed"] == 1
    assert first["next_checkpoint_row"] == 1
    assert first["next_checkpoint"] == {
        "global_row": 1,
        "table": "owners",
        "table_row": 1,
    }
    assert first["exhausted"] is False
    assert second["counts"]["rows_processed"] == 2
    assert second["next_checkpoint_row"] is None
    assert second["exhausted"] is True


def test_missing_live_verified_header_fails_before_sidecar_creation(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "bad-history.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "ownership_history.txt",
            "acct\tpurchase_date\tname\tln_num\r\n"
            "0010010000013\t\tOWNER\t1\r\n",
        )
    property_db = tmp_path / "bad.db"

    with pytest.raises(
        ingest_hcad_property.HCADIngestError,
        match="lacks live-verified columns: site_address",
    ):
        ingest_hcad_property.execute(_args(archive_path, property_db))
    assert not property_db.exists()
