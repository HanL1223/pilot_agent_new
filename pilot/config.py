"""Configuration — every harness knob is an env var, read once into a dataclass.

No settings framework (the Waku rule): if you can read this file, you know
everything pilot can be configured to do. Domain settings (JIRA_*, ...) are not
here; they belong to the pack.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def _load_env() -> str:
    """Load the .env found from where the user IS (usecwd), walking upward —
    the rule git, npm and pytest already taught everyone. Returns the path."""
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path)
    return path


DOTENV_PATH = _load_env()

_DEFAULT_MODELS = {
    "anthropic": ("claude-sonnet-5", "claude-haiku-4-5-20251001"),
    "openai": ("gpt-5.6-luna", "gpt-5.6-luna"),
}


def default_models(provider: str) -> tuple[str, str]:
    """(main, small) default model ids for a provider."""
    try:
        return _DEFAULT_MODELS[provider]
    except KeyError:
        raise ValueError(f"Unknown LLM provider {provider!r}. Use 'anthropic' or 'openai'.") from None

def resolve_home(raw: str | None) -> Path:
    """PILOT_HOME, always absolute (D8). A relative value is resolved once,
    against the working directory at startup — so two shells in two folders can
    never silently get two homes and two owner locks without it being printed."""
    return Path(raw).expanduser().resolve() if raw else (Path.home() / ".pilot").resolve()

def _flag(name: str, default: str = "") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")



@dataclass
class Settings:
    home: Path = field(default_factory=lambda: resolve_home(os.getenv("PILOT_HOME")))

    # --- models
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic").strip().lower())
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "").strip())
    small_model: str = field(default_factory=lambda: os.getenv("LLM_SMALL_MODEL", "").strip())
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    reasoning_effort: str = field(
        default_factory=lambda: os.getenv("LLM_REASONING_EFFORT", "none").strip().lower())
    reasoning_summary: str = field(
        default_factory=lambda: os.getenv("LLM_REASONING_SUMMARY", "").strip().lower())
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "16000")))

    # --- loop guardrail (D1): Strands' native limits={"turns": N}
    max_iterations: int = field(default_factory=lambda: int(os.getenv("PILOT_MAX_ITERATIONS", "12")))

    # --- persistence
    snapshot_image_turns: int = field(default_factory=lambda: int(os.getenv("PILOT_SNAPSHOT_IMAGE_TURNS", "4")))
    runtime_idle_min: float = field(default_factory=lambda: float(os.getenv("PILOT_RUNTIME_IDLE_MIN", "30")))

    # --- memory (plan §4)
    memory: bool = field(default_factory=lambda: _flag("PILOT_MEMORY", "1"))
    consolidate_every: int = field(default_factory=lambda: int(os.getenv("PILOT_CONSOLIDATE_EVERY", "6")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("PILOT_RETRIEVAL_TOP_K", "4")))

    # --- ops
    trace: bool = field(default_factory=lambda: _flag("PILOT_TRACE", "1"))

    def __post_init__(self) -> None:
        main, small = default_models(self.provider)
        self.model = self.model or main
        self.small_model = self.small_model or small

    def ensure_home(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        return self.home

    def validate(self) -> None:
        """Fail fast when the selected provider has no key."""
        if self.provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set. Add it to .env.")
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER=openai but OPENAI_API_KEY is not set. Add it to .env.")