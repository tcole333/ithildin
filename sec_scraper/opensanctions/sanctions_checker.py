"""
Sanctions and PEP status checker.

Checks entities in the database against OpenSanctions data to identify:
- Sanctioned entities (on OFAC, EU, UK, or other sanctions lists)
- Politically Exposed Persons (PEPs)
- Criminal watchlist entries
- Debarred entities
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


@dataclass
class SanctionsCheckResult:
    """Result of checking an entity against sanctions data."""

    entity_name: str
    entity_type: str  # Person, Company, Organization
    is_sanctioned: bool = False
    is_pep: bool = False
    is_criminal: bool = False
    is_debarred: bool = False
    sanction_programs: list = field(default_factory=list)
    sanction_authorities: list = field(default_factory=list)
    pep_positions: list = field(default_factory=list)
    matched_os_entities: list = field(default_factory=list)
    check_date: str = field(default_factory=lambda: datetime.now().isoformat())


class SanctionsChecker:
    """
    Check entities against OpenSanctions sanctions/PEP data.

    Requires OpenSanctions data to be imported first via FtMImporter.

    Example usage:
        checker = SanctionsChecker("bolt://localhost:7687", "neo4j", "password")
        result = checker.check_entity("John Doe", "Person")
        if result.is_sanctioned:
            print(f"ALERT: {result.sanction_programs}")
    """

    # OpenSanctions dataset categories
    SANCTIONS_DATASETS = {
        "us_ofac_sdn", "us_ofac_cons", "eu_fsf", "gb_hmt_sanctions",
        "un_sc_sanctions", "ch_seco_sanctions", "au_dfat_sanctions"
    }

    PEP_DATASETS = {
        "everypolitician", "ru_dossier", "us_congress", "eu_meps",
        "gb_parliament", "worldleaders", "pep"
    }

    CRIMINAL_DATASETS = {
        "interpol_red_notices", "fbi_most_wanted", "europol_most_wanted"
    }

    DEBARMENT_DATASETS = {
        "us_bis_denied", "world_bank_debarred", "us_gsa_debarred"
    }

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        """Initialize the checker."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close database connection."""
        self.driver.close()

    def normalize_name(self, name: str) -> str:
        """Normalize name for matching."""
        if not name:
            return ""
        normalized = name.upper()
        for suffix in [" INC", " CORP", " CO", " LTD", " LLC", " LP"]:
            normalized = normalized.replace(suffix, "")
        return normalized.strip()

    def check_entity(
        self,
        name: str,
        entity_type: str = "Person",
        fuzzy: bool = True,
    ) -> SanctionsCheckResult:
        """
        Check a single entity against sanctions/PEP data.

        Args:
            name: Entity name to check
            entity_type: Person, Company, or Organization
            fuzzy: Whether to use fuzzy matching

        Returns:
            SanctionsCheckResult with status flags
        """
        result = SanctionsCheckResult(entity_name=name, entity_type=entity_type)
        normalized = self.normalize_name(name)

        if not normalized:
            return result

        with self.driver.session() as session:
            # Find matching OpenSanctions entities
            if fuzzy:
                matches = self._fuzzy_search(session, normalized)
            else:
                matches = self._exact_search(session, normalized)

            for match in matches:
                result.matched_os_entities.append({
                    "os_id": match["os_id"],
                    "name": match["name"],
                    "schema": match["schema"],
                    "datasets": match["datasets"],
                })

                # Check dataset categories
                datasets = set(match.get("datasets") or [])

                # Sanctions check
                if datasets & self.SANCTIONS_DATASETS:
                    result.is_sanctioned = True
                    # Get sanction details
                    if match.get("sanction_authority"):
                        result.sanction_authorities.append(match["sanction_authority"])
                    if match.get("sanction_program"):
                        result.sanction_programs.append(match["sanction_program"])

                # PEP check
                if datasets & self.PEP_DATASETS:
                    result.is_pep = True
                    if match.get("position"):
                        result.pep_positions.append(match["position"])

                # Criminal check
                if datasets & self.CRIMINAL_DATASETS:
                    result.is_criminal = True

                # Debarment check
                if datasets & self.DEBARMENT_DATASETS:
                    result.is_debarred = True

        return result

    def _exact_search(self, session, normalized_name: str) -> list[dict]:
        """Find exact name matches in OpenSanctions data."""
        result = session.run("""
            MATCH (e:OpenSanctionsEntity)
            WHERE toUpper(e.name) = $normalized
            RETURN e.os_id AS os_id,
                   e.name AS name,
                   e.ftm_schema AS schema,
                   e.datasets AS datasets,
                   e.sanction_authority AS sanction_authority,
                   e.sanction_program AS sanction_program
        """, normalized=normalized_name)

        return [dict(r) for r in result]

    def _fuzzy_search(self, session, normalized_name: str) -> list[dict]:
        """Find fuzzy name matches in OpenSanctions data."""
        # First try exact match
        matches = self._exact_search(session, normalized_name)

        # If no exact match, try partial matching
        if not matches:
            # Get significant name parts
            parts = [p for p in normalized_name.split() if len(p) >= 4]
            if len(parts) >= 2:
                result = session.run("""
                    MATCH (e:OpenSanctionsEntity)
                    WHERE toUpper(e.name) CONTAINS $part1
                    AND toUpper(e.name) CONTAINS $part2
                    RETURN e.os_id AS os_id,
                           e.name AS name,
                           e.ftm_schema AS schema,
                           e.datasets AS datasets,
                           e.sanction_authority AS sanction_authority,
                           e.sanction_program AS sanction_program
                    LIMIT 10
                """, part1=parts[0], part2=parts[1])
                matches = [dict(r) for r in result]

        return matches

    def check_all_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 10000,
    ) -> dict:
        """
        Check all entities in database against sanctions data.

        Args:
            entity_type: Filter to Person, Company, or Organization
            limit: Maximum entities to check

        Returns:
            Summary statistics and flagged entities
        """
        stats = {
            "checked": 0,
            "sanctioned": [],
            "peps": [],
            "criminal": [],
            "debarred": [],
        }

        with self.driver.session() as session:
            # Get all entities to check
            if entity_type:
                query = f"""
                    MATCH (n:{entity_type})
                    RETURN n.name AS name, '{entity_type}' AS type
                    LIMIT $limit
                """
            else:
                query = """
                    MATCH (n)
                    WHERE n:Person OR n:Company OR n:Organization
                    RETURN n.name AS name,
                           CASE
                               WHEN n:Person THEN 'Person'
                               WHEN n:Company THEN 'Company'
                               ELSE 'Organization'
                           END AS type
                    LIMIT $limit
                """

            result = session.run(query, limit=limit)
            entities = [(r["name"], r["type"]) for r in result]

        logger.info(f"Checking {len(entities)} entities against sanctions data")

        for i, (name, etype) in enumerate(entities):
            if not name:
                continue

            check_result = self.check_entity(name, etype)
            stats["checked"] += 1

            if check_result.is_sanctioned:
                stats["sanctioned"].append({
                    "name": name,
                    "type": etype,
                    "programs": check_result.sanction_programs,
                    "authorities": check_result.sanction_authorities,
                })

            if check_result.is_pep:
                stats["peps"].append({
                    "name": name,
                    "type": etype,
                    "positions": check_result.pep_positions,
                })

            if check_result.is_criminal:
                stats["criminal"].append({"name": name, "type": etype})

            if check_result.is_debarred:
                stats["debarred"].append({"name": name, "type": etype})

            if (i + 1) % 500 == 0:
                logger.info(f"Checked {i + 1}/{len(entities)} entities")

        logger.info(
            f"Check complete: {len(stats['sanctioned'])} sanctioned, "
            f"{len(stats['peps'])} PEPs, {len(stats['criminal'])} criminal"
        )

        return stats

    def flag_sanctioned_entities(self) -> int:
        """
        Add sanctions flags to entities that have OpenSanctions matches.

        Returns:
            Number of entities flagged
        """
        with self.driver.session() as session:
            # Flag entities linked to sanctioned OpenSanctions entries
            result = session.run("""
                MATCH (n)-[:MATCHED_IN_OPENSANCTIONS]->(e:OpenSanctionsEntity)
                WHERE e.is_sanctioned = true
                SET n.sanctions_flag = true,
                    n.sanctions_check_date = datetime()
                RETURN count(n) AS flagged
            """)

            flagged = result.single()["flagged"]
            logger.info(f"Flagged {flagged} entities as sanctioned")
            return flagged


def main():
    """CLI entry point."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Check entities against sanctions")
    parser.add_argument("--check-name", help="Check a specific name")
    parser.add_argument("--check-all", action="store_true", help="Check all entities")
    parser.add_argument("--flag", action="store_true", help="Add sanctions flags to entities")
    parser.add_argument("--type", choices=["Person", "Company", "Organization"], help="Entity type filter")
    parser.add_argument("--limit", type=int, default=10000, help="Limit for batch operations")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j user")
    parser.add_argument("--password", default="password", help="Neo4j password")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    checker = SanctionsChecker(args.uri, args.user, args.password)

    try:
        if args.check_name:
            result = checker.check_entity(args.check_name, args.type or "Person")
            print(f"\n=== Sanctions Check: {args.check_name} ===")
            print(f"Sanctioned: {result.is_sanctioned}")
            print(f"PEP: {result.is_pep}")
            print(f"Criminal: {result.is_criminal}")
            print(f"Debarred: {result.is_debarred}")
            if result.matched_os_entities:
                print(f"Matches: {len(result.matched_os_entities)}")
                for m in result.matched_os_entities[:5]:
                    print(f"  - {m['name']} ({m['schema']})")

        elif args.check_all:
            stats = checker.check_all_entities(entity_type=args.type, limit=args.limit)
            print(f"\n=== Sanctions Check Complete ===")
            print(f"Checked: {stats['checked']}")
            print(f"Sanctioned: {len(stats['sanctioned'])}")
            print(f"PEPs: {len(stats['peps'])}")
            print(f"Criminal: {len(stats['criminal'])}")
            print(f"Debarred: {len(stats['debarred'])}")

            if stats['sanctioned']:
                print(f"\n--- Sanctioned Entities ---")
                for e in stats['sanctioned'][:10]:
                    print(f"  {e['name']} ({e['type']}): {e['programs']}")

        elif args.flag:
            flagged = checker.flag_sanctioned_entities()
            print(f"Flagged {flagged} entities")

    finally:
        checker.close()


if __name__ == "__main__":
    main()
