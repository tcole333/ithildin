#!/usr/bin/env python3
"""Entity registry helper for investigation.db.

Provides a small CLI for entity/role/address/relation operations so skills
do not need inline SQL snippets.
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

DB_PATH = Path(__file__).parent.parent / "investigation.db"

VALID_ENTITY_TYPES = [
    "person",
    "llc",
    "inc",
    "ltd",
    "corporation",
    "pllc",
    "trust",
    "foundation",
    "nonprofit",
    "partnership",
    "fund",
    "association",
    "government",
    "pac",
    "agency",
    "joint_venture",
    "shell",
    "unknown",
]

ENTITY_CORRECT_FIELDS = {
    "address",
    "ein",
    "entity_type",
    "jurisdiction",
    "notes",
    "source",
    "status",
}
VALID_CORRECTION_TYPES = {
    "factual_error",
    "source_mismatch",
    "hallucination",
    "outdated",
    "refinement",
    "merge",
    "retraction",
}


def get_db():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    db.execute("PRAGMA foreign_keys=ON")

    # Reuse canonical schema creation from lead tracker.
    try:
        from tools.lead_tracker import _ensure_schema
    except ModuleNotFoundError:
        from lead_tracker import _ensure_schema

    db = _ensure_schema(db)
    return db


def cmd_lookup(args):
    db = get_db()
    rows = db.execute(
        """
        SELECT id, name, entity_type, jurisdiction, ein, status, source, created_at
        FROM entities
        WHERE name LIKE ?
        ORDER BY name
        LIMIT ?
        """,
        (f"%{args.name}%", args.limit),
    ).fetchall()
    results = [dict(r) for r in rows]
    db.close()

    if write_output(results, args, summary=f"entity lookup '{args.name}'"):
        return

    if not results:
        print(f"No entities found matching '{args.name}'.")
        return

    print(f"Found {len(results)} entities matching '{args.name}':")
    for r in results:
        print(
            f"  #{r['id']:>5} {r['name']} "
            f"[{r.get('entity_type') or 'unknown'} | {r.get('jurisdiction') or '?'} | {r.get('status') or '?'}]"
        )


def cmd_show(args):
    db = get_db()
    entity = db.execute("SELECT * FROM entities WHERE id = ?", (args.entity_id,)).fetchone()
    if not entity:
        db.close()
        print(f"Entity #{args.entity_id} not found.")
        sys.exit(1)

    roles = [
        dict(r)
        for r in db.execute(
            """
            SELECT id, person_name, role, date_start, date_end, source
            FROM entity_roles
            WHERE entity_id = ?
            ORDER BY person_name
            """,
            (args.entity_id,),
        ).fetchall()
    ]
    addresses = [
        dict(r)
        for r in db.execute(
            """
            SELECT id, address, address_type, date_observed, source
            FROM entity_addresses
            WHERE entity_id = ?
            ORDER BY id DESC
            """,
            (args.entity_id,),
        ).fetchall()
    ]
    rel_out = [
        dict(r)
        for r in db.execute(
            """
            SELECT er.id, er.entity_b_id AS related_id, e2.name AS related_name,
                   er.relation_type, er.description, er.source
            FROM entity_relations er
            JOIN entities e2 ON e2.id = er.entity_b_id
            WHERE er.entity_a_id = ?
            ORDER BY er.id DESC
            """,
            (args.entity_id,),
        ).fetchall()
    ]
    rel_in = [
        dict(r)
        for r in db.execute(
            """
            SELECT er.id, er.entity_a_id AS related_id, e1.name AS related_name,
                   er.relation_type, er.description, er.source
            FROM entity_relations er
            JOIN entities e1 ON e1.id = er.entity_a_id
            WHERE er.entity_b_id = ?
            ORDER BY er.id DESC
            """,
            (args.entity_id,),
        ).fetchall()
    ]
    db.close()

    payload = {
        "entity": dict(entity),
        "roles": roles,
        "addresses": addresses,
        "relations_outbound": rel_out,
        "relations_inbound": rel_in,
    }
    if write_output(payload, args, summary=f"entity #{args.entity_id} details"):
        return

    e = payload["entity"]
    print(
        f"Entity #{e['id']}: {e['name']} "
        f"[{e.get('entity_type') or 'unknown'} | {e.get('jurisdiction') or '?'} | {e.get('status') or '?'}]"
    )
    if e.get("source"):
        print(f"  Source: {e['source']}")
    if e.get("notes"):
        print(f"  Notes: {e['notes']}")

    print(f"\nRoles ({len(roles)}):")
    for r in roles:
        span = ""
        if r.get("date_start") or r.get("date_end"):
            span = f" ({r.get('date_start') or '?'} -> {r.get('date_end') or '?'})"
        print(f"  - {r['person_name']} :: {r['role']}{span}")

    print(f"\nAddresses ({len(addresses)}):")
    for a in addresses:
        print(f"  - [{a.get('address_type') or 'registered'}] {a['address']}")

    print(f"\nOutbound Relations ({len(rel_out)}):")
    for r in rel_out:
        print(f"  - {e['name']} --{r['relation_type']}--> {r['related_name']} (#{r['related_id']})")

    print(f"\nInbound Relations ({len(rel_in)}):")
    for r in rel_in:
        print(f"  - {r['related_name']} (#{r['related_id']}) --{r['relation_type']}--> {e['name']}")


def cmd_add_entity(args):
    db = get_db()
    agent_run_id = os.environ.get("ITHILDIN_AGENT_RUN_ID")
    try:
        from tools.entity_resolution import resolve_or_create_entity
    except ImportError:
        from entity_resolution import resolve_or_create_entity

    # --force-new bypasses fuzzy + recorded aliases (exact UNIQUE still applies).
    force_new = getattr(args, "force_new", False)
    threshold = 101 if force_new else getattr(args, "match_threshold", 97)
    res = resolve_or_create_entity(
        db,
        args.name,
        entity_type=args.entity_type,
        jurisdiction=args.jurisdiction,
        ein=args.ein,
        status=args.status,
        source=args.source,
        notes=args.notes,
        agent_run_id=agent_run_id,
        threshold=threshold,
        use_aliases=not force_new,
    )
    db.commit()
    db.close()

    name = args.name.strip()
    if res.action == "created":
        print(f"Created entity #{res.entity_id}: {name}")
    elif res.action == "fuzzy":
        print(f"Matched existing entity #{res.entity_id} (fuzzy {res.score}): {res.matched_name}")
        print(f"  Recorded alias '{name}' -> #{res.entity_id}. Use --force-new to insert a separate entity.")
    elif res.action == "alias":
        print(f"Resolved via alias to entity #{res.entity_id}: {res.matched_name}")
    else:  # exact
        print(f"Entity already exists as #{res.entity_id}: {name}")


def cmd_add_role(args):
    db = get_db()
    db.execute(
        """
        INSERT OR IGNORE INTO entity_roles
            (entity_id, person_name, role, date_start, date_end, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            args.entity_id,
            args.person_name.strip(),
            args.role.strip(),
            args.date_start,
            args.date_end,
            args.source,
        ),
    )
    db.commit()
    db.close()
    print(f"Recorded role: entity #{args.entity_id} :: {args.person_name} -> {args.role}")


def cmd_add_address(args):
    db = get_db()
    db.execute(
        """
        INSERT OR IGNORE INTO entity_addresses
            (entity_id, address, address_type, date_observed, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            args.entity_id,
            args.address.strip(),
            args.address_type,
            args.date_observed,
            args.source,
        ),
    )
    db.commit()
    db.close()
    print(f"Recorded address for entity #{args.entity_id}: {args.address}")


def cmd_add_relation(args):
    db = get_db()
    db.execute(
        """
        INSERT OR IGNORE INTO entity_relations
            (entity_a_id, entity_b_id, relation_type, description, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            args.entity_a_id,
            args.entity_b_id,
            args.relation_type.strip(),
            args.description,
            args.source,
        ),
    )
    db.commit()
    db.close()
    print(
        f"Recorded relation: entity #{args.entity_a_id} --{args.relation_type}--> entity #{args.entity_b_id}"
    )


def correct_entity_field(
    entity_id, field, value, reason, corrected_by=None, correction_type="refinement"
):
    """Correct one whitelisted entity field and append an immutable audit row.

    Entity names are deliberately excluded: identity changes must use the alias
    and merge workflows so dependent graph rows are not silently orphaned.
    Empty values clear nullable metadata, but entity_type and status must remain
    non-empty.
    """
    if field not in ENTITY_CORRECT_FIELDS:
        raise ValueError(
            f"Cannot correct entity field '{field}'. Allowed: "
            f"{', '.join(sorted(ENTITY_CORRECT_FIELDS))}"
        )
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("An audit reason is required to correct an entity")
    if correction_type not in VALID_CORRECTION_TYPES:
        raise ValueError(
            f"Unsupported correction type '{correction_type}'. Allowed: "
            f"{', '.join(sorted(VALID_CORRECTION_TYPES))}"
        )

    normalized_value = str(value).strip() if value is not None else ""
    if field == "entity_type":
        normalized_value = normalized_value.lower()
        if normalized_value not in VALID_ENTITY_TYPES:
            raise ValueError(
                f"entity_type must be one of {', '.join(VALID_ENTITY_TYPES)}"
            )
    elif field == "status" and not normalized_value:
        raise ValueError("status cannot be blank")
    elif not normalized_value:
        normalized_value = None

    db = get_db()
    try:
        entity = db.execute(
            f"SELECT id, {field} FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()
        if entity is None:
            raise ValueError(f"Entity #{entity_id} does not exist")
        old_value = entity[field]
        if old_value == normalized_value:
            return False

        actor = (
            corrected_by
            or os.environ.get("ITHILDIN_AGENT_RUN_ID")
            or "human"
        )
        db.execute(
            """
            INSERT INTO corrections (
                table_name, record_id, field_name, old_value, new_value,
                reason, corrected_by, correction_type
            ) VALUES ('entities', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                field,
                old_value,
                normalized_value,
                reason,
                actor,
                correction_type,
            ),
        )
        db.execute(
            f"UPDATE entities SET {field} = ? WHERE id = ?",
            (normalized_value, entity_id),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cmd_correct(args):
    changed = correct_entity_field(
        args.entity_id,
        args.field,
        args.value,
        args.reason,
        corrected_by=args.by,
        correction_type=args.correction_type,
    )
    if changed:
        print(f"Corrected entity #{args.entity_id}.{args.field}")
        print(f"  Reason: {args.reason.strip()}")
    else:
        print(f"Entity #{args.entity_id}.{args.field} already has that value; no change.")


def _relation_summary(r):
    """One-line description of an entity_relations row (dict)."""
    return (
        f"#{r['id']}: entity {r['entity_a_id']} --{r['relation_type']}--> "
        f"entity {r['entity_b_id']}"
        + (f" [{r['description']}]" if r.get("description") else "")
        + (f" (source: {r['source']})" if r.get("source") else "")
    )


def cmd_delete_relation(args):
    """Delete an entity_relations edge, recording an audit entry in corrections.

    Selection is by explicit --relation-id, or by the triple
    (--entity-a-id, --entity-b-id, --relation-type). If a triple matches
    multiple rows, the matches are listed and the caller must re-run with the
    specific --relation-id (no silent mass delete).
    """
    have_triple = (
        args.entity_a_id is not None
        and args.entity_b_id is not None
        and args.relation_type is not None
    )
    if args.relation_id is None and not have_triple:
        print(
            "Specify --relation-id, or all of --entity-a-id --entity-b-id --relation-type."
        )
        sys.exit(1)

    db = get_db()

    if args.relation_id is not None:
        rows = db.execute(
            "SELECT * FROM entity_relations WHERE id = ?", (args.relation_id,)
        ).fetchall()
        selector = f"relation-id {args.relation_id}"
    else:
        rows = db.execute(
            """
            SELECT * FROM entity_relations
            WHERE entity_a_id = ? AND entity_b_id = ? AND relation_type = ?
            ORDER BY id
            """,
            (args.entity_a_id, args.entity_b_id, args.relation_type.strip()),
        ).fetchall()
        selector = (
            f"triple ({args.entity_a_id} --{args.relation_type}--> {args.entity_b_id})"
        )

    rows = [dict(r) for r in rows]

    if not rows:
        db.close()
        print(f"No entity_relations edge matches {selector}.")
        sys.exit(1)

    if len(rows) > 1:
        db.close()
        print(f"{len(rows)} edges match {selector}; refusing to mass-delete. Matches:")
        for r in rows:
            print(f"  {_relation_summary(r)}")
        print("Re-run with the specific --relation-id.")
        sys.exit(1)

    row = rows[0]

    print(f"Delete Plan (matched via {selector}):")
    print(f"  {_relation_summary(row)}")
    print(f"  Reason: {args.reason}")

    if args.dry_run:
        print("\n  [DRY RUN] No changes made.")
        db.close()
        return

    actor = args.actor or os.environ.get("ITHILDIN_AGENT_RUN_ID") or "human"

    # Audit: record full deleted row contents in corrections before removal so
    # the deletion is recoverable/traceable. correction_type='retraction' matches
    # the CHECK constraint on the corrections table.
    db.execute(
        """
        INSERT INTO corrections
            (table_name, record_id, field_name, old_value, new_value,
             reason, corrected_by, correction_type)
        VALUES ('entity_relations', ?, 'deleted', ?, NULL, ?, ?, 'retraction')
        """,
        (row["id"], repr(row), args.reason, actor),
    )
    db.execute("DELETE FROM entity_relations WHERE id = ?", (row["id"],))
    db.commit()
    db.close()

    print("\n  Deleted 1 edge; recorded audit entry in corrections.")


def main():
    parser = argparse.ArgumentParser(description="Entity registry helper for investigation.db")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("lookup", help="Lookup entities by name")
    p.add_argument("--name", required=True)
    p.add_argument("--limit", type=int, default=30)
    add_output_args(p)

    p = sub.add_parser("show", help="Show entity details with roles/addresses/relations")
    p.add_argument("entity_id", type=int)
    add_output_args(p)

    p = sub.add_parser("add-entity", help="Insert an entity row (resolve-or-create: matches near-duplicates first)")
    p.add_argument("--name", required=True)
    p.add_argument("--entity-type", choices=VALID_ENTITY_TYPES, default="unknown")
    p.add_argument("--jurisdiction")
    p.add_argument("--ein")
    p.add_argument("--status", default="active")
    p.add_argument("--source")
    p.add_argument("--notes")
    p.add_argument("--force-new", action="store_true",
                   help="Skip fuzzy auto-merge and recorded aliases; insert a new row unless an exact (name, jurisdiction) match exists")
    p.add_argument("--match-threshold", type=int, default=97,
                   help="Fuzzy auto-merge threshold, token_sort_ratio 0-100 (default 97 = near-exact)")

    p = sub.add_parser("add-role", help="Insert a person role for an entity")
    p.add_argument("--entity-id", type=int, required=True)
    p.add_argument("--person-name", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--date-start")
    p.add_argument("--date-end")
    p.add_argument("--source")

    p = sub.add_parser("add-address", help="Insert an address for an entity")
    p.add_argument("--entity-id", type=int, required=True)
    p.add_argument("--address", required=True)
    p.add_argument("--address-type", default="registered")
    p.add_argument("--date-observed")
    p.add_argument("--source")

    p = sub.add_parser("add-relation", help="Insert an entity-to-entity relationship")
    p.add_argument("--entity-a-id", type=int, required=True)
    p.add_argument("--entity-b-id", type=int, required=True)
    p.add_argument("--relation-type", required=True)
    p.add_argument("--description")
    p.add_argument("--source")

    p = sub.add_parser(
        "correct",
        help="Correct a canonical entity metadata field with an immutable audit row",
    )
    p.add_argument("entity_id", type=int)
    p.add_argument("--field", "-f", required=True, choices=sorted(ENTITY_CORRECT_FIELDS))
    p.add_argument(
        "--value",
        "-v",
        required=True,
        help="Replacement value; empty clears nullable metadata",
    )
    p.add_argument("--reason", "-r", required=True)
    p.add_argument("--by", help="Reviewer (default: agent run id or human)")
    p.add_argument(
        "--correction-type",
        choices=sorted(VALID_CORRECTION_TYPES),
        default="refinement",
    )

    p = sub.add_parser(
        "delete-relation",
        help="Delete an entity-to-entity relationship edge (records an audit entry)",
    )
    p.add_argument("--relation-id", type=int,
                   help="Row id of the entity_relations edge to delete")
    p.add_argument("--entity-a-id", type=int,
                   help="With --entity-b-id and --relation-type: select the edge by triple")
    p.add_argument("--entity-b-id", type=int)
    p.add_argument("--relation-type")
    p.add_argument("--reason", required=True, help="Why this edge is being deleted (audited)")
    p.add_argument("--actor", help="Who performed the deletion (default: agent run id or 'human')")
    p.add_argument("--dry-run", action="store_true", help="Show what would be deleted without changing anything")

    args = parser.parse_args()
    if args.command == "lookup":
        cmd_lookup(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "add-entity":
        cmd_add_entity(args)
    elif args.command == "add-role":
        cmd_add_role(args)
    elif args.command == "add-address":
        cmd_add_address(args)
    elif args.command == "add-relation":
        cmd_add_relation(args)
    elif args.command == "correct":
        try:
            cmd_correct(args)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            raise SystemExit(2)
    elif args.command == "delete-relation":
        cmd_delete_relation(args)


if __name__ == "__main__":
    main()
