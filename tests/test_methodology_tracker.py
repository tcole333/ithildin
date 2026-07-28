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


def test_ingest_report_accepts_methodology_learnings_header(
    tmp_path,
    monkeypatch,
):
    report = tmp_path / "report.md"
    report.write_text(
        """# Report
## Methodology Learnings
- [Friction] Header variant is parsed
""",
        encoding="utf-8",
    )
    inserted = []
    monkeypatch.setattr(
        methodology_tracker,
        "add_observation",
        lambda **kwargs: inserted.append(kwargs) or len(inserted),
    )

    assert methodology_tracker.ingest_report(report, skill="deep-investigate") == [1]
    assert inserted[0]["description"] == "Header variant is parsed"


def test_ingest_report_accepts_observation_heading_variants_and_unlabeled_bullets(
    tmp_path,
    monkeypatch,
):
    inserted = []
    monkeypatch.setattr(
        methodology_tracker,
        "add_observation",
        lambda **kwargs: inserted.append(kwargs) or len(inserted),
    )

    for index, heading in enumerate(
        [
            "Methodological learnings",
            "Methodology/papercuts",
            "Methodology observation",
            "Papercuts",
            "Caveats",
        ],
        start=1,
    ):
        report = tmp_path / f"report-{index}.md"
        report.write_text(
            f"# Report\n## {heading}\n- Unlabeled operational lesson {index}\n",
            encoding="utf-8",
        )
        assert methodology_tracker.ingest_report(report) == [index]

    assert [item["category"] for item in inserted] == ["methodology"] * 5


def test_ingest_report_links_referenced_papercut_as_duplicate(
    tmp_path,
    monkeypatch,
):
    report = tmp_path / "report.md"
    report.write_text(
        """# Report
## Methodology Learnings
- [Friction] FBI JSON remains unsafe (papercut #500).
""",
        encoding="utf-8",
    )
    duplicates = []
    monkeypatch.setattr(methodology_tracker, "add_observation", lambda **_kwargs: 900)
    monkeypatch.setattr(
        methodology_tracker,
        "get_observation",
        lambda obs_id: {
            "id": obs_id,
            "status": "addressed",
            "resolution": "fixed",
        },
    )
    monkeypatch.setattr(
        methodology_tracker,
        "mark_duplicate",
        lambda obs_id, canonical_id: duplicates.append((obs_id, canonical_id)),
    )

    assert methodology_tracker.ingest_report(report) == [900]
    assert duplicates == [(900, 500)]


def test_ingest_report_keeps_cross_category_papercut_reference_distinct(
    tmp_path,
    monkeypatch,
):
    report = tmp_path / "report.md"
    report.write_text(
        """# Report
## Methodology Learnings
- [Source quality] API coverage is partial (papercut #500).
""",
        encoding="utf-8",
    )
    duplicates = []
    monkeypatch.setattr(methodology_tracker, "add_observation", lambda **_kwargs: 900)
    monkeypatch.setattr(
        methodology_tracker,
        "get_observation",
        lambda obs_id: {
            "id": obs_id,
            "category": "friction",
            "status": "addressed",
            "resolution": "fixed",
        },
    )
    monkeypatch.setattr(
        methodology_tracker,
        "mark_duplicate",
        lambda obs_id, canonical_id: duplicates.append((obs_id, canonical_id)),
    )

    assert methodology_tracker.ingest_report(report) == [900]
    assert duplicates == []
