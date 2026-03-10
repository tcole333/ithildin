"""
CourtListener API client with rate limiting.

Provides authenticated access to CourtListener's REST API v4 with:
- Rate limiting (5,000 requests/hour)
- Automatic pagination
- Retry logic for transient failures

API Docs: https://www.courtlistener.com/help/api/rest/
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Simple rate limiter for API requests."""

    max_requests: int = 5000  # Per hour
    window_seconds: int = 3600  # 1 hour
    request_times: list = field(default_factory=list)

    def wait_if_needed(self) -> None:
        """Wait if we're approaching the rate limit."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        self.request_times = [t for t in self.request_times if t > cutoff]

        # Check if we need to wait
        if len(self.request_times) >= self.max_requests:
            oldest = min(self.request_times)
            wait_until = oldest + timedelta(seconds=self.window_seconds)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                logger.warning(f"Rate limit reached, waiting {wait_seconds:.1f}s")
                time.sleep(wait_seconds)

        self.request_times.append(now)

    def requests_remaining(self) -> int:
        """Get approximate requests remaining in current window."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window_seconds)
        self.request_times = [t for t in self.request_times if t > cutoff]
        return max(0, self.max_requests - len(self.request_times))


class CourtListenerClient:
    """
    Client for CourtListener REST API v4.

    Requires an API token from https://www.courtlistener.com/

    Example usage:
        client = CourtListenerClient(token="your-api-token")

        # Search for cases
        results = client.search("Enron bankruptcy")

        # Get a specific docket
        docket = client.get_docket(12345)

        # Get parties for a docket
        parties = client.get_parties(docket_id=12345)

        # Search financial disclosures
        disclosures = client.get_financial_disclosures(person_id=1213)
    """

    BASE_URL = "https://www.courtlistener.com/api/rest/v4"

    # Court type filters
    FEDERAL_COURTS = [
        "scotus",  # Supreme Court
        "ca1", "ca2", "ca3", "ca4", "ca5", "ca6", "ca7", "ca8", "ca9", "ca10", "ca11", "cadc", "cafc",  # Circuit Courts
        # District courts use format like "dcd", "nysd", "cacd", etc.
    ]

    def __init__(
        self,
        token: Optional[str] = None,
        rate_limit: int = 5000,
    ):
        """
        Initialize the client.

        Args:
            token: CourtListener API token (or set COURTLISTENER_TOKEN env var)
            rate_limit: Max requests per hour (default 5000)
        """
        self.token = token or os.environ.get("COURTLISTENER_TOKEN")
        if not self.token:
            logger.warning(
                "No CourtListener API token provided. "
                "Set COURTLISTENER_TOKEN env var or pass token parameter. "
                "Anonymous requests have severe rate limits."
            )

        self.session = requests.Session()
        if self.token:
            self.session.headers["Authorization"] = f"Token {self.token}"

        self.session.headers["User-Agent"] = "offshore-leaks-research/1.0"
        self.rate_limiter = RateLimiter(max_requests=rate_limit)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        retries: int = 3,
    ) -> dict:
        """
        Make a rate-limited API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            retries: Number of retries for transient failures

        Returns:
            JSON response data
        """
        self.rate_limiter.wait_if_needed()

        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"

        for attempt in range(retries):
            try:
                response = self.session.request(method, url, params=params)

                if response.status_code == 429:
                    # Rate limited, wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                if response.status_code == 401:
                    raise ValueError(
                        "Authentication failed. Check your COURTLISTENER_TOKEN."
                    )

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Request failed, retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise

        return {}

    def _paginate(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        max_results: Optional[int] = None,
    ) -> Iterator[dict]:
        """
        Paginate through API results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_results: Maximum results to return

        Yields:
            Individual result objects
        """
        params = params or {}
        count = 0

        while True:
            data = self._request("GET", endpoint, params)

            for result in data.get("results", []):
                yield result
                count += 1
                if max_results and count >= max_results:
                    return

            # Check for next page
            next_url = data.get("next")
            if not next_url:
                break

            # Extract cursor/page from next URL
            # CourtListener uses cursor-based pagination for id/date ordering
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(next_url)
            next_params = parse_qs(parsed.query)
            params = {k: v[0] for k, v in next_params.items()}

    # =========================================================================
    # Search API
    # =========================================================================

    def search(
        self,
        query: str,
        search_type: str = "o",  # o=opinions, r=recap/dockets, p=people
        court: Optional[str] = None,
        max_results: int = 100,
        **kwargs,
    ) -> list[dict]:
        """
        Search CourtListener.

        Args:
            query: Search query
            search_type: Type of search (o=opinions, r=recap, p=people, rd=recap docs)
            court: Filter to specific court (e.g., "scotus", "ca9")
            max_results: Maximum results to return
            **kwargs: Additional filter parameters

        Returns:
            List of search results
        """
        params = {"q": query, "type": search_type}
        if court:
            params["court"] = court
        params.update(kwargs)

        results = list(self._paginate("search/", params, max_results))
        logger.info(f"Search '{query}' returned {len(results)} results")
        return results

    def search_cases(
        self,
        query: str,
        court: Optional[str] = None,
        date_filed_after: Optional[str] = None,
        date_filed_before: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Search for court cases/dockets.

        Args:
            query: Search query
            court: Court filter
            date_filed_after: Filter cases filed after this date (YYYY-MM-DD)
            date_filed_before: Filter cases filed before this date
            max_results: Maximum results

        Returns:
            List of docket results
        """
        params = {}
        if date_filed_after:
            params["date_filed__gte"] = date_filed_after
        if date_filed_before:
            params["date_filed__lte"] = date_filed_before

        return self.search(
            query,
            search_type="r",  # RECAP/dockets
            court=court,
            max_results=max_results,
            **params,
        )

    # =========================================================================
    # Docket API
    # =========================================================================

    def get_docket(self, docket_id: int) -> dict:
        """
        Get a specific docket by ID.

        Args:
            docket_id: CourtListener docket ID

        Returns:
            Docket details
        """
        return self._request("GET", f"dockets/{docket_id}/")

    def get_dockets(
        self,
        court: Optional[str] = None,
        date_filed_after: Optional[str] = None,
        date_filed_before: Optional[str] = None,
        max_results: int = 100,
        **kwargs,
    ) -> list[dict]:
        """
        Get dockets with filters.

        Args:
            court: Court filter (e.g., "scotus", "nysd")
            date_filed_after: Filter by filing date
            date_filed_before: Filter by filing date
            max_results: Maximum results
            **kwargs: Additional filters

        Returns:
            List of dockets
        """
        params = {}
        if court:
            params["court"] = court
        if date_filed_after:
            params["date_filed__gte"] = date_filed_after
        if date_filed_before:
            params["date_filed__lte"] = date_filed_before
        params.update(kwargs)

        return list(self._paginate("dockets/", params, max_results))

    # =========================================================================
    # Parties API
    # =========================================================================

    def get_parties(
        self,
        docket_id: Optional[int] = None,
        name: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get parties, optionally filtered by docket or name.

        Args:
            docket_id: Filter to specific docket
            name: Filter by party name (partial match)
            max_results: Maximum results

        Returns:
            List of parties with their attorneys
        """
        params = {"filter_nested_results": "True"}
        if docket_id:
            params["docket"] = docket_id
        if name:
            params["name__icontains"] = name

        return list(self._paginate("parties/", params, max_results))

    def search_party_by_name(
        self,
        name: str,
        party_type: Optional[str] = None,  # e.g., "Plaintiff", "Defendant"
        max_results: int = 50,
    ) -> list[dict]:
        """
        Search for parties by name across all cases.

        Args:
            name: Party name to search
            party_type: Filter by party type
            max_results: Maximum results

        Returns:
            List of parties matching the name
        """
        params = {"name__icontains": name}
        if party_type:
            params["party_types__name__icontains"] = party_type

        return list(self._paginate("parties/", params, max_results))

    # =========================================================================
    # Opinions API
    # =========================================================================

    def get_opinion(self, opinion_id: int) -> dict:
        """Get a specific opinion."""
        return self._request("GET", f"opinions/{opinion_id}/")

    def get_opinions(
        self,
        court: Optional[str] = None,
        date_filed_after: Optional[str] = None,
        date_filed_before: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """Get opinions with filters."""
        params = {}
        if court:
            params["cluster__docket__court"] = court
        if date_filed_after:
            params["cluster__date_filed__gte"] = date_filed_after
        if date_filed_before:
            params["cluster__date_filed__lte"] = date_filed_before

        return list(self._paginate("opinions/", params, max_results))

    # =========================================================================
    # People/Judges API
    # =========================================================================

    def get_person(self, person_id: int) -> dict:
        """Get a person (usually a judge) by ID."""
        return self._request("GET", f"people/{person_id}/")

    def search_judges(
        self,
        name: Optional[str] = None,
        court: Optional[str] = None,
        max_results: int = 50,
    ) -> list[dict]:
        """
        Search for judges.

        Args:
            name: Judge name to search
            court: Court filter
            max_results: Maximum results

        Returns:
            List of judges with their positions
        """
        params = {}
        if name:
            params["name_full__icontains"] = name
        if court:
            params["positions__court__id"] = court

        return list(self._paginate("people/", params, max_results))

    # =========================================================================
    # Financial Disclosures API
    # =========================================================================

    def get_financial_disclosures(
        self,
        person_id: Optional[int] = None,
        year: Optional[int] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get financial disclosure documents.

        Args:
            person_id: Filter to specific judge
            year: Filter by disclosure year
            max_results: Maximum results

        Returns:
            List of financial disclosure records
        """
        params = {}
        if person_id:
            params["person"] = person_id
        if year:
            params["year"] = year

        return list(self._paginate("financial-disclosures/", params, max_results))

    def get_investments(
        self,
        person_id: Optional[int] = None,
        description: Optional[str] = None,
        min_value: Optional[str] = None,  # e.g., "P4" for >$50M
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get investment disclosures.

        Args:
            person_id: Filter to specific judge
            description: Filter by investment description (e.g., stock name)
            min_value: Minimum gross value code (J=<$1K, P4=>$50M)
            max_results: Maximum results

        Returns:
            List of investment records
        """
        params = {}
        if person_id:
            params["financial_disclosure__person"] = person_id
        if description:
            params["description__icontains"] = description
        if min_value:
            params["gross_value_code__gte"] = min_value

        return list(self._paginate("investments/", params, max_results))

    def get_gifts(
        self,
        person_id: Optional[int] = None,
        source: Optional[str] = None,
        max_results: int = 100,
    ) -> list[dict]:
        """
        Get gift disclosures.

        Args:
            person_id: Filter to specific judge
            source: Filter by gift source
            max_results: Maximum results

        Returns:
            List of gift records
        """
        params = {}
        if person_id:
            params["financial_disclosure__person"] = person_id
        if source:
            params["source__icontains"] = source

        return list(self._paginate("gifts/", params, max_results))

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_endpoint_options(self, endpoint: str) -> dict:
        """
        Get available filters and options for an endpoint.

        Args:
            endpoint: API endpoint name

        Returns:
            OPTIONS response with available filters
        """
        return self._request("OPTIONS", endpoint)

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status."""
        return {
            "requests_remaining": self.rate_limiter.requests_remaining(),
            "max_per_hour": self.rate_limiter.max_requests,
        }


def main():
    """CLI for testing the API client."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="CourtListener API client")
    parser.add_argument("--token", help="API token (or set COURTLISTENER_TOKEN)")

    subparsers = parser.add_subparsers(dest="command")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search CourtListener")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--type", default="r", help="Search type (o/r/p/rd)")
    search_parser.add_argument("--court", help="Court filter")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")

    # Docket command
    docket_parser = subparsers.add_parser("docket", help="Get docket details")
    docket_parser.add_argument("docket_id", type=int, help="Docket ID")

    # Party search command
    party_parser = subparsers.add_parser("party", help="Search parties")
    party_parser.add_argument("name", help="Party name")
    party_parser.add_argument("--limit", type=int, default=10, help="Max results")

    # Judge command
    judge_parser = subparsers.add_parser("judge", help="Search judges")
    judge_parser.add_argument("name", help="Judge name")
    judge_parser.add_argument("--limit", type=int, default=10, help="Max results")

    # Financial disclosures command
    fd_parser = subparsers.add_parser("disclosures", help="Get financial disclosures")
    fd_parser.add_argument("--person-id", type=int, help="Judge person ID")
    fd_parser.add_argument("--year", type=int, help="Disclosure year")
    fd_parser.add_argument("--limit", type=int, default=10, help="Max results")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    client = CourtListenerClient(token=args.token)

    if args.command == "search":
        results = client.search(
            args.query,
            search_type=args.type,
            court=args.court,
            max_results=args.limit,
        )
        for r in results:
            print(json.dumps(r, indent=2, default=str))

    elif args.command == "docket":
        docket = client.get_docket(args.docket_id)
        print(json.dumps(docket, indent=2, default=str))

    elif args.command == "party":
        parties = client.search_party_by_name(args.name, max_results=args.limit)
        for p in parties:
            print(json.dumps(p, indent=2, default=str))

    elif args.command == "judge":
        judges = client.search_judges(name=args.name, max_results=args.limit)
        for j in judges:
            print(json.dumps(j, indent=2, default=str))

    elif args.command == "disclosures":
        disclosures = client.get_financial_disclosures(
            person_id=args.person_id,
            year=args.year,
            max_results=args.limit,
        )
        for d in disclosures:
            print(json.dumps(d, indent=2, default=str))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
