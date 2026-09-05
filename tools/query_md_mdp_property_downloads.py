#!/usr/bin/env python3
"""Discover, transfer, and inspect Maryland MDP property downloads.

The Maryland Department of Planning (MDP) publishes three related statewide
property-data families from one official page:

* parcel point/polygon geodatabases and their schema workbook;
* Computer Assisted Mass Appraisal (CAMA) releases; and
* monthly property-sales analytic releases and their schema workbook.

Dropbox carries the publisher-linked files, but MDP and the Maryland State
Department of Assessments and Taxation (SDAT) remain the data authorities.
Release slots, provider-link identities, downloaded artifact occurrences, ZIP
member occurrences, parcel/account identities, CAMA component occurrences,
and candidate sale identities are represented separately.

The wrapper deliberately stops at manifest, transfer, and archive inspection.
It does not claim row search for uninspected geodatabase or table members.

Examples:
    uv run python tools/query_md_mdp_property_downloads.py manifest --json
    uv run python tools/query_md_mdp_property_downloads.py prepare \
        --source us-md-mdp-property-sales-downloads --json
    uv run python tools/query_md_mdp_property_downloads.py download \
        --source us-md-mdp-cama-downloads \
        --release cama-2026-q1-statewide \
        --destination /tmp/2026-Q1-Statewide-CAMA.zip \
        --inspect --output /tmp/md-cama-download.json
    uv run python tools/query_md_mdp_property_downloads.py inspect \
        /tmp/Property_Sales_0226.zip \
        --source us-md-mdp-property-sales-downloads --json
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlsplit,
    urlunsplit,
)
from urllib.request import Request, urlopen

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        inspect_zip,
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
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
        DownloadResult,
        inspect_zip,
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


PARCEL_SOURCE_ID = "us-md-mdp-parcel-downloads"
CAMA_SOURCE_ID = "us-md-mdp-cama-downloads"
SALES_SOURCE_ID = "us-md-mdp-property-sales-downloads"
SOURCE_IDS = (PARCEL_SOURCE_ID, CAMA_SOURCE_ID, SALES_SOURCE_ID)

SDAT_PROPERTY_IDENTITY_SOURCE_ID = "us-md-sdat-property-hidden"

LANDING_URL = (
    "https://planning.maryland.gov/MSDC/Pages/9_gam/"
    "district-download-gis-files.aspx"
)
PARCEL_INFORMATION_URL = (
    "https://planning.maryland.gov/MSDC/Pages/91_property_mapping/"
    "parcel-data.aspx"
)
DROPBOX_DOWNLOAD_HELP_URL = (
    "https://help.dropbox.com/share/force-download"
)
SALES_METHODOLOGY_URL = (
    "https://planning.maryland.gov/MSDC/Documents/Sale_Data/"
    "SalesMethodology_CY2024.pdf"
)

OUTPUT_SCHEMA_VERSION = "maryland-mdp-property-downloads/1.0"
MANIFEST_SCHEMA_VERSION = "maryland-mdp-property-download-manifest/1.0"
PROBE_SCHEMA_VERSION = "maryland-mdp-property-download-probe/1.0"
INSPECTION_SCHEMA_VERSION = "maryland-mdp-property-download-inspection/1.0"
CURSOR_PREFIX = "maryland-mdp-property-downloads:v1:"
CURSOR_VERSION = 1

DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_CHUNK_SIZE = 1024 * 1024
DEFAULT_SAMPLE_BYTES = 4096
ZIP_CONTAINER_SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
)

STATE_CODE = "MD"
STATE_FIPS = "24"
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_FIPS,
    name="Maryland",
    state_code=STATE_CODE,
    metadata={"state_fips": STATE_FIPS},
)

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

CAMA_COMPONENT_ALIASES = {
    "core": "core",
    "bldg": "building",
    "building": "building",
    "land": "land",
    "suba": "subareas",
    "subarea": "subareas",
    "subareas": "subareas",
}

CAMA_ROW_OCCURRENCE_KEY = [
    "artifact_sha256",
    "archive_member_path",
    "row_ordinal",
]

CAMA_COMPONENT_CONTRACTS: dict[str, dict[str, Any]] = {
    "core": {
        "record_grain": "one_record_per_parcel_account",
        "parcel_join_key": "ACCTID",
        "semantic_component_key": "ACCTID",
        "component_occurrence_key": CAMA_ROW_OCCURRENCE_KEY,
        "joins": {
            "building": "ACCTID",
            "land": "ACCTID",
            "subareas": "through_building_and_CAMALINK",
        },
    },
    "building": {
        "record_grain": "multiple_records_per_parcel_account",
        "parcel_join_key": "ACCTID",
        "component_occurrence_key": CAMA_ROW_OCCURRENCE_KEY,
        "joins": {
            "core": "ACCTID",
            "subareas": "CAMALINK",
        },
    },
    "land": {
        "record_grain": "multiple_records_per_parcel_account",
        "parcel_join_key": "ACCTID",
        "component_occurrence_key": CAMA_ROW_OCCURRENCE_KEY,
        "joins": {"core": "ACCTID"},
        "scope": "property_land_characteristic_not_building",
    },
    "subareas": {
        "record_grain": "multiple_records_per_building",
        "parcel_join_key": "ACCTID",
        "component_occurrence_key": CAMA_ROW_OCCURRENCE_KEY,
        "joins": {"building": "CAMALINK"},
    },
    "statewide_bundle": {
        "record_grain": "component_specific",
        "parcel_join_key": "ACCTID",
        "component_occurrence_key": CAMA_ROW_OCCURRENCE_KEY,
        "components": ["core", "building", "land", "subareas"],
    },
}

SALES_IDENTITY_CONTRACT = {
    "artifact_occurrence_key": "artifact_sha256",
    "transport_validator_occurrence_key": "validator_occurrence_id",
    "row_occurrence": [
        "artifact_sha256",
        "archive_member_path",
        "row_ordinal",
    ],
    "semantic_transaction_candidate": [
        "ACCTID",
        "TRADATE",
        "CONSIDR1",
    ],
    "semantic_transaction_candidate_basis": (
        "MDP residential-sales methodology duplicate review"
    ),
    "source_issued_transaction_identifier_verified": False,
    "monthly_release_rows_may_repeat": True,
}

SOURCE_WARNINGS = {
    PARCEL_SOURCE_ID: (
        "The parcel bulk files are another MDP/SDAT representation of parcel "
        "accounts. ACCTID is the join to the existing statewide assessment "
        "source, not independent corroboration.",
        "Preserve the publisher release slot separately from each downloaded "
        "artifact digest and member occurrence.",
    ),
    CAMA_SOURCE_ID: (
        "CAMA Core, Building, Land, and Subareas have different row grains. "
        "ACCTID joins components to parcels; CAMALINK relates Building and "
        "Subareas.",
        "Quarterly and historical links are publisher release artifacts. "
        "Artifact validators and digests identify observed occurrences.",
    ),
    SALES_SOURCE_ID: (
        "The MDP sales files are residential-sales analytic releases. They "
        "do not represent complete Maryland deed history.",
        "Monthly releases may repeat a sale. Preserve artifact and row "
        "occurrence identity separately from candidate transaction identity.",
        "ACCTID, trade date, and consideration form a documented "
        "deduplication candidate, not a source-issued transaction ID.",
    ),
}


def _source_metadata(source_id: str) -> SourceMetadata:
    common = {
        "authority": (
            "Maryland Department of Planning and Maryland State Department "
            "of Assessments and Taxation"
        ),
        "coverage": "State of Maryland",
        "official_listing_url": LANDING_URL,
        "transport_provider": "Dropbox publisher-linked shared files",
        "transport_authority": False,
    }
    if source_id == PARCEL_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Maryland MDP Statewide Parcel Downloads",
            source_role="statewide_parcel_bulk_representation",
            base_url=LANDING_URL,
            dataset_id="mdp-statewide-parcels",
            metadata={
                **common,
                "record_identity_source_id": (
                    SDAT_PROPERTY_IDENTITY_SOURCE_ID
                ),
                "parcel_join_key": "ACCTID",
                "representation": "bulk_gis_files",
                "property_mapping_information_url": (
                    PARCEL_INFORMATION_URL
                ),
            },
        )
    if source_id == CAMA_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Maryland MDP CAMA Downloads",
            source_role="statewide_cama_bulk_releases",
            base_url=LANDING_URL,
            dataset_id="mdp-statewide-cama",
            metadata={
                **common,
                "parcel_join_key": "ACCTID",
                "building_subarea_join_key": "CAMALINK",
                "component_contracts": CAMA_COMPONENT_CONTRACTS,
            },
        )
    if source_id == SALES_SOURCE_ID:
        return SourceMetadata(
            source_id=source_id,
            name="Maryland MDP Property Sales Downloads",
            source_role="statewide_residential_sales_analytic_bulk",
            base_url=LANDING_URL,
            dataset_id="mdp-property-sales",
            metadata={
                **common,
                "parcel_join_key": "ACCTID",
                "identity_contract": SALES_IDENTITY_CONTRACT,
                "methodology_url": SALES_METHODOLOGY_URL,
            },
        )
    raise ValueError(f"unknown Maryland MDP download source: {source_id}")


class MarylandMDPDownloadError(RuntimeError):
    """Structured source, selector, or local-artifact failure."""

    status = ResultStatus.SOURCE_CHANGED
    code = "maryland_mdp_download_source_changed"
    category = "source_schema"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status: ResultStatus | None = None,
        code: str | None = None,
        category: str | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code
        if category is not None:
            self.category = category

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class ManifestTransportError(MarylandMDPDownloadError):
    status = ResultStatus.UNAVAILABLE
    code = "maryland_mdp_download_manifest_unavailable"
    category = "transport"
    retryable = True


class CursorError(MarylandMDPDownloadError):
    code = "maryland_mdp_download_cursor_invalid"
    category = "cursor"


class SelectionError(MarylandMDPDownloadError):
    status = ResultStatus.UNAVAILABLE
    code = "maryland_mdp_download_release_selection"
    category = "query_selection"


def dropbox_link_metadata(url: str) -> dict[str, Any]:
    """Return stable provider-link fields from an official Dropbox URL."""

    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if host not in {"dropbox.com", "www.dropbox.com"}:
        raise ValueError("publisher link is not a Dropbox shared-file URL")
    parts = [part for part in parsed.path.split("/") if part]
    link_type: str
    token: str
    if len(parts) >= 4 and parts[:2] == ["scl", "fi"]:
        link_type = "scl_file"
        token = parts[2]
    elif len(parts) >= 3 and parts[0] == "s":
        link_type = "legacy_shared_file"
        token = parts[1]
    else:
        raise ValueError("publisher link is not a recognized Dropbox file share")
    filename = unquote(parts[-1])
    if not filename:
        raise ValueError("Dropbox shared-file URL lacks a filename")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    identity = {
        "provider": "dropbox",
        "link_type": link_type,
        "share_token": token,
        "rlkey": query.get("rlkey"),
        "filename": filename,
    }
    return {
        **identity,
        "provider_link_id": sha256_fingerprint(identity),
        "official_share_url": url,
        "official_query_parameters": query,
    }


def dropbox_download_url(share_url: str) -> str:
    """Resolve a publisher share URL using Dropbox's documented dl=1 form."""

    dropbox_link_metadata(share_url)
    parsed = urlsplit(share_url)
    query = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if key.casefold() not in {"dl", "raw"}
    ]
    query.append(("dl", "1"))
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query),
            parsed.fragment,
        )
    )


@dataclass(frozen=True)
class Release:
    """One publisher-visible file slot discovered from the official page."""

    source_id: str
    release_id: str
    label: str
    filename: str
    share_url: str | None
    publication_kind: str
    format: str
    schema_profile: str
    year: int
    quarter: int | None = None
    month: int | None = None
    component: str | None = None
    release_group_id: str | None = None
    schema_reference: bool = False

    @property
    def effective_at(self) -> str:
        if self.month is not None:
            return f"{self.year:04d}-{self.month:02d}-01"
        if self.quarter is not None:
            return f"{self.year:04d}-Q{self.quarter}"
        return f"{self.year:04d}"

    @property
    def provider_link(self) -> dict[str, Any] | None:
        if self.share_url is None:
            return None
        return dropbox_link_metadata(self.share_url)

    @property
    def download_url(self) -> str:
        if self.share_url is None:
            raise ValueError("local release context has no remote download URL")
        return dropbox_download_url(self.share_url)

    @property
    def identity_contract(self) -> dict[str, Any]:
        if self.schema_reference:
            return {
                "record_grain": "publisher_schema_artifact",
                "release_slot_key": [
                    "source_id",
                    "release_id",
                ],
                "provider_link_key": "provider_link_id",
                "published_link_occurrence_key": [
                    "source_id",
                    "release_id",
                    "provider_link_id",
                ],
                "artifact_occurrence_key": "artifact_sha256",
                "describes_source_id": self.source_id,
                "semantic_rows_exposed": False,
            }
        if self.source_id == PARCEL_SOURCE_ID:
            return {
                "record_grain": "parcel_account",
                "record_identity_source_id": (
                    SDAT_PROPERTY_IDENTITY_SOURCE_ID
                ),
                "semantic_record_key": "ACCTID",
                "release_slot_key": [
                    "source_id",
                    "release_id",
                ],
                "provider_link_key": "provider_link_id",
                "published_link_occurrence_key": [
                    "source_id",
                    "release_id",
                    "provider_link_id",
                ],
                "artifact_occurrence_key": "artifact_sha256",
            }
        if self.source_id == CAMA_SOURCE_ID:
            component = self.component or "statewide_bundle"
            return {
                "record_grain": "cama_component_occurrence",
                "parcel_join_key": "ACCTID",
                "component": component,
                "component_contract": CAMA_COMPONENT_CONTRACTS[component],
                "release_group_id": self.release_group_id,
                "release_slot_key": [
                    "source_id",
                    "release_id",
                ],
                "provider_link_key": "provider_link_id",
                "published_link_occurrence_key": [
                    "source_id",
                    "release_id",
                    "provider_link_id",
                ],
                "artifact_occurrence_key": "artifact_sha256",
            }
        return {
            "record_grain": "residential_sales_analytic_row",
            "parcel_join_key": "ACCTID",
            **SALES_IDENTITY_CONTRACT,
            "release_slot_key": [
                "source_id",
                "release_id",
            ],
            "provider_link_key": "provider_link_id",
            "published_link_occurrence_key": [
                "source_id",
                "release_id",
                "provider_link_id",
            ],
        }

    @property
    def capability(self) -> dict[str, Any]:
        return {
            "dynamic_publisher_manifest": True,
            "artifact_metadata_probe": True,
            "prepared_transfer": True,
            "resumable_download": True,
            "download_sha256_receipt": True,
            "expected_digest_validation": (
                "when_published_or_supplied_by_caller"
            ),
            "container_signature_validation": True,
            "local_zip_or_workbook_inventory": True,
            "local_row_search": False,
            "row_search_state": (
                "archive_member_tables_not_yet_schema_verified"
            ),
        }

    @property
    def schema_contract(self) -> dict[str, Any]:
        if self.schema_reference:
            return {
                "schema_profile": self.schema_profile,
                "artifact_role": "publisher_schema_workbook",
                "workbook_contents_parsed": False,
            }
        if self.source_id == PARCEL_SOURCE_ID:
            return {
                "schema_profile": self.schema_profile,
                "artifact_role": "statewide_parcel_geodatabase",
                "parcel_join_key": "ACCTID",
                "record_identity_source_id": (
                    SDAT_PROPERTY_IDENTITY_SOURCE_ID
                ),
            }
        if self.source_id == CAMA_SOURCE_ID:
            component = self.component or "statewide_bundle"
            return {
                "schema_profile": self.schema_profile,
                "artifact_role": "cama_release",
                "component": component,
                "component_contract": CAMA_COMPONENT_CONTRACTS[component],
            }
        return {
            "schema_profile": self.schema_profile,
            "artifact_role": "residential_sales_analytic_release",
            "parcel_join_key": "ACCTID",
            "transaction_identity": SALES_IDENTITY_CONTRACT,
        }

    def artifact(self) -> BulkArtifact:
        media_types = {
            "zip": "application/zip",
            "xlsx": (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        }
        return BulkArtifact(
            artifact_id=f"{self.release_id}-artifact",
            url=self.download_url,
            filename=self.filename,
            media_type=media_types[self.format],
            archive_format="zip",
            metadata={
                "source_id": self.source_id,
                "release_id": self.release_id,
                "official_share_url": self.share_url,
                "provider_link": self.provider_link,
                "download_url_resolution": {
                    "method": "dropbox_documented_dl_parameter",
                    "documentation_url": DROPBOX_DOWNLOAD_HELP_URL,
                },
                "schema_profile": self.schema_profile,
                "schema_reference": self.schema_reference,
                "identity_contract": self.identity_contract,
            },
        )

    def manifest_record(
        self,
        snapshot: "ManifestSnapshot",
    ) -> dict[str, Any]:
        if self.share_url is None:
            raise ValueError("remote manifest record needs a publisher link")
        provider_link = self.provider_link
        assert provider_link is not None
        release = BulkReleaseMetadata(
            release_id=self.release_id,
            kind="snapshot",
            effective_at=self.effective_at,
            coverage={
                "year": self.year,
                "quarter": self.quarter,
                "month": self.month,
                "component": self.component,
                "release_group_id": self.release_group_id,
                "publication_kind": self.publication_kind,
                "schema_reference": self.schema_reference,
                "monthly_rows_may_repeat": (
                    True
                    if self.source_id == SALES_SOURCE_ID
                    and not self.schema_reference
                    else None
                ),
            },
        )
        manifest = BulkDatasetManifest(
            source_id=self.source_id,
            dataset_id=(
                _source_metadata(self.source_id).dataset_id
                or self.source_id
            ),
            release=release,
            artifacts=(self.artifact(),),
            schema=self.schema_contract,
            metadata={
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                "authority": (
                    "Maryland Department of Planning and Maryland State "
                    "Department of Assessments and Taxation"
                ),
                "transport_provider": "Dropbox",
                "transport_is_authority": False,
                "official_listing_url": LANDING_URL,
                "official_link_label": self.label,
                "official_share_url": self.share_url,
                "provider_link": provider_link,
                "release_set_fingerprint": snapshot.fingerprint,
                "identity_contract": self.identity_contract,
                "capability": self.capability,
            },
        )
        return {
            "canonical_ref": canonical_property_ref(
                self.source_id,
                STATE_FIPS,
                "bulk_release_slot",
                self.release_id,
            ),
            "source_id": self.source_id,
            "record_kind": (
                "bulk_schema_manifest"
                if self.schema_reference
                else "bulk_release_manifest"
            ),
            "release_id": self.release_id,
            "release_group_id": self.release_group_id,
            "label": self.label,
            "filename": self.filename,
            "format": self.format,
            "publication_kind": self.publication_kind,
            "year": self.year,
            "quarter": self.quarter,
            "month": self.month,
            "component": self.component,
            "schema_reference": self.schema_reference,
            "official_share_url": self.share_url,
            "download_url": self.download_url,
            "provider_link": provider_link,
            "identity_contract": self.identity_contract,
            "capability": self.capability,
            "manifest": manifest.to_dict(),
            "source_url": LANDING_URL,
        }


@dataclass(frozen=True)
class ManifestSnapshot:
    """Complete recognized release set from one official-page observation."""

    releases: tuple[Release, ...]
    landing_sha256: str

    @property
    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "landing_url": LANDING_URL,
            "releases": [
                {
                    "source_id": release.source_id,
                    "release_id": release.release_id,
                    "filename": release.filename,
                    "provider_link_id": (
                        (release.provider_link or {}).get(
                            "provider_link_id"
                        )
                    ),
                    "schema_profile": release.schema_profile,
                    "component": release.component,
                }
                for release in self.releases
            ],
        }

    @property
    def fingerprint(self) -> str:
        return sha256_fingerprint(self.fingerprint_payload)

    def by_source(self, source_id: str) -> tuple[Release, ...]:
        return tuple(
            release
            for release in self.releases
            if release.source_id == source_id
        )

    def by_id(self, release_id: str) -> Release | None:
        return next(
            (
                release
                for release in self.releases
                if release.release_id == release_id
            ),
            None,
        )


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
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        self.links.append(
            (
                self._href,
                " ".join("".join(self._text).split()),
            )
        )
        self._href = None
        self._text = []


_PARCEL_RE = re.compile(
    r"(?P<month>[A-Za-z]+)_(?P<year>20\d{2})_Parcels\.zip$",
    re.I,
)
_PARCEL_SCHEMA_RE = re.compile(
    r"MdPropertyView_(?P<year>20\d{2})_Schema\.xlsx$",
    re.I,
)
_CAMA_QUARTER_RE = re.compile(
    r"(?P<year>20\d{2})-Q(?P<quarter>[1-4])-Statewide-CAMA"
    r"(?:\.gdb)?\.zip$",
    re.I,
)
_CAMA_COMPONENT_RE = re.compile(
    r"(?P<year>20\d{2})(?:-?Q(?P<quarter>[1-4]))?_CAMA_"
    r"(?P<component>Core|Bldg|Building|Land|Suba|Subarea|Subareas)"
    r"\.zip$",
    re.I,
)
_CAMA_ANNUAL_RE = re.compile(
    r"(?P<year>20\d{2})_CAMA\.zip$",
    re.I,
)
_SALES_RE = re.compile(
    r"Property_Sales_(?P<month>\d{2})(?P<year>\d{2})\.zip$",
    re.I,
)
_SALES_SCHEMA_RE = re.compile(
    r"PropertySales_(?P<year>20\d{2})_Schema\.xlsx$",
    re.I,
)


def _release_from_filename(
    filename: str,
    *,
    label: str,
    share_url: str | None,
) -> Release | None:
    """Classify one publisher filename without inspecting file contents."""

    match = _PARCEL_RE.fullmatch(filename)
    if match is not None:
        month_name = match.group("month").casefold()
        month = MONTHS.get(month_name)
        if month is None:
            return None
        year = int(match.group("year"))
        return Release(
            source_id=PARCEL_SOURCE_ID,
            release_id=f"parcels-{year:04d}-{month:02d}",
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="statewide_parcel_geodatabase",
            format="zip",
            schema_profile="mdproperty_view_geodatabase",
            year=year,
            month=month,
        )

    match = _PARCEL_SCHEMA_RE.fullmatch(filename)
    if match is not None:
        year = int(match.group("year"))
        return Release(
            source_id=PARCEL_SOURCE_ID,
            release_id=f"parcels-schema-{year:04d}",
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="parcel_schema_workbook",
            format="xlsx",
            schema_profile="mdproperty_view_schema_workbook",
            year=year,
            schema_reference=True,
        )

    match = _CAMA_QUARTER_RE.fullmatch(filename)
    if match is not None:
        year = int(match.group("year"))
        quarter = int(match.group("quarter"))
        group = f"cama-{year:04d}-q{quarter}"
        return Release(
            source_id=CAMA_SOURCE_ID,
            release_id=f"{group}-statewide",
            release_group_id=group,
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="quarterly_statewide_cama_bundle",
            format="zip",
            schema_profile="cama_statewide_bundle",
            year=year,
            quarter=quarter,
            component="statewide_bundle",
        )

    match = _CAMA_COMPONENT_RE.fullmatch(filename)
    if match is not None:
        year = int(match.group("year"))
        quarter_raw = match.group("quarter")
        quarter = int(quarter_raw) if quarter_raw else None
        component = CAMA_COMPONENT_ALIASES[
            match.group("component").casefold()
        ]
        period = (
            f"{year:04d}-q{quarter}"
            if quarter is not None
            else f"{year:04d}"
        )
        group = f"cama-{period}"
        return Release(
            source_id=CAMA_SOURCE_ID,
            release_id=f"{group}-{component}",
            release_group_id=group,
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="cama_component_release",
            format="zip",
            schema_profile=f"cama_{component}_component",
            year=year,
            quarter=quarter,
            component=component,
        )

    match = _CAMA_ANNUAL_RE.fullmatch(filename)
    if match is not None:
        year = int(match.group("year"))
        group = f"cama-{year:04d}"
        return Release(
            source_id=CAMA_SOURCE_ID,
            release_id=f"{group}-statewide",
            release_group_id=group,
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="annual_statewide_cama_bundle",
            format="zip",
            schema_profile="cama_statewide_bundle",
            year=year,
            component="statewide_bundle",
        )

    match = _SALES_RE.fullmatch(filename)
    if match is not None:
        month = int(match.group("month"))
        if month < 1 or month > 12:
            return None
        year = 2000 + int(match.group("year"))
        return Release(
            source_id=SALES_SOURCE_ID,
            release_id=f"sales-{year:04d}-{month:02d}",
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="monthly_residential_sales_analytic_release",
            format="zip",
            schema_profile="mdp_property_sales_monthly",
            year=year,
            month=month,
        )

    match = _SALES_SCHEMA_RE.fullmatch(filename)
    if match is not None:
        year = int(match.group("year"))
        return Release(
            source_id=SALES_SOURCE_ID,
            release_id=f"sales-schema-{year:04d}",
            label=label or filename,
            filename=filename,
            share_url=share_url,
            publication_kind="property_sales_schema_workbook",
            format="xlsx",
            schema_profile="mdp_property_sales_schema_workbook",
            year=year,
            schema_reference=True,
        )
    return None


def parse_release_manifest(
    html_text: str,
    *,
    base_url: str = LANDING_URL,
) -> ManifestSnapshot:
    """Parse the recognized parcel, CAMA, and sales files from the page."""

    parser = _AnchorParser()
    parser.feed(html_text)
    releases: dict[tuple[str, str], Release] = {}
    for href, label in parser.links:
        absolute_url = urljoin(base_url, href)
        filename = Path(
            unquote(urlsplit(absolute_url).path)
        ).name
        release = _release_from_filename(
            filename,
            label=label,
            share_url=absolute_url,
        )
        if release is None:
            continue
        try:
            dropbox_link_metadata(absolute_url)
        except ValueError as error:
            raise MarylandMDPDownloadError(
                "Recognized MDP property artifact uses an unrecognized "
                "publisher-link transport",
                details={
                    "release_id": release.release_id,
                    "url": absolute_url,
                },
            ) from error
        key = (release.source_id, release.release_id)
        previous = releases.get(key)
        if (
            previous is not None
            and (previous.provider_link or {}).get("provider_link_id")
            != (release.provider_link or {}).get("provider_link_id")
        ):
            raise MarylandMDPDownloadError(
                "Official page declares conflicting links for one release",
                details={
                    "source_id": release.source_id,
                    "release_id": release.release_id,
                    "first_url": previous.share_url,
                    "second_url": release.share_url,
                },
            )
        releases[key] = release

    data_sources = {
        release.source_id
        for release in releases.values()
        if not release.schema_reference
    }
    missing = sorted(set(SOURCE_IDS) - data_sources)
    if missing:
        raise MarylandMDPDownloadError(
            "Official page did not expose every recognized property-download "
            "family",
            details={
                "missing_source_ids": missing,
                "recognized_release_count": len(releases),
                "landing_url": base_url,
            },
        )

    source_order = {
        PARCEL_SOURCE_ID: 0,
        CAMA_SOURCE_ID: 1,
        SALES_SOURCE_ID: 2,
    }
    ordered = tuple(
        sorted(
            releases.values(),
            key=lambda release: (
                source_order[release.source_id],
                release.schema_reference,
                -release.year,
                -(release.quarter or 0),
                -(release.month or 0),
                release.release_id,
            ),
        )
    )
    return ManifestSnapshot(
        releases=ordered,
        landing_sha256=hashlib.sha256(
            html_text.encode("utf-8")
        ).hexdigest(),
    )


def _response_status(response: Any) -> int:
    return int(
        getattr(response, "status", getattr(response, "status_code", 200))
    )


def fetch_release_manifest(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    opener: Callable[..., Any] = urlopen,
) -> ManifestSnapshot:
    """Fetch the official Maryland MDP download listing."""

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
                        f"Official Maryland MDP listing returned HTTP {status}",
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
                    "Official Maryland MDP listing returned "
                    f"HTTP {error.code}",
                    details={
                        "url": LANDING_URL,
                        "http_status": error.code,
                    },
                ) from error
        except (URLError, TimeoutError, ConnectionError, OSError) as error:
            last_error = error
            if attempt >= retry_attempts:
                raise ManifestTransportError(
                    "Could not fetch the official Maryland MDP listing: "
                    f"{error}",
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
        raise CursorError(
            "Cursor does not belong to Maryland MDP property downloads"
        )
    encoded = cursor[len(CURSOR_PREFIX) :]
    try:
        padding = "=" * (-len(encoded) % 4)
        value = json.loads(
            base64.urlsafe_b64decode(encoded + padding).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CursorError("Cursor payload is invalid") from error
    if not isinstance(value, dict) or value.get("version") != CURSOR_VERSION:
        raise CursorError("Cursor version is not supported")
    return value


def _selected_releases(
    snapshot: ManifestSnapshot,
    *,
    source_id: str | None,
    release_id: str | None,
    year: int | None,
    component: str | None,
    include_schema: bool,
) -> tuple[Release, ...]:
    return tuple(
        release
        for release in snapshot.releases
        if source_id in {None, "all", release.source_id}
        and release_id in {None, release.release_id}
        and year in {None, release.year}
        and component in {None, release.component}
        and (include_schema or not release.schema_reference)
    )


def _manifest_page(
    snapshot: ManifestSnapshot,
    releases: Sequence[Release],
    *,
    limit: int | None,
    cursor: str | None,
) -> tuple[tuple[Release, ...], str | None]:
    if (
        limit is not None
        and (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        )
    ):
        raise SelectionError("Manifest limit must be a positive integer")
    selection_fingerprint = sha256_fingerprint(
        [
            {
                "source_id": release.source_id,
                "release_id": release.release_id,
            }
            for release in releases
        ]
    )
    offset = 0
    if cursor is not None:
        payload = _decode_cursor(cursor)
        if payload.get("kind") != "manifest":
            raise CursorError("Cursor is not a manifest cursor")
        if payload.get("release_set_fingerprint") != snapshot.fingerprint:
            raise CursorError(
                "Official Maryland MDP release listing changed after this "
                "cursor"
            )
        if payload.get("selection_fingerprint") != selection_fingerprint:
            raise CursorError(
                "Manifest cursor no longer matches the selected releases"
            )
        offset = payload.get("offset")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise CursorError("Manifest cursor offset is invalid")
        if offset > len(releases):
            raise CursorError("Manifest cursor offset exceeds the selection")
    end = len(releases) if limit is None else min(
        len(releases),
        offset + limit,
    )
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
    return tuple(releases[offset:end]), next_cursor


def _one_release(
    snapshot: ManifestSnapshot,
    *,
    source_id: str,
    release_id: str | None,
    year: int | None,
    component: str | None,
) -> Release:
    selected = _selected_releases(
        snapshot,
        source_id=source_id,
        release_id=release_id,
        year=year,
        component=component,
        include_schema=True,
    )
    if release_id is None and year is None and component is None and selected:
        return selected[0]
    if len(selected) != 1:
        raise SelectionError(
            "Operation selectors must resolve to one publisher release",
            details={
                "source_id": source_id,
                "release_id": release_id,
                "year": year,
                "component": component,
                "matched_release_ids": [
                    release.release_id for release in selected
                ],
            },
        )
    return selected[0]


def _component_from_member(path: str) -> str | None:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        path.casefold(),
    )
    patterns = (
        ("subareas", ("subarea", "subareas", "suba")),
        ("building", ("building", "bldg", "bld")),
        ("core", ("core",)),
        ("land", ("land",)),
    )
    for component, aliases in patterns:
        if any(
            re.search(rf"(?:^|_){re.escape(alias)}(?:_|$)", normalized)
            for alias in aliases
        ):
            return component
    return None


def _member_role(
    release: Release,
    member_path: str,
) -> dict[str, Any]:
    member = PurePosixPath(member_path)
    suffix = member.suffix.casefold()
    in_geodatabase = any(
        part.casefold().endswith(".gdb")
        for part in member.parts
    )
    support_name = member.name.casefold().startswith(
        ("readme", "license", "metadata")
    )
    if release.schema_reference:
        return {
            "role": "schema_workbook_part",
            "component": None,
            "semantic_rows_exposed": False,
        }
    if release.source_id == PARCEL_SOURCE_ID:
        data_candidate = in_geodatabase
        return {
            "role": (
                "parcel_file_geodatabase_member"
                if data_candidate
                else "parcel_archive_support_member"
            ),
            "component": "parcel" if data_candidate else None,
            "semantic_record_key": (
                "ACCTID" if data_candidate else None
            ),
            "data_candidate": data_candidate,
            "row_schema_verified": False,
        }
    if release.source_id == CAMA_SOURCE_ID:
        detected_component = (
            release.component
            if release.component != "statewide_bundle"
            else _component_from_member(member_path)
        )
        data_candidate = (
            not support_name
            and (
                in_geodatabase
                or suffix
                in {
                    ".csv",
                    ".dbf",
                    ".shp",
                    ".shx",
                    ".txt",
                }
            )
        )
        component = detected_component if data_candidate else None
        return {
            "role": (
                "cama_component_data_candidate"
                if component
                else (
                    "cama_statewide_data_candidate"
                    if data_candidate
                    else "cama_component_support_member"
                )
            ),
            "component": component,
            "declared_release_component": release.component,
            "component_contract": (
                CAMA_COMPONENT_CONTRACTS.get(component)
                if component
                else None
            ),
            "data_candidate": data_candidate,
            "geodatabase_member": in_geodatabase,
            "row_schema_verified": False,
        }
    row_candidate = (
        not support_name and suffix in {".csv", ".dbf", ".txt"}
    )
    data_candidate = row_candidate or in_geodatabase
    return {
        "role": (
            "property_sales_rows_candidate"
            if row_candidate
            else (
                "property_sales_geodatabase_member"
                if in_geodatabase
                else "property_sales_archive_support_member"
            )
        ),
        "component": "property_sales" if data_candidate else None,
        "data_candidate": data_candidate,
        "row_schema_verified": False,
        "transaction_identity": (
            SALES_IDENTITY_CONTRACT if data_candidate else None
        ),
    }


def inspect_local_artifact(
    path: Path | str,
    *,
    source_id: str | None = None,
    release_id: str | None = None,
    release_context: Release | None = None,
) -> dict[str, Any]:
    """Inventory a recognized local ZIP/XLSX and classify member roles."""

    artifact_path = Path(path).expanduser().resolve()
    if not artifact_path.is_file():
        raise SelectionError(
            "Local Maryland MDP artifact does not exist",
            details={"path": str(artifact_path)},
        )
    release = release_context or _release_from_filename(
        artifact_path.name,
        label=artifact_path.name,
        share_url=None,
    )
    if release is None:
        raise SelectionError(
            "Local artifact filename does not match a recognized MDP "
            "property release",
            details={"filename": artifact_path.name},
        )
    if source_id not in {None, release.source_id}:
        raise SelectionError(
            "Local artifact filename and source selector disagree",
            details={
                "filename": artifact_path.name,
                "source_id": source_id,
                "resolved_source_id": release.source_id,
            },
        )
    if release_id not in {None, release.release_id}:
        raise SelectionError(
            "Local artifact filename and release selector disagree",
            details={
                "filename": artifact_path.name,
                "release_id": release_id,
                "resolved_release_id": release.release_id,
            },
        )

    base = inspect_zip(artifact_path).to_dict()
    _validate_inspected_container(release, base)
    artifact_sha256 = str(base["archive_sha256"])
    classified_members: list[dict[str, Any]] = []
    role_counts: dict[str, int] = {}
    component_counts: dict[str, int] = {}
    for raw_member in base["members"]:
        member = dict(raw_member)
        role = _member_role(release, str(member["path"]))
        role_name = str(role["role"])
        role_counts[role_name] = role_counts.get(role_name, 0) + 1
        component = role.get("component")
        if component:
            component_counts[str(component)] = (
                component_counts.get(str(component), 0) + 1
            )
        member["classification"] = role
        member["member_occurrence_id"] = sha256_fingerprint(
            {
                "artifact_sha256": artifact_sha256,
                "path": member["path"],
                "crc32": member["crc32"],
                "size": member["size"],
            }
        )
        classified_members.append(member)

    schema = {
        **dict(base["schema"]),
        "inspection_schema_version": INSPECTION_SCHEMA_VERSION,
        "source_id": release.source_id,
        "release_id": release.release_id,
        "schema_profile": release.schema_profile,
        "role_counts": role_counts,
        "component_counts": component_counts,
    }
    return {
        **base,
        "schema": schema,
        "schema_fingerprint": sha256_fingerprint(schema),
        "members": classified_members,
        "source_id": release.source_id,
        "release_id": release.release_id,
        "release_group_id": release.release_group_id,
        "filename": artifact_path.name,
        "publisher_filename": release.filename,
        "format": release.format,
        "schema_profile": release.schema_profile,
        "schema_reference": release.schema_reference,
        "identity_contract": release.identity_contract,
        "artifact_occurrence_identity": {
            "artifact_sha256": artifact_sha256,
            "artifact_size": base["archive_size"],
            "interchangeable_with_release_slot": False,
        },
        "role_counts": role_counts,
        "component_counts": component_counts,
        "row_search_performed": False,
    }


def _validator_occurrence(
    release: Release,
    probe: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "source_id": release.source_id,
        "release_id": release.release_id,
        "provider_link_id": (
            (release.provider_link or {}).get("provider_link_id")
        ),
        "etag": probe.get("etag"),
        "last_modified": probe.get("last_modified"),
        "content_length": probe.get("content_length"),
        "sample_sha256": probe.get("sample_sha256"),
    }
    return {
        **fields,
        "validator_occurrence_id": sha256_fingerprint(fields),
        "provider_revision_field_published": bool(
            probe.get("etag") or probe.get("last_modified")
        ),
        "meaning": "observed_transport_validators_not_release_slot_identity",
    }


def _validate_probe_format(
    release: Release,
    probe: Mapping[str, Any],
) -> None:
    sample_size = probe.get("sample_size")
    if (
        isinstance(sample_size, int)
        and sample_size >= 4
        and not _probe_has_zip_signature(probe)
    ):
        raise MarylandMDPDownloadError(
            "Publisher-linked artifact did not return its declared ZIP "
            "container",
            details={
                "source_id": release.source_id,
                "release_id": release.release_id,
                "filename": release.filename,
                "media_type": probe.get("media_type"),
                "signature_hex": probe.get("signature_hex"),
                "official_share_url": release.share_url,
            },
        )


def _probe_has_zip_signature(probe: Mapping[str, Any]) -> bool:
    signature_hex = probe.get("signature_hex")
    if not isinstance(signature_hex, str) or len(signature_hex) < 8:
        return False
    try:
        signature = bytes.fromhex(signature_hex[:8])
    except ValueError:
        return False
    return signature in ZIP_CONTAINER_SIGNATURES


def _validate_inspected_container(
    release: Release,
    inspection: Mapping[str, Any],
) -> None:
    if release.format != "xlsx":
        return
    member_paths = {
        str(member.get("path", "")).casefold()
        for member in inspection.get("members", ())
        if isinstance(member, Mapping)
    }
    required_paths = {
        "[content_types].xml",
        "xl/workbook.xml",
    }
    missing = sorted(required_paths - member_paths)
    if missing:
        raise MarylandMDPDownloadError(
            "Publisher schema artifact is a ZIP container but not a "
            "recognized XLSX workbook",
            details={
                "source_id": release.source_id,
                "release_id": release.release_id,
                "filename": release.filename,
                "missing_workbook_members": missing,
            },
        )


def _validate_local_container_signature(
    path: Path | str,
    *,
    release: Release,
) -> None:
    artifact_path = Path(path)
    with artifact_path.open("rb") as source:
        signature = source.read(4)
    if signature not in ZIP_CONTAINER_SIGNATURES:
        raise MarylandMDPDownloadError(
            "Downloaded publisher artifact is not its declared ZIP "
            "container",
            details={
                "source_id": release.source_id,
                "release_id": release.release_id,
                "filename": release.filename,
                "path": str(artifact_path),
                "signature_hex": signature.hex(),
            },
        )
    if release.format == "xlsx":
        _validate_inspected_container(
            release,
            inspect_zip(artifact_path).to_dict(),
        )


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    return BulkTransferClient(
        timeout=args.timeout,
        max_attempts=args.retry_attempts,
        chunk_size=args.chunk_size,
    )


def source_records() -> list[dict[str, Any]]:
    """Describe the three standalone source contracts."""

    return [
        {
            "source_id": source_id,
            "record_kind": "source_contract",
            "source": _source_metadata(source_id).to_dict(),
            "identity_contract": (
                {
                    "record_identity_source_id": (
                        SDAT_PROPERTY_IDENTITY_SOURCE_ID
                    ),
                    "parcel_join_key": "ACCTID",
                    "representation": "bulk_gis_files",
                }
                if source_id == PARCEL_SOURCE_ID
                else (
                    {
                        "parcel_join_key": "ACCTID",
                        "building_subarea_join_key": "CAMALINK",
                        "components": CAMA_COMPONENT_CONTRACTS,
                    }
                    if source_id == CAMA_SOURCE_ID
                    else SALES_IDENTITY_CONTRACT
                )
            ),
            "capabilities": {
                "manifest": True,
                "probe": True,
                "prepare": True,
                "download": True,
                "inspect": True,
                "row_search": False,
            },
            "official_listing_url": LANDING_URL,
            "transport_documentation_url": DROPBOX_DOWNLOAD_HELP_URL,
            "warnings": list(SOURCE_WARNINGS[source_id]),
        }
        for source_id in SOURCE_IDS
    ]


def _build_query(args: argparse.Namespace) -> PublicRecordsQuery:
    source_value = getattr(args, "source", PARCEL_SOURCE_ID)
    source_id = (
        source_value
        if source_value in SOURCE_IDS
        else PARCEL_SOURCE_ID
    )
    parameters: dict[str, Any] = {}
    for name in (
        "source",
        "release",
        "year",
        "component",
        "artifact",
        "destination",
        "sample_bytes",
        "include_schema",
        "resume",
        "expected_sha256",
        "max_download_bytes",
        "inspect",
    ):
        value = getattr(args, name, None)
        if value is not None:
            parameters[name] = (
                str(value)
                if isinstance(value, Path)
                else value
            )
    return PublicRecordsQuery(
        source=_source_metadata(source_id),
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=getattr(args, "limit", None),
            cursor=getattr(args, "cursor", None),
            metadata={
                "output_schema_version": OUTPUT_SCHEMA_VERSION,
            },
        ),
    )


def _prepared_transfer_record(
    release: Release,
    snapshot: ManifestSnapshot,
) -> dict[str, Any]:
    return {
        **release.manifest_record(snapshot),
        "record_kind": "prepared_bulk_transfer",
        "prepared_transfer": {
            "authority": (
                "Maryland Department of Planning and Maryland State "
                "Department of Assessments and Taxation"
            ),
            "transport_provider": "Dropbox",
            "official_share_url": release.share_url,
            "download_url": release.download_url,
            "expected_filename": release.filename,
            "redirects_expected": True,
            "resolution_method": "dropbox_documented_dl_parameter",
            "resolution_documentation_url": DROPBOX_DOWNLOAD_HELP_URL,
            "resumable_client": "BulkTransferClient",
            "provider_revision": (
                "observe_etag_or_last_modified_during_probe_or_download"
            ),
            "integrity_validation": {
                "sha256_receipt": True,
                "expected_digest": (
                    "verified_when_published_or_supplied_by_caller"
                ),
                "container_signature": True,
                "xlsx_workbook_structure": (
                    "verified_for_schema_workbooks_after_download"
                ),
            },
        },
    }


def _download_record(
    release: Release,
    snapshot: ManifestSnapshot,
    download: DownloadResult,
) -> dict[str, Any]:
    return {
        **release.manifest_record(snapshot),
        "record_kind": "bulk_artifact_download",
        "download": download.to_dict(),
        "artifact_occurrence_identity": {
            "artifact_sha256": download.sha256,
            "etag": download.etag,
            "last_modified": download.last_modified,
            "size": download.size,
            "interchangeable_with_release_slot": False,
        },
        "integrity_validation": {
            "sha256_computed": True,
            "expected_sha256": download.expected_sha256,
            "expected_sha256_verified": (
                download.expected_sha256 is not None
            ),
            "container_signature_verified": True,
            "xlsx_workbook_structure_verified": (
                release.format == "xlsx"
            ),
        },
    }


def execute(
    args: argparse.Namespace,
    *,
    manifest_snapshot: ManifestSnapshot | None = None,
    transfer_client: BulkTransferClient | None = None,
    access_decision: Mapping[str, Any] | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    del access_decision
    query = _build_query(args)
    requested_source = str(
        getattr(args, "source", PARCEL_SOURCE_ID)
    )
    source_id = (
        requested_source
        if requested_source in SOURCE_IDS
        else query.source.source_id
    )
    warnings = SOURCE_WARNINGS.get(source_id, ())
    try:
        if args.command == "sources":
            result = PublicRecordsResult.success(
                query,
                source_records(),
            )
        elif args.command == "inspect":
            inspection = inspect_local_artifact(
                args.artifact,
                source_id=source_id,
                release_id=args.release,
            )
            result = PublicRecordsResult.success(
                query,
                [
                    {
                        "canonical_ref": canonical_property_ref(
                            source_id,
                            STATE_FIPS,
                            "artifact_inspection",
                            str(
                                inspection[
                                    "artifact_occurrence_identity"
                                ]["artifact_sha256"]
                            ),
                        ),
                        "source_id": source_id,
                        "record_kind": "local_artifact_inspection",
                        "inspection": inspection,
                        "source_url": LANDING_URL,
                    }
                ],
                raw_artifact_refs=[str(args.artifact)],
                warnings=warnings,
            )
        else:
            snapshot = manifest_snapshot or fetch_release_manifest(
                timeout=args.timeout,
                retry_attempts=args.retry_attempts,
            )
            if args.command == "manifest":
                selected = _selected_releases(
                    snapshot,
                    source_id=(
                        None if args.source == "all" else args.source
                    ),
                    release_id=args.release,
                    year=args.year,
                    component=args.component,
                    include_schema=args.include_schema,
                )
                page, next_cursor = _manifest_page(
                    snapshot,
                    selected,
                    limit=args.limit,
                    cursor=args.cursor,
                )
                result = PublicRecordsResult.success(
                    query,
                    [
                        release.manifest_record(snapshot)
                        for release in page
                    ],
                    next_cursor=next_cursor,
                )
            else:
                release = _one_release(
                    snapshot,
                    source_id=source_id,
                    release_id=args.release,
                    year=args.year,
                    component=args.component,
                )
                if args.command == "prepare":
                    result = PublicRecordsResult.success(
                        query,
                        [
                            _prepared_transfer_record(
                                release,
                                snapshot,
                            )
                        ],
                        warnings=warnings,
                    )
                else:
                    transfer = transfer_client or _bulk_client(args)
                    if args.command == "probe":
                        probe = transfer.probe(
                            release.artifact(),
                            sample_bytes=args.sample_bytes,
                        )
                        probe_dict = probe.to_dict()
                        _validate_probe_format(release, probe_dict)
                        result = PublicRecordsResult.success(
                            query,
                            [
                                {
                                    **release.manifest_record(snapshot),
                                    "record_kind": "source_probe",
                                    "probe_schema_version": (
                                        PROBE_SCHEMA_VERSION
                                    ),
                                    "artifact_probe": probe_dict,
                                    "validator_occurrence_identity": (
                                        _validator_occurrence(
                                            release,
                                            probe_dict,
                                        )
                                    ),
                                    "format_expectation": {
                                        "declared": release.format,
                                        "zip_container_signature_observed": (
                                            _probe_has_zip_signature(
                                                probe_dict
                                            )
                                        ),
                                        "xlsx_is_zip_container": (
                                            release.format == "xlsx"
                                        ),
                                    },
                                }
                            ],
                            warnings=warnings,
                        )
                    elif args.command == "download":
                        artifact = release.artifact()
                        if args.expected_sha256:
                            artifact = BulkArtifact(
                                **{
                                    **artifact.to_dict(),
                                    "expected_sha256": (
                                        args.expected_sha256
                                    ),
                                }
                            )
                        download = transfer.download(
                            artifact,
                            args.destination,
                            resume=args.resume,
                            max_bytes=args.max_download_bytes,
                        )
                        _validate_local_container_signature(
                            download.path,
                            release=release,
                        )
                        record = _download_record(
                            release,
                            snapshot,
                            download,
                        )
                        if args.inspect:
                            record["inspection"] = (
                                inspect_local_artifact(
                                    download.path,
                                    source_id=source_id,
                                    release_id=release.release_id,
                                    release_context=release,
                                )
                            )
                        result = PublicRecordsResult.success(
                            query,
                            [record],
                            raw_artifact_refs=[download.path],
                            warnings=warnings,
                        )
                    else:
                        raise ValueError(
                            "unsupported Maryland MDP download command "
                            f"{args.command}"
                        )
    except MarylandMDPDownloadError as error:
        result = PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=warnings,
        )
    except BulkSourceError as error:
        result = PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
            warnings=warnings,
        )
    except (OSError, ValueError) as error:
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.SOURCE_CHANGED,
            [
                PublicRecordsError(
                    code="maryland_mdp_download_operation_failed",
                    message=str(error),
                    category="source_or_query",
                    retryable=False,
                )
            ],
            warnings=warnings,
        )

    if log_results:
        result_count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        log_search(
            canonical_json(result.query.to_dict()),
            source_id,
            result_count,
        )
    return result


def _add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.0,
        help="Accepted by shared routing; no additional adapter delay",
    )


def _add_selection_args(
    parser: argparse.ArgumentParser,
    *,
    source_default: str | None = None,
    allow_all: bool = False,
) -> None:
    parser.add_argument(
        "--source",
        choices=(*SOURCE_IDS, "all") if allow_all else SOURCE_IDS,
        default=source_default,
        required=source_default is None,
    )
    parser.add_argument("--release")
    parser.add_argument("--year", type=int)
    parser.add_argument(
        "--component",
        choices=(
            "core",
            "building",
            "land",
            "subareas",
            "statewide_bundle",
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and inspect Maryland MDP statewide property downloads"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser(
        "sources",
        help="Describe the three source and identity contracts",
    )
    sources.set_defaults(source=PARCEL_SOURCE_ID)
    add_output_args(sources)

    manifest = sub.add_parser(
        "manifest",
        help="Discover the official parcel, CAMA, and sales artifacts",
    )
    _add_selection_args(
        manifest,
        source_default="all",
        allow_all=True,
    )
    manifest.add_argument(
        "--include-schema",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    manifest.add_argument("--limit", type=int)
    manifest.add_argument("--cursor")
    _add_runtime_args(manifest)
    add_output_args(manifest)

    prepare = sub.add_parser(
        "prepare",
        help="Resolve one publisher link to a transfer description",
    )
    _add_selection_args(prepare)
    _add_runtime_args(prepare)
    add_output_args(prepare)

    probe = sub.add_parser(
        "probe",
        help="Probe one selected artifact and observe transport validators",
    )
    _add_selection_args(probe)
    probe.add_argument(
        "--sample-bytes",
        type=int,
        default=DEFAULT_SAMPLE_BYTES,
    )
    _add_runtime_args(probe)
    add_output_args(probe)

    download = sub.add_parser(
        "download",
        help="Resume and validate one selected publisher artifact",
    )
    _add_selection_args(download)
    download.add_argument("--destination", required=True)
    download.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument("--inspect", action="store_true")
    _add_runtime_args(download)
    add_output_args(download)

    inspect_parser = sub.add_parser(
        "inspect",
        help="Inventory a downloaded ZIP or schema workbook",
    )
    inspect_parser.add_argument("artifact")
    inspect_parser.add_argument(
        "--source",
        choices=SOURCE_IDS,
        required=True,
    )
    inspect_parser.add_argument("--release")
    add_output_args(inspect_parser)
    return parser


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
) -> None:
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=(
            f"Maryland MDP downloads {args.command} "
            f"({result.status.value})"
        ),
        result_count=(
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        ),
    ):
        return
    if args.json_out:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"Maryland MDP downloads {args.command}: "
        f"{result.status.value} ({len(result.records)} records)"
    )
    for record in result.records:
        label = (
            record.get("release_id")
            or record.get("source_id")
            or record.get("record_kind")
        )
        print(f"  {label}")
    for error in result.errors:
        print(
            f"  ERROR {error.code}: {error.message}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    limit = getattr(args, "limit", None)
    if limit is not None and limit <= 0:
        parser.error("--limit must be positive")
    if getattr(args, "sample_bytes", 0) < 0:
        parser.error("--sample-bytes must not be negative")
    if getattr(args, "retry_attempts", 1) <= 0:
        parser.error("--retry-attempts must be positive")
    if getattr(args, "chunk_size", 1) <= 0:
        parser.error("--chunk-size must be positive")
    if getattr(args, "max_download_bytes", None) is not None and (
        args.max_download_bytes <= 0
    ):
        parser.error("--max-download-bytes must be positive")
    result = execute(args)
    _emit(result, args)
    return (
        0
        if result.status
        in {
            ResultStatus.OK,
            ResultStatus.NO_RESULTS,
            ResultStatus.PARTIAL,
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
