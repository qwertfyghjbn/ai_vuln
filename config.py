import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """Load .env file and return key-value pairs."""
    env = {}
    if not path.exists():
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


@dataclass
class Config:
    root_dir: Path = Path(".")
    excel_path: Path = Path("vuln-analyzed-0605.xlsx")
    timeline_zip_path: Path = Path("ai-vulns-timeline.zip")
    data_root: Path = Path("data/ai-vulns-timeline")
    repos_dir: Path = Path("repos")
    worktrees_dir: Path = Path("worktrees")
    output_dir: Path = Path("output")
    state_dir: Path = Path("state")
    logs_dir: Path = Path("logs")
    max_tasks: int | None = None
    dry_run: bool = False
    offline: bool = False
    max_workers: int = 1
    llm_provider: str = "none"  # none | anthropic | openai | custom

    # LLM API settings
    anthropic_api_key: str = ""
    anthropic_api_url: str = "https://api.anthropic.com"
    openai_api_key: str = ""
    openai_api_url: str = "https://api.openai.com"
    deepseek_api_key: str = ""
    deepseek_api_url: str = "https://api.deepseek.com/anthropic"
    custom_api_key: str = ""
    custom_api_url: str = ""
    llm_model: str = "deepseek-v4-pro"
    llm_max_tokens: int = 4096

    # Agent analysis mode settings
    analysis_mode: str = "prompt"  # prompt | agent
    agent_backend: str = "claude_code_cli"  # claude_code_cli (v1 only)
    agent_command: str = "claude"
    agent_timeout_seconds: int = 1800
    agent_permission_mode: str = "acceptEdits"  # acceptEdits | auto | default | dontAsk | plan

    def __post_init__(self):
        """Load settings from .env file."""
        env = load_dotenv(self.root_dir / ".env")

        # Override settings from .env
        if "LLM_PROVIDER" in env:
            self.llm_provider = env["LLM_PROVIDER"]
        if "ANTHROPIC_API_KEY" in env:
            self.anthropic_api_key = env["ANTHROPIC_API_KEY"]
        if "ANTHROPIC_API_URL" in env:
            self.anthropic_api_url = env["ANTHROPIC_API_URL"]
        if "OPENAI_API_KEY" in env:
            self.openai_api_key = env["OPENAI_API_KEY"]
        if "OPENAI_API_URL" in env:
            self.openai_api_url = env["OPENAI_API_URL"]
        if "DEEPSEEK_API_KEY" in env:
            self.deepseek_api_key = env["DEEPSEEK_API_KEY"]
        if "DEEPSEEK_API_URL" in env:
            self.deepseek_api_url = env["DEEPSEEK_API_URL"]
        if "CUSTOM_API_KEY" in env:
            self.custom_api_key = env["CUSTOM_API_KEY"]
        if "CUSTOM_API_URL" in env:
            self.custom_api_url = env["CUSTOM_API_URL"]
        if "LLM_MODEL" in env:
            self.llm_model = env["LLM_MODEL"]
        if "LLM_MAX_TOKENS" in env:
            self.llm_max_tokens = int(env["LLM_MAX_TOKENS"])
        if "MAX_WORKERS" in env:
            self.max_workers = int(env["MAX_WORKERS"])

        # Agent mode settings from .env
        if "ANALYSIS_MODE" in env:
            self.analysis_mode = env["ANALYSIS_MODE"]
        if "AGENT_BACKEND" in env:
            self.agent_backend = env["AGENT_BACKEND"]
        if "AGENT_COMMAND" in env:
            self.agent_command = env["AGENT_COMMAND"]
        if "AGENT_TIMEOUT_SECONDS" in env:
            self.agent_timeout_seconds = int(env["AGENT_TIMEOUT_SECONDS"])
        if "AGENT_PERMISSION_MODE" in env:
            self.agent_permission_mode = env["AGENT_PERMISSION_MODE"]

        # Also check environment variables (higher priority)
        if os.environ.get("LLM_PROVIDER"):
            self.llm_provider = os.environ["LLM_PROVIDER"]
        if os.environ.get("DEEPSEEK_API_KEY"):
            self.deepseek_api_key = os.environ["DEEPSEEK_API_KEY"]
        if os.environ.get("DEEPSEEK_API_URL"):
            self.deepseek_api_url = os.environ["DEEPSEEK_API_URL"]

        # Agent mode settings from environment variables (higher priority)
        if os.environ.get("ANALYSIS_MODE"):
            self.analysis_mode = os.environ["ANALYSIS_MODE"]
        if os.environ.get("AGENT_BACKEND"):
            self.agent_backend = os.environ["AGENT_BACKEND"]
        if os.environ.get("AGENT_COMMAND"):
            self.agent_command = os.environ["AGENT_COMMAND"]
        if os.environ.get("AGENT_TIMEOUT_SECONDS"):
            self.agent_timeout_seconds = int(os.environ["AGENT_TIMEOUT_SECONDS"])
        if os.environ.get("AGENT_PERMISSION_MODE"):
            self.agent_permission_mode = os.environ["AGENT_PERMISSION_MODE"]

        # Validate agent mode settings
        if self.analysis_mode not in ("prompt", "agent"):
            raise ValueError(f"Invalid analysis_mode: {self.analysis_mode}. Must be 'prompt' or 'agent'.")
        if self.analysis_mode == "agent" and self.agent_backend != "claude_code_cli":
            raise ValueError(f"Unsupported agent backend: {self.agent_backend}")
        valid_permission_modes = ("acceptEdits", "auto", "default", "dontAsk", "plan")
        if self.agent_permission_mode not in valid_permission_modes:
            raise ValueError(f"Invalid agent_permission_mode: {self.agent_permission_mode}. Must be one of {valid_permission_modes}.")
        if self.agent_permission_mode == "bypassPermissions":
            raise ValueError("bypassPermissions is not allowed. Use acceptEdits or auto instead.")
