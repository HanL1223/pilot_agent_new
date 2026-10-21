"""Jira Cloud tools: two reads, two writes.

Jira's REST API v3, authenticated with your email + an API token (HTTP Basic auth).
Rich text (descriptions, comments) is ADF — Atlassian Document Format — a JSON
tree of nodes, not a plain string; `to_adf` and `adf_to_text` convert.

The docstring of each @tool is what the model reads to decide when and how to
call it. The `Args:` section becomes the description of each parameter.
"""

from __future__ import annotations

import os

import requests
from strands import tool

FIELDS = ["summary", "status", "assignee", "issuetype", "priority"]


# -- HTTP ------------------------------------------------------------------------

def _base() -> str:
    url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("JIRA_BASE_URL is not set (see .env.example)")
    return url


def _request(method: str, path: str, **kwargs) -> dict:
    resp = requests.request(method, _base() + path, timeout=30,
                            auth=(os.getenv("JIRA_EMAIL", ""), os.getenv("JIRA_API_TOKEN", "")),
                            headers={"Accept": "application/json"}, **kwargs)
    if resp.status_code >= 400:
        # Raise: Strands turns a tool's exception into an error result the model can read,
        # and it can often fix its own JQL or arguments.
        raise RuntimeError(f"Jira {method} {path} → {resp.status_code}: {resp.text[:300]}")
    return resp.json() if resp.content else {}


def project_key() -> str:
    return os.getenv("JIRA_PROJECT_KEY", "")


# -- ADF ---------------------------------------------------------------------------

def to_adf(text: str) -> dict:
    paragraphs = [p for p in text.split("\n\n") if p.strip()] or [""]
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": p}] if p else []} for p in paragraphs]}


def adf_to_text(node) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    inner = "".join(adf_to_text(child) for child in node.get("content", []))
    return inner + ("\n" if node.get("type") in ("paragraph", "heading", "listItem") else "")


def _line(issue: dict) -> str:
    f = issue.get("fields", {})
    assignee = (f.get("assignee") or {}).get("displayName", "unassigned")
    return (f"{issue['key']} [{(f.get('issuetype') or {}).get('name', '?')}] {f.get('summary', '')} "
            f"— {(f.get('status') or {}).get('name', '?')}, {assignee}")


# -- reads ---------------------------------------------------------------------------

@tool
def search_issues(jql: str, max_results: int = 20) -> str:
    """Search Jira issues with JQL and list them, one line each (key, type, summary, status, assignee).

    Use this for any question about which issues exist: "open bugs", "my tickets", "what's in progress".

    Args:
        jql: A JQL query, e.g. 'project = ABC AND statusCategory != Done ORDER BY updated DESC'.
        max_results: How many issues to return, 1-50.
    """
    data = _request("POST", "/rest/api/3/search/jql",
                    json={"jql": jql, "maxResults": max(1, min(max_results, 50)), "fields": FIELDS})
    issues = data.get("issues", [])
    return "\n".join(_line(i) for i in issues) if issues else "No issues match."


@tool
def get_issue(issue_key: str) -> str:
    """Read one Jira issue in full: summary, status, assignee, description and the latest comments.

    Args:
        issue_key: The issue key, e.g. 'ABC-123'.
    """
    data = _request("GET", f"/rest/api/3/issue/{issue_key}",
                    params={"fields": ",".join(FIELDS + ["description", "comment"])})
    f = data.get("fields", {})
    comments = (f.get("comment") or {}).get("comments", [])[-3:]
    parts = [_line(data), "", "Description:", adf_to_text(f.get("description")).strip() or "(none)"]
    for c in comments:
        author = (c.get("author") or {}).get("displayName", "someone")
        parts += ["", f"Comment by {author}:", adf_to_text(c.get("body")).strip()]
    return "\n".join(parts)


# -- writes (the harness pauses for approval before these run) -----------------------

@tool
def create_issue(summary: str, description: str = "", issue_type: str = "Task") -> str:
    """Create one Jira issue in the configured project.

    Args:
        summary: One-line title.
        description: Plain text; blank lines separate paragraphs.
        issue_type: 'Task', 'Bug' or 'Story'.
    """
    fields = {"project": {"key": project_key()}, "summary": summary, "issuetype": {"name": issue_type}}
    if description:
        fields["description"] = to_adf(description)
    data = _request("POST", "/rest/api/3/issue", json={"fields": fields})
    return f"Created {data.get('key')}." + (" (dry-run: nothing was sent)" if data.get("dry_run") else "")


@tool
def add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to one Jira issue.

    Args:
        issue_key: The issue key, e.g. 'ABC-123'.
        comment: Plain text; blank lines separate paragraphs.
    """
    data = _request("POST", f"/rest/api/3/issue/{issue_key}/comment", json={"body": to_adf(comment)})
    return f"Commented on {issue_key}." + (" (dry-run: nothing was sent)" if data.get("dry_run") else "")


# -- what the human reads before approving a write ---------------------------------

def describe_create(call: dict) -> str:
    a = call["args"]
    text = f"CREATE {a.get('issue_type', 'Task')} in {project_key() or '?'}: {a.get('summary', '')}"
    return text + (f"\n  {a['description']}" if a.get("description") else "")


def describe_comment(call: dict) -> str:
    a = call["args"]
    return f"COMMENT on {a.get('issue_key')}:\n  {a.get('comment', '')}"
