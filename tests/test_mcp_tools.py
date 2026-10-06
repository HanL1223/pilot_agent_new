"""Lucid's MCP client: every page of tools is discovered, a failure is a warning
(never a crash), and no remote tool is a reviewed read until a human says so."""

from __future__ import annotations

import strands.tools.mcp as strands_mcp

from pmagent import env
from pmagent.tools import mcp_tools


class _Page(list):
    def __init__(self, items, token):
        super().__init__(items)
        self.pagination_token = token


class FakeClient:
    """Stands in for strands' MCPClient: two pages of tools, or a failing start."""

    instances: list = []

    def __init__(self, url=None, headers=None, fail=False):
        self.url, self.headers, self.fail = url, headers, fail
        self.started = self.stopped = False
        self.tokens = []
        FakeClient.instances.append(self)

    def start(self):
        if self.fail:
            raise ConnectionError("unreachable")
        self.started = True

    def list_tools_sync(self, pagination_token=None):
        self.tokens.append(pagination_token)
        return _Page(["a", "b"], "next") if pagination_token is None else _Page(["c"], None)

    def stop(self, *exc):
        self.stopped = True


def test_start_lucid_follows_every_page_of_tools(monkeypatch):
    FakeClient.instances = []
    monkeypatch.setattr(strands_mcp, "MCPClient", FakeClient)
    monkeypatch.setattr(env, "LUCID_MCP_AUTH_TOKEN", "tok")
    session = mcp_tools.start_lucid()
    client = FakeClient.instances[0]
    assert session.tools == ["a", "b", "c"] and client.tokens == [None, "next"]
    assert client.headers == {"Authorization": "Bearer tok"}
    session.close()
    assert client.stopped


def test_start_lucid_failing_is_a_warning_and_none_not_a_crash(monkeypatch, capsys):
    FakeClient.instances = []
    monkeypatch.setattr(strands_mcp, "MCPClient", lambda **kw: FakeClient(fail=True, **kw))
    assert mcp_tools.start_lucid() is None
    assert "Lucid MCP unavailable (ConnectionError: unreachable)" in capsys.readouterr().out
    assert FakeClient.instances[0].stopped          # no half-started thread is left behind


def test_no_mcp_tool_is_approved_as_a_read_until_a_human_reviews_it():
    assert mcp_tools.APPROVED_READ_TOOLS == frozenset()
