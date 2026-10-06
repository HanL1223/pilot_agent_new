"""Readers over Strands' (Bedrock Converse) message shape, plus the one writer
the harness needs: closing tool calls that will never get a real result.

    {"role": "user"|"assistant", "content": [block, ...]}
    block: {"text"} | {"toolUse": {toolUseId, name, input}} | {"toolResult": {...}} | {"image"} ...

Tool results are `role: "user"` messages, so "the last user message" is not
"the last thing the human typed" — `last_user_text` skips them.
"""

from __future__ import annotations

ABANDONED_MESSAGE = (
    "Not executed — the approval for this action was abandoned before the user answered. "
    "Nothing was written."
)
OUTCOME_UNKNOWN_MESSAGE = (
    "Outcome unknown — this write may have run before the turn stopped. Verify in Jira before retrying."
)


def blocks(message:dict) -> list[dict]:
    return message.get("content") or []

def text_of(message: dict) -> str:
    return " ".join(b["text"] for b in blocks(message) if "text" in b).strip()

def tool_uses(message: dict) -> list[dict]:
    return [b["toolUse"] for b in blocks(message) if "toolUse" in b]

def tool_results(message: dict) -> list[dict]:
    return [b["toolResult"] for b in blocks(message) if "toolResult" in b]

def is_tool_result(message: dict) -> bool:
    return message.get("role") == "user" and bool(tool_results(message))


def last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and not is_tool_result(message):
            text = text_of(message)
            if text:
                return text
    return ""


def user_message(text: str) -> dict:
    return {"role": "user", "content": [{"text": text}]}

def assistant_message(text: str) -> dict:
    return {"role": "assistant", "content": [{"text": text}]}


def result_text(result: dict) -> str:
    parts: list[str] = []
    for block in result.get("content") or []:
        if "text" in block:
            parts.append(block["text"])
        elif "image" in block:
            parts.append(f"[image: {block['image'].get('format', '?')}]")
        elif "json" in block:
            parts.append(str(block["json"]))
        elif "document" in block:
            parts.append("[document]")
    return "\n".join(parts)


def close_unanswered_tool_calls(messages: list[dict], text: str) -> int:
    """Give every unanswered call in the last assistant turn an explicit error
    result carrying `text`. Mutates `messages` in place; returns how many.

    Keeps the toolUse itself (providers reject a result with no call, and a call
    with no result). Adds nothing when every call already has a result — e.g. a
    resume that failed after the tools ran. Strands would otherwise auto-close
    them with a generic "Tool was interrupted.", which tells the user nothing.
    """
    last = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "assistant"), None)
    if last is None:
        return 0
    wanted = [use["toolUseId"] for use in tool_uses(messages[last])]
    answered = {r["toolUseId"] for m in messages[last + 1:] for r in tool_results(m)}
    missing = [i for i in wanted if i not in answered]
    if missing:
        messages.append({"role": "user", "content": [
            {"toolResult": {"toolUseId": i, "status": "error", "content": [{"text": text}]}} for i in missing
        ]})
    return len(missing)
