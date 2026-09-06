"""Acquire exact observed archive links once, preserving per-page extraction QC."""

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT.parents[2] / "history-access-evidence/older-archive-index.json"


def main():
    index = json.loads(ARCHIVE.read_text())
    entries = []
    seen = set()
    for item in index["entries"]:
        if item["year"] != 2023:
            continue
        for url in item["distinct_urls"]:
            if url in seen:
                continue
            seen.add(url)
            entries.append({
                "source_id": f"BLB-{item['label_date']}",
                "archive_year": 2023,
                "archive_date": item["label_date"],
                "archive_label": item["full_list_label"],
                "archive_entry_id": item["entry_id"],
                "url": url,
                "discovered_on": index["source"]["source_url"],
                "retrieval_status": "pending",
            })
    manifest = ROOT / "source-index.json"
    if manifest.exists():
        old = {e["url"]: e for e in json.loads(manifest.read_text())}
        entries = [old.get(e["url"], e) for e in entries]
    (ROOT / "documents").mkdir(exist_ok=True)
    with requests.Session() as session:
        for entry in entries:
            if entry["retrieval_status"] != "pending":
                continue
            try:
                response = session.get(entry["url"], timeout=45)
                entry.update(http_status=response.status_code, final_url=response.url,
                             content_type=response.headers.get("Content-Type"),
                             retrieved_at_utc=datetime.now(timezone.utc).isoformat())
                response.raise_for_status()
                if not response.content.startswith(b"%PDF-"):
                    raise ValueError("Response is not a PDF")
                stem = ROOT / "documents" / entry["source_id"]
                pdf = stem.with_suffix(".pdf")
                pdf.write_bytes(response.content)
                result = subprocess.run(
                    ["pdftotext", "-layout", str(pdf), str(stem.with_suffix(".txt"))],
                    check=True, capture_output=True, text=True,
                )
                text = stem.with_suffix(".txt").read_text()
                pages = text.split("\f")
                if not pages[-1].strip():
                    pages.pop()
                page_rows = [{"page": i + 1, "text": p} for i, p in enumerate(pages)]
                stem.with_suffix(".pages.json").write_text(json.dumps(page_rows, indent=2))
                info = subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True)
                page_count = int(re.search(r"(?m)^Pages:\s+(\d+)", info.stdout)[1])
                entry.update(
                    retrieval_status="downloaded", bytes=len(response.content),
                    sha256=hashlib.sha256(response.content).hexdigest(),
                    pdf_path=str(pdf.relative_to(ROOT)),
                    text_path=str(stem.with_suffix(".txt").relative_to(ROOT)),
                    pages_path=str(stem.with_suffix(".pages.json").relative_to(ROOT)),
                    page_count=page_count, extracted_page_count=len(pages),
                    page_character_counts=[len(p.strip()) for p in pages],
                    low_text_pages=[i + 1 for i, p in enumerate(pages) if len(p.strip()) < 100],
                    text_characters=len(text), extraction_stderr=result.stderr,
                )
            except (requests.RequestException, ValueError, subprocess.CalledProcessError) as exc:
                entry.update(retrieval_status="error", error=str(exc))
            manifest.write_text(json.dumps(entries, indent=2) + "\n")
            print(entry["source_id"], entry["retrieval_status"], entry.get("page_count"), flush=True)
            time.sleep(0.75)
    manifest.write_text(json.dumps(entries, indent=2) + "\n")


if __name__ == "__main__":
    main()
