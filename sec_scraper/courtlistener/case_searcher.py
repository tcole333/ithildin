"""
Entity-driven case search for CourtListener.

Searches for entities from the Neo4j database in CourtListener to find
related court cases, lawsuits, and legal proceedings.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from neo4j import GraphDatabase

from .api_client import CourtListenerClient

logger = logging.getLogger(__name__)


@dataclass
class CaseSearchResult:
    """Result of searching for an entity in CourtListener."""

    entity_name: str
    entity_type: str
    entity_id: Optional[str] = None
    cases_found: int = 0
    cases: list = field(default_factory=list)
    parties_found: int = 0
    parties: list = field(default_factory=list)


@dataclass
class CaseMatch:
    """A court case matching an entity."""

    docket_id: int
    case_name: str
    court: str
    date_filed: Optional[str] = None
    date_terminated: Optional[str] = None
    nature_of_suit: Optional[str] = None
    cause: Optional[str] = None
    party_role: Optional[str] = None  # How the entity appears (plaintiff, defendant, etc.)
    cl_url: Optional[str] = None


class CaseSearcher:
    """
    Search for entities from Neo4j database in CourtListener.

    Connects to the existing Neo4j database to get entities, then
    searches CourtListener for related court cases.

    Example usage:
        searcher = CaseSearcher(
            cl_token="your-courtlistener-token",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password"
        )

        # Search for a specific entity
        result = searcher.search_entity("Enron Corp")

        # Search for all companies in the database
        results = searcher.search_all_companies(limit=100)

        # Find cases involving sanctioned entities
        results = searcher.search_sanctioned_entities()
    """

    def __init__(
        self,
        cl_token: Optional[str] = None,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
    ):
        """Initialize the searcher."""
        self.cl_client = CourtListenerClient(token=cl_token)
        self.driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )

    def close(self):
        """Close connections."""
        self.driver.close()

    def search_entity(
        self,
        name: str,
        entity_type: str = "Company",
        search_parties: bool = True,
        search_cases: bool = True,
        max_results: int = 20,
    ) -> CaseSearchResult:
        """
        Search for an entity in CourtListener.

        Args:
            name: Entity name to search
            entity_type: Type of entity (Company, Person, Organization)
            search_parties: Search party records
            search_cases: Search case/docket records
            max_results: Maximum results per search type

        Returns:
            CaseSearchResult with found cases and parties
        """
        result = CaseSearchResult(
            entity_name=name,
            entity_type=entity_type,
        )

        # Search parties
        if search_parties:
            try:
                parties = self.cl_client.search_party_by_name(
                    name, max_results=max_results
                )
                result.parties = parties
                result.parties_found = len(parties)
                logger.info(f"Found {len(parties)} party records for '{name}'")
            except Exception as e:
                logger.error(f"Party search failed: {e}")

        # Search cases via full-text search
        if search_cases:
            try:
                cases = self.cl_client.search_cases(name, max_results=max_results)
                result.cases_found = len(cases)

                # Convert to CaseMatch objects
                for case in cases:
                    match = CaseMatch(
                        docket_id=case.get("docket_id", 0),
                        case_name=case.get("caseName", ""),
                        court=case.get("court", ""),
                        date_filed=case.get("dateFiled"),
                        date_terminated=case.get("dateTerminated"),
                        nature_of_suit=case.get("suitNature"),
                        cause=case.get("cause"),
                        cl_url=case.get("absolute_url"),
                    )
                    result.cases.append(match)

                logger.info(f"Found {len(cases)} cases for '{name}'")
            except Exception as e:
                logger.error(f"Case search failed: {e}")

        return result

    def search_entity_from_db(
        self,
        entity_id: int,
        entity_type: str = "Company",
        max_results: int = 20,
    ) -> CaseSearchResult:
        """
        Search for a specific entity from the Neo4j database.

        Args:
            entity_id: Neo4j node ID
            entity_type: Node label (Company, Person, Organization)
            max_results: Maximum results per search type

        Returns:
            CaseSearchResult
        """
        with self.driver.session() as session:
            result = session.run(
                f"MATCH (n:{entity_type}) WHERE id(n) = $id RETURN n.name AS name",
                id=entity_id,
            )
            record = result.single()
            if not record:
                return CaseSearchResult(
                    entity_name="",
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                )

            name = record["name"]

        search_result = self.search_entity(name, entity_type, max_results=max_results)
        search_result.entity_id = str(entity_id)
        return search_result

    def search_all_entities(
        self,
        entity_type: str = "Company",
        limit: int = 100,
        max_results_per_entity: int = 10,
    ) -> list[CaseSearchResult]:
        """
        Search CourtListener for all entities of a given type.

        Args:
            entity_type: Node label to search
            limit: Maximum entities to search
            max_results_per_entity: Max CourtListener results per entity

        Returns:
            List of CaseSearchResults
        """
        results = []

        with self.driver.session() as session:
            query_result = session.run(
                f"""
                MATCH (n:{entity_type})
                WHERE n.name IS NOT NULL
                RETURN n.name AS name, id(n) AS node_id
                LIMIT $limit
                """,
                limit=limit,
            )
            entities = [(r["name"], r["node_id"]) for r in query_result]

        logger.info(f"Searching CourtListener for {len(entities)} {entity_type} entities")

        for i, (name, node_id) in enumerate(entities):
            if not name or len(name) < 3:
                continue

            result = self.search_entity(
                name,
                entity_type,
                max_results=max_results_per_entity,
            )
            result.entity_id = str(node_id)

            if result.cases_found > 0 or result.parties_found > 0:
                results.append(result)
                logger.info(
                    f"[{i+1}/{len(entities)}] {name}: "
                    f"{result.cases_found} cases, {result.parties_found} parties"
                )

            # Check rate limit status
            status = self.cl_client.get_rate_limit_status()
            if status["requests_remaining"] < 100:
                logger.warning(
                    f"Rate limit low ({status['requests_remaining']} remaining), "
                    "stopping early"
                )
                break

        logger.info(f"Found court records for {len(results)}/{len(entities)} entities")
        return results

    def search_sanctioned_entities(
        self,
        limit: int = 50,
        max_results_per_entity: int = 10,
    ) -> list[CaseSearchResult]:
        """
        Search for court cases involving sanctioned entities.

        Looks for entities linked to OpenSanctions that are on sanctions lists.

        Args:
            limit: Maximum sanctioned entities to search
            max_results_per_entity: Max results per entity

        Returns:
            List of CaseSearchResults for sanctioned entities
        """
        results = []

        with self.driver.session() as session:
            # Find entities linked to sanctioned OpenSanctions entries
            query_result = session.run(
                """
                MATCH (n)-[:MATCHED_IN_OPENSANCTIONS]->(e:OpenSanctionsEntity)
                WHERE e.is_sanctioned = true
                   OR any(d IN e.datasets WHERE d IN ['us_ofac_sdn', 'eu_fsf', 'un_sc_sanctions'])
                RETURN DISTINCT n.name AS name,
                       labels(n)[0] AS entity_type,
                       id(n) AS node_id,
                       e.datasets AS datasets
                LIMIT $limit
                """,
                limit=limit,
            )
            entities = [
                (r["name"], r["entity_type"], r["node_id"], r["datasets"])
                for r in query_result
            ]

        logger.info(f"Searching for {len(entities)} sanctioned entities in CourtListener")

        for name, entity_type, node_id, datasets in entities:
            if not name:
                continue

            result = self.search_entity(
                name,
                entity_type or "Company",
                max_results=max_results_per_entity,
            )
            result.entity_id = str(node_id)

            if result.cases_found > 0 or result.parties_found > 0:
                results.append(result)
                logger.info(
                    f"{name} (sanctioned): "
                    f"{result.cases_found} cases, {result.parties_found} parties"
                )

        return results

    def search_offshore_entities(
        self,
        limit: int = 50,
        max_results_per_entity: int = 10,
    ) -> list[CaseSearchResult]:
        """
        Search for court cases involving offshore entities.

        Args:
            limit: Maximum offshore entities to search
            max_results_per_entity: Max results per entity

        Returns:
            List of CaseSearchResults
        """
        results = []

        with self.driver.session() as session:
            query_result = session.run(
                """
                MATCH (o:OffshoreEntity)
                WHERE o.name IS NOT NULL
                AND o.jurisdiction IN ['British Virgin Islands', 'Cayman Islands', 'Panama', 'Bahamas']
                RETURN o.name AS name, o.node_id AS node_id, o.jurisdiction AS jurisdiction
                LIMIT $limit
                """,
                limit=limit,
            )
            entities = [(r["name"], r["node_id"], r["jurisdiction"]) for r in query_result]

        logger.info(f"Searching for {len(entities)} offshore entities in CourtListener")

        for name, node_id, jurisdiction in entities:
            if not name or len(name) < 5:
                continue

            result = self.search_entity(
                name,
                "Company",
                max_results=max_results_per_entity,
            )
            result.entity_id = node_id

            if result.cases_found > 0 or result.parties_found > 0:
                results.append(result)
                logger.info(
                    f"{name} ({jurisdiction}): "
                    f"{result.cases_found} cases, {result.parties_found} parties"
                )

        return results

    def get_search_summary(self, results: list[CaseSearchResult]) -> dict:
        """
        Generate summary statistics for search results.

        Args:
            results: List of search results

        Returns:
            Summary statistics
        """
        total_cases = sum(r.cases_found for r in results)
        total_parties = sum(r.parties_found for r in results)
        entities_with_cases = sum(1 for r in results if r.cases_found > 0)
        entities_with_parties = sum(1 for r in results if r.parties_found > 0)

        return {
            "entities_searched": len(results),
            "entities_with_cases": entities_with_cases,
            "entities_with_parties": entities_with_parties,
            "total_cases_found": total_cases,
            "total_party_records": total_parties,
        }


def main():
    """CLI entry point."""
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser(description="Search CourtListener for entities")
    parser.add_argument("--token", help="CourtListener API token")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")

    subparsers = parser.add_subparsers(dest="command")

    # Search single entity
    search_parser = subparsers.add_parser("search", help="Search for an entity")
    search_parser.add_argument("name", help="Entity name")
    search_parser.add_argument("--type", default="Company", help="Entity type")
    search_parser.add_argument("--limit", type=int, default=20, help="Max results")

    # Search all entities
    all_parser = subparsers.add_parser("search-all", help="Search all entities of a type")
    all_parser.add_argument("--type", default="Company", help="Entity type")
    all_parser.add_argument("--limit", type=int, default=50, help="Max entities")

    # Search sanctioned
    sanct_parser = subparsers.add_parser("search-sanctioned", help="Search sanctioned entities")
    sanct_parser.add_argument("--limit", type=int, default=50, help="Max entities")

    # Search offshore
    offshore_parser = subparsers.add_parser("search-offshore", help="Search offshore entities")
    offshore_parser.add_argument("--limit", type=int, default=50, help="Max entities")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    searcher = CaseSearcher(
        cl_token=args.token or os.environ.get("COURTLISTENER_TOKEN"),
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
    )

    try:
        if args.command == "search":
            result = searcher.search_entity(args.name, args.type, max_results=args.limit)
            print(f"\n=== Search Results: {args.name} ===")
            print(f"Cases found: {result.cases_found}")
            print(f"Party records: {result.parties_found}")

            if result.cases:
                print("\n--- Cases ---")
                for case in result.cases[:10]:
                    print(f"  {case.case_name}")
                    print(f"    Court: {case.court}, Filed: {case.date_filed}")
                    if case.nature_of_suit:
                        print(f"    Nature: {case.nature_of_suit}")

        elif args.command == "search-all":
            results = searcher.search_all_entities(
                entity_type=args.type,
                limit=args.limit,
            )
            summary = searcher.get_search_summary(results)
            print(f"\n=== Search Summary ===")
            for key, value in summary.items():
                print(f"  {key}: {value}")

        elif args.command == "search-sanctioned":
            results = searcher.search_sanctioned_entities(limit=args.limit)
            summary = searcher.get_search_summary(results)
            print(f"\n=== Sanctioned Entity Search ===")
            for key, value in summary.items():
                print(f"  {key}: {value}")

            if results:
                print("\n--- Entities with cases ---")
                for r in results[:10]:
                    print(f"  {r.entity_name}: {r.cases_found} cases")

        elif args.command == "search-offshore":
            results = searcher.search_offshore_entities(limit=args.limit)
            summary = searcher.get_search_summary(results)
            print(f"\n=== Offshore Entity Search ===")
            for key, value in summary.items():
                print(f"  {key}: {value}")

        else:
            parser.print_help()

    finally:
        searcher.close()


if __name__ == "__main__":
    main()
