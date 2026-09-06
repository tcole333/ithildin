#!/usr/bin/env python3
"""Query Oregon county Helion Digital Research Room recorder tenants.

Each county remains a distinct source component even though the portals share
Helion's ASP.NET search, result, detail, and document-delivery shapes.  The
adapter preserves county-native document numbers, internal document/title
selectors, party roles, map/legal fields, related instruments, and the
observed image/text/copy state.

Examples:
    uv run python tools/query_oregon_helion_recorder.py source \
      --source us-or-umatilla-helion-recorder
    uv run python tools/query_oregon_helion_recorder.py search \
      --source us-or-umatilla-helion-recorder \
      --year 2026 --document-from 1 --document-to 20
    uv run python tools/query_oregon_helion_recorder.py detail \
      --source us-or-wasco-helion-recorder 2023 2123
    uv run python tools/query_oregon_helion_recorder.py probe \
      --source us-or-deschutes-helion-recorder
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
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

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
    from tools.public_records_http import system_trust_session
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
    from public_records_http import system_trust_session


STATE_CODE = "OR"
STATE_GEOID = "41"
PLATFORM_FAMILY = "helion_digital_research_room"
CURSOR_PREFIX = "orhelion:v1:"
SOURCE_PAGE_SIZE = 50
SOURCE_SHOW_MAXIMUM = 500
DEFAULT_TIMEOUT = 30.0
DEFAULT_MINIMUM_INTERVAL = 0.25
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF = 0.5


@dataclass(frozen=True)
class HelionTenant:
    """One county-owned Helion recorder component."""

    key: str
    source_id: str
    county_name: str
    county_fips: str
    authority: str
    portal_root: str
    search_path: str = ""
    official_linking_page: str | None = None
    access_observation: str = "public_portal"
    captcha_observed: bool | None = None
    coverage_observation: str | None = None
    resource_observation: str | None = None
    complement_observations: tuple[Mapping[str, Any], ...] = ()

    @property
    def search_url(self) -> str:
        return urljoin(self.portal_root, self.search_path)

    @property
    def name(self) -> str:
        return f"{self.county_name} Helion Digital Research Room"

    @property
    def jurisdiction(self) -> JurisdictionMetadata:
        return JurisdictionMetadata(
            jurisdiction_id=f"us-or-{self.key}",
            name=f"{self.county_name}, Oregon",
            state_code=STATE_CODE,
            county_fips=self.county_fips,
            locality=self.county_name,
            metadata={"state_geoid": STATE_GEOID},
        )

    @property
    def source_metadata(self) -> SourceMetadata:
        return SourceMetadata(
            source_id=self.source_id,
            name=self.name,
            source_role="county_recorded_instrument_search_and_detail_portal",
            base_url=self.portal_root,
            dataset_id=f"helion-drr-{self.key}",
            metadata={
                "authority": self.authority,
                "operator": "Helion Software",
                "platform_family": PLATFORM_FAMILY,
                "county_fips": self.county_fips,
                "search_url": self.search_url,
                "official_linking_page": self.official_linking_page,
                "access_observation": self.access_observation,
                "captcha_observed": self.captcha_observed,
                "coverage_observation": self.coverage_observation,
                "resource_observation": self.resource_observation,
                "complement_observations": [
                    dict(value) for value in self.complement_observations
                ],
                "family_route_contract": {
                    "live_verified_tenants": [
                        "lincoln",
                        "marion",
                        "umatilla",
                        "wasco",
                        "polk",
                        "yamhill",
                    ],
                    "advanced_search_form": "?mode=Advanced",
                    "search_method": "POST",
                    "result_continuation": "RecordingSearch/NextResults",
                    "detail": "Document/Details",
                    "detail_by_id": "Document/DetailsById",
                    "document_image": "DocumentImage",
                    "document_text": "DocumentText",
                    "tenant_form_discovery": True,
                },
            },
        )


TENANTS = (
    HelionTenant(
        key="benton",
        source_id="us-or-benton-helion-recorder",
        county_name="Benton County",
        county_fips="41003",
        authority="Benton County Records and Elections",
        portal_root="https://records.co.benton.or.us/",
        official_linking_page=("https://re.bentoncountyor.gov/real-property-records/"),
        access_observation=(
            "Public search was indexed with current search fields; the bounded "
            "live probe on 2026-07-29 timed out before a response."
        ),
        captcha_observed=None,
        coverage_observation=(
            "The county describes in-person deed indexes for 1848-1966, "
            "online microfilm-designated index data for 1966-2002, and "
            "year/document-number index data from 2003 onward."
        ),
        resource_observation=(
            "The county describes online access as index data; document images "
            "are available by request or in person."
        ),
        complement_observations=(
            {
                "kind": "benton_record_request_and_copy",
                "join_keys": [
                    "recording_number",
                    "microfilm_number",
                    "book_page",
                    "party_name",
                ],
                "relationship": "image_and_historical_index_complement",
            },
            {
                "kind": "benton_assessment_property_search",
                "join_keys": [
                    "taxlot",
                    "account_number",
                    "owner_name",
                    "sale_history",
                ],
                "relationship": "parcel_and_sale_context_complement",
            },
        ),
    ),
    HelionTenant(
        key="crook",
        source_id="us-or-crook-helion-recorder",
        county_name="Crook County",
        county_fips="41013",
        authority="Crook County Clerk",
        portal_root=("https://clerk.crookcountyor.gov/DigitalResearchRoomPublic/"),
        official_linking_page=(
            "https://www.crookcountyor.gov/1337/"
            "Records-Research---Digital-Research-Room"
        ),
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        coverage_observation=(
            "The county reports deeds indexed to about 1882, other recorded "
            "records generally from mid-1971, and marriages from about 1990; "
            "some pre-1971 images may not appear in name search."
        ),
        resource_observation=(
            "The county reports that indexed documents can be purchased "
            "online; a public office terminal is a separate access route."
        ),
        complement_observations=(
            {
                "kind": "county_staff_historical_index_search",
                "join_keys": ["party_name", "approximate_recording_period"],
                "relationship": "coverage_complement",
            },
            {
                "kind": "county_assessor_and_gis",
                "join_keys": ["taxlot", "account_number", "legal_description"],
                "relationship": "parcel_context_complement",
            },
        ),
    ),
    HelionTenant(
        key="deschutes",
        source_id="us-or-deschutes-helion-recorder",
        county_name="Deschutes County",
        county_fips="41017",
        authority="Deschutes County Clerk",
        portal_root=("https://recordings.deschutes.org/DigitalResearchRoomPublic/"),
        official_linking_page=("https://www.deschutes.org/clerk/page/recording"),
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        coverage_observation=(
            "The county describes real-property search from 1983 onward and "
            "older deed lookup by book and page in advanced search."
        ),
        resource_observation=(
            "Official examples expose direct DocumentImage links for some "
            "instruments; certified-copy ordering is a separate county route."
        ),
        complement_observations=(
            {
                "kind": "deschutes_assessor_dial",
                "join_keys": [
                    "taxlot",
                    "account_number",
                    "owner_name",
                    "recording_number",
                ],
                "relationship": "parcel_and_sale_context_complement",
            },
            {
                "kind": "county_copy_order",
                "join_keys": ["recording_number", "book_page"],
                "relationship": "certified_copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="hood-river",
        source_id="us-or-hood-river-helion-recorder",
        county_name="Hood River County",
        county_fips="41027",
        authority="Hood River County Records and Assessment",
        portal_root=("https://records.co.hood-river.or.us/DigitalResearchRoom/"),
        official_linking_page=(
            "https://www.hoodrivercounty.gov/public-records-request"
        ),
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        resource_observation=(
            "The county launched Digital Research Room e-commerce for "
            "non-certified recorded documents in 2025."
        ),
        complement_observations=(
            {
                "kind": "hood_river_property_search",
                "join_keys": ["taxlot", "account_number", "owner_name"],
                "relationship": "parcel_context_complement",
            },
            {
                "kind": "county_public_records_request",
                "join_keys": ["recording_number", "party_name", "date"],
                "relationship": "copy_and_missing_record_complement",
            },
        ),
    ),
    HelionTenant(
        key="jackson",
        source_id="us-or-jackson-helion-recorder",
        county_name="Jackson County",
        county_fips="41029",
        authority="Jackson County Clerk",
        portal_root=("https://apps.jacksoncountyor.gov/DigitalResearchRoomPublic/"),
        official_linking_page=("https://jacksoncountyor.gov/clerk/Recording"),
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        complement_observations=(
            {
                "kind": "jackson_clerk_copy_request",
                "join_keys": [
                    "recording_number",
                    "book_page",
                    "party_name",
                    "recording_date",
                ],
                "relationship": "document_copy_complement",
            },
            {
                "kind": "jackson_assessor_and_gis",
                "join_keys": [
                    "taxlot",
                    "account_number",
                    "owner_name",
                    "legal_description",
                ],
                "relationship": "parcel_context_complement",
            },
        ),
    ),
    HelionTenant(
        key="jefferson",
        source_id="us-or-jefferson-helion-recorder",
        county_name="Jefferson County",
        county_fips="41031",
        authority="Jefferson County Clerk",
        portal_root=("https://clerk.co.jefferson.or.us/DigitalResearchRoomPublic/"),
        official_linking_page="https://www.jeffersoncountyor.gov/cc",
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        complement_observations=(
            {
                "kind": "jefferson_county_gis",
                "join_keys": ["taxlot", "legal_description", "owner_name"],
                "relationship": "parcel_context_complement",
            },
            {
                "kind": "jefferson_clerk_copy_request",
                "join_keys": [
                    "fee_number",
                    "book_page",
                    "party_name",
                    "recording_date",
                ],
                "relationship": "certified_and_uncertified_copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="lincoln",
        source_id="us-or-lincoln-helion-recorder",
        county_name="Lincoln County",
        county_fips="41041",
        authority="Lincoln County Clerk",
        portal_root=("https://helion.co.lincoln.or.us/DigitalResearchRoomPublic/"),
        official_linking_page=(
            "https://www.co.lincoln.or.us/962/Document-Recording-Information-and-Docum"
        ),
        access_observation=(
            "The live public advanced search established an anonymous session "
            "without reCAPTCHA on 2026-07-29 and exposed 395 tenant-native "
            "subtype options."
        ),
        captcha_observed=False,
        coverage_observation=(
            "The advanced form supports year and document number, recording "
            "date, document type and subtype, party, property, legal, and "
            "related-instrument selectors."
        ),
        resource_observation=(
            "A live 2025 Warranty Deed detail exposed direct and indirect "
            "parties, consideration, return address, and a direct PDF image. "
            "The portal reports text alternatives only for documents recorded "
            "on or after 2026-01-01."
        ),
        complement_observations=(
            {
                "kind": "lincoln_propertyweb",
                "join_keys": [
                    "sale_instrument",
                    "recording_number",
                    "party_name",
                    "recording_date",
                ],
                "relationship": "parcel_sale_and_instrument_context_complement",
            },
            {
                "kind": "lincoln_taxlot_wfs",
                "join_keys": [
                    "taxlot",
                    "owner_name",
                    "legal_description",
                ],
                "relationship": "parcel_geometry_and_owner_complement",
            },
            {
                "kind": "lincoln_clerk_recording_information_and_copy",
                "join_keys": [
                    "recording_number",
                    "document_type",
                    "party_name",
                    "recording_date",
                ],
                "relationship": "copy_and_official_guidance_complement",
            },
        ),
    ),
    HelionTenant(
        key="multnomah",
        source_id="us-or-multnomah-helion-recorder",
        county_name="Multnomah County",
        county_fips="41051",
        authority="Multnomah County Division of Assessment, Recording and Taxation",
        portal_root="https://multcorecords.com/",
        official_linking_page=("https://multco.us/info/recording-documents"),
        access_observation=(
            "The live public disclaimer presented Google reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=True,
        coverage_observation=(
            "The county describes electronic recorded-document indexes from "
            "1965 onward; older records and some lien access use separate "
            "office or subscriber paths."
        ),
        complement_observations=(
            {
                "kind": "multnomah_property_recording_alert",
                "join_keys": ["party_name", "recording_number"],
                "relationship": "new_record_alert_complement",
            },
            {
                "kind": "multnomah_mail_or_office_copy_request",
                "join_keys": [
                    "document_type",
                    "recording_number",
                    "book_page",
                    "year",
                    "party_name",
                ],
                "relationship": "historical_and_certified_copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="marion",
        source_id="us-or-marion-clerk-recorded-documents",
        county_name="Marion County",
        county_fips="41047",
        authority="Marion County Clerk",
        portal_root=(
            "https://lrmw-marioncountygcc.msappproxy.net/"
            "DigitalResearchRoomPublic/"
        ),
        official_linking_page=(
            "https://www.co.marion.or.us/CO/Pages/Records.aspx"
        ),
        access_observation=(
            "A live probe on 2026-07-30 completed the public disclaimer POST "
            "and redirect-form POST through Microsoft Entra Application Proxy, "
            "then received an anonymous Helion search session without "
            "reCAPTCHA."
        ),
        captcha_observed=False,
        coverage_observation=(
            "The county records page labels the recorded-document index as "
            "1974 to present. The live advanced form reported documents indexed "
            "through 07/28/2026 and exposed year/document, recording date, "
            "Reel & Page, type/subtype, party, subdivision, PLSS, and legal-"
            "description selectors."
        ),
        resource_observation=(
            "Exact document 2026-00001 exposed recording time, document type, "
            "direct and indirect parties, consideration, return-to data, and "
            "referenced document 2023-01093 with Reel & Page 4683-178. The "
            "sampled detail exposed no direct image, OCR-text, or cart link."
        ),
        complement_observations=(
            {
                "kind": "marion_historical_deed_search",
                "source_url": (
                    "https://apps.co.marion.or.us/DeedSearch/Disclaimer.aspx"
                ),
                "operation_state": (
                    "anonymous_disclaimer_and_search_form_verified_2026-07-30"
                ),
                "coverage_label": "1855-1976",
                "portal_coverage_observation": (
                    "The county records page labels this Deeds search "
                    "1855-1976; the live search form separately says available "
                    "documents exist for year periods 1850 to 1976."
                ),
                "selectors": [
                    "file_date_start",
                    "file_date_end",
                    "instrument_type",
                    "direct_party_grantor",
                    "indirect_party_grantee",
                ],
                "join_keys": [
                    "file_date",
                    "instrument_type",
                    "direct_party",
                    "indirect_party",
                ],
                "overlap_with_current_index": "1974-1976",
                "relationship": "historical_deed_index_complement",
            },
            {
                "kind": "marion_assessor_property_records",
                "source_url": "https://mcasr.co.marion.or.us/",
                "operation_state": (
                    "anonymous_disclaimer_and_search_form_verified_2026-07-30"
                ),
                "selectors": [
                    "account_number",
                    "map_tax_lot",
                    "situs_address",
                    "subdivision",
                ],
                "join_keys": [
                    "account_number",
                    "map_tax_lot",
                    "situs_address",
                    "subdivision",
                ],
                "relationship": "parcel_identification_and_situs_complement",
            },
            {
                "kind": "marion_official_copy_and_certification",
                "source_url": (
                    "https://www.co.marion.or.us/CO/records/Pages/fees.aspx"
                ),
                "standards_url": (
                    "https://www.co.marion.or.us/CO/records/Documents/"
                    "MCC%20Recording%20Standards_rev1.pdf"
                ),
                "retrieval_routes": ["counter", "mail"],
                "join_keys": [
                    "recording_year",
                    "document_number",
                    "book",
                    "page",
                ],
                "relationship": "official_copy_and_certification_complement",
            },
        ),
    ),
    HelionTenant(
        key="polk",
        source_id="us-or-polk-helion-recorder",
        county_name="Polk County",
        county_fips="41053",
        authority="Polk County Clerk",
        portal_root="https://apps2.co.polk.or.us/DigitalResearchRoom/",
        search_path="RecordingSearch",
        access_observation=(
            "The live public disclaimer used a two-step session redirect "
            "without reCAPTCHA on 2026-07-29; recorded documents use the "
            "separate RecordingSearch route."
        ),
        captcha_observed=False,
        coverage_observation=(
            "The portal landing page separates recorded documents from 1983 "
            "onward, historic documents, and marriage licenses."
        ),
        resource_observation=(
            "A live 2026 instrument search exposed direct PDF and OCR-text "
            "links. One document can return multiple title rows, identified "
            "by the Title query parameter."
        ),
        complement_observations=(
            {
                "kind": "polk_historic_deed_search",
                "join_keys": [
                    "book_page",
                    "party_name",
                    "recording_period",
                ],
                "relationship": "pre_1983_index_complement",
            },
            {
                "kind": "polk_assessor_and_gis",
                "join_keys": [
                    "taxlot",
                    "account_number",
                    "owner_name",
                    "legal_description",
                ],
                "relationship": "parcel_context_complement",
            },
        ),
    ),
    HelionTenant(
        key="tillamook",
        source_id="us-or-tillamook-helion-recorder",
        county_name="Tillamook County",
        county_fips="41057",
        authority="Tillamook County Clerk",
        portal_root=("https://query.co.tillamook.or.us/DigitalResearchRoomPublic/"),
        official_linking_page=("https://www.co.tillamook.or.us/clerk/page/recording"),
        access_observation=(
            "The public search was current in the search index and reachable "
            "with a cookie-preserving curl session on 2026-07-29. Python "
            "Requests rejected the server's incomplete certificate chain."
        ),
        captcha_observed=False,
        coverage_observation=(
            "The advanced form documents different party-name layouts for "
            "August 1994 through March 2003 and April 2003 onward."
        ),
        resource_observation=(
            "The portal exposes separate recorded, historic-film, marriage, "
            "and authenticated external-product components."
        ),
        complement_observations=(
            {
                "kind": "historic_film_viewer",
                "join_keys": ["book", "page", "direct_or_indirect_index"],
                "relationship": "historic_index_complement",
            },
            {
                "kind": "county_clerk_copy_request",
                "join_keys": ["recording_number", "book_page", "party_name"],
                "relationship": "copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="umatilla",
        source_id="us-or-umatilla-helion-recorder",
        county_name="Umatilla County",
        county_fips="41059",
        authority="Umatilla County Clerk",
        portal_root=("https://public.co.umatilla.or.us/DigitalResearchRoomPublic/"),
        official_linking_page=(
            "https://www.umatillacounty.gov/departments/clerk/records-lookup"
        ),
        access_observation=(
            "The live public advanced search established an anonymous session "
            "without reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=False,
        resource_observation=(
            "Live detail exposed the index, parties, legal description, "
            "related instruments, and paid certified/non-certified cart "
            "options, but no direct image link for the sampled instrument."
        ),
        complement_observations=(
            {
                "kind": "county_copy_order",
                "join_keys": ["recording_number", "party_name", "date"],
                "relationship": "document_copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="wasco",
        source_id="us-or-wasco-helion-recorder",
        county_name="Wasco County",
        county_fips="41065",
        authority="Wasco County Clerk",
        portal_root=("https://public.co.wasco.or.us/DigitalResearchRoomPublic/"),
        access_observation=(
            "The live public disclaimer used a two-step session redirect "
            "without reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=False,
        resource_observation=(
            "Live detail exposed direct PDF images; 2026 instruments also "
            "exposed OCR text alternatives as distinct resources."
        ),
        complement_observations=(
            {
                "kind": "wasco_assessor_and_gis",
                "join_keys": [
                    "taxlot",
                    "property_id",
                    "owner_name",
                    "legal_description",
                ],
                "relationship": "parcel_context_complement",
            },
            {
                "kind": "county_clerk_certified_copy",
                "join_keys": ["recording_number", "book_page"],
                "relationship": "certified_copy_complement",
            },
        ),
    ),
    HelionTenant(
        key="wheeler",
        source_id="us-or-wheeler-helion-recorder",
        county_name="Wheeler County",
        county_fips="41069",
        authority="Wheeler County Clerk",
        portal_root=("https://wheelercountyoregonrecords.com/DigitalResearchRoom/"),
        official_linking_page="https://www.wheelercountyoregon.com/clerk",
        access_observation=(
            "The live public disclaimer used a two-step session redirect "
            "without reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=False,
        resource_observation=(
            "The county offers copies through the portal and also by email, "
            "phone, or in person."
        ),
        complement_observations=(
            {
                "kind": "county_clerk_copy_request",
                "join_keys": [
                    "recording_number",
                    "party_name",
                    "legal_description",
                ],
                "relationship": "copy_and_missing_record_complement",
            },
        ),
    ),
    HelionTenant(
        key="yamhill",
        source_id="us-or-yamhill-helion-recorder",
        county_name="Yamhill County",
        county_fips="41071",
        authority="Yamhill County Clerk",
        portal_root=(
            "https://clerkwebapp.co.yamhill.or.us/DigitalResearchRoom/"
        ),
        official_linking_page=(
            "https://yamhillcounty.gov/404/Clerk-Records-Elections"
        ),
        access_observation=(
            "The live county-linked public disclaimer established an "
            "anonymous search session without reCAPTCHA on 2026-07-29."
        ),
        captcha_observed=False,
        coverage_observation=(
            "The public tenant reported that documents were indexed through "
            "2026-07-29 during the live probe."
        ),
        resource_observation=(
            "Exact document 2026-003177 exposed recording time, document "
            "type, party roles, return address, legal description, and a "
            "linked prior instrument; the sampled detail did not publish a "
            "direct image resource."
        ),
        complement_observations=(
            {
                "kind": "yamhill_ascendweb_property",
                "join_keys": [
                    "recording_number",
                    "account_number",
                    "map_taxlot",
                    "owner_name",
                ],
                "relationship": "parcel_sale_and_tax_context_complement",
            },
            {
                "kind": "yamhill_county_taxlots",
                "join_keys": [
                    "recording_number",
                    "account_number",
                    "map_taxlot",
                    "owner_name",
                ],
                "relationship": "parcel_geometry_and_lineage_complement",
            },
            {
                "kind": "yamhill_clerk_copy_request",
                "join_keys": [
                    "recording_number",
                    "party_name",
                    "legal_description",
                ],
                "relationship": "document_copy_complement",
            },
        ),
    ),
)

TENANTS_BY_SOURCE = {tenant.source_id: tenant for tenant in TENANTS}
SOURCE_IDS = tuple(TENANTS_BY_SOURCE)

SOURCE_WARNINGS = (
    "Index detail, direct image, OCR text, cart purchase, and certified-copy "
    "availability are reported as separate source observations.",
    "Helion can return multiple title rows for one recorded document; the "
    "native year, document selector, and title selector are preserved.",
    "A search is authoritative only for the selected county tenant and the "
    "selectors shown in the query envelope.",
)

SELECTOR_FIELDS = {
    "year": "Criteria.Filter.YearStart",
    "document_from": "Criteria.Filter.DocumentStart",
    "document_to": "Criteria.Filter.DocumentEnd",
    "recorded_from": "Criteria.Filter.RecordingDateStart",
    "recorded_to": "Criteria.Filter.RecordingDateEnd",
    "historic_number": "Criteria.Filter.HistoricNumber",
    "document_type_key": "Criteria.Filter.DocumentType",
    "subtype_key": "Criteria.Filter.SubtypeKey",
    "last_name": "Criteria.Filter.LastName",
    "first_name": "Criteria.Filter.FirstName",
    "middle_name": "Criteria.Filter.MiddleName",
    "suffix": "Criteria.Filter.Suffix",
    "property_id": "Criteria.Filter.PropertyId",
    "subdivision": "Criteria.Filter.Subdivision",
    "legal_1": "Criteria.Filter.Legal1",
    "legal_2": "Criteria.Filter.Legal2",
    "township": "Criteria.Filter.Township",
    "range": "Criteria.Filter.Range",
    "section": "Criteria.Filter.Section",
    "quarter_quarter": "Criteria.Filter.QQ",
    "taxlot": "Criteria.Filter.Taxlot",
    "legal_description": "Criteria.Filter.LegalDescription",
    "comments": "Criteria.Filter.Comments",
}

PARTY_TYPE_VALUES = {"all": "", "direct": "1", "indirect": "4"}
VIEW_VALUES = {"document": "Document", "party": "Party", "map": "Map"}
SORT_VALUES = {
    "document-number": "DocumentNumber",
    "recording-date": "RecordingDate",
    "party-name": "PartyName",
    "subdivision-lot-block": "SubLotBlock",
}
DIRECTION_VALUES = {"ascending": "Ascending", "descending": "Descending"}


class HelionRecorderError(RuntimeError):
    """Base exception for explicit source and selector failures."""


class HelionTransportError(HelionRecorderError):
    """The tenant could not be reached with a verified client."""


class HelionHTTPError(HelionRecorderError):
    """The tenant returned a non-success HTTP response."""

    def __init__(self, status_code: int, url: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class HelionHumanRequired(HelionRecorderError):
    """The live tenant requires a browser-mediated session step."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class HelionSourceChanged(HelionRecorderError):
    """A verified Helion response shape no longer matches."""


class HelionSelectionError(HelionRecorderError):
    """The caller supplied an invalid selector or continuation."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: ResultStatus = ResultStatus.UNAVAILABLE,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = dict(details or {})


@dataclass(frozen=True)
class CursorState:
    """Opaque continuation bound to one county query and boundary record."""

    source_id: str
    query_fingerprint: str
    offset: int
    anchor: str
    total_results: int


@dataclass(frozen=True)
class SearchBatch:
    """One native Helion result window."""

    records: tuple[Mapping[str, Any], ...]
    total_results: int
    start_position: int
    end_position: int
    source_url: str
    search_id: str | None
    schema_fingerprint: str
    authoritative_empty: bool = False


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _lines(tag: Tag | None) -> list[str]:
    if tag is None:
        return []
    values = [_clean_text(value) for value in tag.stripped_strings]
    return [value for value in values if value]


def _lower_query(url: str) -> dict[str, list[str]]:
    return {
        key.casefold(): values for key, values in parse_qs(urlparse(url).query).items()
    }


def _first_integer(values: Sequence[str] | None) -> int | None:
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None


def _absolute(root: str, href: str | None) -> str | None:
    return urljoin(root, href) if href else None


def _recording_local_iso(raw: str | None) -> str | None:
    if not raw:
        return None
    for pattern in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(raw, pattern).isoformat()
        except ValueError:
            continue
    return None


def _money_string(raw: str | None) -> str | None:
    if not raw or "no value" in raw.casefold():
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", raw)
    if not cleaned:
        return None
    try:
        return format(Decimal(cleaned), "f")
    except InvalidOperation:
        return None


def _canonical_ref(
    tenant: HelionTenant,
    *,
    year: int | None,
    document: int | None,
    title: int | None,
    instrument_number: str,
) -> str:
    if year is not None and document is not None:
        suffix = f":T{title}" if title is not None else ""
        return f"ORREC:{tenant.county_fips}:{year}:{document}{suffix}"
    digest = hashlib.sha256(instrument_number.encode("utf-8")).hexdigest()[:16]
    return f"ORREC:{tenant.county_fips}:INSTRUMENT:{digest}"


def _native_key(record: Mapping[str, Any]) -> str:
    native = record.get("native_detail_key")
    if isinstance(native, Mapping):
        return canonical_json(dict(native))
    return str(record.get("canonical_ref") or "")


def _detail_identity(
    detail_url: str,
    instrument_number: str,
) -> tuple[int | None, int | None, int | None]:
    query = _lower_query(detail_url)
    year = _first_integer(query.get("year"))
    document = _first_integer(query.get("document"))
    title = _first_integer(query.get("title"))
    if year is None:
        match = re.match(r"^\s*(\d{4})\D+(\d+)", instrument_number)
        if match:
            year = int(match.group(1))
            document = int(match.group(2))
    return year, document, title


def _labeled_row_value(row: Tag) -> tuple[str, str, list[str]] | None:
    label = row.select_one(
        "p.bold-dark-text, strong.bold-dark-text, label, strong"
    )
    if label is None:
        return None
    label_text = _clean_text(label.get_text(" ", strip=True))
    if not label_text:
        return None
    label_column = label.find_parent("div")
    if label_column is row:
        value_column = label.find_next_sibling(["div", "p", "ul"])
    else:
        value_column = (
            label_column.find_next_sibling(["div", "p", "ul"])
            if isinstance(label_column, Tag)
            else None
        )
    if not isinstance(value_column, Tag):
        return None
    values = _lines(value_column)
    return label_text.rstrip(":"), " ".join(values), values


def _references(
    section: Tag,
    *,
    tenant: HelionTenant,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for anchor in section.select("a[href]"):
        number_tag = anchor.select_one(
            ".label-reference-number, .reference-link, .recording-link"
        )
        number = _clean_text(
            number_tag.get_text(" ", strip=True)
            if number_tag is not None
            else anchor.get_text(" ", strip=True)
        )
        if not number:
            continue
        href = _absolute(tenant.portal_root, anchor.get("href"))
        query = _lower_query(href or "")
        path_match = re.search(r"/DetailsById/(\d+)", href or "", re.I)
        records.append(
            {
                "instrument_number": number,
                "detail_url": href,
                "recording_year": _first_integer(query.get("year")),
                "document_selector": _first_integer(query.get("document")),
                "system_id": int(path_match.group(1)) if path_match else None,
                "raw_text": _clean_text(anchor.get_text(" ", strip=True)),
            }
        )
    return records


def _copy_options(soup: BeautifulSoup) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for wrapper in soup.select("[id$='item-wrapper']"):
        button = wrapper.select_one("button")
        if button is None:
            continue
        label = _clean_text(button.get_text(" ", strip=True))
        fee = _clean_text(
            " ".join(
                element.get_text(" ", strip=True) for element in wrapper.select("p")
            )
        )
        options.append(
            {
                "label": label,
                "fee_display": fee,
                "button_id": button.get("id"),
                "delivery": "cart",
            }
        )
    return options


def _cart_metadata(soup: BeautifulSoup, root: str) -> dict[str, Any] | None:
    pattern = re.compile(
        r"InitializeCartItemService\s*\(\s*\{(?P<body>.*?)\}\s*\)",
        re.S,
    )
    for script in soup.select("script"):
        match = pattern.search(script.get_text(" ", strip=False))
        if not match:
            continue
        body = match.group("body")
        values = dict(
            re.findall(
                r"([A-Za-z][A-Za-z0-9_]*)\s*:\s*['\"]([^'\"]*)['\"]",
                body,
            )
        )
        return {
            "add_item_url": _absolute(root, values.get("addItemUrl")),
            "system_id": values.get("systemId"),
            "item_type": values.get("itemType"),
            "page_count": (
                int(values["numPages"])
                if values.get("numPages", "").isdigit()
                else None
            ),
            "base_standard_fee": values.get("baseStandardFee"),
            "per_page_standard_fee": values.get("perPageStandardFee"),
        }
    return None


def _inline_labeled_value(container: Tag, label: str) -> str | None:
    wanted = label.casefold().rstrip(":")
    for strong in container.select("strong"):
        candidate = _clean_text(strong.get_text(" ", strip=True))
        if not candidate or candidate.casefold().rstrip(":") != wanted:
            continue
        parent = strong.parent
        if not isinstance(parent, Tag):
            continue
        clone = BeautifulSoup(str(parent), "html.parser")
        clone_strong = clone.select_one("strong")
        if clone_strong is not None:
            clone_strong.decompose()
        return _clean_text(clone.get_text(" ", strip=True))
    return None


def _party_section(section: Tag) -> list[dict[str, Any]]:
    parties: list[dict[str, Any]] = []
    for group_heading in section.select("h4"):
        party_type = _clean_text(group_heading.get_text(" ", strip=True))
        container = group_heading.find_parent("div")
        if not party_type or not isinstance(container, Tag):
            continue
        for item in container.select("ul li"):
            name = _clean_text(item.get_text(" ", strip=True))
            if name:
                parties.append(
                    {
                        "party_type": party_type.upper(),
                        "name": name,
                    }
                )
    if parties:
        return parties

    for container in section.select(".column"):
        heading = container.select_one("label, strong")
        party_type = (
            _clean_text(heading.get_text(" ", strip=True))
            if heading is not None
            else None
        )
        if not party_type:
            continue
        for item in container.select("p"):
            name = _clean_text(item.get_text(" ", strip=True))
            if name:
                parties.append(
                    {
                        "party_type": party_type.upper(),
                        "name": name,
                    }
                )
    return parties


def _legal_section(section: Tag) -> list[dict[str, Any]]:
    legal_descriptions: list[dict[str, Any]] = []
    for table in section.select("table"):
        headers = [
            _clean_text(header.get_text(" ", strip=True))
            for header in table.select("thead th")
        ]
        normalized_headers = [
            header or f"field_{index + 1}" for index, header in enumerate(headers)
        ]
        for row in table.select("tbody tr"):
            cells = [
                _clean_text(cell.get_text(" ", strip=True))
                for cell in row.select("th,td")
            ]
            if cells:
                legal_descriptions.append(
                    {
                        normalized_headers[index]: value
                        for index, value in enumerate(cells)
                        if index < len(normalized_headers)
                    }
                )
    return legal_descriptions


def _dedupe_mappings(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    values: list[dict[str, Any]] = []
    for record in records:
        key = canonical_json(dict(record))
        if key in seen:
            continue
        seen.add(key)
        values.append(dict(record))
    return values


def _parse_titles(
    soup: BeautifulSoup,
    *,
    tenant: HelionTenant,
    year: int | None,
    document: int | None,
    selected_title: int | None,
    fallback_document_type: str | None,
    fallback_consideration: str | None,
) -> list[dict[str, Any]]:
    panes: list[Tag] = list(soup.select(".tab-pane"))
    scopes: list[Tag | BeautifulSoup] = panes or [soup]
    titles: list[dict[str, Any]] = []
    for index, scope in enumerate(scopes, start=1):
        scope_id = scope.get("id") if isinstance(scope, Tag) else None
        id_match = re.fullmatch(r"tab_(\d+)", str(scope_id or ""), re.I)
        title_selector = (
            int(id_match.group(1))
            if id_match
            else (selected_title if selected_title is not None else index)
        )
        title_heading = (
            scope.find("h2", recursive=False) if isinstance(scope, Tag) else None
        )
        title_label = (
            _clean_text(title_heading.get_text(" ", strip=True))
            if title_heading is not None
            else f"Title {title_selector}"
        )
        sections = (
            scope.find_all("div", class_="tab-section", recursive=False)
            if panes
            else soup.select(".tab-section")
        )
        parties: list[dict[str, Any]] = []
        legal_descriptions: list[dict[str, Any]] = []
        references_from_document: list[dict[str, Any]] = []
        references_to_document: list[dict[str, Any]] = []
        title_document_type: str | None = None
        title_consideration: str | None = None
        for section in sections:
            heading = section.select_one("h2, h3, h4")
            heading_text = (
                _clean_text(heading.get_text(" ", strip=True))
                if heading is not None
                else None
            )
            if not heading_text:
                continue
            folded = heading_text.casefold()
            if folded == "parties":
                parties.extend(_party_section(section))
            elif folded == "legal descriptions":
                legal_descriptions.extend(_legal_section(section))
            elif "are referenced in this document" in folded:
                references_from_document.extend(_references(section, tenant=tenant))
            elif "make reference to this document" in folded:
                references_to_document.extend(_references(section, tenant=tenant))
            elif not any(
                marker in folded
                for marker in (
                    "does not reference",
                    "no documents",
                    "no references",
                    "custom data",
                )
            ):
                title_document_type = heading_text
                title_consideration = _inline_labeled_value(
                    section,
                    "Consideration",
                )
        resolved_type = title_document_type or fallback_document_type
        resolved_consideration = title_consideration or fallback_consideration
        title_native_key = {
            "year": year,
            "document": document,
            "title": title_selector,
        }
        titles.append(
            {
                "canonical_ref": _canonical_ref(
                    tenant,
                    year=year,
                    document=document,
                    title=title_selector,
                    instrument_number=(
                        f"{year or ''}-{document or ''}-title-{title_selector}"
                    ),
                ),
                "title_selector": title_selector,
                "title_label": title_label,
                "native_title_key": title_native_key,
                "document_type": resolved_type,
                "consideration_raw": resolved_consideration,
                "consideration_amount": _money_string(resolved_consideration),
                "parties": parties,
                "legal_descriptions": legal_descriptions,
                "references_from_document": references_from_document,
                "references_to_document": references_to_document,
            }
        )
    return titles


def parse_detail_html(
    html: str,
    *,
    tenant: HelionTenant,
    source_url: str,
) -> dict[str, Any]:
    """Normalize one verified Helion document-detail response."""

    soup = BeautifulSoup(html, "html.parser")
    instrument_tag = soup.select_one(".label-document-number")
    if instrument_tag is None:
        raise HelionSourceChanged(
            "document detail no longer contains a native document number"
        )
    instrument_number = _clean_text(instrument_tag.get_text(" ", strip=True))
    if not instrument_number:
        raise HelionSourceChanged("document detail number is empty")

    row_values: dict[str, tuple[str, list[str]]] = {}
    for row in soup.select(".margin-bottom-10.row, .margin-bottom.row"):
        parsed = _labeled_row_value(row)
        if parsed is None:
            continue
        label, value, values = parsed
        row_values.setdefault(label.casefold(), (value, values))

    recording_raw = row_values.get("recording date", (None, []))[0]
    document_type = row_values.get("document type", (None, []))[0]
    return_to = row_values.get("return to", (None, []))
    consideration_raw = row_values.get("consideration", (None, []))[0]
    page_count_raw = row_values.get("page count", (None, []))[0]
    page_count = (
        int(page_count_raw)
        if isinstance(page_count_raw, str) and page_count_raw.isdigit()
        else None
    )

    year, document, title = _detail_identity(
        source_url,
        instrument_number,
    )
    titles = _parse_titles(
        soup,
        tenant=tenant,
        year=year,
        document=document,
        selected_title=title,
        fallback_document_type=document_type,
        fallback_consideration=consideration_raw,
    )
    parties = _dedupe_mappings(
        [party for title_record in titles for party in title_record["parties"]]
    )
    legal_descriptions = _dedupe_mappings(
        [
            legal
            for title_record in titles
            for legal in title_record["legal_descriptions"]
        ]
    )
    references_from_document = _dedupe_mappings(
        [
            reference
            for title_record in titles
            for reference in title_record["references_from_document"]
        ]
    )
    references_to_document = _dedupe_mappings(
        [
            reference
            for title_record in titles
            for reference in title_record["references_to_document"]
        ]
    )
    if document_type is None and len(titles) == 1:
        document_type = titles[0]["document_type"]
    if consideration_raw is None and len(titles) == 1:
        consideration_raw = titles[0]["consideration_raw"]

    direct_image = soup.select_one(
        "a.drr-image-link[href*='DocumentImage'], a[href*='/DocumentImage/']"
    )
    direct_text = soup.select_one(
        "a.drr-image-link[href*='DocumentText'], a[href*='/DocumentText/']"
    )
    cart = _cart_metadata(soup, tenant.portal_root)
    copy_options = _copy_options(soup)
    image_url = _absolute(
        tenant.portal_root,
        direct_image.get("href") if direct_image is not None else None,
    )
    text_url = _absolute(
        tenant.portal_root,
        direct_text.get("href") if direct_text is not None else None,
    )
    if image_url:
        image_state = "viewable"
    elif any(
        "non-certified" in str(option.get("label", "")).casefold()
        for option in copy_options
    ):
        image_state = "purchasable"
    else:
        image_state = "not_advertised"
    text_message = _clean_text(
        soup.select_one(".ocr-message").get_text(" ", strip=True)
        if soup.select_one(".ocr-message") is not None
        else None
    )

    e_recorded = soup.select_one("[title*='e-Recorded']") is not None
    if page_count is None and cart is not None:
        page_count = cart.get("page_count")

    schema = {
        "row_labels": sorted(row_values),
        "party_roles": sorted({str(party["party_type"]) for party in parties}),
        "legal_fields": sorted({key for item in legal_descriptions for key in item}),
        "title_count": len(titles),
        "title_document_types": sorted(
            {
                str(title_record["document_type"])
                for title_record in titles
                if title_record["document_type"]
            }
        ),
        "has_direct_image": bool(image_url),
        "has_direct_text": bool(text_url),
        "has_cart": cart is not None,
    }
    return {
        "canonical_ref": _canonical_ref(
            tenant,
            year=year,
            document=document,
            title=title,
            instrument_number=instrument_number,
        ),
        "source_id": tenant.source_id,
        "record_kind": "recorded_instrument_detail",
        "county_name": tenant.county_name,
        "county_fips": tenant.county_fips,
        "instrument_number": instrument_number,
        "recording_year": year,
        "document_selector": document,
        "title_selector": title,
        "native_detail_key": {
            "year": year,
            "document": document,
            "title": title,
        },
        "recording_date_raw": recording_raw,
        "recording_date_local_iso": _recording_local_iso(recording_raw),
        "recording_timezone": "America/Los_Angeles",
        "document_type": document_type,
        "document_types": [title_record["document_type"] for title_record in titles],
        "return_to": return_to[0],
        "return_to_lines": return_to[1],
        "consideration_raw": consideration_raw,
        "consideration_amount": _money_string(consideration_raw),
        "page_count": page_count,
        "e_recorded": e_recorded,
        "title_count": len(titles),
        "titles": titles,
        "parties": parties,
        "legal_descriptions": legal_descriptions,
        "references_from_document": references_from_document,
        "references_to_document": references_to_document,
        "document_image": {
            "availability": image_state,
            "url": image_url,
            "format": "pdf" if image_url else None,
        },
        "text_alternative": {
            "availability": (
                "viewable"
                if text_url
                else ("not_available" if text_message else "not_advertised")
            ),
            "url": text_url,
            "format": "text" if text_url else None,
            "message": text_message,
        },
        "copy_options": copy_options,
        "cart_metadata": cart,
        "source_url": source_url,
        "source_schema": schema,
        "source_schema_fingerprint": sha256_fingerprint(schema),
    }


def _strong_labeled_value(card: Tag, label: str) -> str | None:
    wanted = label.casefold().rstrip(":")
    for label_tag in card.select("strong, span.bold-light"):
        candidate = _clean_text(label_tag.get_text(" ", strip=True))
        if not candidate or candidate.casefold().rstrip(":") != wanted:
            continue
        parent = label_tag.parent
        if not isinstance(parent, Tag):
            continue
        clone = BeautifulSoup(str(parent), "html.parser")
        clone_label = clone.select_one("strong, span.bold-light")
        if clone_label is not None:
            clone_label.decompose()
        return _clean_text(clone.get_text(" ", strip=True))
    return None


def _search_parties(card: Tag) -> list[dict[str, str]]:
    parties: list[dict[str, str]] = []
    for item in card.select(".result-subline"):
        label_tag = item.select_one("strong, span.bold-light")
        if label_tag is None:
            continue
        party_type = _clean_text(label_tag.get_text(" ", strip=True))
        if not party_type:
            continue
        party_type = party_type.rstrip(":").upper()
        if party_type not in {"DIRECT", "INDIRECT"}:
            continue
        clone = BeautifulSoup(str(item), "html.parser")
        clone_label = clone.select_one("strong, span.bold-light")
        if clone_label is not None:
            clone_label.decompose()
        name = _clean_text(clone.get_text(" ", strip=True))
        if name:
            parties.append({"party_type": party_type, "name": name})
    return parties


def _search_map_fields(card: Tag) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for subline in card.select("span.result-subline"):
        hidden = subline.select_one(".visually-hidden")
        if hidden is None:
            continue
        label = _clean_text(hidden.get_text(" ", strip=True))
        if not label:
            continue
        direct_children = [
            _clean_text(child.get_text(" ", strip=True))
            for child in subline.find_all("span", recursive=False)
        ]
        values = [
            value
            for value in direct_children
            if value
            and value.casefold() != label.casefold()
            and value.casefold()
            not in {"sub", "lot", "block", "twp", "rng", "sec", "qq"}
        ]
        if values:
            fields.append({"field": label, "value": values[-1]})
    return fields


def _resource_from_card(
    card: Tag,
    tenant: HelionTenant,
    path_fragment: str,
) -> str | None:
    anchor = card.select_one(f"a[href*='{path_fragment}']")
    return _absolute(
        tenant.portal_root,
        anchor.get("href") if anchor is not None else None,
    )


def _parse_result_card(
    card: Tag,
    *,
    tenant: HelionTenant,
    position: int,
) -> dict[str, Any]:
    detail_anchor = card.select_one("a.recording-link[href]")
    if detail_anchor is None:
        raise HelionSourceChanged(
            "search result no longer contains a recording detail link"
        )
    instrument_number = _clean_text(detail_anchor.get_text(" ", strip=True))
    if not instrument_number:
        raise HelionSourceChanged("search result document number is empty")
    detail_url = _absolute(tenant.portal_root, detail_anchor.get("href"))
    assert detail_url is not None
    year, document, title = _detail_identity(
        detail_url,
        instrument_number,
    )
    references = []
    for anchor in card.select(
        "a.reference-link[href], a[title='View Reference'][href]"
    ):
        href = _absolute(tenant.portal_root, anchor.get("href"))
        reference_number = _clean_text(anchor.get_text(" ", strip=True))
        if href and reference_number:
            ref_year, ref_document, ref_title = _detail_identity(
                href,
                reference_number,
            )
            references.append(
                {
                    "instrument_number": reference_number,
                    "detail_url": href,
                    "native_detail_key": {
                        "year": ref_year,
                        "document": ref_document,
                        "title": ref_title,
                    },
                }
            )
    image_url = _resource_from_card(card, tenant, "DocumentImage")
    text_url = _resource_from_card(card, tenant, "DocumentText")
    recording_raw = _strong_labeled_value(card, "Date Recorded")
    document_type = _strong_labeled_value(card, "Doc Type")
    map_fields = _search_map_fields(card)
    schema = {
        "classes": sorted(
            {
                class_name
                for element in card.find_all(True)
                for class_name in (element.get("class") or [])
                if class_name
                in {
                    "recording-link",
                    "reference-link",
                    "result-subline",
                    "drr-image-link",
                }
            }
        ),
        "map_fields": sorted({str(field["field"]) for field in map_fields}),
    }
    return {
        "canonical_ref": _canonical_ref(
            tenant,
            year=year,
            document=document,
            title=title,
            instrument_number=instrument_number,
        ),
        "source_id": tenant.source_id,
        "record_kind": "recorded_instrument_index",
        "county_name": tenant.county_name,
        "county_fips": tenant.county_fips,
        "instrument_number": instrument_number,
        "recording_year": year,
        "document_selector": document,
        "title_selector": title,
        "native_detail_key": {
            "year": year,
            "document": document,
            "title": title,
        },
        "recording_date_raw": recording_raw,
        "recording_date_local_iso": _recording_local_iso(recording_raw),
        "recording_timezone": "America/Los_Angeles",
        "document_type": document_type,
        "parties": _search_parties(card),
        "map_legal_fields": map_fields,
        "references": references,
        "document_image": {
            "availability": "viewable" if image_url else "not_advertised",
            "url": image_url,
            "format": "pdf" if image_url else None,
        },
        "text_alternative": {
            "availability": "viewable" if text_url else "not_advertised",
            "url": text_url,
            "format": "text" if text_url else None,
        },
        "detail_url": detail_url,
        "search_position": position,
        "source_schema": schema,
        "source_schema_fingerprint": sha256_fingerprint(schema),
    }


def parse_search_html(
    html: str,
    *,
    tenant: HelionTenant,
    source_url: str,
) -> SearchBatch:
    """Normalize a Helion result window, exact-detail redirect, or empty page."""

    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".label-document-number") is not None:
        detail = parse_detail_html(
            html,
            tenant=tenant,
            source_url=source_url,
        )
        return SearchBatch(
            records=(detail,),
            total_results=1,
            start_position=1,
            end_position=1,
            source_url=source_url,
            search_id=None,
            schema_fingerprint=str(detail["source_schema_fingerprint"]),
        )

    text = soup.get_text(" ", strip=True)
    no_match = any(
        marker in text.casefold()
        for marker in (
            "no matching results found",
            "no records found",
            "no results found",
        )
    )
    cards = soup.select(".search-result")
    total_match = re.search(r"([\d,]+)\s+Results?\s+Found", text, re.I)
    display_match = re.search(
        r"Displaying\s+results\s+([\d,]+)\s*-\s*([\d,]+)",
        text,
        re.I,
    )
    if not cards:
        if no_match or (total_match and int(total_match.group(1)) == 0):
            schema = {
                "empty_marker": (
                    "no_matching_results" if no_match else "zero_results_heading"
                )
            }
            return SearchBatch(
                records=(),
                total_results=0,
                start_position=0,
                end_position=0,
                source_url=source_url,
                search_id=None,
                schema_fingerprint=sha256_fingerprint(schema),
                authoritative_empty=True,
            )
        raise HelionSourceChanged(
            "response contains neither result cards, a detail page, nor the "
            "verified no-match marker"
        )

    if total_match is None or display_match is None:
        raise HelionSourceChanged(
            "result page no longer reports total and displayed positions"
        )
    total = int(total_match.group(1).replace(",", ""))
    start = int(display_match.group(1).replace(",", ""))
    end = int(display_match.group(2).replace(",", ""))
    records = tuple(
        _parse_result_card(
            card,
            tenant=tenant,
            position=start + index,
        )
        for index, card in enumerate(cards)
    )
    if end - start + 1 != len(records):
        raise HelionSourceChanged(
            "displayed result range does not match parsed result cards"
        )
    search_id_input = soup.select_one(
        "form[action*='NextResults'] input[name='SearchId']"
    )
    search_id = (
        str(search_id_input.get("value")) if search_id_input is not None else None
    )
    schema = {
        "card_count": len(cards),
        "has_continuation_form": search_id_input is not None,
        "card_schema_fingerprints": sorted(
            {str(record["source_schema_fingerprint"]) for record in records}
        ),
    }
    return SearchBatch(
        records=records,
        total_results=total,
        start_position=start,
        end_position=end,
        source_url=source_url,
        search_id=search_id,
        schema_fingerprint=sha256_fingerprint(schema),
    )


class HelionRecorderClient:
    """Cookie-preserving client for the verified Helion public workflow."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        minimum_interval: float = DEFAULT_MINIMUM_INTERVAL,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
        session: requests.Session | None = None,
    ) -> None:
        self.timeout = timeout
        self.minimum_interval = max(0.0, minimum_interval)
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff = max(0.0, retry_backoff)
        self.session = session or system_trust_session()
        self.session.headers.setdefault(
            "User-Agent",
            "Ithildin public-records research adapter "
            "(contact via repository maintainers)",
        )
        self._last_request_at = 0.0
        self._owns_session = session is None

    def close(self) -> None:
        if self._owns_session:
            self.session.close()

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self.minimum_interval:
                time.sleep(self.minimum_interval - elapsed)
            try:
                response = self.session.request(
                    method,
                    url,
                    data=data,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                self._last_request_at = time.monotonic()
            except requests.RequestException as error:
                self._last_request_at = time.monotonic()
                last_error = error
                if attempt + 1 < self.max_attempts:
                    time.sleep(self.retry_backoff * (2**attempt))
                    continue
                raise HelionTransportError(str(error)) from error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < self.max_attempts:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else None
                    except ValueError:
                        delay = None
                    time.sleep(
                        delay
                        if delay is not None
                        else self.retry_backoff * (2**attempt)
                    )
                    continue
            if response.status_code >= 400:
                raise HelionHTTPError(
                    response.status_code,
                    response.url,
                    f"Helion returned HTTP {response.status_code}",
                )
            return response
        raise HelionTransportError(str(last_error or "request failed"))

    @staticmethod
    def _form_with_field(
        soup: BeautifulSoup,
        field_name: str,
    ) -> Tag | None:
        for form in soup.select("form"):
            if form.select_one(f"[name='{field_name}']") is not None:
                return form
        return None

    @staticmethod
    def _hidden_fields(form: Tag) -> dict[str, str]:
        values: dict[str, str] = {}
        for element in form.select("input[type='hidden'][name]"):
            name = element.get("name")
            if name:
                values[str(name)] = str(element.get("value") or "")
        return values

    def _post_form(
        self,
        response: requests.Response,
        form: Tag,
        *,
        overrides: Mapping[str, Any] | None = None,
    ) -> requests.Response:
        payload: dict[str, Any] = self._hidden_fields(form)
        payload.update(dict(overrides or {}))
        action = urljoin(response.url, str(form.get("action") or response.url))
        return self._request("POST", action, data=payload)

    def _advanced_url(self, tenant: HelionTenant) -> str:
        separator = "&" if "?" in tenant.search_url else "?"
        return f"{tenant.search_url}{separator}mode=Advanced"

    def acquire_search_form(
        self,
        tenant: HelionTenant,
    ) -> tuple[requests.Response, BeautifulSoup, Tag]:
        response = self._request("GET", self._advanced_url(tenant))
        for _ in range(4):
            soup = BeautifulSoup(response.text, "html.parser")
            form = self._form_with_field(
                soup,
                "Criteria.Filter.YearStart",
            )
            if form is not None and "disclaimer" not in response.url.casefold():
                return response, soup, form

            page_text = soup.get_text(" ", strip=True)
            if "disclaimer" in response.url.casefold() or re.search(
                r"\bDisclaimer\b", page_text[:2500], re.I
            ):
                if (
                    "recaptcha" in response.text.casefold()
                    or "verify that you are not a robot" in page_text.casefold()
                ):
                    raise HelionHumanRequired(
                        "The live county disclaimer requires browser "
                        "JavaScript/reCAPTCHA before the search session.",
                        url=response.url,
                    )
                disclaimer_form = soup.select_one("form")
                if disclaimer_form is None:
                    raise HelionSourceChanged(
                        "disclaimer page no longer contains an agreement form"
                    )
                response = self._post_form(response, disclaimer_form)
                continue

            redirect_form = soup.select_one("form#redirect-form")
            if redirect_form is not None:
                response = self._post_form(response, redirect_form)
                continue

            if response.url.rstrip("/") != tenant.search_url.rstrip("/"):
                response = self._request("GET", self._advanced_url(tenant))
                continue
            if tenant.search_path:
                response = self._request("GET", self._advanced_url(tenant))
                continue
            break
        soup = BeautifulSoup(response.text, "html.parser")
        raise HelionSourceChanged(
            "could not reach the verified advanced-search form at "
            f"{response.url}; page title was "
            f"{_clean_text(soup.title.get_text(' ', strip=True)) if soup.title else None}"
        )

    @staticmethod
    def _control_names(form: Tag) -> set[str]:
        return {
            str(element.get("name"))
            for element in form.select("[name]")
            if element.get("name")
        }

    @staticmethod
    def _validate_option(
        form: Tag,
        field_name: str,
        value: str,
    ) -> None:
        control = form.select_one(f"select[name='{field_name}']")
        if control is None:
            return
        allowed = {
            str(option.get("value") or "") for option in control.select("option")
        }
        if value not in allowed:
            raise HelionSelectionError(
                "selector_value_not_supported",
                f"{field_name} value {value!r} is not offered by this tenant",
                details={
                    "field_name": field_name,
                    "selected_value": value,
                },
            )

    def _search_payload(
        self,
        form: Tag,
        selectors: Mapping[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = self._hidden_fields(form)
        controls = self._control_names(form)
        for selector, field_name in SELECTOR_FIELDS.items():
            value = selectors.get(selector)
            if value in (None, ""):
                continue
            if field_name not in controls:
                raise HelionSelectionError(
                    "selector_not_supported_by_tenant",
                    f"{selector.replace('_', '-')} is not present in this "
                    "tenant's live search form",
                    details={
                        "selector": selector,
                        "field_name": field_name,
                    },
                )
            rendered = str(value)
            self._validate_option(form, field_name, rendered)
            payload[field_name] = rendered

        party_type = str(selectors.get("party_type") or "all")
        view = str(selectors.get("view") or "document")
        direction = str(selectors.get("direction") or "ascending")
        sort = str(
            selectors.get("sort")
            or (
                "party-name"
                if view == "party"
                else ("subdivision-lot-block" if view == "map" else "document-number")
            )
        )
        payload["Criteria.Filter.PartyType"] = PARTY_TYPE_VALUES[party_type]
        payload["Criteria.View"] = VIEW_VALUES[view]
        payload["Criteria.OrderBy.CurrentSort"] = SORT_VALUES[sort]
        payload["Criteria.OrderBy.CurrentDirection"] = DIRECTION_VALUES[direction]
        return payload

    def search(
        self,
        tenant: HelionTenant,
        selectors: Mapping[str, Any],
        *,
        start: int = 1,
        number_to_show: int = SOURCE_PAGE_SIZE,
    ) -> SearchBatch:
        response, _soup, form = self.acquire_search_form(tenant)
        payload = self._search_payload(form, selectors)
        action = urljoin(
            response.url,
            str(form.get("action") or tenant.search_url),
        )
        result = self._request("POST", action, data=payload)
        batch = parse_search_html(
            result.text,
            tenant=tenant,
            source_url=result.url,
        )
        if start <= 1 or batch.total_results <= 1:
            return batch

        result_soup = BeautifulSoup(result.text, "html.parser")
        continuation = result_soup.select_one("form[action*='NextResults']")
        if continuation is None:
            raise HelionSourceChanged(
                "result continuation form is missing for a requested offset"
            )
        continuation_payload = self._hidden_fields(continuation)
        continuation_payload.update(
            {
                "Start": str(start),
                "NumberToShow": str(number_to_show),
                "ViewType": VIEW_VALUES[str(selectors.get("view") or "document")],
            }
        )
        continuation_url = urljoin(
            result.url,
            str(continuation.get("action")),
        )
        page = self._request(
            "POST",
            continuation_url,
            data=continuation_payload,
        )
        return parse_search_html(
            page.text,
            tenant=tenant,
            source_url=page.url,
        )

    def detail(
        self,
        tenant: HelionTenant,
        *,
        year: int,
        document: int,
        title: int | None = None,
    ) -> Mapping[str, Any]:
        self.acquire_search_form(tenant)
        query: dict[str, Any] = {"year": year, "document": document}
        if title is not None:
            query["Title"] = title
        detail_url = urljoin(tenant.portal_root, "Document/Details")
        response = self._request(
            "GET",
            f"{detail_url}?{urlencode(query)}",
        )
        return parse_detail_html(
            response.text,
            tenant=tenant,
            source_url=response.url,
        )

    def probe(self, tenant: HelionTenant) -> Mapping[str, Any]:
        response, soup, form = self.acquire_search_form(tenant)
        text = soup.get_text(" ", strip=True)
        indexed = re.search(
            r"Documents have been indexed through\s+([0-9/]+)",
            text,
            re.I,
        )
        fields = sorted(self._control_names(form))
        options: dict[str, list[dict[str, str]]] = {}
        for select in form.select("select[name]"):
            name = str(select.get("name"))
            options[name] = [
                {
                    "value": str(option.get("value") or ""),
                    "label": _clean_text(option.get_text(" ", strip=True)) or "",
                }
                for option in select.select("option")
            ]
        schema = {
            "form_action": form.get("action"),
            "form_method": str(form.get("method") or "get").lower(),
            "fields": fields,
            "select_option_counts": {key: len(value) for key, value in options.items()},
        }
        return {
            "canonical_ref": f"ORREC_PROBE:{tenant.county_fips}",
            "source_id": tenant.source_id,
            "record_kind": "source_probe",
            "county_name": tenant.county_name,
            "county_fips": tenant.county_fips,
            "status": "ok",
            "search_url": response.url,
            "search_action": _absolute(
                response.url,
                str(form.get("action") or response.url),
            ),
            "search_method": str(form.get("method") or "get").lower(),
            "indexed_through_raw": indexed.group(1) if indexed else None,
            "form_fields": fields,
            "select_options": options,
            "source_schema": schema,
            "source_schema_fingerprint": sha256_fingerprint(schema),
        }


def _date_selector(value: Any, flag: str) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError as error:
        raise HelionSelectionError(
            "invalid_date_selector",
            f"{flag} must be YYYY-MM-DD",
            details={"value": str(value)},
        ) from error


def selectors_from_args(args: argparse.Namespace) -> dict[str, Any]:
    limit = getattr(args, "limit", None)
    if (
        limit is not None
        and (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
        )
    ):
        raise HelionSelectionError(
            "invalid_limit",
            "--limit must be a positive integer",
        )
    selectors = {name: getattr(args, name, None) for name in SELECTOR_FIELDS}
    selectors["recorded_from"] = _date_selector(
        selectors["recorded_from"],
        "--recorded-from",
    )
    selectors["recorded_to"] = _date_selector(
        selectors["recorded_to"],
        "--recorded-to",
    )
    if (
        selectors["recorded_from"]
        and selectors["recorded_to"]
        and selectors["recorded_from"] > selectors["recorded_to"]
    ):
        raise HelionSelectionError(
            "invalid_date_range",
            "--recorded-from cannot be after --recorded-to",
        )
    for name in ("year", "document_from", "document_to"):
        value = selectors.get(name)
        if value is not None and value < 0:
            raise HelionSelectionError(
                "invalid_numeric_selector",
                f"--{name.replace('_', '-')} cannot be negative",
            )
    if (
        selectors["document_from"] is not None
        and selectors["document_to"] is not None
        and selectors["document_from"] > selectors["document_to"]
    ):
        raise HelionSelectionError(
            "invalid_document_range",
            "--document-from cannot be after --document-to",
        )
    selectors.update(
        {
            "party_type": getattr(args, "party_type", "all"),
            "view": getattr(args, "view", "document"),
            "sort": getattr(args, "sort", None),
            "direction": getattr(args, "direction", "ascending"),
        }
    )
    if not any(selectors.get(name) not in (None, "") for name in SELECTOR_FIELDS):
        raise HelionSelectionError(
            "missing_search_selector",
            "search requires at least one document, party, date, map, or "
            "legal selector",
        )
    return selectors


def _query_fingerprint(
    tenant: HelionTenant,
    selectors: Mapping[str, Any],
) -> str:
    return sha256_fingerprint(
        {
            "source_id": tenant.source_id,
            "selectors": dict(selectors),
        }
    )


def _encode_cursor(state: CursorState) -> str:
    payload = {
        "v": 1,
        "source_id": state.source_id,
        "query_fingerprint": state.query_fingerprint,
        "offset": state.offset,
        "anchor": state.anchor,
        "total_results": state.total_results,
    }
    token = (
        base64.urlsafe_b64encode(canonical_json(payload).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{CURSOR_PREFIX}{token}"


def _decode_cursor(
    cursor: str,
    *,
    tenant: HelionTenant,
    query_fingerprint: str,
) -> CursorState:
    if not cursor.startswith(CURSOR_PREFIX):
        raise HelionSelectionError(
            "cursor_invalid",
            "cursor does not use the Oregon Helion continuation format",
            status=ResultStatus.SOURCE_CHANGED,
        )
    token = cursor[len(CURSOR_PREFIX) :]
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HelionSelectionError(
            "cursor_invalid",
            "cursor payload is malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    if not isinstance(payload, Mapping) or payload.get("v") != 1:
        raise HelionSelectionError(
            "cursor_invalid",
            "cursor version is not supported",
            status=ResultStatus.SOURCE_CHANGED,
        )
    if payload.get("source_id") != tenant.source_id:
        raise HelionSelectionError(
            "cursor_source_mismatch",
            "cursor belongs to another county source",
            status=ResultStatus.SOURCE_CHANGED,
            details={
                "cursor_source_id": payload.get("source_id"),
                "query_source_id": tenant.source_id,
            },
        )
    if payload.get("query_fingerprint") != query_fingerprint:
        raise HelionSelectionError(
            "cursor_query_mismatch",
            "cursor belongs to different search selectors",
            status=ResultStatus.SOURCE_CHANGED,
        )
    try:
        offset = int(payload["offset"])
        total = int(payload["total_results"])
        anchor = str(payload["anchor"])
    except (KeyError, TypeError, ValueError) as error:
        raise HelionSelectionError(
            "cursor_invalid",
            "cursor boundary fields are malformed",
            status=ResultStatus.SOURCE_CHANGED,
        ) from error
    if offset <= 0 or total < offset or not anchor:
        raise HelionSelectionError(
            "cursor_invalid",
            "cursor boundary values are inconsistent",
            status=ResultStatus.SOURCE_CHANGED,
        )
    return CursorState(
        source_id=tenant.source_id,
        query_fingerprint=query_fingerprint,
        offset=offset,
        anchor=anchor,
        total_results=total,
    )


def _tenant(args: argparse.Namespace) -> HelionTenant:
    source_id = getattr(args, "source", None)
    if source_id not in TENANTS_BY_SOURCE:
        raise HelionSelectionError(
            "source_not_selected",
            "select one Oregon Helion county source",
        )
    return TENANTS_BY_SOURCE[str(source_id)]


def _source_record(tenant: HelionTenant) -> dict[str, Any]:
    return {
        "canonical_ref": f"ORREC_SOURCE:{tenant.county_fips}",
        "source_id": tenant.source_id,
        "record_kind": "source_metadata",
        "name": tenant.name,
        "authority": tenant.authority,
        "county_name": tenant.county_name,
        "county_fips": tenant.county_fips,
        "portal_root": tenant.portal_root,
        "search_url": tenant.search_url,
        "official_linking_page": tenant.official_linking_page,
        "access_observation": tenant.access_observation,
        "captcha_observed": tenant.captcha_observed,
        "coverage_observation": tenant.coverage_observation,
        "resource_observation": tenant.resource_observation,
        "complement_observations": [
            dict(value) for value in tenant.complement_observations
        ],
    }


def build_query(
    args: argparse.Namespace,
    *,
    selectors: Mapping[str, Any] | None = None,
    decision: Mapping[str, Any] | None = None,
) -> PublicRecordsQuery:
    tenant = _tenant(args)
    requested_limit = getattr(args, "limit", None) if args.command == "search" else None
    if requested_limit is not None and (
        isinstance(requested_limit, bool)
        or not isinstance(requested_limit, int)
        or requested_limit <= 0
    ):
        requested_limit = None
    parameters: dict[str, Any] = {
        "tenant_key": tenant.key,
        "platform_family": PLATFORM_FAMILY,
    }
    if args.command == "search":
        parameters.update(
            {
                "selectors": dict(selectors or {}),
                "cursor": getattr(args, "cursor", None),
                "continuation": ("query_bound_with_native_boundary_anchor"),
            }
        )
    elif args.command == "detail":
        parameters["native_detail_key"] = {
            "year": args.year,
            "document": args.document,
            "title": args.title,
        }
    return PublicRecordsQuery(
        source=tenant.source_metadata,
        jurisdiction=tenant.jurisdiction,
        query=QueryMetadata(
            operation=args.command,
            parameters=parameters,
            requested_limit=requested_limit,
            cursor=(
                getattr(args, "cursor", None) if args.command == "search" else None
            ),
            metadata={"access_decision": dict(decision or {})},
        ),
    )


def _decision_failure(
    query: PublicRecordsQuery,
    decision: Mapping[str, Any],
) -> PublicRecordsResult:
    disposition = str(
        decision.get("automation_disposition") or decision.get("disposition") or ""
    ).casefold()
    if disposition in {"human_required", "manual_only"}:
        status = ResultStatus.HUMAN_REQUIRED
    elif disposition in {"prohibited", "terms_blocked"}:
        status = ResultStatus.TERMS_BLOCKED
    elif disposition in {"restricted", "subscription"}:
        status = ResultStatus.RESTRICTED
    else:
        status = ResultStatus.UNAVAILABLE
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=str(
                    decision.get("reason_code") or "machine_acquisition_unavailable"
                ),
                message=str(
                    decision.get("reason")
                    or "The supplied access decision does not allow this route."
                ),
                category="source_access",
                retryable=False,
                details={"access_decision": dict(decision)},
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _failure(
    query: PublicRecordsQuery,
    error: Exception,
) -> PublicRecordsResult:
    details: dict[str, Any] = {}
    if isinstance(error, HelionSelectionError):
        return PublicRecordsResult.failure(
            query,
            error.status,
            [
                PublicRecordsError(
                    code=error.code,
                    message=str(error),
                    category="query_selection",
                    retryable=False,
                    details=error.details,
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
    if isinstance(error, HelionHumanRequired):
        status = ResultStatus.HUMAN_REQUIRED
        code = "recaptcha_session_required"
        category = "source_access"
        retryable = False
        details = {"resume_url": error.url}
    elif isinstance(error, HelionSourceChanged):
        status = ResultStatus.SOURCE_CHANGED
        code = "source_schema_changed"
        category = "source_schema"
        retryable = False
    elif isinstance(error, HelionHTTPError):
        details = {
            "status_code": error.status_code,
            "source_url": error.url,
        }
        if error.status_code == 429:
            status = ResultStatus.RATE_LIMITED
            code = "source_rate_limited"
            category = "rate_limit"
            retryable = True
        elif error.status_code in {401, 403}:
            status = ResultStatus.RESTRICTED
            code = f"source_http_{error.status_code}"
            category = "authentication"
            retryable = False
        elif error.status_code in {404, 410}:
            status = ResultStatus.SOURCE_CHANGED
            code = f"source_http_{error.status_code}"
            category = "source_route"
            retryable = False
        else:
            status = ResultStatus.UNAVAILABLE
            code = f"source_http_{error.status_code}"
            category = "http"
            retryable = error.status_code >= 500
    elif isinstance(error, HelionTransportError):
        status = ResultStatus.UNAVAILABLE
        code = "source_transport_failed"
        category = "transport"
        retryable = True
    else:
        status = ResultStatus.SOURCE_CHANGED
        code = "normalization_failed"
        category = "source_schema"
        retryable = False
    return PublicRecordsResult.failure(
        query,
        status,
        [
            PublicRecordsError(
                code=code,
                message=str(error),
                category=category,
                retryable=retryable,
                details=details,
            )
        ],
        warnings=SOURCE_WARNINGS,
    )


def _search_result(
    query: PublicRecordsQuery,
    tenant: HelionTenant,
    selectors: Mapping[str, Any],
    client: Any,
    *,
    limit: int | None,
    cursor: str | None,
) -> PublicRecordsResult:
    fingerprint = _query_fingerprint(tenant, selectors)
    state = (
        _decode_cursor(
            cursor,
            tenant=tenant,
            query_fingerprint=fingerprint,
        )
        if cursor
        else None
    )
    start = state.offset if state is not None else 1
    batch = client.search(
        tenant,
        selectors,
        start=start,
        number_to_show=SOURCE_PAGE_SIZE,
    )
    if batch.authoritative_empty:
        if state is not None:
            raise HelionSelectionError(
                "cursor_result_set_changed",
                "the resumed query is now empty",
                status=ResultStatus.SOURCE_CHANGED,
            )
        return PublicRecordsResult.success(
            query,
            [],
            warnings=SOURCE_WARNINGS,
        )

    records = list(batch.records)
    count_changed = state is not None and state.total_results != batch.total_results
    anchor_verified = state is None
    consumed_before = state.offset if state is not None else 0
    if state is not None:
        anchor_index = state.offset - batch.start_position
        if anchor_index < 0 or anchor_index >= len(records):
            raise HelionSelectionError(
                "cursor_anchor_not_in_window",
                "source continuation window does not contain the prior boundary record",
                status=ResultStatus.SOURCE_CHANGED,
            )
        observed_anchor = _native_key(records[anchor_index])
        if observed_anchor != state.anchor:
            raise HelionSelectionError(
                "cursor_anchor_mismatch",
                "the prior boundary record changed before continuation",
                status=ResultStatus.SOURCE_CHANGED,
                details={
                    "expected_anchor": state.anchor,
                    "observed_anchor": observed_anchor,
                },
            )
        anchor_verified = True
        records = records[anchor_index + 1 :]
    else:
        first_index = max(0, 1 - batch.start_position)
        records = records[first_index:]

    target_count = (
        limit
        if limit is not None
        else max(batch.total_results - consumed_before, 0)
    )
    collected = records[:target_count]
    while (
        len(collected) < target_count
        and consumed_before + len(collected) < batch.total_results
    ):
        next_start = consumed_before + len(collected) + 1
        next_batch = client.search(
            tenant,
            selectors,
            start=next_start,
            number_to_show=SOURCE_PAGE_SIZE,
        )
        if next_batch.total_results != batch.total_results:
            count_changed = True
        if not next_batch.records:
            break
        needed = target_count - len(collected)
        next_records = list(next_batch.records)
        first_index = max(0, next_start - next_batch.start_position)
        new_records = next_records[first_index : first_index + needed]
        if not new_records:
            break
        collected.extend(new_records)

    new_offset = consumed_before + len(collected)
    next_cursor = None
    if collected and new_offset < batch.total_results:
        next_cursor = _encode_cursor(
            CursorState(
                source_id=tenant.source_id,
                query_fingerprint=fingerprint,
                offset=new_offset,
                anchor=_native_key(collected[-1]),
                total_results=batch.total_results,
            )
        )
    coverage = {
        "source_reported_total_results": batch.total_results,
        "returned_start_position": (consumed_before + 1 if collected else None),
        "returned_end_position": new_offset if collected else None,
        "records_returned": len(collected),
        "source_window_size": SOURCE_PAGE_SIZE,
        "source_show_maximum": SOURCE_SHOW_MAXIMUM,
        "caller_limit": limit,
        "completion_mode": (
            "caller_selected_limit"
            if limit is not None
            else "source_reported_total"
        ),
        "cursor_anchor_verified": anchor_verified,
        "count_changed_since_cursor": count_changed,
        "complete_for_selected_query": (
            bool(collected) and new_offset >= batch.total_results and not count_changed
        ),
    }
    normalized = []
    for record in collected:
        item = dict(record)
        item["search_metadata"] = {
            "coverage": coverage,
            "query_fingerprint": fingerprint,
        }
        normalized.append(item)

    if count_changed:
        return PublicRecordsResult.failure(
            query,
            ResultStatus.PARTIAL,
            [
                PublicRecordsError(
                    code="result_count_changed_during_continuation",
                    message=(
                        "The source-reported result count changed while "
                        "resuming the query; the boundary anchor still matched."
                    ),
                    category="pagination",
                    retryable=True,
                    details=coverage,
                )
            ],
            records=normalized,
            next_cursor=next_cursor,
            warnings=SOURCE_WARNINGS,
        )
    return PublicRecordsResult.success(
        query,
        normalized,
        next_cursor=next_cursor,
        warnings=SOURCE_WARNINGS,
    )


def _make_client(
    args: argparse.Namespace,
    decision: Mapping[str, Any] | None,
) -> HelionRecorderClient:
    limits = (
        decision.get("limits")
        if decision is not None and isinstance(decision.get("limits"), Mapping)
        else {}
    )
    reviewed_interval = float((limits or {}).get("minimum_interval_seconds") or 0)
    return HelionRecorderClient(
        timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)),
        minimum_interval=max(
            float(
                getattr(
                    args,
                    "minimum_interval",
                    DEFAULT_MINIMUM_INTERVAL,
                )
            ),
            reviewed_interval,
        ),
        max_attempts=int(getattr(args, "max_attempts", DEFAULT_MAX_ATTEMPTS)),
        retry_backoff=float(getattr(args, "retry_backoff", DEFAULT_RETRY_BACKOFF)),
    )


def _log(
    query: PublicRecordsQuery,
    source_id: str,
    count: int | None,
) -> None:
    try:
        log_search(canonical_json(query.to_dict()), source_id, count)
    except Exception as error:
        print(f"Warning: could not log search: {error}", file=sys.stderr)


def execute(
    args: argparse.Namespace,
    *,
    catalog_decision: Mapping[str, Any] | None = None,
    access_decision: Mapping[str, Any] | None = None,
    client: HelionRecorderClient | Any | None = None,
    log_results: bool = True,
) -> PublicRecordsResult:
    """Execute one tenant operation through the public-record contract."""

    if catalog_decision is not None and access_decision is not None:
        raise ValueError("pass catalog_decision or access_decision, not both")
    decision = catalog_decision if catalog_decision is not None else access_decision
    tenant = _tenant(args)
    try:
        selectors = selectors_from_args(args) if args.command == "search" else None
        query = build_query(
            args,
            selectors=selectors,
            decision=decision,
        )
    except HelionSelectionError as error:
        query = build_query(args, decision=decision)
        result = _failure(query, error)
        if log_results:
            _log(query, tenant.source_id, None)
        return result

    if (
        decision is not None
        and decision.get("source_id") is not None
        and decision.get("source_id") != tenant.source_id
    ):
        result = PublicRecordsResult.failure(
            query,
            ResultStatus.UNAVAILABLE,
            [
                PublicRecordsError(
                    code="catalog_decision_source_mismatch",
                    message="Catalog decision belongs to another county source",
                    category="source_access",
                    retryable=False,
                    details={
                        "decision_source_id": decision.get("source_id"),
                        "query_source_id": tenant.source_id,
                    },
                )
            ],
            warnings=SOURCE_WARNINGS,
        )
        if log_results:
            _log(query, tenant.source_id, None)
        return result
    if decision is not None and not decision.get("allowed", False):
        result = _decision_failure(query, decision)
        if log_results:
            _log(query, tenant.source_id, None)
        return result

    source_client = client or _make_client(args, decision)
    owns_client = client is None
    try:
        if args.command == "source":
            result = PublicRecordsResult.success(
                query,
                [_source_record(tenant)],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "probe":
            result = PublicRecordsResult.success(
                query,
                [source_client.probe(tenant)],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "detail":
            record = source_client.detail(
                tenant,
                year=args.year,
                document=args.document,
                title=args.title,
            )
            result = PublicRecordsResult.success(
                query,
                [record],
                warnings=SOURCE_WARNINGS,
            )
        elif args.command == "search":
            assert selectors is not None
            limit = args.limit
            if limit is not None and (
                isinstance(limit, bool)
                or not isinstance(limit, int)
                or limit <= 0
            ):
                raise HelionSelectionError(
                    "invalid_limit",
                    "--limit must be a positive integer",
                )
            result = _search_result(
                query,
                tenant,
                selectors,
                source_client,
                limit=limit,
                cursor=args.cursor,
            )
        else:
            raise HelionSelectionError(
                "unsupported_command",
                f"unsupported command: {args.command}",
            )
    except (
        HelionRecorderError,
        TypeError,
        ValueError,
    ) as error:
        result = _failure(query, error)
    finally:
        if owns_client:
            source_client.close()

    if log_results:
        count = (
            len(result.records)
            if result.status
            in {
                ResultStatus.OK,
                ResultStatus.NO_RESULTS,
                ResultStatus.PARTIAL,
            }
            else None
        )
        _log(query, tenant.source_id, count)
    return result


def _add_source(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", required=True, choices=SOURCE_IDS)


def _add_runtime(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=DEFAULT_MINIMUM_INTERVAL,
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=DEFAULT_RETRY_BACKOFF,
    )
    add_output_args(parser)


def _add_search_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--year", type=int)
    parser.add_argument("--document-from", type=int)
    parser.add_argument("--document-to", type=int)
    parser.add_argument("--recorded-from")
    parser.add_argument("--recorded-to")
    parser.add_argument("--historic-number")
    parser.add_argument("--document-type-key")
    parser.add_argument("--subtype-key")
    parser.add_argument("--last-name")
    parser.add_argument("--first-name")
    parser.add_argument("--middle-name")
    parser.add_argument("--suffix")
    parser.add_argument(
        "--party-type",
        choices=tuple(PARTY_TYPE_VALUES),
        default="all",
    )
    parser.add_argument("--property-id")
    parser.add_argument("--subdivision")
    parser.add_argument(
        "--legal-1",
        help="Tenant-native first subdivision legal field (often lot or block)",
    )
    parser.add_argument(
        "--legal-2",
        help="Tenant-native second subdivision legal field (often block or lot)",
    )
    parser.add_argument("--township")
    parser.add_argument("--range")
    parser.add_argument("--section")
    parser.add_argument("--quarter-quarter")
    parser.add_argument("--taxlot")
    parser.add_argument("--legal-description")
    parser.add_argument("--comments")
    parser.add_argument(
        "--view",
        choices=tuple(VIEW_VALUES),
        default="document",
    )
    parser.add_argument("--sort", choices=tuple(SORT_VALUES))
    parser.add_argument(
        "--direction",
        choices=tuple(DIRECTION_VALUES),
        default="ascending",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=(
            "Optional caller-selected result ceiling; omitted traverses the "
            "source-reported result set"
        ),
    )
    parser.add_argument("--cursor")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Query distinct Oregon county Helion Digital Research Room sources"
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    source = subparsers.add_parser(
        "source",
        help="Show one county source, observed access, and complements",
    )
    _add_source(source)
    _add_runtime(source)

    probe = subparsers.add_parser(
        "probe",
        help="Probe the live advanced-search form and index freshness",
    )
    _add_source(probe)
    _add_runtime(probe)

    search = subparsers.add_parser(
        "search",
        help="Search one county's recorded-document index",
    )
    _add_source(search)
    _add_search_selectors(search)
    _add_runtime(search)

    detail = subparsers.add_parser(
        "detail",
        help="Fetch one native year/document/title detail",
    )
    _add_source(detail)
    detail.add_argument("year", type=int)
    detail.add_argument("document", type=int)
    detail.add_argument("--title", type=int)
    _add_runtime(detail)
    return parser


def _emit(
    result: PublicRecordsResult,
    args: argparse.Namespace,
) -> None:
    payload = result.to_dict()
    tenant = TENANTS_BY_SOURCE[args.source]
    if write_output(
        payload,
        args,
        summary=(f"{tenant.county_name} Helion {args.command} ({result.status.value})"),
    ):
        return
    if getattr(args, "json_out", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(
        f"{tenant.name} {args.command}: {result.status.value} "
        f"({len(result.records)} records)"
    )
    if result.next_cursor:
        print(f"Next cursor: {result.next_cursor}")
    for record in result.records:
        print(
            "  "
            f"{record.get('instrument_number') or record.get('name') or '?'} "
            f"| {record.get('record_kind') or '?'}"
        )
    for error in result.errors:
        print(f"ERROR [{error.code}]: {error.message}", file=sys.stderr)


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = execute(args)
    except (HelionRecorderError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    _emit(result, args)
    if result.status not in {
        ResultStatus.OK,
        ResultStatus.NO_RESULTS,
        ResultStatus.PARTIAL,
    }:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
