from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .models import TaskAuditEvaluation


AUDIT_RESULTS_FIELDNAMES = [
    "project",
    "canonical_id",
    "summary_row_count",
    "summary_row_missing",
    "duplicate_summary_rows",
    "summary_conflict",
    "conflicting_columns",
    "task_dir_present",
    "metadata_present",
    "evidence_bundle_present",
    "required_step_files_present",
    "summary_step_mismatch",
    "mismatch_fields",
    "evidence_missing",
    "needs_manual_review",
    "review_reasons",
]


def write_audit_results_csv(output_path: str | Path, evaluations: list[TaskAuditEvaluation]) -> Path:
    """Write stable machine-readable audit results CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_RESULTS_FIELDNAMES)
        writer.writeheader()
        for evaluation in evaluations:
            writer.writerow(_evaluation_to_csv_row(evaluation))

    return path


def write_audit_results_report(output_path: str | Path, evaluations: list[TaskAuditEvaluation]) -> Path:
    """Write a compact markdown report summarizing audit results."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    total = len(evaluations)
    manual_review = sum(1 for item in evaluations if item.needs_manual_review)
    summary_missing = sum(1 for item in evaluations if item.summary_row_missing)
    duplicate_summary = sum(1 for item in evaluations if item.duplicate_summary_rows)
    summary_conflict = sum(1 for item in evaluations if item.summary_conflict)
    evidence_missing = sum(1 for item in evaluations if item.evidence_missing)
    summary_step_mismatch = sum(1 for item in evaluations if item.summary_step_mismatch)
    reason_counts = Counter(
        reason
        for item in evaluations
        for reason in item.review_reasons
    )

    lines = [
        "# Audit Results Report",
        "",
        "## Summary",
        "",
        f"- **Total Tasks**: {total}",
        f"- **Needs Manual Review**: {manual_review}",
        f"- **Summary Row Missing**: {summary_missing}",
        f"- **Duplicate Summary Rows**: {duplicate_summary}",
        f"- **Summary Conflict**: {summary_conflict}",
        f"- **Evidence Missing**: {evidence_missing}",
        f"- **Summary-Step Mismatch**: {summary_step_mismatch}",
        "",
    ]

    if reason_counts:
        lines.extend([
            "## Review Reasons",
            "",
            "| Reason | Count |",
            "|--------|-------|",
        ])
        for reason, count in reason_counts.most_common():
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    manual_review_examples = [item for item in evaluations if item.needs_manual_review][:20]
    if manual_review_examples:
        lines.extend([
            "## Manual Review Examples",
            "",
            "| Project | Canonical ID | Reasons |",
            "|---------|--------------|---------|",
        ])
        for item in manual_review_examples:
            lines.append(
                f"| {item.project} | {item.canonical_id} | {', '.join(item.review_reasons) or 'none'} |"
            )
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _evaluation_to_csv_row(evaluation: TaskAuditEvaluation) -> dict[str, str | int]:
    return {
        "project": evaluation.project,
        "canonical_id": evaluation.canonical_id,
        "summary_row_count": evaluation.summary_row_count,
        "summary_row_missing": _yes_no(evaluation.summary_row_missing),
        "duplicate_summary_rows": _yes_no(evaluation.duplicate_summary_rows),
        "summary_conflict": _yes_no(evaluation.summary_conflict),
        "conflicting_columns": ",".join(evaluation.conflicting_columns),
        "task_dir_present": _yes_no(evaluation.task_dir_present),
        "metadata_present": _yes_no(evaluation.metadata_present),
        "evidence_bundle_present": _yes_no(evaluation.evidence_bundle_present),
        "required_step_files_present": _yes_no(evaluation.required_step_files_present),
        "summary_step_mismatch": _yes_no(evaluation.summary_step_mismatch),
        "mismatch_fields": ",".join(evaluation.mismatch_fields),
        "evidence_missing": _yes_no(evaluation.evidence_missing),
        "needs_manual_review": _yes_no(evaluation.needs_manual_review),
        "review_reasons": ",".join(evaluation.review_reasons),
    }


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"
