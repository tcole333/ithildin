import json

from tools.public_records_eval import (
    SCHEMA_VERSION,
    evaluate_adapters,
    evaluate_bundle,
    evaluate_extractions,
    evaluate_triage,
    main,
)


def test_adapter_metrics_detect_false_zero_and_barrier_collapse():
    result = evaluate_adapters(
        [
            {
                "case_id": "record",
                "match_fields": ["canonical_ref"],
                "expected": {
                    "status": "ok",
                    "records": [{"canonical_ref": "PROPERTY:x"}],
                },
                "actual": {"status": "no_results", "records": []},
            },
            {
                "case_id": "challenge",
                "expected": {"status": "human_required", "records": []},
                "actual": {"status": "no_results", "records": []},
            },
        ]
    )
    assert result["metrics"]["false_zeroes"] == 1
    assert result["metrics"]["barriers_as_zero"] == 1
    assert result["metrics"]["status_accuracy"] == 0


def test_extraction_metrics_count_invention_critical_precision_and_leakage():
    result = evaluate_extractions(
        [
            {
                "case_id": "doc",
                "gold_fields": [
                    {"name": "document_number", "value": "D1"},
                    {"name": "party_name", "value": "ACME LLC"},
                    {
                        "name": "account_number",
                        "value": "SECRET",
                        "protected": True,
                    },
                ],
                "predicted_fields": [
                    {"name": "document_number", "value": "D1"},
                    {"name": "party_name", "value": "WRONG LLC"},
                    {"name": "account_number", "value": "SECRET"},
                ],
            }
        ]
    )
    metrics = result["metrics"]
    assert metrics["true_positive"] == 1
    assert metrics["invented_values"] == 2
    assert metrics["protected_leakage"] == 1
    assert metrics["critical_fields"]["precision"] == 0.5


def test_triage_reports_material_recall_and_retrieval_reduction():
    result = evaluate_triage(
        [
            {
                "candidate_document_ids": ["a", "b", "c", "d"],
                "material_document_ids": ["b", "d"],
                "selected_document_ids": ["b"],
            }
        ]
    )
    assert result["metrics"]["material_recall"] == 0.5
    assert result["metrics"]["retrieval_reduction"] == 0.75


def test_bundle_applies_only_caller_supplied_thresholds():
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "adapter_cases": [],
        "extraction_cases": [
            {
                "gold_fields": [{"name": "case_number", "value": "1"}],
                "predicted_fields": [{"name": "case_number", "value": "1"}],
            }
        ],
        "triage_cases": [],
        "thresholds": {
            "extraction.metrics.precision": {"min": 0.99},
            "extraction.metrics.protected_leakage": {"max": 0},
        },
    }
    report = evaluate_bundle(bundle)
    assert report["thresholds"]["configured"] is True
    assert report["thresholds"]["passed"] is True
    assert len(report["thresholds"]["checks"]) == 2


def test_cli_template_writes_json(tmp_path, capsys):
    output = tmp_path / "template.json"
    assert main(["template", "--output", str(output)]) == 0
    payload = json.loads(output.read_text())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "saved to" in capsys.readouterr().out
