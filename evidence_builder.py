import json
from pathlib import Path

from config import Config
from models import VulnerabilityTask, VulnEvidence


class EvidenceBuilder:
    def __init__(self, config: Config):
        self.config = config

    def build(self, task: VulnerabilityTask) -> VulnEvidence:
        evidence = VulnEvidence(task=task)

        if not task.primary_data_dir:
            evidence.fail_code = "FAIL_NO_DATA_DIR"
            evidence.fail_reason = "No primary data directory"
            return evidence

        data_dir = task.primary_data_dir

        # Load timeline
        evidence.timeline = self._load_json(data_dir / "relevance_out" / "timeline.json")
        self._extract_timeline(evidence)

        # Load relevance
        evidence.relevance = self._load_json(data_dir / "relevance_out" / "relevance.json")

        # Load issue text
        evidence.issue_text = self._load_text(data_dir / "verify_requirements" / "one_issue.txt")

        # Load root cause
        evidence.root_cause = self._load_text(data_dir / "verify_requirements" / "root_cause.md")
        evidence.root_cause_zh = self._load_text(data_dir / "verify_requirements" / "root_cause_zh.md")

        # Load SAST
        evidence.sast = self._load_json(data_dir / "verify_requirements" / "sast_standardized.json")
        self._extract_sast(evidence)

        # Build project profile
        evidence.project_profile = self._build_project_profile(task)
        evidence.architecture_type = "unknown"

        return evidence

    def _load_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _load_text(self, path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    def _extract_timeline(self, evidence: VulnEvidence) -> None:
        if not evidence.timeline:
            return

        intro = evidence.timeline.get("introduction", {})
        fix = evidence.timeline.get("fix", {})
        disclosure = evidence.timeline.get("public_disclosure", {})

        evidence.intro_commit = intro.get("commit")
        evidence.intro_date = intro.get("date")
        evidence.fix_commit = fix.get("commit")
        evidence.fix_date = fix.get("date")
        evidence.disclosure_date = disclosure.get("date")

    def _extract_sast(self, evidence: VulnEvidence) -> None:
        if not evidence.sast:
            return

        findings = evidence.sast.get("findings", [])
        for finding in findings:
            # Extract vulnerability positions
            for pos in finding.get("vul_pos", []):
                evidence.vuln_positions.append({
                    "file": pos.get("file"),
                    "line_start": pos.get("line_start"),
                    "line_end": pos.get("line_end"),
                    "role": pos.get("role"),
                })

            # Extract dataflow
            for flow in finding.get("dataflow", []):
                evidence.dataflow.append({
                    "file": flow.get("file"),
                    "line": flow.get("line"),
                    "type": flow.get("type"),
                    "description": flow.get("description"),
                })

    def _build_project_profile(self, task: VulnerabilityTask) -> dict:
        return {
            "project": task.project,
            "github_url": task.github_url,
            "owner": task.owner,
            "repo": task.repo,
            "architecture_type": "unknown",
            "description": "",
        }
