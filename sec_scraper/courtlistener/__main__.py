"""
CLI entry point for CourtListener integration.

Usage:
    python -m sec_scraper.courtlistener --help
    python -m sec_scraper.courtlistener search "Enron"
    python -m sec_scraper.courtlistener ingest --entity "Goldman Sachs"
"""

import argparse
import logging
import os
import sys

from .api_client import CourtListenerClient
from .case_searcher import CaseSearcher
from .case_ingester import CaseIngester


def main():
    parser = argparse.ArgumentParser(
        description="CourtListener integration for court case research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for cases involving an entity
  python -m sec_scraper.courtlistener search "Enron Corp"

  # Search and ingest cases for an entity
  python -m sec_scraper.courtlistener ingest --entity "Goldman Sachs" --limit 10

  # Search for cases involving sanctioned entities
  python -m sec_scraper.courtlistener search-sanctioned --limit 20

  # Search for offshore entity litigation
  python -m sec_scraper.courtlistener search-offshore --limit 20

  # Get a specific docket
  python -m sec_scraper.courtlistener docket 12345

  # Set up database schema
  python -m sec_scraper.courtlistener setup

  # Check API rate limit status
  python -m sec_scraper.courtlistener status
        """
    )

    # Connection options
    parser.add_argument("--token", help="CourtListener API token (or set COURTLISTENER_TOKEN)")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j user")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j password")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for court cases")
    search_parser.add_argument("query", help="Search query (entity name)")
    search_parser.add_argument("--type", "-t", default="Company", help="Entity type")
    search_parser.add_argument("--limit", "-l", type=int, default=20, help="Max results")
    search_parser.add_argument("--court", help="Filter by court (e.g., 'scotus', 'ca9')")

    # Search sanctioned entities
    sanct_parser = subparsers.add_parser("search-sanctioned", help="Search sanctioned entities")
    sanct_parser.add_argument("--limit", "-l", type=int, default=50, help="Max entities")

    # Search offshore entities
    offshore_parser = subparsers.add_parser("search-offshore", help="Search offshore entities")
    offshore_parser.add_argument("--limit", "-l", type=int, default=50, help="Max entities")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest court cases into Neo4j")
    ingest_parser.add_argument("--entity", "-e", help="Entity name to search and ingest")
    ingest_parser.add_argument("--docket", "-d", type=int, help="Specific docket ID to ingest")
    ingest_parser.add_argument("--type", "-t", default="Company", help="Entity type")
    ingest_parser.add_argument("--limit", "-l", type=int, default=20, help="Max cases")

    # Docket command
    docket_parser = subparsers.add_parser("docket", help="Get docket details")
    docket_parser.add_argument("docket_id", type=int, help="CourtListener docket ID")
    docket_parser.add_argument("--ingest", "-i", action="store_true", help="Also ingest to Neo4j")

    # Setup command
    subparsers.add_parser("setup", help="Set up Neo4j schema for court data")

    # Stats command
    subparsers.add_parser("stats", help="Show court case statistics")

    # Status command
    subparsers.add_parser("status", help="Check API rate limit status")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Get token
    token = args.token or os.environ.get("COURTLISTENER_TOKEN")

    if args.command == "search":
        searcher = CaseSearcher(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            result = searcher.search_entity(args.query, args.type, max_results=args.limit)

            print(f"\n=== Search Results: {args.query} ===")
            print(f"Cases found: {result.cases_found}")
            print(f"Party records: {result.parties_found}")

            if result.cases:
                print("\n--- Top Cases ---")
                for case in result.cases[:10]:
                    print(f"  [{case.docket_id}] {case.case_name}")
                    print(f"      Court: {case.court}, Filed: {case.date_filed}")
                    if case.nature_of_suit:
                        print(f"      Nature: {case.nature_of_suit}")
        finally:
            searcher.close()

    elif args.command == "search-sanctioned":
        searcher = CaseSearcher(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            results = searcher.search_sanctioned_entities(limit=args.limit)
            summary = searcher.get_search_summary(results)

            print(f"\n=== Sanctioned Entity Court Cases ===")
            for key, value in summary.items():
                print(f"  {key}: {value}")

            if results:
                print("\n--- Entities with court cases ---")
                for r in results[:15]:
                    print(f"  {r.entity_name}: {r.cases_found} cases, {r.parties_found} party records")
        finally:
            searcher.close()

    elif args.command == "search-offshore":
        searcher = CaseSearcher(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            results = searcher.search_offshore_entities(limit=args.limit)
            summary = searcher.get_search_summary(results)

            print(f"\n=== Offshore Entity Court Cases ===")
            for key, value in summary.items():
                print(f"  {key}: {value}")

            if results:
                print("\n--- Entities with court cases ---")
                for r in results[:15]:
                    print(f"  {r.entity_name}: {r.cases_found} cases")
        finally:
            searcher.close()

    elif args.command == "ingest":
        ingester = CaseIngester(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            if args.docket:
                stats = ingester.ingest_docket(args.docket)
            elif args.entity:
                stats = ingester.ingest_cases_for_entity(
                    args.entity,
                    args.type,
                    max_cases=args.limit,
                )
            else:
                print("Error: Must specify --entity or --docket")
                sys.exit(1)

            print(f"\n=== Ingestion Complete ===")
            print(f"Cases created: {stats.cases_created}")
            print(f"Parties created: {stats.parties_created}")
            print(f"Errors: {stats.errors}")
        finally:
            ingester.close()

    elif args.command == "docket":
        client = CourtListenerClient(token=token)

        docket = client.get_docket(args.docket_id)
        print(f"\n=== Docket {args.docket_id} ===")
        print(f"Case: {docket.get('case_name')}")
        print(f"Court: {docket.get('court')}")
        print(f"Filed: {docket.get('date_filed')}")
        print(f"Terminated: {docket.get('date_terminated', 'Active')}")
        print(f"Nature: {docket.get('nature_of_suit')}")
        print(f"Cause: {docket.get('cause')}")
        print(f"URL: https://www.courtlistener.com{docket.get('absolute_url', '')}")

        if args.ingest:
            ingester = CaseIngester(
                cl_token=token,
                neo4j_uri=args.neo4j_uri,
                neo4j_user=args.neo4j_user,
                neo4j_password=args.neo4j_password,
            )
            try:
                stats = ingester.ingest_docket(args.docket_id)
                print(f"\nIngested: {stats.cases_created} case, {stats.parties_created} parties")
            finally:
                ingester.close()

    elif args.command == "setup":
        ingester = CaseIngester(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            ingester.setup_schema()
            print("Court case schema created successfully")
        finally:
            ingester.close()

    elif args.command == "stats":
        ingester = CaseIngester(
            cl_token=token,
            neo4j_uri=args.neo4j_uri,
            neo4j_user=args.neo4j_user,
            neo4j_password=args.neo4j_password,
        )
        try:
            stats = ingester.get_case_stats()
            print(f"\n=== Court Case Statistics ===")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        finally:
            ingester.close()

    elif args.command == "status":
        client = CourtListenerClient(token=token)
        status = client.get_rate_limit_status()
        print(f"\n=== API Status ===")
        print(f"Requests remaining: {status['requests_remaining']}")
        print(f"Max per hour: {status['max_per_hour']}")
        if not token:
            print("\nNote: No API token configured. Set COURTLISTENER_TOKEN for full access.")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
