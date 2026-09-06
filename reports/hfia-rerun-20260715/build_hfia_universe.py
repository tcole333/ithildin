#!/usr/bin/env python3
"""Build the regenerable HFIA post-Act Section 16 universe.

The builder uses SEC full-index form.idx files to define the likely-FPI
screening universe, issuer submissions JSON to enumerate filings, and raw
ownership XML to extract reporting-owner roles and transactions. Raw network
responses are cached so interrupted builds can resume without re-fetching.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


USER_AGENT = "Ithildin research traviscole44@gmail.com"
FPI_FORMS = {"6-K", "20-F", "40-F"}
OWNERSHIP_FORMS = {"3", "3/A", "4", "4/A", "5", "5/A"}
HOT_CAPITAL_FORMS = {"F-1", "F-1/A", "F-3", "F-3/A", "424B3", "424B5", "EFFECT"}
SUBMISSIONS_ROOT = "https://data.sec.gov/submissions"
ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar"
DEFAULT_OUTPUT = Path("/tmp/osint-yg3uYgJy")
DEFAULT_DB = Path("/Users/travcole/projects/osint-research/datasets/hfia_universe.db")
MAX_RESPONSE_BYTES = 100 * 1024 * 1024
TRANSIENT_STATUSES = {429, 500, 502, 503, 504}


class BuildError(RuntimeError):
    """A condition that would make the resulting universe unreliable."""


class IssuerMismatch(BuildError):
    """An ownership filing in a submissions feed that concerns another issuer."""


@dataclass
class IssuerState:
    cik: str
    name: str
    evidence: set[str] = field(default_factory=set)
    evidence_dates: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    tickers: list[str] = field(default_factory=list)
    exchanges: list[str] = field(default_factory=list)
    sic: str = ""
    country: str = ""
    submissions: dict[str, Any] | None = None
    filing_rows: list[dict[str, str]] = field(default_factory=list)
    financing_rows: list[dict[str, str]] = field(default_factory=list)

    @property
    def pre_act_evidence(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for form in ("20-F", "6-K"):
            for filed in self.evidence_dates.get(form, []):
                if filed < "2026-03-18":
                    rows.append((form, filed))
        return sorted(rows, key=lambda item: item[1])


@dataclass
class FilingOwner:
    accession: str
    form: str
    filed_date: str
    issuer_cik: str
    owner_cik: str
    owner_name: str
    is_director: int
    is_officer: int
    is_ten_pct: int
    officer_title: str
    agent_prefix: str


@dataclass
class Transaction:
    accession: str
    tx_code: str
    tx_date: str
    shares: float | None
    price: float | None
    acquired_disposed: str
    ownership_form: str


class SecClient:
    """Sequential SEC client with shared fair-access pacing and disk cache."""

    def __init__(
        self,
        cache_root: Path,
        *,
        requests_per_second: float = 7.5,
        offline: bool = False,
        refresh: bool = False,
    ) -> None:
        if not 0 < requests_per_second <= 8:
            raise ValueError("requests_per_second must be in (0, 8]")
        self.cache_root = cache_root
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.min_interval = 1.0 / requests_per_second
        self.offline = offline
        self.refresh = refresh
        self.last_request = 0.0
        self.lock = threading.Lock()
        self.network_requests = 0
        self.cache_hits = 0
        self.retries = 0

    def get(
        self,
        url: str,
        cache_path: Path,
        *,
        accept: str,
        max_attempts: int = 7,
    ) -> bytes:
        if cache_path.exists() and cache_path.stat().st_size and not self.refresh:
            self.cache_hits += 1
            return cache_path.read_bytes()
        if self.offline:
            raise BuildError(f"offline cache miss: {cache_path} ({url})")

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Encoding": "gzip, deflate",
        }
        error_detail = "unknown error"
        for attempt in range(max_attempts):
            with self.lock:
                delay = self.min_interval - (time.monotonic() - self.last_request)
                if delay > 0:
                    time.sleep(delay)
                request = urllib.request.Request(url, headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=45) as response:
                        self.last_request = time.monotonic()
                        self.network_requests += 1
                        raw = response.read(MAX_RESPONSE_BYTES + 1)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise BuildError(f"SEC response exceeded size cap: {url}")
                        encoding = (
                            (response.headers.get("Content-Encoding") or "")
                            .split(",", 1)[0]
                            .strip()
                            .lower()
                        )
                        if encoding == "gzip":
                            import gzip

                            raw = gzip.decompress(raw)
                        elif encoding == "deflate":
                            import zlib

                            try:
                                raw = zlib.decompress(raw)
                            except zlib.error:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise BuildError(f"expanded SEC response exceeded size cap: {url}")
                        atomic_write(cache_path, raw)
                        return raw
                except urllib.error.HTTPError as exc:
                    self.last_request = time.monotonic()
                    self.network_requests += 1
                    error_detail = f"HTTP {exc.code}"
                    if exc.code not in TRANSIENT_STATUSES or attempt + 1 >= max_attempts:
                        raise BuildError(f"{error_detail} from SEC: {url}") from exc
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    try:
                        backoff = float(retry_after)
                    except (TypeError, ValueError):
                        backoff = min(1.0 * (2**attempt), 30.0)
                except urllib.error.URLError as exc:
                    self.last_request = time.monotonic()
                    error_detail = f"network error: {exc.reason}"
                    if attempt + 1 >= max_attempts:
                        raise BuildError(f"{error_detail}: {url}") from exc
                    backoff = min(1.0 * (2**attempt), 30.0)
                except TimeoutError as exc:
                    self.last_request = time.monotonic()
                    error_detail = "timeout"
                    if attempt + 1 >= max_attempts:
                        raise BuildError(f"timeout retrieving {url}") from exc
                    backoff = min(1.0 * (2**attempt), 30.0)
            self.retries += 1
            time.sleep(max(backoff, self.min_interval))
        raise BuildError(f"SEC request exhausted retries ({error_detail}): {url}")

    def get_json(self, url: str, cache_path: Path) -> dict[str, Any]:
        raw = self.get(url, cache_path, accept="application/json")
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BuildError(f"invalid JSON in {cache_path}: {exc}") from exc
        if not isinstance(value, dict):
            raise BuildError(f"expected JSON object in {cache_path}")
        return value


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def append_progress(progress_path: Path, phase: str, **counts: object) -> None:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    detail = " ".join(f"{key}={str(value).replace(' ', '_')}" for key, value in counts.items())
    line = f"{timestamp} phase={phase} {detail}".rstrip()
    with progress_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def cik10(value: str | int | None) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else ""


def root_form(form: str) -> str:
    return form.strip().upper().removesuffix("/A")


def parse_form_index(raw: bytes) -> Iterator[dict[str, str]]:
    text = raw.decode("latin-1", errors="replace")
    lines = text.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("Form Type")),
        None,
    )
    if header_index is None:
        raise BuildError("SEC form.idx header not found")
    header = lines[header_index]
    labels = ("Form Type", "Company Name", "CIK", "Date Filed", "File Name")
    positions = [header.find(label) for label in labels]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise BuildError(f"unexpected SEC form.idx columns: {header}")

    for line in lines[header_index + 2 :]:
        if not line.strip():
            continue
        match = re.match(
            r"^(?P<prefix>.*?)\s+(?P<cik>\d+)\s+"
            r"(?P<filed>\d{4}-\d{2}-\d{2})\s+"
            r"(?P<filename>edgar/data/\S+)\s*$",
            line,
        )
        if not match:
            continue
        prefix = re.split(r"\s{2,}", match.group("prefix"), maxsplit=1)
        if len(prefix) != 2:
            continue
        form, company = (value.strip() for value in prefix)
        cik = match.group("cik")
        filed = match.group("filed")
        filename = match.group("filename")
        yield {
            "form": form,
            "company": html.unescape(company),
            "cik": cik10(cik),
            "filed_date": filed,
            "filename": filename,
        }


def index_periods(start_date: str, end_date: str) -> list[tuple[int, int]]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    periods: list[tuple[int, int]] = []
    year, quarter = start.year, (start.month - 1) // 3 + 1
    last = (end.year, (end.month - 1) // 3 + 1)
    while (year, quarter) <= last:
        periods.append((year, quarter))
        quarter += 1
        if quarter == 5:
            year += 1
            quarter = 1
    return periods


def build_fpi_universe(
    client: SecClient,
    start_date: str,
    end_date: str,
    progress_path: Path,
) -> tuple[dict[str, IssuerState], list[dict[str, str]]]:
    issuers: dict[str, IssuerState] = {}
    index_manifest: list[dict[str, str]] = []
    for year, quarter in index_periods(start_date, end_date):
        url = f"{ARCHIVES_ROOT}/full-index/{year}/QTR{quarter}/form.idx"
        cache_path = client.cache_root / "indexes" / f"{year}-QTR{quarter}-form.idx"
        raw = client.get(url, cache_path, accept="text/plain")
        matching_rows = 0
        total_rows = 0
        for row in parse_form_index(raw):
            total_rows += 1
            if not start_date <= row["filed_date"] <= end_date:
                continue
            normalized = root_form(row["form"])
            if normalized not in FPI_FORMS:
                continue
            matching_rows += 1
            issuer = issuers.setdefault(
                row["cik"], IssuerState(cik=row["cik"], name=row["company"])
            )
            if row["company"]:
                issuer.name = row["company"]
            issuer.evidence.add(normalized)
            issuer.evidence_dates[normalized].append(row["filed_date"])
        index_manifest.append(
            {
                "period": f"{year}-QTR{quarter}",
                "url": url,
                "bytes": str(len(raw)),
                "rows": str(total_rows),
                "fpi_rows": str(matching_rows),
            }
        )
        append_progress(
            progress_path,
            "fpi_index",
            period=f"{year}_QTR{quarter}",
            rows=total_rows,
            fpi_rows=matching_rows,
            unique_issuers=len(issuers),
        )
    if not 1000 <= len(issuers) <= 4000:
        raise BuildError(
            f"FPI universe count {len(issuers):,} is outside expected safety range 1,000-4,000"
        )
    return issuers, index_manifest


def aligned_submission_rows(filings: dict[str, Any]) -> Iterator[dict[str, str]]:
    keys = (
        "accessionNumber",
        "filingDate",
        "reportDate",
        "acceptanceDateTime",
        "act",
        "form",
        "fileNumber",
        "filmNumber",
        "items",
        "size",
        "isXBRL",
        "isInlineXBRL",
        "primaryDocument",
        "primaryDocDescription",
    )
    arrays = {key: filings.get(key, []) for key in keys}
    count = max((len(value) for value in arrays.values() if isinstance(value, list)), default=0)
    for index in range(count):
        row: dict[str, str] = {}
        for key, values in arrays.items():
            value = values[index] if isinstance(values, list) and index < len(values) else ""
            row[key] = "" if value is None else str(value)
        yield row


def segment_overlaps(segment: dict[str, Any], start_date: str, end_date: str) -> bool:
    filing_from = str(segment.get("filingFrom") or "")
    filing_to = str(segment.get("filingTo") or "")
    return not ((filing_to and filing_to < start_date) or (filing_from and filing_from > end_date))


def country_from_submission(data: dict[str, Any]) -> str:
    addresses = data.get("addresses") or {}
    for address_type in ("business", "mailing"):
        address = addresses.get(address_type) or {}
        value = address.get("stateOrCountryDescription") or address.get("stateOrCountry")
        if value:
            return str(value).strip()
    return str(data.get("stateOfIncorporationDescription") or data.get("stateOfIncorporation") or "").strip()


def load_issuer_submissions(
    client: SecClient,
    issuer: IssuerState,
    start_date: str,
    end_date: str,
) -> None:
    cache_path = client.cache_root / "submissions" / f"CIK{issuer.cik}.json"
    url = f"{SUBMISSIONS_ROOT}/CIK{issuer.cik}.json"
    data = client.get_json(url, cache_path)
    response_cik = cik10(data.get("cik"))
    if response_cik and response_cik != issuer.cik:
        raise BuildError(f"submission CIK mismatch: requested {issuer.cik}, received {response_cik}")
    issuer.submissions = data
    issuer.name = str(data.get("name") or issuer.name).strip()
    issuer.tickers = [str(item) for item in data.get("tickers") or []]
    issuer.exchanges = [str(item) for item in data.get("exchanges") or []]
    issuer.sic = str(data.get("sic") or "")
    issuer.country = country_from_submission(data)

    seen: set[str] = set()
    all_rows: list[dict[str, str]] = []

    def add_rows(filings: dict[str, Any]) -> None:
        for row in aligned_submission_rows(filings):
            accession = row["accessionNumber"]
            filed = row["filingDate"]
            if not accession or accession in seen or not start_date <= filed <= end_date:
                continue
            seen.add(accession)
            all_rows.append(row)

    filings_container = data.get("filings") or {}
    add_rows(filings_container.get("recent") or {})
    for segment in filings_container.get("files") or []:
        if not segment_overlaps(segment, start_date, end_date):
            continue
        filename = str(segment.get("name") or "")
        if not filename or not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", filename):
            raise BuildError(f"unsafe submissions-history filename: {filename!r}")
        history = client.get_json(
            f"{SUBMISSIONS_ROOT}/{filename}",
            client.cache_root / "submissions-history" / filename,
        )
        add_rows(history.get("filings", history))

    issuer.filing_rows = sorted(all_rows, key=lambda row: (row["filingDate"], row["accessionNumber"]))
    issuer.financing_rows = [
        row
        for row in issuer.filing_rows
        if is_financing_form(row["form"])
    ]


def is_financing_form(form: str) -> bool:
    upper = form.strip().upper()
    return (
        root_form(upper) in {"F-1", "F-3"}
        or upper.startswith("424B")
        or upper == "EFFECT"
    )


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def iter_local(element: ET.Element, name: str) -> Iterator[ET.Element]:
    for descendant in element.iter():
        if local_name(descendant) == name:
            yield descendant


def first_local(element: ET.Element, name: str) -> ET.Element | None:
    return next(iter_local(element, name), None)


def local_text(element: ET.Element, name: str, default: str = "") -> str:
    found = first_local(element, name)
    return (found.text or "").strip() if found is not None else default


def nested_value(element: ET.Element, container_name: str) -> str:
    container = first_local(element, container_name)
    return local_text(container, "value") if container is not None else ""


def bool_value(value: str) -> int:
    return int(value.strip().lower() in {"1", "true", "yes", "y"})


def number_value(value: str) -> float | None:
    cleaned = value.strip().replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_ownership_xml(
    raw: bytes,
    *,
    accession: str,
    filing_form: str,
    filed_date: str,
    expected_issuer_cik: str,
) -> tuple[list[FilingOwner], list[Transaction], dict[str, str]]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise BuildError(f"ownership XML parse failure for {accession}: {exc}") from exc
    if local_name(root) != "ownershipDocument":
        raise BuildError(f"unexpected XML root {local_name(root)!r} for {accession}")

    issuer_node = first_local(root, "issuer")
    if issuer_node is None:
        raise BuildError(f"ownership XML missing issuer: {accession}")
    xml_issuer_cik = cik10(local_text(issuer_node, "issuerCik"))
    if xml_issuer_cik and xml_issuer_cik != expected_issuer_cik:
        raise IssuerMismatch(
            f"ownership issuer mismatch for {accession}: {xml_issuer_cik} != {expected_issuer_cik}"
        )
    issuer_meta = {
        "cik": xml_issuer_cik or expected_issuer_cik,
        "name": local_text(issuer_node, "issuerName"),
        "ticker": local_text(issuer_node, "issuerTradingSymbol"),
    }
    clean_accession = accession.replace("-", "")
    agent_prefix = clean_accession[:10]
    owners: list[FilingOwner] = []
    for owner_node in iter_local(root, "reportingOwner"):
        owner_id = first_local(owner_node, "reportingOwnerId")
        relationship = first_local(owner_node, "reportingOwnerRelationship")
        owner_name = local_text(owner_id, "rptOwnerName") if owner_id is not None else ""
        owner_cik = cik10(local_text(owner_id, "rptOwnerCik")) if owner_id is not None else ""
        if not owner_cik:
            digest = hashlib.sha1(owner_name.casefold().encode("utf-8")).hexdigest()[:12]
            owner_cik = f"UNKNOWN:{digest}"
        owners.append(
            FilingOwner(
                accession=accession,
                form=filing_form,
                filed_date=filed_date,
                issuer_cik=issuer_meta["cik"],
                owner_cik=owner_cik,
                owner_name=owner_name or "Unknown reporting owner",
                is_director=bool_value(local_text(relationship, "isDirector")) if relationship is not None else 0,
                is_officer=bool_value(local_text(relationship, "isOfficer")) if relationship is not None else 0,
                is_ten_pct=bool_value(local_text(relationship, "isTenPercentOwner")) if relationship is not None else 0,
                officer_title=local_text(relationship, "officerTitle") if relationship is not None else "",
                agent_prefix=agent_prefix,
            )
        )
    if not owners:
        raise BuildError(f"ownership XML contains no reporting owner: {accession}")

    transactions: list[Transaction] = []
    for transaction_name in ("nonDerivativeTransaction", "derivativeTransaction"):
        for transaction_node in iter_local(root, transaction_name):
            transactions.append(
                Transaction(
                    accession=accession,
                    tx_code=local_text(transaction_node, "transactionCode"),
                    tx_date=nested_value(transaction_node, "transactionDate"),
                    shares=number_value(nested_value(transaction_node, "transactionShares")),
                    price=number_value(nested_value(transaction_node, "transactionPricePerShare")),
                    acquired_disposed=nested_value(
                        transaction_node, "transactionAcquiredDisposedCode"
                    ),
                    ownership_form=(
                        nested_value(transaction_node, "directOrIndirectOwnership")
                        or nested_value(transaction_node, "ownershipForm")
                    ),
                )
            )
    return owners, transactions, issuer_meta


def ownership_document(
    client: SecClient,
    issuer_cik: str,
    accession: str,
    primary_document: str,
) -> tuple[bytes, str]:
    accession_path = accession.replace("-", "")
    base_url = f"{ARCHIVES_ROOT}/data/{int(issuer_cik)}/{accession_path}/"
    safe_primary = Path(primary_document).name
    xml_cache = client.cache_root / "ownership" / f"{accession}.xml"

    if safe_primary and safe_primary.lower().endswith(".xml"):
        raw = client.get(
            urllib.parse.urljoin(base_url, safe_primary),
            xml_cache,
            accept="application/xml,text/xml,text/plain",
        )
        try:
            if local_name(ET.fromstring(raw)) == "ownershipDocument":
                return raw, urllib.parse.urljoin(base_url, safe_primary)
        except ET.ParseError:
            pass

    index_cache = client.cache_root / "filing-index" / f"{accession}.html"
    index_url = base_url
    index_raw = client.get(index_url, index_cache, accept="text/html")
    index_text = index_raw.decode("utf-8", errors="replace")
    candidates = re.findall(r"href=[\"']([^\"']+\.xml(?:\?[^\"']*)?)[\"']", index_text, re.I)
    candidates = sorted(
        dict.fromkeys(candidates),
        key=lambda value: (
            "ownership" not in value.casefold(),
            "xsl" in value.casefold(),
            len(value),
        ),
    )
    for candidate in candidates:
        parsed = urllib.parse.urlparse(candidate)
        candidate_name = Path(parsed.path).name
        if not candidate_name or "xsl" in parsed.path.casefold():
            continue
        candidate_url = urllib.parse.urljoin(base_url, candidate)
        raw = client.get(
            candidate_url,
            client.cache_root / "ownership-candidates" / f"{accession}-{candidate_name}",
            accept="application/xml,text/xml,text/plain",
        )
        try:
            if local_name(ET.fromstring(raw)) != "ownershipDocument":
                continue
        except ET.ParseError:
            continue
        atomic_write(xml_cache, raw)
        return raw, candidate_url
    raise BuildError(f"raw ownership XML not found for {accession}")


def probe_endpoints(client: SecClient, progress_path: Path) -> dict[str, Any]:
    index_url = f"{ARCHIVES_ROOT}/full-index/2026/QTR1/form.idx"
    index_raw = client.get(
        index_url,
        client.cache_root / "indexes" / "2026-QTR1-form.idx",
        accept="text/plain",
    )
    index_rows = sum(1 for _ in parse_form_index(index_raw))
    if index_rows < 100_000:
        raise BuildError(f"Q1 2026 form.idx probe returned only {index_rows:,} rows")

    scisparc_cik = "0001611746"
    data = client.get_json(
        f"{SUBMISSIONS_ROOT}/CIK{scisparc_cik}.json",
        client.cache_root / "submissions" / f"CIK{scisparc_cik}.json",
    )
    candidates = [
        row
        for row in aligned_submission_rows((data.get("filings") or {}).get("recent") or {})
        if row["filingDate"] == "2026-03-18"
        and row["form"] in {"3", "3/A"}
        and row["accessionNumber"].startswith("0001213900")
    ]
    matches: list[dict[str, str]] = []
    for row in candidates:
        raw, xml_url = ownership_document(
            client,
            scisparc_cik,
            row["accessionNumber"],
            row["primaryDocument"],
        )
        owners, _transactions, issuer_meta = parse_ownership_xml(
            raw,
            accession=row["accessionNumber"],
            filing_form=row["form"],
            filed_date=row["filingDate"],
            expected_issuer_cik=scisparc_cik,
        )
        if any("amitay" in owner.owner_name.casefold() and "weiss" in owner.owner_name.casefold() for owner in owners):
            matches.append(
                {
                    "accession": row["accessionNumber"],
                    "xml_url": xml_url,
                    "issuer": issuer_meta["name"],
                    "owner": next(owner.owner_name for owner in owners if "weiss" in owner.owner_name.casefold()),
                }
            )
    if not matches:
        raise BuildError(
            "SciSparc smoke test failed: no 2026-03-18 Amitay Weiss Form 3 with agent prefix 0001213900"
        )
    result = {
        "form_index_url": index_url,
        "form_index_rows": index_rows,
        "submissions_url": f"{SUBMISSIONS_ROOT}/CIK{scisparc_cik}.json",
        "scisparc_match": matches[0],
    }
    append_progress(
        progress_path,
        "endpoint_probe",
        status="passed",
        form_index_rows=index_rows,
        scisparc_accession=matches[0]["accession"],
        owner=matches[0]["owner"],
    )
    return result


def collect_filings(
    client: SecClient,
    issuers: dict[str, IssuerState],
    *,
    fpi_start_date: str,
    act_date: str,
    end_date: str,
    progress_path: Path,
    limit_issuers: int | None,
) -> tuple[list[FilingOwner], list[Transaction], dict[str, str]]:
    filing_owners: list[FilingOwner] = []
    transactions: list[Transaction] = []
    xml_urls: dict[str, str] = {}
    ordered_issuers = sorted(issuers.values(), key=lambda issuer: int(issuer.cik))
    if limit_issuers:
        ordered_issuers = ordered_issuers[:limit_issuers]
    ownership_accessions = 0
    off_target_filings = 0
    parse_errors: list[str] = []

    for issuer_index, issuer in enumerate(ordered_issuers, 1):
        load_issuer_submissions(client, issuer, fpi_start_date, end_date)
        ownership_rows = [
            row
            for row in issuer.filing_rows
            if act_date <= row["filingDate"] <= end_date and row["form"].upper() in OWNERSHIP_FORMS
        ]
        for row in ownership_rows:
            accession = row["accessionNumber"]
            try:
                raw, xml_url = ownership_document(
                    client, issuer.cik, accession, row["primaryDocument"]
                )
                owners, txs, issuer_meta = parse_ownership_xml(
                    raw,
                    accession=accession,
                    filing_form=row["form"].upper(),
                    filed_date=row["filingDate"],
                    expected_issuer_cik=issuer.cik,
                )
            except IssuerMismatch:
                off_target_filings += 1
                continue
            except BuildError as exc:
                parse_errors.append(str(exc))
                continue
            ownership_accessions += 1
            filing_owners.extend(owners)
            transactions.extend(txs)
            xml_urls[accession] = xml_url
            if issuer_meta["name"]:
                issuer.name = issuer_meta["name"]
            ticker = issuer_meta["ticker"]
            if ticker and ticker not in issuer.tickers:
                issuer.tickers.append(ticker)
        if issuer_index % 100 == 0 or issuer_index == len(ordered_issuers):
            append_progress(
                progress_path,
                "submissions_xml",
                issuers_processed=issuer_index,
                issuers_total=len(ordered_issuers),
                ownership_accessions=ownership_accessions,
                filing_owner_rows=len(filing_owners),
                transactions=len(transactions),
                off_target_filings=off_target_filings,
                parse_errors=len(parse_errors),
            )
    if parse_errors:
        sample = " | ".join(parse_errors[:10])
        raise BuildError(
            f"{len(parse_errors):,} ownership filings failed XML parsing; refusing incomplete DB. Sample: {sample}"
        )
    return filing_owners, transactions, xml_urls


def create_database(
    db_path: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
    transactions: list[Transaction],
    *,
    run_timestamp: str,
    fpi_start_date: str,
    act_date: str,
    end_date: str,
    index_count: int,
    probe_status: str,
    complete: int,
) -> dict[str, int]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE issuers (
            cik TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tickers TEXT NOT NULL,
            sic TEXT,
            country TEXT,
            fpi_evidence TEXT NOT NULL
        );
        CREATE TABLE persons (
            cik TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE filings (
            accession TEXT NOT NULL,
            form TEXT NOT NULL,
            filed_date TEXT NOT NULL,
            issuer_cik TEXT NOT NULL REFERENCES issuers(cik),
            owner_cik TEXT NOT NULL REFERENCES persons(cik),
            is_director INTEGER NOT NULL CHECK (is_director IN (0, 1)),
            is_officer INTEGER NOT NULL CHECK (is_officer IN (0, 1)),
            is_ten_pct INTEGER NOT NULL CHECK (is_ten_pct IN (0, 1)),
            officer_title TEXT,
            agent_prefix TEXT NOT NULL,
            PRIMARY KEY (accession, owner_cik)
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            accession TEXT NOT NULL,
            tx_code TEXT,
            tx_date TEXT,
            shares REAL,
            price REAL,
            acquired_disposed TEXT,
            ownership_form TEXT
        );
        CREATE TABLE build_meta (
            run_timestamp TEXT PRIMARY KEY,
            fpi_start_date TEXT NOT NULL,
            act_start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            issuer_count INTEGER NOT NULL,
            person_count INTEGER NOT NULL,
            filing_row_count INTEGER NOT NULL,
            unique_filing_count INTEGER NOT NULL,
            transaction_count INTEGER NOT NULL,
            index_file_count INTEGER NOT NULL,
            probe_status TEXT NOT NULL,
            complete INTEGER NOT NULL CHECK (complete IN (0, 1))
        );
        CREATE INDEX filings_issuer_date_idx ON filings(issuer_cik, filed_date);
        CREATE INDEX filings_owner_date_idx ON filings(owner_cik, filed_date);
        CREATE INDEX filings_agent_date_idx ON filings(agent_prefix, filed_date);
        CREATE INDEX transactions_accession_idx ON transactions(accession);
        """
    )
    issuer_rows = [
        (
            issuer.cik,
            issuer.name,
            json.dumps(sorted(set(issuer.tickers)), ensure_ascii=False, separators=(",", ":")),
            issuer.sic,
            issuer.country,
            json.dumps(sorted(issuer.evidence), separators=(",", ":")),
        )
        for issuer in sorted(issuers.values(), key=lambda item: item.cik)
    ]
    connection.executemany("INSERT INTO issuers VALUES (?, ?, ?, ?, ?, ?)", issuer_rows)

    person_names: dict[str, str] = {}
    for filing in filing_owners:
        person_names[filing.owner_cik] = filing.owner_name
    connection.executemany(
        "INSERT INTO persons VALUES (?, ?)", sorted(person_names.items())
    )
    connection.executemany(
        "INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row.accession,
                row.form,
                row.filed_date,
                row.issuer_cik,
                row.owner_cik,
                row.is_director,
                row.is_officer,
                row.is_ten_pct,
                row.officer_title,
                row.agent_prefix,
            )
            for row in filing_owners
        ],
    )
    connection.executemany(
        """
        INSERT INTO transactions(
            accession, tx_code, tx_date, shares, price, acquired_disposed, ownership_form
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.accession,
                row.tx_code,
                row.tx_date,
                row.shares,
                row.price,
                row.acquired_disposed,
                row.ownership_form,
            )
            for row in transactions
        ],
    )
    unique_filings = len({row.accession for row in filing_owners})
    counts = {
        "issuers": len(issuers),
        "persons": len(person_names),
        "filing_rows": len(filing_owners),
        "unique_filings": unique_filings,
        "transactions": len(transactions),
    }
    connection.execute(
        "INSERT INTO build_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_timestamp,
            fpi_start_date,
            act_date,
            end_date,
            counts["issuers"],
            counts["persons"],
            counts["filing_rows"],
            counts["unique_filings"],
            counts["transactions"],
            index_count,
            probe_status,
            complete,
        ),
    )
    connection.commit()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    output = sqlite3.connect(db_path)
    try:
        connection.backup(output)
        output.execute("PRAGMA journal_mode = WAL")
        output.execute("PRAGMA optimize")
        output.commit()
    finally:
        output.close()
        connection.close()
    return counts


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> int:
    materialized = list(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)
    return len(materialized)


def generate_clusters(
    output_root: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[FilingOwner]] = defaultdict(list)
    for row in filing_owners:
        grouped[row.owner_cik].append(row)
    rows: list[dict[str, Any]] = []
    for owner_cik, filings in grouped.items():
        issuer_ciks = sorted({row.issuer_cik for row in filings})
        if len(issuer_ciks) < 2:
            continue
        roles: set[str] = set()
        for row in filings:
            if row.is_director:
                roles.add("Director")
            if row.is_officer:
                roles.add(row.officer_title or "Officer")
            if row.is_ten_pct:
                roles.add("10% Owner")
        titles = [row.officer_title for row in filings if row.officer_title]
        issuer_list = [f"{issuers[cik].name} [{cik}]" for cik in issuer_ciks]
        rows.append(
            {
                "owner_cik": owner_cik,
                "owner_name": filings[0].owner_name,
                "issuer_count": len(issuer_ciks),
                "filing_count": len({row.accession for row in filings}),
                "form3_count": sum(row.form.startswith("3") for row in filings),
                "form4_count": sum(row.form.startswith("4") for row in filings),
                "form5_count": sum(row.form.startswith("5") for row in filings),
                "roles": "; ".join(sorted(roles)),
                "chairman_flag": int(any("chair" in title.casefold() for title in titles)),
                "director_flag": int(any(row.is_director for row in filings)),
                "agent_prefixes": "; ".join(sorted({row.agent_prefix for row in filings})),
                "issuer_list": "; ".join(issuer_list),
            }
        )
    rows.sort(
        key=lambda row: (-int(row["issuer_count"]), -int(row["form4_count"]), str(row["owner_name"]).casefold())
    )
    write_csv(
        output_root / "clusters.csv",
        [
            "owner_cik",
            "owner_name",
            "issuer_count",
            "filing_count",
            "form3_count",
            "form4_count",
            "form5_count",
            "roles",
            "chairman_flag",
            "director_flag",
            "agent_prefixes",
            "issuer_list",
        ],
        rows,
    )
    return rows


def generate_sync_batches(
    output_root: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    owner_groups: dict[tuple[str, str], list[FilingOwner]] = defaultdict(list)
    agent_groups: dict[tuple[str, str], list[FilingOwner]] = defaultdict(list)
    for row in filing_owners:
        owner_groups[(row.filed_date, row.owner_cik)].append(row)
        agent_groups[(row.filed_date, row.agent_prefix)].append(row)

    for (filed_date, owner_cik), rows in owner_groups.items():
        issuer_ciks = sorted({row.issuer_cik for row in rows})
        if len(issuer_ciks) < 2:
            continue
        batches.append(
            {
                "filed_date": filed_date,
                "batch_type": "owner_cohort",
                "batch_key": owner_cik,
                "issuer_count": len(issuer_ciks),
                "owner_count": 1,
                "filing_count": len({row.accession for row in rows}),
                "agent_prefixes": "; ".join(sorted({row.agent_prefix for row in rows})),
                "owners": f"{rows[0].owner_name} [{owner_cik}]",
                "issuers": "; ".join(f"{issuers[cik].name} [{cik}]" for cik in issuer_ciks),
                "accessions": "; ".join(sorted({row.accession for row in rows})),
            }
        )
    for (filed_date, agent_prefix), rows in agent_groups.items():
        issuer_ciks = sorted({row.issuer_cik for row in rows})
        if len(issuer_ciks) < 2:
            continue
        owners = sorted({(row.owner_name, row.owner_cik) for row in rows})
        batches.append(
            {
                "filed_date": filed_date,
                "batch_type": "agent_prefix",
                "batch_key": agent_prefix,
                "issuer_count": len(issuer_ciks),
                "owner_count": len(owners),
                "filing_count": len({row.accession for row in rows}),
                "agent_prefixes": agent_prefix,
                "owners": "; ".join(f"{name} [{cik}]" for name, cik in owners),
                "issuers": "; ".join(f"{issuers[cik].name} [{cik}]" for cik in issuer_ciks),
                "accessions": "; ".join(sorted({row.accession for row in rows})),
            }
        )
    batches.sort(
        key=lambda row: (
            -int(row["issuer_count"]),
            -int(row["filing_count"]),
            str(row["filed_date"]),
            str(row["batch_type"]),
        )
    )
    write_csv(
        output_root / "sync_batches.csv",
        [
            "filed_date",
            "batch_type",
            "batch_key",
            "issuer_count",
            "owner_count",
            "filing_count",
            "agent_prefixes",
            "owners",
            "issuers",
            "accessions",
        ],
        batches,
    )
    return batches


def generate_late_filers(
    output_root: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
    act_date: str,
) -> list[dict[str, Any]]:
    act = date.fromisoformat(act_date)
    rows: list[dict[str, Any]] = []
    for filing in filing_owners:
        if not filing.form.startswith("3"):
            continue
        filed = date.fromisoformat(filing.filed_date)
        days_after = (filed - act).days
        issuer = issuers[filing.issuer_cik]
        pre_act = issuer.pre_act_evidence
        if days_after <= 30 or not pre_act:
            continue
        rows.append(
            {
                "filed_date": filing.filed_date,
                "days_after_act": days_after,
                "accession": filing.accession,
                "form": filing.form,
                "issuer_cik": issuer.cik,
                "issuer_name": issuer.name,
                "owner_cik": filing.owner_cik,
                "owner_name": filing.owner_name,
                "roles": role_label(filing),
                "officer_title": filing.officer_title,
                "pre_act_fpi_forms": "; ".join(sorted({form for form, _filed in pre_act})),
                "earliest_pre_act_fpi_filing": pre_act[0][1],
                "agent_prefix": filing.agent_prefix,
            }
        )
    rows.sort(key=lambda row: (-int(row["days_after_act"]), str(row["issuer_name"]), str(row["owner_name"])))
    write_csv(
        output_root / "late_filers.csv",
        [
            "filed_date",
            "days_after_act",
            "accession",
            "form",
            "issuer_cik",
            "issuer_name",
            "owner_cik",
            "owner_name",
            "roles",
            "officer_title",
            "pre_act_fpi_forms",
            "earliest_pre_act_fpi_filing",
            "agent_prefix",
        ],
        rows,
    )
    return rows


def role_label(filing: FilingOwner) -> str:
    roles: list[str] = []
    if filing.is_director:
        roles.append("Director")
    if filing.is_officer:
        roles.append(filing.officer_title or "Officer")
    if filing.is_ten_pct:
        roles.append("10% Owner")
    return "; ".join(roles)


def generate_never_filers(
    output_root: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
) -> list[dict[str, Any]]:
    active_ciks = {row.issuer_cik for row in filing_owners}
    rows: list[dict[str, Any]] = []
    for issuer in issuers.values():
        if issuer.cik in active_ciks:
            continue
        forms = Counter(row["form"].upper() for row in issuer.financing_rows)
        f1_f3_424 = sum(
            count
            for form, count in forms.items()
            if root_form(form) in {"F-1", "F-3"} or form.startswith("424B")
        )
        financing_count = len(issuer.financing_rows)
        priority_score = f1_f3_424 * 4 + financing_count + int(bool(issuer.tickers))
        rows.append(
            {
                "priority_score": priority_score,
                "issuer_cik": issuer.cik,
                "issuer_name": issuer.name,
                "tickers": "; ".join(sorted(set(issuer.tickers))),
                "exchanges": "; ".join(sorted(set(issuer.exchanges))),
                "sic": issuer.sic,
                "country": issuer.country,
                "fpi_evidence": "; ".join(sorted(issuer.evidence)),
                "financing_filing_count": financing_count,
                "f1_f3_424_count": f1_f3_424,
                "financing_forms": "; ".join(f"{form}({count})" for form, count in sorted(forms.items())),
                "latest_financing_date": max((row["filingDate"] for row in issuer.financing_rows), default=""),
                "small_cap_proxy": "financing_intensity" if f1_f3_424 else "unscored",
            }
        )
    rows.sort(
        key=lambda row: (-int(row["priority_score"]), str(row["issuer_name"]).casefold())
    )
    write_csv(
        output_root / "never_filers.csv",
        [
            "priority_score",
            "issuer_cik",
            "issuer_name",
            "tickers",
            "exchanges",
            "sic",
            "country",
            "fpi_evidence",
            "financing_filing_count",
            "f1_f3_424_count",
            "financing_forms",
            "latest_financing_date",
            "small_cap_proxy",
        ],
        rows,
    )
    return rows


def generate_hot_form4(
    output_root: Path,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filing in filing_owners:
        if not filing.form.startswith("4"):
            continue
        issuer = issuers[filing.issuer_cik]
        form4_date = date.fromisoformat(filing.filed_date)
        for capital in issuer.financing_rows:
            capital_form = capital["form"].upper()
            if capital_form not in HOT_CAPITAL_FORMS:
                continue
            delta = (form4_date - date.fromisoformat(capital["filingDate"])).days
            if abs(delta) > 30:
                continue
            rows.append(
                {
                    "issuer_cik": issuer.cik,
                    "issuer_name": issuer.name,
                    "tickers": "; ".join(sorted(set(issuer.tickers))),
                    "country": issuer.country,
                    "form4_accession": filing.accession,
                    "form4_form": filing.form,
                    "form4_date": filing.filed_date,
                    "owner_cik": filing.owner_cik,
                    "owner_name": filing.owner_name,
                    "roles": role_label(filing),
                    "capital_accession": capital["accessionNumber"],
                    "capital_form": capital_form,
                    "capital_date": capital["filingDate"],
                    "days_form4_minus_capital": delta,
                    "absolute_days": abs(delta),
                    "agent_prefix": filing.agent_prefix,
                }
            )
    rows.sort(
        key=lambda row: (
            int(row["absolute_days"]),
            str(row["issuer_name"]).casefold(),
            str(row["form4_date"]),
        )
    )
    write_csv(
        output_root / "hot_form4.csv",
        [
            "issuer_cik",
            "issuer_name",
            "tickers",
            "country",
            "form4_accession",
            "form4_form",
            "form4_date",
            "owner_cik",
            "owner_name",
            "roles",
            "capital_accession",
            "capital_form",
            "capital_date",
            "days_form4_minus_capital",
            "absolute_days",
            "agent_prefix",
        ],
        rows,
    )
    return rows


def escalation_candidates(
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
    clusters: list[dict[str, Any]],
    hot_form4: list[dict[str, Any]],
    never_filers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_issuer: dict[str, list[FilingOwner]] = defaultdict(list)
    for row in filing_owners:
        by_issuer[row.issuer_cik].append(row)
    clustered_owners = {str(row["owner_cik"]) for row in clusters}
    hot_counts = Counter(str(row["issuer_cik"]) for row in hot_form4)
    never_by_cik = {str(row["issuer_cik"]): row for row in never_filers}
    candidates: list[dict[str, Any]] = []
    for issuer in issuers.values():
        filings = by_issuer.get(issuer.cik, [])
        form4_count = len({row.accession for row in filings if row.form.startswith("4")})
        form3_count = len({row.accession for row in filings if row.form.startswith("3")})
        amendment_count = len({row.accession for row in filings if row.form.endswith("/A")})
        finance_count = len(issuer.financing_rows)
        cluster_count = len({row.owner_cik for row in filings if row.owner_cik in clustered_owners})
        hot_count = hot_counts[issuer.cik]
        never_priority = int(never_by_cik.get(issuer.cik, {}).get("priority_score", 0))
        score = (
            form4_count * 5
            + min(hot_count, 10) * 7
            + min(finance_count, 12) * 2
            + cluster_count * 4
            + amendment_count * 2
            + never_priority
        )
        if score <= 0:
            continue
        reasons: list[str] = []
        if hot_count:
            reasons.append(f"{hot_count} Form 4/financing-window match(es)")
        if form4_count:
            reasons.append(f"{form4_count} post-Act Form 4 filing(s)")
        if finance_count:
            reasons.append(f"{finance_count} 2025-26 financing/resale filing(s)")
        if cluster_count:
            reasons.append(f"{cluster_count} cross-issuer insider(s)")
        if amendment_count:
            reasons.append(f"{amendment_count} ownership amendment(s)")
        if issuer.cik in never_by_cik:
            reasons.append("zero Section 16 filings despite likely-FPI evidence")
        candidates.append(
            {
                "score": score,
                "issuer_cik": issuer.cik,
                "issuer_name": issuer.name,
                "tickers": ", ".join(issuer.tickers),
                "country": issuer.country,
                "form3_count": form3_count,
                "form4_count": form4_count,
                "hot_count": hot_count,
                "cluster_count": cluster_count,
                "finance_count": finance_count,
                "reason": "; ".join(reasons),
            }
        )
    candidates.sort(key=lambda row: (-int(row["score"]), str(row["issuer_name"]).casefold()))
    return candidates[:10]


def summarize_counter(values: Iterable[str], limit: int = 5) -> str:
    counter = Counter(value or "Unknown" for value in values)
    return ", ".join(f"{value} ({count})" for value, count in counter.most_common(limit)) or "none"


def generate_report(
    output_root: Path,
    *,
    issuers: dict[str, IssuerState],
    filing_owners: list[FilingOwner],
    transactions: list[Transaction],
    clusters: list[dict[str, Any]],
    sync_batches: list[dict[str, Any]],
    late_filers: list[dict[str, Any]],
    never_filers: list[dict[str, Any]],
    hot_form4: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    probe_info: dict[str, Any],
    index_manifest: list[dict[str, str]],
    client: SecClient,
    run_timestamp: str,
    fpi_start_date: str,
    act_date: str,
    end_date: str,
) -> None:
    unique_filings = len({row.accession for row in filing_owners})
    form_counts = Counter(row.form for row in filing_owners)
    active_issuers = len({row.issuer_cik for row in filing_owners})
    unique_people = len({row.owner_cik for row in filing_owners})
    match = probe_info["scisparc_match"]
    lines = [
        "# HFIA Post-Act Universe — 2026-07-15",
        "",
        f"Build timestamp: `{run_timestamp}`",
        "",
        "## Methodology",
        "",
        f"The likely-foreign-private-issuer screening universe was reconstructed from SEC quarterly `form.idx` files for {fpi_start_date} through {end_date}. An issuer enters the universe when a 6-K, 20-F, or 40-F (including amendments normalized to the root form) appears in that interval. This is the HFIA investigation's screening heuristic, not a legal conclusion about issuer status.",
        "",
        f"For every screened issuer, the builder read the issuer submissions JSON plus every overlapping submissions-history segment, selected Forms 3/4/5 and amendments filed from {act_date} through {end_date}, and parsed the raw `ownershipDocument` XML. Amendments remain separate filings. Multi-owner XML filings are expanded to one `filings` row per reporting owner while `transactions` are stored once per accession.",
        "",
        "## Endpoint probes",
        "",
        f"- Full-index probe: `{probe_info['form_index_url']}` parsed {int(probe_info['form_index_rows']):,} filing rows.",
        f"- Issuer-stream probe: `{probe_info['submissions_url']}` exposed SciSparc ownership filings in the issuer submissions stream.",
        f"- XML smoke test: `{match['accession']}` is the 2026-03-18 SciSparc Form 3 for {match['owner']}; raw ownership XML parsed successfully from `{match['xml_url']}`. The accession prefix is `0001213900`.",
        "",
        "## Row counts",
        "",
        f"- Likely-FPI issuers: **{len(issuers):,}**",
        f"- Issuers with at least one post-Act ownership filing: **{active_issuers:,}**",
        f"- Unique ownership accessions: **{unique_filings:,}**",
        f"- Filing-owner rows: **{len(filing_owners):,}**",
        f"- Reporting owners: **{unique_people:,}**",
        f"- Parsed transaction rows: **{len(transactions):,}**",
        f"- Forms: {', '.join(f'{form}={count:,}' for form, count in sorted(form_counts.items())) or 'none'}",
        f"- Cross-issuer reporting-owner clusters: **{len(clusters):,}**",
        f"- Same-day multi-issuer synchronization batches: **{len(sync_batches):,}**",
        f"- Form 3 filing-owner rows more than 30 days after the Act with pre-Act FPI history: **{len(late_filers):,}**",
        f"- Likely-FPI issuers with zero post-Act Section 16 filings: **{len(never_filers):,}**",
        f"- Form 4 / financing-window matches: **{len(hot_form4):,}**",
        f"- SEC network requests: **{client.network_requests:,}**; cache hits: **{client.cache_hits:,}**; retries: **{client.retries:,}**",
        "",
        "## Top 20 cross-issuer clusters",
        "",
    ]
    for index, row in enumerate(clusters[:20], 1):
        lines.append(
            f"### {index}. {row['owner_name']} — {row['issuer_count']} issuers"
        )
        lines.append("")
        lines.append(
            f"CIK `{row['owner_cik']}`; roles: {row['roles'] or 'not specified'}; Form 3/4/5 counts: {row['form3_count']}/{row['form4_count']}/{row['form5_count']}. Chairman flag: {row['chairman_flag']}; director flag: {row['director_flag']}."
        )
        if int(row["form4_count"]):
            characterization = "This cluster includes post-Act change filings, making it more than a synchronized initial-compliance footprint."
        elif int(row["chairman_flag"]):
            characterization = "Chair-related titles make this a governance-network cluster; current records show initial disclosures rather than post-Act changes."
        else:
            characterization = "The observed pattern is primarily a cross-issuer initial-disclosure footprint and should be paired with financing and related-party evidence before escalation."
        lines.append(
            f"Issuers: {row['issuer_list']}. {characterization}"
        )
        lines.append("")

    late_agents = summarize_counter(str(row["agent_prefix"]) for row in late_filers)
    never_countries = summarize_counter(str(row["country"]) for row in never_filers)
    financed_never = [row for row in never_filers if int(row["f1_f3_424_count"]) > 0]
    lines.extend(
        [
            "## Late-filer and never-filer patterns",
            "",
            f"Late Form 3 rows are concentrated among these filing-agent prefixes: {late_agents}. This is a timing screen only: the Act date is used as a common reference point, and the issuer's pre-Act 20-F/6-K history is only a proxy that the disclosed director/officer population already existed.",
            "",
            f"Of {len(never_filers):,} zero-filer issuers, {len(financed_never):,} had F-1/F-3/424B activity in 2025-2026. Leading reported countries/territories are {never_countries}. `never_filers.csv` ranks financing intensity, because EDGAR submissions do not supply market capitalization; the `small_cap_proxy` field must not be read as measured market cap.",
            "",
            "## Ten highest-value escalation candidates",
            "",
        ]
    )
    for index, row in enumerate(candidates, 1):
        ticker = f" ({row['tickers']})" if row["tickers"] else ""
        lines.append(
            f"{index}. **{row['issuer_name']}**{ticker}, CIK `{row['issuer_cik']}` — score {row['score']}. {row['reason']}."
        )
    lines.extend(
        [
            "",
            "The ranking operationalizes the profile doctrine: financing-window Form 4 matches receive the most weight, followed by repeated post-Act changes, cross-issuer insiders, resale/registration activity, and amendments. It is a commissioning screen, not an allegation or finding of misconduct.",
            "",
            "## Data-quality caveats",
            "",
            "- `6-K`/`20-F`/`40-F` history is a likely-FPI heuristic. Publication candidates require direct status confirmation.",
            "- SEC full indexes for the current quarter ordinarily run through the previous business day. The builder applies an inclusive end-date filter but cannot include filings absent from the downloaded index at run time.",
            "- Submission history is deduplicated by accession across recent and overlapping historical JSON segments.",
            "- The filing table's natural key is `(accession, owner_cik)` because a single ownership document can identify more than one reporting owner. Unique accession counts are reported separately.",
            "- Form 3 holdings are not transactions and therefore are not inserted into `transactions`; Form 4/5 non-derivative and derivative transaction rows are included.",
            "- Country is taken from the SEC submission business/mailing address (or incorporation code fallback), so it is not a normalized legal domicile field.",
            "- An accession's first ten digits are a useful filing-agent/cohort fingerprint but do not by themselves identify counsel, a service provider, or coordinated conduct.",
            "- Form 3 'late' status here means more than 30 days after 2026-03-18, not a legal timeliness determination. Appointment dates and individual statutory deadlines were not independently established.",
            "- Financing-intensity ranking is not a substitute for market capitalization. Small-cap status should be added from a dated market-data source before publication.",
            "- Names are preserved as filed. Owner CIK is the cluster key; spelling variants without a common CIK are not automatically merged.",
            "",
            "## Index manifest",
            "",
        ]
    )
    for entry in index_manifest:
        lines.append(
            f"- {entry['period']}: {int(entry['rows']):,} rows, {int(entry['fpi_rows']):,} qualifying form rows, {int(entry['bytes']):,} bytes — `{entry['url']}`"
        )
    (output_root / "report-universe.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_outputs(
    db_path: Path,
    output_root: Path,
    expected_counts: dict[str, int],
) -> None:
    uri = f"file:{urllib.parse.quote(str(db_path))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        table_counts = {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("issuers", "persons", "filings", "transactions", "build_meta")
        }
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        complete = connection.execute("SELECT complete FROM build_meta ORDER BY run_timestamp DESC LIMIT 1").fetchone()[0]
    finally:
        connection.close()
    if integrity != "ok" or complete != 1:
        raise BuildError(f"database audit failed: integrity={integrity!r}, complete={complete!r}")
    checks = {
        "issuers": expected_counts["issuers"],
        "persons": expected_counts["persons"],
        "filings": expected_counts["filing_rows"],
        "transactions": expected_counts["transactions"],
    }
    for table, expected in checks.items():
        if table_counts[table] != expected:
            raise BuildError(f"database row-count mismatch for {table}: {table_counts[table]} != {expected}")
    required = [
        "clusters.csv",
        "sync_batches.csv",
        "late_filers.csv",
        "never_filers.csv",
        "hot_form4.csv",
        "report-universe.md",
    ]
    for filename in required:
        path = output_root / filename
        if not path.exists() or path.stat().st_size == 0:
            raise BuildError(f"required deliverable missing or empty: {path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--fpi-start", default="2025-01-01")
    parser.add_argument("--act-date", default="2026-03-18")
    parser.add_argument("--end-date", default="2026-07-15")
    parser.add_argument("--requests-per-second", type=float, default=7.5)
    parser.add_argument("--offline", action="store_true", help="use cache only; fail on any miss")
    parser.add_argument("--refresh", action="store_true", help="replace cached SEC responses")
    parser.add_argument("--limit-issuers", type=int, help="debug only; produces incomplete metadata")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for value in (args.fpi_start, args.act_date, args.end_date):
        date.fromisoformat(value)
    if not args.fpi_start <= args.act_date <= args.end_date:
        raise BuildError("date range must satisfy fpi_start <= act_date <= end_date")
    args.output_root.mkdir(parents=True, exist_ok=True)
    cache_root = args.output_root / "cache"
    progress_path = args.output_root / "codex-progress.log"
    run_timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    append_progress(progress_path, "build", status="started", run_timestamp=run_timestamp)

    client = SecClient(
        cache_root,
        requests_per_second=args.requests_per_second,
        offline=args.offline,
        refresh=args.refresh,
    )
    probe_info = probe_endpoints(client, progress_path)
    issuers, index_manifest = build_fpi_universe(
        client, args.fpi_start, args.end_date, progress_path
    )
    filing_owners, transactions, _xml_urls = collect_filings(
        client,
        issuers,
        fpi_start_date=args.fpi_start,
        act_date=args.act_date,
        end_date=args.end_date,
        progress_path=progress_path,
        limit_issuers=args.limit_issuers,
    )
    if args.limit_issuers:
        raise BuildError(
            "debug --limit-issuers run completed collection but will not write final deliverables"
        )
    if not filing_owners:
        raise BuildError("no post-Act ownership filings found")
    unique_filing_count = len({row.accession for row in filing_owners})
    if not 8_000 <= unique_filing_count <= 60_000:
        raise BuildError(
            "ownership filing count is outside the expected safety range: "
            f"8,000-60,000 expected, observed {unique_filing_count:,}"
        )

    clusters = generate_clusters(args.output_root, issuers, filing_owners)
    sync_batches = generate_sync_batches(args.output_root, issuers, filing_owners)
    late_filers = generate_late_filers(args.output_root, issuers, filing_owners, args.act_date)
    never_filers = generate_never_filers(args.output_root, issuers, filing_owners)
    hot_form4 = generate_hot_form4(args.output_root, issuers, filing_owners)
    candidates = escalation_candidates(
        issuers, filing_owners, clusters, hot_form4, never_filers
    )
    append_progress(
        progress_path,
        "analytics",
        clusters=len(clusters),
        sync_batches=len(sync_batches),
        late_filers=len(late_filers),
        never_filers=len(never_filers),
        hot_form4=len(hot_form4),
    )
    generate_report(
        args.output_root,
        issuers=issuers,
        filing_owners=filing_owners,
        transactions=transactions,
        clusters=clusters,
        sync_batches=sync_batches,
        late_filers=late_filers,
        never_filers=never_filers,
        hot_form4=hot_form4,
        candidates=candidates,
        probe_info=probe_info,
        index_manifest=index_manifest,
        client=client,
        run_timestamp=run_timestamp,
        fpi_start_date=args.fpi_start,
        act_date=args.act_date,
        end_date=args.end_date,
    )
    counts = create_database(
        args.db,
        issuers,
        filing_owners,
        transactions,
        run_timestamp=run_timestamp,
        fpi_start_date=args.fpi_start,
        act_date=args.act_date,
        end_date=args.end_date,
        index_count=len(index_manifest),
        probe_status="passed",
        complete=1,
    )
    audit_outputs(args.db, args.output_root, counts)
    append_progress(
        progress_path,
        "build",
        status="complete",
        issuers=counts["issuers"],
        unique_filings=counts["unique_filings"],
        filing_rows=counts["filing_rows"],
        persons=counts["persons"],
        transactions=counts["transactions"],
        clusters=len(clusters),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BuildError, ValueError) as exc:
        try:
            error_args = parse_args()
            append_progress(
                error_args.output_root / "codex-progress.log",
                "build",
                status="failed",
                error=type(exc).__name__,
                detail=str(exc)[:300],
            )
        except (OSError, SystemExit):
            pass
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
