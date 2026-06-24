from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from result_audit.package_loader import load_result_package
from result_audit.rules import evaluate_task_entry, evaluate_task_index
from result_audit.task_index import build_task_index


def _write_complete_task_package(
    root: Path,
    summary_rows: list[str],
    *,
    metadata: bool = True,
    evidence_bundle: bool = True,
    step1: str | None = None,
    step2: str | None = None,
    step3: str | None = None,
    step4: str | None = None,
) -> None:
    (root / "summary.csv").write_text(
        "\n".join(
            ["project,canonical_id,intro_time_verdict,manual_review_needed,primary_module,category"] + summary_rows
        )
        + "\n",
        encoding="utf-8",
    )
    task_dir = root / "Demo" / "CVE-2026-0001"
    task_dir.mkdir(parents=True)
    if metadata:
        (task_dir / "metadata.md").write_text("# metadata\n", encoding="utf-8")
    if evidence_bundle:
        (task_dir / "evidence_bundle.md").write_text("# evidence\n", encoding="utf-8")
    if step1 is not None:
        (task_dir / "01_version_verification.md").write_text(step1, encoding="utf-8")
    if step2 is not None:
        (task_dir / "02_module_classification.md").write_text(step2, encoding="utf-8")
    if step3 is not None:
        (task_dir / "03_vulnerability_pattern_classification.md").write_text(step3, encoding="utf-8")
    if step4 is not None:
        (task_dir / "04_exploit_condition_summary.md").write_text(step4, encoding="utf-8")


class ResultAuditRulesTests(unittest.TestCase):
    def test_consistent_complete_task_does_not_need_manual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_task_package(
                root,
                ["Demo,CVE-2026-0001,correct,no,rest_api,A"],
                step1="- intro_time_verdict: correct\n- manual_review_needed: no\n",
                step2="- primary_module: rest_api\n",
                step3="- category: A\n",
                step4="- difficulty: \n",
            )

            index = build_task_index(load_result_package(root))
            entry = index.get("Demo", "CVE-2026-0001")
            evaluation = evaluate_task_entry(entry)

            self.assertFalse(evaluation.evidence_missing)
            self.assertFalse(evaluation.summary_conflict)
            self.assertFalse(evaluation.summary_step_mismatch)
            self.assertFalse(evaluation.needs_manual_review)
            self.assertEqual(evaluation.review_reasons, ())

    def test_exact_duplicate_rows_do_not_create_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            row = "Demo,CVE-2026-0001,correct,no,rest_api,A"
            _write_complete_task_package(
                root,
                [row, row],
                step1="- intro_time_verdict: correct\n- manual_review_needed: no\n",
                step2="- primary_module: rest_api\n",
                step3="- category: A\n",
                step4="- difficulty: \n",
            )

            entry = build_task_index(load_result_package(root)).get("Demo", "CVE-2026-0001")
            evaluation = evaluate_task_entry(entry)

            self.assertTrue(evaluation.duplicate_summary_rows)
            self.assertFalse(evaluation.summary_conflict)
            self.assertFalse(evaluation.needs_manual_review)
            self.assertEqual(evaluation.review_reasons, ("duplicate_summary_rows",))

    def test_conflicting_duplicate_rows_require_manual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_task_package(
                root,
                [
                    "Demo,CVE-2026-0001,correct,no,rest_api,A",
                    "Demo,CVE-2026-0001,correct,no,mcp_server,A",
                ],
                step1="- intro_time_verdict: correct\n- manual_review_needed: no\n",
                step2="- primary_module: rest_api\n",
                step3="- category: A\n",
                step4="- difficulty: \n",
            )

            entry = build_task_index(load_result_package(root)).get("Demo", "CVE-2026-0001")
            evaluation = evaluate_task_entry(entry)

            self.assertTrue(evaluation.summary_conflict)
            self.assertTrue(evaluation.needs_manual_review)
            self.assertEqual(evaluation.conflicting_columns, ("primary_module",))
            self.assertIn("summary_conflict", evaluation.review_reasons)

    def test_missing_evidence_files_require_manual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_task_package(
                root,
                ["Demo,CVE-2026-0001,correct,no,rest_api,A"],
                evidence_bundle=False,
                step1="- intro_time_verdict: correct\n- manual_review_needed: no\n",
                step2="- primary_module: rest_api\n",
                step3="- category: A\n",
                step4=None,
            )

            entry = build_task_index(load_result_package(root)).get("Demo", "CVE-2026-0001")
            evaluation = evaluate_task_entry(entry)

            self.assertTrue(evaluation.evidence_missing)
            self.assertTrue(evaluation.needs_manual_review)
            self.assertFalse(evaluation.evidence_bundle_present)
            self.assertFalse(evaluation.required_step_files_present)
            self.assertIn("evidence_bundle_missing", evaluation.review_reasons)
            self.assertIn("step_files_missing", evaluation.review_reasons)

    def test_summary_step_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_task_package(
                root,
                ["Demo,CVE-2026-0001,correct,no,rest_api,A"],
                step1="- intro_time_verdict: likely_correct\n- manual_review_needed: no\n",
                step2="- primary_module: rest_api\n",
                step3="- category: A\n",
                step4="- difficulty: \n",
            )

            entry = build_task_index(load_result_package(root)).get("Demo", "CVE-2026-0001")
            evaluation = evaluate_task_entry(entry)

            self.assertTrue(evaluation.summary_step_mismatch)
            self.assertTrue(evaluation.needs_manual_review)
            self.assertEqual(evaluation.mismatch_fields, ("intro_time_verdict",))
            self.assertIn("summary_step_mismatch", evaluation.review_reasons)

    def test_task_dir_without_summary_row_requires_manual_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_dir = root / "Demo" / "CVE-2026-0001"
            task_dir.mkdir(parents=True)
            (task_dir / "metadata.md").write_text("# metadata\n", encoding="utf-8")
            (task_dir / "evidence_bundle.md").write_text("# evidence\n", encoding="utf-8")
            (task_dir / "01_version_verification.md").write_text("- intro_time_verdict: correct\n", encoding="utf-8")
            (task_dir / "02_module_classification.md").write_text("- primary_module: rest_api\n", encoding="utf-8")
            (task_dir / "03_vulnerability_pattern_classification.md").write_text("- category: A\n", encoding="utf-8")
            (task_dir / "04_exploit_condition_summary.md").write_text("- difficulty: easy\n", encoding="utf-8")

            evaluations = evaluate_task_index(build_task_index(load_result_package(root)))

            self.assertEqual(len(evaluations), 1)
            evaluation = evaluations[0]
            self.assertTrue(evaluation.summary_row_missing)
            self.assertTrue(evaluation.needs_manual_review)
            self.assertIn("summary_row_missing", evaluation.review_reasons)


if __name__ == "__main__":
    unittest.main()
