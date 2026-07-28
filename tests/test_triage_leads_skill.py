from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILLS = (
    ROOT / ".codex/skills/triage-leads/SKILL.md",
    ROOT / ".claude/skills/triage-leads/SKILL.md",
)


def test_triage_queue_selection_uses_profile_scoped_tracker_commands():
    for path in SKILLS:
        text = path.read_text()
        assert "lead_tracker.py stats" in text
        assert "lead_tracker.py list \\\n  --status pending_triage" in text
        assert "FROM leads WHERE status='pending_triage'" not in text
        assert "investigation_context.py show --output" not in text


def test_triage_target_queries_use_tracker_profile_scope():
    for path in SKILLS:
        text = path.read_text()
        assert text.count('lead_tracker.py list \\\n  --target "<TARGET>"') == 2
        assert "WHERE target_name LIKE ? AND status != 'pending_triage'" not in text
        assert "WHERE target_name = ? AND id != ?" not in text
