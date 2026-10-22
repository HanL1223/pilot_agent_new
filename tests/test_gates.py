from strands import Agent

from harness.gate import APPROVE, REJECT, ApprovalGate
from harness.loop import run_turn
from harness.scripted import ScriptedModel, call, text
from tests.helpers import WRITES, read_thing, write_thing


def agent_with(replies):
    WRITES.clear()
    model = ScriptedModel(replies)
    return Agent(model=model, tools=[read_thing, write_thing], hooks=[ApprovalGate({"read_thing"})],
                 callback_handler=None)


def answer(outcome, response):
    return [{"interruptResponse": {"interruptId": i.id, "response": response}} for i in outcome.interrupts]


def test_a_read_runs_without_asking():
    out = run_turn(agent_with([[call("read_thing", name="a")], [text("ok")]]), "go", 5)
    assert out.kind == "reply"


def test_a_write_pauses_before_it_runs():
    out = run_turn(agent_with([[call("write_thing", name="a")], [text("done")]]), "go", 5)
    assert out.kind == "paused" and WRITES == []


def test_approve_runs_the_write_once():
    agent = agent_with([[call("write_thing", name="a")], [text("done")]])
    out = run_turn(agent, answer(run_turn(agent, "go", 5), APPROVE), 5)
    assert out.kind == "reply" and WRITES == ["a"]


def test_reject_never_runs_it_and_tells_the_model():
    agent = agent_with([[call("write_thing", name="a")], [text("ok")]])
    run_turn(agent, answer(run_turn(agent, "go", 5), REJECT), 5)
    assert WRITES == []
    assert "rejected" in str(agent.messages[-2]["content"])


def test_a_second_write_in_the_same_turn_asks_again():
    # Strands forgets an answered interrupt once its batch has run, so the first "approve"
    # is not reused: the second write pauses again.
    agent = agent_with([[call("write_thing", name="a")], [call("write_thing", name="b")], [text("done")]])
    out = run_turn(agent, answer(run_turn(agent, "go", 5), APPROVE), 5)
    assert out.kind == "paused" and WRITES == ["a"]


def test_one_write_gates_the_whole_batch():
    agent = agent_with([[call("read_thing", name="r"), call("write_thing", name="w")], [text("x")]])
    out = run_turn(agent, "go", 5)
    assert out.kind == "paused"
    assert [c["name"] for c in out.interrupts[0].reason["calls"]] == ["write_thing"]


def test_an_unknown_tool_is_not_gated():
    out = run_turn(agent_with([[call("no_such_tool")], [text("sorry")]]), "go", 5)
    assert out.kind == "reply"
