from __future__ import annotations

import csv
from pathlib import Path

from .models import ResultPackage, SummaryRow, TaskArtifacts


KNOWN_TASK_FILENAMES = {
    "metadata.md",
    "evidence_bundle.md",
    "01_version_verification.md",
    "02_module_classification.md",
    "03_vulnerability_pattern_classification.md",
    "04_exploit_condition_summary.md",
    "final_case_summary.md",
}


def load_result_package(package_dir: str | Path) -> ResultPackage:
    """Load an offline Result Package from disk without touching repos or git."""
    root_dir = Path(package_dir).expanduser().resolve()
    if not root_dir.exists():
        raise FileNotFoundError(f"Result package directory does not exist: {root_dir}")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"Result package path is not a directory: {root_dir}")

    summary_csv_path = _existing_file(root_dir / "summary.csv")
    batch_report_path = _existing_file(root_dir / "batch_report.md")
    audit_report_path = _existing_file(root_dir / "audit_report.md")
    preflight_report_path = _existing_file(root_dir / "preflight_report.md")
    log_paths = sorted(path for path in root_dir.glob("*.log") if path.is_file())

    result = ResultPackage(
        root_dir=root_dir,
        summary_csv_path=summary_csv_path,
        batch_report_path=batch_report_path,
        audit_report_path=audit_report_path,
        preflight_report_path=preflight_report_path,
        log_paths=log_paths,
    )
    result.summary_rows.extend(_load_summary_rows(summary_csv_path, result.warnings))

    project_dirs, task_artifacts_by_key = _scan_task_artifacts(root_dir)
    result.project_dirs.update(project_dirs)
    result.task_artifacts_by_key.update(task_artifacts_by_key)

    return result


def _existing_file(path: Path) -> Path | None:
    return path if path.is_file() else None


def _load_summary_rows(summary_csv_path: Path | None, warnings: list[str]) -> list[SummaryRow]:
    if summary_csv_path is None:
        warnings.append("summary.csv is missing from result package root")
        return []

    rows: list[SummaryRow] = []
    with open(summary_csv_path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=2):
            normalized = {key: (value or "").strip() for key, value in row.items() if key is not None}
            project = normalized.get("project", "")
            canonical_id = normalized.get("canonical_id", "")
            if not project or not canonical_id:
                warnings.append(
                    f"summary.csv row {row_number} is missing project or canonical_id and was skipped"
                )
                continue

            rows.append(
                SummaryRow(
                    row_number=row_number,
                    project=project,
                    canonical_id=canonical_id,
                    values=normalized,
                )
            )

    return rows


def _scan_task_artifacts(root_dir: Path) -> tuple[dict[str, Path], dict[tuple[str, str], TaskArtifacts]]:
    project_dirs: dict[str, Path] = {}
    task_artifacts_by_key: dict[tuple[str, str], TaskArtifacts] = {}

    for project_dir in sorted(root_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith("."):
            continue

        task_dirs = [
            task_dir
            for task_dir in sorted(project_dir.iterdir())
            if task_dir.is_dir() and not task_dir.name.startswith(".") and _looks_like_task_dir(task_dir)
        ]
        if not task_dirs:
            continue

        project_dirs[project_dir.name] = project_dir
        for task_dir in task_dirs:
            artifacts = TaskArtifacts(
                project=project_dir.name,
                canonical_id=task_dir.name,
                task_dir=task_dir,
                metadata_path=_existing_file(task_dir / "metadata.md"),
                evidence_bundle_path=_existing_file(task_dir / "evidence_bundle.md"),
                step1_path=_existing_file(task_dir / "01_version_verification.md"),
                step2_path=_existing_file(task_dir / "02_module_classification.md"),
                step3_path=_existing_file(task_dir / "03_vulnerability_pattern_classification.md"),
                step4_path=_existing_file(task_dir / "04_exploit_condition_summary.md"),
                final_case_summary_path=_existing_file(task_dir / "final_case_summary.md"),
            )
            task_artifacts_by_key[artifacts.task_key] = artifacts

    return project_dirs, task_artifacts_by_key


def _looks_like_task_dir(task_dir: Path) -> bool:
    present_names = {path.name for path in task_dir.iterdir() if path.is_file()}
    return bool(present_names & KNOWN_TASK_FILENAMES)
