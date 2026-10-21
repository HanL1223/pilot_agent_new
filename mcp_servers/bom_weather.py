"""An MCP server for Australian weather forecasts from the Bureau of Meteorology (BOM).

Run on its own to see it work:   uv run python -m mcp_servers.bom_weather --demo Melbourne VIC
The agent starts it for you as a subprocess and talks to it over stdin/stdout.

Data: BOM's public "précis" forecast product, one XML file per state on its
anonymous FTP server, ~7 days for every forecast town. Free to read; keep the
BOM copyright line when you show it. Refreshed by BOM several times a day, so we
cache each file for 10 minutes.

mcp 2.x note: the server class is `MCPServer`. Tutorials written for mcp 1.x
call it `FastMCP` (`from mcp.server.fastmcp import FastMCP`); that import fails on 2.x.
"""

from __future__ import annotations

import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from mcp.server.mcpserver import MCPServer

PRODUCTS = {  # state → précis forecast product id
    "NSW": "IDN11060", "ACT": "IDN11060", "VIC": "IDV10753", "QLD": "IDQ11295",
    "SA": "IDS10044", "TAS": "IDT16710", "WA": "IDW14199", "NT": "IDD10207",
}
URL = "ftp://ftp.bom.gov.au/anon/gen/fwo/{product}.xml"
CACHE_SECONDS = 600
ATTRIBUTION = "Source: Australian Bureau of Meteorology (bom.gov.au)."

_cache: dict[str, tuple[float, ET.Element]] = {}


def fetch(product: str) -> ET.Element:
    hit = _cache.get(product)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    with urllib.request.urlopen(URL.format(product=product), timeout=30) as resp:
        root = ET.fromstring(resp.read())
    _cache[product] = (time.time(), root)
    return root


def _product(state: str) -> str:
    product = PRODUCTS.get(state.strip().upper())
    if product is None:
        raise ValueError(f"Unknown state {state!r}. Use one of: {', '.join(PRODUCTS)}.")
    return product


def towns(root: ET.Element) -> list[str]:
    return sorted(a.get("description") for a in root.iter("area") if a.get("type") == "location")


def _label(day, today) -> str:
    """'Thu 8 Oct (today)': a model reads a weekday and 'today/tomorrow' far more reliably than a bare date."""
    text = f"{day:%a} {day.day} {day:%b}"
    offset = (day - today).days
    return text + {0: " (today)", 1: " (tomorrow)"}.get(offset, "")


def forecast(root: ET.Element, town: str, days: int, now: datetime | None = None) -> str:
    area = next((a for a in root.iter("area")
                 if a.get("type") == "location" and a.get("description", "").lower() == town.strip().lower()),
                None)
    if area is None:
        return f"No BOM forecast town called {town!r} in this state. Use list_towns to see the names."
    periods = area.findall("forecast-period")
    # The file can be hours old: after midnight its first period is often "yesterday evening".
    # Drop every period that has already ended, so the first line is always today.
    now = now or datetime.now(UTC)
    current = [p for p in periods
               if not p.get("end-time-local") or datetime.fromisoformat(p.get("end-time-local")) > now]
    if not current:
        return "BOM's forecast file is out of date; try again later."
    tz = datetime.fromisoformat(current[0].get("start-time-local")).tzinfo
    today = now.astimezone(tz).date()
    lines = [f"Forecast for {area.get('description')} (local time now {now.astimezone(tz):%a %d %b %H:%M}):"]
    for period in current[: max(1, min(days, 7))]:
        values = {e.get("type"): e.text for e in period}
        day = datetime.fromisoformat(period.get("start-time-local")).date()
        low, high = values.get("air_temperature_minimum"), values.get("air_temperature_maximum")
        temps = " ".join(t for t in [f"min {low}°C" if low else "", f"max {high}°C" if high else ""] if t)
        rain = values.get("probability_of_precipitation")
        details = [d for d in [temps, f"chance of rain {rain}" if rain else ""] if d]
        lines.append(f"- {_label(day, today)}: {values.get('precis', 'no summary')} {', '.join(details)}".rstrip())
    return "\n".join(lines + [ATTRIBUTION])


server = MCPServer("bom-weather")


@server.tool()
def list_towns(state: str) -> str:
    """List the towns that have a BOM forecast in one Australian state or territory.

    Args:
        state: NSW, ACT, VIC, QLD, SA, TAS, WA or NT.
    """
    try:
        names = towns(fetch(_product(state)))
    except ValueError as exc:
        return str(exc)      # return it: an exception's message does not travel through MCP
    return f"{len(names)} forecast towns in {state.upper()}: " + ", ".join(names)


@server.tool()
def get_forecast(town: str, state: str, days: int = 3) -> str:
    """Get the BOM forecast for a town: daily summary, min/max temperature, chance of rain.

    Args:
        town: Town name as BOM spells it, e.g. 'Melbourne', 'Sydney', 'Alice Springs'.
        state: NSW, ACT, VIC, QLD, SA, TAS, WA or NT.
        days: Number of days, 1-7, starting today.
    """
    try:
        return forecast(fetch(_product(state)), town, days)
    except ValueError as exc:
        return str(exc)      # e.g. "Unknown state 'XYZ'. Use one of: NSW, ACT, …" so the model can retry


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--demo":
        print(get_forecast(sys.argv[2], sys.argv[3]))
    else:
        server.run()   # stdio: read requests on stdin, write replies on stdout
