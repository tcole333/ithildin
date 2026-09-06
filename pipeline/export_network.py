#!/usr/bin/env python3
"""Export connections and entities from investigation.db as a network graph JSON.

Uses name_aliases table to merge duplicate nodes:
- person_variant: merge split person names ("Barak" + "Ehud Barak" -> one node)
- entity_variant: merge entity name variants ("Gratitude America" + "Gratitude America Ltd")
- entity_as_person: route organization names from connections to entity nodes
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

try:
    from .paths import CONTENT_DIR, DB_PATH
except ImportError:  # Direct CLI execution
    from paths import CONTENT_DIR, DB_PATH


OUTPUT_PATH = CONTENT_DIR / "network.json"

# Add tools to path for name_resolver
sys.path.insert(0, str(Path(__file__).parent.parent))


def slugify(name: str) -> str:
    import re
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    return slug.strip('-')


def _load_aliases(conn: sqlite3.Connection) -> dict[str, tuple[str, str, int | None]]:
    """Load aliases from DB: {alias_lower: (canonical, type, entity_id)}."""
    aliases = {}
    try:
        rows = conn.execute("SELECT canonical_name, alias, alias_type, entity_id FROM name_aliases").fetchall()
        for row in rows:
            aliases[row["alias"].lower()] = (row["canonical_name"], row["alias_type"], row["entity_id"])
    except sqlite3.OperationalError:
        pass
    return aliases


def _resolve_node_id(name: str, aliases: dict, entity_id_map: dict[str, str]) -> str:
    """Resolve a person name to its node ID, routing entity_as_person to entity nodes."""
    entry = aliases.get(name.lower())
    if entry:
        canonical, alias_type, entity_id = entry
        if alias_type == "entity_as_person" and entity_id:
            return f"entity:{entity_id}"
        # For person/entity variants, check if canonical is also entity_as_person
        canonical_entry = aliases.get(canonical.lower())
        if canonical_entry and canonical_entry[1] == "entity_as_person" and canonical_entry[2]:
            return f"entity:{canonical_entry[2]}"
        return canonical
    return name


def export_network(db_path: str | Path = DB_PATH, *, include_unverified: bool = False,
                   profile_id: str | None = None) -> dict:
    """Project distinct claims, retaining their verification and source ownership.

    Public graphs use the same current-evidence gate as dossiers. Raw entity
    roles/relations have no verification lifecycle and are research-only; their
    presence in a registry table does not make them verified claims.
    """
    from tools.findings_tracker import validate_connection_publication

    conn = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        aliases = _load_aliases(conn)
        entity_rows = conn.execute(
            "SELECT id, name, entity_type, jurisdiction, status FROM entities ORDER BY id"
        ).fetchall()
        entity_id_map = {row["name"].lower(): f"entity:{row['id']}" for row in entity_rows}
        nodes = {
            f"entity:{row['id']}": {
                "id": f"entity:{row['id']}", "name": row["name"],
                "slug": slugify(row["name"]), "type": "entity",
                "entity_type": row["entity_type"], "jurisdiction": row["jurisdiction"],
                "status": row["status"], "connections": 0,
            } for row in entity_rows
        }
        edges: list[dict] = []

        def add_edge(edge: dict) -> None:
            if edge["source"] == edge["target"]:
                return
            for node_id in (edge["source"], edge["target"]):
                if node_id not in nodes:
                    nodes[node_id] = {"id": node_id, "name": node_id,
                                      "slug": slugify(node_id), "type": "person",
                                      "connections": 0}
                nodes[node_id]["connections"] += 1
            edges.append(edge)

        predicate = ("COALESCE(verification_status, 'unverified') != 'retracted'"
                     if include_unverified else "verification_status = 'verified'")
        scope = " AND profile_id = ?" if profile_id else ""
        rows = conn.execute(
            f"SELECT * FROM connections WHERE {predicate}{scope} ORDER BY id",
            (profile_id,) if profile_id else (),
        ).fetchall()
        for row in rows:
            if not include_unverified:
                try:
                    validate_connection_publication(conn, row)
                except ValueError:
                    continue
            evidence = [dict(item) for item in conn.execute(
                "SELECT evidence_type, evidence_ref, source_quote, source_page, assessment "
                "FROM connection_evidence WHERE connection_id=? ORDER BY evidence_ref",
                (row["id"],),
            )]
            add_edge({
                "id": f"connection:{row['id']}", "connection_id": row["id"],
                "source": _resolve_node_id(row["person_a"], aliases, entity_id_map),
                "target": _resolve_node_id(row["person_b"], aliases, entity_id_map),
                "relationship_type": row["relationship_type"],
                "description": row["description"], "strength": row["strength"],
                "date_range": row["date_range"],
                "verification_status": row["verification_status"] or "unverified",
                "verified": row["verification_status"] == "verified",
                "profile_ids": [row["profile_id"]] if row["profile_id"] else [],
                "finding_id": row["finding_id"], "evidence": evidence,
            })

        # A scoped view has no evidence that a global structural claim belongs
        # to that profile. Keep this optional overlay only in global research.
        if include_unverified and not profile_id:
            for row in conn.execute("SELECT er.*, e.name AS entity_name FROM entity_roles er "
                                    "JOIN entities e ON e.id=er.entity_id ORDER BY er.id"):
                add_edge({
                    "id": f"entity_role:{row['id']}",
                    "source": _resolve_node_id(row["person_name"], aliases, entity_id_map),
                    "target": f"entity:{row['entity_id']}", "relationship_type": "corporate",
                    "description": f"{row['role']} of {row['entity_name']}",
                    "strength": "unknown", "date_range": f"{row['date_start'] or '?'} - {row['date_end'] or '?'}",
                    "verification_status": "unverified", "verified": False, "profile_ids": [],
                    "evidence": [{"evidence_ref": row["source"]}] if row["source"] else [],
                })
            for row in conn.execute("SELECT * FROM entity_relations ORDER BY id"):
                add_edge({
                    "id": f"entity_relation:{row['id']}",
                    "source": f"entity:{row['entity_a_id']}", "target": f"entity:{row['entity_b_id']}",
                    "relationship_type": row["relation_type"], "description": row["description"],
                    "strength": "unknown", "verification_status": "unverified", "verified": False,
                    "profile_ids": [],
                    "evidence": [{"evidence_ref": row["source"]}] if row["source"] else [],
                })

        finding_counts = conn.execute(
            f"SELECT target_name, COUNT(*) AS cnt FROM findings WHERE {predicate}{scope} GROUP BY target_name",
            (profile_id,) if profile_id else (),
        )
        for row in finding_counts:
            node_id = _resolve_node_id(row["target_name"], aliases, entity_id_map)
            if node_id in nodes:
                nodes[node_id]["finding_count"] = nodes[node_id].get("finding_count", 0) + row["cnt"]
        node_list = sorted((node for node in nodes.values() if node["connections"]),
                           key=lambda node: (-node["connections"], node["id"]))
        return {
            "schema_version": 2,
            "export_options": {"include_unverified": include_unverified, "profile_id": profile_id},
            "nodes": node_list, "edges": edges,
            "stats": {"total_nodes": len(node_list),
                      "person_nodes": sum(node["type"] == "person" for node in node_list),
                      "entity_nodes": sum(node["type"] == "entity" for node in node_list),
                      "total_edges": len(edges)},
        }
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Export network graph from investigation.db")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--stats-only", action="store_true")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--profile", help="Restrict to one investigation profile")
    parser.add_argument("--include-unverified", action="store_true", help="Research export; still excludes retracted claims")
    args = parser.parse_args()

    network = export_network(args.db, include_unverified=args.include_unverified, profile_id=args.profile)

    if args.stats_only:
        print(json.dumps(network["stats"], indent=2))
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(network, f, indent=2, default=str)

    print(f"Network: {network['stats']['total_nodes']} nodes, {network['stats']['total_edges']} edges")
    print(f"  Persons: {network['stats']['person_nodes']}")
    print(f"  Entities: {network['stats']['entity_nodes']}")
    print(f"Output: {args.output}")


if __name__ == "__main__":
    main()
