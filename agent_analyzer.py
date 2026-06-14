import logging
import shutil
import subprocess
from pathlib import Path

from config import Config
from models import VulnEvidence
from output_writer import OutputWriter
from repo_manager import RepoManager
from agent_runner import AgentRunner, AgentRunRequest, AgentRunResult
from agent_prompts import (
    build_agent_step1_prompt,
    build_agent_step2_prompt,
    build_agent_step3_prompt,
    build_agent_step4_prompt,
    build_agent_repair_prompt,
)
from analyzer import validate_step_output, invalid_output_stub

logger = logging.getLogger(__name__)

# Step name to output filename mapping
STEP_FILENAMES = {
    "step1": "01_version_verification.md",
    "step2": "02_module_classification.md",
    "step3": "03_vulnerability_pattern_classification.md",
    "step4": "04_exploit_condition_summary.md",
}

AGENT_CONTEXT_DIRNAME = "agent_context"
AGENT_TAXONOMY_FILENAME = "project-module-types.md"


class AgentAnalyzer:
    def __init__(
        self,
        config: Config,
        output_writer: OutputWriter,
        repo_manager: RepoManager,
        runner: AgentRunner,
    ):
        self.config = config
        self.output_writer = output_writer
        self.repo_manager = repo_manager
        self.runner = runner

    # Files to clean at task start to avoid stale results from previous runs.
    STALE_STEP_FILES = [
        "01_version_verification.md",
        "02_module_classification.md",
        "03_vulnerability_pattern_classification.md",
        "04_exploit_condition_summary.md",
        "final_case_summary.md",
    ]

    def analyze(self, evidence: VulnEvidence) -> dict:
        """Run all 4 analysis steps via agent."""
        task = evidence.task
        task_dir = self.output_writer.task_dir(task).resolve()

        # Clean stale output and trace artifacts from previous runs to avoid mixed results.
        self._clean_stale_task_artifacts(task_dir, task.task_key)

        # Prepare agent workspace
        workspace = self.repo_manager.prepare_agent_workspace(evidence)
        if not workspace:
            logger.error(f"Failed to prepare agent workspace for {task.task_key}")
            # Write stubs for all steps
            results = {}
            for step_name in ["step1", "step2", "step3", "step4"]:
                stub = invalid_output_stub(step_name)
                filename = STEP_FILENAMES[step_name]
                self.output_writer.write_step_file(task, filename, stub)
                results[step_name] = stub

            self.output_writer.write_final_summary(task, {
                "Step 1 - Version Verification": results["step1"],
                "Step 2 - Module Classification": results["step2"],
                "Step 3 - Vulnerability Pattern Classification": results["step3"],
                "Step 4 - Exploit Condition Summary": results["step4"],
            })
            self._raise_task_failure(
                task,
                evidence.fail_code or "FAIL_AGENT_WORKSPACE",
                evidence.fail_reason or "Failed to prepare agent workspace",
            )

        try:
            data_dir = Path(task.primary_data_dir).resolve() if task.primary_data_dir else None
            module_types_file = self._prepare_agent_taxonomy_context(task_dir)

            # Step 1: Version Verification
            step1_file = task_dir / STEP_FILENAMES["step1"]
            step1 = self._run_step(
                "step1", evidence, workspace, task_dir, data_dir,
                lambda: build_agent_step1_prompt(
                    evidence, workspace.worktree_path.resolve(), step1_file.resolve(), data_dir
                ),
            )

            # Step 2: Module Classification
            step2_file = task_dir / STEP_FILENAMES["step2"]
            step2 = self._run_step(
                "step2", evidence, workspace, task_dir, data_dir,
                lambda: build_agent_step2_prompt(
                    evidence, workspace.worktree_path.resolve(), step2_file.resolve(), data_dir,
                    step1_file.resolve(), module_types_file
                ),
            )

            # Step 3: Vulnerability Pattern Classification
            step3_file = task_dir / STEP_FILENAMES["step3"]
            step3 = self._run_step(
                "step3", evidence, workspace, task_dir, data_dir,
                lambda: build_agent_step3_prompt(
                    evidence, workspace.worktree_path.resolve(), step3_file.resolve(), data_dir,
                    step1_file.resolve(), step2_file.resolve()
                ),
            )

            # Step 4: Exploit Condition Summary
            step4_file = task_dir / STEP_FILENAMES["step4"]
            step4 = self._run_step(
                "step4", evidence, workspace, task_dir, data_dir,
                lambda: build_agent_step4_prompt(
                    evidence, workspace.worktree_path.resolve(), step4_file.resolve(), data_dir,
                    step1_file.resolve(), step2_file.resolve(), step3_file.resolve()
                ),
            )

            # Write final summary
            self.output_writer.write_final_summary(task, {
                "Step 1 - Version Verification": step1,
                "Step 2 - Module Classification": step2,
                "Step 3 - Vulnerability Pattern Classification": step3,
                "Step 4 - Exploit Condition Summary": step4,
            })

            return {"step1": step1, "step2": step2, "step3": step3, "step4": step4}

        finally:
            self.repo_manager.cleanup_agent_workspace(workspace)

    def _run_step(
        self,
        step_name: str,
        evidence: VulnEvidence,
        workspace,
        task_dir: Path,
        data_dir: Path,
        build_prompt,
    ) -> str:
        """Execute a single step with retry logic."""
        task = evidence.task
        task_key = task.task_key
        filename = STEP_FILENAMES[step_name]
        trace_dir = task_dir / "agent_trace"
        output_file = task_dir / filename

        # Avoid accepting stale files from previous runs.
        if output_file.exists():
            output_file.unlink()

        # First attempt
        prompt = build_prompt()
        result = self._execute_agent(step_name, prompt, workspace, task_key, task_dir, trace_dir, data_dir)

        # Check if agent modified source code - this is a hard failure
        if self._check_worktree_dirty(workspace):
            logger.error(f"Agent modified source code in worktree for {task_key} {step_name}")
            self._write_worktree_dirty_trace(trace_dir, step_name, task_key)
            self._raise_task_failure(
                task,
                "FAIL_AGENT_WORKTREE_DIRTY",
                f"Agent modified source code in worktree at {step_name}",
            )

        # Log write permission failures explicitly
        if not result.success and result.fail_reason and "FAIL_AGENT_WRITE_PERMISSION" in (result.fail_reason or ""):
            logger.warning(f"Write permission issue for {task_key} {step_name}: {result.fail_reason}")

        # Try to read the output file written by agent
        if result.success and output_file.exists():
            text = output_file.read_text(encoding="utf-8")
            if validate_step_output(step_name, text):
                return text

        # Retry with repair prompt
        logger.info(f"Retrying {step_name} for {task_key} due to validation failure")
        repair_prompt = build_agent_repair_prompt(step_name, prompt)
        if output_file.exists():
            output_file.unlink()
        result = self._execute_agent(step_name, repair_prompt, workspace, task_key, task_dir, trace_dir, data_dir)

        # Check if agent modified source code after retry - this is a hard failure
        if self._check_worktree_dirty(workspace):
            logger.error(f"Agent modified source code in worktree for {task_key} {step_name} (retry)")
            self._write_worktree_dirty_trace(trace_dir, step_name, task_key)
            self._raise_task_failure(
                task,
                "FAIL_AGENT_WORKTREE_DIRTY",
                f"Agent modified source code in worktree at {step_name} (retry)",
            )

        # Log write permission failures on retry
        if not result.success and result.fail_reason and "FAIL_AGENT_WRITE_PERMISSION" in (result.fail_reason or ""):
            logger.warning(f"Write permission issue for {task_key} {step_name} (retry): {result.fail_reason}")

        if result.success and output_file.exists():
            text = output_file.read_text(encoding="utf-8")
            if validate_step_output(step_name, text):
                return text

        # Both attempts failed, write stub
        failure_reason = result.fail_reason if result.fail_reason else "Agent output did not satisfy required format after retry"
        logger.warning(f"Writing stub for {step_name} for {task_key} after retry failure: {failure_reason}")
        stub = invalid_output_stub(step_name)
        self.output_writer.write_step_file(task, filename, stub)

        # Write failure trace with specific reason
        try:
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / f"{step_name}_failure.md").write_text(
                f"# {step_name} Failure\n\n{failure_reason}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        return stub

    def _check_worktree_dirty(self, workspace) -> bool:
        """Check if the worktree has uncommitted changes (agent modified source code)."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=workspace.worktree_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return bool(result.stdout.strip())
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _write_worktree_dirty_trace(self, trace_dir: Path, step_name: str, task_key: str) -> None:
        """Write trace indicating agent modified source code."""
        try:
            trace_dir.mkdir(parents=True, exist_ok=True)
            (trace_dir / f"{step_name}_worktree_dirty.md").write_text(
                f"# {step_name} Worktree Dirty\n\n"
                f"Agent modified source code in worktree. This violates the constraint "
                f"that agents must not modify the source repository.\n"
                f"Task: {task_key}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _clean_stale_task_artifacts(self, task_dir: Path, task_key: str) -> None:
        """Clean stale output and trace artifacts from previous runs.

        Deletes:
        - step files
        - final_case_summary.md
        - agent_trace/ directory contents

        Preserves:
        - metadata.md
        - evidence_bundle.md
        - agent_context/
        """
        for filename in self.STALE_STEP_FILES:
            filepath = task_dir / filename
            if filepath.exists():
                try:
                    filepath.unlink()
                    logger.info(f"Cleaned stale file: {filepath.name} for {task_key}")
                except OSError as e:
                    logger.warning(f"Failed to clean stale file {filepath}: {e}")

        trace_dir = task_dir / "agent_trace"
        if trace_dir.exists():
            try:
                shutil.rmtree(trace_dir)
                logger.info(f"Cleaned stale trace directory for {task_key}")
            except OSError as e:
                logger.warning(f"Failed to clean stale trace directory {trace_dir}: {e}")

    def _execute_agent(
        self,
        step_name: str,
        prompt: str,
        workspace,
        task_key: str,
        task_dir: Path,
        trace_dir: Path,
        data_dir: Path | None = None,
    ) -> AgentRunResult:
        """Execute agent and return result."""
        # Collect extra directories the agent needs access to
        extra_dirs = []
        if data_dir and data_dir.exists():
            extra_dirs.append(data_dir)

        request = AgentRunRequest(
            task_key=task_key,
            step_name=step_name,
            prompt=prompt,
            workspace_dir=workspace.worktree_path,
            output_dir=task_dir,
            trace_dir=trace_dir,
            timeout_seconds=self.config.agent_timeout_seconds,
            extra_allowed_dirs=extra_dirs if extra_dirs else None,
        )
        return self.runner.run_step(request)

    def _prepare_agent_taxonomy_context(self, task_dir: Path) -> Path:
        """Copy the taxonomy file into task-local context to avoid broad read grants."""
        source = (self.config.root_dir / AGENT_TAXONOMY_FILENAME).resolve()
        context_dir = task_dir / AGENT_CONTEXT_DIRNAME
        context_dir.mkdir(parents=True, exist_ok=True)
        target = context_dir / AGENT_TAXONOMY_FILENAME
        shutil.copyfile(source, target)
        return target

    def _raise_task_failure(self, task, fail_code: str, fail_reason: str) -> None:
        """Persist a structured task failure before aborting the run."""
        task.fail_code = fail_code
        task.fail_reason = fail_reason
        raise RuntimeError(f"{fail_code}: {fail_reason}")
