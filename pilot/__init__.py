"""pilot — a local-first agent harness in the shape of Waku's four pillars
(Harness, Loop, Memory, Eval/LLM-Ops), with Strands Agents as the loop engine.

pilot knows nothing about Jira. A domain plugs in as one `CapabilityPack`
(`pilot/pack.py`); `pmagent/pack.py` is the first. The dependency only ever
points one way: pilot never imports pmagent (a test walks the imports).
"""

__version__ = "0.1.0"
