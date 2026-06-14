import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class AgentRunRequest:
    task_key: str
    step_name: str
    prompt: str
    workspace_dir: Path
    output_dir: Path
    trace_dir: Path
    timeout_seconds: int
    extra_allowed_dirs: list[Path] | None = None


@dataclass
class AgentRunResult:
    success: bool
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    fail_reason: str | None = None


class AgentRunner(Protocol):
    def run_step(self, request: AgentRunRequest) -> AgentRunResult: ...


WRITE_PERMISSION_PATTERNS = [
    "waiting for write permission",
    "grant permission to write",
    "文件写入权限问题",
    "请允许我将结果写入",
]


class ClaudeCodeCliRunner:
    def __init__(self, config: Config):
        self.config = config
        self.agent_command = config.agent_command

    def _detect_write_permission_issue(self, stdout: str, stderr: str) -> str | None:
        """Detect if the agent failed due to write permission issues.

        Returns fail_reason if detected, None otherwise.
        """
        combined = (stdout + "\n" + stderr).lower()
        for pattern in WRITE_PERMISSION_PATTERNS:
            if pattern in combined:
                return f"FAIL_AGENT_WRITE_PERMISSION: Agent could not write output file ({pattern})"
        return None

    def run_step(self, request: AgentRunRequest) -> AgentRunResult:
        """Execute a single analysis step via Claude Code CLI."""
        step = request.step_name

        # Write trace: prompt
        self._write_trace(request, f"{step}_prompt.md", request.prompt)

        command = self._build_command(request)

        try:
            result = subprocess.run(
                command,
                input=request.prompt,
                cwd=request.workspace_dir,
                text=True,
                capture_output=True,
                timeout=request.timeout_seconds,
            )

            # Write trace: stdout and stderr
            self._write_trace(request, f"{step}_stdout.txt", result.stdout)
            self._write_trace(request, f"{step}_stderr.txt", result.stderr)

            # Check for write permission issues (even if returncode is 0)
            write_perm_issue = self._detect_write_permission_issue(result.stdout, result.stderr)
            if write_perm_issue:
                success = False
                fail_reason = write_perm_issue
            else:
                success = result.returncode == 0
                fail_reason = None if success else f"exit code {result.returncode}"

            # Write trace: run.json
            run_info = {
                "backend": "claude_code_cli",
                "step_name": step,
                "returncode": result.returncode,
                "success": success,
                "fail_reason": fail_reason,
            }
            self._write_trace_json(request, f"{step}_run.json", run_info)

            return AgentRunResult(
                success=success,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                fail_reason=fail_reason,
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Agent command timed out after {request.timeout_seconds}s"
            logger.error(f"{request.task_key} {step}: {error_msg}")

            self._write_trace(request, f"{step}_stdout.txt", "")
            self._write_trace(request, f"{step}_stderr.txt", error_msg)

            run_info = {
                "backend": "claude_code_cli",
                "step_name": step,
                "returncode": None,
                "success": False,
                "fail_reason": error_msg,
            }
            self._write_trace_json(request, f"{step}_run.json", run_info)

            return AgentRunResult(success=False, fail_reason=error_msg)

        except FileNotFoundError:
            error_msg = f"Agent command not found: {self.agent_command}"
            logger.error(f"{request.task_key} {step}: {error_msg}")

            self._write_trace(request, f"{step}_stdout.txt", "")
            self._write_trace(request, f"{step}_stderr.txt", error_msg)

            run_info = {
                "backend": "claude_code_cli",
                "step_name": step,
                "returncode": None,
                "success": False,
                "fail_reason": error_msg,
            }
            self._write_trace_json(request, f"{step}_run.json", run_info)

            return AgentRunResult(success=False, fail_reason=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error running agent: {e}"
            logger.exception(f"{request.task_key} {step}: {error_msg}")

            self._write_trace(request, f"{step}_stdout.txt", "")
            self._write_trace(request, f"{step}_stderr.txt", error_msg)

            run_info = {
                "backend": "claude_code_cli",
                "step_name": step,
                "returncode": None,
                "success": False,
                "fail_reason": error_msg,
            }
            self._write_trace_json(request, f"{step}_run.json", run_info)

            return AgentRunResult(success=False, fail_reason=error_msg)

    def _build_command(self, request: AgentRunRequest) -> list[str]:
        """Build the CLI command for Claude Code.

        Uses -p flag for non-interactive mode, prompt passed via stdin.
        Configures tool allowlist to restrict agent permissions.
        Sets --permission-mode for non-interactive file writing.
        Adds --add-dir for workspace, output, data, and taxonomy directories.
        """
        cmd = [
            self.agent_command,
            "-p",
            "--permission-mode",
            self.config.agent_permission_mode,
            "--allowedTools",
            "Read",
            "Grep",
            "Glob",
            "Bash(git show*)",
            "Bash(git diff*)",
            "Bash(git log*)",
            f"Write({request.output_dir}/**)",
        ]

        # Always add workspace and output directories
        cmd.extend(["--add-dir", str(request.workspace_dir)])
        cmd.extend(["--add-dir", str(request.output_dir)])

        # Add extra allowed directories (data_dir, taxonomy dir, etc.)
        if request.extra_allowed_dirs:
            for d in request.extra_allowed_dirs:
                cmd.extend(["--add-dir", str(d)])

        return cmd

    def _write_trace(self, request: AgentRunRequest, filename: str, content: str) -> None:
        """Write a trace file."""
        try:
            request.trace_dir.mkdir(parents=True, exist_ok=True)
            (request.trace_dir / filename).write_text(content, encoding="utf-8")
        except OSError:
            logger.warning(f"Failed to write trace: {request.trace_dir / filename}")

    def _write_trace_json(self, request: AgentRunRequest, filename: str, data: dict) -> None:
        """Write a JSON trace file."""
        try:
            request.trace_dir.mkdir(parents=True, exist_ok=True)
            (request.trace_dir / filename).write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        except OSError:
            logger.warning(f"Failed to write trace: {request.trace_dir / filename}")
