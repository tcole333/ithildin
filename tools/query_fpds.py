#!/usr/bin/env python3
"""
FPDS-NG ATOM feed wrapper for federal contract-action research.

The public ATOM feed exposes FPDS workflow fields that are absent from many
other procurement APIs, including the users who created, modified, and
approved an action.

The feed carries two payload roots. A <award> holds a dated contract action;
an <IDV> holds the indefinite-delivery vehicle those actions are placed
against. Both are parsed into the same record shape, tagged by ``record_type``,
so that a vehicle's base award is never mistaken for an absent record. IDVs
have no referenced IDV and no completion dates, so those fields stay null.

Fetches stop at --max-pages. When the feed still offers another page at that
point the results are incomplete: the tool warns on stderr, marks
``truncated`` in --with-metadata output, and exits 2.

API: https://www.fpds.gov/ezsearch/FEEDS/ATOM
Auth: None.

Usage:
    uv run python tools/query_fpds.py piid 70CDCR26FR0000014
    uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64'
    uv run python tools/query_fpds.py piid 70CDCR26FR0000014 \
        --from-file saved-feed.xml --output actions.json
    uv run python tools/query_fpds.py search 'VENDOR_UEI:D13LLJJZYH64' \
        --with-metadata --output actions.json
"""

import argparse
import os
import socket
import ssl
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

if (
    os.environ.get("OSINT_INSECURE_SSL") == "true"
    or os.environ.get("PYTHONHTTPSVERIFY") == "0"
):
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE

try:
    from tools.output_util import add_output_args, write_output
except ImportError:
    from output_util import add_output_args, write_output


BASE_URL = "https://www.fpds.gov/ezsearch/FEEDS/ATOM"
ATOM_NS = "http://www.w3.org/2005/Atom"
FPDS_NS = "https://www.fpds.gov/FPDS"
NS = {"atom": ATOM_NS, "fpds": FPDS_NS}
REQUEST_TIMEOUT = 60
MAX_ATTEMPTS = 3
EXIT_TRUNCATED = 2

# The payload root an entry uses, paired with the identifier wrapper that root
# nests its PIID under. Awards use awardID/awardContractID; vehicles use
# contractID/IDVID. Order matters only in that the first match wins.
RECORD_ROOTS = (
    ("award", "awardID", "awardContractID"),
    ("IDV", "contractID", "IDVID"),
)


class FPDSError(RuntimeError):
    """A clear, user-facing FPDS request or parsing failure."""


class FetchResult(NamedTuple):
    """Parsed actions plus the paging state that produced them."""

    actions: list
    pages_fetched: int
    truncated: bool
    next_url: str | None


def _local_name(tag):
    """Return an XML tag's local name regardless of its namespace prefix."""
    return tag.rsplit("}", 1)[-1]


def _first_descendant(element, local_name):
    """Find the first descendant by local name, tolerating FPDS prefix changes."""
    if element is None:
        return None
    for child in element.iter():
        if _local_name(child.tag) == local_name:
            return child
    return None


def _direct_child(element, local_name):
    """Find a direct child by local name."""
    if element is None:
        return None
    for child in element:
        if _local_name(child.tag) == local_name:
            return child
    return None


def _clean_text(element):
    if element is None or element.text is None:
        return None
    text = " ".join(element.text.split())
    return text or None


def _descendant_text(element, local_name):
    return _clean_text(_first_descendant(element, local_name))


def _child_text(element, local_name):
    return _clean_text(_direct_child(element, local_name))


def _as_number(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _description(element):
    if element is None:
        return None
    return element.attrib.get("description")


def _find_payload(entry):
    """Return ``(payload, record_type, contract_id)`` for one Atom entry.

    Returns ``(None, None, None)`` for an entry whose root is neither an award
    nor an IDV, which keeps an unrecognized root visible as a null
    ``record_type`` rather than silently emitting an all-null record.
    """
    for record_type, id_wrapper, id_element in RECORD_ROOTS:
        payload = _first_descendant(entry, record_type)
        if payload is None:
            continue
        wrapper = _first_descendant(payload, id_wrapper)
        return payload, record_type, _first_descendant(wrapper, id_element)
    return None, None, None


def _parse_entry(entry):
    """Convert one Atom entry into a stable, audit-friendly record."""
    payload, record_type, contract_id = _find_payload(entry)
    referenced_idv = _first_descendant(payload, "referencedIDVID")
    dates = _first_descendant(payload, "relevantContractDates")
    dollar_values = _first_descendant(payload, "dollarValues")
    total_values = _first_descendant(payload, "totalDollarValues")
    vendor = _first_descendant(payload, "vendor")
    uei_info = _first_descendant(vendor, "vendorUEIInformation")
    contract_data = _first_descendant(payload, "contractData")
    product_info = _first_descendant(payload, "productOrServiceInformation")
    transaction_info = _first_descendant(payload, "transactionInformation")

    agency = _direct_child(contract_id, "agencyID")
    action_type = _first_descendant(contract_data, "contractActionType")
    psc = _first_descendant(product_info, "productOrServiceCode")
    naics = _first_descendant(product_info, "principalNAICSCode")

    return {
        "record_type": record_type,
        "title": _child_text(entry, "title"),
        "feed_modified": _child_text(entry, "modified"),
        "piid": _child_text(contract_id, "PIID"),
        "modification_number": _child_text(contract_id, "modNumber"),
        "transaction_number": _child_text(contract_id, "transactionNumber"),
        "agency_id": _clean_text(agency),
        "agency_name": agency.attrib.get("name") if agency is not None else None,
        "referenced_idv_piid": _child_text(referenced_idv, "PIID"),
        "signed_date": _descendant_text(dates, "signedDate"),
        "effective_date": _descendant_text(dates, "effectiveDate"),
        "current_completion_date": _descendant_text(
            dates, "currentCompletionDate"
        ),
        "ultimate_completion_date": _descendant_text(
            dates, "ultimateCompletionDate"
        ),
        "action_obligation": _as_number(
            _descendant_text(dollar_values, "obligatedAmount")
        ),
        "base_and_exercised_options_value": _as_number(
            _descendant_text(dollar_values, "baseAndExercisedOptionsValue")
        ),
        "base_and_all_options_value": _as_number(
            _descendant_text(dollar_values, "baseAndAllOptionsValue")
        ),
        "total_obligation": _as_number(
            _descendant_text(total_values, "totalObligatedAmount")
        ),
        "total_base_and_exercised_options_value": _as_number(
            _descendant_text(
                total_values, "totalBaseAndExercisedOptionsValue"
            )
        ),
        "total_base_and_all_options_value": _as_number(
            _descendant_text(total_values, "totalBaseAndAllOptionsValue")
        ),
        "vendor_name": _descendant_text(vendor, "vendorName"),
        "uei": _descendant_text(uei_info, "UEI"),
        "contract_action_type": _clean_text(action_type),
        "contract_action_type_description": _description(action_type),
        "product_or_service_code": _clean_text(psc),
        "product_or_service_description": _description(psc),
        "naics_code": _clean_text(naics),
        "naics_description": _description(naics),
        "description": _descendant_text(
            contract_data, "descriptionOfContractRequirement"
        ),
        "createdBy": _descendant_text(transaction_info, "createdBy"),
        "createdDate": _descendant_text(transaction_info, "createdDate"),
        "lastModifiedBy": _descendant_text(
            transaction_info, "lastModifiedBy"
        ),
        "lastModifiedDate": _descendant_text(
            transaction_info, "lastModifiedDate"
        ),
        "approvedBy": _descendant_text(transaction_info, "approvedBy"),
        "approvedDate": _descendant_text(transaction_info, "approvedDate"),
    }


def parse_atom(xml_data):
    """Parse an FPDS ATOM document into records and its optional next link."""
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        raise FPDSError(f"FPDS returned invalid ATOM XML: {exc}") from exc

    if _local_name(root.tag) != "feed":
        raise FPDSError(
            f"Expected an ATOM feed, received XML root <{_local_name(root.tag)}>"
        )

    # Use the explicit Atom namespace first. The local-name fallback handles
    # saved feeds whose serializer changed the Atom prefix/default namespace.
    entry_elements = root.findall("atom:entry", NS)
    if not entry_elements:
        entry_elements = [
            child for child in root if _local_name(child.tag) == "entry"
        ]

    next_link = root.find("atom:link[@rel='next']", NS)
    if next_link is None:
        next_link = next(
            (
                child
                for child in root
                if _local_name(child.tag) == "link"
                and child.attrib.get("rel") == "next"
            ),
            None,
        )

    next_url = next_link.attrib.get("href") if next_link is not None else None
    return [_parse_entry(entry) for entry in entry_elements], next_url


def _fetch_atom_page(url):
    """Fetch one ATOM page, retrying server errors and timeouts."""
    request = Request(
        url,
        headers={
            "Accept": "application/atom+xml, application/xml, text/xml",
            "User-Agent": "OSINT-Research/1.0",
        },
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(
                request, timeout=REQUEST_TIMEOUT, context=SSL_CONTEXT
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
        except HTTPError as exc:
            if 500 <= exc.code < 600 and attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            suffix = f": {detail}" if detail else ""
            raise FPDSError(f"FPDS HTTP {exc.code}{suffix}") from exc
        except URLError as exc:
            is_timeout = isinstance(
                exc.reason, (TimeoutError, socket.timeout)
            )
            if is_timeout and attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise FPDSError(f"FPDS request failed: {exc.reason}") from exc
        except (TimeoutError, socket.timeout) as exc:
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise FPDSError("FPDS request timed out after retries") from exc
        else:
            lowered = body.lstrip().lower()
            if (
                "text/html" in content_type.lower()
                or lowered.startswith(b"<html")
                or lowered.startswith(b"<!doctype html")
            ):
                raise FPDSError(
                    "FPDS returned HTML instead of an ATOM feed; "
                    "the request may be blocked"
                )
            return body

    raise FPDSError("FPDS request failed after retries")


def _feed_url(query):
    params = {
        "FEEDNAME": "PUBLIC",
        "templateName": "1.5.3",
        "q": query,
        "start": 0,
    }
    return f"{BASE_URL}?{urlencode(params)}"


def fetch_feed(query, max_pages=10):
    """Fetch and parse ATOM pages, reporting whether the page cap truncated.

    A feed that still offers a rel=next link when the cap is reached has more
    records than were returned. Callers deriving an extremum — an earliest
    action date, a first-seen vendor — must not treat such a result as the
    vendor's complete history.
    """
    actions = []
    next_url = _feed_url(query)
    seen_urls = set()
    pages_fetched = 0

    for page_number in range(1, max_pages + 1):
        if next_url in seen_urls:
            raise FPDSError("FPDS paging loop detected in rel=next links")
        seen_urls.add(next_url)

        if page_number > 1:
            time.sleep(1)
        xml_data = _fetch_atom_page(next_url)
        page_actions, next_url = parse_atom(xml_data)
        actions.extend(page_actions)
        pages_fetched = page_number
        if not next_url:
            break

    return FetchResult(actions, pages_fetched, bool(next_url), next_url)


def fetch_actions(query, max_pages=10):
    """Fetch actions as a plain list, discarding paging state.

    Use ``fetch_feed`` when the caller must know the results were truncated.
    """
    return fetch_feed(query, max_pages=max_pages).actions


def load_actions(path):
    """Parse a saved ATOM response without making any network request."""
    try:
        xml_data = Path(path).read_bytes()
    except OSError as exc:
        raise FPDSError(f"Could not read FPDS fixture {path}: {exc}") from exc
    actions, _next_url = parse_atom(xml_data)
    return actions


def _fmt_money(value):
    if value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def print_actions(actions):
    """Print the required workflow/action fields as a compact table."""
    if not actions:
        print("No FPDS contract actions found.")
        return

    headers = (
        ("TYPE", 5),
        ("MOD", 8),
        ("SIGNED", 10),
        ("ACTION OBLIGATION", 18),
        ("CREATED BY", 16),
        ("LAST MODIFIED BY", 18),
        ("APPROVED BY", 16),
    )
    prefix = " | ".join(f"{label:<{width}}" for label, width in headers)
    print(f"{prefix} | DESCRIPTION")
    print("-" * (len(prefix) + 3 + 72))

    for action in actions:
        signed = (action.get("signed_date") or "")[:10]
        values = (
            (action.get("record_type") or "?", 5),
            (action.get("modification_number") or "", 8),
            (signed, 10),
            (_fmt_money(action.get("action_obligation")), 18),
            (action.get("createdBy") or "", 16),
            (action.get("lastModifiedBy") or "", 18),
            (action.get("approvedBy") or "", 16),
        )
        row = " | ".join(f"{str(value):<{width}}" for value, width in values)
        description = action.get("description") or ""
        if len(description) > 72:
            description = f"{description[:69]}..."
        print(f"{row} | {description}")


def _output_payload(result, query, args):
    """Wrap results with the paging provenance a downstream script needs."""
    return {
        "query": query,
        "source": args.from_file or BASE_URL,
        "record_count": len(result.actions),
        "pages_fetched": result.pages_fetched,
        "max_pages": None if args.from_file else args.max_pages,
        "truncated": result.truncated,
        "next_url": result.next_url,
        "actions": result.actions,
    }


def _positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _add_common_args(parser):
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        help="Parse a saved ATOM XML response instead of fetching",
    )
    parser.add_argument(
        "--max-pages",
        type=_positive_int,
        default=10,
        help="Maximum ATOM pages to fetch (default: 10)",
    )
    parser.add_argument(
        "--with-metadata",
        action="store_true",
        help=(
            "Wrap results in an object carrying query, paging and truncated "
            "fields instead of emitting a bare list"
        ),
    )
    add_output_args(parser)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "FPDS-NG ATOM — contract actions and workflow/approval fields"
        ),
        epilog="No API key. Live paging is limited to one request per second.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    piid_parser = sub.add_parser(
        "piid", help="Fetch all contract actions for an exact PIID"
    )
    piid_parser.add_argument("piid", help="Procurement Instrument Identifier")
    _add_common_args(piid_parser)

    search_parser = sub.add_parser(
        "search", help="Run a raw FPDS ATOM query"
    )
    search_parser.add_argument(
        "query", help='Raw query, e.g. "VENDOR_UEI:D13LLJJZYH64"'
    )
    _add_common_args(search_parser)

    args = parser.parse_args()
    query = (
        f'PIID:"{args.piid}"'
        if args.command == "piid"
        else args.query
    )

    try:
        if args.from_file:
            result = FetchResult(load_actions(args.from_file), 1, False, None)
        else:
            result = fetch_feed(query, max_pages=args.max_pages)
    except FPDSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    actions = result.actions
    unrecognized = sum(1 for row in actions if row["record_type"] is None)
    if unrecognized:
        print(
            f"WARNING: {unrecognized} of {len(actions)} entries used an "
            "unrecognized FPDS payload root and parsed to null fields",
            file=sys.stderr,
        )
    if result.truncated:
        print(
            f"WARNING: stopped at the --max-pages limit of {args.max_pages} "
            f"while the feed still offered another page. These {len(actions)} "
            "records are a partial set; raise --max-pages before deriving "
            "earliest-action or first-seen dates from them.",
            file=sys.stderr,
        )

    payload = _output_payload(result, query, args) if args.with_metadata else actions
    exit_code = EXIT_TRUNCATED if result.truncated else 0

    if write_output(
        payload,
        args,
        summary=f"FPDS actions for {query}",
        result_count=len(actions),
    ):
        return exit_code

    print_actions(actions)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
