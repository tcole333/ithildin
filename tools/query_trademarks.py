#!/usr/bin/env python3
"""
USPTO trademark-register search for ownership and mark research.

The trademark register is separate from the USPTO patent Open Data Portal.
This tool searches wordmarks, owner blocks, serial numbers, and
goods-and-services text without an API key.

API: https://tmsearch.uspto.gov/prod-v1-0-0/tmsearch
Auth: None.

Usage:
    uv run python tools/query_trademarks.py mark "HC STANDARD"
    uv run python tools/query_trademarks.py owner "Global Emergency Resources"
    uv run python tools/query_trademarks.py serial 85877492
    uv run python tools/query_trademarks.py goods "asset tracking" --live-only
    uv run python tools/query_trademarks.py mark "HC STANDARD" \
        --from-file saved-response.json --output trademarks.json
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
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


BASE_URL = "https://tmsearch.uspto.gov/prod-v1-0-0/tmsearch"
REQUEST_TIMEOUT = 60
MAX_ATTEMPTS = 3
MAX_PAGES = 20
SOURCE_FIELDS = [
    "abandonDate",
    "alive",
    "attorney",
    "cancelDate",
    "coordinatedClass",
    "currentBasis",
    "designCodeDescription",
    "disclaimer",
    "drawingCode",
    "filedDate",
    "goodsAndServices",
    "id",
    "internationalClass",
    "markDescription",
    "markType",
    "originalBasis",
    "ownerFullText",
    "ownerName",
    "ownerType",
    "priorityDate",
    "publishForOppositionDate",
    "registrationDate",
    "registrationId",
    "registrationType",
    "supplementalRegistrationDate",
    "translation",
    "usClass",
    "wordmark",
    "wordmarkPseudoText",
]


class TrademarkError(RuntimeError):
    """A clear, user-facing USPTO trademark request or parsing failure."""


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _normalize_class(value: str) -> str:
    text = value.strip().upper()
    if text.startswith("IC "):
        text = text[3:].strip()
    try:
        number = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an international class number, e.g. 042"
        ) from exc
    if not 1 <= number <= 45:
        raise argparse.ArgumentTypeError("must be between 001 and 045")
    return f"IC {number:03d}"


def _mark_clause(
    phrase: str, *, loose: bool, include_pseudo: bool
) -> dict:
    if loose:
        return {
            "bool": {
                "should": [
                    {
                        "match_phrase": {
                            "WM": {"query": phrase, "boost": 5}
                        }
                    },
                    {"match": {"WM": {"query": phrase, "boost": 2}}},
                    {
                        "match_phrase": {
                            "PM": {"query": phrase, "boost": 2}
                        }
                    },
                ]
            }
        }

    phrase_matches = [{"match_phrase": {"WM": {"query": phrase}}}]
    if include_pseudo:
        phrase_matches.append(
            {"match_phrase": {"PM": {"query": phrase}}}
        )
    if len(phrase_matches) == 1:
        return phrase_matches[0]
    return {
        "bool": {
            "should": phrase_matches,
            "minimum_should_match": 1,
        }
    }


def build_query(
    command: str,
    value: str,
    *,
    limit: int = 25,
    offset: int = 0,
    loose: bool = False,
    include_pseudo: bool = False,
    live_only: bool = False,
    dead_only: bool = False,
    international_class: str | None = None,
) -> dict:
    """Build the raw Elasticsearch request body used by USPTO TM Search."""
    if command == "mark":
        query_clause = _mark_clause(
            value, loose=loose, include_pseudo=include_pseudo
        )
    elif command == "owner":
        query_clause = {
            "match_phrase": {"ownerFullText": {"query": value}}
        }
    elif command == "serial":
        query_clause = {"term": {"id": value}}
    elif command == "goods":
        query_clause = {
            "match_phrase": {"goodsAndServices": {"query": value}}
        }
    else:
        raise ValueError(f"Unknown trademark command: {command}")

    filters = []
    if live_only:
        filters.append({"term": {"alive": True}})
    elif dead_only:
        filters.append({"term": {"alive": False}})
    if international_class:
        filters.append(
            {
                "match_phrase": {
                    "internationalClass": {
                        "query": international_class
                    }
                }
            }
        )

    bool_query = {"must": [query_clause]}
    if filters:
        bool_query["filter"] = filters

    return {
        "query": {"bool": bool_query},
        "size": limit,
        "from": offset,
        "track_total_hits": True,
        "_source": SOURCE_FIELDS,
    }


def _parse_response_page(payload: object) -> tuple[list[dict], int | None]:
    if isinstance(payload, (bytes, bytearray)):
        try:
            payload = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrademarkError(
                f"USPTO trademark response was not valid JSON: {exc}"
            ) from exc
    elif isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise TrademarkError(
                f"USPTO trademark response was not valid JSON: {exc}"
            ) from exc

    if not isinstance(payload, dict):
        raise TrademarkError("USPTO trademark response was not a JSON object")
    hits_wrapper = payload.get("hits")
    if not isinstance(hits_wrapper, dict):
        raise TrademarkError(
            "USPTO trademark response did not contain a hits object"
        )
    raw_hits = hits_wrapper.get("hits")
    if not isinstance(raw_hits, list):
        raise TrademarkError(
            "USPTO trademark response did not contain hits.hits[]"
        )

    records = []
    for index, hit in enumerate(raw_hits):
        if not isinstance(hit, dict) or not isinstance(
            hit.get("source"), dict
        ):
            raise TrademarkError(
                "USPTO trademark hit "
                f"{index} did not contain hits.hits[].source"
            )
        records.append(hit["source"])

    total = hits_wrapper.get("totalValue")
    if not isinstance(total, int):
        total = None
    return records, total


def parse_response(payload: object) -> list[dict]:
    """Parse records from the API's hits.hits[].source response shape."""
    records, _total = _parse_response_page(payload)
    return records


def _looks_like_html(body: bytes, content_type: str = "") -> bool:
    lowered = body.lstrip().lower()
    return (
        "text/html" in content_type.lower()
        or lowered.startswith(b"<html")
        or lowered.startswith(b"<!doctype html")
    )


def _fetch_page(body: dict) -> dict:
    """Fetch one result page, retrying server errors and timeouts."""
    encoded_body = json.dumps(body).encode("utf-8")
    request = Request(
        BASE_URL,
        data=encoded_body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (compatible; OSINT-Research/1.0; "
                "+https://github.com/)"
            ),
        },
    )

    for attempt in range(MAX_ATTEMPTS):
        try:
            with urlopen(
                request, timeout=REQUEST_TIMEOUT, context=SSL_CONTEXT
            ) as response:
                content_type = response.headers.get("Content-Type", "")
                response_body = response.read()
        except HTTPError as exc:
            error_body = exc.read()
            if 500 <= exc.code < 600 and attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            error_content_type = (
                exc.headers.get("Content-Type", "")
                if exc.headers is not None
                else ""
            )
            if _looks_like_html(
                error_body, error_content_type
            ):
                raise TrademarkError(
                    "USPTO trademark search returned HTML instead of JSON "
                    f"(HTTP {exc.code}); the request may be blocked"
                ) from exc
            detail = error_body.decode(
                "utf-8", errors="replace"
            ).strip()[:300]
            suffix = f": {detail}" if detail else ""
            raise TrademarkError(
                f"USPTO trademark search HTTP {exc.code}{suffix}"
            ) from exc
        except URLError as exc:
            is_timeout = isinstance(
                exc.reason, (TimeoutError, socket.timeout)
            )
            if is_timeout and attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise TrademarkError(
                f"USPTO trademark request failed: {exc.reason}"
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(2**attempt)
                continue
            raise TrademarkError(
                "USPTO trademark request timed out after retries"
            ) from exc
        else:
            if _looks_like_html(response_body, content_type):
                raise TrademarkError(
                    "USPTO trademark search returned HTML instead of JSON; "
                    "the request may be blocked"
                )
            try:
                decoded = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise TrademarkError(
                    "USPTO trademark search returned invalid JSON: "
                    f"{exc}"
                ) from exc
            if not isinstance(decoded, dict):
                raise TrademarkError(
                    "USPTO trademark search returned a non-object JSON value"
                )
            return decoded

    raise TrademarkError("USPTO trademark request failed after retries")


def fetch_records(
    command: str,
    value: str,
    *,
    limit: int = 25,
    all_pages: bool = False,
    loose: bool = False,
    include_pseudo: bool = False,
    live_only: bool = False,
    dead_only: bool = False,
    international_class: str | None = None,
) -> list[dict]:
    """Fetch one page, or up to 20 pages when all-pages is requested."""
    records = []
    page_count = MAX_PAGES if all_pages else 1

    for page_number in range(page_count):
        if page_number:
            time.sleep(1)
        body = build_query(
            command,
            value,
            limit=limit,
            offset=page_number * limit,
            loose=loose,
            include_pseudo=include_pseudo,
            live_only=live_only,
            dead_only=dead_only,
            international_class=international_class,
        )
        page_records, total = _parse_response_page(_fetch_page(body))
        records.extend(page_records)

        if not all_pages:
            break
        if not page_records or len(page_records) < limit:
            break
        if total is not None and len(records) >= total:
            break

    return records


def load_records(path: str | Path) -> list[dict]:
    """Parse a saved USPTO trademark JSON response without network access."""
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise TrademarkError(
            f"Could not read USPTO trademark fixture {path}: {exc}"
        ) from exc
    return parse_response(payload)


def extract_owner_lines(record: dict) -> list[str]:
    """Return every owner block line, preserving ownership-chain labels."""
    raw_owners = record.get("ownerFullText")
    if raw_owners is None:
        return []
    if isinstance(raw_owners, str):
        raw_owners = [raw_owners]
    if not isinstance(raw_owners, list):
        return [str(raw_owners)]

    lines = []
    for owner in raw_owners:
        for line in str(owner).splitlines():
            cleaned = " ".join(line.split())
            if cleaned:
                lines.append(cleaned)
    return lines


def _as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def filter_records(
    records: list[dict],
    *,
    live_only: bool,
    dead_only: bool,
    international_class: str | None,
    limit: int,
) -> list[dict]:
    filtered = []
    for record in records:
        if live_only and record.get("alive") is not True:
            continue
        if dead_only and record.get("alive") is not False:
            continue
        classes = _as_text_list(record.get("internationalClass"))
        if international_class and international_class not in classes:
            continue
        filtered.append(record)
    return filtered[:limit]


def _truncate(text: str, width: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= width:
        return cleaned
    return f"{cleaned[: width - 3].rstrip()}..."


def print_records(records: list[dict]) -> None:
    """Print mark status, identifiers, classes, owners, and goods."""
    if not records:
        print("0 results.")
        return

    label = "result" if len(records) == 1 else "results"
    print(f"{len(records)} {label}:")
    for record in records:
        wordmark = record.get("wordmark") or "(no wordmark)"
        status = "LIVE" if record.get("alive") is True else "DEAD"
        filed = str(record.get("filedDate") or "N/A")[:10]
        registration = record.get("registrationId") or "N/A"
        classes = ", ".join(
            _as_text_list(record.get("internationalClass"))
        ) or "N/A"
        print(f"\n{wordmark}")
        print(
            f"  Serial: {record.get('id') or 'N/A'} | {status} | "
            f"Filed: {filed} | Registration: {registration} | "
            f"Classes: {classes}"
        )

        owner_lines = extract_owner_lines(record)
        if owner_lines:
            for owner_line in owner_lines:
                print(f"  Owner: {owner_line}")
        else:
            print("  Owner: N/A")

        goods = " | ".join(
            _as_text_list(record.get("goodsAndServices"))
        )
        print(f"  Goods/services: {_truncate(goods) if goods else 'N/A'}")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=25,
        help="Results per page (default: 25)",
    )
    parser.add_argument(
        "--all-pages",
        action="store_true",
        help="Fetch all result pages, capped at 20 pages",
    )
    status_group = parser.add_mutually_exclusive_group()
    status_group.add_argument(
        "--live-only",
        action="store_true",
        help="Return only live marks",
    )
    status_group.add_argument(
        "--dead-only",
        action="store_true",
        help="Return only dead or abandoned marks",
    )
    parser.add_argument(
        "--class",
        dest="international_class",
        type=_normalize_class,
        help="Filter by international class, e.g. 042",
    )
    parser.add_argument(
        "--from-file",
        metavar="PATH",
        help="Parse a saved USPTO trademark JSON response instead of fetching",
    )
    add_output_args(parser)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "USPTO trademark register — marks, owners, serials, and goods"
        ),
        epilog=(
            "No API key. Mark search defaults to exact phrase matching; "
            "use --loose for the site's broad OR-style search."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    mark_parser = subparsers.add_parser(
        "mark", help="Search a wordmark as an exact phrase by default"
    )
    mark_parser.add_argument("value", metavar="PHRASE")
    mark_parser.add_argument(
        "--loose",
        action="store_true",
        help="Use the site's broad, OR-style boosted word search",
    )
    mark_parser.add_argument(
        "--include-pseudo",
        action="store_true",
        help="Also exact-phrase match the pseudo-mark field",
    )
    _add_common_args(mark_parser)

    owner_parser = subparsers.add_parser(
        "owner", help="Find marks whose full owner block matches a name"
    )
    owner_parser.add_argument("value", metavar="NAME")
    _add_common_args(owner_parser)

    serial_parser = subparsers.add_parser(
        "serial", help="Fetch a trademark record by serial number"
    )
    serial_parser.add_argument("value", metavar="ID")
    _add_common_args(serial_parser)

    goods_parser = subparsers.add_parser(
        "goods", help="Search goods-and-services text as an exact phrase"
    )
    goods_parser.add_argument("value", metavar="PHRASE")
    _add_common_args(goods_parser)

    args = parser.parse_args()

    try:
        if args.from_file:
            records = filter_records(
                load_records(args.from_file),
                live_only=args.live_only,
                dead_only=args.dead_only,
                international_class=args.international_class,
                limit=args.limit,
            )
        else:
            records = fetch_records(
                args.command,
                args.value,
                limit=args.limit,
                all_pages=args.all_pages,
                loose=getattr(args, "loose", False),
                include_pseudo=getattr(args, "include_pseudo", False),
                live_only=args.live_only,
                dead_only=args.dead_only,
                international_class=args.international_class,
            )
    except TrademarkError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = f"USPTO trademarks {args.command} search for {args.value!r}"
    if write_output(records, args, summary=summary):
        return 0
    if getattr(args, "json_out", False):
        print(json.dumps(records, indent=2))
        return 0

    print_records(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
