#!/usr/bin/env python3
"""El Peruano (Diario Oficial del Perú) gazette query tool.

Searches and fetches official Peruvian normative documents (Decretos Supremos,
Resoluciones Supremas, Resoluciones Ministeriales, etc.) published in the
Boletín de Normas Legales.

Endpoint discovery (probed 2026-04-27):
    - Search SPA at https://busquedas.elperuano.pe/ (Next.js + Apollo Client).
    - GraphQL endpoint: POST https://busquedas.elperuano.pe/api/graphql?op=Generic
      (the ?op=Generic query string is required — bare /api/graphql returns 404).
    - Document landing pages: https://busquedas.elperuano.pe/dispositivo/{tipoPublicacion}/{op}
      where op is a 7-digit-dash-1 identifier like 2493140-1.
    - Full text HTML: https://busquedas.elperuano.pe/api/visor_html/{op}
    - PDF: returned via urlPDF in search hits (resolves to /api/media/...).

The GraphQL operation `getGenericPublication` accepts:
    fechaIni, fechaFin (YYYYMMDD strings)
    institucion (entity id, optional)
    op (specific dispositivo id, optional)
    paginatedBy (page size, default 20)
    query (full-text query)
    start (offset)
    tipoDispositivo (e.g., "DECRETO SUPREMO", "RESOLUCION SUPREMA")
    tipoPublicacion (e.g., "NL"=Normas Legales, "BO"=Boletín Oficial,
                            "SE"=Separatas Especiales, "DJ"=Decl. Juradas)
    ci ("FULL"=daily edition, "ONLY"=specific date filter)

Usage:
    uv run python tools/query_elperuano.py search "Lockheed" --output out.json
    uv run python tools/query_elperuano.py search "F-16" \\
        --year 2026 --type "DECRETO SUPREMO" --output out.json
    uv run python tools/query_elperuano.py search "Comandante FAP" \\
        --date-from 20251101 --date-to 20251130 --output out.json
    uv run python tools/query_elperuano.py document 2493140-1 --full-text
    uv run python tools/query_elperuano.py document 2493140-1 \\
        --pdf --output ds-001.pdf
    uv run python tools/query_elperuano.py daily 2026-03-05 --output day.json
"""

import argparse
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path
from urllib.parse import urlencode

import requests

GRAPHQL_URL = "https://busquedas.elperuano.pe/api/graphql"
VISOR_URL = "https://busquedas.elperuano.pe/api/visor_html/{op}"
LANDING_URL = "https://busquedas.elperuano.pe/dispositivo/{tipo}/{op}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

# Common type code mapping. The portal stores tipoDispositivo as the full
# uppercase string; --type accepts either the short alias or the full string.
TYPE_ALIASES = {
    "DS": "DECRETO SUPREMO",
    "DL": "DECRETO LEGISLATIVO",
    "DU": "DECRETO DE URGENCIA",
    "RS": "RESOLUCION SUPREMA",
    "RM": "RESOLUCION MINISTERIAL",
    "RD": "RESOLUCION DIRECTORAL",
    "RJ": "RESOLUCION JEFATURAL",
    "RVM": "RESOLUCION VICEMINISTERIAL",
    "LEY": "LEY",
    "ORD": "ORDENANZA",
}

# Common ministry/sector institution codes observed in the Norma metadata.
# (sector ids on the Norma model — kept here for documentation; we filter
# client-side because the GraphQL `institucion` arg uses a different schema.)
KNOWN_SECTORS = {
    "2068": "DEFENSA",
    "2070": "ECONOMIA Y FINANZAS",
    "2076": "RELACIONES EXTERIORES",
    "2077": "INTERIOR",
    "2079": "TRANSPORTES Y COMUNICACIONES",
    "2083": "JUSTICIA Y DERECHOS HUMANOS",
}

# tipoPublicacion codes
PUB_TYPES = {
    "NL": "Normas Legales",
    "BO": "Boletín Oficial",
    "SE": "Separatas Especiales",
    "DJ": "Declaraciones Juradas",
    "PSD": "Patentes y Signos Distintivos",
}

GENERIC_QUERY = """query Generic($fechaIni: String, $fechaFin: String, $institucion: String, $op: String, $paginatedBy: Int, $query: String, $start: Int, $tipoDispositivo: String, $tipoPublicacion: String, $ci: String) {
  results: getGenericPublication(fechaIni: $fechaIni, fechaFin: $fechaFin, institucion: $institucion, op: $op, paginatedBy: $paginatedBy, query: $query, start: $start, tipoDispositivo: $tipoDispositivo, tipoPublicacion: $tipoPublicacion, ci: $ci) {
    totalHits start hasNext paginatedBy
    hits { clasificacion1 clasificacion2 fechaPublicacion nombreDispositivo op paginas rubro sector sumilla tipoDispositivo tipoPublicacion urlPDF urlPortada }
  }
}"""


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Origin": "https://busquedas.elperuano.pe",
        "Referer": "https://busquedas.elperuano.pe/",
    })
    return s


def _post_graphql(session: requests.Session, operation: str, variables: dict,
                  query: str = GENERIC_QUERY, timeout: int = 30) -> dict:
    """POST a GraphQL query to El Peruano. Operation name MUST appear in the URL
    query string (?op=<OperationName>) — the bare endpoint returns 404.
    """
    url = f"{GRAPHQL_URL}?op={operation}"
    payload = {"operationName": operation, "query": query, "variables": variables}
    resp = session.post(url, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"GraphQL HTTP {resp.status_code}: {resp.text[:300]}")
    body = resp.json()
    if "errors" in body and body["errors"]:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    return body.get("data", {})


# ---------------------------------------------------------------- search ----

def cmd_search(args: argparse.Namespace) -> None:
    sess = _session()
    variables: dict = {
        "query": args.query,
        "tipoPublicacion": args.publication or "NL",
        "start": args.start,
        "paginatedBy": args.page_size,
    }
    # Type filter (DS / RS / RM / DECRETO SUPREMO / etc.)
    if args.type:
        variables["tipoDispositivo"] = TYPE_ALIASES.get(
            args.type.upper(), args.type.upper()
        )
    # Year shorthand
    if args.year:
        variables["fechaIni"] = f"{args.year}0101"
        variables["fechaFin"] = f"{args.year}1231"
    if args.date_from:
        variables["fechaIni"] = args.date_from.replace("-", "")
    if args.date_to:
        variables["fechaFin"] = args.date_to.replace("-", "")

    all_hits: list[dict] = []
    page = 0
    while True:
        page += 1
        data = _post_graphql(sess, "Generic", variables)
        results = data.get("results") or {}
        hits = results.get("hits") or []
        # Filter out empty placeholder rows (the daily-bulletin marker rows
        # with empty op/nombreDispositivo).
        for h in hits:
            if not h.get("op") and not h.get("nombreDispositivo"):
                continue
            # Optional ministry filter (client-side on sector or sumilla).
            if args.ministry:
                sector_label = KNOWN_SECTORS.get(h.get("sector"), "")
                hay = (sector_label + " " + (h.get("sumilla") or "")).upper()
                if args.ministry.upper() not in hay:
                    continue
            # Add a stable landing URL for human review.
            h["landingUrl"] = LANDING_URL.format(
                tipo=h.get("tipoPublicacion") or "NL", op=h.get("op")
            )
            h["visorUrl"] = VISOR_URL.format(op=h.get("op"))
            all_hits.append(h)
        if not args.paginate or not results.get("hasNext"):
            break
        if page >= args.max_pages:
            break
        variables["start"] = variables.get("start", 0) + args.page_size
        time.sleep(0.4)

    out = {
        "query": args.query,
        "filters": {
            k: v for k, v in variables.items()
            if k in ("tipoDispositivo", "tipoPublicacion", "fechaIni", "fechaFin")
        },
        "ministry_filter": args.ministry,
        "totalHits": (data.get("results") or {}).get("totalHits", 0),
        "returned": len(all_hits),
        "hits": all_hits,
    }
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_hits)} hits (totalHits={out['totalHits']}) to {args.output}",
          file=sys.stderr)


# ---------------------------------------------------------------- document ----

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_STYLE_SCRIPT_RE = re.compile(
    r"<(style|script)\b[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE
)


def _strip_html(html: str) -> str:
    text = _STYLE_SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = unescape(text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def _extract_op(token: str) -> str:
    """Accept op like 2493140-1 or a full landing URL and return the op id."""
    token = token.strip()
    m = re.search(r"(\d{6,10}-\d+)", token)
    if not m:
        raise ValueError(f"Could not extract dispositivo id from {token!r}")
    return m.group(1)


def fetch_visor(session: requests.Session, op: str, timeout: int = 30) -> str:
    """Return raw HTML of the visor (full-text rendering) for a dispositivo."""
    resp = session.get(VISOR_URL.format(op=op), timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_landing_metadata(session: requests.Session, op: str, tipo: str = "NL",
                           timeout: int = 30) -> dict:
    """Fetch the Next.js landing page and extract the __NEXT_DATA__ Norma blob."""
    url = LANDING_URL.format(tipo=tipo, op=op)
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        resp.text, re.DOTALL,
    )
    if not m:
        return {"landingUrl": url}
    data = json.loads(m.group(1))
    norma = (data.get("props") or {}).get("pageProps", {}).get("dispositivo") or {}
    norma["landingUrl"] = url
    return norma


def cmd_document(args: argparse.Namespace) -> None:
    op = _extract_op(args.id_or_url)
    sess = _session()
    tipo_pub = args.publication or "NL"

    # Try metadata. If it fails (some types don't render the SSR blob), fall
    # back to a search-by-op lookup.
    try:
        meta = fetch_landing_metadata(sess, op, tipo_pub)
    except Exception as e:
        print(f"warn: landing fetch failed: {e}", file=sys.stderr)
        meta = {}
    if not meta.get("nombreDispositivo"):
        try:
            data = _post_graphql(
                sess, "Generic",
                {"op": op, "tipoPublicacion": tipo_pub, "start": 0, "paginatedBy": 5},
            )
            for h in (data.get("results") or {}).get("hits") or []:
                if h.get("op") == op:
                    meta = {**h, "landingUrl": LANDING_URL.format(tipo=tipo_pub, op=op)}
                    break
        except Exception as e:
            print(f"warn: graphql lookup failed: {e}", file=sys.stderr)

    out = {"op": op, "metadata": meta}

    if args.full_text or args.output:
        html = fetch_visor(sess, op)
        out["visorHtml"] = html if args.keep_html else None
        out["fullText"] = _strip_html(html)

    if args.pdf:
        url = meta.get("urlPDF")
        if not url:
            print("error: no urlPDF in metadata; cannot fetch PDF", file=sys.stderr)
            sys.exit(2)
        pdf = sess.get(url, timeout=60)
        pdf.raise_for_status()
        target = Path(args.output or f"{op}.pdf")
        target.write_bytes(pdf.content)
        print(f"Wrote PDF ({len(pdf.content)} bytes) to {target}", file=sys.stderr)
        return

    if args.output:
        Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- daily ----

def cmd_daily(args: argparse.Namespace) -> None:
    """List all NL dispositivos published on a given date."""
    date = args.date.replace("-", "")
    sess = _session()
    variables = {
        "fechaIni": date,
        "fechaFin": date,
        "tipoPublicacion": args.publication or "NL",
        "ci": "ONLY",
        "start": 0,
        "paginatedBy": args.page_size,
    }

    all_hits: list[dict] = []
    page = 0
    while True:
        page += 1
        data = _post_graphql(sess, "Generic", variables)
        results = data.get("results") or {}
        hits = results.get("hits") or []
        for h in hits:
            if not h.get("op") and not h.get("nombreDispositivo"):
                continue
            h["landingUrl"] = LANDING_URL.format(
                tipo=h.get("tipoPublicacion") or "NL", op=h.get("op")
            )
            all_hits.append(h)
        if not results.get("hasNext") or page >= args.max_pages:
            break
        variables["start"] += args.page_size
        time.sleep(0.4)

    out = {
        "date": date,
        "publication": variables["tipoPublicacion"],
        "totalHits": (data.get("results") or {}).get("totalHits", 0),
        "returned": len(all_hits),
        "hits": all_hits,
    }
    target = args.output or f"elperuano-{date}.json"
    Path(target).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_hits)} hits to {target}", file=sys.stderr)


# ---------------------------------------------------------------- main ----

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Full-text search across normative documents")
    s.add_argument("query", help="Search terms (e.g., 'Lockheed F-16')")
    s.add_argument("--year", type=int, help="Restrict to single year (YYYY)")
    s.add_argument("--date-from", help="YYYYMMDD or YYYY-MM-DD")
    s.add_argument("--date-to", help="YYYYMMDD or YYYY-MM-DD")
    s.add_argument("--type", help=(
        "Document type: DS, RS, RM, RD, LEY, ORD, "
        "or full label (e.g., 'DECRETO SUPREMO')"
    ))
    s.add_argument("--publication", default="NL",
                   help="tipoPublicacion code (NL/BO/SE/DJ; default NL)")
    s.add_argument("--ministry",
                   help="Filter by ministry name (matches sector or sumilla)")
    s.add_argument("--start", type=int, default=0, help="Result offset")
    s.add_argument("--page-size", type=int, default=20)
    s.add_argument("--paginate", action="store_true",
                   help="Auto-paginate through all results")
    s.add_argument("--max-pages", type=int, default=10)
    s.add_argument("--output", required=True, help="Path to JSON output file")
    s.set_defaults(func=cmd_search)

    d = sub.add_parser("document", help="Fetch a specific dispositivo by op id or URL")
    d.add_argument("id_or_url", help="Dispositivo id (e.g., 2493140-1) or full URL")
    d.add_argument("--publication", default="NL")
    d.add_argument("--full-text", action="store_true",
                   help="Fetch and strip the visor HTML for plain text")
    d.add_argument("--keep-html", action="store_true",
                   help="Also include the raw visor HTML in JSON output")
    d.add_argument("--pdf", action="store_true",
                   help="Download the PDF instead of JSON")
    d.add_argument("--output",
                   help="Output path (JSON for metadata/text, .pdf for --pdf)")
    d.set_defaults(func=cmd_document)

    y = sub.add_parser("daily", help="List all dispositivos published on a date")
    y.add_argument("date", help="YYYY-MM-DD or YYYYMMDD")
    y.add_argument("--publication", default="NL")
    y.add_argument("--page-size", type=int, default=50)
    y.add_argument("--max-pages", type=int, default=20)
    y.add_argument("--output", help="JSON output path")
    y.set_defaults(func=cmd_daily)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
