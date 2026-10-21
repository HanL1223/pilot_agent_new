"""One run of the agent loop, and what its ending means.

Strands' `agent(prompt)` IS the loop: call the model → run the tools it asked
for → call the model again with the results → … until something stops it.
`result.stop_reason` says what stopped it; this file turns that into one of four
outcomes the rest of the harness understands:

    end_turn                         → "reply"   the model answered (guardrail 1)
    interrupt                        → "paused"  a write is waiting for a human
    limit_turns                      → "limit"   too many model calls (guardrail 2)
    limit_*_tokens, anything else    → "error"   say so; never pretend it answered

Limits apply per call of `agent(...)`, so a resume after an approval starts a
fresh count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

LIMIT_REPLY = "(I hit my step limit before finishing — try a smaller request.)"


def text_of(message: dict) -> str:
    return " ".join(b["text"] for b in message.get("content", []) if "text" in b).strip()


def assistant_message(text: str) -> dict:
    return {"role": "assistant", "content": [{"text": text}]}


@dataclass
class Outcome:
    kind: Literal["reply", "paused", "limit", "error"]
    stop_reason: str
    reply: str = ""
    interrupts: list = field(default_factory=list)


def run_turn(agent, prompt: Any, max_turns: int) -> Outcome:
    """`prompt` is the user's text, or a list of interruptResponse blocks when resuming."""
    result = agent(prompt, limits={"turns": max_turns})
    reason = result.stop_reason
    if reason == "end_turn":
        return Outcome("reply", reason, reply=text_of(result.message))
    if reason == "interrupt":
        return Outcome("paused", reason, interrupts=list(result.interrupts or []))
    if reason == "limit_turns":
        reply = LIMIT_REPLY
    elif reason in ("limit_output_tokens", "limit_total_tokens"):
        reply = f"(I hit the token budget for one turn: {reason}.)"
    else:
        reply = f"(The model stopped without finishing: {reason}.)"
    # The history may end on tool results; close it with an assistant message so
    # the next turn starts cleanly and the model knows it stopped early.
    if not agent.messages or agent.messages[-1]["role"] != "assistant":
        agent.messages.append(assistant_message(reply))
    return Outcome("limit" if reason == "limit_turns" else "error", reason, reply=reply)
