#!/usr/bin/env python3
"""
Query ICIJ Offshore Leaks database.

Neo4j commands require Neo4j running: ./scripts/start_icij_db.sh
Reconciliation API commands work without Neo4j (uses ICIJ's REST API).

Bounded search, entity, connections, and officers queries use ICIJ's official
public reconciliation service and node pages by default. Pass --local only for
deeper/bulk Neo4j traversal.

Usage:
    uv run python tools/query_icij.py search "Jeffrey Epstein"
    uv run python tools/query_icij.py search "Liquid Funding" --type Entity
    uv run python tools/query_icij.py entity 82004676
    uv run python tools/query_icij.py connections 82004676
    uv run python tools/query_icij.py officers 82004676
    uv run python tools/query_icij.py reconcile "Financial Trust Company"
    uv run python tools/query_icij.py reconcile-all --threshold 85
    uv run python tools/query_icij.py reconcile-all --create-leads --threshold 85
"""

import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tools.output_util import add_output_args, write_output
    from tools.lead_tracker import log_search
except ImportError:
    from output_util import add_output_args, write_output
    from lead_tracker import log_search

PROJECT_ROOT = Path(__file__).parent.parent
INVESTIGATION_DB = PROJECT_ROOT / "investigation.db"
RECONCILE_URL = "https://offshoreleaks.icij.org/api/v1/reconcile"
NODE_URL = "https://offshoreleaks.icij.org/nodes/{node_id}?embed=1"
MAX_NODE_PAGE_BYTES = 5_000_000
MAX_RECONCILE_BYTES = 5_000_000

ICIJ_URI = "bolt://localhost:7689"


class ICIJRemoteError(RuntimeError):
    """Official ICIJ remote source was unavailable or changed shape."""


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
        print("Start it with: ./scripts/start_icij_db.sh")
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


def reconcile_name(name, limit=5, node_type=None):
    """Reconcile a single name against ICIJ Offshore Leaks API.

    Uses the OpenRefine Reconciliation API standard. No auth required.
    Returns list of match candidates with scores.
    """
    try:
        query = {"query": name, "limit": min(limit, 25)}
        if node_type:
            query["type"] = node_type
        result = _do_reconcile_request({"q0": query}, timeout=30)
    except HTTPError as exc:
        raise ICIJRemoteError(
            f"official ICIJ reconciliation API returned HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise ICIJRemoteError(
            f"official ICIJ reconciliation API failed: {exc.reason}"
        ) from exc

    candidates = result.get("q0", {}).get("result", [])
    return [{
        "name": c.get("name", ""),
        "id": c.get("id", ""),
        "score": c.get("score", 0),
        "match": c.get("match", False),
        "description": c.get("description", ""),
        "type": [t.get("name", "") for t in (c.get("types") or c.get("type") or [])],
    } for c in candidates]


def _parse_node_page(html, requested_node_id):
    """Extract the bounded first-hop graph embedded in an official node page."""
    marker = "document.body.nodeData"
    marker_index = html.find(marker)
    if marker_index < 0:
        raise ICIJRemoteError("official ICIJ node page did not contain nodeData")
    array_index = html.find("[", marker_index + len(marker))
    if array_index < 0:
        raise ICIJRemoteError("official ICIJ node page contained malformed nodeData")
    try:
        nodes, _ = json.JSONDecoder().raw_decode(html[array_index:])
    except json.JSONDecodeError as exc:
        raise ICIJRemoteError(f"could not parse official ICIJ nodeData: {exc}") from exc
    if not isinstance(nodes, list):
        raise ICIJRemoteError("official ICIJ nodeData was not a list")

    requested = str(requested_node_id)
    by_linkurious = {str(n.get("linkurious_id")): n for n in nodes}
    main = next((n for n in nodes if str(n.get("id")) == requested), None)
    if main is None:
        raise ICIJRemoteError(f"official ICIJ node page omitted requested node {requested}")
    main_linkurious_id = str(main.get("linkurious_id"))

    connections = []
    seen_edges = set()
    for node in nodes:
        for edge in node.get("edges") or []:
            edge_id = str(edge.get("id", ""))
            if edge_id and edge_id in seen_edges:
                continue
            if edge_id:
                seen_edges.add(edge_id)
            if main_linkurious_id not in {str(edge.get("source")), str(edge.get("target"))}:
                continue
            source = by_linkurious.get(str(edge.get("source")))
            target = by_linkurious.get(str(edge.get("target")))
            if not source or not target:
                continue
            edge_data = edge.get("data") or {}
            connections.append({
                "from_name": (source.get("data") or {}).get("properties", {}).get("name")
                    or (source.get("data") or {}).get("properties", {}).get("address"),
                "from_id": str(source.get("id")),
                "from_types": (source.get("data") or {}).get("categories") or [],
                "rel_type": edge_data.get("type"),
                "to_name": (target.get("data") or {}).get("properties", {}).get("name")
                    or (target.get("data") or {}).get("properties", {}).get("address"),
                "to_id": str(target.get("id")),
                "to_types": (target.get("data") or {}).get("categories") or [],
                "properties": edge_data.get("properties") or {},
            })
    return {"main": main, "nodes": nodes, "connections": connections}


def get_remote_node(node_id, timeout=30):
    """Fetch one official HTML node page and its embedded first-hop graph."""
    node_id = str(node_id)
    if not re.fullmatch(r"\d+", node_id):
        raise ICIJRemoteError("remote ICIJ node IDs must be numeric")
    request = Request(
        NODE_URL.format(node_id=node_id),
        headers={"User-Agent": "OSINT-Research/1.0", "Accept": "text/html"},
    )
    try:
        time.sleep(0.5)
        with urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    too_large = int(content_length) > MAX_NODE_PAGE_BYTES
                except ValueError as exc:
                    raise ICIJRemoteError(
                        "official ICIJ node page returned an invalid Content-Length"
                    ) from exc
                if too_large:
                    raise ICIJRemoteError(
                        f"official ICIJ node page exceeds the {MAX_NODE_PAGE_BYTES}-byte safety limit"
                    )
            body = response.read(MAX_NODE_PAGE_BYTES + 1)
            if len(body) > MAX_NODE_PAGE_BYTES:
                raise ICIJRemoteError(
                    f"official ICIJ node page exceeds the {MAX_NODE_PAGE_BYTES}-byte safety limit"
                )
            html = body.decode("utf-8", errors="replace")
    except HTTPError as exc:
        raise ICIJRemoteError(f"official ICIJ node page returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise ICIJRemoteError(f"official ICIJ node page failed: {exc.reason}") from exc
    return _parse_node_page(html, node_id)


def _resolve_remote_node(value, node_type=None):
    if re.fullmatch(r"\d+", str(value)):
        return str(value), None
    candidates = reconcile_name(str(value), limit=5, node_type=node_type)
    if not candidates:
        raise ICIJRemoteError(f"no ICIJ reconciliation candidate found for {value!r}")
    normalized = str(value).strip().casefold()
    exact = [c for c in candidates if c["name"].strip().casefold() == normalized]
    confirmed = [c for c in candidates if c.get("match")]
    eligible = exact or confirmed
    if not eligible:
        preview = "; ".join(
            f"{c.get('id')} {c.get('name')} (score {c.get('score', 0):.1f})"
            for c in candidates[:5]
        )
        raise ICIJRemoteError(
            f"ICIJ returned only fuzzy candidates for {value!r}: {preview}. "
            "Review `query_icij.py search` results, then pass a numeric node ID."
        )
    chosen = max(eligible, key=lambda c: c.get("score", 0))
    return str(chosen["id"]), chosen


def remote_entity(node_id):
    graph = get_remote_node(node_id)
    main = graph["main"]
    data = main.get("data") or {}
    result = dict(data.get("properties") or {})
    result["_labels"] = data.get("categories") or []
    result["_statistics"] = data.get("statistics") or {}
    result["_url"] = NODE_URL.format(node_id=node_id).replace("?embed=1", "")
    result["_first_hop_connections"] = len(graph["connections"])
    return result


def remote_connections(value, limit=50):
    node_id, candidate = _resolve_remote_node(value)
    graph = get_remote_node(node_id)
    rows = graph["connections"][:limit]
    if candidate:
        for row in rows:
            row["resolved_candidate"] = candidate
    return rows


def remote_officers(value, limit=50):
    node_id, candidate = _resolve_remote_node(value, node_type="Entity")
    graph = get_remote_node(node_id)
    main = graph["main"]
    main_props = (main.get("data") or {}).get("properties") or {}
    rows = []
    for connection in graph["connections"]:
        if str(connection["from_id"]) == node_id:
            other_name, other_id, other_types = (
                connection["to_name"], connection["to_id"], connection["to_types"]
            )
        elif str(connection["to_id"]) == node_id:
            other_name, other_id, other_types = (
                connection["from_name"], connection["from_id"], connection["from_types"]
            )
        else:
            continue
        if "Officer" not in other_types:
            continue
        rows.append({
            "entity_name": main_props.get("name"),
            "entity_id": node_id,
            "jurisdiction": main_props.get("jurisdiction_description") or main_props.get("jurisdiction"),
            "role": connection.get("rel_type"),
            "officer_name": other_name,
            "officer_id": other_id,
            "source": (connection.get("properties") or {}).get("sourceID"),
            "resolved_candidate": candidate,
        })
    return rows[:limit]


def _do_reconcile_request(queries, timeout=60):
    """Send a reconcile request with the given queries dict."""
    from urllib.parse import quote
    query_payload = json.dumps(queries)
    data = f"queries={quote(query_payload)}".encode("utf-8")

    req = Request(RECONCILE_URL, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "OSINT-Research/1.0",
    })

    time.sleep(0.5)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_RECONCILE_BYTES + 1)
    except HTTPError as exc:
        raise ICIJRemoteError(
            f"official ICIJ reconciliation API returned HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise ICIJRemoteError(
            f"official ICIJ reconciliation API failed: {exc.reason}"
        ) from exc
    if len(body) > MAX_RECONCILE_BYTES:
        raise ICIJRemoteError(
            "official ICIJ reconciliation response exceeds the "
            f"{MAX_RECONCILE_BYTES}-byte safety limit"
        )
    try:
        return json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ICIJRemoteError(
            f"official ICIJ reconciliation API returned invalid JSON: {exc}"
        ) from exc


def reconcile_batch(names, limit=5):
    """Reconcile multiple names in a single API call.

    The OpenRefine API supports up to ~50 queries per batch.
    On failure, retries with individual queries to avoid losing the whole batch.
    """
    queries = {}
    for i, name in enumerate(names):
        queries[f"q{i}"] = {"query": name, "limit": limit}

    try:
        result = _do_reconcile_request(queries)
    except (HTTPError, URLError) as e:
        # Batch failed — retry each name individually to salvage what we can
        print(f"  Batch failed ({e}), retrying individually...", file=sys.stderr)
        result = {}
        for i, name in enumerate(names):
            try:
                single = _do_reconcile_request({f"q{i}": {"query": name, "limit": limit}})
                result.update(single)
            except (HTTPError, URLError):
                pass  # Skip names that consistently fail

    out = {}
    for i, name in enumerate(names):
        key = f"q{i}"
        candidates = result.get(key, {}).get("result", [])
        out[name] = [{
            "name": c.get("name", ""),
            "id": c.get("id", ""),
            "score": c.get("score", 0),
            "match": c.get("match", False),
            "description": c.get("description", ""),
            "type": [t.get("name", "") for t in (c.get("types") or c.get("type") or [])],
        } for c in candidates]

    return out


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


def create_icij_leads(lead_db, matches):
    """Emit pending_triage leads for ICIJ offshore-leaks matches.

    Routes through the canonical auto_leads.create_lead() emitter — which
    hard-codes status='pending_triage' and writes the note to the lead_notes
    table — instead of a raw INSERT into a nonexistent leads.notes column.
    Dedupes on title via lead_exists(). Returns the number of leads created.
    """
    try:
        from tools.auto_leads import create_lead, lead_exists, LeadLimitReached
    except ImportError:
        from auto_leads import create_lead, lead_exists, LeadLimitReached

    created = 0
    for m in matches:
        types_str = ", ".join(m["type"]) if m["type"] else "offshore entity"
        title = f"ICIJ offshore match: {m['our_name']} -> {m['icij_name']} ({types_str})"
        if lead_exists(lead_db, title):
            continue
        notes = (
            f"Score: {m['score']}. ICIJ ID: {m['icij_id']}. "
            f"Type: {types_str}. Matched: {m['icij_name']}"
        )
        try:
            create_lead(lead_db, title, "entity", "medium", "agent:icij_reconcile",
                        target=m["our_name"], notes=notes)
        except LeadLimitReached:
            break
        created += 1
    return created


def main():
    parser = argparse.ArgumentParser(description="Query ICIJ Offshore Leaks database")
    subparsers = parser.add_subparsers(dest="command")

    # search
    s = subparsers.add_parser("search", help="Search by name")
    s.add_argument("name", help="Name to search")
    s.add_argument("--type", choices=["Entity", "Officer", "Intermediary"], dest="node_type")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--local", action="store_true", help="Use optional local Neo4j instead of the public API")
    s.add_argument("-j", "--json", action="store_true")
    add_output_args(s)

    # entity
    e = subparsers.add_parser("entity", help="Get entity by node_id")
    e.add_argument("node_id", help="Node ID")
    e.add_argument("--local", action="store_true", help="Use optional local Neo4j instead of the public node page")
    e.add_argument("-j", "--json", action="store_true")
    add_output_args(e)

    # connections
    c = subparsers.add_parser("connections", help="Get connections")
    c.add_argument("search", help="Name or node_id")
    c.add_argument("--depth", type=int, default=1)
    c.add_argument("--limit", type=int, default=50)
    c.add_argument("--local", action="store_true", help="Use local Neo4j (required for depth > 1)")
    c.add_argument("-j", "--json", action="store_true")
    add_output_args(c)

    # officers
    o = subparsers.add_parser("officers", help="Get officers of entities")
    o.add_argument("name", help="Entity name")
    o.add_argument("--limit", type=int, default=50)
    o.add_argument("--local", action="store_true", help="Use optional local Neo4j instead of the public node page")
    o.add_argument("-j", "--json", action="store_true")
    add_output_args(o)

    # reconcile (no Neo4j needed)
    r = subparsers.add_parser("reconcile", help="Match a name against ICIJ Offshore Leaks API (no Neo4j)")
    r.add_argument("name", help="Name to reconcile")
    r.add_argument("--limit", type=int, default=5, help="Max candidates per query")
    r.add_argument("-j", "--json", action="store_true")
    add_output_args(r)

    # reconcile-all (no Neo4j needed)
    ra = subparsers.add_parser("reconcile-all", help="Match all investigation.db entities against ICIJ")
    ra.add_argument("--threshold", type=int, default=80, help="Min score to report (default: 80)")
    ra.add_argument("--create-leads", action="store_true", help="Auto-create pending_triage leads for matches")
    ra.add_argument("--limit", type=int, default=5, help="Max candidates per query")
    ra.add_argument("-j", "--json", action="store_true")
    add_output_args(ra)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "search":
        results = (
            search(args.name, node_type=args.node_type, limit=args.limit)
            if args.local
            else reconcile_name(args.name, limit=args.limit, node_type=args.node_type)
        )
        log_search(args.name, "icij_local" if args.local else "icij_reconcile", len(results))
        if write_output(results, args, summary=f"ICIJ search '{args.name}'"):
            pass
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, f"Search: '{args.name}'")

    elif args.command == "entity":
        entity = get_entity(args.node_id) if args.local else remote_entity(args.node_id)
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
        if not args.local and args.depth != 1:
            raise ICIJRemoteError(
                "public ICIJ node pages expose one hop; use --local for --depth greater than 1"
            )
        conns = (
            get_connections(args.search, depth=args.depth, limit=args.limit)
            if args.local
            else remote_connections(args.search, limit=args.limit)
        )
        if write_output(conns, args, summary=f"ICIJ connections for '{args.search}'"):
            pass
        elif args.json:
            print(json.dumps(conns, indent=2, default=str))
        else:
            print_results(conns, f"Connections for '{args.search}' (depth={args.depth})")

    elif args.command == "officers":
        results = (
            get_officers(args.name, limit=args.limit)
            if args.local
            else remote_officers(args.name, limit=args.limit)
        )
        if write_output(results, args, summary=f"ICIJ officers for '{args.name}'"):
            pass
        elif args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results, f"Officers of entities matching '{args.name}'")

    elif args.command == "reconcile":
        candidates = reconcile_name(args.name, limit=args.limit)
        log_search(args.name, "icij_reconcile", len(candidates))

        if write_output(candidates, args, summary=f"ICIJ reconcile '{args.name}'"):
            pass
        elif args.json:
            print(json.dumps(candidates, indent=2))
        else:
            print(f"\nICIJ Reconciliation: '{args.name}' ({len(candidates)} candidates)")
            print("=" * 80)
            for c in candidates:
                match_flag = " [MATCH]" if c["match"] else ""
                types = ", ".join(c["type"]) if c["type"] else "?"
                print(f"  {c['score']:>5.1f}  {c['name']:<40} [{types}]{match_flag}")
                print(f"         ID: {c['id']}")

    elif args.command == "reconcile-all":
        if not INVESTIGATION_DB.exists():
            print(f"ERROR: investigation.db not found at {INVESTIGATION_DB}", file=sys.stderr)
            sys.exit(1)

        inv_db = sqlite3.connect(str(INVESTIGATION_DB))
        inv_db.row_factory = sqlite3.Row

        # Gather entity names + connection person names
        names_to_check = {}
        try:
            for e in inv_db.execute("SELECT id, name, entity_type FROM entities").fetchall():
                name = e["name"].strip()
                if len(name) >= 3:
                    names_to_check[name] = {"source": f"entity #{e['id']}", "type": e["entity_type"]}
        except sqlite3.OperationalError:
            pass

        try:
            for col in ("person_a", "person_b"):
                for r in inv_db.execute(f"SELECT DISTINCT {col} FROM connections").fetchall():
                    name = (r[0] or "").strip()
                    if len(name) >= 3 and name not in names_to_check:
                        names_to_check[name] = {"source": "connection", "type": "person"}
        except sqlite3.OperationalError:
            pass

        inv_db.close()

        print(f"Reconciling {len(names_to_check)} names against ICIJ Offshore Leaks (threshold={args.threshold})")
        print("=" * 90)

        all_matches = []
        names_list = sorted(names_to_check.keys())
        batch_size = 25

        for batch_start in range(0, len(names_list), batch_size):
            batch = names_list[batch_start:batch_start + batch_size]
            if batch_start > 0:
                print(f"  ... checked {batch_start}/{len(names_list)}", flush=True)

            batch_results = reconcile_batch(batch, limit=args.limit)

            for name in batch:
                candidates = batch_results.get(name, [])
                for c in candidates:
                    if c["score"] >= args.threshold:
                        all_matches.append({
                            "our_name": name,
                            "our_source": names_to_check[name]["source"],
                            "icij_name": c["name"],
                            "icij_id": c["id"],
                            "score": c["score"],
                            "match": c["match"],
                            "type": c["type"],
                        })

        all_matches.sort(key=lambda m: m["score"], reverse=True)

        # Create leads if requested
        leads_created = 0
        if args.create_leads and all_matches:
            try:
                from tools.lead_tracker import get_db as get_inv_db
            except ImportError:
                from lead_tracker import get_db as get_inv_db

            lead_db = get_inv_db()
            leads_created = create_icij_leads(lead_db, all_matches)
            lead_db.commit()
            lead_db.close()

        log_search(
            f"reconcile-all (threshold={args.threshold})",
            "icij_reconcile_all",
            len(all_matches),
        )

        output = {"matches": all_matches, "total_checked": len(names_to_check), "leads_created": leads_created}
        if write_output(output, args, summary=f"ICIJ reconcile-all ({len(all_matches)} matches)"):
            pass
        elif args.json:
            print(json.dumps(output, indent=2))
        else:
            # Group by match quality
            high = [m for m in all_matches if m["match"]]
            possible = [m for m in all_matches if not m["match"]]

            if high:
                print(f"\nSTRONG MATCHES ({len(high)})")
                print("-" * 90)
                for m in high:
                    types_str = ", ".join(m["type"]) if m["type"] else "?"
                    print(f"  {m['score']:>5.1f}  {m['our_name']:<35} -> {m['icij_name'][:35]:<35} [{types_str}]")

            if possible:
                print(f"\nPOSSIBLE MATCHES ({len(possible)})")
                print("-" * 90)
                for m in possible[:50]:
                    types_str = ", ".join(m["type"]) if m["type"] else "?"
                    print(f"  {m['score']:>5.1f}  {m['our_name']:<35} -> {m['icij_name'][:35]:<35} [{types_str}]")
                if len(possible) > 50:
                    print(f"  ... and {len(possible) - 50} more")

            print(f"\n{'=' * 90}")
            print(f"SUMMARY: {len(names_to_check)} names checked, {len(all_matches)} matches >= {args.threshold}")
            if args.create_leads:
                print(f"  Leads created: {leads_created}")


if __name__ == "__main__":
    try:
        main()
    except ICIJRemoteError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
