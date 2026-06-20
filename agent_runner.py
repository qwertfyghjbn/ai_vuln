import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import anyio

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


def build_agent_runner(config: Config) -> AgentRunner:
    """Return the appropriate AgentRunner for the configured backend."""
    if config.agent_backend == "claude_code_cli":
        return ClaudeCodeCliRunner(config)
    if config.agent_backend == "claude_agent_sdk":
        return ClaudeAgentSdkRunner(config)
    raise ValueError(f"Unsupported agent backend: {config.agent_backend}")


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


class ClaudeAgentSdkRunner:
    """Agent runner using the Claude Agent SDK (claude-agent-sdk package).

    Communicates with Claude Code via the SDK's async query() function instead
    of a CLI subprocess.  The SDK bundles a Claude Code CLI internally.

    Permissions are enforced via ClaudeAgentOptions (cwd, add_dirs,
    allowed_tools, permission_mode) and post-run worktree-dirty checks ---
    matching the CLI backend's boundaries.
    """

    def __init__(self, config: Config):
        self.config = config
        self._sdk = None  # Lazy-load cache for SDK imports

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run_step(self, request: AgentRunRequest) -> AgentRunResult:
        """Execute a single analysis step via the Claude Agent SDK."""
        step = request.step_name

        # Write trace: prompt
        self._write_trace(request, f"{step}_prompt.md", request.prompt)

        try:
            return anyio.run(self._run_with_sdk, request)
        except Exception as e:
            # Preserve structured fail codes from internal errors
            # (FAIL_AGENT_SDK_UNAVAILABLE, FAIL_AGENT_SDK_ERROR, etc.)
            raw = str(e)
            if raw.startswith("FAIL_AGENT_"):
                error_msg = raw
            else:
                error_msg = f"FAIL_AGENT_SDK_ERROR: {raw}"

            # 将 SDK bundled CLI 的误导性错误消息替换为有意义的描述
            # SDK 内部 CLI 进程初始化失败时，会返回 is_error=true 但 subtype="success"
            # 此时 agent 完全未开始工作（stdout=0，无 session_id，无 turns）
            MISLEADING_ERROR = "Claude Code returned an error result: success"
            if MISLEADING_ERROR in error_msg:
                error_msg = (
                    f"FAIL_AGENT_SDK_ERROR: SDK bundled CLI 进程初始化失败，"
                    f"agent 未开始工作。可能是 CLI 启动超时或资源不足。"
                    f"（原始错误: {MISLEADING_ERROR}）"
                )
            logger.exception(f"{request.task_key} {step}: {error_msg}")

            self._write_trace(request, f"{step}_stdout.txt", "")
            self._write_trace(request, f"{step}_stderr.txt", error_msg)

            run_info = {
                "backend": "claude_agent_sdk",
                "step_name": step,
                "success": False,
                "fail_reason": error_msg,
            }
            self._write_trace_json(request, f"{step}_run.json", run_info)

            return AgentRunResult(success=False, fail_reason=error_msg)

    # ------------------------------------------------------------------
    # Async core
    # ------------------------------------------------------------------

    async def _run_with_sdk(self, request: AgentRunRequest) -> AgentRunResult:
        """Async body: build options, stream messages, collect output.

        Uses a string prompt (not AsyncIterable) with permission_mode set to
        acceptEdits so that Write and Bash are auto-approved without needing
        the can_use_tool callback.  This avoids the SDK bug where
        wait_for_result_and_end_input() closes stdin immediately when no
        hooks or SDK MCP servers are present, breaking the bidirectional
        can_use_tool control protocol.
        """
        step = request.step_name
        query_fn, ClaudeAgentOptionsCls, AssistantMessage, ResultMessage, TextBlock = (
            self._import_sdk()
        )

        options = self._build_sdk_options(request, ClaudeAgentOptionsCls)

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        session_id: str | None = None
        num_turns: int = 0
        total_cost_usd: float | None = None

        with anyio.move_on_after(request.timeout_seconds) as scope:
            async for message in query_fn(prompt=request.prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            stdout_parts.append(block.text)
                    if message.session_id:
                        session_id = message.session_id
                elif isinstance(message, ResultMessage):
                    if message.is_error:
                        stderr_parts.append(
                            f"Agent error: {message.result or 'unknown'}"
                        )
                    elif message.result:
                        stdout_parts.append(message.result)
                    session_id = message.session_id
                    num_turns = message.num_turns
                    total_cost_usd = message.total_cost_usd

        stdout = "\n".join(stdout_parts)
        stderr = "\n".join(stderr_parts) if stderr_parts else ""

        # Write trace files
        self._write_trace(request, f"{step}_stdout.txt", stdout)
        self._write_trace(request, f"{step}_stderr.txt", stderr)

        # Determine success
        if scope.cancel_called:
            fail_reason = (
                f"FAIL_AGENT_SDK_TIMEOUT: Agent SDK call timed out after "
                f"{request.timeout_seconds}s"
            )
            success = False
        else:
            write_perm_issue = self._detect_write_permission_issue(stdout, stderr)
            if write_perm_issue:
                fail_reason = write_perm_issue
                success = False
            else:
                fail_reason = None
                success = True

        # Write run.json
        run_info = {
            "backend": "claude_agent_sdk",
            "step_name": step,
            "success": success,
            "fail_reason": fail_reason,
            "session_id": session_id,
            "num_turns": num_turns,
            "total_cost_usd": total_cost_usd,
        }
        self._write_trace_json(request, f"{step}_run.json", run_info)

        return AgentRunResult(
            success=success,
            returncode=None,
            stdout=stdout,
            stderr=stderr,
            fail_reason=fail_reason,
        )

    # ------------------------------------------------------------------
    # SDK helpers
    # ------------------------------------------------------------------

    def _import_sdk(self):
        """Lazy-import and cache SDK modules.

        Raises RuntimeError (FAIL_AGENT_SDK_UNAVAILABLE) if the
        claude-agent-sdk package is not installed.
        """
        if self._sdk is not None:
            return self._sdk
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
            from claude_agent_sdk import (  # type: ignore
                AssistantMessage,
                ResultMessage,
                TextBlock,
            )
        except ImportError as e:
            raise RuntimeError(
                "FAIL_AGENT_SDK_UNAVAILABLE: claude-agent-sdk package not "
                "installed. Install with: pip install claude-agent-sdk. "
                f"Error: {e}"
            )
        self._sdk = (query, ClaudeAgentOptions, AssistantMessage, ResultMessage, TextBlock)
        return self._sdk

    def _build_sdk_options(self, request: AgentRunRequest, ClaudeAgentOptionsCls):
        """Build ClaudeAgentOptions for the SDK backend.

        Uses acceptEdits permission mode so Write and Bash are auto-approved
        without needing the can_use_tool callback.  This avoids the SDK bug
        where wait_for_result_and_end_input() closes stdin immediately when
        no hooks or SDK MCP servers are present, which breaks the
        bidirectional can_use_tool control protocol.

        Isolation guarantees:
        - tools= restricts the tool *set* to only the five needed tools
        - disallowed_tools blocks network-capable tools even if inherited
        - setting_sources=[] prevents inheriting local Claude settings
        - strict_mcp_config=True prevents inheriting MCP servers
        - add_dirs limits file-system visibility
        - cwd is the task worktree

        Fine-grained Bash/Write restrictions are enforced post-hoc by
        _check_worktree_dirty (agent_analyzer.py) and the step prompt
        instructions.
        """
        add_dirs = [str(request.workspace_dir), str(request.output_dir)]
        if request.extra_allowed_dirs:
            for d in request.extra_allowed_dirs:
                add_dirs.append(str(d))

        return ClaudeAgentOptionsCls(
            cwd=str(request.workspace_dir),
            add_dirs=add_dirs,
            tools=["Read", "Grep", "Glob", "Bash", "Write"],
            disallowed_tools=[
                "WebSearch",
                "WebFetch",
                "Task",
                "NotebookEdit",
            ],
            setting_sources=[],
            strict_mcp_config=True,
            permission_mode=self.config.agent_permission_mode,
        )

    # ------------------------------------------------------------------
    # Post-run checks
    # ------------------------------------------------------------------

    def _detect_write_permission_issue(self, stdout: str, stderr: str) -> str | None:
        """Detect if the agent failed due to write permission issues.

        Returns fail_reason if detected, None otherwise.
        """
        combined = (stdout + "\n" + stderr).lower()
        for pattern in WRITE_PERMISSION_PATTERNS:
            if pattern in combined:
                return (
                    f"FAIL_AGENT_WRITE_PERMISSION: Agent could not write "
                    f"output file ({pattern})"
                )
        return None

    # ------------------------------------------------------------------
    # Trace file writers
    # ------------------------------------------------------------------

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
