"""Settings, read once from environment variables (and a .env file next to this project)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Load THIS project's .env only — never search parent folders for one.
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass
class Settings:
    agent: str = field(default_factory=lambda: _env("AGENT", "jira_weather"))
    provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "anthropic").lower())
    model: str = field(default_factory=lambda: _env("LLM_MODEL"))
    max_tokens: int = field(default_factory=lambda: int(_env("LLM_MAX_TOKENS", "8000")))
    max_turns: int = field(default_factory=lambda: int(_env("AGENT_MAX_TURNS", "10")))
    home: Path = field(default_factory=lambda: Path(_env("AGENT_HOME", str(PROJECT_ROOT / ".agent"))))
    dry_run: bool = True          # Jira writes blocked unless you start with --live

    def __post_init__(self) -> None:
        if not self.model and self.provider == "anthropic":
            self.model = "claude-sonnet-5-5"
        self.home.mkdir(parents=True, exist_ok=True)
