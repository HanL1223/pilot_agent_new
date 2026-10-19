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

