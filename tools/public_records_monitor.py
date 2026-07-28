#!/usr/bin/env python3
"""Catalog-backed source sentinel and drift monitor for public records.

The monitor has no scheduler or independent access policy. ``run`` accepts
explicit source IDs, reads each current acquisition decision from
``PublicRecordsCatalog``, invokes only a visible registered probe handler, and
appends observations to the catalog's immutable probe history.

Usage:
    uv run python tools/public_records_monitor.py plan
    uv run python tools/public_records_monitor.py run us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py history us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py diff us-nc-onemap-parcels
    uv run python tools/public_records_monitor.py record SOURCE_ID --status ok ...
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_bulk import (
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
    )
    from tools.public_records_catalog import (
        DEFAULT_DB_PATH,
        PROBE_STATUSES,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
    from tools.public_records_contract import ResultStatus, sha256_fingerprint
    from tools.public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
    )
    from tools.query_massgis_property import (
        MANIFEST_FIELDS as MASSGIS_MANIFEST_FIELDS,
        MANIFEST_LAYER_URL as MASSGIS_MANIFEST_LAYER_URL,
    )
    from tools.query_nc_property import (
        LAYER_URL as NC_ONEMAP_LAYER_URL,
        OUT_FIELDS as NC_ONEMAP_FIELDS,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_bulk import (
        BulkArtifact,
        BulkSourceError,
        BulkTransferClient,
    )
    from public_records_catalog import (
        DEFAULT_DB_PATH,
        PROBE_STATUSES,
        CatalogError,
        PublicRecordsCatalog,
        acquisition_result_status,
    )
    from public_records_contract import ResultStatus, sha256_fingerprint
    from public_records_http import (
        ArcGISRESTClient,
        PublicRecordsHTTPError,
        RetryPolicy,
    )
    from query_massgis_property import (
        MANIFEST_FIELDS as MASSGIS_MANIFEST_FIELDS,
        MANIFEST_LAYER_URL as MASSGIS_MANIFEST_LAYER_URL,
    )
    from query_nc_property import (
        LAYER_URL as NC_ONEMAP_LAYER_URL,
        OUT_FIELDS as NC_ONEMAP_FIELDS,
    )


MONITOR_ACTOR = "public_records_monitor"


@dataclass(frozen=True)
class ProbeContext:
    """Runtime values visible to every registered handler."""

    source_id: str
    catalog_decision: Mapping[str, Any]
    timeout: float
    max_attempts: int
    sample_bytes: int | None


@dataclass(frozen=True)
class ProbeObservation:
    """Normalized probe data accepted by the catalog."""

    status: str
    endpoint: str | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    schema_sha256: str | None = None
    artifact_sha256: str | None = None
    result_count: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in PROBE_STATUSES:
            raise ValueError(f"unsupported probe status: {self.status}")
        if self.status == "error" and not self.error:
            raise ValueError("error observations require an error message")
        if self.status == ResultStatus.NO_RESULTS.value and self.error:
            raise ValueError("no_results observations cannot contain an error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "endpoint": self.endpoint,
            "http_status": self.http_status,
            "latency_ms": self.latency_ms,
            "schema_sha256": self.schema_sha256,
            "artifact_sha256": self.artifact_sha256,
            "result_count": self.result_count,
            "details": dict(self.details),
            "error": self.error,
        }


ProbeHandler = Callable[[ProbeContext], ProbeObservation]


@dataclass(frozen=True)
class ProbeHandlerSpec:
    """Visible registration for one low-cost source sentinel."""

    source_id: str
    capability: str
    endpoint: str
    observation: str
    expected_requests: int
    sentinel_record_count: int
    sample_bytes: int | None
    handler: ProbeHandler

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "capability": self.capability,
            "endpoint": self.endpoint,
            "observation": self.observation,
            "expected_requests": self.expected_requests,
            "sentinel_record_count": self.sentinel_record_count,
            "sample_bytes": self.sample_bytes,
        }


def _catalog_interval(decision: Mapping[str, Any]) -> float:
    limits = decision.get("limits") or {}
    return float(limits.get("minimum_interval_seconds") or 0)


def probe_nc_onemap(context: ProbeContext) -> ProbeObservation:
    """Fetch one NC OneMap feature and its declared ArcGIS schema."""
    started = time.perf_counter()
    client = ArcGISRESTClient(
        NC_ONEMAP_LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = client.query(
        where="1=1",
        out_fields=NC_ONEMAP_FIELDS,
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    status = ResultStatus.OK.value if fetched.records else ResultStatus.NO_RESULTS.value
    return ProbeObservation(
        status=status,
        endpoint=client.query_url,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        result_count=len(fetched.records),
        details={
            "sentinel_query": "1=1",
            "requested_fields": list(NC_ONEMAP_FIELDS),
            "pages_fetched": fetched.pages_fetched,
            "requests_made": fetched.requests_made,
            "next_cursor": fetched.next_cursor,
            "warnings": list(fetched.warnings),
        },
    )


def probe_massgis(context: ProbeContext) -> ProbeObservation:
    """Fetch Gosnold's official manifest row and a bounded archive signature."""
    started = time.perf_counter()
    manifest_client = ArcGISRESTClient(
        MASSGIS_MANIFEST_LAYER_URL,
        page_size=1,
        max_records=1,
        timeout=context.timeout,
        minimum_interval=_catalog_interval(context.catalog_decision),
        retry_policy=RetryPolicy(max_attempts=context.max_attempts),
    )
    fetched = manifest_client.query(
        where="TOWN = 'GOSNOLD'",
        out_fields=MASSGIS_MANIFEST_FIELDS,
        requested_limit=1,
        max_records=1,
        return_geometry=False,
    )
    if not fetched.records:
        return ProbeObservation(
            status=ResultStatus.NO_RESULTS.value,
            endpoint=manifest_client.query_url,
            latency_ms=(time.perf_counter() - started) * 1000,
            schema_sha256=fetched.schema_fingerprint,
            result_count=0,
            details={
                "sentinel_query": "TOWN = 'GOSNOLD'",
                "pages_fetched": fetched.pages_fetched,
                "requests_made": fetched.requests_made,
            },
        )

    attributes = fetched.records[0].get("attributes")
    if not isinstance(attributes, Mapping):
        raise ValueError("MassGIS sentinel manifest feature lacks attributes")
    artifact_url = attributes.get("SHAPE_LINK")
    if not isinstance(artifact_url, str) or not artifact_url.strip():
        raise ValueError("MassGIS sentinel manifest lacks SHAPE_LINK")
    artifact = BulkArtifact.from_url(
        "shapefile",
        artifact_url.strip(),
        archive_format="zip",
    )
    sample_bytes = context.sample_bytes or 0
    artifact_probe = BulkTransferClient(
        timeout=context.timeout,
        max_attempts=context.max_attempts,
    ).probe(artifact, sample_bytes=sample_bytes)
    artifact_basis = {
        "url": artifact.url,
        "etag": artifact_probe.etag,
        "last_modified": artifact_probe.last_modified,
        "content_length": artifact_probe.content_length,
    }
    artifact_sha256 = artifact_probe.source_sha256 or sha256_fingerprint(
        artifact_basis
    )
    return ProbeObservation(
        status=ResultStatus.OK.value,
        endpoint=artifact.url,
        http_status=artifact_probe.http_status,
        latency_ms=(time.perf_counter() - started) * 1000,
        schema_sha256=fetched.schema_fingerprint,
        artifact_sha256=artifact_sha256,
        result_count=1,
        details={
            "manifest_endpoint": manifest_client.query_url,
            "sentinel_query": "TOWN = 'GOSNOLD'",
            "municipality": attributes.get("TOWN"),
            "town_id": attributes.get("TOWN_ID"),
            "assessor_fiscal_year": attributes.get("FY"),
            "artifact_url": artifact.url,
            "artifact_sha256_basis": (
                "source_sha256"
                if artifact_probe.source_sha256
                else "artifact_metadata_fingerprint"
            ),
            "content_length": artifact_probe.content_length,
            "etag": artifact_probe.etag,
            "last_modified": artifact_probe.last_modified,
            "accept_ranges": artifact_probe.accept_ranges,
            "sample_size": artifact_probe.sample_size,
            "sample_sha256": artifact_probe.sample_sha256,
            "signature_hex": artifact_probe.signature_hex,
            "format_hint": artifact_probe.format_hint,
        },
    )


# Central, inspectable registry. Adding a source requires an explicit entry here.
HANDLER_REGISTRY: dict[str, ProbeHandlerSpec] = {
    "us-nc-onemap-parcels": ProbeHandlerSpec(
        source_id="us-nc-onemap-parcels",
        capability="fetch_parcel",
        endpoint=NC_ONEMAP_LAYER_URL,
        observation="One 1=1 feature query with declared fields and no geometry",
        expected_requests=1,
        sentinel_record_count=1,
        sample_bytes=None,
        handler=probe_nc_onemap,
    ),
    "us-ma-massgis-parcels": ProbeHandlerSpec(
        source_id="us-ma-massgis-parcels",
        capability="probe",
        endpoint=MASSGIS_MANIFEST_LAYER_URL,
        observation=(
            "One Gosnold manifest row, artifact HEAD, and leading byte range"
        ),
        expected_requests=3,
        sentinel_record_count=1,
        sample_bytes=4096,
        handler=probe_massgis,
    ),
}


def registered_handlers(
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> list[dict[str, Any]]:
    """Return the complete visible handler registry."""
    active = handlers if handlers is not None else HANDLER_REGISTRY
    return [active[source_id].to_dict() for source_id in sorted(active)]


def compare_probes(
    previous: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare status and schema/artifact fingerprints between two probes."""
    if previous is None:
        return {
            "baseline": True,
            "drift_detected": False,
            "previous_probe_id": None,
            "current_probe_id": current.get("probe_id"),
            "changes": {},
        }
    fields = ("status", "schema_sha256", "artifact_sha256")
    changes = {
        field_name: {
            "previous": previous.get(field_name),
            "current": current.get(field_name),
            "changed": previous.get(field_name) != current.get(field_name),
        }
        for field_name in fields
    }
    return {
        "baseline": False,
        "drift_detected": any(change["changed"] for change in changes.values()),
        "previous_probe_id": previous.get("probe_id"),
        "current_probe_id": current.get("probe_id"),
        "changes": changes,
    }


def _decision_status(decision: Mapping[str, Any]) -> str:
    return acquisition_result_status(decision)


def _exception_observation(
    error: BaseException,
    *,
    endpoint: str,
    latency_ms: float,
) -> ProbeObservation:
    if isinstance(error, PublicRecordsHTTPError):
        return ProbeObservation(
            status=error.result_status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={"error": error.to_contract_error().to_dict()},
            error=str(error),
        )
    if isinstance(error, BulkSourceError):
        return ProbeObservation(
            status=error.result_status.value,
            endpoint=endpoint,
            latency_ms=latency_ms,
            details={"error": error.to_contract_error().to_dict()},
            error=str(error),
        )
    return ProbeObservation(
        status=ResultStatus.UNAVAILABLE.value,
        endpoint=endpoint,
        latency_ms=latency_ms,
        details={"exception_type": type(error).__name__},
        error=str(error) or type(error).__name__,
    )


def _record_observation(
    catalog: PublicRecordsCatalog,
    source_id: str,
    observation: ProbeObservation,
    *,
    probed_by: str,
    probed_at: str | None,
    probe_kind: str,
    capability: str | None,
    details: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous_rows = catalog.probe_history(source_id)
    previous = previous_rows[0] if previous_rows else None
    recorded = catalog.record_probe(
        source_id,
        status=observation.status,
        probed_by=probed_by,
        probed_at=probed_at,
        probe_kind=probe_kind,
        capability=capability,
        endpoint=observation.endpoint,
        http_status=observation.http_status,
        latency_ms=observation.latency_ms,
        schema_sha256=observation.schema_sha256,
        artifact_sha256=observation.artifact_sha256,
        result_count=observation.result_count,
        details=details,
        error=observation.error,
    )
    current_rows = catalog.probe_history(
        source_id,
        probe_ids=[recorded["probe_id"]],
    )
    current = current_rows[0]
    return current, compare_probes(previous, current)


def plan_sources(
    catalog: PublicRecordsCatalog,
    source_ids: Sequence[str] | None = None,
    *,
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> dict[str, Any]:
    """Describe catalog decisions and registered handlers without probing."""
    active_handlers = handlers if handlers is not None else HANDLER_REGISTRY
    selected_ids = (
        list(source_ids)
        if source_ids
        else [row["source_id"] for row in catalog.list_sources()]
    )
    sources: list[dict[str, Any]] = []
    for source_id in selected_ids:
        try:
            decision = catalog.machine_acquisition_decision(source_id)
            handler = active_handlers.get(source_id)
            if decision["allowed"] and handler is not None:
                mode = "registered_probe"
            elif decision["allowed"]:
                mode = "no_registered_handler"
            else:
                mode = "catalog_decision"
            sources.append(
                {
                    "source_id": source_id,
                    "mode": mode,
                    "catalog_decision": decision,
                    "handler": handler.to_dict() if handler else None,
                }
            )
        except CatalogError as error:
            sources.append(
                {
                    "source_id": source_id,
                    "mode": "catalog_error",
                    "catalog_decision": None,
                    "handler": None,
                    "error": str(error),
                }
            )
    return {
        "command": "plan",
        "handler_registry": registered_handlers(active_handlers),
        "sources": sources,
    }


def run_sources(
    catalog: PublicRecordsCatalog,
    source_ids: Sequence[str],
    *,
    probed_by: str = MONITOR_ACTOR,
    probed_at: str | None = None,
    timeout: float = 30.0,
    max_attempts: int = 3,
    handlers: Mapping[str, ProbeHandlerSpec] | None = None,
) -> dict[str, Any]:
    """Run and record probes only for the explicitly supplied source IDs."""
    if not source_ids:
        raise ValueError("run requires at least one explicit source ID")
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")
    active_handlers = handlers if handlers is not None else HANDLER_REGISTRY
    results: list[dict[str, Any]] = []

    for source_id in source_ids:
        try:
            decision = catalog.machine_acquisition_decision(source_id)
        except CatalogError as error:
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": None,
                    "handler": None,
                    "dispatched": False,
                    "recorded": False,
                    "status": "error",
                    "error": str(error),
                }
            )
            continue

        handler_spec = active_handlers.get(source_id)
        if not decision["allowed"]:
            observation = ProbeObservation(
                status=_decision_status(decision),
                endpoint=catalog.show_source(source_id)["source"]["official_url"],
                details={"catalog_decision": decision},
                error=str(decision["reason"]),
            )
            current, drift = _record_observation(
                catalog,
                source_id,
                observation,
                probed_by=probed_by,
                probed_at=probed_at,
                probe_kind="sentinel",
                capability=handler_spec.capability if handler_spec else None,
                details={
                    **observation.details,
                    "handler": handler_spec.to_dict() if handler_spec else None,
                    "dispatched": False,
                },
            )
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": decision,
                    "handler": handler_spec.to_dict() if handler_spec else None,
                    "dispatched": False,
                    "recorded": True,
                    "probe": current,
                    "drift": drift,
                }
            )
            continue

        if handler_spec is None:
            results.append(
                {
                    "source_id": source_id,
                    "catalog_decision": decision,
                    "handler": None,
                    "dispatched": False,
                    "recorded": False,
                    "status": "error",
                    "error": "No registered low-cost probe handler for this source",
                }
            )
            continue

        context = ProbeContext(
            source_id=source_id,
            catalog_decision=decision,
            timeout=timeout,
            max_attempts=max_attempts,
            sample_bytes=handler_spec.sample_bytes,
        )
        started = time.perf_counter()
        try:
            observation = handler_spec.handler(context)
            if observation.latency_ms is None:
                observation = replace(
                    observation,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
        except Exception as error:
            observation = _exception_observation(
                error,
                endpoint=handler_spec.endpoint,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        details = {
            **observation.details,
            "catalog_decision": decision,
            "handler": handler_spec.to_dict(),
            "dispatched": True,
        }
        current, drift = _record_observation(
            catalog,
            source_id,
            observation,
            probed_by=probed_by,
            probed_at=probed_at,
            probe_kind="sentinel",
            capability=handler_spec.capability,
            details=details,
        )
        results.append(
            {
                "source_id": source_id,
                "catalog_decision": decision,
                "handler": handler_spec.to_dict(),
                "dispatched": True,
                "recorded": True,
                "probe": current,
                "drift": drift,
            }
        )

    return {
        "command": "run",
        "requested_source_ids": list(source_ids),
        "handler_registry": registered_handlers(active_handlers),
        "results": results,
    }


def record_observation(
    catalog: PublicRecordsCatalog,
    source_id: str,
    observation: ProbeObservation,
    *,
    probed_by: str,
    probed_at: str | None = None,
    probe_kind: str = "sentinel",
    capability: str | None = None,
) -> dict[str, Any]:
    """Append an explicitly supplied observation and show resulting drift."""
    decision = catalog.machine_acquisition_decision(source_id)
    current, drift = _record_observation(
        catalog,
        source_id,
        observation,
        probed_by=probed_by,
        probed_at=probed_at,
        probe_kind=probe_kind,
        capability=capability,
        details=observation.details,
    )
    return {
        "command": "record",
        "source_id": source_id,
        "catalog_decision": decision,
        "probe": current,
        "drift": drift,
    }


def history(
    catalog: PublicRecordsCatalog,
    source_id: str,
) -> dict[str, Any]:
    """Return the full immutable probe history for a source."""
    return {
        "command": "history",
        "source_id": source_id,
        "catalog_decision": catalog.machine_acquisition_decision(source_id),
        "probes": catalog.probe_history(source_id),
    }


def diff_history(
    catalog: PublicRecordsCatalog,
    source_id: str,
    *,
    from_probe_id: int | None = None,
    to_probe_id: int | None = None,
) -> dict[str, Any]:
    """Compare two exact probes, or the newest two when IDs are omitted."""
    if (from_probe_id is None) != (to_probe_id is None):
        raise ValueError("from_probe_id and to_probe_id must be supplied together")
    if from_probe_id is None:
        probes = catalog.probe_history(source_id)
        current = probes[0] if probes else None
        previous = probes[1] if len(probes) > 1 else None
    else:
        probes = catalog.probe_history(
            source_id,
            probe_ids=[from_probe_id, to_probe_id],
        )
        by_id = {probe["probe_id"]: probe for probe in probes}
        missing = [
            probe_id
            for probe_id in (from_probe_id, to_probe_id)
            if probe_id not in by_id
        ]
        if missing:
            raise CatalogError(
                f"probe IDs do not belong to {source_id}: "
                + ", ".join(str(probe_id) for probe_id in missing)
            )
        previous = by_id[from_probe_id]
        current = by_id[to_probe_id]
    if current is None:
        comparison = None
    else:
        comparison = compare_probes(previous, current)
    return {
        "command": "diff",
        "source_id": source_id,
        "catalog_decision": catalog.machine_acquisition_decision(source_id),
        "comparison": comparison,
    }


def _parse_details(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    if value.startswith("@"):
        raw = Path(value[1:]).read_text(encoding="utf-8")
    else:
        raw = value
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("details must be a JSON object")
    return data


def _add_output(parser: argparse.ArgumentParser) -> None:
    add_output_args(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, run, record, and compare public-record source probes"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan", help="Show catalog decisions and probe handlers")
    plan.add_argument("source_ids", nargs="*")
    _add_output(plan)

    run = sub.add_parser("run", help="Run explicitly named source probes")
    run.add_argument("source_ids", nargs="+")
    run.add_argument("--probed-by", default=MONITOR_ACTOR)
    run.add_argument("--probed-at")
    run.add_argument("--timeout", type=float, default=30.0)
    run.add_argument("--max-attempts", type=int, default=3)
    _add_output(run)

    record = sub.add_parser("record", help="Append an explicit probe observation")
    record.add_argument("source_id")
    record.add_argument("--status", required=True, choices=sorted(PROBE_STATUSES))
    record.add_argument("--probed-by", required=True)
    record.add_argument("--probed-at")
    record.add_argument("--kind", default="sentinel")
    record.add_argument("--capability")
    record.add_argument("--endpoint")
    record.add_argument("--http-status", type=int)
    record.add_argument("--latency-ms", type=float)
    record.add_argument("--schema-sha256")
    record.add_argument("--artifact-sha256")
    record.add_argument("--result-count", type=int)
    record.add_argument("--details", help="JSON object or @file")
    record.add_argument("--error")
    _add_output(record)

    diff = sub.add_parser("diff", help="Compare schema, artifact, and status")
    diff.add_argument("source_id")
    diff.add_argument("--from-probe-id", type=int)
    diff.add_argument("--to-probe-id", type=int)
    _add_output(diff)

    history_parser = sub.add_parser(
        "history",
        help="Return the complete immutable probe history",
    )
    history_parser.add_argument("source_id")
    _add_output(history_parser)
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    catalog = PublicRecordsCatalog(args.db)
    if args.command == "plan":
        return plan_sources(catalog, args.source_ids)
    if args.command == "run":
        return run_sources(
            catalog,
            args.source_ids,
            probed_by=args.probed_by,
            probed_at=args.probed_at,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
        )
    if args.command == "record":
        return record_observation(
            catalog,
            args.source_id,
            ProbeObservation(
                status=args.status,
                endpoint=args.endpoint,
                http_status=args.http_status,
                latency_ms=args.latency_ms,
                schema_sha256=args.schema_sha256,
                artifact_sha256=args.artifact_sha256,
                result_count=args.result_count,
                details=_parse_details(args.details),
                error=args.error,
            ),
            probed_by=args.probed_by,
            probed_at=args.probed_at,
            probe_kind=args.kind,
            capability=args.capability,
        )
    if args.command == "diff":
        return diff_history(
            catalog,
            args.source_id,
            from_probe_id=args.from_probe_id,
            to_probe_id=args.to_probe_id,
        )
    if args.command == "history":
        return history(catalog, args.source_id)
    raise ValueError(f"unsupported command: {args.command}")


def _emit(data: Mapping[str, Any], args: argparse.Namespace) -> None:
    if write_output(
        data,
        args,
        summary=f"Public-record monitor {args.command}",
    ):
        return
    if args.json_out:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    if args.command == "run":
        print(f"Processed {len(data['results'])} explicitly requested sources")
        for result in data["results"]:
            status = (
                result.get("probe", {}).get("status")
                or result.get("status")
                or "unknown"
            )
            print(
                f"  {result['source_id']}: {status} "
                f"(dispatched={result['dispatched']}, recorded={result['recorded']})"
            )
    elif args.command == "plan":
        print(f"Planned {len(data['sources'])} catalog sources")
        for source in data["sources"]:
            print(f"  {source['source_id']}: {source['mode']}")
    elif args.command == "history":
        print(f"{data['source_id']}: {len(data['probes'])} probes")
    elif args.command == "diff":
        comparison = data["comparison"]
        if comparison is None:
            print(f"{data['source_id']}: no probes")
        else:
            print(
                f"{data['source_id']}: "
                f"drift_detected={comparison['drift_detected']}"
            )
    else:
        print(
            f"Recorded probe #{data['probe']['probe_id']} "
            f"for {data['source_id']}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "timeout", 1) <= 0:
            parser.error("--timeout must be positive")
        if getattr(args, "max_attempts", 1) <= 0:
            parser.error("--max-attempts must be positive")
        data = execute(args)
        _emit(data, args)
        return 0
    except (CatalogError, OSError, ValueError, json.JSONDecodeError) as error:
        if getattr(args, "json_out", False):
            print(
                json.dumps(
                    {
                        "command": args.command,
                        "status": "error",
                        "error": str(error),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
