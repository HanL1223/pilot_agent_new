from __future__ import annotations

from collections.abc import Mapping

from strands.hooks import BeforeToolsEvent, HookProvider, HookRegistry

INTERRUPT_NAME = "approval"
APPROVE = "approve"
REJECT = "reject"

REJECTION_MESSAGE = (
    "The user rejected this action. Nothing was written. Ask what they would like changed."
)

def _is_registered(name:str, agent) -> bool:
    """True when `agent` would actually execute `name` (the executor's own lookup) """
    registry = agent.tool_registry
    return name in registry.dynamic_tools or name in registry.registry


def requires_approval(name:str, agent, effects: Mapping[str,str]) -> bool:
    if not _is_registered(name,agent):
        return False
    return effects.get(name) != 'read'

class ApprovalGate(HookProvider):
    def __init__(self,effects:Mapping[str,str]) -> None:
        self.effects = dict(effects)

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(BeforeToolsEvent, self.check_batch)

    def check_batch(self,event:BeforeToolsEvent) -> None:
        calls = [block["toolUse"] for block in event.message["content"] if "toolUse" in block]
        gated = [c for c in calls if requires_approval(c["name"],event.agent,self.effects)]
        if not gated:
            return
        reason = {"calls": [{"id": c["toolUseId"], "name": c["name"], "args": c["input"]} for c in gated]}
        answer = event.interrupt(INTERRUPT_NAME, reason=reason)
        if answer != APPROVE:
            event.cancel = REJECTION_MESSAGE