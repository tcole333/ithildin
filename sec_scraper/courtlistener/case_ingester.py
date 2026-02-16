"""
Case ingestion pipeline for CourtListener data.

Creates Neo4j nodes for court cases, parties, and their relationships
using FtM-compatible patterns.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from neo4j import GraphDatabase

from .api_client import CourtListenerClient

logger = logging.getLogger(__name__)


@dataclass
class IngestionStats:
    """Statistics from case ingestion."""

    cases_created: int = 0
    cases_updated: int = 0
    parties_created: int = 0
    party_links_created: int = 0
    entity_matches: int = 0
    errors: int = 0


# Schema creation queries for court data
COURT_SCHEMA_QUERIES = [
    # CourtCase node
    "CREATE CONSTRAINT court_case_id IF NOT EXISTS FOR (c:CourtCase) REQUIRE c.case_id IS UNIQUE",
    "CREATE INDEX court_case_cl_id IF NOT EXISTS FOR (c:CourtCase) ON (c.cl_docket_id)",
    "CREATE INDEX court_case_name IF NOT EXISTS FOR (c:CourtCase) ON (c.case_name)",
    "CREATE INDEX court_case_court IF NOT EXISTS FOR (c:CourtCase) ON (c.court)",
    "CREATE INDEX court_case_date IF NOT EXISTS FOR (c:CourtCase) ON (c.date_filed)",

    # CourtCaseParty interstitial node (FtM pattern)
    "CREATE CONSTRAINT court_party_id IF NOT EXISTS FOR (p:CourtCaseParty) REQUIRE p.party_id IS UNIQUE",

    # Judge node
    "CREATE CONSTRAINT judge_id IF NOT EXISTS FOR (j:Judge) REQUIRE j.cl_person_id IS UNIQUE",
    "CREATE INDEX judge_name IF NOT EXISTS FOR (j:Judge) ON (j.name)",

    # Attorney node
    "CREATE CONSTRAINT attorney_id IF NOT EXISTS FOR (a:Attorney) REQUIRE a.cl_attorney_id IS UNIQUE",
    "CREATE INDEX attorney_name IF NOT EXISTS FOR (a:Attorney) ON (a.name)",
]


class CaseIngester:
    """
    Ingest court case data from CourtListener into Neo4j.

    Creates:
    - CourtCase nodes for dockets
    - CourtCaseParty nodes (interstitial, FtM pattern)
    - Links between existing entities and court cases
    - Judge nodes and assignments

    Example usage:
        ingester = CaseIngester(
            cl_token="your-token",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password"
        )
        ingester.setup_schema()

        # Ingest a specific docket
        ingester.ingest_docket(12345)

        # Ingest cases for a company
        ingester.ingest_cases_for_entity("Enron Corp", "Company")

        # Ingest from search results
        from .case_searcher import CaseSearcher
        searcher = CaseSearcher(...)
        results = searcher.search_entity("Goldman Sachs")
        ingester.ingest_search_results(results)
    """

    def __init__(
        self,
        cl_token: Optional[str] = None,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
    ):
        """Initialize the ingester."""
        self.cl_client = CourtListenerClient(token=cl_token)
        self.driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )

    def close(self):
        """Close connections."""
        self.driver.close()

    def setup_schema(self):
        """Create schema constraints for court data."""
        with self.driver.session() as session:
            for query in COURT_SCHEMA_QUERIES:
                try:
                    session.run(query)
                    logger.info(f"Executed: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Schema query failed (may already exist): {e}")

    def generate_case_id(self, cl_docket_id: int) -> str:
        """Generate a stable case ID from CourtListener docket ID."""
        return f"cl-{cl_docket_id}"

    def generate_party_id(self, cl_docket_id: int, party_name: str, role: str) -> str:
        """Generate a stable party ID."""
        content = f"{cl_docket_id}:{party_name}:{role}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def ingest_docket(self, docket_id: int) -> IngestionStats:
        """
        Ingest a single docket from CourtListener.

        Args:
            docket_id: CourtListener docket ID

        Returns:
            Ingestion statistics
        """
        stats = IngestionStats()

        try:
            # Fetch docket details
            docket = self.cl_client.get_docket(docket_id)
            if not docket:
                logger.warning(f"Docket {docket_id} not found")
                return stats

            # Create/update CourtCase node
            case_id = self.generate_case_id(docket_id)
            self._create_case_node(docket, case_id)
            stats.cases_created += 1

            # Create Judge nodes
            self._create_judge_node(docket, case_id)

            # Fetch and create parties
            parties = self.cl_client.get_parties(docket_id=docket_id)
            for party in parties:
                try:
                    self._create_party_node(party, case_id, docket_id)
                    stats.parties_created += 1
                except Exception as e:
                    logger.error(f"Error creating party: {e}")
                    stats.errors += 1

            logger.info(
                f"Ingested docket {docket_id}: "
                f"{stats.cases_created} case, {stats.parties_created} parties"
            )

        except Exception as e:
            logger.error(f"Error ingesting docket {docket_id}: {e}")
            stats.errors += 1

        return stats

    def _create_case_node(self, docket: dict, case_id: str) -> None:
        """Create or update a CourtCase node."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (c:CourtCase {case_id: $case_id})
                SET c.cl_docket_id = $cl_docket_id,
                    c.case_name = $case_name,
                    c.court = $court,
                    c.court_id = $court_id,
                    c.date_filed = $date_filed,
                    c.date_terminated = $date_terminated,
                    c.date_last_filing = $date_last_filing,
                    c.nature_of_suit = $nature_of_suit,
                    c.cause = $cause,
                    c.jury_demand = $jury_demand,
                    c.assigned_to = $assigned_to,
                    c.referred_to = $referred_to,
                    c.cl_url = $cl_url,
                    c.pacer_case_id = $pacer_case_id,
                    c.ingested_date = datetime()
                """,
                case_id=case_id,
                cl_docket_id=docket.get("id"),
                case_name=docket.get("case_name"),
                court=docket.get("court"),
                court_id=docket.get("court_id"),
                date_filed=docket.get("date_filed"),
                date_terminated=docket.get("date_terminated"),
                date_last_filing=docket.get("date_last_filing"),
                nature_of_suit=docket.get("nature_of_suit"),
                cause=docket.get("cause"),
                jury_demand=docket.get("jury_demand"),
                assigned_to=docket.get("assigned_to_str"),
                referred_to=docket.get("referred_to_str"),
                cl_url=docket.get("absolute_url"),
                pacer_case_id=docket.get("pacer_case_id"),
            )

    def _create_party_node(self, party: dict, case_id: str, docket_id: int) -> None:
        """Create a CourtCaseParty interstitial node (FtM pattern)."""
        party_name = party.get("name", "")
        if not party_name:
            return

        # Get party types (plaintiff, defendant, etc.)
        party_types = party.get("party_types", [])
        roles = [pt.get("name", "") for pt in party_types] if party_types else ["Unknown"]

        for role in roles:
            party_id = self.generate_party_id(docket_id, party_name, role)

            with self.driver.session() as session:
                # Create CourtCaseParty node
                session.run(
                    """
                    MERGE (p:CourtCaseParty {party_id: $party_id})
                    SET p.name = $name,
                        p.role = $role,
                        p.extra_info = $extra_info,
                        p.date_terminated = $date_terminated,
                        p.cl_party_id = $cl_party_id
                    WITH p
                    MATCH (c:CourtCase {case_id: $case_id})
                    MERGE (p)-[:IN_CASE]->(c)
                    """,
                    party_id=party_id,
                    name=party_name,
                    role=role,
                    extra_info=party.get("extra_info"),
                    date_terminated=party.get("date_terminated"),
                    cl_party_id=party.get("id"),
                    case_id=case_id,
                )

                # Try to match to existing entity
                self._match_party_to_entity(party_name, party_id)

            # Create Attorney nodes from party's attorneys list
            attorneys = party.get("attorneys", [])
            for attorney in attorneys:
                self._create_attorney_node(attorney, party_id, case_id)

    def _create_attorney_node(self, attorney: dict, party_id: str, case_id: str) -> None:
        """Create an Attorney node and link to party."""
        attorney_name = attorney.get("name", "")
        if not attorney_name:
            return

        cl_attorney_id = attorney.get("id")
        if not cl_attorney_id:
            # Generate ID from name if not provided
            cl_attorney_id = hashlib.md5(attorney_name.encode()).hexdigest()[:12]

        with self.driver.session() as session:
            session.run(
                """
                MERGE (a:Attorney {cl_attorney_id: $cl_attorney_id})
                SET a.name = $name,
                    a.contact_raw = $contact_raw,
                    a.phone = $phone,
                    a.fax = $fax,
                    a.email = $email
                WITH a
                MATCH (p:CourtCaseParty {party_id: $party_id})
                MERGE (a)-[r:REPRESENTS]->(p)
                SET r.roles = $roles
                """,
                cl_attorney_id=str(cl_attorney_id),
                name=attorney_name,
                contact_raw=attorney.get("contact_raw"),
                phone=attorney.get("phone"),
                fax=attorney.get("fax"),
                email=attorney.get("email"),
                party_id=party_id,
                roles=attorney.get("roles", []),
            )

    def _extract_person_id(self, url_or_id) -> Optional[int]:
        """Extract person ID from URL or return ID directly."""
        if url_or_id is None:
            return None
        if isinstance(url_or_id, int):
            return url_or_id
        if isinstance(url_or_id, str):
            # Extract from URL like https://www.courtlistener.com/api/rest/v4/people/1368/
            import re
            match = re.search(r'/people/(\d+)/?', url_or_id)
            if match:
                return int(match.group(1))
        return None

    def _create_judge_node(self, docket: dict, case_id: str, fetch_details: bool = True) -> None:
        """Create Judge node and link to case."""
        # Handle assigned judge
        assigned_to_url = docket.get("assigned_to")
        assigned_to_id = self._extract_person_id(assigned_to_url)
        assigned_to_name = docket.get("assigned_to_str")

        if assigned_to_id and assigned_to_name:
            # Optionally fetch full judge details
            judge_data = {}
            if fetch_details:
                try:
                    judge_data = self.cl_client.get_person(assigned_to_id)
                except Exception as e:
                    logger.debug(f"Could not fetch judge details: {e}")

            with self.driver.session() as session:
                session.run(
                    """
                    MERGE (j:Judge {cl_person_id: $cl_person_id})
                    SET j.name = $name,
                        j.name_first = $name_first,
                        j.name_last = $name_last,
                        j.gender = $gender,
                        j.date_dob = $date_dob,
                        j.slug = $slug
                    WITH j
                    MATCH (c:CourtCase {case_id: $case_id})
                    MERGE (j)-[:PRESIDES_OVER {role: 'assigned'}]->(c)
                    """,
                    cl_person_id=assigned_to_id,
                    name=assigned_to_name,
                    name_first=judge_data.get("name_first"),
                    name_last=judge_data.get("name_last"),
                    gender=judge_data.get("gender"),
                    date_dob=judge_data.get("date_dob"),
                    slug=judge_data.get("slug"),
                    case_id=case_id,
                )
            logger.info(f"Created/updated Judge node: {assigned_to_name} (ID: {assigned_to_id})")

        # Handle referred judge (magistrate)
        referred_to_url = docket.get("referred_to")
        referred_to_id = self._extract_person_id(referred_to_url)
        referred_to_name = docket.get("referred_to_str")

        if referred_to_id and referred_to_name:
            judge_data = {}
            if fetch_details:
                try:
                    judge_data = self.cl_client.get_person(referred_to_id)
                except Exception as e:
                    logger.debug(f"Could not fetch referred judge details: {e}")

            with self.driver.session() as session:
                session.run(
                    """
                    MERGE (j:Judge {cl_person_id: $cl_person_id})
                    SET j.name = $name,
                        j.name_first = $name_first,
                        j.name_last = $name_last,
                        j.gender = $gender,
                        j.date_dob = $date_dob,
                        j.slug = $slug
                    WITH j
                    MATCH (c:CourtCase {case_id: $case_id})
                    MERGE (j)-[:PRESIDES_OVER {role: 'referred'}]->(c)
                    """,
                    cl_person_id=referred_to_id,
                    name=referred_to_name,
                    name_first=judge_data.get("name_first"),
                    name_last=judge_data.get("name_last"),
                    gender=judge_data.get("gender"),
                    date_dob=judge_data.get("date_dob"),
                    slug=judge_data.get("slug"),
                    case_id=case_id,
                )
            logger.info(f"Created/updated referred Judge node: {referred_to_name} (ID: {referred_to_id})")

    def _match_party_to_entity(self, party_name: str, party_id: str) -> bool:
        """
        Try to match a court party to an existing entity in the database.

        Returns True if a match was found.
        """
        if not party_name or len(party_name) < 3:
            return False

        # Normalize name for matching
        normalized = party_name.upper().strip()
        for suffix in [" INC", " CORP", " CO", " LTD", " LLC", " LP", "."]:
            normalized = normalized.replace(suffix, "")
        normalized = normalized.strip()

        with self.driver.session() as session:
            # Try exact match first
            result = session.run(
                """
                MATCH (n)
                WHERE (n:Company OR n:Person OR n:Organization)
                AND toUpper(n.name) = $normalized
                WITH n LIMIT 1
                MATCH (p:CourtCaseParty {party_id: $party_id})
                MERGE (n)-[r:PARTY_IN]->(p)
                SET r.match_method = 'exact',
                    r.match_date = datetime()
                RETURN n.name AS matched_name
                """,
                normalized=normalized,
                party_id=party_id,
            )
            record = result.single()
            if record:
                logger.debug(f"Matched party '{party_name}' to '{record['matched_name']}'")
                return True

            # Try partial match for companies
            if len(normalized) >= 5:
                result = session.run(
                    """
                    MATCH (n:Company)
                    WHERE toUpper(n.name) CONTAINS $normalized
                    OR $normalized CONTAINS toUpper(n.name)
                    WITH n LIMIT 1
                    MATCH (p:CourtCaseParty {party_id: $party_id})
                    MERGE (n)-[r:PARTY_IN]->(p)
                    SET r.match_method = 'partial',
                        r.match_date = datetime(),
                        r.needs_review = true
                    RETURN n.name AS matched_name
                    """,
                    normalized=normalized,
                    party_id=party_id,
                )
                record = result.single()
                if record:
                    logger.debug(
                        f"Partial match: '{party_name}' -> '{record['matched_name']}'"
                    )
                    return True

        return False

    def ingest_cases_for_entity(
        self,
        entity_name: str,
        entity_type: str = "Company",
        max_cases: int = 20,
    ) -> IngestionStats:
        """
        Search for and ingest court cases involving an entity.

        Args:
            entity_name: Entity name to search
            entity_type: Type of entity
            max_cases: Maximum cases to ingest

        Returns:
            Ingestion statistics
        """
        stats = IngestionStats()

        # Search for cases
        cases = self.cl_client.search_cases(entity_name, max_results=max_cases)

        logger.info(f"Found {len(cases)} cases for '{entity_name}'")

        for case in cases:
            docket_id = case.get("docket_id")
            if not docket_id:
                continue

            try:
                case_stats = self.ingest_docket(docket_id)
                stats.cases_created += case_stats.cases_created
                stats.parties_created += case_stats.parties_created
                stats.errors += case_stats.errors
            except Exception as e:
                logger.error(f"Error ingesting docket {docket_id}: {e}")
                stats.errors += 1

        return stats

    def ingest_from_search_results(self, search_results) -> IngestionStats:
        """
        Ingest cases from CaseSearcher results.

        Args:
            search_results: List of CaseSearchResult or single result

        Returns:
            Ingestion statistics
        """
        stats = IngestionStats()

        if not isinstance(search_results, list):
            search_results = [search_results]

        for result in search_results:
            for case in result.cases:
                if not hasattr(case, "docket_id") or not case.docket_id:
                    continue

                try:
                    case_stats = self.ingest_docket(case.docket_id)
                    stats.cases_created += case_stats.cases_created
                    stats.parties_created += case_stats.parties_created
                    stats.errors += case_stats.errors
                except Exception as e:
                    logger.error(f"Error ingesting docket {case.docket_id}: {e}")
                    stats.errors += 1

        return stats

    def link_entity_to_cases(
        self,
        entity_name: str,
        entity_type: str = "Company",
    ) -> int:
        """
        Link an existing entity to any court cases where it appears.

        Args:
            entity_name: Entity name
            entity_type: Entity type

        Returns:
            Number of links created
        """
        # Normalize name
        normalized = entity_name.upper().strip()
        for suffix in [" INC", " CORP", " CO", " LTD", " LLC", " LP", "."]:
            normalized = normalized.replace(suffix, "")
        normalized = normalized.strip()

        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (n:{entity_type})
                WHERE toUpper(n.name) = $normalized
                MATCH (p:CourtCaseParty)
                WHERE toUpper(p.name) CONTAINS $normalized
                   OR $normalized CONTAINS toUpper(p.name)
                MERGE (n)-[r:PARTY_IN]->(p)
                SET r.match_method = 'post_hoc',
                    r.match_date = datetime()
                RETURN count(r) AS links_created
                """,
                normalized=normalized,
            )
            record = result.single()
            links = record["links_created"] if record else 0

            if links > 0:
                logger.info(f"Linked '{entity_name}' to {links} court cases")

            return links

    def get_case_stats(self) -> dict:
        """Get statistics about court cases in the database."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:CourtCase)
                OPTIONAL MATCH (c)<-[:IN_CASE]-(p:CourtCaseParty)
                OPTIONAL MATCH (n)-[:PARTY_IN]->(p)
                WHERE n:Company OR n:Person OR n:Organization
                OPTIONAL MATCH (a:Attorney)-[:REPRESENTS]->(p)
                OPTIONAL MATCH (j:Judge)-[:PRESIDES_OVER]->(c)
                RETURN
                    count(DISTINCT c) AS total_cases,
                    count(DISTINCT p) AS total_parties,
                    count(DISTINCT n) AS linked_entities,
                    count(DISTINCT a) AS total_attorneys,
                    count(DISTINCT j) AS total_judges
                """
            )
            record = result.single()
            return {
                "total_cases": record["total_cases"],
                "total_parties": record["total_parties"],
                "linked_entities": record["linked_entities"],
                "total_attorneys": record["total_attorneys"],
                "total_judges": record["total_judges"],
            }


def main():
    """CLI entry point."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Ingest CourtListener cases")
    parser.add_argument("--token", help="CourtListener API token")
    parser.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    parser.add_argument("--neo4j-user", default="neo4j")
    parser.add_argument("--neo4j-password", default="password")

    subparsers = parser.add_subparsers(dest="command")

    # Setup schema
    subparsers.add_parser("setup", help="Create schema constraints")

    # Ingest docket
    docket_parser = subparsers.add_parser("docket", help="Ingest a specific docket")
    docket_parser.add_argument("docket_id", type=int, help="CourtListener docket ID")

    # Ingest for entity
    entity_parser = subparsers.add_parser("entity", help="Ingest cases for an entity")
    entity_parser.add_argument("name", help="Entity name")
    entity_parser.add_argument("--type", default="Company", help="Entity type")
    entity_parser.add_argument("--limit", type=int, default=20, help="Max cases")

    # Stats
    subparsers.add_parser("stats", help="Show case statistics")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ingester = CaseIngester(
        cl_token=args.token or os.environ.get("COURTLISTENER_TOKEN"),
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
    )

    try:
        if args.command == "setup":
            ingester.setup_schema()
            print("Schema created successfully")

        elif args.command == "docket":
            stats = ingester.ingest_docket(args.docket_id)
            print(f"\n=== Ingestion Complete ===")
            print(f"Cases: {stats.cases_created}")
            print(f"Parties: {stats.parties_created}")
            print(f"Errors: {stats.errors}")

        elif args.command == "entity":
            stats = ingester.ingest_cases_for_entity(
                args.name,
                args.type,
                max_cases=args.limit,
            )
            print(f"\n=== Ingestion Complete ===")
            print(f"Cases: {stats.cases_created}")
            print(f"Parties: {stats.parties_created}")
            print(f"Errors: {stats.errors}")

        elif args.command == "stats":
            stats = ingester.get_case_stats()
            print(f"\n=== Court Case Statistics ===")
            for key, value in stats.items():
                print(f"  {key}: {value}")

        else:
            parser.print_help()

    finally:
        ingester.close()


if __name__ == "__main__":
    main()
