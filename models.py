from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class VulnerabilityTask:
    project: str
    github_url: str
    owner: str
    repo: str
    source: str
    cve_id: Optional[str]
    adv_id: Optional[str]
    canonical_id: str
    task_key: str
    publish_at: Optional[str]
    cwe: Optional[str]
    cve_dir: Optional[Path] = None
    advisory_dir: Optional[Path] = None
    primary_data_dir: Optional[Path] = None
    status: str = "pending"
    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None


@dataclass
class VulnEvidence:
    task: VulnerabilityTask
    timeline: Optional[dict] = None
    relevance: Optional[dict] = None
    issue_text: Optional[str] = None
    root_cause: Optional[str] = None
    root_cause_zh: Optional[str] = None
    sast: Optional[dict] = None
    intro_commit: Optional[str] = None
    intro_parent_commit: Optional[str] = None
    intro_date: Optional[str] = None
    fix_commit: Optional[str] = None
    fix_parent_commit: Optional[str] = None
    fix_date: Optional[str] = None
    disclosure_date: Optional[str] = None
    project_profile: Optional[dict] = None
    architecture_type: Optional[str] = None
    vuln_positions: list[dict] = field(default_factory=list)
    dataflow: list[dict] = field(default_factory=list)
    code_at_intro: dict[str, str] = field(default_factory=dict)
    code_at_intro_parent: dict[str, str] = field(default_factory=dict)
    intro_diff: Optional[str] = None
    fix_diff: Optional[str] = None
    fail_code: Optional[str] = None
    fail_reason: Optional[str] = None
