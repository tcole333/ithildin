"""
SEC Historical Filings Scraper

Tools for scraping and extracting data from historical SEC filings (1987-1989),
focusing on 13D, 14D, and related beneficial ownership filings.
"""

from .models import (
    SECFiling,
    BeneficialOwner,
    Company,
    FilingExtraction,
)
from .url_generator import generate_digest_urls
from .digest_scraper import SECDigestScraper
from .rtf_processor import RTFProcessor
from .llm_extractor import FilingExtractor
from .nara_parser import (
    ORSParser,
    ORSRecord,
    BrokerDealerParser,
    BrokerDealerRecord,
    CorporationIndexParser,
    CorporationRecord,
    InvestmentAdviserParser,
    InvestmentAdviserRecord,
)

__all__ = [
    "SECFiling",
    "BeneficialOwner",
    "Company",
    "FilingExtraction",
    "generate_digest_urls",
    "SECDigestScraper",
    "RTFProcessor",
    "FilingExtractor",
    # NARA parsers
    "ORSParser",
    "ORSRecord",
    "BrokerDealerParser",
    "BrokerDealerRecord",
    "CorporationIndexParser",
    "CorporationRecord",
    "InvestmentAdviserParser",
    "InvestmentAdviserRecord",
]
