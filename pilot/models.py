"""Model construction — the one place a provider is chosen.

Models are *built*, never cached process-wide. Every Strands call runs
`asyncio.run` on a fresh thread, and `AnthropicModel` holds one `AsyncAnthropic`
client bound to whichever event loop first used it — so two conversations (or a
conversation and the consolidation worker) must never share one. Each
`ConversationRuntime` owns its main and small model; anything that needs a model
inside a tool asks for a fresh one through `invocation_state["build_model"]`.

Provider imports are lazy, so only the SDK you use needs to be installed.
"""

from __future__ import annotations

from typing import Literal

from strands.models import Model

from pilot.config import Settings

Which = Literal["main", "small"]

def build_model(settings: Settings, which: Which = "main") -> Model:
    model_id = settings.model if which == "main" else settings.small_model
    if settings.provider == 'anthropic':
        from strands.models.anthropic import AnthropicModel
        # Strands' AnthropicModel needs an explicit output cap; a full PRD is
        # long, and hitting the cap mid-answer raises MaxTokensReachedException.
        return AnthropicModel(
            client_args={"api_key":settings.anthropic_api_key},
            model_id=model_id,
            max_tokens=settings.max_tokens
        )

    if settings.provider =='openai':
        client_args = {"api_key":settings.openai_api_key}
        if settings.reasoning_effort == "none":
            from strands.models.openai import OpenAIModel
            # gpt-5.x rejects function tools on chat completions unless reasoning
            # is explicitly off, and Strands' structured output is itself a tool.
            return OpenAIModel(
                client_args= client_args,
                model_id=model_id,
                params={"reasoning_effort":"none", "temperature":0.1},
            )
        from strands.models.openai_responses import OpenAIResponsesModel
        reasoning = {"effort": settings.reasoning_effort}

        if settings.reasoning_summary:
            reasoning["summary"] = settings.reasoning_summary
        return OpenAIResponsesModel(client_args=client_args, model_id=model_id, params={"reasoning": reasoning})
    
    raise ValueError(f"Unknown LLM_PROVIDER={settings.provider!r}. Use 'anthropic' or 'openai'.")


def structured(schema, prompt: str, *, model: Model, system_prompt: str | None = None, usage_sink=None):
    """One stateless structured-output call: a fresh Agent, no history, no hooks,
    no printing — so its hidden output tool never lands in a conversation.
    Used by the harness's own small-model jobs (retrieval gate, consolidation)."""
    from strands import Agent

    agent = Agent(model=model, system_prompt=system_prompt, messages=[], callback_handler=None)
    result = agent(prompt, structured_output_model=schema)
    if usage_sink is not None:
        from pilot.loop import invocation_usage

        usage_sink(invocation_usage(result))
    return result.structured_output