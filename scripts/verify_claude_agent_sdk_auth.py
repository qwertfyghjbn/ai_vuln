#!/usr/bin/env python3
"""Minimal experiment for validating Claude Agent SDK auth/config behavior.

This script intentionally mirrors the project's claude_agent_sdk backend on
the auth/config-related options, while keeping the prompt tiny and the output
easy to inspect.

It does not try to infer the auth source itself. Instead, it records enough
evidence for a human to compare runs under different local conditions:

1. project-equivalent mode:
   - setting_sources=[]
   - strict_mcp_config=True
   - permission_mode=acceptEdits
   This matches the current project's auth/config isolation behavior.

2. inherit-local mode:
   - setting_sources is omitted
   - strict_mcp_config=False
   This is a contrast run to test whether local Claude settings change the
   outcome.

Recommended usage:

    python3 scripts/verify_claude_agent_sdk_auth.py --mode project-equivalent
    python3 scripts/verify_claude_agent_sdk_auth.py --mode inherit-local

Then compare the generated JSON traces under tmp/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anyio


DEFAULT_PROMPT = (
    "Reply with exactly one line: AUTH_TEST_OK. "
    "Do not use tools unless strictly required."
)


@dataclass
class RunSummary:
    success: bool
    mode: str
    permission_mode: str
    cwd: str
    add_dirs: list[str]
    setting_sources: list[str] | None
    strict_mcp_config: bool
    session_id: str | None
    num_turns: int
    total_cost_usd: float | None
    stdout: str
    stderr: str
    timed_out: bool = False
    exception_type: str | None = None
    exception_message: str | None = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal verification script for Claude Agent SDK auth/config behavior."
    )
    parser.add_argument(
        "--mode",
        choices=("project-equivalent", "inherit-local"),
        default="project-equivalent",
        help=(
            "project-equivalent matches ai_vuln's current SDK backend; "
            "inherit-local omits setting_sources isolation for comparison."
        ),
    )
    parser.add_argument(
        "--permission-mode",
        default="acceptEdits",
        help="Claude Agent SDK permission_mode to use. Defaults to acceptEdits.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Tiny prompt to send. Keep this minimal to reduce cost.",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit output JSON path. Defaults under /tmp.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="SDK query timeout in seconds. Defaults to 60.",
    )
    return parser


def build_output_path(mode: str, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"/tmp/claude_agent_sdk_auth_check_{mode}_{stamp}.json")


def collect_env_snapshot() -> dict[str, str | None]:
    keys = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_URL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_OPENAI",
        "CLAUDE_CODE_USE_MIMO",
        "HTTP_PROXY",
        "HTTPS_PROXY",
    ]
    snapshot: dict[str, str | None] = {}
    for key in keys:
        value = os.environ.get(key)
        if value is None:
            snapshot[key] = None
        elif "KEY" in key:
            snapshot[key] = f"<set:{len(value)} chars>"
        else:
            snapshot[key] = value
    return snapshot


def build_options(
    mode: str,
    permission_mode: str,
    workspace_dir: Path,
    stderr_callback,
):
    try:
        from claude_agent_sdk import ClaudeAgentOptions  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "claude-agent-sdk is not installed. Install with: pip install claude-agent-sdk"
        ) from exc

    kwargs: dict[str, Any] = {
        "cwd": str(workspace_dir),
        "add_dirs": [str(workspace_dir)],
        "tools": ["Read", "Grep", "Glob", "Bash", "Write"],
        "disallowed_tools": ["WebSearch", "WebFetch", "Task", "NotebookEdit"],
        "permission_mode": permission_mode,
        "stderr": stderr_callback,
    }

    if mode == "project-equivalent":
        kwargs["setting_sources"] = []
        kwargs["strict_mcp_config"] = True
    elif mode == "inherit-local":
        kwargs["strict_mcp_config"] = False
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    return ClaudeAgentOptions(**kwargs)


async def run_query(
    mode: str,
    permission_mode: str,
    prompt: str,
    workspace_dir: Path,
    timeout_seconds: int,
) -> RunSummary:
    try:
        from claude_agent_sdk import query  # type: ignore
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "claude-agent-sdk is not installed. Install with: pip install claude-agent-sdk"
        ) from exc

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    session_id: str | None = None
    num_turns = 0
    total_cost_usd: float | None = None
    options = build_options(mode, permission_mode, workspace_dir, stderr_parts.append)

    try:
        timed_out = False
        with anyio.move_on_after(timeout_seconds) as scope:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            stdout_parts.append(block.text)
                    if getattr(message, "session_id", None):
                        session_id = message.session_id
                elif isinstance(message, ResultMessage):
                    if getattr(message, "is_error", False):
                        stderr_parts.append(f"Agent error: {message.result or 'unknown'}")
                    elif getattr(message, "result", None):
                        stdout_parts.append(message.result)
                    session_id = getattr(message, "session_id", session_id)
                    num_turns = getattr(message, "num_turns", num_turns)
                    total_cost_usd = getattr(message, "total_cost_usd", total_cost_usd)
        timed_out = scope.cancel_called

        return RunSummary(
            success=not timed_out,
            mode=mode,
            permission_mode=permission_mode,
            cwd=str(workspace_dir),
            add_dirs=[str(workspace_dir)],
            setting_sources=[] if mode == "project-equivalent" else None,
            strict_mcp_config=(mode == "project-equivalent"),
            session_id=session_id,
            num_turns=num_turns,
            total_cost_usd=total_cost_usd,
            stdout="\n".join(stdout_parts).strip(),
            stderr="\n".join(stderr_parts).strip(),
            timed_out=timed_out,
            exception_type=None if not timed_out else "Timeout",
            exception_message=None if not timed_out else f"SDK query timed out after {timeout_seconds}s",
        )
    except Exception as exc:
        return RunSummary(
            success=False,
            mode=mode,
            permission_mode=permission_mode,
            cwd=str(workspace_dir),
            add_dirs=[str(workspace_dir)],
            setting_sources=[] if mode == "project-equivalent" else None,
            strict_mcp_config=(mode == "project-equivalent"),
            session_id=session_id,
            num_turns=num_turns,
            total_cost_usd=total_cost_usd,
            stdout="\n".join(stdout_parts).strip(),
            stderr="\n".join(stderr_parts).strip(),
            timed_out=False,
            exception_type=type(exc).__name__,
            exception_message=str(exc),
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_path = build_output_path(args.mode, args.output)
    workspace_dir = Path.cwd().resolve()

    payload: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode,
        "workspace_dir": str(workspace_dir),
        "prompt": args.prompt,
        "env_snapshot": collect_env_snapshot(),
        "notes": [
            "project-equivalent mode matches ai_vuln's current auth/config isolation options",
            "inherit-local mode is a contrast run to detect whether local Claude settings affect behavior",
            "success/failure plus session_id/cost can be compared across runs",
        ],
    }

    try:
        summary = anyio.run(
            run_query,
            args.mode,
            args.permission_mode,
            args.prompt,
            workspace_dir,
            args.timeout_seconds,
        )
        payload["summary"] = asdict(summary)
    except Exception as exc:
        payload["summary"] = {
            "success": False,
            "mode": args.mode,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote result to: {output_path}")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    return 0 if payload["summary"].get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
