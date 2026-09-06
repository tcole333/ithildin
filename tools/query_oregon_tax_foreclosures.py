#!/usr/bin/env python3
"""Discover and search official Oregon county tax-foreclosure publications.

The four counties covered here publish different slices of the statutory
process.  The adapter keeps the county, publication, artifact version, and
process stage attached to every extracted record.

Usage:
    uv run python tools/query_oregon_tax_foreclosures.py sources
    uv run python tools/query_oregon_tax_foreclosures.py discover --all \
        --output /tmp/oregon-tax-publications.json
    uv run python tools/query_oregon_tax_foreclosures.py inspect \
        --source us-or-tillamook-tax-foreclosure-publications \
        --artifact /tmp/foreclosure-list.pdf --output /tmp/inspection.json
    uv run python tools/query_oregon_tax_foreclosures.py search \
        --source us-or-multnomah-tax-foreclosure-publications \
        --artifact /tmp/redemption-notices.pdf --owner "EXAMPLE LLC" \
        --output /tmp/results.json
    uv run python tools/query_oregon_tax_foreclosures.py search \
        --source us-or-marion-tax-foreclosure-publications \
        --artifact /tmp/foreclosure-list.pdf \
        --text-artifact /tmp/foreclosure-list-ocr.txt \
        --text-method llm_transcription --output /tmp/results.json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from pypdf import PdfReader
from pypdf.errors import PdfReadError

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
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
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
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


STATE_CODE = "OR"
OUTPUT_SCHEMA_VERSION = "oregon-tax-foreclosure-publications/1.0"
CURSOR_PREFIX = "oregon-tax-foreclosures:v1:"
USER_AGENT = "Ithildin-Public-Records/1.0"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MAX_PAGE_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_DOCUMENT_BYTES = 256 * 1024 * 1024
MIN_SEARCHABLE_TEXT_CHARS = 80

TILLAMOOK_SOURCE_ID = "us-or-tillamook-tax-foreclosure-publications"
MARION_SOURCE_ID = "us-or-marion-tax-foreclosure-publications"
MULTNOMAH_SOURCE_ID = "us-or-multnomah-tax-foreclosure-publications"
CLACKAMAS_SOURCE_ID = "us-or-clackamas-tax-foreclosure-publications"

FORECLOSURE_LIST_STAGE = "foreclosure_list_published"
REDEMPTION_NOTICE_STAGE = "statutory_redemption_notice"
END_REDEMPTION_STAGE = "end_of_redemption_notice"
TAX_TITLE_INVENTORY_STAGE = "tax_title_inventory"
SALE_AUTHORIZATION_STAGE = "sale_authorization"
AUCTION_OFFERING_STAGE = "auction_offering"
AUCTION_RESULTS_STAGE = "auction_results"
ANNOUNCED_IN_PROGRESS_STAGE = "judgment_in_progress"

PROCESS_STAGES = (
    FORECLOSURE_LIST_STAGE,
    REDEMPTION_NOTICE_STAGE,
    END_REDEMPTION_STAGE,
    TAX_TITLE_INVENTORY_STAGE,
    SALE_AUTHORIZATION_STAGE,
    AUCTION_OFFERING_STAGE,
    AUCTION_RESULTS_STAGE,
    ANNOUNCED_IN_PROGRESS_STAGE,
)

SOURCE_PROCESS_STAGES = {
    TILLAMOOK_SOURCE_ID: (FORECLOSURE_LIST_STAGE,),
    MARION_SOURCE_ID: (
        FORECLOSURE_LIST_STAGE,
        END_REDEMPTION_STAGE,
    ),
    MULTNOMAH_SOURCE_ID: (
        REDEMPTION_NOTICE_STAGE,
        ANNOUNCED_IN_PROGRESS_STAGE,
        TAX_TITLE_INVENTORY_STAGE,
        SALE_AUTHORIZATION_STAGE,
    ),
    CLACKAMAS_SOURCE_ID: (
        AUCTION_OFFERING_STAGE,
        AUCTION_RESULTS_STAGE,
    ),
}


@dataclass(frozen=True)
class LandingPage:
    """One official county page from which publication routes are discovered."""

    url: str
    role: str


@dataclass(frozen=True)
class ComplementarySource:
    """A related official route useful for joining or filling a coverage gap."""

    name: str
    url: str
    role: str
    join_keys: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "role": self.role,
            "join_keys": list(self.join_keys),
        }


@dataclass(frozen=True)
class SourceConfig:
    """County source identity and its official publication ecosystem."""

    source_id: str
    county_name: str
    county_geoid: str
    publisher: str
    landing_pages: tuple[LandingPage, ...]
    coverage_note: str
    stable_join_keys: tuple[str, ...]
    complementary_sources: tuple[ComplementarySource, ...]

    @property
    def primary_page(self) -> str:
        return self.landing_pages[0].url

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=f"{self.county_name} tax-foreclosure publications",
            source_role="property_tax_foreclosure_publications",
            base_url=self.primary_page,
            dataset_id=f"{self.county_name.casefold().replace(' ', '-')}-tax-foreclosure",
            metadata={
                "publisher": self.publisher,
                "county_geoid": self.county_geoid,
                "coverage_note": self.coverage_note,
                "stable_join_keys": list(self.stable_join_keys),
                "supported_process_stages": list(
                    SOURCE_PROCESS_STAGES[self.source_id]
                ),
                "landing_pages": [
                    {"url": page.url, "role": page.role} for page in self.landing_pages
                ],
            },
        )

    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=self.county_geoid,
            name=f"{self.county_name}, Oregon",
            state_code=STATE_CODE,
            county_fips=self.county_geoid,
            locality=self.county_name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_metadata().to_dict(),
            "jurisdiction": self.jurisdiction().to_dict(),
            "landing_pages": [
                {"url": page.url, "role": page.role} for page in self.landing_pages
            ],
            "coverage_note": self.coverage_note,
            "stable_join_keys": list(self.stable_join_keys),
            "supported_process_stages": list(
                SOURCE_PROCESS_STAGES[self.source_id]
            ),
            "complementary_sources": [
                item.to_dict() for item in self.complementary_sources
            ],
        }


SOURCES: dict[str, SourceConfig] = {
    TILLAMOOK_SOURCE_ID: SourceConfig(
        source_id=TILLAMOOK_SOURCE_ID,
        county_name="Tillamook County",
        county_geoid="41057",
        publisher="Tillamook County Assessment and Taxation",
        landing_pages=(
            LandingPage(
                "https://www.tillamookcounty.gov/assessment/page/"
                "real-property-tax-foreclosure",
                "foreclosure_publication_index",
            ),
        ),
        coverage_note=(
            "The county page links current and prior annual foreclosure-list "
            "PDFs; each PDF identifies its court case and statutory dates."
        ),
        stable_join_keys=("tax_account", "property_map_id", "court_case_number"),
        complementary_sources=(
            ComplementarySource(
                "Tillamook Property Search Online",
                "https://query.co.tillamook.or.us/PSO/",
                "parcel_and_tax_account_context",
                ("tax_account", "property_map_id"),
            ),
            ComplementarySource(
                "Tillamook prior assessment and tax rolls",
                "https://www.tillamookcounty.gov/assessment/page/"
                "prior-assessment-tax-rolls",
                "historical_assessment_context",
                ("tax_account", "property_map_id"),
            ),
            ComplementarySource(
                "Oregon foreclosure-surplus notices",
                "https://unclaimed.oregon.gov/app/foreclosuresurplus/notices",
                "post_sale_surplus_notices",
                ("owner_name", "property_address"),
            ),
        ),
    ),
    MARION_SOURCE_ID: SourceConfig(
        source_id=MARION_SOURCE_ID,
        county_name="Marion County",
        county_geoid="41047",
        publisher="Marion County Tax Collection Department",
        landing_pages=(
            LandingPage(
                "https://www.co.marion.or.us/AO/TAX/Pages/foreclosure.aspx",
                "foreclosure_publication_index",
            ),
        ),
        coverage_note=(
            "The county links a current foreclosure list and a separate "
            "judgment-cohort end-of-redemption notice packet. The current "
            "foreclosure-list PDF may require a derived text representation."
        ),
        stable_join_keys=(
            "tax_account",
            "map_tax_lot",
            "court_case_number",
            "situs_address",
        ),
        complementary_sources=(
            ComplementarySource(
                "Marion County Property Records",
                "https://mcasr.co.marion.or.us/",
                "parcel_and_owner_context",
                ("tax_account", "map_tax_lot", "situs_address"),
            ),
            ComplementarySource(
                "Marion County tax-foreclosed property sales",
                "https://www.co.marion.or.us/FIN/Pages/propertyinfo.aspx",
                "post_deed_sale_information",
                ("tax_account", "map_tax_lot", "situs_address"),
            ),
            ComplementarySource(
                "Oregon foreclosure-surplus notices",
                "https://unclaimed.oregon.gov/app/foreclosuresurplus/notices",
                "post_sale_surplus_notices",
                ("owner_name", "property_address"),
            ),
        ),
    ),
    MULTNOMAH_SOURCE_ID: SourceConfig(
        source_id=MULTNOMAH_SOURCE_ID,
        county_name="Multnomah County",
        county_geoid="41051",
        publisher="Multnomah County Assessment, Recording and Taxation",
        landing_pages=(
            LandingPage(
                "https://multco.us/info/property-tax-foreclosure",
                "redemption_notice_index",
            ),
            LandingPage(
                "https://multco.us/programs/tax-title",
                "tax_title_publication_index",
            ),
        ),
        coverage_note=(
            "The foreclosure page publishes judgment-cohort statutory "
            "redemption notices. The Tax Title page separately publishes "
            "post-deed inventory and sale-authorization material."
        ),
        stable_join_keys=(
            "real_property_id",
            "map_id",
            "court_case_number",
            "street_address",
        ),
        complementary_sources=(
            ComplementarySource(
                "Multnomah DART property and tax records",
                "https://multcoproptax.com/",
                "parcel_and_tax_account_context",
                ("real_property_id", "map_id", "street_address"),
            ),
            ComplementarySource(
                "Multnomah County Public Records Request Portal",
                "https://multco.us/services/public-records-requests",
                "records_request_for_unpublished_material",
                ("real_property_id", "court_case_number"),
            ),
            ComplementarySource(
                "Oregon foreclosure-surplus notices",
                "https://unclaimed.oregon.gov/app/foreclosuresurplus/notices",
                "post_sale_surplus_notices",
                ("owner_name", "property_address"),
            ),
        ),
    ),
    CLACKAMAS_SOURCE_ID: SourceConfig(
        source_id=CLACKAMAS_SOURCE_ID,
        county_name="Clackamas County",
        county_geoid="41005",
        publisher="Clackamas County Assessor and Tax Collector",
        landing_pages=(
            LandingPage(
                "https://www.clackamas.us/at/foreclosures",
                "foreclosure_process_and_publication_route",
            ),
            LandingPage(
                "https://www.clackamas.us/property",
                "post_deed_property_disposition_index",
            ),
        ),
        coverage_note=(
            "The county describes its annual newspaper foreclosure-list "
            "publication but does not link that list on the process page. "
            "Its property-disposition page publishes post-deed auction "
            "offerings and results."
        ),
        stable_join_keys=("map_tax_lot", "situs_description", "auction_item"),
        complementary_sources=(
            ComplementarySource(
                "Clackamas CMap",
                "https://cmap.clackamas.us/maps/cmap",
                "parcel_and_map_context",
                ("map_tax_lot", "situs_description"),
            ),
            ComplementarySource(
                "Clackamas County Public Records Request",
                "https://www.clackamas.us/rm/policy.html",
                "foreclosure_list_and_judgment_request",
                ("tax_account", "court_case_number"),
            ),
            ComplementarySource(
                "Oregon foreclosure-surplus notices",
                "https://unclaimed.oregon.gov/app/foreclosuresurplus/notices",
                "post_sale_surplus_notices",
                ("owner_name", "property_address"),
            ),
        ),
    ),
}


class OregonTaxPublicationError(RuntimeError):
    """Base class for source, artifact, and query failures."""

    code = "oregon_tax_publication_error"
    category = "source"
    retryable = False
    result_status = ResultStatus.UNAVAILABLE

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class PublicationUnavailable(OregonTaxPublicationError):
    code = "publication_unavailable"
    category = "source_access"
    retryable = True


class PublicationChanged(OregonTaxPublicationError):
    code = "publication_changed"
    category = "source_schema"
    result_status = ResultStatus.SOURCE_CHANGED


class PublicationQueryError(OregonTaxPublicationError):
    code = "publication_query_invalid"
    category = "query"


@dataclass(frozen=True)
class Link:
    href: str
    text: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self.page_text: list[str] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if not value:
            return
        self.page_text.append(value)
        if self._href is not None:
            self._parts.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        self.links.append(Link(self._href, _clean(" ".join(self._parts))))
        self._href = None
        self._parts = []


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _money(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def _iso_date(value: str | None) -> str | None:
    normalized = _clean(value)
    if not normalized:
        return None
    normalized = re.sub(r"^Sept\.", "Sep", normalized, flags=re.I)
    normalized = re.sub(r"^([A-Za-z]{3})\.", r"\1", normalized)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(normalized, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _first_group(
    pattern: str,
    text: str,
    *,
    flags: int = re.I | re.M,
) -> str | None:
    match = re.search(pattern, text, flags)
    return _clean(match.group(1)) if match else None


def _publication_year(text: str) -> int | None:
    years = [int(value) for value in re.findall(r"\b(20\d{2})\b", text)]
    return years[0] if years else None


def _document_id(source_id: str, stage: str, url: str | None, label: str) -> str:
    digest = hashlib.sha256(
        f"{source_id}\n{stage}\n{url or ''}\n{label}".encode()
    ).hexdigest()[:20]
    return f"{source_id}:{stage}:{digest}"


def _route(
    config: SourceConfig,
    *,
    page_url: str,
    page_role: str,
    label: str,
    url: str | None,
    process_stage: str,
    publication_status: str = "published_artifact",
    publication_year: int | None = None,
    case_number: str | None = None,
    publication_date: str | None = None,
) -> dict[str, Any]:
    return {
        "source_id": config.source_id,
        "county_name": config.county_name,
        "publisher": config.publisher,
        "document_id": _document_id(config.source_id, process_stage, url, label),
        "publication_label": label,
        "document_url": url,
        "publication_page_url": page_url,
        "publication_page_role": page_role,
        "process_stage": process_stage,
        "publication_status": publication_status,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "court_case_number": case_number,
        "version_identity": (
            "artifact_sha256_after_download" if url else "page_observation"
        ),
    }


def _parse_anchor_page(
    config: SourceConfig,
    html: str,
    *,
    page: LandingPage,
) -> list[dict[str, Any]]:
    parser = _LinkParser()
    parser.feed(html)
    page_text = _clean(" ".join(parser.page_text))
    routes: list[dict[str, Any]] = []

    if config.source_id == TILLAMOOK_SOURCE_ID:
        for link in parser.links:
            match = re.search(r"\b(20\d{2})\s+Foreclosure\s+List\b", link.text, re.I)
            if not match:
                continue
            label = _clean(link.text)
            routes.append(
                _route(
                    config,
                    page_url=page.url,
                    page_role=page.role,
                    label=label,
                    url=urljoin(page.url, link.href),
                    process_stage=FORECLOSURE_LIST_STAGE,
                    publication_year=int(match.group(1)),
                )
            )

    elif config.source_id == MARION_SOURCE_ID:
        for link in parser.links:
            text = _clean(link.text)
            if re.search(r"\bForeclosure\s+Listing\b", text, re.I):
                routes.append(
                    _route(
                        config,
                        page_url=page.url,
                        page_role=page.role,
                        label=text,
                        url=urljoin(page.url, link.href),
                        process_stage=FORECLOSURE_LIST_STAGE,
                    )
                )
                continue
            match = re.search(
                r"\b(20\d{2})\s+End\s+of\s+Redemption\s+Notices\b",
                text,
                re.I,
            )
            if match:
                routes.append(
                    _route(
                        config,
                        page_url=page.url,
                        page_role=page.role,
                        label=text,
                        url=urljoin(page.url, link.href),
                        process_stage=END_REDEMPTION_STAGE,
                        publication_year=int(match.group(1)),
                    )
                )

    elif config.source_id == MULTNOMAH_SOURCE_ID:
        for link in parser.links:
            text = _clean(link.text)
            judgment = re.search(
                r"\b(20\d{2})\s+Judgment\s*\(([^)]+)\)",
                text,
                re.I,
            )
            if judgment:
                routes.append(
                    _route(
                        config,
                        page_url=page.url,
                        page_role=page.role,
                        label=text,
                        url=urljoin(page.url, link.href),
                        process_stage=REDEMPTION_NOTICE_STAGE,
                        publication_year=int(judgment.group(1)),
                        case_number=_clean(judgment.group(2)),
                    )
                )
                continue
            if re.search(r"\bTax\s+Title\s+Inventory\b", text, re.I):
                routes.append(
                    _route(
                        config,
                        page_url=page.url,
                        page_role=page.role,
                        label=text,
                        url=urljoin(page.url, link.href),
                        process_stage=TAX_TITLE_INVENTORY_STAGE,
                        publication_year=_publication_year(text),
                        publication_date=_date_from_dotted_label(text),
                    )
                )
                continue
            if re.search(r"\border-\d{4}-\d+\.pdf\b", text, re.I):
                routes.append(
                    _route(
                        config,
                        page_url=page.url,
                        page_role=page.role,
                        label=text,
                        url=urljoin(page.url, link.href),
                        process_stage=SALE_AUTHORIZATION_STAGE,
                        publication_year=_publication_year(text),
                    )
                )

        for match in re.finditer(
            r"\b(20\d{2})\s+Judgment\s*\(([^)]+)\)\s*-\s*In\s+Progress\b",
            page_text,
            re.I,
        ):
            routes.append(
                _route(
                    config,
                    page_url=page.url,
                    page_role=page.role,
                    label=_clean(match.group(0)),
                    url=None,
                    process_stage=ANNOUNCED_IN_PROGRESS_STAGE,
                    publication_status="announced_in_progress",
                    publication_year=int(match.group(1)),
                    case_number=_clean(match.group(2)),
                )
            )

    elif config.source_id == CLACKAMAS_SOURCE_ID:
        current_date = _first_group(
            r"Public\s+Oral\s+Auction\s+"
            r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
            page_text,
        )
        current_date_iso = _iso_date(current_date)
        for link in parser.links:
            text = _clean(link.text)
            stage: str | None = None
            if re.search(r"\bAuction\s+Results\b", text, re.I):
                stage = AUCTION_RESULTS_STAGE
            elif re.search(r"\bProperty\s+Flyer\b", text, re.I):
                stage = AUCTION_OFFERING_STAGE
            if stage is None:
                continue
            dated = _first_group(
                r"([A-Z][a-z]+\.?\s+\d{1,2},\s+20\d{2})",
                text,
            )
            publication_date = _iso_date(dated) or current_date_iso
            routes.append(
                _route(
                    config,
                    page_url=page.url,
                    page_role=page.role,
                    label=text,
                    url=urljoin(page.url, link.href),
                    process_stage=stage,
                    publication_year=(
                        int(publication_date[:4]) if publication_date else None
                    ),
                    publication_date=publication_date,
                )
            )

    return _deduplicate_routes(routes)


def _date_from_dotted_label(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
    if not match:
        return None
    month, day, year = (int(value) for value in match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _deduplicate_routes(routes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: dict[tuple[str, str | None], dict[str, Any]] = {}
    for route in routes:
        key = (str(route["document_id"]), route.get("document_url"))
        found[key] = dict(route)
    return sorted(
        found.values(),
        key=lambda item: (
            item.get("publication_year") or 0,
            item.get("publication_date") or "",
            item["process_stage"],
            item["publication_label"],
        ),
        reverse=True,
    )


FetchBytes = Callable[[str, float, int], bytes]


def fetch_bytes(url: str, timeout: float, max_bytes: int) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.5",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > max_bytes:
                raise PublicationUnavailable(
                    "Official artifact is larger than the configured transfer ceiling",
                    details={
                        "url": url,
                        "content_length": int(length),
                        "max_bytes": max_bytes,
                    },
                )
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise PublicationUnavailable(
                        "Official artifact exceeded the configured transfer ceiling",
                        details={"url": url, "max_bytes": max_bytes},
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except OregonTaxPublicationError:
        raise
    except HTTPError as exc:
        raise PublicationUnavailable(
            f"Official publication returned HTTP {exc.code}",
            details={"url": url, "http_status": exc.code},
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise PublicationUnavailable(
            f"Could not retrieve official publication: {exc}",
            details={"url": url},
        ) from exc


def discover_source(
    config: SourceConfig,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_page_bytes: int = DEFAULT_MAX_PAGE_BYTES,
    fetcher: FetchBytes = fetch_bytes,
) -> dict[str, Any]:
    routes: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for page in config.landing_pages:
        payload = fetcher(page.url, timeout, max_page_bytes)
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError:
            html = payload.decode("latin-1")
        page_routes = _parse_anchor_page(config, html, page=page)
        routes.extend(page_routes)
        observations.append(
            {
                "url": page.url,
                "role": page.role,
                "page_sha256": _sha256_bytes(payload),
                "discovered_route_count": len(page_routes),
            }
        )
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source": config.source_metadata().to_dict(),
        "jurisdiction": config.jurisdiction().to_dict(),
        "publication_routes": _deduplicate_routes(routes),
        "landing_page_observations": observations,
        "complementary_sources": [
            item.to_dict() for item in config.complementary_sources
        ],
    }


def infer_process_stage(
    source_id: str,
    *,
    explicit_stage: str | None = None,
    label: str | None = None,
    document_url: str | None = None,
    artifact_name: str | None = None,
    text: str | None = None,
) -> str:
    if explicit_stage:
        if explicit_stage not in PROCESS_STAGES:
            raise PublicationQueryError(
                f"Unknown process stage: {explicit_stage}",
                details={"known_stages": list(PROCESS_STAGES)},
            )
        return explicit_stage

    haystack = " ".join(
        value or "" for value in (label, document_url, artifact_name, text)
    )
    if source_id == TILLAMOOK_SOURCE_ID:
        return FORECLOSURE_LIST_STAGE
    if source_id == MARION_SOURCE_ID:
        if re.search(r"end.of.redemption|redemption.*notice", haystack, re.I):
            return END_REDEMPTION_STAGE
        return FORECLOSURE_LIST_STAGE
    if source_id == MULTNOMAH_SOURCE_ID:
        if re.search(r"tax.title.inventory|inventory", haystack, re.I):
            return TAX_TITLE_INVENTORY_STAGE
        if re.search(r"order-\d{4}-\d+|sale authorization", haystack, re.I):
            return SALE_AUTHORIZATION_STAGE
        return REDEMPTION_NOTICE_STAGE
    if source_id == CLACKAMAS_SOURCE_ID:
        if re.search(r"result|final bid|no bid", haystack, re.I):
            return AUCTION_RESULTS_STAGE
        return AUCTION_OFFERING_STAGE
    raise PublicationQueryError(f"Unknown source: {source_id}")


def _default_publication_page(config: SourceConfig, stage: str) -> str:
    preferred_role: str | None = None
    if stage in {TAX_TITLE_INVENTORY_STAGE, SALE_AUTHORIZATION_STAGE}:
        preferred_role = "tax_title_publication_index"
    elif stage in {AUCTION_OFFERING_STAGE, AUCTION_RESULTS_STAGE}:
        preferred_role = "post_deed_property_disposition_index"
    if preferred_role is not None:
        for page in config.landing_pages:
            if page.role == preferred_role:
                return page.url
    return config.primary_page


def _extract_pdf_text(
    reader: PdfReader,
    *,
    layout: bool,
) -> tuple[str, list[int]]:
    pages: list[str] = []
    page_char_counts: list[int] = []
    for page in reader.pages:
        if layout:
            try:
                value = page.extract_text(extraction_mode="layout") or ""
            except TypeError:
                try:
                    value = page.extract_text() or ""
                except KeyError:
                    value = ""
            except KeyError:
                value = ""
        else:
            try:
                value = page.extract_text() or ""
            except KeyError:
                value = ""
        pages.append(value)
        page_char_counts.append(len(re.sub(r"\s+", "", value)))
    return "\f".join(pages), page_char_counts


def inspect_artifact(
    artifact_path: str | Path,
    *,
    source_id: str,
    process_stage: str | None = None,
    publication_document_id: str | None = None,
    document_url: str | None = None,
    publication_page_url: str | None = None,
    publication_label: str | None = None,
    text_artifact: str | Path | None = None,
    text_method: str | None = None,
) -> dict[str, Any]:
    if source_id not in SOURCES:
        raise PublicationQueryError(f"Unknown source: {source_id}")
    path = Path(artifact_path)
    if not path.is_file():
        raise PublicationUnavailable(
            f"Artifact does not exist: {path}",
            details={"artifact": str(path)},
        )
    artifact_sha256 = _sha256_path(path)
    stage = infer_process_stage(
        source_id,
        explicit_stage=process_stage,
        label=publication_label,
        document_url=document_url,
        artifact_name=path.name,
    )
    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise PublicationChanged(
                    "Publication PDF is encrypted and could not be read",
                    details={"artifact": str(path)},
                ) from exc
        extracted_text, page_char_counts = _extract_pdf_text(
            reader,
            layout=not (
                source_id == MULTNOMAH_SOURCE_ID and stage == TAX_TITLE_INVENTORY_STAGE
            ),
        )
    except (PdfReadError, ValueError, OSError) as exc:
        raise PublicationChanged(
            f"Publication artifact is not a readable PDF: {exc}",
            details={"artifact": str(path)},
        ) from exc

    representation_path: Path | None = None
    representation_method = "embedded_pdf_text"
    if text_artifact is not None:
        representation_path = Path(text_artifact)
        if not representation_path.is_file():
            raise PublicationUnavailable(
                f"Text representation does not exist: {representation_path}",
                details={"text_artifact": str(representation_path)},
            )
        extracted_text = representation_path.read_text(
            encoding="utf-8", errors="replace"
        )
        representation_method = _clean(text_method) or "provided_text"
        page_char_counts = [
            len(re.sub(r"\s+", "", page)) for page in extracted_text.split("\f")
        ]

    searchable_chars = len(re.sub(r"\s+", "", extracted_text))
    text_state = (
        "searchable"
        if searchable_chars >= MIN_SEARCHABLE_TEXT_CHARS
        else "derived_text_needed"
    )
    if process_stage is None:
        stage = infer_process_stage(
            source_id,
            label=publication_label,
            document_url=document_url,
            artifact_name=path.name,
            text=extracted_text[:4_000],
        )
    publication_metadata = extract_publication_metadata(
        source_id,
        stage,
        extracted_text,
        publication_label=publication_label,
        document_url=document_url,
    )
    records: list[dict[str, Any]] = []
    parse_warnings: list[str] = []
    if text_state == "searchable":
        records, parse_warnings = parse_records(
            source_id,
            stage,
            extracted_text,
        )

    metadata = reader.metadata or {}
    text_sha256 = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
    config = SOURCES[source_id]
    document_id = publication_document_id or _document_id(
        source_id,
        stage,
        document_url,
        publication_label or path.name,
    )
    provenance = {
        "source_id": source_id,
        "county_name": config.county_name,
        "publisher": config.publisher,
        "publication_document_id": document_id,
        "process_stage": stage,
        "publication_status": "as_published",
        "publication_label": publication_label,
        "publication_page_url": publication_page_url
        or _default_publication_page(config, stage),
        "document_url": document_url,
        "artifact_path": str(path),
        "artifact_filename": path.name,
        "artifact_sha256": artifact_sha256,
        "artifact_size_bytes": path.stat().st_size,
        "artifact_media_type": "application/pdf",
        "artifact_page_count": len(reader.pages),
        "text_state": text_state,
        "searchable_text_char_count": searchable_chars,
        "page_searchable_char_counts": page_char_counts,
        "text_representation": {
            "method": representation_method,
            "text_sha256": text_sha256,
            "text_artifact_path": (
                str(representation_path) if representation_path else None
            ),
            "parent_artifact_sha256": artifact_sha256,
        },
        **publication_metadata,
    }
    normalized_records = [_attach_provenance(record, provenance) for record in records]
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "source": config.source_metadata().to_dict(),
        "jurisdiction": config.jurisdiction().to_dict(),
        "artifact": {
            "path": str(path),
            "filename": path.name,
            "sha256": artifact_sha256,
            "size_bytes": path.stat().st_size,
            "media_type": "application/pdf",
            "page_count": len(reader.pages),
            "pdf_metadata": {
                str(key).lstrip("/"): str(value)
                for key, value in metadata.items()
                if value is not None
            },
        },
        "publication": provenance,
        "text_state": text_state,
        "searchable_text_char_count": searchable_chars,
        "page_searchable_char_counts": page_char_counts,
        "record_count": len(normalized_records),
        "records": normalized_records,
        "warnings": parse_warnings,
    }


def extract_publication_metadata(
    source_id: str,
    stage: str,
    text: str,
    *,
    publication_label: str | None,
    document_url: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if source_id == TILLAMOOK_SOURCE_ID:
        metadata.update(
            {
                "publication_year": _int_or_none(
                    _first_group(r"For\s+(20\d{2})\s+Foreclosure\s+Tax\s+Year", text)
                ),
                "court_case_number": _first_group(
                    r"Case\s+Number:\s*([0-9A-Z-]+)", text
                ),
                "general_judgment_date": _iso_date(
                    _first_group(r"General\s+Judgment:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
                ),
                "advertising_date": _iso_date(
                    _first_group(r"Advertising\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
                ),
                "deed_to_county_date": _iso_date(
                    _first_group(r"Deed\s+to\s+County:\s*(\d{1,2}/\d{1,2}/\d{4})", text)
                ),
            }
        )
    elif source_id == MARION_SOURCE_ID and stage == END_REDEMPTION_STAGE:
        metadata.update(
            {
                "notice_date": _iso_date(
                    _first_group(
                        r"^\s*([A-Z][A-Z]*[a-z]*\s+\d{1,2},\s+20\d{2})\s*$",
                        text,
                        flags=re.M,
                    )
                ),
                "court_case_number": _first_group(
                    r"Judgment\s+number\s+([0-9A-Z-]+)", text
                ),
                "judgment_date": _iso_date(
                    _first_group(
                        r"Judgment\s+number\s+[0-9A-Z-]+\s+on\s+"
                        r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                        text,
                    )
                ),
                "redemption_expiration_date": _iso_date(
                    _first_group(
                        r"redemption\s+period.*?expire\s+on\s+"
                        r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                        text,
                        flags=re.I | re.S,
                    )
                ),
            }
        )
    elif source_id == MULTNOMAH_SOURCE_ID:
        if stage == REDEMPTION_NOTICE_STAGE:
            metadata.update(
                {
                    "notice_date": _iso_date(
                        _first_group(
                            r"^\s*([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\s*$",
                            text,
                            flags=re.M,
                        )
                    ),
                    "court_case_number": _first_group(
                        r"Circuit\s+Court\s+Case\s+No:\s*([0-9A-Z-]+)", text
                    ),
                    "redemption_expiration_date": _iso_date(
                        _first_group(
                            r"redemption\s+period.*?expires\s+on\s+"
                            r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                            text,
                            flags=re.I | re.S,
                        )
                    ),
                }
            )
        elif stage == TAX_TITLE_INVENTORY_STAGE:
            label_date = _date_from_dotted_label(publication_label or "")
            url_date = _date_from_dotted_label(document_url or "")
            metadata["inventory_as_of_date"] = label_date or url_date
            metadata["publication_year"] = _publication_year(
                " ".join((publication_label or "", document_url or ""))
            )
    elif source_id == CLACKAMAS_SOURCE_ID:
        date_value = _first_group(
            r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\s+Auction",
            text,
        )
        metadata["auction_date"] = _iso_date(date_value)
        metadata["publication_year"] = (
            int(metadata["auction_date"][:4]) if metadata.get("auction_date") else None
        )
    return {key: value for key, value in metadata.items() if value is not None}


def _int_or_none(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


def parse_records(
    source_id: str,
    stage: str,
    text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    if source_id == TILLAMOOK_SOURCE_ID and stage == FORECLOSURE_LIST_STAGE:
        return parse_tillamook_foreclosure_list(text), []
    if source_id == MARION_SOURCE_ID and stage == END_REDEMPTION_STAGE:
        return parse_marion_end_redemption_notices(text), []
    if source_id == MULTNOMAH_SOURCE_ID and stage == REDEMPTION_NOTICE_STAGE:
        return parse_multnomah_redemption_notices(text), []
    if source_id == MULTNOMAH_SOURCE_ID and stage == TAX_TITLE_INVENTORY_STAGE:
        return parse_multnomah_tax_title_inventory(text), []
    if source_id == CLACKAMAS_SOURCE_ID and stage in {
        AUCTION_OFFERING_STAGE,
        AUCTION_RESULTS_STAGE,
    }:
        return parse_clackamas_auction(text, stage=stage), []
    return [], [
        f"No structured property parser is configured for process stage {stage}; "
        "artifact and representation provenance remain available."
    ]


def parse_tillamook_foreclosure_list(text: str) -> list[dict[str, Any]]:
    header = extract_publication_metadata(
        TILLAMOOK_SOURCE_ID,
        FORECLOSURE_LIST_STAGE,
        text,
        publication_label=None,
        document_url=None,
    )
    row_start = re.compile(
        r"^(?P<name>.+?)\s{2,}(?P<code>\d{4})\s+(?P<account>\d+)\s*$"
    )
    map_id = re.compile(r"^[0-9][NS][0-9A-Z]{8,}$", re.I)
    lines = [line.rstrip() for line in text.replace("\f", "\n").splitlines()]
    records: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        match = row_start.match(lines[index])
        if not match:
            index += 1
            continue
        block: list[str] = []
        cursor = index + 1
        property_map_id: str | None = None
        while cursor < len(lines):
            value = lines[cursor].strip()
            if row_start.match(lines[cursor]):
                break
            if map_id.fullmatch(value):
                property_map_id = value.upper()
                cursor += 1
                break
            if value:
                block.append(value)
            cursor += 1
        if property_map_id is None:
            index += 1
            continue
        first_address = next(
            (
                position
                for position, value in enumerate(block)
                if re.match(r"^(?:P\.?\s*O\.?\s+BOX|\d+\s+\S+)", value, re.I)
            ),
            len(block),
        )
        name_lines = [match.group("name").strip(), *block[:first_address]]
        mailing_lines = block[first_address:]
        tax_account = match.group("account")
        case_number = header.get("court_case_number")
        stable_key = ":".join(
            value
            for value in (str(case_number or ""), tax_account, property_map_id)
            if value
        )
        records.append(
            {
                "record_kind": "property_tax_foreclosure_list_entry",
                "process_stage": FORECLOSURE_LIST_STAGE,
                "publication_status": "as_published",
                "stable_property_key": stable_key,
                "tax_account": tax_account,
                "property_map_id": property_map_id,
                "code_area": match.group("code"),
                "published_name": name_lines[0],
                "published_name_lines": name_lines,
                "mailing_address_lines": mailing_lines,
                "mailing_address": _clean(" ".join(mailing_lines)) or None,
                "court_case_number": case_number,
                "foreclosure_tax_year": header.get("publication_year"),
                "general_judgment_date": header.get("general_judgment_date"),
                "advertising_date": header.get("advertising_date"),
                "deed_to_county_date": header.get("deed_to_county_date"),
                "raw": {
                    "header_line": lines[index].strip(),
                    "detail_lines": block,
                    "property_map_id": property_map_id,
                },
            }
        )
        index = cursor
    return records


def _field_between(
    page: str,
    label: str,
    next_label: str,
) -> str | None:
    match = re.search(
        rf"^{re.escape(label)}:\s*(.*?)\n{re.escape(next_label)}:",
        page,
        re.M | re.S | re.I,
    )
    return _clean(match.group(1)) if match else None


def parse_marion_end_redemption_notices(text: str) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for page_number, page in enumerate(text.split("\f"), start=1):
        if not re.search(r"^Property\s+Owner:", page, re.M | re.I):
            continue
        account = _first_group(
            r"^Account\s+Number:\s*([0-9A-Z-]+)\s*$",
            page,
            flags=re.M | re.I,
        )
        if not account:
            continue
        owner = _field_between(page, "Property Owner", "Map Tax Lot")
        map_tax_lot = _field_between(page, "Map Tax Lot", "Situs Address")
        situs = _field_between(page, "Situs Address", "Case/Reference No.")
        case_detail = _field_between(page, "Case/Reference No.", "Total Amount Due")
        case_number = _first_group(r"\b(\d{2}CV-?\d{5})\b", case_detail or page)
        total_due = _money(
            _first_group(r"^Total\s+Amount\s+Due:\s*(\$[\d,]+\.\d{2})", page)
        )
        redemption_date = _iso_date(
            _first_group(
                r"redemption\s+period.*?expire\s+on\s+"
                r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                page,
                flags=re.I | re.S,
            )
        )
        judgment_date = _iso_date(
            _first_group(
                r"Judgment\s+number\s+[0-9A-Z-]+\s+on\s+"
                r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                page,
            )
        )
        notice_date = _iso_date(
            _first_group(
                r"^\s*([A-Z][A-Z]*[a-z]*\s+\d{1,2},\s+20\d{2})\s*$",
                page,
                flags=re.M,
            )
        )
        record = {
            "record_kind": "property_tax_foreclosure_redemption_notice",
            "process_stage": END_REDEMPTION_STAGE,
            "publication_status": "as_published",
            "stable_property_key": ":".join(
                value for value in (case_number, account) if value
            ),
            "tax_account": account,
            "map_tax_lot": map_tax_lot or None,
            "property_owner": owner,
            "situs_address": situs,
            "court_case_number": case_number,
            "case_reference_detail": case_detail,
            "amounts": {
                "total_due_as_published": total_due,
                "currency": "USD",
            },
            "notice_date": notice_date,
            "judgment_date": judgment_date,
            "redemption_expiration_date": redemption_date,
            "published_notice_copy_count": 1,
            "source_page_numbers": [page_number],
            "raw": {"notice_page": page.strip()},
        }
        existing = found.get(account)
        if existing is None:
            found[account] = record
            continue
        existing["published_notice_copy_count"] += 1
        existing["source_page_numbers"].append(page_number)
        for field in (
            "map_tax_lot",
            "property_owner",
            "situs_address",
            "court_case_number",
            "case_reference_detail",
            "notice_date",
            "judgment_date",
            "redemption_expiration_date",
        ):
            if not existing.get(field) and record.get(field):
                existing[field] = record[field]
        if (
            existing["amounts"].get("total_due_as_published") is None
            and total_due is not None
        ):
            existing["amounts"]["total_due_as_published"] = total_due
    return sorted(found.values(), key=lambda item: item["tax_account"])


def parse_multnomah_redemption_notices(text: str) -> list[dict[str, Any]]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for page_number, page in enumerate(text.split("\f"), start=1):
        property_id = _first_group(r"Real\s+Property\s+ID\s+No\.:\s*(R\d+)", page)
        if not property_id:
            continue
        case_number = (
            _first_group(r"Circuit\s+Court\s+Case\s+No:\s*([0-9A-Z-]+)", page) or ""
        )
        key = (property_id, case_number)
        record = {
            "record_kind": "property_tax_foreclosure_redemption_notice",
            "process_stage": REDEMPTION_NOTICE_STAGE,
            "publication_status": "as_published",
            "stable_property_key": ":".join(value for value in key if value),
            "real_property_id": property_id,
            "legal_description": _first_group(
                r"Real\s+Property\s+Legal\s+Description:\s*(.*?)\n\s*"
                r"Street\s+Address:",
                page,
                flags=re.I | re.S,
            ),
            "street_address": _first_group(
                r"Street\s+Address:\s*(.*?)\n\s*Real\s+Property\s+ID",
                page,
                flags=re.I | re.S,
            ),
            "court_case_number": case_number or None,
            "court_name": _first_group(
                r"The\s+Court\s+Where\s+Judgment\s+Entered:\s*(.*?)\n",
                page,
            ),
            "owner_as_shown_on_tax_roll": _first_group(
                r"Owner\s+as\s+Shown\s+on\s+Tax\s+Roll:\s*(.*?)\n", page
            ),
            "notice_date": _iso_date(
                _first_group(
                    r"^\s*([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\s*$",
                    page,
                    flags=re.M,
                )
            ),
            "judgment_date": _iso_date(
                _first_group(
                    r"The\s+Date\s+Judgment\s+Entered:\s*"
                    r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                    page,
                )
            ),
            "redemption_expiration_date": _iso_date(
                _first_group(
                    r"redemption\s+period.*?expires\s+on\s+"
                    r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})",
                    page,
                    flags=re.I | re.S,
                )
            ),
            "published_notice_copy_count": 1,
            "source_page_numbers": [page_number],
            "raw": {"notice_page": page.strip()},
        }
        existing = found.get(key)
        if existing is None:
            found[key] = record
            continue
        existing["published_notice_copy_count"] += 1
        existing["source_page_numbers"].append(page_number)
    return sorted(
        found.values(),
        key=lambda item: (
            item["real_property_id"],
            item.get("court_case_number") or "",
        ),
    )


INVENTORY_ROW_RE = re.compile(
    r"^(?P<property_id>R\d+)\s+"
    r"(?P<received>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<status>[A-Za-z]+)\s+"
    r"(?P<map_id>[0-9][NS][0-9][EW][0-9A-Z]+\s+-\d+)"
)


def parse_multnomah_tax_title_inventory(text: str) -> list[dict[str, Any]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw_line in text.splitlines():
        line = raw_line.lstrip("\f")
        if INVENTORY_ROW_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current:
        blocks.append(current)

    records: list[dict[str, Any]] = []
    for block in blocks:
        first = block[0]
        match = INVENTORY_ROW_RE.match(first)
        if not match:
            continue
        raw_block = "\n".join(block).rstrip()
        money_matches = list(re.finditer(r"\$[\d,]+\.\d{2}", raw_block))
        total_decree = (
            _money(money_matches[-2].group(0)) if len(money_matches) >= 2 else None
        )
        market_value = _money(money_matches[-1].group(0)) if money_matches else None
        layout_row = (
            len(first) >= 120 and len(re.findall(r"\$[\d,]+\.\d{2}", first)) >= 2
        )
        if layout_row:
            size_raw = first[46:55].strip() or None
            address_raw = first[55:82].strip() or None
            first_money = list(re.finditer(r"\$[\d,]+\.\d{2}", first))
            comment_end = (
                first_money[-2].start() if len(first_money) >= 2 else len(first)
            )
            comments = [first[82:comment_end].strip()]
            for continuation in block[1:]:
                value = (
                    continuation[82:].strip()
                    if len(continuation) > 82
                    else continuation.strip()
                )
                if value and not re.match(r"^(?:Tax Title|Property:|ID\s+Date)", value):
                    comments.append(value)
        else:
            size_raw = None
            address_raw = None
            remainder = raw_block[match.end() :]
            remainder = re.sub(r"\$[\d,]+\.\d{2}", " ", remainder)
            comments = [_clean(remainder)]
        property_id = match.group("property_id")
        map_id = _clean(match.group("map_id"))
        records.append(
            {
                "record_kind": "tax_title_inventory_property",
                "process_stage": TAX_TITLE_INVENTORY_STAGE,
                "publication_status": "as_published",
                "stable_property_key": property_id,
                "real_property_id": property_id,
                "property_received_date": _iso_date(match.group("received")),
                "inventory_status": match.group("status"),
                "map_id": map_id,
                "size_square_feet_raw": size_raw,
                "size_square_feet": _number_or_none(size_raw),
                "street_address": address_raw,
                "comments": _clean(" ".join(comments)) or None,
                "amounts": {
                    "total_decree": total_decree,
                    "market_value_as_of_received_date": market_value,
                    "currency": "USD",
                },
                "raw": {"inventory_block": "\n".join(block).rstrip()},
            }
        )
    return records


def _number_or_none(value: str | None) -> float | int | None:
    if not value:
        return None
    normalized = value.replace(",", "").strip()
    try:
        result = float(normalized)
    except ValueError:
        return None
    return int(result) if result.is_integer() else result


AUCTION_ITEM_RE = re.compile(r"(?m)^[ \t]*(\d{1,3})(?=$|[ \t]+(?:$|\d{1,2}[A-Z]\d))")
AUCTION_MAP_RE = re.compile(
    r"(?m)^[ \t]*"
    r"((?:\d{1,2}[A-Z]\d{1,2}[A-Z0-9]*[ \t]*\d{5}[A-Z0-9]*))"
    r"[ \t]*$"
)


def parse_clackamas_auction(
    text: str,
    *,
    stage: str,
) -> list[dict[str, Any]]:
    if stage not in {AUCTION_OFFERING_STAGE, AUCTION_RESULTS_STAGE}:
        raise PublicationQueryError(f"Unsupported Clackamas auction stage: {stage}")
    auction_date = _iso_date(
        _first_group(
            r"([A-Z][a-z]+\s+\d{1,2},\s+20\d{2})\s+Auction",
            text,
        )
    )
    markers = list(AUCTION_ITEM_RE.finditer(text))
    records: list[dict[str, Any]] = []
    for index, marker in enumerate(markers):
        item_number = int(marker.group(1))
        block = (
            text[marker.end() : markers[index + 1].start()]
            if index + 1 < len(markers)
            else text[marker.end() :]
        )
        map_match = AUCTION_MAP_RE.search(block)
        if not map_match:
            continue
        map_tax_lot = re.sub(r"\s+", "", map_match.group(1)).upper()
        acres = _number_or_none(_first_group(r"Approx\.\s+Acres:\s*([0-9.]+)", block))
        description = _first_group(
            r"Unimproved\s+parcel\s+located\s+at\s+(.*?)"
            r"Approx\.\s+Acres:",
            block,
            flags=re.I | re.S,
        )
        amounts = [
            _money(match.group(0))
            for match in re.finditer(r"\$\s*[\d,]+(?:\.\d{2})?", block)
        ]
        real_market_value = amounts[0] if amounts else None
        minimum_bid = amounts[1] if len(amounts) > 1 else None
        third_amount = amounts[2] if len(amounts) > 2 else None
        record = {
            "record_kind": (
                "tax_foreclosed_property_auction_result"
                if stage == AUCTION_RESULTS_STAGE
                else "tax_foreclosed_property_auction_offering"
            ),
            "process_stage": stage,
            "publication_status": "as_published",
            "stable_property_key": ":".join(
                value
                for value in (
                    auction_date or "",
                    str(item_number),
                    map_tax_lot,
                )
                if value
            ),
            "auction_date": auction_date,
            "auction_item": item_number,
            "map_tax_lot": map_tax_lot,
            "situs_description": description,
            "approximate_acres": acres,
            "assessor_real_market_value": real_market_value,
            "minimum_bid": minimum_bid,
            "currency": "USD",
            "raw": {"auction_item_block": block.strip()},
        }
        if stage == AUCTION_RESULTS_STAGE:
            record["auction_result"] = (
                "no_bid" if re.search(r"\bNo\s+Bid\b", block, re.I) else "sold"
            )
            record["final_bid"] = third_amount
        else:
            record["deposit_amount"] = third_amount
        records.append(record)
    return records


def _attach_provenance(
    record: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(record)
    result.update(
        {
            "source_id": provenance["source_id"],
            "county_name": provenance["county_name"],
            "publisher": provenance["publisher"],
            "publication_document_id": provenance["publication_document_id"],
            "process_stage": provenance["process_stage"],
            "publication_status": provenance["publication_status"],
            "publication_label": provenance.get("publication_label"),
            "publication_page_url": provenance.get("publication_page_url"),
            "document_url": provenance.get("document_url"),
            "artifact_sha256": provenance["artifact_sha256"],
            "artifact_filename": provenance["artifact_filename"],
            "artifact_media_type": provenance["artifact_media_type"],
            "artifact_page_count": provenance["artifact_page_count"],
            "text_state": provenance["text_state"],
            "searchable_text_char_count": provenance[
                "searchable_text_char_count"
            ],
            "page_searchable_char_counts": list(
                provenance["page_searchable_char_counts"]
            ),
            "text_representation": dict(provenance["text_representation"]),
        }
    )
    for field in (
        "publication_year",
        "publication_date",
        "court_case_number",
        "notice_date",
        "judgment_date",
        "general_judgment_date",
        "advertising_date",
        "redemption_expiration_date",
        "deed_to_county_date",
        "inventory_as_of_date",
        "auction_date",
    ):
        if result.get(field) is None and provenance.get(field) is not None:
            result[field] = provenance[field]
    return result


def _criteria(args: argparse.Namespace) -> dict[str, Any]:
    return {
        field: getattr(args, field, None)
        for field in (
            "query",
            "owner",
            "account",
            "map_tax_lot",
            "property_id",
            "address",
            "case",
        )
        if getattr(args, field, None)
    }


def _matches(record: Mapping[str, Any], criteria: Mapping[str, Any]) -> bool:
    if not criteria:
        return True
    searchable = {
        "owner": " ".join(
            str(record.get(field) or "")
            for field in (
                "published_name",
                "published_name_lines",
                "property_owner",
                "owner_as_shown_on_tax_roll",
            )
        ),
        "account": " ".join(
            str(record.get(field) or "")
            for field in ("tax_account", "real_property_id")
        ),
        "map_tax_lot": " ".join(
            str(record.get(field) or "")
            for field in ("map_tax_lot", "property_map_id", "map_id")
        ),
        "property_id": str(record.get("real_property_id") or ""),
        "address": " ".join(
            str(record.get(field) or "")
            for field in (
                "mailing_address",
                "situs_address",
                "street_address",
                "situs_description",
            )
        ),
        "case": str(record.get("court_case_number") or ""),
        "query": canonical_json(record),
    }
    for field, value in criteria.items():
        needle = _clean(str(value)).casefold()
        if needle not in searchable[field].casefold():
            return False
    return True


def _encode_cursor(
    *,
    source_id: str,
    artifact_sha256: str,
    criteria_fingerprint: str,
    offset: int,
) -> str:
    payload = canonical_json(
        {
            "v": 1,
            "source_id": source_id,
            "artifact_sha256": artifact_sha256,
            "criteria_fingerprint": criteria_fingerprint,
            "offset": offset,
        }
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return CURSOR_PREFIX + encoded


def _decode_cursor(
    cursor: str,
    *,
    source_id: str,
    artifact_sha256: str,
    criteria_fingerprint: str,
) -> int:
    if not cursor.startswith(CURSOR_PREFIX):
        raise PublicationQueryError("Cursor does not belong to this adapter")
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        payload = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
    except (ValueError, json.JSONDecodeError) as exc:
        raise PublicationQueryError("Cursor is not valid") from exc
    expected = {
        "v": 1,
        "source_id": source_id,
        "artifact_sha256": artifact_sha256,
        "criteria_fingerprint": criteria_fingerprint,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            raise PublicationQueryError(
                "Cursor does not match this artifact and search",
                details={"mismatched_field": key},
            )
    offset = payload.get("offset")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise PublicationQueryError("Cursor offset is not valid")
    return offset


def build_query(
    args: argparse.Namespace,
    *,
    source_id: str,
    access_decision: Mapping[str, Any] | None = None,
    inspection: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    config = SOURCES[source_id]
    publication = (
        inspection.get("publication")
        if isinstance(inspection, Mapping)
        and isinstance(inspection.get("publication"), Mapping)
        else {}
    )
    requested_stage = getattr(args, "process_stage", None)
    resolved_stage = publication.get("process_stage") or requested_stage
    publication_snapshot = {
        field: publication.get(field)
        for field in (
            "publication_document_id",
            "process_stage",
            "publication_status",
            "publication_label",
            "publication_page_url",
            "document_url",
            "artifact_filename",
            "artifact_sha256",
            "artifact_size_bytes",
            "artifact_media_type",
            "artifact_page_count",
            "text_state",
            "searchable_text_char_count",
            "page_searchable_char_counts",
            "text_representation",
            "publication_year",
            "publication_date",
            "court_case_number",
            "notice_date",
            "judgment_date",
            "general_judgment_date",
            "advertising_date",
            "redemption_expiration_date",
            "deed_to_county_date",
            "inventory_as_of_date",
            "auction_date",
        )
        if publication.get(field) is not None
    }
    return PublicRecordsQuery(
        source=config.source_metadata(),
        jurisdiction=config.jurisdiction(),
        query=QueryMetadata(
            operation=args.command,
            parameters={
                "process_stage": resolved_stage,
                "requested_process_stage": requested_stage,
                "resolved_process_stage": resolved_stage,
                "criteria": _criteria(args),
                "artifact": getattr(args, "artifact", None),
                "text_artifact": getattr(args, "text_artifact", None),
                "publication": publication_snapshot or None,
            },
            requested_limit=getattr(args, "max_records", None),
            cursor=getattr(args, "cursor", None),
            metadata={"access_decision": dict(access_decision or {})},
        ),
    )


def search_inspection(
    inspection: Mapping[str, Any],
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
) -> PublicRecordsResult:
    source_id = args.source
    query = build_query(
        args,
        source_id=source_id,
        access_decision=access_decision,
        inspection=inspection,
    )
    artifact = inspection["artifact"]
    artifact_sha256 = str(artifact["sha256"])
    if inspection["text_state"] != "searchable":
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            (
                PublicRecordsError(
                    code="derived_text_needed",
                    message=(
                        "The official PDF has no usable embedded text. Supply a "
                        "text representation with --text-artifact and identify "
                        "its method with --text-method."
                    ),
                    category="document_representation",
                    details={
                        "artifact_sha256": artifact_sha256,
                        "page_count": artifact["page_count"],
                    },
                ),
            ),
            raw_artifact_refs=(artifact_sha256,),
        )

    criteria = _criteria(args)
    criteria_fingerprint = sha256_fingerprint(criteria)
    offset = 0
    if args.cursor:
        offset = _decode_cursor(
            args.cursor,
            source_id=source_id,
            artifact_sha256=artifact_sha256,
            criteria_fingerprint=criteria_fingerprint,
        )
    records = [
        dict(record) for record in inspection["records"] if _matches(record, criteria)
    ]
    selected = records[offset:]
    next_cursor: str | None = None
    if args.max_records is not None and len(selected) > args.max_records:
        selected = selected[: args.max_records]
        next_cursor = _encode_cursor(
            source_id=source_id,
            artifact_sha256=artifact_sha256,
            criteria_fingerprint=criteria_fingerprint,
            offset=offset + len(selected),
        )
    warnings = tuple(str(value) for value in inspection.get("warnings", ()))
    if next_cursor:
        return PublicRecordsResult(
            query=query,
            status=ResultStatus.PARTIAL,
            records=selected,
            next_cursor=next_cursor,
            raw_artifact_refs=(artifact_sha256,),
            warnings=warnings,
        )
    return PublicRecordsResult.success(
        query,
        selected,
        raw_artifact_refs=(artifact_sha256,),
        warnings=warnings,
    )


def _select_route(
    discovery: Mapping[str, Any],
    *,
    process_stage: str | None,
) -> Mapping[str, Any]:
    candidates = [
        route
        for route in discovery["publication_routes"]
        if route.get("document_url")
        and (process_stage is None or route.get("process_stage") == process_stage)
    ]
    if not candidates:
        raise PublicationUnavailable(
            "No linked official publication matched the requested source and stage",
            details={"process_stage": process_stage},
        )
    return candidates[0]


def _download_document(
    url: str,
    destination: Path,
    *,
    timeout: float,
    max_bytes: int,
    fetcher: FetchBytes,
) -> dict[str, Any]:
    payload = fetcher(url, timeout, max_bytes)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return {
        "url": url,
        "destination": str(destination),
        "sha256": _sha256_bytes(payload),
        "size_bytes": len(payload),
    }


def execute(
    args: argparse.Namespace,
    *,
    access_decision: Mapping[str, Any] | None = None,
    fetcher: FetchBytes = fetch_bytes,
) -> Any:
    if args.command == "sources":
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "sources": [SOURCES[source_id].to_dict() for source_id in sorted(SOURCES)],
            "process_stages": list(PROCESS_STAGES),
        }

    if args.command == "discover":
        source_ids = sorted(SOURCES) if args.all else [args.source]
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "discoveries": [
                discover_source(
                    SOURCES[source_id],
                    timeout=args.timeout,
                    max_page_bytes=args.max_page_bytes,
                    fetcher=fetcher,
                )
                for source_id in source_ids
            ],
        }

    if args.command == "download":
        config = SOURCES[args.source]
        document_url = args.document_url
        route: Mapping[str, Any] | None = None
        if document_url is None:
            discovery = discover_source(
                config,
                timeout=args.timeout,
                max_page_bytes=args.max_page_bytes,
                fetcher=fetcher,
            )
            route = _select_route(discovery, process_stage=args.process_stage)
            document_url = str(route["document_url"])
        result = _download_document(
            document_url,
            Path(args.destination),
            timeout=args.timeout,
            max_bytes=args.max_document_bytes,
            fetcher=fetcher,
        )
        result["source_id"] = args.source
        result["process_stage"] = (
            route.get("process_stage") if route else args.process_stage
        )
        result["publication_route"] = dict(route) if route else None
        return result

    if args.command == "inspect":
        return inspect_artifact(
            args.artifact,
            source_id=args.source,
            process_stage=args.process_stage,
            document_url=args.document_url,
            publication_page_url=args.publication_page_url,
            publication_label=args.publication_label,
            text_artifact=args.text_artifact,
            text_method=args.text_method,
        )

    if args.command == "search":
        artifact_path: Path
        document_url = args.document_url
        publication_page_url = args.publication_page_url
        publication_label = args.publication_label
        process_stage = args.process_stage
        publication_document_id: str | None = None
        temporary: tempfile.TemporaryDirectory[str] | None = None
        if args.artifact:
            artifact_path = Path(args.artifact)
        else:
            discovery = discover_source(
                SOURCES[args.source],
                timeout=args.timeout,
                max_page_bytes=args.max_page_bytes,
                fetcher=fetcher,
            )
            route = _select_route(discovery, process_stage=args.process_stage)
            document_url = str(route["document_url"])
            publication_page_url = str(route["publication_page_url"])
            publication_label = str(route["publication_label"])
            process_stage = str(route["process_stage"])
            publication_document_id = str(route["document_id"])
            temporary = tempfile.TemporaryDirectory(
                prefix="osint-oregon-tax-publication-"
            )
            artifact_path = Path(temporary.name) / (
                Path(urlsplit(document_url).path).name or "publication.pdf"
            )
            _download_document(
                document_url,
                artifact_path,
                timeout=args.timeout,
                max_bytes=args.max_document_bytes,
                fetcher=fetcher,
            )
        try:
            inspection = inspect_artifact(
                artifact_path,
                source_id=args.source,
                process_stage=process_stage,
                publication_document_id=publication_document_id,
                document_url=document_url,
                publication_page_url=publication_page_url,
                publication_label=publication_label,
                text_artifact=args.text_artifact,
                text_method=args.text_method,
            )
            return search_inspection(
                inspection,
                args,
                access_decision=access_decision,
            )
        finally:
            if temporary is not None:
                temporary.cleanup()

    if args.command == "probe":
        source_ids = sorted(SOURCES) if args.all else [args.source]
        probes: list[dict[str, Any]] = []
        for source_id in source_ids:
            discovery = discover_source(
                SOURCES[source_id],
                timeout=args.timeout,
                max_page_bytes=args.max_page_bytes,
                fetcher=fetcher,
            )
            probes.append(
                {
                    "source_id": source_id,
                    "status": "ok",
                    "landing_page_count": len(discovery["landing_page_observations"]),
                    "publication_route_count": len(discovery["publication_routes"]),
                    "process_stages": sorted(
                        {
                            route["process_stage"]
                            for route in discovery["publication_routes"]
                        }
                    ),
                    "landing_page_observations": discovery["landing_page_observations"],
                }
            )
        return {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "probes": probes,
        }

    raise PublicationQueryError(f"Unknown command: {args.command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser("sources", help="Describe covered sources")
    add_output_args(sources)

    discover = subparsers.add_parser(
        "discover", help="Discover official publication artifacts"
    )
    _add_source_or_all(discover)
    _add_network_args(discover, include_document_ceiling=False)
    add_output_args(discover)

    download = subparsers.add_parser(
        "download", help="Download one official publication artifact"
    )
    download.add_argument("--source", choices=sorted(SOURCES), required=True)
    download.add_argument("--process-stage", choices=PROCESS_STAGES)
    download.add_argument("--document-url")
    download.add_argument("--destination", required=True)
    _add_network_args(download, include_document_ceiling=True)
    add_output_args(download)

    inspect = subparsers.add_parser(
        "inspect", help="Inspect and parse a local publication PDF"
    )
    _add_artifact_args(inspect)
    add_output_args(inspect)

    search = subparsers.add_parser(
        "search", help="Search one local or current official publication"
    )
    _add_artifact_args(search, artifact_required=False)
    search.add_argument("--query")
    search.add_argument("--owner")
    search.add_argument("--account")
    search.add_argument("--map-tax-lot")
    search.add_argument("--property-id")
    search.add_argument("--address")
    search.add_argument("--case")
    search.add_argument("--max-records", type=_positive_int)
    search.add_argument("--cursor")
    _add_network_args(search, include_document_ceiling=True)
    add_output_args(search)

    probe = subparsers.add_parser(
        "probe", help="Probe landing pages and discovery schemas"
    )
    _add_source_or_all(probe)
    _add_network_args(probe, include_document_ceiling=False)
    add_output_args(probe)
    return parser


def _add_source_or_all(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", choices=sorted(SOURCES))
    group.add_argument("--all", action="store_true")


def _add_artifact_args(
    parser: argparse.ArgumentParser,
    *,
    artifact_required: bool = True,
) -> None:
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--artifact", required=artifact_required)
    parser.add_argument("--process-stage", choices=PROCESS_STAGES)
    parser.add_argument("--document-url")
    parser.add_argument("--publication-page-url")
    parser.add_argument("--publication-label")
    parser.add_argument("--text-artifact")
    parser.add_argument(
        "--text-method",
        help="Method used to create --text-artifact, such as OCR or LLM transcription",
    )


def _add_network_args(
    parser: argparse.ArgumentParser,
    *,
    include_document_ceiling: bool,
) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--max-page-bytes", type=_positive_int, default=DEFAULT_MAX_PAGE_BYTES
    )
    if include_document_ceiling:
        parser.add_argument(
            "--max-document-bytes",
            type=_positive_int,
            default=DEFAULT_MAX_DOCUMENT_BYTES,
        )


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed


def _emit(result: Any, args: argparse.Namespace) -> None:
    payload = result.to_dict() if isinstance(result, PublicRecordsResult) else result
    if write_output(
        payload,
        args,
        summary=f"Oregon tax foreclosure {args.command}",
    ):
        return
    print(json.dumps(payload, indent=2, default=str))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = execute(args)
    except OregonTaxPublicationError as exc:
        payload = {
            "status": exc.result_status.value,
            "error": {
                "code": exc.code,
                "message": str(exc),
                "category": exc.category,
                "retryable": exc.retryable,
                "details": exc.details,
            },
        }
        if write_output(
            payload,
            args,
            summary=f"Oregon tax foreclosure {args.command}",
            result_count=None,
        ):
            return 2
        print(json.dumps(payload, indent=2), file=sys.stderr)
        return 2
    _emit(result, args)
    if args.command == "search":
        payload = result.to_dict()
        try:
            log_search(
                canonical_json(_criteria(args)),
                "oregon_tax_foreclosures",
                len(payload.get("records", [])),
            )
        except Exception as exc:
            print(f"Warning: search log was not updated: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
