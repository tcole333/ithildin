"""Archive the official Boston board index and its linked 2024-2026 decisions."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
INDEX_URL = "https://www.boston.gov/departments/licensing-board/licensing-board-information-and-members"
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"], 1
)}


def date_from_label(label, year):
    match = re.search(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2})", label)
    return f"{year}-{MONTHS[match[1]]:02d}-{int(match[2]):02d}" if match else None


def make_index(path):
    ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, ROOT / "archive-index.html")
    soup = BeautifulSoup(Path(path).read_text(), "html.parser")
    entries = []
    videos = []
    older = Counter()
    seen = set()
    for anchor in soup.select("a[href]"):
        drawer = anchor.find_parent(class_="paragraphs-item-drawer")
        label = drawer.find("label") if drawer else None
        year_text = label.get_text(" ", strip=True) if label else ""
        if not re.fullmatch(r"20\d{2}", year_text):
            continue
        year = int(year_text)
        title = anchor.get_text(" ", strip=True)
        url = urljoin(INDEX_URL, anchor["href"])
        date = date_from_label(title, year)
        if "youtu" in url and "Voting" in title and year >= 2024:
            videos.append({"year": year, "archive_label": title, "archive_date": date, "url": url})
        if not any(token in url for token in [".pdf", "docs.google.com/document/", "drive.google.com/file/"]):
            continue
        if year < 2024:
            older[year] += 1
            continue
        if url in seen:
            continue
        seen.add(url)
        entries.append({
            "source_id": f"BLB-{date}", "archive_year": year,
            "archive_label": title, "archive_date": date,
            "url": url, "discovered_on": INDEX_URL,
            "format_hint": "pdf" if ".pdf" in url else "google_document",
            "retrieval_status": "pending",
        })
    entries.sort(key=lambda entry: (entry["archive_date"] or "", entry["url"]))
    (ROOT / "source-index.json").write_text(json.dumps(entries, indent=2))
    (ROOT / "archive-coverage.json").write_text(json.dumps({
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "index_url": INDEX_URL,
        "index_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "decision_links_by_year": dict(Counter(e["archive_year"] for e in entries)),
        "older_archive_link_counts_not_collected": dict(older),
        "voting_video_links": videos,
    }, indent=2))
    print(json.dumps({"decision_links_by_year": dict(Counter(e["archive_year"] for e in entries)), "total": len(entries)}), flush=True)


def collect():
    index_path = ROOT / "source-index.json"
    entries = json.loads(index_path.read_text())
    (ROOT / "documents").mkdir(exist_ok=True)
    session = requests.Session()
    for entry in entries:
        if entry["retrieval_status"] == "downloaded":
            continue
        if entry["format_hint"] != "pdf":
            entry["retrieval_status"] = "requires_document_review"
            continue
        stem = ROOT / "documents" / entry["source_id"]
        try:
            response = session.get(entry["url"], timeout=45)
            response.raise_for_status()
            if not response.content.startswith(b"%PDF-"):
                raise ValueError(f"Expected PDF; received {response.headers.get('Content-Type')}")
            pdf = stem.with_suffix(".pdf")
            pdf.write_bytes(response.content)
            subprocess.run(["pdftotext", "-layout", str(pdf), str(stem.with_suffix(".txt"))], check=True, capture_output=True)
            text = stem.with_suffix(".txt").read_text()
            pages = text.split("\f")
            if pages[-1].strip() == "":
                pages.pop()
            stem.with_suffix(".pages.json").write_text(json.dumps([
                {"page": i + 1, "text": page} for i, page in enumerate(pages)
            ], indent=2))
            entry.update({
                "retrieval_status": "downloaded", "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "final_url": response.url, "content_type": response.headers.get("Content-Type"),
                "bytes": len(response.content), "sha256": hashlib.sha256(response.content).hexdigest(),
                "pdf_path": str(pdf.relative_to(ROOT)), "text_path": str(stem.with_suffix(".txt").relative_to(ROOT)),
                "pages_path": str(stem.with_suffix(".pages.json").relative_to(ROOT)),
                "page_count": len(pages), "text_characters": len(text),
                "transfer_keyword_count": len(re.findall(r"transfer", text, re.I)),
                "pledge_keyword_count": len(re.findall(r"pledge", text, re.I)),
            })
        except (requests.RequestException, ValueError, subprocess.CalledProcessError) as exc:
            entry.update({"retrieval_status": "error", "error": str(exc)})
        index_path.write_text(json.dumps(entries, indent=2))
        print(entry["source_id"], entry["retrieval_status"], entry.get("page_count", ""), flush=True)
        time.sleep(1)
    index_path.write_text(json.dumps(entries, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-html")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.index_html:
        make_index(args.index_html)
    if args.download:
        collect()
