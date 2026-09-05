"""Validate extraction provenance and write bounded 2020 coverage."""

import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from prepare import KEYWORDS

ROOT = Path(__file__).resolve().parent
EXTRA_TERMS = r"\b(?:assign\w*|mortgag\w*|liens?|collateral|security|financ\w*|acqui\w*)\b"


def clean(text):
    return " ".join(text.replace("\u200b", " ").replace("\xa0", " ").split())


def load(name):
    return json.loads((ROOT / name).read_text())


def main():
    sources = load("source-index.json")
    candidates = load("reviewed-candidates.json")
    ledgers = {name: load(name) for name in ["events.json", "ownership-interest-events.json", "notices.json", "proposed-events.json", "unresolved-events.json"]}
    records = [x for events in ledgers.values() for x in events]
    canonical = [s for s in sources if not s.get("duplicate_of")]
    visual_notes = {
        ("BLB-2020-04-30", 3): "Only the City Hall contact footer; no missing body text.",
        ("BLB-2020-05-14", 3): "Only the City Hall contact footer; no missing body text.",
        ("BLB-2020-05-21", 3): "Visually blank page.",
        ("BLB-2020-05-28", 3): "Visually blank page.",
        ("BLB-2020-12-23", 8): "Only GRANTED, continuing the Hojoko administrative-extension item on page 7; not an ownership or transfer item.",
    }
    assert len({e["event_id"] for e in records}) == len(records)
    all_gaps, rows = [], []
    for src in canonical:
        text = (ROOT / src["text_path"]).read_text().replace("\u200b", " ").replace("\xa0", " ")
        text_clean = clean(text)
        info = subprocess.run(["pdfinfo", str(ROOT / src["pdf_path"])], check=True, capture_output=True, text=True).stdout
        pdf_pages = int(re.search(r"(?m)^Pages:\s+(\d+)", info)[1])
        assert pdf_pages == src["page_count"]
        intervals = []
        for c in candidates:
            if c["source_id"] != src["source_id"]:
                continue
            start = text.find(c["item_text"])
            assert start >= 0
            intervals.append((start, start+len(c["item_text"])))
        hit_lines, gaps = [], []
        offset = 0
        for line_no, line in enumerate(text.splitlines(keepends=True), 1):
            if re.search(KEYWORDS + "|" + EXTRA_TERMS, line, re.I):
                hits = list(re.finditer(KEYWORDS + "|" + EXTRA_TERMS, line, re.I))
                unmatched = [m.group() for m in hits if not any(start<=offset+m.start()<end for start,end in intervals)]
                row = {"line": line_no, "text": line.strip(), "uncovered_terms": unmatched}
                hit_lines.append(row)
                if unmatched:
                    gaps.append(row)
            offset += len(line)
        # splitlines treats formfeeds as line boundaries but retains them, so
        # offsets stay aligned to the page-preserving text.
        all_gaps.extend([dict(gap, source_id=src["source_id"]) for gap in gaps])
        for event in [e for e in records if e["source_id"] == src["source_id"]]:
            assert clean(event["item_text"]) in text_clean
            if event.get("outcome_text"):
                assert clean(event["outcome_text"]) in clean(event["item_text"])
            assert 1 <= event["page_start"] <= event["page_end"] <= pdf_pages
            for side in ["parties_before", "parties_after"]:
                for party in event.get(side, []):
                    assert clean(party["source_quote"]) in clean(event["item_text"])
                    if party["interest_percent"] is not None:
                        assert "%" in party["source_quote"]
        src["text_qc"].update({"pdfinfo_page_count": pdf_pages, "page_count_matches_pdfinfo": True,
                               "sparse_pages_visually_checked": [{"page": p, "finding": visual_notes[(src["source_id"],p)], "image_path": f"visual-{src['source_id']}-page{p}.png"} for p in src["text_qc"]["sparse_page_numbers"]],
                               "ocr_required": False})
        counts = {name.removesuffix(".json"): sum(e["source_id"]==src["source_id"] for e in events) for name,events in ledgers.items()}
        rows.append({"source_id": src["source_id"], "archive_date": src["archive_date"], "document_vote_date": src["document_vote_date"],
                     "archive_date_matches_document_heading": src["archive_date_matches_document_heading"],
                     "sha256": src["sha256"], "page_count": pdf_pages,
                     "reviewed_candidate_count": sum(c["source_id"]==src["source_id"] for c in candidates),
                     **counts, "keyword_lines": hit_lines, "uncovered_keyword_lines": gaps})
    assert not all_gaps, all_gaps
    for src in sources:
        if src.get("duplicate_of"):
            src["text_qc"] = next(s["text_qc"] for s in canonical if s["source_id"]==src["duplicate_of"])
    outcome_by_type = {}
    for e in ledgers["events.json"]:
        outcome_by_type.setdefault(e["event_type"], Counter())[e["outcome"]]+=1
    coverage = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "All 20 exact observed 2020 PDF URLs in the retained older archive inventory. Identical SHA-256 variants share one extracted document; source occurrences are preserved.",
        "source_urls": len(sources), "successful_http_downloads": len(sources), "http_errors": 0,
        "unique_pdf_hashes": len(canonical), "unique_document_pages": sum(s["page_count"] for s in canonical),
        "duplicate_url_assets": [{"source_id": s["source_id"], "duplicate_of": s["duplicate_of"], "url": s["url"], "sha256": s["sha256"]} for s in sources if s.get("duplicate_of")],
        "archive_label_date_range": [min(s["archive_date"] for s in sources), max(s["archive_date"] for s in sources)],
        "document_date_discrepancies": [s["source_id"] for s in sources if not s["archive_date_matches_document_heading"]],
        "reviewed_candidates": len(candidates), "raw_numbered_scan_candidates": len(load("candidates.json")),
        "candidate_classification_counts": dict(Counter(c["review_classification"] for c in candidates)),
        "ledger_counts": {name: len(events) for name,events in ledgers.items()},
        "transfer_pledge_outcomes": outcome_by_type,
        "ownership_outcomes": dict(Counter(e["outcome"] for e in ledgers["ownership-interest-events.json"])),
        "ownership_license_scopes": dict(Counter(e["license_scope"] for e in ledgers["ownership-interest-events.json"])),
        "actual_revocation_or_release_events": 0,
        "explicit_entity_conversions": 0,
        "uncovered_keyword_lines": all_gaps,
        "review_method": "All document headings checked; broad full-document keyword scan including unnumbered text; every matching candidate manually reviewed; full item text, source IDs/URLs, and page spans retained. Five sparse pages and two ambiguous item/outcome layouts visually checked. No OCR required.",
        "keyword_pattern": KEYWORDS, "additional_full_document_pattern": EXTRA_TERMS,
        "limitations": ["The saved index is not proof of meeting completeness. No January–March 2020 materials were linked in that index; no missing-meeting reconciliation was performed.", "Board dispositions do not prove that an approved transaction closed, that a pledge remained effective, or that a loan was outstanding.", "Separate source occurrences, including deferred then granted Atlas applications and repeated Del Frisco's ownership applications, are not a deduplicated transaction count.", "The Asmabanu disposition printed 'Grated' is retained only in unresolved-events.json; it is not counted as a granted ownership change.", "Churrascaria's conditional revocation directive is retained as a notice, not as an established completed revocation."],
        "acquisition_environment_note": "Initial sandbox attempts failed at DNS before HTTP; sandbox-dns-attempts.json preserves them. Approved network execution made one successful HTTP attempt per exact observed URL, with no HTTP-error retry loop.",
        "documents": rows,
    }
    (ROOT / "source-index.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2)+"\n")
    (ROOT / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k:v for k,v in coverage.items() if k in ["unique_pdf_hashes","unique_document_pages","reviewed_candidates","ledger_counts","transfer_pledge_outcomes","ownership_outcomes","uncovered_keyword_lines"]},indent=2))


if __name__ == "__main__":
    main()
