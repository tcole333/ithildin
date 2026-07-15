#!/usr/bin/env python3
"""Query CMS Open Payments physician and company payment data.

CMS migrated OpenPaymentsData.CMS.gov from Socrata to a DKAN catalog in 2026.
This client discovers the live catalog and uses its bounded datastore endpoint;
it does not download the multi-gigabyte annual CSV files automatically.

Examples:
    uv run python tools/query_openpayments.py datasets --query "2025 General"
    uv run python tools/query_openpayments.py search MERKIN --first-name MICHAEL
    uv run python tools/query_openpayments.py search 1952494221
    uv run python tools/query_openpayments.py payments 704135 --year all
    uv run python tools/query_openpayments.py payments 704135 --year 2025
    uv run python tools/query_openpayments.py query DATASET_UUID \
        --where covered_recipient_profile_id=704135 --limit 25

API: https://openpaymentsdata.cms.gov/api/1
Authentication: None.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from tools.lead_tracker import log_search
    from tools.output_util import add_output_args, write_output
except ImportError:
    from lead_tracker import log_search
    from output_util import add_output_args, write_output


BASE_URL = "https://openpaymentsdata.cms.gov/api/1"
CATALOG_PATH = "/metastore/schemas/dataset/items"
PROFILE_DATASET_ID = "6ed6ae76-2999-49da-b0b2-d7df150ac754"
ALL_YEARS_COMPANY_DATASET_ID = "e49defac-4013-408d-b36f-665fc0ad51b2"
ALL_YEARS_NATURE_DATASET_ID = "8d4d1fa0-9419-4993-97ff-9134c95c27a9"

USER_AGENT = "Ithildin-OSINT/1.0 (+public CMS Open Payments research)"
REQUEST_TIMEOUT = 45
MAX_RESPONSE_BYTES = 25 * 1024 * 1024
MAX_LIMIT = 500
MIN_REQUEST_INTERVAL = 0.2
MAX_RETRIES = 3

_DATASET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{2,80}$")
_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_last_request_at = 0.0


NATURE_OF_PAYMENT = {
    "1": "Consulting Fee",
    "2": (
        "Compensation for services other than consulting, including serving as "
        "faculty or as a speaker at a venue other than a continuing education program"
    ),
    "3": "Honoraria",
    "4": "Gift",
    "5": "Entertainment",
    "6": "Food and Beverage",
    "7": "Travel and Lodging",
    "8": "Education",
    "9": "Charitable Contribution",
    "10": "Royalty or license",
    "11": "Current or prospective ownership or investment interest",
    "12": (
        "Compensation for serving as faculty or as a speaker for a non-accredited "
        "and noncertified continuing education program"
    ),
    "13": (
        "Compensation for serving as faculty or as a speaker for an accredited or "
        "certified continuing education program"
    ),
    "14": "Grant",
    "15": "Space rental or facility fees (teaching hospital only)",
    "16": "Compensation for serving as faculty or as a speaker for a medical education program",
    "17": "Debt forgiveness",
    "18": "Long term medical supply or device loan",
    "19": "Acquisitions",
}


class OpenPaymentsError(RuntimeError):
    """Raised for a bounded, user-actionable Open Payments failure."""


@dataclass(frozen=True)
class Condition:
    field: str
    value: str


def _pace() -> None:
    """Apply a small client-side delay even though CMS publishes no API key limit."""
    global _last_request_at
    now = time.monotonic()
    remaining = MIN_REQUEST_INTERVAL - (now - _last_request_at)
    if remaining > 0:
        time.sleep(remaining)
    _last_request_at = time.monotonic()


def _error_body(error: HTTPError) -> str:
    try:
        return error.read(1000).decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _get_json(path: str, params: Iterable[tuple[str, Any]] | None = None) -> Any:
    """Fetch one official API response with pacing, retries, and a size bound."""
    if not path.startswith("/"):
        raise ValueError("API path must start with '/'")
    query = urlencode(list(params or []), doseq=True)
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})

    for attempt in range(MAX_RETRIES):
        _pace()
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                content_type = response.headers.get_content_type()
                if content_type != "application/json":
                    raise OpenPaymentsError(
                        f"CMS returned unexpected content type {content_type!r} for {url}"
                    )
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise OpenPaymentsError(
                        f"CMS response exceeded {MAX_RESPONSE_BYTES:,} bytes; narrow the query"
                    )
                try:
                    return json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise OpenPaymentsError(f"CMS returned invalid JSON for {url}: {exc}") from exc
        except HTTPError as exc:
            body = _error_body(exc)
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt + 1 < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
            detail = f": {body[:300]}" if body else ""
            raise OpenPaymentsError(f"CMS HTTP {exc.code} for {url}{detail}") from exc
        except (URLError, TimeoutError) as exc:
            if attempt + 1 < MAX_RETRIES:
                time.sleep(0.5 * (2**attempt))
                continue
            reason = getattr(exc, "reason", exc)
            raise OpenPaymentsError(f"CMS request failed for {url}: {reason}") from exc

    raise OpenPaymentsError(f"CMS request failed after {MAX_RETRIES} attempts: {url}")


def _bounded_limit(value: int) -> int:
    if not 1 <= value <= MAX_LIMIT:
        raise OpenPaymentsError(f"--limit must be between 1 and {MAX_LIMIT}")
    return value


def _validate_dataset_id(dataset_id: str) -> str:
    if not _DATASET_ID_RE.fullmatch(dataset_id):
        raise OpenPaymentsError(f"Invalid dataset identifier: {dataset_id!r}")
    return dataset_id


def _validate_condition(condition: Condition) -> Condition:
    if not _FIELD_RE.fullmatch(condition.field):
        raise OpenPaymentsError(f"Invalid condition field: {condition.field!r}")
    if len(condition.value) > 500:
        raise OpenPaymentsError(f"Condition value for {condition.field!r} exceeds 500 characters")
    return condition


def query_dataset(
    dataset_id: str,
    conditions: Iterable[Condition] = (),
    *,
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Run a bounded exact-match query against a stable CMS dataset ID."""
    dataset_id = _validate_dataset_id(dataset_id)
    limit = _bounded_limit(limit)
    if offset < 0:
        raise OpenPaymentsError("--offset cannot be negative")

    params: list[tuple[str, Any]] = [("limit", limit), ("offset", offset)]
    normalized = [_validate_condition(c) for c in conditions]
    for index, condition in enumerate(normalized):
        params.extend(
            [
                (f"conditions[{index}][property]", condition.field),
                (f"conditions[{index}][value]", condition.value),
                (f"conditions[{index}][operator]", "="),
            ]
        )

    data = _get_json(f"/datastore/query/{dataset_id}/0", params)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise OpenPaymentsError(f"CMS returned an unexpected datastore response for {dataset_id}")
    return data


def get_catalog() -> list[dict[str, Any]]:
    data = _get_json(CATALOG_PATH, [("show-reference-ids", "true")])
    if not isinstance(data, list):
        raise OpenPaymentsError("CMS returned an unexpected catalog response")
    return [item for item in data if isinstance(item, dict)]


def _distribution_data(item: dict[str, Any]) -> dict[str, Any]:
    distributions = item.get("distribution") or []
    if not distributions or not isinstance(distributions[0], dict):
        return {}
    distribution = distributions[0]
    nested = distribution.get("data")
    return nested if isinstance(nested, dict) else distribution


def summarize_dataset(item: dict[str, Any]) -> dict[str, Any]:
    distribution = _distribution_data(item)
    return {
        "identifier": item.get("identifier"),
        "title": item.get("title"),
        "description": item.get("description"),
        "issued": item.get("issued"),
        "modified": item.get("modified"),
        "temporal": item.get("temporal"),
        "format": distribution.get("format") or distribution.get("mediaType"),
        "download_url": distribution.get("downloadURL"),
        "data_dictionary_url": distribution.get("describedBy"),
    }


def _find_dataset(catalog: list[dict[str, Any]], title: str) -> dict[str, Any]:
    expected = title.casefold()
    matches = [item for item in catalog if str(item.get("title", "")).casefold() == expected]
    if len(matches) != 1:
        raise OpenPaymentsError(
            f"Expected one CMS dataset titled {title!r}, found {len(matches)}; run 'datasets' to inspect"
        )
    return matches[0]


def _year_dataset_ids(year: str) -> tuple[str, str]:
    if year == "all":
        return ALL_YEARS_COMPANY_DATASET_ID, ALL_YEARS_NATURE_DATASET_ID
    if not re.fullmatch(r"20\d{2}", year):
        raise OpenPaymentsError("--year must be 'all' or a four-digit program year")
    catalog = get_catalog()
    company = _find_dataset(
        catalog, f"{year} payments grouped by covered recipient and reporting entities"
    )
    nature = _find_dataset(
        catalog, f"{year} payments grouped by covered recipient and nature of payments"
    )
    return str(company["identifier"]), str(nature["identifier"])


def _parse_where(raw: str) -> Condition:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("conditions must use FIELD=VALUE")
    field, value = raw.split("=", 1)
    try:
        return _validate_condition(Condition(field.strip(), value.strip()))
    except OpenPaymentsError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _emit(data: Any, args: argparse.Namespace, summary: str) -> None:
    if write_output(data, args, summary=summary):
        return
    print(json.dumps(data, indent=2, default=str))


def _profile_url(profile_id: str) -> str:
    return f"https://openpaymentsdata.cms.gov/physician/{profile_id}"


def cmd_datasets(args: argparse.Namespace) -> None:
    catalog = get_catalog()
    query = args.query.casefold().strip() if args.query else ""
    matching = []
    for item in catalog:
        haystack = f"{item.get('title', '')}\n{item.get('description', '')}".casefold()
        if not query or query in haystack:
            matching.append(summarize_dataset(item))
    matching = matching[: _bounded_limit(args.limit)]
    output = {
        "source": "CMS Open Payments",
        "catalog_url": f"{BASE_URL}{CATALOG_PATH}",
        "total_catalog_datasets": len(catalog),
        "matched_datasets": len(matching),
        "results": matching,
    }
    _emit(output, args, f"CMS Open Payments catalog ({len(matching)} matched)")


def cmd_search(args: argparse.Namespace) -> None:
    query = args.query.strip()
    conditions: list[Condition]
    if query.isdigit():
        if len(query) != 10:
            raise OpenPaymentsError("An NPI search must contain exactly 10 digits")
        conditions = [Condition("covered_recipient_npi", query)]
    else:
        conditions = [Condition("covered_recipient_profile_last_name", query.upper())]
        if args.first_name:
            conditions.append(
                Condition("covered_recipient_profile_first_name", args.first_name.strip().upper())
            )
    if args.state:
        state = args.state.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", state):
            raise OpenPaymentsError("--state must be a two-letter code")
        conditions.append(Condition("covered_recipient_profile_state", state))

    data = query_dataset(PROFILE_DATASET_ID, conditions, limit=args.limit, offset=args.offset)
    results = []
    for raw_row in data["results"]:
        row = dict(raw_row)
        profile_id = str(row.get("covered_recipient_profile_id", ""))
        if profile_id.isdigit():
            row["evidence_ref"] = f"OPENPAYMENTS:{profile_id}"
            row["profile_url"] = _profile_url(profile_id)
        results.append(row)
    total = int(data.get("count", len(results)))
    output = {
        "source": "CMS Open Payments",
        "dataset_id": PROFILE_DATASET_ID,
        "query": query,
        "total": total,
        "offset": args.offset,
        "limit": args.limit,
        "truncated": args.offset + len(results) < total,
        "results": results,
    }
    log_search(query, "cms_openpayments_profiles", total)
    _emit(output, args, f"CMS Open Payments profile search {query!r} ({total} total)")


def cmd_payments(args: argparse.Namespace) -> None:
    profile_id = args.profile_id.strip()
    if not profile_id.isdigit():
        raise OpenPaymentsError("profile_id must be numeric")
    company_id, nature_id = _year_dataset_ids(args.year)
    condition = [Condition("recipient_id", profile_id)]
    company_data = query_dataset(company_id, condition, limit=args.limit, offset=args.offset)
    nature_data = query_dataset(nature_id, condition, limit=args.limit, offset=args.offset)

    records: list[dict[str, Any]] = []
    for row in company_data["results"]:
        records.append(
            {
                "summary_kind": "reporting_entity",
                "evidence_ref": f"OPENPAYMENTS:{profile_id}",
                **row,
            }
        )
    for row in nature_data["results"]:
        code = str(row.get("nature_of_payment_type_code", ""))
        records.append(
            {
                "summary_kind": "nature_of_payment",
                "nature_of_payment": NATURE_OF_PAYMENT.get(code, f"Unknown code {code}"),
                "evidence_ref": f"OPENPAYMENTS:{profile_id}",
                **row,
            }
        )

    company_total = int(company_data.get("count", len(company_data["results"])))
    nature_total = int(nature_data.get("count", len(nature_data["results"])))
    output = {
        "source": "CMS Open Payments",
        "profile_id": profile_id,
        "evidence_ref": f"OPENPAYMENTS:{profile_id}",
        "profile_url": _profile_url(profile_id),
        "program_year": args.year,
        "datasets": {"reporting_entities": company_id, "payment_natures": nature_id},
        "totals": {"reporting_entities": company_total, "payment_natures": nature_total},
        "offset": args.offset,
        "limit_per_summary": args.limit,
        "truncated": (
            args.offset + len(company_data["results"]) < company_total
            or args.offset + len(nature_data["results"]) < nature_total
        ),
        "records": records,
    }
    log_search(
        f"profile:{profile_id}:year:{args.year}",
        "cms_openpayments_payments",
        company_total + nature_total,
    )
    _emit(
        output,
        args,
        f"CMS Open Payments profile {profile_id} ({company_total + nature_total} summaries)",
    )


def cmd_query(args: argparse.Namespace) -> None:
    conditions = args.where or []
    data = query_dataset(
        args.dataset_id,
        conditions,
        limit=args.limit,
        offset=args.offset,
    )
    rows = data["results"]
    total = int(data.get("count", len(rows)))
    output = {
        "source": "CMS Open Payments",
        "dataset_id": args.dataset_id,
        "conditions": [{"field": c.field, "value": c.value} for c in conditions],
        "total": total,
        "offset": args.offset,
        "limit": args.limit,
        "truncated": args.offset + len(rows) < total,
        "results": rows,
    }
    condition_label = ",".join(f"{c.field}={c.value}" for c in conditions) or "unfiltered"
    log_search(
        f"dataset:{args.dataset_id}:{condition_label}",
        "cms_openpayments_dataset",
        total,
    )
    _emit(output, args, f"CMS Open Payments dataset {args.dataset_id} ({total} total)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CMS Open Payments physician, company, and payment data"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    datasets = subparsers.add_parser(
        "datasets", help="Discover current datasets and their official CSV download URLs"
    )
    datasets.add_argument("--query", help="Case-insensitive title/description filter")
    datasets.add_argument("--limit", type=int, default=25, help=f"Maximum results (1-{MAX_LIMIT})")
    add_output_args(datasets)
    datasets.set_defaults(func=cmd_datasets)

    search = subparsers.add_parser(
        "search", help="Find a covered-recipient profile by exact last name or 10-digit NPI"
    )
    search.add_argument("query", help="Exact physician last name or NPI")
    search.add_argument("--first-name", help="Optional exact first-name filter")
    search.add_argument("--state", help="Optional two-letter profile state")
    search.add_argument("--limit", type=int, default=25, help=f"Maximum results (1-{MAX_LIMIT})")
    search.add_argument("--offset", type=int, default=0, help="Result offset for pagination")
    add_output_args(search)
    search.set_defaults(func=cmd_search)

    payments = subparsers.add_parser(
        "payments", help="Summarize reporting entities and payment natures for a profile ID"
    )
    payments.add_argument("profile_id", help="CMS covered-recipient profile ID")
    payments.add_argument(
        "--year", default="all", help="Program year (for example 2025) or 'all' (2019+)"
    )
    payments.add_argument(
        "--limit", type=int, default=100, help=f"Maximum rows per summary (1-{MAX_LIMIT})"
    )
    payments.add_argument("--offset", type=int, default=0, help="Result offset for pagination")
    add_output_args(payments)
    payments.set_defaults(func=cmd_payments)

    query = subparsers.add_parser("query", help="Run a bounded exact-match query on a dataset")
    query.add_argument("dataset_id", help="Stable dataset identifier from the catalog")
    query.add_argument(
        "--where", action="append", type=_parse_where, metavar="FIELD=VALUE", help="Exact condition"
    )
    query.add_argument("--limit", type=int, default=25, help=f"Maximum results (1-{MAX_LIMIT})")
    query.add_argument("--offset", type=int, default=0, help="Result offset for pagination")
    add_output_args(query)
    query.set_defaults(func=cmd_query)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (OpenPaymentsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
