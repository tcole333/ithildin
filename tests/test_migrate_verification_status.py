import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.migrate_verification_status import CORRECTED_BY, migrate  # noqa: E402
from tools.lead_tracker import _ensure_schema  # noqa: E402

SEED_FINDINGS = [
    # (target, status, verified_by, verified_at, confidence, claim_type, profile)
    ("Vocab Confirmed", "confirmed", None, None, "high", "paraphrase", "altman"),
    ("Vocab Corroborated", "corroborated", None, None, "high", "paraphrase", "altman"),
    ("Self Verified", "verified", None, None, "high", "direct_quote", "hfia"),
    ("Gate Verified", "verified", "human", "2026-05-01T00:00:00+00:00",
     "confirmed", "direct_quote", "epstein"),
    ("Plain Unverified", "unverified", None, None, "medium", "inference", "epstein"),
    ("Disputed Row", "disputed", None, None, "medium", "inference", "epstein"),
    ("Retracted Row", "retracted", None, None, "medium", "inference", "epstein"),
]


class MigrateVerificationStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.db"
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        _ensure_schema(db)
        for target, status, verified_by, verified_at, confidence, claim_type, profile in SEED_FINDINGS:
            db.execute(
                """
                INSERT INTO findings (target_name, summary, verification_status,
                                      verified_by, verified_at, confidence,
                                      claim_type, profile_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (target, f"summary for {target}", status, verified_by,
                 verified_at, confidence, claim_type, profile),
            )
        db.commit()
        db.close()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _rows(self):
        db = sqlite3.connect(str(self.db_path))
        db.row_factory = sqlite3.Row
        rows = {
            row["target_name"]: row
            for row in db.execute(
                "SELECT target_name, verification_status, verified_by, "
                "       confidence, claim_type, profile_id FROM findings"
            ).fetchall()
        }
        corrections = db.execute(
            "SELECT record_id, field_name, old_value, new_value, corrected_by, "
            "       correction_type FROM corrections ORDER BY id"
        ).fetchall()
        db.close()
        return rows, corrections

    def test_dry_run_reports_without_writing(self):
        summary = migrate(self.db_path, apply=False)

        self.assertEqual(summary["affected"], 3)
        self.assertEqual(
            summary["by_class"],
            {"invalid_vocabulary": 2, "unstamped_verified": 1},
        )

        rows, corrections = self._rows()
        self.assertEqual(rows["Vocab Confirmed"]["verification_status"], "confirmed")
        self.assertEqual(rows["Self Verified"]["verification_status"], "verified")
        self.assertEqual(corrections, [])

    def test_apply_resets_worker_asserted_rows_and_audits(self):
        summary = migrate(self.db_path, apply=True)

        self.assertEqual(summary["updated"], 3)
        self.assertEqual(summary["skipped_concurrent"], 0)

        rows, corrections = self._rows()
        for target in ("Vocab Confirmed", "Vocab Corroborated", "Self Verified"):
            self.assertEqual(rows[target]["verification_status"], "unverified", target)

        # Legitimate states are untouched, including gated verification.
        self.assertEqual(rows["Gate Verified"]["verification_status"], "verified")
        self.assertEqual(rows["Gate Verified"]["verified_by"], "human")
        self.assertEqual(rows["Plain Unverified"]["verification_status"], "unverified")
        self.assertEqual(rows["Disputed Row"]["verification_status"], "disputed")
        self.assertEqual(rows["Retracted Row"]["verification_status"], "retracted")

        # Only the status column changes: confidence and profile_id survive.
        self.assertEqual(rows["Vocab Confirmed"]["confidence"], "high")
        self.assertEqual(rows["Vocab Confirmed"]["profile_id"], "altman")
        self.assertEqual(rows["Self Verified"]["profile_id"], "hfia")

        self.assertEqual(len(corrections), 3)
        old_values = sorted(row["old_value"] for row in corrections)
        self.assertEqual(old_values, ["confirmed", "corroborated", "verified"])
        for row in corrections:
            self.assertEqual(row["field_name"], "verification_status")
            self.assertEqual(row["new_value"], "unverified")
            self.assertEqual(row["corrected_by"], CORRECTED_BY)
            self.assertEqual(row["correction_type"], "refinement")

    def test_apply_is_idempotent(self):
        first = migrate(self.db_path, apply=True)
        second = migrate(self.db_path, apply=True)

        self.assertEqual(first["updated"], 3)
        self.assertEqual(second["affected"], 0)
        self.assertEqual(second["updated"], 0)

        _, corrections = self._rows()
        self.assertEqual(len(corrections), 3)

    def test_cli_dry_run_defaults_to_ithildin_db_path(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "migrate_verification_status.py")],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
            env={**os.environ, "ITHILDIN_DB_PATH": str(self.db_path)},
            timeout=120,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[DRY RUN] 3 findings", result.stdout)
        rows, corrections = self._rows()
        self.assertEqual(rows["Self Verified"]["verification_status"], "verified")
        self.assertEqual(corrections, [])


if __name__ == "__main__":
    unittest.main()
