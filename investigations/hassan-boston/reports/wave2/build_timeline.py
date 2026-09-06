"""Render reviewed ownership-event CSV as offline HTML and a cited Markdown timeline."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    csv.field_size_limit(8 * 1024 * 1024)
    with args.input.open(newline="") as source:
        reader = csv.DictReader(source)
        required = {"event_id", "property_key", "event_date", "event_type", "source_quote"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing fields: {required - set(reader.fieldnames or [])}")
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    ids = [row["event_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate event IDs in reviewed input")
    template = Path(__file__).with_name("timeline-template.html").read_text()
    payload = json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c")
    args.output.write_text(template.replace("__TIMELINE_DATA__", payload))
    groups = defaultdict(list)
    for row in rows:
        groups[row["property_key"]].append(row)
    lines = [
        "# Property ownership timeline — September 4, 2026",
        "",
        "Recorded transfers, trustee changes, financing and other dated observations. "
        "An index entry or assessment label is not a completed chain of title. "
        "Multiple parcel rows for one instrument are one transaction, not additional purchases.",
        "",
        f"{len(rows)} observations across {len(groups)} property/address/instrument groups. "
        "These are coverage counts, not owned-property totals.",
        "",
    ]
    for _, events in sorted(groups.items(), key=lambda item: (item[1][0]["county"], item[1][0]["property_label"])):
        events.sort(key=lambda row: (row["event_date"] or "9999", row["event_id"]))
        first = events[0]
        lines.extend([f"## {first['property_label']} — {first['municipality']}, {first['county']}", ""])
        primary, supplementary = [], []
        for row in events:
            kind = row["event_type"].replace("_", " ")
            date = row["event_date"] or "Date not established"
            if row.get("date_precision") == "year":
                date = date[:4]
            connector = " → " if any(term in kind.lower() for term in ('deed', 'conveyance')) else " / "
            parties = connector.join(filter(None, [row["from_party"], row["to_party"]]))
            capacities = "; ".join(filter(None, [row["from_capacity"], row["to_capacity"]]))
            ref = " ".join(filter(None, [row["registry"], row["book_page"] or row["source_ref"]]))
            url = row["source_url"]
            citation = f"[{ref}]({url})" if url.startswith(("https://", "http://")) else ref
            text = f"- **{date} — {kind}.** {parties}. {capacities}. {citation}. "
            text += f"{row['evidence_status']}."
            if row["consideration_usd"]:
                amount_label = "Assessor sale-price field" if "assess" in kind.lower() else "Consideration"
                text += f" {amount_label} USD: {row['consideration_usd']}."
            if row["loan_amount_usd"]:
                text += f" Loan face amount USD: {row['loan_amount_usd']}."
            if row["notes"]:
                text += " " + row["notes"].replace("\n", " ")
            if "assess" in kind.lower() or "permit" in kind.lower():
                supplementary.append(text)
            else:
                primary.append(text)
        lines.extend(primary or ["No original title transfer has yet been resolved for this group."])
        if supplementary:
            lines.extend(["", "<details><summary>Assessment and permit observations</summary>", ""])
            lines.extend(supplementary)
            lines.extend(["", "</details>"])
        lines.append("")
    args.output.with_suffix(".md").write_text("\n".join(lines))
    print(json.dumps({"events": len(rows), "groups": len(groups), "html": str(args.output)}))


if __name__ == "__main__":
    main()
