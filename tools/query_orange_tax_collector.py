#!/usr/bin/env python3
"""Query Orange County, Florida Tax Collector property-tax records.

This adapter represents two distinct publication paths without conflating
their freshness:

* the current GovHub search index and TaxSys account/bill pages; and
* two historical bulk ZIPs that the Tax Collector page still labels
  ``as of 02/17/20``.

The page calls the ZIP links "Daily" and the old layout documents describe a
weekly update process, but the linked artifacts observed in 2026 are unchanged
2020 publications.  Their observed digests and row counts are recorded as
observations, not as a live refresh cadence.

Identity is similarly explicit.  Only an exact normalized 15-digit Orange
County parcel account is used as a parcel join.  Algolia object IDs, TaxSys
account tokens, bill UUIDs, certificate numbers, receipt/validation numbers,
TaxSummaryID values, downloaded artifact digests, archive members, and source
row occurrences retain separate source roles.

Examples:
    uv run python tools/query_orange_tax_collector.py sources --json
    uv run python tools/query_orange_tax_collector.py search \
        01-20-27-0000-00001 --limit 15 --json
    uv run python tools/query_orange_tax_collector.py account \
        01-20-27-0000-00001 --json
    uv run python tools/query_orange_tax_collector.py history \
        01-20-27-0000-00001 --json
    uv run python tools/query_orange_tax_collector.py bill \
        01-20-27-0000-00001 ca0e3d54-aad7-11f0-bb75-005056815849 \
        --json
    uv run python tools/query_orange_tax_collector.py bulk-manifest --json
    uv run python tools/query_orange_tax_collector.py bulk-probe \
        current --artifact-role data --json
    uv run python tools/query_orange_tax_collector.py bulk-download \
        current /tmp/TaxPaymentTape.zip --inspect --json
    uv run python tools/query_orange_tax_collector.py bulk-inspect \
        current /tmp/TaxPaymentTape.zip --json
    uv run python tools/query_orange_tax_collector.py bulk-search \
        current /tmp/TaxPaymentTape.zip \
        --account 01-20-27-0000-00001 --limit 10 --json
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup
from requests import RequestException

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkDatasetManifest,
        BulkReleaseMetadata,
        BulkSourceError,
        BulkTransferClient,
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
    from tools.public_records_http import RetryPolicy, system_trust_session
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
    from public_records_http import RetryPolicy, system_trust_session
    from public_records_store import canonical_property_ref


SOURCE_ID = "us-fl-orange-tax-collector-property-tax"
COUNTY_GEOID = "12095"
STATE_CODE = "FL"
STATE_FIPS = "12"
COUNTY_NAME = "Orange County"

OFFICIAL_TAX_ROLL_PAGE = (
    "https://www.octaxcol.com/taxes/about-property-tax/tax-roll-download/"
)
GOVHUB_PORTAL_URL = "https://county-taxes.net/fl-orange/property-tax"
TAXSYS_ROOT = "https://orange.county-taxes.com/govhub"
EMBEDDED_TAXSYS_ROOT = (
    "https://county-taxes.net/iframe-taxsys/"
    "orange.county-taxes.com/govhub"
)
ALGOLIA_APPLICATION_ID = "0LWZO52LS2"
ALGOLIA_PUBLIC_SEARCH_KEY = "c0745578b56854a1b90ed57b63fbf0ba"
ALGOLIA_INDEX = "fl-orange.property_tax"
ALGOLIA_URL = "https://0lwzo52ls2-dsn.algolia.net/1/indexes/*/queries"
ALGOLIA_HITS_PER_PAGE = 15

CURRENT_LAYOUT_URL = (
    "https://www.octaxcol.com/assets/uploads/2020/02/LayoutRENew.doc"
)
CURRENT_ROLL_URL = (
    "https://www.octaxcol.com/assets/uploads/2020/02/"
    "TaxPaymentTape.zip"
)
DELINQUENT_LAYOUT_URL = (
    "https://www.octaxcol.com/assets/uploads/2020/02/LayoutDQNew.doc"
)
DELINQUENT_ROLL_URL = (
    "https://www.octaxcol.com/assets/uploads/2020/02/"
    "DelinquentRealEstateTaxData.zip"
)

PUBLICATION_DATE = "2020-02-17"
OUTPUT_SCHEMA_VERSION = "orange-tax-collector-property-tax/1.0"
PORTAL_CURSOR_PREFIX = "orange-tax-portal:v1:"
BULK_CURSOR_PREFIX = "orange-tax-bulk:v1:"
CURSOR_VERSION = 1
USER_AGENT = "Ithildin-Public-Records/1.0"
DEFAULT_TIMEOUT = 45.0
DEFAULT_RETRY_ATTEMPTS = 3
MAX_CSV_FIELD_BYTES = 16 * 1024 * 1024

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)
BILL_URL_RE = re.compile(
    r"/property-tax/(?P<token>[A-Za-z0-9_-]+)/bills/"
    r"(?P<bill>[0-9a-f-]{36})(?:[#/?]|$)",
    re.I,
)
ALGOLIA_OBJECT_PREFIX = "/Taxsys-GovHub/v0/items/"
ACCOUNT_SEMANTIC_PREFIX = "orange:real_estate:parents:"

CURRENT_HEADERS = (
    "ParcelNumber",
    "Folio",
    "TaxYear",
    "MillCode",
    "CityCode",
    "MortgageCode",
    "MortgageLoanNumber",
    "ExemptCode",
    "StatusCode",
    "TotalValue",
    "ExemptValue",
    "TaxableValue",
    "OwnerName",
    "Address1",
    "Address2",
    "Address3",
    "Address4",
    "Address5",
    "Legal1",
    "Legal2",
    "Legal3",
    "Legal4",
    "Legal5",
    "IsInstallment",
    "IsDelinquent",
    "GrossTaxDue",
    "BalanceDue",
    "NovemberAmountDue",
    "DatePaid",
    "ValidationNumber",
    "AmountPaid",
    "PaidBy",
    "Filler",
    "IsBankrupt",
    "IsLitigationPending",
    "IsFloridaTaking",
    "IsLeasehold",
    "TaxSummaryId",
)

DELINQUENT_HEADERS = (
    "Cert Year",
    "Cert No",
    "Cert Seq",
    "Parcel No",
    "Tax Deed Year",
    "Tax Deed No",
    "Tax Deed Seq",
    "Tax Deed Status",
    "Tax Year",
    "Status Code",
    "Mill Code",
    "City Code",
    "Installment Code",
    "Gross Taxes",
    "Certificate Face Value",
    "Total Value",
    "Exempt Value",
    "Taxable Value",
    "Owner1",
    "Owner2",
    "Owner3",
    "Owner4",
    "Owner5",
    "MailingAddress1",
    "MailingAddress2",
    "MailingAddress3",
    "MailingAddress4",
    "MailingAddress5",
    "Legal Description",
    "Payoff Date",
    "Payoff Amount Due",
    "Payoff Interest",
    "Payoff Amount Due Next Month",
    "Payoff Interest Next Month",
    "Payoff Interest Percentage",
    "Payment Date",
    "Payment Code",
    "Validation No",
    "Bidder Number",
    "Buyer Name1",
    "Buyer Name2",
    "Cert Issue Date",
    "Cert Purchase Date",
    "Tax Deed Application Date",
    "Tax Deed Redemption Date",
    "Property Use Code",
    "Situs Street Number",
    "Situs Street Direction",
    "Situs Street Name",
    "Situs Street Type",
    "Situs Suite",
    "Situs City",
    "Situs ZipCode",
    "TaxSummaryID",
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Orange County Tax Collector Property Tax",
    source_role=(
        "county_property_tax_account_bill_payment_certificate_and_"
        "historical_bulk_roll"
    ),
    base_url=OFFICIAL_TAX_ROLL_PAGE,
    dataset_id=(
        "GovHub/TaxSys fl-orange.property_tax plus 2020 tax-roll ZIPs"
    ),
    metadata={
        "authority": "Orange County Tax Collector",
        "county_geoid": COUNTY_GEOID,
        "current_portal": GOVHUB_PORTAL_URL,
        "portal_index": ALGOLIA_INDEX,
        "historical_bulk_page": OFFICIAL_TAX_ROLL_PAGE,
        "parcel_join": "exact normalized 15-digit Orange County account",
        "historical_publication_date": PUBLICATION_DATE,
    },
)
JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=COUNTY_GEOID,
    name=f"{COUNTY_NAME}, Florida",
    state_code=STATE_CODE,
    county_fips=COUNTY_GEOID,
    locality=COUNTY_NAME,
    metadata={"state_fips": STATE_FIPS, "county_fips_3": "095"},
)
SOURCE_WARNINGS = (
    "Tax Collector owner, buyer, payer, and status labels are source "
    "observations, not recorded-title or beneficial-ownership conclusions.",
    "Only an exact normalized 15-digit Orange County account is a parcel "
    "join. Object IDs, account tokens, alternate keys, bill UUIDs, "
    "certificates, receipts, validation numbers, TaxSummaryID values, and "
    "row occurrences retain separate identities.",
    "The official page still links two artifacts labeled as of 02/17/20. "
    "They are represented as fixed historical snapshots, not a daily or "
    "current feed.",
    "Portal balances, bill status, certificate status, and retrieved page "
    "content are observations at retrieval time.",
)


class OrangeTaxError(RuntimeError):
    """Structured Orange source, selector, or schema failure."""

    status = ResultStatus.UNAVAILABLE
    code = "orange_tax_error"
    category = "source"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        status: ResultStatus | None = None,
        code: str | None = None,
        category: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.details = dict(details or {})
        if status is not None:
            self.status = status
        if code is not None:
            self.code = code
        if category is not None:
            self.category = category
        if retryable is not None:
            self.retryable = retryable

    def to_contract_error(self) -> PublicRecordsError:
        return PublicRecordsError(
            code=self.code,
            message=str(self),
            category=self.category,
            retryable=self.retryable,
            details=self.details,
        )


class OrangeTaxQueryError(OrangeTaxError):
    code = "orange_tax_query_invalid"
    category = "query_selection"


class OrangeTaxSourceChanged(OrangeTaxError):
    status = ResultStatus.SOURCE_CHANGED
    code = "orange_tax_source_changed"
    category = "source_schema"


class OrangeTaxTransportError(OrangeTaxError):
    status = ResultStatus.UNAVAILABLE
    code = "orange_tax_transport_error"
    category = "transport"
    retryable = True


class OrangeTaxRestricted(OrangeTaxError):
    status = ResultStatus.RESTRICTED
    code = "orange_tax_access_restricted"
    category = "access"


class OrangeTaxRateLimited(OrangeTaxError):
    status = ResultStatus.RATE_LIMITED
    code = "orange_tax_rate_limited"
    category = "rate_limit"
    retryable = True


@dataclass(frozen=True)
class BulkPublication:
    dataset: str
    release_id: str
    label: str
    data_url: str
    layout_url: str
    data_filename: str
    member_name: str
    layout_filename: str
    headers: tuple[str, ...]
    observed_data_size: int
    observed_data_sha256: str
    observed_layout_size: int
    observed_layout_sha256: str
    observed_line_count_including_header: int
    observed_member_uncompressed_size: int

    @property
    def observed_data_row_count(self) -> int:
        return self.observed_line_count_including_header - 1

    @property
    def schema(self) -> dict[str, Any]:
        return {
            "format": "zip_single_member_comma_delimited_ascii",
            "dataset": self.dataset,
            "member_name": self.member_name,
            "headers": list(self.headers),
            "field_count": len(self.headers),
            "parcel_join": (
                "ParcelNumber"
                if self.dataset == "current"
                else "Parcel No"
            ),
            "parcel_join_rule": "exact_normalized_15_digit_account_only",
            "row_occurrence_key": [
                "artifact_sha256",
                "archive_member_path",
                "source_row_number",
            ],
        }

    @property
    def schema_fingerprint(self) -> str:
        return sha256_fingerprint(self.schema)

    def artifact(self, role: str = "data") -> BulkArtifact:
        if role == "data":
            return BulkArtifact(
                artifact_id=f"{self.release_id}-data",
                url=self.data_url,
                filename=self.data_filename,
                media_type="application/zip",
                archive_format="zip",
                metadata={
                    "role": "data",
                    "dataset": self.dataset,
                    "publication_date": PUBLICATION_DATE,
                    "observed_size": self.observed_data_size,
                    "observed_sha256": self.observed_data_sha256,
                    "observed_line_count_including_header": (
                        self.observed_line_count_including_header
                    ),
                    "publisher_checksum_available": False,
                },
            )
        if role == "layout":
            return BulkArtifact(
                artifact_id=f"{self.release_id}-layout",
                url=self.layout_url,
                filename=self.layout_filename,
                media_type="application/msword",
                metadata={
                    "role": "layout",
                    "dataset": self.dataset,
                    "observed_size": self.observed_layout_size,
                    "observed_sha256": self.observed_layout_sha256,
                    "layout_document_state": "Current as of 02/15/2011",
                    "publisher_checksum_available": False,
                },
            )
        raise OrangeTaxQueryError(
            "artifact role must be data or layout",
            details={"artifact_role": role},
        )

    def manifest(self) -> BulkDatasetManifest:
        return BulkDatasetManifest(
            source_id=SOURCE_ID,
            dataset_id=f"orange-tax-collector-{self.dataset}-roll",
            release=BulkReleaseMetadata(
                release_id=self.release_id,
                kind="snapshot",
                effective_at=PUBLICATION_DATE,
                coverage={
                    "county_geoid": COUNTY_GEOID,
                    "dataset": self.dataset,
                    "official_page_label_date": PUBLICATION_DATE,
                    "publication_state": "fixed_historical_snapshot",
                },
            ),
            artifacts=(
                self.artifact("data"),
                self.artifact("layout"),
            ),
            schema=self.schema,
            metadata={
                "authority": "Orange County Tax Collector",
                "official_listing_url": OFFICIAL_TAX_ROLL_PAGE,
                "official_listing_label": self.label,
                "publication_state": "fixed_historical_snapshot",
                "not_a_live_cadence": True,
                "observed_artifact": {
                    "data_sha256": self.observed_data_sha256,
                    "data_size": self.observed_data_size,
                    "layout_sha256": self.observed_layout_sha256,
                    "layout_size": self.observed_layout_size,
                    "line_count_including_header": (
                        self.observed_line_count_including_header
                    ),
                    "data_row_count": self.observed_data_row_count,
                    "member_uncompressed_size": (
                        self.observed_member_uncompressed_size
                    ),
                    "observation_basis": (
                        "official page and linked artifacts observed 2026-07"
                    ),
                },
                "identity_contract": {
                    "parcel_join": (
                        "exact normalized 15-digit Orange County account"
                    ),
                    "artifact_occurrence": "artifact_sha256",
                    "member_occurrence": [
                        "artifact_sha256",
                        "archive_member_path",
                    ],
                    "row_occurrence": [
                        "artifact_sha256",
                        "archive_member_path",
                        "source_row_number",
                    ],
                    "TaxSummaryID": "source_identifier_not_parcel_join",
                    "certificate": (
                        "certificate_year_number_sequence_source_identity"
                    ),
                    "validation_number": (
                        "source_payment_validation_identity"
                    ),
                },
            },
        )


BULK_PUBLICATIONS = {
    "current": BulkPublication(
        dataset="current",
        release_id="orange-current-roll-2020-02-17",
        label=(
            "Daily Real Estate Update File Zipped Comma Delimited "
            "as of 02/17/20"
        ),
        data_url=CURRENT_ROLL_URL,
        layout_url=CURRENT_LAYOUT_URL,
        data_filename="TaxPaymentTape.zip",
        member_name="TaxPaymentTape.txt",
        layout_filename="LayoutRENew.doc",
        headers=CURRENT_HEADERS,
        observed_data_size=30_315_052,
        observed_data_sha256=(
            "039995d108f7dd71d683dc3821536168c"
            "db9c0c529887f0120b6757103a056ce"
        ),
        observed_layout_size=56_832,
        observed_layout_sha256=(
            "0dd896ec2e43d5c682f29b006d98e6d"
            "50db3cc021956000aec81396711fc3ba7"
        ),
        observed_line_count_including_header=464_380,
        observed_member_uncompressed_size=132_995_185,
    ),
    "delinquent": BulkPublication(
        dataset="delinquent",
        release_id="orange-delinquent-roll-2020-02-17",
        label=(
            "Daily Delinquent Real Estate Update File Zipped Comma "
            "Delimited as of 02/17/20"
        ),
        data_url=DELINQUENT_ROLL_URL,
        layout_url=DELINQUENT_LAYOUT_URL,
        data_filename="DelinquentRealEstateTaxData.zip",
        member_name="DelinquentRealEstateTaxData.csv",
        layout_filename="LayoutDQNew.doc",
        headers=DELINQUENT_HEADERS,
        observed_data_size=8_286_609,
        observed_data_sha256=(
            "454b57e312020520075331decf02f9957"
            "ae3b13acb6a3fa5752e4ab46abf7eb9"
        ),
        observed_layout_size=70_656,
        observed_layout_sha256=(
            "f16fbddbd66a7629081cf686387595569"
            "dec2a811875b9fcef1c5b6c39d47dde"
        ),
        observed_line_count_including_header=118_348,
        observed_member_uncompressed_size=48_583_771,
    ),
}


def _publication(dataset: str) -> BulkPublication:
    try:
        return BULK_PUBLICATIONS[dataset]
    except KeyError as exc:
        raise OrangeTaxQueryError(
            "bulk dataset must be current or delinquent",
            details={"dataset": dataset},
        ) from exc


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _element_text(element: Any) -> str | None:
    if element is None:
        return None
    return _clean_text(element.get_text(" ", strip=True))


def normalize_account(value: str) -> str:
    """Return the exact 15-digit parcel join key."""

    text = str(value).strip()
    if not text or re.fullmatch(r"[\d\s-]+", text) is None:
        raise OrangeTaxQueryError(
            "Orange parcel account must contain only digits, spaces, or hyphens",
            details={"account": text},
        )
    digits = re.sub(r"\D", "", text)
    if len(digits) != 15:
        raise OrangeTaxQueryError(
            "Orange parcel account must normalize to exactly 15 digits",
            details={"account": text, "normalized_length": len(digits)},
        )
    return digits


def _optional_account(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return normalize_account(text)
    except OrangeTaxQueryError:
        return None


def format_account(account: str) -> str:
    digits = normalize_account(account)
    return (
        f"{digits[:2]}-{digits[2:4]}-{digits[4:6]}-"
        f"{digits[6:10]}-{digits[10:]}"
    )


def _account_ref(account: str) -> str:
    return canonical_property_ref(
        SOURCE_ID,
        COUNTY_GEOID,
        "parcel-account",
        normalize_account(account),
    )


def _urlsafe_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _urlsafe_decode(value: str) -> str:
    token = value.strip()
    if not token or re.fullmatch(r"[A-Za-z0-9_-]+", token) is None:
        raise OrangeTaxQueryError(
            "TaxSys account token is not URL-safe base64",
            code="orange_tax_account_token_invalid",
        )
    padding = "=" * (-len(token) % 4)
    try:
        decoded = base64.urlsafe_b64decode(token + padding).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise OrangeTaxQueryError(
            "TaxSys account token could not be decoded",
            code="orange_tax_account_token_invalid",
        ) from exc
    return decoded


def account_token_from_object_id(object_id: str) -> tuple[str, str]:
    """Return ``(semantic_id, token)`` from a verified Algolia object ID."""

    value = str(object_id).strip()
    if not value.startswith(ALGOLIA_OBJECT_PREFIX):
        raise OrangeTaxSourceChanged(
            "Orange Algolia objectID no longer uses the TaxSys item prefix",
            details={"objectID": value},
        )
    semantic_id = value[len(ALGOLIA_OBJECT_PREFIX) :]
    if not semantic_id.startswith(ACCOUNT_SEMANTIC_PREFIX):
        raise OrangeTaxSourceChanged(
            "Orange Algolia objectID is not a real-estate parent account",
            details={"objectID": value},
        )
    native_uuid = semantic_id[len(ACCOUNT_SEMANTIC_PREFIX) :]
    if UUID_RE.fullmatch(native_uuid) is None:
        raise OrangeTaxSourceChanged(
            "Orange Algolia parent objectID lacks a valid native UUID",
            details={"objectID": value},
        )
    return semantic_id, _urlsafe_encode(semantic_id)


def validate_account_token(token: str) -> str:
    semantic_id = _urlsafe_decode(token)
    if not semantic_id.startswith(ACCOUNT_SEMANTIC_PREFIX):
        raise OrangeTaxQueryError(
            "TaxSys account token is not an Orange real-estate parent token",
            code="orange_tax_account_token_invalid",
        )
    native_uuid = semantic_id[len(ACCOUNT_SEMANTIC_PREFIX) :]
    if UUID_RE.fullmatch(native_uuid) is None:
        raise OrangeTaxQueryError(
            "TaxSys account token lacks a valid native UUID",
            code="orange_tax_account_token_invalid",
        )
    return semantic_id


def _native_parent_uuid(semantic_id: str) -> str:
    return semantic_id[len(ACCOUNT_SEMANTIC_PREFIX) :]


def _history_url(token: str) -> str:
    validate_account_token(token)
    return f"{TAXSYS_ROOT}/property-tax/{token}/load-bill-history"


def _bill_url(token: str, bill_uuid: str) -> str:
    validate_account_token(token)
    bill_id = bill_uuid.strip().lower()
    if UUID_RE.fullmatch(bill_id) is None:
        raise OrangeTaxQueryError(
            "bill ID must be a UUID",
            details={"bill_uuid": bill_uuid},
        )
    return f"{TAXSYS_ROOT}/property-tax/{token}/bills/{bill_id}"


def _money_decimal(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None or text in {"—", "-"}:
        return None
    normalized = text.replace("$", "").replace(",", "").replace("%", "")
    try:
        number = Decimal(normalized)
    except InvalidOperation:
        return None
    return format(number, "f")


def _integer(value: Any) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _boolean(value: Any) -> bool | None:
    text = _clean_text(value)
    if text == "1":
        return True
    if text == "0":
        return False
    return None


def _date_value(value: Any, *, datetime_allowed: bool = False) -> dict[str, Any]:
    raw = _clean_text(value)
    if raw is None:
        return {"raw": None, "iso": None}
    formats = ["%m/%d/%Y"]
    if datetime_allowed:
        formats.extend(
            [
                "%m/%d/%Y %I:%M:%S %p",
                "%m/%d/%Y %H:%M:%S",
            ]
        )
    parsed: datetime | None = None
    for date_format in formats:
        try:
            parsed = datetime.strptime(raw, date_format)
            break
        except ValueError:
            continue
    iso = parsed.isoformat() if parsed is not None else None
    if parsed is not None and parsed.date().isoformat() == "1900-01-01":
        iso = None
    return {"raw": raw, "iso": iso}


def _document_fingerprint(html: str, contract: Mapping[str, Any]) -> str:
    return sha256_fingerprint(
        {
            "document_sha256": hashlib.sha256(
                html.encode("utf-8")
            ).hexdigest(),
            "contract": contract,
        }
    )


def normalize_portal_hit(hit: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one Algolia account hit while preserving source fields."""

    object_id = _clean_text(hit.get("objectID"))
    external_id = _clean_text(hit.get("external_id"))
    custom = hit.get("custom_parameters")
    if (
        object_id is None
        or external_id is None
        or not isinstance(custom, Mapping)
    ):
        raise OrangeTaxSourceChanged(
            "Orange search hit lacks objectID, external_id, or custom_parameters",
            details={"hit_keys": sorted(str(key) for key in hit)},
        )
    account = _optional_account(external_id)
    if account is None:
        raise OrangeTaxSourceChanged(
            "Orange property-tax search hit lacks a 15-digit parcel account",
            details={"external_id": external_id},
        )
    semantic_id, token = account_token_from_object_id(object_id)

    raw_entities = custom.get("entities")
    if raw_entities is None:
        raw_entities = []
    if not isinstance(raw_entities, Sequence) or isinstance(
        raw_entities, (str, bytes)
    ):
        raise OrangeTaxSourceChanged(
            "Orange search entities are no longer a list",
            details={"objectID": object_id},
        )
    entities: list[dict[str, Any]] = []
    owners: list[dict[str, Any]] = []
    situs: list[dict[str, Any]] = []
    billing: list[dict[str, Any]] = []
    for item in raw_entities:
        if not isinstance(item, Mapping):
            raise OrangeTaxSourceChanged(
                "Orange search entity is no longer an object",
                details={"objectID": object_id},
            )
        entity = {
            key: _clean_text(item.get(key))
            for key in (
                "external_id",
                "external_type",
                "name",
                "address",
                "city",
                "state",
                "province",
                "zip",
                "country",
            )
        }
        entities.append(entity)
        entity_type = (entity["external_type"] or "").casefold()
        if entity_type == "owner/address":
            owners.append(
                {
                    **entity,
                    "assertion_type": "tax_account_owner_label",
                    "title_caveat": "not_a_title_chain",
                }
            )
        elif entity_type == "address":
            situs.append(entity)
        elif entity_type == "billing address":
            billing.append(entity)

    alternate_keys: list[dict[str, Any]] = []
    raw_alternates = custom.get("alternate_keys") or []
    if not isinstance(raw_alternates, Sequence) or isinstance(
        raw_alternates, (str, bytes)
    ):
        raise OrangeTaxSourceChanged(
            "Orange alternate_keys are no longer a list",
            details={"objectID": object_id},
        )
    for alternate in raw_alternates:
        if isinstance(alternate, Mapping):
            alternate_keys.append(
                {
                    "external_id": _clean_text(
                        alternate.get("external_id")
                    ),
                    "external_type": _clean_text(
                        alternate.get("external_type")
                    ),
                }
            )

    public_url_path = _clean_text(custom.get("public_url"))
    child_groups = hit.get("child_groups") or []
    roll_year_values: set[int] = set()
    top_roll_year = _integer(custom.get("roll_year"))
    if top_roll_year is not None:
        roll_year_values.add(top_roll_year)
    if not isinstance(child_groups, Sequence) or isinstance(
        child_groups,
        (str, bytes),
    ):
        raise OrangeTaxSourceChanged(
            "Orange child_groups are no longer a list",
            details={"objectID": object_id},
        )
    for group in child_groups:
        if not isinstance(group, Mapping):
            raise OrangeTaxSourceChanged(
                "Orange child group is no longer an object",
                details={"objectID": object_id},
            )
        children = group.get("children") or []
        if not isinstance(children, Sequence) or isinstance(
            children,
            (str, bytes),
        ):
            raise OrangeTaxSourceChanged(
                "Orange child group children are no longer a list",
                details={"objectID": object_id},
            )
        for child in children:
            if not isinstance(child, Mapping):
                raise OrangeTaxSourceChanged(
                    "Orange child account is no longer an object",
                    details={"objectID": object_id},
                )
            child_custom = child.get("custom_parameters")
            if isinstance(child_custom, Mapping):
                child_year = _integer(child_custom.get("roll_year"))
                if child_year is not None:
                    roll_year_values.add(child_year)
    if len(roll_year_values) > 1:
        raise OrangeTaxSourceChanged(
            "Orange search hit publishes conflicting roll years",
            details={
                "objectID": object_id,
                "roll_years": sorted(roll_year_values),
            },
        )
    roll_year = next(iter(roll_year_values), None)
    return {
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_account_search_hit",
        "canonical_ref": _account_ref(account),
        "parcel_join": {
            "normalized_15_digit_account": account,
            "formatted_account": format_account(account),
            "exact": True,
        },
        "native_account_id": external_id,
        "algolia_object_id": object_id,
        "taxsys_parent_semantic_id": semantic_id,
        "taxsys_parent_uuid": _native_parent_uuid(semantic_id),
        "taxsys_account_token": token,
        "alternate_keys": alternate_keys,
        "roll_year": roll_year,
        "display_name": _clean_text(hit.get("display_name")),
        "display_type": _clean_text(hit.get("display_type")),
        "item_category": _clean_text(hit.get("item_category")),
        "owners": owners,
        "situs_entities": situs,
        "billing_entities": billing,
        "entities": entities,
        "public_url_path": public_url_path,
        "portal_url": (
            urljoin(GOVHUB_PORTAL_URL, public_url_path)
            if public_url_path
            else GOVHUB_PORTAL_URL
        ),
        "account_history_url": _history_url(token),
        "identity_contract": {
            "parcel_join": "normalized_15_digit_account",
            "source_occurrence": "algolia_object_id",
            "account_locator": "taxsys_account_token",
            "alternate_key": "separate_source_identifier",
        },
        "raw": {
            "external_id_tokens": hit.get("external_id_tokens"),
            "child_groups": child_groups,
            "custom_parameters": dict(custom),
        },
    }


def _portal_cursor(
    query_text: str,
    *,
    page: int,
    offset: int,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "index": ALGOLIA_INDEX,
        "query": query_text,
        "hits_per_page": ALGOLIA_HITS_PER_PAGE,
        "page": page,
        "offset": offset,
    }
    return PORTAL_CURSOR_PREFIX + _urlsafe_encode(canonical_json(payload))


def _parse_portal_cursor(
    cursor: str | None,
    *,
    query_text: str,
) -> tuple[int, int]:
    if cursor is None:
        return 0, 0
    if not cursor.startswith(PORTAL_CURSOR_PREFIX):
        raise OrangeTaxQueryError(
            "portal cursor is not an Orange Tax Collector continuation",
            code="orange_tax_portal_cursor_invalid",
        )
    try:
        payload = json.loads(
            _urlsafe_decode(cursor[len(PORTAL_CURSOR_PREFIX) :])
        )
    except (json.JSONDecodeError, OrangeTaxQueryError) as exc:
        raise OrangeTaxQueryError(
            "portal cursor payload is invalid",
            code="orange_tax_portal_cursor_invalid",
        ) from exc
    expected = {
        "version": CURSOR_VERSION,
        "index": ALGOLIA_INDEX,
        "query": query_text,
        "hits_per_page": ALGOLIA_HITS_PER_PAGE,
    }
    if not isinstance(payload, Mapping) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise OrangeTaxQueryError(
            "portal cursor belongs to a different query or index",
            code="orange_tax_portal_cursor_mismatch",
            details={"expected": expected},
        )
    page = payload.get("page")
    offset = payload.get("offset")
    if (
        isinstance(page, bool)
        or not isinstance(page, int)
        or page < 0
        or isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or offset > ALGOLIA_HITS_PER_PAGE
    ):
        raise OrangeTaxQueryError(
            "portal cursor page or offset is invalid",
            code="orange_tax_portal_cursor_invalid",
        )
    return page, offset


@dataclass(frozen=True)
class PortalSearchResult:
    records: tuple[dict[str, Any], ...]
    next_cursor: str | None
    total_hits: int
    pages_fetched: int
    requests_made: int
    response_contract_fingerprints: tuple[str, ...]


class OrangeTaxPortalClient:
    """Transport-injectable client for Algolia and anonymous TaxSys pages."""

    def __init__(
        self,
        *,
        session: Any | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retry_policy: RetryPolicy | None = None,
        minimum_interval: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if minimum_interval < 0:
            raise ValueError("minimum_interval must not be negative")
        self.session = session or system_trust_session()
        self.timeout = timeout
        self.retry_policy = retry_policy or RetryPolicy(
            max_attempts=DEFAULT_RETRY_ATTEMPTS
        )
        self.minimum_interval = minimum_interval
        self.clock = clock
        self.sleeper = sleeper
        self._last_request_at: float | None = None
        self.request_count = 0

    def _wait(self) -> None:
        if self._last_request_at is not None:
            remaining = (
                self.minimum_interval
                - (self.clock() - self._last_request_at)
            )
            if remaining > 0:
                self.sleeper(remaining)
        self._last_request_at = self.clock()

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        last_error: BaseException | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            self._wait()
            self.request_count += 1
            try:
                kwargs: dict[str, Any] = {
                    "headers": dict(headers),
                    "timeout": self.timeout,
                }
                if json_body is not None:
                    kwargs["json"] = dict(json_body)
                response = self.session.request(method, url, **kwargs)
            except (
                RequestException,
                TimeoutError,
                ConnectionError,
                OSError,
            ) as exc:
                last_error = exc
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                raise OrangeTaxTransportError(
                    f"Orange Tax Collector request failed: {exc}",
                    details={"url": url, "attempts": attempt},
                ) from exc

            status = int(
                getattr(
                    response,
                    "status_code",
                    getattr(response, "status", 0),
                )
            )
            if status in self.retry_policy.retry_statuses:
                if attempt < self.retry_policy.max_attempts:
                    self.sleeper(self.retry_policy.delay(attempt))
                    continue
                if status == 429:
                    raise OrangeTaxRateLimited(
                        "Orange Tax Collector source rate limited the request",
                        details={"url": url, "status_code": status},
                    )
                raise OrangeTaxTransportError(
                    f"Orange Tax Collector source returned HTTP {status}",
                    details={"url": url, "status_code": status},
                )
            if status in {401, 403}:
                raise OrangeTaxRestricted(
                    f"Orange Tax Collector source returned HTTP {status}",
                    details={"url": url, "status_code": status},
                )
            if status in {404, 410}:
                raise OrangeTaxSourceChanged(
                    f"Orange Tax Collector route returned HTTP {status}",
                    details={"url": url, "status_code": status},
                )
            if status < 200 or status >= 300:
                raise OrangeTaxTransportError(
                    f"Orange Tax Collector source returned HTTP {status}",
                    details={"url": url, "status_code": status},
                    retryable=False,
                )
            return response
        raise OrangeTaxTransportError(
            f"Orange Tax Collector request failed: {last_error}",
            details={"url": url},
        )

    def _search_page(self, query_text: str, page: int) -> Mapping[str, Any]:
        params = urlencode(
            {
                "query": query_text,
                "hitsPerPage": ALGOLIA_HITS_PER_PAGE,
                "page": page,
            }
        )
        response = self._request(
            "POST",
            ALGOLIA_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
                "X-Algolia-Application-Id": ALGOLIA_APPLICATION_ID,
                "X-Algolia-API-Key": ALGOLIA_PUBLIC_SEARCH_KEY,
            },
            json_body={
                "requests": [
                    {
                        "indexName": ALGOLIA_INDEX,
                        "params": params,
                    }
                ]
            },
        )
        try:
            body = response.json()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise OrangeTaxSourceChanged(
                "Orange search endpoint returned invalid JSON",
                details={"url": ALGOLIA_URL},
            ) from exc
        results = body.get("results") if isinstance(body, Mapping) else None
        if (
            not isinstance(results, Sequence)
            or isinstance(results, (str, bytes))
            or len(results) != 1
            or not isinstance(results[0], Mapping)
        ):
            raise OrangeTaxSourceChanged(
                "Orange search response no longer contains one result page",
                details={"response_type": type(body).__name__},
            )
        result = results[0]
        required = {
            "hits",
            "nbHits",
            "page",
            "nbPages",
            "hitsPerPage",
            "query",
            "index",
        }
        if not required.issubset(result):
            raise OrangeTaxSourceChanged(
                "Orange search result page lacks required pagination fields",
                details={"keys": sorted(str(key) for key in result)},
            )
        if (
            result.get("index") != ALGOLIA_INDEX
            or result.get("query") != query_text
            or result.get("hitsPerPage") != ALGOLIA_HITS_PER_PAGE
            or result.get("page") != page
            or not isinstance(result.get("hits"), list)
        ):
            raise OrangeTaxSourceChanged(
                "Orange search response pagination contract changed",
                details={
                    "index": result.get("index"),
                    "query": result.get("query"),
                    "hitsPerPage": result.get("hitsPerPage"),
                    "page": result.get("page"),
                },
            )
        return result

    def search(
        self,
        query_text: str,
        *,
        limit: int = ALGOLIA_HITS_PER_PAGE,
        cursor: str | None = None,
    ) -> PortalSearchResult:
        query_value = query_text.strip()
        if not query_value:
            raise OrangeTaxQueryError("portal search query must not be empty")
        if isinstance(limit, bool) or limit <= 0:
            raise OrangeTaxQueryError("search limit must be positive")
        page, offset = _parse_portal_cursor(
            cursor,
            query_text=query_value,
        )
        records: list[dict[str, Any]] = []
        pages_fetched = 0
        total_hits = 0
        contract_fingerprints: list[str] = []
        next_cursor: str | None = None

        while len(records) < limit:
            result = self._search_page(query_value, page)
            pages_fetched += 1
            try:
                total_hits = int(result["nbHits"])
                nb_pages = int(result["nbPages"])
            except (TypeError, ValueError) as exc:
                raise OrangeTaxSourceChanged(
                    "Orange search response has invalid page counts",
                    details={
                        "nbHits": result.get("nbHits"),
                        "nbPages": result.get("nbPages"),
                    },
                ) from exc
            if total_hits < 0 or nb_pages < 0:
                raise OrangeTaxSourceChanged(
                    "Orange search response has negative page counts",
                    details={
                        "nbHits": total_hits,
                        "nbPages": nb_pages,
                    },
                )
            hits = result["hits"]
            if offset > len(hits):
                raise OrangeTaxQueryError(
                    "portal cursor offset exceeds its result page",
                    code="orange_tax_portal_cursor_invalid",
                )
            contract = {
                "index": result["index"],
                "hitsPerPage": result["hitsPerPage"],
                "keys": sorted(str(key) for key in result),
                "hit_keys": sorted(
                    {
                        str(key)
                        for hit in hits
                        if isinstance(hit, Mapping)
                        for key in hit
                        if key != "_highlightResult"
                    }
                ),
            }
            contract_fingerprints.append(sha256_fingerprint(contract))

            for hit_offset in range(offset, len(hits)):
                if len(records) >= limit:
                    next_cursor = _portal_cursor(
                        query_value,
                        page=page,
                        offset=hit_offset,
                    )
                    break
                hit = hits[hit_offset]
                if not isinstance(hit, Mapping):
                    raise OrangeTaxSourceChanged(
                        "Orange search hit is no longer an object",
                        details={"page": page, "offset": hit_offset},
                    )
                records.append(normalize_portal_hit(hit))
            if next_cursor is not None:
                break
            if len(records) >= limit:
                if page + 1 < nb_pages:
                    next_cursor = _portal_cursor(
                        query_value,
                        page=page + 1,
                        offset=0,
                    )
                break
            page += 1
            offset = 0
            if page >= nb_pages:
                break

        return PortalSearchResult(
            records=tuple(records),
            next_cursor=next_cursor,
            total_hits=total_hits,
            pages_fetched=pages_fetched,
            requests_made=pages_fetched,
            response_contract_fingerprints=tuple(contract_fingerprints),
        )

    def resolve_account(self, account: str) -> dict[str, Any]:
        normalized = normalize_account(account)
        search = self.search(normalized, limit=ALGOLIA_HITS_PER_PAGE)
        exact = [
            record
            for record in search.records
            if record["parcel_join"]["normalized_15_digit_account"]
            == normalized
        ]
        if not exact:
            raise OrangeTaxQueryError(
                "Orange Tax Collector search returned no exact account",
                status=ResultStatus.NO_RESULTS,
                code="orange_tax_account_not_found",
                details={"account": normalized},
            )
        if len(exact) != 1:
            raise OrangeTaxSourceChanged(
                "Orange Tax Collector search returned duplicate exact accounts",
                details={"account": normalized, "count": len(exact)},
            )
        return exact[0]

    def _get_html(self, url: str, *, referer: str) -> str:
        response = self._request(
            "GET",
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Referer": referer,
                "User-Agent": USER_AGENT,
            },
        )
        response_headers = {
            str(key).casefold(): str(value)
            for key, value in getattr(response, "headers", {}).items()
        }
        content_type = response_headers.get("content-type", "").casefold()
        text = str(getattr(response, "text", ""))
        if "html" not in content_type and not re.search(
            r"<(?:!doctype|html|table)\b", text, re.I
        ):
            raise OrangeTaxSourceChanged(
                "Orange TaxSys route no longer returned HTML",
                details={"url": url, "content_type": content_type},
            )
        if (
            "just a moment" in text.casefold()
            or "cf-mitigated" in response_headers
        ):
            raise OrangeTaxRestricted(
                "Orange TaxSys route returned an access challenge",
                details={"url": url},
            )
        return text

    def history_html(self, token: str) -> tuple[str, str]:
        url = _history_url(token)
        return url, self._get_html(url, referer=GOVHUB_PORTAL_URL)

    def bill_html(self, token: str, bill_uuid: str) -> tuple[str, str]:
        url = _bill_url(token, bill_uuid)
        return url, self._get_html(url, referer=GOVHUB_PORTAL_URL)

    def bulk_landing_html(self) -> tuple[str, str]:
        return (
            OFFICIAL_TAX_ROLL_PAGE,
            self._get_html(
                OFFICIAL_TAX_ROLL_PAGE,
                referer=OFFICIAL_TAX_ROLL_PAGE,
            ),
        )


def _extract_bill_identity(href: str | None) -> tuple[str, str] | None:
    if not href:
        return None
    match = BILL_URL_RE.search(href)
    if match is None:
        return None
    token = match.group("token")
    validate_account_token(token)
    bill_uuid = match.group("bill").lower()
    if UUID_RE.fullmatch(bill_uuid) is None:
        return None
    return token, bill_uuid


def parse_bill_history_html(
    html: str,
    *,
    account_token: str,
    parcel_account: str | None = None,
    source_url: str | None = None,
) -> list[dict[str, Any]]:
    """Parse TaxSys's anonymous account-history HTML fragment."""

    semantic_id = validate_account_token(account_token)
    normalized_account = (
        normalize_account(parcel_account)
        if parcel_account is not None
        else None
    )
    soup = BeautifulSoup(html, "html.parser")
    headers = [_element_text(item) for item in soup.select("thead th")]
    if "Bill" not in headers or "Amount due" not in headers:
        raise OrangeTaxSourceChanged(
            "Orange bill-history table headers changed",
            details={"headers": headers},
        )
    document_sha = hashlib.sha256(html.encode("utf-8")).hexdigest()
    records: list[dict[str, Any]] = []
    bill_ids: set[str] = set()

    for row in soup.select("tr.regular"):
        description = row.select_one("th.description")
        link = description.find("a", href=True) if description else None
        identity = _extract_bill_identity(
            str(link.get("href")) if link is not None else None
        )
        if identity is None:
            raise OrangeTaxSourceChanged(
                "Orange bill-history row lacks a bill UUID link"
            )
        row_token, bill_uuid = identity
        if row_token != account_token:
            raise OrangeTaxSourceChanged(
                "Orange bill-history row belongs to a different account token",
                details={"bill_uuid": bill_uuid},
            )
        if bill_uuid in bill_ids:
            raise OrangeTaxSourceChanged(
                "Orange bill-history fragment duplicates a bill UUID",
                details={"bill_uuid": bill_uuid},
            )
        bill_ids.add(bill_uuid)
        description_text = _element_text(link)
        year_match = re.search(r"\b(19|20)\d{2}\b", description_text or "")
        tax_year = int(year_match.group(0)) if year_match else None
        balance = _element_text(row.select_one("td.balance"))
        status_cell = row.select_one("td.status")
        status = _element_text(
            status_cell.select_one(".label") if status_cell else None
        )
        status_amount = None
        if status_cell is not None:
            translated = status_cell.select_one("[translate='no']")
            status_amount = _element_text(translated)
        payment_date = _element_text(row.select_one("td.as-of time"))
        message = _element_text(row.select_one("td.message"))
        receipt_match = re.search(
            r"\bReceipt\s*#?([A-Za-z0-9-]+)",
            message or "",
            re.I,
        )
        print_link = row.select_one("a.print-link-with-icon[href]")
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "property_tax_bill_history",
                "canonical_ref": canonical_property_ref(
                    SOURCE_ID,
                    COUNTY_GEOID,
                    "tax-bill",
                    bill_uuid,
                ),
                "parcel_join": (
                    {
                        "normalized_15_digit_account": normalized_account,
                        "formatted_account": format_account(
                            normalized_account
                        ),
                        "exact": True,
                    }
                    if normalized_account
                    else None
                ),
                "taxsys_parent_semantic_id": semantic_id,
                "taxsys_account_token": account_token,
                "bill_uuid": bill_uuid,
                "tax_year": tax_year,
                "description": description_text,
                "balance_due": {
                    "raw": balance,
                    "decimal": _money_decimal(balance),
                    "currency": "USD",
                },
                "status": {
                    "raw": status,
                    "amount_raw": status_amount,
                    "amount_decimal": _money_decimal(status_amount),
                    "retrieved_state": True,
                },
                "payment": (
                    {
                        "date": _date_value(payment_date),
                        "receipt_number": (
                            receipt_match.group(1)
                            if receipt_match
                            else None
                        ),
                        "occurrence_key": [
                            bill_uuid,
                            (
                                receipt_match.group(1)
                                if receipt_match
                                else None
                            ),
                            payment_date,
                        ],
                    }
                    if payment_date or receipt_match
                    else None
                ),
                "bill_url": str(link.get("href")),
                "print_pdf_url": (
                    str(print_link.get("href"))
                    if print_link is not None
                    else None
                ),
                "source_document_url": source_url,
                "source_document_sha256": document_sha,
            }
        )

    for row in soup.select("tr.certificate"):
        link = row.select_one("th.description a[href]")
        identity = _extract_bill_identity(
            str(link.get("href")) if link is not None else None
        )
        if identity is None:
            raise OrangeTaxSourceChanged(
                "Orange certificate row lacks a linked bill UUID"
            )
        row_token, bill_uuid = identity
        if row_token != account_token:
            raise OrangeTaxSourceChanged(
                "Orange certificate belongs to a different account token"
            )
        description = _element_text(link)
        number_match = re.search(
            r"\bCertificate\s*#?([A-Za-z0-9-]+)",
            description or "",
            re.I,
        )
        if number_match is None:
            raise OrangeTaxSourceChanged(
                "Orange certificate row lacks a certificate number",
                details={"description": description},
            )
        certificate_number = number_match.group(1)
        message = _element_text(row.select_one("td.message"))
        face_match = re.search(
            r"\bFace\s*(\$[\d,.]+)",
            message or "",
            re.I,
        )
        rate_match = re.search(
            r"\bRate\s*([\d.]+%)",
            message or "",
            re.I,
        )
        status = _element_text(row.select_one("td.status .label"))
        status_date = _element_text(row.select_one("td.as-of"))
        records.append(
            {
                "source_id": SOURCE_ID,
                "record_kind": "property_tax_certificate_history",
                "canonical_ref": canonical_property_ref(
                    SOURCE_ID,
                    COUNTY_GEOID,
                    "tax-certificate",
                    f"{bill_uuid}:{certificate_number}",
                ),
                "parcel_join": (
                    {
                        "normalized_15_digit_account": normalized_account,
                        "formatted_account": format_account(
                            normalized_account
                        ),
                        "exact": True,
                    }
                    if normalized_account
                    else None
                ),
                "taxsys_parent_semantic_id": semantic_id,
                "taxsys_account_token": account_token,
                "bill_uuid": bill_uuid,
                "certificate_number": certificate_number,
                "certificate_status": status,
                "status_date": _date_value(status_date),
                "face_value": {
                    "raw": face_match.group(1) if face_match else None,
                    "decimal": _money_decimal(
                        face_match.group(1) if face_match else None
                    ),
                    "currency": "USD",
                },
                "interest_rate": {
                    "raw": rate_match.group(1) if rate_match else None,
                    "percent_decimal": _money_decimal(
                        rate_match.group(1) if rate_match else None
                    ),
                },
                "source_document_url": source_url,
                "source_document_sha256": document_sha,
            }
        )

    contract = {
        "headers": headers,
        "record_kinds": sorted(
            {str(record["record_kind"]) for record in records}
        ),
        "bill_count": sum(
            record["record_kind"] == "property_tax_bill_history"
            for record in records
        ),
        "certificate_count": sum(
            record["record_kind"] == "property_tax_certificate_history"
            for record in records
        ),
    }
    fingerprint = _document_fingerprint(html, contract)
    for record in records:
        record["response_contract_fingerprint"] = fingerprint
    return records


def _label_value_rows(container: Any) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    if container is None:
        return result
    for row in container.select(".row"):
        label_element = row.select_one(".label")
        value_element = row.select_one(".value")
        label = _element_text(label_element)
        if label is None or value_element is None:
            continue
        result[label.rstrip(":").casefold()] = _element_text(value_element)
    return result


def parse_bill_detail_html(
    html: str,
    *,
    account_token: str,
    bill_uuid: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Parse one full TaxSys bill detail HTML page."""

    semantic_id = validate_account_token(account_token)
    normalized_bill = bill_uuid.strip().lower()
    if UUID_RE.fullmatch(normalized_bill) is None:
        raise OrangeTaxQueryError("bill ID must be a UUID")
    soup = BeautifulSoup(html, "html.parser")
    account_header = _element_text(soup.select_one(".account-header h1"))
    account_match = re.search(
        r"Account\s*#?([\d-]{15,25})",
        account_header or "",
        re.I,
    )
    if account_match is None:
        raise OrangeTaxSourceChanged(
            "Orange bill detail lacks its account heading",
            details={"heading": account_header},
        )
    account = normalize_account(account_match.group(1))
    bill_heading = _element_text(soup.select_one("h2#bill"))
    if bill_heading is None:
        raise OrangeTaxSourceChanged(
            "Orange bill detail lacks its bill heading"
        )
    year_match = re.search(r"\b(19|20)\d{2}\b", bill_heading)
    tax_year = int(year_match.group(0)) if year_match else None

    print_links = [
        str(link.get("href"))
        for link in soup.select("a.print-link-with-icon[href]")
        if _extract_bill_identity(str(link.get("href")))
    ]
    matching_links = [
        link
        for link in print_links
        if normalized_bill in link.casefold()
    ]
    if not matching_links:
        raise OrangeTaxSourceChanged(
            "Orange bill detail does not reference the requested bill UUID",
            details={"bill_uuid": normalized_bill},
        )

    bill_table_row = soup.select_one(".individual-bill table.bills tbody tr")
    if bill_table_row is None:
        raise OrangeTaxSourceChanged(
            "Orange bill detail lacks its bill summary row"
        )
    summary = {
        "description": _element_text(
            bill_table_row.select_one(".description")
        ),
        "alternate_key": _element_text(
            bill_table_row.select_one(".alternate")
        ),
        "escrow_code": _element_text(
            bill_table_row.select_one(".escrow")
        ),
        "millage_code": _element_text(
            bill_table_row.select_one(".millage")
        ),
        "balance_due_raw": _element_text(
            bill_table_row.select_one(".balance")
        ),
        "status": _element_text(
            bill_table_row.select_one(".emphasized-status")
        ),
    }

    parcel = soup.select_one(".content-group.details.parcel")
    if parcel is None:
        raise OrangeTaxSourceChanged(
            "Orange bill detail lacks the parcel details section"
        )
    owner = _element_text(parcel.select_one(".owners .owner"))
    owner_address = _element_text(
        parcel.select_one(".owners .address:not(.selected):not(.situs) .value")
    )
    situs = _element_text(parcel.select_one(".owners .situs .value"))
    account_details = _label_value_rows(
        parcel.select_one(".account-details")
    )
    parcel_values = _label_value_rows(parcel.select_one(".parcel-values"))
    bill_amounts = _label_value_rows(parcel.select_one(".bill-details"))
    location = _label_value_rows(parcel.select_one(".location"))
    legal = _element_text(
        parcel.select_one("#truncated-legal-description")
    )
    exemptions: list[dict[str, Any]] = []
    exemption_container = parcel.select_one(".exemptions")
    if exemption_container is not None:
        for row in exemption_container.select(".row"):
            label = _element_text(row.select_one(".label"))
            value = _element_text(row.select_one(".value"))
            if label is None or value is None:
                continue
            exemptions.append(
                {
                    "label": label,
                    "amount_raw": value,
                    "amount_decimal": _money_decimal(value),
                    "currency": "USD",
                }
            )

    ad_valorem: list[dict[str, Any]] = []
    for row in soup.select(".advalorem tbody.taxing-authority tr"):
        name = _element_text(row.select_one(".name"))
        if name is None:
            continue
        ad_valorem.append(
            {
                "taxing_authority": name,
                "millage": _element_text(row.select_one(".millage")),
                "assessed_raw": _element_text(row.select_one(".assessed")),
                "assessed_decimal": _money_decimal(
                    _element_text(row.select_one(".assessed"))
                ),
                "exemption_raw": _element_text(
                    row.select_one(".exemption")
                ),
                "exemption_decimal": _money_decimal(
                    _element_text(row.select_one(".exemption"))
                ),
                "taxable_raw": _element_text(row.select_one(".taxable")),
                "taxable_decimal": _money_decimal(
                    _element_text(row.select_one(".taxable"))
                ),
                "tax_raw": _element_text(row.select_one(".tax")),
                "tax_decimal": _money_decimal(
                    _element_text(row.select_one(".tax"))
                ),
                "currency": "USD",
            }
        )
    ad_total_row = soup.select_one(".advalorem tfoot tr")
    ad_total = {
        "millage": _element_text(
            ad_total_row.select_one(".millage")
            if ad_total_row
            else None
        ),
        "tax_raw": _element_text(
            ad_total_row.select_one(".tax") if ad_total_row else None
        ),
    }
    ad_total["tax_decimal"] = _money_decimal(ad_total["tax_raw"])

    non_ad_valorem: list[dict[str, Any]] = []
    for row in soup.select(".nonadvalorem tbody tr"):
        authority = _element_text(
            row.select_one(".levying-authority")
            or row.select_one(".name")
        )
        amount = _element_text(row.select_one(".amount"))
        if authority is None and amount is None:
            continue
        non_ad_valorem.append(
            {
                "levying_authority": authority,
                "rate": _element_text(row.select_one(".rate")),
                "amount_raw": amount,
                "amount_decimal": _money_decimal(amount),
                "currency": "USD",
            }
        )
    non_ad_empty = _element_text(
        soup.select_one(".nonadvalorem .no-taxes")
    )
    ocpa_link = soup.find(
        "a",
        href=lambda value: bool(
            value and "ocpafl.org" in str(value).casefold()
        ),
    )
    document_sha = hashlib.sha256(html.encode("utf-8")).hexdigest()
    contract = {
        "bill_heading": bill_heading,
        "account_detail_labels": sorted(account_details),
        "parcel_value_labels": sorted(parcel_values),
        "bill_amount_labels": sorted(bill_amounts),
        "location_labels": sorted(location),
        "ad_valorem_columns": [
            "taxing_authority",
            "millage",
            "assessed",
            "exemption",
            "taxable",
            "tax",
        ],
        "non_ad_valorem_empty_label": non_ad_empty,
    }
    return {
        "source_id": SOURCE_ID,
        "record_kind": "property_tax_bill_detail",
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "tax-bill",
            normalized_bill,
        ),
        "parcel_join": {
            "normalized_15_digit_account": account,
            "formatted_account": format_account(account),
            "exact": True,
        },
        "native_account_id": account_details.get("account")
        or format_account(account),
        "taxsys_parent_semantic_id": semantic_id,
        "taxsys_parent_uuid": _native_parent_uuid(semantic_id),
        "taxsys_account_token": account_token,
        "bill_uuid": normalized_bill,
        "tax_year": tax_year,
        "bill_label": bill_heading,
        "alternate_key": summary["alternate_key"]
        or account_details.get("alternate key"),
        "escrow_code": summary["escrow_code"],
        "millage": {
            "code": summary["millage_code"]
            or account_details.get("millage code"),
            "rate": account_details.get("millage rate"),
        },
        "amount_due": {
            "raw": summary["balance_due_raw"],
            "decimal": _money_decimal(summary["balance_due_raw"]),
            "currency": "USD",
            "retrieved_state": True,
        },
        "status": {
            "raw": summary["status"],
            "retrieved_state": True,
        },
        "owners": (
            [
                {
                    "raw_name": owner,
                    "role": "published_tax_account_owner",
                    "assertion_type": "tax_account_owner_label",
                    "title_caveat": "not_a_title_chain",
                }
            ]
            if owner
            else []
        ),
        "mailing_address": {
            "raw": owner_address,
            "source_role": "tax_account_owner_address",
        },
        "situs_address": {
            "raw": situs,
            "source_role": "published_situs",
        },
        "property_appraiser_url": (
            str(ocpa_link.get("href")) if ocpa_link is not None else None
        ),
        "parcel_values": {
            key.replace(" ", "_"): {
                "raw": value,
                "decimal": _money_decimal(value),
                "currency": "USD",
            }
            for key, value in parcel_values.items()
        },
        "tax_amounts": {
            key.replace(" ", "_"): {
                "raw": value,
                "decimal": _money_decimal(value),
                "currency": "USD",
            }
            for key, value in bill_amounts.items()
        },
        "ad_valorem": {
            "rows": ad_valorem,
            "total": {
                **ad_total,
                "currency": "USD",
            },
        },
        "non_ad_valorem": {
            "rows": non_ad_valorem,
            "empty_message": non_ad_empty,
        },
        "exemptions": exemptions,
        "legal_description_raw": legal,
        "location": {
            key.replace(" ", "_"): value
            for key, value in location.items()
        },
        "source_document_url": source_url,
        "source_document_sha256": document_sha,
        "response_contract_fingerprint": _document_fingerprint(
            html,
            contract,
        ),
        "print_pdf_url": matching_links[0],
    }


def parse_bulk_landing_page(html: str) -> dict[str, Any]:
    """Validate the four publisher links and return their observed labels."""

    soup = BeautifulSoup(html, "html.parser")
    expected = {
        Path(urlsplit(CURRENT_LAYOUT_URL).path).name: CURRENT_LAYOUT_URL,
        Path(urlsplit(CURRENT_ROLL_URL).path).name: CURRENT_ROLL_URL,
        Path(urlsplit(DELINQUENT_LAYOUT_URL).path).name: (
            DELINQUENT_LAYOUT_URL
        ),
        Path(urlsplit(DELINQUENT_ROLL_URL).path).name: (
            DELINQUENT_ROLL_URL
        ),
    }
    found: dict[str, dict[str, Any]] = {}
    for link in soup.find_all("a", href=True):
        absolute = urljoin(OFFICIAL_TAX_ROLL_PAGE, str(link.get("href")))
        filename = Path(urlsplit(absolute).path).name
        if filename not in expected:
            continue
        found[filename] = {
            "url": absolute,
            "label": _element_text(link),
        }
    if set(found) != set(expected):
        raise OrangeTaxSourceChanged(
            "Orange bulk page no longer links all recognized artifacts",
            details={
                "expected": sorted(expected),
                "found": sorted(found),
            },
        )
    for filename, expected_url in expected.items():
        if found[filename]["url"] != expected_url:
            raise OrangeTaxSourceChanged(
                "Orange bulk artifact URL changed",
                details={
                    "filename": filename,
                    "expected_url": expected_url,
                    "observed_url": found[filename]["url"],
                },
            )
    labels = " ".join(
        str(item["label"] or "") for item in found.values()
    )
    dates = sorted(
        {
            match.group(0)
            for match in re.finditer(r"\b\d{2}/\d{2}/\d{2}\b", labels)
        }
    )
    return {
        "source_id": SOURCE_ID,
        "record_kind": "historical_bulk_landing_observation",
        "official_page": OFFICIAL_TAX_ROLL_PAGE,
        "artifacts": found,
        "label_dates": dates,
        "publication_state": "fixed_historical_snapshot",
        "page_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
    }


def historical_bulk_manifest() -> list[dict[str, Any]]:
    return [
        publication.manifest().to_dict()
        for publication in BULK_PUBLICATIONS.values()
    ]


def _bulk_member_reader(
    artifact: Path | str,
    publication: BulkPublication,
) -> tuple[Any, zipfile.ZipFile, io.TextIOWrapper, csv.reader]:
    path = Path(artifact).expanduser()
    if not path.is_file():
        raise OrangeTaxQueryError(
            "bulk artifact is not a file",
            details={"artifact": str(path)},
        )
    archive_inspection = inspect_zip(path)
    file_members = [
        member
        for member in archive_inspection.members
        if member.get("kind") == "file"
    ]
    if (
        len(file_members) != 1
        or file_members[0].get("path") != publication.member_name
    ):
        raise OrangeTaxSourceChanged(
            "Orange bulk ZIP no longer has its single expected member",
            details={
                "dataset": publication.dataset,
                "expected_member": publication.member_name,
                "observed_members": [
                    member.get("path") for member in file_members
                ],
            },
        )
    archive = zipfile.ZipFile(path)
    try:
        binary = archive.open(publication.member_name)
        text = io.TextIOWrapper(
            binary,
            encoding="utf-8-sig",
            errors="strict",
            newline="",
        )
        old_limit = csv.field_size_limit()
        csv.field_size_limit(MAX_CSV_FIELD_BYTES)
        reader = csv.reader(text)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise OrangeTaxSourceChanged(
                "Orange bulk member is empty",
                details={"dataset": publication.dataset},
            ) from exc
        finally:
            csv.field_size_limit(old_limit)
        if tuple(header) != publication.headers:
            raise OrangeTaxSourceChanged(
                "Orange bulk CSV header changed",
                details={
                    "dataset": publication.dataset,
                    "expected_headers": list(publication.headers),
                    "observed_headers": header,
                },
            )
        return archive_inspection, archive, text, reader
    except Exception:
        archive.close()
        raise


def inspect_bulk_artifact(
    artifact: Path | str,
    *,
    dataset: str,
) -> dict[str, Any]:
    """Validate one local ZIP and stream every row for structural counts."""

    publication = _publication(dataset)
    inspection, archive, text, reader = _bulk_member_reader(
        artifact,
        publication,
    )
    row_count = 0
    tax_years: dict[str, int] = {}
    malformed_accounts = 0
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    try:
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(publication.headers):
                raise OrangeTaxSourceChanged(
                    "Orange bulk row field count changed",
                    details={
                        "dataset": dataset,
                        "row_number": row_number,
                        "expected_field_count": len(
                            publication.headers
                        ),
                        "observed_field_count": len(row),
                    },
                )
            row_count += 1
            fields = dict(zip(publication.headers, row))
            account_field = (
                "ParcelNumber"
                if dataset == "current"
                else "Parcel No"
            )
            if _optional_account(fields[account_field]) is None:
                malformed_accounts += 1
            year_field = "TaxYear" if dataset == "current" else "Tax Year"
            year = _clean_text(fields[year_field])
            if year:
                tax_years[year] = tax_years.get(year, 0) + 1
    except UnicodeDecodeError as exc:
        raise OrangeTaxSourceChanged(
            "Orange bulk member is no longer valid UTF-8/ASCII text",
            details={"dataset": dataset},
        ) from exc
    finally:
        csv.field_size_limit(old_limit)
        text.close()
        archive.close()

    return {
        "source_id": SOURCE_ID,
        "record_kind": "historical_bulk_artifact_inspection",
        "dataset": dataset,
        "publication_date": PUBLICATION_DATE,
        "publication_state": "fixed_historical_snapshot",
        "artifact_path": str(Path(artifact).expanduser().resolve()),
        "artifact_sha256": inspection.archive_sha256,
        "artifact_size": inspection.archive_size,
        "matches_observed_artifact": (
            inspection.archive_sha256
            == publication.observed_data_sha256
        ),
        "archive": inspection.to_dict(),
        "member_name": publication.member_name,
        "row_count": row_count,
        "malformed_or_blank_parcel_accounts": malformed_accounts,
        "tax_year_counts": dict(sorted(tax_years.items())),
        "schema": publication.schema,
        "schema_fingerprint": publication.schema_fingerprint,
        "observed_2020_artifact": {
            "sha256": publication.observed_data_sha256,
            "size": publication.observed_data_size,
            "row_count": publication.observed_data_row_count,
        },
    }


@dataclass(frozen=True)
class BulkSearchCriteria:
    query: str | None = None
    account: str | None = None
    owner: str | None = None
    tax_year: int | None = None
    certificate: str | None = None
    tax_summary_id: str | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "query",
            "owner",
            "certificate",
            "tax_summary_id",
            "status",
        ):
            value = getattr(self, field_name)
            if value is not None:
                cleaned = value.strip()
                if not cleaned:
                    raise OrangeTaxQueryError(
                        f"{field_name} selector must not be empty"
                    )
                object.__setattr__(self, field_name, cleaned)
        if self.account is not None:
            object.__setattr__(
                self,
                "account",
                normalize_account(self.account),
            )
        if self.tax_year is not None and (
            isinstance(self.tax_year, bool)
            or self.tax_year < 1000
            or self.tax_year > 9999
        ):
            raise OrangeTaxQueryError(
                "tax year must be a four-digit integer"
            )
        if not any(
            (
                self.query,
                self.account,
                self.owner,
                self.tax_year,
                self.certificate,
                self.tax_summary_id,
                self.status,
            )
        ):
            raise OrangeTaxQueryError(
                "bulk search requires at least one selector"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "account": self.account,
            "owner": self.owner,
            "tax_year": self.tax_year,
            "certificate": self.certificate,
            "tax_summary_id": self.tax_summary_id,
            "status": self.status,
        }


def _bulk_matches(
    row: Mapping[str, str],
    *,
    dataset: str,
    criteria: BulkSearchCriteria,
) -> bool:
    if criteria.query is not None:
        needle = criteria.query.casefold()
        if not any(needle in value.casefold() for value in row.values()):
            return False
    if criteria.account is not None:
        raw = row["ParcelNumber" if dataset == "current" else "Parcel No"]
        if _optional_account(raw) != criteria.account:
            return False
    if criteria.owner is not None:
        fields = (
            ("OwnerName",)
            if dataset == "current"
            else tuple(f"Owner{index}" for index in range(1, 6))
        )
        needle = criteria.owner.casefold()
        if not any(needle in row[field].casefold() for field in fields):
            return False
    if criteria.tax_year is not None:
        field = "TaxYear" if dataset == "current" else "Tax Year"
        if _integer(row[field]) != criteria.tax_year:
            return False
    if criteria.certificate is not None:
        if dataset != "delinquent":
            return False
        if row["Cert No"].casefold() != criteria.certificate.casefold():
            return False
    if criteria.tax_summary_id is not None:
        field = "TaxSummaryId" if dataset == "current" else "TaxSummaryID"
        if row[field].casefold() != criteria.tax_summary_id.casefold():
            return False
    if criteria.status is not None:
        fields = (
            ("StatusCode",)
            if dataset == "current"
            else (
                "Status Code",
                "Tax Deed Status",
                "Payment Code",
            )
        )
        needle = criteria.status.casefold()
        if not any(needle in row[field].casefold() for field in fields):
            return False
    return True


def _owner_observations(
    values: Sequence[str],
    *,
    role: str = "published_tax_account_owner",
) -> list[dict[str, Any]]:
    return [
        {
            "raw_name": value,
            "role": role,
            "assertion_type": "tax_roll_label",
            "title_caveat": "not_a_title_chain",
        }
        for value in (_clean_text(item) for item in values)
        if value is not None
    ]


def _bulk_occurrence(
    *,
    artifact_sha256: str,
    publication: BulkPublication,
    row_number: int,
) -> dict[str, Any]:
    payload = {
        "artifact_sha256": artifact_sha256,
        "archive_member_path": publication.member_name,
        "source_row_number": row_number,
    }
    return {
        **payload,
        "occurrence_id": sha256_fingerprint(payload),
    }


def _normalize_current_bulk_row(
    row: Mapping[str, str],
    *,
    publication: BulkPublication,
    artifact_sha256: str,
    row_number: int,
) -> dict[str, Any]:
    account = _optional_account(row["ParcelNumber"])
    occurrence = _bulk_occurrence(
        artifact_sha256=artifact_sha256,
        publication=publication,
        row_number=row_number,
    )
    tax_summary_id = _clean_text(row["TaxSummaryId"])
    legal = " ".join(
        value
        for value in (
            _clean_text(row[f"Legal{index}"]) for index in range(1, 6)
        )
        if value
    )
    mailing_lines = [
        value
        for value in (
            _clean_text(row[f"Address{index}"])
            for index in range(1, 6)
        )
        if value
    ]
    return {
        "source_id": SOURCE_ID,
        "record_kind": "historical_current_tax_roll_row",
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "bulk-row-occurrence",
            occurrence["occurrence_id"],
        ),
        "publication_date": PUBLICATION_DATE,
        "publication_state": "fixed_historical_snapshot",
        "parcel_join": (
            {
                "normalized_15_digit_account": account,
                "formatted_account": format_account(account),
                "exact": True,
            }
            if account
            else None
        ),
        "native_parcel_number": _clean_text(row["ParcelNumber"]),
        "folio_number": _clean_text(row["Folio"]),
        "tax_summary_id": tax_summary_id,
        "tax_year": _integer(row["TaxYear"]),
        "mill_code": _clean_text(row["MillCode"]),
        "city_code": _clean_text(row["CityCode"]),
        "status_code": _clean_text(row["StatusCode"]),
        "owners": _owner_observations([row["OwnerName"]]),
        "mailing_address": {
            "raw": ", ".join(mailing_lines) or None,
            "lines": mailing_lines,
            "source_role": "tax_roll_mailing_address",
        },
        "legal_description_raw": legal or None,
        "values": {
            field: {
                "raw": _clean_text(row[source_field]),
                "decimal": _money_decimal(row[source_field]),
                "currency": "USD",
            }
            for field, source_field in (
                ("total", "TotalValue"),
                ("exempt", "ExemptValue"),
                ("taxable", "TaxableValue"),
            )
        },
        "tax": {
            field: {
                "raw": _clean_text(row[source_field]),
                "decimal": _money_decimal(row[source_field]),
                "currency": "USD",
            }
            for field, source_field in (
                ("gross_due", "GrossTaxDue"),
                ("balance_due", "BalanceDue"),
                ("november_amount_due", "NovemberAmountDue"),
                ("amount_paid", "AmountPaid"),
            )
        },
        "payment": {
            "date": _date_value(row["DatePaid"], datetime_allowed=True),
            "validation_number": _clean_text(row["ValidationNumber"]),
            "paid_by_label": _clean_text(row["PaidBy"]),
        },
        "flags": {
            field: _boolean(row[source_field])
            for field, source_field in (
                ("installment", "IsInstallment"),
                ("delinquent", "IsDelinquent"),
                ("bankrupt", "IsBankrupt"),
                ("litigation_pending", "IsLitigationPending"),
                ("florida_taking", "IsFloridaTaking"),
                ("leasehold", "IsLeasehold"),
            )
        },
        "identity_contract": {
            "parcel_join": (
                "normalized_15_digit_account" if account else None
            ),
            "tax_summary_id": tax_summary_id,
            "payment_validation_number": _clean_text(
                row["ValidationNumber"]
            ),
            "row_occurrence": occurrence,
        },
        "raw": dict(row),
    }


def _normalize_delinquent_bulk_row(
    row: Mapping[str, str],
    *,
    publication: BulkPublication,
    artifact_sha256: str,
    row_number: int,
) -> dict[str, Any]:
    account = _optional_account(row["Parcel No"])
    occurrence = _bulk_occurrence(
        artifact_sha256=artifact_sha256,
        publication=publication,
        row_number=row_number,
    )
    owner_values = [row[f"Owner{index}"] for index in range(1, 6)]
    mailing_lines = [
        value
        for value in (
            _clean_text(row[f"MailingAddress{index}"])
            for index in range(1, 6)
        )
        if value
    ]
    buyer_values = [row["Buyer Name1"], row["Buyer Name2"]]
    situs_parts = [
        value
        for value in (
            _clean_text(row["Situs Street Number"]),
            _clean_text(row["Situs Street Direction"]),
            _clean_text(row["Situs Street Name"]),
            _clean_text(row["Situs Street Type"]),
            _clean_text(row["Situs Suite"]),
            _clean_text(row["Situs City"]),
            _clean_text(row["Situs ZipCode"]),
        )
        if value
    ]
    tax_summary_id = _clean_text(row["TaxSummaryID"])
    certificate_identity = {
        "year": _integer(row["Cert Year"]),
        "number": _clean_text(row["Cert No"]),
        "sequence": _integer(row["Cert Seq"]),
    }
    tax_deed_identity = {
        "year": _integer(row["Tax Deed Year"]),
        "number": _clean_text(row["Tax Deed No"]),
        "sequence": _integer(row["Tax Deed Seq"]),
    }
    return {
        "source_id": SOURCE_ID,
        "record_kind": "historical_delinquent_tax_roll_row",
        "canonical_ref": canonical_property_ref(
            SOURCE_ID,
            COUNTY_GEOID,
            "bulk-row-occurrence",
            occurrence["occurrence_id"],
        ),
        "publication_date": PUBLICATION_DATE,
        "publication_state": "fixed_historical_snapshot",
        "parcel_join": (
            {
                "normalized_15_digit_account": account,
                "formatted_account": format_account(account),
                "exact": True,
            }
            if account
            else None
        ),
        "native_parcel_number": _clean_text(row["Parcel No"]),
        "tax_summary_id": tax_summary_id,
        "tax_year": _integer(row["Tax Year"]),
        "status_code": _clean_text(row["Status Code"]),
        "tax_deed_status": _clean_text(row["Tax Deed Status"]),
        "owners": _owner_observations(owner_values),
        "buyers": _owner_observations(
            buyer_values,
            role="published_certificate_buyer_label",
        ),
        "mailing_address": {
            "raw": ", ".join(mailing_lines) or None,
            "lines": mailing_lines,
            "source_role": "tax_roll_mailing_address",
        },
        "situs_address": {
            "raw": " ".join(situs_parts) or None,
            "source_role": "published_situs",
        },
        "legal_description_raw": _clean_text(row["Legal Description"]),
        "certificate": {
            **certificate_identity,
            "face_value": {
                "raw": _clean_text(row["Certificate Face Value"]),
                "decimal": _money_decimal(row["Certificate Face Value"]),
                "currency": "USD",
            },
            "issue_date": _date_value(row["Cert Issue Date"]),
            "purchase_date": _date_value(row["Cert Purchase Date"]),
            "bidder_number": _clean_text(row["Bidder Number"]),
        },
        "tax_deed": {
            **tax_deed_identity,
            "status": _clean_text(row["Tax Deed Status"]),
            "application_date": _date_value(
                row["Tax Deed Application Date"]
            ),
            "redemption_date": _date_value(
                row["Tax Deed Redemption Date"]
            ),
        },
        "values": {
            field: {
                "raw": _clean_text(row[source_field]),
                "decimal": _money_decimal(row[source_field]),
                "currency": "USD",
            }
            for field, source_field in (
                ("total", "Total Value"),
                ("exempt", "Exempt Value"),
                ("taxable", "Taxable Value"),
            )
        },
        "tax": {
            field: {
                "raw": _clean_text(row[source_field]),
                "decimal": _money_decimal(row[source_field]),
                "currency": "USD",
            }
            for field, source_field in (
                ("gross", "Gross Taxes"),
                ("payoff_due", "Payoff Amount Due"),
                ("payoff_interest", "Payoff Interest"),
                (
                    "payoff_due_next_month",
                    "Payoff Amount Due Next Month",
                ),
                (
                    "payoff_interest_next_month",
                    "Payoff Interest Next Month",
                ),
            )
        },
        "payment": {
            "payoff_date": _date_value(row["Payoff Date"]),
            "payment_date": _date_value(row["Payment Date"]),
            "payment_code": _clean_text(row["Payment Code"]),
            "validation_number": _clean_text(row["Validation No"]),
        },
        "property_use_code": _clean_text(row["Property Use Code"]),
        "identity_contract": {
            "parcel_join": (
                "normalized_15_digit_account" if account else None
            ),
            "certificate": certificate_identity,
            "tax_deed": tax_deed_identity,
            "tax_summary_id": tax_summary_id,
            "payment_validation_number": _clean_text(
                row["Validation No"]
            ),
            "row_occurrence": occurrence,
        },
        "raw": dict(row),
    }


def _bulk_cursor(
    *,
    publication: BulkPublication,
    criteria: BulkSearchCriteria,
    artifact_sha256: str,
    row_number: int,
) -> str:
    payload = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "dataset": publication.dataset,
        "criteria_fingerprint": sha256_fingerprint(criteria.to_dict()),
        "artifact_sha256": artifact_sha256,
        "schema_fingerprint": publication.schema_fingerprint,
        "row_number": row_number,
    }
    return BULK_CURSOR_PREFIX + _urlsafe_encode(canonical_json(payload))


def _parse_bulk_cursor(
    cursor: str | None,
    *,
    publication: BulkPublication,
    criteria: BulkSearchCriteria,
    artifact_sha256: str,
) -> int:
    if cursor is None:
        return 2
    if not cursor.startswith(BULK_CURSOR_PREFIX):
        raise OrangeTaxQueryError(
            "bulk cursor is not an Orange Tax Collector continuation",
            code="orange_tax_bulk_cursor_invalid",
        )
    try:
        payload = json.loads(
            _urlsafe_decode(cursor[len(BULK_CURSOR_PREFIX) :])
        )
    except (json.JSONDecodeError, OrangeTaxQueryError) as exc:
        raise OrangeTaxQueryError(
            "bulk cursor payload is invalid",
            code="orange_tax_bulk_cursor_invalid",
        ) from exc
    expected = {
        "version": CURSOR_VERSION,
        "source_id": SOURCE_ID,
        "dataset": publication.dataset,
        "criteria_fingerprint": sha256_fingerprint(criteria.to_dict()),
        "artifact_sha256": artifact_sha256,
        "schema_fingerprint": publication.schema_fingerprint,
    }
    if not isinstance(payload, Mapping) or any(
        payload.get(key) != value for key, value in expected.items()
    ):
        raise OrangeTaxQueryError(
            "bulk cursor belongs to different criteria, artifact, or schema",
            code="orange_tax_bulk_cursor_mismatch",
            details={"expected": expected},
        )
    row_number = payload.get("row_number")
    if (
        isinstance(row_number, bool)
        or not isinstance(row_number, int)
        or row_number < 2
    ):
        raise OrangeTaxQueryError(
            "bulk cursor row is invalid",
            code="orange_tax_bulk_cursor_invalid",
        )
    return row_number


def search_bulk_artifact(
    artifact: Path | str,
    *,
    dataset: str,
    criteria: BulkSearchCriteria,
    limit: int | None = None,
    cursor: str | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    """Stream matching CSV rows without loading the publication into memory."""

    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0
    ):
        raise OrangeTaxQueryError("bulk search limit must be positive")
    publication = _publication(dataset)
    inspection, archive, text, reader = _bulk_member_reader(
        artifact,
        publication,
    )
    start_row = _parse_bulk_cursor(
        cursor,
        publication=publication,
        criteria=criteria,
        artifact_sha256=inspection.archive_sha256,
    )
    records: list[dict[str, Any]] = []
    next_cursor: str | None = None
    old_limit = csv.field_size_limit()
    csv.field_size_limit(MAX_CSV_FIELD_BYTES)
    try:
        for row_number, values in enumerate(reader, start=2):
            if len(values) != len(publication.headers):
                raise OrangeTaxSourceChanged(
                    "Orange bulk row field count changed",
                    details={
                        "dataset": dataset,
                        "row_number": row_number,
                        "expected_field_count": len(
                            publication.headers
                        ),
                        "observed_field_count": len(values),
                    },
                )
            if row_number < start_row:
                continue
            row = dict(zip(publication.headers, values))
            if not _bulk_matches(
                row,
                dataset=dataset,
                criteria=criteria,
            ):
                continue
            if limit is not None and len(records) >= limit:
                next_cursor = _bulk_cursor(
                    publication=publication,
                    criteria=criteria,
                    artifact_sha256=inspection.archive_sha256,
                    row_number=row_number,
                )
                break
            normalizer = (
                _normalize_current_bulk_row
                if dataset == "current"
                else _normalize_delinquent_bulk_row
            )
            records.append(
                normalizer(
                    row,
                    publication=publication,
                    artifact_sha256=inspection.archive_sha256,
                    row_number=row_number,
                )
            )
    except UnicodeDecodeError as exc:
        raise OrangeTaxSourceChanged(
            "Orange bulk member is no longer valid UTF-8/ASCII text",
            details={"dataset": dataset},
        ) from exc
    finally:
        csv.field_size_limit(old_limit)
        text.close()
        archive.close()
    metadata = {
        "dataset": dataset,
        "artifact_sha256": inspection.archive_sha256,
        "archive_member_path": publication.member_name,
        "schema_fingerprint": publication.schema_fingerprint,
        "matches_observed_artifact": (
            inspection.archive_sha256
            == publication.observed_data_sha256
        ),
    }
    return records, next_cursor, metadata


def _query(
    operation: str,
    parameters: Mapping[str, Any],
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> PublicRecordsQuery:
    return PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(
            operation=operation,
            parameters=parameters,
            requested_limit=limit,
            cursor=cursor,
            metadata={"adapter_schema_version": OUTPUT_SCHEMA_VERSION},
        ),
    )


def _client(args: argparse.Namespace) -> OrangeTaxPortalClient:
    try:
        return OrangeTaxPortalClient(
            timeout=args.timeout,
            retry_policy=RetryPolicy(max_attempts=args.retry_attempts),
            minimum_interval=args.minimum_interval,
        )
    except ValueError as exc:
        raise OrangeTaxQueryError(
            f"invalid portal transport configuration: {exc}"
        ) from exc


def _bulk_client(args: argparse.Namespace) -> BulkTransferClient:
    try:
        return BulkTransferClient(
            timeout=args.timeout,
            max_attempts=args.retry_attempts,
            chunk_size=args.chunk_size,
            user_agent=USER_AGENT,
        )
    except ValueError as exc:
        raise OrangeTaxQueryError(
            f"invalid bulk transport configuration: {exc}"
        ) from exc


def _resolve_token(
    client: OrangeTaxPortalClient,
    account_or_token: str,
) -> tuple[str, str | None, dict[str, Any] | None]:
    try:
        account = normalize_account(account_or_token)
    except OrangeTaxQueryError:
        validate_account_token(account_or_token)
        return account_or_token, None, None
    hit = client.resolve_account(account)
    return str(hit["taxsys_account_token"]), account, hit


def execute(
    args: argparse.Namespace,
    *,
    portal_client: OrangeTaxPortalClient | None = None,
    bulk_client: BulkTransferClient | None = None,
) -> PublicRecordsResult:
    """Execute a parsed CLI namespace and return the shared result envelope."""

    operation = args.command
    parameters: dict[str, Any] = {}
    requested_limit = getattr(args, "limit", None)
    cursor = getattr(args, "cursor", None)
    query = _query(
        operation,
        parameters,
        limit=requested_limit,
        cursor=cursor,
    )
    try:
        if operation == "sources":
            records = [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "source_capability",
                    "current_portal": {
                        "search": True,
                        "account_resolution": True,
                        "bill_history": True,
                        "bill_detail": True,
                        "algolia_index": ALGOLIA_INDEX,
                        "hits_per_page": ALGOLIA_HITS_PER_PAGE,
                        "taxsys_direct_root": TAXSYS_ROOT,
                        "taxsys_embedded_root": EMBEDDED_TAXSYS_ROOT,
                    },
                    "historical_bulk": {
                        "manifest": True,
                        "probe": True,
                        "resumable_download": True,
                        "local_inspect": True,
                        "local_stream_search": True,
                        "datasets": ["current", "delinquent"],
                        "publication_date": PUBLICATION_DATE,
                        "publication_state": "fixed_historical_snapshot",
                    },
                    "identity_contract": {
                        "parcel_join": (
                            "exact normalized 15-digit account only"
                        ),
                        "portal_occurrence": "algolia_object_id",
                        "bill": "bill_uuid",
                        "certificate": "certificate_number",
                        "receipt": "receipt_number",
                        "bulk_row": [
                            "artifact_sha256",
                            "archive_member_path",
                            "source_row_number",
                        ],
                    },
                }
            ]
            query = _query(operation, {})
            return PublicRecordsResult.success(
                query,
                records,
                warnings=SOURCE_WARNINGS,
            )

        if operation == "search":
            parameters = {"query": args.query}
            query = _query(
                operation,
                parameters,
                limit=args.limit,
                cursor=args.cursor,
            )
            active_client = portal_client or _client(args)
            result = active_client.search(
                args.query,
                limit=args.limit,
                cursor=args.cursor,
            )
            records = list(result.records)
            for record in records:
                record["portal_search_metadata"] = {
                    "total_hits": result.total_hits,
                    "pages_fetched": result.pages_fetched,
                    "response_contract_fingerprints": list(
                        result.response_contract_fingerprints
                    ),
                }
            return PublicRecordsResult.success(
                query,
                records,
                next_cursor=result.next_cursor,
                raw_artifact_refs=(ALGOLIA_URL,),
                warnings=SOURCE_WARNINGS,
            )

        if operation in {"account", "history"}:
            parameters = {"account_or_token": args.account_or_token}
            query = _query(operation, parameters)
            active_client = portal_client or _client(args)
            token, account, hit = _resolve_token(
                active_client,
                args.account_or_token,
            )
            source_url, html = active_client.history_html(token)
            records = parse_bill_history_html(
                html,
                account_token=token,
                parcel_account=account,
                source_url=source_url,
            )
            if operation == "account" and hit is not None:
                records.insert(0, hit)
            return PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=(source_url,),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bill":
            parameters = {
                "account_or_token": args.account_or_token,
                "bill_uuid": args.bill_uuid,
            }
            query = _query(operation, parameters)
            active_client = portal_client or _client(args)
            token, account, _hit = _resolve_token(
                active_client,
                args.account_or_token,
            )
            source_url, html = active_client.bill_html(
                token,
                args.bill_uuid,
            )
            record = parse_bill_detail_html(
                html,
                account_token=token,
                bill_uuid=args.bill_uuid,
                source_url=source_url,
            )
            if (
                account is not None
                and record["parcel_join"][
                    "normalized_15_digit_account"
                ]
                != account
            ):
                raise OrangeTaxSourceChanged(
                    "resolved account and bill detail account do not match",
                    details={
                        "resolved_account": account,
                        "bill_account": record["parcel_join"][
                            "normalized_15_digit_account"
                        ],
                    },
                )
            return PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(source_url,),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bulk-manifest":
            parameters = {"verify_page": args.verify_page}
            query = _query(operation, parameters)
            records = [
                {
                    "source_id": SOURCE_ID,
                    "record_kind": "historical_bulk_manifest",
                    "manifest": manifest,
                }
                for manifest in historical_bulk_manifest()
            ]
            if args.verify_page:
                active_client = portal_client or _client(args)
                _source_url, html = active_client.bulk_landing_html()
                records.insert(0, parse_bulk_landing_page(html))
            return PublicRecordsResult.success(
                query,
                records,
                raw_artifact_refs=(OFFICIAL_TAX_ROLL_PAGE,),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bulk-probe":
            parameters = {
                "dataset": args.dataset,
                "artifact_role": args.artifact_role,
            }
            query = _query(operation, parameters)
            publication = _publication(args.dataset)
            artifact = publication.artifact(args.artifact_role)
            active_bulk = bulk_client or _bulk_client(args)
            if args.sample_bytes < 0:
                raise OrangeTaxQueryError(
                    "sample bytes must not be negative"
                )
            probe = active_bulk.probe(
                artifact,
                sample_bytes=args.sample_bytes,
            )
            if args.artifact_role == "data" and (
                probe.signature_hex is None
                or not probe.signature_hex.startswith("504b")
            ):
                raise OrangeTaxSourceChanged(
                    "Orange bulk data URL no longer has a ZIP signature",
                    details=probe.to_dict(),
                )
            record = {
                "source_id": SOURCE_ID,
                "record_kind": "historical_bulk_artifact_probe",
                "dataset": args.dataset,
                "artifact_role": args.artifact_role,
                "publication_date": PUBLICATION_DATE,
                "publication_state": "fixed_historical_snapshot",
                "probe": probe.to_dict(),
                "observed_artifact": dict(artifact.metadata),
                "content_length_matches_observed": (
                    probe.content_length
                    == artifact.metadata.get("observed_size")
                ),
            }
            return PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(artifact.url,),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bulk-download":
            parameters = {
                "dataset": args.dataset,
                "artifact_role": args.artifact_role,
                "destination": str(args.destination),
            }
            query = _query(operation, parameters)
            publication = _publication(args.dataset)
            if args.inspect and args.artifact_role != "data":
                raise OrangeTaxQueryError(
                    "--inspect applies only to the bulk data ZIP"
                )
            if (
                args.max_download_bytes is not None
                and args.max_download_bytes <= 0
            ):
                raise OrangeTaxQueryError(
                    "maximum download bytes must be positive"
                )
            artifact = publication.artifact(args.artifact_role)
            if args.expected_sha256:
                try:
                    artifact = BulkArtifact(
                        artifact_id=artifact.artifact_id,
                        url=artifact.url,
                        filename=artifact.filename,
                        media_type=artifact.media_type,
                        archive_format=artifact.archive_format,
                        expected_sha256=args.expected_sha256,
                        metadata=dict(artifact.metadata),
                    )
                except ValueError as exc:
                    raise OrangeTaxQueryError(
                        f"invalid expected SHA-256: {exc}"
                    ) from exc
            active_bulk = bulk_client or _bulk_client(args)
            receipt = active_bulk.download(
                artifact,
                args.destination,
                resume=args.resume,
                max_bytes=args.max_download_bytes,
            )
            record: dict[str, Any] = {
                "source_id": SOURCE_ID,
                "record_kind": "historical_bulk_download_receipt",
                "dataset": args.dataset,
                "artifact_role": args.artifact_role,
                "publication_date": PUBLICATION_DATE,
                "publication_state": "fixed_historical_snapshot",
                "receipt": receipt.to_dict(),
                "matches_observed_artifact": (
                    receipt.sha256
                    == artifact.metadata.get("observed_sha256")
                ),
            }
            if args.inspect:
                record["inspection"] = inspect_bulk_artifact(
                    receipt.path,
                    dataset=args.dataset,
                )
            return PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(artifact.url, receipt.path),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bulk-inspect":
            parameters = {
                "dataset": args.dataset,
                "artifact": str(args.artifact),
            }
            query = _query(operation, parameters)
            record = inspect_bulk_artifact(
                args.artifact,
                dataset=args.dataset,
            )
            return PublicRecordsResult.success(
                query,
                [record],
                raw_artifact_refs=(str(args.artifact),),
                warnings=SOURCE_WARNINGS,
            )

        if operation == "bulk-search":
            criteria = BulkSearchCriteria(
                query=args.query,
                account=args.account,
                owner=args.owner,
                tax_year=args.tax_year,
                certificate=args.certificate,
                tax_summary_id=args.tax_summary_id,
                status=args.status,
            )
            parameters = {
                "dataset": args.dataset,
                "artifact": str(args.artifact),
                "criteria": criteria.to_dict(),
            }
            query = _query(
                operation,
                parameters,
                limit=args.limit,
                cursor=args.cursor,
            )
            records, next_cursor, metadata = search_bulk_artifact(
                args.artifact,
                dataset=args.dataset,
                criteria=criteria,
                limit=args.limit,
                cursor=args.cursor,
            )
            for record in records:
                record["bulk_search_metadata"] = metadata
            return PublicRecordsResult.success(
                query,
                records,
                next_cursor=next_cursor,
                raw_artifact_refs=(str(args.artifact),),
                warnings=SOURCE_WARNINGS,
            )

        raise OrangeTaxQueryError(
            "unknown Orange Tax Collector operation",
            details={"operation": operation},
        )
    except OrangeTaxQueryError as error:
        if error.status == ResultStatus.NO_RESULTS:
            return PublicRecordsResult.success(
                query,
                [],
                warnings=SOURCE_WARNINGS,
            )
        return PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except OrangeTaxError as error:
        return PublicRecordsResult.failure(
            query,
            error.status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )
    except BulkSourceError as error:
        return PublicRecordsResult.failure(
            query,
            error.result_status,
            [error.to_contract_error()],
            warnings=SOURCE_WARNINGS,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query Orange County Tax Collector current portal records and "
            "fixed historical bulk tax-roll snapshots"
        )
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP timeout in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--retry-attempts",
        type=int,
        default=DEFAULT_RETRY_ATTEMPTS,
        help="bounded HTTP attempt count (default: %(default)s)",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=0.25,
        help="minimum seconds between portal requests (default: %(default)s)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1024 * 1024,
        help="bulk download chunk size (default: %(default)s)",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="do not record portal searches in search_log",
    )
    add_output_args(parser)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser(
        "sources",
        help="show current-portal and historical-bulk capabilities",
    )
    add_output_args(sources)

    search = subparsers.add_parser(
        "search",
        help="search the current public GovHub index",
    )
    search.add_argument("query")
    search.add_argument(
        "--limit",
        type=int,
        default=ALGOLIA_HITS_PER_PAGE,
    )
    search.add_argument("--cursor")
    add_output_args(search)

    account = subparsers.add_parser(
        "account",
        help="resolve an exact account and fetch its bill history",
    )
    account.add_argument("account_or_token")
    add_output_args(account)

    history = subparsers.add_parser(
        "history",
        help="fetch bill/certificate history by account or account token",
    )
    history.add_argument("account_or_token")
    add_output_args(history)

    bill = subparsers.add_parser(
        "bill",
        help="fetch a full bill detail by account/token and bill UUID",
    )
    bill.add_argument("account_or_token")
    bill.add_argument("bill_uuid")
    add_output_args(bill)

    manifest = subparsers.add_parser(
        "bulk-manifest",
        help="show the two fixed historical bulk publication manifests",
    )
    manifest.add_argument(
        "--verify-page",
        action="store_true",
        help="also verify the four links on the official publication page",
    )
    add_output_args(manifest)

    probe = subparsers.add_parser(
        "bulk-probe",
        help="probe one official historical artifact",
    )
    probe.add_argument("dataset", choices=sorted(BULK_PUBLICATIONS))
    probe.add_argument(
        "--artifact-role",
        choices=("data", "layout"),
        default="data",
    )
    probe.add_argument("--sample-bytes", type=int, default=4096)
    add_output_args(probe)

    download = subparsers.add_parser(
        "bulk-download",
        help="download one official historical artifact",
    )
    download.add_argument("dataset", choices=sorted(BULK_PUBLICATIONS))
    download.add_argument("destination", type=Path)
    download.add_argument(
        "--artifact-role",
        choices=("data", "layout"),
        default="data",
    )
    download.add_argument("--expected-sha256")
    download.add_argument("--max-download-bytes", type=int)
    download.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    download.add_argument("--inspect", action="store_true")
    add_output_args(download)

    inspect_parser = subparsers.add_parser(
        "bulk-inspect",
        help="validate and count one local bulk ZIP",
    )
    inspect_parser.add_argument(
        "dataset",
        choices=sorted(BULK_PUBLICATIONS),
    )
    inspect_parser.add_argument("artifact", type=Path)
    add_output_args(inspect_parser)

    bulk_search = subparsers.add_parser(
        "bulk-search",
        help="stream-search one local historical bulk ZIP",
    )
    bulk_search.add_argument(
        "dataset",
        choices=sorted(BULK_PUBLICATIONS),
    )
    bulk_search.add_argument("artifact", type=Path)
    bulk_search.add_argument("--query")
    bulk_search.add_argument("--account")
    bulk_search.add_argument("--owner")
    bulk_search.add_argument("--tax-year", type=int)
    bulk_search.add_argument("--certificate")
    bulk_search.add_argument("--tax-summary-id")
    bulk_search.add_argument("--status")
    bulk_search.add_argument("--limit", type=int)
    bulk_search.add_argument("--cursor")
    add_output_args(bulk_search)
    return parser


def _log_if_needed(args: argparse.Namespace, result: PublicRecordsResult) -> None:
    if args.no_log or args.command not in {"search", "account", "history", "bill"}:
        return
    query_text = (
        getattr(args, "query", None)
        or getattr(args, "account_or_token", None)
        or ""
    )
    try:
        log_search(
            query_text=query_text,
            source=SOURCE_ID,
            result_count=len(result.records),
        )
    except (OSError, ValueError, TypeError) as exc:
        print(
            f"Warning: could not log Orange Tax Collector search: {exc}",
            file=sys.stderr,
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = execute(args)
    _log_if_needed(args, result)
    payload = result.to_dict()
    if write_output(
        payload,
        args,
        summary=f"Orange Tax Collector {args.command}",
        result_count=len(result.records),
    ):
        return 0 if not result.errors else 1
    print(json.dumps(payload, indent=2))
    return 0 if not result.errors else 1


if __name__ == "__main__":
    sys.exit(main())
