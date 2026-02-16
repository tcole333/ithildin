#!/usr/bin/env python3
"""Identify and prepare article topic clusters from investigation.db.

Outputs cluster definitions with all relevant findings/connections/evidence
that a writing agent will use to generate articles.
"""

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "investigation.db"
OUTPUT_DIR = Path(__file__).parent.parent / "content"

# Seed clusters identified from 11 waves of findings
CLUSTERS = [
    {
        "id": "apollo-money-pipeline",
        "title": "The Apollo Money Pipeline",
        "subtitle": "How $158M+ flowed from 3 billionaires to a convicted sex offender",
        "style_angle": "How do you move $40M to a felon through legitimate banking?",
        "targets": ["Leon Black", "Marc Rowan", "Joshua Harris", "Southern Trust Company",
                     "Apollo Global Management", "The 2017 Caterpillar Trust", "Ariane de Rothschild",
                     "Edmond de Rothschild Bank"],
        "keywords": ["apollo", "black", "rowan", "harris", "caterpillar trust", "STC",
                     "rothschild", "family office", "$158M", "$40M"],
    },
    {
        "id": "wexner-trust-architecture",
        "title": "Wexner Trust Architecture",
        "subtitle": "A masterclass in using trusts to obscure beneficial ownership",
        "targets": ["Leslie Wexner", "Les Wexner", "Financial Trust Company", "NWO LLC",
                     "Maple Inc", "L Brands"],
        "keywords": ["wexner", "FTC", "NWO", "maple", "L brands", "BBWI", "7.8M shares",
                     "9 e 71st"],
    },
    {
        "id": "deutsche-bank-plumbing",
        "title": "Deutsche Bank Plumbing",
        "subtitle": "What 579 transactions and $304M tell us about compliance theater",
        "targets": ["Deutsche Bank", "WE LLC", "Southern Trust Company", "Jeffrey Epstein"],
        "keywords": ["deutsche bank", "DS10", "SAR", "compliance", "WE LLC"],
    },
    {
        "id": "gulf-intelligence-web",
        "title": "The Gulf Intelligence Web",
        "subtitle": "The geopolitics of a financier's Rolodex",
        "targets": ["Jabor Al Thani", "Sultan Bin Sulayem", "Raafat Alsabbagh",
                     "Fettah Tamince", "Elliott Broidy"],
        "keywords": ["qatar", "saudi", "UAE", "al thani", "HBJ", "radical breakthrough",
                     "broidy", "nader"],
    },
    {
        "id": "shadow-lobbying-empire",
        "title": "Shadow Lobbying Empire",
        "subtitle": "How to lobby Congress without technically lobbying Congress",
        "targets": ["International Peace Institute", "IPI", "Humpty Dumpty Institute", "HDI",
                     "Terje Rod-Larsen"],
        "keywords": ["IPI", "HDI", "lobbying", "FARA", "congress", "shadow"],
    },
    {
        "id": "corporate-shell-network",
        "title": "The Corporate Shell Network",
        "subtitle": "The corporate structure diagram that takes a full wall",
        "targets": ["IGO Company LLC", "Southern Financial LLC", "Maple Inc",
                     "JEGE Inc", "Darren Indyke", "Richard Kahn"],
        "keywords": ["shell", "LLC", "corporate", "BBVI", "5-tier", "indyke"],
    },
    {
        "id": "legal-shield",
        "title": "The Legal Shield",
        "subtitle": "When your lawyers are also your intelligence service",
        "targets": ["Ken Starr", "Brad Karp", "Reid Weingarten", "Dechert LLP",
                     "Brad Edwards"],
        "keywords": ["starr", "karp", "paul weiss", "dechert", "privilege", "defense"],
    },
    {
        "id": "science-tech-interface",
        "title": "Science & Tech Interface",
        "subtitle": "Philanthropy as a social technology",
        "targets": ["Carbyne/Reporty", "Ian Osborne", "Peter Thiel", "Valar Ventures",
                     "Masha Drokova", "Enhanced Education"],
        "keywords": ["gates", "nikolic", "carbyne", "edge foundation", "science", "tech",
                     "osborne", "thiel", "hedosophia"],
    },
    {
        "id": "norwegian-connection",
        "title": "The Norwegian Connection",
        "subtitle": "An ex-diplomat, a defense minister, and a registered sex offender",
        "targets": ["Terje Rod-Larsen", "Ehud Barak", "Thorbjorn Jagland"],
        "keywords": ["norway", "norwegian", "rod-larsen", "barak", "jagland", "telenor"],
    },
    {
        "id": "inner-circle-operations",
        "title": "Inner Circle Operations",
        "subtitle": "The org chart of a criminal enterprise that filed its taxes",
        "targets": ["Darren Indyke", "Richard Kahn", "Lesley Groff", "Karyna Shuliak"],
        "keywords": ["indyke", "kahn", "groff", "galbraith", "shuliak", "inner circle"],
    },
    {
        "id": "usvi-operations",
        "title": "USVI Operations",
        "subtitle": "Why the US Virgin Islands is the Delaware of the Caribbean",
        "targets": ["Southern Trust Company", "Southern Financial LLC", "Maple Inc",
                     "Gratitude America", "Gratitude America Ltd"],
        "keywords": ["USVI", "virgin islands", "southern trust", "great st james",
                     "little st james", "gratitude"],
    },
    {
        "id": "political-influence-machine",
        "title": "The Political Influence Machine",
        "subtitle": "Campaign finance as relationship management",
        "targets": ["Gratitude America", "Gratitude America Ltd", "IPI", "HDI"],
        "keywords": ["FEC", "bundling", "plaskett", "richardson", "clinton", "campaign",
                     "political", "donation"],
    },
]


def gather_cluster_data(conn: sqlite3.Connection, cluster: dict) -> dict:
    """Gather all findings, connections, and evidence for a cluster."""
    targets = cluster["targets"]
    keywords = cluster.get("keywords", [])

    # Findings for named targets
    placeholders = ",".join("?" * len(targets))
    findings = conn.execute(
        f"""
        SELECT id, target_name, finding_type, summary, detail, source_datasets,
               confidence, date_of_event, claim_type, verification_status
        FROM findings
        WHERE target_name IN ({placeholders}) AND verification_status != 'retracted'
        ORDER BY date_of_event IS NULL, date_of_event
        """,
        targets,
    ).fetchall()

    # Also search by keywords in summary/detail
    keyword_findings = []
    for kw in keywords:
        kw_rows = conn.execute(
            """
            SELECT id, target_name, finding_type, summary, detail, source_datasets,
                   confidence, date_of_event, claim_type, verification_status
            FROM findings
            WHERE (summary LIKE ? OR detail LIKE ?) AND verification_status != 'retracted'
            """,
            (f"%{kw}%", f"%{kw}%"),
        ).fetchall()
        keyword_findings.extend(kw_rows)

    # Deduplicate
    seen_ids = {f["id"] for f in findings}
    for f in keyword_findings:
        if f["id"] not in seen_ids:
            findings.append(f)
            seen_ids.add(f["id"])

    # Get evidence for all findings
    finding_ids = list(seen_ids)
    evidence = {}
    for fid in finding_ids:
        evs = conn.execute(
            "SELECT evidence_type, evidence_ref, source_quote, source_page, assessment FROM finding_evidence WHERE finding_id = ?",
            (fid,),
        ).fetchall()
        if evs:
            evidence[fid] = [dict(e) for e in evs]

    # Connections between targets
    connections = []
    for i, ta in enumerate(targets):
        for tb in targets[i + 1 :]:
            conns = conn.execute(
                """
                SELECT id, person_a, person_b, relationship_type, description, strength, date_range
                FROM connections
                WHERE ((person_a = ? AND person_b = ?) OR (person_a = ? AND person_b = ?))
                  AND verification_status != 'retracted'
                """,
                (ta, tb, tb, ta),
            ).fetchall()
            connections.extend(conns)

    return {
        **cluster,
        "findings": [dict(f) for f in findings],
        "evidence": {str(k): v for k, v in evidence.items()},
        "connections": [dict(c) for c in connections],
        "stats": {
            "total_findings": len(findings),
            "total_connections": len(connections),
            "unique_targets": len(set(f["target_name"] for f in findings)),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Prepare article cluster data")
    parser.add_argument("--cluster", help="Single cluster ID to export")
    parser.add_argument("--list", action="store_true", help="List available clusters")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if args.list:
        for c in CLUSTERS:
            print(f"  {c['id']}: {c['title']}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    clusters_to_export = CLUSTERS
    if args.cluster:
        clusters_to_export = [c for c in CLUSTERS if c["id"] == args.cluster]
        if not clusters_to_export:
            print(f"Unknown cluster: {args.cluster}")
            return

    results = []
    for cluster in clusters_to_export:
        data = gather_cluster_data(conn, cluster)
        results.append(data)
        print(f"  {cluster['id']}: {data['stats']['total_findings']} findings, "
              f"{data['stats']['total_connections']} connections, "
              f"{data['stats']['unique_targets']} targets")

    out_path = args.output_dir / "clusters.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nExported {len(results)} clusters to {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
