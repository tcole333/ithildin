#!/usr/bin/env python3
"""Peru Infogob (JNE) — political-figure / officials registry.

Infogob is the Jurado Nacional de Elecciones (JNE) public observatory at
https://infogob.jne.gob.pe . It indexes:
  - Hojas de vida (CVs / asset declarations) of elected officials
  - Party affiliations and political career arcs
  - Suspensions / vacancias / revocatorias
  - Procesos electorales (electoral history)

The legacy infogob.com.pe domain has been hijacked / redirects to
unrelated content — always use infogob.jne.gob.pe.

The search endpoint POST /Politico/ListarPolitico is protected by a
server-side validated Google reCAPTCHA. Programmatic search therefore
returns the friendly error: "Lo sentimos. Ocurrió un problema...".

Workarounds this tool supports:
  1. Direct profile fetch by URL slug (if you already have it from a
     prior crawl or manual search)
  2. Manual cookie + recaptcha-token injection via INFOGOB_COOKIE and
     INFOGOB_RECAPTCHA env vars (you solve the captcha once in a
     browser, copy the token, and run multiple lookups within its
     lifetime — typically 2 minutes)
  3. Deep-link generation for human follow-up

Usage:
    python tools/query_infogob.py person "Dina Boluarte"
    python tools/query_infogob.py person "Carlos Chavez" --apellido CHAVEZ
    python tools/query_infogob.py declaration <token>          # FichaPolitico fetch
    python tools/query_infogob.py deep-links "Yang Zhihua"

Source reliability: JNE records are primary-source. Asset declarations
filed by candidates are sworn statements with criminal penalties for
falsehood.
"""

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path
from urllib.parse import urlencode, quote_plus, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 "
              "Safari/537.36")
BASE = "https://infogob.jne.gob.pe"
RATE_LIMIT = 1.0


def _post(url, data, cookie=None, timeout=20):
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/Politico",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    if cookie:
        headers["Cookie"] = cookie
    req = Request(url, data=urlencode(data).encode("utf-8"),
                  headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return {"status": resp.status, "json": json.loads(body)}
            except json.JSONDecodeError:
                return {"status": resp.status, "html": body}
    except HTTPError as e:
        return {"status": e.code, "error": e.read().decode("utf-8", errors="replace")}
    except URLError as e:
        return {"status": 0, "error": str(e)}


def _get(url, cookie=None, timeout=20):
    headers = {"User-Agent": USER_AGENT, "Referer": f"{BASE}/"}
    if cookie:
        headers["Cookie"] = cookie
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return {"status": resp.status,
                    "html": resp.read().decode("utf-8", errors="replace")}
    except HTTPError as e:
        return {"status": e.code,
                "error": e.read().decode("utf-8", errors="replace")}
    except URLError as e:
        return {"status": 0, "error": str(e)}


def search_person(nombre="", apellido_pat="", apellido_mat="", dni=""):
    """Attempt to search Infogob for a politician.

    Without a fresh reCAPTCHA token, this will fail with the JNE 'Estado:
    danger' message. To bypass, set INFOGOB_RECAPTCHA env var to a
    g-recaptcha-response token captured from a manual browser solve, and
    optionally INFOGOB_COOKIE."""
    cookie = os.environ.get("INFOGOB_COOKIE")
    recap = os.environ.get("INFOGOB_RECAPTCHA")
    payload = {
        "IdDNI": dni,
        "TxApePat": apellido_pat.upper(),
        "TxApeMat": apellido_mat.upper(),
        "TxNombre": nombre.upper(),
        "PaginaTamano": 24,
        "PaginaNumero": 1,
        "TotalRegistros": 0,
    }
    if recap:
        payload["responseReCaptcha"] = recap
    res = _post(f"{BASE}/Politico/ListarPolitico", payload, cookie=cookie)
    out = {
        "query": {"nombre": nombre, "apellido_pat": apellido_pat,
                   "apellido_mat": apellido_mat, "dni": dni},
        "captcha_supplied": bool(recap),
        "raw": res,
    }
    if isinstance(res, dict) and res.get("json"):
        body = res["json"]
        if isinstance(body, dict) and body.get("Estado") == "danger":
            out["blocked"] = True
            out["reason"] = body.get("Mensaje")
        else:
            out["results"] = body if isinstance(body, list) else [body]
            out["blocked"] = False
    return out


def fetch_ficha_by_token(token):
    """Fetch a politician's full ficha (CV / declaration / electoral history)
    using their internal token. Token is the encoded ID at the end of
    /politico/<slug>_acerca-de_<token>.

    These three list endpoints power the ficha tabs and do NOT require
    captcha:
      - /Politico/ListarInformacionFichaPolitico
      - /Politico/ListarEstabilidadFichaPolitico
      - /Politico/_HistorialFichaPolitico?istrParameters=...
      - /Politico/_ProcesosFichaPolitico?istrParameters=...
    """
    out = {"token": token, "tabs": {}}
    for name, url, method in [
        ("informacion", f"{BASE}/Politico/ListarInformacionFichaPolitico", "POST"),
        ("estabilidad", f"{BASE}/Politico/ListarEstabilidadFichaPolitico", "POST"),
        ("historial",   f"{BASE}/Politico/_HistorialFichaPolitico?istrParameters={quote(token)}", "GET"),
        ("procesos",    f"{BASE}/Politico/_ProcesosFichaPolitico?istrParameters={quote(token)}", "GET"),
    ]:
        if method == "POST":
            res = _post(url, {"istrParameters": token})
        else:
            res = _get(url)
        out["tabs"][name] = res
        time.sleep(RATE_LIMIT)
    return out


def deep_links(query):
    q = quote_plus(query.strip())
    return {
        "query": query,
        "search_form": f"{BASE}/Politico",
        "google_site_search": f"https://www.google.com/search?q=site%3Ainfogob.jne.gob.pe+{q}",
        "google_hojavida": f"https://www.google.com/search?q=site%3Ainfogob.jne.gob.pe+{q}+%22hoja+de+vida%22",
        "radar_electoral": "https://web.jne.gob.pe/radarelectoral/",
        "_note": ("Infogob search itself requires solving a Google reCAPTCHA. "
                  "Use Google site-search to discover slugged URLs, then pass "
                  "the token to `query_infogob.py declaration <token>`."),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Peru Infogob (JNE) political-figure registry.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_person = sub.add_parser("person", help="Search Infogob for a politician")
    p_person.add_argument("name", help="First name (TxNombre)")
    p_person.add_argument("--apellido-pat", default="", help="Apellido paterno")
    p_person.add_argument("--apellido-mat", default="", help="Apellido materno")
    p_person.add_argument("--dni", default="", help="DNI (8 digits)")
    add_output_args(p_person)

    p_decl = sub.add_parser("declaration", help="Fetch ficha by internal token")
    p_decl.add_argument("token", help="istrParameters token (URL-encoded)")
    add_output_args(p_decl)

    p_links = sub.add_parser("deep-links", help="Print Infogob deep-link URLs")
    p_links.add_argument("query", help="Person name")
    add_output_args(p_links)

    args = parser.parse_args()

    if args.cmd == "person":
        data = search_person(nombre=args.name,
                             apellido_pat=args.apellido_pat,
                             apellido_mat=args.apellido_mat,
                             dni=args.dni)
        if not write_output(data, args, summary=f"Infogob search '{args.name}'"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0 if not data.get("blocked") else 2

    if args.cmd == "declaration":
        data = fetch_ficha_by_token(args.token)
        if not write_output(data, args, summary=f"Infogob ficha {args.token[:20]}"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "deep-links":
        data = deep_links(args.query)
        if not write_output(data, args, summary=f"Infogob links '{args.query}'"):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    sys.exit(main())
