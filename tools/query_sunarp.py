#!/usr/bin/env python3
"""Peru SUNARP corporate / property registry lookup.

SUNARP publishes Peru's authoritative corporate registry (Registro de
Personas Jurídicas) and the property registry (Registro de Propiedad
Inmueble). Both are accessed via the **Servicio de Publicidad Registral
en Línea (SPRL)** at https://enlinea.sunarp.gob.pe — which requires:
  1. A registered user account (free signup with DNI/RUC)
  2. Pre-paid credits for property certificates (corporate name lookup
     is included free in some packages, paid in others)

Programmatic scraping is therefore not feasible without manual cookie
injection. This tool provides:
  - Best-effort name search using publicly indexed records (Google /
    Bing site:sunarp.gob.pe) — useful when SUNARP boletines or audit
    notices have been crawled
  - Direct deep-link URLs to the SPRL search forms
  - Optional manual cookie injection via SUNARP_COOKIE env var

Usage:
    python tools/query_sunarp.py search "SEMAN PERU SAC"
    python tools/query_sunarp.py partida 12345678   # if cookie set
    python tools/query_sunarp.py deep-links "Carlos Chavez Cateriano"

Source reliability: SUNARP records are primary-source government
filings. Indirect (Google-cached) hits should be marked paraphrase /
medium confidence until corroborated by direct SPRL pull.
"""

import argparse
import json
import os
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

USER_AGENT = "OSINT-Research/1.0 (peru-lockheed)"
SPRL_BASE = "https://enlinea.sunarp.gob.pe"
RATE_LIMIT = 1.0


def deep_links(query):
    """Return a dict of SUNARP deep-link URLs for manual follow-up."""
    q = quote_plus(query.strip())
    return {
        "query": query,
        "sprl_login": f"{SPRL_BASE}/sprl/IniciarSession.htm",
        "sprl_corporate_name_search": (
            f"{SPRL_BASE}/sprl-app-extranet/?searchType=NAME&q={q}"
        ),
        "publicidad_registral_landing": (
            "https://www.gob.pe/709-acceder-a-la-plataforma-de-servicio-"
            "de-publicidad-registral-en-linea-sprl"
        ),
        "google_site_search": (
            f"https://www.google.com/search?q=site%3Asunarp.gob.pe+{q}"
        ),
        "bing_site_search": (
            f"https://www.bing.com/search?q=site%3Asunarp.gob.pe+{q}"
        ),
        "boletines_sunarp": (
            f"https://www.sunarp.gob.pe/buscar.html?q={q}"
        ),
    }


def search_public_index(query):
    """Best-effort name search via the SUNARP institutional site (boletines,
    publicaciones, judicial notices). Returns hit URLs and titles where
    findable. NOT a substitute for SPRL — many corporate records are not
    publicly indexed."""
    q = quote_plus(query.strip())
    url = f"https://www.sunarp.gob.pe/buscar.html?q={q}"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError) as e:
        return {"query": query, "error": str(e), "results": []}

    # Very rough HTML extraction — SUNARP's site is server-rendered Liferay
    import re
    hits = []
    for m in re.finditer(r'<a[^>]+href="([^"]+sunarp[^"]+)"[^>]*>([^<]{10,200})</a>',
                         html):
        href, label = m.group(1), m.group(2).strip()
        if query.lower().split()[0] in (href + label).lower():
            hits.append({"url": href, "title": label})

    return {
        "query": query,
        "result_count": len(hits),
        "results": hits[:50],
        "_note": "Public-index search only. For full corporate records, use SPRL.",
    }


def fetch_partida(partida, zona="09"):
    """Attempt to fetch a partida registral. Requires SUNARP_COOKIE env var.

    Args:
        partida: Numeric partida (e.g. 12345678)
        zona: SUNARP zona registral code (e.g. 09 = Lima)
    """
    cookie = os.environ.get("SUNARP_COOKIE")
    if not cookie:
        return {
            "partida": partida,
            "zona": zona,
            "supported": False,
            "reason": (
                "SPRL requires authenticated session. Set SUNARP_COOKIE env "
                "var to a valid session cookie (login at "
                f"{SPRL_BASE}/sprl/IniciarSession.htm and copy the JSESSIONID "
                "cookie from your browser). Many partidas are paid-tier."),
            "manual_url": (
                f"{SPRL_BASE}/sprl-app-extranet/buscaTituloApp.html"
                f"?numero={partida}&zona={zona}"),
        }
    url = (f"{SPRL_BASE}/sprl-app-extranet/buscaTituloApp.html"
           f"?numero={partida}&zona={zona}")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Cookie": cookie})
    try:
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return {"partida": partida, "zona": zona, "html_size": len(html),
                "_note": "Raw HTML returned — parse externally.", "html": html}
    except (HTTPError, URLError) as e:
        return {"partida": partida, "zona": zona, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Peru SUNARP corporate / property registry lookup.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Best-effort name search via public index")
    p_search.add_argument("query", help="Company or person name")
    add_output_args(p_search)

    p_links = sub.add_parser("deep-links", help="Print direct SUNARP URLs for manual follow-up")
    p_links.add_argument("query", help="Company or person name")
    add_output_args(p_links)

    p_partida = sub.add_parser("partida", help="Fetch partida registral (requires cookie)")
    p_partida.add_argument("partida", help="Partida number")
    p_partida.add_argument("--zona", default="09", help="Zona registral (default 09 = Lima)")
    add_output_args(p_partida)

    args = parser.parse_args()

    if args.cmd == "search":
        data = search_public_index(args.query)
        if not write_output(data, args, summary=f"SUNARP search '{args.query}'"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "deep-links":
        data = deep_links(args.query)
        if not write_output(data, args, summary=f"SUNARP links '{args.query}'"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "partida":
        data = fetch_partida(args.partida, args.zona)
        if not write_output(data, args, summary=f"SUNARP partida {args.partida}"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
