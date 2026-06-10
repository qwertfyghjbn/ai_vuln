from pathlib import Path

from config import Config
from models import VulnerabilityTask


class RecordResolver:
    def __init__(self, config: Config):
        self.config = config
        self.data_root = config.root_dir / config.data_root
        self._project_dir_cache: dict[str, dict[str, str]] = {}

    def resolve(self, task: VulnerabilityTask) -> VulnerabilityTask:
        candidates = []

        if task.cve_id:
            candidates.append(("cve_dir", "cves", task.cve_id))
            candidates.append(("cve_dir", "security_advisories", task.cve_id))

        if task.adv_id:
            candidates.append(("advisory_dir", "security_advisories", task.adv_id))
            candidates.append(("advisory_dir", "cves", task.adv_id))

        matched = []
        attempted = []

        for field_name, subdir, vuln_id in candidates:
            attempted.append(f"{subdir}/{task.project}/{vuln_id}")
            path = self._find_dir(subdir, task.project, vuln_id)
            if path:
                matched.append((field_name, subdir, vuln_id, path))

        task.cve_dir = None
        task.advisory_dir = None
        task.primary_data_dir = None
        task.fail_code = None
        task.fail_reason = None

        for field_name, _subdir, _vuln_id, path in matched:
            if field_name == "cve_dir" and task.cve_dir is None:
                task.cve_dir = path
            elif field_name == "advisory_dir" and task.advisory_dir is None:
                task.advisory_dir = path

        if task.cve_dir:
            task.primary_data_dir = task.cve_dir
        elif task.advisory_dir:
            task.primary_data_dir = task.advisory_dir
        else:
            task.fail_code = "FAIL_NO_VULN_DIR"
            task.fail_reason = self._build_fail_reason(task, attempted)

        return task

    def _find_dir(self, subdir: str, project: str, vuln_id: str) -> Path | None:
        """Find directory with case-insensitive matching."""
        base_dir = self.data_root / subdir

        # Try exact match first
        exact_path = base_dir / project / vuln_id
        if exact_path.exists():
            return exact_path

        # Try case-insensitive match for project directory
        if not base_dir.exists():
            return None

        # Cache project directory mappings
        cache_key = f"{subdir}:{project}"
        if cache_key not in self._project_dir_cache:
            self._project_dir_cache[cache_key] = {}
            for d in base_dir.iterdir():
                if d.is_dir():
                    self._project_dir_cache[cache_key][d.name.lower()] = d.name

        # Find actual project directory name
        actual_project = self._project_dir_cache.get(cache_key, {}).get(project.lower())
        if not actual_project:
            return None

        # Check if vuln_id directory exists
        vuln_path = base_dir / actual_project / vuln_id
        if vuln_path.exists():
            return vuln_path

        return None

    def _build_fail_reason(self, task: VulnerabilityTask, attempted: list[str] | None = None) -> str:
        parts = []
        if task.cve_id:
            parts.append(f"CVE dir not found for {task.cve_id}")
        if task.adv_id:
            parts.append(f"Advisory dir not found for {task.adv_id}")
        if attempted:
            parts.append("attempted: " + ", ".join(attempted))
        if not parts:
            parts.append("No directory paths configured")
        return "; ".join(parts)
