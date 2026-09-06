"""Parse representative documented writes without touching the investigation DB."""

from pathlib import Path
import re
import shlex
import sys

import pytest

from tools import findings_tracker


@pytest.mark.parametrize("runtime", [".claude", ".codex"])
@pytest.mark.parametrize("skill", ["analyze-network", "timeline-analysis", "systemic-analysis"])
def test_analysis_finding_example_matches_current_cli(runtime, skill, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    text = (root / runtime / "skills" / skill / "SKILL.md").read_text()
    commands = re.findall(r"```bash\n(.*?)\n```", text, flags=re.DOTALL)
    command = next(block for block in commands if block.startswith("uv run python tools/findings_tracker.py add "))
    argv = shlex.split(command.replace("\\\n", " "))[3:]
    captured = []

    def validate_write(**kwargs):
        refs = kwargs["evidence_ids"]
        quotes = kwargs["source_quotes"]
        assert len(refs) == 2
        assert len(set(refs)) == len(refs)
        assert set(quotes) == set(refs)
        for ref in refs:
            findings_tracker._validate_evidence_payload(ref, quotes[ref]["quote"],
                                                        claim_type=kwargs["claim_type"])
        findings_tracker._validate_source_datasets(kwargs["source_datasets"])
        assert kwargs["claim_type"] == "synthesis"
        assert kwargs["confidence"] == "medium"
        captured.append(kwargs)
        return 1

    monkeypatch.setattr(findings_tracker, "add_finding", validate_write)
    monkeypatch.setattr(sys, "argv", argv)
    findings_tracker.main()
    assert len(captured) == 1
