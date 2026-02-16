"""
CLI entry point for OpenSanctions integration.

Usage:
    python -m sec_scraper.opensanctions --help
    python -m sec_scraper.opensanctions --import-ftm entities.ftm.json
    python -m sec_scraper.opensanctions --match-entities
    python -m sec_scraper.opensanctions --check-sanctions "Entity Name"
"""

import argparse
import logging
import sys
from pathlib import Path

from .ftm_importer import FtMImporter
from .entity_matcher import EntityMatcher
from .sanctions_checker import SanctionsChecker


def main():
    parser = argparse.ArgumentParser(
        description="OpenSanctions integration tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import OpenSanctions ICIJ dataset
  python -m sec_scraper.opensanctions --import-ftm icij_offshoreleaks.ftm.json

  # Match imported entities with existing database
  python -m sec_scraper.opensanctions --match-entities --limit 1000

  # Check a name against sanctions lists
  python -m sec_scraper.opensanctions --check-sanctions "Carl Icahn"

  # Cross-reference with existing OffshoreEntity nodes
  python -m sec_scraper.opensanctions --cross-ref-offshore

  # Batch check all entities for sanctions
  python -m sec_scraper.opensanctions --check-all-sanctions
        """
    )

    # Connection options
    parser.add_argument("--uri", default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--user", default="neo4j", help="Neo4j user")
    parser.add_argument("--password", default="password", help="Neo4j password")

    # Import operations
    import_group = parser.add_argument_group("Import Operations")
    import_group.add_argument(
        "--import-ftm", "-i", metavar="FILE",
        help="Import FtM JSON file (supports .ftm.json and .ftm.json.gz)"
    )
    import_group.add_argument("--batch-size", type=int, default=1000, help="Import batch size")
    import_group.add_argument("--setup-schema", action="store_true", help="Set up schema before import")

    # Matching operations
    match_group = parser.add_argument_group("Matching Operations")
    match_group.add_argument("--match-entities", action="store_true", help="Match unmatched OS entities")
    match_group.add_argument("--match-id", metavar="OS_ID", help="Match a specific OS entity ID")
    match_group.add_argument("--cross-ref-offshore", action="store_true", help="Cross-reference with OffshoreEntity")

    # Sanctions checking
    sanctions_group = parser.add_argument_group("Sanctions Checking")
    sanctions_group.add_argument("--check-sanctions", metavar="NAME", help="Check a name against sanctions")
    sanctions_group.add_argument("--check-all-sanctions", action="store_true", help="Check all entities")
    sanctions_group.add_argument("--flag-sanctioned", action="store_true", help="Add sanctions flags to entities")
    sanctions_group.add_argument("--entity-type", choices=["Person", "Company", "Organization"], help="Filter by type")

    # Common options
    parser.add_argument("--limit", "-l", type=int, help="Limit for batch operations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    # Handle import operation
    if args.import_ftm:
        importer = FtMImporter(args.uri, args.user, args.password)
        try:
            if args.setup_schema:
                print("Setting up schema...")
                importer.setup_schema()

            print(f"Importing from {args.import_ftm}...")
            stats = importer.import_file(
                Path(args.import_ftm),
                batch_size=args.batch_size,
                limit=args.limit,
            )

            print(f"\n=== Import Complete ===")
            print(f"Total entities: {stats.total_entities}")
            print(f"Time: {stats.elapsed_seconds:.1f}s")
            print(f"\nBy schema:")
            for schema, count in sorted(stats.by_schema.items(), key=lambda x: -x[1])[:15]:
                print(f"  {schema}: {count:,}")
        finally:
            importer.close()
        return

    # Handle matching operations
    if args.match_entities or args.match_id or args.cross_ref_offshore:
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
                print("Cross-referencing with OffshoreEntity nodes...")
                stats = matcher.cross_reference_offshore()
                print(f"\n=== Cross-Reference Complete ===")
                print(f"Matched: {stats['matched']}")
                print(f"Unmatched: {stats['unmatched']}")

            elif args.match_entities:
                limit = args.limit or 1000
                print(f"Matching up to {limit} unmatched entities...")
                results = matcher.match_all_pending(limit=limit)
                matched = sum(1 for r in results if r.confidence >= matcher.REVIEW_THRESHOLD)
                print(f"\n=== Matching Complete ===")
                print(f"Processed: {len(results)}")
                print(f"Matched (>= {matcher.REVIEW_THRESHOLD}): {matched}")
        finally:
            matcher.close()
        return

    # Handle sanctions operations
    if args.check_sanctions or args.check_all_sanctions or args.flag_sanctioned:
        checker = SanctionsChecker(args.uri, args.user, args.password)
        try:
            if args.check_sanctions:
                result = checker.check_entity(
                    args.check_sanctions,
                    args.entity_type or "Person"
                )
                print(f"\n=== Sanctions Check: {args.check_sanctions} ===")
                print(f"Sanctioned: {result.is_sanctioned}")
                print(f"PEP: {result.is_pep}")
                print(f"Criminal: {result.is_criminal}")
                print(f"Debarred: {result.is_debarred}")
                if result.matched_os_entities:
                    print(f"\nMatches ({len(result.matched_os_entities)}):")
                    for m in result.matched_os_entities[:5]:
                        print(f"  - {m['name']} ({m['schema']})")
                        if m.get('datasets'):
                            print(f"    Datasets: {', '.join(m['datasets'][:3])}")

            elif args.check_all_sanctions:
                limit = args.limit or 10000
                print(f"Checking up to {limit} entities...")
                stats = checker.check_all_entities(
                    entity_type=args.entity_type,
                    limit=limit
                )
                print(f"\n=== Sanctions Check Complete ===")
                print(f"Checked: {stats['checked']}")
                print(f"Sanctioned: {len(stats['sanctioned'])}")
                print(f"PEPs: {len(stats['peps'])}")
                print(f"Criminal: {len(stats['criminal'])}")
                print(f"Debarred: {len(stats['debarred'])}")

                if stats['sanctioned']:
                    print(f"\n--- Sanctioned Entities ---")
                    for e in stats['sanctioned'][:10]:
                        print(f"  {e['name']} ({e['type']})")

            elif args.flag_sanctioned:
                flagged = checker.flag_sanctioned_entities()
                print(f"Flagged {flagged} entities as sanctioned")
        finally:
            checker.close()
        return

    # No operation specified
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
