from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from result_audit.service import run_audit


FIXTURES_ROOT = Path(__file__).parent / "fixtures" / "result_packages"


class ResultAuditFixtureRegressionTests(unittest.TestCase):
    def test_complete_package_fixture(self):
        run, rows, report_text = _run_fixture("complete_package")

        self.assertEqual(len(run.evaluations), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project"], "Demo")
        self.assertEqual(rows[0]["canonical_id"], "CVE-2026-0001")
        self.assertEqual(rows[0]["needs_manual_review"], "no")
        self.assertEqual(rows[0]["evidence_missing"], "no")
        self.assertIn("- **Needs Manual Review**: 0", report_text)
        self.assertIn("- **Evidence Missing**: 0", report_text)

    def test_duplicate_conflict_package_fixture(self):
        run, rows, report_text = _run_fixture("duplicate_conflict_package")

        self.assertEqual(len(run.evaluations), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["canonical_id"], "CVE-2026-0002")
        self.assertEqual(rows[0]["duplicate_summary_rows"], "yes")
        self.assertEqual(rows[0]["summary_conflict"], "yes")
        self.assertEqual(rows[0]["needs_manual_review"], "yes")
        self.assertIn("primary_module", rows[0]["conflicting_columns"])
        self.assertIn("summary_conflict", rows[0]["review_reasons"])
        self.assertIn("- **Summary Conflict**: 1", report_text)

    def test_missing_evidence_package_fixture(self):
        run, rows, report_text = _run_fixture("missing_evidence_package")

        self.assertEqual(len(run.evaluations), 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["canonical_id"], "CVE-2026-0003")
        self.assertEqual(rows[0]["evidence_missing"], "yes")
        self.assertEqual(rows[0]["needs_manual_review"], "yes")
        self.assertEqual(rows[0]["evidence_bundle_present"], "no")
        self.assertEqual(rows[0]["required_step_files_present"], "no")
        self.assertIn("evidence_bundle_missing", rows[0]["review_reasons"])
        self.assertIn("step_files_missing", rows[0]["review_reasons"])
        self.assertIn("- **Evidence Missing**: 1", report_text)


def _run_fixture(fixture_name: str):
    fixture_dir = FIXTURES_ROOT / fixture_name
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        run = run_audit(fixture_dir, output_dir)
        with open(run.audit_results_csv_path, "r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        report_text = run.audit_results_report_path.read_text(encoding="utf-8")
        return run, rows, report_text


if __name__ == "__main__":
    unittest.main()
