"""Dry-run: block every HTTP write made with `requests`, whichever tool makes it.

The block sits at the transport (the adapter every `requests` call goes
through), not inside each tool, so a tool you add later can't forget it.
GET/HEAD/OPTIONS pass. Other methods pass only if listed in `allow` as
"METHOD /path" — for APIs that read with POST (Jira search does). Everything
else gets a fake 200 reply saying it was not sent, and is printed.

The model's own API calls use httpx, not requests, so they are unaffected.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter

_original_send = HTTPAdapter.send
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def install(allow: set[str], log=print) -> None:
    def send(self, request, *args, **kwargs):
        path = urlsplit(request.url).path
        if request.method in SAFE_METHODS or f"{request.method} {path}" in allow:
            return _original_send(self, request, *args, **kwargs)
        log(f"[dry-run] blocked {request.method} {path}")
        fake = requests.Response()
        fake.status_code = 200
        fake.url = request.url
        fake.request = request
        fake._content = json.dumps({"dry_run": True, "key": "DRY-RUN", "id": "0"}).encode()
        fake.headers["Content-Type"] = "application/json"
        return fake

    HTTPAdapter.send = send


def uninstall() -> None:
    HTTPAdapter.send = _original_send
