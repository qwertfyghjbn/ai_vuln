from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from result_audit.service import run_audit


class ResultAuditServiceTests(unittest.TestCase):
    def test_run_audit_writes_csv_and_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "\n".join(
                    [
                        "project,canonical_id,intro_time_verdict,manual_review_needed,primary_module,category",
                        "Demo,CVE-2026-0001,correct,no,rest_api,A",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            task_dir = root / "Demo" / "CVE-2026-0001"
            task_dir.mkdir(parents=True)
            (task_dir / "metadata.md").write_text("# metadata\n", encoding="utf-8")
            (task_dir / "evidence_bundle.md").write_text("# evidence\n", encoding="utf-8")
            (task_dir / "01_version_verification.md").write_text(
                "- intro_time_verdict: correct\n- manual_review_needed: no\n",
                encoding="utf-8",
            )
            (task_dir / "02_module_classification.md").write_text("- primary_module: rest_api\n", encoding="utf-8")
            (task_dir / "03_vulnerability_pattern_classification.md").write_text("- category: A\n", encoding="utf-8")
            (task_dir / "04_exploit_condition_summary.md").write_text("- difficulty: \n", encoding="utf-8")

            run = run_audit(root)

            self.assertTrue(run.audit_results_csv_path.exists())
            self.assertTrue(run.audit_results_report_path.exists())
            with open(run.audit_results_csv_path, "r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["project"], "Demo")
            self.assertEqual(rows[0]["needs_manual_review"], "no")
            report_text = run.audit_results_report_path.read_text(encoding="utf-8")
            self.assertIn("Audit Results Report", report_text)
            self.assertIn("Total Tasks", report_text)

    def test_run_audit_respects_custom_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "package"
            output_dir = Path(temp_dir) / "artifacts"
            root.mkdir(parents=True)
            (root / "summary.csv").write_text(
                "project,canonical_id\nDemo,CVE-2026-0001\n",
                encoding="utf-8",
            )

            run = run_audit(root, output_dir)

            self.assertEqual(run.output_dir, output_dir.resolve())
            self.assertTrue((output_dir / "audit_results.csv").exists())
            self.assertTrue((output_dir / "audit_results_report.md").exists())


if __name__ == "__main__":
    unittest.main()
