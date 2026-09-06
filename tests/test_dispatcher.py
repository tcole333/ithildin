import json
import os
import sqlite3
import sys
import tempfile
import unittest
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import dispatcher  # noqa: E402 - standalone unittest bootstrap
from tools.lead_tracker import _ensure_schema  # noqa: E402


class FakeAuthFailureBackend:
    name = "claude"

    def preflight(self):
        return False, "auth_failed", "OAuth token has expired"

    def build_command(self, prompt, config, system_prompts):
        raise AssertionError("build_command should not be called on auth failure")


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        self.orig_db_path = dispatcher.DB_PATH
        dispatcher.DB_PATH = self.db_path

        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        db.close()

        self.config = dispatcher.deep_merge(
            dispatcher.DEFAULT_CONFIG,
            {
                "staging_root": str(Path(self.tmpdir.name) / "staging"),
                "timeout_seconds": 60,
                "stall_seconds": 1,
            },
        )

    def tearDown(self):
        dispatcher.DB_PATH = self.orig_db_path
        self.tmpdir.cleanup()

    def _db(self):
        db = dispatcher.get_db()
        dispatcher.ensure_dispatch_table(db)
        return db

    def _insert_run(self, **overrides):
        db = self._db()
        defaults = {
            "run_type": "trace_entity",
            "job_type": "trace_entity",
            "target": "Example Co",
            "pid": None,
            "status": "completed",
            "prompt_hash": "hash123",
            "output_file": None,
            "lead_id": None,
            "hypothesis_id": None,
            "brief": None,
            "skill_name": "trace-entity",
            "expected_artifacts": json.dumps(dispatcher.REQUIRED_ARTIFACTS),
            "priority": "high",
            "timeout_seconds": 60,
            "cost_cap_usd": None,
            "review_required": 1,
            "orchestrator": "codex",
            "backend": "claude",
            "task_contract_json": "{}",
            "staging_dir": None,
            "health_status": "healthy",
            "health_detail": None,
        }
        defaults.update(overrides)
        cursor = db.execute(
            """
            INSERT INTO dispatch_runs (
                run_type, job_type, target, pid, status, prompt_hash, output_file,
                lead_id, hypothesis_id, brief, skill_name, expected_artifacts, priority,
                timeout_seconds, cost_cap_usd, review_required, orchestrator, backend,
                task_contract_json, staging_dir, health_status, health_detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                defaults["run_type"],
                defaults["job_type"],
                defaults["target"],
                defaults["pid"],
                defaults["status"],
                defaults["prompt_hash"],
                defaults["output_file"],
                defaults["lead_id"],
                defaults["hypothesis_id"],
                defaults["brief"],
                defaults["skill_name"],
                defaults["expected_artifacts"],
                defaults["priority"],
                defaults["timeout_seconds"],
                defaults["cost_cap_usd"],
                defaults["review_required"],
                defaults["orchestrator"],
                defaults["backend"],
                defaults["task_contract_json"],
                defaults["staging_dir"],
                defaults["health_status"],
                defaults["health_detail"],
            ),
        )
        run_id = cursor.lastrowid
        db.commit()
        db.close()
        return run_id

    def test_launch_job_records_auth_failure(self):
        db = self._db()
        contract = dispatcher.TaskContract(
            job_type="trace_entity",
            target="Swiss Commodity Re Limited",
            skill_name="trace-entity",
            expected_artifacts=list(dispatcher.REQUIRED_ARTIFACTS),
            priority="high",
            timeout_seconds=60,
            review_required=True,
            orchestrator="codex",
        )

        launched = dispatcher.launch_job(
            db,
            self.config,
            contract,
            backend=FakeAuthFailureBackend(),
        )
        self.assertFalse(launched)

        row = db.execute("SELECT * FROM dispatch_runs ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["health_status"], "auth_failed")
        self.assertIn("expired", row["error"])
        db.close()

    def test_launch_job_skips_duplicate_running_task(self):
        contract = dispatcher.TaskContract(
            job_type="trace_entity",
            target="Swiss Commodity Re Limited",
            skill_name="trace-entity",
            expected_artifacts=list(dispatcher.REQUIRED_ARTIFACTS),
            priority="high",
            timeout_seconds=60,
            review_required=True,
            orchestrator="codex",
        )
        task_hash = dispatcher.prompt_hash(contract)
        self._insert_run(status="running", prompt_hash=task_hash)

        db = self._db()
        launched = dispatcher.launch_job(
            db,
            self.config,
            contract,
            backend=FakeAuthFailureBackend(),
        )
        self.assertFalse(launched)

        count = db.execute("SELECT COUNT(*) AS n FROM dispatch_runs").fetchone()["n"]
        self.assertEqual(count, 1)
        db.close()

    def test_refresh_running_health_marks_stalled_run(self):
        staging_dir = Path(self.tmpdir.name) / "stalled-run"
        staging_dir.mkdir(parents=True, exist_ok=True)
        report = staging_dir / "report.md"
        report.write_text("old report")
        old_ts = 946684800  # 2000-01-01
        os.utime(report, (old_ts, old_ts))
        os.utime(staging_dir, (old_ts, old_ts))

        run_id = self._insert_run(
            status="running",
            staging_dir=str(staging_dir),
            output_file=str(staging_dir / "raw_output.json"),
            pid=os.getpid(),
            review_required=1,
        )

        db = self._db()
        dispatcher.refresh_running_health(db, self.config)
        row = db.execute("SELECT health_status, health_detail FROM dispatch_runs WHERE id = ?", (run_id,)).fetchone()
        self.assertEqual(row["health_status"], "stalled")
        self.assertIn("No staged artifact updates", row["health_detail"])
        db.close()

    def test_inspect_staging_bundle_flags_missing_artifact(self):
        staging_dir = Path(self.tmpdir.name) / "invalid-run"
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "report.md").write_text("# partial")

        run_id = self._insert_run(
            staging_dir=str(staging_dir),
            output_file=str(staging_dir / "raw_output.json"),
            review_required=1,
        )
        db = self._db()
        run = db.execute("SELECT * FROM dispatch_runs WHERE id = ?", (run_id,)).fetchone()
        inspection = dispatcher.inspect_staging_bundle(db, run, self.config, update_db=True)
        self.assertFalse(inspection["ready"])
        self.assertIn("run.json", inspection["validation_error"])

        staging = db.execute("SELECT review_status FROM dispatch_staging WHERE run_id = ?", (run_id,)).fetchone()
        self.assertEqual(staging["review_status"], "invalid")
        db.close()

    def test_import_staged_run_imports_and_prevents_double_import(self):
        staging_dir = Path(self.tmpdir.name) / "valid-run"
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "report.md").write_text("# report\n")
        (staging_dir / "run.json").write_text(
            json.dumps(
                {
                    "summary": "done",
                    "status": "completed",
                    "sources_checked": ["hk_registry"],
                    "counts": {"findings": 1, "leads": 1, "entities": 1},
                    "notes": ["ok"],
                    "lead_disposition": "keep_open",
                }
            )
        )
        (staging_dir / "candidate_findings.jsonl").write_text(
            json.dumps(
                {
                    "target_name": "Swiss Commodity Re Limited",
                    "summary": "Registry confirms Hong Kong incorporation",
                    "finding_type": "financial",
                    "source_datasets": ["official_website"],
                    "confidence": "high",
                    "claim_type": "paraphrase",
                    "evidence_ids": ["https://example.org/registry/fixture"],
                    "source_quotes": {"https://example.org/registry/fixture": {"quote": "Registry confirms incorporation"}},
                }
            )
            + "\n"
        )
        (staging_dir / "candidate_leads.jsonl").write_text(
            json.dumps(
                {
                    "title": "Trace founder shareholder",
                    "description": "Identify International Fiduciaries relationship",
                    "category": "entity",
                    "priority": "high",
                    "status": "open",
                    "source": "staged_worker",
                }
            )
            + "\n"
        )
        (staging_dir / "candidate_entities.jsonl").write_text(
            json.dumps(
                {
                    "record_type": "entity",
                    "name": "Swiss Commodity Re Limited",
                    "entity_type": "ltd",
                    "jurisdiction": "Hong Kong",
                    "status": "active",
                    "source": "hk_registry",
                }
            )
            + "\n"
        )
        (staging_dir / "candidate_connections.jsonl").write_text("")

        run_id = self._insert_run(
            staging_dir=str(staging_dir),
            output_file=str(staging_dir / "raw_output.json"),
            review_required=1,
            task_contract_json=json.dumps({"profile_id": "feeding-our-future"}),
        )

        db = self._db()
        run = db.execute("SELECT * FROM dispatch_runs WHERE id = ?", (run_id,)).fetchone()
        inspection = dispatcher.inspect_staging_bundle(db, run, self.config, update_db=True)
        self.assertTrue(inspection["ready"])

        db.commit()
        dispatcher.approve_staged_run(db, run_id, self.config, "test")

        counts = dispatcher.import_staged_run(db, run_id, self.config, actor="test")
        self.assertEqual(counts["findings"], 1)
        self.assertEqual(counts["leads"], 1)
        self.assertEqual(counts["entities"], 1)

        finding_count = db.execute("SELECT COUNT(*) AS n FROM findings").fetchone()["n"]
        lead_count = db.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
        entity_count = db.execute("SELECT COUNT(*) AS n FROM entities").fetchone()["n"]
        self.assertEqual(finding_count, 1)
        self.assertEqual(lead_count, 1)
        self.assertEqual(entity_count, 1)

        finding = db.execute("SELECT profile_id FROM findings LIMIT 1").fetchone()
        lead = db.execute("SELECT profile_id FROM leads LIMIT 1").fetchone()
        self.assertEqual(finding["profile_id"], "feeding-our-future")
        self.assertEqual(lead["profile_id"], "feeding-our-future")

        self.assertEqual(dispatcher.import_staged_run(db, run_id, self.config, actor="test"), counts)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM findings").fetchone()[0], 1)

        staging = db.execute(
            "SELECT import_status, review_status FROM dispatch_staging WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        self.assertEqual(staging["import_status"], "imported")
        self.assertEqual(staging["review_status"], "imported")
        db.close()

    def test_import_staged_run_accepts_mixed_candidate_entity_records(self):
        staging_dir = Path(self.tmpdir.name) / "mixed-entity-run"
        staging_dir.mkdir(parents=True, exist_ok=True)
        (staging_dir / "report.md").write_text("# report\n")
        (staging_dir / "run.json").write_text(
            json.dumps(
                {
                    "summary": "done",
                    "status": "completed",
                    "sources_checked": ["mn_sos", "propublica_990"],
                    "counts": {"findings": 0, "leads": 0, "entities": 4},
                    "notes": ["ok"],
                    "lead_disposition": "keep_open",
                }
            )
        )
        (staging_dir / "candidate_findings.jsonl").write_text("")
        (staging_dir / "candidate_leads.jsonl").write_text("")
        (staging_dir / "candidate_entities.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "record_type": "entity",
                            "name": "Partners in Nutrition",
                            "entity_type": "nonprofit",
                            "jurisdiction": "Minnesota",
                            "status": "active",
                            "source": "propublica_990",
                        }
                    ),
                    json.dumps(
                        {
                            "record_type": "address",
                            "address": "2722 Park Ave S, Minneapolis, MN",
                            "associated_entities": [
                                "Partners in Nutrition",
                                "Horn of Africa Development and Education Foundation",
                            ],
                            "source": "web_reporting",
                        }
                    ),
                    json.dumps(
                        {
                            "record_type": "role",
                            "person_name": "Mukhtar Yusuf",
                            "role": "Executive Director",
                            "entity": "Horn of Africa Development and Education Foundation",
                            "source": "propublica_990",
                        }
                    ),
                    json.dumps(
                        {
                            "record_type": "relation",
                            "entity_a": "Partners in Nutrition",
                            "entity_b": "Horn of Africa Development and Education Foundation",
                            "relationship": "sponsor_to_site_operator",
                            "notes": "PIQC sponsored the HADEF site.",
                            "source": "web_reporting",
                        }
                    ),
                ]
            )
            + "\n"
        )
        (staging_dir / "candidate_connections.jsonl").write_text("")

        run_id = self._insert_run(
            staging_dir=str(staging_dir),
            output_file=str(staging_dir / "raw_output.json"),
            review_required=1,
            task_contract_json=json.dumps({"profile_id": "feeding-our-future"}),
        )

        db = self._db()
        run = db.execute("SELECT * FROM dispatch_runs WHERE id = ?", (run_id,)).fetchone()
        inspection = dispatcher.inspect_staging_bundle(db, run, self.config, update_db=True)
        self.assertTrue(inspection["ready"])

        db.commit()
        dispatcher.approve_staged_run(db, run_id, self.config, "test")

        counts = dispatcher.import_staged_run(db, run_id, self.config, actor="test")
        self.assertGreaterEqual(counts["entities"], 4)

        role_count = db.execute("SELECT COUNT(*) AS n FROM entity_roles").fetchone()["n"]
        address_count = db.execute("SELECT COUNT(*) AS n FROM entity_addresses").fetchone()["n"]
        relation_count = db.execute("SELECT COUNT(*) AS n FROM entity_relations").fetchone()["n"]
        self.assertEqual(role_count, 1)
        self.assertEqual(address_count, 2)
        self.assertEqual(relation_count, 1)
        db.close()

    def test_dispatch_cycle_stages_research_and_pins_the_selected_profile(self):
        db = self._db()
        db.execute("INSERT OR REPLACE INTO investigation_config (key, value) VALUES ('active_profile', 'epstein')")
        db.execute(
            """
            INSERT INTO leads (title, description, category, priority, status, source, target_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "High priority lead",
                "Needs investigation",
                "entity",
                "high",
                "open",
                "test",
                "Swiss Commodity Re Limited",
            ),
        )
        db.execute("UPDATE leads SET profile_id='epstein' WHERE title='High priority lead'")
        db.commit()
        db.close()

        captured = []
        original_launch_job = dispatcher.launch_job

        def fake_launch_job(db, config, contract, backend=None, dry_run=False):
            captured.append(contract)
            return True

        dispatcher.launch_job = fake_launch_job
        try:
            dispatcher.dispatch_cycle(self.config, dry_run=False)
        finally:
            dispatcher.launch_job = original_launch_job

        self.assertTrue(captured)
        self.assertTrue(all(contract.orchestrator == "auto" for contract in captured))
        research = [c for c in captured if c.job_type in {"pursue_lead", "deep_investigate"}]
        self.assertTrue(research)
        self.assertTrue(all(c.review_required for c in research))
        self.assertTrue(all(c.profile_id == "epstein" and c.lead_id for c in research))

    def test_hydrate_contract_uses_active_profile_from_investigation_config(self):
        db = self._db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS investigation_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP
            )
            """
        )
        db.execute(
            """
            INSERT INTO investigation_config (key, value, updated_at)
            VALUES ('active_profile', 'feeding-our-future', CURRENT_TIMESTAMP)
            """
        )
        db.commit()
        db.close()

        args = argparse.Namespace(
            type="trace_entity",
            target="Stigma-Free International",
            lead_id=None,
            hypothesis_id=None,
            brief=None,
            skill_name=None,
            expected_artifact=None,
            priority=None,
            timeout_seconds=None,
            cost_cap_usd=None,
            review_required=None,
            orchestrator="codex",
        )

        contract = dispatcher.hydrate_contract(args, self.config)
        self.assertEqual(contract.profile_id, "feeding-our-future")

    def test_normalize_job_type_accepts_investigate_infra(self):
        self.assertEqual(dispatcher.normalize_job_type("investigate-infra"), "investigate_infra")


if __name__ == "__main__":
    unittest.main()
