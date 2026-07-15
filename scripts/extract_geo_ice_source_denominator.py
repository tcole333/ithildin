#!/usr/bin/env python3
"""Download and text-extract the GEO-linked ICE inspection/death-review denominator.

This is a source-preparation helper, not a finding generator. It preserves each
official URL, its local hash, extraction status, and every event/death-review
association so later quote review can distinguish a link from evidence.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, unquote, urlparse, urlsplit, urlunsplit

from pypdf import PdfReader


USER_AGENT = "Ithildin-OSINT/1.0 public-record research"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_name(url: str) -> str:
    name = Path(unquote(urlparse(url).path)).name or "document.pdf"
    return name.replace(" ", "_")


def request_url(url: str) -> str:
    """Encode path spaces while preserving the official source URL in output."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, parts.fragment))


def ocr_pdf(pdf_path: Path, text_path: Path, ocr_executable: Path) -> int:
    """OCR image-only PDFs page by page and return non-whitespace text size."""
    with tempfile.TemporaryDirectory(prefix="ice-ocr-", dir=pdf_path.parent.parent) as temp:
        prefix = Path(temp) / "page"
        rendered = subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "200", str(pdf_path), str(prefix)],
            capture_output=True,
            text=True,
            timeout=240,
        )
        if rendered.returncode != 0:
            raise RuntimeError(rendered.stderr.strip() or "pdftoppm OCR render failed")
        page_text = []
        for image in sorted(Path(temp).glob("page-*.jpg")):
            completed = subprocess.run(
                [str(ocr_executable), str(image)],
                capture_output=True,
                text=True,
                timeout=180,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or f"tesseract failed on {image.name}")
            page_text.append(completed.stdout.strip())
        text_path.write_text("\n\f\n".join(page_text) + "\n")
    return len("".join(text_path.read_text(errors="replace").split()))


def load_sources(inspection_index: Path, death_index: Path) -> tuple[list[dict], dict[str, dict]]:
    inspection = json.loads(inspection_index.read_text())
    associations: list[dict] = []
    sources: dict[str, dict] = {}
    for event_number, event in enumerate(inspection["events"], 1):
        event_id = f"inspection-{event_number:03d}"
        for artifact in event["artifacts"]:
            url = artifact["url"].replace("http://", "https://")
            associations.append({
                "association_type": "inspection",
                "event_id": event_id,
                "canonical_facility": event["canonical_facility"],
                "source_label": event["source_label"],
                "inspection_date": event["inspection_date"],
                "geo_role": event["geo_role"],
                "contract_channel": event["contract_channel"],
                "award_or_vehicle": event["award_or_vehicle"],
                "artifact_label": artifact["label"],
                "url": url,
            })
            sources.setdefault(url, {"url": url, "source_types": set()})["source_types"].add("inspection")

    with death_index.open(newline="", encoding="utf-8") as stream:
        for death_number, row in enumerate(csv.DictReader(stream), 1):
            url = row["source_url"].replace("http://", "https://")
            associations.append({
                "association_type": "death_review",
                "event_id": f"death-{death_number:03d}",
                "canonical_facility": row["matched_canonical_facilities"],
                "source_label": row["name"],
                "inspection_date": row["date_of_death"],
                "geo_role": "",
                "contract_channel": "",
                "award_or_vehicle": "",
                "artifact_label": "Detainee Death Review",
                "url": url,
            })
            sources.setdefault(url, {"url": url, "source_types": set()})["source_types"].add("death_review")
    return associations, sources


def download_one(
    url: str,
    pdf_dir: Path,
    text_dir: Path,
    ocr_executable: Path,
    ocr_if_any_page_blank: bool,
) -> dict:
    stem = hashlib.sha256(url.encode()).hexdigest()[:12]
    pdf_path = pdf_dir / f"{stem}-{source_name(url)}"
    text_path = text_dir / f"{stem}-{Path(source_name(url)).stem}.txt"
    result = {
        "url": url,
        "status": "error",
        "http_status": None,
        "content_type": "",
        "local_pdf": str(pdf_path),
        "local_text": str(text_path),
        "sha256": "",
        "bytes": 0,
        "pages": 0,
        "text_chars": 0,
        "text_nonspace_chars": 0,
        "extraction_method": "",
        "error": "",
    }
    try:
        request = urllib.request.Request(request_url(url), headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            result["http_status"] = getattr(response, "status", 200)
            result["content_type"] = response.headers.get("Content-Type", "")
        if not data.startswith(b"%PDF"):
            raise ValueError(f"response is not a PDF ({result['content_type']})")
        pdf_path.write_bytes(data)
        result["sha256"] = sha256_bytes(data)
        result["bytes"] = len(data)
        try:
            result["pages"] = len(PdfReader(pdf_path).pages)
        except Exception as exc:  # pdftotext may still recover malformed PDFs
            result["error"] = f"page-count warning: {exc}"
        completed = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(text_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "pdftotext failed")
        text = text_path.read_text(errors="replace")
        result["text_chars"] = len(text)
        result["text_nonspace_chars"] = len("".join(text.split()))
        result["extraction_method"] = "pdftotext"
        page_text = text.split("\f")[: result["pages"]]
        blank_page_present = any(len("".join(page.split())) < 20 for page in page_text)
        if result["text_nonspace_chars"] < 50 or (ocr_if_any_page_blank and blank_page_present):
            result["text_nonspace_chars"] = ocr_pdf(pdf_path, text_path, ocr_executable)
            result["text_chars"] = len(text_path.read_text(errors="replace"))
            result["extraction_method"] = "apple_vision_ocr"
        result["status"] = "ok"
    except Exception as exc:  # isolate and audit every source-specific transport/PDF failure
        result["error"] = str(exc)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspection-index", required=True, type=Path)
    parser.add_argument("--death-index", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    pdf_dir = args.workdir / "pdfs"
    text_dir = args.workdir / "texts"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    ocr_executable = args.workdir / "vision_ocr"
    compile_ocr = subprocess.run(
        ["swiftc", "-O", str(Path(__file__).with_name("vision_ocr.swift")), "-o", str(ocr_executable)],
        capture_output=True,
        text=True,
        timeout=240,
    )
    if compile_ocr.returncode != 0:
        raise RuntimeError(compile_ocr.stderr.strip() or "failed to compile Vision OCR helper")
    associations, source_map = load_sources(args.inspection_index, args.death_index)

    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(
                download_one,
                url,
                pdf_dir,
                text_dir,
                ocr_executable,
                "inspection" in source_map[url]["source_types"],
            ): url
            for url in source_map
        }
        for future in as_completed(futures):
            row = future.result()
            results[row["url"]] = row

    sources = []
    for url in sorted(source_map):
        row = results[url]
        row["source_types"] = sorted(source_map[url]["source_types"])
        row["association_count"] = sum(item["url"] == url for item in associations)
        sources.append(row)

    manifest = {
        "inspection_associations": sum(x["association_type"] == "inspection" for x in associations),
        "death_review_associations": sum(x["association_type"] == "death_review" for x in associations),
        "unique_urls": len(sources),
        "successful_downloads": sum(x["status"] == "ok" for x in sources),
        "failed_downloads": sum(x["status"] != "ok" for x in sources),
        "zero_text_documents": sum(x["status"] == "ok" and x["text_nonspace_chars"] == 0 for x in sources),
        "ocr_documents": sum(x["status"] == "ok" and x["extraction_method"] == "apple_vision_ocr" for x in sources),
        "sources": sources,
        "associations": associations,
    }
    output = args.workdir / "source-denominator-manifest.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: manifest[key] for key in (
        "inspection_associations", "death_review_associations", "unique_urls",
        "successful_downloads", "failed_downloads", "zero_text_documents", "ocr_documents",
    )}, indent=2))
    print(output)


if __name__ == "__main__":
    main()
