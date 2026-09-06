"""Retain broad page-preserving candidates and every unmatched keyword context."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = re.compile(
    r"transfer|pledg|owner|interest|share|equity|sale|sold|stock|beneficial|membership|corporate structure|convert|conversion",
    re.I,
)
items = []
contexts = []
for e in json.loads((ROOT / "source-index.json").read_text()):
    if e.get("duplicate_of") or e["retrieval_status"] != "downloaded":
        continue
    pages = json.loads((ROOT / e["pages_path"]).read_text())
    text = "\n".join(
        p["text"].replace("\u200b", "").replace("\xa0", " ") for p in pages
    )
    offsets = []
    at = 0
    for p in pages:
        offsets.append((at, p["page"]))
        at += len(p["text"].replace("\u200b", "").replace("\xa0", " ")) + 1
    pattern = r"(?m)^[ \t]*(\d{1,3})(?:[.,]|\)\.?)[ \t]+([^\n]+)"
    if e["source_id"] == "BLB-2021-09-30":
        pattern = r"(?m)^[ \t]*(\d{1,3})(?:[.,]|\)\.?|(?=\s))[ \t]+([^\n]+)"
    starts = []
    for m in re.finditer(pattern, text):
        if (m[1] == "70" and m[2].startswith("Truc To Thanh")) or (
            m[1] == "100" and m[2].startswith("and kitchen. Feng Chen")
        ):
            continue
        if e["source_id"] == "BLB-2021-09-30" and not re.match(
            r"^[ \t]*\d+[.,)]", m[0]
        ):
            tail = text[m.end() :].lstrip()
            if not tail.startswith("D/B/A:"):
                continue
        starts.append(m)
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        segment = text[m.start() : end]
        section = re.search(
            r"(?mi)^(?:Old & New Business|Old and New Business|ALL ONE DAY SPECIAL|The following is applying|The Following Lodging|The Board previously voted|The following Common)",
            segment,
        )
        if section:
            end = m.start() + section.start()
        end = m.start() + len(text[m.start() : end].rstrip(" \n\t_"))
        raw = text[m.start() : end].strip()
        if not KEY.search(raw):
            continue
        p1 = next(p for o, p in reversed(offsets) if m.start(1) >= o)
        p2 = next(
            p
            for o, p in reversed(offsets)
            if end
            - len(text[m.start() : end])
            + len(text[m.start() : end].rstrip())
            - 1
            >= o
        )
        items.append(
            {
                "candidate_id": e["source_id"] + f"-c{i + 1:03d}",
                "source_id": e["source_id"],
                "source_url": e["url"],
                "source_sha256": e["sha256"],
                "archive_date": e["archive_date"],
                "page_start": p1,
                "page_end": p2,
                "item_number": m[1],
                "heading": m[2].strip(),
                "license_numbers": list(
                    dict.fromkeys(
                        "LB-" + n for n in re.findall(r"LB\s*[-–‑]?\s*(\d+)", raw)
                    )
                ),
                "item_text": raw,
            }
        )
    for p in pages:
        lines = p["text"].splitlines()
        for i, line in enumerate(lines):
            if KEY.search(line):
                contexts.append(
                    {
                        "source_id": e["source_id"],
                        "page": p["page"],
                        "line": i + 1,
                        "text": "\n".join(
                            lines[max(0, i - 2) : min(len(lines), i + 4)]
                        ),
                    }
                )
(ROOT / "candidates.json").write_text(json.dumps(items, indent=2))
(ROOT / "all-keyword-contexts.json").write_text(json.dumps(contexts, indent=2))
(ROOT / "candidate-review.txt").write_text(
    "\n\n".join(
        "### "
        + x["candidate_id"]
        + " p"
        + str(x["page_start"])
        + "-"
        + str(x["page_end"])
        + "\n"
        + x["item_text"]
        for x in items
    )
)
print(len(items), "candidates;", len(contexts), "keyword lines")
