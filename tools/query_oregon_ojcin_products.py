#!/usr/bin/env python3
"""Describe and verify official Oregon statewide court-data products.

This adapter keeps five Oregon Judicial Department routes separately
attributable:

* OECI subscription access for circuit courts and the Tax Court;
* ACMS subscription access for the Supreme Court and Court of Appeals;
* the optional OJCIN standard report package;
* approved monthly or one-time bulk data transfers; and
* statewide data requests submitted to the Office of the State Court
  Administrator (OSCA).

OJD's public materials identify the products and acquisition routes but do not
publish a bulk or report delivery schema.  ``inspect-delivery`` therefore
creates a byte-level provenance receipt without interpreting delivery rows.

Examples:
    uv run python tools/query_oregon_ojcin_products.py products --json
    uv run python tools/query_oregon_ojcin_products.py search "judgment index" \
        --output /tmp/ojcin-products.json
    uv run python tools/query_oregon_ojcin_products.py handoff \
        us-or-ojcin-bulk-data-transfer --json
    uv run python tools/query_oregon_ojcin_products.py probe \
        --output /tmp/ojcin-probe.json
    uv run python tools/query_oregon_ojcin_products.py inspect-delivery \
        us-or-ojcin-bulk-data-transfer /path/to/acquired-delivery \
        --delivery-version 2026-07 --output /tmp/ojcin-receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import requests

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        SourceMetadata,
        sha256_fingerprint,
    )
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from public_records_contract import (
        JurisdictionMetadata,
        PublicRecordsQuery,
        PublicRecordsResult,
        QueryMetadata,
        SourceMetadata,
        sha256_fingerprint,
    )


SOURCE_ID = "us-or-ojd-statewide-court-data-products"
STATE_CODE = "OR"
STATE_GEOID = "41"
OUTPUT_SCHEMA_VERSION = "oregon-ojcin-products/1.0"
DELIVERY_RECEIPT_SCHEMA_VERSION = "oregon-ojcin-delivery-receipt/1.0"

USER_AGENT = "Ithildin-Public-Records/1.0"
DEFAULT_TIMEOUT = 45.0
DEFAULT_MINIMUM_INTERVAL = 0.2
DEFAULT_MAX_RETRIES = 2

OJCIN_URL = "https://www.courts.oregon.gov/services/online/pages/ojcin.aspx"
SIGNUP_URL = (
    "https://www.courts.oregon.gov/services/online/pages/ojcin-signup.aspx"
)
FEE_SCHEDULE_URL = (
    "https://www.courts.oregon.gov/forms/Documents/OJCINFeeSchedule.pdf"
)
CURRENT_CJO_URL = (
    "https://www.courts.oregon.gov/rules/Documents/CJO_2025-025.pdf"
)
TERMS_URL = (
    "https://www.courts.oregon.gov/forms/Documents/OJCINTermsofUse.pdf"
)
CUSTOMER_FORM_URL = (
    "https://www.courts.oregon.gov/forms/Documents/"
    "OJCIN_CustomerInformation_New_201005.pdf"
)
DOCUMENT_ACCESS_FORM_URL = (
    "https://www.courts.oregon.gov/forms/Documents/"
    "OJCINDocumentAccessRequest.pdf"
)
OECI_LOGIN_URL = (
    "https://publicaccess.courts.oregon.gov/PublicAccessLogin/Login.aspx"
    "?ReturnUrl=%2FPublicAccessLogin%2Fdefault.aspx"
)
ACMS_LOGIN_URL = "https://trportal.courts.oregon.gov/"
FREE_SEARCH_INFO_URL = (
    "https://www.courts.oregon.gov/services/online/Pages/"
    "records-calendars.aspx"
)
FREE_SEARCH_URL = "https://webportal.courts.oregon.gov/portal/"
RECORDS_REQUEST_URL = (
    "https://www.courts.oregon.gov/about/Pages/records-request.aspx"
)
CASE_COPY_REQUEST_URL = (
    "https://www.courts.oregon.gov/forms/Pages/records-request.aspx"
)
OSCA_REQUEST_PORTAL_URL = "https://courtsoregon.govqa.us/WEBAPP/_rs/"

CURRENT_FEE_EFFECTIVE_DATE = "2025-09-01"
OJCIN_CONTACT_EMAIL = "ojcin.online@ojd.state.or.us"
OJCIN_CONTACT_PHONE = "1-800-858-9658"
OSCA_MAILING_ADDRESS = (
    "Office of the State Court Administrator, Supreme Court Building, "
    "1163 State Street, Salem, OR 97301-2563"
)


class OJCINProductsError(RuntimeError):
    """Base error for OJCIN product discovery and delivery receipts."""


class DeliveryInspectionError(OJCINProductsError):
    """Raised when a user-acquired delivery cannot be inspected."""


@dataclass(frozen=True)
class Complement:
    """An official route that adds related records or another access path."""

    name: str
    url: str
    role: str
    adds: str
    observed_access: str
    documented_formats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "role": self.role,
            "adds": self.adds,
            "observed_access": self.observed_access,
            "documented_formats": list(self.documented_formats),
        }


@dataclass(frozen=True)
class OJCINProduct:
    """One separately attributable OJD product or delivery route."""

    source_id: str
    name: str
    source_role: str
    system: str
    acquisition_mode: str
    acquisition_url: str
    coverage: Mapping[str, Any]
    contents: tuple[str, ...]
    current_fees: Mapping[str, Any]
    acquisition: Mapping[str, Any]
    official_evidence: tuple[Mapping[str, str], ...]
    complements: tuple[Complement, ...] = ()
    delivery_schema_status: str = (
        "not_published_in_verified_official_materials"
    )

    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role=self.source_role,
            base_url=self.acquisition_url,
            dataset_id=self.source_id,
            metadata={
                "publisher": "Oregon Judicial Department",
                "state_code": STATE_CODE,
                "system": self.system,
                "acquisition_mode": self.acquisition_mode,
                "delivery_schema_status": self.delivery_schema_status,
            },
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "adapter_source_id": SOURCE_ID,
            "source": self.source_metadata().to_dict(),
            "jurisdiction": JURISDICTION.to_dict(),
            "product_id": self.source_id,
            "system": self.system,
            "acquisition_mode": self.acquisition_mode,
            "coverage": dict(self.coverage),
            "contents": list(self.contents),
            "current_fees": dict(self.current_fees),
            "fee_effective_date": CURRENT_FEE_EFFECTIVE_DATE,
            "acquisition": dict(self.acquisition),
            "delivery_schema": {
                "status": self.delivery_schema_status,
                "row_interpretation_available": False,
                "inspection_available": "byte_level_provenance_receipt",
            },
            "official_evidence": [dict(item) for item in self.official_evidence],
            "complements": [item.to_dict() for item in self.complements],
            "canonical_ref": f"OR-OJCIN-PRODUCT:{self.source_id}",
        }


JURISDICTION = JurisdictionMetadata(
    jurisdiction_id=STATE_GEOID,
    name="Oregon",
    state_code=STATE_CODE,
    metadata={"jurisdiction_level": "state"},
)

SOURCE_METADATA = SourceMetadata(
    source_id=SOURCE_ID,
    name="Oregon OJCIN and Statewide Court-Data Products",
    source_role="statewide_court_data_product_directory",
    base_url=OJCIN_URL,
    dataset_id="oregon-ojcin-products",
    metadata={
        "publisher": "Oregon Judicial Department",
        "state_code": STATE_CODE,
    },
)

FREE_SEARCH_COMPLEMENT = Complement(
    name="OJD free records and calendar search",
    url=FREE_SEARCH_INFO_URL,
    role="free_basic_case_and_calendar_discovery",
    adds=(
        "Basic case information and calendars for circuit, Tax, Court of "
        "Appeals, and Supreme Court matters; the official page links the "
        "interactive search."
    ),
    observed_access=(
        "The official information page is anonymously accessible. The "
        "interactive search is a browser-rendered route."
    ),
)

CASE_COPY_COMPLEMENT = Complement(
    name="OJD case record copy request",
    url=CASE_COPY_REQUEST_URL,
    role="separately_acquired_case_documents_and_audio",
    adds=(
        "Copies of identified Circuit, Tax, or appellate case documents and "
        "recordings from the court that holds the case record."
    ),
    observed_access=(
        "Request workflow asks for the case number and exact documents or "
        "hearing dates."
    ),
    documented_formats=("PDF", "TIFF", "paper"),
)

PUBLIC_KIOSK_COMPLEMENT = Complement(
    name="Oregon courthouse public access terminals",
    url=RECORDS_REQUEST_URL,
    role="on_premises_case_record_access",
    adds=(
        "Free access to Oregon eCourt records at public terminals in circuit "
        "courts, with local court copy routes for case documents."
    ),
    observed_access="On premises during the relevant court's public hours.",
)

OSCA_REQUEST_COMPLEMENT = Complement(
    name="OSCA statewide public records request",
    url=RECORDS_REQUEST_URL,
    role="custom_statewide_data_request",
    adds=(
        "Existing statewide court data and administrative records held by "
        "the Office of the State Court Administrator."
    ),
    observed_access="Online request portal or written request to OSCA.",
)

PRODUCTS: dict[str, OJCINProduct] = {
    "us-or-ojcin-oeci-subscription": OJCINProduct(
        source_id="us-or-ojcin-oeci-subscription",
        name="OJCIN OECI Circuit and Tax Court Subscription",
        source_role="circuit_and_tax_court_register_subscription",
        system="OECI",
        acquisition_mode="paid_subscription",
        acquisition_url=SIGNUP_URL,
        coverage={
            "courts": "all 36 Oregon circuit courts and Oregon Tax Court",
            "geography": "statewide",
            "update_observation": (
                "OJD describes OJCIN information as near real time and states "
                "that court staff update case information daily."
            ),
        },
        contents=(
            "case information",
            "Register of Actions",
            "judgment records",
            "civil cases",
            "small claims cases",
            "tax cases",
            "domestic cases",
            "criminal cases",
        ),
        current_fees={
            "setup_fee_usd": 170,
            "monthly_fee_varies_by_account_type": True,
            "fee_schedule_url": FEE_SCHEDULE_URL,
            "document_access": (
                "included or separately approved according to account type"
            ),
        },
        acquisition={
            "signup_url": SIGNUP_URL,
            "login_url": OECI_LOGIN_URL,
            "terms_url": TERMS_URL,
            "customer_form_url": CUSTOMER_FORM_URL,
            "document_access_form_url": DOCUMENT_ACCESS_FORM_URL,
            "contact_email": OJCIN_CONTACT_EMAIL,
            "contact_phone": OJCIN_CONTACT_PHONE,
        },
        official_evidence=(
            {
                "url": OJCIN_URL,
                "supports": "system scope, courts, records, update cadence",
            },
            {
                "url": SIGNUP_URL,
                "supports": "subscription and document-access handoff",
            },
            {
                "url": CURRENT_CJO_URL,
                "supports": "current fees and authorized document access",
            },
        ),
        complements=(
            FREE_SEARCH_COMPLEMENT,
            CASE_COPY_COMPLEMENT,
            PUBLIC_KIOSK_COMPLEMENT,
        ),
        delivery_schema_status="interactive_system_not_bulk_delivery_schema",
    ),
    "us-or-ojcin-acms-subscription": OJCINProduct(
        source_id="us-or-ojcin-acms-subscription",
        name="OJCIN ACMS Appellate Court Subscription",
        source_role="appellate_register_subscription",
        system="ACMS",
        acquisition_mode="paid_subscription",
        acquisition_url=SIGNUP_URL,
        coverage={
            "courts": "Oregon Supreme Court and Oregon Court of Appeals",
            "geography": "statewide",
        },
        contents=(
            "appellate case information",
            "appellate Register of Actions",
            "judgment records",
            "authorized appellate case documents",
        ),
        current_fees={
            "setup_fee_usd": 170,
            "monthly_fee_varies_by_account_type": True,
            "fee_schedule_url": FEE_SCHEDULE_URL,
            "document_access": (
                "included or separately approved according to account type"
            ),
        },
        acquisition={
            "signup_url": SIGNUP_URL,
            "login_url": ACMS_LOGIN_URL,
            "customer_form_acms_selection": (
                "The customer form asks whether an ACMS user ID is needed."
            ),
            "customer_form_url": CUSTOMER_FORM_URL,
            "contact_email": OJCIN_CONTACT_EMAIL,
            "contact_phone": OJCIN_CONTACT_PHONE,
        },
        official_evidence=(
            {
                "url": OJCIN_URL,
                "supports": "ACMS identity and appellate court coverage",
            },
            {
                "url": CUSTOMER_FORM_URL,
                "supports": "ACMS user-ID request field",
            },
            {
                "url": CURRENT_CJO_URL,
                "supports": "subscription includes ACMS public information",
            },
        ),
        complements=(FREE_SEARCH_COMPLEMENT, CASE_COPY_COMPLEMENT),
        delivery_schema_status="interactive_system_not_bulk_delivery_schema",
    ),
    "us-or-ojcin-standard-report-package": OJCINProduct(
        source_id="us-or-ojcin-standard-report-package",
        name="OJCIN Standard Report Package",
        source_role="subscription_index_report_package",
        system="OJCIN report package",
        acquisition_mode="subscription_add_on",
        acquisition_url=OJCIN_URL,
        coverage={
            "courts": (
                "OJCIN statewide systems; the public order does not specify "
                "a narrower court list for the report package"
            ),
            "official_labels": (
                "optional report package",
                "Daily Reports",
            ),
            "frequency_observation": (
                "The fee schedule labels these Daily Reports; the current "
                "order identifies the package components."
            ),
        },
        contents=(
            "criminal judgment index",
            "civil judgment index",
            "case index",
        ),
        current_fees={
            "monthly_add_on_usd": 29,
            "fee_schedule_url": FEE_SCHEDULE_URL,
        },
        acquisition={
            "contact_email": OJCIN_CONTACT_EMAIL,
            "contact_phone": OJCIN_CONTACT_PHONE,
            "subscription_url": SIGNUP_URL,
            "order_url": CURRENT_CJO_URL,
        },
        official_evidence=(
            {
                "url": CURRENT_CJO_URL,
                "supports": "three report components and current monthly fee",
            },
            {
                "url": FEE_SCHEDULE_URL,
                "supports": "current daily-report fee listing",
            },
        ),
        complements=(OSCA_REQUEST_COMPLEMENT,),
    ),
    "us-or-ojcin-bulk-data-transfer": OJCINProduct(
        source_id="us-or-ojcin-bulk-data-transfer",
        name="OJCIN Approved Bulk Data Transfer",
        source_role="approved_statewide_court_bulk_delivery",
        system="OJCIN bulk data",
        acquisition_mode="application_agreement_and_subscription",
        acquisition_url=OJCIN_URL,
        coverage={
            "account_types": ("approved monthly", "approved one-time"),
            "monthly_add_on": (
                "OJD states that data-reseller subscriptions may add monthly "
                "bulk data downloads after approval and agreement."
            ),
            "ojcin_system_context": (
                "OJCIN contains OECI and ACMS; the public order does not "
                "enumerate the fields or court scope of an approved bulk "
                "delivery."
            ),
            "delivery_scope": (
                "established by OJD approval and the executed transfer "
                "agreement"
            ),
        },
        contents=(
            "approved OJD bulk data delivery",
            "delivery scope established by the executed agreement",
        ),
        current_fees={
            "initial_bulk_administrative_fee_usd": 1200,
            "monthly_bulk_add_on_usd": 575,
            "data_reseller_base_monthly_usd": 1750,
            "fee_schedule_url": FEE_SCHEDULE_URL,
        },
        acquisition={
            "required_official_steps": (
                "OJD approval",
                "executed Bulk Data Transfer Agreement",
                "applicable OJCIN account setup",
            ),
            "contact_email": OJCIN_CONTACT_EMAIL,
            "contact_phone": OJCIN_CONTACT_PHONE,
            "signup_url": SIGNUP_URL,
            "terms_url": TERMS_URL,
            "current_order_url": CURRENT_CJO_URL,
        },
        official_evidence=(
            {
                "url": CURRENT_CJO_URL,
                "supports": (
                    "monthly downloads, one-time accounts, approval, "
                    "agreement, and current fees"
                ),
            },
            {
                "url": FEE_SCHEDULE_URL,
                "supports": "bulk add-on and administrative fees",
            },
            {
                "url": TERMS_URL,
                "supports": "OJCIN account and data-reseller terms",
            },
        ),
        complements=(OSCA_REQUEST_COMPLEMENT, CASE_COPY_COMPLEMENT),
    ),
    "us-or-osca-statewide-court-data-request": OJCINProduct(
        source_id="us-or-osca-statewide-court-data-request",
        name="OSCA Statewide Court Data Request",
        source_role="statewide_court_data_public_records_request",
        system="OSCA public records",
        acquisition_mode="public_records_request",
        acquisition_url=RECORDS_REQUEST_URL,
        coverage={
            "custodian": "Office of the State Court Administrator",
            "request_scope": (
                "statewide data requests and other administrative records "
                "held by OSCA"
            ),
            "geography": "statewide",
        },
        contents=(
            "existing statewide court data requested from OSCA",
            "OSCA administrative records",
        ),
        current_fees={
            "estimate_threshold_usd": 25,
            "fee_basis": "actual costs described on the official request page",
        },
        acquisition={
            "request_page_url": RECORDS_REQUEST_URL,
            "online_portal_url": OSCA_REQUEST_PORTAL_URL,
            "mailing_address": OSCA_MAILING_ADDRESS,
            "request_description_guidance": (
                "Identify the existing statewide data or administrative "
                "records sought and the useful date and court scope."
            ),
        },
        official_evidence=(
            {
                "url": RECORDS_REQUEST_URL,
                "supports": "OSCA custody, statewide request route, and fees",
            },
            {
                "url": OSCA_REQUEST_PORTAL_URL,
                "supports": "online Public Records Center handoff",
            },
            {
                "url": CASE_COPY_REQUEST_URL,
                "supports": (
                    "OSCA route for complex or statewide data requests and "
                    "separate case-copy route"
                ),
            },
        ),
        complements=(
            FREE_SEARCH_COMPLEMENT,
            CASE_COPY_COMPLEMENT,
            PUBLIC_KIOSK_COMPLEMENT,
        ),
    ),
}


ADAPTER_SCHEMA_FINGERPRINT = sha256_fingerprint(
    {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "component_source_ids": sorted(PRODUCTS),
        "record_fields": [
            "adapter_source_id",
            "source",
            "jurisdiction",
            "product_id",
            "system",
            "acquisition_mode",
            "coverage",
            "contents",
            "current_fees",
            "fee_effective_date",
            "acquisition",
            "delivery_schema",
            "official_evidence",
            "complements",
            "canonical_ref",
        ],
        "commands": [
            "products",
            "search",
            "handoff",
            "probe",
            "inspect-delivery",
        ],
    }
)


@dataclass(frozen=True)
class EndpointExpectation:
    """Expected public representation for one official endpoint."""

    endpoint_id: str
    url: str
    role: str
    source_ids: tuple[str, ...]
    media_kind: str
    marker: str | None = None


ENDPOINTS: tuple[EndpointExpectation, ...] = (
    EndpointExpectation(
        "ojcin_landing",
        OJCIN_URL,
        "official_product_landing",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-standard-report-package",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "html",
        "OJCIN OnLine",
    ),
    EndpointExpectation(
        "ojcin_signup",
        SIGNUP_URL,
        "subscription_handoff",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "html",
        "Opening an OJCIN Online Subscription Account",
    ),
    EndpointExpectation(
        "fee_schedule",
        FEE_SCHEDULE_URL,
        "current_fee_evidence",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-standard-report-package",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "pdf",
    ),
    EndpointExpectation(
        "current_cjo",
        CURRENT_CJO_URL,
        "current_product_and_fee_authority",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-standard-report-package",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "pdf",
    ),
    EndpointExpectation(
        "ojcin_terms",
        TERMS_URL,
        "subscription_terms_handoff",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "pdf",
    ),
    EndpointExpectation(
        "customer_form",
        CUSTOMER_FORM_URL,
        "subscription_customer_form",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-ojcin-bulk-data-transfer",
        ),
        "pdf",
    ),
    EndpointExpectation(
        "document_access_form",
        DOCUMENT_ACCESS_FORM_URL,
        "document_access_request_form",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
        ),
        "pdf",
    ),
    EndpointExpectation(
        "oeci_login",
        OECI_LOGIN_URL,
        "subscriber_login_handoff",
        ("us-or-ojcin-oeci-subscription",),
        "html",
        "Oregon eCourt Case Information",
    ),
    EndpointExpectation(
        "acms_login",
        ACMS_LOGIN_URL,
        "subscriber_login_handoff",
        ("us-or-ojcin-acms-subscription",),
        "html",
        '<div id="app">',
    ),
    EndpointExpectation(
        "osca_request_page",
        RECORDS_REQUEST_URL,
        "statewide_request_authority",
        ("us-or-osca-statewide-court-data-request",),
        "html",
        "statewide data requests",
    ),
    EndpointExpectation(
        "osca_request_portal",
        OSCA_REQUEST_PORTAL_URL,
        "statewide_request_portal",
        ("us-or-osca-statewide-court-data-request",),
        "html",
        "Public Records Center",
    ),
    EndpointExpectation(
        "case_copy_request",
        CASE_COPY_REQUEST_URL,
        "case_document_copy_alternative",
        tuple(PRODUCTS),
        "html",
        "Records Request",
    ),
    EndpointExpectation(
        "free_search_information",
        FREE_SEARCH_INFO_URL,
        "free_basic_search_alternative",
        (
            "us-or-ojcin-oeci-subscription",
            "us-or-ojcin-acms-subscription",
            "us-or-osca-statewide-court-data-request",
        ),
        "html",
        "Free Access to Court Dates",
    ),
)


class OfficialEndpointClient:
    """Small retrying HTTP client for official OJD representations."""

    def __init__(
        self,
        session: requests.Session | Any | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.session = session or requests.Session()
        if hasattr(self.session, "headers"):
            self.session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/pdf;"
                        "q=0.9,*/*;q=0.6"
                    ),
                    "Accept-Language": "en-US,en;q=0.8",
                }
            )
        self.timeout = timeout
        self.minimum_interval = minimum_interval
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)

    def get(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._wait()
            try:
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                last_error = exc
                self._last_request_at = time.monotonic()
                if attempt < self.max_retries:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise OJCINProductsError(
                    f"official endpoint request failed for {url}: {exc}"
                ) from exc

            self._last_request_at = time.monotonic()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < self.max_retries:
                    time.sleep(0.25 * (2**attempt))
                    continue
            return response

        raise OJCINProductsError(
            f"official endpoint request failed for {url}: {last_error}"
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _result(
    records: Sequence[Mapping[str, Any]],
    *,
    operation: str,
    parameters: Mapping[str, Any],
    warnings: Sequence[str] = (),
) -> dict[str, Any]:
    query = PublicRecordsQuery(
        source=SOURCE_METADATA,
        jurisdiction=JURISDICTION,
        query=QueryMetadata(operation=operation, parameters=parameters),
    )
    return PublicRecordsResult.success(
        query,
        records,
        warnings=warnings,
    ).to_dict()


def product_records(product_id: str | None = None) -> list[dict[str, Any]]:
    """Return deterministic, separately attributable product records."""

    if product_id is not None:
        try:
            return [PRODUCTS[product_id].to_record()]
        except KeyError as exc:
            raise OJCINProductsError(f"unknown product: {product_id}") from exc
    return [PRODUCTS[key].to_record() for key in sorted(PRODUCTS)]


def search_products(query: str) -> list[dict[str, Any]]:
    """Search static official product metadata without collapsing products."""

    needle = query.strip().casefold()
    if not needle:
        raise OJCINProductsError("search query must not be empty")
    return [
        record
        for record in product_records()
        if needle in json.dumps(record, sort_keys=True).casefold()
    ]


def handoff_record(product_id: str) -> dict[str, Any]:
    """Return a compact acquisition handoff for one product."""

    try:
        product = PRODUCTS[product_id]
    except KeyError as exc:
        raise OJCINProductsError(f"unknown product: {product_id}") from exc
    record = product.to_record()
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "product_id": product_id,
        "name": product.name,
        "publisher": "Oregon Judicial Department",
        "system": product.system,
        "coverage": record["coverage"],
        "contents": record["contents"],
        "current_fees": record["current_fees"],
        "fee_effective_date": CURRENT_FEE_EFFECTIVE_DATE,
        "acquisition_mode": product.acquisition_mode,
        "acquisition": record["acquisition"],
        "delivery_schema": record["delivery_schema"],
        "official_evidence": record["official_evidence"],
        "complements": record["complements"],
        "receipt_command": (
            "uv run python tools/query_oregon_ojcin_products.py "
            f"inspect-delivery {product_id} DELIVERY_PATH "
            "--delivery-version VERSION --output RECEIPT.json"
        ),
    }


def _header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", {}) or {}
    return headers.get(name) or headers.get(name.lower())


def probe_endpoint(
    client: OfficialEndpointClient,
    endpoint: EndpointExpectation,
) -> dict[str, Any]:
    """Probe one official endpoint and validate its public representation."""

    try:
        response = client.get(endpoint.url)
    except OJCINProductsError as exc:
        return {
            "endpoint_id": endpoint.endpoint_id,
            "url": endpoint.url,
            "role": endpoint.role,
            "source_ids": list(endpoint.source_ids),
            "status": "error",
            "error": str(exc),
        }

    content = bytes(getattr(response, "content", b""))
    text = getattr(response, "text", "")
    if not text and endpoint.media_kind == "html":
        text = content.decode("utf-8", errors="replace")
    http_ok = 200 <= response.status_code < 300
    if endpoint.media_kind == "pdf":
        representation_ok = content.lstrip().startswith(b"%PDF")
    else:
        representation_ok = endpoint.marker is None or endpoint.marker.casefold() in (
            text.casefold()
        )

    if http_ok and representation_ok:
        status = "ok"
    elif not http_ok:
        status = "http_error"
    else:
        status = "representation_changed"

    return {
        "endpoint_id": endpoint.endpoint_id,
        "url": endpoint.url,
        "final_url": getattr(response, "url", endpoint.url),
        "role": endpoint.role,
        "source_ids": list(endpoint.source_ids),
        "status": status,
        "http_status": response.status_code,
        "content_type": _header(response, "Content-Type"),
        "content_length": len(content),
        "etag": _header(response, "ETag"),
        "last_modified": _header(response, "Last-Modified"),
        "expected_media_kind": endpoint.media_kind,
        "expected_marker": endpoint.marker,
        "representation_ok": representation_ok,
    }


def probe_all(
    client: OfficialEndpointClient,
    *,
    endpoint_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Probe all or selected official product and acquisition endpoints."""

    selected = set(endpoint_ids)
    unknown = selected - {endpoint.endpoint_id for endpoint in ENDPOINTS}
    if unknown:
        raise OJCINProductsError(
            f"unknown endpoint(s): {', '.join(sorted(unknown))}"
        )
    endpoints = [
        endpoint
        for endpoint in ENDPOINTS
        if not selected or endpoint.endpoint_id in selected
    ]
    probes = [probe_endpoint(client, endpoint) for endpoint in endpoints]
    failed = [probe for probe in probes if probe["status"] != "ok"]
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "adapter_source_id": SOURCE_ID,
        "adapter_schema_fingerprint": ADAPTER_SCHEMA_FINGERPRINT,
        "probed_at": _utc_now(),
        "status": "ok" if not failed else "partial",
        "endpoint_count": len(probes),
        "ok_count": len(probes) - len(failed),
        "probes": probes,
    }


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _format_observation(file_path: Path) -> dict[str, Any]:
    with file_path.open("rb") as stream:
        prefix = stream.read(32)
    extension = file_path.suffix.casefold() or None
    guessed_media_type, guessed_encoding = mimetypes.guess_type(file_path.name)
    if prefix.startswith(b"%PDF"):
        magic_kind = "pdf"
    elif prefix.startswith(b"PK\x03\x04"):
        magic_kind = "zip"
    elif prefix.startswith(b"\x1f\x8b"):
        magic_kind = "gzip"
    elif prefix.lstrip().startswith((b"{", b"[")):
        magic_kind = "json_text_candidate"
    elif prefix.lstrip().startswith(b"<?xml"):
        magic_kind = "xml_text_candidate"
    else:
        magic_kind = "unclassified"
    return {
        "extension": extension,
        "guessed_media_type": guessed_media_type,
        "guessed_encoding": guessed_encoding,
        "magic_kind": magic_kind,
        "observation_only": True,
    }


def _zip_member_inventory(file_path: Path) -> list[dict[str, Any]]:
    if not zipfile.is_zipfile(file_path):
        return []
    with zipfile.ZipFile(file_path) as archive:
        return [
            {
                "member_path": member.filename,
                "size_bytes": member.file_size,
                "compressed_size_bytes": member.compress_size,
                "crc32": f"{member.CRC:08x}",
                "is_directory": member.is_dir(),
            }
            for member in archive.infolist()
        ]


def _delivery_files(delivery_path: Path) -> tuple[Path, list[Path]]:
    resolved = delivery_path.expanduser().resolve(strict=True)
    if resolved.is_file():
        return resolved.parent, [resolved]
    if not resolved.is_dir():
        raise DeliveryInspectionError(
            f"delivery path is not a regular file or directory: {resolved}"
        )
    files = sorted(
        (candidate for candidate in resolved.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(resolved).as_posix(),
    )
    if not files:
        raise DeliveryInspectionError(
            f"delivery directory contains no regular files: {resolved}"
        )
    return resolved, files


def _normalize_received_at(value: str | None) -> tuple[str, str]:
    if value is None:
        return _utc_now(), "inspection_time"
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeliveryInspectionError(
            "--received-at must be an ISO 8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise DeliveryInspectionError("--received-at must include a timezone")
    return (
        parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "user_supplied",
    )


def inspect_delivery(
    product_id: str,
    delivery_path: Path,
    *,
    delivery_version: str,
    received_at: str | None = None,
    provider_reference: str | None = None,
    correction_state: str = "not_stated_in_delivery",
    delivery_scope_note: str | None = None,
    specification_refs: Sequence[str] = (),
    case_document_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Create a provenance receipt without interpreting undocumented rows."""

    try:
        product = PRODUCTS[product_id]
    except KeyError as exc:
        raise DeliveryInspectionError(f"unknown product: {product_id}") from exc
    version = delivery_version.strip()
    if not version:
        raise DeliveryInspectionError("--delivery-version must not be empty")
    normalized_received_at, received_at_basis = _normalize_received_at(
        received_at
    )
    root, files = _delivery_files(delivery_path)

    file_records: list[dict[str, Any]] = []
    for file_path in files:
        relative_path = (
            file_path.name
            if len(files) == 1 and root == file_path.parent
            else file_path.relative_to(root).as_posix()
        )
        file_records.append(
            {
                "relative_path": relative_path,
                "absolute_path": str(file_path),
                "size_bytes": file_path.stat().st_size,
                "sha256": _sha256_file(file_path),
                "format_observation": _format_observation(file_path),
                "zip_members": _zip_member_inventory(file_path),
            }
        )

    artifact_set_sha256 = sha256_fingerprint(
        [
            {
                "relative_path": record["relative_path"],
                "size_bytes": record["size_bytes"],
                "sha256": record["sha256"],
            }
            for record in file_records
        ]
    )
    receipt_id = sha256_fingerprint(
        {
            "product_id": product_id,
            "delivery_version": version,
            "received_at": normalized_received_at,
            "artifact_set_sha256": artifact_set_sha256,
            "provider_reference": provider_reference,
        }
    )
    product_record = product.to_record()
    return {
        "schema_version": DELIVERY_RECEIPT_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "created_at": _utc_now(),
        "product": {
            "source_id": product_id,
            "name": product.name,
            "system": product.system,
            "publisher": "Oregon Judicial Department",
            "official_coverage": product_record["coverage"],
            "official_evidence": product_record["official_evidence"],
        },
        "delivery": {
            "version": version,
            "received_at": normalized_received_at,
            "received_at_basis": received_at_basis,
            "provider_reference": provider_reference,
            "correction_state": correction_state,
            "delivery_scope_note": delivery_scope_note,
            "specification_refs": list(specification_refs),
            "case_document_refs": list(case_document_refs),
        },
        "artifact_root": str(root),
        "artifact_set_sha256": artifact_set_sha256,
        "file_count": len(file_records),
        "total_size_bytes": sum(
            int(record["size_bytes"]) for record in file_records
        ),
        "files": file_records,
        "interpretation": {
            "records_parsed": 0,
            "rows_interpreted": False,
            "delivery_schema_status": product.delivery_schema_status,
            "format_labels_are_observations": True,
            "raw_file_hashes_preserved": True,
        },
    }


def _emit(
    data: Any,
    args: argparse.Namespace,
    *,
    summary: str,
    result_count: int | None = None,
) -> None:
    kwargs: dict[str, Any] = {}
    if result_count is not None:
        kwargs["result_count"] = result_count
    if write_output(data, args, summary=summary, **kwargs):
        return
    print(json.dumps(data, indent=2, sort_keys=True))


def _client_from_args(args: argparse.Namespace) -> OfficialEndpointClient:
    return OfficialEndpointClient(
        timeout=args.timeout,
        minimum_interval=args.minimum_interval,
        max_retries=args.max_retries,
    )


def run(args: argparse.Namespace) -> int:
    """Execute one CLI command."""

    if args.command == "products":
        records = product_records(args.product)
        data = _result(
            records,
            operation="products",
            parameters={"product": args.product},
        )
        _emit(
            data,
            args,
            summary="Oregon statewide court-data products",
            result_count=len(records),
        )
        return 0

    if args.command == "search":
        records = search_products(args.query)
        log_search(args.query, SOURCE_ID, len(records))
        data = _result(
            records,
            operation="search",
            parameters={"query": args.query},
        )
        _emit(
            data,
            args,
            summary=f"Oregon court-data product search {args.query!r}",
            result_count=len(records),
        )
        return 0

    if args.command == "handoff":
        data = handoff_record(args.product)
        _emit(
            data,
            args,
            summary=f"Oregon court-data handoff {args.product}",
            result_count=1,
        )
        return 0

    if args.command == "probe":
        data = probe_all(
            _client_from_args(args),
            endpoint_ids=args.endpoint,
        )
        _emit(
            data,
            args,
            summary="Oregon court-data endpoint probe",
            result_count=data["ok_count"],
        )
        return 0 if data["status"] == "ok" else 2

    if args.command == "inspect-delivery":
        data = inspect_delivery(
            args.product,
            Path(args.delivery_path),
            delivery_version=args.delivery_version,
            received_at=args.received_at,
            provider_reference=args.provider_reference,
            correction_state=args.correction_state,
            delivery_scope_note=args.delivery_scope_note,
            specification_refs=args.specification_ref,
            case_document_refs=args.case_document_ref,
        )
        _emit(
            data,
            args,
            summary=f"Oregon court-data delivery receipt {args.product}",
            result_count=data["file_count"],
        )
        return 0

    raise OJCINProductsError(f"unknown command: {args.command}")


def _add_network_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
        help=(
            "Minimum seconds between official endpoint requests "
            f"(default: {DEFAULT_MINIMUM_INTERVAL:g})"
        ),
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help=f"Retries for transient HTTP failures (default: {DEFAULT_MAX_RETRIES})",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Official Oregon OJCIN, bulk, report, and statewide data-request "
            "product directory"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    products = subparsers.add_parser(
        "products",
        help="List separately attributable OJD court-data products",
    )
    products.add_argument("--product", choices=sorted(PRODUCTS))
    add_output_args(products)

    search = subparsers.add_parser(
        "search",
        help="Search product scope, contents, and acquisition metadata",
    )
    search.add_argument("query")
    add_output_args(search)

    handoff = subparsers.add_parser(
        "handoff",
        help="Prepare the verified acquisition handoff for one product",
    )
    handoff.add_argument("product", choices=sorted(PRODUCTS))
    add_output_args(handoff)

    probe = subparsers.add_parser(
        "probe",
        help="Probe official product, fee, login, and request representations",
    )
    probe.add_argument(
        "--endpoint",
        action="append",
        default=[],
        choices=[endpoint.endpoint_id for endpoint in ENDPOINTS],
        help="Probe only this endpoint (repeatable; default: all)",
    )
    _add_network_args(probe)
    add_output_args(probe)

    inspect = subparsers.add_parser(
        "inspect-delivery",
        help=(
            "Fingerprint an acquired delivery and create a provenance receipt "
            "without interpreting rows"
        ),
    )
    inspect.add_argument("product", choices=sorted(PRODUCTS))
    inspect.add_argument("delivery_path")
    inspect.add_argument(
        "--delivery-version",
        required=True,
        help="Version, period, or label supplied with the delivery",
    )
    inspect.add_argument(
        "--received-at",
        help=(
            "ISO 8601 receipt timestamp with timezone; defaults to inspection "
            "time"
        ),
    )
    inspect.add_argument(
        "--provider-reference",
        help="OJD invoice, request, transfer, or correspondence reference",
    )
    inspect.add_argument(
        "--correction-state",
        default="not_stated_in_delivery",
        help="Correction or replacement label supplied with the delivery",
    )
    inspect.add_argument(
        "--delivery-scope-note",
        help="Scope statement supplied with or established for this delivery",
    )
    inspect.add_argument(
        "--specification-ref",
        action="append",
        default=[],
        help="Reference to an accompanying data specification (repeatable)",
    )
    inspect.add_argument(
        "--case-document-ref",
        action="append",
        default=[],
        help="Reference to a separately acquired case document (repeatable)",
    )
    add_output_args(inspect)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        exit_code = run(args)
    except (OJCINProductsError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
