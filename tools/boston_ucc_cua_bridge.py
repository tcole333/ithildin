#!/usr/bin/env python3
"""Local form bridge for durable, explicitly transcribed MA UCC index observations.

Run: uv run python tools/boston_ucc_cua_bridge.py --port 8768
Open the printed loopback URL in the in-app browser. Paste the documented JSON
into the form and save. This tool never queries UCC or changes the source queue.
Validated events can be imported by the separate queue tool from ucc-cua/events.jsonl.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import parse_qs, urljoin, urlsplit


DEFAULT_QUEUE = Path(__file__).resolve().parents[1] / (
    "reports/boston-liquor-license-collateral-2026-09-03/full-review/ucc-queue.json"
)
MAX_BODY = 5 * 1024 * 1024
EMPTY_MESSAGE = "No records found; try a new search using different criteria"
COLUMNS = (
    "name", "name_type", "city", "state", "filing_type", "filing_number",
    "original_filing_number", "filing_date",
)
HEADERS = ("Name", "Name Type", "City", "State", "Filing Type", "Filing Number",
           "Original Filing Number", "Filing Date")


class ValidationError(ValueError):
    """An observation cannot safely change index coverage."""


def digest(value):
    return hashlib.sha256(value).hexdigest()


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def load_queue(path):
    data = json.loads(path.read_text())
    holders = data.get("holders")
    if not isinstance(holders, list) or not holders:
        raise ValidationError("Queue must contain a nonempty holders list")
    indexed = {}
    for holder in holders:
        key = holder["holder_id"]
        if key in indexed:
            raise ValidationError("Duplicate holder_id in queue")
        indexed[key] = holder
    return indexed


def validate_url(value, page):
    if not isinstance(value, str):
        raise ValidationError("Source URLs must be strings")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or parsed.netloc != "corp.sec.state.ma.us"
            or parsed.path.lower() != f"/corpweb/uccsearch/{page.lower()}"):
        raise ValidationError(f"Expected an official MA UCC {page} URL")
    return value


def validate_observation(observation, holders):
    if not isinstance(observation, dict):
        raise ValidationError("Each observation must be an object")
    holder_id = observation.get("holder_id")
    holder = holders.get(holder_id) if isinstance(holder_id, str) else None
    if holder is None:
        raise ValidationError("Unknown holder_id")
    scope = observation.get("scope")
    if scope not in ("current", "lapsed"):
        raise ValidationError("scope must be current or lapsed")
    query = observation.get("query")
    if query not in (holder["query_proposal"], holder["query_proposal"]["query"]):
        raise ValidationError("query must exactly match this holder's displayed query")
    query = holder["query_proposal"]
    heading = observation.get("heading")
    if not isinstance(heading, str) or heading.strip() != "UCC Search Results":
        raise ValidationError("Expected the observed UCC Search Results heading")
    source_url = validate_url(observation.get("source_url", observation.get("url")), "UCCSearchResults.aspx")
    retrieved_at = observation.get("retrieved_at", observation.get("captured_at"))
    try:
        captured = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        if captured.tzinfo is None:
            raise ValueError("missing timezone")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValidationError("retrieved_at must be an ISO timestamp with timezone") from exc
    count = observation.get("reported_count")
    if type(count) is not int or count < 0:
        raise ValidationError("reported_count must be a nonnegative integer")
    truncated = observation.get("truncated", count > 500)
    if type(truncated) is not bool:
        raise ValidationError("truncated must be a boolean")
    if "rows" in observation and "occurrences" in observation:
        raise ValidationError("Supply rows or occurrences, not both")
    raw_rows = observation.get("rows", observation.get("occurrences"))
    if not isinstance(raw_rows, list):
        raise ValidationError("rows must be an explicit list, including [] for no results")
    occurrences = []
    headers = observation.get("headers")
    header_seen = headers == list(HEADERS)
    if headers is not None and not header_seen:
        raise ValidationError("Observed table headers do not match the eight UCC columns")
    for row in raw_rows:
        if isinstance(row, list):
            cells, history_url = row, None
        elif isinstance(row, dict) and "cells" in row:
            cells, history_url = row["cells"], row.get("history_url")
        elif isinstance(row, dict) and set(COLUMNS).issubset(row):
            cells = [row[column] for column in COLUMNS]
            history_url = row.get("history_url")
        else:
            raise ValidationError("Every row must provide the eight observed column values")
        if not isinstance(cells, list) or len(cells) != 8:
            raise ValidationError("Every row must contain exactly eight cells")
        texts = []
        for cell in cells:
            value = cell.get("text") if isinstance(cell, dict) else cell
            if not isinstance(value, str):
                raise ValidationError("Every cell must be a string or an object with text")
            texts.append(value.strip())
        if tuple(texts) == HEADERS and not occurrences:
            header_seen = True
            continue
        if not header_seen:
            raise ValidationError("Positive results require the observed exact eight-column header")
        if isinstance(cells[5], dict):
            links = cells[5].get("links", [])
            if not isinstance(links, list):
                raise ValidationError("Cell links must be a list")
            for link in links:
                if isinstance(link, dict) and str(link.get("text", "")).strip() == texts[5]:
                    if not isinstance(link.get("url"), str):
                        raise ValidationError("Observed history link URL must be a string")
                    history_url = urljoin(source_url, link["url"])
                    break
        cells = texts
        if not cells[5].isdigit():
            raise ValidationError("Observed filing number must contain digits")
        normalized = dict(zip(COLUMNS, cells))
        if history_url:
            normalized["history_url"] = validate_url(history_url, "UCCFilingHistory.aspx")
        occurrences.append(normalized)
    returned = len(occurrences)
    if count and not header_seen:
        raise ValidationError("Positive results require the observed exact eight-column header")
    if returned > 500 or (count > 500 and not truncated):
        raise ValidationError("Over 500 records requires a bounded partial capture for review")
    if count < returned or (not truncated and count != returned):
        raise ValidationError("reported_count does not match observed rows; partial pages need truncated=true")
    if truncated and count <= returned:
        raise ValidationError("truncated=true requires reported_count greater than observed rows")
    if "returned_count" in observation and observation["returned_count"] != returned:
        raise ValidationError("returned_count does not match observed rows")
    quote = observation.get("source_quote", observation.get("text"))
    if not isinstance(quote, str):
        raise ValidationError("source_quote must preserve the observed count or empty marker")
    if count == 0:
        if EMPTY_MESSAGE.casefold() not in quote.casefold():
            raise ValidationError("Zero records requires the explicit observed no-records marker")
        if re.search(r"Number of records:\s*[1-9]", quote, re.I):
            raise ValidationError("No-records marker contradicts a positive displayed count")
    else:
        match = re.search(r"Number of records:\s*([\d,]+)", quote, re.I)
        if not match or int(match[1].replace(",", "")) != count:
            raise ValidationError("source_quote record count does not match reported_count")
        if EMPTY_MESSAGE.casefold() in quote.casefold():
            raise ValidationError("Positive count contradicts the no-records marker")
    state = "partial" if truncated else "complete"
    if observation.get("state", state) != state:
        raise ValidationError("state contradicts validated index coverage")
    return {
        "holder_id": holder["holder_id"], "scope": scope, "state": state,
        "query": query, "reported_count": count, "returned_count": returned,
        "truncated": truncated, "retrieved_at": retrieved_at, "source_url": source_url,
        "source_quote": quote, "occurrences": occurrences,
        "capture_method": "transcription_of_in_app_browser_dom_observation",
        "review": {"history_state": "not_started", "attachments_state": "not_started"},
    }


class ObservationStore:
    def __init__(self, queue_path, output_dir):
        self.queue_path = queue_path
        self.output_dir = output_dir.resolve()
        self.raw_dir = self.output_dir / "observations"
        self.events_path = self.output_dir / "events.jsonl"
        self.lock = threading.Lock()
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def events(self):
        if not self.events_path.exists():
            return []
        return [json.loads(line) for line in self.events_path.read_text().splitlines() if line]

    def save(self, raw_text):
        if len(raw_text.encode("utf-8")) > MAX_BODY:
            raise ValidationError("Observation JSON exceeds 5 MiB")
        try:
            parsed = json.loads(raw_text)
        except (ValueError, RecursionError) as exc:
            raise ValidationError("Invalid observation JSON") from exc
        observations = parsed.get("results") if isinstance(parsed, dict) else parsed
        if not isinstance(observations, list) or not 1 <= len(observations) <= 100:
            raise ValidationError("Supply a JSON list or {results: [...]} with 1–100 observations")
        with self.lock:
            holders = load_queue(self.queue_path)
            events = [validate_observation(item, holders) for item in observations]
            raw_bytes = raw_text.encode("utf-8")
            raw_hash = digest(raw_bytes)
            attempt = 1
            while True:
                raw_path = self.raw_dir / f"{raw_hash[:24]}-attempt-{attempt:04d}.json"
                try:
                    raw_file = raw_path.open("xb")
                    break
                except FileExistsError:
                    attempt += 1
            with raw_file:
                raw_file.write(raw_bytes)
                raw_file.flush()
                os.fsync(raw_file.fileno())
            for event in events:
                event.update({"source_file": str(raw_path), "source_file_sha256": raw_hash,
                              "saved_at": datetime.now(timezone.utc).isoformat()})
                event["event_sha256"] = digest(json_bytes(event))
            with self.events_path.open("ab") as event_file:
                event_file.write(b"".join(json_bytes(event) + b"\n" for event in events))
                event_file.flush()
                os.fsync(event_file.fileno())
            return events

    def snapshot(self, scope):
        holders = load_queue(self.queue_path)
        effective = {}
        ordered = sorted(holders.values(), key=lambda h: bool(
            h["query_input_requires_review"] or h.get("name_mode_review_reasons")))
        for holder in ordered:
            for name in ("current", "lapsed"):
                effective[holder["holder_id"], name] = holder["searches"][name]["state"]
        events = self.events()
        for event in events:
            key = event["holder_id"], event["scope"]
            if key in effective and effective[key] != "complete":
                effective[key] = event["state"]
        counts = {name: dict(Counter(value for (_, s), value in effective.items() if s == name))
                  for name in ("current", "lapsed")}
        pending = []
        for holder in ordered:
            for name in (("current", "lapsed") if scope == "both" else (scope,)):
                state = effective[holder["holder_id"], name]
                if state == "complete":
                    continue
                pending.append({"holder_id": holder["holder_id"], "scope": name,
                                "query": holder["query_proposal"]["query"],
                                "query_parameters": holder["query_proposal"], "index_state": state,
                                "business_name": holder["business_name"],
                                "license_numbers": holder["license_numbers"],
                                "query_input_requires_review": holder["query_input_requires_review"],
                                "name_mode_review_reasons": holder.get("name_mode_review_reasons", []),
                                "name_mode_review_required": bool(holder.get("name_mode_review_reasons"))})
        return counts, pending[:20], len(pending), len(events)


SAVE_SCRIPT = """
(() => {
  let saving = false;
  async function save(form) {
    if (saving || !form.reportValidity()) return;
    const status = document.querySelector('[role="status"]');
    const button = form.querySelector('button[type="submit"]');
    const body = new URLSearchParams(new FormData(form));
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 30000);
    saving = true;
    button.disabled = true;
    status.textContent = 'Saving observed results…';
    try {
      const response = await fetch(form.action, {
        method: 'POST', body, credentials: 'same-origin', mode: 'same-origin',
        signal: abort.signal, headers: {'Accept': 'text/html'}
      });
      const text = await response.text();
      const page = new DOMParser().parseFromString(text, 'text/html');
      if (!response.ok) {
        status.textContent = page.querySelector('[role="status"]')?.textContent
          || `Not saved (HTTP ${response.status}): ${page.body.textContent.slice(0, 1000)}`;
        return;
      }
      if (!page.querySelector('#pending-json') || !page.querySelector('#observation-form')) {
        throw new Error('Unexpected save response');
      }
      // Keep this delegated handler; response scripts must not execute a second time.
      page.querySelectorAll('script').forEach(script => script.remove());
      document.body.replaceChildren(...Array.from(page.body.childNodes));
    } catch (error) {
      status.textContent = 'Save response unavailable; input retained. Check saved events before retrying. '
        + error.message;
    } finally {
      clearTimeout(timer);
      saving = false;
      button.disabled = false;
    }
  }
  // Handle the click directly: embedded browsers may suppress native form navigation.
  document.addEventListener('click', event => {
    const button = event.target.closest?.('#observation-form button[type="submit"]');
    if (!button) return;
    event.preventDefault();
    save(button.form);
  }, true);
  document.addEventListener('submit', event => {
    if (event.target.id !== 'observation-form') return;
    event.preventDefault();
    save(event.target);
  }, true);
})();
"""


def render_page(store, token, scope, message="", raw_text="", script_nonce=""):
    counts, pending, remaining, attempts = store.snapshot(scope)
    template = {
        "results": [{"holder_id": pending[0]["holder_id"] if pending else "QUEUE_COMPLETE",
                     "scope": pending[0]["scope"] if pending else "current",
                     "query": pending[0]["query"] if pending else {},
                     "heading": "UCC Search Results", "captured_at": "ISO timestamp with timezone",
                     "url": "https://corp.sec.state.ma.us/CorpWeb/UCCSearch/UCCSearchResults.aspx?sysvalue=OBSERVED",
                     "reported_count": 0, "truncated": False,
                     "text": EMPTY_MESSAGE, "rows": []}]
    }
    def escaped(value):
        return html.escape(value, quote=True)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<title>Boston UCC observation queue</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:2rem auto;padding:0 1rem}}
pre,textarea{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:1rem}}
textarea{{box-sizing:border-box;width:100%;min-height:260px}}button{{padding:.7rem;font:inherit}}
.message{{font-weight:bold}}small{{display:block}}</style>
<h1>Boston UCC observation queue</h1>
<p>Local evidence writer. Search coverage is index-only. Filing histories, documents,
collateral and ownership still require review. Pending does not mean no records.</p>
<p class="message" role="status">{escaped(message)}</p>
<nav><a href="/?scope=current">Current queue</a> · <a href="/?scope=lapsed">Lapsed queue</a> ·
<a href="/?scope=both">Both scopes</a></nav>
<h2>Coverage counts</h2><pre id="counts">{escaped(json.dumps(counts, indent=2))}</pre>
<p>{remaining} unfinished {escaped(scope)} requests; {attempts} saved bridge observation attempts.</p>
<h2>Next requests (first 20)</h2>
<pre id="pending-json">{escaped(json.dumps(pending, ensure_ascii=False, indent=2))}</pre>
<h2>Import observed results</h2>
<p>Copy the exact displayed query string; use the displayed search parameters. Preserve all eight
columns, the header row, cell text and links, and repeated row occurrences.
For positive results, quote “Number of records: N”. For zero results, quote the complete explicit
no-records marker. Partial pages require truncated=true and remain unfinished.</p>
<p>Rows may be arrays of eight cells (strings or objects with text and links), or objects with cells
and an optional history_url. Include the exact table header as the first row for positive results.
Requests needing organization-versus-person name review sort last. Zero organization-mode results
do not exclude debt indexed under individuals or partnerships.
Column order: {escaped(', '.join(COLUMNS))}.</p>
<details><summary>JSON format example for next request (replace with actual observations)</summary>
<pre>{escaped(json.dumps(template, indent=2))}</pre></details>
<form id="observation-form" method="post" action="/save?scope={escaped(scope)}">
<input type="hidden" name="csrf" value="{escaped(token)}">
<label for="observations">Observed results JSON</label>
<textarea id="observations" name="observations" required maxlength="{MAX_BODY}">{escaped(raw_text)}</textarea>
<small>Maximum request size 5 MiB, up to 100 observations per save. All observations must validate.</small>
<button type="submit">Save observations</button></form>
<script nonce="{escaped(script_nonce)}">{SAVE_SCRIPT}</script></html>"""


class BridgeServer(HTTPServer):
    def __init__(self, port, store):
        self.store = store
        self.csrf_token = secrets.token_urlsafe(32)
        self.script_nonce = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), BridgeHandler)

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(10)
        return sock, address


class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Avoid logging submitted evidence or URLs; startup and UI report state.

    def local_request(self, require_origin=False):
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host")
        origin = self.headers.get("Origin")
        if len(self.headers.get_all("Host", [])) != 1 or host not in hosts:
            return False
        if len(self.headers.get_all("Origin", [])) > 1:
            return False
        if origin is not None and origin != f"http://{host}":
            return False
        if require_origin and origin != f"http://{host}":
            return False
        return self.headers.get("Sec-Fetch-Site", "same-origin") not in ("cross-site", "same-site")

    def respond(self, code, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", (
            f"default-src 'none'; script-src 'nonce-{self.server.script_nonce}'; "
            "connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'none'"
        ))
        self.end_headers()
        self.wfile.write(data)

    def scope(self):
        params = parse_qs(urlsplit(self.path).query)
        value = params.get("scope", ["current"])
        if len(value) != 1 or value[0] not in ("current", "lapsed", "both"):
            raise ValidationError("Unknown queue scope")
        return value[0]

    def do_GET(self):
        if not self.local_request():
            self.respond(403, "Loopback host/origin required", "text/plain")
            return
        if urlsplit(self.path).path != "/":
            self.respond(404, "Not found", "text/plain")
            return
        try:
            body = render_page(self.server.store, self.server.csrf_token, self.scope(),
                               script_nonce=self.server.script_nonce)
        except (ValueError, KeyError) as exc:
            self.respond(400, html.escape(str(exc)))
            return
        self.respond(200, body)

    def do_POST(self):
        if not self.local_request(require_origin=True):
            self.respond(403, "Same-origin loopback form required", "text/plain")
            return
        if urlsplit(self.path).path != "/save":
            self.respond(404, "Not found", "text/plain")
            return
        try:
            if self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length", [])) != 1:
                raise ValidationError("One Content-Length header required")
            length = int(self.headers["Content-Length"])
            if not 0 < length <= MAX_BODY:
                self.respond(413, "Request exceeds 5 MiB or is empty", "text/plain")
                return
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                raise ValidationError("Use the ordinary observation form")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValidationError("Incomplete request body")
            fields = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=2)
            if set(fields) != {"csrf", "observations"} or any(len(v) != 1 for v in fields.values()):
                raise ValidationError("Expected one CSRF token and observation field")
            if not secrets.compare_digest(fields["csrf"][0], self.server.csrf_token):
                self.respond(403, "Invalid form token; reload this page", "text/plain")
                return
            scope = self.scope()
            raw_text = fields["observations"][0]
            try:
                events = self.server.store.save(raw_text)
            except ValidationError as exc:
                self.respond(400, render_page(self.server.store, self.server.csrf_token, scope,
                                             f"Not saved: {exc}", raw_text,
                                             script_nonce=self.server.script_nonce))
                return
            message = f"Saved {len(events)} index observations. Raw files and append-only events are durable."
            self.respond(200, render_page(self.server.store, self.server.csrf_token, scope, message,
                                         script_nonce=self.server.script_nonce))
        except (ValueError, UnicodeError, TimeoutError) as exc:
            self.respond(400, html.escape(f"Not saved: {exc}"))
        except OSError:
            self.respond(500, "Local persistence failed; inspect evidence directory before retrying", "text/plain")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--output-dir", type=Path, help="Defaults to queue parent / ucc-cua")
    parser.add_argument("--port", type=int, default=8768)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1–65535")
    load_queue(args.queue)
    store = ObservationStore(args.queue, args.output_dir or args.queue.parent / "ucc-cua")
    with (store.output_dir / ".bridge.lock").open("a") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Another bridge already owns this observation directory")
        with BridgeServer(args.port, store) as server:
            print(f"UCC observation bridge: http://127.0.0.1:{server.server_port}/", flush=True)
            print(f"Evidence directory: {store.output_dir}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
