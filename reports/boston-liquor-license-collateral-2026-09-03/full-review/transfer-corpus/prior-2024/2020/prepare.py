"""Retain page-preserving broad candidates for manual disposition review."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYWORDS = r"\b(?:transf\w*|pledg\w*|stocks?|share\w*|beneficial|ownership|corporate|reorganiz\w*|members?\b(?!\s+present)|conver\w*|interests?|revok\w*|revoc\w*|rescind\w*|cancel\w*|surrend\w*|releas\w*|sold|sale)\b"


def main():
    index = json.loads((ROOT / "source-index.json").read_text())
    items = []
    coverage = []
    for src in index:
        if src.get("duplicate_of") or src["retrieval_status"] != "downloaded":
            continue
        raw_text = (ROOT / src["text_path"]).read_text()
        text = raw_text.replace("\u200b", " ").replace("\xa0", " ")
        starts = list(re.finditer(r"(?m)(?:^|(?<=\f))[ \t]*(\d{1,3}|[A-Z])[.),][ \t]+([^\n]+)", text))
        starts = [m for m in starts if not re.match(r"(?:SF|AM|PM)\b", m[2])]
        regions = [(0, starts[0].start() if starts else len(text), None)]
        regions += [(m.start(), starts[i+1].start() if i+1 < len(starts) else len(text), m) for i, m in enumerate(starts)]
        source_items = []
        for number, (start, end, match) in enumerate(regions):
            block = text[start:end].strip()
            if not re.search(KEYWORDS, block, re.I):
                continue
            hits = [m.group() for m in re.finditer(KEYWORDS, block, re.I)]
            if hits and all(h.lower() == "members" for h in hits) and "all members present" in block:
                continue
            license_matches = list(re.finditer(r"LB\s*[-‐‑–—]?\s*(\d+)", block))
            source_items.append({
                "candidate_id": f"{src['source_id']}-C{number:03d}",
                "source_id": src["source_id"], "source_url": src["url"],
                "source_urls": [x["url"] for x in index if x.get("sha256") == src["sha256"]],
                "archive_date": src["archive_date"],
                "page_start": raw_text[:match.start(1) if match else start].count("\f") + 1,
                "page_end": raw_text[:end].rstrip().count("\f") + 1,
                "item_number": match[1] if match else None,
                "heading": match[2].strip() if match else None,
                "license_ids_raw": list(dict.fromkeys(m.group() for m in license_matches)),
                "license_numbers": list(dict.fromkeys(f"LB-{m[1]}" for m in license_matches)),
                "keyword_hits": hits, "item_text": block,
                "character_start": start, "character_end": end,
            })
        items.extend(source_items)
        coverage.append({"source_id": src["source_id"], "page_count": src["page_count"],
                         "candidate_count": len(source_items), "document_heading": text[:850],
                         "full_document_keyword_line_count": sum(bool(re.search(KEYWORDS, line, re.I)) for line in text.splitlines())})
    (ROOT / "candidates.json").write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "candidate-coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "candidate-review.txt").write_text("\n\n".join(f"===== {x['candidate_id']} page {x['page_start']}-{x['page_end']} =====\n{x['item_text']}" for x in items))
    for x in items:
        print(x["candidate_id"], x["page_start"], x["item_number"], x["heading"], x["license_numbers"])
    print("TOTAL", len(items))


if __name__ == "__main__":
    main()
