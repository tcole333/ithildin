"""
Pydantic models for SEC filings data extraction.
"""

from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FilingType(str, Enum):
    """SEC filing form types."""
    FORM_13D = "13D"
    FORM_13G = "13G"
    FORM_14D_1 = "14D-1"
    FORM_14D_9 = "14D-9"
    FORM_13F = "13F"
    FORM_3 = "3"
    FORM_4 = "4"
    FORM_5 = "5"
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"
    FORM_8K = "8-K"
    PROXY = "DEF 14A"
    OTHER = "OTHER"


class FilingStatus(str, Enum):
    """Status of the filing."""
    NEW = "new"
    AMENDMENT = "amendment"
    REVISION = "revision"


class Company(BaseModel):
    """Target company in a filing."""
    name: str = Field(..., description="Company name")
    ticker: Optional[str] = Field(None, description="Stock ticker symbol")
    cusip: Optional[str] = Field(None, description="CUSIP number")
    sic_code: Optional[str] = Field(None, description="SIC industry code")
    exchange: Optional[str] = Field(None, description="Stock exchange (NYSE, AMEX, etc.)")
    address: Optional[str] = Field(None, description="Company address")


class BeneficialOwner(BaseModel):
    """Person or entity filing beneficial ownership."""
    name: str = Field(..., description="Name of filer/beneficial owner")
    address: Optional[str] = Field(None, description="Address of filer")
    is_group: bool = Field(False, description="Whether filer is a group")
    group_members: Optional[list[str]] = Field(None, description="Names of group members if applicable")


class SECFiling(BaseModel):
    """Extracted SEC filing information."""

    # Filing metadata
    form_type: FilingType = Field(..., description="Type of SEC form")
    filing_date: date = Field(..., description="Date the filing was made")
    status: FilingStatus = Field(FilingStatus.NEW, description="Filing status")

    # Target company
    company: Company = Field(..., description="Target company")

    # Filer information
    filer: BeneficialOwner = Field(..., description="Person/entity making the filing")

    # Ownership details (for 13D/13G filings)
    shares_owned: Optional[int] = Field(None, description="Number of shares owned")
    percentage_owned: Optional[float] = Field(None, description="Percentage of class owned")
    security_type: Optional[str] = Field(None, description="Type of security (common stock, etc.)")

    # Transaction details
    transaction_date: Optional[date] = Field(None, description="Date of transaction triggering filing")
    acquisition_price: Optional[float] = Field(None, description="Price per share")

    # Tender offer details (for 14D filings)
    is_tender_offer: bool = Field(False, description="Whether this involves a tender offer")
    offer_price: Optional[float] = Field(None, description="Tender offer price per share")

    # Source tracking
    source_document: Optional[str] = Field(None, description="Source document path or URL")
    source_page: Optional[int] = Field(None, description="Page number in source")
    extraction_confidence: Optional[float] = Field(None, description="LLM confidence in extraction")

    # Raw text
    raw_text: Optional[str] = Field(None, description="Original text from which this was extracted")


class FilingExtraction(BaseModel):
    """Result of extracting filings from a document."""
    source_file: str = Field(..., description="Path to source file")
    source_date: Optional[date] = Field(None, description="Date of the source document")
    filings: list[SECFiling] = Field(default_factory=list, description="Extracted filings")
    extraction_notes: Optional[str] = Field(None, description="Notes about extraction quality/issues")
    raw_text_length: int = Field(0, description="Length of source text")


class DigestEntry(BaseModel):
    """A single entry from an SEC News Digest.

    SEC News Digests from 1987-1989 list filings in a standardized format
    with company name, security type, filer, shares, CUSIP, and status.
    """
    company_name: str = Field(..., description="Name of the company")
    security_type: Optional[str] = Field(None, description="Type of security")
    filer_name: str = Field(..., description="Name of the beneficial owner/filer")
    form_type: FilingType = Field(..., description="Form type (13D, 14D-1, etc.)")
    filing_date: date = Field(..., description="Date of filing")
    shares_owned: Optional[int] = Field(None, description="Number of shares")
    percentage_owned: Optional[float] = Field(None, description="Percentage owned")
    cusip: Optional[str] = Field(None, description="CUSIP number")
    status: FilingStatus = Field(FilingStatus.NEW, description="New, amendment, or revision")


# ========== Data Source Integrator Models ==========


class SourceType(str, Enum):
    """Types of data sources for ingestion."""
    COURT_RECORD = "court_record"
    NEWS_ARTICLE = "news_article"
    REAL_ESTATE = "real_estate"
    LEAK = "leak"
    CORPORATE_FILING = "corporate_filing"
    NONPROFIT_990 = "nonprofit_990"
    REGULATORY = "regulatory"
    GENERIC_DOCUMENT = "generic_document"


class ReliabilityTier(str, Enum):
    """Source reliability tiers for confidence weighting."""
    AUTHORITATIVE = "authoritative"  # Court filings, SEC records, official documents
    JOURNALISTIC = "journalistic"    # Major publications with editorial standards
    INFORMAL = "informal"            # Blogs, forums, unverified leaks


class ClaimType(str, Enum):
    """Types of claims extracted from sources."""
    OWNERSHIP = "ownership"           # Ownership stake, beneficial ownership
    EMPLOYMENT = "employment"         # Employment relationship
    TRANSACTION = "transaction"       # Financial transaction
    RELATIONSHIP = "relationship"     # Generic relationship between entities
    PARTY_ROLE = "party_role"         # Role in legal proceeding
    ALLEGATION = "allegation"         # Unproven claim in legal context
    FINDING = "finding"               # Court finding or ruling
    BIOGRAPHICAL = "biographical"     # Birth, death, education, etc.
    LOCATION = "location"             # Address or location association
    FINANCIAL = "financial"           # Financial amounts, values


class EntityType(str, Enum):
    """Types of entities extracted from sources."""
    PERSON = "person"
    COMPANY = "company"
    ORGANIZATION = "organization"
    ADDRESS = "address"
    GOVERNMENT = "government"


class MatchStatus(str, Enum):
    """Status of entity match resolution."""
    PENDING = "pending"
    AUTO_MATCHED = "auto_matched"
    MANUAL_MATCHED = "manual_matched"
    NEEDS_REVIEW = "needs_review"
    NEW_ENTITY = "new_entity"
    REJECTED = "rejected"


class ExtractedEntity(BaseModel):
    """An entity extracted from a source document."""
    name: str = Field(..., description="Entity name as it appears in source")
    entity_type: EntityType = Field(..., description="Type of entity")
    role: Optional[str] = Field(None, description="Role in context (e.g., 'plaintiff', 'CEO')")
    identifiers: Optional[dict] = Field(None, description="Any identifiers (EIN, CUSIP, etc.)")
    attributes: Optional[dict] = Field(None, description="Additional attributes extracted")


class ExtractedRelationship(BaseModel):
    """A relationship between entities extracted from a source."""
    subject: str = Field(..., description="Name of subject entity")
    subject_type: EntityType = Field(..., description="Type of subject entity")
    predicate: str = Field(..., description="Relationship type/predicate")
    object: str = Field(..., description="Name of object entity")
    object_type: EntityType = Field(..., description="Type of object entity")
    effective_date: Optional[date] = Field(None, description="When relationship started")
    end_date: Optional[date] = Field(None, description="When relationship ended")
    amount: Optional[float] = Field(None, description="Associated amount if applicable")
    percentage: Optional[float] = Field(None, description="Associated percentage if applicable")
    context: Optional[str] = Field(None, description="Additional context about the relationship")


class ExtractedClaim(BaseModel):
    """A single extracted claim with provenance information."""
    claim_text: str = Field(..., description="The factual statement extracted")
    claim_type: ClaimType = Field(..., description="Type of claim")
    entities: list[ExtractedEntity] = Field(default_factory=list, description="Entities mentioned")
    relationships: list[ExtractedRelationship] = Field(default_factory=list, description="Relationships stated")
    page_number: Optional[int] = Field(None, description="1-indexed page number")
    paragraph: Optional[int] = Field(None, description="Paragraph on page")
    section: Optional[str] = Field(None, description="Section heading")
    char_start: Optional[int] = Field(None, description="Character offset start")
    char_end: Optional[int] = Field(None, description="Character offset end")
    raw_excerpt: Optional[str] = Field(None, description="Original text context (for verification)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    needs_review: bool = Field(False, description="Flag for manual review")
    review_reason: Optional[str] = Field(None, description="Why review is needed")


class ExtractionResult(BaseModel):
    """Complete extraction output for a source document."""
    source_id: str = Field(..., description="Unique source identifier")
    source_type: SourceType = Field(..., description="Type of source")
    source_metadata: dict = Field(default_factory=dict, description="Source-specific metadata")
    claims: list[ExtractedClaim] = Field(default_factory=list, description="Extracted claims")
    extraction_notes: Optional[str] = Field(None, description="Notes about extraction quality")
    total_entities: int = Field(0, description="Total unique entities found")
    total_relationships: int = Field(0, description="Total relationships found")


class MatchCandidate(BaseModel):
    """A candidate match during entity resolution."""
    name: str = Field(..., description="Matched entity name")
    entity_type: EntityType = Field(..., description="Entity type")
    score: float = Field(..., ge=0.0, le=1.0, description="Match confidence score")
    method: str = Field(..., description="How match was found (exact, fuzzy, alias, identifier)")
    factors: list[str] = Field(default_factory=list, description="Factors contributing to score")


class MatchResult(BaseModel):
    """Result of entity resolution attempt."""
    extracted_name: str = Field(..., description="Name as extracted from source")
    normalized_name: str = Field(..., description="Normalized form of name")
    entity_type: EntityType = Field(..., description="Inferred entity type")
    status: MatchStatus = Field(..., description="Resolution status")
    matched_entity: Optional[str] = Field(None, description="Name of matched entity if resolved")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall match confidence")
    factors: list[str] = Field(default_factory=list, description="Match factors")
    alternatives: list[MatchCandidate] = Field(default_factory=list, description="Alternative matches")


class IntegrationSummary(BaseModel):
    """Summary of a source integration operation."""
    source_id: str = Field(..., description="Source ID processed")
    source_type: SourceType = Field(..., description="Source type")
    claims_extracted: int = Field(0, description="Number of claims extracted")
    entities_found: int = Field(0, description="Unique entities mentioned")
    entities_auto_matched: int = Field(0, description="Entities automatically matched")
    entities_new: int = Field(0, description="New entities created")
    entities_needs_review: int = Field(0, description="Entities flagged for review")
    relationships_created: int = Field(0, description="Relationships created")
    document_summary: Optional[str] = Field(None, description="Human-readable document summary")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")
    review_queue_path: Optional[str] = Field(None, description="Path to review queue file")
