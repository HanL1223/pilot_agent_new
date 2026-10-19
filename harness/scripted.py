"""A fake Strands model that replays a script — tests and offline demos, no API key.

A Strands `Model` only has to stream events in this order:

    messageStart → (contentBlockStart → contentBlockDelta → contentBlockStop)* → messageStop → metadata

The real agent loop, hooks and interrupts run unchanged on top; only the model's
choices are canned. Each script entry is one model reply: a list of blocks made
with `text(...)` and `call(...)`.
"""

from __future__ import annotations

import copy
import itertools
import json
from typing import Any

from strands.models import Model

_ids = itertools.count(1)


def text(value: str) -> dict:
    return {"text": value}


def call(tool: str, /, **args: Any) -> dict:
    return {"toolUse": {"name": tool, "toolUseId": f"tooluse_{next(_ids)}", "input": args}}


class ScriptedModel(Model):
    def __init__(self, replies: list | None = None) -> None:
        self.replies = list(replies or [])
        self.requests: list[dict] = []          # what the model was shown, per call
        self.config = {"model_id": "scripted"}

    def update_config(self, **config: Any) -> None:
        self.config.update(config)

    def get_config(self) -> dict:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        raise NotImplementedError
        yield  # makes this an async generator, as the base class expects

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.requests.append({"system_prompt": system_prompt, "messages": copy.deepcopy(messages),
                              "tools": [t["name"] for t in tool_specs or []]})
        reply = self.replies.pop(0) if self.replies else [text("(script finished)")]
        blocks = reply(messages) if callable(reply) else reply
        yield {"messageStart": {"role": "assistant"}}
        for block in blocks:
            if "text" in block:
                yield {"contentBlockStart": {"start": {}}}
                yield {"contentBlockDelta": {"delta": {"text": block["text"]}}}
            else:
                use = block["toolUse"]
                yield {"contentBlockStart": {"start": {"toolUse": {"name": use["name"],
                                                                   "toolUseId": use["toolUseId"]}}}}
                yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(use["input"])}}}}
            yield {"contentBlockStop": {}}
        stop = "tool_use" if any("toolUse" in b for b in blocks) else "end_turn"
        yield {"messageStop": {"stopReason": stop}}
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                            "metrics": {"latencyMs": 1}}}
