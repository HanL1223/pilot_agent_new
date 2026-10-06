"""THE LOOP — one Strands invocation, with Waku's two guardrails named.

Strands' `Agent.__call__` is the whole observe → reason → act → repeat loop.
    guardrail 1  the model stops asking for tools   → stop_reason "end_turn"
    guardrail 2  the iteration cap                  → stop_reason "limit_turns"
                 (Strands' native limits={"turns": N}; tools that the previous
                 turn requested always finish first, so history stays reinvokable)

    pause        a write needs a human              → stop_reason "interrupt"

Every stop reason maps to exactly one outcome (plan D1). `max_tokens` never
comes back as a result — Strands raises MaxTokensReachedException, which the
caller handles as an exception. Never call `agent.cancel()` on a lane agent: it
can skip the end of a tool cycle and leave interrupt state behind.
"""


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pilot.runtime.messages import assistant_message, text_of

ITERATION_LIMIT_REPLY = (
    "(I hit my iteration limit before finishing — try breaking the request into smaller steps.)"
)

Kind = Literal["reply", "pending", "error", "cancelled"]

@dataclass
class LoopOutcome:
    kind: Kind
    stop_reason: str
    reply: str
    interrupts: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)

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

def run_turn(agent, prompt: Any, *, max_iterations: int, invocation_state: dict | None = None) -> LoopOutcome:
    """Run the agent once (a new prompt, or a list of interruptResponse blocks)."""
    result = agent(prompt, invocation_state=invocation_state or {}, limits={"turns": max_iterations})
    usage = invocation_usage(result)
    reason = result.stop_reason

    if reason == "interrupt":
        return LoopOutcome("pending", reason, interrupts=list(result.interrupts or []), usage=usage)
    if reason == "end_turn":
        return LoopOutcome("reply", reason, reply=text_of(result.message), usage=usage)
    if reason == "cancelled":
        return LoopOutcome("cancelled", reason, usage=usage)
    if reason == "limit_turns":
        # messages[-1] is a toolResult here; answer it so roles alternate and the
        # model knows, next turn, that it stopped rather than finished.
        agent.messages.append(assistant_message(ITERATION_LIMIT_REPLY))
        return LoopOutcome("error", reason, reply=ITERATION_LIMIT_REPLY, usage=usage)

    # content_filtered, guardrail_intervened, stop_sequence, limit_*_tokens, and
    # anything a future Strands adds: say so, never pretend it was an answer.
    reply = f"(The model stopped without finishing: {reason}.)"
    if agent.messages and agent.messages[-1].get("role") != "assistant":
        agent.messages.append(assistant_message(reply))
    return LoopOutcome("error", reason, reply=reply, usage=usage)