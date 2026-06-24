from __future__ import annotations

from markdown_parser import normalize_value, parse_task_output

from .models import TaskAuditEvaluation
from .task_index import TaskIndex, TaskIndexEntry


REQUIRED_STEP_FILENAMES = (
    "01_version_verification.md",
    "02_module_classification.md",
    "03_vulnerability_pattern_classification.md",
    "04_exploit_condition_summary.md",
)

SUMMARY_STEP_COMPARISON_FIELDS = (
    "intro_time_verdict",
    "vuln_exists_at_intro_version",
    "manual_review_needed",
    "architecture_type",
    "classification_type",
    "primary_module",
    "secondary_modules",
    "category",
    "category_name",
    "module_from_step2_primary",
    "module_from_step2_secondary",
    "module_from_step2_classification_type",
    "input_type",
    "input_subtype",
    "mechanism_type",
    "mechanism_subtype",
    "requires_ai_function",
    "ai_native_subtype",
    "cross_agent",
    "difficulty",
)


def evaluate_task_index(task_index: TaskIndex) -> list[TaskAuditEvaluation]:
    """Evaluate every indexed task and return stable ordered results."""
    return [
        evaluate_task_entry(task_index.entries_by_key[task_key])
        for task_key in sorted(task_index.entries_by_key)
    ]


def evaluate_task_entry(entry: TaskIndexEntry) -> TaskAuditEvaluation:
    """Evaluate one deduplicated task entry into audit signals."""
    reasons: set[str] = set()
    task_artifacts = entry.task_artifacts
    task_dir_present = task_artifacts is not None
    metadata_present = bool(task_artifacts and task_artifacts.metadata_path)
    evidence_bundle_present = bool(task_artifacts and task_artifacts.evidence_bundle_path)
    required_step_files_present = bool(
        task_artifacts
        and task_artifacts.step1_path
        and task_artifacts.step2_path
        and task_artifacts.step3_path
        and task_artifacts.step4_path
    )

    summary_row_missing = entry.canonical_summary_row is None
    if summary_row_missing:
        reasons.add("summary_row_missing")

    if entry.duplicate_summary_rows:
        reasons.add("duplicate_summary_rows")
    if entry.summary_conflict:
        reasons.add("summary_conflict")

    if not task_dir_present:
        reasons.add("task_dir_missing")
    if not metadata_present:
        reasons.add("metadata_missing")
    if not evidence_bundle_present:
        reasons.add("evidence_bundle_missing")
    if not required_step_files_present:
        reasons.add("step_files_missing")

    evidence_missing = not (
        task_dir_present
        and metadata_present
        and evidence_bundle_present
        and required_step_files_present
    )

    mismatch_fields: tuple[str, ...] = ()
    summary_step_mismatch = False
    if required_step_files_present and task_artifacts and entry.canonical_summary_row:
        mismatch_fields = _collect_mismatch_fields(entry)
        summary_step_mismatch = bool(mismatch_fields)
        if summary_step_mismatch:
            reasons.add("summary_step_mismatch")

    manual_review_requested = _summary_requests_manual_review(entry)
    if manual_review_requested:
        reasons.add("summary_marked_manual_review")

    needs_manual_review = any(
        (
            summary_row_missing,
            entry.summary_conflict,
            evidence_missing,
            summary_step_mismatch,
            manual_review_requested,
        )
    )

    return TaskAuditEvaluation(
        project=entry.project,
        canonical_id=entry.canonical_id,
        summary_row_count=entry.summary_row_count,
        summary_row_missing=summary_row_missing,
        duplicate_summary_rows=entry.duplicate_summary_rows,
        summary_conflict=entry.summary_conflict,
        conflicting_columns=entry.conflicting_columns,
        task_dir_present=task_dir_present,
        metadata_present=metadata_present,
        evidence_bundle_present=evidence_bundle_present,
        required_step_files_present=required_step_files_present,
        summary_step_mismatch=summary_step_mismatch,
        mismatch_fields=mismatch_fields,
        evidence_missing=evidence_missing,
        needs_manual_review=needs_manual_review,
        review_reasons=tuple(sorted(reasons)),
    )


def _collect_mismatch_fields(entry: TaskIndexEntry) -> tuple[str, ...]:
    if entry.task_artifacts is None or entry.canonical_summary_row is None:
        return ()

    step_values = parse_task_output(entry.task_artifacts.task_dir)
    summary_values = entry.canonical_summary_row.values

    mismatches: list[str] = []
    for field_name in SUMMARY_STEP_COMPARISON_FIELDS:
        summary_value = _normalize_comparison_value(summary_values.get(field_name, ""), field_name)
        step_value = _normalize_comparison_value(step_values.get(field_name, ""), field_name)
        if summary_value != step_value:
            mismatches.append(field_name)

    return tuple(mismatches)


def _normalize_comparison_value(value: str, field_name: str) -> str:
    return normalize_value(value, field_name)


def _summary_requests_manual_review(entry: TaskIndexEntry) -> bool:
    if entry.canonical_summary_row is None:
        return False

    manual_review_value = entry.canonical_summary_row.values.get("manual_review_needed", "")
    return _normalize_comparison_value(manual_review_value, "manual_review_needed") == "yes"
