from strands import Agent

from harness.loop import LIMIT_REPLY, run_turn
from harness.scripted import ScriptedModel, call, text
from tests.helpers import read_thing


def test_end_turn_is_a_reply():
    agent = Agent(model=ScriptedModel([[text("hi")]]), callback_handler=None)
    out = run_turn(agent, "hello", 5)
    assert (out.kind, out.reply) == ("reply", "hi")


def test_the_turn_limit_stops_a_runaway_loop():
    replies = [[call("read_thing", name=str(i))] for i in range(10)]
    agent = Agent(model=ScriptedModel(replies), tools=[read_thing], callback_handler=None)
    out = run_turn(agent, "loop forever", 3)
    assert out.kind == "limit" and out.reply == LIMIT_REPLY
    assert agent.messages[-1]["role"] == "assistant"     # history ends cleanly
