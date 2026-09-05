"""One-attempt acquisition of exact retained 2020 archive links."""

import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OLD_INDEX = ROOT.parents[2] / "history-access-evidence/older-archive-index.json"


def main():
    if (ROOT / "source-index.json").exists():
        raise SystemExit("The acquisition manifest already exists; no requests made. Preserve the one-attempt audit before starting another authorized acquisition.")
    archive = json.loads(OLD_INDEX.read_text())
    assets = [a for a in archive["deduplicated_assets"] if 2020 in a["years"]]
    assets.sort(key=lambda a: (a["label_dates"][0], a["source_url"]))
    count = Counter()
    index = []
    hashes = {}
    session = requests.Session()
    session.headers["User-Agent"] = "Public-records research archive (single request per observed URL)"
    for asset in assets:
        date = asset["label_dates"][0]
        count[date] += 1
        sid = f"BLB-{date}" + (f"-v{count[date]}" if count[date] > 1 else "")
        entry = {
            "source_id": sid, "archive_date": date, "archive_year": 2020,
            "url": asset["source_url"], "archive_occurrences": asset["occurrences"],
            "retrieval_status": "pending", "request_attempts": 1,
        }
        try:
            response = session.get(entry["url"], timeout=45)
            entry.update({"http_status": response.status_code, "final_url": response.url,
                          "content_type": response.headers.get("Content-Type"),
                          "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
            response.raise_for_status()
            if not response.content.startswith(b"%PDF-"):
                raise ValueError("Response is not a PDF")
            digest = hashlib.sha256(response.content).hexdigest()
            entry.update({"sha256": digest, "bytes": len(response.content)})
            if digest in hashes:
                canonical = hashes[digest]
                entry.update({k: canonical[k] for k in ["pdf_path", "text_path", "pages_path", "page_count", "text_characters", "text_qc"]})
                entry.update({"retrieval_status": "downloaded_identical_hash", "duplicate_of": canonical["source_id"]})
            else:
                stem = ROOT / "documents" / sid
                pdf = stem.with_suffix(".pdf")
                pdf.write_bytes(response.content)
                subprocess.run(["pdftotext", "-layout", str(pdf), str(stem.with_suffix(".txt"))], check=True, capture_output=True)
                text = stem.with_suffix(".txt").read_text()
                texts = text.split("\f")
                if not texts[-1].strip():
                    texts.pop()
                pages = [{"page": i + 1, "text": t} for i, t in enumerate(texts)]
                stem.with_suffix(".pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2) + "\n")
                entry.update({
                    "retrieval_status": "downloaded", "pdf_path": str(pdf.relative_to(ROOT)),
                    "text_path": str(stem.with_suffix(".txt").relative_to(ROOT)),
                    "pages_path": str(stem.with_suffix(".pages.json").relative_to(ROOT)),
                    "page_count": len(pages), "text_characters": len(text),
                    "text_qc": {"page_character_counts": [len(t.strip()) for t in texts],
                                "sparse_page_numbers": [i + 1 for i, t in enumerate(texts) if len(t.strip()) < 100],
                                "replacement_character_count": text.count("\ufffd"),
                                "keyword_counts": {word: len(re.findall(word, text, re.I)) for word in ["transfer", "pledg", "stock", "ownership", "corporate structure", "granted", "denied", "deferred"]}},
                })
                hashes[digest] = entry
        except (requests.RequestException, ValueError, subprocess.CalledProcessError) as exc:
            entry.update({"retrieval_status": "error", "error": str(exc)})
        index.append(entry)
        (ROOT / "source-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
        print(sid, entry["retrieval_status"], entry.get("page_count"), flush=True)


if __name__ == "__main__":
    main()
