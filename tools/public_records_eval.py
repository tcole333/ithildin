#!/usr/bin/env python3
"""Evaluate public-record adapters, extraction output, and document triage.

The evaluator is deliberately model- and adapter-agnostic. A gold-set bundle
contains expected and observed values plus any release thresholds the caller
wants to apply. The tool reports exact metrics and threshold outcomes; it does
not embed an unseen release policy.

Usage:
    uv run python tools/public_records_eval.py run gold-set.json
    uv run python tools/public_records_eval.py template --output gold-template.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

try:
    from tools.output_util import add_output_args, write_output
    from tools.public_records_contract import (
        ResultStatus,
        canonical_json,
        utc_now_iso,
    )
except ImportError:
    from output_util import add_output_args, write_output
    from public_records_contract import ResultStatus, canonical_json, utc_now_iso


SCHEMA_VERSION = "public-records-eval/1.0"
BARRIER_STATUSES = frozenset(
    {
        "partial",
        "unavailable",
        "restricted",
        "human_required",
        "rate_limited",
        "terms_blocked",
        "source_changed",
    }
)
RESULT_STATUSES = frozenset(status.value for status in ResultStatus)
CRITICAL_FIELD_RE = re.compile(
    r"(?:^|_)(?:id|identifier|number|date|amount|price|consideration|value)(?:$|_)"
)


class EvaluationError(RuntimeError):
    """Raised for malformed evaluation inputs."""


def _load_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationError(f"evaluation file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid evaluation JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise EvaluationError("evaluation bundle must be a JSON object")
    return value


def _ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _metric_counts(expected: Counter[str], predicted: Counter[str]) -> dict[str, Any]:
    true_positive = sum((expected & predicted).values())
    false_positive = sum((predicted - expected).values())
    false_negative = sum((expected - predicted).values())
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": _f1(precision, recall),
    }


def _require_cases(value: Any, name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise EvaluationError(f"{name} must be an array")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise EvaluationError(f"{name}[{index}] must be an object")
        result.append(item)
    return result


def _record_key(record: Any, fields: Sequence[str] | None = None) -> str:
    if fields:
        if not isinstance(record, Mapping):
            return canonical_json(record)
        return canonical_json({field: record.get(field) for field in fields})
    if isinstance(record, Mapping):
        for field in (
            "canonical_ref",
            "native_document_id",
            "native_parcel_id",
            "case_number",
            "id",
        ):
            if field in record:
                return canonical_json({field: record[field]})
    return canonical_json(record)


def evaluate_adapters(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    case_results: list[dict[str, Any]] = []
    expected_records: Counter[str] = Counter()
    predicted_records: Counter[str] = Counter()
    status_matches = 0
    false_zeroes = 0
    barriers_as_zero = 0
    invalid_statuses = 0

    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or f"adapter-{index}")
        expected = case.get("expected")
        actual = case.get("actual")
        if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
            raise EvaluationError(
                f"adapter case {case_id} requires expected and actual objects"
            )
        expected_status = str(expected.get("status") or "")
        actual_status = str(actual.get("status") or "")
        if actual_status not in RESULT_STATUSES:
            invalid_statuses += 1
        status_match = actual_status == expected_status
        status_matches += int(status_match)
        expected_rows = expected.get("records") or []
        actual_rows = actual.get("records") or []
        if not isinstance(expected_rows, list) or not isinstance(actual_rows, list):
            raise EvaluationError(
                f"adapter case {case_id} records must be arrays"
            )
        key_fields_raw = case.get("match_fields")
        if key_fields_raw is not None and (
            not isinstance(key_fields_raw, list)
            or not all(isinstance(field, str) for field in key_fields_raw)
        ):
            raise EvaluationError(
                f"adapter case {case_id} match_fields must be an array of strings"
            )
        key_fields = key_fields_raw or None
        expected_keys = Counter(_record_key(row, key_fields) for row in expected_rows)
        actual_keys = Counter(_record_key(row, key_fields) for row in actual_rows)
        expected_records.update(expected_keys)
        predicted_records.update(actual_keys)
        false_zero = actual_status == "no_results" and bool(expected_rows)
        barrier_as_zero = (
            actual_status == "no_results" and expected_status in BARRIER_STATUSES
        )
        false_zeroes += int(false_zero)
        barriers_as_zero += int(barrier_as_zero)
        record_metrics = _metric_counts(expected_keys, actual_keys)
        case_results.append(
            {
                "case_id": case_id,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "status_match": status_match,
                "false_zero": false_zero,
                "barrier_as_zero": barrier_as_zero,
                "record_metrics": record_metrics,
            }
        )

    aggregate = _metric_counts(expected_records, predicted_records)
    aggregate.update(
        {
            "case_count": len(cases),
            "status_accuracy": _ratio(status_matches, len(cases)),
            "false_zeroes": false_zeroes,
            "barriers_as_zero": barriers_as_zero,
            "invalid_statuses": invalid_statuses,
        }
    )
    return {"metrics": aggregate, "cases": case_results}


def _field_token(field: Mapping[str, Any]) -> str:
    name = field.get("name")
    if not isinstance(name, str) or not name:
        raise EvaluationError("extraction fields require a non-empty name")
    value = field.get("value")
    qualifiers = field.get("qualifiers") or {}
    if not isinstance(qualifiers, Mapping):
        raise EvaluationError("field qualifiers must be an object")
    return canonical_json({"name": name, "value": value, "qualifiers": qualifiers})


def _critical_token(field: Mapping[str, Any]) -> str | None:
    name = str(field.get("name") or "")
    return _field_token(field) if CRITICAL_FIELD_RE.search(name) else None


def evaluate_extractions(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected_all: Counter[str] = Counter()
    predicted_all: Counter[str] = Counter()
    expected_critical: Counter[str] = Counter()
    predicted_critical: Counter[str] = Counter()
    protected_gold: Counter[str] = Counter()
    predicted_protected: Counter[str] = Counter()
    case_results: list[dict[str, Any]] = []

    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or f"extraction-{index}")
        gold = case.get("gold_fields") or []
        predicted = case.get("predicted_fields") or []
        if not isinstance(gold, list) or not isinstance(predicted, list):
            raise EvaluationError(
                f"extraction case {case_id} fields must be arrays"
            )
        normal_gold: list[Mapping[str, Any]] = []
        protected: list[Mapping[str, Any]] = []
        for field in gold:
            if not isinstance(field, Mapping):
                raise EvaluationError(
                    f"extraction case {case_id} gold field must be an object"
                )
            (protected if field.get("protected") is True else normal_gold).append(field)
        for field in predicted:
            if not isinstance(field, Mapping):
                raise EvaluationError(
                    f"extraction case {case_id} predicted field must be an object"
                )

        gold_tokens = Counter(_field_token(field) for field in normal_gold)
        predicted_tokens = Counter(_field_token(field) for field in predicted)
        protected_tokens = Counter(_field_token(field) for field in protected)
        explicit_protected = Counter(
            _field_token(field)
            for field in predicted
            if field.get("protected") is True
        )
        leaked = (predicted_tokens & protected_tokens) + explicit_protected
        expected_all.update(gold_tokens)
        predicted_all.update(predicted_tokens)
        protected_gold.update(protected_tokens)
        predicted_protected.update(leaked)

        gold_critical = Counter(
            token
            for field in normal_gold
            if (token := _critical_token(field)) is not None
        )
        predicted_critical_case = Counter(
            token
            for field in predicted
            if (token := _critical_token(field)) is not None
        )
        expected_critical.update(gold_critical)
        predicted_critical.update(predicted_critical_case)
        metrics = _metric_counts(gold_tokens, predicted_tokens)
        metrics["protected_leakage"] = sum(leaked.values())
        case_results.append({"case_id": case_id, "metrics": metrics})

    metrics = _metric_counts(expected_all, predicted_all)
    critical = _metric_counts(expected_critical, predicted_critical)
    metrics.update(
        {
            "case_count": len(cases),
            "invented_values": metrics["false_positive"],
            "protected_gold_values": sum(protected_gold.values()),
            "protected_leakage": sum(predicted_protected.values()),
            "critical_fields": critical,
        }
    )
    return {"metrics": metrics, "cases": case_results}


def evaluate_triage(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected: Counter[str] = Counter()
    predicted: Counter[str] = Counter()
    total_candidates = 0
    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or f"triage-{index}")
        material = case.get("material_document_ids") or []
        selected = case.get("selected_document_ids") or []
        candidates = case.get("candidate_document_ids")
        if not isinstance(material, list) or not isinstance(selected, list):
            raise EvaluationError(
                f"triage case {case_id} material/selected IDs must be arrays"
            )
        if candidates is not None and not isinstance(candidates, list):
            raise EvaluationError(
                f"triage case {case_id} candidate IDs must be an array"
            )
        gold = Counter(str(value) for value in material)
        picks = Counter(str(value) for value in selected)
        expected.update(gold)
        predicted.update(picks)
        candidate_count = len(candidates) if candidates is not None else len(set(material + selected))
        total_candidates += candidate_count
        metrics = _metric_counts(gold, picks)
        metrics["candidate_count"] = candidate_count
        metrics["selected_count"] = len(selected)
        metrics["retrieval_reduction"] = (
            1.0 - (len(selected) / candidate_count) if candidate_count else None
        )
        case_results.append({"case_id": case_id, "metrics": metrics})

    metrics = _metric_counts(expected, predicted)
    metrics.update(
        {
            "case_count": len(cases),
            "candidate_count": total_candidates,
            "selected_count": sum(predicted.values()),
            "material_recall": metrics["recall"],
            "retrieval_reduction": (
                1.0 - (sum(predicted.values()) / total_candidates)
                if total_candidates
                else None
            ),
        }
    )
    return {"metrics": metrics, "cases": case_results}


def _lookup_metric(report: Mapping[str, Any], path: str) -> Any:
    current: Any = report
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise EvaluationError(f"threshold metric not found: {path}")
        current = current[part]
    return current


def apply_thresholds(
    report: Mapping[str, Any], thresholds: Mapping[str, Any] | None
) -> dict[str, Any]:
    if thresholds is None:
        return {"configured": False, "passed": None, "checks": []}
    if not isinstance(thresholds, Mapping):
        raise EvaluationError("thresholds must be an object")
    checks: list[dict[str, Any]] = []
    for path, rule in sorted(thresholds.items()):
        if not isinstance(rule, Mapping):
            raise EvaluationError(f"threshold {path} must be an object")
        value = _lookup_metric(report, str(path))
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EvaluationError(f"threshold metric {path} is not numeric")
        if not math.isfinite(float(value)):
            raise EvaluationError(f"threshold metric {path} is not finite")
        if set(rule) not in ({"min"}, {"max"}):
            raise EvaluationError(
                f"threshold {path} must contain exactly one of min or max"
            )
        operator = "min" if "min" in rule else "max"
        target = rule[operator]
        if isinstance(target, bool) or not isinstance(target, (int, float)):
            raise EvaluationError(f"threshold {path}.{operator} must be numeric")
        passed = value >= target if operator == "min" else value <= target
        checks.append(
            {
                "metric": path,
                "value": value,
                "operator": operator,
                "threshold": target,
                "passed": passed,
            }
        )
    return {
        "configured": True,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
    }


def evaluate_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationError(f"schema_version must be {SCHEMA_VERSION}")
    adapter_cases = _require_cases(bundle.get("adapter_cases"), "adapter_cases")
    extraction_cases = _require_cases(
        bundle.get("extraction_cases"), "extraction_cases"
    )
    triage_cases = _require_cases(bundle.get("triage_cases"), "triage_cases")
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "evaluated_at": utc_now_iso(),
        "adapter": evaluate_adapters(adapter_cases),
        "extraction": evaluate_extractions(extraction_cases),
        "triage": evaluate_triage(triage_cases),
    }
    report["thresholds"] = apply_thresholds(report, bundle.get("thresholds"))
    report["input_fingerprint"] = _sha256(bundle)
    return report


def _sha256(value: Any) -> str:
    import hashlib

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def template() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "adapter_cases": [
            {
                "case_id": "fixture-ok",
                "match_fields": ["canonical_ref"],
                "expected": {
                    "status": "ok",
                    "records": [{"canonical_ref": "PROPERTY:source/jurisdiction/parcel/1"}],
                },
                "actual": {
                    "status": "ok",
                    "records": [{"canonical_ref": "PROPERTY:source/jurisdiction/parcel/1"}],
                },
            }
        ],
        "extraction_cases": [
            {
                "case_id": "fixture-document",
                "gold_fields": [
                    {"name": "document_number", "value": "2026-1"},
                    {
                        "name": "account_number",
                        "value": "fixture-protected",
                        "protected": True,
                    },
                ],
                "predicted_fields": [
                    {"name": "document_number", "value": "2026-1"}
                ],
            }
        ],
        "triage_cases": [
            {
                "case_id": "fixture-docket",
                "candidate_document_ids": ["1", "2", "3"],
                "material_document_ids": ["2"],
                "selected_document_ids": ["2"],
            }
        ],
        "thresholds": {},
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate public-record adapters and document understanding"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("bundle")
    add_output_args(run)
    make_template = commands.add_parser("template")
    add_output_args(make_template)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = evaluate_bundle(_load_json(args.bundle)) if args.command == "run" else template()
        if not write_output(result, args, summary=f"public-record evaluation {args.command}"):
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (EvaluationError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
