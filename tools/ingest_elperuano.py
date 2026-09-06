#!/usr/bin/env python3
"""Ingest El Peruano normative documents into datasets/elperuano/.

Fetches the full text + metadata for one or more dispositivos and stores them
as canonical JSON files at:

    datasets/elperuano/<TIPO>-<NUMERO>.json

Optionally creates a finding via tools/findings_tracker.py.

Usage:
    uv run python tools/ingest_elperuano.py 2493140-1
    uv run python tools/ingest_elperuano.py 2493140-1 \\
        --finding "Lockheed Martin Peru sale" \\
        --confidence confirmed \\
        --quote "EL PRESIDENTE DE LA REPÚBLICA"
    uv run python tools/ingest_elperuano.py --search "F-16 Fuerza Aerea" \\
        --year 2026 --max 5
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Re-use the query module so we don't duplicate the GraphQL plumbing.
import query_elperuano as qep  # noqa: E402  (sibling import)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "datasets" / "elperuano"
DATASET_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(meta: dict, op: str) -> str:
    """Build a stable filename like DECRETO_SUPREMO-001-2026-DE.json."""
    tipo = (meta.get("tipoDispositivo") or "DOCUMENT").replace(" ", "_")
    nombre = (meta.get("nombreDispositivo") or op).strip()
    nombre = re.sub(r"[^A-Za-z0-9_./-]+", "_", nombre)
    nombre = nombre.lstrip("Nº").lstrip("N°").strip("_-. ")
    if not nombre:
        nombre = op
    return f"{tipo}-{nombre}.json"


def _fetch_one(op: str, publication: str = "NL") -> dict:
    sess = qep._session()
    meta = qep.fetch_landing_metadata(sess, op, publication)
    if not meta.get("nombreDispositivo"):
        # Fall back to GraphQL lookup by op
        data = qep._post_graphql(
            sess, "Generic",
            {"op": op, "tipoPublicacion": publication, "start": 0, "paginatedBy": 5},
        )
        for h in (data.get("results") or {}).get("hits") or []:
            if h.get("op") == op:
                meta = {**h, "landingUrl": qep.LANDING_URL.format(tipo=publication, op=op)}
                break

    visor_html = qep.fetch_visor(sess, op)
    full_text = qep._strip_html(visor_html)

    return {
        "op": op,
        "source": "elperuano",
        "tipoPublicacion": publication,
        "metadata": meta,
        "landingUrl": qep.LANDING_URL.format(tipo=publication, op=op),
        "visorUrl": qep.VISOR_URL.format(op=op),
        "fullText": full_text,
        "visorHtml": visor_html,
    }


def _save(record: dict, override_path: Path | None = None) -> Path:
    op = record["op"]
    if override_path:
        path = override_path
    else:
        path = DATASET_DIR / _safe_filename(record["metadata"], op)
    # Drop the raw HTML from disk (full text is enough; URL is preserved).
    persisted = {k: v for k, v in record.items() if k != "visorHtml"}
    path.write_text(json.dumps(persisted, ensure_ascii=False, indent=2))
    return path


def _create_finding(record: dict, args: argparse.Namespace) -> None:
    """Invoke findings_tracker.py to register a finding for this document."""
    meta = record["metadata"]
    nombre = meta.get("nombreDispositivo") or record["op"]
    tipo = meta.get("tipoDispositivo") or "DOCUMENT"
    sumilla = (meta.get("sumilla") or "").strip()

    full_text = (record.get("fullText") or "").strip()
    quote = args.quote.strip() if args.quote is not None else None
    if quote is None:
        # Derive a representative direct-quote excerpt: the sumilla is the
        # official summary — verbatim from the gazette page header.
        quote = sumilla[:480] if sumilla else full_text[:480]
    if not quote:
        raise ValueError("A finding requires a nonblank quote from the fetched document")
    if quote in sumilla:
        evidence_ref = record["landingUrl"]
    elif quote in full_text:
        evidence_ref = record["visorUrl"]
    else:
        raise ValueError("The requested quote does not occur in the fetched sumilla or full text")

    summary = (
        f"{tipo} {nombre} ({meta.get('fechaPublicacion','')}): {sumilla[:280]}"
    )
    detail = f"Source: {record['landingUrl']}\n\nSumilla: {sumilla}"

    cmd = [
        "uv", "run", "python", "tools/findings_tracker.py", "add",
        "--target", args.finding,
        "--type", "document",
        "--summary", summary,
        "--detail", detail,
        "--evidence", evidence_ref,
        "--claim-type", args.claim_type,
        "--source-quote", f"{evidence_ref}:{quote}",
        "--sources", "elperuano",
        "--confidence", args.confidence,
    ]
    print("-> " + " ".join(cmd[3:]), file=sys.stderr)
    res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"findings_tracker exit {res.returncode}: {res.stderr.strip()}")
    else:
        print(res.stdout.strip(), file=sys.stderr)


def cmd_ingest(args: argparse.Namespace) -> None:
    ops: list[str] = []
    if args.search:
        sess = qep._session()
        variables = {
            "query": args.search,
            "tipoPublicacion": args.publication,
            "start": 0,
            "paginatedBy": args.max or 20,
        }
        if args.year:
            variables["fechaIni"] = f"{args.year}0101"
            variables["fechaFin"] = f"{args.year}1231"
        if args.type:
            variables["tipoDispositivo"] = qep.TYPE_ALIASES.get(
                args.type.upper(), args.type.upper()
            )
        data = qep._post_graphql(sess, "Generic", variables)
        hits = (data.get("results") or {}).get("hits") or []
        ops = [h["op"] for h in hits if h.get("op")]
        if args.max:
            ops = ops[: args.max]
        print(f"Found {len(ops)} ops via search", file=sys.stderr)
    if args.ops:
        ops += args.ops

    if not ops:
        print("error: pass either OPs or --search QUERY", file=sys.stderr)
        sys.exit(2)

    finding_failed = False
    for op in ops:
        op = qep._extract_op(op)
        try:
            rec = _fetch_one(op, args.publication)
        except Exception as e:
            print(f"  [{op}] fetch failed: {e}", file=sys.stderr)
            continue
        path = _save(rec, args.output)
        meta = rec["metadata"]
        display_path = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        print(f"saved {display_path}  "
              f"({meta.get('tipoDispositivo')} {meta.get('nombreDispositivo')})",
              file=sys.stderr)

        if args.finding:
            try:
                _create_finding(rec, args)
            except (ValueError, RuntimeError) as exc:
                print(f"  [{op}] finding failed: {exc}", file=sys.stderr)
                finding_failed = True
    if finding_failed:
        raise SystemExit(1)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ops", nargs="*",
                   help="Dispositivo IDs (e.g., 2493140-1) or landing URLs")
    p.add_argument("--search", help="Pull all hits matching a search query")
    p.add_argument("--max", type=int, default=10, help="Max docs to ingest")
    p.add_argument("--year", type=int)
    p.add_argument("--type", help="DS, RS, RM, RD, LEY, ORD, or full label")
    p.add_argument("--publication", default="NL", help="tipoPublicacion (default NL)")
    p.add_argument("--output", type=Path,
                   help="Specific output JSON path (single-doc mode)")

    p.add_argument("--finding",
                   help="Target name — if set, create a finding via findings_tracker")
    p.add_argument("--claim-type", default="direct_quote",
                   choices=["direct_quote", "paraphrase", "inference",
                            "synthesis", "user_provided"])
    p.add_argument("--confidence", default="confirmed",
                   choices=["unverified", "low", "medium", "high", "confirmed"])
    p.add_argument("--quote", help="Override source-quote (default: sumilla)")

    args = p.parse_args()
    cmd_ingest(args)


if __name__ == "__main__":
    main()
