from __future__ import annotations

from dataclasses import dataclass, field

from .models import ResultPackage, SummaryRow, TaskArtifacts, TaskKey


SUMMARY_KEY_COLUMNS = ("project", "canonical_id")


@dataclass(frozen=True)
class TaskIndexEntry:
    """Deduplicated task view built from one Result Package."""

    project: str
    canonical_id: str
    summary_rows: list[SummaryRow] = field(default_factory=list)
    unique_summary_rows: list[SummaryRow] = field(default_factory=list)
    duplicate_summary_rows: bool = False
    summary_conflict: bool = False
    conflicting_columns: tuple[str, ...] = ()
    task_artifacts: TaskArtifacts | None = None

    @property
    def task_key(self) -> TaskKey:
        return (self.project, self.canonical_id)

    @property
    def summary_row_count(self) -> int:
        return len(self.summary_rows)

    @property
    def unique_summary_row_count(self) -> int:
        return len(self.unique_summary_rows)

    @property
    def canonical_summary_row(self) -> SummaryRow | None:
        if not self.unique_summary_rows:
            return None
        return self.unique_summary_rows[0]


@dataclass(frozen=True)
class TaskIndex:
    """Indexed task-level view of a Result Package."""

    entries_by_key: dict[TaskKey, TaskIndexEntry]

    @property
    def task_count(self) -> int:
        return len(self.entries_by_key)

    def get(self, project: str, canonical_id: str) -> TaskIndexEntry | None:
        return self.entries_by_key.get((project, canonical_id))


def build_task_index(result_package: ResultPackage) -> TaskIndex:
    """Build one deterministic task entry per (project, canonical_id)."""
    rows_by_key: dict[TaskKey, list[SummaryRow]] = {}
    for row in result_package.summary_rows:
        rows_by_key.setdefault(row.task_key, []).append(row)

    entries_by_key: dict[TaskKey, TaskIndexEntry] = {}
    for task_key in sorted(result_package.task_keys):
        summary_rows = rows_by_key.get(task_key, [])
        unique_summary_rows = _dedupe_summary_rows(summary_rows)
        conflicting_columns = _collect_conflicting_columns(unique_summary_rows)
        entries_by_key[task_key] = TaskIndexEntry(
            project=task_key[0],
            canonical_id=task_key[1],
            summary_rows=list(summary_rows),
            unique_summary_rows=unique_summary_rows,
            duplicate_summary_rows=len(summary_rows) > 1,
            summary_conflict=len(unique_summary_rows) > 1,
            conflicting_columns=conflicting_columns,
            task_artifacts=result_package.task_artifacts_by_key.get(task_key),
        )

    return TaskIndex(entries_by_key=entries_by_key)


def _dedupe_summary_rows(summary_rows: list[SummaryRow]) -> list[SummaryRow]:
    unique_rows: list[SummaryRow] = []
    seen_signatures: set[tuple[tuple[str, str], ...]] = set()

    for row in summary_rows:
        signature = _row_signature(row)
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        unique_rows.append(row)

    return unique_rows


def _collect_conflicting_columns(summary_rows: list[SummaryRow]) -> tuple[str, ...]:
    if len(summary_rows) <= 1:
        return ()

    all_columns = set()
    for row in summary_rows:
        all_columns.update(row.values)

    conflicts: list[str] = []
    for column in sorted(all_columns):
        if column in SUMMARY_KEY_COLUMNS:
            continue
        distinct_values = {row.values.get(column, "") for row in summary_rows}
        if len(distinct_values) > 1:
            conflicts.append(column)

    return tuple(conflicts)


def _row_signature(summary_row: SummaryRow) -> tuple[tuple[str, str], ...]:
    payload = [
        (column, value)
        for column, value in summary_row.values.items()
        if column not in SUMMARY_KEY_COLUMNS
    ]
    return tuple(sorted(payload))
