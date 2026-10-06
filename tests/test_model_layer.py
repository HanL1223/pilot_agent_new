"""pilot/models.py — which provider class is built for which settings.

No network: provider objects are only constructed, never called.
"""

from __future__ import annotations

import pytest

from pilot.config import Settings
from pilot.models import build_model


def settings(provider, effort="none", summary=""):
    return Settings(provider=provider, reasoning_effort=effort, reasoning_summary=summary,
                    anthropic_api_key="test-key", openai_api_key="test-key", max_tokens=16000)


def test_anthropic_builds_the_anthropic_model():
    model = build_model(settings("anthropic"))
    assert type(model).__name__ == "AnthropicModel"
    assert model.get_config()["max_tokens"] == 16000
    assert model.get_config()["model_id"] == "claude-sonnet-5"


def test_the_small_model_is_the_cheap_one():
    assert build_model(settings("anthropic"), "small").get_config()["model_id"] == "claude-haiku-4-5-20251001"


def test_openai_without_reasoning_uses_chat_completions_with_effort_none():
    # gpt-5.x rejects temperature unless reasoning_effort is "none", so the two go together.
    model = build_model(settings("openai"))
    assert type(model).__name__ == "OpenAIModel"
    assert model.get_config()["params"] == {"reasoning_effort": "none", "temperature": 0.1}


def test_openai_with_reasoning_uses_the_responses_api():
    model = build_model(settings("openai", effort="high", summary="detailed"))
    assert type(model).__name__ == "OpenAIResponsesModel"
    assert model.get_config()["params"] == {"reasoning": {"effort": "high", "summary": "detailed"}}


def test_an_unknown_provider_is_refused():
    with pytest.raises(ValueError, match="Unknown LLM provider 'llama'"):
        Settings(provider="llama")
