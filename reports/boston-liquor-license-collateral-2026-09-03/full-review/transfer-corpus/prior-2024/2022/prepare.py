"""Prepare page-preserving keyword candidates; extraction requires explicit review."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY = re.compile(
    r"transfer|pledg|\bstock\b|ownership|beneficial|convert|conversion|\bmember|revok|\bsale\b|\bsold\b|purchase|surrender|\bowner\b|\binterest\b|\bshares?\b|\bequity\b|corporate structure|stockholder",
    re.I,
)


def main():
    candidates = []
    unmatched = []
    for entry in json.loads((ROOT / "source-index.json").read_text()):
        pages = json.loads((ROOT / entry["pages_path"]).read_text())
        text = "\n".join(
            p["text"].replace("\u200b", "").replace("\u00a0", " ") for p in pages
        )
        offsets = []
        position = 0
        for page in pages:
            offsets.append((position, page["page"]))
            position += (
                len(page["text"].replace("\u200b", "").replace("\u00a0", " ")) + 1
            )
        matches = [
            m
            for m in re.finditer(
                r"(?m)^[ \t]*(\d{1,3})(?:[.,]|(?= Speakeasy))[ \t]+([^\n]*)", text
            )
            if not (
                (m[1] == "99" and m[2].startswith("Restaurant business"))
                or (m[1] == "48" and m[2].startswith("The enclosed floor plan"))
            )
        ]
        ranges = []
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            raw = text[m.start() : end].strip()
            if not KEY.search(raw):
                continue
            ranges.append((m.start(), end))

            def pp(pos):
                return next(p for start, p in reversed(offsets) if start <= pos)

            row = {
                "candidate_id": f"{entry['source_id']}-{i + 1:03d}",
                "source_id": entry["source_id"],
                "source_url": entry["url"],
                "source_sha256": entry["sha256"],
                "archive_date": entry["archive_date"],
                "page_start": pp(m.start(1)),
                "page_end": pp(
                    end
                    - len(text[m.start() : end])
                    + len(text[m.start() : end].rstrip())
                    - 1
                ),
                "item_number": int(m[1]),
                "heading": m[2].strip(),
                "item_text": raw,
                "license_numbers": list(
                    dict.fromkeys(
                        "LB-" + s
                        for s in re.findall(r"LB\s*[-\u2010-\u2015]?\s*(\d+)", raw)
                    )
                ),
            }
            candidates.append(row)
        for m in KEY.finditer(text):
            if not any(a <= m.start() < b for a, b in ranges):
                unmatched.append(
                    {
                        "source_id": entry["source_id"],
                        "offset": m.start(),
                        "context": text[max(0, m.start() - 150) : m.end() + 300],
                    }
                )
    (ROOT / "candidates.json").write_text(json.dumps(candidates, indent=2))
    (ROOT / "unmatched-keywords.json").write_text(json.dumps(unmatched, indent=2))
    for j in range(0, len(candidates), 25):
        (ROOT / f"review-{j // 25 + 1:02}.txt").write_text(
            "\n\n".join(
                f"=== {i + j + 1} | {c['candidate_id']} | pages {c['page_start']}-{c['page_end']} ===\n{c['item_text']}"
                for i, c in enumerate(candidates[j : j + 25])
            )
        )
    print("Candidates:", len(candidates), "unmatched:", len(unmatched))


if __name__ == "__main__":
    main()
