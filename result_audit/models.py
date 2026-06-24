from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


TaskKey = tuple[str, str]


@dataclass(frozen=True)
class SummaryRow:
    """One raw row from summary.csv, keyed by project and canonical_id."""

    row_number: int
    project: str
    canonical_id: str
    values: dict[str, str]

    @property
    def task_key(self) -> TaskKey:
        return (self.project, self.canonical_id)


@dataclass(frozen=True)
class TaskArtifacts:
    """Files discovered for one task directory inside a result package."""

    project: str
    canonical_id: str
    task_dir: Path
    metadata_path: Path | None = None
    evidence_bundle_path: Path | None = None
    step1_path: Path | None = None
    step2_path: Path | None = None
    step3_path: Path | None = None
    step4_path: Path | None = None
    final_case_summary_path: Path | None = None

    @property
    def task_key(self) -> TaskKey:
        return (self.project, self.canonical_id)

    @property
    def known_paths(self) -> dict[str, Path]:
        paths = {
            "metadata.md": self.metadata_path,
            "evidence_bundle.md": self.evidence_bundle_path,
            "01_version_verification.md": self.step1_path,
            "02_module_classification.md": self.step2_path,
            "03_vulnerability_pattern_classification.md": self.step3_path,
            "04_exploit_condition_summary.md": self.step4_path,
            "final_case_summary.md": self.final_case_summary_path,
        }
        return {name: path for name, path in paths.items() if path is not None}

    @property
    def present_filenames(self) -> set[str]:
        return set(self.known_paths)


@dataclass
class ResultPackage:
    """A bounded offline package used as input to the Result Auditor."""

    root_dir: Path
    summary_csv_path: Path | None = None
    batch_report_path: Path | None = None
    audit_report_path: Path | None = None
    preflight_report_path: Path | None = None
    log_paths: list[Path] = field(default_factory=list)
    summary_rows: list[SummaryRow] = field(default_factory=list)
    task_artifacts_by_key: dict[TaskKey, TaskArtifacts] = field(default_factory=dict)
    project_dirs: dict[str, Path] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def task_keys(self) -> set[TaskKey]:
        return set(self.task_artifacts_by_key) | {row.task_key for row in self.summary_rows}

    @property
    def summary_row_count(self) -> int:
        return len(self.summary_rows)

    @property
    def task_dir_count(self) -> int:
        return len(self.task_artifacts_by_key)

    def get_task_artifacts(self, project: str, canonical_id: str) -> TaskArtifacts | None:
        return self.task_artifacts_by_key.get((project, canonical_id))


@dataclass(frozen=True)
class TaskAuditEvaluation:
    """Task-level audit result derived from indexed package artifacts."""

    project: str
    canonical_id: str
    summary_row_count: int = 0
    summary_row_missing: bool = False
    duplicate_summary_rows: bool = False
    summary_conflict: bool = False
    conflicting_columns: tuple[str, ...] = ()
    task_dir_present: bool = False
    metadata_present: bool = False
    evidence_bundle_present: bool = False
    required_step_files_present: bool = False
    summary_step_mismatch: bool = False
    mismatch_fields: tuple[str, ...] = ()
    evidence_missing: bool = False
    needs_manual_review: bool = False
    review_reasons: tuple[str, ...] = ()

    @property
    def task_key(self) -> TaskKey:
        return (self.project, self.canonical_id)
