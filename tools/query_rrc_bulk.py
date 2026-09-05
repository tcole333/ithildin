#!/usr/bin/env python3
"""Discover, download, parse, and join Texas RRC public bulk records.

The Railroad Commission publishes three complementary statewide files:

* P-4: 92-byte EBCDIC records containing lease and operator history.
* P-5: 350-byte EBCDIC records or CRLF-delimited ASCII records containing
  organization identities and status.
* Wellbore Query: a headerless, 59-column CSV snapshot containing well, API,
  lease, operator, county, and well-location fields.

The parsers are generators and have no built-in result cap. ``--limit`` and
``--offset`` are caller-selected output windows. Raw source records and native
record locators are retained with every normalized record.

Examples:
    uv run python tools/query_rrc_bulk.py releases wellbore --output /tmp/releases.json
    uv run python tools/query_rrc_bulk.py download p5 /tmp/rrc --output /tmp/download.json
    uv run python tools/query_rrc_bulk.py p5 /tmp/orf850.txt.gz \
        --p5-number 830589 --output /tmp/operator.json
    uv run python tools/query_rrc_bulk.py p4 /tmp/p4f606.ebc.gz \
        --oil-gas O --district 06 --lease-id 04411 --output /tmp/history.json
    uv run python tools/query_rrc_bulk.py wellbore /tmp/OG_WELLBORE_EWA_Report.csv \
        --api 00100001 --output /tmp/well.json
    uv run python tools/query_rrc_bulk.py resolve \
        --p4 /tmp/p4f606.ebc.gz --p5 /tmp/orf850.txt.gz \
        --wellbore /tmp/OG_WELLBORE_EWA_Report.csv \
        --oil-gas O --district 06 --lease-id 04411 \
        --output /tmp/resolved.json
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, BinaryIO, TextIO

try:
    from tools.public_records_http import system_trust_session
except ImportError:
    from public_records_http import system_trust_session


P4_SOURCE_ID = "us-tx-rrc-p4-bulk"
P5_SOURCE_ID = "us-tx-rrc-p5-bulk"
WELLBORE_SOURCE_ID = "us-tx-rrc-wellbore-bulk"

DATASETS_PAGE = (
    "https://www.rrc.texas.gov/resource-center/research/"
    "data-sets-available-for-download/"
)
P4_MANUAL_URL = (
    "https://www.rrc.texas.gov/media/wdmjsoph/"
    "p4-user-manual_p4a002_feb2015.pdf"
)
P5_MANUAL_URL = (
    "https://www.rrc.texas.gov/media/jtqfynn3/"
    "ora001_p5_manual_october-2014.pdf"
)
WELLBORE_MANUAL_URL = (
    "https://www.rrc.texas.gov/media/di1mm5or/"
    "og_wellbore_ewadefinitionmanual2013-10-30_subscription.pdf"
)

SHARE_URLS = {
    "p4": "https://mft.rrc.texas.gov/link/19f9b9c7-2b82-4d7c-8dbd-77145a86d3de",
    "p5": "https://mft.rrc.texas.gov/link/04652169-eed6-4396-9019-2e270e790f6c",
    "wellbore": (
        "https://mft.rrc.texas.gov/link/"
        "650649b7-e019-4d77-a8e0-d118d6455381"
    ),
}
GODRIVE_FORM_URL = (
    "https://mft.rrc.texas.gov/webclient/godrive/PublicGoDrive.xhtml"
)

P4_RECORD_LENGTH = 92
P5_EBCDIC_RECORD_LENGTH = 350
VERIFIED_AT = "2026-07-29"

SOURCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "p4": {
        "source_id": P4_SOURCE_ID,
        "share_url": SHARE_URLS["p4"],
        "manual_url": P4_MANUAL_URL,
        "update_window": "monthly; available by the 27th",
        "release_kind": "current snapshot containing historical P-4 filings",
        "filename_pattern": "p4f606.ebc.gz",
        "record_length_bytes": P4_RECORD_LENGTH,
        "encoding": "EBCDIC cp037 display fields with packed-decimal root fields",
        "record_ids": {
            "01": "lease_root",
            "02": "p4_information",
            "03": "gatherer_purchaser_nominator",
            "04": "filing_remark",
            "05": "lease_pointer",
            "06": "p4_lease_restriction",
            "07": "lease_name",
            "08": "p4_lease_remark",
            "09": "severance",
            "10": "severance_remark",
            "11": "gas_schedule",
            "12": "gas_schedule_cycle",
            "13": "gas_problem_letter_section",
            "14": "gas_problem_letter_date",
            "15": "oil_schedule",
            "16": "oil_schedule_cycle",
            "17": "oil_problem_letter_section",
            "18": "oil_problem_letter_date",
            "19": "oil_yates_unit_cycle",
            "20": "schedule_unit",
            "21": "unit_reporting_cycle",
            "22": "unit_previous_allowable",
            "23": "unit_remark",
            "24": "lease_exception",
            "25": "commingle_permit_pointer",
            "26": "form_p17_exception_date",
            "27": "p4_fee_received",
            "28": "p4_check_register",
            "29": "p4_severance_fee",
            "30": "p4_severance_fee_payment",
        },
        "live_validation": {
            "filename": "p4f606.ebc.gz",
            "compressed_bytes": 207_592_761,
            "uncompressed_bytes": 2_787_886_120,
            "record_count": 30_303_110,
            "sha256": (
                "530629ea3cb16f9574fd0a9cb711318c57296001ad2467c45496d"
                "9995fbe5708"
            ),
        },
        "source_result_ceiling": None,
    },
    "p5": {
        "source_id": P5_SOURCE_ID,
        "share_url": SHARE_URLS["p5"],
        "manual_url": P5_MANUAL_URL,
        "update_window": "monthly; available by the 25th",
        "release_kind": "current snapshot of active and inactive organizations",
        "filename_patterns": ["orf850.txt.gz", "orf850.ebc.gz"],
        "record_length_bytes": P5_EBCDIC_RECORD_LENGTH,
        "observed_ascii_framing": (
            "CRLF-delimited records with trailing filler removed; "
            "organization A records are currently 334 content characters "
            "(336 bytes including CRLF)"
        ),
        "observed_ascii_bytes": (
            "ASCII-compatible single-byte records with isolated extended "
            "and control bytes; parsed with a byte-preserving Latin-1 decode"
        ),
        "live_validation": {
            "filename": "orf850.txt.gz",
            "compressed_bytes": 19_489_800,
            "uncompressed_bytes": 120_902_504,
            "sha256": (
                "dd45052b32545854b06e9f97dbf9f1db34bd0c856b3e4dca8cdb"
                "77a220507989"
            ),
        },
        "source_result_ceiling": None,
    },
    "wellbore": {
        "source_id": WELLBORE_SOURCE_ID,
        "share_url": SHARE_URLS["wellbore"],
        "manual_url": WELLBORE_MANUAL_URL,
        "update_window": "monthly; available the second working day",
        "release_kind": "dated statewide snapshot",
        "filename_pattern": "OG_WELLBORE_EWA_Report_YYYY-MM-DD.csv",
        "format": "headerless quoted CSV with 59 fields",
        "archive_window_observed": "dated monthly files from 2020-09 onward",
        "http_range_behavior_observed": (
            "GoDrive download returned HTTP 200 and the complete object "
            "when a byte range was requested"
        ),
        "live_validation": {
            "filename": "OG_WELLBORE_EWA_Report_2026-07-02.csv",
            "bytes": 496_557_360,
            "record_count": 1_368_247,
            "physical_line_count_including_report_footer": 1_368_263,
            "report_footer_row_count": 1_368_247,
            "sha256": (
                "1a39f0a87cb48662e2ac7e5a1a203785e15f772d02f23cbc6bf04"
                "cd34c14d7f3"
            ),
            "range_request_status": 200,
            "range_request_returned_complete_artifact": True,
        },
        "source_result_ceiling": None,
    },
}

TAPE_TO_RRC_DISTRICT = {
    "01": "01",
    "02": "02",
    "03": "03",
    "04": "04",
    "05": "05",
    "06": "06",
    "07": "6E",
    "08": "7B",
    "09": "7C",
    "10": "08",
    "11": "8A",
    "12": "8B",
    "13": "09",
    "14": "10",
}

P4_CHANGE_FLAGS = (
    "new_well",
    "change_of_gatherer",
    "change_of_purchaser",
    "change_of_nominator",
    "change_of_purchaser_system",
    "change_of_field",
    "change_of_operator",
    "change_of_lease_name",
    "consolidation",
    "subdivision",
    "reclassification",
    "special_form_filed",
    "oil_field_transfer",
)

P4_RECORD_TYPES = {
    "O": "original_questionnaire",
    "D": "dummy",
    "R": "regular",
    "A": "automatic_change",
    "T": "filed_on_tape",
    "B": "bridged",
}

P4_COMPLETE_RECORD_TYPES = {
    "06": "p4_lease_restriction",
    "08": "p4_lease_remark",
    "09": "severance",
    "10": "severance_remark",
    "11": "gas_schedule",
    "12": "gas_schedule_cycle",
    "13": "gas_problem_letter_section",
    "14": "gas_problem_letter_date",
    "15": "oil_schedule",
    "16": "oil_schedule_cycle",
    "17": "oil_problem_letter_section",
    "18": "oil_problem_letter_date",
    "19": "oil_yates_unit_cycle",
    "20": "schedule_unit",
    "21": "unit_reporting_cycle",
    "22": "unit_previous_allowable",
    "23": "unit_remark",
    "24": "lease_exception",
    "25": "commingle_permit_pointer",
    "26": "form_p17_exception_date",
    "27": "p4_fee_received",
    "28": "p4_check_register",
    "29": "p4_severance_fee",
    "30": "p4_severance_fee_payment",
}

P5_STATUS = {
    "A": "active",
    "I": "inactive",
    "D": "delinquent",
    "S": "see_remarks",
}

P5_ORGANIZATION_TYPES = {
    "A": "corporation",
    "B": "limited_partnership",
    "C": "sole_proprietor",
    "D": "partnership",
    "E": "trust",
    "F": "joint_venture",
    "G": "other",
}

WELLBORE_FIELDS = (
    "DISTRICT",
    "COUNTY_CODE",
    "API_NO",
    "COUNTY_NAME",
    "OIL_GAS_CODE",
    "LEASE_NAME",
    "FIELD_NUMBER",
    "FIELD_NAME",
    "LEASE_NUMBER",
    "WELL_NO_DISPLAY",
    "OIL_UNIT_NUMBER",
    "OPERATOR_NAME",
    "OPERATOR_NUMBER",
    "WB_WATER_LAND_CODE",
    "MULTI_COMP_FLAG",
    "API_DEPTH",
    "WB_SHUT_IN_DATE",
    "WB_14B2_FLAG",
    "WELL_TYPE_NAME",
    "WL_SHUT_IN_DATE",
    "PLUG_DATE",
    "PLUG_LEASE_NAME",
    "PLUG_OPERATOR_NAME",
    "RECENT_PERMIT",
    "RECENT_PERMIT_LEASE_NAME",
    "RECENT_PERMIT_OPERATOR_NO",
    "ON_SCHEDULE",
    "OG_WELLBORE_EWA_ID",
    "W2-G1_FILED_DATE",
    "W2_G1_DATE",
    "COMPLETION_DATE",
    "W3_FILE_DATE",
    "CREATED_BY",
    "CREATED_DT",
    "MODIFIED_BY",
    "MODIFIED_DT",
    "WELL_NO",
    "P5_RENEWAL_MONTH",
    "P5_RENEWAL_YEAR",
    "P5_ORG_STATUS",
    "CURR_INACT_YRS",
    "CURR_INACT_MOS",
    "WL_14B2_EXT_STATUS",
    "WL_14B2_MECH_INTEG",
    "WL_14B2_PLG_ORD_SF",
    "WL_14B2_POLLUTION",
    "WL_14B2_FLDOPS_HOLD",
    "WL_14B2_H15_PROB",
    "WL_14B2_H15_DELQ",
    "WL_14B2_OPER_DELQ",
    "WL_14B2_DIST_SFP",
    "WL_14B2_DIST_SF_CLNUP",
    "WL_14B2_DIST_ST_PLG",
    "WL_14B2_GOOD_FAITH",
    "WL_14B2_WELL_OTHER",
    "SURF_EQP_VIOL",
    "W3X_VIOL",
    "H15_STATUS_CODE",
    "ORIG_COMPLETION_DT",
)

_WELLBORE_RELEASE_RE = re.compile(
    r"^OG_WELLBORE_EWA_Report_(\d{4}-\d{2}-\d{2})\.csv$",
    re.IGNORECASE,
)
_CONTENT_DISPOSITION_NAME_RE = re.compile(
    r'filename="([^"]+)"',
    re.IGNORECASE,
)


class RRCBulkError(RuntimeError):
    """Base error for an RRC bulk source or layout failure."""


class RRCLayoutError(RRCBulkError):
    """A source record does not match its published layout."""


class RRCDownloadError(RRCBulkError):
    """The official bulk-share transfer did not match the selected artifact."""


@dataclass(frozen=True)
class GoDriveEntry:
    """One file row in an RRC GoDrive public share."""

    index: int
    filename: str
    modified_display: str
    size_display: str
    row_key: str | None = None
    modified_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "filename": self.filename,
            "modified_display": self.modified_display,
            "modified_at": self.modified_at,
            "size_display": self.size_display,
            "row_key": self.row_key,
        }


class _GoDriveHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[GoDriveEntry] = []
        self.view_state: str | None = None
        self._row: dict[str, Any] | None = None
        self._cell: str | None = None
        self._link_index: int | None = None
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        values = dict(attrs)
        if (
            tag == "input"
            and values.get("name") == "javax.faces.ViewState"
            and values.get("value")
        ):
            self.view_state = values["value"]
        if tag == "tr" and values.get("data-ri") is not None:
            self._row = {
                "index": int(values["data-ri"] or 0),
                "row_key": values.get("data-rk"),
            }
        if self._row is None:
            return
        if tag == "td":
            class_name = values.get("class") or ""
            if "NameColumn" in class_name:
                self._cell = "filename"
            elif "ModifiedOnColumn" in class_name:
                self._cell = "modified_display"
            elif "SizeColumn" in class_name:
                self._cell = "size_display"
            else:
                self._cell = None
            self._text = []
        elif tag == "a":
            match = re.fullmatch(
                r"fileTable:(\d+):j_id_2f",
                values.get("id") or "",
            )
            if match:
                self._link_index = int(match.group(1))

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._cell is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "a":
            self._link_index = None
        elif tag == "td":
            if self._cell:
                self._row[self._cell] = "".join(self._text).strip()
            self._cell = None
            self._text = []
        elif tag == "tr":
            filename = str(self._row.get("filename") or "").strip()
            modified = str(
                self._row.get("modified_display") or ""
            ).strip()
            size = str(self._row.get("size_display") or "").strip()
            if filename:
                modified_at = _parse_listing_datetime(modified)
                self.entries.append(
                    GoDriveEntry(
                        index=int(self._row["index"]),
                        filename=filename,
                        modified_display=modified,
                        size_display=size,
                        row_key=self._row.get("row_key"),
                        modified_at=modified_at,
                    )
                )
            self._row = None


def _parse_listing_datetime(value: str) -> str | None:
    try:
        parsed = datetime.strptime(value, "%m/%d/%y %I:%M:%S %p")
    except ValueError:
        return None
    return parsed.isoformat()


def parse_godrive_listing(html_text: str) -> tuple[list[GoDriveEntry], str]:
    """Parse the file rows and JSF view state from an RRC public share."""
    parser = _GoDriveHTMLParser()
    parser.feed(html_text)
    if not parser.entries:
        raise RRCLayoutError("RRC GoDrive listing contains no file rows")
    if not parser.view_state:
        raise RRCLayoutError("RRC GoDrive listing lacks JSF view state")
    return parser.entries, parser.view_state


def preferred_release(
    source: str,
    entries: Sequence[GoDriveEntry],
) -> GoDriveEntry:
    """Select the parser-preferred current artifact from a live listing."""
    if source == "p4":
        expected = "p4f606.ebc.gz"
        matches = [item for item in entries if item.filename == expected]
    elif source == "p5":
        expected = "orf850.txt.gz"
        matches = [item for item in entries if item.filename == expected]
    else:
        dated: list[tuple[str, GoDriveEntry]] = []
        for item in entries:
            match = _WELLBORE_RELEASE_RE.fullmatch(item.filename)
            if match:
                dated.append((match.group(1), item))
        matches = [max(dated, key=lambda value: value[0])[1]] if dated else []
        expected = "latest dated Wellbore snapshot"
    if not matches:
        raise RRCLayoutError(
            f"RRC {source} listing lacks {expected}"
        )
    return matches[0]


class RRCGoDriveClient:
    """Small client for the official RRC GoDrive public shares."""

    def __init__(
        self,
        *,
        timeout: float = 120.0,
        session: Any | None = None,
    ) -> None:
        self.timeout = timeout
        self.session = (
            session if session is not None else system_trust_session()
        )

    def list(self, source: str) -> tuple[list[GoDriveEntry], str]:
        response = self.session.get(
            SHARE_URLS[source],
            headers={"User-Agent": "Ithildin-RRC-Bulk/1"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return parse_godrive_listing(response.text)

    def download(
        self,
        source: str,
        destination: str | Path,
        *,
        filename: str | None = None,
        replace: bool = False,
    ) -> dict[str, Any]:
        entries, view_state = self.list(source)
        selected = (
            next(
                (item for item in entries if item.filename == filename),
                None,
            )
            if filename
            else preferred_release(source, entries)
        )
        if selected is None:
            raise RRCDownloadError(
                f"RRC {source} listing has no file named {filename}"
            )

        destination_path = Path(destination).expanduser()
        if destination_path.exists() and destination_path.is_dir():
            destination_path = destination_path / selected.filename
        elif str(destination).endswith(os.sep):
            destination_path = destination_path / selected.filename
        if destination_path.exists() and not replace:
            raise FileExistsError(destination_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        field = f"fileTable:{selected.index}:j_id_2f"
        response = self.session.post(
            GODRIVE_FORM_URL,
            data={
                "fileList": "fileList",
                field: field,
                "fileList_SUBMIT": "1",
                "javax.faces.ViewState": view_state,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Ithildin-RRC-Bulk/1",
            },
            timeout=self.timeout,
            stream=True,
            allow_redirects=True,
        )
        response.raise_for_status()
        hasher = hashlib.sha256()
        byte_count = 0
        temporary_path: Path | None = None
        try:
            with response:
                disposition = response.headers.get(
                    "Content-Disposition",
                    "",
                )
                match = _CONTENT_DISPOSITION_NAME_RE.search(disposition)
                response_filename = match.group(1) if match else None
                if response_filename != selected.filename:
                    raise RRCDownloadError(
                        "RRC download response filename differs from "
                        f"selection: {response_filename!r}"
                    )
                with tempfile.NamedTemporaryFile(
                    prefix=f".{destination_path.name}.",
                    suffix=".part",
                    dir=destination_path.parent,
                    delete=False,
                ) as handle:
                    temporary_path = Path(handle.name)
                    for chunk in response.iter_content(1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        hasher.update(chunk)
                        byte_count += len(chunk)
            temporary_path.replace(destination_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return {
            "source": source,
            "source_id": SOURCE_CONTRACTS[source]["source_id"],
            "filename": selected.filename,
            "path": str(destination_path.resolve()),
            "bytes": byte_count,
            "sha256": hasher.hexdigest(),
            "listing": selected.to_dict(),
        }


def _clean(value: str) -> str | None:
    text = value.strip()
    return text or None


def _digits(value: str) -> str | None:
    text = value.strip()
    if not text or not text.isdigit() or set(text) == {"0"}:
        return None
    return text


def _iso_date(value: str) -> str | None:
    text = value.strip()
    if len(text) != 8 or not text.isdigit() or set(text) == {"0"}:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _complement_date(value: str) -> str | None:
    text = value.strip()
    if len(text) != 8 or not text.isdigit():
        return None
    original = f"{99_999_999 - int(text):08d}"
    return _iso_date(original)


def _rrc_district_from_tape(value: str) -> str:
    native = value.strip()
    return TAPE_TO_RRC_DISTRICT.get(native, native)


def normalize_lease_id(value: str) -> str:
    text = value.strip()
    return text.zfill(6) if text.isdigit() else text


def _api_fields(value: str) -> dict[str, str | None]:
    native = value.strip()
    if len(native) != 8 or not native.isdigit():
        return {
            "api_number": native or None,
            "api_number_10": None,
            "api_display": None,
        }
    return {
        "api_number": native,
        "api_number_10": f"42{native}",
        "api_display": f"42-{native[:3]}-{native[3:]}",
    }


def _source_evidence(
    source_id: str,
    path: Path,
    record_number: int,
    *,
    byte_offset: int,
    raw_hex: str | None = None,
    raw_text: str | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "source_id": source_id,
        "source_path": str(path.resolve()),
        "record_number": record_number,
        "uncompressed_byte_offset": byte_offset,
    }
    if raw_hex is not None:
        evidence["raw_hex"] = raw_hex
    if raw_text is not None:
        evidence["raw_text"] = raw_text
    return evidence


@contextmanager
def _open_binary(path: Path) -> Iterator[BinaryIO]:
    with path.open("rb") as raw:
        magic = raw.read(2)
        raw.seek(0)
        if magic == b"\x1f\x8b":
            with gzip.GzipFile(fileobj=raw, mode="rb") as handle:
                yield handle
        else:
            yield raw


def _ebcdic(raw: bytes, start: int, end: int) -> str:
    return raw[start:end].decode("cp037").strip()


def _record_id(raw: bytes) -> str:
    return _ebcdic(raw, 0, 2)


def _parse_p4_root(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    oil_gas = _ebcdic(raw, 2, 3)
    tape_district = _ebcdic(raw, 3, 5)
    lease_id = _ebcdic(raw, 5, 11)
    return {
        "record_type": "lease_root",
        "oil_gas_code": oil_gas,
        "district": _rrc_district_from_tape(tape_district),
        "district_tape_code": tape_district,
        "lease_id": lease_id,
        "lease_key": f"{oil_gas}:{_rrc_district_from_tape(tape_district)}:{lease_id}",
        "current_field_number": _digits(_ebcdic(raw, 11, 19)),
        "on_schedule": _ebcdic(raw, 19, 20) == "N",
        "native_on_off_schedule_indicator": _ebcdic(raw, 19, 20),
        "current_operator_number": _digits(_ebcdic(raw, 20, 26)),
        "remove_from_schedule_reason": _clean(_ebcdic(raw, 26, 28)),
        "remove_from_schedule_date": _iso_date(_ebcdic(raw, 28, 36)),
        "stock_on_hand_indicator": _clean(_ebcdic(raw, 36, 37)),
        "schedule_sequence_key_native": _ebcdic(raw, 37, 45),
        "pending_lease_removal": _ebcdic(raw, 45, 46) == "Y",
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_p4_info(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    flags_native = _ebcdic(raw, 34, 47)
    flags = {
        name: (
            flags_native[index] == "Y"
            if index < len(flags_native)
            else False
        )
        for index, name in enumerate(P4_CHANGE_FLAGS)
    }
    sequence_key = _ebcdic(raw, 2, 10)
    effective_key = _ebcdic(raw, 10, 18)
    record_type_native = _ebcdic(raw, 50, 51)
    return {
        "record_type": "p4_filing",
        "sequence_key_native": sequence_key,
        "sequence_date": _complement_date(sequence_key),
        "effective_key_native": effective_key,
        "effective_date": _iso_date(_ebcdic(raw, 18, 26)),
        "effective_date_from_key": _complement_date(effective_key),
        "approval_date": _iso_date(_ebcdic(raw, 26, 34)),
        "change_flags_native": flags_native,
        "change_flags": flags,
        "filing_type_native": record_type_native,
        "filing_type": P4_RECORD_TYPES.get(record_type_native),
        "p4_info_field_number": _digits(_ebcdic(raw, 51, 59)),
        "p4_info_operator_number": _digits(_ebcdic(raw, 59, 65)),
        "p5_number_filing_on_tape": _digits(_ebcdic(raw, 65, 71)),
        "gatherer_purchaser_nominator": [],
        "remarks": [],
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_implied_decimal(value: str) -> float | None:
    text = value.strip()
    if not text.isdigit():
        return None
    return int(text) / 10_000


def _parse_p4_gpn(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    type_native = _ebcdic(raw, 3, 4)
    return {
        "product_code": _clean(_ebcdic(raw, 2, 3)),
        "role_native": type_native,
        "role": {
            "G": "gatherer",
            "H": "purchaser",
            "I": "nominator",
        }.get(type_native),
        "percentage_key_native": _ebcdic(raw, 4, 9),
        "p5_number": _digits(_ebcdic(raw, 9, 15)),
        "purchaser_system_number": _digits(_ebcdic(raw, 15, 19)),
        "current_p4_filing_native": _ebcdic(raw, 19, 20),
        "actual_percentage": _parse_implied_decimal(
            _ebcdic(raw, 20, 25)
        ),
        "interstate_market": _ebcdic(raw, 25, 26) == "Y",
        "intrastate_market": _ebcdic(raw, 26, 27) == "Y",
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_p4_remark(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    return {
        "remark_number": _clean(_ebcdic(raw, 2, 4)),
        "line_number": _clean(_ebcdic(raw, 4, 6)),
        "remark_date": _iso_date(_ebcdic(raw, 6, 14)),
        "text": _clean(_ebcdic(raw, 14, 80)),
        "hold": _ebcdic(raw, 80, 81) == "Y",
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_p4_pointer(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    effective_key = _ebcdic(raw, 2, 10)
    oil_gas = _ebcdic(raw, 11, 12)
    tape_district = _ebcdic(raw, 12, 14)
    district = _rrc_district_from_tape(tape_district)
    lease_id = _ebcdic(raw, 14, 20)
    return {
        "effective_key_native": effective_key,
        "effective_date": _complement_date(effective_key),
        "direction_native": _ebcdic(raw, 10, 11),
        "oil_gas_code": oil_gas,
        "district": district,
        "district_tape_code": tape_district,
        "lease_id": lease_id,
        "lease_key": f"{oil_gas}:{district}:{lease_id}",
        "reason_native": _ebcdic(raw, 20, 21),
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_p4_name(
    raw: bytes,
    path: Path,
    record_number: int,
) -> dict[str, Any]:
    sequence_key = _ebcdic(raw, 2, 10)
    effective_key = _ebcdic(raw, 10, 18)
    return {
        "sequence_key_native": sequence_key,
        "sequence_date": _complement_date(sequence_key),
        "effective_key_native": effective_key,
        "effective_date": _complement_date(effective_key),
        "lease_name": _clean(_ebcdic(raw, 18, 50)),
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _parse_p4_auxiliary(
    raw: bytes,
    path: Path,
    record_number: int,
    record_id: str,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "record_type": P4_COMPLETE_RECORD_TYPES[record_id],
        "evidence": _source_evidence(
            P4_SOURCE_ID,
            path,
            record_number,
            byte_offset=record_number * P4_RECORD_LENGTH,
            raw_hex=raw.hex(),
        ),
    }


def _lease_name_for_event(
    names: Sequence[Mapping[str, Any]],
    event: Mapping[str, Any],
) -> str | None:
    exact = next(
        (
            item.get("lease_name")
            for item in names
            if item.get("sequence_key_native")
            == event.get("sequence_key_native")
        ),
        None,
    )
    if exact:
        return str(exact)
    event_date = event.get("sequence_date")
    candidates = [
        item
        for item in names
        if item.get("sequence_date")
        and event_date
        and str(item["sequence_date"]) <= str(event_date)
    ]
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: str(item["sequence_date"]))
    return str(selected.get("lease_name") or "") or None


def _finalize_p4_group(group: dict[str, Any]) -> dict[str, Any]:
    root = group["lease"]
    events = group["operator_history"]
    names = group["lease_name_history"]
    dated_names = [
        item for item in names if item.get("sequence_date")
    ]
    current_name = (
        max(dated_names, key=lambda item: str(item["sequence_date"])).get(
            "lease_name"
        )
        if dated_names
        else None
    )
    group["current_lease_name"] = current_name
    for index, event in enumerate(events):
        event["lease_name"] = _lease_name_for_event(names, event)
        native_operator = event.get("p4_info_operator_number")
        if native_operator:
            event["operator_number"] = native_operator
            event["operator_number_basis"] = "p4_info_history"
        elif index == 0 and root.get("current_operator_number"):
            event["operator_number"] = root["current_operator_number"]
            event["operator_number_basis"] = "p4_root_current"
        else:
            event["operator_number"] = None
            event["operator_number_basis"] = None
        native_field = event.get("p4_info_field_number")
        if native_field:
            event["field_number"] = native_field
            event["field_number_basis"] = "p4_info_history"
        elif index == 0 and root.get("current_field_number"):
            event["field_number"] = root["current_field_number"]
            event["field_number_basis"] = "p4_root_current"
        else:
            event["field_number"] = None
            event["field_number_basis"] = None
        event["event_key"] = (
            f"{root['lease_key']}:{event['sequence_key_native']}"
        )
    return group


def _p4_lease_key(raw: bytes) -> str:
    oil_gas = _ebcdic(raw, 2, 3)
    tape_district = _ebcdic(raw, 3, 5)
    lease_id = _ebcdic(raw, 5, 11)
    return (
        f"{oil_gas}:{_rrc_district_from_tape(tape_district)}:{lease_id}"
    )


def iter_p4_groups(
    path: str | Path,
    *,
    lease_key: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream normalized P-4 lease groups from EBCDIC or EBCDIC-gzip."""
    source_path = Path(path)
    current: dict[str, Any] | None = None
    current_event: dict[str, Any] | None = None
    root_seen = False
    child_record_ids = {
        "02",
        "03",
        "04",
        "05",
        "07",
        *P4_COMPLETE_RECORD_TYPES,
    }
    with _open_binary(source_path) as handle:
        record_number = 0
        while True:
            raw = handle.read(P4_RECORD_LENGTH)
            if not raw:
                break
            if len(raw) != P4_RECORD_LENGTH:
                raise RRCLayoutError(
                    "P-4 file ends with a partial 92-byte record at "
                    f"uncompressed offset {record_number * P4_RECORD_LENGTH}"
                )
            record_id = _record_id(raw)
            if record_id == "01":
                if current is not None:
                    yield _finalize_p4_group(current)
                root_seen = True
                current_event = None
                if lease_key is not None and _p4_lease_key(raw) != lease_key:
                    current = None
                    record_number += 1
                    continue
                current = {
                    "source_id": P4_SOURCE_ID,
                    "lease": _parse_p4_root(
                        raw,
                        source_path,
                        record_number,
                    ),
                    "operator_history": [],
                    "lease_pointers": [],
                    "lease_name_history": [],
                    "complete_p4_auxiliary_records": [],
                }
            elif not root_seen:
                raise RRCLayoutError(
                    f"P-4 child record {record_id!r} precedes a root"
                )
            elif current is None:
                if record_id not in child_record_ids:
                    raise RRCLayoutError(
                        "P-4-only file contains unexpected record ID "
                        f"{record_id!r} at record {record_number}"
                    )
            elif record_id == "02":
                current_event = _parse_p4_info(
                    raw,
                    source_path,
                    record_number,
                )
                current["operator_history"].append(current_event)
            elif record_id == "03":
                if current_event is None:
                    raise RRCLayoutError(
                        "P-4 GPN record is not attached to an information record"
                    )
                current_event["gatherer_purchaser_nominator"].append(
                    _parse_p4_gpn(raw, source_path, record_number)
                )
            elif record_id == "04":
                if current_event is None:
                    raise RRCLayoutError(
                        "P-4 remark is not attached to an information record"
                    )
                current_event["remarks"].append(
                    _parse_p4_remark(raw, source_path, record_number)
                )
            elif record_id == "05":
                current["lease_pointers"].append(
                    _parse_p4_pointer(raw, source_path, record_number)
                )
                current_event = None
            elif record_id == "07":
                current["lease_name_history"].append(
                    _parse_p4_name(raw, source_path, record_number)
                )
                current_event = None
            elif record_id in P4_COMPLETE_RECORD_TYPES:
                current["complete_p4_auxiliary_records"].append(
                    _parse_p4_auxiliary(
                        raw,
                        source_path,
                        record_number,
                        record_id,
                    )
                )
            else:
                raise RRCLayoutError(
                    f"P-4-only file contains unexpected record ID {record_id!r} "
                    f"at record {record_number}"
                )
            record_number += 1
    if current is not None:
        yield _finalize_p4_group(current)


def _parse_address(
    padded: str,
    *,
    line1: tuple[int, int],
    line2: tuple[int, int],
    city: tuple[int, int],
    state: tuple[int, int],
    zipcode: tuple[int, int],
    suffix: tuple[int, int],
) -> dict[str, Any]:
    zip_value = padded[slice(*zipcode)].strip()
    zip_suffix = padded[slice(*suffix)].strip()
    return {
        "line1": _clean(padded[slice(*line1)]),
        "line2": _clean(padded[slice(*line2)]),
        "city": _clean(padded[slice(*city)]),
        "state": _clean(padded[slice(*state)]),
        "zip": (
            f"{zip_value}-{zip_suffix}"
            if zip_value and zip_suffix and set(zip_suffix) != {"0"}
            else (zip_value or None)
        ),
    }


def _parse_p5_organization(
    text: str,
    path: Path,
    record_number: int,
    byte_offset: int,
    *,
    source_encoding: str,
    raw_hex: str,
) -> dict[str, Any]:
    if len(text) < 42:
        raise RRCLayoutError(
            f"P-5 organization record {record_number} is shorter than "
            "the status field"
        )
    parsed_text = text.replace("\x00", " ")
    padded = parsed_text.ljust(P5_EBCDIC_RECORD_LENGTH)
    p5_number = padded[2:8]
    status_native = padded[41:42]
    organization_type_native = padded[44:45]
    return {
        "source_id": P5_SOURCE_ID,
        "p5_number": p5_number,
        "organization_key": f"RRC-P5:{p5_number}",
        "organization_name": _clean(padded[8:40]),
        "refiling_required": padded[40:41] == "Y",
        "status_native": status_native,
        "status": P5_STATUS.get(status_native, "other"),
        "hold_mail": padded[42:43] == "H",
        "renewal_letter_code": _clean(padded[43:44]),
        "organization_type_native": organization_type_native,
        "organization_type": P5_ORGANIZATION_TYPES.get(
            organization_type_native,
            "other",
        ),
        "organization_type_other": _clean(padded[45:65]),
        "gatherer_code": _clean(padded[65:70]),
        "mailing_address": _parse_address(
            padded,
            line1=(70, 101),
            line2=(101, 132),
            city=(132, 145),
            state=(145, 147),
            zipcode=(147, 152),
            suffix=(152, 156),
        ),
        "location_address": _parse_address(
            padded,
            line1=(156, 187),
            line2=(187, 218),
            city=(218, 231),
            state=(231, 233),
            zipcode=(233, 238),
            suffix=(238, 242),
        ),
        "date_built": _iso_date(padded[242:250]),
        "date_inactive": _iso_date(padded[250:258]),
        "phone_number": _digits(padded[258:268]),
        "last_p5_received_date": _iso_date(padded[294:302]),
        "emergency_phone_number": _digits(padded[324:334]),
        "source_encoding": source_encoding,
        "source_record_length": len(text),
        "evidence": _source_evidence(
            P5_SOURCE_ID,
            path,
            record_number,
            byte_offset=byte_offset,
            raw_hex=raw_hex,
            raw_text=text,
        ),
    }


def _p5_encoding(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    name = path.name.lower()
    if name.endswith(".gz"):
        name = name[:-3]
    return "cp037" if name.endswith(".ebc") else "ascii"


def iter_p5_organizations(
    path: str | Path,
    *,
    encoding: str = "auto",
) -> Iterator[dict[str, Any]]:
    """Stream P-5 organization ``A `` records from ASCII or EBCDIC files."""
    source_path = Path(path)
    selected_encoding = _p5_encoding(source_path, encoding)
    with _open_binary(source_path) as handle:
        if selected_encoding == "cp037":
            record_number = 0
            while True:
                byte_offset = record_number * P5_EBCDIC_RECORD_LENGTH
                raw = handle.read(P5_EBCDIC_RECORD_LENGTH)
                if not raw:
                    break
                if len(raw) != P5_EBCDIC_RECORD_LENGTH:
                    raise RRCLayoutError(
                        "P-5 EBCDIC file ends with a partial 350-byte "
                        f"record at offset {byte_offset}"
                    )
                text = raw.decode("cp037")
                if text[:2] == "A ":
                    yield _parse_p5_organization(
                        text,
                        source_path,
                        record_number,
                        byte_offset,
                        source_encoding="cp037",
                        raw_hex=raw.hex(),
                    )
                record_number += 1
            return
        if selected_encoding != "ascii":
            raise ValueError(f"unsupported P-5 encoding: {selected_encoding}")
        record_number = 0
        while True:
            byte_offset = handle.tell()
            raw_line = handle.readline()
            if not raw_line:
                break
            raw_record = raw_line.rstrip(b"\r\n")
            text = raw_record.decode("latin-1")
            if text[:2] == "A ":
                yield _parse_p5_organization(
                    text,
                    source_path,
                    record_number,
                    byte_offset,
                    source_encoding="latin-1-byte-preserving",
                    raw_hex=raw_record.hex(),
                )
            record_number += 1


def _wellbore_native_map(row: Sequence[str]) -> dict[str, str]:
    return dict(zip(WELLBORE_FIELDS, row, strict=True))


def _normalize_wellbore(
    row: Sequence[str],
    raw_line: str,
    path: Path,
    record_number: int,
    byte_offset: int,
    *,
    csv_layout_recovery: str | None = None,
) -> dict[str, Any]:
    native = _wellbore_native_map(row)
    oil_gas = native["OIL_GAS_CODE"].strip()
    district = native["DISTRICT"].strip()
    lease_id = normalize_lease_id(native["LEASE_NUMBER"])
    api = _api_fields(native["API_NO"])
    record = {
        "source_id": WELLBORE_SOURCE_ID,
        "wellbore_key": f"RRC-WELLBORE:{api['api_number']}",
        **api,
        "district": district,
        "county_code": _clean(native["COUNTY_CODE"]),
        "county_name": _clean(native["COUNTY_NAME"]),
        "oil_gas_code": oil_gas,
        "lease_id": lease_id,
        "lease_key": f"{oil_gas}:{district}:{lease_id}",
        "lease_number_native": native["LEASE_NUMBER"],
        "lease_name": _clean(native["LEASE_NAME"]),
        "field_number": _clean(native["FIELD_NUMBER"]),
        "field_name": _clean(native["FIELD_NAME"]),
        "well_number": _clean(native["WELL_NO"]),
        "well_number_display": _clean(native["WELL_NO_DISPLAY"]),
        "operator_number": _clean(native["OPERATOR_NUMBER"]),
        "operator_name": _clean(native["OPERATOR_NAME"]),
        "water_land_code": _clean(native["WB_WATER_LAND_CODE"]),
        "well_type": _clean(native["WELL_TYPE_NAME"]),
        "api_depth": _clean(native["API_DEPTH"]),
        "on_schedule": native["ON_SCHEDULE"].strip() == "Y",
        "plug_date": _clean(native["PLUG_DATE"]),
        "completion_date": _clean(native["COMPLETION_DATE"]),
        "original_completion_date": _clean(
            native["ORIG_COMPLETION_DT"]
        ),
        "recent_permit": _clean(native["RECENT_PERMIT"]),
        "wellbore_id": _clean(native["OG_WELLBORE_EWA_ID"]),
        "p5_organization_status": _clean(native["P5_ORG_STATUS"]),
        "native": native,
        "evidence": _source_evidence(
            WELLBORE_SOURCE_ID,
            path,
            record_number,
            byte_offset=byte_offset,
            raw_text=raw_line,
        ),
    }
    if csv_layout_recovery is not None:
        record["evidence"]["csv_layout_recovery"] = csv_layout_recovery
    return record


def _parse_wellbore_csv_line(
    raw_line: str,
    record_number: int,
) -> tuple[list[str], str | None]:
    try:
        row = next(csv.reader([raw_line], strict=True))
    except csv.Error:
        row = []
    if len(row) == len(WELLBORE_FIELDS):
        return row, None

    if raw_line.startswith('"') and raw_line.endswith('"'):
        boundary_row = [
            value.replace('""', '"')
            for value in raw_line[1:-1].split('","')
        ]
        if len(boundary_row) == len(WELLBORE_FIELDS):
            return boundary_row, "quoted_field_boundary_recovery"

    raise RRCLayoutError(
        f"Wellbore row {record_number} has {len(row)} fields; "
        f"expected {len(WELLBORE_FIELDS)}"
    )


def iter_wellbores(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream rows from the headerless 59-column Wellbore Query CSV."""
    csv.field_size_limit(1_000_000)
    source_path = Path(path)
    with _open_binary(source_path) as handle:
        record_number = 0
        first_data_row = True
        while True:
            byte_offset = handle.tell()
            raw = handle.readline()
            if not raw:
                break
            try:
                raw_line = raw.rstrip(b"\r\n").decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise RRCLayoutError(
                    f"Wellbore row {record_number} is not UTF-8/ASCII"
                ) from error
            if raw_line == "":
                footer_raw = handle.readline()
                try:
                    footer_line = footer_raw.rstrip(b"\r\n").decode(
                        "utf-8"
                    )
                except UnicodeDecodeError as error:
                    raise RRCLayoutError(
                        "Wellbore report footer is not UTF-8/ASCII"
                    ) from error
                footer_match = re.fullmatch(
                    r"(\d+) rows selected\.",
                    footer_line,
                )
                if footer_match is None:
                    raise RRCLayoutError(
                        f"Wellbore row {record_number} is blank outside "
                        "the report footer"
                    )
                selected_count = int(footer_match.group(1))
                if selected_count != record_number:
                    raise RRCLayoutError(
                        "Wellbore report footer count "
                        f"{selected_count} differs from parsed row count "
                        f"{record_number}"
                    )
                return
            row, csv_layout_recovery = _parse_wellbore_csv_line(
                raw_line,
                record_number,
            )
            if first_data_row and tuple(row) == WELLBORE_FIELDS:
                first_data_row = False
                record_number += 1
                continue
            first_data_row = False
            if len(row) != len(WELLBORE_FIELDS):
                raise RRCLayoutError(
                    f"Wellbore row {record_number} has {len(row)} fields; "
                    f"expected {len(WELLBORE_FIELDS)}"
                )
            yield _normalize_wellbore(
                row,
                raw_line,
                source_path,
                record_number,
                byte_offset,
                csv_layout_recovery=csv_layout_recovery,
            )
            record_number += 1


def _contains(value: Any, query: str | None) -> bool:
    if not query:
        return True
    return query.casefold() in str(value or "").casefold()


def _normalized_identity_name(value: Any) -> str | None:
    text = str(value or "").upper()
    normalized = " ".join(re.findall(r"[A-Z0-9]+", text))
    return normalized or None


def _identity_match(
    p5_number: str | None,
    organization: Mapping[str, Any] | None,
    *,
    source_name: str | None = None,
) -> dict[str, Any] | None:
    if organization is None or not p5_number:
        return None
    p5_name = organization.get("organization_name")
    source_normalized = _normalized_identity_name(source_name)
    p5_normalized = _normalized_identity_name(p5_name)
    if source_name is None:
        name_comparison = "not_available"
    elif source_normalized == p5_normalized:
        name_comparison = "exact_normalized"
    else:
        name_comparison = "different"
    return {
        "basis": "exact_p5_number",
        "p5_number": p5_number,
        "name_comparison": name_comparison,
        "source_name_normalized": source_normalized,
        "p5_name_normalized": p5_normalized,
        "text_heuristic_used": False,
    }


def _match_p5(record: Mapping[str, Any], args: argparse.Namespace) -> bool:
    if args.p5_number and record.get("p5_number") not in args.p5_number:
        return False
    if args.status and record.get("status") not in args.status:
        return False
    return _contains(record.get("organization_name"), args.name)


def _match_wellbore(
    record: Mapping[str, Any],
    args: argparse.Namespace,
) -> bool:
    checks = (
        ("api_number", args.api),
        ("operator_number", args.operator_number),
        ("oil_gas_code", args.oil_gas),
        ("district", args.district),
    )
    for key, expected in checks:
        if expected and record.get(key) != expected:
            return False
    if args.lease_id and record.get("lease_id") != normalize_lease_id(
        args.lease_id
    ):
        return False
    if not _contains(record.get("county_name"), args.county):
        return False
    return _contains(record.get("lease_name"), args.name)


def _event_in_date_window(
    event: Mapping[str, Any],
    args: argparse.Namespace,
) -> bool:
    value = event.get("effective_date") or event.get("sequence_date")
    if args.effective_from and (
        not value or str(value) < args.effective_from
    ):
        return False
    return not (
        args.effective_to
        and (not value or str(value) > args.effective_to)
    )


def _match_p4(group: Mapping[str, Any], args: argparse.Namespace) -> bool:
    lease = group["lease"]
    if args.oil_gas and lease.get("oil_gas_code") != args.oil_gas:
        return False
    if args.district and lease.get("district") != args.district:
        return False
    if args.lease_id and lease.get("lease_id") != normalize_lease_id(
        args.lease_id
    ):
        return False
    if not _contains(group.get("current_lease_name"), args.name):
        return False
    if args.operator_number:
        operator_numbers = {
            lease.get("current_operator_number"),
            *(
                event.get("operator_number")
                for event in group["operator_history"]
            ),
        }
        if args.operator_number not in operator_numbers:
            return False
    if args.effective_from or args.effective_to:
        return any(
            _event_in_date_window(event, args)
            for event in group["operator_history"]
        )
    return True


def query_p4(
    path: str | Path,
    args: argparse.Namespace,
) -> Iterator[dict[str, Any]]:
    exact_lease = bool(
        args.oil_gas and args.district and args.lease_id
    )
    exact_lease_key = (
        f"{args.oil_gas}:{args.district}:"
        f"{normalize_lease_id(args.lease_id)}"
        if exact_lease
        else None
    )
    for group in iter_p4_groups(path, lease_key=exact_lease_key):
        if not _match_p4(group, args):
            continue
        if args.effective_from or args.effective_to:
            group = {
                **group,
                "operator_history": [
                    event
                    for event in group["operator_history"]
                    if _event_in_date_window(event, args)
                ],
            }
        yield group
        if exact_lease:
            break


def resolve_records(
    p4_path: str | Path,
    p5_path: str | Path,
    wellbore_path: str | Path,
    args: argparse.Namespace,
) -> Iterator[dict[str, Any]]:
    """Join selected P-4 groups to P-5 names and Wellbore lease rows."""
    groups = list(_window(query_p4(p4_path, args), args, {}))
    operator_numbers: set[str] = set()
    lease_keys: set[str] = set()
    for group in groups:
        lease = group["lease"]
        lease_keys.add(str(lease["lease_key"]))
        if lease.get("current_operator_number"):
            operator_numbers.add(str(lease["current_operator_number"]))
        for event in group["operator_history"]:
            if event.get("operator_number"):
                operator_numbers.add(str(event["operator_number"]))
            for relationship in event["gatherer_purchaser_nominator"]:
                if relationship.get("p5_number"):
                    operator_numbers.add(str(relationship["p5_number"]))

    organizations = {
        record["p5_number"]: record
        for record in iter_p5_organizations(
            p5_path,
            encoding=args.p5_encoding,
        )
        if record["p5_number"] in operator_numbers
    }
    wells_by_lease: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for well in iter_wellbores(wellbore_path):
        if well["lease_key"] in lease_keys:
            operator = organizations.get(well.get("operator_number"))
            well["operator"] = operator
            well["operator_identity_match"] = _identity_match(
                well.get("operator_number"),
                operator,
                source_name=well.get("operator_name"),
            )
            wells_by_lease[well["lease_key"]].append(well)

    for group in groups:
        lease = group["lease"]
        current_number = lease.get("current_operator_number")
        group["current_operator"] = organizations.get(current_number)
        group["current_operator_identity_match"] = _identity_match(
            current_number,
            group["current_operator"],
        )
        for event in group["operator_history"]:
            event["operator"] = organizations.get(
                event.get("operator_number")
            )
            event["operator_identity_match"] = _identity_match(
                event.get("operator_number"),
                event["operator"],
            )
            for relationship in event["gatherer_purchaser_nominator"]:
                relationship["organization"] = organizations.get(
                    relationship.get("p5_number")
                )
                relationship["organization_identity_match"] = _identity_match(
                    relationship.get("p5_number"),
                    relationship["organization"],
                )
        group["wellbores"] = wells_by_lease.get(lease["lease_key"], [])
        for well in group["wellbores"]:
            well["operator_matches_p4_current"] = (
                bool(well.get("operator_number"))
                and well.get("operator_number") == current_number
            )
        group["join"] = {
            "lease_key": lease["lease_key"],
            "p5_operator_key": current_number,
            "wellbore_match_count": len(group["wellbores"]),
        }
        yield group


def _window(
    records: Iterable[dict[str, Any]],
    args: argparse.Namespace,
    stats: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    offset = int(getattr(args, "offset", 0) or 0)
    limit = getattr(args, "limit", None)
    matched = 0
    returned = 0
    for record in records:
        matched += 1
        if matched <= offset:
            continue
        if limit is not None and returned >= limit:
            stats["has_more"] = True
            break
        returned += 1
        yield record
    stats["matched_before_window_stop"] = matched
    stats["returned"] = returned
    stats.setdefault("has_more", False)


def _file_metadata(path: str | Path) -> dict[str, Any]:
    source_path = Path(path)
    stat = source_path.stat()
    name_match = _WELLBORE_RELEASE_RE.fullmatch(source_path.name)
    return {
        "path": str(source_path.resolve()),
        "filename": source_path.name,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        ).isoformat().replace("+00:00", "Z"),
        "snapshot_date_from_filename": (
            name_match.group(1) if name_match else None
        ),
        "compression": (
            "gzip" if source_path.name.lower().endswith(".gz") else None
        ),
    }


def _open_output(path: str | None) -> tuple[TextIO, bool]:
    if not path:
        return sys.stdout, False
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path.open("w", encoding="utf-8"), True


def _emit_records(
    records: Iterable[dict[str, Any]],
    *,
    operation: str,
    source_ids: Sequence[str],
    args: argparse.Namespace,
    metadata: Mapping[str, Any] | None = None,
    apply_window: bool = True,
) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    selected = _window(records, args, stats) if apply_window else records
    handle, close_handle = _open_output(args.output)
    try:
        if args.format == "jsonl":
            handle.write(
                json.dumps(
                    {
                        "_metadata": {
                            "operation": operation,
                            "source_ids": list(source_ids),
                            **dict(metadata or {}),
                        }
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            count = 0
            for record in selected:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
                count += 1
            stats.setdefault("returned", count)
            handle.write(
                json.dumps({"_summary": stats}, sort_keys=True) + "\n"
            )
        else:
            envelope = {
                "operation": operation,
                "source_ids": list(source_ids),
                "verified_contract_date": VERIFIED_AT,
                **dict(metadata or {}),
            }
            handle.write("{\n")
            first_key = True
            for key, value in envelope.items():
                if not first_key:
                    handle.write(",\n")
                handle.write(
                    f"  {json.dumps(key)}: "
                    f"{json.dumps(value, sort_keys=True)}"
                )
                first_key = False
            handle.write(',\n  "records": [\n')
            count = 0
            first_record = True
            for record in selected:
                if not first_record:
                    handle.write(",\n")
                rendered = json.dumps(record, sort_keys=True)
                handle.write("    " + rendered)
                first_record = False
                count += 1
            stats.setdefault("returned", count)
            handle.write("\n  ],\n")
            handle.write(
                '  "summary": '
                + json.dumps(stats, sort_keys=True)
                + "\n}\n"
            )
    finally:
        if close_handle:
            handle.close()
    if args.output:
        print(
            f"{stats.get('returned', 0)} results ({operation}) saved to "
            f"{Path(args.output).expanduser()}"
        )
    return stats


def _nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be nonnegative")
    return parsed


def _add_output_window(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--offset", type=_nonnegative, default=0)
    parser.add_argument(
        "--limit",
        type=_nonnegative,
        help="Caller-selected result window; omitted means no result cap",
    )
    parser.add_argument("--output", help="Write structured results to FILE")
    parser.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
    )


def _add_p4_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--oil-gas", choices=("O", "G"))
    parser.add_argument("--district")
    parser.add_argument("--lease-id")
    parser.add_argument("--operator-number")
    parser.add_argument("--name", help="Case-insensitive lease-name substring")
    parser.add_argument("--effective-from", metavar="YYYY-MM-DD")
    parser.add_argument("--effective-to", metavar="YYYY-MM-DD")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    contracts = subparsers.add_parser(
        "contracts",
        help="Show the verified source and file-layout contracts",
    )
    contracts.add_argument("--output")
    contracts.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
    )

    releases = subparsers.add_parser(
        "releases",
        help="List the files in an official RRC bulk share",
    )
    releases.add_argument("source", choices=tuple(SHARE_URLS))
    releases.add_argument("--timeout", type=float, default=120.0)
    _add_output_window(releases)

    download = subparsers.add_parser(
        "download",
        help="Download an exact or preferred file from an official RRC share",
    )
    download.add_argument("source", choices=tuple(SHARE_URLS))
    download.add_argument("destination")
    download.add_argument("--filename")
    download.add_argument("--replace", action="store_true")
    download.add_argument("--timeout", type=float, default=300.0)
    download.add_argument("--output")
    download.add_argument(
        "--format",
        choices=("json", "jsonl"),
        default="json",
    )

    p5 = subparsers.add_parser(
        "p5",
        help="Stream P-5 organization records",
    )
    p5.add_argument("file")
    p5.add_argument("--p5-number", action="append")
    p5.add_argument("--name")
    p5.add_argument(
        "--status",
        action="append",
        choices=tuple(P5_STATUS.values()),
    )
    p5.add_argument(
        "--encoding",
        choices=("auto", "ascii", "cp037"),
        default="auto",
    )
    _add_output_window(p5)

    p4 = subparsers.add_parser(
        "p4",
        help="Stream P-4 lease and operator-history groups",
    )
    p4.add_argument("file")
    _add_p4_selectors(p4)
    _add_output_window(p4)

    wellbore = subparsers.add_parser(
        "wellbore",
        help="Stream Wellbore Query rows",
    )
    wellbore.add_argument("file")
    wellbore.add_argument("--api")
    wellbore.add_argument("--operator-number")
    wellbore.add_argument("--oil-gas", choices=("O", "G"))
    wellbore.add_argument("--district")
    wellbore.add_argument("--lease-id")
    wellbore.add_argument("--county")
    wellbore.add_argument("--name", help="Case-insensitive lease-name substring")
    _add_output_window(wellbore)

    resolve = subparsers.add_parser(
        "resolve",
        help="Join selected P-4 history to P-5 names and Wellbore rows",
    )
    resolve.add_argument("--p4", required=True)
    resolve.add_argument("--p5", required=True)
    resolve.add_argument("--wellbore", required=True)
    resolve.add_argument(
        "--p5-encoding",
        choices=("auto", "ascii", "cp037"),
        default="auto",
    )
    _add_p4_selectors(resolve)
    _add_output_window(resolve)
    return parser


def _contracts_record() -> dict[str, Any]:
    return {
        "official_datasets_page": DATASETS_PAGE,
        "verified_at": VERIFIED_AT,
        "sources": SOURCE_CONTRACTS,
        "wellbore_fields": list(WELLBORE_FIELDS),
        "p4_tape_district_map": TAPE_TO_RRC_DISTRICT,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "contracts":
            _emit_records(
                [_contracts_record()],
                operation="contracts",
                source_ids=(
                    P4_SOURCE_ID,
                    P5_SOURCE_ID,
                    WELLBORE_SOURCE_ID,
                ),
                args=args,
            )
        elif args.command == "releases":
            client = RRCGoDriveClient(timeout=args.timeout)
            entries, _view_state = client.list(args.source)
            selected = preferred_release(args.source, entries)
            records = (
                {
                    **entry.to_dict(),
                    "preferred": entry == selected,
                }
                for entry in entries
            )
            _emit_records(
                records,
                operation="releases",
                source_ids=(SOURCE_CONTRACTS[args.source]["source_id"],),
                args=args,
                metadata={
                    "share_url": SHARE_URLS[args.source],
                    "source_contract": SOURCE_CONTRACTS[args.source],
                },
            )
        elif args.command == "download":
            record = RRCGoDriveClient(timeout=args.timeout).download(
                args.source,
                args.destination,
                filename=args.filename,
                replace=args.replace,
            )
            _emit_records(
                [record],
                operation="download",
                source_ids=(SOURCE_CONTRACTS[args.source]["source_id"],),
                args=args,
            )
        elif args.command == "p5":
            records = (
                record
                for record in iter_p5_organizations(
                    args.file,
                    encoding=args.encoding,
                )
                if _match_p5(record, args)
            )
            _emit_records(
                records,
                operation="p5",
                source_ids=(P5_SOURCE_ID,),
                args=args,
                metadata={"artifact": _file_metadata(args.file)},
            )
        elif args.command == "p4":
            _emit_records(
                query_p4(args.file, args),
                operation="p4",
                source_ids=(P4_SOURCE_ID,),
                args=args,
                metadata={"artifact": _file_metadata(args.file)},
            )
        elif args.command == "wellbore":
            records = (
                record
                for record in iter_wellbores(args.file)
                if _match_wellbore(record, args)
            )
            _emit_records(
                records,
                operation="wellbore",
                source_ids=(WELLBORE_SOURCE_ID,),
                args=args,
                metadata={"artifact": _file_metadata(args.file)},
            )
        else:
            _emit_records(
                resolve_records(
                    args.p4,
                    args.p5,
                    args.wellbore,
                    args,
                ),
                operation="resolve",
                source_ids=(
                    P4_SOURCE_ID,
                    P5_SOURCE_ID,
                    WELLBORE_SOURCE_ID,
                ),
                args=args,
                metadata={
                    "artifacts": {
                        "p4": _file_metadata(args.p4),
                        "p5": _file_metadata(args.p5),
                        "wellbore": _file_metadata(args.wellbore),
                    }
                },
                apply_window=False,
            )
    except (
        OSError,
        RRCBulkError,
        ValueError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
