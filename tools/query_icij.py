#!/usr/bin/env python3
"""
Query ICIJ Offshore Leaks database (Neo4j, ~800K entities).

Requires Neo4j running: ./scripts/start_icij_db.sh

Usage:
    python tools/query_icij.py search "Jeffrey Epstein"
    python tools/query_icij.py search "Liquid Funding" --type Entity
    python tools/query_icij.py entity 80063035
    python tools/query_icij.py connections "Liquid Funding" --depth 2
    python tools/query_icij.py officers "Financial Trust"
"""

import argparse
import json
import sys

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

ICIJ_URI = "bolt://localhost:7689"


def get_driver():
    """Get Neo4j driver. Requires neo4j package."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: neo4j package not installed. Run: uv pip install neo4j")
        sys.exit(1)

    try:
        driver = GraphDatabase.driver(ICIJ_URI)
        with driver.session() as session:
            session.run("RETURN 1")
        return driver
    except Exception as e:
        print(f"ERROR: Cannot connect to ICIJ database at {ICIJ_URI}")
        print(f"Start it with: ./scripts/start_icij_db.sh")
        print(f"Error: {e}")
        sys.exit(1)


def search(name, node_type=None, limit=50):
    """Search ICIJ database by name. Returns list of matches."""
    driver = get_driver()

    results = []
    types_to_search = [node_type] if node_type else ["Entity", "Officer", "Intermediary"]

    with driver.session() as session:
        for ntype in types_to_search:
            query = f"""
                MATCH (n:{ntype})
                WHERE toLower(n.name) CONTAINS toLower($name)
                RETURN n.name as name,
                       n.node_id as node_id,
                       n.jurisdiction as jurisdiction,
                       n.jurisdiction_description as jurisdiction_desc,
                       n.countries as countries,
                       n.sourceID as source,
                       '{ntype}' as node_type
                LIMIT $limit
            """
            try:
                result = session.run(query, name=name, limit=limit)
                for record in result:
                    results.append(dict(record))
            except Exception as e:
                print(f"  Warning: query failed for {ntype}: {e}", file=sys.stderr)

    driver.close()
    return results


def get_entity(node_id):
    """Get a specific entity by node_id with all properties."""
    driver = get_driver()

    with driver.session() as session:
        query = """
            MATCH (n)
            WHERE n.node_id = $node_id
            RETURN n, labels(n) as types
        """
        result = session.run(query, node_id=str(node_id))
        record = result.single()
        if record:
            node = dict(record["n"])
            node["_labels"] = record["types"]
            driver.close()
            return node

    driver.close()
    return None


def get_connections(name_or_id, depth=1, limit=50):
    """Get connections for an entity (by name or node_id)."""
    driver = get_driver()
    all_connections = []

    with driver.session() as session:
        # First try by node_id, then by name
        for match_clause in [
            "MATCH (n) WHERE n.node_id = $search",
            "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($search)",
        ]:
            query = f"""
                {match_clause}
                MATCH path = (n)-[r*1..{depth}]-(connected)
                UNWIND relationships(path) as rel
                WITH startNode(rel) as from_node, endNode(rel) as to_node, type(rel) as rel_type
                RETURN DISTINCT
                    from_node.name as from_name,
                    from_node.node_id as from_id,
                    labels(from_node) as from_types,
                    rel_type,
                    to_node.name as to_name,
                    to_node.node_id as to_id,
                    labels(to_node) as to_types
                LIMIT $limit
            """
            try:
                result = session.run(query, search=str(name_or_id), limit=limit)
                records = list(result)
                if records:
                    all_connections = [dict(r) for r in records]
                    break
            except Exception:
                continue

    driver.close()
    return all_connections


def get_officers(entity_name, limit=50):
    """Get officers/directors of matching entities."""
    driver = get_driver()
    results = []

    with driver.session() as session:
        query = """
            MATCH (e:Entity)<-[r]-(o:Officer)
            WHERE toLower(e.name) CONTAINS toLower($name)
            RETURN e.name as entity_name,
                   e.node_id as entity_id,
                   e.jurisdiction as jurisdiction,
                   type(r) as role,
                   o.name as officer_name,
                   o.node_id as officer_id,
                   o.countries as officer_countries
            LIMIT $limit
        """
        try:
            result = session.run(query, name=entity_name, limit=limit)
            results = [dict(r) for r in result]
        except Exception as e:
            print(f"Warning: query failed: {e}", file=sys.stderr)

    driver.close()
    return results


def print_results(results, title="Results"):
    """Pretty-print query results."""
    print(f"\n{'='*70}")
    print(f"{title}: {len(results)} match(es)")
    print(f"{'='*70}")

    for i, r in enumerate(results, 1):
        print(f"\n--- [{i}] ---")
        for k, v in r.items():
            if v is not None and v != "" and not k.startswith("_"):
                print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Query ICIJ Offshore Leaks database")
    subparsers = parser.add_subparsers(dest="command")

    # search
    s = subparsers.add_parser("search", help="Search by name")
    s.add_argument("name", help="Name to search")
    s.add_argument("--type", choices=["Entity", "Officer", "Intermediary"], dest="node_type")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("-j", "--json", action="store_true")
    add_output_args(s)

    # entity
    e = subparsers.add_parser("entity", help="Get entity by node_id")
    e.add_argument("node_id", help="Node ID")
    e.add_argument("-j", "--json", action="store_true")
    add_output_args(e)

    # connections
    c = subparsers.add_parser("connections", help="Get connections")
    c.add_argument("search", help="Name or node_id")
    c.add_argument("--depth", type=int, default=1)
    c.add_argument("--limit", type=int, default=50)
    c.add_argument("-j", "--json", action="store_true")
    add_output_args(c)

    # officers
    o = subparsers.add_parser("officers", help="Get officers of entities")
    o.add_argument("name", help="Entity name")
    o.add_argument("--limit", type=int, default=50)
    o.add_argument("-j", "--json", action="store_true")
    add_output_args(o)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        results = search(args.name, node_type=args.node_type, limit=args.limit)
        if write_output(results, args, summary=f"ICIJ search '{args.name}'"):
            pass
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, f"Search: '{args.name}'")

    elif args.command == "entity":
        entity = get_entity(args.node_id)
        if entity:
            if write_output(entity, args, summary=f"ICIJ entity {args.node_id}"):
                pass
            elif args.json:
                print(json.dumps(entity, indent=2, default=str))
            else:
                print(f"\nEntity {args.node_id}:")
                for k, v in entity.items():
                    if v is not None and v != "":
                        print(f"  {k}: {v}")
        else:
            print(f"Entity {args.node_id} not found.")

    elif args.command == "connections":
        conns = get_connections(args.search, depth=args.depth, limit=args.limit)
        if write_output(conns, args, summary=f"ICIJ connections for '{args.search}'"):
            pass
        elif args.json:
            print(json.dumps(conns, indent=2, default=str))
        else:
            print_results(conns, f"Connections for '{args.search}' (depth={args.depth})")

    elif args.command == "officers":
        results = get_officers(args.name, limit=args.limit)
        if write_output(results, args, summary=f"ICIJ officers for '{args.name}'"):
            pass
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, f"Officers of entities matching '{args.name}'")


if __name__ == "__main__":
    main()
