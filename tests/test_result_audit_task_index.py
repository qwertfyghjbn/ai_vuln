from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from result_audit.package_loader import load_result_package
from result_audit.task_index import build_task_index


class ResultTaskIndexTests(unittest.TestCase):
    def test_exact_duplicate_summary_rows_are_deduplicated_without_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "\n".join(
                    [
                        "project,canonical_id,category,primary_module,manual_review_needed",
                        "Demo,CVE-2026-0001,A,rest_api,no",
                        "Demo,CVE-2026-0001,A,rest_api,no",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            package = load_result_package(root)
            index = build_task_index(package)
            entry = index.get("Demo", "CVE-2026-0001")

            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertTrue(entry.duplicate_summary_rows)
            self.assertFalse(entry.summary_conflict)
            self.assertEqual(entry.summary_row_count, 2)
            self.assertEqual(entry.unique_summary_row_count, 1)
            self.assertEqual(entry.conflicting_columns, ())
            self.assertEqual(entry.canonical_summary_row.row_number, 2)

    def test_different_summary_payloads_are_marked_as_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "summary.csv").write_text(
                "\n".join(
                    [
                        "project,canonical_id,category,primary_module,input_subtype,manual_review_needed",
                        "Demo,CVE-2026-0001,A,tool_execution,mcp_tool_arguments,no",
                        "Demo,CVE-2026-0001,A,mcp_server,mcp_tool_call_arguments,no",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            package = load_result_package(root)
            index = build_task_index(package)
            entry = index.get("Demo", "CVE-2026-0001")

            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertTrue(entry.duplicate_summary_rows)
            self.assertTrue(entry.summary_conflict)
            self.assertEqual(entry.summary_row_count, 2)
            self.assertEqual(entry.unique_summary_row_count, 2)
            self.assertEqual(entry.conflicting_columns, ("input_subtype", "primary_module"))
            self.assertEqual(entry.canonical_summary_row.values["primary_module"], "tool_execution")

    def test_task_dir_without_summary_row_still_gets_index_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / "Demo" / "CVE-2026-0001"
            task_dir.mkdir(parents=True)
            (task_dir / "metadata.md").write_text("# meta\n", encoding="utf-8")

            package = load_result_package(root)
            index = build_task_index(package)
            entry = index.get("Demo", "CVE-2026-0001")

            self.assertIsNotNone(entry)
            assert entry is not None
            self.assertEqual(entry.summary_row_count, 0)
            self.assertEqual(entry.unique_summary_row_count, 0)
            self.assertFalse(entry.duplicate_summary_rows)
            self.assertFalse(entry.summary_conflict)
            self.assertIsNotNone(entry.task_artifacts)


if __name__ == "__main__":
    unittest.main()
