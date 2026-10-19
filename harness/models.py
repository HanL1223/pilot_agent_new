"""Build the LLM client. Called once per conversation — never shared.

Why not one global model? Strands runs each agent call inside its own asyncio
event loop. The Anthropic/OpenAI async clients remember the loop they were first
used on, so a model shared by two conversations breaks the second one.
"""

from __future__ import annotations

import os

from strands.models import Model

from harness.config import Settings


def _key(name: str) -> str:
    key = os.getenv(name, "").strip()
    if not key:
        raise RuntimeError(f"{name} is empty. Put your key in .env (see .env.example).")
    return key


def build_model(settings: Settings) -> Model:
    if settings.provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            client_args={"api_key": _key("ANTHROPIC_API_KEY")},
            model_id=settings.model,
            max_tokens=settings.max_tokens,
        )
    if settings.provider == "openai":
        from strands.models.openai import OpenAIModel

        if not settings.model:
            raise ValueError("Set LLM_MODEL to an OpenAI model id when LLM_PROVIDER=openai.")
        return OpenAIModel(client_args={"api_key": _key("OPENAI_API_KEY")}, model_id=settings.model)
    raise ValueError(f"Unknown LLM_PROVIDER={settings.provider!r}; use 'anthropic' or 'openai'.")
