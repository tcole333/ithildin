"""
FollowTheMoney (FtM) format importer for OpenSanctions data.

Parses newline-delimited JSON files in FtM format and imports
entities into Neo4j, preserving the original FtM schema and properties.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from neo4j import GraphDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FtMEntity(BaseModel):
    """A FollowTheMoney entity."""

    id: str = Field(..., description="Unique entity ID")
    schema_name: str = Field(..., alias="schema", description="FtM schema type")
    properties: dict = Field(default_factory=dict, description="Entity properties")
    datasets: list[str] = Field(default_factory=list, description="Source datasets")
    referents: list[str] = Field(default_factory=list, description="Merged entity IDs")
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    last_change: Optional[str] = None

    class Config:
        populate_by_name = True


class ImportStats(BaseModel):
    """Statistics from an import operation."""

    total_entities: int = 0
    by_schema: dict = Field(default_factory=dict)
    errors: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0


# Schema queries for OpenSanctions entities
OPENSANCTIONS_SCHEMA_QUERIES = [
    # OpenSanctions entity node
    "CREATE CONSTRAINT os_entity_id IF NOT EXISTS FOR (e:OpenSanctionsEntity) REQUIRE e.os_id IS UNIQUE",
    "CREATE INDEX os_entity_schema IF NOT EXISTS FOR (e:OpenSanctionsEntity) ON (e.ftm_schema)",
    "CREATE INDEX os_entity_name IF NOT EXISTS FOR (e:OpenSanctionsEntity) ON (e.name)",
    "CREATE INDEX os_entity_datasets IF NOT EXISTS FOR (e:OpenSanctionsEntity) ON (e.datasets)",

    # FtM-style Ownership node (for ownership relationships)
    "CREATE CONSTRAINT ftm_ownership_id IF NOT EXISTS FOR (o:Ownership) REQUIRE o.ownership_id IS UNIQUE",
    "CREATE INDEX ftm_ownership_percentage IF NOT EXISTS FOR (o:Ownership) ON (o.percentage)",

    # FtM-style Directorship node
    "CREATE CONSTRAINT ftm_directorship_id IF NOT EXISTS FOR (d:Directorship) REQUIRE d.directorship_id IS UNIQUE",
]


class FtMImporter:
    """
    Import FollowTheMoney format data into Neo4j.

    Supports the OpenSanctions data format including ICIJ Offshore Leaks data.

    Example usage:
        importer = FtMImporter("bolt://localhost:7687", "neo4j", "password")
        importer.setup_schema()
        stats = importer.import_file("entities.ftm.json")
        print(f"Imported {stats.total_entities} entities")
    """

    # FtM schemas that map to Person nodes
    PERSON_SCHEMAS = {"Person", "Suspect", "Defendant", "Applicant"}

    # FtM schemas that map to Company/Organization nodes
    COMPANY_SCHEMAS = {"Company", "PublicBody", "Organization", "LegalEntity"}

    # FtM relationship schemas (interstitial entities)
    RELATIONSHIP_SCHEMAS = {
        "Ownership", "Directorship", "Employment", "Membership",
        "Family", "Representation", "UnknownLink"
    }

    # Schemas we import as-is to OpenSanctionsEntity
    SUPPORTED_SCHEMAS = PERSON_SCHEMAS | COMPANY_SCHEMAS | RELATIONSHIP_SCHEMAS | {
        "Address", "Sanction", "Security", "BankAccount", "CourtCase"
    }

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ):
        """Initialize the importer."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Close database connection."""
        self.driver.close()

    def setup_schema(self):
        """Create schema constraints for OpenSanctions data."""
        with self.driver.session() as session:
            for query in OPENSANCTIONS_SCHEMA_QUERIES:
                try:
                    session.run(query)
                    logger.info(f"Executed: {query[:50]}...")
                except Exception as e:
                    logger.warning(f"Schema query failed (may already exist): {e}")

    def parse_ftm_file(self, file_path: Path) -> Iterator[FtMEntity]:
        """
        Parse a FollowTheMoney NDJSON file.

        Args:
            file_path: Path to the .ftm.json file

        Yields:
            FtMEntity objects
        """
        path = Path(file_path)

        # Handle gzipped files
        if path.suffix == ".gz":
            import gzip
            opener = gzip.open
        else:
            opener = open

        with opener(path, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    yield FtMEntity(**data)
                except Exception as e:
                    logger.warning(f"Error parsing line {line_num}: {e}")
                    continue

    def import_file(
        self,
        file_path: Path,
        batch_size: int = 1000,
        limit: Optional[int] = None,
        filter_schemas: Optional[set[str]] = None,
    ) -> ImportStats:
        """
        Import entities from an FtM file.

        Args:
            file_path: Path to the FtM JSON file
            batch_size: Number of entities per batch
            limit: Maximum entities to import
            filter_schemas: Only import these schema types

        Returns:
            Import statistics
        """
        start_time = datetime.now()
        stats = ImportStats()
        batch = []

        logger.info(f"Starting import from {file_path}")

        for entity in self.parse_ftm_file(file_path):
            # Apply schema filter
            if filter_schemas and entity.schema_name not in filter_schemas:
                stats.skipped += 1
                continue

            # Apply limit
            if limit and stats.total_entities >= limit:
                break

            batch.append(entity)
            stats.total_entities += 1
            stats.by_schema[entity.schema_name] = stats.by_schema.get(entity.schema_name, 0) + 1

            if len(batch) >= batch_size:
                self._import_batch(batch)
                logger.info(f"Imported {stats.total_entities} entities...")
                batch = []

        # Import remaining
        if batch:
            self._import_batch(batch)

        stats.elapsed_seconds = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Import complete: {stats.total_entities} entities in {stats.elapsed_seconds:.1f}s"
        )
        return stats

    def _import_batch(self, entities: list[FtMEntity]) -> None:
        """Import a batch of entities."""
        with self.driver.session() as session:
            for entity in entities:
                try:
                    self._create_entity(session, entity)
                except Exception as e:
                    logger.error(f"Error importing entity {entity.id}: {e}")

    def _create_entity(self, session, entity: FtMEntity) -> None:
        """Create a single entity in Neo4j."""
        # Extract common properties
        name = self._get_property(entity, "name") or self._get_property(entity, "caption")

        # Store as OpenSanctionsEntity for all types
        session.run("""
            MERGE (e:OpenSanctionsEntity {os_id: $os_id})
            SET e.ftm_schema = $schema,
                e.name = $name,
                e.datasets = $datasets,
                e.first_seen = $first_seen,
                e.last_seen = $last_seen,
                e.properties = $properties
        """,
            os_id=entity.id,
            schema=entity.schema_name,
            name=name,
            datasets=entity.datasets,
            first_seen=entity.first_seen,
            last_seen=entity.last_seen,
            properties=json.dumps(entity.properties),
        )

        # Also create typed nodes for key schemas
        if entity.schema_name in self.PERSON_SCHEMAS:
            self._create_person_node(session, entity, name)
        elif entity.schema_name in self.COMPANY_SCHEMAS:
            self._create_company_node(session, entity, name)
        elif entity.schema_name == "Ownership":
            self._create_ownership_node(session, entity)
        elif entity.schema_name == "Directorship":
            self._create_directorship_node(session, entity)
        elif entity.schema_name == "Sanction":
            self._create_sanction_link(session, entity)

    def _create_person_node(self, session, entity: FtMEntity, name: str) -> None:
        """Create or link a Person node."""
        if not name:
            return

        # Get additional person properties
        birth_date = self._get_property(entity, "birthDate")
        nationality = self._get_property(entity, "nationality")

        session.run("""
            MERGE (p:Person {name: $name})
            ON CREATE SET
                p.birth_date = $birth_date,
                p.nationality = $nationality
            WITH p
            MATCH (e:OpenSanctionsEntity {os_id: $os_id})
            MERGE (p)-[:MATCHED_IN_OPENSANCTIONS {confidence: 1.0, match_method: 'same_entity'}]->(e)
        """,
            name=name,
            os_id=entity.id,
            birth_date=birth_date,
            nationality=nationality,
        )

    def _create_company_node(self, session, entity: FtMEntity, name: str) -> None:
        """Create or link a Company/Organization node."""
        if not name:
            return

        # Get company properties
        jurisdiction = self._get_property(entity, "jurisdiction")
        registration_number = self._get_property(entity, "registrationNumber")
        incorporation_date = self._get_property(entity, "incorporationDate")

        # Determine if Company or Organization based on schema
        if entity.schema_name == "Company":
            session.run("""
                MERGE (c:Company {name: $name})
                ON CREATE SET
                    c.jurisdiction = $jurisdiction,
                    c.registration_number = $registration_number,
                    c.incorporation_date = $incorporation_date
                WITH c
                MATCH (e:OpenSanctionsEntity {os_id: $os_id})
                MERGE (c)-[:MATCHED_IN_OPENSANCTIONS {confidence: 1.0, match_method: 'same_entity'}]->(e)
            """,
                name=name,
                os_id=entity.id,
                jurisdiction=jurisdiction,
                registration_number=registration_number,
                incorporation_date=incorporation_date,
            )
        else:
            session.run("""
                MERGE (o:Organization {name: $name})
                ON CREATE SET
                    o.jurisdiction = $jurisdiction,
                    o.registration_number = $registration_number
                WITH o
                MATCH (e:OpenSanctionsEntity {os_id: $os_id})
                MERGE (o)-[:MATCHED_IN_OPENSANCTIONS {confidence: 1.0, match_method: 'same_entity'}]->(e)
            """,
                name=name,
                os_id=entity.id,
                jurisdiction=jurisdiction,
                registration_number=registration_number,
            )

    def _create_ownership_node(self, session, entity: FtMEntity) -> None:
        """Create an Ownership interstitial node."""
        owner_id = self._get_property(entity, "owner")
        asset_id = self._get_property(entity, "asset")
        percentage = self._get_property(entity, "percentage")
        shares_count = self._get_property(entity, "sharesCount")
        start_date = self._get_property(entity, "startDate")
        end_date = self._get_property(entity, "endDate")

        if not owner_id or not asset_id:
            return

        # Generate ownership ID
        ownership_id = hashlib.md5(f"{owner_id}-{asset_id}-{entity.id}".encode()).hexdigest()[:16]

        session.run("""
            MERGE (own:Ownership {ownership_id: $ownership_id})
            SET own.percentage = $percentage,
                own.shares_count = $shares_count,
                own.start_date = $start_date,
                own.end_date = $end_date,
                own.os_entity_id = $os_id
            WITH own
            OPTIONAL MATCH (owner:OpenSanctionsEntity {os_id: $owner_id})
            OPTIONAL MATCH (asset:OpenSanctionsEntity {os_id: $asset_id})
            FOREACH (o IN CASE WHEN owner IS NOT NULL THEN [1] ELSE [] END |
                MERGE (owner)-[:OWNER]->(own)
            )
            FOREACH (a IN CASE WHEN asset IS NOT NULL THEN [1] ELSE [] END |
                MERGE (own)-[:OF]->(asset)
            )
        """,
            ownership_id=ownership_id,
            os_id=entity.id,
            owner_id=owner_id,
            asset_id=asset_id,
            percentage=percentage,
            shares_count=shares_count,
            start_date=start_date,
            end_date=end_date,
        )

    def _create_directorship_node(self, session, entity: FtMEntity) -> None:
        """Create a Directorship interstitial node."""
        director_id = self._get_property(entity, "director")
        org_id = self._get_property(entity, "organization")
        role = self._get_property(entity, "role")
        start_date = self._get_property(entity, "startDate")
        end_date = self._get_property(entity, "endDate")

        if not director_id or not org_id:
            return

        directorship_id = hashlib.md5(f"{director_id}-{org_id}-{entity.id}".encode()).hexdigest()[:16]

        session.run("""
            MERGE (d:Directorship {directorship_id: $directorship_id})
            SET d.role = $role,
                d.start_date = $start_date,
                d.end_date = $end_date,
                d.os_entity_id = $os_id
            WITH d
            OPTIONAL MATCH (director:OpenSanctionsEntity {os_id: $director_id})
            OPTIONAL MATCH (org:OpenSanctionsEntity {os_id: $org_id})
            FOREACH (dir IN CASE WHEN director IS NOT NULL THEN [1] ELSE [] END |
                MERGE (director)-[:HOLDS]->(d)
            )
            FOREACH (o IN CASE WHEN org IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:AT]->(org)
            )
        """,
            directorship_id=directorship_id,
            os_id=entity.id,
            director_id=director_id,
            org_id=org_id,
            role=role,
            start_date=start_date,
            end_date=end_date,
        )

    def _create_sanction_link(self, session, entity: FtMEntity) -> None:
        """Create sanction relationship to target entity."""
        target_id = self._get_property(entity, "entity")
        authority = self._get_property(entity, "authority")
        program = self._get_property(entity, "program")

        if not target_id:
            return

        session.run("""
            MATCH (target:OpenSanctionsEntity {os_id: $target_id})
            SET target.is_sanctioned = true,
                target.sanction_authority = $authority,
                target.sanction_program = $program
        """,
            target_id=target_id,
            authority=authority,
            program=program,
        )

    @staticmethod
    def _get_property(entity: FtMEntity, prop_name: str) -> Optional[str]:
        """Get first value of a property (FtM properties are multi-valued)."""
        values = entity.properties.get(prop_name, [])
        if values and isinstance(values, list):
            return values[0] if values else None
        return values if values else None


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Import OpenSanctions FtM data")
    parser.add_argument("--file", "-f", required=True, help="FtM JSON file to import")
    parser.add_argument("--limit", "-l", type=int, help="Maximum entities to import")
    parser.add_argument("--batch-size", "-b", type=int, default=1000, help="Batch size")
    parser.add_argument("--setup-schema", action="store_true", help="Set up schema first")
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j user")
    parser.add_argument("--password", default="password", help="Neo4j password")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    importer = FtMImporter(args.uri, args.user, args.password)

    try:
        if args.setup_schema:
            importer.setup_schema()

        stats = importer.import_file(
            Path(args.file),
            batch_size=args.batch_size,
            limit=args.limit,
        )

        print(f"\n=== Import Complete ===")
        print(f"Total entities: {stats.total_entities}")
        print(f"By schema:")
        for schema, count in sorted(stats.by_schema.items(), key=lambda x: -x[1]):
            print(f"  {schema}: {count}")
        print(f"Time: {stats.elapsed_seconds:.1f}s")

    finally:
        importer.close()


if __name__ == "__main__":
    main()
