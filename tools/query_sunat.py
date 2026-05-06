#!/usr/bin/env python3
"""Peru SUNAT (tax authority) RUC lookup.

SUNAT publishes the canonical taxpayer registry (RUC = Registro Único de
Contribuyentes). The official portal at https://e-consultaruc.sunat.gob.pe
requires solving a CAPTCHA on every search.

This tool wraps the free, no-auth third-party mirror at api.apis.net.pe/v1
which proxies SUNAT data. The mirror only supports lookup BY RUC NUMBER —
it does NOT support free-text name search. To resolve a company name to a
RUC, use one of:
  - SEACE procurement search (vendors are listed with RUC)
  - OpenCorporates Peru jurisdiction
  - The official portal (manual captcha)

Usage:
    python tools/query_sunat.py ruc 20100017491
    python tools/query_sunat.py ruc 20100017491 --output ruc.json
    python tools/query_sunat.py search "SEMAN PERU"   # name-resolution stub

Source reliability: SUNAT is the canonical Peruvian tax authority. The
apis.net.pe mirror returns the same fields as the official portal. Treat
results as primary-source government records.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

BASE_URL = "https://api.apis.net.pe/v1/ruc"
RATE_LIMIT = 0.6
USER_AGENT = "OSINT-Research/1.0 (peru-lockheed)"


def _get_json(url, timeout=20, retries=2):
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            })
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            if e.code in (429, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            # 422 / 401 etc: surface error body to caller
            try:
                return {"_http_status": e.code, **json.loads(body)}
            except Exception:
                return {"_http_status": e.code, "_body": body}
        except URLError:
            if attempt < retries:
                time.sleep(1)
                continue
            raise


def lookup_ruc(ruc):
    """Lookup a single RUC. Returns SUNAT record or error dict."""
    ruc = str(ruc).strip()
    if not ruc.isdigit() or len(ruc) != 11:
        return {"error": f"Invalid RUC '{ruc}': must be 11 digits"}
    url = f"{BASE_URL}?{urlencode({'numero': ruc})}"
    data = _get_json(url)
    if isinstance(data, dict) and "_http_status" in data:
        return {"ruc": ruc, "error": data.get("error") or data.get("_body"),
                "_http_status": data.get("_http_status")}
    # Add canonical key
    if isinstance(data, dict) and "numeroDocumento" in data:
        data["ruc"] = data.get("numeroDocumento")
        data["_source"] = "sunat (via apis.net.pe)"
        data["_fetched_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return data


def search_by_name(name):
    """Name-search workaround.

    apis.net.pe v1 does NOT support name search. We return a structured
    'not supported' response with deep links the user / agent can follow:
      - SUNAT portal (requires captcha)
      - SEACE vendor search
      - OpenCorporates Peru
    """
    name_q = name.strip()
    return {
        "query": name_q,
        "supported": False,
        "reason": "apis.net.pe v1 RUC mirror does not expose name search; "
                  "SUNAT portal requires CAPTCHA. Use SEACE or OpenCorporates.",
        "fallback_urls": {
            "sunat_portal": "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias",
            "seace_vendor_search": (
                f"https://prodapp2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml"
                f"?razonSocial={name_q.replace(' ', '+')}"
            ),
            "opencorporates_pe": (
                f"https://opencorporates.com/companies/pe?q={name_q.replace(' ', '+')}"
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Peru SUNAT RUC lookup (via apis.net.pe v1 mirror).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ruc = sub.add_parser("ruc", help="Lookup RUC number")
    p_ruc.add_argument("ruc", help="11-digit RUC")
    add_output_args(p_ruc)

    p_search = sub.add_parser("search", help="Search by company name (stub)")
    p_search.add_argument("name", help="Company name")
    add_output_args(p_search)

    p_batch = sub.add_parser("batch", help="Lookup multiple RUCs")
    p_batch.add_argument("rucs", nargs="+", help="RUC numbers")
    add_output_args(p_batch)

    args = parser.parse_args()

    if args.cmd == "ruc":
        data = lookup_ruc(args.ruc)
        if not write_output(data, args, summary=f"SUNAT RUC {args.ruc}"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0 if data.get("nombre") else 1

    if args.cmd == "search":
        data = search_by_name(args.name)
        if not write_output(data, args, summary=f"SUNAT search '{args.name}' (unsupported)"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "batch":
        out = []
        for r in args.rucs:
            out.append(lookup_ruc(r))
            time.sleep(RATE_LIMIT)
        if not write_output(out, args, summary=f"SUNAT batch ({len(args.rucs)})"):
            print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
