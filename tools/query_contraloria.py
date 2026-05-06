#!/usr/bin/env python3
"""Peru Contraloría General de la República (CGR) audit-report query tool.

The CGR publishes:
    1. Comunicados / noticias  — institutional press releases.
    2. Informes de Servicios de Control — published audit reports
       (control posterior/CPO, control simultáneo/CSI, control previo/CPR,
       acción de oficio/OSAN, etc.).
    3. Normas legales — internal CGR resoluciones.

Endpoint discovery (probed 2026-04-27):
    Direct CGR portals (apps8.contraloria.gob.pe, buscadorinformes.contraloria.gob.pe)
    are reachable from US/EU networks but were unreachable from the test
    environment (TCP timeouts to 161.132.147.245). The gob.pe Plataforma
    del Estado mirror exposes the same content via stable JSON endpoints:

        Search (works portal-wide; institucion[]= filters to CGR):
          https://www.gob.pe/busquedas.json
            ?institucion[]=contraloria
            &term=<text>
            &sort_by=fecha-publicacion
            &sheet=<page-1-indexed>
        Per-institution news index:
          https://www.gob.pe/institucion/contraloria/noticias.json?page=N
        Per-institution informes index:
          https://www.gob.pe/institucion/contraloria/informes-publicaciones.json?page=N
        Per-institution normas index:
          https://www.gob.pe/institucion/contraloria/normas-legales.json?page=N

    Audit-report ficha-resumen (PDF, on the CGR app):
        https://apps8.contraloria.gob.pe/SPIC/srvDownload/ViewPDF
            ?CRES_CODIGO=<codigo>&TIPOARCHIVO=<RE|ADJ|ARC>
        codigo format: YYYY{TYPE}{ENTITY_GROUP}{ENTITY_NUM}{NN}, e.g.
            2025CSI038800082  -> 2025, control simultáneo (CSI), entity-group
                                 0388 (a Lima entidad), seq 00082
            2024CPO043400057  -> control posterior, entity 0434, seq 00057
            2026CPRL43500001  -> control previo (CPRL), region 435 Cajamarca

The tool falls back gracefully: if the SPIC PDF endpoint is unreachable
the URL is still recorded as the citation reference for follow-up.

Usage:
    uv run python tools/query_contraloria.py search \\
        --entity "Fuerza Aérea" --output cgr-fap.json

    # Restrict to noticias only:
    uv run python tools/query_contraloria.py search \\
        --term "F-16" --type noticia --output cgr-f16.json

    # Browse the comunicados feed (most recent N pages):
    uv run python tools/query_contraloria.py feed --pages 3 \\
        --output cgr-feed.json

    # Pull a specific informe ficha-resumen:
    uv run python tools/query_contraloria.py report 2024CPO043400057 \\
        --output 2024CPO043400057.pdf

    # Or a press release / informe by gob.pe URL or numeric id:
    uv run python tools/query_contraloria.py report \\
        https://www.gob.pe/institucion/contraloria/noticias/1382747-... \\
        --output noticia.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html import unescape
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)

GOBPE_SEARCH = "https://www.gob.pe/busquedas.json"
GOBPE_INSTITUTION_FEED = (
    "https://www.gob.pe/institucion/contraloria/{section}.json"
)
GOBPE_PAGE_HOST = "https://www.gob.pe"

# Internal section -> gob.pe slug (also used as the user-facing --type filter)
TYPE_SECTIONS = {
    "noticia": "noticias",
    "informe": "informes-publicaciones",
    "norma": "normas-legales",
    "comunicado": "noticias",  # CGR uses noticias as comunicado feed
    "auditoria": "informes-publicaciones",  # alias
}

# CGR ficha-resumen download endpoint (apps8.contraloria.gob.pe).
SPIC_VIEWPDF = (
    "https://apps8.contraloria.gob.pe/SPIC/srvDownload/ViewPDF"
    "?CRES_CODIGO={codigo}&TIPOARCHIVO={archive}"
)

# CGR codigo regex: YYYY + TYPE (3-4 letters) + entity (3-4 digits, optional
# region letter prefix) + sequence (5 digits). The ARC archive concatenation
# uses dashes (2026-CPR-L435-00001).
SPIC_CODIGO_RE = re.compile(
    r"\b(?P<yr>\d{4})[-]?(?P<typ>CPO|CSI|CPR|CPRL|OSAN|CCO|OCI|CG)"
    r"[-]?(?P<ent>L?\d{3,4})[-]?(?P<seq>\d{5})\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- session ----

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.gob.pe/contraloria",
    })
    return s


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    return _WS_RE.sub(" ", unescape(_TAG_RE.sub(" ", s or ""))).strip()


def _extract_url_from_anchor(blob: str) -> str | None:
    if not blob:
        return None
    m = re.search(r'href="([^"]+)"', blob)
    return m.group(1) if m else None


def _absurl(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith("http"):
        return path
    if path.startswith("/"):
        return GOBPE_PAGE_HOST + path
    return path


# ---------------------------------------------------------------- search ----

def _search_one(session: requests.Session, term: str, page: int,
                tipo_filter: str | None, timeout: int = 30) -> dict:
    params = [
        ("institucion[]", "contraloria"),
        ("sheet", str(page)),
        ("sort_by", "fecha-publicacion"),
        ("term", term),
    ]
    # The gob.pe filter slot for the content_types facet is "contenido[]".
    # When set, the result list only contains that document_type. We still
    # do client-side type filtering as a defensive cross-check because the
    # filter taxonomy on gob.pe occasionally drifts.
    if tipo_filter == "noticia":
        params.append(("contenido[]", "noticia"))
    elif tipo_filter == "informe":
        params.append(("contenido[]", "publicacion"))
    elif tipo_filter == "norma":
        params.append(("contenido[]", "norma"))
    url = f"{GOBPE_SEARCH}?{urlencode(params)}"
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _normalize_search_hit(hit: dict, requested_type: str | None) -> dict | None:
    """Convert a gob.pe search-result row to a flat record."""
    name = hit.get("name_with_parent") or ""
    if not isinstance(name, str):
        name = ""
    name = _strip_html(name)
    desc = hit.get("description") or ""
    if not isinstance(desc, str):
        desc = ""
    desc = _strip_html(desc)
    href = _extract_url_from_anchor(hit.get("url") or "")
    href = _absurl(href)
    doc_type = hit.get("document_type") or ""

    # Client-side type filter as a defensive check.
    if requested_type:
        wanted = TYPE_SECTIONS.get(requested_type)
        if wanted and href and (f"/{wanted}/" not in href):
            return None

    rec = {
        "id": hit.get("id"),
        "title": name,
        "description": desc,
        "publication": hit.get("publication"),
        "document_type": doc_type or None,
        "url": href,
    }
    # Try to extract any embedded SPIC codigo (informe id) from the title or url
    for src in (name, desc, href or ""):
        m = SPIC_CODIGO_RE.search(src)
        if m:
            rec["spic_codigo"] = (m.group("yr") + m.group("typ").upper()
                                  + m.group("ent").upper() + m.group("seq"))
            rec["spic_pdf_url"] = SPIC_VIEWPDF.format(
                codigo=rec["spic_codigo"], archive="RE")
            break
    return rec


def cmd_search(args: argparse.Namespace) -> None:
    sess = _session()
    terms: list[str] = []
    if args.term:
        terms.extend(args.term)
    if args.entity:
        terms.extend(args.entity)
    if not terms:
        print("error: at least one --term or --entity required", file=sys.stderr)
        sys.exit(2)

    requested_type = args.type
    if requested_type and requested_type not in TYPE_SECTIONS:
        print(f"error: --type must be one of {sorted(TYPE_SECTIONS)}",
              file=sys.stderr)
        sys.exit(2)

    all_hits: list[dict] = []
    seen_ids: set[str] = set()
    facet_summary: dict = {}

    for term in terms:
        for page in range(1, args.max_pages + 1):
            try:
                payload = _search_one(sess, term, page, requested_type)
            except requests.RequestException as e:
                print(f"warn: search '{term}' page {page} failed: {e}",
                      file=sys.stderr)
                break
            attrs = (payload.get("data") or {}).get("attributes") or {}
            if page == 1:
                facet_summary[term] = {
                    "total_count": attrs.get("total_count"),
                    "by_content_type": (attrs.get("filters") or {}).get(
                        "content_types"),
                }
            results = attrs.get("results") or []
            if not results:
                break
            new_in_page = 0
            for r in results:
                rec = _normalize_search_hit(r, requested_type)
                if rec is None:
                    continue
                key = str(rec.get("id") or rec.get("url") or rec.get("title"))
                if key in seen_ids:
                    continue
                seen_ids.add(key)
                rec["query_term"] = term
                all_hits.append(rec)
                new_in_page += 1
            if not new_in_page:
                break
            time.sleep(0.3)

    out = {
        "tool": "query_contraloria.py",
        "command": "search",
        "filters": {"terms": terms, "type": requested_type,
                    "max_pages": args.max_pages},
        "facets": facet_summary,
        "returned": len(all_hits),
        "hits": all_hits,
    }
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_hits)} hits to {args.output}", file=sys.stderr)


# ---------------------------------------------------------------- feed ----

def cmd_feed(args: argparse.Namespace) -> None:
    """Walk the institutional noticias / informes feed in publication order."""
    section = TYPE_SECTIONS.get(args.type or "noticia", "noticias")
    sess = _session()
    items: list[dict] = []
    for page in range(1, args.pages + 1):
        url = GOBPE_INSTITUTION_FEED.format(section=section)
        try:
            resp = sess.get(url, params={"page": page}, timeout=30)
            resp.raise_for_status()
            page_items = resp.json()
        except (requests.RequestException, ValueError) as e:
            print(f"warn: feed page {page} failed: {e}", file=sys.stderr)
            break
        if not page_items:
            break
        items.extend(page_items)
        time.sleep(0.2)

    out = {
        "tool": "query_contraloria.py", "command": "feed",
        "section": section, "pages": args.pages,
        "returned": len(items), "items": items,
    }
    Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(items)} feed items to {args.output}", file=sys.stderr)


# ---------------------------------------------------------------- report ----

def cmd_report(args: argparse.Namespace) -> None:
    """Fetch a specific report.

    Accepts:
      - SPIC codigo (e.g. 2024CPO043400057) -> downloads ficha-resumen PDF
      - gob.pe URL or numeric id -> fetches the JSON-rendered noticia/informe
    """
    sess = _session()
    target = args.id

    # SPIC codigo path
    m = SPIC_CODIGO_RE.search(target)
    if m and "/institucion/contraloria" not in target:
        codigo = (m.group("yr") + m.group("typ").upper()
                  + m.group("ent").upper() + m.group("seq"))
        archive = (args.archive or "RE").upper()
        url = SPIC_VIEWPDF.format(codigo=codigo, archive=archive)
        out_path = Path(args.output) if args.output else Path(f"{codigo}_{archive}.pdf")
        try:
            r = sess.get(url, timeout=60)
            r.raise_for_status()
            out_path.write_bytes(r.content)
            print(f"Wrote {len(r.content)} bytes to {out_path}", file=sys.stderr)
        except requests.RequestException as e:
            stub = {
                "tool": "query_contraloria.py", "command": "report",
                "spic_codigo": codigo, "archive": archive,
                "spic_pdf_url": url,
                "error": f"unable to download: {e}",
                "note": (
                    "apps8.contraloria.gob.pe was not reachable from this "
                    "network. The URL above is the canonical CGR endpoint; "
                    "use a network with Peruvian connectivity, the WebFetch "
                    "tool, or the Wayback Machine."
                ),
            }
            stub_path = out_path.with_suffix(".json")
            stub_path.write_text(json.dumps(stub, ensure_ascii=False, indent=2))
            print(f"Wrote stub (download failed) to {stub_path}", file=sys.stderr)
        return

    # gob.pe URL/id path
    if target.startswith("http"):
        page_url = target
    elif target.isdigit():
        # Heuristic: numeric ids are stable across sections; try news first
        page_url = (f"{GOBPE_PAGE_HOST}/institucion/contraloria/noticias/"
                    f"{target}")
    else:
        print("error: id must be a SPIC codigo, a gob.pe URL, or a numeric id",
              file=sys.stderr)
        sys.exit(2)

    try:
        resp = sess.get(page_url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"error: fetch failed: {e}", file=sys.stderr)
        sys.exit(2)

    html = resp.text
    title = ""
    m_title = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    if m_title:
        title = _strip_html(m_title.group(1))
    body_text = _strip_html(html)[:100_000]

    # Look for any SPIC codigos referenced in the body
    codigos = sorted({
        m.group("yr") + m.group("typ").upper()
        + m.group("ent").upper() + m.group("seq")
        for m in SPIC_CODIGO_RE.finditer(body_text)
    })

    out = {
        "tool": "query_contraloria.py", "command": "report",
        "url": page_url, "title": title,
        "spic_codigos_referenced": codigos,
        "spic_pdf_urls": [SPIC_VIEWPDF.format(codigo=c, archive="RE")
                          for c in codigos],
        "text": body_text,
    }
    out_path = args.output or f"contraloria-{target.split('/')[-1]}.json"
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path}", file=sys.stderr)


# ---------------------------------------------------------------- main ----

def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="Search CGR-scoped content via gob.pe")
    s.add_argument("--term", action="append", help="Free-text search term")
    s.add_argument("--entity", action="append",
                   help="Audited-entity name (joined to term list)")
    s.add_argument("--type",
                   choices=sorted(TYPE_SECTIONS.keys()),
                   help="Filter to a specific content type")
    s.add_argument("--max-pages", type=int, default=5,
                   help="Pages of results per term (default 5)")
    s.add_argument("--output", required=True)
    s.set_defaults(func=cmd_search)

    f = sub.add_parser("feed", help="Walk the CGR comunicado / informe feed")
    f.add_argument("--type", choices=sorted(TYPE_SECTIONS.keys()),
                   default="noticia",
                   help="Feed to walk (default: noticia)")
    f.add_argument("--pages", type=int, default=3,
                   help="Number of pages to fetch (default 3)")
    f.add_argument("--output", required=True)
    f.set_defaults(func=cmd_feed)

    r = sub.add_parser("report", help="Fetch a specific report by SPIC codigo or URL")
    r.add_argument("id",
                   help="SPIC codigo (e.g. 2024CPO043400057), gob.pe URL, "
                        "or numeric id")
    r.add_argument("--archive", choices=["RE", "ADJ", "ARC"], default="RE",
                   help="SPIC archive variant (RE=resumen, ADJ=adjunto, "
                        "ARC=archivo full; default RE)")
    r.add_argument("--output")
    r.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
