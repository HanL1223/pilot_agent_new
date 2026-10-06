"""pilot/config.py — one dataclass read from the environment: the provider's
default models, an always-absolute home, and a key check that names the key."""

from __future__ import annotations

import pytest

from pilot.config import Settings, default_models, resolve_home


def test_each_provider_has_a_main_and_a_small_default():
    assert default_models("anthropic") == ("claude-sonnet-5", "claude-haiku-4-5-20251001")
    assert default_models("openai")[0].startswith("gpt")


def test_a_misspelled_provider_is_refused_not_guessed():
    with pytest.raises(ValueError, match="Unknown LLM provider 'antropic'"):
        default_models("antropic")


def test_blank_models_fall_back_to_the_providers_defaults(tmp_path):
    s = Settings(home=tmp_path, provider="anthropic", model="", small_model="")
    assert (s.model, s.small_model) == ("claude-sonnet-5", "claude-haiku-4-5-20251001")
    assert Settings(home=tmp_path, provider="anthropic", model="claude-opus-5-5").model == "claude-opus-5-5"


def test_the_home_is_always_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_home("state") == tmp_path.resolve() / "state"
    assert resolve_home(None).is_absolute() and resolve_home(None).name == ".pilot"


def test_a_missing_key_names_the_key(tmp_path):
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        Settings(home=tmp_path, provider="anthropic", anthropic_api_key="").validate()
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(home=tmp_path, provider="openai", openai_api_key="").validate()
    Settings(home=tmp_path, provider="openai", openai_api_key="k").validate()


def test_env_vars_drive_the_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PILOT_MAX_ITERATIONS", "7")
    monkeypatch.setenv("PILOT_MEMORY", "0")
    s = Settings(home=tmp_path)
    assert s.max_iterations == 7 and s.memory is False
