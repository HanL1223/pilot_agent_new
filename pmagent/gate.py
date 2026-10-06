"""
Which of PO Agent's tools write — the domain half of the approval gate.

The gate itself is the harness's (`pilot/gate.py`): a Strands `BeforeToolsEvent`
hook that interrupts any tool batch containing a call this LANE does not declare
as a read. This module is the declaration it is built from, kept here because
only the domain knows what its tools do:

* `TOOL_MODULES` — every module that defines tools. Each declares `READ_TOOLS`
  and `WRITE_TOOLS`; `pmagent/pack.py` derives each tool's effect from them.
* `WRITE_TOOL_NAMES` — the same writes, listed by hand. Kept explicit (not
  derived) so adding a write is a deliberate two-place change: the tests fail
  until the module list and this set agree, and until the write has an
  approval describer in `pmagent/approval_text.py`.
* `READ_TOOL_NAMES` — every declared read, plus MCP tools a human reviewed.
"""

from __future__ import annotations

from pmagent.tools import (
    confluence_tools,
    diagram_tools,
    finance_tools,
    mcp_tools,
    spreadsheet_tools,
)
from pmagent.tools.jira import tools_read as jira_read
from pmagent.tools.jira import tools_write as jira_write

# Every module that defines @tools. Each declares READ_TOOLS and WRITE_TOOLS;
# tests/test_agent_lanes.py walks pmagent/tools/ and fails if one is missing here.
TOOL_MODULES = (
    jira_read,
    jira_write,
    confluence_tools,
    diagram_tools,
    finance_tools,
    spreadsheet_tools,
)

# Tools that change something outside this process. Anything listed here runs
# only after a human has approved it. Kept explicit (not derived from
# WRITE_TOOLS) so adding a write tool is a deliberate two-place change that the
# tests reconcile.
WRITE_TOOL_NAMES = frozenset({
    "create_jira_issues",
    "create_jira_issue",
    "assign_jira_issue",
    "update_jira_issue",
    "add_jira_comment",
    "transition_jira_issues",
    "move_jira_issues_to_sprint",
    "remove_jira_issues_from_sprint",
    "propose_spreadsheet_cell_update",
    "apply_approved_spreadsheet_updates",
    "prepare_spreadsheet_approval_queue",
    # Writes a CSV of real financial figures plus its audit sidecar. "Outside
    # this process" includes the local filesystem — a generated budget file gets
    # ingested into Snowflake, so producing one is not a preview.
    "create_fy_budget_csv",
})

# Tools that may run without asking: every module's declared reads, plus MCP
# tools a human has reviewed.
READ_TOOL_NAMES = frozenset(
    {t.tool_name for module in TOOL_MODULES for t in module.READ_TOOLS}
    | mcp_tools.APPROVED_READ_TOOLS
)
