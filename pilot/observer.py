"""One observer protocol for everything that watches a turn (plan §3.4).

    Observer = Callable[[kind, event], None]

Waku's idea: gateways show a turn live and ops records it, without either being
wired into the loop. Here the Strands side is one `ObserverHook` that turns hook
events into observer events; the CLI echo, the tracer and the event log (which
feeds the dashboard) are all just observers, joined with `compose`.

Events emitted by the hook:
    message    {message}                         every message Strands appends
    llm.start  {attempt}
    llm.end    {attempt, stop_reason, usage}     usage = THIS call's (see below)
    llm.end    {attempt, error, usage: None}     a failed model call
    tool_call  {id, name, args}                  once per toolUseId (re-fires on resume are deduped)
    tool       {id, name, status, output}

Usage is read from `stop_response.message["metadata"]["usage"]`, which Strands
sets just before AfterModelCallEvent. `event_loop_metrics` is only updated after
the event, so reading it here would report the previous call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from strands.hooks import (
    AfterModelCallEvent,
    AfterToolCallEvent,
    BeforeModelCallEvent,
    BeforeToolsEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

Observer = Callable[[str, dict], None]


def null_observer(kind: str, event: dict) -> None:
    return None


def compose(*observers: Observer | None) -> Observer:
    """Fan one event out to many observers. An observer that raises never
    breaks the turn (a display bug must not become a lost write)."""
    live = [o for o in observers if o is not None]

    def notify(kind: str, event: dict) -> None:
        for observer in live:
            try:
                observer(kind, event)
            except Exception:  # noqa: BLE001
                pass

    return notify


def _usage(raw: dict | None) -> dict:
    raw = raw or {}
    return {
        "input_tokens": raw.get("inputTokens", 0),
        "output_tokens": raw.get("outputTokens", 0),
        "total_tokens": raw.get("totalTokens", 0),
    }


class BlockTracker:
    """Names the assistant message being streamed. Every text/reasoning delta
    carries this `block_id`, and so does the finished `message` event that
    replaces them — a reader renders each block exactly once."""

    def __init__(self) -> None:
        self.current = ""
        self._n = 0

    def new(self) -> str:
        self._n += 1
        self.current = f"b{self._n}-{id(self):x}"
        return self.current


def stream_handler(get_notify: Callable[[], Observer], blocks: BlockTracker) -> Callable[..., None]:
    """A Strands callback_handler that turns streamed chunks into delta events."""

    def handle(**kwargs: Any) -> None:
        if kwargs.get("data"):
            get_notify()("text.delta", {"block_id": blocks.current, "delta": kwargs["data"]})
        elif kwargs.get("reasoningText"):
            get_notify()("reasoning.delta", {"block_id": blocks.current, "delta": kwargs["reasoningText"]})

    return handle


class ObserverHook(HookProvider):
    """Bridges Strands hook events to the current observer.

    `get_notify` is read at event time, so one long-lived lane agent can report
    to whichever gateway submitted the current job.
    """

    def __init__(self, get_notify: Callable[[], Observer], blocks: BlockTracker | None = None) -> None:
        self._get_notify = get_notify
        self._blocks = blocks or BlockTracker()
        self._seen_tool_uses: set[str] = set()
        self._attempt = 0

    def _notify(self, kind: str, event: dict[str, Any]) -> None:
        self._get_notify()(kind, event)

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(MessageAddedEvent, self._on_message)
        registry.add_callback(BeforeModelCallEvent, self._before_model)
        registry.add_callback(AfterModelCallEvent, self._after_model)
        registry.add_callback(BeforeToolsEvent, self._before_tools)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def _on_message(self, event: MessageAddedEvent) -> None:
        payload = {"message": event.message}
        if event.message.get("role") == "assistant":
            payload["block_id"] = self._blocks.current
        self._notify("message", payload)

    def _before_model(self, event: BeforeModelCallEvent) -> None:
        self._attempt += 1
        self._notify("llm.start", {"attempt": self._attempt, "block_id": self._blocks.new()})

    def _after_model(self, event: AfterModelCallEvent) -> None:
        if event.stop_response is None:
            self._notify("llm.end", {"attempt": self._attempt, "error": repr(event.exception), "usage": None})
            return
        metadata = event.stop_response.message.get("metadata") or {}
        self._notify("llm.end", {
            "attempt": self._attempt,
            "stop_reason": event.stop_response.stop_reason,
            "usage": _usage(metadata.get("usage")),
        })

    def _before_tools(self, event: BeforeToolsEvent) -> None:
        for block in event.message["content"]:
            use = block.get("toolUse")
            if use and use["toolUseId"] not in self._seen_tool_uses:
                self._seen_tool_uses.add(use["toolUseId"])
                self._notify("tool_call", {"id": use["toolUseId"], "name": use["name"], "args": use["input"]})

    def _after_tool(self, event: AfterToolCallEvent) -> None:
        result = event.result or {}
        self._notify("tool", {
            "id": event.tool_use["toolUseId"],
            "name": event.tool_use["name"],
            "status": result.get("status"),
            "output": result,
        })
