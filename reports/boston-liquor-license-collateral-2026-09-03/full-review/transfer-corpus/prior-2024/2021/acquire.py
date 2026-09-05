"""Acquire only observed 2021 archive assets, retaining every URL and hash."""

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT.parents[2] / "history-access-evidence" / "older-archive-index.json"


def main():
    workdir = Path(tempfile.mkdtemp(prefix="osint-2021-", dir="/private/tmp"))
    index_path = ROOT / "source-index.json"
    if index_path.exists():
        previous = json.loads(index_path.read_text())
        if not all(
            "NameResolutionError" in e.get("error", "") and "http_status" not in e
            for e in previous
        ):
            raise SystemExit(
                "Acquisition already initialized; inspect retained index instead of retrying."
            )
        index_path.rename(ROOT / "sandbox-dns-failures.json")
    archive = json.loads(ARCHIVE.read_text())
    sources = []
    for entry in archive["entries"]:
        if entry["year"] != 2021:
            continue
        for i, url in enumerate(entry["distinct_urls"]):
            source_id = (
                "BLB-"
                + entry["label_date"]
                + (f"-v{i + 1}" if len(entry["distinct_urls"]) > 1 else "")
            )
            sources.append(
                {
                    "source_id": source_id,
                    "archive_date": entry["label_date"],
                    "archive_year": 2021,
                    "archive_label": entry["full_list_label"],
                    "url": url,
                    "source_url": url,
                    "archive_entry_id": entry["entry_id"],
                    "link_occurrences": [
                        a
                        for a in entry["link_occurrences"]
                        if a.get("absolute_url") == url
                    ],
                    "discovered_on": archive["source"]["source_url"],
                    "retrieval_status": "pending",
                }
            )
    session = requests.Session()
    hashes = {}
    for entry in sources:
        entry["attempted_at_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            response = session.get(entry["url"], timeout=45)
            entry.update(
                {
                    "http_status": response.status_code,
                    "final_url": response.url,
                    "content_type": response.headers.get("Content-Type"),
                }
            )
            response.raise_for_status()
            if not response.content.startswith(b"%PDF-"):
                raise ValueError("Observed URL did not return a PDF")
            digest = hashlib.sha256(response.content).hexdigest()
            entry.update(
                {
                    "sha256": digest,
                    "bytes": len(response.content),
                    "retrieval_status": "downloaded",
                }
            )
            if digest in hashes:
                original = hashes[digest]
                entry.update(
                    {
                        "duplicate_of": original["source_id"],
                        **{
                            k: original[k]
                            for k in [
                                "pdf_path",
                                "text_path",
                                "pages_path",
                                "page_count",
                                "text_characters",
                                "text_qc",
                            ]
                        },
                    }
                )
            else:
                stem = ROOT / "documents" / entry["source_id"]
                stem.with_suffix(".pdf").write_bytes(response.content)
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
                text = stem.with_suffix(".txt").read_text()
                pages = text.split("\f")
                if not pages[-1].strip():
                    pages.pop()
                stem.with_suffix(".pages.json").write_text(
                    json.dumps(
                        [{"page": j + 1, "text": p} for j, p in enumerate(pages)],
                        indent=2,
                    )
                )
                entry.update(
                    {
                        "pdf_path": str(stem.with_suffix(".pdf").relative_to(ROOT)),
                        "text_path": str(stem.with_suffix(".txt").relative_to(ROOT)),
                        "pages_path": str(
                            stem.with_suffix(".pages.json").relative_to(ROOT)
                        ),
                        "page_count": len(pages),
                        "text_characters": len(text),
                        "text_qc": {
                            "extraction": "pdftotext -layout",
                            "page_characters": [len(p.strip()) for p in pages],
                            "replacement_characters": text.count("\ufffd"),
                            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "ocr_applied": False,
                        },
                        "header_text": "\n".join(text.splitlines()[:20]),
                        "keywords": {
                            word: len(re.findall(word, text, re.I))
                            for word in [
                                "transfer",
                                "pledg",
                                "ownership",
                                "stock",
                                "convert",
                            ]
                        },
                    }
                )
                hashes[digest] = entry
        except (
            requests.RequestException,
            ValueError,
            subprocess.CalledProcessError,
        ) as exc:
            entry.update(
                {"retrieval_status": "error", "error": str(exc), "retry_count": 0}
            )
        index_path.write_text(json.dumps(sources, indent=2))
        print(
            entry["source_id"],
            entry["retrieval_status"],
            entry.get("page_count"),
            entry.get("duplicate_of", ""),
            flush=True,
        )
    (ROOT / "acquisition-run.json").write_text(
        json.dumps(
            {
                "at_utc": datetime.now(timezone.utc).isoformat(),
                "workdir": str(workdir),
                "archive_index_sha256": hashlib.sha256(
                    ARCHIVE.read_bytes()
                ).hexdigest(),
                "requests": len(sources),
                "retry_policy": "One attempt per observed URL; no retries.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
