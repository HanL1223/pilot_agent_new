"""A tiny agent for tests: one read tool, one write tool that records what it wrote."""

from strands import tool

from harness.spec import AgentSpec, ToolSpec

WRITES: list[str] = []


@tool
def read_thing(name: str) -> str:
    """Read a thing.

    Args:
        name: Which thing.
    """
    return f"{name} is fine"


@tool
def write_thing(name: str) -> str:
    """Write a thing.

    Args:
        name: Which thing.
    """
    WRITES.append(name)
    return f"wrote {name}"


TEST_AGENT = AgentSpec(
    name="test",
    prompt="You are a test agent.",
    tools=(ToolSpec(read_thing, "read"),
           ToolSpec(write_thing, "write", describe=lambda c: f"WRITE {c['args']['name']}")),
)


