"""How an agent is described to the harness. The one seam you extend.

    ToolSpec       one local tool + whether it reads or writes
    MCPServerSpec  one MCP server to start, and which of its tools are read-only
    AgentSpec      name + system prompt + tools + MCP servers

An agent lives in `agents/<name>/agent.py` and exposes `AGENT = AgentSpec(...)`.
The harness loads it by name (env AGENT=<name>) and never imports it directly.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

Effect = Literal["read", "write"]


def default_describe(call: dict) -> str:
    """Approval text when a tool has no describe(): its name and arguments."""
    return f"{call['name']}({json.dumps(call['args'], ensure_ascii=False)})"


@dataclass(frozen=True)
class ToolSpec:
    tool: Any                                   # a function decorated with Strands' @tool
    effect: Effect
    describe: Callable[[dict], str] | None = None   # writes: what the human reads before approving

    @property
    def name(self) -> str:
        return self.tool.tool_name


@dataclass(frozen=True)
class MCPServerSpec:
    prefix: str                                 # tool names become "<prefix>_<remote name>"
    command: str
    args: tuple[str, ...] = ()
    read_tools: frozenset[str] = frozenset()    # FULL prefixed names a human reviewed as read-only


@dataclass(frozen=True)
class AgentSpec:
    name: str
    prompt: str
    tools: tuple[ToolSpec, ...] = ()
    mcp_servers: tuple[MCPServerSpec, ...] = ()
    http_reads: frozenset[str] = frozenset()    # "POST /path" calls that only read (allowed in dry-run)


def load_agent(name: str) -> AgentSpec:
    """Import agents/<name>/agent.py and return its AGENT."""
    module = importlib.import_module(f"agents.{name}.agent")
    agent = getattr(module, "AGENT", None)
    if not isinstance(agent, AgentSpec):
        raise TypeError(f"agents/{name}/agent.py must define AGENT = AgentSpec(...)")
    return agent


def validate(agent: AgentSpec, reserved: set[str]) -> None:
    """Refuse to start on a mistake that would otherwise surface mid-conversation."""
    names = [spec.name for spec in agent.tools]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"duplicate tool names: {sorted(duplicates)}")
    clashes = set(names) & reserved
    if clashes:
        raise ValueError(f"tool names reserved by the harness: {sorted(clashes)}")
    prefixes = [s.prefix for s in agent.mcp_servers]
    if len(prefixes) != len(set(prefixes)):
        raise ValueError(f"MCP prefixes must be unique: {prefixes}")
    for spec in agent.tools:
        if spec.effect not in ("read", "write"):
            raise ValueError(f"{spec.name}: effect must be 'read' or 'write'")
