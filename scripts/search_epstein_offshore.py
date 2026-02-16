#!/usr/bin/env python3
"""
Batch search Epstein-related entities against ICIJ Offshore Leaks database.
Usage: python3 scripts/search_epstein_offshore.py
"""

import json
import sys
from datetime import datetime
from neo4j import GraphDatabase

# ICIJ Offshore Leaks database (no auth)
ICIJ_URI = "bolt://localhost:7689"

# Entities to search
PEOPLE = [
    "Ghislaine Maxwell",
    "Jeffrey Epstein",
    "Leslie Wexner",
    "Leon Black",
    "Jean Luc Brunel",
    "Darren Indyke",
    "Richard Kahn",
    "Sarah Kellen",
    "Erika Kellerhals",
    "Harry Beller",
]

COMPANIES = [
    "Financial Trust",
    "Southern Trust",
    "Southern Financial",
    "JEGE",
    "Hyperion Air",
    "Air Ghislaine",
    "Shmitka Air",
    "Freedom Air",
    "Plan D",
    "Zorro",
    "Butterfly Trust",
    "Haze Trust",
    "NES LLC",
    "LSJ LLC",
    "LSJE LLC",
    "MC2 Model",
    "Forums LLC",
    "COUQ Foundation",
    "C.O.U.Q.",
    "Jeepers",
    "Neptune",
    "Laurel Inc",
    "Ranch Lake",
    "Mort Inc",
    "Thomas World Air",
    "Lafayette",
    "LCP Company",
    "Maple Inc",
    "Nautilus",
    "Cypress Inc",
    "Wexner",
]


def search_offshore(driver, name: str) -> list[dict]:
    """Search ICIJ database for entity name."""
    with driver.session() as session:
        # Try different node types - ICIJ uses Entity, Officer, Intermediary, Address
        results = []

        # Search all node types with fuzzy matching
        query = """
        CALL {
            MATCH (n:Entity)
            WHERE toLower(n.name) CONTAINS toLower($name)
            RETURN n, labels(n) as types, 'Entity' as node_type
            UNION
            MATCH (n:Officer)
            WHERE toLower(n.name) CONTAINS toLower($name)
            RETURN n, labels(n) as types, 'Officer' as node_type
            UNION
            MATCH (n:Intermediary)
            WHERE toLower(n.name) CONTAINS toLower($name)
            RETURN n, labels(n) as types, 'Intermediary' as node_type
        }
        RETURN n.name as name,
               n.node_id as node_id,
               n.jurisdiction as jurisdiction,
               n.jurisdiction_description as jurisdiction_desc,
               n.countries as countries,
               n.sourceID as source,
               node_type,
               types
        LIMIT 50
        """

        try:
            result = session.run(query, name=name)
            for record in result:
                results.append({
                    "name": record["name"],
                    "node_id": record["node_id"],
                    "jurisdiction": record["jurisdiction"],
                    "jurisdiction_desc": record["jurisdiction_desc"],
                    "countries": record["countries"],
                    "source": record["source"],
                    "node_type": record["node_type"],
                })
        except Exception as e:
            # Try simpler query if CALL fails
            for node_type in ["Entity", "Officer", "Intermediary"]:
                try:
                    simple_query = f"""
                    MATCH (n:{node_type})
                    WHERE toLower(n.name) CONTAINS toLower($name)
                    RETURN n.name as name,
                           n.node_id as node_id,
                           n.jurisdiction as jurisdiction,
                           n.jurisdiction_description as jurisdiction_desc,
                           n.countries as countries,
                           n.sourceID as source
                    LIMIT 20
                    """
                    result = session.run(simple_query, name=name)
                    for record in result:
                        results.append({
                            "name": record["name"],
                            "node_id": record["node_id"],
                            "jurisdiction": record["jurisdiction"],
                            "jurisdiction_desc": record["jurisdiction_desc"],
                            "countries": record["countries"],
                            "source": record["source"],
                            "node_type": node_type,
                        })
                except:
                    pass

        return results


def get_connections(driver, node_id: str) -> list[dict]:
    """Get connected entities for a node."""
    with driver.session() as session:
        query = """
        MATCH (n)-[r]-(connected)
        WHERE n.node_id = $node_id
        RETURN type(r) as relationship,
               connected.name as connected_name,
               connected.node_id as connected_id,
               labels(connected) as connected_type
        LIMIT 20
        """

        try:
            result = session.run(query, node_id=node_id)
            return [dict(record) for record in result]
        except:
            return []


def main():
    print("=" * 60)
    print("EPSTEIN ENTITY CROSS-REFERENCE: ICIJ Offshore Leaks")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    try:
        driver = GraphDatabase.driver(ICIJ_URI)
        # Test connection
        with driver.session() as session:
            session.run("RETURN 1")
        print(f"\nConnected to ICIJ database at {ICIJ_URI}\n")
    except Exception as e:
        print(f"\nERROR: Cannot connect to ICIJ database at {ICIJ_URI}")
        print(f"Please start the database with: ./scripts/start_icij_db.sh")
        print(f"Error: {e}")
        sys.exit(1)

    all_matches = []

    # Search people
    print("\n" + "=" * 40)
    print("SEARCHING PEOPLE")
    print("=" * 40)

    for name in PEOPLE:
        matches = search_offshore(driver, name)
        if matches:
            print(f"\n[FOUND] {name}: {len(matches)} match(es)")
            for m in matches:
                print(f"  - {m['name']}")
                print(f"    Type: {m['node_type']} | Jurisdiction: {m.get('jurisdiction', 'N/A')}")
                print(f"    Source: {m.get('source', 'N/A')}")

                # Get connections for interesting matches
                if m.get('node_id'):
                    connections = get_connections(driver, m['node_id'])
                    if connections:
                        print(f"    Connections:")
                        for c in connections[:5]:
                            print(f"      -> {c.get('relationship', '?')}: {c.get('connected_name', '?')}")

                all_matches.append({"search_term": name, "category": "person", **m})
        else:
            print(f"[  --  ] {name}: No matches")

    # Search companies
    print("\n" + "=" * 40)
    print("SEARCHING COMPANIES")
    print("=" * 40)

    for name in COMPANIES:
        matches = search_offshore(driver, name)
        if matches:
            print(f"\n[FOUND] {name}: {len(matches)} match(es)")
            for m in matches[:5]:  # Limit output for common terms
                print(f"  - {m['name']}")
                print(f"    Type: {m['node_type']} | Jurisdiction: {m.get('jurisdiction', 'N/A')}")
                all_matches.append({"search_term": name, "category": "company", **m})
            if len(matches) > 5:
                print(f"  ... and {len(matches) - 5} more")
        else:
            print(f"[  --  ] {name}: No matches")

    driver.close()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total matches found: {len(all_matches)}")

    # Group by source leak
    sources = {}
    for m in all_matches:
        src = m.get('source', 'unknown')
        sources[src] = sources.get(src, 0) + 1

    print("\nMatches by leak source:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    # Save results
    output_file = "data/epstein-docs/icij_matches.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_matches": len(all_matches),
            "matches": all_matches
        }, f, indent=2)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
