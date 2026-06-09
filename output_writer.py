import csv
from pathlib import Path

from config import Config
from models import VulnerabilityTask, VulnEvidence


class OutputWriter:
    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.root_dir / config.output_dir

    def task_dir(self, task: VulnerabilityTask) -> Path:
        """Get output directory for a task."""
        return self.output_dir / task.project / task.canonical_id

    def write_metadata(self, task: VulnerabilityTask) -> None:
        """Write metadata.md for a task."""
        task_path = self.task_dir(task)
        task_path.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# {task.canonical_id}",
            "",
            "## Basic Info",
            "",
            f"- **Project**: {task.project}",
            f"- **GitHub URL**: {task.github_url}",
            f"- **Owner**: {task.owner}",
            f"- **Repo**: {task.repo}",
            f"- **Source**: {task.source}",
            f"- **CVE ID**: {task.cve_id or 'N/A'}",
            f"- **Advisory ID**: {task.adv_id or 'N/A'}",
            f"- **Canonical ID**: {task.canonical_id}",
            f"- **Task Key**: {task.task_key}",
            f"- **Published At**: {task.publish_at or 'N/A'}",
            f"- **CWE**: {task.cwe or 'N/A'}",
            "",
            "## Data Paths",
            "",
            f"- **CVE Dir**: {task.cve_dir or 'N/A'}",
            f"- **Advisory Dir**: {task.advisory_dir or 'N/A'}",
            f"- **Primary Data Dir**: {task.primary_data_dir or 'N/A'}",
            "",
        ]

        if task.fail_code:
            lines.extend([
                "## Failure Info",
                "",
                f"- **Fail Code**: {task.fail_code}",
                f"- **Fail Reason**: {task.fail_reason or 'N/A'}",
                "",
            ])

        (task_path / "metadata.md").write_text("\n".join(lines), encoding="utf-8")

    def write_failure(self, task: VulnerabilityTask) -> None:
        """Write failure info for a task."""
        self.write_metadata(task)

    def write_step_file(self, task: VulnerabilityTask, filename: str, content: str) -> None:
        """Write a step analysis file."""
        task_path = self.task_dir(task)
        task_path.mkdir(parents=True, exist_ok=True)
        (task_path / filename).write_text(content, encoding="utf-8")

    def write_evidence_bundle(self, evidence: VulnEvidence) -> None:
        """Write evidence_bundle.md for a task."""
        task_path = self.task_dir(evidence.task)
        task_path.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Evidence Bundle: {evidence.task.canonical_id}",
            "",
        ]

        # Timeline
        if evidence.timeline:
            lines.extend([
                "## Timeline",
                "",
                f"- **Intro Commit**: {evidence.intro_commit or 'N/A'}",
                f"- **Intro Parent**: {evidence.intro_parent_commit or 'N/A'}",
                f"- **Intro Date**: {evidence.intro_date or 'N/A'}",
                f"- **Fix Commit**: {evidence.fix_commit or 'N/A'}",
                f"- **Fix Parent**: {evidence.fix_parent_commit or 'N/A'}",
                f"- **Fix Date**: {evidence.fix_date or 'N/A'}",
                f"- **Disclosure Date**: {evidence.disclosure_date or 'N/A'}",
                "",
            ])

        # Root Cause
        if evidence.root_cause or evidence.root_cause_zh:
            lines.extend([
                "## Root Cause",
                "",
            ])
            if evidence.root_cause_zh:
                lines.append(f"### Chinese\n\n{evidence.root_cause_zh}\n")
            if evidence.root_cause:
                lines.append(f"### English\n\n{evidence.root_cause}\n")

        # SAST
        if evidence.vuln_positions:
            lines.extend([
                "## Vulnerability Positions",
                "",
            ])
            for pos in evidence.vuln_positions:
                lines.append(f"- `{pos.get('file', 'N/A')}:{pos.get('line_start', '?')}-{pos.get('line_end', '?')}` ({pos.get('role', 'unknown')})")
            lines.append("")

        if evidence.dataflow:
            lines.extend([
                "## Dataflow",
                "",
            ])
            for flow in evidence.dataflow:
                lines.append(f"- `{flow.get('file', 'N/A')}:{flow.get('line', '?')}` ({flow.get('type', 'unknown')}): {flow.get('description', '')}")
            lines.append("")

        # Intro Diff
        if evidence.intro_diff:
            lines.extend([
                "## Intro Diff",
                "",
                "```diff",
                evidence.intro_diff[:40000],
                "```",
                "",
            ])

        # Fix Diff
        if evidence.fix_diff:
            lines.extend([
                "## Fix Diff",
                "",
                "```diff",
                evidence.fix_diff[:40000],
                "```",
                "",
            ])

        # Code at Intro
        if evidence.code_at_intro:
            lines.extend([
                "## Code at Intro Commit",
                "",
            ])
            for key, code in evidence.code_at_intro.items():
                lines.extend([
                    f"### {key}",
                    "",
                    "```python",
                    code[:10000],
                    "```",
                    "",
                ])

        # Code at Intro Parent
        if evidence.code_at_intro_parent:
            lines.extend([
                "## Code at Intro Parent",
                "",
            ])
            for key, code in evidence.code_at_intro_parent.items():
                lines.extend([
                    f"### {key}",
                    "",
                    "```python",
                    code[:10000],
                    "```",
                    "",
                ])

        # Fail info
        if evidence.fail_code:
            lines.extend([
                "## Failure",
                "",
                f"- **Code**: {evidence.fail_code}",
                f"- **Reason**: {evidence.fail_reason or 'N/A'}",
                "",
            ])

        (task_path / "evidence_bundle.md").write_text("\n".join(lines), encoding="utf-8")

    def write_final_summary(self, task: VulnerabilityTask, sections: dict[str, str]) -> None:
        """Write final_case_summary.md for a task."""
        task_path = self.task_dir(task)
        task_path.mkdir(parents=True, exist_ok=True)

        lines = [
            f"# Final Case Summary: {task.canonical_id}",
            "",
        ]

        for section_name, content in sections.items():
            lines.append(f"## {section_name}")
            lines.append("")
            lines.append(content)
            lines.append("")

        (task_path / "final_case_summary.md").write_text("\n".join(lines), encoding="utf-8")

    def append_summary_csv(self, row: dict) -> None:
        """Append a row to summary.csv."""
        csv_path = self.output_dir / "summary.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        # Get all possible fieldnames
        fieldnames = [
            "project", "canonical_id", "source", "cwe",
            "publish_at", "cve_id", "adv_id",
            "intro_time_verdict", "vuln_exists_at_intro_version", "manual_review_needed",
            "architecture_type", "architecture_confidence",
            "classification_type", "primary_module", "secondary_modules",
            "category", "category_name",
            "module_from_step2_primary", "module_from_step2_secondary", "module_from_step2_classification_type",
            "input_type", "input_subtype", "mechanism_type", "mechanism_subtype",
            "requires_ai_function", "ai_native_subtype", "cross_agent",
            "difficulty", "confidence",
            "overall_confidence", "manual_review_reason",
            "fail_code", "fail_reason",
        ]

        file_exists = csv_path.exists()

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
