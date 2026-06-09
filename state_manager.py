import json
from pathlib import Path

from config import Config
from models import VulnerabilityTask


class StateManager:
    def __init__(self, config: Config):
        self.config = config
        self.progress_file = config.root_dir / config.state_dir / "progress.jsonl"

    def load_completed_keys(self) -> set[str]:
        """Load set of completed task keys from progress file."""
        completed = set()
        if not self.progress_file.exists():
            return completed

        with open(self.progress_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if record.get("status") == "success":
                        completed.add(record["task_key"])
                except (json.JSONDecodeError, KeyError):
                    continue

        return completed

    def load_latest_records(self) -> dict[str, dict]:
        """Load latest record for each task_key from progress file."""
        latest = {}
        if not self.progress_file.exists():
            return latest

        with open(self.progress_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    task_key = record.get("task_key")
                    if task_key:
                        latest[task_key] = record
                except (json.JSONDecodeError, KeyError):
                    continue

        return latest

    def append_status(
        self,
        task: VulnerabilityTask,
        status: str,
        fail_code: str | None = None,
        fail_reason: str | None = None,
    ) -> None:
        """Append task status to progress file."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)

        record = {
            "task_key": task.task_key,
            "project": task.project,
            "canonical_id": task.canonical_id,
            "status": status,
            "fail_code": fail_code,
            "fail_reason": fail_reason,
        }

        with open(self.progress_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
