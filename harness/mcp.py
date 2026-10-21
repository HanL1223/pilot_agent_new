"""Start the agent's MCP servers and collect their tools.

MCP (Model Context Protocol) lets tools live in ANOTHER process. Our side is the
*client*: Strands' `MCPClient` launches the server program, talks to it over
stdin/stdout ("stdio transport"), asks it which tools it has, and wraps each one
so an Agent can call it exactly like a local `@tool`.

Lifecycle: `start_all()` once at startup, `stop()` at exit. We own the client
ourselves and pass only its *tools* to the Agent — passing the client too would
make the Agent try to start it a second time.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.tools.mcp import MCPClient

from harness.config import PROJECT_ROOT
from harness.spec import MCPServerSpec


@dataclass
class MCPConnection:
    spec: MCPServerSpec
    client: MCPClient
    tools: list

    def stop(self) -> None:
        self.client.stop(None, None, None)


def _command(spec: MCPServerSpec) -> str:
    # "python" means "the Python running this harness", so the server sees the same packages.
    return sys.executable if spec.command == "python" else spec.command


def start(spec: MCPServerSpec) -> MCPConnection:
    params = StdioServerParameters(command=_command(spec), args=list(spec.args), cwd=PROJECT_ROOT)
    client = MCPClient(lambda: stdio_client(params), prefix=spec.prefix)
    client.start()
    try:
        tools = client.list_tools_sync()
        names = {t.tool_name for t in tools}
        unknown = spec.read_tools - names
        if unknown:  # a typo here would silently gate a read forever; fail loudly instead
            raise ValueError(f"MCP '{spec.prefix}': read_tools not on the server: {sorted(unknown)}; "
                             f"it has {sorted(names)}")
    except Exception:
        client.stop(None, None, None)
        raise
    return MCPConnection(spec, client, list(tools))


def start_all(specs) -> list[MCPConnection]:
    started: list[MCPConnection] = []
    try:
        for spec in specs:
            started.append(start(spec))
    except Exception:
        for conn in started:
            conn.stop()
        raise
    return started
