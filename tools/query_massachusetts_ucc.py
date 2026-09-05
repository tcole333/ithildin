#!/usr/bin/env python3
"""Read Massachusetts public UCC records through an isolated Chrome session.

The current database and lapsed archive are separate search scopes. A search
row is a party/filing occurrence, not necessarily a distinct financing statement.
Use filing-number lookup to retrieve the complete source-returned filing history.

Requires Node.js, playwright (or playwright-core), and Google Chrome.

The Secretary's terms prohibit portal scraping. Full-roster collection is
paused pending a supported bulk-data route; see 950 CMR 140.11 and the
Massachusetts UCC section of docs/modules/registries.md. A reachable search
form does not establish permission for a bulk run.

Examples:
    uv run python tools/query_massachusetts_ucc.py runtime-check
    uv run python tools/query_massachusetts_ucc.py search-org "HARVARD" --limit 25 --output results.json
    uv run python tools/query_massachusetts_ucc.py filing 202178754190 --output filing.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
    from tools.search_log_util import canonical_search_key
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output
    from search_log_util import canonical_search_key


SOURCE_NAME = "massachusetts_ucc"
SEARCH_URL = "https://corp.sec.state.ma.us/corpweb/UCCSearch/UCCSearch.aspx"
HELPER_PATH = Path(__file__).with_name("_ma_ucc_browser_helper.js")
MAX_RESULTS = 500
SEARCH_HEADERS = (
    "Name", "Name Type", "City", "State", "Filing Type", "Filing Number",
    "Original Filing Number", "Filing Date",
)
SEARCH_FIELDS = (
    "name", "name_type", "city", "state", "filing_type", "filing_number",
    "original_filing_number", "filing_date",
)
PARTY_SECTIONS = {
    "Debtor(s)": "debtors", "Secured Parties": "secured_parties",
    "Assignee": "assignees", "Assignees": "assignees",
}
EMPTY_MESSAGE = "No records found; try a new search using different criteria"


class PortalError(RuntimeError):
    """Unavailable or changed source; never equivalent to an empty search."""


def _text(element) -> str:
    return " ".join(element.get_text(" ", strip=True).split())


def _lines(element) -> list[str]:
    # A separator on get_text would also split inline font tags in Corp Type.
    copy = BeautifulSoup(str(element), "html.parser")
    for br in copy.find_all("br"):
        br.replace_with("\n")
    return [line.strip() for line in copy.get_text().splitlines() if line.strip()]


def _rows(table):
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def _source_url(href: str, base_url: str) -> str:
    url = urljoin(base_url, href)
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.netloc != "corp.sec.state.ma.us"
            or not parsed.path.lower().startswith("/corpweb/uccsearch/")):
        raise PortalError("Unexpected UCC source link; the portal layout may have changed.")
    return url


def _soup(html: str, url: str) -> BeautifulSoup:
    _source_url(url, SEARCH_URL)
    soup = BeautifulSoup(html, "html.parser")
    if not soup.find("h2"):
        raise PortalError("UCC page lacks its expected heading; browser challenge or changed source.")
    return soup


def _date_iso(value: str) -> str | None:
    try:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _datetime_iso(value: str) -> str | None:
    try:
        # The source gives a local clock time without an offset. Do not invent one.
        return datetime.strptime(value, "%m/%d/%Y %I:%M:%S %p").isoformat()
    except ValueError:
        return None


def _is_empty(soup: BeautifulSoup) -> bool:
    message = soup.find(id="MainContent_lblMessage")
    return bool(message and _text(message).lstrip("* ") == EMPTY_MESSAGE)


def parse_search_page(html: str, url: str) -> dict:
    """Parse one verified result page, retaining repeated party occurrences."""
    soup = _soup(html, url)
    heading = _text(soup.find("h2"))
    if not re.search(r"UCC.*Search Results", heading, re.I):
        raise PortalError("Expected UCC search results; received a form, challenge, or error page.")
    count_match = re.search(r"Number of records:\s*([\d,]+)", soup.get_text(" "))
    table = soup.find("table", id="MainContent_grdSearchResults")
    if _is_empty(soup) and table is None and count_match is None:
        return {"reported_count": 0, "results": [], "search_criteria": {}}
    if not count_match:
        raise PortalError("UCC result count is missing; cannot certify an empty search.")
    reported_count = int(count_match[1].replace(",", ""))
    results = []
    if table:
        rows = _rows(table)
        if not rows:
            raise PortalError("UCC results table has no header row.")
        headers = tuple(_text(cell) for cell in rows[0].find_all(["td", "th"], recursive=False))
        if headers != SEARCH_HEADERS:
            raise PortalError("UCC search columns changed; refusing to mislabel records.")
        for row in rows[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) == 1 and cells[0].find("table"):
                continue  # ASP.NET grid pager, not a filing occurrence.
            if len(cells) != len(SEARCH_FIELDS):
                raise PortalError("Unexpected UCC search row shape.")
            raw_values = [cell.get_text(" ", strip=False) for cell in cells]
            item = dict(zip(SEARCH_FIELDS, (_text(cell) for cell in cells), strict=True))
            if not re.fullmatch(r"\d+", item["filing_number"]):
                raise PortalError("UCC search row has no filing number.")
            link = cells[5].find("a", href=True)
            if not link:
                raise PortalError("UCC search row has no source history link.")
            item.update(
                raw_cells=raw_values,
                history_url=_source_url(link["href"], url),
                filing_date_iso=_date_iso(item["filing_date"]),
                citation=f"MA-UCC:{item['filing_number']}",
            )
            results.append(item)
    if (reported_count and not results) or len(results) > reported_count:
        raise PortalError("UCC result count and parsed rows disagree.")
    criteria = {}
    for criteria_table in soup.select("table[id^='MainContent_tblSearch']"):
        for row in _rows(criteria_table):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) == 2:
                criteria[_text(cells[0]).rstrip(":")] = _text(cells[1])
    return {"reported_count": reported_count, "results": results, "search_criteria": criteria}


def _party(cell) -> dict:
    lines = _lines(cell)
    corp_type = None
    address_lines = []
    for line in lines[1:]:
        if line.startswith("Corp Type:"):
            corp_type = line.partition(":")[2].strip()
        else:
            address_lines.append(line)
    return {
        "name": lines[0], "address_lines": address_lines,
        "corporation_type": corp_type, "raw_text": "\n".join(lines),
    }


def parse_filing_page(html: str, url: str, requested_number: str) -> list[dict]:
    """Keep parties/collateral attached to their own initial or amending record."""
    soup = _soup(html, url)
    table = soup.find("table", id="MainContent_tblFilingHistory")
    if table is None and _is_empty(soup):
        return []
    if not table or _text(soup.find("h2")) != "Filing History":
        raise PortalError("Expected filing history; lookup did not return a filing record.")
    filings = []
    current = None
    section = None
    for row in _rows(table):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        text = _text(cells[0])
        if len(cells) == 1 and re.match(r"^UCC-\d\b", text):
            current = {
                "filing_type": text, "filing_number": None, "filing_date": None,
                "action": None, "debtors": [], "secured_parties": [],
                "assignees": [], "collateral": [], "documents": [],
            }
            filings.append(current)
            section = None
            continue
        if current is None:
            raise PortalError("Filing history has data before its filing header.")
        if text.startswith("UCC Filing Number:"):
            if len(cells) != 4:
                raise PortalError("Filing metadata columns changed.")
            values = _lines(cells[1])
            if len(values) != 2 or not re.fullmatch(r"\d+", values[0]):
                raise PortalError("Filing number/date metadata is malformed.")
            current["filing_number"], current["filing_date"] = values
            current["filing_datetime_iso"] = _datetime_iso(values[1])
            current["citation"] = f"MA-UCC:{values[0]}"
            current["documents_text"] = _text(cells[3])
            for link in cells[3].find_all("a", href=True):
                following = []
                for sibling in link.next_siblings:
                    if getattr(sibling, "name", None) in {"a", "br"}:
                        break
                    following.append(str(sibling))
                pages = re.search(r"(\d+)\s*pgs?", "".join(following))
                current["documents"].append({
                    "filename": _text(link),
                    "viewer_url": _source_url(link["href"], url),
                    "page_count": int(pages[1]) if pages else None,
                })
            section = None
        elif text == "Action:":
            if len(cells) < 2:
                raise PortalError("Filing action value is missing.")
            current["action"] = _text(cells[1])
            section = None
        elif len(cells) == 1 and text in PARTY_SECTIONS:
            section = PARTY_SECTIONS[text]
        elif len(cells) == 1 and text == "Collateral Information":
            section = "collateral"
        elif row.find("input", type="checkbox"):
            section = None  # Paid certified-copy controls are never selected.
        elif section in PARTY_SECTIONS.values():
            for cell in cells:
                if _text(cell):
                    current[section].append(_party(cell))
        elif section == "collateral":
            for textarea in row.find_all("textarea"):
                current["collateral"].append(textarea.get_text())
            if not row.find("textarea") and _text(row):
                raise PortalError("Collateral field changed from its verified textarea layout.")
        elif _text(row):
            raise PortalError(f"Unrecognized filing-history section: {_text(row)[:100]}")
    if not filings or any(not item["filing_number"] for item in filings):
        raise PortalError("Filing history is empty or incomplete.")
    if requested_number not in {item["filing_number"] for item in filings}:
        raise PortalError("Returned filing history does not contain the requested filing number.")
    return filings


def run_helper(payload: dict) -> dict:
    node = shutil.which("node")
    if not node:
        raise PortalError("Node.js was not found. Install Node.js and npm install playwright.")
    if not HELPER_PATH.is_file():
        raise PortalError(f"Browser helper is missing: {HELPER_PATH}")
    try:
        completed = subprocess.run(
            [node, str(HELPER_PATH)], input=json.dumps(payload),
            capture_output=True, text=True,
            timeout=30 if payload["command"] == "runtime-check" else 210,
        )
    except subprocess.TimeoutExpired as exc:
        raise PortalError("Massachusetts UCC browser operation exceeded its time limit.") from exc
    except OSError as exc:
        raise PortalError(f"Cannot launch Massachusetts UCC browser helper: {exc}") from exc
    if completed.returncode:
        raise PortalError(completed.stderr.strip() or "Massachusetts UCC browser helper failed.")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PortalError("Browser helper returned invalid JSON.") from exc
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise PortalError("Browser helper did not confirm a successful operation.")
    return data


def runtime_check() -> dict:
    """Check local dependencies only; this does not establish live availability."""
    return run_helper({"command": "runtime-check"})


def _payload(args: argparse.Namespace) -> dict:
    payload = {"command": args.command}
    if args.command in {"runtime-check", "probe"}:
        return payload
    payload.update(query=args.query.strip(), lapsed=args.lapsed)
    if not payload["query"]:
        raise ValueError("The search value must not be blank.")
    if args.command == "filing":
        if not re.fullmatch(r"\d{12}", payload["query"]):
            raise ValueError("Filing number must contain exactly 12 digits.")
        return payload
    maximum_length = 175 if args.command == "search-org" else 35
    if len(payload["query"]) > maximum_length:
        raise ValueError(f"Search name exceeds the source's {maximum_length}-character limit.")
    if args.city and len(args.city) > 35:
        raise ValueError("City exceeds the source's 35-character limit.")
    if args.command == "search-individual":
        if any(len(getattr(args, field)) > 25 for field in ("first", "middle", "suffix")):
            raise ValueError("First name, middle name, and suffix each have a 25-character limit.")
    if not 1 <= args.limit <= MAX_RESULTS:
        raise ValueError(f"--limit must be between 1 and {MAX_RESULTS}.")
    if args.search_type != "begins" and args.role != "debtor":
        raise ValueError("Secured-party and assignee searches require --search-type begins.")
    if args.command == "search-individual" and args.search_type == "exact":
        raise ValueError("Exact Match is available only for organization searches.")
    if args.state and not re.fullmatch(r"[A-Z]{2}", args.state):
        raise ValueError("--state must be a two-letter uppercase state code.")
    since = None
    if args.since:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
                raise ValueError("Expected ISO date")
            since = date.fromisoformat(args.since).strftime("%m/%d/%Y")
        except ValueError as exc:
            raise ValueError("--since must be a real date in YYYY-MM-DD format.") from exc
    payload.update(
        search_type=args.search_type, role=args.role, limit=args.limit,
        city=args.city, state=args.state, since=since,
    )
    if args.command == "search-individual":
        payload.update(first=args.first, middle=args.middle, suffix=args.suffix)
    return payload


def execute(payload: dict) -> dict:
    return parse_response(payload, run_helper(payload))


def parse_response(payload: dict, raw: dict, *, log: bool = True) -> dict:
    """Shared parser for single calls, durable session responses and cache recovery."""
    if raw.get("ok") is not True:
        raise PortalError(raw.get("error") or "Browser did not confirm a successful response.")
    if "submitted" in raw and payload["command"] not in {"runtime-check", "probe"}:
        expected = {"limit": 25, "search_type": "begins", "role": "debtor", **payload}
        if raw["submitted"] != expected:
            raise PortalError("Browser submitted parameters differ from the requested query.")
    if payload["command"] == "runtime-check":
        return {"source": SOURCE_NAME, "live_checked": False, **raw}
    pages = raw.get("pages")
    if (not isinstance(pages, list) or not pages
            or any(not isinstance(page, dict) or not isinstance(page.get("html"), str)
                   or not isinstance(page.get("url"), str) for page in pages)):
        raise PortalError("Browser returned no usable source pages.")
    result = {
        "source": SOURCE_NAME, "source_url": SEARCH_URL,
        "retrieved_at": raw.get("captured_at") or datetime.now(timezone.utc).isoformat(),
        "scope": "lapsed" if payload.get("lapsed") else "current",
        "query": payload,
        "provenance": [
            {"url": page["url"], "sha256": hashlib.sha256(page["html"].encode()).hexdigest()}
            for page in pages
        ],
    }
    command = payload["command"]
    if command == "probe":
        soup = _soup(pages[0]["html"], pages[0]["url"])
        required = ["rdoSearchI", "rdoSearchO", "rdoSearchF", "txtFilingNumber", "btnSearch"]
        if not all(soup.find(id=f"MainContent_{name}") for name in required):
            raise PortalError("Public UCC search form is unavailable or has changed.")
        return {**result, "ok": True, "live_checked": True, "search_form_available": True}
    if command == "filing":
        filings = parse_filing_page(pages[0]["html"], pages[0]["url"], payload["query"])
        result.update(filings=filings, found=bool(filings), returned=len(filings), history_url=pages[0]["url"])
    else:
        parsed_pages = [parse_search_page(page["html"], page["url"]) for page in pages]
        total = parsed_pages[0]["reported_count"]
        criteria = parsed_pages[0]["search_criteria"]
        if payload["command"] == "search-org" and "Organization Name" in criteria:
            def normalize(value):
                return " ".join(value.split()).casefold()
            if normalize(criteria["Organization Name"]) != normalize(payload["query"]):
                raise PortalError("Source result organization differs from the requested query.")
        if any(page["reported_count"] != total or page["search_criteria"] != criteria
               for page in parsed_pages[1:]):
            raise PortalError("UCC search count or criteria changed during pagination; retry the search.")
        rows = [row for page in parsed_pages for row in page["results"]]
        # Detect replayed pages without deduplicating legitimate repeated party rows.
        signatures = [json.dumps(page["results"], sort_keys=True) for page in parsed_pages]
        if len(set(signatures)) != len(signatures):
            raise PortalError("UCC pagination repeated a page; refusing incomplete results.")
        if len(rows) != min(len(pages) * 25, total):
            raise PortalError("UCC pagination returned an unexpected number of rows.")
        if len(rows) < min(payload["limit"], total):
            raise PortalError("UCC pagination stopped before the requested result limit.")
        rows = rows[:payload["limit"]]
        for index, row in enumerate(rows, start=1):
            row["occurrence"] = index
        result.update(
            reported_count=total, returned=len(rows), truncated=len(rows) < total,
            pages_fetched=len(pages), result_grain="party/filing search occurrence",
            search_criteria=criteria, results=rows,
        )
    if not log:
        return result
    try:
        filters = {key: value for key, value in payload.items() if key not in {"command", "query"}}
        log_search(canonical_search_key(command, payload["query"], **filters), SOURCE_NAME, result["returned"])
    except Exception as exc:
        print(f"WARNING: Could not log Massachusetts UCC search: {exc}", file=sys.stderr)
    return result


def save_transport(path: Path, payload: dict, raw: dict) -> None:
    """Fsync the raw per-result checkpoint before parsing or scheduling more work."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"payload": payload, "raw": raw}, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def recover_transport(path: Path, payload: dict) -> dict:
    saved = json.loads(path.read_text())
    if saved.get("payload") != payload:
        raise PortalError("Raw checkpoint query differs from the queued request.")
    result = parse_response(payload, saved["raw"])
    result["transport_capture"] = {
        "source_file": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "format": "JSON containing complete source HTML pages and observed submission parameters",
    }
    return result


class BrowserSession:
    """Bounded request/response JSONL transport through one owned visible Chrome.

    Each call writes its raw checkpoint before parsing. The caller checkpoints
    its queue before issuing the next call. EOF/signals close only this browser.
    """

    def __init__(self, max_requests: int = 20, *, command=None, timeout=210):
        if type(max_requests) is not int or not 1 <= max_requests <= 50:
            raise ValueError("Browser session size must be 1–50")
        node = shutil.which("node")
        if command is None and not node:
            raise PortalError("Node.js was not found.")
        self.command = command or [node, str(HELPER_PATH), "--session", str(max_requests)]
        self.max_requests = max_requests
        self.timeout = timeout
        self.requests = 0
        self.process = None
        self.stderr = None
        self.buffer = b""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
            except BrokenPipeError:
                pass
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.process.kill()  # Only the owned helper; pipe shutdown releases Chrome.
                    self.process.wait(timeout=5)
            if self.process.stdout:
                self.process.stdout.close()
            self.process = None
        if self.stderr:
            self.stderr.close()
            self.stderr = None

    def _diagnostic(self):
        self.stderr.seek(0, os.SEEK_END)
        self.stderr.seek(max(0, self.stderr.tell() - 8192))
        return self.stderr.read().decode("utf-8", errors="replace").strip()

    def _response(self):
        deadline = time.monotonic() + self.timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PortalError("Persistent UCC request exceeded its per-request deadline.")
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            if not ready:
                raise PortalError("Persistent UCC request exceeded its per-request deadline.")
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise PortalError(self._diagnostic() or "Persistent UCC helper ended before a complete response.")
            self.buffer += chunk
            if len(self.buffer) > 64 * 1024 * 1024:
                raise PortalError("Persistent UCC response exceeded 64 MiB.")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            return json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise PortalError("Persistent UCC helper returned invalid JSONL.") from exc

    def execute(self, payload: dict, raw_path: Path) -> dict:
        if self.requests >= self.max_requests:
            raise PortalError("Bounded browser session request limit reached.")
        envelope = {"request_id": str(self.requests + 1), "request": payload}
        request = (json.dumps(envelope) + "\n").encode()
        if len(request) > 65536:
            raise PortalError("Persistent UCC request exceeds 64 KiB.")
        try:
            if self.process is None:
                self.stderr = tempfile.TemporaryFile()
                self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE, stderr=self.stderr)
            self.requests += 1
            self.process.stdin.write(request)
            self.process.stdin.flush()
            raw = self._response()
            if not isinstance(raw, dict) or raw.get("request_id") != envelope["request_id"]:
                raise PortalError("Persistent UCC response request ID mismatch.")
            save_transport(raw_path, payload, raw)
            return recover_transport(raw_path, payload)
        except (OSError, ValueError) as exc:
            self.close()
            raise PortalError(f"Persistent UCC transport failed: {exc}") from exc
        except BaseException:
            self.close()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("runtime-check", "probe", "search-org", "search-individual", "filing"):
        child = sub.add_parser(command)
        add_output_args(child)
        if command in {"runtime-check", "probe"}:
            continue
        child.add_argument("query", help="Organization, individual LAST name, or filing number")
        child.add_argument("--lapsed", action="store_true", help="Search the separate lapsed archive")
        if command == "filing":
            continue
        child.add_argument("--search-type", choices=("begins", "article9", "exact"), default="begins")
        child.add_argument("--role", choices=("debtor", "secured", "assignee"), default="debtor")
        child.add_argument("--city")
        child.add_argument("--state")
        child.add_argument("--since", metavar="YYYY-MM-DD")
        child.add_argument("--limit", type=int, default=25, help="Maximum occurrences, 1–500 (default 25)")
        if command == "search-individual":
            child.add_argument("--first", default="")
            child.add_argument("--middle", default="")
            child.add_argument("--suffix", default="")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _payload(args)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        result = execute(payload)
    except PortalError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if args.output:
            write_output(
                {"source": SOURCE_NAME, "status": "error", "source_available": False, "error": str(exc)},
                args, summary="Massachusetts UCC unavailable",
            )
        return 1
    if not write_output(result, args, summary=f"Massachusetts UCC {args.command}"):
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
