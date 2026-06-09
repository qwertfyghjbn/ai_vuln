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

        # Also check environment variables (higher priority)
        if os.environ.get("LLM_PROVIDER"):
            self.llm_provider = os.environ["LLM_PROVIDER"]
        if os.environ.get("DEEPSEEK_API_KEY"):
            self.deepseek_api_key = os.environ["DEEPSEEK_API_KEY"]
        if os.environ.get("DEEPSEEK_API_URL"):
            self.deepseek_api_url = os.environ["DEEPSEEK_API_URL"]
