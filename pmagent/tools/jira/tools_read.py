"""Read-only Jira `@tool`s. Nothing in this module changes anything in Jira.

The split from `tools_write.py` is structural, not cosmetic: `gate.py` gates
writes by name (`WRITE_TOOL_NAMES`), and a tool that ends up in the wrong list
either bypasses the human approval gate or blocks a harmless read behind it.
`tests/test_agent_lanes.py` asserts this module's `READ_TOOLS` and
`tools_write.WRITE_TOOLS` agree with that set, so the file a tool lives in is
now the thing that decides its gate.

Read tools belong in *every* lane that could be asked for them — a read
withheld from the read-only query lane produces the same "I can't do that" as a
missing tool, with none of the safety justification.
"""
from __future__ import annotations

import json

from strands import tool

from pmagent import env
from pmagent.tools.jira.client import get_client
from pmagent.tools.jira.fields import build_issue_fields
from pmagent.tools.jira.jql import JqlBuilder
from pmagent.tools.jira.metrics import compute_sprint_metrics
from pmagent.tools.jira.render import (
    _DETAIL_MAX_ISSUES,
    format_candidates,
    format_issue_line,
    render_issue_detail,
    render_sprint_report,
)
from pmagent.tools.jira.validate import check_draft_standard, parse_drafts
