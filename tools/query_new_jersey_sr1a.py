#!/usr/bin/env python3
"""Search New Jersey Treasury SR1A property-sale releases.

The Division of Taxation publishes a current year-to-date SR1A ZIP and annual
ZIP snapshots.  Each archive contains one CRLF-delimited, 663-byte fixed-width
file with grantor/grantee names, sale and assessment values, deed references,
recording dates, parcel components, and building attributes.

Release discovery follows the official statistics page at runtime.  Search
downloads are cached under validator-derived filenames, so a replaced annual
or year-to-date artifact cannot be silently confused with an earlier copy.
Omitting ``--limit`` traverses every matching row in the selected releases.

Examples:
    uv run python tools/query_new_jersey_sr1a.py manifest --json
    uv run python tools/query_new_jersey_sr1a.py search "ACME HOLDINGS" \
        --field party --year 2025 --output /tmp/nj-sales.json
    uv run python tools/query_new_jersey_sr1a.py search \
        --municipality-code 1225 --block 299 --lot 1.02
    uv run python tools/query_new_jersey_sr1a.py search "123 MAIN ST" \
        --field property-address --limit 50
    uv run python tools/query_new_jersey_sr1a.py probe --year 2026 --json
    uv run python tools/query_new_jersey_sr1a.py alternatives --json
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import re
import sys
import tempfile
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        ArtifactProbe,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
    )
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from tools.public_records_store import canonical_property_ref
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        ArtifactProbe,
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        file_sha256,
    )
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsError,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        ResultStatus,
        SourceMetadata,
        canonical_json,
        sha256_fingerprint,
    )
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-nj-treasury-sr1a-sales"
LANDING_URL = "https://www.nj.gov/treasury/taxation/lpt/statdata.shtml"
LAYOUT_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/SR1Afilelayout.pdf"
)
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_CACHE_DIR = (
    Path(tempfile.gettempdir()) / "ithildin-new-jersey-sr1a"
)
RECORD_WIDTH = 663
PHYSICAL_RECORD_WIDTH = 665
CURSOR_PREFIX = "nj-sr1a:v1:"
CURSOR_VERSION = 1

NJGIN_PARCELS_URL = "https://www.nj.gov/njgin/edata/parcels/"
NJGIN_MODIV_URL = (
    "https://njogis-newjersey.opendata.arcgis.com/documents/"
    "property-tax-list-mod-iv-of-nj-fgdb-download/about"
)
ASSESSOR_DIRECTORY_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "assessor/statewidebycounty.pdf"
)
COUNTY_TAX_BOARD_URL = (
    "https://www.nj.gov/treasury/taxation/pdf/lpt/"
    "CountyBoardsofTaxation.pdf"
)
STATE_ARCHIVES_COUNTY_URL = (
    "https://www.nj.gov/state/archives/catcounty.html"
)
COUNTY_INFORMATION_URL = (
    "https://www.nj.gov/nj/gov/county/counties.shtml"
)
TAX_COURT_DOCKET_URL = (
    "https://www.njcourts.gov/courts/tax/docketed-cases"
)
TAX_COURT_OPINIONS_URL = (
    "https://www.njcourts.gov/attorneys/opinions/published-tax"
)
PROPERTY_APPEALS_URL = (
    "https://www.nj.gov/treasury/taxation/lpt/lpt-appeal.shtml"
)
PROPERTY_REGISTRATION_URL = (
    "https://serviceportal.dca.nj.gov/ultra-bhi-home/"
    "ultra-bhi-propertysearch/"
)
OPRA_URL = "https://www.nj.gov/opra/home/request-records.shtml"

COUNTIES = {
    "01": ("Atlantic", "34001"),
    "02": ("Bergen", "34003"),
    "03": ("Burlington", "34005"),
    "04": ("Camden", "34007"),
    "05": ("Cape May", "34009"),
    "06": ("Cumberland", "34011"),
    "07": ("Essex", "34013"),
    "08": ("Gloucester", "34015"),
    "09": ("Hudson", "34017"),
    "10": ("Hunterdon", "34019"),
    "11": ("Mercer", "34021"),
    "12": ("Middlesex", "34023"),
    "13": ("Monmouth", "34025"),
    "14": ("Morris", "34027"),
    "15": ("Ocean", "34029"),
    "16": ("Passaic", "34031"),
    "17": ("Salem", "34033"),
    "18": ("Somerset", "34035"),
    "19": ("Sussex", "34037"),
    "20": ("Union", "34039"),
    "21": ("Warren", "34041"),
}
COUNTY_ALIASES = {
    re.sub(r"[^a-z0-9]", "", name.casefold()): code
    for code, (name, _geoid) in COUNTIES.items()
}

SOURCE_WARNINGS = (
    (
        "The current year-to-date file is a replaceable snapshot. Rows repeated "
        "in later SR1A snapshots are the same source lineage, not independent "
        "corroboration."
    ),
    (
        "The source layout declares an implied two-decimal transfer fee; live "
        "releases have used both implied cents and an explicit decimal. Results "
        "retain the raw field and identify the normalization used."
    ),
    (
        "The six-digit date columns do not share one encoding: last-update is "
        "MMDDYY, aging/deed/recorded are YYMMDD, and field-date is DDMMYY. "
        "Each result preserves the raw date and reports its field-specific format."
    ),
)

DATE_FORMATS = {
    "last_update_date": ("%m%d%y", "MMDDYY"),
    "aging_date": ("%y%m%d", "YYMMDD"),
    "deed_date": ("%y%m%d", "YYMMDD"),
    "date_recorded": ("%y%m%d", "YYMMDD"),
    "field_date": ("%d%m%y", "DDMMYY"),
}


@dataclass(frozen=True)
class FieldSpec:
    """One field from the official 1-based inclusive layout."""

    name: str
    picture: str
    start: int
    end: int

    @property
    def width(self) -> int:
        return self.end - self.start + 1

    @property
    def byte_slice(self) -> slice:
        return slice(self.start - 1, self.end)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "picture": self.picture,
            "start": self.start,
            "end": self.end,
            "width": self.width,
        }


FIELD_SPECS = (
    FieldSpec("county_code", "99", 1, 2),
    FieldSpec("district_code", "99", 3, 4),
    FieldSpec("total_assessment", "9(12)", 5, 16),
    FieldSpec("operator_initials", "X(3)", 17, 19),
    FieldSpec("last_update_date", "9(6)", 20, 25),
    FieldSpec("un_type", "X", 34, 34),
    FieldSpec("sr_nu_code", "X(3)", 35, 37),
    FieldSpec("reported_sales_price", "9(9)", 38, 46),
    FieldSpec("verified_sales_price", "9(9)", 47, 55),
    FieldSpec("main_value_land", "9(9)", 56, 64),
    FieldSpec("main_value_building", "9(9)", 65, 73),
    FieldSpec("main_value_total", "9(9)", 74, 82),
    FieldSpec("sales_ratio", "S999V99", 83, 87),
    FieldSpec("realty_transfer_fee", "9(7)V99", 88, 96),
    FieldSpec("rtf_error_flag", "X", 97, 97),
    FieldSpec("rtf_exempt_code", "X", 98, 98),
    FieldSpec("serial_number", "9(7)", 99, 105),
    FieldSpec("grantor_name", "X(35)", 110, 144),
    FieldSpec("grantor_street", "X(25)", 145, 169),
    FieldSpec("grantor_city_state", "X(25)", 170, 194),
    FieldSpec("grantor_zip", "9(9)", 195, 203),
    FieldSpec("grantee_name", "X(35)", 204, 238),
    FieldSpec("grantee_street", "X(25)", 239, 263),
    FieldSpec("grantee_city_state", "X(25)", 264, 288),
    FieldSpec("grantee_zip", "9(9)", 289, 297),
    FieldSpec("property_location", "X(25)", 298, 322),
    FieldSpec("aging_date", "9(6)", 323, 328),
    FieldSpec("deed_book", "X(5)", 329, 333),
    FieldSpec("deed_page", "X(5)", 334, 338),
    FieldSpec("deed_date", "9(6)", 339, 344),
    FieldSpec("date_recorded", "9(6)", 345, 350),
    FieldSpec("block", "X(5)", 351, 355),
    FieldSpec("block_suffix", "X(4)", 356, 359),
    FieldSpec("lot", "X(5)", 360, 364),
    FieldSpec("lot_suffix", "X(4)", 365, 368),
    FieldSpec("etc", "X", 369, 369),
    *tuple(
        spec
        for index, start in enumerate((370, 420, 470, 520, 570), 1)
        for spec in (
            FieldSpec(f"additional_block_{index}", "X(9)", start, start + 8),
            FieldSpec(
                f"additional_lot_{index}",
                "X(9)",
                start + 9,
                start + 17,
            ),
            FieldSpec(
                f"additional_qualifier_{index}",
                "X(5)",
                start + 18,
                start + 22,
            ),
            FieldSpec(
                f"additional_value_land_{index}",
                "9(9)",
                start + 23,
                start + 31,
            ),
            FieldSpec(
                f"additional_value_building_{index}",
                "9(9)",
                start + 32,
                start + 40,
            ),
            FieldSpec(
                f"additional_value_total_{index}",
                "9(9)",
                start + 41,
                start + 49,
            ),
        )
    ),
    FieldSpec("qualification_codes", "X(5)", 620, 624),
    FieldSpec("assess_year", "99", 625, 626),
    FieldSpec("property_class", "X(3)", 627, 629),
    FieldSpec("class_4_type", "9(3)", 630, 632),
    FieldSpec("assessor_number_code", "X(3)", 639, 641),
    FieldSpec("field_status_code", "X", 642, 642),
    FieldSpec("field_date", "9(6)", 643, 648),
    FieldSpec("critical_error_flag", "X", 649, 649),
    FieldSpec("year_built", "9(4)", 653, 656),
    FieldSpec("living_space", "9(7)", 657, 663),
)
FIELD_BY_NAME = {field.name: field for field in FIELD_SPECS}

DECLARED_SCHEMA = {
    "format": "fixed_width",
    "layout_url": LAYOUT_URL,
    "record_width_bytes": RECORD_WIDTH,
    "physical_record_width_bytes": PHYSICAL_RECORD_WIDTH,
    "line_ending": "CRLF",
    "position_semantics": "one_based_inclusive_byte_positions",
    "observed_encoding": "ASCII",
    "fields": [field.to_dict() for field in FIELD_SPECS],
}

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="New Jersey Treasury SR1A Property Sales",
    source_role="statewide_property_sale_deed_party_assessment_index",
    base_url=LANDING_URL,
    dataset_id="SR1A",
    metadata={
        "authority": "New Jersey Division of Taxation",
        "coverage": "New Jersey statewide annual and current-year property sales",
        "layout_url": LAYOUT_URL,
        "release_discovery": "official statistics-page links",
        "record_width_bytes": RECORD_WIDTH,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id="us-nj",
    name="New Jersey",
    state_code="NJ",
    metadata={"state_fips": "34"},
)


class NewJerseySR1AError(RuntimeError):
    """Structured source-specific failure."""

    status = ResultStatus.SOURCE_CHANGED
    code = "nj_sr1a_source_changed"
    category = "source_schema"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class ManifestTransportError(NewJerseySR1AError):
    status = ResultStatus.UNAVAILABLE
    code = "nj_sr1a_manifest_unavailable"
    category = "transport"
    retryable = True


class CursorError(NewJerseySR1AError):
    code = "nj_sr1a_cursor_invalid"
    category = "cursor"


class ArchiveContractError(NewJerseySR1AError):
    code = "nj_sr1a_archive_changed"
    category = "source_archive"


class PartialTraversalError(NewJerseySR1AError):
    """Schema/archive failure after one or more valid records were found."""

    def __init__(
        self,
        error: NewJerseySR1AError,
        records: Sequence[Mapping[str, Any]],
    ) -> None:
        super().__init__(str(error), details=error.details)
        self.error = error
        self.records = tuple(records)


@dataclass(frozen=True)
class Release:
    release_id: str
    year: int
    series: str
    label: str
    url: str

    @property
    def filename(self) -> str:
        return Path(unquote(urlsplit(self.url).path)).name

    @property
    def coverage(self) -> dict[str, Any]:
        return {
            "calendar_year": self.year,
            "scope": self.series,
            "replacement_semantics": (
                "replaceable_current_snapshot"
                if self.series == "year_to_date"
                else "published_annual_snapshot"
            ),
        }

    def artifact(self) -> BulkArtifact:
        return BulkArtifact.from_url(
            "sr1a_fixed_width_zip",
            self.url,
            media_type="application/zip",
            archive_format="zip",
            metadata={
                "release_id": self.release_id,
                "year": self.year,
                "series": self.series,
            },
        )

    def manifest_record(
        self,
        snapshot: ManifestSnapshot,
    ) -> dict[str, Any]:
        manifest = BulkDatasetManifest(
            source_id=SOURCE_ID,
            dataset_id="SR1A-property-sales",
            release=BulkReleaseMetadata(
                release_id=self.release_id,
                kind="snapshot",
                coverage=self.coverage,
            ),
            artifacts=(self.artifact(),),
            schema=DECLARED_SCHEMA,
            metadata={
                "official_listing_url": LANDING_URL,
                "official_link_label": self.label,
                "layout_url": snapshot.layout_url,
                "release_set_fingerprint": snapshot.fingerprint,
            },
        )
        return {
            "canonical_ref": canonical_property_ref(
                SOURCE_ID,
                "34",
                "bulk_release",
                self.release_id,
            ),
            "release_id": self.release_id,
            "year": self.year,
            "series": self.series,
            "label": self.label,
            "url": self.url,
            "manifest": manifest.to_dict(),
        }


@dataclass(frozen=True)
class ManifestSnapshot:
    releases: tuple[Release, ...]
    layout_url: str

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "landing_url": LANDING_URL,
            "layout_url": self.layout_url,
            "releases": [
                {
                    "release_id": release.release_id,
                    "year": release.year,
                    "series": release.series,
                    "url": release.url,
                }
                for release in self.releases
            ],
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload)


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        label = " ".join("".join(self._text).split())
        self.links.append((self._href, label))
        self._href = None
        self._text = []


_YTD_RE = re.compile(r"^YTDSR1A(?P<year>\d{4})\.zip$", re.I)
_ANNUAL_RE = re.compile(r"^Sales(?P<year>\d{4})\.zip$", re.I)


def parse_release_manifest(
    html_text: str,
    *,
    base_url: str = LANDING_URL,
) -> ManifestSnapshot:
    """Parse current SR1A releases from the official statistics page."""
    parser = _AnchorParser()
    parser.feed(html_text)
    releases: dict[str, Release] = {}
    layout_url = LAYOUT_URL
    for href, label in parser.links:
        absolute_url = urljoin(base_url, href)
        filename = Path(unquote(urlsplit(absolute_url).path)).name
        if filename.casefold() == "sr1afilelayout.pdf":
            layout_url = absolute_url
            continue
        match = _YTD_RE.fullmatch(filename)
        series = "year_to_date"
        if match is None:
            match = _ANNUAL_RE.fullmatch(filename)
            series = "annual"
        if match is None:
            continue
        year = int(match.group("year"))
        release_id = (
            f"sr1a-ytd-{year}"
            if series == "year_to_date"
            else f"sr1a-annual-{year}"
        )
        release = Release(
            release_id=release_id,
            year=year,
            series=series,
            label=label or filename,
            url=absolute_url,
        )
        previous = releases.get(release_id)
        if previous is not None and previous.url != release.url:
            raise NewJerseySR1AError(
                "Official page declares conflicting URLs for one SR1A release",
                details={
                    "release_id": release_id,
                    "first_url": previous.url,
                    "second_url": release.url,
                },
            )
        releases[release_id] = release
    if not releases:
        raise NewJerseySR1AError(
            "Official statistics page did not expose any SR1A ZIP releases",
            details={"landing_url": base_url},
        )
    ordered = tuple(
        sorted(
            releases.values(),
            key=lambda item: (
                -item.year,
                0 if item.series == "year_to_date" else 1,
                item.release_id,
            ),
        )
    )
    return ManifestSnapshot(releases=ordered, layout_url=layout_url)


def _response_status(response: Any) -> int:
    return int(getattr(response, "status", getattr(response, "status_code", 200)))


def fetch_release_manifest(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    opener: Callable[..., Any] = urlopen,
) -> ManifestSnapshot:
    """Fetch and parse the official release listing."""
    request = Request(
        LANDING_URL,
        headers={
            "User-Agent": "Ithildin-Public-Records/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        try:
            with opener(request, timeout=timeout) as response:
                status = _response_status(response)
                if status < 200 or status >= 300:
                    raise ManifestTransportError(
                        f"Official SR1A listing returned HTTP {status}",
                        details={
                            "url": LANDING_URL,
                            "http_status": status,
                        },
                    )
                body = response.read()
            return parse_release_manifest(
                body.decode("utf-8", errors="replace")
            )
        except HTTPError as error:
            last_error = error
            retryable = error.code in {429, 500, 502, 503, 504}
            if not retryable or attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Official SR1A listing returned HTTP {error.code}",
                    details={
                        "url": LANDING_URL,
                        "http_status": error.code,
                    },
                ) from error
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = error
            if attempt >= retry_attempts:
                raise ManifestTransportError(
                    f"Could not fetch the official SR1A listing: {error}",
                    details={"url": LANDING_URL},
                ) from error
        if attempt < retry_attempts:
            time.sleep(min(0.25 * (2 ** (attempt - 1)), 2.0))
    assert last_error is not None
    raise ManifestTransportError(str(last_error))


def _encode_cursor(payload: Mapping[str, Any]) -> str:
    encoded = base64.urlsafe_b64encode(
        canonical_json(payload).encode("utf-8")
    ).decode("ascii")
    return CURSOR_PREFIX + encoded.rstrip("=")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    if not cursor.startswith(CURSOR_PREFIX):
        raise CursorError("Cursor does not belong to the New Jersey SR1A source")
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        value = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("Cursor payload is not valid") from error
    if not isinstance(value, dict) or value.get("version") != CURSOR_VERSION:
        raise CursorError("Cursor version is not supported")
    return value


def paginate_manifest(
    snapshot: ManifestSnapshot,
    releases: Sequence[Release],
    *,
    limit: int | None,
    cursor: str | None,
) -> tuple[tuple[Release, ...], str | None]:
    """Apply a release-set-bound offset cursor to manifest records."""
    selection_fingerprint = sha256_fingerprint(
        [release.release_id for release in releases]
    )
    offset = 0
    if cursor is not None:
        payload = _decode_cursor(cursor)
        if payload.get("kind") != "manifest":
            raise CursorError("Cursor is not a manifest cursor")
        if payload.get("release_set_fingerprint") != snapshot.fingerprint:
            raise CursorError(
                "SR1A release listing changed after this cursor was issued",
                details={
                    "expected_release_set_fingerprint": payload.get(
                        "release_set_fingerprint"
                    ),
                    "current_release_set_fingerprint": snapshot.fingerprint,
                },
            )
        if payload.get("selection_fingerprint") != selection_fingerprint:
            raise CursorError(
                "SR1A manifest cursor no longer matches the release selectors",
                details={
                    "cursor_selection_fingerprint": payload.get(
                        "selection_fingerprint"
                    ),
                    "current_selection_fingerprint": selection_fingerprint,
                },
            )
        offset = payload.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CursorError("Manifest cursor offset is invalid")
    end = len(releases) if limit is None else min(len(releases), offset + limit)
    selected = tuple(releases[offset:end])
    next_cursor = None
    if end < len(releases):
        next_cursor = _encode_cursor(
            {
                "version": CURSOR_VERSION,
                "kind": "manifest",
                "release_set_fingerprint": snapshot.fingerprint,
                "selection_fingerprint": selection_fingerprint,
                "offset": end,
            }
        )
    return selected, next_cursor


def _clean(value: str) -> str | None:
    normalized = " ".join(value.strip().split())
    return normalized or None


def _text_key(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _identifier_key(value: str | None) -> str:
    compact = re.sub(r"\s+", "", (value or "").strip().upper())
    if re.fullmatch(r"\d+(?:\.\d+)?", compact):
        integer, dot, fraction = compact.partition(".")
        integer = integer.lstrip("0") or "0"
        fraction = fraction.rstrip("0")
        return integer + (f".{fraction}" if dot and fraction else "")
    return compact


def _raw_fields(row: bytes) -> tuple[dict[str, str], str]:
    if len(row) != RECORD_WIDTH:
        raise ArchiveContractError(
            "SR1A row does not match the official 663-byte layout",
            details={
                "expected_width": RECORD_WIDTH,
                "actual_width": len(row),
            },
        )
    try:
        text = row.decode("ascii")
        encoding = "ascii"
    except UnicodeDecodeError:
        try:
            text = row.decode("cp1252")
            encoding = "cp1252"
        except UnicodeDecodeError:
            text = row.decode("latin-1")
            encoding = "latin-1-byte-preserving"
    return {
        field.name: text[field.byte_slice]
        for field in FIELD_SPECS
    }, encoding


def _integer(raw: str, *, zero_is_none: bool = False) -> int | None:
    value = raw.strip()
    if not value or not value.isdigit():
        return None
    number = int(value)
    return None if zero_is_none and number == 0 else number


_POSITIVE_OVERPUNCH = dict(zip("{ABCDEFGHI", "0123456789", strict=True))
_NEGATIVE_OVERPUNCH = dict(zip("}JKLMNOPQR", "0123456789", strict=True))


def _implied_decimal(raw: str, places: int) -> Decimal | None:
    value = raw.strip().upper()
    if not value:
        return None
    sign = 1
    if value[0] in "+-":
        sign = -1 if value[0] == "-" else 1
        value = value[1:]
    if value and value[-1] in _POSITIVE_OVERPUNCH:
        value = value[:-1] + _POSITIVE_OVERPUNCH[value[-1]]
    elif value and value[-1] in _NEGATIVE_OVERPUNCH:
        value = value[:-1] + _NEGATIVE_OVERPUNCH[value[-1]]
        sign = -1
    if not value.isdigit():
        return None
    return Decimal(sign * int(value)).scaleb(-places)


def _decimal_text(value: Decimal | None, places: int) -> str | None:
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum), f".{places}f")


def _transfer_fee(raw: str) -> tuple[int | None, str | None, str | None]:
    value = raw.strip()
    if not value:
        return None, None, None
    if "." in value:
        try:
            amount = Decimal(value)
        except InvalidOperation:
            return None, None, None
        normalization = "explicit_decimal"
    else:
        amount = _implied_decimal(value, 2)
        normalization = "implied_two_decimals"
    if amount is None:
        return None, None, None
    cents = int((amount * 100).to_integral_value())
    return cents, _decimal_text(amount, 2), normalization


def _date_value(raw: str, field_name: str) -> str | None:
    value = raw.strip()
    if not value or value == "000000":
        return None
    if not re.fullmatch(r"\d{6}", value):
        return None
    source_format = DATE_FORMATS[field_name][0]
    try:
        return datetime.strptime(value, source_format).date().isoformat()
    except ValueError:
        return None


def _year_value(raw: str) -> int | None:
    value = raw.strip()
    if not re.fullmatch(r"\d{2}", value):
        return None
    year = int(value)
    return 2000 + year if year <= 68 else 1900 + year


def _postal_code(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if len(value) == 9 and value.isdigit():
        return f"{value[:5]}-{value[5:]}"
    return value


def _date_record(raw: str, field_name: str) -> dict[str, Any]:
    return {
        "raw": raw.strip() or None,
        "source_format": DATE_FORMATS[field_name][1],
        "iso": _date_value(raw, field_name),
    }


def _address(street: str, city_state: str, postal: str) -> dict[str, Any]:
    return {
        "street": _clean(street),
        "city_state": _clean(city_state),
        "postal_code_raw": postal.strip() or None,
        "postal_code": _postal_code(postal),
    }


def _normalization_issues(fields: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    numeric_fields = (
        "total_assessment",
        "reported_sales_price",
        "verified_sales_price",
        "main_value_land",
        "main_value_building",
        "main_value_total",
        "serial_number",
        "year_built",
        "living_space",
    )
    numeric_fields += tuple(
        f"additional_value_{kind}_{index}"
        for index in range(1, 6)
        for kind in ("land", "building", "total")
    )
    for name in numeric_fields:
        raw = fields[name].strip()
        if raw and not raw.isdigit():
            issues.append(f"{name}:unparsed_numeric:{raw}")
    for name in DATE_FORMATS:
        raw = fields[name].strip()
        if raw and raw != "000000" and _date_value(raw, name) is None:
            issues.append(f"{name}:unparsed_date:{raw}")
    ratio_raw = fields["sales_ratio"].strip()
    if ratio_raw and _implied_decimal(ratio_raw, 2) is None:
        issues.append(f"sales_ratio:unparsed_numeric:{ratio_raw}")
    fee_raw = fields["realty_transfer_fee"].strip()
    if fee_raw and _transfer_fee(fee_raw)[0] is None:
        issues.append(f"realty_transfer_fee:unparsed_numeric:{fee_raw}")
    return issues


@dataclass(frozen=True)
class ArchiveDescriptor:
    member_name: str
    member_size: int
    member_crc32: str
    record_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "member_size": self.member_size,
            "member_crc32": self.member_crc32,
            "record_count": self.record_count,
            "record_width_bytes": RECORD_WIDTH,
            "line_ending": "CRLF",
        }


def describe_archive(path: Path | str) -> ArchiveDescriptor:
    """Validate central-directory assumptions and return record metadata."""
    archive_path = Path(path)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = [
                item
                for item in archive.infolist()
                if not item.is_dir()
                and not item.filename.startswith("__MACOSX/")
                and Path(item.filename).name != ".DS_Store"
            ]
    except (OSError, zipfile.BadZipFile) as error:
        raise ArchiveContractError(
            f"SR1A artifact is not a readable ZIP archive: {error}",
            details={"path": str(archive_path)},
        ) from error
    if len(members) != 1:
        raise ArchiveContractError(
            "SR1A archive no longer contains exactly one data member",
            details={
                "path": str(archive_path),
                "member_names": [item.filename for item in members],
            },
        )
    member = members[0]
    if not member.filename.casefold().endswith(".txt"):
        raise ArchiveContractError(
            "SR1A archive member is no longer a text file",
            details={"path": str(archive_path), "member": member.filename},
        )
    if member.flag_bits & 0x1:
        raise ArchiveContractError(
            "SR1A archive member unexpectedly requires a password",
            details={"path": str(archive_path), "member": member.filename},
        )
    if member.file_size == 0 or member.file_size % PHYSICAL_RECORD_WIDTH:
        raise ArchiveContractError(
            "SR1A member size is incompatible with 663-byte CRLF records",
            details={
                "path": str(archive_path),
                "member": member.filename,
                "member_size": member.file_size,
                "physical_record_width": PHYSICAL_RECORD_WIDTH,
            },
        )
    return ArchiveDescriptor(
        member_name=member.filename,
        member_size=member.file_size,
        member_crc32=f"{member.CRC:08x}",
        record_count=member.file_size // PHYSICAL_RECORD_WIDTH,
    )


@dataclass(frozen=True)
class LocalRelease:
    release: Release
    archive_path: Path
    archive_size: int
    archive_sha256: str
    descriptor: ArchiveDescriptor
    etag: str | None = None
    last_modified: str | None = None

    @property
    def binding(self) -> dict[str, Any]:
        return {
            "release_id": self.release.release_id,
            "url": self.release.url,
            "archive_size": self.archive_size,
            "archive_sha256": self.archive_sha256,
            "etag": self.etag,
            "last_modified": self.last_modified,
            **self.descriptor.to_dict(),
        }


@contextmanager
def _artifact_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _cache_destination(
    release: Release,
    probe: ArtifactProbe,
    cache_dir: Path,
) -> Path:
    validator = sha256_fingerprint(
        {
            "url": release.url,
            "etag": probe.etag,
            "last_modified": probe.last_modified,
            "content_length": probe.content_length,
        }
    )[:16]
    stem = Path(release.filename).stem
    return cache_dir / f"{stem}.{validator}.zip"


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=args.chunk_size,
    )


def _local_release_from_path(
    release: Release,
    path: Path | str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
    known_sha256: str | None = None,
) -> LocalRelease:
    archive_path = Path(path)
    descriptor = describe_archive(archive_path)
    return LocalRelease(
        release=release,
        archive_path=archive_path,
        archive_size=archive_path.stat().st_size,
        archive_sha256=known_sha256 or file_sha256(archive_path),
        descriptor=descriptor,
        etag=etag,
        last_modified=last_modified,
    )


def resolve_local_releases(
    args: argparse.Namespace,
    releases: Sequence[Release],
    *,
    transfer_client: BulkTransferClient,
    archive_paths: Mapping[str, Path | str] | None = None,
) -> tuple[LocalRelease, ...]:
    """Resolve selected releases to hash-bound local archives."""
    if archive_paths is not None:
        missing = [
            release.release_id
            for release in releases
            if release.release_id not in archive_paths
        ]
        if missing:
            raise ArchiveContractError(
                "Local archive mapping omitted selected releases",
                details={"missing_release_ids": missing},
            )
    resolved: list[LocalRelease] = []
    for release in releases:
        if archive_paths is not None and release.release_id in archive_paths:
            resolved.append(
                _local_release_from_path(
                    release,
                    archive_paths[release.release_id],
                )
            )
            continue
        artifact = release.artifact()
        probe = transfer_client.probe(artifact, sample_bytes=16)
        if probe.format_hint != "zip":
            raise ArchiveContractError(
                "SR1A download no longer has a ZIP signature",
                details={
                    "release_id": release.release_id,
                    "url": release.url,
                    "signature_hex": probe.signature_hex,
                    "media_type": probe.media_type,
                },
            )
        destination = _cache_destination(
            release,
            probe,
            Path(args.cache_dir),
        )
        with _artifact_lock(destination.with_suffix(".lock")):
            download = transfer_client.download(
                BulkArtifact(
                    artifact_id=artifact.artifact_id,
                    url=artifact.url,
                    filename=artifact.filename,
                    media_type=artifact.media_type,
                    archive_format=artifact.archive_format,
                    expected_size=probe.content_length,
                    etag=probe.etag,
                    last_modified=probe.last_modified,
                    metadata=artifact.metadata,
                ),
                destination,
                resume=True,
                max_bytes=args.max_download_bytes,
            )
        resolved.append(
            _local_release_from_path(
                release,
                download.path,
                etag=download.etag or probe.etag,
                last_modified=download.last_modified or probe.last_modified,
                known_sha256=download.sha256,
            )
        )
    return tuple(resolved)


def iter_archive_rows(
    local: LocalRelease,
    *,
    start_row: int = 0,
) -> Iterator[tuple[int, bytes]]:
    """Yield zero-based row positions after validating physical framing."""
    if start_row < 0 or start_row > local.descriptor.record_count:
        raise CursorError(
            "Cursor row position is outside the selected SR1A release",
            details={
                "release_id": local.release.release_id,
                "row_position": start_row,
                "record_count": local.descriptor.record_count,
            },
        )
    row_count = 0
    try:
        with zipfile.ZipFile(local.archive_path) as archive:
            with archive.open(local.descriptor.member_name) as source:
                for row_index, raw_line in enumerate(source):
                    row_count = row_index + 1
                    if not raw_line.endswith(b"\r\n"):
                        raise ArchiveContractError(
                            "SR1A row no longer uses the published CRLF framing",
                            details={
                                "release_id": local.release.release_id,
                                "member": local.descriptor.member_name,
                                "row_number": row_index + 1,
                                "physical_width": len(raw_line),
                            },
                        )
                    row = raw_line[:-2]
                    if len(row) != RECORD_WIDTH:
                        raise ArchiveContractError(
                            "SR1A row no longer has the published 663-byte width",
                            details={
                                "release_id": local.release.release_id,
                                "member": local.descriptor.member_name,
                                "row_number": row_index + 1,
                                "actual_width": len(row),
                            },
                        )
                    if row_index >= start_row:
                        yield row_index, row
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise ArchiveContractError(
            f"Could not stream the SR1A archive: {error}",
            details={
                "release_id": local.release.release_id,
                "path": str(local.archive_path),
            },
        ) from error
    if row_count != local.descriptor.record_count:
        raise ArchiveContractError(
            "SR1A row count does not match the archive directory",
            details={
                "release_id": local.release.release_id,
                "expected_rows": local.descriptor.record_count,
                "actual_rows": row_count,
            },
        )


@dataclass(frozen=True)
class SearchSelection:
    query: str | None
    field: str
    county_code: str | None
    municipality_code: str | None
    block: str | None
    lot: str | None
    deed_book: str | None
    deed_page: str | None
    recorded_from: str | None
    recorded_to: str | None
    reported_price_min: int | None
    reported_price_max: int | None
    verified_price_min: int | None
    verified_price_max: int | None
    release_ids: tuple[str, ...]

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "field": self.field,
            "county_code": self.county_code,
            "municipality_code": self.municipality_code,
            "block": self.block,
            "lot": self.lot,
            "deed_book": self.deed_book,
            "deed_page": self.deed_page,
            "recorded_from": self.recorded_from,
            "recorded_to": self.recorded_to,
            "reported_price_min": self.reported_price_min,
            "reported_price_max": self.reported_price_max,
            "verified_price_min": self.verified_price_min,
            "verified_price_max": self.verified_price_max,
            "release_ids": list(self.release_ids),
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload)


def _county_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if re.fullmatch(r"\d{1,2}", normalized):
        code = normalized.zfill(2)
        if code in COUNTIES:
            return code
    alias = re.sub(r"[^a-z0-9]", "", normalized.casefold())
    if alias.endswith("county"):
        alias = alias.removesuffix("county")
    code = COUNTY_ALIASES.get(alias)
    if code is None:
        raise ValueError(f"Unknown New Jersey county: {value}")
    return code


def _selected_releases(
    args: argparse.Namespace,
    snapshot: ManifestSnapshot,
) -> tuple[Release, ...]:
    years = set(getattr(args, "year", None) or ())
    release_ids = set(getattr(args, "release", None) or ())
    return tuple(
        release
        for release in snapshot.releases
        if (not years or release.year in years)
        and (not release_ids or release.release_id in release_ids)
    )


def build_selection(
    args: argparse.Namespace,
    releases: Sequence[Release],
) -> SearchSelection:
    county = _county_code(getattr(args, "county", None))
    municipality = getattr(args, "municipality_code", None)
    if municipality is not None:
        municipality = municipality.strip()
        if not re.fullmatch(r"\d{4}", municipality):
            raise ValueError("municipality-code must contain four digits")
        if county is not None and municipality[:2] != county:
            raise ValueError(
                "municipality-code county prefix does not match --county"
            )
        county = county or municipality[:2]
    recorded_from = getattr(args, "recorded_from", None)
    recorded_to = getattr(args, "recorded_to", None)
    if recorded_from and recorded_to and recorded_from > recorded_to:
        raise ValueError("recorded-from must not be after recorded-to")
    for minimum_name, maximum_name in (
        ("reported_price_min", "reported_price_max"),
        ("verified_price_min", "verified_price_max"),
    ):
        minimum = getattr(args, minimum_name, None)
        maximum = getattr(args, maximum_name, None)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(
                f"{minimum_name.replace('_', '-')} must not exceed "
                f"{maximum_name.replace('_', '-')}"
            )
    query = getattr(args, "query", None)
    query = _clean(query) if query is not None else None
    return SearchSelection(
        query=query,
        field=args.field,
        county_code=county,
        municipality_code=municipality,
        block=_clean(getattr(args, "block", None) or ""),
        lot=_clean(getattr(args, "lot", None) or ""),
        deed_book=_clean(getattr(args, "deed_book", None) or ""),
        deed_page=_clean(getattr(args, "deed_page", None) or ""),
        recorded_from=recorded_from,
        recorded_to=recorded_to,
        reported_price_min=getattr(args, "reported_price_min", None),
        reported_price_max=getattr(args, "reported_price_max", None),
        verified_price_min=getattr(args, "verified_price_min", None),
        verified_price_max=getattr(args, "verified_price_max", None),
        release_ids=tuple(release.release_id for release in releases),
    )


def _parcel_pairs(fields: Mapping[str, str]) -> list[tuple[str, str]]:
    pairs = [
        (
            fields["block"] + fields["block_suffix"],
            fields["lot"] + fields["lot_suffix"],
        )
    ]
    pairs.extend(
        (
            fields[f"additional_block_{index}"],
            fields[f"additional_lot_{index}"],
        )
        for index in range(1, 6)
    )
    return [
        (block, lot)
        for block, lot in pairs
        if block.strip() or lot.strip()
    ]


def _query_haystack(
    fields: Mapping[str, str],
    field: str,
) -> str:
    names: tuple[str, ...]
    if field == "grantor":
        names = ("grantor_name",)
    elif field == "grantee":
        names = ("grantee_name",)
    elif field == "party":
        names = ("grantor_name", "grantee_name")
    elif field == "property-address":
        names = ("property_location",)
    elif field == "deed":
        names = ("deed_book", "deed_page", "deed_date", "date_recorded")
    elif field == "block-lot":
        names = (
            "block",
            "block_suffix",
            "lot",
            "lot_suffix",
            *tuple(
                name
                for index in range(1, 6)
                for name in (
                    f"additional_block_{index}",
                    f"additional_lot_{index}",
                    f"additional_qualifier_{index}",
                )
            ),
        )
    else:
        names = (
            "grantor_name",
            "grantor_street",
            "grantor_city_state",
            "grantee_name",
            "grantee_street",
            "grantee_city_state",
            "property_location",
            "deed_book",
            "deed_page",
            "block",
            "block_suffix",
            "lot",
            "lot_suffix",
            "serial_number",
            *tuple(
                name
                for index in range(1, 6)
                for name in (
                    f"additional_block_{index}",
                    f"additional_lot_{index}",
                    f"additional_qualifier_{index}",
                )
            ),
        )
    return _text_key(" ".join(fields[name] for name in names))


def row_matches(
    fields: Mapping[str, str],
    selection: SearchSelection,
) -> bool:
    if selection.query is not None:
        if _text_key(selection.query) not in _query_haystack(
            fields,
            selection.field,
        ):
            return False
    county = fields["county_code"].strip()
    district = fields["district_code"].strip()
    if selection.county_code is not None and county != selection.county_code:
        return False
    if (
        selection.municipality_code is not None
        and county + district != selection.municipality_code
    ):
        return False
    if selection.block is not None or selection.lot is not None:
        matches_parcel = False
        for block, lot in _parcel_pairs(fields):
            if (
                selection.block is not None
                and _identifier_key(block) != _identifier_key(selection.block)
            ):
                continue
            if (
                selection.lot is not None
                and _identifier_key(lot) != _identifier_key(selection.lot)
            ):
                continue
            matches_parcel = True
            break
        if not matches_parcel:
            return False
    if (
        selection.deed_book is not None
        and _identifier_key(fields["deed_book"])
        != _identifier_key(selection.deed_book)
    ):
        return False
    if (
        selection.deed_page is not None
        and _identifier_key(fields["deed_page"])
        != _identifier_key(selection.deed_page)
    ):
        return False
    recorded = _date_value(fields["date_recorded"], "date_recorded")
    if selection.recorded_from is not None and (
        recorded is None or recorded < selection.recorded_from
    ):
        return False
    if selection.recorded_to is not None and (
        recorded is None or recorded > selection.recorded_to
    ):
        return False
    reported = _integer(fields["reported_sales_price"])
    verified = _integer(fields["verified_sales_price"])
    if selection.reported_price_min is not None and (
        reported is None or reported < selection.reported_price_min
    ):
        return False
    if selection.reported_price_max is not None and (
        reported is None or reported > selection.reported_price_max
    ):
        return False
    if selection.verified_price_min is not None and (
        verified is None or verified < selection.verified_price_min
    ):
        return False
    if selection.verified_price_max is not None and (
        verified is None or verified > selection.verified_price_max
    ):
        return False
    return True


def normalize_row(
    row: bytes,
    *,
    local: LocalRelease,
    row_index: int,
    include_raw_line: bool = False,
) -> dict[str, Any]:
    """Normalize one source row while retaining audit coordinates and raw values."""
    fields, encoding = _raw_fields(row)
    county_code = fields["county_code"].strip()
    district_code = fields["district_code"].strip()
    municipality_code = county_code + district_code
    county_name, county_geoid = COUNTIES.get(
        county_code,
        (None, None),
    )
    serial = fields["serial_number"].strip()
    deed_book = fields["deed_book"].strip()
    deed_page = fields["deed_page"].strip()
    recorded_raw = fields["date_recorded"].strip()
    sale_record_id = ":".join(
        (
            municipality_code,
            serial,
            deed_book,
            deed_page,
            recorded_raw,
        )
    )
    source_occurrence_id = ":".join(
        (
            local.release.release_id,
            sale_record_id,
        )
    )
    transfer_fee_cents, transfer_fee_dollars, fee_normalization = (
        _transfer_fee(fields["realty_transfer_fee"])
    )
    ratio = _implied_decimal(fields["sales_ratio"], 2)
    additional_parcels: list[dict[str, Any]] = []
    for index in range(1, 6):
        block = _clean(fields[f"additional_block_{index}"])
        lot = _clean(fields[f"additional_lot_{index}"])
        qualifier = _clean(fields[f"additional_qualifier_{index}"])
        land = _integer(fields[f"additional_value_land_{index}"])
        building = _integer(fields[f"additional_value_building_{index}"])
        total = _integer(fields[f"additional_value_total_{index}"])
        if any(
            value not in (None, 0)
            for value in (block, lot, qualifier, land, building, total)
        ):
            additional_parcels.append(
                {
                    "slot": index,
                    "block": block,
                    "lot": lot,
                    "qualifier": qualifier,
                    "assessed_value_dollars": {
                        "land": land,
                        "building": building,
                        "total": total,
                    },
                }
            )
    source_record: dict[str, Any] = {
        "archive_url": local.release.url,
        "archive_sha256": local.archive_sha256,
        "archive_size": local.archive_size,
        "archive_member": local.descriptor.member_name,
        "archive_member_crc32": local.descriptor.member_crc32,
        "row_number": row_index + 1,
        "byte_offset_in_member": row_index * PHYSICAL_RECORD_WIDTH,
        "record_width_bytes": RECORD_WIDTH,
        "record_sha256": hashlib.sha256(row).hexdigest(),
        "source_encoding": encoding,
    }
    if include_raw_line:
        source_record["raw_fixed_width"] = row.decode(
            "latin-1"
        )
    result = {
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            county_geoid or "34",
            "property_sale",
            sale_record_id,
        ),
        "source_id": SOURCE_ID,
        "record_type": "property_sale",
        "native_record_id": source_occurrence_id,
        "sale_record_id": sale_record_id,
        "source_occurrence_id": source_occurrence_id,
        "record_identity": {
            "scope": "stable_across_ytd_and_annual_release_occurrences",
            "fields": [
                "municipality_code",
                "serial_number",
                "deed_book",
                "deed_page",
                "date_recorded",
            ],
            "release_occurrence_fields": [
                "release_id",
                "archive_sha256",
                "archive_member",
                "row_number",
                "record_sha256",
            ],
        },
        "release": {
            "release_id": local.release.release_id,
            "year": local.release.year,
            "series": local.release.series,
            "release_set_role": (
                "replaceable_current_snapshot"
                if local.release.series == "year_to_date"
                else "annual_snapshot"
            ),
        },
        "source_record": source_record,
        "jurisdiction": {
            "state_code": "NJ",
            "state_fips": "34",
            "county_code": county_code or None,
            "county_name": county_name,
            "county_geoid": county_geoid,
            "district_code": district_code or None,
            "municipality_code": municipality_code or None,
        },
        "transaction": {
            "serial_number": serial or None,
            "un_type": _clean(fields["un_type"]),
            "sr_nu_code": _clean(fields["sr_nu_code"]),
            "reported_sale_price_dollars": _integer(
                fields["reported_sales_price"]
            ),
            "verified_sale_price_dollars": _integer(
                fields["verified_sales_price"]
            ),
            "sales_ratio": {
                "raw": fields["sales_ratio"].strip() or None,
                "percent": _decimal_text(ratio, 2),
            },
            "realty_transfer_fee": {
                "raw": fields["realty_transfer_fee"].strip() or None,
                "cents": transfer_fee_cents,
                "dollars": transfer_fee_dollars,
                "normalization": fee_normalization,
            },
            "rtf_error_flag": _clean(fields["rtf_error_flag"]),
            "rtf_exempt_code": _clean(fields["rtf_exempt_code"]),
            "qualification_codes": _clean(fields["qualification_codes"]),
        },
        "parties": {
            "grantor": {
                "name": _clean(fields["grantor_name"]),
                "mailing_address": _address(
                    fields["grantor_street"],
                    fields["grantor_city_state"],
                    fields["grantor_zip"],
                ),
            },
            "grantee": {
                "name": _clean(fields["grantee_name"]),
                "mailing_address": _address(
                    fields["grantee_street"],
                    fields["grantee_city_state"],
                    fields["grantee_zip"],
                ),
            },
        },
        "property": {
            "location": _clean(fields["property_location"]),
            "parcel": {
                "municipality_code": municipality_code or None,
                "block": _clean(fields["block"]),
                "block_suffix": _clean(fields["block_suffix"]),
                "lot": _clean(fields["lot"]),
                "lot_suffix": _clean(fields["lot_suffix"]),
                "etc": _clean(fields["etc"]),
            },
            "additional_parcels": additional_parcels,
            "total_assessment_dollars": _integer(
                fields["total_assessment"]
            ),
            "main_assessed_value_dollars": {
                "land": _integer(fields["main_value_land"]),
                "building": _integer(fields["main_value_building"]),
                "total": _integer(fields["main_value_total"]),
            },
            "assessment_year_raw": fields["assess_year"].strip() or None,
            "assessment_year": _year_value(fields["assess_year"]),
            "property_class": _clean(fields["property_class"]),
            "class_4_type": _clean(fields["class_4_type"]),
            "year_built_raw": fields["year_built"].strip() or None,
            "year_built": _integer(
                fields["year_built"],
                zero_is_none=True,
            ),
            "living_space_square_feet_raw": (
                fields["living_space"].strip() or None
            ),
            "living_space_square_feet": _integer(
                fields["living_space"],
                zero_is_none=True,
            ),
        },
        "deed": {
            "book": _clean(fields["deed_book"]),
            "page": _clean(fields["deed_page"]),
            "deed_date": _date_record(fields["deed_date"], "deed_date"),
            "recorded_date": _date_record(
                fields["date_recorded"],
                "date_recorded",
            ),
        },
        "source_processing": {
            "operator_initials": _clean(fields["operator_initials"]),
            "last_update_date": _date_record(
                fields["last_update_date"],
                "last_update_date",
            ),
            "aging_date": _date_record(fields["aging_date"], "aging_date"),
            "assessor_number_code": _clean(fields["assessor_number_code"]),
            "field_status_code": _clean(fields["field_status_code"]),
            "field_date": _date_record(fields["field_date"], "field_date"),
            "critical_error_flag": _clean(fields["critical_error_flag"]),
        },
        "normalization_issues": _normalization_issues(fields),
    }
    if county_code and county_geoid is None:
        result["normalization_issues"].append(
            f"county_code:unknown:{county_code}"
        )
    return result


def _artifact_binding_fingerprint(
    locals_: Sequence[LocalRelease],
) -> str:
    return sha256_fingerprint([local.binding for local in locals_])


def _search_cursor(
    *,
    selection: SearchSelection,
    snapshot: ManifestSnapshot,
    locals_: Sequence[LocalRelease],
    release_index: int,
    row_index: int,
) -> str:
    return _encode_cursor(
        {
            "version": CURSOR_VERSION,
            "kind": "search",
            "selection_fingerprint": selection.fingerprint,
            "release_set_fingerprint": snapshot.fingerprint,
            "artifact_binding_fingerprint": (
                _artifact_binding_fingerprint(locals_)
            ),
            "release_index": release_index,
            "row_index": row_index,
        }
    )


def _search_start(
    cursor: str | None,
    *,
    selection: SearchSelection,
    snapshot: ManifestSnapshot,
    locals_: Sequence[LocalRelease],
) -> tuple[int, int]:
    if cursor is None:
        return 0, 0
    payload = _decode_cursor(cursor)
    if payload.get("kind") != "search":
        raise CursorError("Cursor is not a search cursor")
    checks = {
        "selection_fingerprint": selection.fingerprint,
        "release_set_fingerprint": snapshot.fingerprint,
        "artifact_binding_fingerprint": (
            _artifact_binding_fingerprint(locals_)
        ),
    }
    for name, current in checks.items():
        if payload.get(name) != current:
            raise CursorError(
                f"SR1A cursor no longer matches {name.replace('_', ' ')}",
                details={
                    "field": name,
                    "cursor_value": payload.get(name),
                    "current_value": current,
                },
            )
    release_index = payload.get("release_index")
    row_index = payload.get("row_index")
    if (
        isinstance(release_index, bool)
        or not isinstance(release_index, int)
        or release_index < 0
        or release_index >= len(locals_)
        or isinstance(row_index, bool)
        or not isinstance(row_index, int)
        or row_index < 0
    ):
        raise CursorError("SR1A cursor position is invalid")
    return release_index, row_index


def search_local_releases(
    *,
    selection: SearchSelection,
    snapshot: ManifestSnapshot,
    locals_: Sequence[LocalRelease],
    limit: int | None,
    cursor: str | None,
    include_raw_line: bool,
) -> tuple[list[dict[str, Any]], str | None]:
    """Stream selected archives with deterministic, artifact-bound resumption."""
    if not locals_:
        return [], None
    start_release, start_row = _search_start(
        cursor,
        selection=selection,
        snapshot=snapshot,
        locals_=locals_,
    )
    records: list[dict[str, Any]] = []
    try:
        for release_index in range(start_release, len(locals_)):
            local = locals_[release_index]
            release_start = start_row if release_index == start_release else 0
            for row_index, row in iter_archive_rows(
                local,
                start_row=release_start,
            ):
                fields, _encoding = _raw_fields(row)
                if not row_matches(fields, selection):
                    continue
                if limit is not None and len(records) >= limit:
                    return records, _search_cursor(
                        selection=selection,
                        snapshot=snapshot,
                        locals_=locals_,
                        release_index=release_index,
                        row_index=row_index,
                    )
                records.append(
                    normalize_row(
                        row,
                        local=local,
                        row_index=row_index,
                        include_raw_line=include_raw_line,
                    )
                )
    except NewJerseySR1AError as error:
        if records:
            raise PartialTraversalError(error, records) from error
        raise
    return records, None


def validate_local_release(local: LocalRelease) -> dict[str, Any]:
    """Traverse one complete release and summarize observed schema variants."""
    encoding_counts: Counter[str] = Counter()
    fee_normalizations: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    county_counts: Counter[str] = Counter()
    first_record_sha256: str | None = None
    last_record_sha256: str | None = None
    traversed = 0
    for row_index, row in iter_archive_rows(local):
        fields, encoding = _raw_fields(row)
        row_sha256 = hashlib.sha256(row).hexdigest()
        first_record_sha256 = first_record_sha256 or row_sha256
        last_record_sha256 = row_sha256
        traversed = row_index + 1
        encoding_counts[encoding] += 1
        county_counts[fields["county_code"].strip() or "(blank)"] += 1
        fee_raw = fields["realty_transfer_fee"].strip()
        if fee_raw:
            _cents, _dollars, normalization = _transfer_fee(fee_raw)
            fee_normalizations[normalization or "unparsed"] += 1
        for issue in _normalization_issues(fields):
            issue_counts[issue.split(":", 1)[0]] += 1
    return {
        "source_id": SOURCE_ID,
        "record_type": "release_validation",
        "release_id": local.release.release_id,
        "year": local.release.year,
        "series": local.release.series,
        "artifact_binding": local.binding,
        "validation": {
            "complete_archive_traversal": True,
            "records_traversed": traversed,
            "expected_records": local.descriptor.record_count,
            "record_width_bytes": RECORD_WIDTH,
            "physical_record_width_bytes": PHYSICAL_RECORD_WIDTH,
            "line_ending": "CRLF",
            "encoding_counts": dict(sorted(encoding_counts.items())),
            "transfer_fee_normalizations": dict(
                sorted(fee_normalizations.items())
            ),
            "normalization_issue_counts_by_field": dict(
                sorted(issue_counts.items())
            ),
            "county_code_counts": dict(sorted(county_counts.items())),
            "first_record_sha256": first_record_sha256,
            "last_record_sha256": last_record_sha256,
        },
    }


def _alternative_routes() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "us-nj-njgin-parcels-modiv",
            "name": "NJGIN Parcels and MOD-IV Composite",
            "url": NJGIN_PARCELS_URL,
            "authority": "New Jersey Office of GIS",
            "access": "anonymous statewide ArcGIS service and bulk downloads",
            "join_fields": [
                "four-digit municipality code",
                "block",
                "lot",
                "deed book/page",
                "property location",
            ],
            "adds": (
                "parcel geometry, current joined assessment/tax attributes, "
                "and stable PAMS/GIS parcel identifiers"
            ),
            "relationship_to_sr1a": "complementary parcel and assessment layer",
        },
        {
            "source_id": "us-nj-njgin-modiv-tax-list",
            "name": "NJGIN statewide MOD-IV tax-list download",
            "url": NJGIN_MODIV_URL,
            "authority": (
                "New Jersey Division of Taxation and New Jersey Office of GIS"
            ),
            "access": "anonymous File Geodatabase download",
            "join_fields": ["municipality code", "block", "lot"],
            "adds": (
                "current tax-list rows, including records not joined to a "
                "statewide parcel polygon"
            ),
            "relationship_to_sr1a": "separate official assessment snapshot",
        },
        {
            "source_id": "us-nj-county-clerks-registers",
            "name": "County Clerk/Register property-record systems",
            "url": COUNTY_INFORMATION_URL,
            "archives_url": STATE_ARCHIVES_COUNTY_URL,
            "authority": "New Jersey county clerks and registers",
            "access": "county-specific public search, copies, and archives",
            "join_fields": [
                "party",
                "deed book/page",
                "recording date",
                "parcel",
            ],
            "adds": (
                "deed and mortgage instrument images, releases, assignments, "
                "legal descriptions, and historical title-chain records"
            ),
            "relationship_to_sr1a": "document-level evidence behind sale indexes",
        },
        {
            "source_id": "us-nj-local-assessors-tax-boards",
            "name": "Municipal assessors and County Boards of Taxation",
            "url": ASSESSOR_DIRECTORY_URL,
            "county_board_url": COUNTY_TAX_BOARD_URL,
            "appeal_guidance_url": PROPERTY_APPEALS_URL,
            "authority": "Municipal assessors and county tax boards",
            "access": "local public search, inspection, copies, and board records",
            "join_fields": ["municipality", "block", "lot", "owner", "address"],
            "adds": (
                "property record cards, local corrections, certified tax "
                "lists, added/omitted assessments, and county appeal records"
            ),
            "relationship_to_sr1a": "local administration and valuation context",
        },
        {
            "source_id": "us-nj-tax-court-property-cases",
            "name": "New Jersey Tax Court local-property dockets and judgments",
            "url": TAX_COURT_DOCKET_URL,
            "opinions_url": TAX_COURT_OPINIONS_URL,
            "authority": "New Jersey Judiciary",
            "access": "public daily docket lists, judgment spreadsheets, and opinions",
            "join_fields": [
                "party",
                "county",
                "municipality",
                "block",
                "lot",
                "assessment year",
            ],
            "adds": (
                "open and docketed property-tax cases, judgments, challenged "
                "assessments, counsel, and written judicial reasoning"
            ),
            "relationship_to_sr1a": "litigation and valuation-dispute context",
        },
        {
            "source_id": "us-nj-dca-property-registration",
            "name": "New Jersey DCA property registration search",
            "url": PROPERTY_REGISTRATION_URL,
            "authority": "New Jersey Department of Community Affairs",
            "access": "anonymous property search",
            "join_fields": ["county", "municipality", "block", "lot", "address"],
            "adds": (
                "registration number and registered-property context for "
                "covered buildings"
            ),
            "relationship_to_sr1a": "complementary regulatory property index",
        },
        {
            "source_id": "us-nj-opra-property-records",
            "name": "New Jersey OPRA record-custodian routing",
            "url": OPRA_URL,
            "authority": "State, county, or municipal record custodian",
            "access": "request channel for a defined public record",
            "join_fields": ["custodian", "record series", "parcel", "date range"],
            "adds": (
                "specified records or extracts not already published by the "
                "statewide, county, assessor, recorder, or court route"
            ),
            "relationship_to_sr1a": "record-specific acquisition route",
        },
    ]


def _positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must not be negative")
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return number


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "date must use YYYY-MM-DD"
        ) from error


def build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    parameters: dict[str, Any] = {}
    for name in (
        "query",
        "field",
        "county",
        "municipality_code",
        "block",
        "lot",
        "deed_book",
        "deed_page",
        "recorded_from",
        "recorded_to",
        "reported_price_min",
        "reported_price_max",
        "verified_price_min",
        "verified_price_max",
        "include_raw_line",
        "range_bytes",
        "destination",
        "max_download_bytes",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = str(value) if isinstance(value, Path) else value
    for name in ("year", "release"):
        value = getattr(args, name, None)
        if value:
            parameters[name] = list(value)
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
        ),
    )


def _download_record(
    release: Release,
    snapshot: ManifestSnapshot,
    download: DownloadResult,
) -> dict[str, Any]:
    return {
        **release.manifest_record(snapshot),
        "download": download.to_dict(),
        "archive": describe_archive(download.path).to_dict(),
    }


def execute(
    args: argparse.Namespace,
    *,
    manifest_snapshot: ManifestSnapshot | None = None,
    transfer_client: BulkTransferClient | None = None,
    archive_paths: Mapping[str, Path | str] | None = None,
) -> PublicRecordsResult:
    """Execute one operation and return the shared public-record envelope."""
    query = build_query(args)
    try:
        if args.command == "alternatives":
            result = PublicRecordsResult.success(query, _alternative_routes())
        else:
            snapshot = manifest_snapshot or fetch_release_manifest(
                timeout=args.timeout,
                retry_attempts=args.retry_attempts,
            )
            releases = _selected_releases(args, snapshot)
            if args.command == "manifest":
                selected, next_cursor = paginate_manifest(
                    snapshot,
                    releases,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        release.manifest_record(snapshot)
                        for release in selected
                    ],
                    next_cursor=next_cursor,
                )
            elif not releases:
                result = PublicRecordsResult.success(
                    query,
                    [],
                    warnings=(
                        "No currently published SR1A release matched the "
                        "selected year/release.",
                    ),
                )
            else:
                transfer = transfer_client or _bulk_client(args)
                if args.command == "probe":
                    release = releases[0]
                    probe = transfer.probe(
                        release.artifact(),
                        sample_bytes=args.range_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            {
                                **release.manifest_record(snapshot),
                                "probe": probe.to_dict(),
                            }
                        ],
                    )
                elif args.command == "download":
                    if len(releases) != 1:
                        raise ValueError(
                            "download requires selectors matching one release"
                        )
                    release = releases[0]
                    download = transfer.download(
                        release.artifact(),
                        args.destination,
                        resume=True,
                        max_bytes=args.max_download_bytes,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [_download_record(release, snapshot, download)],
                        raw_artifact_refs=(download.path,),
                    )
                elif args.command == "validate":
                    locals_ = resolve_local_releases(
                        args,
                        releases,
                        transfer_client=transfer,
                        archive_paths=archive_paths,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        [
                            validate_local_release(local)
                            for local in locals_
                        ],
                        raw_artifact_refs=tuple(
                            str(local.archive_path) for local in locals_
                        ),
                        warnings=SOURCE_WARNINGS,
                    )
                else:
                    selection = build_selection(args, releases)
                    locals_ = resolve_local_releases(
                        args,
                        releases,
                        transfer_client=transfer,
                        archive_paths=archive_paths,
                    )
                    records, next_cursor = search_local_releases(
                        selection=selection,
                        snapshot=snapshot,
                        locals_=locals_,
                        limit=args.limit,
                        cursor=args.cursor,
                        include_raw_line=args.include_raw_line,
                    )
                    result = PublicRecordsResult.success(
                        query,
                        records,
                        next_cursor=next_cursor,
                        raw_artifact_refs=tuple(
                            str(local.archive_path) for local in locals_
                        ),
                        warnings=SOURCE_WARNINGS,
                    )
    except PartialTraversalError as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [error.error.to_contract_error()],
            records=error.records,
            warnings=SOURCE_WARNINGS,
        )
    except NewJerseySR1AError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
        )
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
        )
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="nj_sr1a_operation_failed",
                    message=str(error),
                    category="source_or_query",
                    retryable=False,
                )
            ],
        )
    result_count = (
        len(result.records)
        if result.status
        in {ResultStatus.OK, ResultStatus.NO_RESULTS, ResultStatus.PARTIAL}
        else None
    )
    log_search(
        canonical_json(query.to_dict()),
        SOURCE_ID,
        result_count,
    )
    return result


def _emit(result: PublicRecordsResult, args: argparse.Namespace) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"New Jersey SR1A {args.command} ({result.status.value})",
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"New Jersey SR1A {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        if args.command == "manifest":
            print(
                f"  {record['release_id']} | {record['url']}"
            )
        elif args.command == "alternatives":
            print(f"  {record['name']} | {record['url']}")
        elif args.command == "search":
            print(
                f"  {record['native_record_id']} | "
                f"{record['parties']['grantor']['name'] or '?'} -> "
                f"{record['parties']['grantee']['name'] or '?'} | "
                f"{record['property']['location'] or '?'}"
            )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def _add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=DEFAULT_TIMEOUT,
    )
    parser.add_argument(
        "--retry-attempts",
        type=_positive_int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument(
        "--chunk-size",
        type=_positive_int,
        default=DEFAULT_CHUNK_SIZE,
    )


def _add_release_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--year",
        type=_positive_int,
        action="append",
        help="Calendar year; repeat to select more than one",
    )
    parser.add_argument(
        "--release",
        action="append",
        help="Exact release ID such as sr1a-annual-2025; repeatable",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover, download, and search New Jersey Treasury SR1A "
            "property-sale files"
        )
    )
    subparsers = parser.add_subparsers(dest="command")

    manifest = subparsers.add_parser(
        "manifest",
        help="List releases from the current official statistics page",
    )
    _add_release_selectors(manifest)
    manifest.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional release-record bound",
    )
    manifest.add_argument("--cursor")
    _add_network_args(manifest)
    add_output_args(manifest)

    probe = subparsers.add_parser(
        "probe",
        help="Probe the newest or selected published ZIP",
    )
    _add_release_selectors(probe)
    probe.add_argument(
        "--range-bytes",
        type=_nonnegative_int,
        default=64,
    )
    _add_network_args(probe)
    add_output_args(probe)

    download = subparsers.add_parser(
        "download",
        help="Download and validate one selected release",
    )
    _add_release_selectors(download)
    download.add_argument("destination", type=Path)
    download.add_argument("--max-download-bytes", type=_positive_int)
    _add_network_args(download)
    add_output_args(download)

    validate = subparsers.add_parser(
        "validate",
        help=(
            "Download and fully traverse selected releases, returning "
            "schema-variant counts without emitting sale rows"
        ),
    )
    _add_release_selectors(validate)
    validate.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
    )
    validate.add_argument("--max-download-bytes", type=_positive_int)
    _add_network_args(validate)
    add_output_args(validate)

    search = subparsers.add_parser(
        "search",
        help=(
            "Search selected releases; with no query or row filters, "
            "returns the full selected corpus"
        ),
    )
    search.add_argument("query", nargs="?")
    search.add_argument(
        "--field",
        choices=(
            "any",
            "grantor",
            "grantee",
            "party",
            "property-address",
            "deed",
            "block-lot",
        ),
        default="any",
    )
    search.add_argument("--county")
    search.add_argument("--municipality-code")
    search.add_argument("--block")
    search.add_argument("--lot")
    search.add_argument("--deed-book")
    search.add_argument("--deed-page")
    search.add_argument("--recorded-from", type=_iso_date)
    search.add_argument("--recorded-to", type=_iso_date)
    search.add_argument("--reported-price-min", type=_nonnegative_int)
    search.add_argument("--reported-price-max", type=_nonnegative_int)
    search.add_argument("--verified-price-min", type=_nonnegative_int)
    search.add_argument("--verified-price-max", type=_nonnegative_int)
    _add_release_selectors(search)
    search.add_argument(
        "--limit",
        type=_positive_int,
        help="Optional match bound; omitted traverses every match",
    )
    search.add_argument(
        "--cursor",
        help="Artifact-bound continuation cursor from a prior search",
    )
    search.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
    )
    search.add_argument("--max-download-bytes", type=_positive_int)
    search.add_argument(
        "--include-raw-line",
        action="store_true",
        help="Include the exact 663-character source row in each match",
    )
    _add_network_args(search)
    add_output_args(search)

    alternatives = subparsers.add_parser(
        "alternatives",
        help="List complementary official property and court routes",
    )
    add_output_args(alternatives)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    result = execute(args)
    _emit(result, args)
    return 0 if result.status in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
