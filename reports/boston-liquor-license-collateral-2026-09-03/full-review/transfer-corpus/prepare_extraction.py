"""Prepare page-preserving candidate items for manual review; no decision inference."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent


def prepare_google(index):
    for date in ["2025-10-01", "2025-11-06", "2025-11-20"]:
        entry = next(e for e in index if e["archive_date"] == date)
        stem = ROOT / "documents" / entry["source_id"]
        if not stem.with_suffix(".html").is_file():
            raise FileNotFoundError(f"Retrieve the indexed official Google page first: {entry['url']}")
        if date == "2025-10-01":
            soup = BeautifulSoup(stem.with_suffix(".html").read_text(), "html.parser")
            body = soup.select_one("#contents") or soup
            paragraphs = [p.get_text("", strip=False) for p in body.select("p")]
            text = "\n".join(paragraphs)
            if "Voting Hearing Agenda" not in text:
                raise ValueError("Published document text was not recovered")
            stem.with_suffix(".txt").write_text(text)
            pages = [{"page": None, "text": text}]
            source_file = stem.with_suffix(".html")
            entry["content_format"] = "published_html_no_pagination"
        else:
            source_file = stem.with_suffix(".pdf")
            if not source_file.read_bytes().startswith(b"%PDF-"):
                raise ValueError("Drive download is not PDF")
            subprocess.run(["pdftotext", "-layout", str(source_file), str(stem.with_suffix(".txt"))], check=True)
            text = stem.with_suffix(".txt").read_text()
            page_texts = text.split("\f")
            if not page_texts[-1].strip():
                page_texts.pop()
            pages = [{"page": i+1, "text": p} for i, p in enumerate(page_texts)]
            entry["pdf_path"] = str(source_file.relative_to(ROOT))
            entry["content_format"] = "pdf"
            match = re.search(r'https://drive.usercontent.google.com/uc[^\"]+', stem.with_suffix(".html").read_text())
            entry["download_url_observed_in_drive_page"] = match[0].encode().decode("unicode_escape")
        stem.with_suffix(".pages.json").write_text(json.dumps(pages, indent=2))
        entry.update({
            "retrieval_status": "downloaded", "bytes": source_file.stat().st_size,
            "sha256": hashlib.sha256(source_file.read_bytes()).hexdigest(),
            "html_path": str(stem.with_suffix(".html").relative_to(ROOT)),
            "text_path": str(stem.with_suffix(".txt").relative_to(ROOT)),
            "pages_path": str(stem.with_suffix(".pages.json").relative_to(ROOT)),
            "page_count": len(pages) if pages[0]["page"] is not None else None,
            "text_characters": len(text),
        })


def prepare_candidates(index):
    items = []
    for entry in index:
        if entry["archive_year"] < 2025:
            continue
        pages = json.loads((ROOT / entry["pages_path"]).read_text())
        for page in pages:
            page["text"] = page["text"].replace("\u200b", "").replace("\u00a0", " ")
        normalized_text = "\n".join(p["text"] for p in pages)
        page_offsets = []
        offset = 0
        for page in pages:
            page_offsets.append((offset, page["page"]))
            offset += len(page["text"]) + 1
        matches = list(re.finditer(r"(?m)^[ \t]*(\d{1,3})[.,][ \t]+([^\n]*)", normalized_text))
        for position, match in enumerate(matches):
            end = matches[position + 1].start() if position + 1 < len(matches) else len(normalized_text)
            raw = normalized_text[match.start():end].strip()
            if not re.search(r"transfer|pledg", raw, re.I):
                continue
            page_start = next((p for start, p in reversed(page_offsets) if match.start(1) >= start), None)
            trimmed_end = end - len(normalized_text[match.start():end]) + len(normalized_text[match.start():end].rstrip())
            page_end = next((p for start, p in reversed(page_offsets) if trimmed_end - 1 >= start), None)
            license_ids = list(dict.fromkeys(re.findall(r"LB\s*[-\u2010\u2011\u2013]?\s*(\d+)", raw)))
            items.append({
                "candidate_id": f"{entry['source_id']}-{position+1:03d}",
                "source_id": entry["source_id"], "source_url": entry["url"],
                "archive_date": entry["archive_date"], "page_start": page_start, "page_end": page_end,
                "item_number": int(match[1]), "heading": match[2].strip(),
                "license_numbers": [f"LB-{x}" for x in license_ids], "item_text": raw,
            })
    (ROOT / "candidates-2025-2026.json").write_text(json.dumps(items, indent=2))
    print(json.dumps({"candidate_items": len(items), "source_documents": len({x['source_id'] for x in items})}))


if __name__ == "__main__":
    index_path = ROOT / "source-index.json"
    index = json.loads(index_path.read_text())
    prepare_google(index)
    index_path.write_text(json.dumps(index, indent=2))
    prepare_candidates(index)
