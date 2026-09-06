"""Prepare a roster attachment for an unsent UCC data-access inquiry, offline."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
FIELDS = (
    "holder_id", "business_name", "name_variants", "dbas", "license_numbers",
    "source_row_ids", "scope_classes", "has_core_alcohol_license",
    "name_mode_review_reasons",
)


def build():
    source = BASE / "ucc-queue.json"
    queue = json.loads(source.read_text())
    holders = queue["holders"]
    if len({holder["holder_id"] for holder in holders}) != len(holders):
        raise ValueError("Duplicate holder IDs in the source queue")
    destination = BASE / "ucc-request-roster.csv"
    with destination.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for holder in sorted(holders, key=lambda row: (row["business_name"], row["holder_id"])):
            row = {field: holder[field] for field in FIELDS}
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list)
                             else value for key, value in row.items()})
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "prepared_not_sent",
        "purpose": "Scope an access or price inquiry for existing public UCC records; not a placed search or copy order.",
        "attachment": destination.name,
        "attachment_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "source_queue": source.name,
        "source_queue_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_roster": queue["source_roster"],
        "source_roster_sha256": queue["source_roster_sha256"],
        "holder_rows": len(holders),
        "license_count": len({number for holder in holders for number in holder["license_numbers"]}),
        "core_alcohol_holder_rows": sum(holder["has_core_alcohol_license"] for holder in holders),
        "name_mode_review_rows": sum(bool(holder["name_mode_review_reasons"]) for holder in holders),
        "list_cell_encoding": "JSON arrays within CSV cells, preserving source-name and row lineage.",
        "limitations": [
            "Holder IDs identify local normalized roster groups, not official company or UCC debtor IDs.",
            "Roster names, DBAs and license numbers do not establish debtor identity, jurisdiction, aliases or common ownership.",
            "Core alcohol records and separately flagged BYOB/unclear categories remain distinguishable.",
            "This attachment neither requests newly created analysis nor authorizes fees, purchases or agency contact.",
        ],
    }
    (BASE / "ucc-request-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(json.dumps({key: result[key] for key in
                      ("status", "holder_rows", "license_count", "core_alcohol_holder_rows", "name_mode_review_rows")}))
