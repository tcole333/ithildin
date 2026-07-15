import json
from pathlib import Path

import pytest

from scripts import build_geo_cy2025_ice_revenue_reconciliation as builder


def test_external_output_dir_writes_complete_reconciliation(tmp_path):
    if not builder.SOURCE_DIR.is_dir():
        pytest.skip(f"GEO lead-62481 source archive not available at {builder.SOURCE_DIR}")

    outputs = builder.build(tmp_path)

    reconciliation = json.loads(outputs["reconciliation"].read_text())
    manifest = json.loads(outputs["manifest"].read_text())

    assert reconciliation["direct_ice_actions"]["action_count"] == 124
    assert reconciliation["direct_ice_actions"]["award_count"] == 34
    assert reconciliation["direct_ice_actions"]["action_date_obligations"] == "699338118.97"
    assert reconciliation["award_snapshot_boundary"]["outlay_not_reported_award_count"] == 2
    assert len(manifest["outputs"]) == 5
    assert all(Path(item["path"]).parent == tmp_path for item in manifest["outputs"])
    assert all(path.parent == tmp_path for path in outputs.values())
