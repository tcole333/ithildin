"""
CourtListener integration module.

Provides tools for searching federal court records, ingesting case data,
and detecting judicial conflicts of interest via financial disclosures.

API Documentation: https://www.courtlistener.com/help/api/rest/
"""

from .api_client import CourtListenerClient
from .case_searcher import CaseSearcher
from .case_ingester import CaseIngester

__all__ = [
    "CourtListenerClient",
    "CaseSearcher",
    "CaseIngester",
]
