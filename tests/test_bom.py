import xml.etree.ElementTree as ET
from datetime import datetime

from mcp_servers import bom_weather

# A cut-down copy of a real BOM précis file: one town, three periods.
SAMPLE = """<product><forecast>
  <area aac="VIC_PT042" description="Melbourne" type="location">
    <forecast-period index="0" start-time-local="2026-10-05T22:00:00+11:00" end-time-local="2026-10-06T00:00:00+11:00">
      <text type="precis">Clear.</text>
    </forecast-period>
    <forecast-period index="1" start-time-local="2026-10-06T00:00:00+11:00" end-time-local="2026-10-07T00:00:00+11:00">
      <text type="precis">Partly cloudy.</text>
      <text type="probability_of_precipitation">10%</text>
    </forecast-period>
    <forecast-period index="2" start-time-local="2026-10-07T00:00:00+11:00" end-time-local="2026-10-08T00:00:00+11:00">
      <element type="air_temperature_minimum" units="Celsius">9</element>
      <element type="air_temperature_maximum" units="Celsius">17</element>
      <text type="precis">Sunny.</text>
    </forecast-period>
  </area>
  <area aac="VIC_PW007" description="Central" type="public-district"/>
</forecast></product>"""


def test_towns_lists_only_locations():
    assert bom_weather.towns(ET.fromstring(SAMPLE)) == ["Melbourne"]


# 00:30 on Tue 6 Oct, Melbourne time: the file still starts with Monday evening.
NOW = datetime.fromisoformat("2026-10-06T00:30:00+11:00")


def test_forecast_labels_today_and_tomorrow():
    out = bom_weather.forecast(ET.fromstring(SAMPLE), "melbourne", days=2, now=NOW)
    assert "Tue 6 Oct (today): Partly cloudy. chance of rain 10%" in out
    assert "Wed 7 Oct (tomorrow): Sunny. min 9°C max 17°C" in out
    assert "Bureau of Meteorology" in out


def test_periods_that_have_ended_are_dropped():
    # The bug this fixes: after midnight, "tomorrow" was read off the wrong line.
    out = bom_weather.forecast(ET.fromstring(SAMPLE), "melbourne", days=3, now=NOW)
    assert "Clear." not in out and "Mon 5 Oct" not in out


def test_unknown_town_says_what_to_do():
    assert "list_towns" in bom_weather.forecast(ET.fromstring(SAMPLE), "Gotham", days=1, now=NOW)


def test_unknown_state_is_refused():
    try:
        bom_weather._product("XYZ")
    except ValueError as exc:
        assert "VIC" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_a_bad_state_comes_back_as_text_not_an_exception():
    # Through MCP an exception arrives as a bare "Error executing tool"; text the model can act on.
    assert "Use one of" in bom_weather.get_forecast("Melbourne", "XYZ")
    assert "Use one of" in bom_weather.list_towns("XYZ")
