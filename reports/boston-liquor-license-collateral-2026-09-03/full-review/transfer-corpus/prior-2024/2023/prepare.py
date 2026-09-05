"""Prepare numbered items and every unmatched keyword line for human review."""

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEYWORDS = re.compile(r"transfer|pledg|stock|shareholder|stockholder|beneficial|ownership|membership|issuance|corporate.{0,30}structure|conver(?:sion|t)|merger", re.I)


def main():
    sources = json.loads((ROOT / "source-index.json").read_text())
    all_items, candidates, coverage, uncovered = [], [], [], []
    for src in sources:
        if src["retrieval_status"] != "downloaded":
            continue
        raw = (ROOT / src["text_path"]).read_text()
        text = raw.replace("\u200b", "").replace("\u00a0", " ")
        headers = list(re.finditer(r"(?m)^[ \t\f]*(\d{1,3})[.)][ \t]+([^\n]*)", text))
        spans = []
        for i, match in enumerate(headers):
            start = match.start(1)
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            block = text[start:end].strip()
            item = {
                "candidate_id": f"{src['source_id']}-{i+1:03d}",
                "source_id": src["source_id"], "source_url": src["url"],
                "source_sha256": src["sha256"], "archive_date": src["archive_date"],
                "page_start": text[:start].count("\f") + 1,
                "page_end": text[:end].rstrip().count("\f") + 1,
                "item_number": match[1], "heading": match[2].strip(),
                "license_numbers": list(dict.fromkeys("LB-"+m for m in re.findall(r"LB\s*[‐‑–—-]?\s*(\d+)", block))),
                "item_text": block,
                "item_text_sha256": hashlib.sha256(block.encode()).hexdigest(),
            }
            all_items.append(item)
            if KEYWORDS.search(block):
                candidates.append(item)
                spans.append((start, end))
        offset = 0
        for line in text.splitlines(keepends=True):
            if KEYWORDS.search(line) and not any(a <= offset < b for a, b in spans):
                uncovered.append({"source_id": src["source_id"], "page": text[:offset].count("\f")+1, "line": line.rstrip()})
            offset += len(line)
        dates = re.findall(r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s*2023", text[:1000])
        coverage.append({"source_id": src["source_id"], "archive_date": src["archive_date"],
                         "header": text[:700], "header_dates": dates,
                         "numbered_items": len(headers), "candidates": sum(x["source_id"]==src["source_id"] for x in candidates),
                         "low_text_pages": src["low_text_pages"], "page_count": src["page_count"]})
    for name, value in [("all-items.json",all_items),("candidates.json",candidates),("candidate-coverage.json",coverage),("uncovered-keywords.json",uncovered)]:
        (ROOT/name).write_text(json.dumps(value,indent=2)+"\n")
    print(json.dumps({"sources":len(sources),"pages":sum(x["page_count"] for x in coverage),"items":len(all_items),"candidates":len(candidates),"uncovered_lines":len(uncovered)}))
    print(json.dumps(uncovered,indent=2))


if __name__ == "__main__":
    main()
