import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sources = json.loads((ROOT / "source-index.json").read_text())
items = []
coverage = []
for src in sources:
    if src["archive_year"] != 2024:
        continue
    f = ROOT / "documents" / f"{src['source_id']}.txt"
    if not f.exists():
        continue
    text = f.read_text()
    headers = list(re.finditer(r"(?m)^\s*(\d{1,2})[.)]\s+([^\n]+)", text))
    counts = 0
    for i, m in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[m.start() : end].strip()
        if not re.search(r"\btransfer\w*\b|\bpledge\w*\b", block, re.I):
            continue
        if not re.search(r"\blicen[cs]e\b", block, re.I):
            continue
        lic = re.search(r"LB\s*[‐‑–—-]?\s*(\d+)", block)
        name = m.group(2).strip()
        clean = " ".join(block.split())
        outcome_match = re.search(
            r"(?im)^\s*(Granted|Denied|Deferred|Withdrawn|Rejected|Approved|No Action|Acknowledged|Rescinded|Not approved)\b([^\n]*)",
            block,
        )
        counts += 1
        items.append(
            {
                "source_id": src["source_id"],
                "source_url": src["url"],
                "archive_date": src["archive_date"],
                "page_start": text[: m.start(1)].count("\f") + 1,
                "page_end": text[:end].rstrip().count("\f") + 1,
                "item_number": m.group(1),
                "license_number": f"LB-{lic.group(1)}" if lic else None,
                "party_heading": name,
                "outcome_guess": outcome_match.group(0).strip()
                if outcome_match
                else None,
                "item_text": block,
            }
        )
    coverage.append(
        {
            "source_id": src["source_id"],
            "page_count": text.count("\f"),
            "heading": text[:600],
            "keyword_candidate_count": counts,
        }
    )
(OUT / "candidates.json").write_text(
    json.dumps(items, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "candidate-coverage.json").write_text(
    json.dumps(coverage, ensure_ascii=False, indent=2) + "\n"
)
for x in items:
    print(
        f"{x['source_id']} p{x['page_start']}-{x['page_end']} item{x['item_number']} {x['license_number']} {x['party_heading']} OUTCOME={x['outcome_guess']}"
    )
print("TOTAL", len(items), "DOCUMENTS", len(coverage))
