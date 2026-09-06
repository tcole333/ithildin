from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from tools import query_rrc_bulk as rrc


FIXTURE_DIR = Path("tests/fixtures/public_records/texas_rrc")
P4_FIXTURE = json.loads(
    (FIXTURE_DIR / "p4_group.json").read_text(encoding="utf-8")
)
PROVENANCE = json.loads(
    (FIXTURE_DIR / "provenance.json").read_text(encoding="utf-8")
)
P5_FIXTURE = FIXTURE_DIR / "p5_organizations.txt"
WELLBORE_FIXTURE = FIXTURE_DIR / "wellbore_rows.csv"
WELLBORE_TERMINAL_QUOTE_FIXTURE = (
    FIXTURE_DIR / "wellbore_terminal_quote.csv"
)


def _write_p4(path: Path, *, compressed: bool = False) -> Path:
    content = b"".join(
        bytes.fromhex(value) for value in P4_FIXTURE["records_hex"]
    )
    assert all(
        len(bytes.fromhex(value)) == rrc.P4_RECORD_LENGTH
        for value in P4_FIXTURE["records_hex"]
    )
    if compressed:
        with gzip.open(path, "wb") as handle:
            handle.write(content)
    else:
        path.write_bytes(content)
    return path


def test_verified_contracts_expose_real_source_windows_and_no_ceiling():
    assert rrc.SOURCE_CONTRACTS["p4"]["live_validation"] == {
        "filename": "p4f606.ebc.gz",
        "compressed_bytes": 207_592_761,
        "uncompressed_bytes": 2_787_886_120,
        "record_count": 30_303_110,
        "sha256": PROVENANCE["p4"]["sha256"],
    }
    assert (
        rrc.SOURCE_CONTRACTS["wellbore"]["live_validation"]["bytes"]
        == 496_557_360
    )
    assert (
        rrc.SOURCE_CONTRACTS["wellbore"]["live_validation"][
            "record_count"
        ]
        == 1_368_247
    )
    assert (
        rrc.SOURCE_CONTRACTS["wellbore"]["live_validation"][
            "physical_line_count_including_report_footer"
        ]
        == 1_368_263
    )
    assert (
        rrc.SOURCE_CONTRACTS["wellbore"]["live_validation"][
            "range_request_returned_complete_artifact"
        ]
        is True
    )
    assert rrc.SOURCE_CONTRACTS["p4"]["record_ids"]["30"] == (
        "p4_severance_fee_payment"
    )
    assert all(
        contract["source_result_ceiling"] is None
        for contract in rrc.SOURCE_CONTRACTS.values()
    )


def test_parsers_have_no_default_result_cap():
    args = rrc.build_parser().parse_args(
        [
            "p4",
            "p4f606.ebc.gz",
            "--oil-gas",
            "O",
            "--district",
            "06",
        ]
    )

    assert args.limit is None
    assert args.offset == 0


def test_godrive_listing_prefers_newest_dated_wellbore_not_stale_alias():
    html_text = (FIXTURE_DIR / "godrive_listing.html").read_text(
        encoding="utf-8"
    )

    entries, view_state = rrc.parse_godrive_listing(html_text)
    selected = rrc.preferred_release("wellbore", entries)

    assert view_state == "fixture-view-state"
    assert len(entries) == 3
    assert selected.filename == "OG_WELLBORE_EWA_Report_2026-07-02.csv"
    assert selected.index == 71
    assert selected.modified_at == "2026-07-02T10:00:54"
    assert entries[0].filename == "OG_WELLBORE_EWA_Report.csv"
    assert entries[0] != selected


def test_godrive_client_uses_repository_system_trust_session(monkeypatch):
    session = object()
    monkeypatch.setattr(rrc, "system_trust_session", lambda: session)

    client = rrc.RRCGoDriveClient()

    assert client.session is session


def test_p5_ascii_handles_removed_filler_and_preserves_source_lines():
    organizations = list(rrc.iter_p5_organizations(P5_FIXTURE))
    indexed = {item["p5_number"]: item for item in organizations}

    assert len(organizations) == 6
    assert indexed["830589"]["organization_name"] == (
        "SUPREME ENERGY COMPANY, INC."
    )
    assert indexed["830589"]["status"] == "active"
    assert indexed["224830"]["status"] == "inactive"
    assert indexed["250920"]["status"] == "delinquent"
    assert indexed["830589"]["source_record_length"] == 334
    assert indexed["028612"]["source_record_length"] == 303
    assert indexed["028612"]["organization_name"] == "APR OPERATING LLC"
    assert indexed["830589"]["evidence"]["raw_text"].startswith(
        "A 830589SUPREME"
    )
    assert indexed["830589"]["evidence"]["raw_hex"].startswith("412038")


def test_p5_ascii_variant_preserves_observed_extended_and_control_bytes(
    tmp_path,
):
    source = next(
        line
        for line in P5_FIXTURE.read_bytes().splitlines()
        if line.startswith(b"A 830589")
    )
    raw = bytearray(source)
    observation = PROVENANCE["p5"]["extended_byte_observation"]
    raw[303:306] = b"\x00\x00\xf4"
    fixture_path = tmp_path / "orf850.txt"
    fixture_path.write_bytes(bytes(raw) + b"\r\n")

    organizations = list(rrc.iter_p5_organizations(fixture_path))

    assert len(organizations) == 1
    record = organizations[0]
    assert record["p5_number"] == "830589"
    assert record["organization_name"] == "SUPREME ENERGY COMPANY, INC."
    assert record["source_encoding"] == "latin-1-byte-preserving"
    assert record["evidence"]["raw_hex"][606:612] == "0000f4"
    assert observation["zero_byte_offsets"] == [303, 304]


def test_p5_ebcdic_uses_published_350_byte_framing(tmp_path):
    ascii_record = next(
        line
        for line in P5_FIXTURE.read_text(encoding="ascii").splitlines()
        if line.startswith("A 830589")
    )
    record = ascii_record.ljust(rrc.P5_EBCDIC_RECORD_LENGTH).encode(
        "cp037"
    )
    fixture_path = tmp_path / "orf850.ebc.gz"
    with gzip.open(fixture_path, "wb") as handle:
        handle.write(record)

    organizations = list(rrc.iter_p5_organizations(fixture_path))

    assert len(organizations) == 1
    assert organizations[0]["p5_number"] == "830589"
    assert organizations[0]["source_encoding"] == "cp037"
    assert organizations[0]["source_record_length"] == 350


def test_p4_streaming_group_reconstructs_operator_history_and_name(tmp_path):
    fixture_path = _write_p4(
        tmp_path / "p4f606.ebc.gz",
        compressed=True,
    )

    groups = list(rrc.iter_p4_groups(fixture_path))

    assert len(groups) == 1
    group = groups[0]
    lease = group["lease"]
    assert lease["oil_gas_code"] == "O"
    assert lease["district"] == "06"
    assert lease["lease_id"] == "004411"
    assert lease["current_field_number"] == "16481001"
    assert lease["current_operator_number"] == "830589"
    assert group["current_lease_name"] == "7-11 RANCH -B-"

    events = group["operator_history"]
    assert [event["sequence_date"] for event in events] == [
        "2017-03-22",
        "2016-10-04",
        "1977-06-23",
    ]
    assert events[0]["effective_date"] == "2017-02-01"
    assert events[0]["change_flags"]["change_of_operator"] is True
    assert events[0]["operator_number"] == "830589"
    assert events[0]["operator_number_basis"] == "p4_root_current"
    assert events[1]["operator_number"] == "699848"
    assert events[1]["operator_number_basis"] == "p4_info_history"
    assert events[2]["operator_number"] == "224830"
    assert all(event["lease_name"] == "7-11 RANCH -B-" for event in events)

    relationship = events[0]["gatherer_purchaser_nominator"][0]
    assert relationship["role"] == "gatherer"
    assert relationship["p5_number"] == "667883"
    assert (
        len(events[0]["evidence"]["raw_hex"])
        == rrc.P4_RECORD_LENGTH * 2
    )


def test_p4_rejects_a_trailing_partial_fixed_record(tmp_path):
    fixture_path = _write_p4(tmp_path / "p4f606.ebc")
    with fixture_path.open("ab") as handle:
        handle.write(b"\xf0")

    with pytest.raises(rrc.RRCLayoutError, match="partial 92-byte"):
        list(rrc.iter_p4_groups(fixture_path))


def test_p4_preserves_complete_file_auxiliary_records(tmp_path):
    fixture_path = _write_p4(tmp_path / "p4f606.ebc")
    sentinel = PROVENANCE["p4"]["complete_record_sentinel"]
    with fixture_path.open("ab") as handle:
        handle.write(bytes.fromhex(sentinel["raw_hex"]))

    group = next(rrc.iter_p4_groups(fixture_path))

    auxiliary = group["complete_p4_auxiliary_records"]
    assert len(auxiliary) == 1
    assert auxiliary[0]["record_id"] == sentinel["record_id"]
    assert auxiliary[0]["record_type"] == sentinel["record_type"]
    assert auxiliary[0]["evidence"]["raw_hex"] == sentinel["raw_hex"]


def test_wellbore_stream_validates_headerless_59_column_layout():
    records = list(rrc.iter_wellbores(WELLBORE_FIXTURE))

    assert len(records) == 2
    first = records[0]
    assert first["api_number"] == "00100001"
    assert first["api_number_10"] == "4200100001"
    assert first["api_display"] == "42-001-00001"
    assert first["lease_id"] == "004411"
    assert first["lease_key"] == "O:06:004411"
    assert first["operator_number"] == "830589"
    assert first["county_name"] == "ANDERSON"
    assert first["water_land_code"] == "Land Well"
    assert len(first["native"]) == 59
    assert first["evidence"]["raw_text"].startswith('"06","001"')

    apr = records[1]
    assert apr["operator_number"] == "028612"
    assert apr["operator_name"] == "APR OPERATING LLC"
    assert apr["lease_key"] == "O:08:048522"


def test_wellbore_rejects_column_count_drift(tmp_path):
    malformed = tmp_path / "wellbore.csv"
    malformed.write_text('"06","001","00100001"\n', encoding="ascii")

    with pytest.raises(rrc.RRCLayoutError, match="has 3 fields; expected 59"):
        list(rrc.iter_wellbores(malformed))


def test_wellbore_recovers_observed_terminal_quote_layout_anomaly():
    records = list(
        rrc.iter_wellbores(WELLBORE_TERMINAL_QUOTE_FIXTURE)
    )

    assert len(records) == 1
    record = records[0]
    assert record["well_number_display"] == '2023H"'
    assert record["well_number"] == '2023H"'
    assert len(record["native"]) == 59
    assert record["evidence"]["csv_layout_recovery"] == (
        "quoted_field_boundary_recovery"
    )


def test_wellbore_validates_and_stops_at_observed_report_footer(tmp_path):
    fixture_path = tmp_path / "wellbore-with-footer.csv"
    fixture_path.write_bytes(
        WELLBORE_FIXTURE.read_bytes()
        + b"\n2 rows selected.\n\n"
        + b"*****************************************************\n"
    )

    records = list(rrc.iter_wellbores(fixture_path))

    assert len(records) == 2


def test_wellbore_rejects_report_footer_count_drift(tmp_path):
    fixture_path = tmp_path / "wellbore-with-footer.csv"
    fixture_path.write_bytes(
        WELLBORE_FIXTURE.read_bytes() + b"\n3 rows selected.\n"
    )

    with pytest.raises(
        rrc.RRCLayoutError,
        match="footer count 3 differs from parsed row count 2",
    ):
        list(rrc.iter_wellbores(fixture_path))


def test_resolve_joins_only_by_exact_p5_number_and_labels_name_comparison(
    tmp_path,
):
    p4_path = _write_p4(tmp_path / "p4f606.ebc")
    args = rrc.build_parser().parse_args(
        [
            "resolve",
            "--p4",
            str(p4_path),
            "--p5",
            str(P5_FIXTURE),
            "--wellbore",
            str(WELLBORE_FIXTURE),
            "--oil-gas",
            "O",
            "--district",
            "06",
            "--lease-id",
            "04411",
        ]
    )

    records = list(
        rrc.resolve_records(
            p4_path,
            P5_FIXTURE,
            WELLBORE_FIXTURE,
            args,
        )
    )

    assert len(records) == 1
    record = records[0]
    assert record["current_operator"]["p5_number"] == "830589"
    assert record["current_operator_identity_match"] == {
        "basis": "exact_p5_number",
        "p5_number": "830589",
        "name_comparison": "not_available",
        "source_name_normalized": None,
        "p5_name_normalized": "SUPREME ENERGY COMPANY INC",
        "text_heuristic_used": False,
    }
    assert record["operator_history"][1]["operator"]["p5_number"] == "699848"
    assert record["join"]["wellbore_match_count"] == 1
    well = record["wellbores"][0]
    assert well["api_number"] == "00100001"
    assert well["operator_matches_p4_current"] is True
    assert well["operator_identity_match"]["basis"] == "exact_p5_number"
    assert (
        well["operator_identity_match"]["name_comparison"]
        == "exact_normalized"
    )
    assert well["operator_identity_match"]["text_heuristic_used"] is False


def test_assignment_party_sentinels_distinguish_exact_and_heuristic_matches():
    exact, heuristic = PROVENANCE["identity_sentinels"]

    assert exact["recorder_party"] == "APR OPERATING LLC"
    assert exact["p5_number"] == exact["wellbore_operator_number"]
    assert exact["match_basis"] == "exact_p5_number_and_normalized_name"
    assert heuristic["recorder_party"] == (
        "THREE RIVERS OPERATING CO III LLC"
    )
    assert heuristic["match_basis"] == "text_heuristic_candidate_only"
    assert heuristic["automatic_join_performed"] is False


def test_cli_caller_window_is_explicit_and_output_remains_valid_json(
    tmp_path,
):
    output_path = tmp_path / "p5.json"

    exit_code = rrc.main(
        [
            "p5",
            str(P5_FIXTURE),
            "--limit",
            "1",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 1
    assert payload["summary"] == {
        "has_more": True,
        "matched_before_window_stop": 2,
        "returned": 1,
    }
