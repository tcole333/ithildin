"""Acquire only the 24 observed 2022 archive URLs, without retries."""

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT.parents[2] / "history-access-evidence/older-archive-index.json"


def main():
    source = json.loads(ARCHIVE.read_text())
    entries = []
    for entry in source["entries"]:
        if entry["year"] != 2022:
            continue
        for url in entry["distinct_urls"]:
            entries.append(
                {
                    "source_id": "BLB-" + entry["label_date"],
                    "archive_year": 2022,
                    "archive_date": entry["label_date"],
                    "archive_label": entry["full_list_label"],
                    "archive_entry_id": entry["entry_id"],
                    "url": url,
                    "source_url": url,
                    "discovered_on": source["source"]["source_url"],
                }
            )
    assert len(entries) == len({e["url"] for e in entries}) == 24
    session = requests.Session()
    for e in entries:
        stem = ROOT / "documents" / e["source_id"]
        e["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            r = session.get(e["url"], timeout=45)
            e.update(
                {
                    "http_status": r.status_code,
                    "final_url": r.url,
                    "content_type": r.headers.get("content-type"),
                }
            )
            r.raise_for_status()
            if not r.content.startswith(b"%PDF-"):
                raise ValueError("Observed archive URL did not return PDF")
            stem.with_suffix(".pdf").write_bytes(r.content)
            subprocess.run(
                [
                    "pdftotext",
                    "-layout",
                    str(stem.with_suffix(".pdf")),
                    str(stem.with_suffix(".txt")),
                ],
                check=True,
                capture_output=True,
            )
            raw = stem.with_suffix(".txt").read_text()
            pages = raw.split("\f")
            if pages and not pages[-1].strip():
                pages.pop()
            stem.with_suffix(".pages.json").write_text(
                json.dumps(
                    [{"page": i + 1, "text": p} for i, p in enumerate(pages)], indent=2
                )
            )
            e.update(
                {
                    "retrieval_status": "downloaded",
                    "sha256": hashlib.sha256(r.content).hexdigest(),
                    "bytes": len(r.content),
                    "pdf_path": str(stem.with_suffix(".pdf").relative_to(ROOT)),
                    "text_path": str(stem.with_suffix(".txt").relative_to(ROOT)),
                    "pages_path": str(
                        stem.with_suffix(".pages.json").relative_to(ROOT)
                    ),
                    "page_count": len(pages),
                    "text_characters": len(raw),
                    "text_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "text_qc": {
                        "characters_by_page": [len(p.strip()) for p in pages],
                        "empty_pages": [
                            i + 1 for i, p in enumerate(pages) if not p.strip()
                        ],
                        "pages_below_100_characters": [
                            i + 1 for i, p in enumerate(pages) if len(p.strip()) < 100
                        ],
                        "replacement_characters": raw.count("\ufffd"),
                    },
                    "transfer_keyword_count": len(re.findall("transfer", raw, re.I)),
                    "pledge_keyword_count": len(re.findall("pledg", raw, re.I)),
                }
            )
        except (
            requests.RequestException,
            ValueError,
            subprocess.CalledProcessError,
        ) as exc:
            e.update({"retrieval_status": "error", "error": str(exc)})
        (ROOT / "source-index.json").write_text(json.dumps(entries, indent=2))
        print(e["source_id"], e["retrieval_status"], e.get("page_count"), flush=True)


if __name__ == "__main__":
    main()
