from tools import methodology_tracker


def test_ingest_report_accepts_common_learning_bullet_formats(tmp_path, monkeypatch):
    report = tmp_path / "report.md"
    report.write_text(
        """---
agent: agent-a
target: "Example"
skill: deep-investigate
---
# Report
## Learnings / Papercuts
- [Friction] bracket format
- **Source quality:** bold format
- Outcome method: plain label format
""",
        encoding="utf-8",
    )
    inserted = []

    def fake_add_observation(**kwargs):
        inserted.append(kwargs)
        return len(inserted)

    monkeypatch.setattr(methodology_tracker, "add_observation", fake_add_observation)

    assert methodology_tracker.ingest_report(report) == [1, 2, 3]
    assert [item["category"] for item in inserted] == [
        "friction",
        "source_quality",
        "methodology",
    ]
    assert all(item["agent"] == "agent-a" for item in inserted)
    assert all(item["target"] == "Example" for item in inserted)
