"""
The one helper for stateless structured-output calls — and nothing else.

Model CONSTRUCTION belongs to the harness (`pilot/models.py`, plan D11): it knows
the provider, the keys and which model each caller should own. The domain only
ever receives a model — the router, the PRD writer/reviewer and the diagram
brief all get theirs passed in — so this module reads no configuration at all.

STRANDS CONCEPT — structured output. Passing `structured_output_model=` to an
agent call makes Strands give the model a hidden tool whose input schema is the
Pydantic model, and validate what comes back. A *fresh* Agent is built every
call, on purpose:
  - `callback_handler=None` — nothing is printed;
  - a new, empty message list — these are stateless jobs, and their hidden tool
    traffic must never leak into the conversation the user is having;
  - no hooks — in particular no approval gate: there is nothing to approve.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel
from strands import Agent
from strands.models import Model


def structured[T: BaseModel](
    schema: type[T],
    prompt: str,
    system_prompt: str | None = None,
    model: Model | None = None,
    usage_sink: Callable[[dict], None] | None = None,
) -> T:
    """Ask `model` for one instance of `schema`. Stateless: one prompt in, one object out."""
    if model is None:
        raise ValueError("structured() needs a model: the harness passes one (pilot/models.py).")
    agent = Agent(model=model, system_prompt=system_prompt, messages=[], callback_handler=None)
    result = agent(prompt, structured_output_model=schema)
    if usage_sink is not None:
        usage_sink(invocation_usage(result))
    return result.structured_output


def invocation_usage(result) -> dict:
    """Token usage of the invocation that produced `result` (not the agent's lifetime)."""
    invocation = result.metrics.latest_agent_invocation
    usage = dict(invocation.usage) if invocation else {}
    return {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "total_tokens": usage.get("totalTokens", 0),
        "model_calls": len(invocation.cycles) if invocation else 0,
    }
