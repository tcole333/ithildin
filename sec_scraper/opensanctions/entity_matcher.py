"""
Entity matcher for cross-referencing OpenSanctions entities with existing database nodes.

Matches imported OpenSanctions/ICIJ entities against:
- Existing Company, Person, Organization nodes
- Existing OffshoreEntity nodes (from ICIJ import)
- EntityAlias records

Uses confidence scoring similar to our existing entity resolution.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of matching an OpenSanctions entity."""

    os_id: str
    os_name: str
    os_schema: str
    matched_node_type: Optional[str] = None
    matched_node_name: Optional[str] = None
    matched_node_id: Optional[str] = None
    confidence: float = 0.0
    match_method: str = "none"
    alternatives: list = field(default_factory=list)


class EntityMatcher:
    """
    Match OpenSanctions entities against existing database entities.

    Thresholds:
        >= 0.85: Auto-match (create link)
        0.50-0.85: Create link but flag for review
        < 0.50: No automatic match

    Example usage:
        matcher = EntityMatcher("bolt://localhost:7687", "neo4j", "password")
        results = matcher.match_all_pending()
        for r in results:
            print(f"{r.os_name} -> {r.matched_node_name} ({r.confidence})")
    """

    # Match score thresholds
    AUTO_MATCH_THRESHOLD = 0.85
    REVIEW_THRESHOLD = 0.50

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        """Initialize the matcher."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close database connection."""
        self.driver.close()

    def normalize_name(self, name: str) -> str:
        """Normalize a name for matching."""
        if not name:
            return ""
        # Uppercase and remove common suffixes
        normalized = name.upper()
        for suffix in [
            " INC", " CORP", " CO", " LTD", " LLC", " LP", " L.P.",
            " SA", " AG", " NV", " BV", " GMBH", " PLC", " LIMITED",
            " TRUST", " FOUNDATION", " ET AL", ".",
        ]:
            normalized = normalized.replace(suffix, "")
        return normalized.strip()

    def match_os_entity(self, os_id: str) -> MatchResult:
        """
        Find matches for a single OpenSanctions entity.

        Args:
            os_id: OpenSanctions entity ID

        Returns:
            MatchResult with best match and alternatives
        """
        with self.driver.session() as session:
            # Get the OS entity
            result = session.run("""
                MATCH (e:OpenSanctionsEntity {os_id: $os_id})
                RETURN e.name AS name, e.ftm_schema AS schema, e.properties AS properties
            """, os_id=os_id)

            record = result.single()
            if not record:
                return MatchResult(os_id=os_id, os_name="", os_schema="")

            os_name = record["name"] or ""
            os_schema = record["schema"] or ""

            match_result = MatchResult(
                os_id=os_id,
                os_name=os_name,
                os_schema=os_schema,
            )

            normalized = self.normalize_name(os_name)
            if not normalized:
                return match_result

            # Try exact name match
            matches = self._find_exact_matches(session, normalized, os_schema)

            if matches:
                best = matches[0]
                match_result.matched_node_type = best["type"]
                match_result.matched_node_name = best["name"]
                match_result.matched_node_id = best.get("id")
                match_result.confidence = 1.0
                match_result.match_method = "exact_name"
                match_result.alternatives = matches[1:5]
                return match_result

            # Try fuzzy matching via existing OffshoreEntity
            offshore_matches = self._find_offshore_matches(session, normalized)
            if offshore_matches:
                best = offshore_matches[0]
                match_result.matched_node_type = "OffshoreEntity"
                match_result.matched_node_name = best["name"]
                match_result.matched_node_id = best["node_id"]
                match_result.confidence = 0.90  # High confidence for ICIJ overlap
                match_result.match_method = "offshore_overlap"
                match_result.alternatives = offshore_matches[1:5]
                return match_result

            # Try partial name matching
            partial_matches = self._find_partial_matches(session, normalized, os_schema)
            if partial_matches:
                best = partial_matches[0]
                match_result.matched_node_type = best["type"]
                match_result.matched_node_name = best["name"]
                match_result.matched_node_id = best.get("id")
                match_result.confidence = best.get("score", 0.6)
                match_result.match_method = "partial_name"
                match_result.alternatives = partial_matches[1:5]

            return match_result

    def _find_exact_matches(self, session, normalized_name: str, schema: str) -> list[dict]:
        """Find exact name matches in existing entities."""
        # Determine which node types to search based on schema
        if schema in {"Person", "Suspect", "Defendant"}:
            node_labels = ["Person"]
        elif schema in {"Company", "Organization", "PublicBody", "LegalEntity"}:
            node_labels = ["Company", "Organization"]
        else:
            node_labels = ["Company", "Organization", "Person"]

        matches = []
        for label in node_labels:
            result = session.run(f"""
                MATCH (n:{label})
                WHERE toUpper(n.name) = $normalized
                RETURN '{label}' AS type, n.name AS name, id(n) AS id
                LIMIT 5
            """, normalized=normalized_name)
            matches.extend([dict(r) for r in result])

        return matches

    def _find_offshore_matches(self, session, normalized_name: str) -> list[dict]:
        """Find matches in existing OffshoreEntity nodes."""
        result = session.run("""
            MATCH (o:OffshoreEntity)
            WHERE toUpper(o.name) = $normalized
            RETURN o.node_id AS node_id, o.name AS name, o.source_leak AS source
            LIMIT 10
        """, normalized=normalized_name)

        return [dict(r) for r in result]

    def _find_partial_matches(self, session, normalized_name: str, schema: str) -> list[dict]:
        """Find partial name matches with scoring."""
        # Get significant name parts (at least 4 chars)
        parts = [p for p in normalized_name.split() if len(p) >= 4]
        if not parts:
            return []

        # Search for entities containing the significant parts
        if schema in {"Person", "Suspect", "Defendant"}:
            node_labels = ["Person"]
        elif schema in {"Company", "Organization", "PublicBody", "LegalEntity"}:
            node_labels = ["Company", "Organization"]
        else:
            node_labels = ["Company", "Organization", "Person"]

        matches = []
        for label in node_labels:
            for part in parts[:3]:  # First 3 significant words
                result = session.run(f"""
                    MATCH (n:{label})
                    WHERE toUpper(n.name) CONTAINS $part
                    WITH n, '{label}' AS type,
                         CASE WHEN toUpper(n.name) STARTS WITH $part THEN 0.7
                              WHEN toUpper(n.name) CONTAINS ' ' + $part + ' ' THEN 0.65
                              ELSE 0.55 END AS score
                    RETURN type, n.name AS name, id(n) AS id, score
                    ORDER BY score DESC
                    LIMIT 5
                """, part=part)

                for record in result:
                    # Avoid duplicates
                    if not any(m["name"] == record["name"] for m in matches):
                        matches.append(dict(record))

        # Sort by score
        matches.sort(key=lambda x: x.get("score", 0), reverse=True)
        return matches[:10]

    def match_all_pending(self, limit: int = 1000) -> list[MatchResult]:
        """
        Match all OpenSanctions entities that don't have matches yet.

        Args:
            limit: Maximum entities to process

        Returns:
            List of MatchResults
        """
        results = []

        with self.driver.session() as session:
            # Find unmatched OS entities
            query_result = session.run("""
                MATCH (e:OpenSanctionsEntity)
                WHERE NOT (e)<-[:MATCHED_IN_OPENSANCTIONS]-()
                AND e.name IS NOT NULL
                RETURN e.os_id AS os_id
                LIMIT $limit
            """, limit=limit)

            os_ids = [record["os_id"] for record in query_result]

        logger.info(f"Matching {len(os_ids)} unmatched OpenSanctions entities")

        for i, os_id in enumerate(os_ids):
            match_result = self.match_os_entity(os_id)
            results.append(match_result)

            # Auto-create links for high-confidence matches
            if match_result.confidence >= self.AUTO_MATCH_THRESHOLD:
                self._create_match_link(match_result, needs_review=False)
            elif match_result.confidence >= self.REVIEW_THRESHOLD:
                self._create_match_link(match_result, needs_review=True)

            if (i + 1) % 100 == 0:
                logger.info(f"Processed {i + 1}/{len(os_ids)} entities")

        return results

    def _create_match_link(self, match: MatchResult, needs_review: bool = False) -> None:
        """Create a relationship link for a match."""
        if not match.matched_node_name or not match.matched_node_type:
            return

        with self.driver.session() as session:
            # Create link from existing entity to OpenSanctions entity
            session.run(f"""
                MATCH (n:{match.matched_node_type} {{name: $name}})
                MATCH (e:OpenSanctionsEntity {{os_id: $os_id}})
                MERGE (n)-[r:MATCHED_IN_OPENSANCTIONS]->(e)
                SET r.confidence = $confidence,
                    r.match_method = $method,
                    r.needs_review = $needs_review
            """,
                name=match.matched_node_name,
                os_id=match.os_id,
                confidence=match.confidence,
                method=match.match_method,
                needs_review=needs_review,
            )

    def cross_reference_offshore(self) -> dict:
        """
        Cross-reference OpenSanctions ICIJ data with existing OffshoreEntity nodes.

        Returns:
            Statistics about matches found
        """
        stats = {"matched": 0, "unmatched": 0}

        with self.driver.session() as session:
            # Match by exact normalized name
            result = session.run("""
                MATCH (e:OpenSanctionsEntity)
                WHERE 'icij_offshoreleaks' IN e.datasets
                OR 'panama_papers' IN e.datasets
                OR 'paradise_papers' IN e.datasets
                MATCH (o:OffshoreEntity)
                WHERE toUpper(o.name) = toUpper(e.name)
                MERGE (o)-[r:SAME_AS_OPENSANCTIONS]->(e)
                SET r.match_method = 'name_match'
                RETURN count(r) AS matched
            """)

            stats["matched"] = result.single()["matched"]

            # Count unmatched
            result = session.run("""
                MATCH (e:OpenSanctionsEntity)
                WHERE ('icij_offshoreleaks' IN e.datasets
                    OR 'panama_papers' IN e.datasets
                    OR 'paradise_papers' IN e.datasets)
                AND NOT (e)<-[:SAME_AS_OPENSANCTIONS]-()
                RETURN count(e) AS unmatched
            """)

            stats["unmatched"] = result.single()["unmatched"]

        logger.info(f"Cross-reference complete: {stats['matched']} matched, {stats['unmatched']} unmatched")
        return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Match OpenSanctions entities")
    parser.add_argument("--match-all", action="store_true", help="Match all pending entities")
    parser.add_argument("--cross-ref-offshore", action="store_true", help="Cross-reference with OffshoreEntity")
    parser.add_argument("--match-id", help="Match a specific OS entity ID")
    parser.add_argument("--limit", type=int, default=1000, help="Limit for batch operations")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j user")
    parser.add_argument("--password", default="password", help="Neo4j password")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    matcher = EntityMatcher(args.uri, args.user, args.password)

    try:
        if args.match_id:
            result = matcher.match_os_entity(args.match_id)
            print(f"\n=== Match Result ===")
            print(f"OS Entity: {result.os_name} ({result.os_schema})")
            if result.matched_node_name:
                print(f"Matched: {result.matched_node_type}:{result.matched_node_name}")
                print(f"Confidence: {result.confidence:.2f}")
                print(f"Method: {result.match_method}")
            else:
                print("No match found")

        elif args.cross_ref_offshore:
            stats = matcher.cross_reference_offshore()
            print(f"\n=== Cross-Reference Complete ===")
            print(f"Matched: {stats['matched']}")
            print(f"Unmatched: {stats['unmatched']}")

        elif args.match_all:
            results = matcher.match_all_pending(limit=args.limit)
            matched = sum(1 for r in results if r.confidence >= matcher.REVIEW_THRESHOLD)
            print(f"\n=== Matching Complete ===")
            print(f"Processed: {len(results)}")
            print(f"Matched (>= {matcher.REVIEW_THRESHOLD}): {matched}")

    finally:
        matcher.close()


if __name__ == "__main__":
    main()
