#!/usr/bin/env python3
"""Peru OEFA (Organismo de Evaluación y Fiscalización Ambiental).

OEFA is the environmental enforcement agency. Public records are
distributed across:
  - Resoluciones / sanciones (administrative sanction rulings)
  - Informes técnicos (technical reports)
  - Reportes de fiscalización (oversight reports)
  - News / press releases on illegal mining, illegal logging, oil spills

OEFA's institutional pages live at https://www.gob.pe/oefa . The unified
gob.pe search endpoint at /busquedas filters by `institucion[]=oefa`.

Usage:
    python tools/query_oefa.py search "tala ilegal" --content publicaciones
    python tools/query_oefa.py search "Yang Zhihua"
    python tools/query_oefa.py recent --content noticias --limit 50

Source reliability: OEFA resolutions are primary-source government
records. News releases are agency-issued (high reliability for fact
of the action; may omit detail).
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0")
BASE = "https://www.gob.pe"
RATE_LIMIT = 1.0


def _get(url, timeout=25):
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        return f"<!--error: {e}-->"


# Regex for /institucion/oefa/<type>/<slug>  e.g.
# /institucion/oefa/informes-publicaciones/7720234-proveedores-...
_RESULT_RE = re.compile(
    r'<a[^>]+href="(?P<url>/institucion/oefa/(?P<type>[a-z0-9_-]+)/'
    r'(?P<slug>[0-9]+[a-z0-9_-]*))"[^>]*>(?P<title>[^<]{4,300})</a>',
    re.IGNORECASE | re.DOTALL,
)
# Card-format fallback: titles in h3/h4 followed by /institucion/oefa/...
_PATH_RE = re.compile(
    r'/institucion/oefa/(?P<type>[a-z0-9_-]+)/'
    r'(?P<slug>[0-9]+[a-z0-9_-]+)')


_INITIAL_DATA_RE = re.compile(
    r'window\.initialData\s*=\s*(\{.*?\})\s*;?\s*</script>', re.DOTALL)
_HREF_RE = re.compile(r'href="([^"]+)"')
_LABEL_RE = re.compile(r'>([^<]+)</a>')


def _parse_initial_data(html):
    """gob.pe injects search results as JSON into window.initialData. Return
    the parsed dict or None."""
    m = _INITIAL_DATA_RE.search(html)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def search(query, content_type="publicaciones", limit=50, institution="oefa",
           exclude_types=("BranchOffice",)):
    """Search gob.pe for institution-tagged content.

    content_type values (gob.pe filter):
      - publicaciones, normas, noticias, tramites, sedes, servicios, todos

    exclude_types: filter out searchable_type values that are usually noise
      for substantive queries (e.g. BranchOffice = list of office locations,
      which gob.pe ranks first regardless of query relevance).
    """
    qs = {"institucion[]": institution, "query": query}
    if content_type and content_type != "todos":
        qs["contenido[]"] = content_type
    url = f"{BASE}/busquedas?{urlencode(qs, doseq=True)}"
    html = _get(url)

    results = []
    total = None
    initial = _parse_initial_data(html)
    if initial:
        try:
            attrs = initial["data"]["attributes"]
            total = attrs.get("total_count")
            for r in attrs.get("results", []):
                if r.get("searchable_type") in exclude_types:
                    continue
                if len(results) >= limit:
                    break
                # `url` field is an HTML <a> tag with embedded href + label
                raw_url = r.get("url") or ""
                href_m = _HREF_RE.search(raw_url)
                label_m = _LABEL_RE.search(raw_url)
                href = href_m.group(1) if href_m else ""
                label = label_m.group(1).strip() if label_m else ""
                full_url = href if href.startswith("http") else f"{BASE}{href}"
                results.append({
                    "id": r.get("id"),
                    "title": label,
                    "url": full_url,
                    "type": r.get("searchable_type"),
                    "subtype": r.get("official_document_type") or r.get("group_type"),
                    "parent_type": r.get("parent_type"),
                    "subtitle": r.get("content_sub_title_card"),
                    "content": (r.get("content") or "")[:400],
                    "publication": r.get("publication"),
                    "score": r.get("score"),
                    "subject": r.get("subject"),
                    "action_url": r.get("action_url"),
                })
        except (KeyError, TypeError):
            pass

    # Regex fallback if JSON not found / changed
    if not results:
        seen = set()
        for m in _RESULT_RE.finditer(html):
            u = m.group("url")
            if u in seen:
                continue
            seen.add(u)
            results.append({
                "url": f"{BASE}{u}",
                "type": m.group("type"),
                "slug": m.group("slug"),
                "title": re.sub(r"\s+", " ", m.group("title")).strip(),
            })
            if len(results) >= limit:
                break

    # gob.pe's /busquedas endpoint does NOT actually filter by query text on
    # institutional content — it returns the institution's full corpus
    # ranked by visit / freshness, with a `total_count` equal to the
    # institution's entire content count (e.g. 50,712 for OEFA). The
    # `score` field reveals this: when the query matches nothing, all
    # scores are ~150 (default rank). When real text matches occur,
    # scores rise. We surface this signal as `_query_appears_matched`.
    matched = (total is not None and total < 5000) or any(
        r.get("score", 0) and r["score"] > 200 for r in results)
    return {
        "query": query,
        "institution": institution,
        "content_type": content_type,
        "search_url": url,
        "total_count": total,
        "result_count": len(results),
        "_query_appears_matched": matched,
        "_note": ("gob.pe search returns institution-ranked content "
                  "regardless of query when total_count == institution's "
                  "full corpus. Use `query_oefa.py site-search` for "
                  "Google-mediated text search."),
        "google_site_search_url": (
            f"https://www.google.com/search?q=site%3Agob.pe%2Finstitucion"
            f"%2F{institution}+{quote_plus(query)}"),
        "results": results,
    }


def fetch_record(path_or_url):
    """Fetch a single gob.pe/institucion/oefa/... page and return raw text
    + extracted title / date if findable."""
    if path_or_url.startswith("/"):
        url = f"{BASE}{path_or_url}"
    else:
        url = path_or_url
    html = _get(url)
    title_m = re.search(r"<title>([^<]+)</title>", html)
    h1_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    date_m = re.search(r'<time[^>]*datetime="([^"]+)"', html)
    return {
        "url": url,
        "title_tag": title_m.group(1).strip() if title_m else None,
        "h1": h1_m.group(1).strip() if h1_m else None,
        "date": date_m.group(1) if date_m else None,
        "html_size": len(html),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Peru OEFA (environmental enforcement) search.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search OEFA records on gob.pe")
    p_search.add_argument("query", help="Search term")
    p_search.add_argument("--content",
                          default="todos",
                          choices=["publicaciones", "normas", "noticias",
                                   "tramites", "sedes", "servicios", "todos"],
                          help="Content type filter")
    p_search.add_argument("--institution", default="oefa",
                          help="gob.pe institution slug (default: oefa). "
                               "Use 'mindef', 'fap', 'fiscalia' etc.")
    p_search.add_argument("--limit", type=int, default=50)
    add_output_args(p_search)

    p_record = sub.add_parser("record", help="Fetch a specific OEFA record")
    p_record.add_argument("path", help="Path or full URL")
    add_output_args(p_record)

    args = parser.parse_args()

    if args.cmd == "search":
        data = search(args.query, args.content, args.limit,
                      institution=args.institution)
        if not write_output(data, args,
                            summary=f"{args.institution} search '{args.query}'"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "record":
        data = fetch_record(args.path)
        if not write_output(data, args, summary=f"OEFA record"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
