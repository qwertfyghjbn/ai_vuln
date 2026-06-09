import subprocess
from pathlib import Path

from config import Config
from models import VulnerabilityTask, VulnEvidence


class RepoManager:
    def __init__(self, config: Config):
        self.config = config
        self.repos_dir = config.root_dir / config.repos_dir
        self.worktrees_dir = config.root_dir / config.worktrees_dir

    def ensure_repo(self, task: VulnerabilityTask) -> Path | None:
        """Clone or fetch repository. Returns repo path or None on failure."""
        repo_path = self.repos_dir / task.project

        if repo_path.exists():
            # Fetch latest
            try:
                self._run_git(repo_path, ["fetch", "--all", "--tags", "--prune"], timeout=180)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass  # Fetch failure is not fatal
            return repo_path

        # Clone with partial blob filter for faster clone
        try:
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            self._run_git(None, [
                "clone", "--filter=blob:none", task.github_url, str(repo_path)
            ], timeout=600)
            return repo_path
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

    def get_parent_commit(self, repo_path: Path, commit: str) -> str | None:
        """Get parent commit hash."""
        try:
            result = self._run_git(repo_path, ["rev-parse", f"{commit}~1"])
            return result.strip()
        except subprocess.CalledProcessError:
            return None

    def create_worktree(
        self, repo_path: Path, task: VulnerabilityTask, commit: str, label: str
    ) -> Path | None:
        """Create a worktree for a specific commit."""
        worktree_name = f"{task.project}_{task.canonical_id}_{label}"
        worktree_path = self.worktrees_dir / worktree_name

        if worktree_path.exists():
            return worktree_path

        try:
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            # Use absolute path for worktree
            abs_worktree_path = worktree_path.resolve()
            self._run_git(repo_path, [
                "worktree", "add", "--detach", str(abs_worktree_path), commit
            ])
            return worktree_path
        except subprocess.CalledProcessError:
            return None

    def remove_worktree(self, repo_path: Path, worktree_path: Path) -> None:
        """Remove a worktree."""
        try:
            self._run_git(repo_path, ["worktree", "remove", "--force", str(worktree_path)])
        except subprocess.CalledProcessError:
            pass

    def collect_diff(
        self, repo_path: Path, from_commit: str, to_commit: str, paths: list[str] | None = None
    ) -> str | None:
        """Collect diff between two commits."""
        cmd = ["diff", f"{from_commit}..{to_commit}"]
        if paths:
            cmd.append("--")
            cmd.extend(paths)

        try:
            result = self._run_git(repo_path, cmd)
            # Truncate if too long
            if len(result) > 80000:
                result = result[:80000] + "\n\n... (truncated)"
            return result
        except subprocess.CalledProcessError:
            return None

    def collect_file_windows(
        self, worktree_path: Path, positions: list[dict], context_lines: int = 40
    ) -> dict[str, str]:
        """Read code windows around vulnerability positions."""
        windows = {}

        for pos in positions:
            file_path = worktree_path / pos["file"]
            if not file_path.exists():
                continue

            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, pos.get("line_start", 1) - context_lines - 1)
                end = min(len(lines), pos.get("line_end", pos.get("line_start", 1)) + context_lines)

                # Limit to 300 lines per file
                if end - start > 300:
                    end = start + 300

                window = "\n".join(lines[start:end])
                key = f"{pos['file']}:{start+1}-{end}"
                windows[key] = window
            except (OSError, UnicodeDecodeError):
                continue

        return windows

    def collect_evidence(self, evidence: VulnEvidence) -> None:
        """Collect code evidence for a task."""
        task = evidence.task

        if not task.primary_data_dir:
            evidence.fail_code = "FAIL_NO_DATA_DIR"
            return

        if not evidence.intro_commit:
            evidence.fail_code = "FAIL_NO_INTRO_COMMIT"
            evidence.fail_reason = "No introduction commit found"
            return

        # Ensure repo
        repo_path = self.ensure_repo(task)
        if not repo_path:
            evidence.fail_code = "FAIL_REPO_CLONE"
            evidence.fail_reason = "Failed to clone or access repository"
            return

        # Get parent commits
        evidence.intro_parent_commit = self.get_parent_commit(repo_path, evidence.intro_commit)
        if evidence.fix_commit:
            evidence.fix_parent_commit = self.get_parent_commit(repo_path, evidence.fix_commit)

        # Collect target file paths
        target_paths = self._get_target_paths(evidence)

        # Collect diffs
        if evidence.intro_parent_commit:
            evidence.intro_diff = self.collect_diff(
                repo_path, evidence.intro_parent_commit, evidence.intro_commit, target_paths
            )

        if evidence.fix_commit and evidence.fix_parent_commit:
            evidence.fix_diff = self.collect_diff(
                repo_path, evidence.fix_parent_commit, evidence.fix_commit, target_paths
            )

        # Collect code windows
        if evidence.vuln_positions:
            worktree = self.create_worktree(repo_path, task, evidence.intro_commit, "intro")
            if worktree:
                evidence.code_at_intro = self.collect_file_windows(worktree, evidence.vuln_positions)
                self.remove_worktree(repo_path, worktree)

        if evidence.intro_parent_commit:
            worktree = self.create_worktree(repo_path, task, evidence.intro_parent_commit, "intro_parent")
            if worktree:
                evidence.code_at_intro_parent = self.collect_file_windows(worktree, evidence.vuln_positions)
                self.remove_worktree(repo_path, worktree)

    def _get_target_paths(self, evidence: VulnEvidence) -> list[str] | None:
        """Get target file paths for diff."""
        paths = set()

        # From timeline
        if evidence.timeline:
            intro = evidence.timeline.get("introduction", {})
            fix = evidence.timeline.get("fix", {})
            for f in intro.get("files", []):
                paths.add(f)
            for f in fix.get("files", []):
                paths.add(f)

        # From SAST dataflow
        for flow in evidence.dataflow:
            if flow.get("file"):
                paths.add(flow["file"])

        # From vuln positions
        for pos in evidence.vuln_positions:
            if pos.get("file"):
                paths.add(pos["file"])

        return list(paths) if paths else None

    def _run_git(self, cwd: Path | None, args: list[str], timeout: int = 120) -> str:
        """Run a git command."""
        cmd = ["git"] + args
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result.stdout
