from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from result_audit.package_loader import load_result_package


class ResultPackageLoaderTests(unittest.TestCase):
    def test_loads_root_level_artifacts_without_task_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "project,canonical_id,category\nDemo,CVE-2026-0001,A\n",
                encoding="utf-8",
            )
            (root / "audit_report.md").write_text("# Audit\n", encoding="utf-8")
            (root / "batch_report.md").write_text("# Batch\n", encoding="utf-8")
            (root / "sdk_batch_test.log").write_text("ok\n", encoding="utf-8")

            package = load_result_package(root)

            self.assertEqual(package.summary_row_count, 1)
            self.assertEqual(package.task_dir_count, 0)
            self.assertEqual(package.task_keys, {("Demo", "CVE-2026-0001")})
            self.assertIsNotNone(package.summary_csv_path)
            self.assertIsNotNone(package.audit_report_path)
            self.assertEqual([path.name for path in package.log_paths], ["sdk_batch_test.log"])

    def test_loads_project_task_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "project,canonical_id,category\nDemo,CVE-2026-0001,A\n",
                encoding="utf-8",
            )
            task_dir = root / "Demo" / "CVE-2026-0001"
            task_dir.mkdir(parents=True)
            (task_dir / "metadata.md").write_text("# meta\n", encoding="utf-8")
            (task_dir / "01_version_verification.md").write_text("- intro_time_verdict: correct\n", encoding="utf-8")
            (task_dir / "03_vulnerability_pattern_classification.md").write_text("- category: A\n", encoding="utf-8")

            package = load_result_package(root)

            self.assertEqual(package.task_dir_count, 1)
            self.assertEqual(package.project_dirs["Demo"], root / "Demo")
            artifacts = package.get_task_artifacts("Demo", "CVE-2026-0001")
            self.assertIsNotNone(artifacts)
            assert artifacts is not None
            self.assertEqual(
                artifacts.present_filenames,
                {"metadata.md", "01_version_verification.md", "03_vulnerability_pattern_classification.md"},
            )

    def test_skips_invalid_summary_rows_and_records_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "project,canonical_id,category\nDemo,,A\n,GHSA-1,B\n",
                encoding="utf-8",
            )

            package = load_result_package(root)

            self.assertEqual(package.summary_row_count, 0)
            self.assertEqual(len(package.warnings), 2)


if __name__ == "__main__":
    unittest.main()
