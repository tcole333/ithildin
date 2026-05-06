#!/usr/bin/env python3
"""
Epstein document catalog — Stage 4: Report generation.

Reads $WORKDIR/catalog.db populated by catalog_epstein_docs.py and emits
reports/epstein-document-catalog-YYYYMMDD.md.

Usage:
    uv run python tools/catalog_build_report.py \
        --workdir $WORKDIR \
        --output reports/epstein-document-catalog-YYYYMMDD.md
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import date
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TAXONOMY_PATH = REPO_ROOT / "investigations/epstein/document_taxonomy.yaml"
EXPOSED_DB = REPO_ROOT / "datasets/epstein_exposed.db"

CORPUS_DESCRIPTIONS = {
    "doj_vol11": "DOJ Vol 11 OCR'd release (EFTA bates; `~/projects/epstein-docs/output/documents.db`)",
    "lmsband": "LMSBAND corpus — 12 DOJ datasets with entity extraction (`datasets/lmsband_epstein_files.db`)",
    "unified": "Unified DB — emails + docs + entities + triples (`datasets/unified_epstein.db`)",
    "epstein_20k": "House Oversight 20K release (`datasets/epstein_files_20k.db`)",
    "doc_explorer": "Epstein Doc Explorer — LLM-categorized + RDF triples of the 20K (`datasets/Epstein-doc-explorer/document_analysis.db`)",
    "epstein_exposed": "EpsteinExposed.com person network DB (no documents) (`datasets/epstein_exposed.db`)",
}

LOOSE_DESCRIPTIONS = {
    "epstein_archive": "Epstein-archive web project — curated docs (Black Book, Flight Logs, Court Exhibits)",
    "epstein_emails_hf": "HuggingFace email dump sources (feed Unified DB)",
    "ds09_extracted": "WARC-extracted files from LMSBAND dataset 9 (heavily duplicated with lmsband corpus)",
    "epstractor_sample": "Epstractor sample outputs",
    "standalone_root_pdfs": "Standalone EFTA PDFs at datasets/ root (overlap with DOJ Vol 11)",
}


def fmt_num(n: int | None) -> str:
    if n is None:
        return "-"
    return f"{n:,}"


def pct(n: int, total: int) -> str:
    return f"{(n * 100 / total):.1f}%" if total else "-"


_DATE_RX = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}")


def _looks_like_date_range(de: str | None, dl: str | None) -> bool:
    """Guard against OCR-derived garbage like '0 Dec 2010' or '0180-01-01'."""
    if not de or not dl:
        return False
    # Require at least one bound to be an ISO-ish YYYY-MM-DD prefix
    return bool(_DATE_RX.match(de) and _DATE_RX.match(dl) and de >= "1970" and dl <= "2030")


def section(buf: list[str], title: str, level: int = 2) -> None:
    buf.append("")
    buf.append(f"{'#' * level} {title}")
    buf.append("")


def axis_names(tax: dict, axis_key: str) -> list[str]:
    return list(tax[axis_key].keys())


# --- Report sections ------------------------------------------------------


def executive_summary(buf, conn, tax):
    section(buf, "1. Executive summary")

    total = conn.execute("SELECT COUNT(*) FROM doc_refs").fetchone()[0]
    loose_total = conn.execute("SELECT COUNT(*) FROM loose_files").fetchone()[0]
    buf.append(f"- **Documents in structured corpora:** {fmt_num(total)}")
    buf.append(f"- **Loose files catalogued:** {fmt_num(loose_total)}")

    buf.append("")
    buf.append("Per-corpus totals:")
    buf.append("")
    buf.append("| Corpus | Documents | Share |")
    buf.append("|---|---:|---:|")
    for r in conn.execute("SELECT corpus, COUNT(*) n FROM doc_refs GROUP BY corpus ORDER BY n DESC"):
        buf.append(f"| {r['corpus']} | {fmt_num(r['n'])} | {pct(r['n'], total)} |")

    buf.append("")
    buf.append("Top document forms (axis 2) across all corpora:")
    buf.append("")
    buf.append("| Form | Count | Share |")
    buf.append("|---|---:|---:|")
    for r in conn.execute(
        "SELECT axis2, COUNT(*) n FROM classifications GROUP BY axis2 ORDER BY n DESC LIMIT 15"
    ):
        buf.append(f"| `{r['axis2']}` | {fmt_num(r['n'])} | {pct(r['n'], total)} |")

    buf.append("")
    buf.append("Most-populated (origin × form × custodian) triples:")
    buf.append("")
    buf.append("| Origin | Form | Custodian | Count |")
    buf.append("|---|---|---|---:|")
    for r in conn.execute(
        """SELECT axis1, axis2, axis3, COUNT(*) n
           FROM classifications
           GROUP BY axis1, axis2, axis3
           ORDER BY n DESC LIMIT 15"""
    ):
        buf.append(f"| {r['axis1']} | {r['axis2']} | {r['axis3']} | {fmt_num(r['n'])} |")


def corpus_inventory(buf, conn):
    section(buf, "2. Corpus inventory")

    for corpus, descr in CORPUS_DESCRIPTIONS.items():
        if corpus == "epstein_exposed":
            continue  # covered separately in person-network appendix
        section(buf, f"2.{list(CORPUS_DESCRIPTIONS.keys()).index(corpus) + 1} {corpus}", level=3)
        buf.append(descr)
        row = conn.execute(
            """SELECT COUNT(*) n, MIN(date_earliest) de, MAX(date_latest) dl
               FROM doc_refs WHERE corpus=?""",
            (corpus,),
        ).fetchone()
        if row and row["n"]:
            buf.append("")
            buf.append(f"- **Documents:** {fmt_num(row['n'])}")
            if _looks_like_date_range(row["de"], row["dl"]):
                buf.append(f"- **Date range (from metadata):** {row['de']} → {row['dl']}")
            # signal coverage
            sig = conn.execute(
                """SELECT
                       SUM(CASE WHEN filename IS NOT NULL THEN 1 ELSE 0 END) fn,
                       SUM(CASE WHEN existing_category IS NOT NULL THEN 1 ELSE 0 END) cat,
                       SUM(CASE WHEN dataset_num IS NOT NULL THEN 1 ELSE 0 END) ds,
                       SUM(CASE WHEN source_prefix IS NOT NULL THEN 1 ELSE 0 END) sp,
                       SUM(CASE WHEN content_sample IS NOT NULL AND content_sample != '' THEN 1 ELSE 0 END) cs
                   FROM doc_refs WHERE corpus=?""",
                (corpus,),
            ).fetchone()
            buf.append(
                f"- **Signal coverage:** filename {pct(sig['fn'] or 0, row['n'])}, "
                f"prior category {pct(sig['cat'] or 0, row['n'])}, "
                f"dataset# {pct(sig['ds'] or 0, row['n'])}, "
                f"source prefix {pct(sig['sp'] or 0, row['n'])}, "
                f"content sample {pct(sig['cs'] or 0, row['n'])}"
            )
            # top axis2 forms for this corpus
            buf.append("")
            buf.append("Top forms in this corpus:")
            buf.append("")
            buf.append("| Form | Count |")
            buf.append("|---|---:|")
            for r in conn.execute(
                """SELECT c.axis2, COUNT(*) n
                   FROM doc_refs d JOIN classifications c ON c.doc_ref_id = d.id
                   WHERE d.corpus = ?
                   GROUP BY c.axis2 ORDER BY n DESC LIMIT 8""",
                (corpus,),
            ):
                buf.append(f"| `{r['axis2']}` | {fmt_num(r['n'])} |")
        else:
            buf.append("")
            buf.append("- (no documents ingested — database missing or empty)")

    # Known overlaps
    buf.append("")
    buf.append("**Known overlaps between corpora:**")
    buf.append("")
    # doc_explorer doc_ids vs epstein_20k house_oversight_ids
    overlap_20k = conn.execute(
        """SELECT COUNT(*) FROM doc_refs a JOIN doc_refs b
           ON a.doc_id = b.doc_id
           WHERE a.corpus = 'epstein_20k' AND b.corpus = 'doc_explorer'"""
    ).fetchone()[0]
    buf.append(
        f"- **Epstein 20K ⇄ Doc Explorer:** {fmt_num(overlap_20k)} shared `HOUSE_OVERSIGHT_*` IDs "
        "(Doc Explorer is an LLM-analyzed derivative of the 20K release)."
    )
    # LMSBAND dataset 9 ⇄ ds09_extracted loose
    lms9 = conn.execute(
        "SELECT COUNT(*) FROM doc_refs WHERE corpus='lmsband' AND dataset_num=9"
    ).fetchone()[0]
    ds09 = conn.execute(
        "SELECT COUNT(*) FROM loose_files WHERE group_name='ds09_extracted'"
    ).fetchone()[0]
    buf.append(
        f"- **LMSBAND dataset 9 ⇄ loose ds09_extracted:** {fmt_num(lms9)} LMSBAND docs vs "
        f"{fmt_num(ds09)} loose files — the loose tree appears to be the raw extraction that fed LMSBAND."
    )
    # DOJ Vol 11 EFTA IDs present in LMSBAND
    efta_overlap = conn.execute(
        """SELECT COUNT(*) FROM doc_refs a JOIN doc_refs b
           ON a.filename = b.filename
           WHERE a.corpus='doj_vol11' AND b.corpus='lmsband'
             AND a.filename LIKE 'EFTA%'"""
    ).fetchone()[0]
    buf.append(
        f"- **DOJ Vol 11 ⇄ LMSBAND:** {fmt_num(efta_overlap)} filenames match (EFTA*.pdf); LMSBAND "
        "carries extraction metadata, DOJ Vol 11 carries OCR text — treat as two views of the same docs."
    )


def cross_corpus_matrix(buf, conn, tax):
    section(buf, "3. Cross-corpus form matrix")
    buf.append("Where to look for each document form:")
    buf.append("")
    corpora = [r[0] for r in conn.execute(
        "SELECT corpus FROM doc_refs GROUP BY corpus ORDER BY COUNT(*) DESC"
    )]
    buf.append("| Form | " + " | ".join(corpora) + " |")
    buf.append("|---|" + "|".join(["---:"] * len(corpora)) + "|")
    # Get every axis2 value actually present, no duplicates
    totals = {
        r[0]: r[1]
        for r in conn.execute("SELECT axis2, COUNT(*) FROM classifications GROUP BY axis2")
    }
    axis2_list = sorted(totals.keys(), key=lambda x: -totals[x])
    for form in axis2_list:
        if totals.get(form, 0) == 0:
            continue
        row = [f"`{form}`"]
        for corpus in corpora:
            n = conn.execute(
                """SELECT COUNT(*) FROM doc_refs d JOIN classifications c ON c.doc_ref_id=d.id
                   WHERE d.corpus=? AND c.axis2=?""",
                (corpus, form),
            ).fetchone()[0]
            row.append(fmt_num(n) if n else "-")
        buf.append("| " + " | ".join(row) + " |")


def origin_form_matrix(buf, conn, tax):
    section(buf, "4. Origin × form matrix")
    buf.append(
        "What kinds of material do we have from each investigation/proceeding? "
        "Only cells with ≥1 doc are shown."
    )
    buf.append("")
    rows = list(conn.execute(
        """SELECT axis1, axis2, COUNT(*) n FROM classifications
           WHERE axis1 != 'unknown' OR axis2 != 'unknown'
           GROUP BY axis1, axis2
           HAVING n > 0
           ORDER BY axis1, n DESC"""
    ))
    current_origin = None
    for r in rows:
        if r["axis1"] != current_origin:
            current_origin = r["axis1"]
            buf.append("")
            buf.append(f"**{current_origin}**")
            buf.append("")
            buf.append("| Form | Count |")
            buf.append("|---|---:|")
        buf.append(f"| `{r['axis2']}` | {fmt_num(r['n'])} |")


def coverage_gaps(buf, conn, tax):
    section(buf, "5. Coverage gaps")
    buf.append(
        "Taxonomy types with fewer than 10 documents found — either genuinely rare in the corpus, "
        "or signals aren't strong enough for the rule-based classifier to detect them."
    )
    buf.append("")
    counts = {r[0]: r[1] for r in conn.execute(
        "SELECT axis2, COUNT(*) FROM classifications GROUP BY axis2"
    )}
    buf.append("**Axis 2 (form) gaps (<10 docs):**")
    buf.append("")
    for form in axis_names(tax, "axis2_form"):
        n = counts.get(form, 0)
        if n < 10:
            buf.append(f"- `{form}`: {n}")

    counts_a1 = {r[0]: r[1] for r in conn.execute(
        "SELECT axis1, COUNT(*) FROM classifications GROUP BY axis1"
    )}
    buf.append("")
    buf.append("**Axis 1 (origin) gaps (<10 docs):**")
    buf.append("")
    for origin in axis_names(tax, "axis1_origin"):
        n = counts_a1.get(origin, 0)
        if n < 10:
            buf.append(f"- `{origin}`: {n}")

    counts_a3 = {r[0]: r[1] for r in conn.execute(
        "SELECT axis3, COUNT(*) FROM classifications GROUP BY axis3"
    )}
    buf.append("")
    buf.append("**Axis 3 (custodian) gaps (<10 docs):**")
    buf.append("")
    for c in axis_names(tax, "axis3_custodian"):
        n = counts_a3.get(c, 0)
        if n < 10:
            buf.append(f"- `{c}`: {n}")


def low_confidence(buf, conn):
    section(buf, "6. Confidence and low-coverage strata")

    total = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
    buf.append("Confidence distribution:")
    buf.append("")
    buf.append("| Bucket | Count | Share |")
    buf.append("|---|---:|---:|")
    for r in conn.execute(
        """SELECT CASE
                    WHEN confidence >= 0.8 THEN 'high (>=0.8)'
                    WHEN confidence >= 0.5 THEN 'medium (0.5-0.8)'
                    WHEN confidence > 0    THEN 'low (0-0.5)'
                    ELSE 'zero'
                  END bucket, COUNT(*) n
           FROM classifications
           GROUP BY bucket ORDER BY n DESC"""
    ):
        buf.append(f"| {r['bucket']} | {fmt_num(r['n'])} | {pct(r['n'], total)} |")

    buf.append("")
    buf.append(
        "**LLM validation:** not yet run. "
        "Stage 3 (`tools/catalog_llm_sample.py`) is staged but requires "
        "`ANTHROPIC_API_KEY` in .env and `anthropic` added to `pyproject.toml`. "
        "Run after key setup to sanity-check rule output and discover missing types."
    )

    buf.append("")
    buf.append("**Highest-unknown strata** (most opportunity for rule refinement):")
    buf.append("")
    buf.append("| Corpus | axis1 | axis2 | axis3 | Count |")
    buf.append("|---|---|---|---|---:|")
    for r in conn.execute(
        """SELECT d.corpus, c.axis1, c.axis2, c.axis3, COUNT(*) n
           FROM doc_refs d JOIN classifications c ON c.doc_ref_id=d.id
           WHERE c.axis1='unknown' AND c.axis2='unknown'
           GROUP BY d.corpus, c.axis1, c.axis2, c.axis3
           ORDER BY n DESC LIMIT 10"""
    ):
        buf.append(f"| {r['corpus']} | {r['axis1']} | {r['axis2']} | {r['axis3']} | {fmt_num(r['n'])} |")


def loose_files_section(buf, conn):
    section(buf, "7. Loose files inventory")
    buf.append(
        "File-level inventory of dataset directories not backed by a structured DB. "
        "Sizes in MB."
    )
    buf.append("")
    buf.append("| Group | Files | Total size (MB) | Top extensions |")
    buf.append("|---|---:|---:|---|")
    for r in conn.execute(
        """SELECT group_name, COUNT(*) n, SUM(size_bytes) sz
           FROM loose_files GROUP BY group_name ORDER BY n DESC"""
    ):
        exts = conn.execute(
            """SELECT file_ext, COUNT(*) n FROM loose_files
               WHERE group_name=? GROUP BY file_ext ORDER BY n DESC LIMIT 5""",
            (r["group_name"],),
        ).fetchall()
        ext_str = ", ".join(f"`{e['file_ext']}` ({fmt_num(e['n'])})" for e in exts if e["file_ext"])
        sz_mb = (r["sz"] or 0) / (1024 * 1024)
        desc = LOOSE_DESCRIPTIONS.get(r["group_name"], "")
        buf.append(f"| **{r['group_name']}** — {desc} | {fmt_num(r['n'])} | {sz_mb:,.1f} | {ext_str} |")


def epstein_exposed_appendix(buf):
    section(buf, "8. EpsteinExposed person network (appendix)")
    if not EXPOSED_DB.exists():
        buf.append("_(EpsteinExposed DB not available)_")
        return
    conn = sqlite3.connect(EXPOSED_DB)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    buf.append(f"EpsteinExposed.com person database — {fmt_num(total)} persons (not documents).")
    buf.append("")
    buf.append("| Category | Persons |")
    buf.append("|---|---:|")
    for r in conn.execute(
        "SELECT category, COUNT(*) n FROM persons GROUP BY category ORDER BY n DESC"
    ):
        buf.append(f"| {r['category'] or '(none)'} | {fmt_num(r['n'])} |")
    bb = conn.execute(
        "SELECT COUNT(*) FROM persons WHERE black_book_entry=1"
    ).fetchone()[0]
    buf.append("")
    buf.append(f"- **Black book entries:** {fmt_num(bb)}")
    buf.append(
        "- **Use case:** cross-reference entity mentions in the document corpora "
        "against curated person metadata (categories, aliases, short bios). Query via "
        "`uv run python tools/ingest_epstein_exposed.py persons`."
    )
    conn.close()


def methodology(buf, conn, workdir):
    section(buf, "9. Methodology")
    buf.append(
        f"- **Working DB:** `{workdir}/catalog.db` (intermediate; not committed)"
    )
    buf.append(
        "- **Taxonomy:** `investigations/epstein/document_taxonomy.yaml` (3-axis: origin × form × custodian)"
    )
    buf.append(
        "- **Pipeline:** `tools/catalog_epstein_docs.py` (ingest + rule-based classify), "
        "`tools/catalog_build_report.py` (this report)"
    )
    buf.append("- **Rule families (in precedence order):**")
    buf.append("  1. Reuse of existing `category` fields from Unified DB and Doc Explorer")
    buf.append("  2. LMSBAND dataset 9/10 financial-subtable and travel-subtable lookup")
    buf.append("  3. Document-ID prefix (`HOUSE_OVERSIGHT_*`, `EFTA*`)")
    buf.append("  4. Filename regex (302, deposition, subpoena, indictment, flight_log, etc.)")
    buf.append("  5. Source path directory segments (`sdny/`, `usvi/`, `giuffre/`, etc.)")
    buf.append("  6. File extension fallback (.eml → email, .jpg → photograph_video, etc.)")
    buf.append("  7. Content keyword scan on first 2KB (FD-302, deposition of, NPA, compound email headers)")
    buf.append("")
    buf.append("- **Not yet run:** Stage 3 LLM-sampled validation.")
    buf.append("- **Caveats:**")
    buf.append("  - 3 sources returning the same document is redundancy, not corroboration "
               "(see CLAUDE.md). Overlaps are noted in §2 rather than deduplicated.")
    buf.append("  - The `email` count in DOJ Vol 11 is ~96% of the corpus because the "
               "release is largely Epstein's comms records (OCR'd scans preserving "
               "From/To/Subject headers).")
    buf.append("  - `unknown` at axis 1 (origin) is high because most local documents "
               "were released into collections (DOJ, HouseO) without preserved "
               "provenance back to the original proceeding that generated them.")


# --- Main -----------------------------------------------------------------


def build_report(workdir: Path, output: Path) -> None:
    conn = sqlite3.connect(workdir / "catalog.db")
    conn.row_factory = sqlite3.Row
    with open(TAXONOMY_PATH) as f:
        tax = yaml.safe_load(f)

    buf: list[str] = []
    today = date.today().isoformat()
    buf.append(f"# Epstein document catalog — {today}")
    buf.append("")
    buf.append(
        "A structured inventory of locally-stored Epstein-related documents, "
        "classified along three orthogonal axes: investigative origin (what "
        "proceeding produced it), document form (what kind of document), and "
        "custodian (who held it). Rule-based classification; see §9 for method."
    )

    executive_summary(buf, conn, tax)
    corpus_inventory(buf, conn)
    cross_corpus_matrix(buf, conn, tax)
    origin_form_matrix(buf, conn, tax)
    coverage_gaps(buf, conn, tax)
    low_confidence(buf, conn)
    loose_files_section(buf, conn)
    epstein_exposed_appendix(buf)
    methodology(buf, conn, workdir)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(buf) + "\n")
    conn.close()
    print(f"Wrote {output} ({output.stat().st_size:,} bytes)")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workdir", required=True, help="Catalog working directory")
    p.add_argument("--output", required=True, help="Output markdown report path")
    args = p.parse_args()
    build_report(Path(args.workdir).expanduser(), Path(args.output))


if __name__ == "__main__":
    main()
