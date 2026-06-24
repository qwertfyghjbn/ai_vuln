from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ResultPackage, TaskAuditEvaluation
from .package_loader import load_result_package
from .report_writer import write_audit_results_csv, write_audit_results_report
from .rules import evaluate_task_index
from .task_index import TaskIndex, build_task_index


AUDIT_RESULTS_CSV_NAME = "audit_results.csv"
AUDIT_RESULTS_REPORT_NAME = "audit_results_report.md"


@dataclass(frozen=True)
class AuditResultsRun:
    package: ResultPackage
    task_index: TaskIndex
    evaluations: list[TaskAuditEvaluation]
    output_dir: Path
    audit_results_csv_path: Path
    audit_results_report_path: Path


def run_audit(package_dir: str | Path, out_dir: str | Path | None = None) -> AuditResultsRun:
    """Run the offline result auditor for one package and write outputs."""
    package = load_result_package(package_dir)
    task_index = build_task_index(package)
    evaluations = evaluate_task_index(task_index)

    output_dir = Path(out_dir).expanduser().resolve() if out_dir else package.root_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    audit_results_csv_path = write_audit_results_csv(output_dir / AUDIT_RESULTS_CSV_NAME, evaluations)
    audit_results_report_path = write_audit_results_report(
        output_dir / AUDIT_RESULTS_REPORT_NAME,
        evaluations,
    )

    return AuditResultsRun(
        package=package,
        task_index=task_index,
        evaluations=evaluations,
        output_dir=output_dir,
        audit_results_csv_path=audit_results_csv_path,
        audit_results_report_path=audit_results_report_path,
    )
